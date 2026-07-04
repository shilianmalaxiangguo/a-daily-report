# 日报结构优化验证记录

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

结果：687 个测试通过。

本轮动作优先和 Bear HTML 改动后的复跑结果：

```bash
.generated/venv-py314/bin/python3.14 -m unittest -f \
  tests.test_report_runtime \
  tests.test_daily_report_markdown_html \
  tests.test_daily_report_render \
  tests.test_daily_report_entry_html_output \
  tests.test_report_acceptance_audit
```

结果：576 个测试通过。

## 格式检查

```bash
git diff --check
```

结果：通过。

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
