# PSQL Structured Replay Facts and Report Source Labels

## Goal

Make the daily report visibly distinguish tables backed by structured PostgreSQL replay facts, and keep the PostgreSQL fact boundary aligned with the trading/replay need: store only facts that help later replay, evidence review, comparison, tracking, and attribution. After implementation, regenerate the 2026-05-29 report using `--postgres-only`, verify the report and database, then commit on `develop`.

## What I Already Know

- The user does not want runtime JSON as the durable data path. JSON may be used only as a one-time import seed, not as the source for future replay generation.
- The existing PostgreSQL implementation already persists key structured facts: market cycle rows, sector flow, sector attack evidence, observation pools, tracking memory, candidate traces, extreme conviction cases/mentions, and planned participation steps.
- `2026-05-29 --postgres-only` currently regenerates successfully from PostgreSQL facts and report audit passes.
- The report auto-numbers markdown tables in `scripts/report/runtime.py::_number_report_tables()` as `**T-001**`, `**T-002**`, etc.
- The report does not yet surface whether a numbered table came from structured PostgreSQL facts. The user explicitly wants examples such as `T-089（PSQL）` when that table is backed by structured PostgreSQL data.
- Reports are ignored by git; regenerated reports are verification artifacts, not commit targets.
- Snap-ui is out of scope.

## Requirements

- Add visible source labeling for numbered report tables backed by structured PostgreSQL facts when the report runtime is in PostgreSQL-only mode.
- Labels must render as `**T-xxx（PSQL）**`, keeping existing numbering stable.
- PSQL labels should apply to durable replay/evidence/tracking facts, including at least:
  - cycle calendar / cycle interpretation / pivot-mainline style cycle tables,
  - mainline capacity, attack evidence, turnover-share trend, and sector-week/sector-cycle views,
  - sector fund flow / concept or sector tracking tables that are backed by stored PostgreSQL facts,
  - observation pools / tracking memory / leading memory tables,
  - candidate trace and extreme-conviction tracking tables, including the user example `T-089` when it is the extreme-conviction 25-day table.
- Do not label transient render-only tables as PSQL merely because the final report was produced in PostgreSQL-only mode.
- Do not store raw service payloads, render outputs, diagnostics, caches, logs, raw JSON blobs, or duplicate payload fields in PostgreSQL facts.
- Keep the implementation narrow: prefer table-numbering/source-label post-processing over editing every report section renderer unless a narrower implementation is impossible.
- Preserve all unrelated dirty working-tree changes.

## Acceptance Criteria

- [ ] Unit tests cover `_number_report_tables()` adding `（PSQL）` only for PSQL-backed table contexts, while leaving ordinary tables as `T-xxx`.
- [ ] Unit tests cover the example style: a `明日极度看好近25日跟踪表` table in PostgreSQL-only mode is numbered as `T-xxx（PSQL）`.
- [ ] Existing numbering behavior remains stable when PostgreSQL labeling is disabled.
- [ ] `2026-05-29 --postgres-only` regenerates a full replay report successfully.
- [ ] The regenerated 2026-05-29 full report contains PSQL labels on structured evidence tables, including at least the cycle section and the extreme-conviction 25-day table.
- [ ] Report acceptance audit passes for the regenerated 2026-05-29 report.
- [ ] SQL verification shows key structured tables are populated and low-value/payload-style fields are not stored.
- [ ] Relevant unit tests pass under `.generated/venv-py314/bin/python3.14`.

## Technical Approach

Use `scripts/report/runtime.py` as the integration point. `_number_report_tables()` already has full line context while inserting T labels. Extend it to accept or infer a `postgres_only` flag and mark only table contexts whose recent headings/text match durable PostgreSQL-backed fact families.

Expected implementation shape:

- Add a helper that inspects recent context before each table and returns whether the table is PSQL-backed.
- Pass `postgres_only` from `render_markdown_report_runtime()` into the report sanitization/numbering path.
- Keep default behavior unchanged for non-PostgreSQL report generation and existing tests.
- Add focused regression tests in `tests/test_report_runtime.py`.
- Use SQL/report checks as final verification, not as replacement for unit tests.

## Data Boundary

Structured PostgreSQL facts should include durable, queryable items that support future replay and evidence review:

- Market and cycle facts: daily market totals, cycle calendar, cycle periods, mainline switch/capacity records.
- Sector and board facts: sector flow, sector attack evidence, diffusion/competition/capacity records, mainline turnover/share history.
- Pools and memory: observation pools, tracking memory, leader memory, A-kill cooling items.
- Candidate evidence: candidate trace rows and their structured field evidence, extreme-conviction cases and mentions, planned participation steps, participation/fate/review records.
- Compact daily report fact fields only for curated scalar/list summaries that do not duplicate raw payloads.

Not stored:

- Raw service payloads and nested `payload` / `payload_json` / `raw_detail` data.
- Rendered markdown/HTML/logs/appendices as fact data.
- Temporary diagnostics, caches, request logs, minute-bar JSON caches, large intermediate bundles, or duplicate cross-JSON snapshots.
- Snap-ui public JSON or UI publish artifacts.

## Out of Scope

- Rebuilding every renderer to carry formal source metadata per table.
- Changing the PostgreSQL schema unless a concrete missing fact is found during verification.
- Migrating snap-ui or publishing snap-ui data.
- Reworking unrelated dirty files already present in the user's worktree.
- Making live external data calls the default for historical replay.

## Definition of Done

- Code and tests implemented.
- Focused tests and relevant integration tests pass.
- 2026-05-29 report regenerated with `--postgres-only`.
- SQL checks prove structured facts are present and low-value fields are absent.
- Changes committed on `develop` without including unrelated dirty files.
- Final response reports what changed, verification evidence, and any remaining caveats.

## Technical Notes

- Python command must use `.generated/venv-py314/bin/python3.14`.
- Existing commits on `develop`: `e1ec1c97` merged PostgreSQL replay facts and `54d93972` fixed idempotent Xuangubao summary counts.
- Existing related files:
  - `scripts/report/runtime.py`
  - `tests/test_report_runtime.py`
  - `scripts/storage/postgres_daily_fact_db.py`
  - `tests/test_postgres_daily_fact_db.py`
  - `scripts/daily_report_entry_demo.py`
  - `scripts/daily_report_render.py`
- Relevant spec guidance:
  - `.trellis/spec/backend/index.md`
  - `.trellis/spec/backend/database-guidelines.md`
  - `.trellis/spec/guides/cross-layer-thinking-guide.md`
