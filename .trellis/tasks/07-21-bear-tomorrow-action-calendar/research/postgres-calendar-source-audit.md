# Research: Bear 明日操作日历的 PostgreSQL 事实源

## Question

最近 25 条明日操作、连续两个实际交易日、每条 1x/50% 持仓腿的开收收益和上证同口径收益分别应从哪里读取，哪些缺口不能猜测？

## Sources

- `scripts/storage/postgres_daily_fact_db.py`
- `scripts/storage/database_service.py`
- `scripts/report/strategy_tracking_store.py`
- `scripts/input/index_cross_validation.py`
- `scripts/market_data/daily_price_runtime.py`
- `scripts/market_data/tushare_market_activity_service.py`
- `scripts/replay/sector_forward_replay.py`
- `scripts/portfolio/position_strategy_report.py`
- `tests/test_postgres_daily_fact_db.py`
- `wiki/交易思想/日报术语契约.md`

## Findings

### 明日操作：初始结构判断

- `strategy_performance_ledger` 以 `(mode, report_date)` 为主键，结构化保存 `stock_code`、`stock_name`、`can_new_entry`、`position_level`、`operation_state`、`execution_status` 和 `final_action`。
- `strategy_performance_record_fields` 以 `(mode, report_date, field_name)` 保存 `planned_new_entry_pct`、`new_entry_pct` 等扩展标量。
- `load_strategy_performance_ledger(mode)` 当前按 `report_date ASC` 读取全量，没有最近 25 条专用查询。
- 同日报告在同一 `mode` 下由主键去重；正式与 replay 必须按 mode 隔离。
- `stock_code` 为空只能证明没有结构化新标的，不能单独证明计划层的账户动作；执行日没有任何活跃两日腿时，账户结果显示 `空仓`，同时保留 `plan_action_kind=no_new_entry`。若上一份标的仍有第 2 日腿，则显示该标的并标注本日计划不新增。

### 个股开收到收涨幅

- `stock_daily_quotes_recent` 以 `(trade_date, ts_code)` 为主键，包含目标日 `open` 与 `close`。
- `query_stock_daily_quotes_recent(trade_date, stock_codes)` 精确按交易日查询；无目标日期行返回空列表。
- 表中 `pct_chg` 是昨收到今收口径，不符合本日历的账户日内比较；应使用 `(close / open - 1) * 100`。必须先以行是否存在区分“事实缺失”和“真实 0%”。

### 上证当日涨幅

- `index_daily_bars` 结构化保存指数代码、日期、开高低收、成交量额，但不保存涨跌幅。
- 上证代码规范化为 `sh000001`；查询结果日期字段为目标交易日。
- 本日历的上证当日涨幅应与账户收益保持同一时间边界：`(close / open - 1) * 100`。
- 交易日行可用于映射执行日，即使 `open/close` 缺失也不能把计划顺延到下一交易日；此时只把收益标为事实不足。同日重复且开收冲突时也不得静默采用最后一条。

### 下一实际交易日

- 现有账户日序 `_shift_trade_days()` 只跳过周末，无法覆盖法定休市，不适合作为本日历历史归属来源。
- 项目有 TuShare `trade_cal` 开市日查询，可正确跳过法定休市；但历史收益主链不应因本地事实缺失而联网补写。
- PostgreSQL 没有独立交易日日历表。对已发生历史记录，`report_date` 之后第一条上证日线日期是最可信的下一实际交易日。
- 每份具体标的连续映射下一、下二两个实际交易日，分别形成第 1 日和第 2 日 `1x/50%` 腿；若数据库缺相应交易日事实，历史记录留为事实不足，未来记录可显示待发生，不用自然日猜测。
- `不新增` 不清除前一计划的第 2 日腿；有第 2 日腿时账户仍显示持仓标的。没有任何活跃腿时账户显示空仓；明确 `明日空仓` 同样清除当日全部腿。
- 项目没有完整节日名称表，本任务对落在日历窗口的已核验日期保留带来源的最小映射（`2026-06-19：端午休假`）；交易日数据之外的周历空位标为样本外或记录缺失，不伪造其它节日名称。

### 现有 25 日跟踪不能直接复用

- `decision_ledger` 的近 25 日表记录入选日、标的和绝对后续 1/3/5 日收益，但没有逐条上证收益、独立空仓日和实际执行日字段。
- `strategy_tracking` 有相对上证公式和窗口汇总，但不可执行/空仓样本不进入可执行统计，不能直接满足本日历。

### Bear 插入位置

- 当前正式日报的 Mermaid 块是候选推导附录流程图，内容为 `flowchart TD`，不是甘特图。
- 用户所称甘特图对应 Bear 顶部由账户日序表渲染的 `.position-timeline-shell` 时间轴。
- 日历应作为 `markdown-body` 的第一个块，直接位于 `.position-timeline-shell` 之前；不得插到附录 Mermaid 流程图前。

## Recommendation

复用现有 PostgreSQL 表和 service/repository 边界，新建一个小型只读日历载荷构建器：优先以最近 25 条 `strategy_factor_snapshots` 日期及其 `strategy_factor_snapshot_fields` 最终明日决定为骨架；无快照记录时才兼容旧 `strategy_performance_ledger`。用 `index_daily_bars` 映射连续两个执行日并计算上证开收涨幅，用 `stock_daily_quotes_recent` 的 `open/close` 计算每腿收益。数据库缺失时显式留缺，不解析历史 Markdown/HTML/JSON，也不新增数据库表。

## Real Database Verification

- 数据库：`postgresql:///a_daily_report_psql_529`。
- `strategy_performance_ledger` 与 `strategy_performance_record_fields` 均为 0 行。
- `strategy_factor_snapshots` 有 25 个 frozen 报告日，范围为 `2026-06-16` 至 `2026-07-21`。
- 最终对象读取路径：
  - `two_layer_decision_payload.next_day_action.final_object_identity`
  - `two_layer_decision_payload.next_day_action.position_stance`
  - `two_layer_decision_payload.next_day_action.stock.code`
  - `two_layer_decision_payload.next_day_action.stock.name`
  - `two_layer_decision_payload.tomorrow_account_action.action`
- 真实 25 日还原为 11 个具体标的计划、17 个账户持仓日、8 个账户空仓日和 14 个不新增计划日；其中 6 个不新增计划日仍有上一份标的第 2 日持仓，另外 8 个是不新增计划且账户已空仓。
- 初始单日单票算法曾得到累计计划 `+41.52%`、同期上证昨收到今收 `+0.44%`、累计跑赢 `+41.07%`。该结果只保留为研究修订历史，因忽略第 2 日 `1x/50%`、重叠腿和开收时间边界，已失效，不得用于现行日历。
- 按最终账户口径重算：25 条记录中有 24 个已发生有效交易日、1 个待发生；累计账户收益 `+14.17%`，同期上证开收到收累计 `-0.55%`，累计跑赢上证 `+14.72%`。例如 `2026-06-18` 同时持有兴森科技第 2 日和兆易创新第 1 日，各占 `1x/50%`，合成账户当日收益 `+8.45%`。
- `save_strategy_performance_ledger()` 会先按 mode 删除策略主表、字段表和全部因子快照，因此日历链路禁止调用该接口，只允许只读查询。

## Impact

- PRD: 明确 PostgreSQL 主来源、四类操作语义、日期映射、收益公式与缺失规则。
- Design: 日历载荷在入口构建，HTML 渲染器只消费结构化数据。
- Implementation: 先补 repository/service 查询与纯函数测试，再接 Bear HTML 和视觉验证。
