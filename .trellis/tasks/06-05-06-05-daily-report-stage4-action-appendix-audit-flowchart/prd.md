# daily report stage 4 action appendix audit flowchart

## Goal

Close the report with a next-day action checklist, migrate supporting evidence to appendix without losing conclusions, strengthen acceptance audit against final-object conflicts, regenerate replay output, and regenerate the Mermaid flowchart.

## Parent Task

Parent PRD: `.trellis/tasks/06-05-daily-report-full-rewrite/prd.md`

## In Scope

* Move or render `next_day_action` as the closing recap:
  * position stance,
  * primary object,
  * execution or observation conditions,
  * no-participation conditions,
  * old-position handling,
  * review points.
* Keep appendix evidence available while preventing it from competing with the final answer.
* Update report acceptance audit so downstream sections cannot introduce a different final object.
* Regenerate `2026-06-04 --replay` after implementation.
* Regenerate the Mermaid HTML flowchart at `reports/flowcharts/当前日报选股到最终标的流转图.html`.

## Out of Scope

* Creating new market/fund/candidate logic from scratch.
* Manual edits to replay markdown as the fix.
* Replacing Mermaid.js or redesigning the browser UI beyond the flowchart content.

## Non-goals

* Do not remove useful evidence tables without a named replacement in the main body or appendix.
* Do not allow technical audit/source sections to appear before the action and derivation flow.
* Do not let the flowchart describe old logic after code changes.

## Done Definition

* The report ends with a clear next-day action checklist.
* Appendix headings are visibly supporting evidence where needed.
* Acceptance audit catches conflicting final-object identity between opening, final object, action plan, and process graph.
* Replay generation and acceptance audit pass for the selected sample.
* Mermaid HTML flowchart is regenerated and viewable in the in-app browser.

## Likely Files

Execution agents should inspect before editing:

* `scripts/report/report_acceptance_audit.py`
* `scripts/report/two_layer_decision_payload.py`
* `scripts/report/front_page_v2_renderer.py`
* `scripts/report/runtime.py`
* `scripts/daily_report_entry_demo.py`
* `reports/flowcharts/当前日报选股到最终标的流转图.html`
* flowchart generation scripts discovered by `rg Mermaid|mermaid|flowchart`
* `tests/test_report_acceptance_audit.py`
* `tests/test_report_runtime.py`

## Acceptance Criteria

* [ ] `next_day_action` appears after detailed derivation and before appendix-only diagnostics when applicable.
* [ ] Appendix/process sections cannot render a second final object.
* [ ] Acceptance audit fails when final object identity conflicts.
* [ ] Replay command uses `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay`.
* [ ] Flowchart HTML uses Chinese node labels and describes the new market-to-action pipeline.

## Implementation Notes

Use the section migration map from the parent PRD. Keep evidence; reduce duplicate conclusions.
