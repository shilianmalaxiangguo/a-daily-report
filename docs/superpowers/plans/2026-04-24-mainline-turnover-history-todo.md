# 主线更替与板块成交额占比 Todo

> 目标：把“当前主线 / 最近一次主线 / 主线更替 / 板块成交额占两市成交额比例 / 占比趋势”做成可追踪、可 node 化、可替换、可回放的日报能力。

## 当前接口盘点

### 现在已经有的基础

- `scripts/domains/market_state/request.py`
  - 已有 `total_turnover` 两市成交额请求。
- `scripts/domains/market_activity/request.py`
  - 已有 `sector_fund_flow`、`hot_plates`、`sector_change_up/down`、`turnover_rank`。
- `scripts/domains/market_state/support.py`
  - 已有 `load_recent_sector_flow_history()`、`load_recent_market_turnover_history()`，能从历史快照回看序列。
  - 已有 `build_unified_sector_strength_rows()`，能产出当天主线/次主线候选。
- `scripts/research/market_research_support.py`
  - 已有 `build_mainline_competition_snapshot()`、`build_mainline_rotation_snapshot()`。
- `scripts/report/market_research_snapshot_nodes.py`
  - 已有 `rotation` 节点，说明这个需求适合继续挂在研究快照链路里做 node 化扩展。

## 本轮实测结论（2026-04-24）

### 已验证可用的数据源

- `TencentFinanceData.get_sector_fund_flow()` / 腾讯 `Fundflow/getHyRank`
  - 已实测行业资金流向里的 `code` 与腾讯板块详情 code 对齐：
    - `电池 -> pt01801737`
    - `半导体 -> pt01801081`
  - 原始接口字段 `cje` 可作为板块成交额使用。
  - 当前标准化口径：`turnover_yi = cje / 1e4`。
  - 已实测 2026-04-24：
    - `半导体 cje=26381045.00 -> 2638.10亿`
    - `2638.10 / 26414.92 = 9.99%`
- `ths-advanced-analysis` / `thsdk`
  - 已实测 `ths.market_data_block(link_code, "基础数据")` 可返回板块级字段：
    - `成交量`
    - `总金额`
    - `板块流通市值`
    - `板块总市值`
    - `上涨家数`
    - `下跌家数`
    - `领涨股`
  - 其中 `总金额` 可以直接作为“板块成交额”使用。
  - 已实测示例：
    - `半导体 -> URFI881121`
    - 返回 `总金额 = 270294100000`
- 两市成交额
  - 继续复用现有 `scripts/domains/market_state/request.py` 的 `total_turnover`。
  - 因此 `板块成交额占比 = 板块总金额 / 两市总成交额` 这条链已经有可实现数据源。

### 已验证不适合作为主数据源的路径

- `iwencai-screener`
  - 是行业/概念选股技能，不是板块聚合行情接口。
- `pywencai` / `pywencaistock`
  - 已实测自然语言查询 `"通信行业成交额"`、`"半导体行业成交额"`、`"通信板块成交额"`。
  - 返回的是个股行数据，字段里有 `成交额[date]`，但不是板块聚合总成交额。
  - 适合作为选股/股票筛选补充，不适合作为“板块成交额占比”的稳定主链路。
- `IWENCAI_BASE_URL=https://openapi.iwencai.com`
  - 环境变量已配置完成。
  - 但常见入口 `/v1`、`/v1/models`、`/v1/chat/completions`、`/docs`、`/openapi.json` 本轮实测均返回 `404 Route Not Found`。
  - 当前不能把这条 OpenAPI 路径视为已验证可接入的数据源。

### 当前最稳结论

- “板块成交额 / 两市成交额占比” 当前优先走腾讯 `sector_fund_flow.cje + total_turnover`。
- `thsdk market_data_block(..., "基础数据") + total_turnover` 保留为备选/补充链路。
- 问财路径当前保留为备选，不作为日报 node 的首版主链路。

### 当前不能直接满足的点

- 还没有“板块成交额汇总”接口。
  - 现在的 `turnover_rank` 只是个股成交额排行，不能准确代表板块总成交额。
- 还没有“主线更替历史记录”接口。
  - 现在只有当天主线推导，没有标准化的逐日主线历史表。
- 还没有“板块成交额占两市成交额比例”的日级序列。
  - 因为缺板块总成交额，所以无法可靠计算 `sector_turnover / total_turnover`。
- 历史快照口径当前不完全一致。
  - 旧入口会保存原始 `data` 快照；新 orchestrator 目前已开始保存 `analysis.mainline_history_record / analysis.sector_turnover_snapshot` 原子节点，但历史 loader 还没统一读取两套口径。

## 方案结论

- 不建议用 `turnover_rank` 前 50 个股去近似板块成交额占比。
  - 这个近似会严重低估分散型板块，也会把龙头高成交错当成整板块放量。
- 推荐新增“板块成交额日快照”数据链，再做占比序列。
  - 这样主线更替、成交额占比、占比趋势、分化节奏四件事才能用同一口径输出。
- 首选数据源改为腾讯行业资金流向。
  - `sector_fund_flow.code` 负责板块 code 映射。
  - `sector_fund_flow.cje` 负责板块总成交额。
  - `thsdk` 保留为腾讯缺字段/缺板块时的备选补充。

## 当前未完成事项

### A. 当前工作树收口

- [ ] 提交当前 `runtime` 尾部 helper 清理改动
  - 文件：`scripts/report/runtime.py`
  - 文件：`tests/test_report_runtime.py`

### B. 新需求的数据层

- [x] 定义 `mainline_history_record` 合同
  - 最少字段：`date`、`primary_mainline`、`secondary_mainline`、`rotation_label`、`leading_line`、`source`
  - 当前落点：`scripts/domains/market_state/mainline_history_runtime.py`
  - 当前补充字段：`competition_mainline`、`state_code`、`rotation_summary`
- [x] 定义 `sector_turnover_snapshot` 合同
  - 最少字段：`date`、`sector_name`、`sector_turnover`、`total_turnover`、`turnover_share_pct`
- [x] 确定板块成交额真实数据源
  - 结论：首选腾讯 `Fundflow/getHyRank["cje"]`，备选 `thsdk market_data_block(link_code, "基础数据")["总金额"]`
  - 原则：不用 `turnover_rank` 近似；不用 `pywencai` 个股成交额结果冒充板块聚合
- [x] 新增腾讯板块成交额适配层
  - 输入：行业/概念名称、`sector_fund_flow`
  - 输出：标准化 `sector_turnover_snapshot`
  - 当前落点：`scripts/input/tencent_sector_runtime.py`
  - 当前能力：支持用快照内 `cje / turnover_yi` 直接计算；旧快照只有 `code` 时可回查腾讯 `Fundflow/getHyRank` 补 `cje`
- [x] 新增 `thsdk` 板块成交额适配层
  - 输入：行业/概念名称
  - 输出：标准化 `sector_turnover_snapshot`
  - 当前落点：`scripts/input/ths_sector_runtime.py`
  - 当前能力：已支持行业精确命中、行业模糊聚合、`总金额 -> 亿元` 标准化、占比计算
- [ ] 设计 `thsdk` 数据源降级策略
  - 游客账户可用于验证，但不应直接作为生产稳定性承诺
  - 当前进度：`ths_sector_runtime` 已在 `thsdk` 客户端不可用 / 限流时降级为空快照，返回 `source_status=error` 与 `source_error`
  - 当前进度：多板块聚合时，单个 `market_data_block()` 失败不再清空整组结果；当前会保留已成功板块，并输出 `failed_sector_codes`
- [x] 统一历史快照读取口径
  - 让旧 `data` 快照和新 orchestrator `analysis.*` 持久化都能被历史加载层识别
  - 当前进度：`persist.snapshot` 已开始落 `analysis.mainline_history_record / analysis.sector_turnover_snapshot`
  - 当前进度：`mainline_history_runtime / sector_turnover_history_runtime` 已支持读取旧顶层快照和嵌套 `analysis.*` 结构
  - 当前进度：`replay.report_replay` 已支持把 `analysis.mainline_history_record / analysis.sector_turnover_snapshot` 抬平给报表链路复用

### C. 新需求的 domain 拆分

- [x] 新增主线历史 infer 节点
  - 输入：当天 `mainline_rotation_snapshot`、`mainline_competition_snapshot`、`state_machine_snapshot`
  - 输出：当天主线历史记录
- [x] 新增板块成交额占比 infer 节点
  - 输入：当天板块成交额快照、`total_turnover`
  - 输出：当天各板块成交额占比
- [x] 新增历史序列 loader
  - 已完成：`scripts/domains/market_state/mainline_history_runtime.py` 可读取最近 N 日主线历史
  - 已完成：`scripts/domains/market_state/sector_turnover_history_runtime.py` 可读取最近 N 日目标板块成交额占比
- [x] 新增趋势摘要 infer 节点
  - 输出：主线是否切换、当前主线连续天数、主线占比扩大/收缩、节奏偏抱团/偏分化
  - 当前进度：已新增 `scripts/domains/market_state/mainline_turnover_summary_runtime.py`，可生成 `mainline_turnover_summary` contract

### D. node 化接入日报

- [x] 给市场研究快照新增“主线更替与成交额占比”节点
  - 结论优先，不解释公式
- [x] 给前摘要补一个极简结论出口
  - 例如：`主线未切换 / 切换为通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化`
- [x] 支持 `enabled_node_keys`
  - 能单独裁掉该节点，不影响其它日报模块
- [x] `execution_chain.environment_follow_stage` 显式透传主线成交额原子节点
  - 当前已导出：`current_mainline_history_record / recent_mainline_history / current_sector_turnover_snapshot / recent_sector_turnover_history / mainline_turnover_summary`
  - 作用：后续 `full / summary / replay` 出口可直接复用，不必再从 `market_research_snapshot` 内部反解
- [x] `report.runtime -> report.tail_summary` 显式透传主线成交额原子节点
  - 当前已透传到 `build_legacy_final_conclusion_lines()` context
  - 作用：尾部结论、总结出口、后续 replay 验收都能直接复用这组原子字段

### E. TDD 顺序

- [x] 红灯 1：先证明当前接口无法准确给出板块成交额占比
  - 结论：repo 现有 `turnover_rank` 不行；`pywencai` 自然语言“行业成交额”返回的是个股行，不是板块聚合
- [x] 红灯 2：补 `thsdk -> sector_turnover_snapshot` 标准化 contract 测试
  - 测试文件：`tests/test_ths_sector_runtime.py`
  - 已验证：
    - 行业精确匹配可输出标准化快照
    - `通信` 这类宽主线可按行业模糊匹配做聚合
    - 概念库不会在行业已命中时误抢优先级
- [x] 红灯 3：补主线历史记录 contract 测试
  - 测试文件：`tests/test_mainline_history_runtime.py`
  - 已验证：
    - 优先读取 `state_machine.leading_line`
    - 可从 `mainline_competition_snapshot` 回填 `次强线 / 竞争线`
    - 缺少状态机时可回退到 `observation.mainline_candidates / secondary_candidates`
- [x] 红灯 4：补板块成交额占比序列 loader 测试
- [x] 红灯 5：补研究快照新 node 渲染测试
- [x] 红灯 6：补 full / summary / replay 回归测试
  - 当前进度：已补 `environment_follow_stage` exports 回归，以及 `runtime -> tail_summary -> final conclusion context` 透传回归
  - 当前进度：已补 `report.runtime` 的 `full / summary` 成品摘要回归，确认 `主线更替与占比` 行能进入最终 markdown
  - 当前进度：已刷新 `reports/replay/2026-04-23_A股日报_完整版_replay.md` 与 `reports/replay/2026-04-23_A股日报_执行摘要_replay.md`，真实产物已出现主线成交额占比文本
  - 当前进度：已新增 `replay.report_replay.build_replay_report_outputs_contract()` 自动串联 `replay -> render -> save`，并在测试中断言最终 replay 文件包含 `主线更替与占比`

## 推荐实现落点

- 数据请求：
  - `scripts/domains/market_activity/request.py`
  - 或新增 `scripts/domains/market_activity/sector_turnover_request.py`
  - 或新增 `scripts/input/ths_sector_runtime.py`
- 历史/推导：
  - 新增 `scripts/domains/market_state/mainline_history_runtime.py`
  - 新增 `scripts/domains/market_state/sector_turnover_history_runtime.py`
- node 接入：
  - `scripts/report/market_research_snapshot_node_registry.py`
  - `scripts/report/market_research_snapshot_nodes.py`
  - `scripts/report/front_summary_builder.py`
  - `tests/test_market_research_renderer.py`
  - `tests/test_front_summary_builder.py`

## 默认口径草案

- 主线口径：
  - 默认以 `state_machine.leading_line` 为主
  - 辅以 `mainline_competition_snapshot` 的 `主攻线 / 次强线 / 竞争线`
- 趋势口径：
  - 至少看最近 5 个交易日
- 输出口径：
  - 先说结论
  - 再给数据
  - 不写概念解释味
