# SQLite Report Fact Store Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move slow daily-report historical reads away from giant JSON snapshots and onto the existing SQLite/D1-compatible fact store.

**Architecture:** Use the existing `DatabaseService.sqlite_d1_compatible()` facade and `CloudflareFreeDailyDb` tables as the first local fact store. Keep JSON snapshots as replay/audit artifacts only; historical report logic should query narrow fact rows first and only use old JSON as a temporary backfill source while the database is being filled.

**Tech Stack:** Python 3.14, stdlib `sqlite3`, existing `scripts/storage/database_service.py`, existing `scripts/storage/cloudflare_free_daily_db.py`, existing market-state history index.

---

## Why This Change Exists

- The current daily report JSON snapshot is doing too much: current facts, runtime context, historical lookup source, and replay artifact.
- `execution_stage_context` can carry a full `data` object. Once that object is serialized into JSON, the next day may read a huge previous snapshot just to extract a few small historical facts.
- Evidence from the 2026-05-22 run: data-source phase finished in about 60 seconds, then report generation stayed CPU-bound while reading `snapshots/2026-05-21.json`.
- Snapshot size jumped from about 2MB on 2026-05-20 to 218MB on 2026-05-21, and replay reached 526MB.
- Historical report logic usually needs narrow facts: market turnover, sector flow, mainline history, mainline turnover, new-high feedback. It does not need the full previous report payload.
- SQLite is already present in the repo and is the correct local stepping stone. PostgreSQL can later implement the same facade methods without changing report logic.
- The existing local fact store is `data/cloudflare_free_daily.db` via `DatabaseService.sqlite_d1_compatible()`. Do not revive the older `data/daily_report.db` path.
- Complete JSON and full report markdown remain artifacts for replay/audit/backfill. The database stores queryable facts, indexes, source policy, and artifact references.

## In Scope

- Add narrow SQLite-backed fact methods for market daily totals and sector fund-flow history if missing.
- Change the slow historical lookup paths used during report generation to query SQLite first.
- Ensure the daily metric index can backfill required facts from existing snapshots or markdown once, then future runs use SQLite.
- Add regression tests that prove historical lookups do not call `load_data_snapshot` when database rows exist.
- Add a small repair/backfill command or helper for 2026-05-21/2026-05-22 investigation use.

## Out of Scope

- Full PostgreSQL implementation.
- Removing all JSON snapshots immediately.
- Rewriting the whole report pipeline.
- Changing trading logic or report conclusions.
- Building a new ORM or migration framework.
- Reusing or extending the old `data/daily_report.db` database.
- Storing complete `execution_stage_context`, K-line arrays, minute arrays, or full decision-ledger JSON in SQLite during this slice.
- snap-ui and related static publishing/export work. That path is currently frozen and must not be used as a reason to keep or expand JSON snapshot behavior in this slice.

## Non-goals

- Do not optimize every slow data source in this pass.
- Do not make JSON prettier, smaller, or more compatible as the main solution.
- Do not create a parallel storage abstraction when `DatabaseService` already exists.

## Done Definition

- A 2026-05-22 report run no longer reads `snapshots/2026-05-21.json` for narrow history if SQLite facts exist.
- Tests show market-turnover and sector-flow history query SQLite first.
- Existing mainline/new-high SQLite history tests still pass.
- The implementation preserves the `DatabaseService` facade so PostgreSQL can replace the repository later.
- Verification commands use `.generated/venv-py314/bin/python3.14`.

---

### Task 1: Add Sector Fund-Flow Daily Facts

**Files:**
- Modify: `scripts/storage/cloudflare_free_daily_db.py`
- Modify: `scripts/storage/database_service.py`
- Test: `tests/test_database_service.py`

- [ ] **Step 1: Write the failing test**

Add a test that creates a temp SQLite db, upserts sector fund-flow rows for two dates, and queries a date window.

```python
def test_database_service_can_store_and_query_sector_fund_flow_daily(self):
    from storage.database_service import DatabaseService

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "daily.db"
        service = DatabaseService.sqlite_d1_compatible(db_path)
        service.upsert_sector_fund_flow_daily(
            {
                "trade_date": "2026-05-21",
                "sector_name": "半导体",
                "net_inflow_yi": 12.34,
                "source": "tushare.moneyflow_ind_ths",
            }
        )
        service.upsert_sector_fund_flow_daily(
            {
                "trade_date": "2026-05-22",
                "sector_name": "半导体",
                "net_inflow_yi": -5.67,
                "source": "tushare.moneyflow_ind_ths",
            }
        )

        rows = service.query_sector_fund_flow_series("2026-05-22", "半导体", window_days=2)

    self.assertEqual([row["date"] for row in rows], ["2026-05-21", "2026-05-22"])
    self.assertEqual(rows[0]["inflow"], 12.34)
    self.assertEqual(rows[1]["inflow"], -5.67)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_database_service
```

Expected: fails because `upsert_sector_fund_flow_daily` / `query_sector_fund_flow_series` do not exist.

- [ ] **Step 3: Implement storage methods**

Add a `sector_fund_flow_daily` table to `CloudflareFreeDailyDb._ensure_schema()`:

```sql
CREATE TABLE IF NOT EXISTS sector_fund_flow_daily (
    trade_date TEXT NOT NULL,
    sector_name TEXT NOT NULL,
    net_inflow_yi REAL NOT NULL DEFAULT 0,
    source_policy TEXT NOT NULL DEFAULT '',
    source_run_id INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (trade_date, sector_name)
)
```

Add repository methods:

```python
def upsert_sector_fund_flow_daily(self, row):
    ...

def query_sector_fund_flow_series(self, end_date, sector_name, *, window_days=8):
    ...
```

Return rows with:

```python
{"date": trade_date, "sector_name": sector_name, "inflow": net_inflow_yi}
```

Add matching facade methods in `DatabaseService`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_database_service
```

Expected: OK.

---

### Task 2: Index Market Turnover And Sector Flow Into SQLite

**Files:**
- Modify: `scripts/domains/market_state/daily_metric_history_index.py`
- Test: `tests/test_daily_metric_history_index.py`

- [ ] **Step 1: Write failing tests**

Add a test where `ensure_daily_metric_history_index()` receives a snapshot containing:

```python
{
    "total_turnover": 29246.59,
    "sector_fund_flow": {
        "inflow": [{"name": "半导体", "zljlr": 12.34}],
        "outflow": [{"name": "元器件", "zljlr": -5.67}],
    },
}
```

Then assert:

```python
market_total = service.query_market_daily_total("2026-05-22")
sector_rows = service.query_sector_fund_flow_series("2026-05-22", "半导体", window_days=1)
self.assertEqual(market_total["total_turnover"], 29246.59)
self.assertEqual(sector_rows[0]["inflow"], 12.34)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_metric_history_index
```

Expected: sector fund-flow rows missing, and possibly market total not indexed from snapshot.

- [ ] **Step 3: Implement index extraction**

In `daily_metric_history_index.py`, add helpers:

```python
def _market_total_record_from_snapshot(snapshot_data, fallback_date):
    ...

def _sector_fund_flow_records_from_snapshot(snapshot_data, fallback_date):
    ...
```

Inside `ensure_daily_metric_history_index()`, after `snapshot_data` is loaded:

```python
market_total_row = _market_total_record_from_snapshot(snapshot_data, cursor)
if market_total_row:
    service.upsert_market_daily_total(market_total_row)

for row in _sector_fund_flow_records_from_snapshot(snapshot_data, cursor):
    service.upsert_sector_fund_flow_daily(row)
```

If the existing repository only has `rebuild_market_daily_total()` and not a direct upsert, add `upsert_market_daily_total()` to the facade and repository.

- [ ] **Step 4: Run tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_metric_history_index tests.test_database_service
```

Expected: OK.

---

### Task 3: Query SQLite Before JSON In Market-State Support

**Files:**
- Modify: `scripts/domains/market_state/support.py`
- Test: `tests/test_market_state_support.py`

- [ ] **Step 1: Write failing tests**

Add two tests:

1. `_load_recent_market_turnover_history_legacy_body()` should return SQLite rows and must not call `load_data_snapshot`.
2. `_load_recent_sector_flow_history_legacy_body()` should return SQLite rows and must not call `load_data_snapshot`.

Use a fake `DatabaseService` or temp SQLite db through helper injection, matching existing style in nearby tests.

Expected assertions:

```python
self.assertEqual(history, [{"date": "2026-05-21", "turnover": 29246.59}])
self.assertEqual(snapshot_calls, [])
```

and:

```python
self.assertEqual(history, [{"date": "2026-05-21", "inflow": 12.34}])
self.assertEqual(snapshot_calls, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_state_support
```

Expected: it calls `load_data_snapshot`.

- [ ] **Step 3: Implement SQLite-first lookups**

In `support.py`, import or lazily use `DatabaseService` like other market-state modules. Before the JSON loop:

```python
service = DatabaseService.sqlite_d1_compatible()
rows = service.query_market_daily_total_series(target_date, window_days=lookback_days)
if rows:
    return rows
```

For sector flow:

```python
rows = service.query_sector_fund_flow_series(target_date, sector_name, window_days=lookback_days)
if rows:
    return rows
```

Use helper injection where available so tests can provide a fake service.

- [ ] **Step 4: Run tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_state_support tests.test_database_service tests.test_daily_metric_history_index
```

Expected: OK.

---

### Task 4: Backfill 2026-05-21 / 2026-05-22 Facts And Verify Runtime

**Files:**
- Modify or create only if needed: `scripts/domains/market_state/daily_metric_history_index.py`
- Test: existing tests from Tasks 1-3

- [ ] **Step 1: Backfill local SQLite facts**

Run:

```bash
.generated/venv-py314/bin/python3.14 - <<'PY'
from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index
result = ensure_daily_metric_history_index(end_date="2026-05-22", window_days=25, max_scan_days=40)
print(result)
PY
```

Expected: indexed dates include `2026-05-21` and/or `2026-05-22`.

- [ ] **Step 2: Re-run 2026-05-22 with timing**

Run:

```bash
/usr/bin/time -p .generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-05-22 --replay
```

Expected: report generation does not spend minutes CPU-bound reading `snapshots/2026-05-21.json` for narrow history. If replay snapshot for 2026-05-22 does not exist, first run the normal command once after backfill.

- [ ] **Step 3: Confirm no large snapshot read in the hot path**

During the run, if needed:

```bash
ps -Ao pid,ppid,etime,pcpu,pmem,command | rg "daily_report_entry_demo|python3.14"
lsof -p <pid> | rg "snapshots/2026-05-21.json"
```

Expected: no persistent open read against the huge 2026-05-21 snapshot once SQLite facts exist.

- [ ] **Step 4: Run focused regression**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_state_support tests.test_mainline_history_runtime tests.test_sector_turnover_history_runtime tests.test_daily_metric_history_index tests.test_database_service
git diff --check
```

Expected: OK.

---

## PostgreSQL Migration Boundary

The later PostgreSQL migration should implement the same methods exposed by `DatabaseService`:

- `query_market_daily_total(...)`
- `query_market_daily_total_series(...)`
- `upsert_market_daily_total(...)`
- `query_sector_fund_flow_series(...)`
- `upsert_sector_fund_flow_daily(...)`
- existing mainline/new-high/turnover methods

Report logic must depend on the facade, not on SQLite file paths or raw `sqlite3` connections.

`D1SyncService` currently syncs only part of the local fact store. Expanding that sync range is a follow-up after the local runtime is fast and correct; it should include the newer mainline, turnover, new-high, price-band, and conviction mention tables without changing report callers.
