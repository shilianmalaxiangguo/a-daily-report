# Design: 市场语言翻译接入日报与 LLM Wiki

## Scope And Boundaries

本设计增加一个独立、只读的市场语言研究产物，用现有市场、板块、个股和可追溯分钟事实描述合力范围、价格压力方向与阶段。它不进入 `data`、`market_research_snapshot` 或 `execution_stage_context`，也不参与候选、仓位、B1/B2 或买卖动作计算。

第一版不新增外部数据源。分钟事实不存在时，产物降级为日终概览或事实不足，不能从日线插值候选时刻。第一版只展示证据与下一窗口复核任务，不生成、保留、取消或调整任何正式动作。

## Runtime Order

真实报告会用同一份可变 `data` 连续生成完整版和摘要版，而现有市场研究区的第一次渲染早于最终对象解析。因此本任务不复用早期 `market_research_snapshot` 节点，采用以下顺序：

```text
日报命令入口 / AgentRunner / replay 入口
  -> 从原始 data 提取不可变的 market_language_source_projection
  -> 只准备一次 market_language_translation.v1，并保留在入口局部变量
  -> build_report_outputs 接收显式 artifact
  -> 完整版与摘要版各接收一份深拷贝，只能读取

每次 report runtime
  -> 原有 execution stages
  -> 第二次 selection_workflow / final_target_resolution 解析完成
  -> 构建 final front page snapshot
  -> render_front_page_v2(..., market_language_translation=artifact)
  -> 在最终前台的证据区渲染

两种版本生成 + 日报检查 + 整日事实同步均通过
  -> fresh 入口独立提交 market_language_translation.v1
  -> replay 入口只保存 replay 副本，不覆盖 fresh
```

研究产物可以在正式决定之前完成计算，但它从不进入正式决定输入；只有展示发生在第二次最终对象解析之后。这样比把产物写入共享字典再依赖调用顺序更可验证。

## Contracts / Data Flow

```text
目标日期日终事实 + 可选目标日期分钟事实 + 来源元数据
  -> 市值加权 / 全市场宽度 / 板块同步三层对照
  -> 多轮候选、确认、失效与阶段切换
  -> market_language_translation.v1
  -> 显式只读参数
  -> 最终前台“市场语言翻译（研究证据）”
  -> 独立 artifact writer
  -> replay 目标日期 loader + 事后验收

selection_workflow / final_target_resolution / 仓位 / B1-B2 / 退出动作
  -> 不读取 market_language_translation.v1
```

## Artifact Contract

### `market_language_translation.v1`

```json
{
  "schema_version": "market_language_translation.v1",
  "target_date": "YYYY-MM-DD",
  "as_of_time": "15:00",
  "analysis_mode": "fresh|replay",
  "artifact_origin": "computed|loaded|reconstructed",
  "data_granularity": "one_minute|five_minute|end_of_day|mixed",
  "evidence_status": "sufficient|partial|insufficient",
  "missing_evidence": [],
  "force_scope": "index_weighted|single_stock|single_sector|multi_sector|whole_market|unclear",
  "pressure_direction": "upward|downward|balanced|unclear",
  "phase": "trigger|expansion|crowding|decay|cascade|repair|unclear",
  "phase_label": "",
  "timeline": {
    "first_candidate_at": null,
    "latest_confirmed_at": null,
    "candidate_invalidations": 0,
    "latest_transition_at": null,
    "events": []
  },
  "aggregation_comparison": {
    "cap_weighted": {},
    "market_breadth": {},
    "sector_synchrony": {}
  },
  "price_pressure": {},
  "participation": {},
  "liquidity_proxies": {},
  "fixed_window_observations": [],
  "evidence": [],
  "counter_evidence": [],
  "next_window_task": "",
  "posthoc_validation": null,
  "sources": []
}
```

### Source Records

每个输入来源必须先登记，再由派生字段通过 `source_refs` 引用：

| 字段 | 类型 | 含义 |
|------|------|------|
| `source_id` | string | artifact 内稳定编号 |
| `provider` | string | PostgreSQL、官方快照或明确行情来源 |
| `target_date` | date | 本次判断日期 |
| `source_date` | date | 来源事实所属交易日 |
| `query_date` | date | 实际查询或冻结日期 |
| `granularity` | enum | `one_minute/five_minute/end_of_day` |
| `time_semantics` | string | bar 开始、bar 结束、日终或累计口径 |
| `fields` | string[] | 该来源实际提供的字段 |
| `content_hash` | string/null | 冻结输入可用时保存哈希 |

`source_date != target_date` 的行情、宽度、板块或分钟事实不得进入派生判断。`query_date` 可以为 `null`；非空值必须是严格的 `YYYY-MM-DD`、不得早于 `source_date`，也不能替代 `source_date`。`market_stats` 的 `trade_date/source_date` 由执行精确日期查询的 Tushare 或 PostgreSQL 生产端写入；翻译层不得从外层报告日期继承。既有板块成交占比行可能使用 `18.1%` 展示值，source projection 只在该百分数可解析且日期、板块身份都匹配时将其规范化为百分点浮点数。

### Timeline Events

`timeline.events[]` 每一轮候选独立保存，不用最后成功的一次覆盖此前失败：

| 字段 | 含义 |
|------|------|
| `event_id` | 本轮稳定编号 |
| `candidate_at` | 第一根满足候选条件的分钟结束时点 |
| `detected_at` | 运行时首次可以发出候选的时点，不得早于 `candidate_at` |
| `confirmed_at` | 连续证据满足确认条件的时点，可为空 |
| `invalidated_at` | 该轮候选失效时点，可为空 |
| `causal_cutoff` | 构造该记录时允许读取的最后时点 |
| `pressure_direction` | `upward/downward/balanced/unclear` |
| `phase` | 当时阶段，不使用收盘后最佳公式回填 |
| `confirmation_basis` | 固定为三根重叠十五分钟斜率方向连续；不冒充三份独立证据 |
| `confirmation_quality` | `unconfirmed/slope_persistence_only/directional_follow_through` |
| `directional_follow_through_at` | 候选后价格首次达到同向延续条件的时点，可早于或晚于 `confirmed_at` |
| `evidence_refs` | 当时证据编号 |

改变 `causal_cutoff` 之后的数据不能修改已保存事件的候选、确认或失效时点；新数据只能追加后续事件或更新仍未结束事件的允许字段。

### Derived Field Units

| 容器 | 最小子字段 | 单位与时间语义 |
|------|------------|----------------|
| `aggregation_comparison.cap_weighted` | `return_pct`, `slope_bp_per_min`, `source_refs`, `as_of_time` | 百分比、bp/交易分钟 |
| `aggregation_comparison.market_breadth` | `advance_ratio_pct`, `median_return_pct`, `synchronized_down_pct`, `source_refs`, `as_of_time` | 百分比；缺失保持 `null` |
| `aggregation_comparison.sector_synchrony` | `leading_sector`, `active_constituent_pct`, `cross_sector_sync_pct`, `source_refs`, `as_of_time` | 百分比；明确样本范围 |
| `price_pressure` | `slope_5m_bp_per_min`, `slope_10m_bp_per_min`, `slope_20m_bp_per_min`, `slope_change_bp_per_min`, `curvature_bp_per_min2`, `drawdown_from_known_high_pct`, `failed_rebound_count`, `source_refs`, `as_of_time` | 只用 `as_of_time` 以前数据；曲率代理用未舍入值判断 |
| `participation` | `sector_turnover_share_pct`, `sector_turnover_share_change_pp`, `breadth_change_pp`, `core_follower_spread_pct`, `rival_relative_strength_pct`, `source_refs`, `as_of_time` | 占比、百分点、相对收益 |
| `liquidity_proxies` | `impact_per_100m_turnover_bp`, `impact_reversion_ratio`, `below_vwap_dwell_minutes`, `is_proxy`, `source_refs`, `as_of_time` | 代理字段；指数 VWAP 缺失时保持 `null` |
| `fixed_window_observations[]` | `window`, `observation_prefix`, `as_of_time`, `pressure_direction`, `phase`, `evidence_refs`, `counter_evidence_refs` | 只保存窗口截止时已知事实 |
| `evidence[]/counter_evidence[]` | `evidence_id`, `fact`, `as_of_time`, `source_refs` | 可追溯事实，不保存未来解释 |

## Scope And Phase Rules

### 合力范围

- `index_weighted`：只有市值加权指数事实，或权重与宽度不一致。
- `single_stock`：只有单股路径。
- `single_sector`：一个板块内部同步成立。
- `multi_sector`：多个板块同步，但全市场宽度仍不完整；必须有数值化跨板块同步证据，且板块方向必须与产物当前方向一致。
- `whole_market`：市值加权指数、全市场宽度和多板块同步三层同向；`cross_sector_sync_pct >= 50%` 只作过半同向的语义下限，裸方向文字不能成立。
- `unclear`：证据互相冲突或关键数据缺失。

上证指数形状不能单独生成 `whole_market`。

### 方向与阶段合法组合

| `pressure_direction` | 允许阶段 | 语义 |
|----------------------|----------|------|
| `upward` | `trigger`, `expansion`, `crowding`, `decay`, `repair` | 向上启动/扩散/高位拥挤/向上合力衰减，或此前向下压力后的修复 |
| `downward` | `trigger`, `expansion`, `decay`, `cascade` | 向下压力启动/扩散/边际衰减，或向下反馈加速 |
| `balanced` | `unclear` | 多空接近平衡，不强行命名阶段 |
| `unclear` | `unclear` | 方向或事实不足 |

`crowding` 不用于向下路径；向下反馈加速写 `cascade`。`decay` 必须写清是向上合力衰减还是向下压力衰减，后者不等于修复。

## Time Contract

### 固定时间钟

- `09:30-09:35`：开盘冲击、竞价表态与首五分钟承接。
- `09:45-09:50`：只记录前哨证据，为下一正式窗口准备，不写新增买卖动作。
- `09:50-10:10`：普通结构的早盘二次确认。
- `14:30-14:55`：已观察一整天后的尾部确认、风险复核或隔夜研究。

### 事件时间钟

全天连续记录 `candidate -> confirmed -> invalidated -> re_candidate -> transition`。`10:10-11:00` 与 `13:00-14:30` 的事件只进入观察记录，等下一正式窗口或下一份日报处理。

方向与短长斜率比较使用 `0.05 bp/交易分钟` 噪声带。`confirmed_at` 只表示三根重叠十五分钟斜率方向连续；若没有候选后价格同向延续，`confirmation_quality` 保持 `slope_persistence_only`。已确认事件最多容忍两分钟中性区，第三分钟才失效；相反方向立即失效。

二十分钟曲率代理统一为 `kappa20(t) = [s5(t) - s5(t-15)] / 15`，其中 `s5` 是六个收盘点拟合的五交易分钟对数价格斜率。正式产物和论文生成器复用同一函数，分类前不舍入。只有 240 个完整 A 股一分钟结束时点才可标记 `evidence_status=sufficient`。

当最新分钟表象落入平衡/不清楚但仍有未失效事件时，当前方向跟随活动事件；冲突的日终投票进入反证。展示层按当前方向筛选结构化事件，筛选为空时不得回退全局候选或确认时刻。

每条 `fixed_window_observations[]` 必须符合相同的方向/阶段合法组合，`evidence_refs` 与 `counter_evidence_refs` 都只能引用 artifact 内存在的证据编号；窗口截止时间正确但语义自相矛盾时仍视为无效产物。

## Report Placement

- 新增二级标题 `## 市场语言翻译（研究证据）`，沿用现有 Bear HTML 的证据区分类机制。
- 最终插入点是 `render_front_page_v2`，它发生在第二次 `selection_workflow` 与 `final_target_resolution` 解析之后；不复用早期市场研究节点注册表。
- 位置在动作优先首屏之后、最终前台的周期与主线证据区域内。
- 内容最多六行：范围与方向、阶段、候选/确认/失效、三层对照、反证、下一窗口任务。
- 公式名、AICc 和长表只进入 replay 或研究 HTML，不进入普通日报正文。
- `markdown_report_html.py` 把该二级标题加入 `_EVIDENCE_H2_TITLES`；现有模板已经覆盖 `h2.bear-section-evidence`，不新增三级标题样式。

## Artifact Persistence

研究产物不写回共享 `data`。新增独立 writer/loader：

- PostgreSQL：复用 `daily_report_fact_fields`。artifact 行使用专属、精确的 `source_policy=postgresql.market_language_translation.v1`；writer 在一个事务内按 `trade_date + source_policy` 精确删除旧 artifact 行并批量写入新行，不使用 `LIKE`，因此 `_`、`%` 和 `\` 不参与通配匹配。
- 整日事实保存：`save_daily_report_snapshot` 删除同日旧事实时必须排除上述专属 `source_policy`，确保“先写 artifact、后再次同步整日事实”不会清掉 artifact。
- 本地 fresh 回退：`data/market-language/fresh/<target_date>.json`，使用原子替换并保存 schema 版本。
- fresh 保存时点：只由正式日报命令入口在完整版、摘要版、正式日报检查和整日事实同步全部通过后提交；`build_report_outputs` 只消费 artifact，不持久化。
- replay 保存时点：replay 入口和当前只支持 replay 的 AgentRunner 在报告保存后重新读取磁盘完整版，确认与已经检查的正文一致并通过最终检查后，才写 replay 副本；不调用 PostgreSQL fresh writer。
- replay artifact 根目录始终是项目根目录，不能因为报告写到项目外的绝对路径而改到报告父目录。
- loader 必须按 `target_date` 精确读取，不读取“最近一日”替代目标日期。

`daily_report_fact_fields` 已能按字段路径恢复嵌套 JSON，因此不新增数据库表；但必须新增专属 `source_policy` writer/loader、整日保存保留逻辑与 round-trip 测试，不能把一字段投影交给会先删除整日事实的现有整日保存函数。

写入前先按 schema 规范化数值类型：计数为整数，比率、价格和斜率为有限浮点数，禁止 NaN/Infinity。PostgreSQL 与本地 JSON 的验收比较规范化结构和 canonical JSON 哈希，不比较缩进后的原始字节；这样 `1.0` 被数据库恢复成 `1` 时不会制造伪差异。

## Fresh And Replay Loading

### Fresh

1. 正式日报命令入口在第一次渲染前从原始输入提取白名单 source projection 并构建一次 artifact，保留在局部变量；fresh source projection 本身也不携带未来日线、资金重叠或交易日历。
2. `build_report_outputs` 接收显式 artifact，完整版与摘要版各接收深拷贝；渲染后原 artifact 的 canonical JSON 哈希必须不变。
3. 两种版本的正式决定投影、日报检查和整日事实同步都通过后，由正式命令入口调用 writer 提交 fresh artifact。

### Replay

1. 若目标日 artifact 存在且 `target_date/source_date` 合法，加载后从 replay `data` 中抽离，以显式参数传入；所有兼容键都必须从共享输入移除。只有带交易所的主标的身份和主一分钟 `content_hash` 都与当前 replay projection 一致时，才允许把旧事件与当前路径拼接为 `posthoc_validation`，否则保持事实不足。
2. 若 artifact 不存在，但有可证明属于目标日的官方快照、replay 快照或 PostgreSQL 事实，则按同一 builder 重建，标记 `artifact_origin=reconstructed`。
3. 若目标日事实不足，仍生成 `evidence_status=insufficient` 的最小产物，`timeline.events=[]`，列出缺失项；不使用当前日期事实，不伪造时刻。
4. replay 加载、重建和 `posthoc_validation` 都只作用于内存副本；如需落盘，只写 `snapshots/replay/market-language/<target_date>.json`，不得覆盖 PostgreSQL fresh `source_policy` 或 `data/market-language/fresh/`。
5. 当前 AgentRunner 只支持 replay，`run()` 起点直接拒绝 fresh，自定义 loader 不能绕过；只有预保存检查、报告保存、磁盘正文复读和保存后的最终检查全部通过，才写上述 replay 副本。最终检查未通过时不提交。

历史 replay 不再采用“无 artifact 就静默跳过”的含糊分支。功能未启用的旧正式报告保持原样；功能启用后的 replay 明确显示已加载、已重建或事实不足。

## Posthoc Validation

- fresh artifact 的 `posthoc_validation` 固定为 `null`。
- replay 可在独立副本中填写未来 `5/10/20` 分钟、低区/高区、主要行情完成比例、MFE/MAE、T+1/T+2 和资金重叠。T+1/T+2 必须由覆盖目标日的显式开市日历定位，核对来源日、查询日和带交易所的标的身份；缺少 T+1 时 T+2 不前移，没有完整日历时保持缺失。同标的同日期但一分钟内容哈希不同，也不得混合旧事件与新价格路径。
- `posthoc_validation` 不得回写到 source projection、timeline、evidence 或生产 artifact。

## Validation Design

### 锚定样本

- 2026-07-10 兆易创新：多次候选、确认、失效与再确认。
- 2026-07-10 长电科技：主段降温、尾盘第二轮压力。
- 2026-05-21 上证指数：早盘假候选、午后指数/权重方向压力候选、指数聚合外形。

### 保护样本

- 普通缓跌但没有加速。
- 消息导致的一次性价值重估。
- 单一大资金持续执行但横截面不同步。
- 快速下跌后持续修复。
- 少数权重股主导指数、全市场中位数相反。
- 正向启动、扩散后健康分歧，而非拥挤衰减。

### 评价维度

- 多轮候选出现、确认和失效时间是否完整，改变未来数据后历史事件是否不变。
- 阶段对起点、粒度和成交额时间的敏感性。
- 候选发生后 `5/10/20` 分钟的走前预测误差。
- 低区/高区、MFE/MAE、T+1/T+2 资金重叠只作事后验收。
- 完整版和摘要版接入前后的正式决定投影逐字段不变。
- artifact PostgreSQL 与本地 round-trip 后规范化结构及 canonical JSON 哈希一致。
- `artifact -> 整日事实再次保存 -> artifact` 仍可读取，且名称相似的同日普通字段不受 writer 影响。

## Compatibility / Migration

- 不修改已有 `market_research_snapshot` schema，也不把 artifact 加入其压缩白名单。
- `render_front_page_v2` 新参数可选；缺省时旧行为不变。
- `build_report_outputs` 与下游报告入口的新参数可选；未启用时不创建标题或 artifact。
- PostgreSQL 使用现有通用事实表的专属 `source_policy` 与字段前缀，不需要数据库 DDL；整日保存必须显式保留该 `source_policy`。
- 若后续默认知识上下文需要加载新节点，单独更新 `WIKI_VERSION`、`SOURCE_PATHS`、字段映射和相应测试。

## Tradeoffs

- 显式参数会多穿过几层报告函数，但可以从类型和测试上证明正式决定读取不到研究产物。
- 专属 `source_policy` writer 比把字段塞入共享快照多一些代码，但避免通配转义、压缩丢字段、整日事实误删和二次渲染污染。
- 同时保留固定时间钟与事件时间钟，观察记录更复杂，但不会把午后新事件塞进早盘窗口。
- 缺少一分钟数据时允许输出不完整判断，牺牲表面完整度以换取日期和因果真实性。

## Rollback / Roll-forward

- 回退：停止构建/传入显式参数并删除最终前台证据标题；旧报告函数按缺省参数继续运行。
- 已保存 artifact 可保留作 replay 研究，不进入正式决定；必要时按字段前缀删除，不影响同日其他日报事实。
- 向前修正：字段新增只以可选字段扩展；语义变化时升级 schema 版本，不静默重定义旧值。
- 一旦接入前后正式决定投影不同，停止渲染与持久化，先排查显式参数是否进入任何正式决定消费者。
