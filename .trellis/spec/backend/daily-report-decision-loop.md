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
