# Mainline Attack Evidence Structure Design

## Summary

日报下一步要把 `主线确认` 的初因从文字判断升级为结构化的 `主线攻击证据`。它不预测明天延续，也不重写周报；只回答今天资金是否真的进攻了某个板块，以及这个进攻是否足够让它成为 `主攻线`、候选线、混沌轮动，或无主线。

这个设计延续 `主线容量与格局判断`：容量判断市场能养几条线，攻击证据判断资金今天打哪里，格局判断这些线之间是什么关系。

## In Scope

- 定义 `主线攻击证据` 的结构化字段。
- 定义从板块证据到 `确认 / 候选 / 混沌 / 无主线` 的确定性输出。
- 定义单主线、双线竞争、混沌接力、无主线的前置证据边界。
- 定义如何把攻击证据写回 `mainline_capacity_regime_summary.confirmation_evidence`。
- 保留 `主线成交额占比趋势` 作为传递性证据，但不把它当作唯一主线确认依据。

## Out Of Scope

- 不实现主线周报视图。
- 不改个股参与窗口、仓位、止损和执行计划。
- 不引入新闻、基本面或外部预测作为主线确认初因。
- 不把历史成交额经验锚点写进规则、报告或测试样例。
- 不追求预测明天主线延续，只判断今日资金攻击是否成立。

## Non-goals

- 不做复杂评分模型炫技。
- 不输出无法复核的综合分。
- 不用斜率、动能、阶段进程反推主线确认。
- 不把每个热点都命名为主线。

## Done Definition

- 有一个结构化 `mainline_attack_evidence_summary`，可以被运行时、前台摘要和推理输入复用。
- 至少覆盖四类验收样本：强单主线、双线竞争、混沌轮动、无主线。
- `confirmation_evidence` 由结构化字段生成，不再只依赖上游自由文本。
- 当证据不足时，输出 `无主线` 或 `混沌接力`，不强行制造主攻线。
- 相关测试保证旧的 `mainline_capacity_regime_summary` 兼容路径不被破坏。

## Evidence Fields

每个候选板块使用同一套字段。字段允许缺失，但缺失必须进入解释，不允许伪装成精确判断。

| 字段 | 含义 | 用途 |
|---|---|---|
| `sector_name` | 板块名称 | 证据归属 |
| `net_inflow_amount` | 板块资金净流入金额 | 判断真金白银是否进入 |
| `net_inflow_rank` | 净流入排名 | 判断是否靠前或明显领先 |
| `limit_up_count` | 板块涨停家数 | 判断批量涨停 |
| `high_anchor_height` | 板块最高连板或高标高度 | 判断高标是否疯狂 |
| `high_anchor_name` | 最高辨识度样本 | 解释高标强度 |
| `broad_rally_pct` | 板块上涨家数占比 | 判断普涨 |
| `strong_gain_count` | 板块内高涨幅个股数量 | 判断高涨幅集群 |
| `turnover_share_pct` | 板块成交额占比 | 判断资金聚焦度 |
| `turnover_share_change` | 成交额占比变化 | 判断占比扩张或回落 |
| `evidence_labels` | 命中的证据标签 | 用于生成可审计解释 |
| `missing_fields` | 缺失字段 | 防止假精度 |

允许的证据标签固定为：

- `资金净流入靠前`
- `资金净流入明显领先`
- `批量涨停`
- `高标强度突出`
- `板块普涨`
- `高涨幅集群`
- `成交占比扩张`

## Classification

`主线攻击证据` 先输出板块级状态，再交给 `主线容量与格局判断`。

| 输出 | 条件含义 | 解释方式 |
|---|---|---|
| `confirmed_attack` | 一个板块同时具备资金证据和涨停/高标/普涨等强度证据 | 可以命名为主攻线 |
| `candidate_attack` | 有局部强度，但证据不完整或领先不明显 | 只能做候选线 |
| `chaotic_rotation` | 多个方向各有局部证据，但没有一个明显胜出 | 格局优先写混沌接力 |
| `no_attack` | 资金、涨停、高标、普涨都不集中 | 输出无主线 |

确定性原则：

- 资金净流入和涨停/高标/普涨至少要形成交叉验证，单一字段不直接确认主线。
- `confirmed_attack` 必须同时有资金侧证据和强度侧证据；只有其中一侧时最多是 `candidate_attack`。
- 如果净流入领先但涨停和普涨都不支持，只能是候选线或资金试探。
- 如果涨停很多但资金净流入不支持，要提示情绪强于资金确认。
- 如果多个板块都有两项以内局部证据且差距小，输出 `chaotic_rotation`。
- 如果市场容量低且攻击证据分散，优先输出 `no_attack` 或 `chaotic_rotation`。

## Mainline Confirmation Output

运行时新增一个中间摘要：

```python
{
    "attack_state": "confirmed_attack",
    "primary_line": "半导体",
    "candidate_lines": ["电力"],
    "background_lines": ["化学制品"],
    "evidence_labels": ["资金净流入靠前", "批量涨停", "高标强度突出", "成交占比扩张"],
    "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
    "evidence_gaps": [],
}
```

这个摘要只负责主线确认初因，不负责仓位和买卖。

## Integration With Capacity And Regime

`mainline_capacity_regime_summary` 使用新摘要时，字段来源如下：

| 现有字段 | 新来源 |
|---|---|
| `primary_line` | `mainline_attack_evidence_summary.primary_line` |
| `other_lines` | `candidate_lines + background_lines` |
| `confirmation_evidence` | 结构化生成的 `confirmation_evidence` |
| `mainline_regime` | 结合 `attack_state` 与 `主线容量` 判断 |
| `sector_relationship_state` | 结合候选线、背景线和旧主线记录判断 |

如果没有 `mainline_attack_evidence_summary`，保留当前兼容路径，不让旧报告断裂。

## Calibration Samples

实现前至少准备这些验收样本：

| 样本 | 输入特征 | 期望输出 |
|---|---|---|
| 强单主线 | 一个板块净流入靠前，涨停多，高标突出，普涨或占比扩张 | `confirmed_attack` + `单主线聚焦` |
| 双线竞争 | 两个板块都有资金和强度证据，市场容量支持双线 | `confirmed_attack` + `双主线竞争` |
| 混沌轮动 | 三个以上方向各有局部强度，但没有明显资金胜出 | `chaotic_rotation` + `混沌接力` |
| 无主线 | 净流入分散，涨停少，普涨弱，占比无扩张 | `no_attack` + `无主线` |
| 情绪强于资金 | 涨停多但净流入不支持 | `candidate_attack`，解释为情绪强、资金确认不足 |
| 资金试探 | 净流入靠前但涨停、高标、普涨不足 | `candidate_attack`，解释为资金试探 |

## Acceptance Checks

- 不能只因为 `primary_mainline` 有值就确认主线。
- 不能只因为新闻热度或题材名出现就确认主线。
- 不能只因为一个高标涨停就确认整个板块。
- `confirmation_evidence` 必须包含至少一个资金字段和一个强度字段，或明确说明缺口。
- 混沌轮动不能被写成三主线并行，除非市场格局明确是牛市或超级牛市。
- 缺失字段必须进入 `missing_fields` 或解释文本，不能输出假精确。
- 前台仍只展示简洁结论，不倾倒全量原始数据。
