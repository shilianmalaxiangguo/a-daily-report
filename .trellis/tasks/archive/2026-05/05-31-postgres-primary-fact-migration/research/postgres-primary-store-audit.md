# PostgreSQL Primary Store Audit

## Scope

This audit covers backend daily-report runtime facts only. `snap-ui` and frontend static export paths are intentionally excluded by user instruction.

## Existing PostgreSQL Coverage

Current `develop` already contains PostgreSQL support for:

* cycle calendar and cycle periods
* mainline daily and mainline turnover
* sector fund flow and sector attack evidence
* sector diffusion score and diffusion components
* sector competition
* market capacity evolution
* zhongshu mainline records
* daily observation pool items and lifecycle
* leader memory items
* tracking memory daily status
* extreme-conviction cases, mentions, hypotheses, planned participation, participation review, trend fate, and cycle acceptance review

Core files:

* `scripts/storage/database_service.py`
* `scripts/storage/postgres_daily_fact_db.py`
* `scripts/report/decision_ledger.py`
* `scripts/research/tracking_memory_runtime.py`

## Remaining JSON Primary Stores

These JSON paths still hold decision-affecting or cross-day state and should move behind `DatabaseService` / `PostgresDailyFactDb`:

* `scripts/report/strategy_tracking_store.py`
  * `scripts/data/strategy_performance.json`
  * `scripts/data/strategy_performance_replay.json`
  * `scripts/data/factor_snapshots/<date>.json`
* `scripts/risk/a_kill_blacklist_store.py`
  * `data/a_kill_blacklist.json`
* `scripts/report/candidate_trace_artifacts.py`
  * `data/candidate-traces/<date>.json`
* `scripts/report/runtime.py`
  * direct fallback read from `data/decision-ledger/index.json`

## JSON Allowed To Remain

JSON can remain when it is not the primary decision store:

* frozen snapshots: `snapshots/<date>.json`
* replay snapshots: `snapshots/replay/<date>_replay.json`
* run/error audit logs: `reports/runs/*/*.json`, `logs/errors/*.json`
* LLM, market-data, and temporary cache files

## Implementation Notes

* Extend existing storage facade methods instead of adding a separate storage layer.
* Preserve existing public function APIs where possible, using PostgreSQL when configured and JSON only as legacy fallback when PostgreSQL is not configured.
* For PostgreSQL-backed execution, avoid silent JSON fallback for primary facts. Return or raise visible errors so report generation can show that primary facts were not persisted.
* Keep all Python commands on `.generated/venv-py314/bin/python3.14`.
* Do not edit `snap-ui` files or frontend static export paths in this task.

## Post-Commit Audit: 2026-05-31

Commit audited: `ee22fe56 feat: migrate remaining daily report facts to postgres`.

Verification evidence:

* `git diff --cached --check`
* `.generated/venv-py314/bin/python3.14 -m compileall ...`
* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_strategy_tracking_store tests.test_a_kill_blacklist_store tests.test_candidate_trace_artifacts tests.test_report_runtime tests.test_postgres_daily_fact_db tests.test_tracking_memory_runtime tests.test_decision_ledger`
* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight tests.test_report_runtime`
* `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-05-29 --replay`
* `PYTHONPATH=scripts .generated/venv-py314/bin/python3.14 -m report.report_acceptance_audit reports/replay/2026-05-29_A股日报_完整版_replay.md`

Migrated or protected former JSON primary stores:

* `scripts/report/strategy_tracking_store.py`
  * PostgreSQL configured: `load_strategy_performance_ledger`, `save_strategy_performance_ledger`, and `save_factor_snapshot` use `DatabaseService`.
  * PostgreSQL configured but service/reader/writer unavailable: raise visible errors instead of reading or writing the JSON ledger/factor files.
  * JSON paths remain only inside legacy bodies for non-PostgreSQL compatibility.
* `scripts/risk/a_kill_blacklist_store.py`
  * PostgreSQL configured: active cooling reads and replacement writes use `DatabaseService`.
  * JSON path remains only for non-PostgreSQL compatibility.
* `scripts/report/candidate_trace_artifacts.py`
  * PostgreSQL configured: trace artifacts are written with `replace_candidate_trace_artifact`.
  * JSON path remains only for non-PostgreSQL compatibility.
* `scripts/research/tracking_memory_runtime.py`
  * PostgreSQL configured: load/save functions are taken from `DatabaseService`.
  * Missing PostgreSQL service or reader/writer is visible and does not fall back to `data/tracking_memory.json`.
* `scripts/report/decision_ledger.py`
  * PostgreSQL configured: service selection failure returns `fact_db_sync.status=failed` without creating `data/decision-ledger/*.json`.
  * PostgreSQL service selected but structured write fails: returns `fact_db_sync.status=failed` before JSON archive writes.
  * JSON archive writes remain available when explicitly requested and when PostgreSQL-only runtime mode is not set.
* `scripts/report/runtime.py`
  * PostgreSQL configured: decision ledger tracking reads through `DatabaseService`.
  * PostgreSQL read failures are surfaced instead of hidden behind `data/decision-ledger/index.json`.

Remaining JSON usage classification from `git grep` on `HEAD`:

* Allowed replay/archive/log/cache/export:
  * `snapshots/*.json`, `snapshots/replay/*.json`
  * `reports/runs/*/*.json`, `logs/errors/*.json`
  * LLM, reasoning-decision, minute-price, and history cache files
  * cloud/export/report publishing payloads
* Explicitly excluded:
  * `snap-ui` publishers and frontend static artifacts.
* Legacy compatibility:
  * JSON read/write bodies in migrated stores are retained only when PostgreSQL is not configured.
  * The retired local database compatibility layer has been removed from current runtime code and tests.

Residual risk:

* Real PostgreSQL execution was not verified locally because `A_DAILY_REPORT_DATABASE_URL` and `DATABASE_URL` were unset and `psql` was unavailable.
* The current proof is unit-level PostgreSQL service behavior plus replay/report verification on the local non-PostgreSQL environment.
