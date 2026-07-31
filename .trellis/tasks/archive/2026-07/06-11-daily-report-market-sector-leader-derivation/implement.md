# Implementation: 日报市场板块龙头推导重构

## Prerequisites

- 使用 `.generated/venv-py314/bin/python3.14` 运行所有 Python 命令。
- 先读 `prd.md`、`design.md` 和 `research/current-selection-workflow-evidence.md`。
- 修改前确认当前工作树里相关文件是否已有用户改动，不能回退无关变更。

## Ordered Checklist

- [x] I1: 更新 `tests/test_selection_workflow.py`，加入严格板块推导样本：T字板/一字板不能作为新仓候选入口，板块先铺后筛出的核心可以进入对照。
- [x] I2: 扩展 `scripts/report/selection_workflow.py`，新增 `derivation_contract = "sector_first_strict.v1"`、市场/资金/板块/市场情绪线/龙头结构化字段和严格候选入口规则。
- [x] I3: 增加对象分层测试和逻辑：新仓候选、持仓风险处理对象、手动问股观察对象分开流转。
- [x] I4: 增加线路冲突测试和逻辑：市场情绪线与板块主线冲突时按环境切换优先级，未分胜负时不输出100%。
- [x] I5: 增加关键数据缺失测试和逻辑：市场、板块发酵、市场情绪线、龙头、价格行为或账户执行关键数据缺失时，停止生成日报并列出缺失项。
- [x] I6: 更新 Mermaid 输出，确保节点展示市场、资金、板块、市场情绪线、龙头、价格行为、执行资格和最终结论。
- [x] I7: 更新 `tests/test_two_layer_decision_payload.py` 和 `scripts/report/two_layer_decision_payload.py`，让日报正文推导层展示新版链路和严格候选生命周期。
- [x] I8: 更新 `tests/test_front_page_v2_renderer.py` 和 `scripts/report/front_page_v2_renderer.py`，确保首页只消费 `selection_workflow.final`，旧对象不能残留。
- [x] I9: 更新 `tests/test_daily_report_markdown_html.py` 和 Bear HTML 相关模板/渲染，确保最终 Markdown 中的新推导链在 Bear 版 HTML 中可读。
- [x] I10: 运行窄测试，修正不符合 PRD 的旧断言。
- [x] I11: 选择一个 replay 日期生成日报，检查正文和 Bear HTML 的推导链是否同源。
- [x] I12: 新增冲突旧容器回归：只有 `candidate_pool` 中通过资金方向证明的对象可以取得新仓资格，`selected_position_candidate`、极致信念、跨线、Step2/Step3 和狙击手冲突对象只能成为过程证据。
- [x] I13: 收紧 `scripts/report/selection_workflow.py` 的候选归一和最终选择，取消显式旧对象的候选注入/优先权；特殊行情先形成可证明资金方向，再从方向派生候选。
- [x] I14: 重构 `scripts/report/runtime.py` 的 `final_target_resolution`，只从 `selection_workflow.final` 和账户上下文解释动作，停止独立生成观察/过程对象和反向改写候选选择。
- [x] I15: 改造首页、两层决策、狙击手、淘汰赛、候选质量和附录：存在工作流时只投影 `candidate_pool/final`，旧容器只显示过程证据。
- [x] I16: 增加接受检查，拒绝任何当前动作表面与 `selection_workflow.final` 的对象或仓位不一致，以及空最终对象被旧列表补回。
- [x] I17: 运行受影响模块测试和 2026-07-29 replay；核对明新旭腾只作过程证据、没有当前观察资格或未来价位，Markdown/Bear/JSON 同源，正式历史哈希不变。
- [x] I18: 执行两个独立提交前审计，分别覆盖代码行为和 replay/正式产物一致性；两项均因未在阶段节点返回证据而停止，不宣称独立审计通过，改用定向测试与关键出处抽查收口。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_front_page_v2_renderer tests.test_two_layer_decision_payload`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_sniper_target_derivation tests.test_elimination_tournament tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_daily_report_markdown_html`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <target-date> --replay`

## Risk And Rollback Points

- `selection_workflow` 字段会影响多个消费者，优先新增字段并保留旧字段。
- 日报正文和 Bear HTML 由 Markdown 串联，正文若没有新版推导，HTML 也不会有；不要在 HTML 里另写一套判断。
- 若历史 replay 缺少板块发酵数据，必须停止生成并列出缺失项，不回退到涨停入口，也不输出观察版日报。

## Review Checkpoints

- [x] 新旧样本都通过：旧错误样本不能成为新仓候选，板块先铺样本可以进入对照。
- [x] 缺失关键数据样本必须停止生成，并提示优先修复缺失数据。
- [x] Mermaid、日报正文、首页和 Bear HTML 最终对象一致。
- [x] 用户可见文字符合 `wiki/交易思想/日报术语契约.md`。
- [x] 冲突旧名单不能创建、覆盖或补齐当前候选和最终对象。
- [x] `final_target_resolution` 的新仓对象与仓位逐字段等于 `selection_workflow.final`，旧仓只进入旧仓动作解释。
- [x] 狙击手、Step2/Step3、淘汰赛、候选质量和附录在工作流存在时只读同一台账。

## Verification Evidence

- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow` passed, 16 tests.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight` passed, 32 tests.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_daily_report_markdown_html` passed, 130 tests.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router` passed, 38 tests.
- 2026-06-12: `scripts/daily_report_entry_demo.py 2026-06-12 --replay` could not verify because `snapshots/2026-06-12.json` is missing.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay` generated replay markdown and HTML successfully.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-05_A股日报_完整版_replay.md` passed.
- 2026-06-12: lint/typecheck commands were not available: `.generated/venv-py314/bin/python3.14 -m ruff --version` and `.generated/venv-py314/bin/python3.14 -m mypy --version` both reported missing modules.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_candidate_traces_can_be_built_from_selection_workflow tests.test_report_runtime.ReportRuntimeTest.test_runtime_inserts_single_final_target_solution_before_account_advice tests.test_report_runtime.ReportRuntimeTest.test_selection_workflow_zero_blocks_surface_candidate_even_with_front_observation tests.test_report_runtime.ReportRuntimeTest.test_selection_workflow_can_feed_two_layer_and_sniper_packets tests.test_report_runtime.ReportRuntimeTest.test_daily_judgment_front_panel_uses_anchor_primary_not_same_day_observation_records` passed, 5 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow` passed, 16 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_daily_report_markdown_html` passed, 130 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router` passed, 38 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay` generated replay markdown and HTML successfully; report consistency check passed; output table now renders `入口处理` and old legacy tomorrow-action wording is absent.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-05_A股日报_完整版_replay.md` passed after replay regeneration.
- 2026-06-13: lint/typecheck commands were still unavailable: `.generated/venv-py314/bin/python3.14 -m ruff --version` and `.generated/venv-py314/bin/python3.14 -m mypy --version` both reported missing modules.
- 2026-07-27: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime` passed, 344 tests. Six positive runtime fixtures now provide the complete local trend-sector proof and a sector-derived candidate; the 100% sample also provides broad market confirmation.
- 2026-07-27: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow tests.test_llm_wiki_context tests.test_llm_wiki_router` passed, 186 tests; `tests.test_llm_wiki_manifest` passed, 18 tests.
- 2026-07-27: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay` stopped before writing report artifacts because the historical snapshot did not satisfy current completeness checks for `ETF两市成交额趋势` and `价格带风格趋势`. No replay Markdown, HTML, or replay snapshot was created or overwritten.
- 2026-07-27: the pre-existing `reports/replay/2026-06-04_A股日报_完整版_replay.md` still shows `退潮`, `0%不参与`, and no execution object, with 上海石化 and 豫能控股 only as process observations. Its mtime remains 2026-06-08, so it is not fresh verification evidence. Running `report_acceptance_audit.py` on that old artifact reported ten pre-existing consistency findings; fresh replay acceptance remains unverified until the two target-date facts are available.
- 2026-07-27: added `test_unqualified_selected_pool_candidate_yields_to_qualified_sector_candidate`. A selected process candidate that is present in the pool but does not belong to the proven trend direction now yields to another qualified sector-derived candidate; a selected object absent from the pool still blocks fallback. `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow` passed, 48 tests.
- 2026-07-27: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime` passed, 344 tests; `tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_daily_report_markdown_html tests.test_daily_report_html_renderer` passed, 232 tests.
- 2026-07-27: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router tests.test_llm_wiki_manifest` passed, 157 tests; `tests.test_report_acceptance_audit` passed, 244 tests; the two sector-first preflight regressions passed.
- 2026-07-27: the full `tests.test_daily_report_entry_preflight` suite is not clean independently of this slice. It ends with 1 failure and 3 errors: `test_main_audits_full_report_with_chanlun_html_after_generation` observes two audit calls instead of one; `test_main_overwrite_official_keeps_frozen_mode_when_report_exists` stops on missing PostgreSQL index bars; `test_main_stops_market_language_write_when_saved_markdown_differs` and `test_main_switches_to_replay_when_existing_official_report_fails_audit` stop because the Wiki source trace is incomplete. This slice does not modify those paths.
- 2026-07-27: `py_compile` for the changed selection/runtime/Wiki modules and tests passed; `git diff --check` passed. `ruff` and `mypy` remain unavailable in the fixed Python 3.14 environment.
- 2026-07-27: replay verification was repeated for `2026-06-04` and again stopped on `ETF两市成交额趋势` and `价格带风格趋势`. The pre-existing full replay Markdown, HTML, and replay snapshot retained the same mtimes, sizes, and SHA-256 hashes before and after the run, so no historical artifact was overwritten.
- 2026-07-27: three independent pre-commit review agents were dispatched for selection logic, runtime propagation, and Wiki/spec alignment. All three exceeded the ten-minute project limit without returning review evidence and were stopped, so this dispatch is not counted as a passed independent review. A previously completed independent selection-pipeline audit had identified the selected-process-candidate early-return defect; the new regression and the runtime final-object tests now cover that finding.
- 2026-07-27: a second review attempt narrowed each agent to one function or one Wiki entry, but none returned evidence after five minutes; all three were stopped. No fresh independent-review pass is claimed.
- 2026-07-27: residual scope is explicit. Raw exploratory candidates are still produced before the final sector-proof filter, so this slice guarantees the final new-entry object follows the proven direction rather than physically reordering every upstream discovery stage. In addition, an explicitly supplied `local_trend_sector_proof` is not yet required to carry its own target-date provenance fields; historical proof ownership therefore remains a follow-up risk.
- 2026-07-30: fixed full/summary render input isolation in `build_report_outputs()`. The summary payload is copied before either renderer runs, so summary mutations cannot change the original full-render payload used by replay snapshot persistence. `tests.test_daily_report_render` passed 88 tests, including the new identity/initial-facts/no-write-back regression.
- 2026-07-30: all affected suites passed in three groups: 241 selection/front-page tests, 438 runtime/appendix/sniper tests, and 424 replay/audit/HTML tests. The remaining planned suites also passed: 66 preflight tests and 199 Markdown/Bear/Wiki tests; 1,456 tests passed in total.
- 2026-07-30: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-29 --replay` completed successfully in 168.60 seconds. Full Markdown, summary Markdown, Bear HTML, and replay snapshot all report 46 market-structure inputs; the replay snapshot contains 46 unique candidate codes.
- 2026-07-30: 明新旭腾(605068) remains one process candidate with `new_entry_qualified=false` and `front_observation_qualified=false`; final execution object, `watch_target`, and `process_target` are empty. Current-action wording and future observation prices are absent; `18.72` remains only in the frozen limit-up OHLC row.
- 2026-07-30: official 2026-07-29 artifacts remained unchanged: Markdown `fcc205060a0122c801282c8552248340d9eed78148ef185eb2789324f33b6a94`, HTML `2b951dce350262b100b48eeec7eda2942e86c4662a333359092204ca7b222b99`, snapshot `9bf449dfc3c76d9bc53bc8063ce7ecbeeb7eca1521edec4e72fc1a4a9f1b0513`.
- 2026-07-30: `report_acceptance_audit.py`, `py_compile` for all changed Python files, and `git diff --check` passed. `ruff` and `mypy` are not installed in the fixed Python 3.14 environment.
- 2026-07-31: the three new regressions for positive-final preservation, old-position front-page cleanup, and PostgreSQL copy normalization passed. The seven directly affected modules passed 670 tests; the remaining changed and planned modules passed 923 tests, for 1,593 passing tests in total.
- 2026-07-31: after removing the inherited MA template from non-final decision-ledger plans, `tests.test_decision_ledger` passed 91 tests. `py_compile` for every changed Python file and `git diff --check` passed. `ruff` and `mypy` remain unavailable in the fixed Python 3.14 environment.
- 2026-07-31: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-29 --replay` completed successfully in 60.87 seconds after the final code change; `report_acceptance_audit.py` passed against the new full replay Markdown.
- 2026-07-31: structured replay assertions passed: 20 identical `selection_workflow` copies; 46 candidates and 46 unique codes; 明新旭腾(605068) exactly once in the unified pool; 8 zero-position front-page/market snapshot conclusion copies; 12 tracking-memory copies with no current 605068 row; 298 structured 605068 rows with no positive position or participation qualification; 10 empty `final_target_resolution` copies; and a pure `no_trade` decision-ledger plan.
- 2026-07-31: official 2026-07-29 hashes remained unchanged: Markdown `fcc205060a0122c801282c8552248340d9eed78148ef185eb2789324f33b6a94`, HTML `2b951dce350262b100b48eeec7eda2942e86c4662a333359092204ca7b222b99`, snapshot `9bf449dfc3c76d9bc53bc8063ce7ecbeeb7eca1521edec4e72fc1a4a9f1b0513`.
- 2026-07-31: two fresh read-only pre-commit audits started in parallel at `12:17:27 CST`, covering code behavior and replay/formal-artifact consistency. Both were stopped at `12:28:29 CST` without returning stage evidence; effective finding count was 0 for each, neither is counted as an independent pass, and the parallel wall-clock was 11m02s. This exceeded the 10-minute audit budget by 1m02s; no replacement broad audit was dispatched, and main-thread targeted verification was used as required for evidence-free stopped audits.
