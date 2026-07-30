# Implementation: 日报目标日就绪检查、17:30 数据日期契约与快速重渲染

## Prerequisites

- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 保留当前 2026-07-27 日报修复相关修改，不回滚、不格式化无关文件。
- 实现前读取本任务 `prd.md`、`design.md`、研究记录和清单中的后端 Spec。
- 运行场景固定为目标交易日 17:30（Asia/Shanghai）后；不修改调度器或龙虎榜采集。

## Ordered Checklist

- [x] I1: 为 PostgreSQL loader 增加“候选检查阶段不实时补取”的窄参数，默认保持现行为。
- [x] I2: 在日报入口实现普通完整日报资格判断和目标日快速路径选择，复用现有严格事实判断与关键数据检查。
- [x] I3: 缓存通过检查的 PostgreSQL 数据，后续生成直接复用；记录最终路径和脱敏原因。
- [x] I4: 增加 `--force-live` 并排除 replay、显式 PostgreSQL-only、no-report、source-health-only、单票诊断的自动改写。
- [x] I5: 成功运行后移除旧 `latest_failure.json`，保留历史错误文件。
- [x] I6: 新增入口和运行摘要定向测试，覆盖通过、缺失、关键数据失败、强制实时及兼容路径。
- [x] I7: 运行相关测试；修复本任务引入的回归。
- [x] I8: 在 ETF payload 生产端补齐 `latest_data_date`、`is_stale_for_target` 和目标日可用性；目标日缺失时不得继续返回可用。
- [x] I9: 把“目标日缺失”加入现有新浪当前列表和 Tushare `fund_daily` 备用来源条件，复用 120 秒总预算，不增加外层轮询。
- [x] I10: 在输入汇总和正式生成前检查中同时校验 ETF 最后事实日与覆盖质量，并给出可读的目标日缺失原因。
- [x] I11: 在 PostgreSQL 快速重渲染资格判断中复核 ETF 目标日；兼容旧 payload 通过 `rows` 推导最后事实日，不允许字段缺失绕过检查。
- [x] I12: 增加 ETF 生产端、输入汇总、正式生成前检查和快速选路四层回归；覆盖 17:30 当前列表补齐、Tushare 补齐、旧日误收和精确目标日通过。
- [x] I13: 确认融资允许一个交易日滞后、拒绝两个交易日滞后、交易日历缺失不猜休市日、主来源过旧时采用更近备用来源；8 项定向测试已通过。
- [x] I14: 运行完整定向验证和 2026-07-27 PostgreSQL 快速重渲染演练，确认报告判断字段不变。
- [x] I15: 启用独立子代理做 commit 前审计，主代理核验发现并完成最终验证。
- [x] I16: 记录 2026-07-28 会话总耗时、日报程序耗时、采集步骤、历史解码内存和协作等待耗时，形成可复核研究表。
- [x] I17: 公开现有紧凑历史快照 loader，并让主线历史、板块成交历史和板块资金历史的默认回退路径使用它；保留自定义 loader 注入。
- [x] I18: 增加默认路径不得调用完整快照 loader、注入路径仍兼容的定向回归。
- [x] I19: 在日报入口记录非重叠阶段耗时，写入终端、运行日志和运行观察信息；补充总数与阶段合计一致性测试。
- [x] I20: 使用 Python 3.14 运行历史读取与入口定向回归，并对 1.2GB 快照重复运行紧凑读取基准。
- [x] I21: 运行正式稿与 replay 接受检查，比较最终对象、仓位、执行性质、B1/B2 和退出动作不变。
- [x] I22: 启用新的独立子代理做本轮 commit 前审计；宽范围审计超过 10 分钟后停止，改用两个紧凑独立审计并取得具体发现。
- [x] I23: 修复审计发现的 PostgreSQL-only replay 回读、紧凑字段兼容缺口、空数据成功退出和阶段结构测试不足。
- [x] I24: 修正耗时证据中的 6 秒算术偏差，并把采集前准备、实时采集和采集后区间分开记录。
- [x] I25: 运行最终定向测试、1.2GB 基准、正式稿与 replay 接受检查及工作区差异检查。

## Verification Evidence

- 2026-07-28: Python 3.14 编译检查通过。
- 2026-07-28: `test_daily_report_entry_preflight`、`test_daily_report_source_health`、`test_run_log_runtime`、`test_daily_report_entry_html_output` 共 146 项通过。
- 2026-07-28: 日期字段缺失、关键数据检查异常、显式模式保留和运行观察字段新增 4 项针对性用例通过。
- 2026-07-28: `git diff --check HEAD` 通过。
- 2026-07-28: ETF 日期与快速重渲染直接相关四模块完整回归 303 项通过；数据源检查、运行日志、Bear HTML 和融资压力扩展回归 92 项通过。
- 2026-07-28: 官方资料确认融资汇总约在次日 8:30 更新上一交易日数据，ETF 日线成交额是收盘后目标日数据；次日更新时间属于 ETF 份额规模类数据。
- 2026-07-28: 融资日期 8 项定向测试通过；当前 PostgreSQL 中 2026-07-27 融资最后事实日为 2026-07-24，滞后一个交易日且可用。
- 2026-07-28: ETF 错日反例已在生产端、输入汇总、正式生成前检查和快速选路四层拒绝；精确目标日、当前列表补齐、Tushare 补齐与来源全部失败均有回归保护。
- 2026-07-28: 修复备用来源预算首次检查的缩进回归；预算耗尽时不再查询 Tushare 交易日历，单项与四模块完整回归均通过。
- 2026-07-28: 普通命令 `scripts/daily_report_entry_demo.py 2026-07-27` 自动采用 PostgreSQL-only，149.28 秒完成 replay 重渲染，未覆盖正式历史。
- 2026-07-28: 正式稿与 replay 稿的日报一致性检查均通过，Bear HTML 均存在且含 `bear-shell`、动作区和证据区结构。
- 2026-07-28: 当前 ETF 最后事实日为 2026-07-27；融资最后事实日为 2026-07-24、滞后 1 个交易日；覆盖质量与事实日期分别检查。
- 2026-07-28: 正式判断投影 SHA256 为 `7a4784e745d466db620a9263271a0a8fb0b0b0c24e163ec9c5a7853cb940a850`，与修改前基线一致。
- 2026-07-28: 最终独立微审计发现 Tushare 注入日历/逐日读取异常会清空既有 Sina 诊断载荷，且逐日读取中途耗尽预算未记录原因；已在备用函数内部收口并新增 3 项回归。
- 2026-07-28: 审计发现修正后，5 项异常与预算定向测试、303 项四模块完整回归均通过；Python 3.14 编译检查与 `git diff --check HEAD` 通过。
- 2026-07-28: 正式稿与 Bear、上证缠论、淘汰赛、板块资金页面对照检查全部通过；replay 稿与 Bear 对照检查通过。
- 2026-07-29: 2026-07-28 会话精确总时长为 3558.878 秒；日报程序为 1650.74 秒，实时采集为 162.46 秒，分层耗时已写入研究记录。
- 2026-07-29: 紧凑历史读取、主线历史、板块成交历史、板块资金历史、入口与渲染共 205 项 Python 3.14 测试通过；相关文件编译检查通过。
- 2026-07-29: 约 1.2GB 的 `snapshots/2026-07-22.json` 紧凑读取复测为 9.779 秒，最大 RSS 503,169,024 字节（约 479.9MiB）；主线、板块成交和板块资金字段均存在。
- 2026-07-29: 龙虎榜显式原始数/归并数/买卖数均为 0、但排行非空的反例通过；记录数取买卖排行较大值，不相加。
- 2026-07-29: 2026-07-28 正式稿与 replay 稿接受检查均通过；两者最终对象=无、新仓=0%、收盘目标仓位=0%、执行性质=无明日执行对象、B1/B2=无、旧仓动作=无旧仓需要处理。
- 2026-07-29: 独立紧凑审计发现 PostgreSQL-only 主线历史仍可能读 series replay、紧凑字段遗漏旧兼容形状、空载荷可能成功退出，以及耗时表余数多记 6 秒；对应代码、测试与研究证据已修正。
- 2026-07-29: 修正后历史索引、主线历史、板块成交历史和入口共 96 项 Python 3.14 定向测试通过。
- 2026-07-29: 最终相关回归 208 项通过；Python 3.14 编译、Trellis 清单校验和 `git diff --check HEAD` 均通过。
- 2026-07-29: 补齐兼容字段后的 1.2GB 紧凑读取为 18.85 秒，最大 RSS 493,355,008 字节（470.5MiB），三个目标历史字段均存在。
- 2026-07-29: 收口时再次运行 208 项相关回归，32.193 秒全部通过；正式稿与 replay 接受检查均为 `passed=true`、0 条发现，Bear HTML 动作区与证据区结构存在。
- 2026-07-29: 收口时 `git diff --check HEAD` 通过；龙虎榜正式与 replay 运行日志均显示归并 76 条，旧快照未保留原始行数的事实边界已明确记录。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_source_health`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_run_log_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_html_output`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_margin_pressure_runtime tests.test_tushare_input_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_input_runtime tests.test_daily_report_render tests.test_daily_report_entry_preflight`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-07-27_A股日报_完整版.md --json`
- `git diff --check HEAD`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_metric_history_index tests.test_mainline_history_runtime tests.test_sector_turnover_history_runtime tests.test_market_state_support`
- 对 `snapshots/2026-07-22.json` 运行 `load_compact_metric_history_snapshot()` 基准并记录 wall time 与峰值 RSS。

## Risk And Rollback Points

- 最高风险是误选快速路径。实现必须以严格 loader 和关键数据检查双重通过为条件。
- 路径切换后 `_POSTGRES_ONLY_RUNTIME` 与环境标记必须在 `finally` 恢复，避免影响同一进程后续测试。
- 快速候选数据必须复用，不能加载后再查一次并得到不同结果。
- 成功只移除指向当前故障的摘要；不得删除 `logs/errors/` 或 `logs/runs/` 历史文件。
- ETF 日期缺失与覆盖不足是两个不同原因；不要用覆盖字段掩盖目标日缺失，也不要为兼容旧 payload 放宽日期要求。
- 17:30 当日来源只允许追加来源日期为目标日的成交额；融资上一交易日可用规则不得误套到 ETF。

## Review Checkpoints

- Checkpoint 1: PRD、设计和实施范围不包含检查点架构或无关重构。
- Checkpoint 2: 自动路径只覆盖普通完整日报，显式路径兼容测试通过。
- Checkpoint 3: 其他日期和不完整载荷无法取得快速重渲染资格。
- Checkpoint 4: commit 前独立审计检查误选路、日期串用、运行状态误报和既有改动干扰。
- Checkpoint 5: 用 2026-07-27 固定事实确认融资 2026-07-24 可用、ETF 2026-07-27 可用；把 ETF 改成 2026-07-24 后四层均不再判为可用。
- Checkpoint 6: 比较修改前后 `selection_workflow`、最终对象、仓位、执行性质、B1/B2 和退出动作，必须逐字段一致。
- Checkpoint 7: 默认历史回退不再调用完整快照 loader；自定义 loader 夹具仍被调用。
- Checkpoint 8: 阶段耗时互不重叠，显示合计与总耗时一致，且不会把完整业务数据写入运行观察信息。
