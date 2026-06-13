# Daily Decision Ledger Implementation Tasks

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first local judgment ledger slice for daily-report high-conviction samples, with tests and a stable report/replay consumption contract.

**Architecture:** Keep the first implementation inside `a-daily-report`: a focused `decision_ledger` module builds `data/decision-ledger/YYYY-MM-DD.json` and `data/decision-ledger/index.json` from the daily report's `extreme_conviction_list`. Database import and broad frontend UI work stay out of scope until the local artifact is stable and tested.

**Tech Stack:** Python 3, `unittest`, JSON artifacts, existing `scripts/` import path.

---

## Status Board

- [x] Spec and domain language written.
- [x] LLM Wiki updated for judgment-sample principles.
- [x] Local ledger data model and JSON builder.
- [x] Daily snapshot writer.
- [x] Index writer with `latest_trade_date`, `available_trade_dates`, `by_stock_code`.
- [x] State classification helpers.
- [x] 25-trading-day cycle handling.
- [x] Runtime integration point.
- [x] report/replay consumption contract placeholder.
- [x] decision-ledger contract check.
- [x] Focused Python tests.
- [x] Final verification and docs update.

## In Scope

- Generate local source artifacts under `data/decision-ledger/`.
- Use only the daily report's `extreme_conviction_list` for first-stage strong tracking.
- Keep one case per stock per 25-trading-day cycle; append mentions on repeated report appearances.
- Produce daily snapshot and index files.
- Test field completeness, repeated mentions, status classification, cycle close/open, and index shape.

## Out of Scope

- No database writes in the first local ledger slice.
- No online deploy.
- No all-watchlist strong tracking.
- No full frontend dashboard redesign.
- No new SaaS/user/subscription work.

## Task 1: Decision Ledger Core Builder

**Files:**
- Create: `scripts/report/decision_ledger.py`
- Test: `tests/test_decision_ledger.py`

- [x] Write failing tests for generating one daily snapshot from `extreme_conviction_list`.
- [x] Implement `build_decision_ledger_snapshot(...)`.
- [x] Normalize stock code/name/sector/reason fields.
- [x] Require a three-layer hypothesis shape.
- [x] Run `venv/bin/python3 -m unittest tests.test_decision_ledger -q`.

## Task 2: Mention And Cycle Rules

**Files:**
- Modify: `scripts/report/decision_ledger.py`
- Test: `tests/test_decision_ledger.py`

- [x] Add failing test: same stock in the same open 25-day cycle appends `mentions`.
- [x] Add failing test: same stock after closed 25-day cycle creates a new case.
- [x] Implement `merge_snapshot_with_previous_index(...)`.
- [x] Keep `case_id` stable inside one cycle.
- [x] Run `venv/bin/python3 -m unittest tests.test_decision_ledger -q`.

## Task 3: Validation State Helpers

**Files:**
- Modify: `scripts/report/decision_ledger.py`
- Test: `tests/test_decision_ledger.py`

- [x] Add failing test: intact stock setup plus unselected sector is `等待市场选择`.
- [x] Add failing test: sector evidence plus stock evidence is `市场选择确认`.
- [x] Add failing test: sector path lost plus stock structure broken is `真正失败`.
- [x] Implement `classify_validation_state(...)`.
- [x] Run `venv/bin/python3 -m unittest tests.test_decision_ledger -q`.

## Task 4: Cycle Acceptance Labels

**Files:**
- Modify: `scripts/report/decision_ledger.py`
- Test: `tests/test_decision_ledger.py`

- [x] Add failing tests for the five cycle acceptance labels.
- [x] Implement `classify_cycle_acceptance(...)`.
- [x] Ensure every closed 25-day case has exactly one final label.
- [x] Run `venv/bin/python3 -m unittest tests.test_decision_ledger -q`.

## Task 5: Artifact Writer

**Files:**
- Modify: `scripts/report/decision_ledger.py`
- Test: `tests/test_decision_ledger.py`

- [x] Add failing test: writer creates `data/decision-ledger/YYYY-MM-DD.json`.
- [x] Add failing test: writer creates/refreshes `data/decision-ledger/index.json`.
- [x] Implement `write_decision_ledger_artifacts(...)` with injectable root path for tests.
- [x] Keep JSON stable with sorted keys and UTF-8 text.
- [x] Run `venv/bin/python3 -m unittest tests.test_decision_ledger -q`.

## Task 6: Runtime Integration Point

**Files:**
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py` or a new focused runtime test if smaller.

- [x] Add failing test that report runtime can call the ledger writer when enabled.
- [x] Add a narrow optional input flag such as `persist_decision_ledger`.
- [x] Pass `target_date`, `extreme_conviction_list`, market/sector context, and report metadata into the writer.
- [x] Keep default behavior compatible for existing tests.
- [x] Run focused runtime tests.

## Task 7: Report/Replay Consumption Contract

**Files:**
- Modify: report/replay consumption contract only if a small existing read seam is available.
- Prefer: add source artifact expectation to existing local contract tests after local artifact exists.

- [x] Identify the smallest existing report/replay read seam.
- [x] Add test that consumed data can include decision-ledger `index.json` and latest snapshot.
- [x] Add failure test for incomplete decision-ledger contract.
- [x] Validate decision-ledger `index.json` and latest snapshot before report/replay consumption succeeds.
- [x] Keep UI page changes out of this slice.
- [x] Run focused Python unit test.

## Task 8: Final Verification

**Files:**
- Update: this task list.

- [x] Run `venv/bin/python3 -m unittest tests.test_decision_ledger -q`.
- [x] Run the focused runtime regression touched by Task 6.
- [x] Run focused Python unit test if Task 7 touched report/replay consumption.
- [x] Run `git diff --check`.
- [x] Scan changed user-visible docs for forbidden wording.
- [x] Summarize remaining follow-ups: PostgreSQL import, frontend review UI, richer trend fate automation.

## Follow-ups Not In This Slice

- [ ] Add PostgreSQL import after local artifacts are stable.
- [ ] Add frontend judgment-ledger page or panel for lifecycle review.
- [ ] Automate richer trend fate classification from Tushare 25-day bars.
- [ ] Add release/publish contract check only if a future frontend deploy path returns.

## Execution Notes 2026-05-13

- Markdown-report fallback is implemented: the ledger can be backfilled from the generated full report table when runtime structured input is not available.
- Real 2026-05-12 local artifacts were generated under ignored source path `data/decision-ledger/`.
- The first real ledger snapshot contains three high-conviction judgment samples: `601991 大唐发电`, `603007 花王股份`, `300449 汉邦高科`.
- Report/replay consumption now validates `data/decision-ledger/index.json` plus the latest snapshot.
- Turnover facts preserve existing per-stock `net_inflow_yi` values when regenerated ranking payloads do not carry richer net-inflow data.
- Full 25-trading-day trend-fate automation, PostgreSQL import, and a dedicated lifecycle panel remain follow-up work.
