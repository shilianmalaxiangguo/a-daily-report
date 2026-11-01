# 日报结构优化说明

本目录记录本轮日报结构优化的改动范围、处理流程和验证证据，方便人工复盘，也方便后续 AI 继续理解这次调整。

> 历史记录说明：本文档记录旧版结构优化过程，不是当前日报验收规范。文中若出现
> 手机端、窄屏或固定宽度验证，只表示当时的验证证据；当前日报默认只按桌面阅读面维护，
> 不要求手机兼容。当前策略和执行口径以仓库根目录 `AGENTS.md` 与现行 Wiki 为准。

## 改动目标

- 让日报首屏先给最终动作，再给推导和证据。
- 让 Bear HTML 与 Markdown 使用同一套动作优先顺序。
- 让旧仓、新机会、观察对象、过程候选分开表达，避免把观察信号写成执行资格。
- 让生成的“明日操作”“明日策略”统一使用 2B 执行口径：B1先买参与权，B2只在确认后补；没有确认不补足。
- 让完整版、轻量版和附录有稳定层级，减少标题漂移和重复内容。
- 让历史 replay 使用目标日期事实，避免无日期行情旁路影响历史判断。
- 让市场语言研究证据在最终动作之后解释范围、方向与阶段，同时保持正式决定不变。

## 主要文件

- `scripts/report/runtime.py`：完整版阅读地图、账户日序表位置、板块资金证据后置、附录标题降级、空对象附录清理、0%场景前台观察对象保留。
- `scripts/report/execution_wording.py`：统一“明日操作”“明日策略”使用的 B1/B2 执行文案。
- `scripts/report/markdown_report_html.py`：Bear HTML 标题分类，区分动作段、证据段和阅读地图。
- `scripts/templates/daily_report_markdown_reader.html`：Bear HTML 对动作段和证据段的视觉样式。
- `scripts/daily_report_render.py`：轻量版阅读地图去重，报告伴随文档路径，preflight 前刷新报价敏感派生结果。
- `scripts/report/selection_workflow.py`：同日行情日期匹配，外层日期可信时才允许无行内日期的旁路价格进入判定。
- `scripts/report/report_acceptance_audit.py`：接受检查提示改成中文交易口径，减少英文工程化提示。
- `scripts/daily_report_entry_demo.py`：账户日序表插入到标题和阅读地图之后。
- `scripts/report/front_page_v2_renderer.py`：首屏结论和前台观察表达配合结构调整。
- `scripts/domains/market_state/market_language_translation.py`：目标日来源投影、事件时钟、范围/方向/阶段和 replay 事后验收。
- `scripts/report/market_language_translation_artifacts.py`：fresh/replay 独立准备、加载与保存。
- `scripts/report/final_conclusion_nodes.py`、`scripts/report/action_plan_nodes.py`、`scripts/domains/execution_chain/pk_decision_nodes/action_plan_context.py`：把最终结论、操作计划和 PK 执行上下文同步到 2B 口径。

对应测试主要在：

- `tests/test_report_runtime.py`
- `tests/test_daily_report_markdown_html.py`
- `tests/test_daily_report_render.py`
- `tests/test_selection_workflow.py`
- `tests/test_report_acceptance_audit.py`
- `tests/test_daily_report_entry_html_output.py`
- `tests/test_front_page_v2_renderer.py`
- `tests/test_market_language_translation.py`
- `tests/test_market_language_translation_lifecycle.py`
- `tests/test_quant_pressure_one_minute_study.py`

## 阅读入口

- 看改动怎么流转：`flow.md`
- 看跑了哪些验证：`testing.md`
- 看 HTML 对比解析：`report-structure-comparison.html`

## 修改后对比

| 项目 | 修改前 | 修改后 | 不变项 |
|------|--------|--------|--------|
| Markdown 顺序 | 板块资金扩散淘汰赛可能压在明日执行结论前面。 | 明日执行结论、执行条件、不执行条件先出现，板块资金证据随后解释。 | 明日对象、仓位和执行性质仍取自原结构化结果。 |
| Bear HTML | 只按普通标题渲染，动作段和证据段不区分。 | 动作段和证据段有不同样式标记，顺序跟随 Markdown。 | HTML 不参与候选、评分、淘汰或最终对象解析。 |
| 明日操作/明日策略 | 容易读成开盘一次性买够，或把第二笔当成任务仓。 | 正向执行统一写明：B1先买参与权，B2只在确认后补；没有确认不补足。同股T时，已有1x先视为B1参与权。 | `selection_workflow`、`final_target_resolution`、仓位百分比和最终对象不因文案升级而改变。 |
| 市场语言研究证据 | 公式、弧形和量化压力只在独立研究报告中解释。 | 完整版和摘要版在明日动作之后增加只读证据区；缺少一分钟事实时明确降级，未来表现只进入 replay。 | 正式候选、最终对象、仓位、执行性质、B1/B2 和退出动作不变。 |
| 文档说明 | flow/testing/readme 记录了上一轮结构优化，未覆盖这次动作优先后置证据的细节。 | flow/testing/readme/AGENTS 都记录修改后对比和验证方式。 | 历史 replay 的正式产物覆盖策略不变。 |

## 当前验证结论

本轮展示层改动已通过新增窄路径测试、相关文件级测试、格式检查、稳定结构单测和临时 Bear HTML 渲染检查。

2B 执行口径补充验证：

- `tests.test_front_page_v2_renderer` 覆盖账户页“明日动作”和同股T表达。
- `tests.test_report_runtime` 覆盖正文、附录、满仓归一化和历史旧文案升级。
- `tests.test_final_conclusion_renderer` 覆盖“明日策略”。
- `tests.test_action_plan_renderer` 覆盖“明日操作计划”。
- `tests.test_two_layer_decision_payload` 覆盖明日执行结论。
- `tests.test_pk_decision_stage` 覆盖 PK 阶段执行上下文。

市场语言研究证据补充验证：

- 相关 12 模块 766 项整套回归覆盖来源日期、真实市场宽度生产形状、事件顺序、正式决定隔离、fresh/replay 保存、前台和 Bear HTML；1 项真实 PostgreSQL 用例在常规模式按条件跳过后已单独开启并通过。
- 真实 PostgreSQL 同库重存测试证明整日事实再次保存后仍能按目标日读回研究产物。
- 真实 Runtime 比较接入前后正式决定投影，确认动作先于研究证据且共享输入不残留研究产物。
- Revision 4 论文通过 23 项研究测试、逐字一致、HTML 解析和当时的桌面/`390px` Playwright
  复核；这是历史证据，不是当前手机端验收要求。

当前工作树下重新跑 `2026-06-05 --replay` 时，日报正文生成后因路径诊断来源日期缺失停止生成，失败草稿写入运行期槽位：

- `.generated/report-audit-failures/latest_failed_report.md`
- `.generated/report-audit-failures/latest_failed_report_bear.html`

其中 `latest_failed_report.md` 会被后续单测覆盖；最终验收以稳定单测、测试输出和临时 Bear HTML 抽检为准。

历史 replay 样本仍可作为上一轮参考：

- `reports/replay/2026-06-05_A股日报_完整版_replay.md`
- `reports/replay/2026-06-05_A股日报_轻量版_replay.md`
- `reports/replay/2026-06-05_A股日报_完整版_replay.html`

已确认：

- 完整版 H1 后只有一张 `## 阅读地图`。
- `## 账户日序表` 在阅读地图之后。
- 单测覆盖 `## 明日执行结论` 在 `## 板块资金扩散淘汰赛` 之前。
- 单测覆盖 `明日执行对象=无`、`明日仓位=0%不参与`、`执行性质=无明日执行对象` 不因证据摘要插入而改变。
- 临时 Bear HTML 中动作段和证据段有稳定样式标记，且动作段在证据段之前。
- 轻量版 H1 后只有一张 `## 阅读地图`，不会跑到标题前。
- `推导审计层` 已归入 `## 八、详细附录` 下。
- 没有 `附录：#` 残留。
- 空最终对象时，过程候选只作回放证据，不新增参与。

## 剩余注意

- 当前 `2026-06-05 --replay` 因路径诊断来源日期缺失停止生成，这是当前工作树已有一致性检查暴露的问题，不是本轮展示结构改动导致。
- `2026-06-04 --replay` 因 `ETF两市成交额趋势` 缺失停止生成，这是数据缺口，不是本轮结构整理问题。
- `2026-07-03 --replay` 因缺少 `snapshots/2026-07-03.json` 停止生成；本轮只修生成代码，没有覆盖旧的 2026-07-03 Markdown/HTML 产物，旧产物仍含旧执行文案。
- 当前工作树还有很多既有修改和未跟踪产物。建议提交时只纳入本轮结构优化相关文件，避免混入无关内容。
