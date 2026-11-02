# 日报结构优化验证记录

> 历史展示记录，不适用于当前日报入口。下文结果只证明当时的实现，不证明新版可用，也不要求新日报维持旧账户和操作文字。当前验证见[验证约定](../../references/verification.md)与[框架重建 PRD](../plans/2026-10-22-daily-report-framework-rebuild-prd.md)。

## Python 解释器

本轮所有 Python 命令均使用：

```bash
.generated/venv-py314/bin/python3.14
```

## 窄路径测试

### 空最终对象与前台观察对象

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_report_runtime.ReportRuntimeTest.test_runtime_final_resolution_keeps_explicit_front_observation_when_workflow_final_is_zero \
  tests.test_report_runtime.ReportRuntimeTest.test_final_target_resolution_skips_process_observation_and_keeps_front_observation \
  tests.test_report_runtime.ReportRuntimeTest.test_runtime_final_resolution_rejects_process_identity_even_when_front_observation_qualified \
  tests.test_report_runtime.ReportRuntimeTest.test_runtime_final_resolution_rejects_source_pool_process_identity
```

结果：通过。

覆盖点：

- 0%不参与时，合格前台观察对象仍可保留。
- 过程候选、过程观察样本不能变成当前对象。

### 历史行情日期约束

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_selection_workflow.SelectionWorkflowTest.test_undated_hot_rank_without_container_date_does_not_block_target_date_candidate \
  tests.test_selection_workflow.SelectionWorkflowTest.test_limit_down_anchor_without_reversal_plan_stays_repair_observation \
  tests.test_selection_workflow.SelectionWorkflowTest.test_plain_reversal_text_does_not_combine_with_quote_limit_down \
  tests.test_selection_workflow.SelectionWorkflowTest.test_limit_down_reversal_plan_can_remain_final_when_explicit_and_cancelable
```

结果：通过。

覆盖点：

- 无日期热榜不能影响历史目标日价格判断。
- 外层日期能证明属于目标日时，热榜价格状态仍可用于风险判断。
- 明确跌停反包专项仍可保留执行资格判断。

### 轻量版阅读地图

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_daily_report_render.DailyReportRenderTest.test_build_lightweight_report_text_keeps_actions_but_drops_heavy_sections \
  tests.test_daily_report_render.DailyReportRenderTest.test_build_lightweight_report_text_deduplicates_existing_reading_map_after_title
```

结果：通过。

覆盖点：

- 轻量版只有一张阅读地图。
- 阅读地图在 H1 之后。
- 轻量版保留明日账户建议、执行图、市场底色、个股处理、明日三窗口和最终结论。

### 动作优先与 Bear HTML 展示

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_report_runtime.ReportRuntimeTest.test_runtime_inserts_reading_map_once_after_title \
  tests.test_report_runtime.ReportRuntimeTest.test_insert_sector_capital_preflight_front_summary_places_tournament_after_execution_section \
  tests.test_report_runtime.ReportRuntimeTest.test_insert_sector_capital_preflight_front_summary_places_tournament_after_execution_conditions \
  tests.test_report_runtime.ReportRuntimeTest.test_insert_sector_capital_preflight_front_summary_keeps_zero_execution_rows_unchanged \
  tests.test_report_runtime.ReportRuntimeTest.test_insert_sector_capital_preflight_front_summary_replaces_stale_existing_section \
  tests.test_report_runtime.ReportRuntimeTest.test_insert_sector_capital_preflight_front_summary_replaces_stale_section_before_next_h2 \
  tests.test_daily_report_markdown_html.DailyReportMarkdownHtmlTest.test_render_marks_action_and_evidence_sections_for_bear_reader
```

结果：通过。

覆盖点：

- 阅读地图第一行先读明日执行结论、执行条件和不执行条件。
- 板块资金扩散淘汰赛插在明日执行结论和执行/不执行条件之后。
- 0%不参与样本中，`明日仓位`、`明日执行对象`、`执行性质` 三行不因证据摘要插入而改变。
- 旧的板块资金证据段会被替换，不会重复插入。
- Bear HTML 给动作段和证据段加不同样式标记，并保持 Markdown 顺序。
- 不触碰选股流程、最终对象解析、候选池评分和数据源。

## 相关文件级测试

```bash
.generated/venv-py314/bin/python3.14 -m unittest -f \
  tests.test_daily_report_render \
  tests.test_daily_report_markdown_html \
  tests.test_selection_workflow \
  tests.test_report_runtime \
  tests.test_front_page_v2_renderer \
  tests.test_two_layer_decision_payload \
  tests.test_report_acceptance_audit \
  tests.test_daily_report_entry_html_output
```

结果：749 个测试通过。

本轮动作优先和 Bear HTML 改动后的复跑结果：

```bash
.generated/venv-py314/bin/python3.14 -m unittest -f \
  tests.test_report_runtime \
  tests.test_daily_report_markdown_html \
  tests.test_daily_report_render \
  tests.test_daily_report_entry_html_output \
  tests.test_report_acceptance_audit
```

结果：590 个测试通过。

## 2B执行口径验证

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_entry_plan_stage \
  tests.test_positioning_node_runtime \
  tests.test_pk_decision_renderer \
  tests.test_front_summary_support \
  tests.test_appendix_renderer \
  tests.test_position_strategy_report
```

结果：58 个测试通过。

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_front_page_v2_renderer \
  tests.test_report_runtime \
  tests.test_final_conclusion_renderer \
  tests.test_action_plan_renderer \
  tests.test_two_layer_decision_payload \
  tests.test_pk_decision_renderer \
  tests.test_positioning_node_runtime \
  tests.test_sniper_target_derivation \
  tests.test_bayesian_diagnosis
```

结果：485 个测试通过。

覆盖点：

- 账户页“明日动作”正向执行文案包含 B1/B2。
- 同股T表达为已有1x先视为B1参与权，B2只在强表态存活后补。
- 正文和附录中的“明天具体怎么做”“出手时怎么做”“真到盘中怎么做”同步到新口径。
- “明日策略”同步到新口径。
- 旧的 50%/满仓执行文案在归一化时升级到新口径。
- 100%核心进攻首屏仓位文案同步包含 B1/B2，不再只写“不满足回到0%”。
- 明日对象、明日仓位和执行性质仍来自原结构化结果。

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_market_research_renderer \
  tests.test_entry_plan_node_runtime \
  tests.test_pk_decision_stage \
  tests.test_llm_wiki_context \
  tests.test_llm_wiki_router \
  tests.test_positioning_node_runtime \
  tests.test_gem_breathing_runtime
```

结果：194 个测试通过。

覆盖点：

- 市场研究、PK阶段、20cm分支和 LLM Wiki 路由没有继续输出旧的正向执行短句。
- 过程观察类文案仍保持只观察、不新增参与。

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_use_execution_appendix_tail \
  tests.test_decision_ledger
```

结果：103 个测试通过。

覆盖点：

- 极度看好列表中被升级为“明日执行对象”的标的同步使用 B1/B2 口径。
- 历史回测表中的“历史标准动作”同步使用共享执行文案。

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit
```

结果：166 个测试通过。

### 2026-07-03 replay 生成尝试

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-03 --replay
```

结果：停止生成。

原因：`snapshots/2026-07-03.json` 不存在，入口脚本按历史 replay 规则拒绝生成。

本地已存在这些旧产物，但未在本轮覆盖：

- `reports/2026-07-03_A股日报_完整版.md`
- `reports/2026-07-03_A股日报_完整版.html`
- `reports/replay/2026-07-03_A股日报_完整版_replay.md`
- `reports/replay/2026-07-03_A股日报_完整版_replay.html`

抽检结果：这些旧产物仍含旧执行文案。本轮已修生成代码和测试，后续要重写 2026-07-03 历史产物，需要先补齐同日快照，或明确允许按目标日期重新采集并覆盖对应 replay/正式产物。

## 格式检查

```bash
git diff --check
```

结果：通过。

## 附录主线推导链展示

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_two_layer_decision_payload \
  tests.test_daily_report_markdown_html \
  tests.test_report_acceptance_audit
```

结果：46、62、253 项分别通过。

覆盖点：

- `主线推导链` 下先出现 Mermaid，随后才是节点结论表。
- 节点表只显示中文交易含义，不出现 `passes_forward` 原始字典。
- N8 节点表仍能被日报一致性检查识别，首页与推导链对象不一致时停止通过。
- 2026-08-05 replay 日报一致性检查通过，Markdown 与 Bear HTML 均不含原始字典。
- in-app Browser 在 `1440x900` 和 `390x844` 实际生成 1 个非空 Mermaid SVG，控制台无错误。
- 两个视口的页面 `scrollWidth == clientWidth`；390px 的节点宽表只在自身容器内滚动。
- replay 与正式稿的明日执行对象均为无、仓位均为 0%、执行性质均为无明日执行对象、B1/B2 均不执行；旧仓动作均为“先核对实际持仓；不从明日新仓0%反推卖出”。展示修改未改变这些决定。

正式历史日报未覆盖；本轮验证产物只写入 `reports/replay/` 和 `snapshots/replay/`。

## 真实 replay 验证

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay
```

当前复跑结果：停止生成。

关键结果：

- 关键数据检查通过。
- 生成过程进入日报正文后，一致性检查报告 `bayesian_path_source_date_missing`，提示路径诊断来源日期缺失。
- 失败草稿写入 `.generated/report-audit-failures/latest_failed_report.md`；该路径是运行期失败草稿槽位，后续单测可能覆盖内容。
- 这次停止点来自当前工作树已有的路径诊断来源日期检查，不是动作优先展示顺序失败。

旧验证生成文件仍可作为上一轮历史样本参考，本轮没有覆盖正式历史日报：

- `reports/replay/2026-06-05_A股日报_完整版_replay.md`
- `reports/replay/2026-06-05_A股日报_执行摘要_replay.md`
- `reports/replay/2026-06-05_A股日报_轻量版_replay.md`
- `reports/replay/2026-06-05_A股日报_证据附录_replay.md`
- `reports/replay/2026-06-05_A股日报_运行日志_replay.md`
- `reports/replay/2026-06-05_A股日报_完整版_replay.html`

本轮临时 Bear HTML 验证文件：

- `.generated/report-audit-failures/latest_failed_report_bear.html`

## 结构抽检

对稳定单测和临时 Bear HTML 执行结构检查：

- `## 阅读地图` 只出现一次。
- H1 在阅读地图之前。
- 单测覆盖 `## 明日执行结论` 在 `## 板块资金扩散淘汰赛` 之前。
- Bear HTML 中 `bear-section-action` 在 `bear-section-evidence` 之前出现。
- 单测覆盖 `明日仓位=0%不参与`、`明日执行对象=无`、`执行性质=无明日执行对象` 不因证据摘要插入而改变。
- 没有 `附录：#`。
- 没有顶层 `## 推导审计层`。
- 附录中空最终对象写为过程候选回放，不新增参与。

结果：通过。

## 已知未通过样本

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay
```

结果：停止生成。

原因：`ETF两市成交额趋势` 缺失。这个是历史 replay 数据缺口，不是本轮结构整理问题。

## 市场语言研究证据验证

相关整套回归命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_market_language_translation \
  tests.test_postgres_daily_fact_db \
  tests.test_front_page_v2_renderer \
  tests.test_daily_report_render \
  tests.test_daily_report_agent_runner \
  tests.test_market_language_translation_lifecycle \
  tests.test_report_replay \
  tests.test_daily_report_markdown_html \
  tests.test_report_acceptance_audit \
  tests.test_llm_wiki_context \
  tests.test_quant_pressure_one_minute_study \
  tests.test_tushare_input_runtime
```

结果：766 项通过，1 项按环境条件跳过。该组测试覆盖目标日来源、真实市场宽度生产形状、分钟事件、固定窗口内部一致性、正式决定隔离、fresh/replay 保存、前台顺序、Bear HTML 与 Revision 4 逐字一致。

补充检查：

- `A_DAILY_REPORT_RUN_POSTGRES_INTEGRATION=1` 的同库重存测试：1 项通过。
- 真实 Runtime 与命令入口的正式决定不变、动作优先、保存时点和磁盘正文一致测试：5 项通过。
- `.generated/venv-py314/bin/python3.14 -m html.parser reports/research/quant-pressure-replay-study-20260711.html`。
- Playwright 桌面与 `390px`：页面级横向溢出、元素重叠、SVG 非空、公式可见、窗口底色和控制台错误。

Revision 4 论文 HTML 解析和生成器逐字一致通过，23 项研究测试通过，SHA256 为 `b203af7a579eb16366da899baa7ac43b544fe9b96ba0ab76a26bdda866ca3f8d`。Playwright 结果保持为：桌面与 `390px` 页面级横向溢出和元素重叠均为零，10/10 SVG 非空，公式与四类窗口底色可见，控制台零错误。

## Bear 候选生命周期分层展示

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_two_layer_decision_payload \
  tests.test_daily_report_markdown_html

.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_report_runtime \
  tests.test_report_acceptance_audit

.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  reports/2026-08-05_A股日报_完整版.md
```

结果：候选展示定向检查 108 项通过；相关四模块合计 730 项通过；2026-08-05 实际完整版一致性检查通过。

覆盖点：

- Markdown 表头使用“发现路径”，已知内部来源显示为中文。
- Bear HTML 先显示 45 只候选概览，默认展开 10 只重点样本，35 只普通过程样本默认收起；通用过程池计数为 37 只。
- 四列明细保留全部 45 只股票，每只在候选组件中只出现一次；空候选、只有重点候选和 HTML 转义均有单测覆盖。
- 从未修改的 2026-08-05 Markdown 重建 Bear HTML；正式 Markdown 与 `snapshots/2026-08-05.json` 均无本轮差异。
- 正式决定仍为：明日新仓 0%不参与、明日执行对象无、执行性质无明日执行对象；旧仓动作保持“先核对实际持仓；不从明日新仓0%反推卖出”。本轮只从同一 Markdown 重建 HTML，没有运行候选或决定生成链路。
- in-app Browser 在 `1440x900` 与 `390x844` 检查通过：页面横向溢出为 0，宽表只在组件内部滚动；关闭时 35 行表格为 `display:none` 且高度为 0，展开后恢复显示，两个状态均无重叠。
- 历史兼容抽检通过：2026-06-10 的“首次来源 / 进入理由”旧表进入专用视图；2026-06-24 的 `limit_up` 显示为“涨停/连板证据”。
- 重点判定按分隔后的身份词精确匹配，“非板块锚”“不能作为最终执行对象”不会误入重点区；只有普通过程样本时仍显示默认收起区。

### 提交前独立审计

- 统一开始：`2026-08-05 23:14:46.194 +08:00`；两个审计共用 10 分钟截止，最终有效墙钟为 9 分 42 秒。
- 代码行为审计：`23:14:46.194` 开始，`23:24:28.400` 结束，未被停止；确认 4 项有效发现，分别处理为历史“进入理由”兼容、`limit_up` 中文名、否定身份精确匹配，以及折叠/窄屏定向验证。
- 产物一致性审计：`23:14:46.194` 开始，8 分钟节点无阶段证据；主线程在下一次恢复控制时于 `23:23:52.564` 停止，未超过 10 分钟截止，有效发现 0 项。
- 产物审计停止后的定向核对：实际 Markdown 一致性检查通过；正式 Markdown 和快照无本轮差异；45/10/35、45 只各出现一次、内部英文来源为 0；正式决定仍为明日新仓 0%不参与、明日执行对象无、执行性质无明日执行对象，旧仓动作不变。
- 处理后重新运行 730 项相关测试、实际日报一致性检查、HTML 解析和 `git diff --check`，结果均通过。

## Bear 25日板块周期泳道

验证命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_daily_report_render \
  tests.test_daily_report_entry_html_output
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  reports/2026-08-05_A股日报_完整版.md
.generated/venv-py314/bin/python3.14 -m html.parser \
  reports/2026-08-05_A股日报_完整版.html
git diff --check
```

结果：泳道渲染模块 65 项通过；相关渲染、入口和文档模块 181 项通过；实际日报一致性检查、HTML 解析和格式检查通过。

覆盖点：

- 真实 2026-08-05 Markdown 生成 25 个交易日、12 条板块泳道；国产芯片替代只在 2026-08-04 至 2026-08-05 连续，2026-07-29 保持独立。
- 空白方向日期保留在横轴上并切断前后同方向；占比暂缺保持 `null`，ASCII 中显示 `?`，不按 0 处理。
- 主章节和两个详细附录副本各生成一张泳道；原始标题、T 编号、表头、数据行和解读完整保留在默认收起区。
- 收起区在小周期方向表结束后立即闭合；`T-073` 和 `T-117` 不会被误收进板块原始记录。
- ECharts 正常时三张泳道均有非空 canvas，ASCII 隐藏；移除 ECharts 加载后隐藏空白画布，ASCII 可见且包含首尾日期、状态字符和图例，常显滑杆改为控制 ASCII。
- `1440x900` 页面 `scrollWidth == clientWidth == 1440`；时间轨道 `1450 > 796`，只在组件内部横向滚动。
- `390x844` 页面 `scrollWidth == clientWidth == 390`；固定板块列为 106px，无标签溢出，时间轨道 `1450 > 196`，可滚到最大 `scrollLeft=1254` 并看到 2026-08-05。
- 桌面与 390px 的底部滑杆均常显；滑杆最大值分别同步为 `654` 和 `1254`，拖到末端后 `value == scrollLeft == max`，左右按钮会随起点、终点启停。
- 浏览器控制台错误为 0。正式 Markdown 本轮前后 SHA-256 均为 `3e7d49fe66b6d227f9c2e9af65d3b9c1ef6ea83a7aa139676d051c132b06aa57`，`snapshots/2026-08-05.json` 本轮前后均为 `af8fbf260bb74e71015a2e5ef8d3be37957bdf47548f97eaa24eb2db032eff28`；正式决定仍为明日新仓 0%不参与、明日执行对象无、执行性质无明日执行对象。

提交前独立审计：

- 统一开始：`2026-08-06 00:44:22.226 +08:00`；两个审计并行墙钟约 8 分 8 秒，均未停止。
- 代码行为审计：`00:45:09.109` 开始，`00:52:29.862` 结束，3 项有效发现；已修复附录闭合边界、空白方向断点和 ASCII 缺失标记，并补充回归测试。
- 展示与产物审计：`00:44:22.226` 开始，`00:50:15.253` 结束，2 项有效发现；附录边界与前项重复并已修复，降级和 390px 运行证据已补齐。

常显横向控件修正审计：

- 统一开始：`2026-08-06 09:57:59.321 +08:00`；两个审计并行墙钟 7 分 51 秒，均未停止。
- 代码行为审计：`09:57:59.321` 开始，`10:05:16.388` 结束；报告 3 项，其中三份泳道符合主章节与两个附录副本的既定范围，不作去重；采纳降级控件目标与运行验证两项，已隐藏空白画布并让同一控件控制 ASCII，补跑单测和桌面/390px 浏览器检查。
- 产物与文档审计：`09:57:59.321` 开始，`10:05:50.355` 结束，2 项有效发现；已收窄正式历史保护表述，并记录 Markdown、快照本轮前后 SHA-256。

### 2026-08-07 强势高标方向补充

验证命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_runtime
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_daily_report_render \
  tests.test_daily_report_entry_html_output
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_research_runtime
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-08-07 --replay
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  reports/replay/2026-08-07_A股日报_完整版_replay.md
git diff --check
```

结果：板块摘要 34 项、Bear 渲染 65 项、日报渲染与入口 152 项、市场研究 37 项全部通过；板块摘要、Bear 与市场研究合并复跑 136 项通过；2026-08-07 replay 生成成功，日报一致性检查与格式检查通过。

覆盖点：

- 8 个板块名额已满时，小金属凭 1046.72 亿成交额、3.9% 占比、云南锗业 4 天 4 板和同板块 2 只涨停取得优先保留资格。
- 板块成交额缺失且无法由有效占比与两市成交额推导，或只有 1 只涨停的反例不会取得该资格；可推导样本按 `10000亿 × 3.9% = 390.00亿` 保留。错日与非有限数值同样不参与优先保留。
- 当当前主线与另外 7 个方向都已有目标日成交事实时，新的强势方向不再替换其中任何一个；强势优先只替换仅有历史记录的方向。
- replay Markdown、Bear HTML 和 replay 快照都包含“小金属”；展示沿用事实源名称，不硬编码“稀土”或“有色金属”。
- `selection_workflow`、`two_layer_decision_payload`、`position_decision` 与正式快照哈希一致；`final_target_resolution` 只少 replay 不适用的 PostgreSQL 生成阶段元数据，其余字段一致。
- 正式 Markdown、Bear HTML 和快照的时间戳仍为 `2026-08-08 00:13:41/43`，本轮只写 `reports/replay/` 与 `snapshots/replay/`。
- `1440px` 页面 `scrollWidth == clientWidth == 1440`，轨道和滑杆末端均为 654；`390x844` 页面 `scrollWidth == clientWidth == 390`，轨道和滑杆末端均为 1254。两个视口均能看到 2026-08-07 小金属节点，无文字重叠。
- 最新本地静态服务浏览器复测控制台错误为 0。

补充提交前独立审计：

- 统一开始：`2026-08-08 13:44:53.106 +08:00`；共享 8 分钟阶段节点为 `13:52:53.106`，10 分钟截止为 `13:54:53.106`。
- 代码行为审计约于 `13:53:20` 结束，未被停止，有效发现 3 项：备用替换会挤掉已有目标日成交事实、可推导成交额未取得资格、错日与非有限值缺少校验。三项均已修复并由 34 项定向测试覆盖。
- 产物一致性审计未在共享 10 分钟内返回，最终于 `14:02:07` 结束，晚到结论为 0 项发现；该结论不计作按时审计证据。主线程对最新重新生成的产物另行完成接受度检查、JSON 解析、决定字段哈希、8 个板块、小金属事实、正式产物时间戳和两个视口的定向核对。
- 最新浏览器结果：3 张泳道均 `is-chart-ready` 且各有 1 个 canvas；桌面页面 `1440/1440`、轨道/滑杆最大值 `654`，390px 页面 `390/390`、轨道与滑杆同步到 `1254`，原始记录默认收起，控制台错误为 0。

## 2026-08-11 Bear 去重与详细附录整理

上面的“三张泳道”是上一轮当时的验收记录，本节记录纠正后的现行口径：正式主章节只显示一张泳道，两个附录不再重复创建图卡；三组原始事实仍分别完整保留。

验证命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_daily_report_render \
  tests.test_daily_report_entry_html_output
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  reports/2026-08-10_A股日报_完整版.md
git diff --check
```

新增覆盖点：

- 主文与两个同名附录同时存在时，泳道图卡和可见标题各只有一个。
- 即使兼容附录标题先出现，只要正式主章节存在，图卡仍放在正式主章节后；只有主章节缺失的旧报告才使用附录位置。
- 三个周期事实来源组仍各有一个默认收起的原始记录区，T-041、T-073、T-111 及对应表格完整保留。
- “八、详细附录”下每个直属三级标题形成独立原生收起区，摘要锚点唯一；后续知识、原则和经验章节位于折叠区之外。
- 桌面和 390px 已复核摘要换行、展开/收起、目录定位、组件内部横向滚动和页面级横向溢出；移动目录展开组包含 21 个可见三级入口。

### 2026-08-11 最终验收证据

真实产物：`reports/2026-08-10_A股日报_完整版.html` 从未修改的 Markdown 重渲染；Markdown SHA-256 `bb91407eb9cb7195ecf2ac028c603ae287e83cc6688dd9abcf1c950ff1ff6462`，快照 SHA-256 `924ba6a170dbde9ec4e41ac023d0ff1fb1d18202924b3e55414809e9e438549b`，重渲染前后均不变。

结构核对：`sector_cycle_swimlane` canvas 1 个、可见标题 1 个、周期原始记录组 3 个、详细附录折叠组 21 个；`T-041`、`T-073`、`T-111` 各保留 1 次。所有附录和原始记录默认关闭，知识复利候选位于附录折叠区之外。

单测与静态检查：`tests.test_daily_report_markdown_html` 70 项通过；`tests.test_daily_report_render tests.test_daily_report_entry_html_output` 153 项通过；日报一致性检查、HTML 解析、目标文件语法检查和 `git diff --check` 通过。新增回归还覆盖无直属三级标题、文末闭合、fenced code 伪标题和三组原始记录各自的内容边界。

决定隔离：快照 `data` 中的四个决定字段与同一快照的冻结决定副本逐项相等。规范化 SHA-256 分别为 `selection_workflow=a9c5e0c2901b0bfb6f2a16dc9a753d4d70c625b547d3d2e73a95a060863ca4e7`、`final_target_resolution=3a335a39a66ac53f5d537f6f4ab7f37bb3a416e54593b369f8df163ec8c52940`、`position_decision=f7704b0d9dfbc93171a528675c81f957e79b727e5185feddfab3fceb69d20d64`、`two_layer_decision_payload=180f985488c176748315033a283b0d94c540b00794b84b8146aa82280df6617a`。当前结果仍为执行对象空、明日仓位 0%、不参与，B1、B2 和退出动作均为空；Markdown 用户可见结果仍为“明日执行对象：无”“执行性质：无明日执行对象”。

浏览器（本地 Python 3.14 静态服务，系统 Chromium）：`1440x900` 与 `390x844` 均为 `scrollWidth == clientWidth`（分别 1440/1440、390/390），canvas 非空，21 个摘要无重叠且可展开/收起，桌面和移动目录都能定位到唯一摘要；周期滑杆与内部时间轨道双向同步（最大滚动值分别 654、1254），页面控制台错误为 0。截图保存在 `.generated/verification/bear-content-dedup-*.png`。

说明：静态服务首次未拦截浏览器自动请求的 `/favicon.ico` 时出现一次 404；应用资源、页面脚本和交互本身无错误，复测已对该非应用请求返回空响应并确认控制台为 0。

### 2026-08-11 提交前独立审计

- 统一墙钟从 `00:36:51.971 +08:00` 开始，8 分钟阶段节点为 `00:44:51.971`，10 分钟截止为 `00:46:51.971`；两个审计按并行墙钟共用这 10 分钟，不把各自时长相加。
- 代码行为审计于 `00:39:08.386` 派发，阶段节点前返回“暂无确认发现”，统一截止时按停止处理；最终消息在客户端于 `00:47:09.116` 回收。有效发现 2 项：代码块中的伪主标题会使旧报告兼容位置少生成泳道，以及三来源测试未逐组锁定内容边界。两项均已修复并新增回归。
- 产物一致性审计于 `00:39:58.899` 派发，阶段节点前已确认 1 项记录问题，统一截止时按停止处理；最终消息在客户端于 `00:47:15.590` 回收。有效发现 2 项：PRD 验收勾选与已有证据不一致，以及决定字段缺少可复查哈希。两项均已补齐。
- 两个最终消息的客户端回收时间分别超过统一截止 17.145 秒和 23.619 秒；超时部分不延长正式审计预算，新增细节按主线程定向复核处理。处理后重跑 Bear 70 项、关联入口 153 项、实际日报一致性检查、HTML 解析、语法检查和全工作区格式检查，结果均通过。

## 2026-08-13 Top50 叠加创业板指数

验证命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest -b \
  tests.test_daily_report_entry_html_output \
  tests.test_daily_report_markdown_html
.generated/venv-py314/bin/python3.14 -m unittest tests.test_postgres_daily_fact_db
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  reports/2026-08-12_A股日报_完整版.md
.generated/venv-py314/bin/python3.14 -m html.parser \
  reports/2026-08-12_A股日报_完整版.html
git diff --check
```

已完成的定向证据：

- PostgreSQL 存储 61 项测试通过、1 项按环境条件跳过；入口与 Bear 渲染 129 项通过；日报渲染 101 项通过。覆盖乱序、重复、未来日期、无效收盘值、数据库读取失败、独立 Markdown 重建入口、同日对齐、双轴双图例和无创业板序列降级。
- PostgreSQL `sz399006` 截至 2026-08-12 有 49 条历史记录；最近 25 条为 2026-07-08 至 2026-08-12，目标日收盘 3602.0835。
- Top50 表保留 25 个日期；其中 24 日有同日创业板收盘点。2026-07-30 在 PostgreSQL 与正式快照中均无创业板收盘事实，载荷保持 `null`，提示显示“事实不足”。
- 浏览器实测 `1440x900` 和 `390x844` 页面横向溢出均为 0；双线分别使用左右轴，两个图例用真实鼠标点击后可独立关闭和恢复。
- 390px 画布为 604x662 设备像素，抽样中有 2433 个非白有效像素，排除空白画布。
- 正式 Markdown SHA-256 在重渲染前后均为 `02f425ef0e0c94e38ddfd81514f17f1f96ad9fa0bae808e18b3e9f744cc8f571`；正式快照均为 `c8920d993e44bbb902edd117a3491656a335f9620dc3d69c6f2466c73a34e5b4`。本轮只重建 Bear HTML，不改交易决定。
- Bear HTML SHA-256 为 `6aaf6cb6d1bb09b7516a0dda1523c0dcbed273943407c4290522d044748233f6`；HTML 解析和 `git diff --check` 通过。

日报一致性检查退出码为 1，唯一发现为正式 Markdown 原有的 `placeholder_sector_fact`：日报仍含“待补充板块”事实。该问题不来自本轮 Bear 展示修改；为保护正式历史 Markdown，本轮不修写该文件，因此不把整项检查记录为通过。

### 2026-08-13 提交前独立审计

- 统一墙钟从 `11:40:26.302 +08:00` 开始，8 分钟阶段节点为 `11:48:26.302`，10 分钟截止为 `11:50:26.302`；本轮有效并行墙钟为 8 分 55.698 秒。
- 代码行为审计于 `11:40:26.302` 开始、`11:49:22.000` 结束，未被停止，有效发现 1 项：独立 Markdown 重建入口未传创业板载荷。已新增 `--chinext-index-trend-json` 并补充入口回归测试。
- 产物一致性审计未成功派发，未开始、未结束，不适用停止状态，有效发现 0 项；未在同一轮重新派发宽任务。主线程改做定向核验：正式 Markdown 与快照哈希不变、Top50 25 日与创业板 24 个同日点、2026-07-30 保持缺失、双视口无页面横向溢出、图例分别关闭和恢复、画布非空、控制台无错误。
- 审计后抽查还发现 PostgreSQL 查询可能先取 25 行再过滤而少于 25 个有效点；已让 `finite_positive_close_only` 在 SQL `LIMIT` 前生效，并新增查询顺序回归测试。

### 2026-08-13 收尾独立审计

- 统一墙钟从 `12:24:22.188 +08:00` 开始，8 分钟阶段节点为 `12:32:22.188`，10 分钟截止为 `12:34:22.188`；两个审计共用 10 分钟预算。
- 代码行为审计于 `12:24:45.818` 开始，8 分钟节点无阶段证据，主线程于 `12:33:21.564` 停止；有效发现 0 项。停止后主线程抽查 SQL 过滤顺序、独立 Markdown 重建入口、双轴/缺失值渲染和对应测试，未发现新增问题。
- 产物一致性审计于 `12:24:59.867` 开始，在 8 分钟节点返回“暂无确认发现”，并于统一截止结束，未由主线程中断；有效发现 1 项：图卡可见说明和 `aria-label` 仍沿用旧单线口径。已改为有创业板事实时显示“Top50成交占比与创业板指趋势”和双轴说明，无创业板事实时保留原单线文案，并补充两个分支的回归断言。
- 修复后重新运行 PostgreSQL 存储 61 项（1 项跳过）、入口与 Bear 渲染 129 项、日报渲染 101 项，均通过；HTML 解析、`git diff --check`、默认宽度与 390px 页面核对通过。正式 Markdown 与快照哈希不变，Bear HTML 新哈希为 `6aaf6cb6d1bb09b7516a0dda1523c0dcbed273943407c4290522d044748233f6`。

## 2026-08-14 板块资金扩散淘汰赛三坐标

历史验证命令（2026-08-14 当时执行；Trellis 校验命令已不再可用）：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_candidate_decision_evidence \
  tests.test_selection_workflow \
  tests.test_elimination_tournament \
  tests.test_report_runtime \
  tests.test_sector_stage_mainline

.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_llm_wiki_context \
  tests.test_llm_wiki_manifest \
  tests.test_llm_wiki_router

.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py \
  2026-08-06 --replay

.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py validate \
  .trellis/tasks/08-13-sector-tournament-three-axis
git diff --check
```

要求覆盖：

- 八类校准样本分别识别空间、时间、认知位置；普通下跌不能事后命名成首次主动分歧。
- 同一输入重复构建得到相同输入哈希与产物哈希，且构建器不修改输入。
- 目标日之后的趋势、价格或分歧事实不能进入目标日判断；日期或两级哈希损坏时整份产物拒绝展示。
- 阶段跨度按交易所日历含首尾计算；第 2 个活跃日和第 9 个交易日只能保持候选或事实不足，第 10 个交易日首次满足全部条件时才写确认日，且首次确认日与最近确认日相等。
- 候选期确认日为空；后续完整续证只移动最近确认日，弱化或失效保留最后完整续证日。逐项核对 `启动日 <= 确认日 <= 最近确认日 <= 截至日`，且截至日等于目标日。
- 从去重活跃日、冷却后回流、逐日板块指数路径、相对强度指标/窗口/比较范围/覆盖率/名次、内部趋势股分子分母/定义版本，以及适用的分歧与修复日期重算阶段身份；不信任概括标签。
- 覆盖双主线并存、未经分歧检验、停止回流、指数路径中途走弱、比较范围不完整、内部只有单股、密度下降、相对强度落后、修复失败和失效后单日修复等反例。
- 当日主攻线、日内多次轮动、两个活跃日、两个指数端点或单股强势均不得确认阶段主线；未来事实不得进入目标日产物、工作流载荷或两级哈希。
- T0 只冻结未来一至两个交易日的板块竞争假设；加入 T+1/T+2 事后结果只能改变复盘结论，不能改变原始 T0 判断或正式决定投影。
- 工作流、淘汰赛、生成前复核、Markdown、companion HTML 和内嵌 JSON 使用同一三坐标产物。
- 没有真实量价事实时，量化痕迹层显示事实不足，不用概念文案补齐。
- replay 比较明日执行对象、仓位、执行性质、B1/B2、旧仓、退出动作和最终动作，确认三坐标接入前后逐字段一致。

### 2026-08-14 旧口径验证结果

以下结果只证明 R1-R10 兼容基线，不能证明当前 R12-R16 已完成：

- `tests.test_candidate_decision_evidence` 42 项、`tests.test_selection_workflow` 68 项、`tests.test_elimination_tournament` 57 项，组合回归共 167 项；`tests.test_report_runtime` 401 项、Wiki 三模块 169 项全部通过。
- 八个目标 Python 文件通过语法检查；Trellis 任务校验和 `git diff --check` 通过。
- 新增反例覆盖：已有两个历史斜率日期时追加未来说明或来源不改变目标日产物与两级哈希；系统性风险优先进入失败校准；新三坐标覆盖旧复核列表；旧列表在没有结构化量价事实时改写为事实不足。
- `2026-08-06 --replay` 运行到最终日报一致性检查后，因 `placeholder_sector_fact` 和 `extreme_conviction_tracking_missing` 两项既有历史事实缺口停止。官方快照和既有 replay 快照 SHA-256 分别保持 `c35d2c49c7326dc1063f114f6939fd4cbec6e7124ab4fc82c8a0c6f10242b318`、`94e3aae13911451fae01353228e7180d1e2a43c71a748ba0bd3a646d8f76d900`；正式 Markdown 与 Bear HTML 分别保持 `b0685d54fcf632fe5576ca246130a3afb46eada54451c0b195aa881be3244f6c`、`0ee5531d4a58f8f8137dfbcfe9dd3c580a95ee1e6272593a978ae3335a561d38`，没有覆盖正式历史产物。
- 官方与 replay 快照的只读冻结投影中，正式对象、仓位、执行性质、账户动作、账户结果、B1、B2、旧仓、退出动作和资金去向 11 组字段逐项一致；共同缺失的历史正式输入和账户判断保持事实不足。

### 2026-08-14 旧口径提交前独立审计

- 两个审计共用 `01:04:09.815` 至 `01:14:09.815 +08:00` 的 10 分钟墙钟；统一截止时停止继续等待，不把两路耗时相加。
- 代码行为审计确认 3 项：未来日期只过滤日期数组却保留说明/来源，系统性风险与“假设获得验证”并存，旧兼容决定列表写入无来源正向量价描述。三项均已修复并增加反例。
- 跨产物审计确认 1 项：旧复核载荷与新淘汰赛合并时可能保留旧决定列表，造成十问与新三坐标分叉。现改为有效三坐标存在时始终由其十问重建决定列表。
- 处理后重新运行淘汰赛 56 项和日报运行时 401 项，均通过；其他模块在最后一次各自输入变更后保持 40、64、169 项通过。

### 2026-08-14 旧口径来源日期边界复核

- 首轮代码行为审计超出统一 10 分钟截止，主线程停止继续等待后采用 1 项有效发现：无自身来源日期的阶段主线、当日主攻线、日内轮动次数与斜率说明可能进入历史目标日产物和哈希。该轮不作为修复后的最终审计结论。
- 已在 `selection_workflow` 生产层和三坐标规范化层同时增加字段级来源日期约束，并补无日期未来说明、未来名称、未来当日主攻线与未来日内次数反例。
- 修复后 `tests.test_candidate_decision_evidence` 41 项、`tests.test_selection_workflow` 65 项、`tests.test_elimination_tournament` 56 项、`tests.test_report_runtime` 401 项全部通过。
- 正式快照与现有 replay 快照的完整正式决定投影逐字段一致，投影哈希均为 `aba746928b8b3b0b52356b0518a56048c40cd522ee16aa5e84c5e6c2b55a61f7`。
- 修复后的来源日期终审使用 `03:27:47.649` 至 `03:37:47.649 +08:00` 的统一墙钟。来源日期、规范化输入与产物一致性主题在截止前返回阶段证据，截止时结束，有效发现 3 项：方向与自身日期解耦；高优先级未来或无日期事实压掉有效旧事实，并可能把别层日期配给当前值；规范化输入与产物未逐字段保留结构化斜率说明，且证据不足后仍残留肯定标签。
- 已改为值与自身来源日期成对选择并逐级寻找有效事实；`direction_source_date` 进入规范化输入、产物和两级哈希；轮动或指数路径不足两个日期时对应状态回到事实不足；结构化斜率说明原样进入阶段主线；淘汰赛消费者除两级哈希外，还核对方向、阶段字段、来源日期和规范化输入。
- 处理后完整重跑三坐标 42 项、工作流 68 项、淘汰赛 57 项（合计 167 项）、日报运行时 401 项和 Wiki 169 项，全部通过。该终审没有新增交易决定问题；固定 replay 仍只因上述两项既有历史事实缺口停止。

### 2026-08-14 R12-R16 纠偏后验证与独立审计

- 纠偏实现完成后，`tests.test_candidate_decision_evidence` 与 `tests.test_sector_stage_mainline` 合计 49 项通过；核心五模块组合 576 项在独立审计前后各完整通过一次，审计后复验用时 1079.700 秒。
- 新增反例确认：早于阶段第 10 个交易日的输入确认日被清空并暴露日期问题；删除应比较方向会保留空事实并降低覆盖率；纯说明文字不能把明确分歧改写为已修复。有效修复必须同时核对板块指数路径、修复日资金重新活跃和内部趋势股密度。
- 新一轮审计共用 `2026-08-14 15:16:40` 至 `15:26:40 +08:00` 的 10 分钟墙钟，8 分钟阶段节点为 `15:24:40`。代码行为审计于 `15:25:02` 结束并按时限停止，有效发现 3 项：历史确认日可提前倒写、比较范围可通过删方向伪装满覆盖、任意文字可冒充分歧修复；三项均已修复并补回归。
- 跨产物审计在阶段节点后 22 秒返回“暂无确认发现”，主线程立即停止，按时限记录为未完成、有效发现 0 项。随后定向核对工作流、淘汰赛、生成前复核、Markdown 与 companion HTML 仍只消费同一有效三坐标产物；正式决定隔离由完整组合回归和冻结决定投影继续覆盖。
- `2026-08-06 --replay` 再次运行到最终日报一致性检查，仍只因 `placeholder_sector_fact` 与 `extreme_conviction_tracking_missing` 两项既有历史事实缺口停止；没有覆盖正式历史产物。官方快照、replay 快照、正式 Markdown 和 Bear HTML 的 SHA-256 仍分别为 `c35d2c49c7326dc1063f114f6939fd4cbec6e7124ab4fc82c8a0c6f10242b318`、`94e3aae13911451fae01353228e7180d1e2a43c71a748ba0bd3a646d8f76d900`、`b0685d54fcf632fe5576ca246130a3afb46eada54451c0b195aa881be3244f6c`、`0ee5531d4a58f8f8137dfbcfe9dd3c580a95ee1e6272593a978ae3335a561d38`。
- 正式与 replay 的 11 组冻结决定字段逐项一致，字段子集哈希均为 `dc4378a6ff749d453a6f5bce308bbc28d2b105e713579b981a9ef51580b220ce`。两边共同缺少 `formal_decision_input` 与 `formal_account_decision`，继续显示历史事实不足，不伪造账户动作。
- `2026-08-14` 官方快照尚不存在，因此没有运行该日隔离 replay，也没有用盘中或当前事实替代完整 T+2。Trellis 任务校验、目标 Python 文件语法检查和 `git diff --check` 均通过；Wiki 三模块最近一次 169 项回归通过，纠偏修复未改 Wiki 文件。

## 2026-08-14 板块相对路径泳道

验证命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_daily_report_markdown_html \
  tests.test_daily_report_entry_html_output \
  tests.test_sector_stage_mainline

node --check <从固定 Bear HTML 提取的内联脚本>
git diff --check
```

已完成覆盖：

- 10 项最窄测试覆盖共同起点归一、高质量修复、窗口不一致、缺日断点、稀疏旧方向不跨未记录日期连线、缺失指标不显示为 0、无效哈希回退、未来日期排除、Bear 输入哈希，以及文件函数和命令行入口传递；随后四模块完整回归 181 项通过。
- 浏览器首次检查发现两项仅靠字符串断言无法识别的问题：`custom.renderItem` 从不提供原始泳道的字段取数，导致相对路径未绘制；`Number(null)` 把缺日变成 0，造成假暴跌和无路径板块假平线。现分别改为按 `params.dataIndex` 读取闭包载荷和使用 `nullableNumber`，并增加回归断言。
- 修复后桌面画布为 `760x320`，完整样本分别显示 `阶段主线 / 当前评估` 与 `当日主攻`；缺日样本在 2026-08-06 形成真实断点，无路径板块不画价格线。
- 桌面页面宽度为 `1440/1440`，390px 页面宽度为 `390/390`；390px 图内轨道为 `174/760`，滑杆末端与图内位置同步为 `586/586`，向左滚动后同步为 `406/406`。
- `test_bear_html_input_hash_and_extraction_include_sector_three_axis` 证明 Bear 提取与输入哈希携带同一产物；`test_sector_cycle_swimlane_rendering_keeps_complete_formal_decision_projection` 用固定夹具逐字段比较对象、仓位、执行性质、账户动作、B1、B2、旧仓、退出动作和资金去向，相对路径 v2 渲染前后完全一致。
- JavaScript 语法检查通过；浏览器页面本身没有控制台错误，记录到的报错来自已安装扩展自身脚本，不属于日报页面。
- 两路提交前独立审计共用 `2026-08-14 23:52:24.529` 至 `2026-08-15 00:02:24.529` 的 10 分钟预算，均未被停止；从统一开始到最后一路完成的并行墙钟为 7 分 25 秒。
- 代码行为审计运行于 `23:53:15.629` 至 `23:59:22.568`，有效发现 3 项：缺失指标误写为 0、稀疏方向跨空白日期连线、文件函数/命令行未携带三坐标。三项均已修复并加入回归测试。
- 产物一致性审计运行于 `23:54:05.278` 至 `23:59:49.507`，有效发现 3 项，其中独立重渲染入口与前一路重复；其余两项为决定字段缺少可复查测试证据、任务验收记录未同步。前者已转为九字段自动化比较，后者在本任务收尾同步。

## 2026-08-17 板块反馈区间泳道

本轮把 v2 主图从逐日短横线改为甘特式反馈区间，价格路径降为辅助线；逐日节点分别表达价格响应、跨日反馈、轮动/回流、成交参与、主力净流入和机构净买。

中断恢复后的验证证据：

- 修复后 `tests.test_daily_report_markdown_html` 88 项通过；`tests.test_daily_report_markdown_html`、`tests.test_daily_report_entry_html_output`、`tests.test_sector_stage_mainline` 三模块完整回归 155 项通过。目标 Python 文件语法、当前渲染结果的 1 个内联 JavaScript 脚本块和 `git diff --check` 均通过。
- 固定夹具覆盖 `2026-07-31 -> 2026-08-14` 连续反馈区间、左侧轴外起点回退、区间在横轴前已结束时不被更晚事件重新拉起、价格路径缺日仍保留区间、弱化/失效结束于最近完整续证日、主力净流入与机构净买分离、同日节点详情隔离、机构表缺股票列或股票无法映射板块时不生成节点，以及九字段决定投影不变。
- 浏览器复核覆盖桌面和 `390px`：页面宽度分别为 `1440/1440`、`390/390`，`760x340` 画布非空；390px 抽样 64600 个像素中有 9129 个非背景有效像素，三条左侧标签无文字溢出。同日七类证据分成 7 个独立节点，25 项事件对应 25 个图形，目标日节点包围盒碰撞数为 0；每个节点只显示自身详情和机构个股。
- 桌面滑杆与图内滚动在末端和中点分别同步为 `60/60`、`30/30`；390px 下分别同步为 `622/622`、`311/311`。重新载入当前页面后控制台错误和警告均为 0；截图保存在 `.generated/browser-check/sector-feedback-390.png`，临时 HTML 和静态服务已清理。
- `2026-08-06 --replay` 运行到最终一致性检查后，因既有 `placeholder_sector_fact` 历史事实缺口停止生成。正式快照、Markdown、Bear HTML 和 replay 快照的 SHA-256 仍分别为 `c35d2c49c7326dc1063f114f6939fd4cbec6e7124ab4fc82c8a0c6f10242b318`、`b0685d54fcf632fe5576ca246130a3afb46eada54451c0b195aa881be3244f6c`、`0ee5531d4a58f8f8137dfbcfe9dd3c580a95ee1e6272593a978ae3335a561d38`、`94e3aae13911451fae01353228e7180d1e2a43c71a748ba0bd3a646d8f76d900`，文件时间不变，没有覆盖正式历史产物。
- 正式与 replay 快照的对象、仓位、执行性质、账户动作、B1、B2、旧仓动作、退出动作和资金去向九字段一致，规范化子集哈希同为 `8cb28287be1fb592d5009a678f0fa892e72304ca0309997b696c15e8775ccd89`；两边共同为历史 `no_trade/unresolved`，只证明展示修改前后未变化，不把它写成完整交易决定证据。

本轮提交前独立审计：

- 两路审计共用 `2026-08-17 23:48:38.067` 至 `23:58:38.067 +08:00` 的 10 分钟预算；均在阶段节点前返回证据且未被停止。从统一开始到最后一路完成的并行墙钟为 7 分 42.621 秒。
- 代码行为审计从 `23:48:38.067` 至 `23:55:35.960`，有效发现 4 项：已经结束的阶段会被结束日后事件重新拉起、左侧轴外起点没有裁到首次可核实反馈、同日节点混入其他类型详情、同日节点发生视觉重叠。四项均已修复并补回归。
- 产物一致性审计从 `23:49:54.543` 至 `23:56:20.688`，有效发现 1 项，与代码行为审计的左侧轴外起点问题重复；合并采用同一修复和反例。正式产物哈希、九字段决定投影及 replay 隔离复核均未发现新增问题。
## 2026-08-20 股指期货净空趋势图

验证命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_cffex_index_futures_position \
  tests.test_cffex_index_futures_position_evidence \
  tests.test_cffex_position_backfill \
  tests.test_postgres_daily_fact_db \
  tests.test_report_replay \
  tests.test_daily_report_render \
  tests.test_daily_report_markdown_html \
  tests.test_daily_report_entry_html_output

.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-08-19 --replay
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  reports/replay/2026-08-19_A股日报_完整版_replay.md --json
```

已覆盖：

- Bear 只从同目标日、同来源日的冻结载荷读取最近 60 日，不从 Markdown 摘要表反推；未来日期排除，缺失值保持 `null`，冲突重复日期拒绝生成图。
- 三个共享日期轴分别使用名义金额折线、会员日变零轴柱和前 20 榜单差额折线；图例可独立显隐，目标日高亮，原目标日精确表继续保留。
- 文件渲染和 CLI 覆盖无载荷、有效载荷、坏 JSON 和非对象 JSON；Bear 输入哈希覆盖 CFFEX `artifact_hash`，A/B 哈希变化会实际触发重新渲染。
- 当前 replay HTML 的桌面画布为 `944x651`，390px 画布为 `302x611`；有效像素抽样分别为 11512 和 4911。两边页面 `scrollWidth/clientWidth` 分别为 `1440/1440`、`390/390`。
- 默认窗口索引为 `40..59`，60 日切换后为 `0..59`；两个视口均为 3 个系列、3 个横轴、3 个纵轴，截图目检无明显文字重叠。
- 新截图保存在 `.generated/verification/2026-08-19-cffex-trend-current-desktop.png`、`.generated/verification/2026-08-19-cffex-trend-current-mobile.png` 及对应的 `-60.png`。
- 正式与 replay 决定投影哈希均为 `0abb5a38be8a6679de1c83c303a2aed59a5c997cfa2ab861e67df1364c0d998e`，`selection_workflow` 与 `final_target_resolution` 逐对象一致。

## 2026-08-30 八月热门股双群聚证据

历史验证命令（2026-08-30 当时执行；Trellis 校验命令已不再可用）：

```bash
.generated/venv-py314/bin/python3.14 -m unittest -b \
  tests.test_market_polarization_evidence \
  tests.test_market_polarization_report_runtime

.generated/venv-py314/bin/python3.14 -m unittest -b \
  tests.test_market_polarization_evidence \
  tests.test_market_polarization_report_runtime \
  tests.test_report_runtime \
  tests.test_daily_report_markdown_html \
  tests.test_daily_report_entry_html_output \
  tests.test_daily_report_render \
  tests.test_report_replay

.generated/venv-py314/bin/python3.14 scripts/knowledge/llm_wiki_lint.py
.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py validate \
  08-30-august-hot-stock-polarization-bear-evidence
git diff --check -- \
  AGENTS.md docs/daily-report-structure-optimization \
  scripts/report/market_polarization_evidence.py \
  scripts/report/runtime.py scripts/report/markdown_report_html.py \
  tests/test_market_polarization_evidence.py \
  tests/test_market_polarization_report_runtime.py \
  wiki
```

已完成覆盖：

- 载荷校验确认来源日、采集/可用日、同口径分母、来源哈希、全市场反证和解释范围；明确废弃 `68.9%`。
- 精确 Wiki 词组可命中，单独的宽泛词不命中；Wiki、Markdown、Bear 和快照冻结副本复用同一研究哈希。
- fresh 缺少 `query_date` 时按报告目标日判断；研究可用边界取合法 `target_date` 与 `query_date` 中较早者；目标日在 `available_from` 之前不渲染研究段。replay 可用日之前不使用冻结副本，也不读取当前研究文件；可用日后的冻结副本正常复用。
- 完整版、摘要版和 Bear 均保持正式行动在研究证据之前；挂载前后完整正式决定逐字段不变，研究不取得买入资格。
- 目标 Python 文件语法检查、定向 24 项测试和此前 781 项受影响组合回归均通过。研究可用边界取合法 `target_date` 与 `query_date` 中较早者。尚未新增真实历史日报覆盖；现有 replay 若因其他既有事实缺口停止，按数据缺失记录，不用当前盘面替代。
- 最新 Bear 抽检确认研究章节存在并归入证据区；桌面与 `390px` 页面宽度均为 `1440/1440`、`390/390`，研究宽表只在自身容器内横向滚动，页面没有横向溢出。长哈希行的断行规则已补回归。
- `scripts/knowledge/llm_wiki_context.py` 已改为按合法 `target_date` 与 `query_date` 的较早者过滤日期知识，并新增混合日期回归；8 月 30 日知识不会倒灌到 8 月 29 日查询。

本次恢复后的追加复核：

- `tests.test_dual_cluster_projection`、`tests.test_elimination_tournament`、
  `tests.test_daily_report_markdown_html`、`tests.test_report_runtime`、
  `tests.test_position_strategy_report` 和
  `tests.test_market_polarization_evidence` 共 636 项通过；研究/Wiki 相关
  7 个模块再通过 231 项。
- 账户投影覆盖 `Ta`--`Te`、Te 目标归属、核心占用与 B1/B2 容量分离、九类
  校准样本、未来事实排除和中文可见状态；淘汰赛投影覆盖来源哈希、单日脉冲、
  续证迁移、缺口去重和内部枚举不出现在可见区域。
- 1440px 伴随页页面宽度为 `1440/1440`，三张投影卡无重叠且子元素无溢出；
  Bear 主页面 Mermaid 资源返回 200、控制台无错误，账户双轨覆盖 Ta--Te，
  原始六列表位于默认收起区。后续 390px 复核沿用同一页面级宽度断言。

### 本轮提交前独立审计

- 统一墙钟从 `2026-08-30 10:54:49.813 +08:00` 开始，8 分钟阶段节点为 `11:02:49.813`，10 分钟截止为 `11:04:49.813`；两路审计共用该并行预算。
- 产物一致性审计在截止前确认 2 项有效发现：Wiki 上下文按 `query_date` 单独过滤会把 8 月 30 日知识带入 8 月 29 日查询；验证记录仍写成定向 20 项、受影响组合 777 项。前者已由目标/查询日较早者修复并补混合日期回归，后者已修正为 24/781。
- 代码行为审计在统一截止前未返回阶段证据，主线程按时停止，不能记录为“暂无发现”；停止后的定向测试、语法检查、Bear 抽检和关键出处复核由主线程完成，未发现新增问题。

### 2026-08-31 中断恢复后的最新提交前审计

- 两路审计共用 `started_at=1788186149.8099258`，8 分钟阶段节点为
  `1788186629.8099258`，10 分钟截止为 `1788186749.8099258`；对应上海时间
  约为 `22:22:29` 至 `22:32:29`。记录使用同一并行墙钟。
- 产物一致性与代码行为两个主题均未在阶段节点前返回可采用出处，按统一截止
  停止并记录为 `conclusion=incomplete`、`stopped=true`、
  `stage_evidence_received=false`、`finding_count=0`。不能把这轮写成“暂无发现”，
  也未重新派发宽审计。
- 主线程完成了补充复核：目标文件完整，定向测试、语法检查、Wiki lint、任务校验
  和限定 `git diff --check` 继续作为最终证据；Bear 桌面/390px 页面检查确认页面
  宽度不溢出、双群聚投影可见，正式决定字段未被展示层改写。

### 2026-08-31 第二轮提交前审计（中断恢复后）

- 两路审计共用 `started_at=1788190653.7810419`，8 分钟阶段节点为
  `1788191133.7810419`，10 分钟截止为 `1788191253.7810419`；主题为
  `artifact-consistency` 和 `code-behavior`。
- 两路均未在阶段节点前返回可采用出处，按统一节点停止并记录为
  `conclusion=incomplete`、`stopped=true`、`stage_evidence_received=false`、
  `finding_count=0`。不能把这轮写成“暂无发现”，也未重新派发宽审计。
- 主线程随后完成定向出处抽查，并复跑核心 `636` 项、研究/Wiki `675` 项、
  Python 语法、Wiki lint、Trellis 任务校验、限定 `git diff --check` 和 Bear
  `390px` 页面检查；页面级宽度为 `390/390`，账户双轨可见，原始六列默认收起，
  正式决定字段未被展示层改写。


## 2026-09-20 用户确认的图表精简版

- 修改前：Bear 全文包含长解释、重复原表及未选图表。修改后：`scripts/report/compact_bear_report.py` 从已生成 Bear HTML 提取 11 项独立精简页，原 Markdown、完整 HTML 和快照保留。
- 固定顺序：明日执行结论、T0市场底色、两市成交额趋势、Top50成交占比与创业板指趋势、周期日历主视图、板块资金扩散淘汰赛、成交额Top30、当日封板金额排行、股指期货净空结构趋势、创新高全A占比、龙虎榜净额表态。未选项不在精简页展开。
- 板块淘汰赛保留首张摘要表，原证据和反证折叠保留；周期日历与操作收益日历分开。封板金额使用目标日 `limit_list_d.fd_amount`（元），仅收盘涨停，过滤 ST、*ST 和无效金额；默认前20，可展开全部。
- 不变项：候选、最终对象、仓位、执行性质、B1/B2、旧仓与退出动作不重算；精简前后执行结论逐格相同，源文件哈希不变。缺图保留事实不足说明。
- 验证：Python 3.14 执行 `-m unittest tests.test_compact_bear_report tests.test_historical_rebuild`；浏览器核对 11 项顺序、淘汰赛折叠、封板前20/全部切换及 1440px、390px 下画布非空和页面无横向溢出。
- 封板图样式修正：沿用成交额Top30的配色、字体、细横柱和圆角；柱尾同时标注亿元与万手，390px 下分两行。手数按封单金额 ÷ 收盘涨停价 ÷ 100 换算，缺价保持待确认；小金额增加小数位，避免正值显示为零。名称按 ST、*ST 前缀排除，代码去除首尾空白后检查。
- 期货图遗漏修正：2026-09-18 正文已有完整持仓事实，补齐 HTML 渲染参数及 replay 快照的 `cffex_index_futures_position_evidence`，移除过时的缺失来源说明。校验目标日期与哈希，保留20／60日切换和三图例独立显隐；明日执行结论与四组正式决定字段逐项不变。
- 本次验收：Python 3.14 定向测试38项通过，Markdown一致性检查通过；1440px、390px均保留11项、8张非空图，封板20/78切换正常，柱尾金额和手数均未越过画布边界。期货20/60切换及三图例独立显隐通过，浏览器错误数为0。截图位于 `.generated/chart-picker/seal-final-*.png` 和 `futures-final-*.png`。
- 独立审计：单个代码行为主题，2026-09-20 16:06:37至16:11:35（上海时间），墙钟298.39秒，未被停止；确认2项问题，均已修复并补测试。详细时间记录见 `.generated/chart-picker/seal-audit-timing.json`。本轮没有提交或覆盖正式历史报告。

## 2026-10-01 板块假设精简版日报（历史版本）

- 单测覆盖行业事实的目标日/来源日/查询日一致性、来源标识、未来日期排除、无效数值、重复行业、HTML转义、冻结方向哈希校验和 CLI 快照传参。
- 单测覆盖精简版中执行结论先于证据、六个板块观察问题、三个竞争假设卡、概率未估计、最大计划损失待核定和正式执行表不变。
- 目标日 `2026-09-29` 重新生成后，正式完整版 Markdown、完整版 HTML 和快照 SHA-256 与生成前一致；精简版共12项，原7张图表画布保留。
- 浏览器检查覆盖 1440px 与 390px：页面宽度无横向溢出，板块事实表只在自身区域滚动，三个假设卡无内容溢出，研究区默认收起内容可展开，淘汰赛原证据仍可展开。

## 2026-10-01 新版板块日报

- `tests.test_sector_daily_report` 覆盖主文四部分、前三行业、三个竞争假设、主文长度、缺失事实、日期冲突、HTML转义、执行表与图表JSON不变、快照不改写、replay同目录、CLI、写入失败保留原文件和生成入口接入。
- 定向验证：`.generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_daily_report tests.test_compact_bear_report tests.test_historical_rebuild tests.test_daily_report_entry_html_output tests.test_daily_report_consensus_compact_output`。
- 产物比较：正式完整版Markdown/HTML、旧图表精简页和快照哈希不变；新页与旧页执行表逐格相同，图表JSON相同，原淘汰赛正文完整保留。
- 浏览器1440px/390px检查四部分顺序、3行板块/3行假设、原图表默认收起、展开后7张画布有像素、再次收起、页面无横向溢出与控制台无错误。记录在 `.generated/sector-daily-20260929/`。

## 2026-10-02 假设修正验证

Python 3.14执行 `tests.test_hypothesis_revision`、`tests.test_compact_bear_report`、`tests.test_sector_daily_report`、`tests.test_historical_rebuild`、`tests.test_daily_report_entry_html_output`，共111项通过；覆盖日期边界、同源身份、缺失不等于失败、原记录不可改写、相对优势及三假设一致。语法检查与 `git diff --check` 通过。

9月30日两份产物的假设哈希相同，前次复核只用9月29日。1440px/390px浏览检查：3张板块卡、3条前次复核、8个有像素图表；封板前20/全部52切换有效，板块图表默认收起且展开/收起正常，页面无横向溢出。原执行结论按原表核对；9月29日正式文件与快照哈希仍与上一轮基线相同。

本轮日期账本验证：`tests.test_hypothesis_revision`、`tests.test_compact_bear_report`、`tests.test_sector_daily_report` 共51项通过；覆盖同日重生成复用、不同事实拒绝覆盖、旧身份退出榜单仍续验、缺口不判失败、首验失败/缺失不被后续成功改写、来源哈希与 replay 目录隔离。2026-09-30 账本哈希为 `47cea522feb8875ea129da43c60964270a9cdaf7257ff17c31523230679d454b`；两页共享该记录，执行表与原图表 JSON 不变。Playwright 在1440px/390px检查两页各8张图表尺寸有效、6条持续观察摘要、9行逐期事实；390px精简页8张画布均有像素，展开与收起均为 `scrollWidth=viewport`。

## 2026-10-03 生命周期验证

- Python 3.14 定向测试覆盖支持→撤销→恢复、缺证→补证、部分字段缺失、追加事件不改旧行、混合撤销与缺口摘要，以及两页共用记录。
- 浏览器在1440px与390px打开两页，检查日期节点、首验结果、逐项条件表的展开/收起、8张画布非空和页面 `scrollWidth` 不超过视口。
- 9月30日两份产物复核：旧行业事实保持缺证暂停；新同花顺指数保持建立观察；账本、原执行结论和图表 JSON 未被改写。
# 2026-10-04：主动跟踪回归

新增`tests.test_tracked_sector_facts`覆盖退榜仍查询、下跌撤销、代码/日期/成员完整性、起点复算、非有限数、查询失败留痕、同日内容不可覆盖、两页同源、历史显式查询、replay隔离、失败重试不遮盖成功、矛盾结果拒收、跨日补查进度和首日不自证。与原五组日报测试最终综合验证140项通过。

产物证据：`.generated/reports-20260930/tracked-facts/`。38份受保护文件哈希不变；两页同账本、同补查凭据、原执行表和图表JSON逐项相同；1440px/390px图表非空、展开收起正常且无页面溢出。

9月30日实数补查已完成：78只固定成员行情聚合得到全国地产+1.778350%（16/26上涨）、区域地产+0.688148%（23/43）、软饮料+0.328287%（5/9）；两页均为3项续证、0项取数未完成，并有2处地产上涨面收窄提示。原账本与原缺证首验保持不变。备用路径新增5项回归覆盖响应身份/地址、来源、日期、金额单位、复权、完整成员、起点复算与篡改凭据，最终综合145项通过；浏览器检查沿用产物未变的本轮1440px/390px结果。最终日志、跨来源复算与独立审计记录在`.generated/reports-20260930/history-repair/`。

趋势路径验收：`.generated/reports-20260930/trend/artifact-verification.json` 确认6条路径、共同窗口2026-08-31至09-30、每条22个交易日节点，两页路径正文相同，原执行表与图表JSON不变。Playwright在1440px/390px展开全部6条路径，SVG非空、逐日表132行、原单日记录可展开收起、8张旧画布非空且页面无横向溢出。趋势定向测试与原组共157项通过；原始行情留在趋势sidecar，不膨胀HTML。

## 2026-10-06 交互趋势验收

本节替代上轮静态SVG展示验收。Python3.14七组定向测试共163项通过；新增覆盖前缀不改写、缺失/相对优势丢失结束回踩、弱势反弹不造信号、缺宽度仅记价格修复、收窄不称扩散恢复、HTML转义与只读。

两页1440px/390px的3个新ECharts均有像素，真实tooltip含日期/数值/修正，图例显隐/恢复、缩放/恢复、板块与口径联动、色带点击、原表展开/收起通过，无页面溢出。原8张图表保留、132条节点存在，41份保护文件及原执行表/JSON一致。

证据：`.generated/reports-20260930/trend/charts-verification.json`、`charts-browser-check.js`、`artifact-verification.json`。独立产物审计无发现；代码审计无阶段证据被停止，不计通过。两项共用一个计时起点，墙钟537.86秒，不累加代理耗时。

## 2026-10-07 电脑端五图验收

当前及后续设备范围只含电脑端，以1440px为基准；不再安排390px测试，以上旧结果保留为历史记录。

- Python3.14七组定向测试170项通过，覆盖新增/保留观察、背景不计续证、弱势反弹、缺失中断、冷热分档边界、候选最少观察期与上涨面缺口、逐日前缀不改写、日期和来源校验、两页同源。
- 两份9月30日报告各5张非空ECharts、6行冷暖方格、6行阶段进度、132条逐日记录；走势、回撤、上涨面各自有独立坐标轴和tooltip。
- 1440px真实鼠标悬浮只显示当前图数据；图例显隐与恢复、独立缩放与恢复、比较口径和板块选择、方格点击、缺上涨面提示、详情展开/收起通过。页面无横向溢出，脚本错误为0。
- 41份保护文件哈希不变；执行结论原表和原图表JSON逐项相同，两页研究正文相同。
- 主线程直接检查，发现并补齐阶段角色未显示的问题；本轮没有新增独立代理审计，未提交。

证据位于`.generated/reports-20260930/trend/`：`desktop-tests.log`、`desktop-browser-verification.json`、`artifact-verification.json`；`charts-browser-check.js`现仅运行1440px。
## 2026-10-12 Bootstrap 六版式与自动重点标注验收

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_daily_report tests.test_sector_trend_tracking tests.test_tracked_sector_facts tests.test_compact_bear_report tests.test_daily_report_markdown_html`：190项通过，新增覆盖Bootstrap卡片字段、缺失新仓不编造、执行条件保留、折叠保留原表、窄屏堆叠表列名和自动标注语义。
- 样式来源：`scripts/templates/vendor/bootstrap-6.0.0-alpha.1.min.css`（SHA-256 `678508b1…6095112`）与官方 SHA384 一致，`bootstrap-LICENSE.txt` 同目录保存。
- 重渲染 `reports/replay/2026-10-09_A股日报_板块日报_replay.html`：15份保护文件哈希不变，执行/大盘/研究文字与冻结脚本载荷逐项相同，自动标注26处，净空默认60日，进度表默认收起。
- 浏览器 1440px / 768px / 390px：首屏导航、居中标题、执行卡、折叠区与7张图表画布正常；导航跳转自动展开证据并滚动定位；390px板块表切换为堆叠显示列名；减弱动效下过渡为0s且内容完整；控制台无错误。
- 证据目录：`.generated/art-direction-report/artifacts/`（`before-*.png` 旧皮肤、`ship-desktop.png`/`ship-mobile.png` 交付版、`repaired-desktop.png` 审查后修复版）。
- 独立视觉审查（`frontend-art-direction` 流程，独立代理、不看实现历史）判定 `CURRENT WINS`；其提出的三处已修：结论高亮由自定义黄改为 `primary-bg-subtle`+`primary` 令牌、诊断块由米黄自研色改为 `bg-1`/`border-color`、报头留白压缩并把重点图例移到执行卡旁。发现记录：`.generated/art-direction-report/.art-direction/visual-critique/critique-20261012095515-9786e8b9.json`。

## 2026-10-13 截图式标注验证

- Python3.14：`tests.test_sector_daily_report tests.test_compact_bear_report`，46项通过。
- 10月12日轻量replay渲染：17份正式报告、快照与研究文件哈希不变；执行表、研究文字和全部嵌入JSON相同，22处自动标注保留。
- 1440px/390px浏览器：浅黄结论、浅紫待确认、淡红条件线和浅蓝说明块已实际渲染；多行高亮按行延续，页面宽度分别1425/375px，控制台无错误；引用清除旧伪元素，只保留玫红竖线。
- 10月13日正式生成前检查：Tushare目标日行情5574行；雪球已配置登录态被拒绝，正式生成停止，未用旧热榜替代。此前Top50历史25日与交易日历逐日核对，包含9月30日，无缺口。

## 2026-10-14 关系图、日期事实与Top30验收

- Python3.14定向测试285项通过：`tests.test_hypothesis_revision tests.test_tracked_sector_facts tests.test_sector_trend_tracking tests.test_sector_daily_report tests.test_compact_bear_report tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output`。
- 10月13日板块阅读页直接重渲染；19份原完整版、Markdown、快照与观察记录哈希不变，执行原表逐格相同，冻结研究载荷与468条逐日路径完整保留。成交额图取目标日冻结50条榜中的前30，其他图表JSON不变。
- 实页1440px/390px检查：桑基图18个日期结论节点、16组连线；选择软饮料后5段路径高亮、11组背景连接变淡，日期按钮与实际节点点击能查看不同日期事实，未兑现记录在后续好转时仍保留。
- 滚动走势选择疫苗及9月29日显示观察前历史背景，选择10月13日显示已冻结缺口而非补0。完整事实表默认收起，468条日期记录可展开。
- Top30实际20px柱、36px行高，画布1122px/外框620px，能滚到第30名先导智能；窄屏尾标分两行。净空默认60日及20/60切换保留。
- 展开全部折叠区后单侧边框数量0；页面宽度1440/390px时内容宽度1425/375px，控制台无错误。桑基图仅在自身容器内横向滚动。正式Markdown一致性检查通过。
- 验收证据：`.generated/modern-reader/evidence.json`、`browser-evidence.json`、`flow-evidence.json`。本轮未全量重采集日报。

## 2026-10-14 紧密矩阵与当前主攻验收

- Python3.14八组定向测试304项通过：前述七组加`tests.test_sector_chart_facts`。月份分层、来源中文和补查成功保留修正后，相关五组120项通过；最终月份居中后趋势36项通过。
- 新增边界：不同日期/代码不得填缺、未来与重复主攻日期拒收、重签内容不得替换旧事实、磁盘篡改拒收、重复查询失败不抹去成功补查、当前主攻与阶段主线分离、20名单/540明细不混入主攻对照、真实当日值不被滚动缺口遮盖。
- 真实10月14日页面：20×27=540格，默认416px，放大636px后可恢复；点击出版业9月10日显示事实不足，切回文化传媒显示同名指数与中证全指首日100对照。实际点击图例关闭文化传媒，中证全指仍开启。
- 接力默认7日期、6条主攻连接，包含10月13日通信设备→14日文化传媒；实际节点点击显示两日原始依据和中文来源，7/14份切换及全部通道切换通过。
- 1440px/390px内容宽度分别1423/373px，展开完整事实表和原图表后无页面横向溢出；矩阵和接力在组件内滚动。各13张非空画布、脚本错误0、净空默认60日且20/60切换通过。
- 6份保护文件哈希、执行表、原图表JSON、原观察记录与原趋势凭据不变；20板块当日全部有数，出版业9月10日/11日缺口保留。补查并不伪装成当时已知事实。
- 证据：`.generated/sector-matrix-oct14/smoke-evidence.json`和`browser-evidence.json`。未全量重采集日报，未改写交易对象、仓位、B1/B2或退出动作。

## 2026-10-15 PDF参考与图表统一验收

- 参考PDF首屏、摘要页、时间线和图表页已读取；实际页面改为浅灰紫底、白卡、衬线大标题、紫色导航和细边框。
- 冷暖矩阵实际显示红涨绿跌：`#E73922`/`#07C160`，20×27=540格；其他图表实际使用T0字体、图例、提示框、网格和线条参数。
- 净空图实际getOption的`dataZoom=[]`；滚轮、拖拽和触控缩放后仍60日，20日切换为20条尾段数据，提示日期与数值匹配，关闭图例后切换窗口不恢复。
- 桌面与窄屏各13张画布非空，1440px/390px页面内容宽度1425/375px；图表局部滚动不造成页面横向溢出，浏览器脚本错误0。
- 287项Python3.14定向测试通过；证据保存在`.generated/notes-reference/`。正式执行结论、原事实、快照和完整版来源未改写。

## 2026-10-16 市场底色5000家紫色提示验收

- Python3.14执行`-m unittest tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output`，167项通过；用实际生成的JavaScript验证4999/5000为绿色、5001/5108为紫色、零和缺失值保留、两条线位于负向家数坐标、提示框继续显示真实家数。移除旧的源码字符串断言。
- 10月15日冻结事实重渲染：5108家下跌的柱形为`#B000FF`，4000家绿色线与5000家紫色线同时存在；执行表、正文、全部图表JSON与28份保护文件哈希不变。
- 1440px/390px实际页面核对紫柱、双参考线与标签，画布非空且无页面横向溢出；净空图仍默认60日。证据：`.generated/market-breadth-purple-verification.json`。

## 2026-10-17 接力、24行矩阵和单曲线悬浮验收

- Python3.14：`-m unittest tests.test_hypothesis_revision tests.test_sector_trend_tracking tests.test_sector_daily_report tests.test_compact_bear_report tests.test_sector_chart_facts`，127项通过；覆盖真实同通道分叉/合并、空日报、尾部缺报、HTML转义，以及悬浮只显示所选板块的真实数值。
- 10月16日冻结输入重渲染至 `reports/replay/2026-10-16_A股日报_板块日报_replay.html`：38份正式报告、快照及观察资料哈希不变；执行表逐格一致，输入对象不变，24×29=696条事实明细保留。接力仅调整展示日期列、深度及默认选择，原节点身份、边、记录与来源哈希不变。
- 桌面默认接力：7列、18个节点、14条色带，白酒合并次强/竞争两条记录；14份与28份选项分别保留15列和36列（包含缺报日），所有节点中心与所属日期列头偏差为0。三通道筛选、白酒高亮及真实节点点击显示两日原始依据。
- 真实浏览器临时边界场景：单日报、末尾空日报、全空通道均保留正确日期列，没有非有限坐标、虚构节点或旧图残留。
- 矩阵三档大小外框高度分别504/624/768px，均 `scrollHeight == clientHeight`；24行和696格不变，实际点击最后一行水泥同步2026-10-16。390px仍全部行展开，仅日期方向局部横滚。
- 实际鼠标指向两条独立曲线的数据点，各自仅出现一个板块名、对应日期和正确累计差值；曲线段悬浮及点击读取最近节点，移到空白后提示消失。桌面13张画布均有像素，窄屏13张画布尺寸有效；1440px/390px页面宽度分别1425/375px，浏览器无脚本错误。
- 证据：`.generated/sector-charts-oct16/render-evidence.json`、`browser-evidence.json`、`relay-desktop.png`、`matrix-desktop.png`、`matrix-mobile.png`。未改原正式历史阅读页。

## 2026-10-17 阅读页标注与指数缺口回补

- 标注脚本：生成后的阅读页含 `script#sector-reader-annotations`，存储键为 `daily-report-annotations:v1:<目标日期>`，且页面不加载任何外部资源；`tests.test_sector_daily_report` 覆盖脚本位置、存储键与无外部资源三项。
- 实页操作（托管 Chromium，页面经本地静态服务打开）：选中“中证全指 +0.13% ·”点高亮得到 `mark.reader-note-mark--highlight` 且记录写入本地存储；刷新后标注仍在；划线得到 `span.reader-note-mark--underline`，装饰线 `rgb(226,114,91)`；批注记录写入正文笔注文字并出现气泡；“我的标注”面板列出章节与引文，删除后记录由2条降到1条，全部清除需二次确认且清空后页面标注为0。
- 版面：桌面 1365px 页面宽 1350px；390px 页面宽 375px，面板变为底部抽屉（left 0／right 375），13张画布仍有像素；做空趋势默认选中60日。
- 未变项：页面记录哈希 `2950f01c…` 与9个图表载荷逐字节相同；`reports/2026-10-16_A股日报_板块日报.html` 修改时间仍为 2026-10-16 18:34，未被覆盖。
- 数据缺口复现与回补：旧冻结凭据 `d7aa266b…` 的13条指数缺 20261016 行，按新检查口径会停止保存；回补凭据 `017bc5802f…`（基线 `9ee44d05…`，记录 `2950f01c…`）写入后，无网络的重新保存成功，24条轨道均具备目标日涨跌幅。884240.TI 目标日 -1.716% 与公开线自算值一致。
- 证据：`.generated/reader-annotations-oct17/browser-evidence.json`；缺口记录 `logs/errors/20261017-010200__2026-10-16__sector-index-target-day-gap.json`。
- 龙虎榜身份接线：入口七处调用点统一用 `_lhb_limit_status_for_bear` 传冻结名单，`markdown_report_html` 在入口只裁决一次并同时供表格单元格与图表载荷使用；`tests.test_daily_report_markdown_html`、`tests.test_daily_report_entry_html_output`、`tests.test_compact_bear_report` 共196项通过（含缺参／日期不符／结构非法七种形态不染色的用例）。
- 回放页按入口同一函数重渲染（`_render_daily_report_html_for_acceptance` ＋ 事实库支撑的 T0底色与创业板序列）：与旧页相比只有 `lhb_net_flow` 一项变化——`002552` 保留冻结身份“跌停”，`002531／301345／603893` 因不在冻结收盘名单里改为不标注，其余 8 个图表载荷、页面记录与补查凭据逐字节相同；图表柱色仍按净额正负取红绿，身份只落在表格单元格的 `signal-hot／signal-cold`。
- 注意：入口 `daily_report_entry_demo.py 2026-10-16 --replay` 当前在日报一致性检查停住（`monthly_rhythm_missing`、`empty_final_object_appendix_current_object_conflict`），与本轮改动无关，已由该次运行写入 `logs/errors/20261017-014205__2026-10-16.json`。


## 2026-10-21 板块阅读页独立清洗

- Python 3.14：`.generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_daily_cleanup tests.test_sector_daily_report tests.test_hypothesis_revision tests.test_tracked_sector_facts tests.test_sector_trend_tracking tests.test_compact_bear_report`，164项通过。
- 离线验证：使用 `snapshots/2026-10-20.json` 和已有 2026-10-20 完整版 HTML 写入 `reports/replay/2026-10-20_A股日报_板块清洗验证_replay.html`；不运行完整日报、不联网、不写旧研究记录。
- 保护核验：`verify_frozen.py` 对本轮开始时 `reports/**`、`snapshots/**`、`data/hypothesis-revision/**` 的1937份基线逐项 SHA-256 对照，变化0份。
- 浏览器：1440px 与390px检查默认折叠、证据展开、6张事实图、期货60/20日、图例显隐、窄屏表格和无页面横向溢出；画布均非空，错误0。
- 限定：上述证据只覆盖独立板块阅读页，不证明旧完整日报流水线或交易策略盈利。
