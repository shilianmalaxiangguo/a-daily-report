# Verification

Use this when the request needs evidence. Keep checks focused; users should not have to remember commands.

## Practical Commands

- Runtime preference: use Python 3.14-first when dependencies are available; do not silently fall back to 3.11. If `/opt/homebrew/bin/python3.14` lacks packages that the populated `venv/bin/python` has, say so before choosing the venv for the run.
- Replay generation: `venv/bin/python scripts/daily_report_entry_demo.py 2026-04-24 --replay`
- Current replay audit: `venv/bin/python scripts/report/report_acceptance_audit.py reports/replay/2026-04-24_A股日报_完整版_replay.md`
- Focused docs test: `venv/bin/python -m unittest tests.test_daily_report_skill_docs`
- Acceptance smoke: `venv/bin/python -m unittest tests.test_report_acceptance_audit tests.test_entry_plan_node_runtime`
- Focused unittest commands usually take the form: `venv/bin/python -m unittest tests.test_report_acceptance_audit`
- Tushare gateway smoke: `PYTHONPATH=scripts venv/bin/python -c "from market_data.tushare_client import TUSHARE_HTTP_URL; print(TUSHARE_HTTP_URL)"` should print `http://121.40.135.59:8010/`; the client factory is `create_tushare_pro_api`.
- Tushare-first data-source regression: `PYTHONPATH=scripts venv/bin/python -m unittest tests.test_tushare_input_runtime tests.test_market_activity_request tests.test_new_stock_calendar_request`
- Diff hygiene: `git diff --check`

## Verification Rules

- For report-output defects, passing unit tests is not enough if replay markdown still reads wrong.
- For skill docs, verify the router and safety rules with lightweight tests before claiming the onboarding contract is ready.
- For trading/report behavior, prefer fresh replay or audit evidence over assumptions from older memory.
