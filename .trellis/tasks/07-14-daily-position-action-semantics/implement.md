# Implementation: 日报新仓旧仓动作与空仓语义收口

> I1-I14 已落地并通过验证；工作区保留未提交，等待用户决定提交范围。

## Prerequisites

- 当前任务为 `in_progress`，按已 review 的 PRD、设计与清单完成剩余验证。
- 读取 backend/front-end 相关 spec 和任务 research。
- 保留工作区现有未提交改动，不格式化或清理无关文件。

## Ordered Checklist

- [x] I1: 先增加失败测试，覆盖持仓未知、明确无仓、待成交确认、旧仓失败、10:10 待复核、正常 T+2 六类输入。
- [x] I2: 扩展个人持仓上下文与 `report.position_context`，产生并规范化 `old_position_plan.v1`。
- [x] I3: 修正 `full_or_empty_exposure.v1`，让已确认旧仓计入暴露，未知持仓不再显示 0x。
- [x] I4: 把旧仓计划接入 `final_target_resolution`、`two_layer_daily_decision.v1`，保持新仓对象与比例不变。
- [x] I5: 修改日报首页、明日执行结论和持仓策略，分别展示新仓、旧仓事实、旧仓判断、旧仓动作和收盘目标仓位。
- [x] I6: 扩展日报验收检查，拒绝账户事实与动作矛盾，并验证 Bear HTML 同义。
- [x] I7: 更新 LLM Wiki 的术语契约与价格行为/能量框架，记录三类旧仓路径和反例纪律。
- [x] I8: 原 2026-07-14 产物验证已由 I12 的 2026-07-15 全量重新采集验证替代，不再覆盖旧日期。
- [x] I9: 启用 subagents 做一轮提交前逻辑、范围和用户可见文案审计；主代理逐项核对并修复确认的问题。
- [x] I10: 增加回归测试，覆盖模拟继承 1x、外部待核实 0x、无新目标继续保留旧仓、明确空仓停止继承、显式真实持仓和持仓未知。
- [x] I11: 修复注入、归一、运行时、持仓策略、Bear 与验收链，确保前日报明日标成为模拟旧仓，外部待核实记录不被误升为旧仓。
- [x] I12: 使用 PostgreSQL-only 数据和显式输入今日空仓覆盖 2026-07-15 正式产物，逐字段确认候选、最终对象、新仓比例和 B1/B2 未改变；未输入明日账户归零指令。
- [x] I13: 统一 LLM Wiki 的明日空仓语义：先补回归测试，再同步中央术语契约、相关交易思想节点、静态模型上下文和知识路由；历史别名只保留为检索兼容，不再进入新输出口径。
- [x] I14: 统一“前日报明日标次日自动成为真实 100% / 1x 模拟旧仓”口径，保留 `external_trade_pending` 0x 例外；生成并验收 2026-07-16 正式日报、持仓策略和 Bear HTML，最后完成提交前审计。

## 当前验证记录

- 账户/Bear 聚焦套件 81 项通过；跨层回归 668 项通过。
- 验收、Bear HTML、摘要与双层展示套件 392 项通过；任务验证命令 414 项通过。
- Python 3.14 `py_compile` 与 `git diff --check` 通过；仓库未配置独立 lint/type-check 工具。
- 历史 replay 不再作为本轮完成条件；本轮按用户要求使用 PostgreSQL-only 数据验证 2026-07-15 今日空仓正式产物。
- 提交前审计修复：结构化旧仓计划按判断类别统一动作字段；失败旧仓验收同时要求上午窗口和明确退出动作；明确外部待核实记录收盘口径统一为0x。
- I13 聚焦套件 76 项通过；静态上下文、知识路由和全部相关 Wiki 统一区分明日空仓、明日新仓0%、当前空仓与持仓未知，旧别名只保留在路由触发词中。提交前子代理审计发现的三处歧义文案已由主代理复核并修正。
- 2026-07-15 新鲜事实已在首次生成时同步 PostgreSQL；修复附录候选冲突后，正式报告只使用同批 PostgreSQL 事实重渲染，未再次改变输入。
- 同批失败草稿与最终正式报告的候选数、最终对象、明日新仓和 B1/B2 定点差异为零：候选43只、最终对象无、明日新仓0%、Te没有B1/B2。旧 replay 的46只与新鲜事实43只属于输入批次差异；同输入回归证明账户事实不会改写选股字段。
- 中断前全部本次改动对应模块 1544 项通过；恢复现场后确认没有遗留运行进程，73 项既有未提交变化全部保留。
- 恢复后的六路只读提交前审计确认入口缓存清理正确，并发现两处遗漏：历史 Ta/Tb/Tc 的持仓未知文字会覆盖 Te 当日明确动作；Markdown 已检查明日空仓完整动作，但 Bear 账户动作表未做同等检查。两处均先增加失败反例，再修复实现并同步 backend/frontend/cross-layer 规格。
- 01:36 与 01:54 的中间产物用于区分今日空仓和显式明日账户归零语义；两批均已被本轮最终正式生成覆盖，不作为最终交付事实。
- 02:32 使用 `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-15 --postgres-only --position 空仓 --overwrite-official` 重新生成正式产物；生成前 PostgreSQL 覆盖检查为46798条，写回39915个字段，入口、Bear 与两次后续一致性检查均通过，耗时91.25秒。
- 最终正式 Markdown、摘要、轻量版、持仓策略和 Bear HTML 均显示“已确认无旧仓”“明日新仓0%不参与”“明日执行对象无”“无旧仓需要处理”和“收盘目标仓位0%”；不存在有效明日账户归零动作。候选仍为43只，最终对象无，Te没有B1/B2。
- 受影响的 Bear、验收与入口模块共324项通过。全部本次改动对应模块首次1546项运行出现1次 replay 历史补齐非确定性结果；目标用例连续复跑通过，`tests.test_report_replay` 60项通过，随后在无并发条件下1546项全部通过，耗时259.321秒。
- 本轮新一轮提交前审计发现 `position_fact_status()` 曾把任意非空模糊摘要当成已确认旧仓；回归先复现两次失败，再收紧为明确事实才确认。最终全部受影响模块1546项通过，耗时260.190秒；独立日报一致性检查通过。
- 正式产物有 PostgreSQL-only 成功运行日志和文件时间链，但当前没有正式快照哈希或字段级 manifest；运行日志中部分事实来源仍显示 `unknown`，不能把“同批生成”扩大表述成“每个字段已有哈希绑定”。
- 正式 HTML 的文本、Te 分类、账户动作表和响应式约束已由自动化与文件定点检查覆盖；恢复后的浏览器视觉复核因本地 `file://` 地址被浏览器安全策略拒绝，未取得新的桌面与窄屏截图。
- 2026-07-16 首轮 PostgreSQL-only 生成发现昨日明确空仓在入口被降为持仓未知；新增明确空仓与无法解析两条回归后，入口会把 `previous_position_ended=true` 写为 `previous_report_explicit_empty`，不会只凭 `previous_report_no_target` 猜空仓。
- 新一轮六路只读提交前审计发现并修复两条真实遗漏：`external_trade_pending` 可能被历史目标覆盖；Markdown 回退把“报告日空仓”错误放在同日报明日目标之前。新增三条回归后，读取优先级固定为“显式明日空仓 > 有效明日目标 > 报告日当前空仓或退出事实”。
- 审计修复后的入口、持仓策略、跨层、Bear、验收和 replay 相关套件共 1032 项通过；`tests.test_report_replay` 60 项独立通过，耗时 199.562 秒。Python 3.14 `py_compile`、`git diff --check` 与独立日报一致性检查通过。
- 最终代码使用 `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-16 --postgres-only --overwrite-official` 成功覆盖正式产物：生成前 PostgreSQL 记录数 45029，写回 38142 个字段，耗时 89.11 秒，入口和保存后两次一致性检查均通过。
- 最终完整版、摘要版、轻量版、持仓策略、正式 Bear HTML 与 replay Bear HTML 均显示“已确认无旧仓”“明日新仓0%不参与”“收盘目标仓位0%”；最终对象仍为无、执行性质仍为无明日执行对象、Te 没有 B1/B2。市场资金结构输入仍为 46，账户修复未改写最终选择。
- 通过本地 HTTP 预览完成 1440x900 与 390x844 视觉核验：页面无横向溢出，标题、日序表和明日执行表无重叠；窄屏账户动作完整可读，控制台无错误或警告。
- 最终产物 SHA-256：完整版 `d34c279e...a590639`，执行摘要 `76dec975...121596f`，轻量版 `50673abf...3d896ac`，持仓策略 `82f17fa3...460ac5`，正式 Bear `6b162c98...f107e9d`，replay Bear `a61f9fbe...a78fa2`。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_position_management_report tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_position_strategy_report tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-16 --postgres-only --overwrite-official`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-07-16_A股日报_完整版.md`
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

## Bug Analysis: 模糊持仓摘要被误认作真实旧仓

### 1. Root Cause Category

- **Category**: B/D/E - 跨层契约、测试覆盖缺口与隐式假设。
- **Specific Cause**: 分类函数用“摘要非空”代替“持仓事实已确认”，让叙述文本越过账户事实边界并生成旧仓动作。

### 2. Why Fixes Failed

- 前一轮覆盖了空摘要、明确无仓、待成交与明确持有，但没有把“有文字、无事实”的反例纳入测试。

### 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|---|---|---|---|
| P0 | Test Coverage | 增加待核对与昨日计划模糊摘要反例，并保留直接持有/待成交对照 | DONE |
| P0 | Runtime | 只有明确标志、正数实际仓位、结构化旧仓计划或直接持仓文字才确认 | DONE |
| P1 | Documentation | 同步 backend 契约与跨层核对清单 | DONE |

### 4. Systematic Expansion

- **Similar Issues**: 候选、结论、持仓策略与 Bear 都消费同一分类结果，必须统一依赖 `position_fact_status`。
- **Design Improvement**: 叙述文本只提供证据描述，不再单独承担账户事实来源。
- **Process Improvement**: 账户语义测试同时保留 unknown、none、pending、confirmed 四类及模糊文本反例。

### 5. Knowledge Capture

- [x] 更新 backend 日报决策契约。
- [x] 更新跨层核对清单。
- [x] 增加失败回归并运行完整受影响套件。
