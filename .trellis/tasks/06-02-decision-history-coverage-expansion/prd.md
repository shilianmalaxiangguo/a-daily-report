# Decision History Coverage Expansion

## Goal

Make historical decision review honest before expanding it. Current replay/statistics must show the actual covered sample and date range, then define how to grow from the current 25/36/41/42-day surfaces toward 60 and 120 trading days.

## Current Facts

- Official full reports: 42 trading days from `2026-03-31` through `2026-06-01`.
- Official snapshots: 41 trading days from `2026-04-01` through `2026-06-01`.
- Replay full reports: 36 trading days from `2026-04-03` through `2026-06-01`.
- Replay snapshots: 35 trading days from `2026-04-03` through `2026-06-01`.
- Current decision-ledger tracking/backtest code still uses a 25-trading-day recent-cycle default.

## In Scope

- Audit report, snapshot, replay snapshot, and decision-ledger coverage.
- Add or expose `sample_count`, `start_date`, `end_date`, and missing-fact metadata for tracking/backtest/statistics rows.
- Make rendered review text say the true covered sample instead of implying 60/120-day coverage.
- Separate "recent 25 trading day cycle" from "current covered historical sample".
- Define replay/backfill commands needed to reach 60 and 120 trading days when source facts exist.
- Add tests for coverage metadata and wording.

## Out of Scope

- Fully automated trading.
- Probability scoring or base-rate recommendation.
- Redesigning the front page.
- Adding a broad factor-mining or general backtesting framework.
- Using current-only data to fill historical fields.

## Non-goals

- Do not create fake 60/120-day evidence.
- Do not count missing review facts as hit or failure.
- Do not overwrite official reports unless explicitly requested.
- Do not conflate official report coverage with replay snapshot coverage.

## Requirements

- Coverage audit reports counts by source type:
  - official full reports,
  - official snapshots,
  - replay full reports,
  - replay snapshots,
  - decision-ledger settled rows.
- Review/statistics output must render the actual coverage:
  - sample count,
  - first covered date,
  - last covered date,
  - missing fields if any.
- Current 25-day tracking can remain as a recent-cycle view, but it must not be the only review surface if broader covered rows exist.
- 60/120-day labels are allowed only when source-dated facts support those windows.

## Acceptance Criteria

- [x] A coverage helper or equivalent output can identify the current covered sample count and date range.
- [x] Decision-ledger tracking/backtest rendering distinguishes recent 25-day cycle from current covered sample.
- [x] Tests fail before and pass after implementation for coverage metadata and no fake long-window wording.
- [x] Replay generation for a representative date completes with Python 3.14.
- [x] Report acceptance audit passes or reports exact missing facts.

## Definition of Done

- Relevant tests run with `.generated/venv-py314/bin/python3.14 -m unittest ...`.
- Relevant report/replay command runs with `.generated/venv-py314/bin/python3.14`.
- Generated report surfaces true coverage.
- No user-visible wording uses banned engineering terms from the repository terminology contract.

## Technical Approach

- Start in `scripts/report/decision_ledger.py`, where recent-cycle and backtest rendering already live.
- Prefer small helpers that compute coverage from existing index rows rather than introducing a new subsystem.
- Add tests in `tests/test_decision_ledger.py`.
- Use `.trellis/tasks/06-02-daily-report-decision-loop/research/history-coverage-current-state.md` as the factual planning baseline.

## Verification Evidence

- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/decision_ledger.py scripts/report/runtime.py tests/test_decision_ledger.py tests/test_report_runtime.py`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_decision_ledger` -> 76 tests OK.
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime` -> 137 tests OK.
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-01 --replay` -> replay report regenerated and internal consistency check passed.
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-01_A股日报_完整版_replay.md` -> passed.
- `ruff` and `mypy` are not installed in the Python 3.14 environment, so those checks could not run.

## Implementation Result

- Added `decision_coverage_summary.v1` support through `build_decision_coverage_summary`.
- The near-25-day extreme-conviction tracking table now states the full current covered sample count and date range.
- The historical backtest table now states the full current covered sample count/date range and separately says how many recent rows are displayed.
- Runtime database-backed tracking rows still compute coverage from the full decision-ledger index, not only from the displayed database row subset.
- `2026-06-01` replay output now shows: current review sample `41` rows, covering `2026-05-12` through `2026-06-01`.

## Decision (ADR-lite)

**Context**: The user pointed out that current review coverage is recent 25 days or starts around late March/early April, not 60/120 days.

**Decision**: Prioritize coverage honesty and expansion before probability/statistics claims.

**Consequences**: The system will first become trustworthy with the data it actually has, then expand historical windows without overstating evidence.
