# Follow-up TODO

Date: 2026-04-22
Scope: `a-daily-report`

## Open Issues

### 1. `data_collector` 模块缺失，阻塞旧入口直跑验证

- Status: parked
- Priority: medium
- Trigger:
  `python3 scripts/daily_report_entry_demo.py 2026-04-22 --replay`
- Current error:
  `ModuleNotFoundError: No module named 'data_collector'`
- Current location:
  [`scripts/daily_report_entry_demo.py:1973`](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/daily_report_entry_demo.py:1973)
- Impact:
  会阻塞旧版 CLI 入口的整链直跑验证，导致当前只能通过单元测试和 orchestrator smoke 间接验证重构结果。
- Current observation:
  仓库内没有可直接导入的 `data_collector.py`，旧入口仍然依赖历史导入路径。
- Follow-up actions:
  1. 确认 `AShareDataCollector` 的真实来源文件是否已经迁移、删除，或仍在仓库外部路径。
  2. 决定修复方式：
     在仓库内补兼容 wrapper；
     或改成新的模块路径；
     或彻底移除旧入口对该模块的依赖。
  3. 修复后补一个最小回归验证：
     至少保证 `python3 scripts/daily_report_entry_demo.py 2026-04-22 --replay` 不会在 import 阶段失败。
