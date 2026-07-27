# Design: 诺曼底气象决策知识接入 LLM Wiki

## Scope And Boundaries

- 资料层新增一份 D 日来源卡，只保存史实、整理判断、类比边界和待核实缺口。
- 交易思想层新增一个稳定方法节点，把历史案例抽象为可重复使用的判断流程。
- 运行层只注册这一个方法节点，使用现有精确市场事实路径完成结构化确认。
- 报告层沿用当前知识引用段，不新增独立决策或动作段。

## Contracts / Data Flow

```text
目标日市场事实
  ├─ market.market_form
  ├─ market.breadth
  └─ market.turnover_distribution
          |
          v
trigger_terms + fact_conditions.must_any
          |
          v
历史先验、实时结构与可用窗口（explanation_only）
          |
          v
知识引用 / 解释 / 复盘
```

正式决定在 Wiki 路由前已经形成。知识命中只附着说明，随后复用现有正式决定投影比较；若投影变化，移除知识解释并记录不一致。

### 运行知识条目

- 一个稳定 `knowledge_id`，来源指向交易思想主节点。
- `trigger_terms` 只承担候选召回，覆盖历史类比、实时结构、模型分歧、反弹与修复等表达。
- `fact_conditions.must_any` 只使用当前允许的精确叶子路径，并要求相应叶子包含结构词；单独的问题文本不满足生产命中。
- `decision_scope` 固定为 `explanation_only`。

### 方法节点字段

- `historical_prior`：历史样本限定什么可能范围。
- `current_structure`：来源明确的当前结构事实。
- `competing_hypotheses`：至少两个可竞争的解释。
- `shared_observations`：不同解释共同承认的事实。
- `discriminating_evidence`：下一组能够区分解释的事实。
- `evidence_gap`：当前缺少什么，缺少时保持事实不足。
- `next_review_window`：下一次核对什么，不新增临时动作。
- `invalidation_condition`：什么反证令当前解释失效。
- `analogy_limit`：气象与市场类比在哪些地方断裂。

## Compatibility / Migration

- 不扩展 `EXPLICIT_FACT_PATHS`，因此旧 trace、快照和调用方 schema 不变。
- 新来源加入 `SOURCE_PATHS` 后，当前 manifest 的来源集合和内容指纹会变化；这是预期的知识版本变化。
- replay 继续保存目标日冻结的 manifest、trace 和 hits；当前来源变化只影响复核信息。
- 人工问答仍可由 `wiki/README.md` 直接路由，生产日报命中继续要求结构化事实。

## Tradeoffs

- 复用宽泛的 `market.*` 文本叶子，避免为一个跨域类比扩展事实模型；代价是首版只能在事实生产端已经写出相应结构词时命中。
- 只注册主节点，来源卡不直接进入运行 manifest，避免同一方法出现重复引用；代价是查史实时需从主节点跳转来源卡。
- 不把历史回测数字写进稳定节点，降低过期和刻舟求剑风险；代价是每次具体比较仍需读取日期化研究。

## Rollback / Roll-forward

- 回滚：删除新增运行条目和 `SOURCE_PATHS` 项；两份 Markdown 可保留为人工可查资料，不影响日报。
- 向前：只有当现有生产事实长期无法表达模型分歧，而且有多个现实使用场景时，才单独评估是否扩展事实路径。
