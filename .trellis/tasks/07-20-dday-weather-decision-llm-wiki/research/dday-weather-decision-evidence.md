# Research: D 日气象预报分歧与交易类比边界

## Question

哪些 D 日气象史实足以支撑“历史先验与实时结构如何分工”的稳定方法，哪些影视化叙述仍应保留为待核实？

## Sources

- UK Met Office, `D-Day weather forecast`：https://www.metoffice.gov.uk/weather/learn-about/weather/case-studies/d-day-weather-forecast
- Imperial War Museums, D-Day weather history：https://www.iwm.org.uk/history/how-weather-forecasting-helped-d-day-succeed
- Dwight D. Eisenhower Presidential Library, D-Day records：https://www.eisenhowerlibrary.gov/research/online-documents/d-day
- James Martin Stagg, *Forecast for Overlord*, Ian Allan, 1971。
- Sverre Petterssen 相关历史材料与回忆，作为后续方法细节核验入口。

## Findings

### 当前史料概述（待一手材料逐项复核）

以下内容来自本轮已收集的权威来源入口与历史研究摘要，但外部网页正文和一手材料未能稳定取得，不能视为已经完成逐条原文定位。

- 本轮材料暂将 James Martin Stagg 概括为 SHAEF 首席气象官，负责整合多来源预报并向 Eisenhower 汇报；最终是否行动由 Eisenhower 决定。
- 本轮材料暂将 Irving P. Krick 概括为美方 USAAF 预报方法的重要代表，而不是与 Stagg 并列的 SHAEF 首席气象官；具体编制和会议身份待一手材料核验。
- 分歧不是简单的“暴雨对晴天”，而是对北大西洋扰动如何演化、当前稀疏观测应占多大权重、历史类比和周期模式是否可靠的分歧。
- 本轮材料把英国/挪威方法概括为相对更重视当前天气图、锋面、低压系统和高空资料的物理演变，把 Krick 方法概括为相对更重视历史相似型和周期模式；具体权重仍待一手材料核验，也不能简化成 Krick 完全不看当前天气图。
- 6 月 6 日只是两次恶劣天气之间边际可用的短暂改善窗口。当天仍有风、云和恶劣海况，不能写成预报了晴空万里。
- 高空观测与上层风是分析材料的一部分；现有证据不足以证明现代意义的 jet stream 是独立且唯一的决定变量。

### 整理判断

- D 日案例适合说明：先验提供可能范围，实时观测更新判断，模型分歧需要区分证据，行动只在损失可以接受的窗口发生。
- 对交易更有价值的不是“谁猜对天气”，而是 Stagg 提交了带条件、带不确定性、带时间窗口的整合判断，并没有把边际窗口说成确定性好天气。
- “市场急流”可以作为资金方向、范围、速度和反馈的类比名称，但必须拆回指数、宽度、成交分布、板块同步和价格承接等来源明确的事实。

### 类比失效处

- 气象系统受物理规律约束；市场参与者会观察和改变市场，存在反身性。
- 天文潮汐等约束接近确定，市场历史模式没有同等稳定性。
- D 日是高度不可逆的一次性协同行动，多数证券交易应优先设计成可减仓、可退出、能承认错误。
- 战争中的人员与战略损失不能被压缩成证券账户收益率语言。

## Recommendation

- 建立一份历史来源卡，保存史实和查证缺口。
- 只建立一个稳定交易思想节点，抽象“历史先验、实时结构、模型分歧、区分证据、下一观察窗口”。
- 运行时只在现有市场结构事实已经存在时召回该节点；“诺曼底”“急流”或“刻舟求剑”等问题词本身不能成为生产命中依据。
- 节点始终保持 `explanation_only`，不得进入候选、对象、仓位和动作计算。

## Impact

- PRD：将“高空急流”从固定市场映射降为受约束类比；新增史实准确性和负例验收。
- Design：沿用现有事实路径和冻结轨迹，不新增事实模型。
- Implementation：新增两份 Wiki 文档、一条运行知识、导航与定向测试。

## Evidence Gaps

- 本轮环境无法稳定抓取官方网页正文，因此不写未经当前会话逐字点验的直接引文。
- Krick 所用历史周期的精确天数、各次会议逐项预报和 Petterssen 的具体原话，需要以 Stagg 回忆录、会议记录或其他一手材料继续核验。
