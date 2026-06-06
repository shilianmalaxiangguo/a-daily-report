# Daily Report Decision Loop

> The daily report is the ship; quantitative work is the instrument panel. Do not reverse that relationship.

## Purpose

The daily report must evolve from a readable market explanation into an auditable trading decision system. Every optimization should strengthen the loop:

1. produce a judgment,
2. rehearse tomorrow's participation plan,
3. review whether the rehearsal worked,
4. revise one rule or condition from the evidence.

The report should not become a traditional fully automated strategy first. Quantification serves the existing decision surface by measuring whether its judgments, windows, samples, and position choices actually worked.

## In Scope

- Daily report structure and backend payload contracts for decision review.
- Judgment ledger fields for mainline evidence, participation windows, sample tiers, position choices, review labels, and short-horizon performance.
- Rules for converting qualitative trading judgment into auditable fields.
- Replay behavior for historical reports, including same-date facts and explicit missing-data labels.
- Acceptance checks that keep final action, process evidence, and review evidence separated.
- Historical coverage metadata for every review/statistics surface.

## Out Of Scope

- A fully automated buy/sell system.
- Factor mining, broad backtesting framework work, broker execution, trade-cost modeling, or live-trading stability work.
- Replacing the existing report contract, reasoning contract, or mainline attack evidence design.
- Adding new data sources only for future metrics before the current loop can review existing judgments.
- Claiming 60/120-day review evidence when the source facts do not cover those windows.

## Non-goals

- Do not make score output look more certain than the underlying facts.
- Do not let performance statistics create a new trade action when the original report did not provide a valid participation plan.
- Do not collapse stock selection quality, buy-point quality, missed-entry handling, and risk-reward into one success label.
- Do not optimize wording while leaving the judgment unreviewable.
- Do not hide a short sample behind long-window wording.

## Done Definition

A report optimization follows this spec when:

- The front page can answer: participation qualification, mainline, tomorrow action, cancellation condition, and prior rehearsal result.
- Each high-conviction item has a machine-readable planned participation record.
- Each reviewed item has an explicit review label derived from next-day facts.
- Ledger records can compute 1-day, 3-day, and 5-day follow-up performance without using current-day facts for historical dates.
- Replay output states which fields came from official snapshots, which came from target-date refill, and which remain missing.
- Statistics and tracking surfaces state the true sample count and covered date range.

## Current Historical Coverage Rule

As of `2026-06-02`, the repository has:

- 42 official full daily reports from `2026-03-31` through `2026-06-01`.
- 41 official snapshots from `2026-04-01` through `2026-06-01`.
- 36 replay full reports from `2026-04-03` through `2026-06-01`.

Any report or statistics surface may summarize only the rows that are actually present and auditable. If the underlying data covers 25, 36, 41, or 42 trading days, the rendered text must say that exact scope or use a neutral phrase such as "current covered sample".

60-day and 120-day windows are expansion targets. They are allowed only after source facts and settlement rows cover those windows. Until then, write the window as a target or missing coverage, not as current evidence.

## Scenario: Decision Loop Contract

### 1. Scope / Trigger

Use this contract when changing:

- daily report front-page conclusions,
- action-plan rendering,
- decision-ledger records,
- participation review logic,
- replay report reconstruction,
- quantification or dashboard metrics derived from report judgments.

### 2. Signatures

#### `decision_ledger_record.v1`

```python
{
    "schema_version": "decision_ledger_record.v1",
    "report_date": "YYYY-MM-DD",
    "source_report_path": "reports/...md",
    "market_participation_qualification": "qualified | not_qualified | incomplete",
    "position_plan_pct": 0 | 50 | 100,
    "position_plan_label": "0%不参与 | 50%标准进攻 | 100%核心进攻",
    "mainline": "str | None",
    "mainline_attack_evidence_score": "int 0..5 | None",
    "mainline_attack_evidence_labels": ["str"],
    "sample_tier": "high | middle | low | missed | observation | old_position",
    "trend_chain_position": "leader | same_chain | laggard | crossline | unknown",
    "planned_participation": "planned_participation.v1 | None",
    "cancellation_conditions": ["str"],
    "source_dates": {
        "snapshot_date": "YYYY-MM-DD | None",
        "refill_date": "YYYY-MM-DD | None",
        "price_source_date": "YYYY-MM-DD | None"
    },
    "missing_fields": ["str"]
}
```

#### `planned_participation.v1`

```python
{
    "window": "09:30-09:35 | 09:50-10:10 | 14:30-14:55 | no_trade",
    "position_plan_pct": 0 | 50 | 100,
    "action": "participate | wait | skip | reduce | exit",
    "confirm_conditions": ["str"],
    "cancellation_conditions": ["str"],
    "missed_entry_plan": "str | None",
    "invalid_price": "float | str | None",
    "risk_reward_ratio": "float | None"
}
```

#### `participation_review.v1`

```python
{
    "schema_version": "participation_review.v1",
    "report_date": "YYYY-MM-DD",
    "review_date": "YYYY-MM-DD",
    "review_status": "预演命中 | 预演作废 | 错过后方案命中 | 预演过早 | 待补事实",
    "fact_inputs": {
        "auction_matched": "bool | None",
        "first_minutes_accepted": "bool | None",
        "board_sealed": "bool | None",
        "reseal_success": "bool | None",
        "sector_supported": "bool | None",
        "cancellation_triggered": "bool | None",
        "primary_unavailable": "bool | None",
        "missed_action_worked": "bool | None"
    },
    "performance": {
        "return_1d_pct": "float | None",
        "return_3d_pct": "float | None",
        "return_5d_pct": "float | None",
        "max_drawdown_5d_pct": "float | None"
    },
    "missing_fields": ["str"]
}
```

#### `decision_coverage_summary.v1`

```python
{
    "schema_version": "decision_coverage_summary.v1",
    "surface": "tracking | backtest | statistics | probability",
    "sample_count": "int >= 0",
    "start_date": "YYYY-MM-DD | None",
    "end_date": "YYYY-MM-DD | None",
    "available_report_count": "int >= 0",
    "available_snapshot_count": "int >= 0",
    "available_replay_count": "int >= 0",
    "target_window_days": "25 | 60 | 120 | None",
    "coverage_status": "covered | partial | missing",
    "missing_fields": ["str"]
}
```

#### `five_judgment_statistics.v1`

```python
{
    "schema_version": "five_judgment_statistics.v1",
    "sample_count": "int >= 0",
    "missing_fact_count": "int >= 0",
    "start_date": "YYYY-MM-DD | None",
    "end_date": "YYYY-MM-DD | None",
    "rows": [
        {
            "judgment_type": "market_state | mainline | core_candidate | participation_rehearsal | cancellation_condition",
            "label": "str",
            "metric_definition": "str",
            "sample_count": "int >= 0",
            "correct_count": "int >= 0",
            "wrong_count": "int >= 0",
            "missing_fact_count": "int >= 0",
            "accuracy_pct": "float 0..100 | None",
            "start_date": "YYYY-MM-DD | None",
            "end_date": "YYYY-MM-DD | None",
            "latest_mistake": "str",
            "missing_fields": ["str"]
        }
    ]
}
```

### 3. Contracts

- Final action must be easier to find than process evidence.
- Final action must include `position_plan_pct`, a participation window or `no_trade`, confirmation conditions, and cancellation conditions.
- A 0% result is valid only when the report explains no qualified target, weak market, invalid trend chain, failed cancellation condition, account mismatch, old-position handling, or incomplete key data.
- 50% and 100% results require a planned participation record. If no record exists, render the item as observation and record the missing field.
- Review labels must be derived from explicit next-day facts. If facts are missing, use `待补事实` instead of inventing a result.
- Metrics may summarize past judgments, but they must not create tomorrow's action without the report action contract.
- Historical replay must preserve target-date boundaries through `report_date`, `review_date`, `source_dates`, and `missing_fields`.
- Every tracking, backtest, statistics, or probability surface must carry `sample_count`, `start_date`, and `end_date` or explicitly mark coverage as missing.
- A long-window label such as 60-day or 120-day is valid only when source facts and decision-ledger settlement rows cover that window.
- If runtime renders recent rows from a database query, coverage metadata must still be computed from the full decision-ledger index, not from the displayed row subset.
- Five-judgment statistics must render exactly five rows: market state, mainline, core candidate, participation rehearsal, and cancellation condition.
- Five-judgment statistics must read explicit `judgment_reviews` first. Limited fallback is allowed only from auditable ledger fields: `validation` for mainline continuation, `selection_result` for core candidate visibility, and `participation_review` for participation rehearsal plus cancellation condition.
- Missing facts must not count as correct or wrong. If a row has no settlement evidence, keep `accuracy_pct` null and render it as `待补事实`.
- Market-state accuracy requires explicit market-state settlement evidence. Do not infer it from `market_branch` wording alone.
- Core-candidate settlement must use the ordered first candidate as the primary target. Backup, catch-up, or follower visibility may appear in `actual`, but it cannot make the row correct when the primary target fails, is absent from next-day attention, or has a failed participation review.
- Core-candidate settlement must read both newly loaded next-day price facts and existing `participation_review` facts for the primary target. Re-running settlement for the same `report_date` and `judgment_type` must replace stale resolved rows instead of preserving a previously wrong result.
- Core-candidate summary tables may compact long `actual` text, but the settled detail row must keep the primary target outcome, stronger same-theme leader when detectable, and visible backup/follower facts separated from the reason column.
- The report front page must separate the daily decision loop into three surfaces: recent five settled trading days accuracy, previous trading day settlement, and current trading day judgment. For a `2026-06-01` replay, the previous settlement date is `2026-05-29`; the `2026-06-01` judgments wait for the next trading day before they can enter the accuracy denominator.
- The previous trading day settlement table must contain only resolved correct/wrong rows. Rows still missing settlement facts must move to a separate unresolved section so the settlement table never mixes completed correction with missing evidence.
- Current trading day judgment rows may state today's market state, mainline, core candidates, participation rehearsal, and cancellation condition, but they must not be counted as correct or wrong until settlement facts exist.
- Cancellation-condition settlement may use same-next-day participation facts. Later 3-day or 5-day return gaps must not block judging whether "do not buy / stay empty / do not chase" avoided an invalid participation.

### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| `position_plan_pct` is not 0, 50, or 100 | Reject the record or downgrade to incomplete before rendering |
| 50% or 100% has no `planned_participation` | Render as observation; record missing `planned_participation` |
| `planned_participation.window` is outside the allowed windows | Treat as invalid participation plan |
| Review facts are missing | Use `待补事实`; do not count as hit or failed rehearsal |
| Historical replay uses a current-only data source | Stop using that source for the historical field; record the missing field |
| Performance metric has no price source date | Keep metric null and record missing `price_source_date` |
| Mainline score exists without evidence labels | Keep score out of the user-facing report until labels are available |
| Statistics text claims 60/120 days but coverage is shorter | Render the true coverage or mark the long window as a target only |
| Coverage has reports but no snapshots for a date | Keep the date in report coverage but record missing snapshot facts |
| Runtime displays only database recent rows | Render the display window and the full covered sample separately |
| Five-judgment row has missing settlement fields | Exclude it from the accuracy denominator and increment missing facts |
| Five-judgment table has more or fewer than five rows | Treat as a contract violation |
| Market-state row has only a qualitative report label | Keep it as `待补事实`; do not infer correctness |
| Core-candidate first target fails while backup/follower enters attention | Mark core candidate wrong; put backup/follower visibility in `actual`, not in correctness |
| Core-candidate row already has a stale resolved result | Recompute and replace the same `report_date` plus `judgment_type` row from latest auditable facts |
| Report date has a previous trading day | Render the previous trading day's five judgment settlement before today's new five judgment rows |
| Previous trading day has only partial settlement facts | Render resolved rows in the settlement table and missing rows in a separate unresolved section |
| Current trading day judgment has no next-day facts yet | Render the judgment and verification point, but do not count it in accuracy |
| Cancellation trigger is confirmed but 3-day/5-day return facts are missing | Settle the cancellation condition from the next-day invalidation facts and keep later performance fields out of this accuracy denominator |

### 5. Good / Base / Bad Cases

| Case | Input | Expected Output |
|---|---|---|
| Good high-conviction plan | mainline confirmed, explicit window, invalid price, missed-entry plan | 50% or 100% planned participation plus review eligibility |
| Base observation | candidate has structure but no valid participation window | 0% observation with missing or unmet conditions |
| Good missed-entry review | core target unavailable, fallback plan worked | `错过后方案命中` |
| Good short coverage label | 36 replay reports available | Render "current covered sample: 36 trading days" or equivalent |
| Good database recent rows | 41 covered ledger rows, 25 rows displayed from database | Render 41 covered rows/date range and state the table displays the recent 25-day cycle |
| Good five-judgment table | explicit `judgment_reviews` plus participation review rows | Render five rows with independent accuracy and mistake text |
| Base five-judgment table | no market-state settlement evidence | Market-state row renders `待补事实` and does not affect accuracy |
| Bad fake precision | report shows 0.00% or exact metric without source date | metric removed or marked missing |
| Bad language-only judgment | strong wording exists but no fields | no performance credit until fieldized |
| Bad five-judgment inference | market state inferred from `market_branch` text | keep missing until settlement evidence exists |
| Bad long-window claim | only 42 official reports available but text says 120-day review | replace with true coverage and mark 120-day as expansion target |

### 6. Tests Required

When implementation changes this contract, add or update tests that assert:

- renderer output shows final action before process evidence,
- ledger records preserve `position_plan_pct`, participation window, and cancellation conditions,
- review labels only appear when required fact inputs exist,
- replay reports keep target-date facts separate from current facts,
- performance windows use 1-day, 3-day, and 5-day target-date price data,
- missing fields remain visible instead of becoming fake numeric values,
- statistics and tracking surfaces render the true covered sample count and date range,
- five-judgment statistics render exactly five rows with missing facts outside the accuracy denominator,
- front-page daily judgment panel renders recent five settled trading days, previous trading day settlement, and current trading day judgment separately,
- decision-ledger index records preserve `validation`, `selection_result`, and `judgment_reviews` when present,
- database-backed tracking rows still render coverage from the full ledger index,
- 60/120-day wording is not rendered until coverage supports it.

For a report behavior change, also run a replay sample and the report acceptance audit against the generated replay markdown.

### 7. Wrong vs Correct

#### Wrong

```text
The report says a stock is very strong, then later the metric table marks it as a successful judgment.
```

Why wrong: strong wording is not an auditable decision. The record does not identify the participation window, position plan, cancellation condition, or review facts.

#### Correct

```text
The report stores a 50% planned participation record with a 09:50-10:10 window, confirmation conditions, cancellation conditions, and a missed-entry plan. The next-day review uses explicit facts to label the rehearsal result.
```

Why correct: the decision can be replayed, reviewed, and measured without changing the original trading context.

#### Wrong

```text
A statistics table says it reviewed 120 days because that is the desired horizon, while only 42 official reports exist.
```

Why wrong: target horizon is not current evidence. It makes the sample look stronger than it is.

#### Correct

```text
The table states that the current covered sample is 42 trading days from 2026-03-31 through 2026-06-01, and lists 60/120 days as expansion targets.
```

Why correct: the user can separate current evidence from the next data-expansion objective.

## Scenario: Opportunity Comparison Snapshot Sources

### 1. Scope / Trigger

Use this contract when the report compares an existing holding against a new target, renders an `opportunity_comparison.v1` table, or downgrades 50% / 100% output because risk prices or risk-reward are incomplete.

### 2. Signatures

Runtime comparison builders consume existing target-date snapshot data only:

```python
_runtime_opportunity_comparison(
    data: dict,
    selected_position_candidate: dict,
    position_decision: dict,
    market_research_snapshot: dict,
) -> dict
```

The comparison output keeps the report-level contract:

```python
{
    "schema_version": "opportunity_comparison.v1",
    "old_position": {...},
    "new_target": {...},
    "additional_target_comparisons": [
        {"schema_version": "opportunity_comparison.v1", "new_target": {...}, "comparison": {...}}
    ],
    "comparison": {...},
}
```

### 3. Contracts

- The selected target is not the only valid comparison row. If the approved spec names a calibration target that already exists in the same target-date snapshot, the table must include it even when the runtime-selected display target has moved to another observation anchor.
- Extra comparison rows may come from existing snapshot sources such as `extreme_conviction_list`, `candidate_snapshot.extreme_conviction_list`, `display_observation_candidates`, `watchlist`, `candidates`, `hot_rank_top50`, `hot_rank_top30`, `integrated_hot_list`, `turnover_rank`, or `turnover_over_100b`.
- Historical replay must not add a new live data source only to fill the table. If the row is not in target-date facts, keep it missing and report the risk.
- When a candidate source has only name/code or a stale sector such as `未归类`, enrich display fields from `stock_full_info[code]` in the same snapshot. Use `close` as the observation/current price and `industry` / `所属行业` as the display line when candidate sector is missing.
- Enrichment must fill missing price facts; it must not create a positive participation result. Missing MA5, MA10, VWAP, invalidation, or risk-reward still caps the row at observation/no new participation.
- When the extra target is in the same line as the selected target and has no explicit role, label it as a same-line comparison candidate rather than a new core.

### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| Selected target has incomplete risk prices | Render observation/no new participation and record missing fields |
| Spec-required comparison target exists only in `candidates` or hot/turnover lists | Include it and enrich from same-date `stock_full_info` |
| Candidate sector is `未归类` but stock info has an industry | Render the stock-info industry for comparison |
| Extra target has no MA5/MA10/VWAP or invalidation | Show `-` for missing risk prices and keep risk-reward as incomplete |
| Historical replay lacks the target in all same-date facts | Do not fetch current data; keep the row absent or explicitly missing |

### 5. Good / Base / Bad Cases

| Case | Input | Expected Output |
|---|---|---|
| Good replay calibration | 华天科技 appears in `candidates` and `stock_full_info` but not `extreme_conviction_list` | Table includes 华天科技 with target-date close and observation-only conclusion |
| Base selected observation | Runtime selects 长电科技 as observation anchor with incomplete risk prices | Table keeps 长电科技 observation-only |
| Bad list-only lookup | Extra rows search only `extreme_conviction_list` | Spec-required target disappears from the table |
| Bad live refill | Replay calls a current-only quote source to fill missing MA prices | Reject the data for historical comparison |

### 6. Tests Required

- `tests.test_report_runtime.ReportRuntimeTest.test_runtime_opportunity_table_keeps_huatian_calibration_candidate`
- `tests.test_candidate_execution_contracts` for risk price comfort and risk-reward boundaries
- `tests.test_report_acceptance_audit` for positive 50% / 100% wording with missing comparison or incomplete risk/reward
- A generated replay report plus `scripts/report/report_acceptance_audit.py` when the rendered table changes

### 7. Wrong vs Correct

#### Wrong

```text
Only search the final extreme-conviction list for extra comparison rows, so a target that exists in same-date hot-list/candidate facts disappears from the opportunity table.
```

#### Correct

```text
Search existing target-date candidate, hot-list, turnover, and stock-info facts; render the target as a comparison row, then keep it observation-only when risk prices are incomplete.
```

## Scenario: Appendix Fact Normalization And Current Target Priority

### 1. Scope / Trigger

Use this contract when changing daily report appendix sections, market-analysis
nodes, process-evidence tables, quant-environment rendering, or final
observation target panels.

This scenario exists to prevent four report-output failures:

- flat sector turnover history rendered as duplicate zero-share rows,
- absolute turnover wording hiding target-date shrinkage facts,
- no-trade process rows retaining stale intraday participation evidence,
- stale candidate records overriding the current resolved observation target.

### 2. Signatures

`recent_sector_turnover_history` may arrive in grouped or flat form:

```python
[
    {
        "sector_name": "电力",
        "history": [
            {"date": "YYYY-MM-DD", "turnover_share_pct": 2.8},
            {"date": "YYYY-MM-DD", "turnover_share_pct": 3.5},
        ],
    },
    {"date": "YYYY-MM-DD", "sector_name": "半导体", "turnover_share_pct": 5.8},
]
```

Market turnover comparison may use direct market history or an existing
target-date Top50 share series:

```python
{
    "total_turnover": 27791.64,
    "market_turnover_history": [
        {"date": "YYYY-MM-DD", "turnover": 32643.59},
    ],
    "top50_turnover_share_series": {
        "rows": [
            {"trade_date": "YYYY-MM-DD", "market_amount_yi": 31531.25},
            {"trade_date": "YYYY-MM-DD", "market_amount_yi": 27791.64},
        ]
    },
}
```

Current observation target priority:

```python
[
    "final_target_resolution.watch_target",
    "market_research_snapshot.selected_position_candidate",
    "selected_position_candidate",
    "current_core_candidate",
    "decision-ledger fallback only when no current candidate context exists",
]
```

No-trade process rows must normalize derived fields before rendering:

```python
{
    "participation_window_type": "no_trade",
    "position_plan_pct": 0,
    "auction_script": "只观察，不新增参与",
    "first_minutes_script": "只观察，不新增参与",
    "board_script": "只观察，不新增参与",
    "reseal_script": "只观察，不新增参与",
}
```

### 3. Contracts

- Sector-turnover trend builders must normalize mixed flat/grouped history by
  sector before computing trend rows.
- Top-N sector turnover output must compute all normalized sector candidates,
  sort by latest positive share, and only then slice the display list.
- A sector with target-date positive share must not render as `0.0%` or
  `待累计` because the input used flat rows.
- Market-analysis volume text must prefer target-date relative comparison
  labels from `build_turnover_comparison(...)` when available. The absolute
  turnover condition may follow as context, but it must not hide continuous
  shrinkage or pullback.
- If `market_turnover_history` is missing but
  `top50_turnover_share_series.rows[*].market_amount_yi` is present for the
  target date, use that existing same-date series before falling back to
  absolute-only wording.
- Quant-environment rendering must support both nested
  `{"environment": {...}}` and detector-top-level `{summary, modes, action}`
  payloads.
- Generic no-trade process rows without a stock identity, or repeated rows that
  add no new price/window/cancellation facts, must be compacted before the
  appendix table is rendered.
- A no-trade process row must not keep stale `50%`, timed entry windows,
  auction/reseal participation scripts, or board-action wording.
- Final decision panels and appendix observation anchors must prefer the
  current resolved target over same-day stale ledger or scorecard fallbacks.
- Current observation-only rows still count as current context. Do not refill
  the panel with a stale core candidate merely because the current rows are not
  participating.

### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| `recent_sector_turnover_history` contains flat rows | Group by sector, sort each history by date, then compute trend |
| Same sector appears in grouped and flat input | Merge by sector identity and avoid duplicate display rows |
| More than five sectors are available | Rank all computed sectors by latest share before slicing Top 5 |
| Latest sector share is positive | Render the latest share and trend sequence, not `0.0%` / `待累计` |
| Direct market history is absent but Top50 series has `market_amount_yi` | Build relative turnover comparison from the existing target-date series |
| Relative comparison says turnover is shrinking while absolute level is high | Render shrinkage/pullback first, then absolute condition |
| Quant detector returns top-level `summary`, `modes`, `action` | Render the detected summary and action instead of `待识别` |
| No-trade row has no stock identity and repeats generic scripts | Drop the duplicate row from process evidence |
| No-trade row has stock identity but stale timed scripts | Keep the row only after rewriting scripts to observation-only text |
| Final target resolution names one watch target | Use that target for T-116-style panels and appendix anchors |
| Ledger fallback names a different stock while current context exists | Keep the current target; ledger data remains fallback only |

### 5. Good / Base / Bad Cases

| Case | Input | Expected Output |
|---|---|---|
| Good flat sector history | Flat `电力` and `半导体` rows with positive shares | One row per sector with real share sequence |
| Good Top 5 ranking | Six normalized sectors where the sixth input row has the highest latest share | Highest latest-share sectors appear after sorting, independent of input order |
| Base short sector history | Only one positive day for a sector | Render latest share and mark trend as pending or insufficient, without duplicating the sector |
| Good shrinkage wording | Current turnover is high but recent target-date series falls sharply | Volume line starts with continuous pullback/shrinkage label |
| Good quant payload | Detector returns top-level action advice | Quant appendix renders current summary and action advice |
| Good observation target | Runtime resolves `豫能控股(001896)` while stale fallback has `上海石化(600688)` | Current panel and appendix anchor render `豫能控股` |
| Bad flat-sector handling | Flat rows are treated as grouped rows with missing `history` | Duplicate sectors render `0.0%` and `待累计` |
| Bad absolute-only volume | `27791.64亿元` is called abundant without mentioning sharp pullback | User cannot see the shrinkage fact |
| Bad stale process evidence | `no_trade` row still shows `50%` or timed entry scripts | Report implies a participation plan that no longer exists |
| Bad stale target fallback | Same-day ledger target replaces runtime-resolved target | Process evidence contradicts the final observation target |

### 6. Tests Required

When these surfaces change, add or update tests that assert:

- `tests.test_market_activity_domain_report_sections` covers flat sector
  history normalization, deduplication, and non-zero latest shares.
- `tests.test_sector_fund_flow_enhancer` covers quant-environment top-level and
  nested payload shapes.
- `tests.test_market_analysis_builder` covers relative turnover shrinkage from
  both `market_turnover_history` and `top50_turnover_share_series`.
- `tests.test_two_market_turnover_node_runtime` covers target-date fallback
  history extraction from existing Top50 series rows.
- `tests.test_candidate_selection_stage` covers no-trade process-row compaction
  and stale script removal.
- `tests.test_report_runtime` and `tests.test_front_page_v2_renderer` cover
  current target priority over stale fallback records.

For a rendered-report behavior change, also run the narrow replay command for
the target date when the required historical snapshot exists.

### 7. Wrong vs Correct

#### Wrong

```python
for item in rows[:5]:
    build_sector_turnover_trend(item)
```

Why wrong: flat rows do not have grouped `history`, and slicing before ranking
can drop the strongest latest-share sector.

#### Correct

```python
normalized = _normalize_sector_turnover_history_rows(rows)
summary_rows = [build_sector_turnover_trend(item) for item in normalized]
summary_rows = [row for row in summary_rows if row.latest_share_pct > 0]
summary_rows = sorted(summary_rows, key=lambda row: row.latest_share_pct, reverse=True)[:5]
```

Why correct: every sector is computed once, ranked by current share, and only
then limited for display.

#### Wrong

```text
量能水平: 27791.64亿元，量能充沛，但赚钱效应不足
```

when same-date history shows a large turnover pullback.

#### Correct

```text
量能水平: 27791.64亿元，成交额冲高后回落；量能充沛，但赚钱效应不足
```

Why correct: the user sees both the relative contraction and the absolute
context.

## Scenario: Sniper Target Derivation Packet

### 1. Scope / Trigger

Use this contract when changing daily-report final target resolution, front-page
target explanation, candidate-quality process evidence, action-plan rendering,
appendix observation anchors, or report acceptance checks.

### 2. Signatures

Runtime must build and store one canonical packet after
`final_target_resolution` exists:

```python
{
    "schema_version": "sniper_target_derivation.v1",
    "target_date": "YYYY-MM-DD",
    "canonical_target": {"code": "001896", "name": "豫能控股", "role": "观察对象"},
    "final_action": {
        "position_pct": 0,
        "action": "只观察，不新增参与",
        "reason": "str",
    },
    "steps": [
        {
            "step_id": "T0",
            "label": "原始候选",
            "source": "execution_stage_context.best_stock",
            "candidate": {"code": "600688", "name": "上海石化"},
            "role": "过程候选",
            "decision": "被替换",
            "reason": "最终解析未选为观察对象",
        },
        {
            "step_id": "T3",
            "label": "最终对象解析",
            "source": "final_target_resolution.watch_target",
            "candidate": {"code": "001896", "name": "豫能控股"},
            "role": "观察对象",
            "decision": "最终",
            "reason": "str",
        },
    ],
    "warnings": ["str"],
    "compact_ascii": ["str"],
    "full_ascii": ["str"],
}
```

Store the same packet under:

- `data["sniper_target_derivation"]`
- `execution_stage_context["sniper_target_derivation"]`
- `market_research_snapshot["sniper_target_derivation"]`

### 3. Contracts

- `canonical_target` is the only final observation target for final-action
  surfaces. It must prefer `final_target_resolution.watch_target`, then
  `display_target`, then `new_entry_target`, then the selected/current
  candidate.
- Front-page final-target solution must render the packet's compact ASCII chain.
- Appendix must render the packet's full ASCII chain before process tables.
- Candidate-quality and action-plan process evidence may render other candidates
  only as role-labeled nodes such as `过程候选`, `被替换`, `备选观察`, or
  `仅过程证据`.
- A stale `best_stock`, `watch_anchor`, or prebuilt
  `candidate_quality_panel_fields` value must not become a final observation
  target when the packet canonical target differs.
- Current selected/current-core candidates are valid observation context even
  when position is 0%. Do not refill them from stale process candidates solely
  because the current result is observation-only.
- Acceptance audit must compare the rendered final observation target with the
  derivation-chain final target. Process candidates may differ; the final target
  may not.

### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| `best_stock/watch_anchor` is 上海石化 and `final_target_resolution.watch_target` is 豫能控股 | Render 豫能控股 as the only final observation target; render 上海石化 only as `过程候选 / 被替换` |
| Candidate-quality prebuilt fields contain a stale local stock | Replace final panel identity with `canonical_target`; keep stale stock only as process evidence when the packet has that node |
| Front page receives the packet | Render compact ASCII before or inside the final-target explanation |
| Appendix receives the packet | Render full ASCII chain before detailed process tables |
| Acceptance audit sees final target and chain target differ | Return `sniper_target_derivation_mismatch` |

### 5. Tests Required

- Runtime packet build/store tests for `sniper_target_derivation.v1`.
- Runtime full-report test where local process candidate differs from the
  canonical target.
- Front-page renderer test for compact chain consumption.
- Candidate-quality/action-plan renderer test that keeps non-final candidates as
  process evidence.
- Acceptance audit tests for matching and mismatching chain final targets.

## Full Attack Roadmap

### Phase 1: Honest Coverage And Stable Closed Loop

Every daily report must contain:

- participation qualification,
- mainline and attack evidence,
- final next-day action,
- cancellation condition,
- yesterday rehearsal review,
- one rule correction when evidence requires it,
- true coverage count/date range for review tables.

### Phase 2: Judgment Ledger

Backfill currently available reports into structured records first. Track:

- mainline attack evidence score,
- participation window hit rate,
- high-conviction 1-day / 3-day / 5-day performance,
- rehearsal hit, invalidation, early, and missed-entry outcomes,
- 0% / 50% / 100% result distribution,
- high / middle / low sample rotation outcomes,
- missed-entry plan versus chasing outcome.

After the current covered sample is reliable, expand toward 60 and 120 trading days only with source-dated facts.

### Phase 3: Decision Instrument Panel

Only after the ledger is useful, add probability and base-rate views that support the report:

- historical win rate by position plan,
- drawdown by sample tier,
- mainline score versus next-day continuation,
- participation window quality,
- missed-entry plan quality.

These views support the next report. They do not replace the report's action contract.
