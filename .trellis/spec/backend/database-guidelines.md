# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

The daily report PostgreSQL store is the durable replay source for facts that
support later review, attribution, comparison, and tracking. JSON may still be
used as a one-time import seed or ignored render artifact, but future replay
paths must read durable report facts from PostgreSQL.

---

## Query Patterns

Use `DatabaseService.from_environment()` and `PostgresDailyFactDb` for report
facts. Do not scan historical JSON snapshots from PostgreSQL-only runtime paths.

Report runtime computed facts must be merged back into the `data` payload before
final PostgreSQL import. If a renderer computes a durable replay fact, export it
from the node result and merge it into `data`; then
`PostgresDailyFactDb.import_daily_report_facts()` must write both:

- dedicated structured tables when a table exists, such as
  `sector_diffusion_score_daily` and `sector_diffusion_score_components`;
- curated `daily_report_fact_fields` paths for structured facts that do not yet
  have dedicated tables, such as `market_research_snapshot.sector_internal_analysis.turnover_trend`.

---

## Scenario: PostgreSQL-Only Daily Report Replay Facts

### 1. Scope / Trigger

- Trigger: changing daily report storage, replay, report table source labels, or
  runtime-computed facts that later review may query.

### 2. Signatures

- CLI: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <YYYY-MM-DD> --postgres-only`
- Import API: `PostgresDailyFactDb.import_daily_report_facts(trade_date, data)`
- Snapshot API: `PostgresDailyFactDb.save_daily_report_snapshot(trade_date, data)`
- Load API: `PostgresDailyFactDb.load_daily_report_snapshot(trade_date)`

### 3. Contracts

- `--postgres-only` must load from PostgreSQL via
  `load_daily_report_data_from_postgres()`.
- `--postgres-only` must finish by calling
  `import_daily_report_data_to_postgres()`, not only
  `save_daily_report_data_to_postgres()`, so dedicated structured tables are
  refreshed after the report runtime computes new facts.
- Report table labels use semantic context plus non-placeholder table rows, not
  dynamic `T-xxx` ids. A rendered label may move to a different table id after
  upstream sections change; implementation must not key on that id.
- Runtime-computed sector facts must flow as:
  `build_sector_fund_inflow_node().exports["sector_internal_analysis"]` ->
  `build_market_activity_report_sections().exports` ->
  `report.runtime` merged `data` ->
  `PostgresDailyFactDb.import_daily_report_facts()`.
- Low-value fields must not be written to `daily_report_fact_fields`: raw
  payloads, payload JSON, request diagnostics, rendered markdown/html, appendices,
  module logs, caches, debug fields, duplicate payloads, and Xuangubao raw item
  lists.

### 4. Validation & Error Matrix

- Missing PostgreSQL URL in PostgreSQL-only mode -> stop generation with a clear
  data-missing error.
- Report table has a PostgreSQL semantic heading but only placeholder rows such
  as `数据暂缺` / `待累计` -> render plain `T-xxx`, without `（PSQL）`.
- Runtime-computed diffusion facts present only at top level while
  `market_research_snapshot` also exists -> importer must merge them into the
  market snapshot before writing structured tables.
- Low-value field path appears in `daily_report_fact_fields` -> fix the compact
  projection or low-value key filter before accepting the migration.

### 5. Good/Base/Bad Cases

- Good: `2026-05-29 --postgres-only` refreshes
  `sector_diffusion_score_daily`, `sector_diffusion_score_components`, observation
  pools, tracking memory, candidate traces, and extreme conviction tables.
- Base: a populated cycle table is rendered as `T-xxx（PSQL）` because its semantic
  heading and table body are durable facts.
- Bad: a placeholder `主线成交额占比趋势` row is rendered as `T-xxx（PSQL）` only
  because the heading matched.
- Bad: `--postgres-only` prints PostgreSQL sync success after only saving generic
  fact fields while dedicated structured tables remain stale.

### 6. Tests Required

- Unit test table numbering with PostgreSQL-only mode, dynamic ids, adjacent table
  contamination, populated structured tables, and placeholder tables.
- Unit test runtime sector exports from `market_activity` into
  `sector_internal_analysis`.
- Unit test `import_daily_report_facts()` writes runtime
  `sector_internal_analysis.diffusion_quality` to dedicated diffusion tables and
  preserves `turnover_trend` / `quant_environment` in generic structured fact
  fields.
- Integration verification for a real replay date must include SQL counts for
  dedicated structured tables and a precise low-value-field query that returns
  zero.

### 7. Wrong vs Correct

#### Wrong

```python
if args.postgres_only:
    result = save_daily_report_data_to_postgres(target_date, data)
```

This updates generic fact fields only and can leave dedicated replay tables stale.

#### Correct

```python
if args.postgres_only:
    result = import_daily_report_data_to_postgres(target_date, data)
```

This refreshes both dedicated structured tables and curated generic fact fields.

---

## Naming Conventions

<!-- Table names, column names, index names -->

(To be filled by the team)

---

## Common Mistakes

- Treating dynamic report table ids such as `T-xxx` as stable identifiers. They
  are render artifacts; use semantic section context and data-source contracts.
- Assuming a runtime renderer export is persisted because it appears in Markdown.
  Verify the import path and SQL rows.
- Using broad regexes such as `raw` against encoded field paths; this can match
  legitimate terms like `max_drawdown`. Match field path components instead.
