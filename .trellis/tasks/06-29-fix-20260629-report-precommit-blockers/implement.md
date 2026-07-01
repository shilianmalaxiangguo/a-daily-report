# Implementation: 修复 2026-06-29 日报提交前阻断项

## Prerequisites

- Active task is `.trellis/tasks/06-29-fix-20260629-report-precommit-blockers`.
- Python commands use `.generated/venv-py314/bin/python3.14`.
- No subagents in implementation/check phase.
- Avoid unrelated dirty files.

## Ordered Checklist

- [x] I1: Add focused failing tests for sector fund-flow alias normalization and visible all-zero audit failures.
- [x] I2: Patch sector fund-flow normalization/rendering so `net_amount` / `net_inflow_yi` / `change_pct` rows render as real values.
- [x] I3: Add focused failing tests for Markdown Ta/Tb/Tc timeline parity and known old-position wording.
- [x] I4: Patch existing report rendering/runtime functions so Markdown gets a readable Ta/Tb/Tc table and account wording uses 太极实业 when old-path data exists.
- [x] I5: Add or adjust acceptance-audit checks for Markdown/HTML timeline parity, old-holding conflicts, and excessive official unresolved facts.
- [x] I6: Run targeted unit tests and fix regressions.
- [x] I7: Regenerate 2026-06-29 official report artifacts.
- [x] I8: Run report acceptance audit and static `rg` checks on the regenerated Markdown/HTML.
- [x] I9: Update PRD status and record verification evidence.

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_request tests.test_market_activity_domain_report_sections tests.test_daily_report_markdown_html tests.test_report_acceptance_audit tests.test_front_page_v2_renderer`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-29`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-29_A股日报_完整版.md --companion-html reports/2026-06-29_A股日报_完整版.html`
- `rg -n "position-timeline|2026-06-28|2026-06-30|太极实业|深科技|持仓未输入|0.00亿 \\| \\+0.00%|待补事实" reports/2026-06-29_A股日报_完整版.md reports/2026-06-29_A股日报_完整版.html`
- `git diff --check`

## Risk And Rollback Points

- Sector-flow alias changes may affect replay and historical snapshots. Roll back I2 if tests show old snapshot shapes break.
- Timeline rendering touches user-facing output. Roll back I4 if unrelated report dates lose empty-state clarity.
- Acceptance audit may become too strict. Keep checks targeted to official report surfaces and clear visible defects.

## Review Checkpoints

- After I2: fund-flow unit tests pass.
- After I4: Markdown and HTML both contain Ta/Tb/Tc with correct 2026-06-29 facts.
- After I5: acceptance audit fails on synthetic bad samples and passes regenerated official report.
- After I8: report artifacts match user-visible expectations.

## Completion Evidence

- Focused runtime regression after final account-panel patch passed:
  `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_positive_final_action_relabels_inferred_old_path_account_panel tests.test_report_runtime.ReportRuntimeTest.test_runtime_keeps_inferred_previous_report_path_from_blocking_tomorrow_target tests.test_report_runtime.ReportRuntimeTest.test_positive_final_action_keeps_independent_etf_holding_from_old_position_appendix tests.test_pk_decision_stage.PkDecisionStageTest.test_candidate_quality_scorecard_keeps_inferred_old_path_separate_from_empty_position`
- Focused report suite passed: 456 tests.
- Official 2026-06-29 artifacts regenerated with `--overwrite-official`; output saved under `reports/`.
- `report_acceptance_audit` passed on the regenerated Markdown plus companion HTML.
- Static negative check found no `无持仓负担`, `无旧仓`, or `持仓未输入` in the regenerated Markdown/HTML.
- Static visible assertions passed for Ta/Tb/Tc timeline dates, Ta=太极实业, Tb=深科技, Tc=没有Tc+0, Bear HTML timeline, and T-015/T-017/T-018/T-025 table presence/content.
- `git diff --check` passed.
- Subagent audit found the appendix account-panel contradiction before the final patch; final checks confirm it is gone.
