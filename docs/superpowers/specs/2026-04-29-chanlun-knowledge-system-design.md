# 缠论知识体系实现契约设计

日期：2026-04-29

状态：用户评审稿。本文档用于后续完全重做缠论模块的 node 与运行时，不直接实现代码。

原文来源：本仓库本地知识库 `chanlun/108`，对应《教你炒股票》108 篇核心课程。正文只把原文中可作为规则契约的内容抽象出来；个人经验、展示需求和工程近似必须单独标注，不能混入原文定理。

## 1. 目标

本 spec 的目标是给代码实现提供一套可执行的缠论规则契约。

后续实现必须做到：

- 先按缠论原文建立概念、递归构造、分解、买卖点和诊断层。
- 再把工程数据周期、日报输出、可视化平台、仓位语言接入该规则层。
- 所有 node 输出必须能说明自己来自哪类规则：原文硬规则、工程映射、经验假设或数据不足。
- 禁止把日 K 重叠、固定天数、固定最小长度、平台间桥接线等工程经验写成缠论核心定义。

本文档不是交易建议，也不设计仓位策略。仓位、主线、日报表达只允许消费缠论结构输出，不能反向改写缠论结构。

## 2. 规则分层

实现中所有判断都必须带 `rule_tier`。

| rule_tier | 含义 | 可否作为核心判定 |
|---|---|---|
| `original_rule` | 108 课原文里的定义、原理、定理、明确推论 | 可以 |
| `derived_contract` | 从原文定义推导出的工程契约，必须可回溯到原文 | 可以，但要列出处 |
| `engineering_mapping` | 为了程序可复现而选定的数据周期、最低级别、窗口、字段 | 可以参与实现，但不能宣称为原文定理 |
| `diagnostic_heuristic` | 用于提示、可视化、排序或人类阅读的经验判断 | 不能替代核心判定 |
| `user_experience` | 用户个人交易经验或界面偏好 | 只能作为可选展示或待验证假设 |
| `data_insufficient` | 数据不足导致无法确认 | 必须显式输出，不能回退成启发式确认 |

示例：`相邻平台之间显式保留一条桥接连接线` 应归入 `user_experience` 或 `diagnostic_heuristic`。它可以指导可视化或归并展示，但不能成为中枢、走势类型或连接走势的原文定义。

## 3. 原文核心公理

### 3.1 走势必完美

来源：017《走势终完美》、102《再说走势必完美》。

规则：

- 任何级别的任何走势类型终要完成。
- 任何走势都必须能被归入某种结构分解中，不能把尾部 K 线当作无归属噪音丢掉。
- 当下未完成结构必须标为未完成，而不是强行确认为已完成走势类型。
- 高级别变化必须从低级别开始，但低级别变化不等于高级别已经完成变化。

实现契约：

```text
EveryBar -> must_have_structural_assignment
UnfinishedMove -> status = forming
CompletedMove -> status = completed
UnknownByData -> status = data_insufficient
```

任何 node 都不得输出“过渡段”作为结构逃逸口。可接受的归属包括：分型构造中、笔延伸中、线段形成中、走势类型形成中、中枢内、离开中枢、返回中枢、中枢震荡、中阴状态、数据不足。

### 3.2 级别递归

来源：017、035、053、084、102。

规则：

- 中枢和走势类型互相依存，必须通过级别递归解除循环定义。
- 最低级别可由 K 线、分型、笔、线段等起始函数定义；最低级别以上用连续次级别走势类型重叠定义中枢。
- 级别不是天然等同某个时间周期。时间周期只是工程映射。
- 使用某一级别观察时，已完成的次级别走势类型可以被视为线段或整体零件。

实现契约：

```text
LevelDefinition
  level_id
  parent_level_id
  child_level_id
  construction_mode: primitive | recursive
  time_period_mapping: optional engineering_mapping
  source_rule_tier
```

程序必须允许替换级别映射。例如 `1m -> 5m -> 30m -> daily` 或 `1m -> 5m -> 15m -> 60m -> daily` 都是工程映射，不能写死成缠论唯一真理。

### 3.3 完全分类与当下性

来源：032《走势的当下与投资者的思维方式》、033《走势的多义性》、036、038、068、084、102。

规则：

- 缠论不是预测未来，而是给出当下分段函数。
- 当下只能依据已经走出来的结构判断。
- 多义性不是含糊性；它是在严格规则下，不同级别或不同结合方式对同一走势的多种合法解释。
- 同一段走势可以存在多个合法分解，但每个分解必须有明确边界、级别、结合依据和操作含义。

实现契约：

```text
Interpretation
  interpretation_id
  level_id
  decomposition_mode
  segments[]
  confidence_kind: confirmed | forming | alternative | invalidated
  boundary_reason[]
  chosen_for_operation: boolean
```

如果有多个合理解释，node 不得只保留一个静默结果。必须输出 `primary_interpretation` 与 `alternative_interpretations`，并说明为什么当前采用主解释。

## 4. 基础构造链

来源：062、065、067、071、072、077、078、081、083、084、091。

后续实现的构造链为：

```text
原始K线
-> 包含处理后的K线
-> 分型
-> 笔
-> 线段
-> 最低级别中枢
-> 各级别中枢
-> 走势类型
-> 买卖点 / 背驰 / 区间套
```

### 4.1 包含处理

来源：062、065。

规则：

- 分型识别前必须处理相邻 K 线包含关系。
- 包含处理要遵守方向和顺序原则。
- 包含关系不符合传递律，必须逐根合并。

实现契约：

```text
MergedBar
  raw_bar_ids[]
  direction_context: up | down
  high
  low
  merge_reason
```

禁止直接在原始 K 线上识别分型，除非该级别没有任何包含关系并记录了检查结果。

### 4.2 分型

来源：062、065、079、081、091。

规则：

- 顶分型：中间 K 线高点最高，低点也最高。
- 底分型：中间 K 线低点最低，高点也最低。
- 分型只在处理后 K 线上识别。
- 当下分型未确认时，只能处于构造状态。

实现契约：

```text
Fractal
  type: top | bottom
  bar_ids[]
  extreme_price
  status: forming | confirmed | invalidated
```

### 4.3 笔

来源：062、065、091。

规则：

- 笔由相邻、交替的顶分型和底分型构造。
- 顶底之间至少应有可构造笔的 K 线间隔，不能把共用 K 线或只有顶底贴合的结构直接当笔。
- 同类分型相邻时，按定义保留更有效的分型，不能构造同向笔。
- 笔不能构成中枢。笔可用于表里关系、状态过滤和更低级别观察，但不能直接作为最小中枢零件。

实现契约：

```text
Stroke
  direction: up | down
  start_fractal_id
  end_fractal_id
  status: forming | confirmed | invalidated
```

### 4.4 线段

来源：062、065、067、071、078、083。

规则：

- 线段至少由三笔组成，但不是任意连续三笔都必然构成线段。
- 线段前三笔必须有重叠部分。
- 线段结束以特征序列分型与破坏规则确认。
- 线段比笔稳定，适合作为最低级别中枢构造零件。

实现契约：

```text
Segment
  direction: up | down
  stroke_ids[]
  feature_sequence[]
  break_type: none | first_case | second_case
  status: forming | confirmed | invalidated
```

简单“三笔成段”只能作为候选，不能作为确认输出。

## 5. 中枢契约

来源：017、018、020、035、053、057、061、072、083、092、099。

### 5.1 中枢定义

原文硬规则：

- 某级别走势类型中，被至少三个连续次级别走势类型所重叠的部分，称为该级别走势中枢。
- 具体计算以前三个连续、已完成的次级别走势类型重叠为准。
- 不是几根同级别 K 线重叠。

实现契约：

```text
ZhongshuCandidate
  level_id
  child_trend_type_ids[3..]
  zd
  zg
  dd
  gg
  status: forming | confirmed | extension | expansion | completed | invalidated
```

对前三个连续次级别走势类型 `A`、`B`、`C`：

```text
ZD = max(low(A), low(B), low(C))
ZG = min(high(A), high(B), high(C))
valid if ZG > ZD
```

边界相等如何处理属于工程映射，必须显式记录。默认严格采用 `ZG > ZD`；如为了 A 股最小报价单位允许相等容差，必须标为 `engineering_mapping`。

### 5.2 盘整与趋势

来源：017、018。

规则：

- 盘整：某完成走势类型只包含一个该级别走势中枢。
- 趋势：某完成走势类型至少包含两个以上依次同向的该级别走势中枢。
- 趋势中的同级别中枢之间必须绝对不存在重叠。

实现契约：

```text
TrendType
  level_id
  type: consolidation | uptrend | downtrend
  zhongshu_ids[]
  start_time
  end_time
  status: forming | completed
```

没有至少一个确认中枢，不能确认完成的盘整或趋势走势类型。

### 5.3 中枢延伸、破坏、扩张、新生

来源：018、020、029、053、089、092、099。

规则：

- 中枢延伸：后续与中枢方向一致的 `Zn` 区间与 `[ZD, ZG]` 继续重叠。
- 中枢破坏：次级别走势离开中枢后，其后的次级别回抽不重新回到中枢内。
- 第三类买卖点来自中枢破坏。
- 更大级别中枢产生：连续两个同级别中枢相关波动区间产生重叠。
- 中阴状态表示走势生长阶段的不确定性，不能被硬切成唯一趋势。

实现契约：

```text
ZhongshuEvolution
  event_type:
    formed
    extended
    left_up
    left_down
    returned
    third_buy_candidate
    third_sell_candidate
    expanded_to_higher_level
    new_same_level_zhongshu
    neutral_yin_state
  evidence_segment_ids[]
  boundary_price
  rule_tier
```

不得把中枢之后的所有运动统一叫“连接段”。必须区分离开、返回、延伸、破坏、扩张、新同级别中枢、中阴状态。

## 6. 连接与同级别分解契约

来源：017、018、035、036、038、039、040、099。

### 6.1 连接走势

原文硬规则：

- 在趋势中，连接两个同级别中枢的必然是次级别以下走势类型。
- 该连接不必然是趋势，也不一定是严格次级别；极端情况可以是缺口或更低级别走势。
- 连接中枢的走势级别一定小于中枢。

实现契约：

```text
ConnectorMove
  from_zhongshu_id
  to_zhongshu_id
  max_level_must_be_below_zhongshu_level: true
  component_move_ids[]
  connector_kind: trend_type | lower_level_move | gap | unresolved
```

`相邻平台之间显式保留一条桥接连接线` 的处理方式：

- 可用于可视化，把多个低级别细节压缩成一个展示 connector。
- 可用于同级别分解中的归并结果。
- 不得规定为“平台与平台之间只能有一条原文连接线”。
- 如果多个低级别走势在同级别分解中可按结合律合并为一个连接走势，输出 `connector_kind = lower_level_move` 并保留原始组成。

### 6.2 结合律与多义性

原文硬规则：

- 走势类型连接符合结合律。
- 结合律不等于可以乱分解。
- 好的分解规则必须保证该规则下的唯一性。
- 同级别分解是把所有走势按固定级别走势类型分解，适合机械化操作。

实现契约：

```text
DecompositionMode
  mode_id
  level_id
  uses_same_level_decomposition: boolean
  allows_zhongshu_extension: boolean
  allows_consolidation_plus_consolidation: boolean
  uniqueness_claim: boolean
```

后续实现至少支持两种模式：

- `strict_recursive_mode`：按递归中枢定义处理延伸、扩张、走势类型。
- `same_level_operation_mode`：按固定级别分解走势类型连接，用于操作节奏与机械化节点。

两种模式输出不可混写。报告可同时展示，但必须标注模式。

## 7. 买卖点与动力学契约

来源：015、017、020、021、024、025、027、029、037、043、044、053、055、061、073。

### 7.1 三类买卖点

规则：

- 第一类买卖点：某级别趋势背驰导致的转折点。
- 第二类买卖点：第一类买卖点后第一次次级别回调/反弹形成的位置；小级别转大级别时尤其重要。
- 第三类买点：次级别走势向上离开中枢后，以次级别走势回试，其低点不跌破 `ZG`。
- 第三类卖点：次级别走势向下离开中枢后，以次级别走势回抽，其高点不升破 `ZD`。
- 三类买卖点归根到底可回到不同级别的第一类买卖点，但在同一级别上三者都有独立操作意义。

实现契约：

```text
TradePoint
  type:
    first_buy | first_sell
    second_buy | second_sell
    third_buy | third_sell
  level_id
  related_zhongshu_id
  related_trend_type_ids[]
  evidence
  status: candidate | confirmed | invalidated
```

价格站上/跌破某个箱体边界不能单独确认买卖点，必须有走势类型和级别证据。

### 7.2 背驰、盘整背驰与区间套

规则：

- 背驰首先是走势力度比较，不是指标信号。
- MACD、均线面积、柱面积等只能辅助判断力度，不能替代走势分解。
- 盘整背驰是围绕中枢震荡的力度比较推广。
- 区间套用于从较大级别背驰段逐级进入小级别定位。

实现契约：

```text
DivergenceEvidence
  compared_move_a_id
  compared_move_b_id
  comparison_level_id
  structural_weaker: boolean
  indicator_evidence: optional
  status: possible | confirmed | negated
```

任何背驰输出必须包含比较对象。不能输出“MACD 背驰所以买点成立”这种无结构结论。

## 8. 工程映射与数据契约

### 8.1 级别映射

缠论级别不是时间周期。为了程序可复现，工程上必须选定默认映射，但要标注为 `engineering_mapping`。

第一版推荐支持：

```text
1m -> 5m -> 15m -> 60m -> daily -> weekly
```

同时保留可配置能力，以便切换到更贴近原文示例的：

```text
1m -> 5m -> 30m -> daily -> weekly -> monthly
```

报告或运行时不得写“60 分钟天然就是日线直接次级别”。只能写“本次工程配置中，日线的直接构造级别为 60 分钟”。

### 8.2 数据状态

实现必须显式区分：

- `confirmed`：结构已完成且规则满足。
- `forming`：结构正在形成，尚不能确认。
- `candidate`：满足部分条件，等待确认。
- `alternative`：合法但非主采用解释。
- `invalidated`：被后续走势否定。
- `data_insufficient`：缺少下级别、历史长度或收盘标记。

数据不足时不能降级为日 K 重叠、固定长度平台或经验框。

### 8.3 覆盖归属

每根输入 K 线都必须能追溯到结构归属。

```text
BarAssignment
  raw_bar_id
  merged_bar_id
  fractal_id
  stroke_id
  segment_id
  trend_type_id
  zhongshu_id
  role
  status
```

允许角色：

- `inside_zhongshu`
- `leaving_zhongshu`
- `returning_to_zhongshu`
- `connector_move`
- `forming_fractal`
- `forming_stroke`
- `forming_segment`
- `forming_trend_type`
- `neutral_yin_state`
- `data_insufficient`

禁止角色：`transition`、`misc`、`noise`。

## 9. Node 边界设计

后续重做缠论模块时，建议按以下 node 分层。

### 9.1 Source Nodes

职责：读取、标准化、校验 K 线。

输出：

- 标准 K 线序列。
- 收盘状态。
- 级别映射配置。
- 数据覆盖诊断。

### 9.2 Morphology Nodes

职责：形态学构造。

包含：

- 包含处理 node。
- 分型 node。
- 笔 node。
- 线段 node。
- 最低级别中枢 node。

这些 node 只产出结构，不产出买卖建议。

### 9.3 Recursive Structure Nodes

职责：中枢、走势类型、同级别分解。

包含：

- 中枢识别 node。
- 中枢演化 node。
- 走势类型 node。
- 同级别分解 node。
- 连接走势 node。
- 多义性诊断 node。

这些 node 必须保留 rule_tier 和 evidence。

### 9.4 Dynamics Nodes

职责：背驰、力度、买卖点、区间套。

包含：

- 力度比较 node。
- 背驰候选 node。
- 区间套定位 node。
- 三类买卖点 node。

这些 node 可以消费指标数据，但指标只能作为辅助 evidence。

### 9.5 Report Adapter Nodes

职责：把严格结构翻译成日报或可视化语言。

规则：

- 可以把复杂结构摘要成“平台”“连接线”“结构片段”等易读表达。
- 必须保留底层 `source_structure_id`。
- 不得反向改变核心结构判断。

## 10. 禁止项

以下规则不得进入核心缠论判定：

- 用日 K 重叠直接确认日线中枢。
- 用“必须大于 20 日”确认中枢。
- 用单根 60 分钟 K 线当 60 分钟走势类型。
- 用固定 PEAK/TROUGH 箱体替代次级别走势类型重叠。
- 用 MACD 背离单独确认背驰。
- 用平台视觉连续性要求改写中枢连接定理。
- 把形成中结构写成已确认结构。
- 把多义性静默压扁成一个无诊断结果。
- 把数据不足回退成经验判断后仍称为严格缠论。

## 11. 验收标准

后续实现完成时，至少需要满足以下验收。

### 11.1 单元级验收

- 包含处理在向上、向下、连续包含场景中可复现。
- 分型只能从处理后 K 线确认。
- 笔必须交替，不能同类分型直接成笔。
- 线段必须通过特征序列规则确认。
- 中枢必须由至少三个连续已完成次级别走势类型重叠确认。
- 三买三卖必须有离开、回试/回抽、不回中枢的次级别证据。

### 11.2 契约级验收

- 每个中枢输出包含 `level_id`、`child_trend_type_ids`、`ZD`、`ZG`、`status`、`rule_tier`。
- 每个走势类型输出包含级别、类型、包含中枢、完成状态。
- 每个连接走势输出说明其级别低于中枢级别。
- 每个买卖点输出包含结构证据和状态。
- 每个解释输出可追溯到分解模式。

### 11.3 回归级验收

必须用原文定义建立最小样例：

- 三段次级别走势重叠形成中枢。
- 三段无重叠不形成中枢。
- 中枢延伸。
- 离开后返回形成中枢震荡。
- 离开后回试不回中枢形成第三类买点。
- 两个同级别中枢重叠波动导致高级别中枢。
- 多个合法分解并存时保留 alternative。
- 数据不足时输出 `data_insufficient`。

## 12. 与日报交易系统的边界

日报可以使用缠论模块输出，但不能把日报语言写进缠论核心。

建议边界：

- 上证指数结构：用于市场环境、参与档位、风险边界。
- 个股结构：用于买点剧本、确认条件、失效条件。
- 30 分钟或更小级别：可以用于止损、确认、区间套定位，但必须服从当前级别配置。

这属于日报应用层，不属于缠论原文核心层。若后续实现交易策略 node，必须另写策略 spec。

## 13. 第一版默认工程选择

以下选择用于第一版实现。它们都是 `engineering_mapping` 或适配层约定，不是原文定理。后续可以通过配置切换，但默认实现必须先保持一致。

| 问题 | 第一版默认 | 规则层级 |
|---|---|---|
| 默认级别链 | `1m -> 5m -> 15m -> 60m -> daily -> weekly` | `engineering_mapping` |
| 可选级别链 | 保留 `1m -> 5m -> 30m -> daily -> weekly -> monthly` 配置入口 | `engineering_mapping` |
| 最低级别输入 | 先从 1 分钟 K 线开始；没有 1 分钟数据时输出 `data_insufficient` | `engineering_mapping` |
| 最低级别构造零件 | 使用包含处理、分型、笔、线段，再构造最低级别中枢 | `derived_contract` |
| 中枢有效条件 | 默认 `ZG > ZD`；不做报价单位容差 | `original_rule` |
| `ZG == ZD` | 第一版视为无有效重叠；如后续放宽必须另写兼容说明 | `engineering_mapping` |
| 缺口 | 可以作为低于中枢级别的连接走势形态，不能直接当上级别走势类型 | `original_rule` |
| 涨跌停/一字板 | 按实际 K 线和缺口/延伸处理；不能因连续涨停自动升级中枢级别 | `derived_contract` |
| 停牌 | 标记交易中断，不补造走势；恢复交易后按缺口/连续结构处理 | `engineering_mapping` |
| 可视化桥接线 | 只在 report adapter 或 visual adapter 中生成，保留底层组件列表 | `diagnostic_heuristic` |
| “中枢”用词 | 仅用于严格满足定义的 confirmed/forming zhongshu | `original_rule` |
| “平台”用词 | 可用于展示层描述中枢或类中枢平台，但必须带底层状态 | `diagnostic_heuristic` |
| “结构片段”用词 | 用于数据不足、形成中、非严格中枢的报告摘要 | `diagnostic_heuristic` |

## 14. 结论

后续重做缠论模块时，核心路线应是：

```text
原文硬规则
-> 递归结构契约
-> 可配置工程映射
-> 带证据的 node 输出
-> 日报/可视化适配
```

这条路线能避免两个旧问题：

- 把过度简化的工程框当成缠论中枢。
- 把个人经验或展示偏好误写成原文定理。

只有当 node 能清楚回答“这个判断来自哪条原文规则、哪段结构证据、哪个工程映射”时，才算进入可实现状态。
