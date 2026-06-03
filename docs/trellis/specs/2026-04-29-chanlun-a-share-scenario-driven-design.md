# 缠论 A 股场景驱动验收设计

日期：2026-04-29

状态：用户评审稿。本文档是《缠论知识体系实现契约设计》的场景化补充，用于后续重做缠论模块时生成样例、观察输出、反向优化规则。

关联理论 spec：

- `docs/trellis/specs/2026-04-29-chanlun-knowledge-system-design.md`

## 1. 目标

这份 spec 不重新定义缠论原文规则。它解决三个工程问题：

1. 用 A 股常见输入构造一组可重复的验收场景。
2. 让每个场景都能生成结构输出、报告摘要和诊断 metadata。
3. 观察生成结果，把不合理结果归因到规则、数据、适配层或报告表达，再反向优化 spec 和实现。

核心原则：

- 先按输入场景跑出结果，再判断结果是否像人类看盘会接受。
- 任何优化都必须说明改的是理论契约、工程映射、数据能力还是报告适配。
- 不把“看着像平台”直接改写成严格中枢。
- 不因为 A 股特殊情况直接跳过结构证据。

## 2. 与旧 spec 的关系

旧 spec 是理论契约，回答“什么能算缠论结构”。

本 spec 是样例驱动验收契约，回答“在 A 股常见输入下，模块应该怎么输出、怎么降级、怎么被观察”。

实现时必须同时满足：

- 理论层不违背旧 spec。
- 场景层能解释 A 股真实常见走势。
- 报告层能用结论优先的语言消费结构结果。

## 3. 场景运行闭环

每个场景都按同一闭环执行。

```text
ScenarioInput
-> Generate Chanlun Output
-> Observe Output
-> Classify Defect
-> Optimize Spec Or Implementation
-> Re-run Scenario
```

### 3.1 输入模板

```text
ScenarioInput
  scenario_id
  market_role: index | stock
  symbol
  symbol_name
  a_share_condition_tags[]
  daily_bars
  minute_bars_60m optional
  minute_bars_30m optional
  minute_bars_15m optional
  target_date
  expected_behavior
```

### 3.2 输出模板

```text
ScenarioOutput
  scenario_id
  success
  mode
  primary_interpretation
  alternative_interpretations[]
  structure_state
  zhongshu_permission
  report_label
  report_sentence
  data_capability
  rule_tier_trace[]
  observation
```

### 3.3 观察模板

```text
ScenarioObservation
  accepted: boolean
  human_readable_result
  mismatch_type:
    none
    theory_violation
    engineering_mapping_error
    data_capability_error
    report_language_error
    a_share_edge_case_missing
    over_strict
    over_loose
  correction_target:
    spec
    implementation
    adapter
    data_source
    no_change
  correction_note
```

## 4. 通用输出命名

场景输出必须区分这些状态：

| 状态 | 含义 | 报告层可用说法 |
|---|---|---|
| `confirmed_zhongshu` | 严格满足至少三个连续次级别走势类型重叠 | 日线中枢 |
| `daily_practical_platform` | 日 K 实用级别下形成平台，但缺严格次级别确认 | 日线平台 / 日线结构片段 |
| `forming_structure` | 结构正在形成，证据不足 | 形成中结构 |
| `connector_move` | 平台或中枢之间的低级别连接走势 | 连接走势 |
| `breakout_candidate` | 离开上沿，但未完成三买确认 | 突破候选 |
| `breakdown_candidate` | 跌破下沿，但未完成三卖确认 | 跌破候选 |
| `third_buy_candidate` | 离开中枢后回试不回中枢的候选 | 三买候选 |
| `third_sell_candidate` | 离开中枢后回抽不回中枢的候选 | 三卖候选 |
| `data_insufficient` | 数据不足，不能确认 | 数据不足 |
| `not_applicable` | 该场景不适合输出某类结构 | 不输出 |

禁止报告层把 `daily_practical_platform` 直接写成严格 `confirmed_zhongshu`。

## 5. A 股常见输入场景库

### S01 上证指数 250 日震荡平台

目的：验证默认 practical daily mode 能用 250 根日 K 建立结构基底。

输入特征：

- `market_role = index`
- `symbol = sh000001`
- 250 根已收盘日 K。
- 多数 K 线在一个宽幅区间内反复震荡。
- 60m 可无数据。

预期输出：

```text
structure_state = daily_practical_platform
zhongshu_permission = practical_only
report_label = 日线平台
data_capability.daily.supports_250_day_base = true
minute_confirmation.confirmation_status = not_requested
```

报告句式：

```text
上证指数仍处在日线平台内，市场环境以震荡处理；该结论来自 250 根日 K 的实用结构基底，未请求分钟线确认。
```

观察重点：

- 如果输出“严格日线中枢”，属于 `over_loose`。
- 如果因为没有 60m 而整体失败，属于 `over_strict`。

### S02 上证指数突破平台上沿

目的：验证突破只改变位置状态，不自动生成三买。

输入特征：

- 前 200-250 日形成平台。
- 最近 1-3 根日 K 收在平台上沿之上。
- 60m 未给出回试不回中枢证据。

预期输出：

```text
structure_state = breakout_candidate
zhongshu_permission = practical_only
trade_point_permission = none
report_label = 平台上沿突破候选
```

报告句式：

```text
指数离开日线平台上沿，但还没有回试不回平台的次级别证据；只能看作突破候选，不直接升级为三买。
```

观察重点：

- 若直接输出第三类买点，属于 `theory_violation`。
- 若完全忽略突破位置，属于 `report_language_error` 或 `implementation` 位置判断缺失。

### S03 上证指数跌破平台下沿

目的：验证跌破与空仓/防守档表达分离。

输入特征：

- 前期存在日线平台。
- 最近日 K 收在平台下沿之下。
- 跌破后无有效返回。

预期输出：

```text
structure_state = breakdown_candidate
market_role_output = risk_environment
trade_point_permission = none
report_label = 跌破平台下沿
```

报告句式：

```text
指数跌破日线平台下沿，市场环境转为防守；这只决定参与环境，不替代个股买卖点。
```

观察重点：

- 若把指数跌破直接写成所有个股卖点，属于 `adapter` 越界。
- 若报告直接扁平成永远空仓，属于日报策略层问题，不属于缠论核心。

### S04 日 K 看像平台但 60m 不确认

目的：验证 practical 与 hybrid 的边界。

输入特征：

- 日 K 区间有重叠，形成实用平台。
- 60m 三段走势类型没有共同重叠。

预期输出：

```text
practical.structure_state = daily_practical_platform
hybrid.confirmation_status = not_confirmed
zhongshu_permission = practical_only
report_label = 日线结构片段
```

报告句式：

```text
日 K 结构像平台，但 60 分钟没有给出三段走势重叠确认；报告只称日线结构片段，不称严格日线中枢。
```

观察重点：

- 如果 hybrid 否定后 practical 也消失，属于 `over_strict`。
- 如果 60m 不确认仍叫严格中枢，属于 `theory_violation`。

### S05 60m 足够、15m 不足

目的：验证数据能力约束。

输入特征：

- 60m 返回约 493 个交易日。
- 15m 返回约 124 个交易日。
- 日 K 有 250 根。

预期输出：

```text
confirmation_primary = 60m
15m.capability_status = local_confirmation_only
15m.supports_250_day_base = false
```

报告句式：

```text
本次日线结构确认以 60 分钟为主；15 分钟只用于近期局部观察，不参与 250 日结构基底。
```

观察重点：

- 如果实现用 15m 去确认 250 日结构，属于 `data_capability_error`。
- 如果因为 15m 不足否定 60m 确认，属于 `engineering_mapping_error`。

### S06 次新股历史不足 250 日

目的：验证新股/次新股不能硬补 250 日。

输入特征：

- 个股上市不足 250 个交易日。
- 有 80-180 根日 K。
- K 线可能已经形成局部平台。

预期输出：

```text
data_capability.daily.capability_status = data_insufficient
structure_state = daily_practical_platform | forming_structure
zhongshu_permission = practical_only_or_none
report_label = 上市历史不足
```

报告句式：

```text
该股上市历史不足 250 根日 K，只能做局部结构观察；不能把当前平台放大成完整日线中枢。
```

观察重点：

- 若实现为了凑 250 日补造 K 线，属于 `data_capability_error`。
- 若完全不输出任何局部结构，可能属于 `over_strict`。

### S07 连续涨停或一字板

目的：验证涨停不自动升级结构级别。

输入特征：

- 个股连续涨停或一字板。
- 多根 K 线高低价接近或相等。
- 可能伴随缺口。

预期输出：

```text
structure_state = connector_move | leaving_zhongshu | forming_structure
limit_up_tag = true
zhongshu_permission = none unless child trend overlap exists
```

报告句式：

```text
连续涨停表示强离开或加速段，不自动构成更高级别中枢；后续要看开板后的低级别回试结构。
```

观察重点：

- 如果连续涨停被识别成平台中枢，通常属于 `over_loose`。
- 如果缺口完全丢失结构归属，属于 `a_share_edge_case_missing`。

### S08 停牌复牌跳空

目的：验证交易中断与缺口处理。

输入特征：

- 个股停牌数日。
- 复牌后跳空高开或低开。
- 停牌期间无真实 K 线。

预期输出：

```text
trading_halt_tag = true
gap_tag = true
connector_kind = gap | unresolved
synthetic_bars_created = false
```

报告句式：

```text
停牌期间不补造走势；复牌缺口作为低级别连接或未决连接处理，等待后续真实 K 线确认。
```

观察重点：

- 若补出停牌期间 K 线，属于 `data_capability_error`。
- 若把缺口直接当完整走势类型，属于 `theory_violation`。

### S09 ST 或低流动性个股

目的：验证弱流动性导致的结构降级。

输入特征：

- ST、低价股或成交极低。
- K 线常出现长时间横平、无量、极小振幅。

预期输出：

```text
liquidity_warning = true
structure_state = forming_structure | daily_practical_platform
confidence_note = low_liquidity
```

报告句式：

```text
该股流动性较弱，结构只能作低置信度观察；不把窄幅横平直接放大为高质量中枢。
```

观察重点：

- 如果低流动性横盘被高置信度确认，属于 `over_loose`。
- 如果输出没有任何流动性提示，属于 `a_share_edge_case_missing`。

### S10 平台贴平台，中间只有低级别连接

目的：验证“桥接连接线”只属于展示/诊断，不属于原文硬规则。

输入特征：

- 两个相邻平台在展示窗口中很接近。
- 中间有一个或多个低级别连接走势。
- 人眼看图需要一条连接线避免平台贴平台。

预期输出：

```text
core_segments = [platform, connector_move, platform]
connector.rule_tier = diagnostic_heuristic | derived_contract
visual_bridge_allowed = true
```

报告句式：

```text
两个平台之间保留连接走势，便于展示结构推进；连接线不改变中枢定义。
```

观察重点：

- 若平台直接合并且没有扩张证据，属于 `over_loose`。
- 若把桥接线写成原文硬规则，属于 `theory_violation`。

### S11 个股日线结构用于买点剧本

目的：验证指数与个股职责分离。

输入特征：

- 上证指数给出环境状态。
- 个股有自身日线平台或结构片段。
- 个股当前位置在平台上沿、下沿或中间。

预期输出：

```text
index_output.role = market_environment
stock_output.role = entry_script_source
entry_permission_source = stock_structure
```

报告句式：

```text
指数只决定市场环境；个股买点剧本来自个股自身结构位置，不能用指数中枢替代。
```

观察重点：

- 若个股没有结构却借指数结构生成买点，属于 `adapter` 越界。
- 若指数环境完全不参与仓位环境，属于日报策略层缺失。

### S12 回试不回中枢的三买候选

目的：验证三买必须有“离开 + 回试 + 不回中枢”。

输入特征：

- 已有平台或中枢。
- 走势向上离开。
- 随后回试低点不跌回 ZG。
- 次级别证据可来自 60m。

预期输出：

```text
structure_state = third_buy_candidate
trade_point_permission = candidate
required_evidence = leave_up + pullback_not_returning
```

报告句式：

```text
该股具备三买候选形态：先离开平台，再回试不回平台上沿；仍需次日承接确认。
```

观察重点：

- 只有突破、没有回试，不得输出三买。
- 回试跌回平台内部，不得输出三买。

## 6. 生成样例格式

后续实现测试夹具时，每个场景至少生成两份 artifact：

```text
tests/fixtures/chanlun_scenarios/<scenario_id>.json
reports/replay/chanlun_scenarios/<scenario_id>.md
```

JSON 夹具格式：

```json
{
  "scenario_id": "S01_index_250d_platform",
  "market_role": "index",
  "symbol": "sh000001",
  "symbol_name": "上证指数",
  "target_date": "2026-04-29",
  "a_share_condition_tags": ["index", "250_daily_base", "range_platform"],
  "daily_bars": [],
  "minute_bars_60m": [],
  "expected_behavior": {
    "structure_state": "daily_practical_platform",
    "zhongshu_permission": "practical_only",
    "minute_confirmation_status": "not_requested"
  }
}
```

Markdown 观察格式：

```text
## S01 上证指数 250 日震荡平台

结论：通过 / 不通过

生成结果：
- 结构状态：
- 报告标签：
- 数据能力：
- rule_tier：

人工观察：
- 是否像 A 股实际看盘：
- 是否误称中枢：
- 是否过严或过松：

优化动作：
- no_change / spec / implementation / adapter / data_source
```

## 7. 优化规则

场景跑出来后，按以下决策表改进。

| 观察问题 | 优先修正对象 | 不允许的修正 |
|---|---|---|
| 严格中枢误报 | 实现或 adapter | 放宽原文中枢定义 |
| 日线平台被完全丢弃 | 工程映射或 report adapter | 伪造成严格中枢 |
| 15m 被用作 250 日确认 | 数据能力契约 | 把 15m 数据不足解释成行情无效 |
| 连续涨停识别成中枢 | A 股边界规则 | 因涨停强势自动升级级别 |
| 停牌期间被补 K | 数据源处理 | 用合成 K 线参与结构确认 |
| 指数结构替代个股买点 | report adapter | 把指数环境写成个股买点 |
| 报告语言过度解释公式 | report adapter | 删除底层 metadata |

优化后的 spec 必须记录：

```text
ScenarioOptimizationRecord
  scenario_id
  previous_output
  observed_problem
  correction_target
  spec_change_summary
  implementation_change_summary
  acceptance_after_change
```

## 8. 第一版验收清单

第一版缠论模块重做完成前，至少要让以下场景可运行：

- S01 上证指数 250 日震荡平台。
- S02 上证指数突破平台上沿。
- S03 上证指数跌破平台下沿。
- S04 日 K 看像平台但 60m 不确认。
- S05 60m 足够、15m 不足。
- S06 次新股历史不足 250 日。
- S07 连续涨停或一字板。
- S08 停牌复牌跳空。
- S10 平台贴平台，中间只有低级别连接。
- S11 个股日线结构用于买点剧本。
- S12 回试不回中枢的三买候选。

S09 低流动性场景可以作为第二批，但如果实现过程中已经能拿到成交额/成交量质量字段，应一并纳入第一版。

## 9. 与日报输出的边界

日报只消费场景结果，不在报告层重新判定缠论。

报告层必须做到：

- 先说结论，再说为什么。
- 不解释公式细节。
- 不把每个 node 的内部过程写进日报正文。
- 保留 metadata 给调试和 replay 使用。
- 指数结构只作为市场环境。
- 个股结构才作为买点剧本来源。
- 30m 或更小级别只用于止损、局部定位和执行细节。

推荐日报句式：

```text
结论：指数处在日线平台内，市场按震荡环境处理。
原因：250 根日 K 显示平台结构仍未被有效破坏；分钟线本次未作为必需确认。
```

```text
结论：该股只是突破候选，不是三买确认。
原因：价格离开平台上沿，但还没有回试不回平台的次级别证据。
```

## 10. 禁止项

- 不准把场景样例当成缠论原文定义。
- 不准为了让某个样例通过而放宽中枢定义。
- 不准把 `daily_practical_platform` 改名成严格 `zhongshu`。
- 不准用 15m 不足否定 60m 可用。
- 不准用指数结构替代个股结构。
- 不准补造停牌期间 K 线。
- 不准把一字板直接识别成高级别中枢。
- 不准把报告展示桥接线写成原文硬规则。

## 11. 下一步

后续 implementation plan 应在已有重做计划基础上追加一个场景验收任务：

```text
Task: Add Chanlun A-share scenario fixtures and observation runner

Outputs:
  tests/fixtures/chanlun_scenarios/*.json
  scripts/decision/chanlun/scenario_runner.py
  reports/replay/chanlun_scenarios/*.md
  tests/test_chanlun_a_share_scenarios.py
```

场景 runner 的职责不是优化结果，而是稳定地暴露结果，让人能观察：

- 哪些场景通过。
- 哪些场景过严。
- 哪些场景过松。
- 哪些是数据能力不足。
- 哪些是报告表达不对。

只有观察记录明确后，才允许进入下一轮 spec 或实现优化。
