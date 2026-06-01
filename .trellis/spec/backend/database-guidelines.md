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
- PostgreSQL-only runtime must not read historical snapshot archives for
  backfill. Both `daily_report_snapshot_io.load_data_snapshot()` and direct
  replay snapshot readers must reject `A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME=1`.
  If PostgreSQL history is short or stale, return the available structured rows
  or an empty list; do not rebuild by scanning `snapshots/*.json` or
  `snapshots/replay/*_replay.json`.
- JSON archives are allowed only as one-time import seeds, official replay
  archives, or explicit manual repair inputs. They are not a daily report hot
  path once PostgreSQL facts exist.
- When saving a replay snapshot over an existing official snapshot,
  `_save_data_snapshot()` may preserve `supplementary_perspective`, but it must
  read only compact metadata from the existing file rather than `json.load()` the
  full archive.
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
- PostgreSQL-only runtime attempts any `load_data_snapshot()` or replay snapshot
  JSON read -> raise immediately with the target date and stack, then fix the
  caller to read PostgreSQL or degrade to missing history.
- PostgreSQL-only history helper has fewer rows than requested -> return those
  rows; do not backfill by scanning archive JSON.
- Existing official snapshot is hundreds of MB and `_save_data_snapshot()` needs
  only `supplementary_perspective` -> read tail metadata only; do not parse the
  full archive.
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
- Base: `--postgres-only` with incomplete `mainline_daily` history renders using
  the available PostgreSQL rows and never calls the snapshot index rebuild.
- Bad: `_save_data_snapshot()` reads a 700 MB official snapshot with
  `json.load()` only to preserve `supplementary_perspective`.
- Bad: a placeholder `主线成交额占比趋势` row is rendered as `T-xxx（PSQL）` only
  because the heading matched.
- Bad: `--postgres-only` prints PostgreSQL sync success after only saving generic
  fact fields while dedicated structured tables remain stale.

### 6. Tests Required

- Unit test table numbering with PostgreSQL-only mode, dynamic ids, adjacent table
  contamination, populated structured tables, and placeholder tables.
- Unit test PostgreSQL-only history helpers with short/stale database history:
  snapshot readers and daily metric index rebuilds must not be called.
- Unit test replay snapshot direct readers under
  `A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME=1`.
- Unit test `_save_data_snapshot()` preserving `supplementary_perspective`
  without invoking `json.load()` on an existing official snapshot.
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

#### Wrong

```python
if db_history and _history_is_short(db_history, lookback_days):
    ensure_daily_metric_history_index(...)
```

In PostgreSQL-only runtime this can scan hundreds of MB from historical JSON.

#### Correct

```python
if db_history and postgres_only:
    return db_history
if postgres_only:
    return []
```

PostgreSQL-only runtime accepts the structured facts already present and keeps
archive JSON out of the report generation path.

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

## Scenario: Hot Sector Turnover Watch

### 1. Scope / Trigger

- Trigger: changing mainline turnover summaries, sector attack evidence, or any
  report section that compares sector turnover share across days.

### 2. Signatures

- Runtime API:
  `build_mainline_turnover_summary(..., recent_hot_sector_turnover_history=None, sector_attack_evidence_rows=None)`
- PostgreSQL import:
  `PostgresDailyFactDb.import_daily_report_facts(trade_date, data)`
- PostgreSQL load helpers:
  `load_sector_attack_evidence_rows(trade_date)` and
  `load_recent_hot_sector_turnover_history(trade_date, lookback_days=25)`
- Dedicated table fields:
  `sector_attack_evidence_daily.sector_turnover_yi`,
  `sector_attack_evidence_daily.total_turnover_yi`,
  `sector_attack_evidence_daily.turnover_share_pct`,
  `sector_attack_evidence_daily.source_policy`,
  `sector_attack_evidence_daily.source_run_id`

### 3. Contracts

- `hot_sector_turnover_watch_rows` is the replay-worthy table for recent hot
  sector turnover tracking. It must include at least `date`, `sector_name`,
  `sector_turnover`, `total_turnover`, `share`, `share_change`,
  `sample_status`, and `interpretation`.
- Renderers must split `hot_sector_turnover_watch_rows` into sector-scoped
  tables headed like `近期热点板块成交额连续跟踪：<sector_name>`. Do not render all
  sectors in one mixed watch table.
- `share_change` must be calculated only against the previous row for the same
  `sector_name`. If no prior same-sector point exists, render `待累计`.
- Daily selected-mainline turnover rows may still render as
  `主线切换成交额记录`, but they are switch records, not a same-sector trend.
- When multiple sectors appear in the selected-mainline history, summary text
  must not show a cross-sector percentage range as if it were a trend. Describe
  it as different directions or split points instead.
- `sector_attack_evidence_rows` must be stored in
  `sector_attack_evidence_daily`, not duplicated into generic
  `daily_report_fact_fields`.
- A table label such as `T-018（PSQL）` is valid only because the semantic table
  is PostgreSQL-backed; never key behavior on the dynamic `T-018` id.

### 4. Validation & Error Matrix

- A current hot sector has turnover and market total -> write both amounts and
  derive `turnover_share_pct` if needed.
- A current hot sector has share only -> derive sector turnover only when market
  total is present; otherwise keep the amount missing.
- No prior same-sector row -> `share_change=待累计`, not a cross-sector delta.
- Selected-mainline history switches sector names -> render
  `主线切换成交额记录` and avoid same-sector trend wording.
- Generic fact projection contains `sector_attack_evidence_rows` -> fix the
  projection filter; the dedicated table is the source of record.

### 5. Good/Base/Bad Cases

- Good: 2026-05-29 shows 通信设备, 国产芯片替代, 半导体, 电力, and other current hot
  sectors as separate sector tables, with changes only against each sector's own
  history.
- Base: 光通信/CPO has a 2026-05-28 point but no 2026-05-29 same-concept point;
  it remains `待累计` and is not compared to 新型电力.
- Bad: rendering `29.6% -> 0.9%` as a continuous turnover-share fall when the
  first point is 光通信/CPO and the second point is 新型电力.
- Bad: storing the same `sector_attack_evidence_rows` payload in both
  `sector_attack_evidence_daily` and generic fact fields.

### 6. Tests Required

- Unit test same-sector share deltas and cross-sector `待累计` behavior.
- Unit test renderer output splits hot-sector watch rows into sector-scoped
  tables and avoids a single mixed-sector watch table.
- Unit test mixed selected-mainline summary text does not use cross-sector arrow
  trends or cross-sector percentage ranges.
- Unit test PostgreSQL schema contains turnover amount, market amount, and source
  fields for `sector_attack_evidence_daily`.
- Unit test PostgreSQL import filters `sector_attack_evidence_rows` from generic
  fact fields while preserving `hot_sector_turnover_watch_rows`.
- Integration verification for replay dates must run `--postgres-only`, inspect
  the rendered hot-sector watch table, and query dedicated PostgreSQL rows.

### 7. Wrong vs Correct

#### Wrong

```python
previous_share = previous_share_any_mainline
row["share_change"] = _format_share_change(current_share, previous_share)
```

This compares different sectors and can turn a switch record into a fake fall.

#### Correct

```python
previous_share = previous_share_by_sector.get(sector_name, 0.0)
row["share_change"] = _format_share_change(current_share, previous_share)
previous_share_by_sector[sector_name] = current_share
```

Same-sector history is the only valid basis for turnover-share change.
