# Verification

Default to desktop report checks. Do not require mobile-width adaptation or mobile acceptance unless the user explicitly requests it.

Use this when the request needs evidence. Keep checks focused; users should not have to remember commands.

## Practical Commands

- Runtime: use `.generated/venv-py314/bin/python3.14`; do not fall back to another interpreter.
- Replay generation: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-04-24 --replay`
- Current replay audit: `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-04-24_A股日报_完整版_replay.md`
- Focused docs test: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_skill_docs`
- Acceptance smoke: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit tests.test_entry_plan_node_runtime`
- Focused unittest commands usually take the form: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit`
- Tushare proxy smoke: `PYTHONPATH=scripts .generated/venv-py314/bin/python3.14 -c "from market_data.tushare_client import fetch_demo_frames; a,b=fetch_demo_frames(); print(len(a), len(b))"` should return nonzero row counts; the client factory is `create_tushare_pro_api` and reads `TUSHARE_TOKEN` / `TUSHARE_HTTP_URL` from `.env`.
- Tushare-first data-source regression: `PYTHONPATH=scripts .generated/venv-py314/bin/python3.14 -m unittest tests.test_tushare_input_runtime tests.test_market_activity_request tests.test_new_stock_calendar_request`
- Diff hygiene: `git diff --check`

## Verification Rules

- For report-output defects, passing unit tests is not enough if replay markdown still reads wrong.
- For skill docs, verify the router and safety rules with lightweight tests before claiming the onboarding contract is ready.
- For trading/report behavior, prefer fresh replay or audit evidence over assumptions from older memory.
