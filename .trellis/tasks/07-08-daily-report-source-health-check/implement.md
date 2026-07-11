# Implementation: 日报生成前数据源健康检查

## Prerequisites

- 实现前读取：
  - `prd.md`
  - `design.md`
  - `wiki/运行契约/日报数据源契约.md`
  - `openspec/specs/architecture/error-handling.md`
  - `openspec/specs/architecture/observability.md`
  - `.trellis/spec/backend/database-guidelines.md`
  - `.trellis/spec/backend/quality-guidelines.md`
- 所有 Python 命令必须使用 `.generated/venv-py314/bin/python3.14`。
- 实现前确认当前工作区已有大量未提交修改，不把无关文件纳入本任务提交。

## Ordered Checklist

- [x] I1: 新增健康检查数据模型和结果归一化函数，先用普通 dict，避免引入新依赖。
- [x] I2: 新增凭证检查 helper，只返回 `ok / missing / suspected_expired / not_required / not_checked`，不返回原始值。
- [x] I3: 新增脱敏 helper，覆盖 token、cookie、Bearer、API key、数据库 URL。
- [x] I4: 新增 source health runner，第一版登记 Tushare、PostgreSQL、雪球、QuickTiny、iwencai、Xuangubao、Investor QA、DeepSeek。
- [x] I5: 为每个外部探测加独立超时；超时写入检查行，不让整体命令卡住。
- [x] I6: 新增 CLI：`scripts/daily_report_source_health.py <YYYY-MM-DD>`，输出 JSON、HTML 和终端摘要。
- [x] I7: 新增 Bear 风格 HTML renderer，只消费 JSON 结果，不访问外部源。
- [x] I8: 在日报入口完整生成前接入健康检查；关键失败时停止生成并打印 HTML 路径。
- [x] I9: 新增 `--source-health-only` 或等价轻量入口，方便只预生成检查表。
- [x] I10: 单测覆盖通过、凭证缺失、疑似失效、超时、脱敏、HTML 打勾表格、入口早停。
- [x] I11: 运行最小验证命令，确认不影响现有 `build_report_preflight()` 和日报一致性检查。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_source_health`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_input_runtime`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_source_health.py 2026-07-08`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-08 --source-health-only`

## Risk And Rollback Points

- 入口接入风险最高。先保持独立 CLI 可用，再接入 `daily_report_entry_demo.py`。
- 不要让健康检查复用完整采集函数，否则会把“生成前检查”变成另一条慢链路。
- 不要在日志、HTML 或测试快照中写入任何真实凭证。
- 如果完整入口接入导致误停，可先只保留 `--source-health-only`，把默认接入留到下一步。

## Review Checkpoints

- Checkpoint 1: JSON 契约和 HTML 样例通过单测。
- Checkpoint 2: 凭证脱敏和单源超时通过单测。
- Checkpoint 3: 入口早停只发生在关键项失败时。
- Checkpoint 4: commit 前启用 subagent 做一轮审计，明确使用 `model: gpt-5.5`、`reasoning_effort: xhigh`，重点看是否误改日报决策逻辑、是否泄漏凭证、是否扩大重构范围。
