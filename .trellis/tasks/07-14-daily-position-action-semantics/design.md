# Design: 日报新仓旧仓动作与空仓语义收口

## Scope And Boundaries

本任务只调整账户动作契约、用户可见渲染、验收检查与 Wiki。新仓对象和仓位继续由现有 `selection_workflow`、`position_decision` 和 `final_target_resolution` 产生。

复用现有 `old_position_plan.v1`，不建立第二套旧仓模型。现有 `full_or_empty_exposure.v1` 继续负责账户暴露，但必须区分已确认旧仓、模拟继承旧仓、明确外部待核实记录、明确无旧仓和持仓未输入。

## Contracts / Data Flow

```text
显式持仓输入 / 独立成交事实
  -> personal_position_context.existing_position_summary (confirmed)
  -> old_position_plan.v1

最近未结束的前日报明日标的（模拟账户）
  -> personal_position_context.existing_position_summary (confirmed, actual 1x / 100%)
  -> old_position_plan.v1

明确 external_trade_pending
  -> personal_position_context.existing_position_summary (pending_confirmation, actual 0x)
  -> 不生成 old_position_plan.v1

显式输入今日空仓
  -> personal_position_context.existing_position_summary (none, actual 0x)

以上账户事实
  -> final_target_resolution（仅 confirmed 填充 old_position_plan）
  -> full_or_empty_exposure.v1 + two_layer_daily_decision.v1
  -> 日报首页 / 明日执行结论 / 持仓策略 / Bear HTML
  -> report_acceptance_audit
```

### `old_position_plan.v1` 增量字段

在已有字段上增加：

```python
{
    "decision_class": "failed | review_at_10_10 | normal | incomplete",
    "primary_action_window": "09:50-10:10 | 14:30-14:55 | none",
    "review_conditions": ["str"],
    "closing_target_position_pct": "int | None",
}
```

约束：

- `failed`：`action == "exit"`，`primary_action_window == "09:50-10:10"`，`tail_exit_allowed == False`。
- `review_at_10_10`：`action == "wait_for_repair"`；只有三层事实成立才把退出延后到尾盘。
- `normal`：旧仓逻辑仍成立；只有明确 T+2 或尾盘预案时才写 `14:30-14:55`。
- `incomplete`：缺少足够事实；不得制造精确旧仓动作。

三层复核固定为：

1. 个股相对昨收和分时均价仍有承接。
2. 个股相对指数强势没有快速消失。
3. 板块核心与板块宽度同步承接，不是个股孤立冲高。

### 账户事实与暴露

`full_or_empty_exposure.v1` 增加 `position_fact_status`：

- `confirmed`：显式持仓输入、明确成交事实确认的旧仓，或前日报明日标在模拟账户中自动形成的 1x 旧仓，风险暴露不得显示 0x。
- `pending_confirmation`：只用于 `external_trade_pending` 等明确来自外部的待核实记录，按 0x。
- `none`：用户明确输入无旧仓，可写 0x。
- `unknown`：持仓未输入，风险暴露与收盘目标都写待确认。

### 用户可见账户动作

账户动作面固定展示：

- `明日新仓`
- `旧仓事实`
- `旧仓判断`
- `旧仓动作`
- `收盘目标仓位`

`明日新仓 0%` 允许与正常存活旧仓并存。`明日标的为空` 同样只表示没有新买对象。用户可见动作面不得把这两种说法缩写成账户空仓。

显式 `明日空仓` 是更高优先级的明日账户指令，不是新仓比例的别名：

1. 次日不买任何新股。
2. 集合竞价卖清全部可卖旧仓。
3. 成交后账户仓位为 0。
4. 当日不做 T。
5. 集合竞价未全部成交时继续尽早卖；未卖清前显示清仓中或待卖清，不得显示已经空仓。

这条指令覆盖 `failed / review_at_10_10 / normal` 的常规旧仓处理时点，但只在报告明确写出 `明日空仓` 时生效。用户明确输入 `当前空仓` 只表示当前账户事实为 0；持仓未知仍保持待确认，二者都不能替代明日指令。

## Compatibility / Migration

- 新生成的个人持仓上下文直接写结构化 `old_position_plan.v1`。
- 历史快照只有 `summary` 时，兼容层仅识别明确词组：买点失败/失效/必须卖、10:10 不能修复、独立评估/继续持有。其他文本归入 `incomplete`。
- `inferred_from_previous_report=true` 或 `position_source=previous_report_target_default_1x` 表示模拟账户从前日报明日标继承，必须规范为 `has_position=true`、`has_pending_position=false`、实际仓位 100%，并进入旧仓计划。
- 没有新明日标不等于旧仓结束；读取链保留最近未结束的继承旧仓。Markdown 回退按“显式明日空仓 > 有效明日目标 > 报告日当前空仓或退出事实”解析：当前空仓只终止更早旧仓，不压掉同日报告为下一交易日选出的明日目标。
- `external_trade_pending` 不按模拟继承升级，继续保持实际 0x 与待核实动作。
- 不批量迁移或覆盖其他正式历史日报；仅覆盖用户明确要求的 2026-07-15 与 2026-07-16 产物，replay 使用兼容层验证。

## Tradeoffs

- 10:10 复核减少全天盯盘，但无法保证卖在日内最高；这是低注意力策略接受的机会成本。
- “通过复核后尾盘退出”保护可能继续走强甚至涨停的旧仓，也会保留类似长电科技上午强、下午转弱的假阳性。必须用后续样本继续校准，不在本任务内调统计阈值。
- 模糊历史文案宁可显示事实不足，也不为了前台完整而制造确定动作。

## Rollback / Roll-forward

- 回滚时可移除新增结构化字段和账户动作行，旧的候选与仓位计算不受影响。
- 若 replay 暴露历史快照缺少结构化事实，向前补兼容测试，不修改正式历史产物。
- 如果接入前后最终对象、明日新仓比例或 B1/B2 变化，立即停止并回查越界修改。
