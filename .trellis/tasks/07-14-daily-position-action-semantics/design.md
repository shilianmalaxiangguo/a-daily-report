# Design: 日报新仓旧仓动作与空仓语义收口

## Scope And Boundaries

本任务只调整账户动作契约、用户可见渲染、验收检查与 Wiki。新仓对象和仓位继续由现有 `selection_workflow`、`position_decision` 和 `final_target_resolution` 产生。

复用现有 `old_position_plan.v1`，不建立第二套旧仓模型。现有 `full_or_empty_exposure.v1` 继续负责账户暴露，但必须区分已确认旧仓、待成交确认、明确无旧仓和持仓未输入。

## Contracts / Data Flow

```text
用户持仓输入 / 历史账户事实
  -> personal_position_context.existing_position_summary
  -> old_position_plan.v1
  -> final_target_resolution.old_position_plan
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

- `confirmed`：已确认旧仓，风险暴露不得显示 0x。
- `pending_confirmation`：前日报计划待成交确认，按 0x。
- `none`：用户明确输入无旧仓，可写 0x。
- `unknown`：持仓未输入，风险暴露与收盘目标都写待确认。

### 用户可见账户动作

账户动作面固定展示：

- `明日新仓`
- `旧仓事实`
- `旧仓判断`
- `旧仓动作`
- `收盘目标仓位`

`明日新仓 0%` 允许与正常存活旧仓并存。用户可见动作面不再用单独“空仓”证明账户为零；需要账户归零时，必须写明完成时刻。

## Compatibility / Migration

- 新生成的个人持仓上下文直接写结构化 `old_position_plan.v1`。
- 历史快照只有 `summary` 时，兼容层仅识别明确词组：买点失败/失效/必须卖、10:10 不能修复、独立评估/继续持有。其他文本归入 `incomplete`。
- 前日报计划推定继续使用现有 `inferred_from_previous_report` 语义，不进入旧仓计划。
- 不迁移或覆盖正式历史日报；replay 使用兼容层验证。

## Tradeoffs

- 10:10 复核减少全天盯盘，但无法保证卖在日内最高；这是低注意力策略接受的机会成本。
- “通过复核后尾盘退出”保护可能继续走强甚至涨停的旧仓，也会保留类似长电科技上午强、下午转弱的假阳性。必须用后续样本继续校准，不在本任务内调统计阈值。
- 模糊历史文案宁可显示事实不足，也不为了前台完整而制造确定动作。

## Rollback / Roll-forward

- 回滚时可移除新增结构化字段和账户动作行，旧的候选与仓位计算不受影响。
- 若 replay 暴露历史快照缺少结构化事实，向前补兼容测试，不修改正式历史产物。
- 如果接入前后最终对象、明日新仓比例或 B1/B2 变化，立即停止并回查越界修改。
