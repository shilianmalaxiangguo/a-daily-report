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
