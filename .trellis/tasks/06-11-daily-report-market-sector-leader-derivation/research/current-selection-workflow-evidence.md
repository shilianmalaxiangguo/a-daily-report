# Research: Current Selection Workflow Evidence

## Question

当前日报推导链路里，市场情绪、板块发酵、龙头确认、布鲁克斯价格行为和 A股成交量分别已经落在哪里，哪里仍需要重构？

## Sources

- `scripts/report/selection_workflow.py`
- `tests/test_selection_workflow.py`
- `docs/superpowers/specs/2026-06-08-selection-workflow-chain-design.md`
- `docs/trellis/specs/2026-06-11-brooks-price-action-a-share-volume-design.md`
- `wiki/交易思想/布鲁克斯价格行为趋势.md`
- `wiki/板块补充/板块中枢与主线延续.md`
- `scripts/report/two_layer_decision_payload.py`
- `scripts/report/front_page_v2_renderer.py`
- `scripts/report/markdown_report_html.py`
- `scripts/templates/daily_report_markdown_reader.html`
- `tests/test_two_layer_decision_payload.py`
- `tests/test_front_page_v2_renderer.py`
- `tests/test_daily_report_markdown_html.py`
- `wiki/运行契约/日报数据源契约.md`

## Findings

- 当前 `selection_workflow.v1` 已有 N0-N9 节点名：数据封装、市场周期判断、资金方向判断、板块关系拆解、板块内角色识别、候选池归一、反推龙头、候选对照淘汰、仓位与执行条件、输出一致性复核。
- 当前实现里，N1-N4 多数只传递 `market_state`、`mainline` 和是否存在 `sector_trend_snapshot`，还没有把市场氛围、板块成交扩散、板块发酵、板块情绪和龙头被市场选出的过程落成稳定字段。
- 当前候选来源仍从 `extreme_conviction_list`、`crossline_observation_stocks`、`watchlist`、`core_stocks`、`secondary_stocks` 等池子归一；已有设计明确涨停池、连板、T字板、热榜、历史记忆只能作为候选来源或后置证据。
- 当前 Brooks 价格行为判断在候选池构建和 N7 中体现，能识别放量、缩量、强收盘、长上影、弱收盘、放量破位、冲高回落等，并把“成交量不能单独生成买入资格”写入 N7。
- 现有测试已经覆盖：只有涨停但缺少反推证据不能成为最终对象；只有放量不能新增资格；放量冲高回落记录为价格未接受；显式候选不在候选池时不能绕过链路；仓位只允许 0%、50%、100%。
- `wiki/板块补充/板块中枢与主线延续.md` 已经保存用户当前核心思想：当前更常见的是资金先铺出板块效应，再用二波创新高群、成交承接和后排反馈筛出真正核心。
- `wiki/交易思想/布鲁克斯价格行为趋势.md` 已经保存本次书本蒸馏：成交量是资金表态，价格接受才可能形成买入资格；龙头身份只提高优先级，不直接给买入资格。
- 日报正文推导层已有 `render_selection_workflow_derivation_layer()`，当前能渲染节点和候选生命周期表，但表头仍偏旧，尚未突出市场、板块、龙头、价格行为和执行资格的分形推导。
- 首页已有 `selection_workflow` 保护逻辑，能在 0% 且无最终对象时压制旧的观察对象，说明最终对象同源消费已有基础。
- Bear 版 HTML 不是直接消费结构化对象，而是消费最终 Markdown；因此全面范围下必须先让日报正文输出新版推导，再由 `markdown_report_html.py` 和 `daily_report_markdown_reader.html` 正确渲染。必要时只对 Bear HTML 增加轻量样式或锚点，不应另起一套选择逻辑。
- `wiki/运行契约/日报数据源契约.md` 已经规定：日报生成链路里已经登记的判断因子，失败、未采集或载荷为空都停止生成；雪球热榜、雪球 AI 解释、创新高反馈、Top50 成交额占比趋势、龙虎榜、概念资金流、价格带风格趋势等不是可静默跳过的装饰项。

## Recommendation

本任务应重构推导契约，而不是新增一个指标分数。核心应从“候选对照里补 Brooks 判断”前移为“市场情绪 -> 板块发酵 -> 市场选出龙头 -> 价格行为确认 -> A股执行资格”的主链。

用户已明确更新产品取舍：不保留涨停、连板、T字板、一字板作为折中入口。新版必须严格从板块推导个股。这些形态只能在板块已经推出个股之后，作为可交易性、分歧日、风险或价格行为证据解释。

第一版应优先要求稳定字段和可视化推导，而不是追求新的复杂评分：

- N1-N4 需要输出可验收字段，证明市场和板块为什么值得继续看。
- N5-N6 需要证明个股是从板块发酵中被选出，不是先有个股再找板块理由。
- N7 继续保留 Brooks 和成交量本地化，但要明确它是价格接受确认，不是单独指标。
- N8-N9 继续保留账户、时间窗口、仓位和输出一致性。
- 缺失关键数据时应停止生成并提示优先修复缺失项，不能输出半份日报、观察版结论，也不能回到涨停、连板、T字板、一字板、热榜或历史记忆入口。
- 日报正文、Mermaid、首页和 Bear HTML 都需要使用同一条推导结果；Bear HTML 只渲染最终 Markdown，不重新选择对象。

## Impact

- PRD: 需要新增“分形推导契约”“严格板块推导个股契约”“A股量能优先但价格确认契约”“市场选龙头契约”。
- Design: 需要定义 N1-N9 的字段输出、Mermaid 推导展示、日报正文和 Bear HTML 渲染边界。
- Implementation: 应扩展 `selection_workflow` 的结构化字段和测试样本，加入缺失关键数据停止生成校验，再接入日报正文、首页一致性和 Bear HTML 验证。
