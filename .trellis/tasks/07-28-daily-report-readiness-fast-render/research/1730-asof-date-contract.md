# Research: 17:30 日报的融资与 ETF 事实日期契约

## Question

目标交易日 17:30（Asia/Shanghai）开始生成正式日报时，融资信息和 ETF 成交额分别允许使用哪一个事实日期；当前代码是否会把旧日期事实误判为可用？

## Sources

- Tushare《融资融券交易汇总》：https://tushare.pro/document/2?doc_id=58
- Tushare《ETF 日线行情》：https://tushare.pro/document/2?doc_id=127
- Tushare《ETF 份额规模》：https://tushare.pro/document/2?doc_id=408
- Tushare《ETF 实时日线》：https://tushare.pro/document/2?doc_id=400
- `scripts/domains/market_state/margin_pressure_runtime.py`
- `scripts/input/tushare_runtime.py`
- `scripts/input/runtime.py`
- `scripts/daily_report_render.py`
- `scripts/daily_report_entry_demo.py`
- `.trellis/tasks/07-22-fix-etf-turnover-history-coverage/`
- PostgreSQL 中 2026-07-27 日报事实的只读检查

## Findings

### 公开资料

- 融资融券交易汇总文档原文为“交易所于每天 8 点 30 左右更新上一日数据”。目标日 17:30 运行时，当日融资事实尚未发布属于正常情况。
- ETF 日线行情文档说明其接口获取“每日收盘后成交数据”，`amount` 是成交额。目标日收盘后生成日报时，ETF 成交额应属于目标日。
- ETF 份额规模文档原文为“次日早 8 点 30 左右更新上一交易日的数据”。该规则适用于份额、规模、净值等字段，不适用于 ETF 日线成交额。
- ETF 实时日线也提供当日 `amount`，进一步说明成交额没有天然滞后一个交易日的业务属性。

### 17:30 运行解释

- 对目标交易日 D，融资最后事实日允许为 D 或 D 的上一交易日。周一 2026-07-27 的上一交易日是周五 2026-07-24，因此该融资事实可用。
- 对目标交易日 D，ETF 成交额最后事实日必须为 D。数据提供方暂时只返回上一交易日属于来源延迟，不能把旧成交额写入 D 日日报。
- 17:30 等待龙虎榜发布是正式日报的运行前提；本任务不修改龙虎榜采集或调度器。

### 当前事实

- 2026-07-27 PostgreSQL 融资：`available=True`、`latest_data_date=2026-07-24`、`stale_trade_days=1`。
- 2026-07-27 PostgreSQL ETF：最后一行 `trade_date=2026-07-27`、`coverage_anomaly=False`，当前正式日报没有引用错日。
- 融资日期相关 8 项定向测试通过，覆盖一个交易日可用、两个交易日不可用、交易日历缺失和更近备用来源。

### 当前缺口

- `_build_etf_turnover_series_payload()` 使用 `bool(rows)` 设置 `available`，没有要求最后一行等于请求日。
- `_annotate_etf_turnover_coverage_quality()` 找不到目标日时默认检查最后一行，可能把上一交易日覆盖率判为正常。
- 输入汇总和正式生成前检查只复核行数与覆盖质量，没有复核最后事实日。
- PostgreSQL 快速重渲染只额外复核大盘涨跌统计日期，旧 ETF payload 可以通过现有关键数据检查。
- 最小复现：请求 `2026-07-27`，只提供 `2026-07-24` 一行且覆盖数量正常，结果仍是 `available=True`、`coverage_anomaly=False`、`coverage_status=normal`。

## Recommendation

1. 保持融资规则：允许精确一个交易日滞后，保留目标日、最后事实日和滞后交易日数；超过一个交易日则不可用。
2. ETF 数据生产端独立计算最后事实日；只有目标日存在且覆盖正常时才可用。
3. 目标日缺失时，在现有 120 秒总预算内尝试目标日新浪当前列表和 Tushare `fund_daily`；仍缺失则停止生成，不使用上一交易日成交额。
4. 输入汇总、正式生成前检查和 PostgreSQL 快速重渲染重复复核 ETF 目标日，以保护旧 payload 和持久化事实。
5. 使用固定日期测试覆盖四层数据流，并确认目标日事实完整时不改变报告判断字段。

## Impact

- PRD：增加 17:30 运行前提、融资与 ETF 分数据日期要求、失败行为和可度量验收。
- Design：增加 ETF 目标日来源流、payload 日期字段和四层复核。
- Implementation：在现有 ETF 120 秒预算内做最小修改，不新增调度器、外层轮询或其他数据源。
