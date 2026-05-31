# PostgreSQL Primary Fact Migration

## Goal

Move all runtime facts that affect daily report judgment, cross-day memory, cycle reading, sector comparison, and observation pools to PostgreSQL as the primary store. JSON may remain only as replay/archive/export/cache output, not as the source used for current decisions.

## What I already know

* The user has abandoned the D1 plan and wants PostgreSQL, not JSON, to hold structured daily report facts.
* The user specifically called out the drift between the leader memory pool and the tomorrow high-conviction 25-day pool as evidence that JSON-backed storage is not trustworthy enough.
* The user wants the cycle concept stored directly in the database instead of cross-reading daily JSON files.
* Existing local `develop` already has PostgreSQL fact-store commits:
  * `1089b6c0 feat: add postgres daily report fact store`
  * `e990a185 fix: persist sector cycle facts to postgres`
* Current PostgreSQL coverage already includes cycle days/periods, mainline daily/turnover, sector fund flow, sector attack evidence, sector diffusion score/components, sector competition, market capacity evolution, zhongshu mainline records, observation pool items/lifecycle, leader memory, tracking memory, and extreme-conviction ledger tables.
* Real PostgreSQL local verification has not been completed because `A_DAILY_REPORT_DATABASE_URL` and `DATABASE_URL` were unset and `psql` was not available in the prior environment check.

## Assumptions (temporary)

* SQLite can remain as a compatibility/test fallback, but production-like local runs should use PostgreSQL when configured.
* JSON snapshots under `snapshots/` and `snapshots/replay/` should remain valid replay/archive artifacts.

## Open Questions

* None currently. User explicitly excluded `snap-ui` from this task.

## Requirements

* PostgreSQL is the primary store for all runtime facts that influence current daily report decisions.
* JSON files are not used as the primary cross-day source for:
  * leader memory pool
  * tracking memory state
  * tomorrow high-conviction 25-day pool
  * daily report observation pools
  * cycle calendar / cycle interpretation / zhongshu-mainline reading
  * sector diffusion / sector competition / market capacity evolution
  * A-kill cooling records
  * strategy performance ledger and factor snapshots, if used by later decisions
  * candidate trace artifacts, if used by later explanation or filtering
* JSON may remain for replay snapshots, frozen archives, run logs, error logs, and caches.
* When PostgreSQL is configured, runtime reads should prefer PostgreSQL and should not silently fall back to JSON for primary decision data.
* Failures to write primary PostgreSQL facts should be visible in report/runtime output and tests.
* `snap-ui` and all related static frontend JSON are not part of this task.

## Acceptance Criteria

* [ ] A generated replay report still passes the daily report consistency check.
* [ ] Unit tests prove PostgreSQL-backed decision ledger reads do not rely on `data/decision-ledger/index.json`.
* [ ] Unit tests prove tracking memory uses PostgreSQL when configured.
* [ ] Unit tests cover PostgreSQL storage for A-kill cooling records.
* [ ] Unit tests cover PostgreSQL storage for strategy performance ledger and factor snapshots.
* [ ] Unit tests cover PostgreSQL storage for candidate trace artifacts.
* [ ] A code audit command or test proves remaining JSON writes are archive/export/cache only, or explicitly excluded.
* [ ] PostgreSQL environment setup and verification steps are documented.
* [ ] The implementation plan does not include `snap-ui` files, frontend static export changes, or frontend data loading changes.

## Definition of Done

* Tests added or updated for every migrated store.
* Narrow Python unittest suite passes using `.generated/venv-py314/bin/python3.14`.
* Replay generation for a representative date passes using `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <date> --replay`.
* If local PostgreSQL is unavailable, the exact missing dependency and residual risk are reported.
* Documentation records which JSON paths are allowed to remain and why.

## Out of Scope (explicit)

* Deleting historical JSON snapshot archives.
* Any `snap-ui` or frontend data work.
* Replacing every cache JSON that is purely performance-related and not used as cross-day truth.
* Reworking unrelated report rendering, terminology, or trading logic.
* Reverting unrelated dirty working-tree changes.

## Decision (ADR-lite)

**Context**: The original audit included frontend static JSON as an export category, but the user clarified that this migration must not consider `snap-ui` at all.

**Decision**: The MVP is limited to daily-report runtime facts that affect decisions, cross-day memory, cycle reading, sector comparison, observation pools, A-kill cooling, strategy performance, factor snapshots, and candidate traces. `snap-ui` paths and frontend static exports are excluded. The implementation should extend the existing `DatabaseService` and `PostgresDailyFactDb` pattern rather than introducing a new storage abstraction.

**Consequences**: The implementation can stay focused on backend/report storage and tests. Frontend artifacts may continue to exist, but this task will not modify, validate, or redesign them.

## Technical Approach

Data flow:

`daily report runtime inputs -> normalized domain rows -> DatabaseService facade -> PostgreSQL tables -> service readback -> report/runtime consumers`

Implementation expectations:

* Add focused PostgreSQL tables/methods for remaining decision-affecting stores instead of keeping opaque JSON files as the primary store.
* Preserve existing function-level APIs where possible so report logic does not need to know whether the backing store is PostgreSQL or legacy JSON.
* For replay/archive paths, keep JSON behavior only when it is explicitly a frozen snapshot or diagnostic artifact.
* When PostgreSQL is configured and write/read fails for primary decision facts, surface the failure rather than silently reading old JSON.
* Keep SQLite compatibility only for existing tests and fallback paths; do not add new SQLite-first behavior for migrated stores.

## Technical Notes

* Primary PostgreSQL facade: `scripts/storage/database_service.py`.
* PostgreSQL implementation: `scripts/storage/postgres_daily_fact_db.py`.
* Existing decision ledger JSON archive path: `data/decision-ledger/<date>.json` and `data/decision-ledger/index.json`.
* Existing tracking memory fallback: `data/tracking_memory.json`.
* Remaining JSON primary stores found so far:
  * `scripts/report/strategy_tracking_store.py` writes `scripts/data/strategy_performance.json`, `scripts/data/strategy_performance_replay.json`, and `scripts/data/factor_snapshots/*.json`.
  * `scripts/risk/a_kill_blacklist_store.py` writes `data/a_kill_blacklist.json`.
  * `scripts/report/candidate_trace_artifacts.py` writes `data/candidate-traces/<date>.json`.
  * `scripts/report/runtime.py` still has a direct fallback read from `data/decision-ledger/index.json`.
* Archive/cache JSON paths found so far:
  * `snapshots/*.json`, `snapshots/replay/*.json`
  * `reports/runs/*/*.json`, `logs/errors/*.json`
  * LLM and market-data cache JSON files
* Explicitly ignored for this task: all `snap-ui` paths and frontend static export flows.
* Project constraint: all Python commands must use `.generated/venv-py314/bin/python3.14`.
