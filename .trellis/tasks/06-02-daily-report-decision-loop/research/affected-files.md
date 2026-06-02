# Affected Files Research

- Query: Smallest implementation slice for Daily Report Decision Loop MVP.
- Scope: internal
- Date: 2026-06-02

## Recommended Minimal Slice

Implement this as a targeted extension of the existing decision-ledger path, not as a new strategy or dashboard subsystem.

The current code already has the main loop surfaces:

- `scripts/report/decision_ledger.py` builds planned participation records from markdown/candidates, classifies participation review labels, writes `data/decision-ledger/YYYY-MM-DD.json`, updates `data/decision-ledger/index.json`, and renders tracking/backtest rows.
- `scripts/report/runtime.py` persists the ledger during report generation and appends tracking/backtest lines to the report tail.
- `reports/replay/2026-06-01_A股日报_完整版_replay.md` already renders the tracking and historical backtest sections, but the current table does not expose 1-day / 3-day / 5-day follow-up performance or explicit missing/source-date fields.

Recommended MVP:

1. Extend existing decision-ledger records with explicit closed-loop metadata:
   - `schema_version: decision_ledger_record.v1` or equivalent version marker at record/case level.
   - `report_date` from the snapshot trade date.
   - `source_report_path` from `snapshot["source_report"]["path"]`.
   - `position_plan_pct` derived from planned `attack_state` values (`0%`, `50%`, `100%`) without inventing participation.
   - `position_plan_label` using the existing 0/50/100 language.
   - `planned_participation` preserved for 50%/100% records.
   - `cancellation_conditions` from planned `cancellation`, `ma20_invalidation`, and any explicit invalid/cancel fields.
   - `source_dates` with `snapshot_date`, `refill_date`, and `price_source_date`.
   - `missing_fields` for absent planned participation, source dates, review facts, or price windows.

2. Keep participation review labels fact-derived:
   - Current labels include `预演命中`, `预演作废`, `错过后方案命中`, `预演过早`, `主目标不可成交`, `等待复盘`, and `等待窗口复盘`.
   - Spec wants missing facts surfaced as `待补事实`. Minimal slice should map missing next-day fact states to `待补事实` in the new spec-facing fields/backtest output, while preserving legacy labels only where tests or existing UI still expect them.
   - Do not turn `等待复盘` into success/failure in metrics.

3. Add performance only where target-date price data exists:
   - Add a narrow helper in `scripts/report/decision_ledger.py` that computes `return_1d_pct`, `return_3d_pct`, `return_5d_pct`, and `max_drawdown_5d_pct` from daily bars bounded by the mention date and subsequent target dates.
   - Reuse existing local/fetch price paths if possible. Do not add a broad backtest framework or new external source.
   - If price data or price source date is absent, set metrics to `None` and add `price_source_date` / performance field names to `missing_fields`.

4. Extend backtest rows and rendering:
   - Add performance fields to `build_extreme_conviction_backtest_rows`.
   - Render them in `render_extreme_conviction_backtest_lines` as extra historical evidence columns, keeping the existing warning that the table is past review evidence and not tomorrow's action.
   - Keep selection quality, buy-point quality, risk-reward, execution review, and standard action as separate columns.

5. Ensure 2026-06-01 replay exposes the result:
   - Regenerate with replay mode after code changes.
   - The expected output surface is the existing tail area around the tracking/backtest sections, not the front-page final action table.

## Files To Edit

- `scripts/report/decision_ledger.py`
  - Builds normalized planned participation from nested/top-level fields at lines 500-566.
  - Creates default planned participation with `participation_window`, `attack_state`, and cancellation text at lines 569-597.
  - Merges/defaults planned participation in `_build_planned_participation` at lines 600-655.
  - Classifies participation review labels in `classify_planned_participation_review` at lines 658-820.
  - Builds next-day facts from market data in `build_participation_review_facts_from_market_fact` at lines 1015-1192.
  - Reads local/fetched daily and minute facts at lines 1856-2004.
  - Compacts review fields for the index at lines 2007-2024.
  - Builds index records in `_case_index_record` at lines 1681-1721; this is the best place to add record-level schema, report date, source path, position plan, source dates, and missing fields.
  - Builds index and cached backtest rows at lines 1724-1780.
  - Applies next-day review facts to previous records at lines 2429-2471.
  - Writes snapshot/index artifacts at lines 2474-2617.
  - Builds snapshots from the current report candidates at lines 2674-2751.
  - Builds historical backtest rows at lines 2333-2378 and renders them at lines 2381-2409; this is the smallest rendering surface for 1/3/5-day performance and missing fields.

- `scripts/report/runtime.py`
  - Persists the decision ledger through `_maybe_persist_decision_ledger` at lines 1132-1175.
  - Builds report tail tracking/backtest lines through `_build_decision_ledger_tracking_lines` at lines 1379-1415.
  - Calls ledger persistence before final report rendering at lines 3916-3941.
  - Appends decision-ledger tracking/backtest lines to the report at lines 4239-4240.
  - Only edit this file if the ledger output must carry extra metadata into report rendering; otherwise keep the MVP in `decision_ledger.py`.

- `scripts/report/report_acceptance_audit.py`
  - No likely production edit needed for MVP.
  - Use it as a verification command against the generated replay markdown.

- `scripts/daily_report_entry_demo.py`
  - No likely production edit needed.
  - CLI already supports `2026-06-01 --replay`.

## Tests To Add Or Update

- `tests/test_decision_ledger.py`
  - Existing review-label tests are at lines 1018-1104 and 1105-1127.
  - Existing market-fact review tests continue through the next block around lines 1128-1278.
  - Snapshot/index participation review coverage is at lines 1279-1458.
  - Existing tracking/backtest table tests are at lines 1505-1605 and 1606-1683.
  - Existing multi-mention/backtest behavior around lines 1950-1983 should be extended for missing facts and performance fields.
  - Existing writer review-refresh coverage around lines 2660-2692 is the best place to assert source dates and missing fact handling through `write_decision_ledger_artifacts`.

Recommended narrow tests:

1. `test_index_records_decision_loop_contract_fields`
   - Build a snapshot with explicit planned participation and `source_report`.
   - Assert index record has report date, source report path, position plan percent/label, cancellation conditions, source dates, missing fields, and preserved planned participation.

2. `test_participation_review_missing_facts_uses_waiting_fact_label`
   - Call `classify_planned_participation_review` without required next-day fact inputs.
   - Assert spec-facing status or normalized backtest review status is `待补事实`.
   - Assert it is not counted as `预演命中` or `预演作废`.

3. `test_backtest_rows_include_follow_up_performance_or_missing_fields`
   - Provide a small index/record with enough daily bars or precomputed performance facts.
   - Assert backtest row has `return_1d_pct`, `return_3d_pct`, `return_5d_pct`, `max_drawdown_5d_pct`, `price_source_date`, and `missing_fields`.
   - Add a second record without price data and assert metrics are `None` plus missing fields are visible.

4. `test_renders_backtest_performance_without_new_action`
   - Extend the existing backtest renderer assertion to include 1日/3日/5日 and 最大回撤 columns.
   - Assert rendered text still includes “不作为明日新增参与依据”.

- `tests/test_report_runtime.py`
  - Existing runtime tests stub ledger tracking/backtest output around lines 4940-5010 and 5280-5350.
  - Add/adjust one narrow assertion only if runtime wiring changes; otherwise rely on `tests/test_decision_ledger.py`.

- `tests/test_report_acceptance_audit.py`
  - No likely edit needed unless new section headings confuse the report audit.

## Verification Commands

Use Python 3.14 only:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_decision_ledger
```

If `scripts/report/runtime.py` changes:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime
```

If replay code or replay contracts change:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_replay
```

Regenerate the replay report:

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-01 --replay
```

Audit the generated replay markdown:

```bash
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-01_A股日报_完整版_replay.md
```

Optional direct artifact inspection after replay:

```bash
rg -n "重点观察历史回测表|1日|3日|5日|最大回撤|待补事实|不作为明日新增参与依据" reports/replay/2026-06-01_A股日报_完整版_replay.md data/decision-ledger/index.json
```

## Risks / Non-goals

- Do not add a general backtesting framework, dashboard, factor miner, broker/execution model, trade-cost model, or new data source for this MVP.
- Do not use current-only facts to fill 2026-06-01 replay fields. If the source cannot prove target-date price/fact provenance, keep the metric empty and record the missing field.
- Do not collapse selection quality, buy-point quality, risk-reward, execution review, and standard action into one success label.
- Do not let performance fields create a new next-day action. The backtest table must remain historical review evidence.
- Current artifacts show `reports/replay/2026-06-01_A股日报_完整版_replay.md` already contains tracking/backtest tables around lines 1954-2024, but existing rows show `等待复盘` / `等待事实` and do not expose 1/3/5-day performance columns.
- `data/decision-ledger/index.json` currently has `extreme_conviction_backtest_rows`, but sampled rows lack `source_dates`, `missing_fields`, `price_source_date`, and follow-up performance fields.
