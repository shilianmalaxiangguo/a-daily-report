# 2026-06-10 最终对象身份一致性补丁

## Goal

修复日报前台中“最终观察对象”和 T-006 今日判断对象来源不一致的问题。2026-06-10 这类场景里，中船特气可以作为最终观察对象，双星新材可以作为过程候选或待验证样本，但不能绕过最终解析出现在“核心候选判断”里。

## In Scope

- 约束 T-006 今日判断里的核心候选来源。
- 当最终解析已经给出“等待 / 旧仓优先 / 仅观察”结果时，不再从 `best_stock`、候选池或同日记录回填核心候选。
- 只有最终解析给出新对象或可用替代对象时，T-006 才显示核心候选。
- 补一个 2026-06-10 形态的回归测试。

## Out of Scope

- 不重写候选池生成、评分、排序和最终解析算法。
- 不改 Bear HTML、Mermaid HTML 或 replay 回补。
- 不处理 P1 的 hook 管线、结构化 HTML、历史来源日期等后续项。

## Non-goals

- 不把过程候选隐藏掉；过程候选仍可进入附录和推导链。
- 不把观察对象包装成明日新增参与对象。
- 不为了这次补丁引入新的候选抽象层。

## Contract

1. T-006 的“核心候选判断”必须先看最终解析结果。
2. 最终解析的 `capital_priority_decision.capital_priority` 为 `new_entry`、`new_entry_after_old_exit` 或 `tradable_proxy` 时，T-006 可显示对应的新对象或可用替代对象。
3. 最终解析为 `wait`、旧仓优先，或只有 `watch_target` 时，T-006 核心候选显示 `待补事实`。
4. `best_stock`、`watch_anchor`、极度看好名单和同日记录只能作为无最终解析时的兜底；有最终解析时不能覆盖它。
5. 附录、过程证据、候选观察样本可以继续展示双星新材，但必须保留其过程身份。

## Verification

- 运行：
  `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_daily_judgment_front_panel_ignores_best_stock_when_final_result_waits`
- 运行：
  `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_daily_judgment_front_panel_uses_anchor_primary_not_same_day_observation_records tests.test_decision_statistics.DecisionStatisticsTest.test_daily_panel_keeps_observation_candidates_out_of_core_judgment`
- 如果需要重新生成 2026-06-10 日报，再运行日报生成命令和一致性检查。
