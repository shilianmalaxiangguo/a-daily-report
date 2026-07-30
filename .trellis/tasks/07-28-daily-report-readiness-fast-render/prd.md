# 日报目标日就绪检查、17:30 数据日期契约与快速重渲染

状态：✅ 已完成（2026-07-29；未提交、未推送）

## Goal

让通常在交易日 17:30（Asia/Shanghai）启动的正式日报，先按不同数据的真实发布时间判断目标日期事实是否可用，再决定直接重渲染或实时采集：融资允许使用明确属于上一交易日的最新事实，ETF 成交额必须包含目标日收盘事实；任何较早事实都不能冒充目标日可用数据。同时让一次成功运行明确取代旧失败摘要，减少小时级重复空跑和错误排查方向。对于必须实时生成的场景，历史比较只读取需要的小型字段，并在运行日志中记录可相加复核的阶段耗时，避免再次把 1GB 级历史快照完整解码而长期无可见进度。

## User Story

- **角色**：日报维护者
- **场景**：交易日收盘后等待龙虎榜发布，通常从 17:30 开始生成或重新生成当日正式日报和 Bear HTML
- **目标**：入口按融资与 ETF 各自的发布日期规则判断已有事实能否用于目标日报，能用就不再重复实时全量采集，不能用则只尝试目标日来源并明确失败原因
- **成功标准**：融资的上一交易日事实不会被误判缺失，ETF 上一交易日成交额不会被误判为目标日事实；快速路径、实时路径和最终产物遵守同一日期规则

### 用户旅程

1. 用户在目标交易日 17:30 后运行普通完整日报命令，系统先检查目标日期 PostgreSQL 事实。
2. 系统把融资事实解释为“截至哪个交易日”，允许目标日或上一交易日；超过一个交易日则不可用。
3. 系统要求 ETF 成交额窗口最后一行精确等于目标日；缺失时先尝试目标日当前列表或目标日 `fund_daily`，不得使用上一交易日替代。
4. 若全部关键事实通过检查，系统采用 PostgreSQL 快速重渲染；否则回到实时路径，目标日事实仍缺失时停止生成并说明缺口。
5. 用户确实需要重新采集时，使用 `--force-live` 明确要求实时路径。
6. 运行成功后，`latest_run.json` 反映成功结果，旧的当前失败摘要不再继续误导排查；历史错误文件仍保留。

## What I Already Know

- 普通入口当前只在用户显式传入 `--postgres-only` 时走 PostgreSQL，默认命令不会先判断目标日已有事实是否可重渲染。
- `load_daily_report_data_from_postgres()` 已用 `_postgres_loaded_data_has_target_facts()` 拒绝只有历史行、只有市场总量或只有外壳字段的载荷。
- `build_report_preflight()` 已负责完整日报关键数据检查，可作为快速路径的第二层资格判断。
- `run_source_health_check()` 的实时模式会检查 PostgreSQL 连接，但不会把目标日期事实完整度作为默认路径选择依据。
- `run_with_log_capture()` 每次都会更新 `latest_run.json`，但只有失败时写 `latest_failure.json`；后续成功不会让旧失败摘要失效。
- 本工作区已有 2026-07-27 日报修复相关未提交修改，本任务必须与其共存，不回滚、不重排、不顺手清理。
- 融资融券汇总约在次日 8:30 更新上一交易日数据；因此 2026-07-27 周一 17:30 运行时，最新事实为 2026-07-24 周五属于正常情况。
- ETF 日线 `amount` 是每日收盘成交额；ETF 份额、规模等数据才按次日约 8:30 更新上一交易日数据，不能把后者的规则套到成交额。
- 当前 2026-07-27 PostgreSQL 事实正确：融资最新日为 2026-07-24、滞后一个交易日；ETF 最新日为 2026-07-27。
- 当前 ETF payload 仍可能把“请求 2026-07-27、最后一行仅到 2026-07-24”的序列标为 `available=True` 且覆盖正常，这是快速重渲染会误收旧事实的确定缺口。
- 2026-07-28 本次 Codex 会话从请求到最终交付共 `3558.878` 秒，约 `59分19秒`；其中日报程序自身为 `1650.74` 秒，约 `27分31秒`，其余主要是独立审计等待、复核和视觉检查。
- 日报程序的数据采集只占 `162.46` 秒；采集前的目标日选路与数据源检查约 `36.28` 秒，实时采集完成后的历史比较、报告构建和快照保存为 `24分12秒`，是程序内部最大耗时区间。
- 运行中进程峰值物理内存约 `12.3GB`，采样时正在通过 `json.load` 解码约 `1.2GB` 的 `snapshots/2026-07-22.json`。同一文件使用现有紧凑字段读取器实测 `12.175` 秒、峰值约 `479.8MB`。

## Problem Definition

- **需要改善的决定**：一次 17:30 启动的普通完整日报，哪些事实已经达到目标日可用条件，以及应当实时采集还是直接使用 PostgreSQL 重渲染。
- **事实边界**：ETF 成交额只承认最后事实日等于目标日的载荷；融资只承认目标日或明确的上一交易日事实。其他日期存在数据不能替代这两项规则。
- **不可改变项**：replay、显式 PostgreSQL-only、只采集不生成、只做数据源检查、单票诊断和正式历史保护策略保持原行为。
- **完成证据**：定向测试证明正确选路、错误日期和不完整载荷不会误选、主动实时采集可用、成功运行收口旧失败摘要。

## In Scope

- 普通完整日报入口的目标日 PostgreSQL 就绪检查和数据路径选择。
- PostgreSQL 就绪时复用已加载数据，避免重复查询和实时全量采集。
- 显式 `--force-live` 参数及其兼容行为。
- 最近运行与旧失败摘要的成功收口。
- 与上述行为直接相关的单元测试和定向回归验证。
- ETF 成交额生产端、输入汇总、正式生成前检查和 PostgreSQL 快速重渲染的一致目标日校验。
- 融资“允许一个交易日滞后、拒绝两个及以上交易日滞后”的既有行为确认与回归保护。
- 三个历史回退读取点改用现有紧凑快照读取能力，且保留测试注入 loader 的兼容行为。
- 日报入口按非重叠阶段记录耗时，在终端、运行日志和运行观察信息中保留总耗时与阶段明细。
- 记录 2026-07-28 会话与日报程序的分层耗时证据、主要耗时项和可优化结论。
- 实时、replay 或 PostgreSQL 读取返回空数据时，入口不得把补充日期字段后的空结果当作成功运行。

## Requirements

- [x] R1: 普通完整日报在实时全量采集前检查目标日期 PostgreSQL 事实，并输出可读的路径选择结论。
- [x] R2: 只有目标日期数据同时通过现有 PostgreSQL 目标事实判断和 `build_report_preflight()` 关键数据检查时，才取得快速重渲染资格。
- [x] R3: 快速重渲染取得资格时，入口自动采用 PostgreSQL-only 行为并复用已检查的数据，不调用 `get_daily_data()`。
- [x] R4: PostgreSQL 事实缺失、不完整、日期不符或检查异常时，普通完整日报保持现有实时路径；`--force-live` 必须无条件保留实时路径。
- [x] R5: replay、显式 `--postgres-only`、`--no-report`、`--source-health-only` 和单票诊断保持现有选路含义，不被自动快速路径改写。
- [x] R6: 成功运行后旧 `latest_failure.json` 不再表示当前故障，同时保留 `logs/errors/` 下的历史错误记录。
- [x] R7: 路径选择、运行观察信息和终端输出只记录日期、结论和脱敏后的原因，不泄露数据库连接串或其他凭证。
- [x] R8: 对 17:30 当日生成建立分数据日期契约：ETF 成交额最后事实日必须等于目标日；融资最后事实日可以等于目标日或上一交易日，并保留目标日、最后事实日和滞后交易日数。
- [x] R9: ETF 历史接口缺少目标日时，只能使用来源日期为目标日且覆盖正常的新浪当前列表或 Tushare `fund_daily` 补齐；所有目标日来源都不可用时，ETF 结果必须不可用并停止生成，不得沿用上一交易日成交额。
- [x] R10: ETF 日期判断必须在数据生产端、输入汇总、正式生成前检查和 PostgreSQL 快速重渲染四处一致生效，旧 PostgreSQL payload 也不能绕过目标日检查。
- [x] R11: 融资交易日历缺失时不得把缺失日期猜成休市日；主来源过旧时尝试日期更近的市场级备用来源，最终仍超过一个交易日则不可用。
- [x] R12: 默认生产路径的主线历史、板块成交历史和板块资金历史不得调用完整快照 loader；只读取历史判断需要的紧凑字段，并保留既有主线和成交额兼容字段形状。测试注入自定义 `load_data_snapshot` 时继续使用注入值。
- [x] R13: 日报成功运行时，运行日志必须记录可相加复核的阶段名称、耗时和占总耗时比例；阶段合计与总耗时的差额必须作为“其他收尾”显式记录，不能只保留一个总数。
- [x] R14: 运行观察信息必须保留同一份阶段耗时结构，便于下次直接定位慢在数据检查、采集、报告构建、事实同步还是产物保存。
- [x] R15: 实时、replay 或 PostgreSQL 读取返回空数据或非字典载荷时，必须明确停止生成并记录失败原因，不能返回成功。

## Non-functional Requirements

### 性能

- 目标日就绪检查只允许本地 PostgreSQL 读取、现有纯本地整理和关键数据检查，不触发实时全量采集。
- 快速路径必须复用检查阶段已加载的数据，避免为同一决策重复读取完整快照。
- ETF 实时分支沿用现有 120 秒总预算；预算内只执行现有目标日来源链，不增加小时级轮询或外层重复生成。
- 以 `snapshots/2026-07-22.json` 约 1.2GB 文件为固定基准，紧凑读取耗时低于 30 秒、峰值物理内存低于 1GB。
- 本轮不对整次实时日报设不受外部网络影响的绝对完成时间；验收以消除完整历史快照解码和提供可复核阶段耗时为准。

### 安全

- 数据库异常和路径选择原因沿用现有脱敏策略，不输出连接串原文。

### 兼容性

- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 不改变报告判断逻辑、候选池、明日对象、仓位、执行性质、B1/B2 或退出动作。
- 不改变正式历史覆盖和 replay 写入位置。
- 不把 17:30 写成新的调度器或系统时钟限制；它是正式日报的运行前提，日期判断仍由显式 `target_date` 和来源日期完成。

## Acceptance Criteria

- [x] AC-R1-1: 给定目标日 PostgreSQL 完整事实，运行普通完整日报时，在任何 `get_daily_data()` 调用前输出快速重渲染结论。
- [x] AC-R2-1: 给定只有其他日期事实、只有历史结构行、只有市场总量或关键数据检查失败的载荷，快速路径判定为不可用。
- [x] AC-R2-2: 给定目标日严格事实和关键数据检查均通过的载荷，快速路径判定为可用。
- [x] AC-R3-1: 快速路径可用时，`load_daily_report_data_from_postgres()` 的结果被后续生成复用，`get_daily_data()` 不被调用。
- [x] AC-R4-1: 快速路径不可用时，入口继续调用现有实时数据源检查和 `get_daily_data()`。
- [x] AC-R4-2: 传入 `--force-live` 时，即使目标日 PostgreSQL 事实完整，也不执行自动快速重渲染。
- [x] AC-R5-1: replay、显式 PostgreSQL-only、no-report、source-health-only 和单票入口的已有定向测试继续通过。
- [x] AC-R6-1: 先存在失败摘要再完成成功运行后，`latest_run.json` 为成功，`latest_failure.json` 不再存在；原 `logs/errors/<run-key>.json` 仍存在。
- [x] AC-R7-1: 新增测试中的错误原因和运行摘要不包含数据库 URL 原文。
- [x] AC-R8-1: 给定目标日 2026-07-27、融资最后事实日 2026-07-24 和交易日历包含 2026-07-24/2026-07-27，融资结果可用且 `stale_trade_days=1`。
- [x] AC-R8-2: 给定目标日 2026-07-27、ETF 最后一行 2026-07-24，即使有行且覆盖率正常，ETF 结果仍不可用并明确缺少目标日成交额。
- [x] AC-R9-1: 给定 17:30 当日运行、上一交易日有已验收的 24 日历史底座、目标日新浪当前列表覆盖不低于 95%，组合结果最后一行等于目标日且可用。
- [x] AC-R9-2: 给定新浪未取得目标日成交额、Tushare `fund_daily` 有目标日完整数据，结果采用 Tushare 目标日数据；两者都没有目标日时停止生成。
- [x] AC-R10-1: 给定 PostgreSQL 中 ETF payload 请求日为 2026-07-27、最后事实日为 2026-07-24，输入汇总与正式生成前检查均判为不可用，自动选路不得采用快速重渲染。
- [x] AC-R10-2: 给定 PostgreSQL 中 ETF 最后事实日等于目标日且覆盖正常，新增日期检查不改变快速重渲染资格。
- [x] AC-R11-1: 给定 2026-07-23 至 2026-07-27 相隔两个交易日，融资结果不可用；若备用来源提供 2026-07-24，则采用备用事实并按一个交易日滞后处理。
- [x] AC-R12-1: 给定默认生产 loader，三个历史回退模块都调用公开紧凑读取器，完整 `load_data_snapshot()` 若被调用则测试失败。
- [x] AC-R12-2: 给定测试注入的 `load_data_snapshot()`，三个历史回退模块仍读取注入数据并保持现有结果。
- [x] AC-R12-3: 对约 1.2GB 的 2026-07-22 快照重复实测，紧凑读取低于 30 秒且峰值物理内存低于 1GB，并能返回主线、板块成交和板块资金所需字段。
- [x] AC-R12-4: 给定只包含复数主线记录、板块成交快照、市场成交额别名或嵌套成交额的历史快照，紧凑读取仍保留消费者需要的字段。
- [x] AC-R13-1: 给定固定计时样本，运行日志展示总耗时、每阶段秒数、比例和“其他收尾”，阶段秒数之和与总耗时在显示精度内一致。
- [x] AC-R14-1: 运行观察信息包含阶段耗时列表，字段仅为阶段名、秒数和占比，不含连接串、凭证或完整业务载荷。
- [x] AC-R15-1: 给定 `get_daily_data()` 返回空字典，入口记录加载为空与生成前检查失败，并抛出关键数据不完整错误而不返回成功。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md`、`implement.md` 和必要研究记录已补齐。
- [x] `implement.jsonl`、`check.jsonl` 只引用本任务需要的 Spec 与研究摘要。
- [x] 新增和相关既有测试使用 Python 3.14 通过。
- [x] commit 前独立子代理审计完成，发现已处理或明确记录。
- [x] PRD 状态更新为已完成；本轮不提交、不推送。

## Out Of Scope

- 不实现逐数据源检查点、断点恢复或完整采集任务编排。
- 不修改数据库结构、环境配置或 CI。
- 不优化各外部数据源自身耗时。
- 不在本轮并发调用外部数据源；选股通等单源耗时先由阶段统计持续观察，另行评估限流和失败放大风险。
- 不重构日报完整生成链路或报告决策逻辑。
- 不把 ETF 份额、规模、净值的次日更新规则套用到 ETF 成交额。
- 不用上一交易日 ETF 成交额继续生成，也不为了等待 ETF 数据启动小时级轮询。
- 不修改龙虎榜发布时间、采集逻辑或 17:30 调度方式。
- 不提交或推送代码。

## Non-goals

- 不保证实时全量采集永不失败；本任务只在已有目标日事实可用时避免不必要重跑，并让缺失更早可见。
- 不用其他日期的事实冒充目标日期。
- 不把快速重渲染变成默认覆盖正式历史的授权。
- 不改变候选生成、最终对象、仓位、执行性质、B1/B2 或退出动作来换取速度。

## Source Of Truth

- 融资更新时间以 Tushare《融资融券交易汇总》所引交易所发布时间和明确的交易日历为准。
- ETF 成交额以 Tushare《ETF 日线行情》的 `trade_date/amount`、新浪目标日当前列表及本地已验收 PostgreSQL 历史窗口为准。
- ETF 份额规模的次日更新时间只解释份额、规模、净值类字段，不改变成交额日期要求。

## Root Cause

- **现象**：ETF 请求目标日为 2026-07-27、最后事实日仅到 2026-07-24 时，payload 仍可能显示可用且覆盖正常，随后被输入汇总、正式生成前检查和快速重渲染接受。
- **根因**：ETF 生产端把“存在任意行”当作可用，覆盖检查在找不到目标日时默认检查最后一行；下游只复核行数和覆盖率，没有复核最后事实日。
- **影响范围**：17:30 当日生成时目标日 ETF 历史接口暂未更新、以及 PostgreSQL 保存了旧 ETF payload 的场景。

## Reproduction

1. 构造请求日期 `2026-07-27`，只传入一行 `2026-07-24` ETF 成交额且覆盖数量正常。
2. 预期：明确缺少目标日 ETF 成交额，结果不可用。
3. 当前实际：`available=True`、`coverage_anomaly=False`、`coverage_status=normal`。

## Fix Strategy

- **修改点**：ETF 日期元数据与可用性、目标日备用来源触发、输入汇总、正式生成前检查、自动快速重渲染资格和直接相关测试。
- **修改方式**：把“目标日存在”与“样本覆盖正常”作为两个必须同时满足的独立条件；融资继续按交易日而不是自然日计算允许滞后。
- **风险评估**：中。修改会让过去被误收的旧 ETF 序列停止生成，但不会改变目标日事实完整时的报告判断或输出结构。

## Regression Guard

- ETF 生产端覆盖目标日存在、目标日缺失、当前列表补齐、Tushare 补齐和所有来源缺失。
- 输入汇总与正式生成前检查覆盖“有 25 行但最后日期错误”的情况。
- 快速重渲染覆盖旧 PostgreSQL payload 被拒绝和精确目标日 payload 继续通过。
- 融资保留一个交易日可用、两个交易日不可用、交易日历缺失和更近备用来源四类用例。
- 历史读取回归同时覆盖默认紧凑读取和自定义 loader 注入，避免为了性能破坏测试与 replay 兼容路径。
- 耗时统计使用非重叠阶段并保留未归类差额，避免下次仍只能看到一个无法解释的总耗时。

## Technical Notes

### 参考来源

- `.trellis/tasks/07-28-daily-report-readiness-fast-render/research/current-runtime-evidence.md`
- `.trellis/tasks/07-28-daily-report-readiness-fast-render/research/1730-asof-date-contract.md`
- `.trellis/tasks/07-28-daily-report-readiness-fast-render/research/recurring-asof-date-break-loop.md`
- `.trellis/tasks/07-28-daily-report-readiness-fast-render/research/20260728-runtime-performance.md`
- `.trellis/tasks/07-22-fix-etf-turnover-history-coverage/` — 已验收的上一交易日窗口与目标日当前列表组合方式
- https://tushare.pro/document/2?doc_id=58 — 融资融券交易汇总更新时间
- https://tushare.pro/document/2?doc_id=127 — ETF 日线成交额
- https://tushare.pro/document/2?doc_id=408 — ETF 份额规模更新时间
- `.trellis/spec/backend/quality-guidelines.md`
- `.trellis/spec/backend/error-handling.md`
- `.trellis/spec/backend/logging-guidelines.md`
- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/spec/guides/cross-layer-thinking-guide.md`
- `wiki/运行契约/日报数据源契约.md`

### 影响区域

- `scripts/daily_report_entry_demo.py`：目标日就绪检查、路径选择、显式实时参数和数据复用。
- `scripts/orchestrator/run_log_runtime.py`：成功运行后旧失败摘要收口。
- `tests/test_daily_report_entry_preflight.py`：路径选择与兼容回归。
- `tests/test_run_log_runtime.py`：最近运行状态回归。
- `scripts/input/tushare_runtime.py`：ETF 目标日存在性、目标日备用来源和融资日期规则。
- `scripts/input/runtime.py`：ETF 输入汇总日期判断。
- `scripts/daily_report_render.py`：正式生成前 ETF 目标日检查。
- `scripts/daily_report_entry_demo.py`：PostgreSQL 快速重渲染的最终日期复核。
- `tests/test_tushare_input_runtime.py`、`tests/test_input_runtime.py`、`tests/test_daily_report_render.py`、`tests/test_daily_report_entry_preflight.py`：跨层日期回归。
- `scripts/domains/market_state/daily_metric_history_index.py`：公开现有紧凑历史快照读取器。
- `scripts/domains/market_state/mainline_history_runtime.py`、`sector_turnover_history_runtime.py`、`support.py`：默认历史回退改为紧凑读取。
- `scripts/daily_report_entry_demo.py`：非重叠阶段耗时记录和运行日志表。
- `tests/test_daily_metric_history_index.py`、`tests/test_mainline_history_runtime.py`、`tests/test_sector_turnover_history_runtime.py`、`tests/test_market_state_support.py`：紧凑读取与注入兼容回归。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_source_health`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_run_log_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_html_output`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_margin_pressure_runtime tests.test_tushare_input_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_input_runtime tests.test_daily_report_render tests.test_daily_report_entry_preflight`
- 使用固定输入复现“ETF 最后一行早于目标日”并确认四层均不再把它判为可用。
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_metric_history_index tests.test_mainline_history_runtime tests.test_sector_turnover_history_runtime tests.test_market_state_support`
- 对 `snapshots/2026-07-22.json` 运行紧凑读取基准，记录耗时和峰值物理内存。

## 落地 commit

本轮按用户要求不提交。
