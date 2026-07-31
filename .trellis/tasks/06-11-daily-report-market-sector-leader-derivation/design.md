# Design: 日报市场板块龙头推导重构

## Scope And Boundaries

本设计实现严格板块推导个股：市场氛围先决定是否继续看板块，板块发酵决定哪些方向值得看，市场选出的板块核心才进入龙头确认和价格行为确认。

范围内：

- 扩展 `selection_workflow.v1` 的结构化字段和 Mermaid 输出。
- 改造日报正文推导层，让新版链路可见。
- 保证首页、最终对象、候选流水账和 Bear 版 HTML 消费同一份推导结果。
- 保留0%/50%/100%仓位表达。

范围外：

- 不重写全部日报生成器。
- 不新增外部工作流平台。
- 不让涨停、连板、T字板、一字板作为新仓候选入口。

## Contracts / Data Flow

保持 `schema_version = "selection_workflow.v1"` 以兼容现有消费者，新增 `derivation_contract = "sector_first_strict.v1"` 表示新版语义。

核心流向：

```text
N0 数据封装
  -> N1 市场氛围与赚钱效应
  -> N2 资金方向与量能表态
  -> N3 板块动向、发酵、情绪 / 市场情绪线
  -> N4 板块角色与市场选龙头 / 市场总龙
  -> N5 候选池归一
  -> N6 严格反推龙头
  -> N7 Brooks 价格行为与 A股量价确认
  -> N8 仓位、时间窗口、认错线
  -> N9 输出一致性
```

### 单一来源不变量

```text
资金方向证明
  -> selection_workflow.candidate_pool（唯一候选台账）
  -> selection_workflow.final（唯一最终对象）
  -> final_target_resolution（账户动作解释）
  -> 首页 / 两层决策 / 狙击手 / 淘汰赛 / 候选质量 / 附录 / Markdown / Bear
```

- `candidate_pool` 同时登记新仓候选、持仓风险对象、手动问股对象和旧信号过程对象，但只有 `candidate_origin=sector_first` 且方向证明完整的行可以取得 `new_entry_qualified=true`。
- 特殊行情先归一为可证明的“情绪抱团资金方向”，再进入同一台账；不能从市场总龙或高标身份直接创建候选。
- `selected_position_candidate`、`best_stock`、`watch_anchor`、Step2/Step3、极致信念和跨线名单只提供来源证据。它们可以补充已登记行或形成 `legacy_signal_only` 过程行，不能越过方向证明。
- `selection_workflow.final` 同时拥有对象、仓位、B1/B2 和失败条件。消费层不得根据来源顺序、旧名单或展示需要重新选择对象。
- `final_target_resolution` 保留兼容字段，但 `new_entry_target/display_target/new_entry_pct` 必须逐字段投影工作流最终结果；`watch_target/process_target` 在当前动作解析中保持空。旧仓对象只进入旧仓动作字段。

候选入口规则：

- 新仓候选必须来自 N3/N4 的板块推导结果。
- 普跌抱团、市场总龙和情绪龙头必须先在 N3 形成包含多个资金载体、成交容量、大众可参与性、分歧承接和竞争方向对照的资金方向，N4 才能从该方向识别核心。
- 涨停、连板、T字板、一字板、热榜和题材标签不能创建新仓候选。
- 这些形态只能作为已被板块推导出的个股的风险、分歧日、可交易性或价格行为证据。
- 持仓和用户手动问股对象可进入风险处理或观察链路，但不得自动获得新仓资格。
- 若持仓或手动问股对象要从观察转成新仓候选，仍需回到市场、板块、龙头和价格行为确认。

资金方向优先级规则：

- 普跌、窄池子进攻、抱团明显时，情绪抱团可以作为资金方向参加对照，但不能以单只高标代替方向证明。
- 板块扩散、成交占比抬升、后排承接良好时，普通板块方向优先，情绪抱团只作为竞争方向证据。
- 两类方向都强但互相冲突时，先在方向层PK；未分胜负时可以保留多个台账行，但最终对象仍只能有一个且不得给100%。

输出层：

- `render_selection_workflow_derivation_layer()` 渲染新版推导链和候选生命周期。
- `front_page_v2_renderer` 只读取 `selection_workflow.final` 作为首页执行对象来源。
- `two_layer_decision_payload`、`sniper_target_derivation`、`elimination_tournament`、候选质量和附录在存在工作流时，只从 `candidate_pool/final` 生成展示投影。
- `final_target_resolution` 只读取 `selection_workflow.final` 与账户上下文，不再从候选池、观察对象或旧列表挑选对象，也不反向写回 `selected_position_candidate/current_core_candidate`。
- Bear 版 HTML 继续由最终 Markdown 渲染，不重新选择对象。

缺失数据处理：

- 市场、板块发酵、市场情绪线、龙头确认、价格行为或账户执行所需关键数据缺失时，日报生成必须停止。
- 停止提示必须列出缺失数据项，并提醒用户优先修复数据缺失问题。
- 不能用涨停、连板、T字板、一字板、热榜、历史龙头记忆或旧缓存回退生成新仓结论。
- 明确允许为空的事实仍按 `wiki/运行契约/日报数据源契约.md` 执行，例如当天没有涨停或没有跌停。

## Compatibility / Migration

- 不修改现有 Python 运行入口。
- 尽量保留现有 `selection_workflow.v1` 字段，新增字段而不是删除字段。
- 旧测试中“涨停池可入候选”的样本需要更新为严格板块推导语义。
- 旧测试中“缺少工作流时从极致信念/跨线/selected/best_stock 回填当前对象”的断言改为过程证据兼容；当前动作不再支持这类回填。
- 旧持仓处理和盘中问股不能被新仓严格入口误伤；它们保留风险处理和观察能力，但不自动转成买入资格。
- 若部分历史 replay 缺少板块发酵字段，必须停止生成 replay 日报并列出缺失项，不能回退到涨停/连板入口或输出观察版日报。

## Tradeoffs

- 严格板块推导会减少旧式高标点火样本的前置机会，但更贴合用户当前买入窗口和风险偏好。
- 增加市场情绪线后，可以覆盖普跌抱团和总龙环境，但必须防止它退化成旧连板/高标战法。
- 线路优先级采用环境切换，能减少固定偏见，但实现上必须把冲突解释写清楚，否则日报会看起来摇摆。
- 全面改到日报正文和 Bear HTML 能更快验证效果，但影响面比仅改内部字段大，需要更完整测试。
- 缺失关键数据时直接停止生成会降低“勉强可读”的产出数量，但能防止残缺事实被包装成交易结论。
- 保持 `selection_workflow.v1` 可降低消费者适配成本，但必须用 `derivation_contract` 防止语义混淆。
- 保留旧字段形状会增加一段迁移期兼容代码，但兼容代码只能读和展示，不能继续拥有选择权；这是消除多套池子感知所需的当前成本。

## Rollback / Roll-forward

- 回滚：撤回 `selection_workflow` 新字段和渲染接入，保留 wiki/PRD 不影响日报生成。
- 向前修正：若 replay 发现板块字段不足，优先补齐目标日期可验证的数据；补不齐时停止生成并提示缺失项，不允许回到涨停入口。
