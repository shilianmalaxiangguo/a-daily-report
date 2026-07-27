# Research: ETF 两市成交额历史来源诊断

## Question

为什么 2026-07-22 ETF 当前列表约 1600 只，而新浪历史聚合只有约 1000 只；是否发生反爬，以及还有哪些可验证来源可以支持 25 日趋势？

## Sources

- `scripts/input/tushare_runtime.py`
- `scripts/market_data/tushare_client.py`
- `scripts/storage/postgres_daily_fact_db.py`
- PostgreSQL `a_daily_report_psql_529` 中 2026-07-21 日报事实
- 新浪 ETF 当前分类列表与逐证券历史接口
- 当前 `TUSHARE_HTTP_URL` 的标准 DataApi POST 接口
- AkShare 东方财富 ETF 接口

## Findings

### 雪球凭据

- 新 Cookie 已写入 `.env` 的 `XUEQIU_COOKIE`。
- 窄检查返回热榜 100 条、热榜理由 8 条，登录态可用。

### 新浪 ETF

- `ak.fund_etf_category_sina("ETF基金")` 返回 1607 个唯一沪深代码，其中上海 906、深圳 701。
- 2026-07-22 当前列表中 1606 只有正成交额，覆盖率 99.94%。
- 对 1607 个逐证券历史 URL 做 16 并发请求，约 52 秒完成：1606 个返回非空响应，仅 1 个 HTTP 异常。没有整体反爬或批量拒绝证据。
- 问题发生在历史记录有效日期层：同一批接口聚合后的目标历史日覆盖会从约 1100 只进一步波动到数百只，不能稳定证明 25 日趋势完整。
- 当前实现把 HTTP 错误、空响应、解码失败、缺目标日期和成交额非正数合并为 `empty_etf_count`，诊断粒度不足，但这不影响本次“该历史聚合不可作为完整来源”的结论。

### Tushare

- 当前 `.env` 的 URL 走官方 `tushare.pro.client.DataApi` POST 协议，不是项目的 Replay GET 适配器。
- 标准 POST 的 `fund_daily` 可用：2026-07-22 单日约 2075 行，其中与新浪样本池相交且正成交 1606 只；2026-07-21 为 1603 只。
- 项目 `_fetch_tushare_fund_daily_amount_rows()` 首次调用显式传 `offset=0`。当前代理对省略 offset 的同一请求返回数据，对 `offset=0` 返回空表，这是确定的兼容性 bug。
- 代理的 `start_date/end_date` 批量查询返回空表；逐日查询在 2026-06-17 至 07-03、07-21、07-22 可用，但 07-06 至 07-20 为空，因此不能单独拼出 25 日。
- 按 `ts_code + start_date/end_date` 查询单只 ETF 可得到完整 25 日，但 1607 只串行预计约 35 分钟，不适合作为日报正常路径。

### PostgreSQL

- 2026-07-21 的 `etf_turnover_series` 有连续 25 个交易日，从 2026-06-16 至 2026-07-21。
- 每日有成交 ETF 数从 1561 增加到 1603；`coverage_status=normal`、`coverage_anomaly=False`，总体覆盖 99.88%。
- 该窗口已经通过 2026-07-21 正式日报的数据完整性检查，可作为下一交易日的历史底座。
- 现有 row 只有 `trade_date`、成交额、覆盖数量和变化率；本次组合时需要显式补充来源、来源日期和查询日期。

### 其他来源

- `ak.fund_etf_spot_em()` 与 `ak.fund_etf_hist_em()` 当前均被远端断开连接，不能作为本次稳定来源。
- PostgreSQL 没有单独的 ETF 逐证券日额表，只有日报已验收的聚合窗口。

## Recommendation

优先使用“上一交易日已验收 PostgreSQL 窗口 + 目标日新浪当前列表”的滚动续接方式：

1. 精确确定上一交易日并加载其 ETF 25 日窗口。
2. 验证窗口连续、最后日期等于上一交易日、历史 payload 未标记为不完整。
3. 保留最近 24 日，追加目标日 1606/1607 当前列表汇总。
4. 为每行补充来源、来源日期和查询日期，并重新运行现有 70%/95% 检查。
5. 任一条件不满足时继续尝试 Tushare 备用来源；仍不完整则停止生成。

同时修复 Tushare 首次分页传 `offset=0` 的问题，但不把不完整日期序列当作成功来源。

## Impact

- PRD: 保持严格完整性要求，增加上一交易日事实连续性和来源日期验收。
- Design: 在输入模块内复用现有 `DatabaseService` 注入模式，避免入口脚本直接拼接数据。
- Implementation: 先补组合与拒绝路径测试，再改 ETF 函数，最后生成 2026-07-22 正式产物。
