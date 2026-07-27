# Design: 修复仓位档与1x/2x语义串位

## Scope And Boundaries

本任务只统一仓位语义及其跨层传播。选股、评分、板块判断、最终对象、交易窗口与取消条件保持不变。

核心边界：

- 计划仓位档是决策真值，生产端只允许写 `0/50/100`，不得生成 `40/60` 等中间计划档。
- x档是计划仓位档的等价表达：`0/1/2`。
- 实际仓位记录一手颗粒度或成交事实；实际 `40%-60%` 可以归入 1x 风险带，但用户可见计划仍写 `1x/50%`，实际比例不得反向修改计划仓位档。
- B1/B2 是执行顺序：B1=1x；B2 确认后总仓位=2x。

## Contracts / Data Flow

### Canonical Position Tier Contract

新增纯函数契约，集中处理：

```python
normalize_position_tier_pct(value) -> 0 | 50 | 100
position_tier_pct_to_x(value) -> 0 | 1 | 2
position_x_to_tier_pct(value) -> 0 | 50 | 100
position_tier_label(value) -> str
```

这些函数负责把兼容输入归一为计划仓位档；新计划生产端必须直接写 `0/50/100`。实际成交的 `40%-60%` 只在账户事实层归入 1x 风险带，不能输出成 `1x/40%` 或 `1x/60%` 计划。任何用户可见层不得再用字符串内容推断或修改仓位。

### Previous Report Inheritance

```text
previous_report_target_default_1x
  -> position_fact_status=confirmed
  -> planned_position_pct=50
  -> position_x=1
  -> old_position_plan.holding.position_pct=50
  -> B1 已存在
```

若历史记录在该来源下写了 0、缺失或 100，统一修复为 50；显式真实持仓来源不走该修复。

### Exposure Contract V2

新产物使用 `position_tier_exposure.v2`：

```python
{
    "schema_version": "position_tier_exposure.v2",
    "position_fact_status": "confirmed | pending_confirmation | none | unknown",
    "old_position_pct": "0 | 50 | 100 | None",
    "old_position_x": "0 | 1 | 2 | None",
    "planned_new_entry_pct": "0 | 50 | 100",
    "planned_new_entry_x": "0 | 1 | 2",
    "new_entry_pct": "0 | 50 | 100",
    "new_entry_x": "0 | 1 | 2",
    "same_stock_target": "bool",
    "same_stock_t": "bool",
    "possible_intraday_overlap": "bool",
    "max_runtime_exposure_pct": "0 | 50 | 100 | None",
    "max_runtime_exposure_x": "0 | 1 | 2 | None",
    "policy": "str",
    "legacy": {
        "source_schema_version": "full_or_empty_exposure.v1 | None"
    }
}
```

`planned_new_entry_pct/x` 是该对象的计划总档，`new_entry_pct/x` 是扣除同股已有仓位或账户剩余空间后的当前新增档；两者不得互换。`same_stock_target=true` 表示计划对象与旧仓相同，只有当前仍需新增 B2 时 `same_stock_t=true`。旧 v1 字段只用于兼容读取；新渲染器消费 v2 数值字段。汇总规则为各腿 x档相加并封顶 2x，不生成 200% 模型。

### Rendering

```text
selection_workflow.final.position_pct
  -> position_decision.target_position_pct
  -> final_target_resolution
  -> position tier label
  -> Markdown/stdout
  -> Bear HTML
```

删除 `50%条件执行 -> 满仓条件执行` 的字符串替换。风险文字净化可以保留，但必须与仓位归一分离。

### Acceptance

验收从“全文出现满仓就禁止 50%”改为按同一对象/同一动作核对结构化仓位和可见仓位：

- 50% 只允许 1x/B1/半仓。
- 100% 只允许 2x/B1+B2/满仓。
- 旧仓实际比例与新仓计划档分别核对，互不覆盖。

## Compatibility / Migration

- 保留 `previous_report_target_default_1x` source id，避免数据库与快照迁移。
- v1 暴露对象可读取；若有显式 `position_pct` 则按比例换算，若仅有旧布尔值则标记 legacy/incomplete，不把 `old_position_1x=True` 自动解释为100%。
- 已明确为默认1x来源的历史记录，即使带错误100，也修复为50。
- 显式真实100%持仓保持2x；不因历史默认规则降级。
- 不覆盖正式历史产物，replay 在读取边界修复语义。

## Tradeoffs

- 新增 v2 会增加少量兼容代码，但能让每腿比例与总暴露显式化，避免继续靠布尔字段猜测仓位。
- 不直接重命名历史 source id，牺牲命名美观以降低数据迁移风险。
- 本任务不调整弱环境是否给1x的选股规则；只保证一旦最终档是50%，任何层都不能显示2x/满仓。

## Rollback / Roll-forward

- 回滚时可恢复 v1 生产，但必须同时恢复对应测试；不得只恢复字符串替换。
- 若发现遗漏消费者，优先让其读取 v2 数值字段；不要新增局部换算。
- 若跨层对比发现最终对象或窗口变化，停止完成声明并回查越界修改。
