# Implementation: 日报生成前板块资金扩散审计落地

## Prerequisites

- Use `.generated/venv-py314/bin/python3.14` for all Python commands.
- Keep the change centered on the runtime/report generation path.
- Do not change the final-target selection algorithm in this task.

## Ordered Checklist

- [x] I1: Add a runtime builder for `sector_capital_preflight.v1` that can be
  stored in `data`, `execution_stage_context`, and `market_research_snapshot`.
- [x] I2: Add a renderer for the preflight payload that can emit the Mermaid
  audit block and per-layer elimination rows.
- [x] I3: Wire the payload into the report runtime so it is available before
  Markdown save and companion HTML save.
- [x] I4: Save a companion HTML artifact for the new audit block beside the dated
  report output without changing the final execution object.
- [x] I5: Extend the acceptance audit so it can recognize the new companion HTML
  and compare its final action with the Markdown / runtime final object.
- [x] I6: Add or update focused tests for payload shape, output order, companion
  HTML existence, and zero-position leak prevention.
- [x] I7: Run focused tests, replay verification, and `git diff --check`.
- [x] I8: Mark PRD complete and commit on the feature branch.

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_daily_report_entry_html_output tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html reports/replay/2026-06-12_板块资金扩散生成前复核.html`
- `git diff --check`

## Risk And Rollback Points

- Risk: preflight payload becomes a second decision system.
  - Mitigation: keep it observational and feed it from existing runtime truth.
- Risk: companion HTML drifts from the final object.
  - Mitigation: verify against `selection_workflow.final`,
    `final_target_resolution`, and `two_layer_decision_payload`.
- Risk: 0% reports leak process candidates as execution targets.
  - Mitigation: keep process evidence labeled as observation-only and assert the
    final action source in tests.
- Risk: replay/offical paths diverge.
  - Mitigation: derive companion paths from saved Markdown paths.

## Review Checkpoints

- After I1/I2: confirm the payload has a single final action and a Mermaid chain.
- After I3/I4: confirm report generation writes the companion artifact without
  changing the current target.
- After I5: confirm the audit can fail on companion/Markdown final-action drift.
- Before commit: run the narrow unit tests and diff check again.

## Verification Notes

- Passed:
  - `.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/elimination_tournament.py scripts/report/runtime.py scripts/report/report_acceptance_audit.py scripts/daily_report_entry_demo.py tests/test_elimination_tournament.py tests/test_report_runtime.py tests/test_report_acceptance_audit.py tests/test_daily_report_entry_html_output.py`
  - `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_elimination_tournament tests.test_report_acceptance_audit tests.test_daily_report_entry_html_output`
  - `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_daily_report_entry_html_output tests.test_report_acceptance_audit`
  - `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html reports/replay/2026-06-12_板块资金扩散生成前复核.html`
  - `git diff --check`
- Replay generation note:
  - `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay` stopped because `snapshots/2026-06-12.json` is missing. Existing replay Markdown and the sector-capital companion HTML pass acceptance audit, but fresh replay regeneration requires the official snapshot to be restored first.
- Final verification note:
  - `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_daily_report_render tests.test_daily_report_entry_html_output tests.test_report_acceptance_audit tests.test_elimination_tournament` passed with `Ran 474 tests ... OK`.
  - Existing `reports/replay/2026-06-12_板块资金扩散生成前复核.html` visibly contains `相关决策列表` and `白痴指数复核表`.
