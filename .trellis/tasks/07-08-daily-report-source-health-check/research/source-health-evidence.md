# Research: 日报生成前健康检查现状证据

## Question

现有仓库已经有哪些数据源检查、凭证配置、日志和结果检查能力，可以作为生成前健康检查的基础？

## Sources

- `scripts/daily_report_entry_demo.py`
- `scripts/daily_report_render.py`
- `scripts/input/request_diagnostics_runtime.py`
- `scripts/orchestrator/run_log_runtime.py`
- `scripts/market_data/tushare_client.py`
- `scripts/market_data/xueqiu_hot_stock_service.py`
- `scripts/input/runtime.py`
- `scripts/input/iwencai_runtime.py`
- `scripts/xuangubao_intraday.py`
- `wiki/运行契约/日报数据源契约.md`
- `openspec/specs/architecture/error-handling.md`
- `openspec/specs/architecture/observability.md`

## Findings

- 入口已有 Tushare 跑前检查，使用 `check_tushare_runtime_ready(timeout_seconds=60)`，失败时抛出“停止生成”错误。
- 结果级检查集中在 `build_report_preflight(data, target_date)`，它能识别关键字段缺失、空载荷和登记失败，但发生在采集之后。
- 请求诊断已有 `build_request_diagnostics(module_logs, data_status, step_status)`，可统计请求失败、降级、回退和状态失败数。
- 日志捕获已有 `run_with_log_capture()`，并会写 `logs/latest_run.json` / `logs/latest_failure.json`，但当前摘要不是数据源任务表。
- 日报数据源契约要求登记过的判断因子失败、未采集或载荷为空时停止生成。
- Tushare 凭证来自 `TUSHARE_TOKEN` 和 `TUSHARE_HTTP_URL`。
- 雪球源依赖 `XUEQIU_COOKIE` 或 `XUEQIU_COOKIE_CAPTURE_DIR`，cookie 失效或接口返回空时不能继续生成关键判断。
- QuickTiny 异动检测 token 使用 `QUICKTINY_EXCHANGE_MONITOR_TOKEN` 或 `QUICKTINY_TOKEN`。
- iwencai 使用 `IWENCAI_API_KEY` / `IWENCAI_BASE_URL`，当前多处缺 key 时会走回补或返回空。
- 选股通新闻源使用 `XUANGUBAO_IVANKA_TOKEN`。
- 投资者问答补充源使用 `INVESTOR_QA_ENDPOINT_URL`。
- LLM 服务使用 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`。
- PostgreSQL 使用 `A_DAILY_REPORT_DATABASE_URL` 或 `DATABASE_URL`。

## Recommendation

第一版健康检查应当独立于完整采集链路，先复用已有低成本探测函数和请求诊断结构，再新增统一 JSON/HTML 输出。入口接入应放在完整采集前，并保留单独命令供用户先生成 Bear 风格检查表。

## Impact

- PRD: 需要把凭证、接口、目标日期覆盖、记录数、耗时和处理建议列为验收项。
- Design: 需要定义 `daily_report_source_health.v1` JSON 契约和 HTML 表格列。
- Implementation: 先做独立 CLI 和 HTML，再接入完整入口，避免一次性修改主链路。
