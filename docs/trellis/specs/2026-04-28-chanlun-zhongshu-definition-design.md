# Chanlun Zhongshu Definition Design

Date: 2026-04-28

Scope: redesign how `a-daily-report` defines and labels zhongshu so the report can keep its practical daily rhythm while moving toward a stricter Chanlun structure. This is a design spec only; implementation will follow a separate plan after review.

## Core Decision

Use **250 daily K-lines as the structural data base**, keep the **report's main view focused on the latest 120 daily K-lines**, and use **60-minute K-lines as the Chanlun confirmation layer**.

The report must stop treating a simple daily overlapping box as a strict Chanlun zhongshu. A daily box can be a useful structure candidate, but a confirmed Chanlun zhongshu needs lower-level structure evidence.

## Why This Shape

The user wants a system built for mainline cycles, not intraday noise. The working belief is:

- A real market mainline should usually last at least 20 trading days.
- Daily K-lines are the main battlefield for mainline and position sizing.
- A 120-day view is enough for the current report surface, but not always enough to understand the prior structure behind a new zhongshu.
- A 250-day daily base gives the algorithm enough context to detect the previous confirmed structure, departures, returns, expansions, and new structure births.
- 60-minute data is coarse enough to reduce noise, but detailed enough to decompose the daily structure into subordinate swings.

Therefore:

- Daily K-lines decide the mainline cycle and candidate structure.
- 60-minute K-lines confirm whether the candidate structure deserves to be called Chanlun zhongshu.
- 30-minute, 15-minute, 5-minute, and 1-minute data stay out of the core definition for now.

## Terminology

The report will use four distinct terms.

| Term | Meaning | Can It Be Called Strict Zhongshu? |
|---|---|---|
| Daily structure box | A visible daily price range or overlap area found from daily K-lines | No |
| Daily mainline cycle | A daily cycle candidate, normally at least 20 trading days, carrying one or more market mainlines | No |
| Daily-level zhongshu candidate | A daily cycle or box long enough to deserve 60-minute confirmation | Not yet |
| Confirmed daily-level Chanlun zhongshu | A daily-level structure confirmed by 60-minute subordinate trend overlap | Yes |

Old wording like `日线中枢` must not be used for daily boxes unless the 60-minute confirmation layer has confirmed it.

## Data Windows

### Daily K-lines

- Fetch at least 250 daily K-lines for the index.
- Use the latest 120 daily K-lines for the report's main surface.
- Use the full 250 daily K-lines only for background structure:
  - previous confirmed zhongshu
  - departure from previous zhongshu
  - return to previous zhongshu
  - zhongshu expansion
  - zhongshu newborn state

### 60-Minute K-lines

- Fetch enough 60-minute K-lines to cover the 250 daily K-line background when available.
- If full coverage is unavailable, the engine should degrade explicitly:
  - keep daily structure boxes
  - mark Chanlun confirmation as `insufficient_60m_history`
  - do not silently upgrade a daily box to confirmed zhongshu

### 30-Minute And Lower

These are intentionally out of scope for the first strict definition.

- 30-minute data may later be used to refine buy points.
- 15-minute and 5-minute data may later be used for intraday execution.
- They must not affect daily-level zhongshu confirmation in the first implementation.

## Definition Pipeline

### Stage 1: Daily Structure Candidate

Input: 250 daily K-lines.

Responsibilities:

1. Detect visible daily structure boxes and current price position.
2. Detect mainline cycles of at least 20 trading days where possible.
3. Mark short boxes as `daily_structure_box`, not zhongshu.
4. Mark recent active boxes below 20 trading days as `daily_candidate_forming`.
5. Attach mainline context to candidate periods:
   - primary mainline
   - secondary mainline
   - turnover share trend
   - whether the mainline is strengthening, rotating, fading, or returning

Output fields:

```text
daily_structure_candidates[]
  start_date
  end_date
  kline_count
  high
  low
  zg_candidate
  zd_candidate
  current_position
  mainline
  mainline_state
  candidate_status
```

### Stage 2: 60-Minute Chanlun Structure

Input: 60-minute K-lines covering the daily candidate window.

Responsibilities:

1. Normalize 60-minute bars.
2. Handle K-line inclusion.
3. Detect fractals.
4. Build strokes.
5. Build segments.
6. Derive subordinate trend types.
7. Find overlap of at least three consecutive subordinate trend types.
8. Output 60-minute zhongshu structures and their ZG/ZD.

This stage is where strict Chanlun logic lives. The daily layer can propose, but this layer confirms.

Output fields:

```text
chanlun_60m_structures[]
  start_time
  end_time
  zg
  zd
  direction
  trend_type_count
  status
  departure_state
  return_state
  buy_sell_point
```

### Stage 3: Daily-Level Confirmation

A daily-level zhongshu is confirmed only when all required conditions are met.

| Condition | Rule |
|---|---|
| Daily duration | The daily candidate normally covers at least 20 trading days |
| Subordinate structure | The 60-minute layer shows at least three consecutive subordinate trend types with overlap |
| Range | The engine can output clear ZG and ZD |
| State | The engine can identify inside, departure, return, expansion, newborn, breakout, or breakdown |
| Mainline mapping | The structure can be mapped to the mainline state for that period |

If the daily duration is below 20 trading days:

- It can be `daily_candidate_forming`.
- It cannot be a confirmed daily-level Chanlun zhongshu.

If 60-minute confirmation is missing:

- It remains `daily_structure_box` or `daily_level_candidate`.
- The report must say why confirmation is missing.

## Report Contract

The report should split the old zhongshu language into two tables.

### Daily Structure Table

Purpose: show what the daily chart says visually and cyclically.

Columns:

- period
- daily box range
- daily K-line count
- mainline
- mainline state
- price position
- candidate status

Allowed statuses:

- `daily_structure_box`
- `daily_candidate_forming`
- `daily_cycle_confirmed_by_duration`
- `insufficient_duration`

### Chanlun Confirmation Table

Purpose: show whether the daily structure is confirmed by 60-minute Chanlun structure.

Columns:

- candidate period
- 60-minute confirmation status
- Chanlun ZG/ZD
- subordinate trend count
- current Chanlun state
- buy/sell point qualification
- explanation

Allowed statuses:

- `confirmed_daily_level_zhongshu`
- `forming_daily_level_zhongshu`
- `not_confirmed`
- `insufficient_60m_history`
- `structure_conflict`

## Decision Rules

### Position Sizing

Daily structure controls the broad position state.

- No 20-day daily candidate: default defensive.
- Daily candidate forming but 60-minute unconfirmed: observation only.
- Daily candidate and 60-minute confirmed inside zhongshu: defensive or light observation.
- Confirmed zhongshu plus valid 60-minute third buy: can evaluate attack qualification.
- Confirmed zhongshu breakdown or third sell: defensive or exit.

### Mainline Qualification

A mainline should not be promoted by a single daily price box.

It needs:

1. at least 20 trading days of daily relevance or a forming candidate moving toward that state,
2. turnover share support,
3. 60-minute structure confirmation or explicit explanation that confirmation is still forming.

### Current Day Handling

The current trading day is a comparison bar until closed and persisted.

- It can be used to judge position relative to ZG/ZD.
- It should not be silently counted into a historical candidate if the pipeline is using a completed-history window.
- After the next generation run, the prior current day may enter the historical window.

## 2026-04-27 Example Interpretation

Under the new design, `2026-04-14 ~ 2026-04-24` with 9 daily K-lines is not a confirmed daily-level Chanlun zhongshu.

It should be labeled:

- `daily_candidate_forming`
- daily range: `3992.41-4114.84`
- daily count: `9/20`
- Chanlun status: pending 60-minute confirmation

The report can say it is inside the candidate box, but it must not call it a confirmed daily-level zhongshu.

## Data Source Strategy

AkShare is acceptable for the first implementation.

Observed local support:

- `stock_zh_a_minute(symbol="sh000001", period="60")` returns enough 60-minute data.
- `stock_zh_a_minute(symbol="sh000001", period="30")` also returns enough data but is not selected for the core.
- 5-minute and 1-minute data are too short for long-window structure and remain out of scope.

The implementation must cache 60-minute data locally because public minute-history endpoints are not guaranteed to provide permanent history.

## Non-Goals

- Do not implement 30-minute or 5-minute execution logic in this phase.
- Do not claim strict Chanlun confirmation from daily K-line overlap alone.
- Do not render every low-level stroke or segment in the daily report.
- Do not replace the whole trading system at once.
- Do not make a new visual UI in this spec.

## Acceptance Criteria

1. The report no longer uses `日线中枢` for daily boxes without 60-minute confirmation.
2. Daily boxes below 20 K-lines are labeled as forming candidates, not confirmed zhongshu.
3. The engine can fetch and normalize 250 daily K-lines.
4. The engine can fetch and normalize enough 60-minute K-lines for the current daily candidate.
5. The report exposes both daily structure status and Chanlun confirmation status.
6. Missing 60-minute data produces an explicit degraded status.
7. 2026-04-27 renders as a 9/20 daily candidate, not confirmed zhongshu.
8. Existing daily-report sections keep conclusion-first wording and avoid formula-heavy explanations.

## References

- Chanlun 108 lessons archive: https://chanlun108.cn/
- Chanlun lesson 17: https://chanlun108.cn/chanzhongshuochan108ke/17.html
- Chanlun lesson 18: https://chanlun108.cn/chanzhongshuochan108ke/18.html
- Chanlun lesson 35: https://chanlun108.cn/chanzhongshuochan108ke/35.html

