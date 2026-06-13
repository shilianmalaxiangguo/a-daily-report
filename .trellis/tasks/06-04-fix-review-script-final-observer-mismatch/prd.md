# fix: Review Script And Final Observer Mismatch

## Goal

Make the process-evidence review tables use the same resolved target identity as the front page and final target context, and stop rendering repeated `no_trade` placeholder rows as if they were meaningful fixed-window review rows.

## What I Already Know

* The user saw T-109 `重点观察复核脚本` rows where the first cell was `no_trade`, the position was `0%`, and many columns repeated placeholder observation-only text.
* The user saw T-116 `今日总决策面板` show `观察对象 上海石化(600688)` after prior report logic had been talking about `豫能控股(001896)`.
* Existing tests show report runtime intentionally aligns appendix `观察优先锚点` from the front-page `观察锚`; this is correct only when the front-page anchor itself is the resolved current target.
* `build_daily_quality_decision_panel()` renders `主买对象` / `补位对象`; sanitized runtime text may rename these fields when they are process evidence.
* `candidate_quality_scorecard._build_panel_fields()` currently takes `best_stock` and `watch_anchor`, so stale or fallback candidates can leak into T-116 if the upstream context is not resolved consistently.

## In Scope

* Trace and fix the current-context priority for T-116 target identity.
* Ensure current runtime-selected target / final target resolution wins over same-day stale ledger fallback.
* Ensure observation-only `no_trade` rows do not render as repeated actionable review script rows.
* Keep useful observation evidence, but compact it to one coherent row per actual observed stock.
* Add focused tests for report runtime/front-page/candidate-quality output.

## Out of Scope

* Rewriting candidate selection.
* Changing anchor-reversal scoring rules.
* Rebuilding historical reports.
* Removing all process evidence tables.

## Non-goals

* Do not hide observation-only rows if they are the real final observation target.
* Do not promote observation-only rows into participation.
* Do not use older same-day ledger records to refill a current target when the runtime context already has a resolved observation target.

## Requirements

* T-116 must derive the visible observation object from the same resolved source used by front page and final action:
  * `final_target_resolution.watch_target` when present;
  * otherwise `selected_position_candidate` / runtime-selected current candidate;
  * ledger records only when current runtime context has no current candidate rows.
* T-109 must filter or compact repeated placeholder `no_trade` rows. Explorer identified the direct T-109 renderer as `scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py::build_candidate_selection_conviction_list_node()`, which currently iterates the full `extreme_conviction_list`.
* A row with `participation_window_type == "no_trade"` can appear only as observation evidence for a real stock, not as repeated generic script filler.
* Stale positive execution wording must not survive on no-participation rows.
* Report sanitizer must not rewrite an appendix anchor to a wrong front-page anchor; it should align only after the front-page anchor has been resolved from current context.

## Acceptance Criteria

* [ ] A focused report-runtime test with final target `豫能控股` and stale fallback `上海石化` renders `豫能控股` in T-116/process evidence.
* [ ] A focused test with multiple no-participation placeholder candidates does not render repeated `no_trade` rows in `重点观察复核脚本`.
* [ ] Existing tests that align appendix anchor from the front page still pass when the front-page anchor is valid.
* [ ] Zero-participation rows remain observation-only and do not regain board/reseal or new-entry wording.

## Definition of Done

* Focused tests pass with Python 3.14.
* The implementation changes only final-target resolution, review-script rendering, or report sanitization needed by this defect.
* The parent task can cite the test output as evidence for T-109 and T-116.

## Verification

* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime`
* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer`
* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_renderer`

## Technical Approach

* Likely files:
  * `scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py`
  * `scripts/domains/execution_chain/pk_decision_nodes/candidate_quality_scorecard.py`
  * `scripts/selection/candidate_quality_contracts.py`
  * `scripts/report/front_page_v2_renderer.py`
  * `scripts/report/runtime.py`
  * `tests/test_candidate_selection_stage.py` for the T-109 no-trade script boundary
  * `tests/test_action_plan_renderer.py` for T-116 panel rendering boundaries
* Implementation subagent must first inspect current dirty changes in these files and preserve them.
