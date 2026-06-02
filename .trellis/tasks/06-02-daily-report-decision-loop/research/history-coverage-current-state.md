# History Coverage Current State

Generated on `2026-06-02` for the Daily Report Decision Loop full-attack planning update.

## Counts

| Surface | Count | First Date | Last Date |
|---|---:|---|---|
| Official full reports | 42 | 2026-03-31 | 2026-06-01 |
| Official summary reports | 37 | 2026-04-03 | 2026-06-01 |
| Replay full reports | 36 | 2026-04-03 | 2026-06-01 |
| Official snapshots | 41 | 2026-04-01 | 2026-06-01 |
| Replay snapshots | 35 | 2026-04-03 | 2026-06-01 |

## Implication

The current repository does not yet support honest 60-day or 120-day decision statistics. Those are expansion targets. Current report/statistics wording must use the actual available sample size and date range.

## Discovered Code Constraint

`scripts/report/decision_ledger.py` uses `DEFAULT_CYCLE_LENGTH_TRADE_DAYS = 25` and passes `window_days=25` / `max_rows=25` through current tracking and backtest surfaces. This explains why some current review surfaces appear as recent-25-day views even though more reports exist.

## Required Next Step

The first implementation child task should:

- compute coverage metadata for decision-ledger surfaces,
- render true sample count and date range,
- separate the recent cycle view from longer target review windows,
- prevent 60/120-day labels until source facts and settled rows support them.
