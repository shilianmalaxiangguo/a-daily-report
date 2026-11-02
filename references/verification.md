# Verification

Use .generated/venv-py314/bin/python3.14 for every Python command. The current Wiki and small-cap v0.3 define current behavior. Tests verify code and factual boundaries, never future profitability.

## Current strategy and entry

    .generated/venv-py314/bin/python3.14 -m unittest tests.test_current_strategy_scope tests.test_current_entry_isolation tests.test_small_cap_plan tests.test_market_reading_entry tests.test_daily_report_skill_docs tests.test_daily_report_wechat_draft_skill tests.test_run_log_runtime

- Inspect actual current CLI imports in an isolated process. Neither the historical account/selection chain nor the external WorkBuddy quant system may load for the current command.
- The five-name plus three-backup plan must work independently of old market-regime advice. Missing turnover or financials remain data gaps, never a fabricated empty account.
- Commission is 0.01% with no minimum. Transfer fee and sell-side stamp duty are separate. A 1,000-yuan purchase pays 0.10 yuan commission.
- Daily whole-lot output must say single-period simulation and disclose missing previous cash, holdings and original buy prices. It must not claim actual fills or continuous account identity.
- The only current evaluation window is 2025-02-28 through 2026-10-29. Retired methods and tournament observations receive no invented performance.
- Use desktop 1440px for visible-output checks. No phone layouts or phone-window acceptance are maintained.
- Current chart code reads dedicated factual JavaScript, not the historical full-report template. CFFEX projection must not import the retired renderer or Wiki chain. Historical additions load only validators for present fields; date and fingerprint checks still apply.

## Replay and factual regression

For generated-output changes or report requests, run the affected suites and one selected frozen snapshot offline:

    .generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_daily_report tests.test_sector_reading_restoration tests.test_sector_choice tests.test_daily_report_entry_preflight tests.test_compact_bear_report
    .generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-20 --replay

- Replay reads exactly the selected official or replay snapshot. No network refresh, old account inheritance, or old full-report rebuild. Missing a selected source must fail.
- Capture official-file hashes before and after: target official reports/snapshot, original hypothesis/trend/chart-fact records. Experiments write replay outputs and isolated diagnostics.
- Validate all original facts before trimming display or historical memory. Missing values stay null; sample, units, dates, source identities and recorded retrieval times remain truthful. Rebuild prior comparisons against their complete original source before discarding large historical inputs.
- Compare chart JSON, source fingerprints, full rows and numeric results. Preserve input immutability and repeated replay identity. A nonempty canvas alone does not establish correct data or tradability.
- Check saved HTML exclusions, navigation and factual gaps. Run actual browser checks only when the current change is explicitly about layout or interaction; use desktop and inspect the changed saved page.
- Facts include selected-sector history, same-window member/sector/market comparison, complete Top30, correctly dated Top50, breadth, new highs, seal amounts and CFFEX facts when available. Preserve their individual missing reasons; do not create empty charts or move another day's value into a gap.

## Wiki and historical compatibility

Pure Wiki/contract changes require focused document tests, link checks and archive-hash checks rather than collection or report generation. Read wiki/README.md and the relevant current page first. User-confirmed facts, opinions, simulations and actual trades remain distinct.

--output-mode full only locates an existing historical original; it does not run the old full chain. short is stopped. Historical tests must not restore retired rules to the current entry.

The former LLM Wiki suites are named tests.legacy_llm_wiki_*. They preserve archived knowledge-graph behavior, not current strategy acceptance. See [historical test notes](../tests/LEGACY_TESTS.md). Old decision-board/daily-extras algorithm tests are historical compatibility checks; current exclusions live in tests.test_current_strategy_scope. Do not claim the whole repository test suite passes from focused results.

Fifty-one retired execution/account/full-render suites are named tests.legacy_test_*. Their source-to-archive mapping and hashes are preserved in the [migration manifest](../docs/archive/daily-report-framework/2026-11-02/retired-strategy-tests-manifest.json). They are not default current acceptance. Neither bare discovery nor a historical suite may reinstate old strategy or phone requirements.

Explicit Alpha/Beta research regression (does not activate daily advice):

    .generated/venv-py314/bin/python3.14 -m unittest tests.test_market_alpha_beta tests.test_decision_board tests.test_daily_extras

Task-specific historical checklists moved intact to [verification history](../docs/archive/daily-report-framework/2026-11-02/verification-task-history.md). They are evidence of dated tasks, not a current execution queue.

## Delivery evidence

1. State behavior, boundaries and relevant checks; identify target/source/output dates only for generated reports.
2. Run the narrowest meaningful tests, syntax and git diff --check.
3. Complete independent review, correct concrete findings and verify again when needed.
4. Check saved output and official-file hashes for historical replay. Distinguish fresh failures, old incompatible expectations and unavailable sources.
5. Report what passed and remaining limits accurately. Never bundle unrelated working-tree changes.

For a generated-report response include the complete request wall clock under 生成耗时回顾. A successful run's duration is separate and requires an actual run log; missing phase times remain 未细分耗时.
