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

Monthly account continuity is stored separately in `monthly_account_ledger`.
Use it for per-account monthly continuity, not `daily_report_fact_fields`.
Persist `month_return_pct` together with a derived
`simulated_cumulative_return_pct` so the report can render the current month and
the compounded month series without defaulting missing returns to zero.

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
- `DatabaseService.load_daily_report_snapshot()` may return a metadata envelope
  whose report payload is under `data`. Account-history consumers must unwrap
  that payload before reading `personal_position_context`; treating the envelope
  itself as report data silently drops existing positions.
- `personal_position_context.existing_position_summary` is the durable current
  account source for the day-order renderer. Explicit CLI position input wins;
  otherwise an empty transient `positions` list must be restored from this
  PostgreSQL summary.
- Historical Ta/Tb/Tc account rows are PostgreSQL-first. Rendered Markdown is a
  compatibility fallback only when PostgreSQL has no usable fact and the run is
  not PostgreSQL-only.
- A PostgreSQL metadata envelope with `data={}`, or a raw empty mapping, means
  that the requested report-day fact is unavailable. PostgreSQL-only runtime
  must stop before reading Markdown; non-PostgreSQL runtime may use the explicit
  compatibility fallback.
- `--postgres-only` must finish by calling
  `import_daily_report_data_to_postgres()`, not only
  `save_daily_report_data_to_postgres()`, so dedicated structured tables are
  refreshed after the report runtime computes new facts.
- Production daily-report PostgreSQL writes must use
  `save_daily_report_data_to_postgres()` or
  `import_daily_report_data_to_postgres()`. These wrappers normalize inferred
  previous-report plans before delegating to storage; callers must not bypass
  them with a direct repository write.
- PostgreSQL-only runtime must not read historical snapshot archives for
  backfill. Both `daily_report_snapshot_io.load_data_snapshot()` and direct
  replay snapshot readers must reject `A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME=1`.
  If PostgreSQL history is short or stale, return the available structured rows
  or an empty list; do not rebuild by scanning `snapshots/*.json` or
  `snapshots/replay/*_replay.json`.
- Monthly account lookup should use `DatabaseService.from_environment()` when a
  repository may be PostgreSQL-backed. Do not hard-code retired local database paths
  when the database URL is already configured.
- JSON archives are allowed only as one-time import seeds, official replay
  archives, or explicit manual repair inputs. They are not a daily report hot
  path once PostgreSQL facts exist.
- PostgreSQL-only market structure analysis must inject
  `index_daily_bars` through `analyze_market_zhongshu(fetch_dataframe=...)` for
  both the report body and the companion Chanlun HTML. Do not leave the report
  body on the default live index loader while only the HTML uses PostgreSQL.
- Chanlun HTML generated from PostgreSQL-only replay must pass the PostgreSQL
  daily-bar loader, PostgreSQL minute-bar fetcher, and `allow_live_fallback=False`;
  the summary table should expose the daily-bar source, such as
  `postgresql.index_daily_bars`.
- When saving a replay snapshot over an existing official snapshot,
  `_save_data_snapshot()` may preserve `supplementary_perspective`, but it must
  read only compact metadata from the existing file rather than `json.load()` the
  full archive.
- Report table labels use semantic context plus non-placeholder table rows, not
  dynamic `T-xxx` ids. A rendered label may move to a different table id after
  upstream sections change; implementation must not key on that id.
- No-sample observation rows are placeholders even when their heading names a
  durable table family. Rows such as `暂无 / 无龙回头样本 / 今天没有单独观察对象`
  must render as plain `T-xxx`, not `T-xxx（PSQL）`.
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
- PostgreSQL stores a current position but Td omits its stock identity -> stop
  generation with `position_day_order_current_position_missing` and preserve
  the finding in the run error record.
- Bear HTML omits the PostgreSQL current position while Markdown contains it ->
  stop generation with `position_day_order_html_current_position_missing`.
- PostgreSQL summary is marked as inherited from the previous report ->
  normalize every structured copy to `has_position=true`,
  `has_pending_position=false`, actual `position=50`, `position_pct=50`,
  `default_position_pct=50`, and role `旧仓处理`; calculate confirmed 1x/50%
  old-position exposure.
- PostgreSQL load, snapshot save, or fact import sees a legacy inherited summary
  with pending or zero fields -> repair it to the confirmed 1x/50% payload before any
  consumer or write boundary.
- PostgreSQL inherited summary appears in a later Ta/Tb/Tc lookup -> preserve it
  as a historical confirmed simulated old position.
- Explicit empty input, an executed tomorrow-empty instruction, or an explicit
  exit fact overrides inherited PostgreSQL records. A report with no new target
  does not clear the most recent unfinished inherited old position.
- An explicitly external pending trade record also carries
  `has_pending_position=true`, remains 0x, and only verifies its trade record.
- Existing official snapshot is hundreds of MB and `_save_data_snapshot()` needs
  only `supplementary_perspective` -> read tail metadata only; do not parse the
  full archive.
- Report table has a PostgreSQL semantic heading but only placeholder rows such
  as `数据暂缺` / `待累计` -> render plain `T-xxx`, without `（PSQL）`.
- Observation-pool table has only no-sample rows such as `无龙回头样本` or
  `没有单独观察对象` -> render plain `T-xxx`, without `（PSQL）`.
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
  contamination, populated structured tables, placeholder tables, and no-sample
  observation-pool placeholders.
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
- Unit test PostgreSQL load/save/import boundaries normalize an inherited
  previous-report target to `has_position=true`, `has_pending_position=false`,
  actual `position=50`, `position_pct=50`, and
  `default_position_pct=50`, while preserving source date and identity.
- Unit test `external_trade_pending` remains `has_position=false`,
  `has_pending_position=true`, and actual 0 after the same boundaries.
- Unit test the same normalization leaves an explicit confirmed position
  byte-for-byte unchanged.
- Unit test the real empty-load shape (`{"data": {}}`), not only a mocked
  `None`, and verify PostgreSQL-only entry stops before database sync or report
  artifact writes while an explicit `position_context_provided=true` empty
  account fact remains valid.

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

## Scenario: PostgreSQL Runtime Cache Entries

### 1. Scope / Trigger

- Trigger: changing any report helper that previously wrote local JSON cache
  files, including price-history cache, minute-bar cache, reasoning-decision
  cache, or LLM event-analysis cache.

### 2. Signatures

- DB table: `runtime_cache_entries(namespace, cache_key, target_date, payload, source, expires_at)`
- Facade APIs:
  - `DatabaseService.get_runtime_cache_entry(namespace, cache_key, target_date="")`
  - `DatabaseService.set_runtime_cache_entry(namespace, cache_key, target_date, payload, source="", ttl_seconds=None)`
  - `DatabaseService.delete_expired_runtime_cache_entries()`
  - `DatabaseService.get_runtime_cache_stats(namespace, target_date="")`
- Env:
  - `A_DAILY_REPORT_DATABASE_URL` or `DATABASE_URL`
  - `A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME=1`

### 3. Contracts

- Runtime cache is not a durable replay fact. It may use compact JSONB payloads
  only inside `runtime_cache_entries`, with `expires_at` required for every row.
- Index minute bars are replay-worthy structure, not disposable cache. Live
  fetch helpers must write them to `index_minute_bars` when PostgreSQL is
  configured.
- PostgreSQL-only runtime must never read or write local JSON cache files. If a
  helper cannot use PostgreSQL, it must either use process memory for that run or
  report the missing PostgreSQL dependency, depending on whether the cache is
  optional.
- Cache namespaces must be explicit and stable, such as `history_cache`,
  `minute_price`, `reasoning_decision`, and `llm_event_analysis`.
- Durable report facts still belong in dedicated structured tables or curated
  `daily_report_fact_fields`; do not put replay-worthy facts into
  `runtime_cache_entries`.
- Historical JSON cache files may be used once as a manual seed into
  `runtime_cache_entries`, then the runtime must query PostgreSQL.

### 4. Validation & Error Matrix

- PostgreSQL URL configured -> helper reads/writes `runtime_cache_entries` and
  does not create local `*.json` cache files.
- `A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME=1` without PostgreSQL and optional cache
  -> use process memory only; do not touch local JSON.
- `A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME=1` without PostgreSQL and required
  storage -> raise a clear PostgreSQL-required error before opening JSON files.
- Expired row -> treat as cache miss; do not backfill from local JSON.
- Live index-minute fetch succeeds but PostgreSQL write fails -> still return
  the live bars, and include `postgres_write_status="failed"` plus
  `postgres_write_error`; do not report a clean structured write.
- SQL low-value-field audit -> `daily_report_fact_fields` remains free of
  `payload`, `raw`, `cache`, rendered markdown/html, module logs, and request
  diagnostics.
- Run-log duration output -> append one compact Markdown table. Do not insert
  blank lines between table rows, because that makes the runtime evidence hard
  to scan.

### 5. Good/Base/Bad Cases

- Good: 2026-05-29 `--postgres-only` uses `llm_event_analysis` runtime cache for
  calendar-event analysis and still reports full cache hits without reading
  `data/event_analysis_cache.json`.
- Base: minute price cache has no PostgreSQL entry; the helper can fetch live
  bars and skip local file writes in PostgreSQL-only runtime.
- Base: live minute fetch can continue after a PostgreSQL write failure only if
  the returned payload exposes the failed write.
- Bad: a helper writes `scripts/cache/history_cache/<date>.json` or
  `data/event_analysis_cache.json` during PostgreSQL-only report generation.
- Bad: a helper returns `status="success"` for live minute bars while silently
  dropping the failed `index_minute_bars` write.
- Bad: replay-worthy sector, pool, candidate, or cycle facts are stored only as a
  runtime cache payload instead of structured tables.

### 6. Tests Required

- Unit test each migrated cache helper with PostgreSQL configured: assert service
  `get_runtime_cache_entry` / `set_runtime_cache_entry` calls and no local JSON
  file creation.
- Unit test PostgreSQL-only mode without a PostgreSQL URL: required stores raise
  before JSON access; optional caches use memory and do not write files.
- Unit test live minute-bar fetch with a failing PostgreSQL write returns the
  bars plus `postgres_write_status="failed"` and the error text.
- Unit test `PostgresDailyFactDb` schema includes `runtime_cache_entries`,
  TTL column, and namespace/date indexes.
- Integration verification for a replay date must run `--postgres-only`, inspect
  PSQL-labeled report tables, query `runtime_cache_entries` namespaces, and
  confirm low-value fields are absent from `daily_report_fact_fields`.

### 7. Wrong vs Correct

#### Wrong

```python
cache_path = Path("data/event_analysis_cache.json")
cache_path.write_text(json.dumps(cache), encoding="utf-8")
```

This keeps local JSON on the report runtime path.

#### Correct

```python
service.set_runtime_cache_entry(
    "llm_event_analysis",
    event_hash,
    "",
    {"timestamp": time.time(), "title": title, "result": result},
    source="llm_service",
    ttl_seconds=5 * 86400,
)
```

This keeps disposable cache separate from durable replay facts and lets
PostgreSQL expire it.

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

---

## Scenario: Recent 25-Day Replay Fact Migration

### 1. Scope / Trigger

- Trigger: importing historical report facts from JSON seeds into PostgreSQL, or
  changing the PostgreSQL-only replay path after such an import.

### 2. Signatures

- CLI:
  `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <YYYY-MM-DD> --postgres-only`
- Import API:
  `DatabaseService.from_environment().import_daily_report_facts(trade_date, data)`
- Load API:
  `DatabaseService.from_environment().load_daily_report_data(trade_date)`
- Lookback rule: import the recent 25 trading days needed for replay and
  comparison; older JSON archives are not runtime inputs after the import.

### 3. Contracts

- JSON snapshots may seed a one-time 25-trading-day import. After import, the
  report runtime must read PostgreSQL facts and must not scan old JSON archives
  to answer daily report history questions.
- The 25-day cutoff must come from explicit trading-day series, such as
  `new_high_feedback.trend_rows`, `top50_turnover_share_series.rows`,
  `etf_turnover_series.rows`, or `margin_pressure.rows`; do not derive it from
  arbitrary nested `date` / `query_date` / `source_date` fields.
- Only replay-worthy facts belong in PostgreSQL: market totals, market cycle
  rows, mainline/capacity records, sector flow, sector attack evidence,
  same-sector turnover watch rows, observation pools, tracking memory,
  candidate traces, extreme-conviction cases/mentions, planned participation
  steps, and compact scalar/list summaries.
- Large payloads, cache files, diagnostics, render logs, raw service response
  trees, minute-bar blobs, and duplicated nested payload fields must stay out of
  PostgreSQL.
- `market_cycle_days` must have a target-day row when `current_mainline_history_record`
  or `recent_mainline_history` contains that day, even if
  `cycle_calendar_rows` is missing the row.
- Hot-sector turnover tracking must keep exact board/concept names as grouping
  keys. `电力`, `新型电力`, `绿色电力`, and `绿电` may be related in narrative
  analysis, but they must not be merged into one same-sector turnover series.
- If a generic compact summary contains same-day hot-sector watch rows with the
  same sector turnover, market turnover, and share but different `sector_name`
  values, treat it as stale generic contamination. Preserve the row that records
  the exact current concept as `待累计` and reject the false same-sector
  continuity row before rendering or writing the refreshed compact facts.
- Structured PostgreSQL rows should overwrite stale generic fact-field rows
  during PostgreSQL-only enrichment. Do not keep a generic JSON-shaped value
  when a dedicated table has a cleaner replay row for the same concept.
- `new_high_feedback_daily` must preserve `source_date`, `query_date`, and
  `requested_trade_date` through insert and query. A source without an explicit
  target-date capability, such as a current ranking endpoint, must not be saved
  under a historical `trade_date`; keep the historical fact missing instead.
- When the explicit replay series has fewer than 25 trading days, import must
  record `structured_counts.recent_replay_window_status` with `status`,
  `available_days`, `required_days`, `min_trade_date`, and `max_trade_date`.
  Do not silently skip the pruning decision, and do not widen into archive JSON.
- Candidate action traces should prefer the richer contract-generated trace over
  an incomplete generic trace. Missing account context is not required when an
  earlier market or mainline condition has already decided `继续不参与`.

### 4. Validation & Error Matrix

- Import range has fewer than 25 trading days -> report the actual date range
  and row counts; do not silently widen to stale archives.
- A non-trading-day calendar event, source date, or query date appears inside
  the report object -> ignore it for the replay pruning cutoff.
- PostgreSQL-only runtime attempts to open archive JSON for history -> stop and
  fix the caller to use PostgreSQL or accept missing history.
- Replay series has fewer than 25 trading days -> return an explicit
  `recent_replay_window_status` in the PostgreSQL import result and leave pruning
  off for that import.
- A target date has current mainline history but no cycle calendar row -> derive
  one `market_cycle_days` row from the mainline record with date, weekday, week
  label, mainline, and phase when available.
- Hot-sector rows contain related power concept names -> render/query separate
  sector tables, unless the source itself uses the exact same sector name.
- Hot-sector rows contain same-day identical turnover/share metrics under two
  different sector names -> keep the exact current concept point and drop the
  pseudo-continuity row from the refreshed report facts.
- Candidate trace has placeholders such as `暂无` or `数据缺失` but another
  structured source has the field -> fill the placeholder before rendering and
  before PostgreSQL import.
- Candidate trace dedicated rows exist for the target date -> PostgreSQL-only
  load must hydrate `candidate_trace_artifact.traces` from those rows, even if a
  compact generic artifact also exists.
- `daily_report_fact_fields` contains paths with `payload`, `raw`, `cache`,
  `module_logs`, or `request_diagnostics` as path components -> reject the
  projection and filter those fields.

### 5. Good/Base/Bad Cases

- Good: 2026-05-29 replay uses PostgreSQL-only data, shows `T-xxx（PSQL）` on
  structured cycle, sector, candidate, and extreme-conviction tables, and SQL
  queries can inspect the same facts by table.
- Base: 2026-05-27 has no official snapshot but has a replay seed; the one-time
  import may use that seed, while later generation still reads PostgreSQL.
- Base: a mixed `电力` / `新型电力` history renders and queries as separate
  rows/tables, so same-sector deltas are never calculated across them.
- Bad: broadening the import to every historical JSON file because a 25-day
  comparison helper found a short table.
- Bad: keeping a 700 MB JSON archive as the report history source after the
  recent 25-day import has populated PostgreSQL.

### 6. Tests Required

- Unit test `import_daily_report_facts()` filters low-value paths from generic
  fact fields while preserving dedicated structured rows.
- Unit test replay cutoff uses a known 25-trading-day series and ignores
  unrelated calendar/source dates.
- Unit test insufficient replay series reports
  `structured_counts.recent_replay_window_status` and does not prune.
- Unit test PostgreSQL load enrichment overwrites stale generic
  `recent_hot_sector_turnover_history` with structured rows.
- Unit test PostgreSQL load enrichment overwrites stale generic
  `sector_attack_evidence_rows` and hydrates `candidate_trace_artifact` from the
  dedicated trace tables.
- Unit test related hot-sector concept names stay separate in both loader and
  runtime summary paths.
- Unit test self-conflicted hot-sector watch rows: same date + same turnover
  metrics + different sector names must remove the false continuous row while
  preserving unrelated current hot-sector rows.
- Unit test `market_cycle_days` target-day fallback from current or recent
  mainline history.
- Unit test candidate trace enrichment fills placeholders and keeps no-action
  traces complete when account context is irrelevant.
- Integration verification for a replay date must run `--postgres-only`, inspect
  PSQL-labeled tables in the rendered report, and query row counts from the
  dedicated PostgreSQL tables.

### 7. Wrong vs Correct

#### Wrong

```python
rows = load_recent_json_snapshots(lookback_days=25)
return build_turnover_history(rows)
```

This keeps old JSON archives on the replay path after the PostgreSQL import.

#### Correct

```python
rows = db.load_recent_hot_sector_turnover_history(trade_date, lookback_days=25)
return build_turnover_history(rows)
```

The 25-day import is only the seed; PostgreSQL is the replay source after that.

## Scenario: Bounded Daily Snapshot Serialization

### 1. Scope / Trigger

- Trigger: changing daily-report runtime context, JSON serialization, snapshot
  persistence, replay snapshot writes, or snapshot observability.

### 2. Signatures

- Runtime compaction:
  `_compact_execution_stage_context_for_persistence(execution_stage_context) -> dict`
- Serializer:
  `_make_serializable(obj, _depth=0, _active_ids=None) -> Any`
- Persistence:
  `_save_data_snapshot(data, target_date, mode="frozen") -> str`
- Limit: `MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024`

### 3. Contracts

- `data.execution_stage_context` must not contain the complete parent `data`
  mapping or callable runtime dependencies. It must retain business outputs
  such as candidate evidence, selection results, final decisions, and source
  dates.
- The active runtime stage context keeps its callables until all dependent
  rerenders finish. Persistence compaction returns a shallow copy and must not
  mutate the active context; otherwise later PK rendering loses price-focus and
  stop-plan helpers.
- Circular-reference detection uses the current recursion path, not a global
  visited-object set. A reference already on the current path becomes
  `<circular_reference>`; the same shared value used by sibling fields remains
  fully serialized in both fields.
- The 50-level recursion limit remains a final malformed-depth fallback. It is
  not the normal way to stop a direct or indirect object cycle.
- New official and replay snapshots must not exceed 64MiB of actual UTF-8 JSON
  bytes. Crossing the limit raises before a target file is replaced.
- Snapshot JSON is written to a unique temporary file in the target directory.
  Only a complete dump, flush, and file sync may be followed by `os.replace()`.
  Every failure removes the temporary file and preserves an existing target
  byte-for-byte.
- An existing official snapshot remains frozen. A later frozen save applies
  the same bounded atomic contract to the replay path.
- The main daily-report entry records the requested mode, actual mode, target
  path, actual file size, and size-limit result for every official or replay
  snapshot attempt. Logs must not contain the complete report payload or
  database secrets. Alternate orchestrator observation remains a separate
  migration item; it still uses the same bounded atomic writer.
- The 64MiB snapshot is transitional recovery material. After PostgreSQL-only
  replay and downstream consumers pass their migration checks, stop creating
  new full-report JSON while retaining the old reader for explicit import and
  repair.

### 4. Validation & Error Matrix

| Situation | Required handling |
|---|---|
| `data -> execution_stage_context -> data` | Remove the runtime parent reference before persistence; serializer fallback emits one circular marker |
| Same mapping appears under two sibling keys without a cycle | Serialize the value under both keys |
| Serialized bytes exceed 64MiB | Raise a clear size error, remove the temporary file, preserve the target |
| JSON encoding or file sync fails | Remove the temporary file and preserve the target |
| First official save succeeds | Produce valid JSON at the official path and report actual bytes |
| Official path already exists | Leave it unchanged and apply the same atomic limit to the replay path |
| Snapshot save is mocked and returns a non-path test value | Observation may omit size; production save still returns a real path |

### 5. Good/Base/Bad Cases

- Good: an 8MiB report object with a direct self-reference serializes to about
  8MiB plus metadata and one circular marker instead of repeating the object.
- Good: a replay write stays below 64MiB, replaces the old replay file only
  after complete JSON is durable, and records the final byte count.
- Base: a legacy object contains a deeper indirect cycle not removed by runtime
  compaction; the serializer stops at the first repeated object on the active
  path.
- Bad: use a global `seen` set and replace a legitimate shared candidate object
  in the second sibling field with a circular marker.
- Bad: open the final target with mode `w` before checking size; an oversized or
  failed dump destroys the previous recoverable snapshot.
- Bad: rely on the 50-level fallback for a direct self-reference, producing a
  GB-scale file from a tens-of-MB report object.

### 6. Tests Required

- Unit test a direct `data -> context -> data` cycle and assert one
  `<circular_reference>` marker without repeated expansion.
- Unit test a shared sibling mapping and assert both serialized values remain
  complete.
- Unit test a valid small frozen save parses as complete JSON and leaves no
  temporary files.
- Unit test an oversized replay save raises, leaves the prior replay bytes
  unchanged, and leaves no temporary files.
- Report-runtime tests must assert compaction returns a persistence copy without
  `data` or callable dependencies, preserves selection output, and leaves the
  active stage context unchanged until dependent rerenders finish.
- Entry verification must confirm snapshot observation includes the real file
  size when a production path is returned.

### 7. Wrong vs Correct

#### Wrong

```python
data["execution_stage_context"] = {"data": data, **runtime_dependencies}
with snapshot_path.open("w", encoding="utf-8") as file_obj:
    json.dump(_make_serializable(data), file_obj)
```

This creates a self-reference, expands it until the depth fallback, and
truncates an existing target before size or encoding success is known.

#### Correct

```python
persisted_context = {
    key: value
    for key, value in context.items()
    if key != "data" and not callable(value)
}
data["execution_stage_context"] = persisted_context

write_bounded_temp_json(data, max_bytes=64 * 1024 * 1024)
os.replace(temp_path, snapshot_path)
```

The persisted context retains business facts, circular fallback remains at the
serializer boundary, and only a complete bounded file replaces the target.

## Scenario: Bear Tomorrow-Action Calendar History

### 1. Scope / Trigger

- Trigger: adding or changing the Bear calendar that reviews recent report-day
  tomorrow decisions and their planned account performance over the next two
  trading days.

### 2. Signatures

- Repository:
  `PostgresDailyFactDb.query_tomorrow_action_history(end_date, *, mode="frozen", limit=25)`.
- Facade:
  `DatabaseService.query_tomorrow_action_history(end_date, *, mode="frozen", limit=25)`.
- Source tables: `strategy_factor_snapshots` and
  `strategy_factor_snapshot_fields`.

### 3. Contracts

- Select the latest `limit` snapshot report dates where
  `mode = <requested mode>` and `report_date <= end_date`, then restore them in
  ascending report-date order.
- Read only final tomorrow-decision fields:
  `two_layer_decision_payload.next_day_action.final_object_identity`,
  `position_stance`, `stock.code`, `stock.name`, and
  `two_layer_decision_payload.tomorrow_account_action.action`.
- A stock identity produces `action_type="execute"`. `无` together with
  `0%不参与` produces `action_type="no_trade"` and `can_new_entry=false`.
- Only an explicit account action `empty` or `明日空仓` produces
  `tomorrow_account_empty=true`. An empty account-action object and a missing
  stock identity do not prove an empty account.
- The calendar path is read-only. It must never call
  `save_strategy_performance_ledger()`: that writer deletes all ledger and
  factor-snapshot rows for the mode before replacing them.
- If final snapshot history is absent, the calendar builder may read the legacy
  strategy ledger for compatibility. It must not scan Markdown, HTML, or JSON.
- The calendar builder requests one report before the displayed window because
  that plan can still contribute its second-day `1x/50%` leg to the first
  displayed execution date.
- Each concrete target creates a `1x/50%` leg on each of the next two actual
  trading days. A no-new-entry decision creates no new leg but preserves a
  prior target's second-day leg. An explicit tomorrow-empty action clears every
  leg on that execution date.
- Keep plan action and account result separate. If a no-new-entry plan has no
  active leg on its execution date, the account result is `empty` while the
  plan remains `no_new_entry`; if a prior second-day leg exists, the account
  result is the target and the UI adds a no-new-entry plan note.
- Derive actual trading dates from the presence of Shanghai Composite daily-bar
  rows. Do not drop a date merely because its `open` or `close` is missing;
  preserve the execution date and mark only its return as incomplete.
- Calculate every stock leg and the Shanghai benchmark from the same day's
  `open` and `close`. A missing, non-finite, or conflicting same-day price fact
  is incomplete and must not become zero or silently select the last row.
- At most two `1x/50%` legs may be active on one day. More than two is an
  incomplete account fact, not a displayed position above `2x/100%`.
- Calendar-only holiday notes (for example, `2026-06-19` `端午休假`) and
  sample-outside notes are not report records and never enter holdings,
  valid-day, or return counts.

### 4. Validation & Error Matrix

- Invalid `end_date` -> return an empty history list without querying rows.
- Missing repository method -> the facade returns an empty list.
- No final snapshot history -> use the same-mode legacy ledger only.
- Snapshot says `无 + 0%不参与` without explicit account empty -> return
  `no_trade`, never `tomorrow_account_empty=true`.
- Requested `replay` mode -> query only replay rows; never fill from frozen rows.
- One active stock leg lacks a valid target-day open or close -> preserve all
  actions and the execution date, but exclude that day from every return total.
- Duplicate Shanghai rows disagree on the target-day open or close -> preserve
  the trading date and mark the benchmark return incomplete.
- Calendar generation attempts a full strategy-ledger save -> reject the
  implementation because it can erase the existing snapshot history.

### 5. Good/Base/Bad Cases

- Good: 25 frozen snapshots restore 11 stock targets and 14 no-new-entry days
  while preserving all 25 report dates; target plans expand into first- and
  second-day `1x/50%` account legs without creating extra report records.
- Good: a no-new-entry day still shows and evaluates the prior target's
  second-day leg.
- Base: no snapshot rows but a legacy same-mode ledger exists; the calendar
  uses the legacy records and exposes that source.
- Bad: an empty `tomorrow_account_action` mapping is rendered as an empty
  account.
- Bad: the report entry rewrites the complete strategy ledger solely to make
  the current calendar row visible.

### 6. Tests Required

- Repository SQL test asserts the selected field paths, `LIMIT %s`, mode/date
  parameters, ascending restored dates, target identity, no-new-entry, and
  explicit account-empty handling.
- Service-builder test asserts final snapshot history wins when the legacy
  ledger is empty and exposes
  `source="postgresql.strategy_factor_snapshot_fields"`.
- Integration check against the configured PostgreSQL database reports record,
  target-plan, account-holding, no-new-entry, and explicit-empty counts plus the
  independently compounded account, Shanghai, and excess returns without
  writing any table.

### 7. Wrong vs Correct

#### Wrong

```python
update_strategy_performance_book(...)
calendar = service.load_strategy_performance_ledger(mode=mode)
```

This can route through a full-replacement writer and remove older factor
snapshots.

#### Correct

```python
records = service.query_tomorrow_action_history(
    target_report_date,
    mode=mode,
    limit=25,
)
```

This keeps the review surface read-only and uses the durable final-decision
facts already present in PostgreSQL.
