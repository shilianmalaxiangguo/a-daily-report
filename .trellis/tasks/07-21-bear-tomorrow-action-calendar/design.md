# Design: Bear 最近25条明日操作日历

## Scope And Boundaries

本任务只增加 PostgreSQL 历史事实查询、只读日历载荷和 Bear HTML 展示。决策生产端仍由现有日报运行时负责；HTML 渲染器不能根据历史日历反推或改写明日对象、仓位与账户动作。

界面叙事是“交易复盘台上的周历”：用户处于快速核对状态，需要在数秒内顺着交易周看清计划、结果和相对上证表现。视觉沿用现有 Bear 报告的纸面与表格语言，不新增营销式卡片、动画或装饰。

## Contracts / Data Flow

```text
PostgreSQL strategy_factor_snapshots / strategy_factor_snapshot_fields
  -> 最近25条报告日的最终明日决定（从新到旧 LIMIT 25，再恢复正序）
  -> 明确分类：target / empty / no_new_entry / incomplete

PostgreSQL strategy_performance_ledger
  -> 仅在没有因子快照历史时兼容旧记录

PostgreSQL index_daily_bars (sh000001)
  -> 每个 report_date 之后第一条实际交易日 = execution_date
  -> execution_date 当日 open / close
  -> 上证开收到收涨幅

PostgreSQL stock_daily_quotes_recent (execution_date + stock_code)
  -> 每条活跃持仓腿的当日 open / close

连续两日账户模型
  -> 每份具体明日标的生成第1日、第2日两条 1x/50% 腿
  -> 同日最多两腿；不新增保留前一腿第2日，明确空仓清除全部腿

以上事实
  -> tomorrow_action_calendar.v1 只读载荷
  -> render_markdown_report_html(..., tomorrow_action_calendar=...)
  -> 顶部 Bear 账户日序时间轴前的交易周日历
  -> 汇总行
```

### `tomorrow_action_calendar.v1`

```python
{
    "schema": "tomorrow_action_calendar.v1",
    "mode": "frozen | replay",
    "requested_count": 25,
    "record_count": int,
    "report_date_start": "YYYY-MM-DD | ''",
    "report_date_end": "YYYY-MM-DD | ''",
    "execution_date_start": "YYYY-MM-DD | ''",
    "execution_date_end": "YYYY-MM-DD | ''",
    "source": "postgresql.strategy_factor_snapshot_fields | postgresql.strategy_performance_ledger",
    "records": [
        {
            "report_date": "YYYY-MM-DD",
            "execution_date": "YYYY-MM-DD | ''",
            "weekday_label": "周一 | ... | ''",
            "action_kind": "target | empty | no_new_entry | incomplete",
            "action_label": "股票名称(代码) | 空仓 | 不新增 | 事实不足",
            "plan_action_kind": "target | empty | no_new_entry | incomplete",
            "action_items": [
                {
                    "label": "股票名称(代码)",
                    "position_label": "1x/50% | 2x/100%",
                    "holding_label": "第1日 | 第2日 | 第1+2日",
                    "plan_date_label": "YYYY-MM-DD[/YYYY-MM-DD]",
                }
            ],
            "active_legs": [
                {
                    "plan_report_date": "YYYY-MM-DD",
                    "holding_day": "1 | 2",
                    "weight_pct": 50.0,
                    "stock_return_pct": "float | None",
                    "contribution_pct": "float | None",
                }
            ],
            "total_position_pct": "0 | 50 | 100 | None",
            "stock_code": "str",
            "stock_name": "str",
            "daily_return_pct": "float | None",
            "shanghai_return_pct": "float | None",
            "excess_shanghai_pct": "float | None",
            "performance_status": "complete | future | incomplete",
            "missing_fields": ["str"],
        }
    ],
    "summary": {
        "valid_count": int,
        "plan_target_count": int,
        "holding_count": int,
        "target_count": int,
        "empty_count": int,
        "no_new_entry_count": int,
        "incomplete_count": int,
        "outperform_count": int,
        "average_daily_return_pct": "float | None",
        "average_excess_shanghai_pct": "float | None",
        "cumulative_daily_return_pct": "float | None",
        "cumulative_shanghai_return_pct": "float | None",
        "cumulative_excess_shanghai_pct": "float | None",
    },
}
```

### 账户结果与计划分类

计划分类仍按数据库明日决定产生 `target / no_new_entry / empty / incomplete`；账户结果则根据执行日活跃腿独立计算：

1. 明确账户归零计划清除当日全部腿。
2. 有活跃腿时账户结果为 `target`，即使本格计划分类是 `no_new_entry`。
3. 没有活跃腿且计划分类为 `no_new_entry` 时，账户结果为 `empty`，并保留 `plan_action_kind=no_new_entry`。
4. 计划分类为 `incomplete` 或超过两条腿时，账户结果为 `incomplete`，不得猜测为空仓。

因此 `空仓` 与 `不新增计划` 可以在同一执行日同时成立；有上一计划第 2 日腿时，页面显示持仓标的和 `本日计划：不新增`，不显示空仓。

### 收益与持仓公式

- 每份 `target` 计划从下一实际交易日起连续参与两个交易日；每个交易日是一条 `1x/50%` 腿。
- 同一执行日最多两条活跃腿。不同股时分别显示两个 `1x/50%`；同股重叠时合并显示 `2x/100% · 第1+2日`，收益仍按两条 `0.5` 权重腿求和。
- 每条腿 `stock_return_pct = (stock_close / stock_open - 1) * 100`，`contribution_pct = stock_return_pct * 0.5`。
- `daily_return_pct = Σ contribution_pct`；`shanghai_return_pct = (index_close / index_open - 1) * 100`；`excess_shanghai_pct = daily_return_pct - shanghai_return_pct`。
- `empty` 清除当日全部腿，`daily_return_pct = 0.0`。`no_new_entry` 不生成新腿，但前一份具体标的的第 2 日腿继续参与；只有没有任何活跃腿时账户收益才为 `0.0`。
- 汇总中的累计账户收益与累计上证收益在同一组完整有效日分别逐日复利；`cumulative_excess_shanghai_pct = cumulative_daily_return_pct - cumulative_shanghai_return_pct`，不使用每日超额百分点简单相加。
- 任一活跃腿或上证的同日开收事实缺失、非有限或冲突时，收益字段为 `None`；不把缺失默认成 `0`。

### 日期契约

- 最近 25 条按 `report_date <= target_report_date` 过滤。
- `execution_date` 是 `report_date` 之后 PostgreSQL 上证日线的第一条日期；具体标的另取该日期之后下一条交易日作为第 2 日，因此自然跳过周末和法定休市。
- 交易日行存在与该行开收收益可算是两件事：即使开收字段缺失，也保留真实执行日归属并将收益标为事实不足，不得顺延到下一天。
- 若目标日报之后尚无上证日线且该日期仍在未来，标为 `future`；历史记录缺下一交易日事实则标为 `incomplete`。
- TuShare `trade_cal` 只允许作为当前生成日的未来执行日期补充；历史收益不得依赖联网补数。本轮最小闭环优先使用数据库日线，无法确认则留缺。

## HTML Composition

- 日历标题：`最近25条明日操作日历`。
- 组件插入 `.position-timeline-shell` 账户日序时间轴之前；由于该时间轴是 Bear 正文的首个 Markdown 组件，日历作为 `markdown-body` 的第一个块渲染。若页面没有账户时间轴，日历仍保持正文首块，不丢弃组件。
- 布局使用一张 5 列语义化表格，每行代表一个交易周，列为周一至周五。
- 每格顺序固定：日期与星期、活跃持仓腿、每腿 `1x/50%` 与第几日、计划日报日期、本格计划、账户当日涨幅、跑赢上证。
- 周历结构空位不默认为缺失记录：已知法定休市显示节日名称（例如 `端午休假`），报告执行范围外显示 `样本外`，范围内无记录才显示 `记录缺失`；这些注释不进入记录数或收益汇总。
- 正收益使用现有报告的上涨色，负收益使用下跌色；同时始终显示符号。
- 底部汇总是组件的单独汇总带，不在每个格子重复。
- 390px 下组件内部横向滚动，最小宽度保证 5 列不挤压；页面本身不横向滚动。
- 纯静态报告不增加动画、交互按钮或外部依赖。

## Compatibility / Migration

- `render_markdown_report_html()` 新参数默认 `None`，现有调用方和测试不传时输出保持不变。
- 入口只在成功构建结构化载荷后传入；数据库缺失时传入带来源状态的空载荷，渲染明确事实不足。
- 正式与 replay 通过明确 `mode` 查询各自台账，绝不跨模式回填。
- 不修改现有 Markdown，不把日历写回日报正文或 PostgreSQL 决策表；日历生成链路只读数据库，不调用会重写整本策略历史的保存接口。

## Tradeoffs

- 使用数据库下一条上证日线映射执行日，可正确覆盖历史周末和休市，但数据库历史不完整时会留缺；这是比猜日期更可信的选择。
- `不新增` 只描述本格没有新腿，不会结束前一份计划的第 2 日持仓；汇总同时展示“明日标的计划日”和“账户持仓日”，避免两类计数重叠造成误解。
- 本轮按计划账户的同日开收到收收益计算，不代表真实券商成交价、滑点或实际账户净值；界面保持“计划表现”含义，不延伸为实盘收益。

## Rollback / Roll-forward

- 回滚时移除入口传参与 HTML 日历渲染，不影响 Markdown、数据库和决策链。
- 如果计划台账缺少明确空仓字段，仍可依据执行日没有活跃腿显示账户 `空仓`，但保留原计划分类 `不新增`；只有计划分类为 `incomplete` 或收益事实缺失时才显示事实不足。本任务不通过文案猜测或数据库迁移扩大范围。
- 如果接入前后任何决策字段变化，停止交付并回查入口边界。
