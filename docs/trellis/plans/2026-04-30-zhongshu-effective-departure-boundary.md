# Zhongshu Effective Departure Boundary Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make effective envelope departure the default Zhongshu boundary rule, so departure days such as Shanghai Composite `2026-04-08` are rendered as connectors instead of being swallowed into the prior platform, while Longpan `603906` keeps `2026-04-01 ~ 2026-04-20` confirmed and `2026-04-21 ~ 2026-04-28` as a candidate platform.

**Architecture:** Add one focused boundary pass in `scripts/decision/chanlun_zhongshu_runtime.py` after raw macro-platform merging and before final date partitioning. Reuse the same envelope-departure metadata for stock tail candidates in `scripts/decision/zhongshu_runtime.py`, then normalize the new connector role in snap-ui without introducing a new chart shape.

**Tech Stack:** Python runtime/tests with `venv/bin/python -m pytest`; Nuxt/Vitest snap-ui with `npm test`; existing JSON fixtures under `data/snap-ui` and `snapshots`.

---

## File Structure

- Modify `scripts/decision/chanlun_zhongshu_runtime.py`
  - Owns pure effective-departure detection against platform envelopes.
  - Owns the macro-platform boundary cut before `_partition_macro_sequence_by_dates_with_confirmed_minimum()`.
  - Owns connector metadata annotation for connector segments created by date partitioning.
- Modify `scripts/decision/zhongshu_runtime.py`
  - Uses the shared envelope-departure detector to annotate right-edge `candidate_platform` segments such as Longpan.
- Modify `scripts/export/security_zhongshu_visual_snapshot.py`
  - Bumps stock Zhongshu cache version so old stock-cache payloads regenerate.
- Modify `snap-ui/server/utils/snapshot/stockZhongshuVisualSnapshot.ts`
  - Bumps the matching stock cache version used by snap-ui.
- Modify `snap-ui/app/types/snapshot.ts`
  - Adds `departure` to connector role and exposes optional departure metadata on zones.
- Modify `snap-ui/server/utils/snapshot/zhongshuAdapter.ts`
  - Preserves `connector_role: "departure"` and shows departure-aware copy.
- Modify tests:
  - `tests/test_chanlun_zhongshu_runtime.py`
  - `tests/test_security_zhongshu_node.py`
  - `snap-ui/tests/unit/stockZhongshuAdapter.test.ts`
  - `snap-ui/tests/unit/stockZhongshuVisualSnapshot.test.ts`

## Task 1: Backend Regression Tests For Effective Boundary Cuts

**Files:**
- Modify: `tests/test_chanlun_zhongshu_runtime.py`

- [ ] **Step 1: Add the failing Shanghai Composite effective-departure regression**

Append this test method inside `class ChanlunZhongshuRuntimeTest(unittest.TestCase):` after `test_aggregate_daily_macro_platforms_merges_real_index_fragments_until_complete_departure`:

```python
    def test_aggregate_daily_macro_platforms_cuts_real_index_departure_before_warning(self):
        payload = json.loads((ROOT / "data/snap-ui/zhongshu-visual/2026-04-29-sh000001.json").read_text())
        rows = payload["index_klines"]["sh000001"]
        hist_rows = rows[:-1]
        trend_types = runtime.build_trend_types_from_bars(hist_rows, level="daily")
        raw_segments, _raw_platforms = runtime.build_platform_sequence_from_trend_types(trend_types, level="daily")

        segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            ordered_dates=hist_rows,
        )

        platform = next(item for item in platforms if item["start_date"] == "2026-03-23")
        self.assertEqual(platform["end_date"], "2026-04-07")
        self.assertEqual(platform["boundary_policy"], "effective_departure")
        self.assertEqual(platform["retrospective_end_date"], "2026-04-08")
        self.assertEqual(platform["departure_warning_date"], "2026-04-08")
        self.assertEqual(platform["departure_confirmed_date"], "2026-04-10")
        self.assertEqual(platform["departure_direction"], "up")

        departure_connector = next(
            item
            for item in segments
            if item.get("segment_type") == "connector"
            and item.get("connector_role") == "departure"
            and item["start_date"] == "2026-04-08"
        )
        self.assertEqual(departure_connector["end_date"], "2026-04-09")
        self.assertEqual(departure_connector["departure_status"], "confirmed")
        self.assertEqual(departure_connector["departure_direction"], "up")
        self.assertFalse(
            any(
                item.get("segment_type") == "connector" and right.get("segment_type") == "connector"
                for item, right in zip(segments, segments[1:])
            ),
            segments,
        )
```

- [ ] **Step 2: Add the Longpan no-core-only-cut regression**

Append this test method in the same class:

```python
    def test_effective_departure_detector_uses_envelope_not_core_for_longpan_tail(self):
        reference = {
            "segment_type": "zhongshu",
            "start_date": "2026-04-01",
            "end_date": "2026-04-20",
            "zg": 23.3,
            "zd": 21.2,
            "high": 27.68,
            "low": 20.71,
            "segment_high": 27.68,
            "segment_low": 20.71,
            "visual_high": 27.68,
            "visual_low": 20.71,
        }
        rows = [
            {"date": "2026-04-14", "high": 24.2, "low": 22.11, "close": 23.68},
            {"date": "2026-04-16", "high": 25.05, "low": 24.1, "close": 25.05},
            {"date": "2026-04-20", "high": 27.68, "low": 25.92, "close": 27.31},
            {"date": "2026-04-21", "high": 26.66, "low": 25.22, "close": 26.02},
            {"date": "2026-04-22", "high": 28.62, "low": 26.2, "close": 28.62},
            {"date": "2026-04-23", "high": 31.4, "low": 27.95, "close": 30.45},
            {"date": "2026-04-28", "high": 31.48, "low": 29.61, "close": 29.99},
        ]

        metadata = runtime.detect_effective_departure_from_envelope(reference, rows)

        self.assertEqual(metadata["departure_warning_date"], "2026-04-22")
        self.assertEqual(metadata["departure_confirmed_date"], "2026-04-23")
        self.assertEqual(metadata["departure_direction"], "up")
        self.assertEqual(metadata["departure_status"], "confirmed")
```

- [ ] **Step 3: Run the new backend tests and verify they fail**

Run:

```bash
venv/bin/python -m pytest tests/test_chanlun_zhongshu_runtime.py::ChanlunZhongshuRuntimeTest::test_aggregate_daily_macro_platforms_cuts_real_index_departure_before_warning tests/test_chanlun_zhongshu_runtime.py::ChanlunZhongshuRuntimeTest::test_effective_departure_detector_uses_envelope_not_core_for_longpan_tail -q
```

Expected: FAIL. The first test currently sees platform `2026-03-23 ~ 2026-04-08`; the second test fails because `detect_effective_departure_from_envelope` does not exist.

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/test_chanlun_zhongshu_runtime.py
git commit -m "test: capture effective zhongshu departure boundaries"
```

## Task 2: Implement Effective Departure Boundary Unit

**Files:**
- Modify: `scripts/decision/chanlun_zhongshu_runtime.py`
- Test: `tests/test_chanlun_zhongshu_runtime.py`

- [ ] **Step 1: Export the shared detector**

Update `__all__` near the top of `scripts/decision/chanlun_zhongshu_runtime.py`:

```python
__all__ = [
    "DAILY_CANDIDATE_MIN_KLINES",
    "DAILY_REPORT_FOCUS_DAYS",
    "DAILY_STRUCTURE_LOOKBACK_DAYS",
    "analyze_chanlun_zhongshu",
    "build_daily_structure_candidates",
    "build_chanlun_60m_structures",
    "aggregate_daily_macro_platforms",
    "build_platform_sequence_from_trend_types",
    "build_trend_types_from_bars",
    "confirm_daily_level_zhongshu",
    "detect_effective_departure_from_envelope",
]
```

- [ ] **Step 2: Add envelope and departure helpers**

Insert this block after `CENTER_MIGRATION_ENVELOPE_RATIO_LIMIT = 0.22`:

```python
EFFECTIVE_DEPARTURE_TAIL_SCAN_BARS = 3
EFFECTIVE_DEPARTURE_CONFIRM_LOOKAHEAD_BARS = 6


def _first_strict_number(mapping, *keys):
    for key in keys:
        value = _strict_float(mapping.get(key))
        if value is not None:
            return value
    return None


def _platform_envelope_bounds(platform):
    high = _first_strict_number(platform, "visual_high", "segment_high", "high", "zg", "ZG")
    low = _first_strict_number(platform, "visual_low", "segment_low", "low", "zd", "ZD")
    if high is None or low is None:
        return None
    return max(high, low), min(high, low)


def _row_departure_direction(row, envelope_high, envelope_low, *, warning):
    high = _strict_float(row.get("high"))
    low = _strict_float(row.get("low"))
    close = _strict_float(row.get("close"))
    if high is None or low is None:
        return None
    if warning:
        if close is not None and close > envelope_high:
            return "up"
        if close is not None and close < envelope_low:
            return "down"
        return None
    if low > envelope_high:
        return "up"
    if high < envelope_low:
        return "down"
    return None


def _departure_metadata(direction, warning_row, confirmed_row, envelope_high, envelope_low):
    return {
        "boundary_policy": "effective_departure",
        "departure_status": "confirmed",
        "departure_direction": direction,
        "departure_warning_date": warning_row["date"],
        "departure_confirmed_date": confirmed_row["date"],
        "departure_envelope_high": float(envelope_high),
        "departure_envelope_low": float(envelope_low),
        "rule_tier": "effective_departure_boundary",
    }


def detect_effective_departure_from_envelope(reference_platform, rows):
    """Detect a confirmed departure from a completed platform envelope."""
    bounds = _platform_envelope_bounds(reference_platform or {})
    if bounds is None:
        return None
    envelope_high, envelope_low = bounds
    date_items = _coerce_ordered_date_items(rows)
    warning = None
    direction = None
    for row in date_items:
        row_direction = _row_departure_direction(row, envelope_high, envelope_low, warning=True)
        if row_direction is None:
            continue
        warning = row
        direction = row_direction
        break
    if warning is None or direction is None:
        return None
    warning_seen = False
    for row in date_items:
        if row["date"] == warning["date"]:
            warning_seen = True
            continue
        if not warning_seen:
            continue
        confirmed_direction = _row_departure_direction(row, envelope_high, envelope_low, warning=False)
        if confirmed_direction == direction:
            return _departure_metadata(direction, warning, row, envelope_high, envelope_low)
        opposite_warning = _row_departure_direction(row, envelope_high, envelope_low, warning=True)
        if opposite_warning and opposite_warning != direction:
            return {
                "boundary_policy": "effective_departure",
                "departure_status": "failed",
                "departure_direction": direction,
                "departure_warning_date": warning["date"],
                "departure_confirmed_date": "",
                "departure_envelope_high": float(envelope_high),
                "departure_envelope_low": float(envelope_low),
                "rule_tier": "failed_departure_boundary",
            }
    return {
        "boundary_policy": "effective_departure",
        "departure_status": "warning",
        "departure_direction": direction,
        "departure_warning_date": warning["date"],
        "departure_confirmed_date": "",
        "departure_envelope_high": float(envelope_high),
        "departure_envelope_low": float(envelope_low),
        "rule_tier": "effective_departure_warning",
    }
```

- [ ] **Step 3: Add the macro-boundary cut helpers**

Insert this block after `detect_effective_departure_from_envelope()`:

```python
def _prefix_envelope(rows):
    highs = [_strict_float(row.get("high")) for row in rows]
    lows = [_strict_float(row.get("low")) for row in rows]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    if not highs or not lows:
        return None
    return float(max(highs)), float(min(lows))


def _find_effective_departure_boundary(platform, next_platform, date_items, index_by_date):
    bounds = _date_index_bounds(platform, index_by_date)
    next_bounds = _date_index_bounds(next_platform, index_by_date)
    if bounds is None or next_bounds is None:
        return None
    start_idx, end_idx = bounds
    if end_idx - start_idx + 1 < MIN_CONFIRMED_PLATFORM_KLINES + 1:
        return None
    scan_start = max(
        start_idx + MIN_CONFIRMED_PLATFORM_KLINES,
        end_idx - EFFECTIVE_DEPARTURE_TAIL_SCAN_BARS + 1,
    )
    scan_end = end_idx
    confirm_end = min(
        len(date_items) - 1,
        max(next_bounds[0], scan_end + EFFECTIVE_DEPARTURE_CONFIRM_LOOKAHEAD_BARS),
    )
    for warning_idx in range(scan_start, scan_end + 1):
        prefix_rows = date_items[start_idx:warning_idx]
        if len(prefix_rows) < MIN_CONFIRMED_PLATFORM_KLINES:
            continue
        envelope = _prefix_envelope(prefix_rows)
        if envelope is None:
            continue
        envelope_high, envelope_low = envelope
        warning_row = date_items[warning_idx]
        direction = _row_departure_direction(warning_row, envelope_high, envelope_low, warning=True)
        if direction is None:
            continue
        for confirm_idx in range(warning_idx + 1, confirm_end + 1):
            confirmed_row = date_items[confirm_idx]
            confirmed_direction = _row_departure_direction(confirmed_row, envelope_high, envelope_low, warning=False)
            if confirmed_direction != direction:
                continue
            decision_end_idx = warning_idx - 1
            if decision_end_idx - start_idx + 1 < MIN_CONFIRMED_PLATFORM_KLINES:
                return None
            metadata = _departure_metadata(direction, warning_row, confirmed_row, envelope_high, envelope_low)
            metadata.update(
                {
                    "retrospective_start_date": platform.get("start_date"),
                    "retrospective_end_date": platform.get("end_date"),
                    "decision_start_date": date_items[start_idx]["date"],
                    "decision_end_date": date_items[decision_end_idx]["date"],
                    "departure_warning_index": warning_idx,
                    "departure_confirmed_index": confirm_idx,
                }
            )
            return {"decision_end_idx": decision_end_idx, "metadata": metadata}
    return None


def apply_effective_departure_boundaries(platforms, ordered_dates, *, level="daily"):
    del level
    date_items = _coerce_ordered_date_items(ordered_dates)
    if not platforms or not date_items:
        return platforms
    if any(
        _strict_float(item.get("high")) is None
        or _strict_float(item.get("low")) is None
        or _strict_float(item.get("close")) is None
        for item in date_items
    ):
        return platforms
    index_by_date = {item["date"]: idx for idx, item in enumerate(date_items)}
    adjusted = []
    for index, platform in enumerate(platforms):
        copied = dict(platform)
        next_platform = platforms[index + 1] if index + 1 < len(platforms) else None
        if next_platform is not None:
            event = _find_effective_departure_boundary(copied, next_platform, date_items, index_by_date)
            if event is not None:
                bounds = _date_index_bounds(copied, index_by_date)
                if bounds is not None:
                    shortened = _apply_date_span(copied, bounds[0], event["decision_end_idx"], date_items)
                    if shortened is not None:
                        shortened.update(event["metadata"])
                        shortened["effective_departure"] = dict(event["metadata"])
                        copied = shortened
        adjusted.append(copied)
    return adjusted
```

- [ ] **Step 4: Add connector metadata annotation**

Insert this block before `aggregate_daily_macro_platforms()`:

```python
def _date_in_segment(date, segment):
    normalized = normalize_kline_date_str(date)
    start = normalize_kline_date_str(segment.get("start_date"))
    end = normalize_kline_date_str(segment.get("end_date"))
    if not normalized or not start or not end:
        return False
    left, right = (start, end) if start <= end else (end, start)
    return left <= normalized <= right


def _annotate_effective_departure_connectors(segments):
    annotated = []
    pending_departure = None
    for segment in segments:
        copied = dict(segment)
        if copied.get("segment_type") == "connector" and pending_departure:
            warning_date = pending_departure.get("departure_warning_date")
            if _date_in_segment(warning_date, copied):
                copied.update(
                    {
                        "connector_role": "departure",
                        "departure_status": pending_departure.get("departure_status", "confirmed"),
                        "departure_direction": pending_departure.get("departure_direction", ""),
                        "departure_warning_date": pending_departure.get("departure_warning_date", ""),
                        "departure_confirmed_date": pending_departure.get("departure_confirmed_date", ""),
                        "departure_envelope_high": pending_departure.get("departure_envelope_high"),
                        "departure_envelope_low": pending_departure.get("departure_envelope_low"),
                        "rule_tier": pending_departure.get("rule_tier", "effective_departure_boundary"),
                        "reason": "有效离开前平台包络，作为离开段连接到下一结构",
                    }
                )
                pending_departure = None
        annotated.append(copied)
        if copied.get("segment_type") == "zhongshu":
            pending_departure = copied.get("effective_departure") if isinstance(copied.get("effective_departure"), Mapping) else None
    return annotated
```

- [ ] **Step 5: Wire the boundary pass into `aggregate_daily_macro_platforms()`**

Replace the bottom of `aggregate_daily_macro_platforms()` with this version:

```python
    macro_segments, macro_platforms = _build_price_platform_sequence(raw_segments, level=level)
    if ordered_dates:
        initial_partition = _partition_macro_sequence_by_dates_with_confirmed_minimum(
            macro_platforms,
            ordered_dates,
            level=level,
        )
        if initial_partition is not None:
            _initial_segments, macro_platforms = initial_partition
        macro_platforms = _merge_platforms_by_envelope_departure(macro_platforms, ordered_dates, level=level)
        macro_platforms = apply_effective_departure_boundaries(macro_platforms, ordered_dates, level=level)
    partitioned = _partition_macro_sequence_by_dates_with_confirmed_minimum(
        macro_platforms,
        ordered_dates,
        level=level,
    )
    if partitioned is not None:
        partitioned_segments, partitioned_platforms = partitioned
        return _annotate_effective_departure_connectors(partitioned_segments), partitioned_platforms

    return _annotate_effective_departure_connectors(macro_segments), [platform.copy() for platform in macro_platforms]
```

- [ ] **Step 6: Run the backend tests from Task 1**

Run:

```bash
venv/bin/python -m pytest tests/test_chanlun_zhongshu_runtime.py::ChanlunZhongshuRuntimeTest::test_aggregate_daily_macro_platforms_cuts_real_index_departure_before_warning tests/test_chanlun_zhongshu_runtime.py::ChanlunZhongshuRuntimeTest::test_effective_departure_detector_uses_envelope_not_core_for_longpan_tail -q
```

Expected: PASS.

- [ ] **Step 7: Run existing Zhongshu backend regression tests**

Run:

```bash
venv/bin/python -m pytest tests/test_chanlun_zhongshu_runtime.py tests/test_zhongshu_runtime.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit the boundary unit**

```bash
git add scripts/decision/chanlun_zhongshu_runtime.py tests/test_chanlun_zhongshu_runtime.py
git commit -m "feat: cut zhongshu boundaries on effective departure"
```

## Task 3: Annotate Longpan Tail Candidate Departure Metadata

**Files:**
- Modify: `scripts/decision/zhongshu_runtime.py`
- Modify: `tests/test_security_zhongshu_node.py`

- [ ] **Step 1: Import the shared detector**

Update the import block at the top of `scripts/decision/zhongshu_runtime.py`:

```python
from decision.chanlun_zhongshu_runtime import (
    aggregate_daily_macro_platforms,
    analyze_chanlun_zhongshu,
    build_platform_sequence_from_trend_types,
    build_trend_types_from_bars,
    detect_effective_departure_from_envelope,
)
```

- [ ] **Step 2: Add departure metadata when building a tail candidate**

Inside `append_tail_candidate_platform()`, after the `candidate = { ... }` dict is created and before `return [*structure_segments[:-1], candidate]`, add:

```python
    departure_metadata = detect_effective_departure_from_envelope(previous_platform, rows)
    if departure_metadata and departure_metadata.get("departure_status") == "confirmed":
        candidate.update(
            {
                "departure_status": departure_metadata.get("departure_status"),
                "departure_direction": departure_metadata.get("departure_direction"),
                "departure_warning_date": departure_metadata.get("departure_warning_date"),
                "departure_confirmed_date": departure_metadata.get("departure_confirmed_date"),
                "departure_envelope_high": departure_metadata.get("departure_envelope_high"),
                "departure_envelope_low": departure_metadata.get("departure_envelope_low"),
                "departure_source_platform_start_date": previous_platform.get("start_date"),
                "departure_source_platform_end_date": previous_platform.get("end_date"),
            }
        )
```

- [ ] **Step 3: Extend the Longpan security-node test**

In `tests/test_security_zhongshu_node.py`, inside `test_appends_tail_candidate_platform_without_promoting_to_confirmed`, add these assertions after `self.assertEqual(latest["zd"], 29.61)`:

```python
        self.assertEqual(latest["departure_status"], "confirmed")
        self.assertEqual(latest["departure_direction"], "up")
        self.assertEqual(latest["departure_warning_date"], "2026-04-22")
        self.assertEqual(latest["departure_confirmed_date"], "2026-04-23")
        self.assertEqual(latest["departure_envelope_high"], 27.68)
        self.assertEqual(latest["departure_envelope_low"], 20.71)
        self.assertEqual(latest["departure_source_platform_start_date"], "2026-04-01")
        self.assertEqual(latest["departure_source_platform_end_date"], "2026-04-20")
```

- [ ] **Step 4: Run the security-node regression**

Run:

```bash
venv/bin/python -m pytest tests/test_security_zhongshu_node.py::SecurityZhongshuNodeTest::test_appends_tail_candidate_platform_without_promoting_to_confirmed -q
```

Expected: PASS.

- [ ] **Step 5: Commit Longpan tail metadata**

```bash
git add scripts/decision/zhongshu_runtime.py tests/test_security_zhongshu_node.py
git commit -m "feat: annotate stock tail departure metadata"
```

## Task 4: Normalize Departure Metadata In Snap-UI

**Files:**
- Modify: `snap-ui/app/types/snapshot.ts`
- Modify: `snap-ui/server/utils/snapshot/zhongshuAdapter.ts`
- Modify: `snap-ui/tests/unit/stockZhongshuAdapter.test.ts`

- [ ] **Step 1: Extend the zone type**

In `snap-ui/app/types/snapshot.ts`, replace the `connectorRole` line in `ZhongshuZone` and add optional departure fields below it:

```ts
  connectorRole: 'leading' | 'between' | 'trailing' | 'departure' | ''
  departureStatus?: string
  departureDirection?: 'up' | 'down' | ''
  departureWarningDate?: string
  departureConfirmedDate?: string
```

- [ ] **Step 2: Accept `departure` as a connector role**

In `snap-ui/server/utils/snapshot/zhongshuAdapter.ts`, replace both `rawConnectorRole()` and `connectorRole()` implementations with:

```ts
function rawConnectorRole(value: unknown) {
  const role = asText(value)
  return role === 'leading' || role === 'between' || role === 'trailing' || role === 'departure' ? role : ''
}
```

```ts
function connectorRole(value: unknown): ZhongshuZone['connectorRole'] {
  const role = asText(value)
  return role === 'leading' || role === 'between' || role === 'trailing' || role === 'departure' ? role : ''
}
```

- [ ] **Step 3: Add departure copy helpers**

In `snap-ui/server/utils/snapshot/zhongshuAdapter.ts`, add these helpers before `sourceLabelForSegment()`:

```ts
function departureStatusLabel(segment: Record<string, unknown>) {
  const status = asText(segment.departure_status ?? segment.departureStatus)
  if (status === 'confirmed') return '确认'
  if (status === 'failed') return '失败返回'
  if (status === 'warning') return '预警'
  return '观察'
}

function isDepartureSegment(segment: Record<string, unknown>) {
  return rawConnectorRole(segment.connector_role ?? segment.connectorRole) === 'departure'
}
```

- [ ] **Step 4: Use departure-aware labels**

In `sourceLabelForSegment()`, add this as the first line:

```ts
  if (segmentType === 'connector' && isDepartureSegment(segment)) return `离开段（${departureStatusLabel(segment)}）`
```

Change the signature of `strictStatusForSegment()` from:

```ts
function strictStatusForSegment(segmentType: ZhongshuZone['segmentType'], policy: ChanlunVisualPolicy) {
```

to:

```ts
function strictStatusForSegment(segment: Record<string, unknown>, segmentType: ZhongshuZone['segmentType'], policy: ChanlunVisualPolicy) {
```

Add this as the first line of the function body:

```ts
  if (segmentType === 'connector' && isDepartureSegment(segment)) return `离开段：${departureStatusLabel(segment)}离开前平台包络`
```

Update the call site in `zones.push({ ... })`:

```ts
      strictStatus: strictStatusForSegment(zone, segmentType, policy),
```

- [ ] **Step 5: Preserve departure metadata on normalized zones**

In the `zones.push({ ... })` object, add these properties after `connectorRole`:

```ts
      departureStatus: asText(zone.departure_status ?? zone.departureStatus),
      departureDirection: asText(zone.departure_direction ?? zone.departureDirection) === 'down' ? 'down' : asText(zone.departure_direction ?? zone.departureDirection) === 'up' ? 'up' : '',
      departureWarningDate: asText(zone.departure_warning_date ?? zone.departureWarningDate),
      departureConfirmedDate: asText(zone.departure_confirmed_date ?? zone.departureConfirmedDate),
```

- [ ] **Step 6: Add adapter regression for departure connector copy**

Append this test to `snap-ui/tests/unit/stockZhongshuAdapter.test.ts`:

```ts
  it('normalizes confirmed departure connectors with departure copy', () => {
    const result = normalizeZhongshuStructure(
      {
        data: {
          strict_chanlun_policy: {
            source_algorithm: 'practical_daily_node_runtime; full_recursive_mode_deferred',
            default_mode: 'practical_daily_mode',
            minute_confirmation: 'not_requested'
          },
          index_klines: {
            sh000001: [
              { date: '2026-04-07', open: 3900, close: 3920, low: 3880, high: 3955, volume: 1, amount: 1 },
              { date: '2026-04-08', open: 3930, close: 3994.997, low: 3926.248, high: 3994.997, volume: 1, amount: 1 },
              { date: '2026-04-09', open: 3990, close: 3966.171, low: 3955.245, high: 3979.127, volume: 1, amount: 1 },
              { date: '2026-04-10', open: 3988, close: 4048, low: 3979.814, high: 4065.373, volume: 1, amount: 1 }
            ]
          },
          market_zhongshu: {
            success: true,
            today_date: '2026-04-10',
            today_price: 4048,
            current_zhongshu: {
              start_date: '2026-04-10',
              end_date: '2026-04-10',
              zg: 4057.831,
              zd: 4038.428,
              high: 4065.373,
              low: 3979.814,
              segment_type: 'zhongshu'
            },
            structure_segments: [
              {
                start_date: '2026-03-23',
                end_date: '2026-04-07',
                zg: 3933.061,
                zd: 3880.572,
                high: 3955.943,
                low: 3794.684,
                kline_count: 10,
                segment_type: 'zhongshu',
                boundary_policy: 'effective_departure',
                departure_warning_date: '2026-04-08',
                departure_confirmed_date: '2026-04-10',
                departure_direction: 'up'
              },
              {
                start_date: '2026-04-08',
                end_date: '2026-04-09',
                high: 3994.997,
                low: 3926.248,
                segment_high: 3994.997,
                segment_low: 3926.248,
                start_close: 3994.997,
                end_close: 3966.171,
                kline_count: 2,
                segment_type: 'connector',
                connector_role: 'departure',
                departure_status: 'confirmed',
                departure_direction: 'up',
                departure_warning_date: '2026-04-08',
                departure_confirmed_date: '2026-04-10'
              }
            ],
            signal: {
              status: '✅ 突破中枢',
              signal_type: '大盘突破',
              comparison_state: 'breakout'
            }
          }
        }
      },
      {
        date: '2026-04-10',
        mode: 'frozen',
        indexCode: 'sh000001',
        instrumentType: 'index'
      }
    )

    expect(result.zones[1]).toMatchObject({
      segmentType: 'connector',
      connectorRole: 'departure',
      sourceLabel: '离开段（确认）',
      strictStatus: '离开段：确认离开前平台包络',
      departureStatus: 'confirmed',
      departureDirection: 'up',
      departureWarningDate: '2026-04-08',
      departureConfirmedDate: '2026-04-10'
    })
  })
```

- [ ] **Step 7: Run the adapter test**

Run:

```bash
cd snap-ui && npm test -- tests/unit/stockZhongshuAdapter.test.ts
```

Expected: PASS.

- [ ] **Step 8: Commit snap-ui metadata normalization**

```bash
git add snap-ui/app/types/snapshot.ts snap-ui/server/utils/snapshot/zhongshuAdapter.ts snap-ui/tests/unit/stockZhongshuAdapter.test.ts
git commit -m "feat: expose zhongshu departure connectors in snap ui"
```

## Task 5: Bump Stock Zhongshu Cache Version

**Files:**
- Modify: `scripts/export/security_zhongshu_visual_snapshot.py`
- Modify: `snap-ui/server/utils/snapshot/stockZhongshuVisualSnapshot.ts`
- Modify: `snap-ui/tests/unit/stockZhongshuVisualSnapshot.test.ts`

- [ ] **Step 1: Bump the Python exporter algorithm version**

In `scripts/export/security_zhongshu_visual_snapshot.py`, replace:

```python
SECURITY_ZHONGSHU_VISUAL_ALGORITHM_VERSION = "security-zhongshu-tail-candidate-v2"
```

with:

```python
SECURITY_ZHONGSHU_VISUAL_ALGORITHM_VERSION = "security-zhongshu-effective-departure-v1"
```

- [ ] **Step 2: Bump the snap-ui cache version**

In `snap-ui/server/utils/snapshot/stockZhongshuVisualSnapshot.ts`, replace:

```ts
const STOCK_ZHONGSHU_ALGORITHM_VERSION = 'security-zhongshu-tail-candidate-v2'
```

with:

```ts
const STOCK_ZHONGSHU_ALGORITHM_VERSION = 'security-zhongshu-effective-departure-v1'
```

- [ ] **Step 3: Update stock cache tests**

In `snap-ui/tests/unit/stockZhongshuVisualSnapshot.test.ts`, replace every expected string:

```ts
'security-zhongshu-tail-candidate-v2'
```

with:

```ts
'security-zhongshu-effective-departure-v1'
```

Also replace the JSON fixture text:

```json
"algorithm_version": "security-zhongshu-tail-candidate-v2"
```

with:

```json
"algorithm_version": "security-zhongshu-effective-departure-v1"
```

- [ ] **Step 4: Run stock cache tests**

Run:

```bash
cd snap-ui && npm test -- tests/unit/stockZhongshuVisualSnapshot.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit cache version bump**

```bash
git add scripts/export/security_zhongshu_visual_snapshot.py snap-ui/server/utils/snapshot/stockZhongshuVisualSnapshot.ts snap-ui/tests/unit/stockZhongshuVisualSnapshot.test.ts
git commit -m "chore: refresh stock zhongshu cache version"
```

## Task 6: Full Verification

**Files:**
- No code edits in this task.

- [ ] **Step 1: Run focused Python Zhongshu tests**

Run:

```bash
venv/bin/python -m pytest tests/test_chanlun_zhongshu_runtime.py tests/test_zhongshu_runtime.py tests/test_security_zhongshu_node.py -q
```

Expected: PASS.

- [ ] **Step 2: Run focused snap-ui unit tests**

Run:

```bash
cd snap-ui && npm test -- tests/unit/stockZhongshuAdapter.test.ts tests/unit/stockZhongshuVisualSnapshot.test.ts tests/unit/zhongshuOptions.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run full snap-ui build**

Run:

```bash
cd snap-ui && npm run build
```

Expected: PASS. Existing sourcemap or chunk-size warnings are acceptable only if the process exits with code `0`.

- [ ] **Step 4: Regenerate a stock payload for Longpan and inspect metadata**

Run:

```bash
venv/bin/python scripts/export/security_zhongshu_visual_snapshot.py --date 2026-04-29 --security-code 603906 --security-name 龙蟠科技 --security-type stock --output /tmp/603906-effective-departure.json
```

Expected: exit code `0`.

Run:

```bash
venv/bin/python - <<'PY'
import json
payload = json.load(open('/tmp/603906-effective-departure.json'))
segments = payload['security_zhongshu']['structure_segments']
latest = segments[-1]
print(latest['segment_type'], latest.get('departure_warning_date'), latest.get('departure_confirmed_date'), latest.get('departure_status'))
PY
```

Expected output:

```text
candidate_platform 2026-04-22 2026-04-23 confirmed
```

- [ ] **Step 5: Inspect Shanghai boundary from generated fixture path**

Run:

```bash
venv/bin/python - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from decision import chanlun_zhongshu_runtime as runtime
payload = json.loads(Path('data/snap-ui/zhongshu-visual/2026-04-29-sh000001.json').read_text())
hist_rows = payload['index_klines']['sh000001'][:-1]
trend_types = runtime.build_trend_types_from_bars(hist_rows, level='daily')
raw_segments, _ = runtime.build_platform_sequence_from_trend_types(trend_types, level='daily')
segments, platforms = runtime.aggregate_daily_macro_platforms(raw_segments, level='daily', ordered_dates=hist_rows)
target = next(item for item in platforms if item['start_date'] == '2026-03-23')
connector = next(item for item in segments if item.get('connector_role') == 'departure')
print(target['start_date'], target['end_date'], target['departure_warning_date'], target['departure_confirmed_date'])
print(connector['start_date'], connector['end_date'], connector['departure_status'])
PY
```

Expected output:

```text
2026-03-23 2026-04-07 2026-04-08 2026-04-10
2026-04-08 2026-04-09 confirmed
```

- [ ] **Step 6: Confirm verification did not leave generated artifacts in tracked implementation files**

Inspect the files touched by this plan:

```bash
git status --short scripts/decision/chanlun_zhongshu_runtime.py scripts/decision/zhongshu_runtime.py scripts/export/security_zhongshu_visual_snapshot.py tests/test_chanlun_zhongshu_runtime.py tests/test_security_zhongshu_node.py snap-ui/app/types/snapshot.ts snap-ui/server/utils/snapshot/zhongshuAdapter.ts snap-ui/server/utils/snapshot/stockZhongshuVisualSnapshot.ts snap-ui/tests/unit/stockZhongshuAdapter.test.ts snap-ui/tests/unit/stockZhongshuVisualSnapshot.test.ts
```

Expected: no output after all task commits have been created.

## Self-Review Checklist

- Spec coverage:
  - Shanghai `2026-03-23 ~ 2026-04-07` boundary is covered by Task 1 and Task 2.
  - Longpan `2026-04-01 ~ 2026-04-20` confirmed plus `2026-04-21 ~ 2026-04-28` candidate is covered by Task 1 and Task 3.
  - Failed/warning departure metadata shape is covered by Task 2 helper return values and Task 4 UI normalization.
  - Existing purple connector rendering remains untouched; `zhongshuOptions.ts` is only verified in Task 6.
  - Cache invalidation is covered by Task 5.
- Placeholder scan:
  - The plan contains no forbidden placeholder markers and no unfilled command placeholders.
- Type consistency:
  - Python metadata uses snake_case.
  - Snap-ui normalized zone fields use camelCase.
  - `connector_role: "departure"` maps to `connectorRole: "departure"`.
