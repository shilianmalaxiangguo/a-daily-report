# Implementation: 修复ETF成交额历史覆盖并生成20260722日报

## Prerequisites

- 新雪球 Cookie 已写入 `.env` 并通过热榜窄检查。
- PostgreSQL 2026-07-21 ETF 窗口存在且覆盖正常。
- 阅读 `.trellis/spec/backend/quality-guidelines.md`、数据库规范和本任务研究结论。

## Ordered Checklist

- [x] I1: 为 Tushare 单日基金行情增加“首批省略零 offset”的分页行为和测试。
- [x] I2: 增加上一交易日 ETF 事实窗口加载、日期/覆盖校验与逐行来源标准化 helper。
- [x] I3: 在新浪历史 payload 不完整且目标日当前列表完整时，优先组合上一交易日 24 行和目标日 1 行；组合失败时保留原有 Tushare 备用与停止生成行为。
- [x] I4: 增加正常续接、历史缺失/不完整、日期断档、目标日覆盖不足的单测。
- [x] I5: 运行 ETF 相关测试和输入/报告检查回归。
- [x] I6: 重新运行 2026-07-22 正式生成，验收 Markdown、快照和 Bear HTML。
- [x] I7: 启用子代理完成提交前审计，主代理按 `file:line` 复核发现。

## Completion Evidence

- `tests.test_tushare_input_runtime`: 124 tests passed after the final audit fixes.
- Cross-layer input, report-preflight, and market-overview suite: 106 tests passed.
- The first live generation for 2026-07-22 exited successfully and wrote the official Markdown, Bear HTML, summary, run log, and snapshot.
- The final audit fix rerun respected official-history protection and wrote replay Markdown, Bear HTML, run log, and snapshot instead of overwriting the official artifacts.
- Replay ETF facts contain 25 dates, actual minimum coverage 1562/1607 (`0.972`), and target-date coverage 1606/1607 with 5791.75亿元 turnover.
- Independent replay report acceptance passed after the final audit fixes.
- Two pre-commit audit rounds completed; the final round's date-window, failure-path, provenance, and metadata findings were fixed and re-verified. Changes remain uncommitted pending user approval.

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_tushare_input_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_input_runtime tests.test_daily_report_render tests.test_market_overview_nodes`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-22`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-07-22_A股日报_完整版_replay.md`

## Risk And Rollback Points

- `scripts/input/tushare_runtime.py` 已有用户未提交的创新高、ETF 当日替换和涨跌停改动；补丁必须局部应用，不能覆盖或格式化相邻代码。
- 如果上一交易日事实读取造成生成延迟或日期歧义，停止并保留原失败结果，不使用最近日期猜测。
- 如果组合后 `selection_workflow`、最终对象、仓位、B1/B2 或退出动作出现非预期变化，停止交付并回查数据影响。

## Review Checkpoints

- 实现前：确认完整性阈值没有改变。
- 单测后：检查失败路径仍然停止生成。
- 正式生成后：检查 ETF 25 日日期、来源、覆盖和最终产物。
- 提交前：独立审计代码差异、测试充分性、凭据泄露和产物一致性。
