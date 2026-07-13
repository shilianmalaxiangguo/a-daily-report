# Implementation: 日报新仓旧仓动作与空仓语义收口

> 当前仅完成 PRD 与设计，不进入代码实现。用户后续明确继续后再执行以下清单。

## Prerequisites

- 当前任务保持 `planning`，规划产物通过 review 后再启动。
- 读取 backend/front-end 相关 spec 和任务 research。
- 保留工作区现有未提交改动，不格式化或清理无关文件。

## Ordered Checklist

- [ ] I1: 先增加失败测试，覆盖持仓未知、明确无仓、待成交确认、旧仓失败、10:10 待复核、正常 T+2 六类输入。
- [ ] I2: 扩展个人持仓上下文与 `report.position_context`，产生并规范化 `old_position_plan.v1`。
- [ ] I3: 修正 `full_or_empty_exposure.v1`，让已确认旧仓计入暴露，未知持仓不再显示 0x。
- [ ] I4: 把旧仓计划接入 `final_target_resolution`、`two_layer_daily_decision.v1`，保持新仓对象与比例不变。
- [ ] I5: 修改日报首页、明日执行结论和持仓策略，分别展示新仓、旧仓事实、旧仓判断、旧仓动作和收盘目标仓位。
- [ ] I6: 扩展日报验收检查，拒绝账户事实与动作矛盾，并验证 Bear HTML 同义。
- [ ] I7: 更新 LLM Wiki 的术语契约与价格行为/能量框架，记录三类旧仓路径和反例纪律。
- [ ] I8: 运行窄范围单测，再运行 2026-07-13 replay、一致性检查和接入前后决策字段对比。
- [ ] I9: 启用 subagents 做一轮提交前逻辑、范围和用户可见文案审计；主代理逐项核对并修复确认的问题。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_position_management_report tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_position_strategy_report tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-13 --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-07-13_A股日报_完整版_replay.md`
- `git diff --check`

## Risk And Rollback Points

- `scripts/report/runtime.py` 与 `front_page_v2_renderer.py` 已有用户改动，修改前后必须逐段核对，禁止覆盖现有逻辑。
- 修改 `明日仓位` 展示时同步检查审计标签与 Bear HTML，不做全仓库机械替换。
- 旧文案兼容只允许明确匹配，模糊输入回到事实不足。
- 每完成一个数据边界就运行对应单测，出现新仓对象或仓位变化立即回滚该边界的实现。

## Review Checkpoints

- RP1: `old_position_plan.v1` 只承载旧仓，不参与候选生成。
- RP2: 持仓未知、待确认和已确认三者在 Markdown、HTML、审计中一致。
- RP3: `09:50-10:10` 是正式窗口，`13:45-14:10` 仍只作研究。
- RP4: 强旧仓反例通过测试，不能因新仓 0% 自动上午卖出。
- RP5: 提交前 subagents 审计结论全部由主代理复核。
