# Verification

Use this when the request needs evidence. Keep checks focused; users should not have to remember commands.

## Practical Commands

- Replay generation: `venv/bin/python scripts/daily_report_entry_demo.py 2026-04-24 --replay`
- Current replay audit: `venv/bin/python scripts/report/report_acceptance_audit.py reports/replay/2026-04-24_A股日报_完整版_replay.md`
- Focused docs test: `venv/bin/python -m unittest tests.test_daily_report_skill_docs`
- Acceptance smoke: `venv/bin/python -m unittest tests.test_report_acceptance_audit tests.test_entry_plan_node_runtime`
- Focused unittest commands usually take the form: `venv/bin/python -m unittest tests.test_report_acceptance_audit`
- Diff hygiene: `git diff --check`

## Verification Rules

- For report-output defects, passing unit tests is not enough if replay markdown still reads wrong.
- For skill docs, verify the router and safety rules with lightweight tests before claiming the onboarding contract is ready.
- For trading/report behavior, prefer fresh replay or audit evidence over assumptions from older memory.
