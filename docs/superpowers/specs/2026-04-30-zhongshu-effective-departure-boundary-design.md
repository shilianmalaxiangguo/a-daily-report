# Zhongshu Effective Departure Boundary Design

Date: 2026-04-30

## Context

The current daily platform/Zhongshu visual engine can retrospectively extend a platform to include the first strong leaving day. The Shanghai Composite case exposes the problem:

- On `2026-04-08`, the actionable view should be that `2026-03-23 ~ 2026-04-07` is the platform and `2026-04-08` is the upward departure day.
- In the later `2026-04-29` retrospective chart, the current engine can show `2026-03-23 ~ 2026-04-08` as one platform because the completed trend type still overlaps the prior core.

That behavior is structurally explainable, but it is wrong for this system's primary use. The Zhongshu model is the root of the trading decision system, so it must not use future structure completion to swallow a day that was already an effective departure from the platform.

The design decision is: **effective departure has priority over retrospective trend-type extension**.

## Goals

1. Keep platform boundaries consistent with actionable trading interpretation.
2. Prevent effective breakout/downbreak days from being absorbed back into the prior platform.
3. Preserve confirmed small running platforms when price has not effectively departed their envelope.
4. Keep tail candidate platforms, such as Longpan Technology `603906`, compatible with the same boundary rule.
5. Make failed departure/returning moves explicit instead of silently merging them back.

## Non-Goals

- Do not add one-off date-specific fixes for `2026-04-08`.
- Do not remove all retrospective diagnostics. Retrospective evidence can be recorded as metadata, but it must not drive the default decision boundary.
- Do not classify a departure day as a new confirmed platform by itself.
- Do not use the platform core range alone as the departure boundary.

## Core Rule

The platform core range and platform envelope have different jobs:

- **Core range** (`zg / zd`) defines the overlap of completed movement types.
- **Envelope range** (`visual_high / visual_low` or `segment_high / segment_low`) defines the price area that still belongs to the platform's movement digestion.

Effective departure is judged against the **platform envelope**, not only the core range.

### Departure States

For an upward departure from a platform:

- `departure_warning`: close is above the platform envelope high.
- `departure_confirmed`: the whole K-line is above the platform envelope high, i.e. `low > envelope_high`.

For a downward departure:

- `departure_warning`: close is below the platform envelope low.
- `departure_confirmed`: the whole K-line is below the platform envelope low, i.e. `high < envelope_low`.

When a departure is confirmed, the platform boundary is cut at the trading day before the first unresolved departure warning in that leaving sequence.

If there is a connector or tail movement already separated by the base platform sequence, the connector remains outside the platform; the boundary rule must not pull it back into the platform just because later trend types overlap.

## Shanghai Composite Replay

### Prior Platform Departure

The platform before the March decline has envelope roughly `3947.42 ~ 4197.23`.

- `2026-03-20`: close `3957.05` is near the lower envelope. It is a warning/pressure day, but not a clean envelope departure.
- `2026-03-23`: high `3906.62` is below envelope low `3947.42`. This is confirmed downward departure.

Therefore `2026-03-23` must not be swallowed by the old platform. It becomes a connecting/downward leaving move and can later serve as the start anchor for a new forming structure.

### New Platform Upward Departure

For the next platform:

- Candidate platform area: `2026-03-23 ~ 2026-04-07`.
- Core: `ZG 3933.06 / ZD 3880.57`.
- Envelope through `2026-04-07`: approximately `3794.68 ~ 3955.94`.

Then:

- `2026-04-08`: close `3994.997` is above envelope high `3955.94`; this is upward departure warning.
- `2026-04-09`: price stays above the core but the low is close to the old envelope; it does not invalidate the warning.
- `2026-04-10`: low `3979.81` is above envelope high `3955.94`; this confirms the upward departure.

Once confirmed, the boundary is cut before the first departure warning:

```text
platform: 2026-03-23 ~ 2026-04-07
departure / connector: starts 2026-04-08
next platform formation: starts after the departure sequence, around 2026-04-10
```

The default chart and daily report should not show `2026-03-23 ~ 2026-04-08` as the platform boundary.

## Longpan Technology Replay

For `603906`:

- Confirmed platform: `2026-04-01 ~ 2026-04-20`.
- Core: `ZG 23.49 / ZD 21.01`.
- Envelope: `20.71 ~ 27.68`.

Replay table:

| Date | Open | High | Low | Close | Boundary reading |
| --- | ---: | ---: | ---: | ---: | --- |
| 2026-04-01 | 21.70 | 22.30 | 20.71 | 21.88 | Platform starts; envelope low anchor |
| 2026-04-02 | 21.88 | 23.49 | 21.01 | 22.90 | Core overlap upper/lower references form |
| 2026-04-03 | 22.90 | 23.10 | 21.35 | 21.80 | Inside platform |
| 2026-04-07 | 21.80 | 23.30 | 21.20 | 23.00 | Inside platform |
| 2026-04-08 | 23.00 | 23.20 | 21.50 | 22.00 | Inside platform |
| 2026-04-09 | 22.00 | 24.00 | 21.80 | 23.60 | Close is above core high, but still inside envelope |
| 2026-04-10 | 23.60 | 24.20 | 22.50 | 22.90 | Inside platform |
| 2026-04-13 | 21.90 | 22.89 | 21.78 | 22.41 | Inside platform |
| 2026-04-14 | 22.51 | 24.20 | 22.11 | 23.68 | Close is above core high, but still inside envelope |
| 2026-04-15 | 23.46 | 23.46 | 22.59 | 22.77 | Inside platform |
| 2026-04-16 | 24.10 | 25.05 | 24.10 | 25.05 | Strong internal extension, still inside envelope |
| 2026-04-17 | 25.80 | 27.20 | 25.07 | 25.99 | Near envelope high, not departed |
| 2026-04-20 | 25.92 | 27.68 | 25.92 | 27.31 | Platform end; envelope high anchor |
| 2026-04-21 | 26.22 | 26.66 | 25.22 | 26.02 | First post-platform bar, still inside old envelope |
| 2026-04-22 | 26.55 | 28.62 | 26.20 | 28.62 | Upward departure warning: close above old envelope high |
| 2026-04-23 | 28.62 | 31.40 | 27.95 | 30.45 | Upward departure confirmed: low above old envelope high |
| 2026-04-24 | 30.44 | 33.25 | 29.50 | 32.56 | Right-edge candidate structure |
| 2026-04-27 | 30.44 | 33.25 | 29.50 | 32.56 | Right-edge candidate structure |
| 2026-04-28 | 31.28 | 31.48 | 29.61 | 29.99 | Candidate overlap forms `31.48 / 29.61` |

Important observation:

- Several dates inside the platform close above the core, including `2026-04-14`, `2026-04-16`, and `2026-04-20`.
- These must not be treated as departure solely because they close above `ZG`.

This proves the rule cannot use core-only departure. It must use the platform envelope.

After the platform:

- `2026-04-21`: connector/first post-platform pullback; close `26.02`, still inside the old envelope.
- `2026-04-22`: close `28.62` is above old envelope high `27.68`, so upward departure warning appears.
- `2026-04-23`: low `27.95` is above old envelope high `27.68`, so upward departure is confirmed.
- `2026-04-24 ~ 2026-04-28`: price surges and then retraces; recent overlap creates a useful right-edge candidate platform.

Expected interpretation:

```text
confirmed platform: 2026-04-01 ~ 2026-04-20
post-platform leaving / candidate structure: 2026-04-21 ~ 2026-04-28
candidate core: 31.48 / 29.61
status: candidate_platform, forming, not in zhongshu_list
```

This is consistent with the current Longpan candidate-platform visual result. The new boundary rule should reinforce that result, not undo it.

## Algorithm Design

### Unit Boundary

Create a focused post-processing unit after raw platform detection and macro aggregation:

```text
apply_effective_departure_boundaries(
  structure_segments,
  ordered_daily_rows,
  boundary_policy="effective_departure"
)
```

The unit receives already-built platform and connector segments. It returns a normalized sequence where:

- effective departure days are not absorbed into the prior platform,
- platform date ranges are cut at the correct decision boundary,
- connector ranges cover the leaving move,
- metadata records any retrospective range that was shortened.

### Detection Steps

For each confirmed platform:

1. Compute envelope high/low from the platform's actual assigned K-lines.
2. Scan the assigned trailing area and any immediately adjacent extension inside the same raw platform.
3. Find first departure warning against the envelope.
4. Confirm the warning if a later day in the same leaving sequence fully departs the envelope.
5. If confirmed, cut the platform at the day before the first warning.
6. Move the warning day and subsequent leaving days into a connector or candidate structure.

### Metadata

When a segment is shortened by effective departure:

```json
{
  "boundary_policy": "effective_departure",
  "retrospective_start_date": "2026-03-23",
  "retrospective_end_date": "2026-04-08",
  "decision_start_date": "2026-03-23",
  "decision_end_date": "2026-04-07",
  "departure_warning_date": "2026-04-08",
  "departure_confirmed_date": "2026-04-10",
  "departure_direction": "up",
  "rule_tier": "effective_departure_boundary"
}
```

Connector metadata:

```json
{
  "segment_type": "connector",
  "connector_role": "departure",
  "departure_status": "confirmed",
  "departure_direction": "up",
  "reason": "effective departure from prior platform envelope"
}
```

### Failed Departure

If a warning appears but is invalidated before confirmation, do not silently merge it as ordinary platform extension.

Represent it as:

```text
failed_departure / returning_move
```

The first implementation must keep failed departures as connectors with explicit metadata. They do not merge back into the original platform by default. A later UI pass can add a distinct visual state if needed, but the first implementation should preserve the decision-time fact that a departure attempt happened.

## Frontend / API Contract

The API should keep using `structure_segments` as the complete visual sequence.

Existing segment types remain:

- `zhongshu`
- `connector`
- `candidate_platform`

Additional connector metadata should be normalized into UI copy:

- `connectorRole: "departure"` for effective leaving moves,
- source label such as `离开段（确认）` or `离开段（预警）`,
- strict status explaining whether it is confirmed departure or failed return.

No new visual type is required in the first implementation. Existing purple connectors and candidate purple dashed boxes are enough.

## Testing Requirements

### Shanghai Composite

Required fixture around `2026-03-20 ~ 2026-04-10`:

- Default boundary policy outputs platform `2026-03-23 ~ 2026-04-07`.
- `2026-04-08` is connector/departure, not part of the platform.
- Retrospective metadata may record that the raw trend-type platform ended on `2026-04-08`.
- A retrospective/debug policy may still expose `2026-03-23 ~ 2026-04-08`, but it cannot be the default.

### Longpan Technology

Required fixture around `2026-04-01 ~ 2026-04-28`:

- Confirmed platform remains `2026-04-01 ~ 2026-04-20`.
- Core-only closes above `ZG` inside that platform do not trigger departure.
- `2026-04-22` triggers upward departure warning from the old platform envelope.
- `2026-04-23` confirms the upward departure.
- `2026-04-21 ~ 2026-04-28` remains a `candidate_platform`.
- Candidate remains absent from `zhongshu_list`.

### Regression

- Shanghai Composite small running platforms such as `2025-06-26 ~ 2025-07-07` remain confirmed if they do not have confirmed effective departure inside the range.
- Long M-shaped platforms remain valid when no effective envelope departure is confirmed.
- No adjacent connector segments appear in API output.
- Existing candidate-platform display remains purple dashed, and connectors keep endpoint circles.

## First Implementation Decisions

1. Failed departures are explicit connector/returning-move segments and are not merged back into the prior platform by default.
2. `departure_warning` is stored in metadata in the first implementation. The chart can keep the existing connector/candidate visuals, with copy such as `leaving move confirmed` when metadata is available.
3. Snap-ui does not need a first-version toggle between `effective_departure` and `retrospective_raw`. Retrospective raw ranges remain metadata/debug data until the default rule is stable.

## Recommendation

Use `effective_departure` as the default boundary policy for both daily reports and snap-ui.

The system's purpose is not only to label structures after the fact. It is to preserve actionable decisions. Therefore, once price effectively leaves a platform envelope and the departure is confirmed, the leaving day must not be swallowed back into the prior platform.
