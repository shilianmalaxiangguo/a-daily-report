# Implementation: 日报指数目标日双源核对

## Prerequisites

- 只修改与六指数采集、核对、生成前检查、测试和 `2026-07-13` 产物直接相关的文件。
- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 工作区已有其他未提交修改；编辑前后均检查局部 diff，不覆盖用户改动。
- 先写失败测试，再实现最小代码使其通过。

## Ordered Checklist

- [x] I1: 为指数日线标准化补齐 `pre_close`、`change`、`pct_chg`、`amount` 字段，并新增字段保留测试。
- [x] I2: 为主要指数和单指数入口新增目标日期严格匹配测试，确认前一交易日数据不能冒充目标日。
- [x] I3: 实现腾讯日 K 精确日期读取和 `report_index_cross_validation.v1` 构建函数，覆盖通过、日期错位、字段缺失和数值冲突测试。
- [x] I4: 在市场状态请求完成六指数采集后执行核对，保存结构化事实并同步状态与请求日志。
- [x] I5: 扩展日报生成前检查，要求主要指数、中证500和指数交叉核对有效，并验证核对证据与当前载荷一致。
- [x] I6: 跑聚焦测试并处理现有测试夹具的真实契约缺口。
- [x] I7: 使用当前双源数据重新采集 `2026-07-13`，覆盖 PostgreSQL 错误事实并重生成正式日报。
- [x] I8: 核对重生成报告六指数、PostgreSQL 日期字段、日报一致性和交易结论差异。
- [x] I9: 跑相关扩大回归、`git diff --check`，并检查本任务 diff 未混入无关改动。
- [x] I10: commit 前启动 subagent 审计，明确使用 `gpt-5.6-sol` 和 `reasoning_effort=max`；处理发现后重新验证。
- [x] I11: 用户要求再次实时生成后，修复“最终对象为空但过程候选仍声称进入明日执行结论”的一致性问题，并新增报告生成前复核。
- [x] I12: 修复日报检查把 `-10.00%` 误识别为伪 `0.00%` 的边界匹配问题。
- [x] I13: 修复首屏未读取选股流程 45 个过程候选、误写“没有过程候选”的问题，并增加候选数量与摘要一致性复核。
- [x] I14: 修复成交额 Top30 忽略排名事实内真实报价、把缺失字段伪写为全 0 的问题，并让 HTML 柱尾直接展示涨跌幅。
- [x] I15: 在正式日报写入前，把本次 Top30 源事实传入日报检查，逐行核对排名、代码、成交额、涨跌幅和四价，任何非零错值或行数差异都停止接受。

## Commit 前审计结论

- 审计代理：`trellis-check`，模型 `gpt-5.6-sol`，`reasoning_effort=max`，只读审计。
- 发现一：`2026-07-13` 之前的新采集也会写入核对事实。已改为生产入口显式判断生效日期，旧日期不调用核对函数、不写状态或请求日志。
- 发现二：成功事实可能夹带重复项、错误代码、遗留失败原因或错误差异记录。已增加逐项完整性复核并用反例测试覆盖。
- 测试缺口：PostgreSQL 原测试只确认字段被写入。已增加保存、回读、生成前复核的完整往返测试，同时覆盖正确事实继续生成和错误代码停止生成。
- 修复后由同一审计代理定向复查，结论为无剩余发现；三条审计回归测试再次通过。
- 第二次实时生成发现华天科技仍携带旧的最终对象说明，但最终对象实际为空。已清理非最终候选的旧说明，并让日报检查在同类矛盾残留时停止写正式产物。
- PostgreSQL-only 验收暴露 `-10.00%` 被子串匹配成 `0.00%`；已改为数字边界匹配，真实跌停幅度不再被误报。
- 首屏过程候选摘要原先只读取旧执行阶段列表，没有读取 `selection_workflow.candidate_pool`。已把选股流程候选纳入摘要证据，并在候选数大于零但摘要写成没有过程候选时停止接受日报。
- 最新提交前只读审计无发现；审计指出同义文案可能漏检后，已把“无过程候选”和候选数量为零等同义表述一并纳入复核。
- Top30 提交前审计发现辅助行情可能覆盖排行行自身报价，以及成交核心章节整表缺失时检查未报错；两项均先补失败测试再修复，并交由原审计代理定向复查。
- 原审计代理定向复查确认两项均已闭合，新增冲突与整表缺失测试通过，结论为无阻断发现。
- 最终源事实一致性复查又发现占位 0 误报与报价别名漏比；已让比较规则与渲染规则对齐，三项边界测试和原审计代理复查均通过，结论为无阻断发现。
- 本次提交前独立审计发现非有限数值、主来源缺失、核对来源被替换，以及当前载荷代码/来源变化可以逃过复核。已先增加反例测试，再收紧有限数值、来源身份和载荷一致性检查，定向 `11` 项测试通过。

## Verification Notes

- 指数、采集入口、输入运行、生成前检查和 PostgreSQL：`252` 项通过，`1` 项按既有条件跳过。
- 日报渲染与一致性审计：`284` 项通过。
- 实时 Tushare/腾讯再核对：`6/6`，失败明细为空。
- PostgreSQL 已保存事实回读：`6/6`，生成前核对通过。
- 正式日报一致性审计通过；修复前后执行结论紧凑快照逐字段一致。
- 修复选股说明后，`tests.test_selection_workflow tests.test_report_acceptance_audit` 共 `247` 项通过。
- 最终完整实时生成耗时 `957.46` 秒，六指数 `6/6`，上涨/下跌家数 `801/4683`，量化信号 `0`，龙头 `0`，正式 Markdown 与 HTML 写入成功。
- PostgreSQL 回读确认候选池 `45` 项、旧的最终对象说明 `0` 项；`selection_workflow`、`final_target_resolution`、`position_decision` 和 `two_layer_decision_payload` 均为无执行对象、`0%` 不参与。
- 候选摘要与同义文案修复后，`tests.test_two_layer_decision_payload tests.test_selection_workflow tests.test_report_acceptance_audit` 共 `288` 项通过。
- 使用最新实时采集事实执行 PostgreSQL-only 正式重渲染，六指数核对 `6/6`，完整日报检查 `0` 项发现，首屏如实写有过程候选但无明日执行对象。
- 成交额 Top30 的 Markdown 30 行涨跌幅与 PostgreSQL 排名事实逐行核对，按两位小数比较差异为空；HTML 柱尾直接显示涨跌幅。
- 含日报入口、Top30 数据、HTML 和日报检查在内的扩大回归共 `429` 项，全部通过；正式日报检查 `0` 项发现。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_tushare_input_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_state_request`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight tests.test_daily_report_render`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-13 --overwrite-official`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-07-13_A股日报_完整版.md`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_domain_report_sections tests.test_daily_report_markdown_html tests.test_report_acceptance_audit`
- `git diff --check`

## Risk And Rollback Points

- 最大风险是误把历史 replay 或旧测试夹具中的无日期数据当作通过；处理原则是补足明确证据，不放宽目标日期要求。
- 腾讯协议解析必须只读取目标日和前一交易日，不使用最新报价替代历史日线。
- 生成前检查必须验证当前载荷与核对证据一致，避免旧成功结果为新载荷背书。
- 若重生成改变交易结论，先判断是否由指数事实修正合理触发；不以保持旧结论为由恢复错误指数。
- 覆盖正式日报仅限用户已要求修复的 `2026-07-13`。

## Review Checkpoints

- Checkpoint 1: 目标日缺失测试先失败，证明复现真实根因。
- Checkpoint 2: 腾讯解析与差异容差测试通过，核对事实包含六项完整证据。
- Checkpoint 3: 生成前检查对缺失、错位、冲突和载荷被替换均会停止生成。
- Checkpoint 4: `2026-07-13` 六指数与 Tushare、腾讯一致，正式报告不再出现旧值。
- Checkpoint 5: subagent 重点审计日期边界、独立来源真实性、失败路径、PostgreSQL 回读和范围控制。
