# Research: 当前日报选路与运行摘要证据

## Question

为什么普通完整日报会在 PostgreSQL 已有目标日事实时仍重复长时间采集，以及旧失败为什么会在后续成功后继续影响排查？

## Sources

- `scripts/daily_report_entry_demo.py`
- `scripts/daily_report_source_health.py`
- `scripts/orchestrator/run_log_runtime.py`
- `scripts/daily_report_render.py`
- `tests/test_daily_report_entry_preflight.py`
- `tests/test_daily_report_source_health.py`
- `tests/test_run_log_runtime.py`

## Findings

- `daily_report_entry_demo.main()` 只依据显式 `--postgres-only`、`--replay` 选择数据路径；普通命令在数据源检查后直接调用 `get_daily_data()`。
- `get_daily_data()` 进入 `run_input_runtime()`，后者按顺序运行市场状态、涨跌停池、热榜、板块、日历、趋势、融资压力、监控、候选和报告输入整理，失败可能在较晚阶段才显现。
- `load_daily_report_data_from_postgres()` 已具备目标日严格事实判断；其 `_postgres_loaded_data_has_target_facts()` 会拒绝没有目标日宽表和没有目标日报告主干结构事实的载荷。
- `build_report_preflight()` 会继续检查两市成交额、指数、成交额排名、大盘涨跌统计、热度样本和已登记的决策事实，适合作为“可否重渲染”的第二层判断。
- 实时 `run_source_health_check()` 当前只要求 PostgreSQL 可连接；非 PostgreSQL-only 时不要求目标日期覆盖，也不负责自动选路。
- `run_with_log_capture()` 总会写 `latest_run.json`，失败时额外写 `latest_failure.json`；成功分支不处理已有 `latest_failure.json`，所以旧失败仍容易被误读为当前状态。
- 历史错误详情已经独立保存在 `logs/errors/<run-key>.json`，成功后移除“当前失败”摘要不会丢失历史错误证据。

## Recommendation

在普通完整日报入口增加一个只读的目标日 PostgreSQL 候选加载：复用严格事实判断，关闭该阶段的实时补取，再运行现有关键数据检查。通过则缓存数据并采用 PostgreSQL-only 行为；不通过则回到原实时路径。增加 `--force-live` 作为主动重采集出口。成功运行后移除旧的 `latest_failure.json`，保留历史错误文件。

## Impact

- PRD：形成目标日严格检查、自动快速路径、显式实时出口和成功状态收口四类可验收要求。
- Design：选路发生在数据源检查与完整采集之前；快速路径复用候选数据。
- Implementation：只改入口、运行摘要和直接相关测试，不拆分输入运行时，也不新增检查点体系。
