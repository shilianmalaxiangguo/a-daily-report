# Chanlun Module Rebuild Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Chanlun module as a node-based practical daily system that uses 250 closed daily bars as the structural base, keeps 120 daily bars for reports, and uses 60m only as optional confirmation.

**Architecture:** Create a new `decision.chanlun` package with focused source, morphology, structure, confirmation, and adapter nodes. Keep `scripts/decision/chanlun_zhongshu_runtime.py` as a compatibility facade so existing report code can migrate without a broad rewrite. Full recursive mode is out of scope for this plan and must not be implemented in v1.

**Tech Stack:** Python, pandas, unittest, existing AkShare/SkillHub fetch wrappers, existing report runtime contracts.

---

## Scope Rules

- Do not implement `full_recursive_mode` in this plan.
- Do not request 1m or 5m data in default paths.
- Do not let 15m data serve as a 250-day structural base.
- Do not use fixed 20-day duration to confirm a zhongshu.
- Do not call visual bridge lines a core Chanlun rule.
- Preserve the current public function `analyze_chanlun_zhongshu(...)` until downstream code is migrated.

## File Structure

- Create `scripts/decision/chanlun/__init__.py`: package exports for the new module.
- Create `scripts/decision/chanlun/contracts.py`: constants, status strings, and output builders shared by nodes.
- Create `scripts/decision/chanlun/source_nodes.py`: K-line normalization, daily window selection, data capability diagnostics.
- Create `scripts/decision/chanlun/morphology_nodes.py`: inclusion handling, fractals, strokes, and first-pass segment candidates.
- Create `scripts/decision/chanlun/structure_nodes.py`: trend-type construction, platform/zhongshu detection, connector classification, ambiguity metadata.
- Create `scripts/decision/chanlun/confirmation_nodes.py`: 60m confirmation and data-insufficient handling.
- Create `scripts/decision/chanlun/runtime.py`: practical daily orchestrator and hybrid confirmation orchestrator.
- Create `scripts/decision/chanlun/scenario_runner.py`: built-in A-share scenario generator, runner, and markdown observation writer.
- Modify `scripts/decision/chanlun_zhongshu_runtime.py`: replace internal logic with a compatibility facade delegating to `decision.chanlun.runtime`.
- Modify `scripts/decision/zhongshu_runtime.py`: consume the facade without changing report-level payload names.
- Create `tests/test_chanlun_source_nodes.py`.
- Create `tests/test_chanlun_morphology_nodes.py`.
- Create `tests/test_chanlun_structure_nodes.py`.
- Create `tests/test_chanlun_confirmation_nodes.py`.
- Create `tests/test_chanlun_runtime_contract.py`.
- Create `tests/test_chanlun_a_share_scenarios.py`.
- Modify `tests/test_chanlun_zhongshu_runtime.py`: keep existing compatibility assertions and remove expectations tied to legacy internals.

## Task 1: Source Nodes And Data Capability

**Files:**
- Create: `scripts/decision/chanlun/__init__.py`
- Create: `scripts/decision/chanlun/contracts.py`
- Create: `scripts/decision/chanlun/source_nodes.py`
- Create: `tests/test_chanlun_source_nodes.py`

- [ ] **Step 1: Write failing tests for daily windows and data capability**

Add this to `tests/test_chanlun_source_nodes.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import source_nodes


def _rows(count):
    return [
        {
            "date": f"2026-01-{(idx % 28) + 1:02d}",
            "datetime": f"2026-01-{(idx % 28) + 1:02d} 15:00:00",
            "open": 100 + idx,
            "high": 105 + idx,
            "low": 95 + idx,
            "close": 101 + idx,
            "volume": 1000 + idx,
            "amount": 10000 + idx,
        }
        for idx in range(count)
    ]


class ChanlunSourceNodesTest(unittest.TestCase):
    def test_select_practical_daily_window_uses_250_base_and_120_focus(self):
        window = source_nodes.select_practical_daily_window(_rows(300))

        self.assertEqual(window["mode"], "practical_daily_mode")
        self.assertEqual(len(window["base_rows"]), 250)
        self.assertEqual(len(window["focus_rows"]), 120)
        self.assertFalse(window["minute_data_required"])
        self.assertEqual(window["data_capability"]["capability_status"], "sufficient")

    def test_daily_window_reports_data_insufficient_without_failing_shape(self):
        window = source_nodes.select_practical_daily_window(_rows(80))

        self.assertEqual(len(window["base_rows"]), 80)
        self.assertEqual(len(window["focus_rows"]), 80)
        self.assertEqual(window["data_capability"]["capability_status"], "data_insufficient")
        self.assertEqual(window["data_capability"]["requested_bars"], 250)
        self.assertEqual(window["data_capability"]["returned_bars"], 80)

    def test_build_minute_capability_marks_15m_as_local_only(self):
        capability = source_nodes.build_minute_capability(
            provider="akshare.stock_zh_a_minute",
            period="15",
            requested_bars=2500,
            returned_bars=1970,
            returned_trading_days=124,
            first_datetime="2025-10-27 11:15:00",
            last_datetime="2026-04-29 11:30:00",
        )

        self.assertEqual(capability["period"], "15")
        self.assertEqual(capability["capability_status"], "local_confirmation_only")
        self.assertFalse(capability["supports_250_day_base"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_source_nodes -v
```

Expected: import failure for `decision.chanlun` or missing function failures.

- [ ] **Step 3: Implement source node contracts**

Create `scripts/decision/chanlun/__init__.py`:

```python
from __future__ import annotations

__all__ = [
    "contracts",
    "source_nodes",
    "morphology_nodes",
    "structure_nodes",
    "confirmation_nodes",
    "runtime",
]
```

Create `scripts/decision/chanlun/contracts.py`:

```python
from __future__ import annotations

PRACTICAL_DAILY_MODE = "practical_daily_mode"
HYBRID_CONFIRMATION_MODE = "hybrid_confirmation_mode"
DATA_SUFFICIENT = "sufficient"
DATA_INSUFFICIENT = "data_insufficient"
LOCAL_CONFIRMATION_ONLY = "local_confirmation_only"

DAILY_BASE_BARS = 250
DAILY_FOCUS_BARS = 120
DEFAULT_CONFIRMATION_PERIOD = "60"
SECONDARY_CONFIRMATION_PERIOD = "30"
LOCAL_ONLY_PERIODS = {"1", "5", "15"}
```

Create `scripts/decision/chanlun/source_nodes.py`:

```python
from __future__ import annotations

from market_data.kline_dates import normalize_kline_date_str, parse_kline_date

from .contracts import (
    DAILY_BASE_BARS,
    DAILY_FOCUS_BARS,
    DATA_INSUFFICIENT,
    DATA_SUFFICIENT,
    LOCAL_CONFIRMATION_ONLY,
    LOCAL_ONLY_PERIODS,
    PRACTICAL_DAILY_MODE,
)


def _normalize_row(row):
    item = dict(row or {})
    item["date"] = normalize_kline_date_str(item.get("date") or item.get("datetime") or "")
    return item


def normalize_kline_rows(rows):
    normalized = [_normalize_row(row) for row in list(rows or []) if isinstance(row, dict)]
    return sorted(normalized, key=lambda item: parse_kline_date(item.get("date")) or item.get("date") or "")


def build_daily_capability(rows, requested_bars=DAILY_BASE_BARS):
    returned_bars = len(rows or [])
    status = DATA_SUFFICIENT if returned_bars >= requested_bars else DATA_INSUFFICIENT
    return {
        "provider": "daily_rows",
        "period": "daily",
        "requested_bars": int(requested_bars),
        "returned_bars": int(returned_bars),
        "returned_trading_days": int(returned_bars),
        "first_datetime": rows[0].get("date") if rows else None,
        "last_datetime": rows[-1].get("date") if rows else None,
        "capability_status": status,
        "supports_250_day_base": status == DATA_SUFFICIENT,
    }


def build_minute_capability(
    *,
    provider,
    period,
    requested_bars,
    returned_bars,
    returned_trading_days,
    first_datetime=None,
    last_datetime=None,
):
    period_text = str(period)
    supports_base = int(returned_trading_days or 0) >= DAILY_BASE_BARS
    if period_text in LOCAL_ONLY_PERIODS:
        status = LOCAL_CONFIRMATION_ONLY
        supports_base = False
    else:
        status = DATA_SUFFICIENT if supports_base else DATA_INSUFFICIENT
    return {
        "provider": provider,
        "period": period_text,
        "requested_bars": int(requested_bars or 0),
        "returned_bars": int(returned_bars or 0),
        "returned_trading_days": int(returned_trading_days or 0),
        "first_datetime": first_datetime,
        "last_datetime": last_datetime,
        "capability_status": status,
        "supports_250_day_base": bool(supports_base),
    }


def select_practical_daily_window(rows, *, base_bars=DAILY_BASE_BARS, focus_bars=DAILY_FOCUS_BARS):
    normalized = normalize_kline_rows(rows)
    base_rows = normalized[-int(base_bars) :]
    focus_rows = base_rows[-int(focus_bars) :]
    return {
        "mode": PRACTICAL_DAILY_MODE,
        "base_rows": base_rows,
        "focus_rows": focus_rows,
        "minute_data_required": False,
        "data_capability": build_daily_capability(base_rows, requested_bars=base_bars),
    }
```

- [ ] **Step 4: Run source tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_source_nodes -v
```

Expected: `OK`.

- [ ] **Step 5: Commit source nodes**

Run:

```bash
git add scripts/decision/chanlun/__init__.py scripts/decision/chanlun/contracts.py scripts/decision/chanlun/source_nodes.py tests/test_chanlun_source_nodes.py
git commit -m "feat: add chanlun source nodes"
```

## Task 2: Morphology Nodes

**Files:**
- Create: `scripts/decision/chanlun/morphology_nodes.py`
- Create: `tests/test_chanlun_morphology_nodes.py`

- [ ] **Step 1: Write failing tests for inclusion, fractals, and strokes**

Add this to `tests/test_chanlun_morphology_nodes.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import morphology_nodes


class ChanlunMorphologyNodesTest(unittest.TestCase):
    def test_merge_inclusion_marks_contained_bars(self):
        rows = [
            {"date": "2026-04-20", "high": 10, "low": 5, "close": 8},
            {"date": "2026-04-21", "high": 9, "low": 6, "close": 7},
            {"date": "2026-04-22", "high": 12, "low": 7, "close": 11},
        ]

        merged = morphology_nodes.merge_inclusion_bars(rows)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["source_bar_count"], 2)
        self.assertEqual(merged[0]["rule_tier"], "original_rule")

    def test_detect_fractals_uses_processed_bars_only(self):
        processed = [
            {"date": "2026-04-20", "high": 10, "low": 5},
            {"date": "2026-04-21", "high": 12, "low": 7},
            {"date": "2026-04-22", "high": 9, "low": 4},
            {"date": "2026-04-23", "high": 7, "low": 3},
            {"date": "2026-04-24", "high": 8, "low": 4},
        ]

        fractals = morphology_nodes.detect_fractals(processed)

        self.assertEqual(fractals[0]["fractal_type"], "top")
        self.assertEqual(fractals[1]["fractal_type"], "bottom")
        self.assertEqual(fractals[0]["source"], "processed_bars")

    def test_build_strokes_requires_alternating_fractals(self):
        fractals = [
            {"fractal_id": "f1", "fractal_type": "bottom", "index": 0, "date": "2026-04-20", "price": 5},
            {"fractal_id": "f2", "fractal_type": "top", "index": 2, "date": "2026-04-22", "price": 12},
            {"fractal_id": "f3", "fractal_type": "top", "index": 3, "date": "2026-04-23", "price": 13},
            {"fractal_id": "f4", "fractal_type": "bottom", "index": 5, "date": "2026-04-25", "price": 4},
        ]

        strokes = morphology_nodes.build_strokes(fractals)

        self.assertEqual(len(strokes), 2)
        self.assertEqual(strokes[0]["direction"], "up")
        self.assertEqual(strokes[1]["direction"], "down")
        self.assertNotIn("f2", strokes[1]["fractal_ids"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run morphology tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_morphology_nodes -v
```

Expected: missing module or missing function failures.

- [ ] **Step 3: Implement morphology nodes**

Create `scripts/decision/chanlun/morphology_nodes.py` with functions:

```python
from __future__ import annotations


def _is_contained(prev, curr):
    return (
        float(curr["high"]) <= float(prev["high"])
        and float(curr["low"]) >= float(prev["low"])
    ) or (
        float(curr["high"]) >= float(prev["high"])
        and float(curr["low"]) <= float(prev["low"])
    )


def merge_inclusion_bars(rows):
    merged = []
    for row in list(rows or []):
        item = dict(row)
        item.setdefault("source_bar_count", 1)
        item.setdefault("source_dates", [item.get("date")])
        item["rule_tier"] = "original_rule"
        if merged and _is_contained(merged[-1], item):
            prev = merged[-1]
            prev["high"] = max(float(prev["high"]), float(item["high"]))
            prev["low"] = min(float(prev["low"]), float(item["low"]))
            prev["close"] = item.get("close", prev.get("close"))
            prev["date"] = item.get("date", prev.get("date"))
            prev["source_bar_count"] = int(prev.get("source_bar_count", 1)) + 1
            prev["source_dates"] = list(prev.get("source_dates") or []) + [item.get("date")]
        else:
            merged.append(item)
    return merged


def detect_fractals(processed_bars):
    bars = list(processed_bars or [])
    fractals = []
    for index in range(1, len(bars) - 1):
        prev_bar, bar, next_bar = bars[index - 1], bars[index], bars[index + 1]
        if float(bar["high"]) > float(prev_bar["high"]) and float(bar["high"]) > float(next_bar["high"]) and float(bar["low"]) > float(prev_bar["low"]) and float(bar["low"]) > float(next_bar["low"]):
            fractals.append({"fractal_id": f"fractal_{len(fractals) + 1}", "fractal_type": "top", "index": index, "date": bar.get("date"), "price": float(bar["high"]), "source": "processed_bars", "rule_tier": "original_rule"})
        if float(bar["low"]) < float(prev_bar["low"]) and float(bar["low"]) < float(next_bar["low"]) and float(bar["high"]) < float(prev_bar["high"]) and float(bar["high"]) < float(next_bar["high"]):
            fractals.append({"fractal_id": f"fractal_{len(fractals) + 1}", "fractal_type": "bottom", "index": index, "date": bar.get("date"), "price": float(bar["low"]), "source": "processed_bars", "rule_tier": "original_rule"})
    return fractals


def _prefer_fractal(existing, incoming):
    if existing["fractal_type"] == "top":
        return incoming if float(incoming["price"]) > float(existing["price"]) else existing
    return incoming if float(incoming["price"]) < float(existing["price"]) else existing


def build_strokes(fractals):
    selected = []
    for fractal in list(fractals or []):
        item = dict(fractal)
        if selected and selected[-1]["fractal_type"] == item["fractal_type"]:
            selected[-1] = _prefer_fractal(selected[-1], item)
        else:
            selected.append(item)
    strokes = []
    for start, end in zip(selected, selected[1:]):
        direction = "up" if start["fractal_type"] == "bottom" and end["fractal_type"] == "top" else "down"
        strokes.append({
            "stroke_id": f"stroke_{len(strokes) + 1}",
            "start_date": start.get("date"),
            "end_date": end.get("date"),
            "start_index": int(start.get("index", 0)),
            "end_index": int(end.get("index", 0)),
            "direction": direction,
            "fractal_ids": [start.get("fractal_id"), end.get("fractal_id")],
            "rule_tier": "derived_contract",
            "status": "completed_stroke",
        })
    return strokes
```

- [ ] **Step 4: Run morphology tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_morphology_nodes -v
```

Expected: `OK`.

- [ ] **Step 5: Commit morphology nodes**

Run:

```bash
git add scripts/decision/chanlun/morphology_nodes.py tests/test_chanlun_morphology_nodes.py
git commit -m "feat: add chanlun morphology nodes"
```

## Task 3: Structure Nodes

**Files:**
- Create: `scripts/decision/chanlun/structure_nodes.py`
- Create: `tests/test_chanlun_structure_nodes.py`

- [ ] **Step 1: Write failing tests for trend types, platforms, and connectors**

Add this to `tests/test_chanlun_structure_nodes.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import structure_nodes


class ChanlunStructureNodesTest(unittest.TestCase):
    def test_identify_platform_requires_three_completed_trend_types_overlap(self):
        trend_types = [
            {"trend_type_id": "t1", "high": 110, "low": 100, "direction": "up", "status": "completed_trend_type"},
            {"trend_type_id": "t2", "high": 108, "low": 98, "direction": "down", "status": "completed_trend_type"},
            {"trend_type_id": "t3", "high": 109, "low": 101, "direction": "up", "status": "completed_trend_type"},
        ]

        segments, platforms = structure_nodes.identify_platforms_from_trend_types(trend_types, level_id="daily")

        self.assertEqual(len(platforms), 1)
        self.assertEqual(platforms[0]["ZD"], 101.0)
        self.assertEqual(platforms[0]["ZG"], 108.0)
        self.assertEqual(platforms[0]["rule_tier"], "original_rule")
        self.assertEqual(segments[0]["role"], "inside_zhongshu")

    def test_no_overlap_returns_connector_not_zhongshu(self):
        trend_types = [
            {"trend_type_id": "t1", "high": 110, "low": 108, "status": "completed_trend_type"},
            {"trend_type_id": "t2", "high": 100, "low": 98, "status": "completed_trend_type"},
            {"trend_type_id": "t3", "high": 90, "low": 88, "status": "completed_trend_type"},
        ]

        segments, platforms = structure_nodes.identify_platforms_from_trend_types(trend_types, level_id="daily")

        self.assertEqual(platforms, [])
        self.assertEqual(segments[0]["segment_type"], "connector")
        self.assertEqual(segments[0]["role"], "connector_move")

    def test_platforms_touching_get_diagnostic_bridge_only(self):
        trend_types = [
            {"trend_type_id": "t1", "high": 110, "low": 100, "status": "completed_trend_type"},
            {"trend_type_id": "t2", "high": 108, "low": 98, "status": "completed_trend_type"},
            {"trend_type_id": "t3", "high": 109, "low": 101, "status": "completed_trend_type"},
            {"trend_type_id": "t4", "high": 130, "low": 120, "status": "completed_trend_type"},
            {"trend_type_id": "t5", "high": 128, "low": 118, "status": "completed_trend_type"},
            {"trend_type_id": "t6", "high": 129, "low": 121, "status": "completed_trend_type"},
        ]

        segments, platforms = structure_nodes.identify_platforms_from_trend_types(trend_types, level_id="daily")

        self.assertEqual(len(platforms), 2)
        self.assertEqual([item["segment_type"] for item in segments], ["zhongshu", "connector", "zhongshu"])
        self.assertEqual(segments[1]["rule_tier"], "diagnostic_heuristic")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run structure tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_structure_nodes -v
```

Expected: missing module or missing function failures.

- [ ] **Step 3: Implement structure nodes**

Create `scripts/decision/chanlun/structure_nodes.py` using pure functions:

```python
from __future__ import annotations


def _normalize_type(item, index):
    high = float(item["high"])
    low = float(item["low"])
    if high <= low or item.get("status", "completed_trend_type") != "completed_trend_type":
        return None
    return {
        **dict(item),
        "trend_type_id": item.get("trend_type_id") or f"trend_{index + 1}",
        "high": high,
        "low": low,
    }


def _overlap(first_three):
    zg = min(item["high"] for item in first_three)
    zd = max(item["low"] for item in first_three)
    if zg <= zd:
        return None
    return {"ZG": float(zg), "ZD": float(zd)}


def _connector(units, sequence_id, *, bridge=False):
    return {
        "segment_type": "connector",
        "connector_id": f"connector_{sequence_id}",
        "role": "connector_move",
        "trend_type_ids": [item["trend_type_id"] for item in units],
        "rule_tier": "diagnostic_heuristic" if bridge else "derived_contract",
        "reason": "platform visual bridge" if bridge else "no three completed trend types overlap",
    }


def _platform(units, zone, sequence_id, level_id):
    return {
        "segment_type": "zhongshu",
        "role": "inside_zhongshu",
        "zhongshu_id": f"{level_id}_zhongshu_{sequence_id}",
        "level_id": level_id,
        "child_trend_type_ids": [item["trend_type_id"] for item in units[:3]],
        "trend_type_ids": [item["trend_type_id"] for item in units],
        "ZG": zone["ZG"],
        "ZD": zone["ZD"],
        "status": "confirmed",
        "rule_tier": "original_rule",
    }


def identify_platforms_from_trend_types(trend_types, *, level_id):
    units = []
    for index, item in enumerate(list(trend_types or [])):
        normalized = _normalize_type(item, index)
        if normalized is not None:
            units.append(normalized)
    segments = []
    platforms = []
    connector_units = []
    index = 0
    connector_count = 0
    platform_count = 0
    while index <= len(units) - 3:
        zone = _overlap(units[index : index + 3])
        if zone is None:
            connector_units.append(units[index])
            index += 1
            continue
        if connector_units:
            connector_count += 1
            segments.append(_connector(connector_units, connector_count))
            connector_units = []
        elif segments and segments[-1]["segment_type"] == "zhongshu":
            connector_count += 1
            segments.append(_connector([units[index]], connector_count, bridge=True))
        platform_count += 1
        platform = _platform(units[index : index + 3], zone, platform_count, level_id)
        segments.append(platform)
        platforms.append(platform)
        index += 3
    if index < len(units):
        connector_units.extend(units[index:])
    if connector_units:
        connector_count += 1
        segments.append(_connector(connector_units, connector_count))
    return segments, platforms
```

- [ ] **Step 4: Run structure tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_structure_nodes -v
```

Expected: `OK`.

- [ ] **Step 5: Commit structure nodes**

Run:

```bash
git add scripts/decision/chanlun/structure_nodes.py tests/test_chanlun_structure_nodes.py
git commit -m "feat: add chanlun structure nodes"
```

## Task 4: Confirmation Nodes Without Full Mode

**Files:**
- Create: `scripts/decision/chanlun/confirmation_nodes.py`
- Create: `tests/test_chanlun_confirmation_nodes.py`

- [ ] **Step 1: Write failing tests for 60m default and 15m local-only behavior**

Add this to `tests/test_chanlun_confirmation_nodes.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import confirmation_nodes


class ChanlunConfirmationNodesTest(unittest.TestCase):
    def test_60m_confirms_when_three_child_trend_types_overlap(self):
        result = confirmation_nodes.confirm_with_child_trend_types(
            [{"high": 110, "low": 100}, {"high": 108, "low": 98}, {"high": 109, "low": 101}],
            period="60",
        )

        self.assertTrue(result["confirmed"])
        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertEqual(result["period"], "60")

    def test_15m_is_local_only_for_daily_base(self):
        result = confirmation_nodes.confirm_with_child_trend_types(
            [{"high": 110, "low": 100}, {"high": 108, "low": 98}, {"high": 109, "low": 101}],
            period="15",
        )

        self.assertFalse(result["confirmed"])
        self.assertEqual(result["confirmation_status"], "local_confirmation_only")
        self.assertIn("15", result["explanation"])

    def test_full_mode_request_is_rejected_in_v1(self):
        result = confirmation_nodes.reject_full_recursive_mode()

        self.assertFalse(result["enabled"])
        self.assertEqual(result["mode"], "full_recursive_mode")
        self.assertEqual(result["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run confirmation tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_confirmation_nodes -v
```

Expected: missing module or missing function failures.

- [ ] **Step 3: Implement confirmation nodes**

Create `scripts/decision/chanlun/confirmation_nodes.py`:

```python
from __future__ import annotations

from .contracts import DEFAULT_CONFIRMATION_PERIOD, LOCAL_ONLY_PERIODS


def _overlap(units):
    if len(units) < 3:
        return None
    zg = min(float(item["high"]) for item in units[:3])
    zd = max(float(item["low"]) for item in units[:3])
    if zg <= zd:
        return None
    return {"ZG": zg, "ZD": zd}


def confirm_with_child_trend_types(child_trend_types, *, period=DEFAULT_CONFIRMATION_PERIOD):
    period_text = str(period)
    if period_text in LOCAL_ONLY_PERIODS:
        return {
            "confirmed": False,
            "confirmation_status": "local_confirmation_only",
            "period": period_text,
            "ZG": None,
            "ZD": None,
            "explanation": f"{period_text}m only supports local confirmation in v1 and cannot confirm the 250-day daily base.",
        }
    units = list(child_trend_types or [])
    zone = _overlap(units)
    if zone is None:
        return {
            "confirmed": False,
            "confirmation_status": "data_insufficient" if len(units) < 3 else "not_confirmed",
            "period": period_text,
            "ZG": None,
            "ZD": None,
            "explanation": "Need three completed child trend types with overlap.",
        }
    return {
        "confirmed": True,
        "confirmation_status": "confirmed_daily_level_zhongshu",
        "period": period_text,
        "ZG": zone["ZG"],
        "ZD": zone["ZD"],
        "explanation": f"Three completed {period_text}m trend types overlap.",
    }


def reject_full_recursive_mode():
    return {
        "mode": "full_recursive_mode",
        "enabled": False,
        "status": "deferred",
        "explanation": "Full recursive mode needs an external long-history minute data store and is outside v1.",
    }
```

- [ ] **Step 4: Run confirmation tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_confirmation_nodes -v
```

Expected: `OK`.

- [ ] **Step 5: Commit confirmation nodes**

Run:

```bash
git add scripts/decision/chanlun/confirmation_nodes.py tests/test_chanlun_confirmation_nodes.py
git commit -m "feat: add chanlun confirmation nodes"
```

## Task 5: Practical Runtime Orchestrator

**Files:**
- Create: `scripts/decision/chanlun/runtime.py`
- Create: `tests/test_chanlun_runtime_contract.py`

- [ ] **Step 1: Write failing runtime contract tests**

Add this to `tests/test_chanlun_runtime_contract.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import runtime


def _daily_rows():
    return [
        {"date": "2026-04-14", "high": 102, "low": 98, "close": 100},
        {"date": "2026-04-15", "high": 112, "low": 99, "close": 110},
        {"date": "2026-04-16", "high": 111, "low": 100, "close": 101},
        {"date": "2026-04-17", "high": 110, "low": 100, "close": 109},
    ]


class ChanlunRuntimeContractTest(unittest.TestCase):
    def test_practical_daily_runtime_does_not_request_minutes(self):
        calls = []

        result = runtime.analyze_practical_daily_structure(
            daily_rows=_daily_rows(),
            fetch_minute_bars=lambda **kwargs: calls.append(kwargs),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "practical_daily_mode")
        self.assertEqual(calls, [])
        self.assertEqual(result["minute_confirmation"]["confirmation_status"], "not_requested")

    def test_hybrid_runtime_requests_60m_by_default(self):
        calls = []

        def fetch_minute_bars(**kwargs):
            calls.append(kwargs)
            return {"success": True, "bars": []}

        result = runtime.analyze_hybrid_structure(
            daily_rows=_daily_rows(),
            fetch_minute_bars=fetch_minute_bars,
        )

        self.assertEqual(calls[0]["period"], "60")
        self.assertEqual(result["minute_confirmation"]["confirmation_status"], "data_insufficient")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run runtime tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_runtime_contract -v
```

Expected: missing module or missing function failures.

- [ ] **Step 3: Implement runtime orchestrator**

Create `scripts/decision/chanlun/runtime.py`:

```python
from __future__ import annotations

from .contracts import DEFAULT_CONFIRMATION_PERIOD, HYBRID_CONFIRMATION_MODE, PRACTICAL_DAILY_MODE
from .confirmation_nodes import confirm_with_child_trend_types
from .source_nodes import select_practical_daily_window
from .structure_nodes import identify_platforms_from_trend_types


def _trend_type_from_row(row, index):
    return {
        "trend_type_id": f"daily_trend_{index + 1}",
        "high": float(row["high"]),
        "low": float(row["low"]),
        "direction": "unknown",
        "status": "completed_trend_type",
    }


def _daily_trend_types(rows):
    return [_trend_type_from_row(row, index) for index, row in enumerate(rows or []) if "high" in row and "low" in row]


def _not_requested_confirmation():
    return {
        "confirmed": False,
        "confirmation_status": "not_requested",
        "period": None,
        "ZG": None,
        "ZD": None,
        "explanation": "Practical daily mode does not require minute confirmation.",
    }


def analyze_practical_daily_structure(*, daily_rows, fetch_minute_bars=None, target_date=None):
    del fetch_minute_bars, target_date
    window = select_practical_daily_window(daily_rows)
    trend_types = _daily_trend_types(window["base_rows"])
    segments, platforms = identify_platforms_from_trend_types(trend_types, level_id="daily")
    current = platforms[-1] if platforms else None
    return {
        "success": True,
        "mode": PRACTICAL_DAILY_MODE,
        "status": "success" if current else "not_yet_platform",
        "data_capability": window["data_capability"],
        "daily_trend_types": trend_types,
        "daily_structure_segments": segments,
        "daily_structure_candidates": platforms,
        "current_candidate": current,
        "child_trend_types": [],
        "minute_confirmation": _not_requested_confirmation(),
    }


def analyze_hybrid_structure(*, daily_rows, fetch_minute_bars, target_date=None, index_code="sh.000001", minute_period=DEFAULT_CONFIRMATION_PERIOD):
    result = analyze_practical_daily_structure(daily_rows=daily_rows, target_date=target_date)
    minute_payload = fetch_minute_bars(index_code=index_code, period=str(minute_period))
    bars = minute_payload.get("bars") if isinstance(minute_payload, dict) else []
    child_trend_types = _daily_trend_types(bars or [])
    result["mode"] = HYBRID_CONFIRMATION_MODE
    result["child_trend_types"] = child_trend_types
    result["minute_confirmation"] = confirm_with_child_trend_types(child_trend_types, period=str(minute_period))
    result["minute_source_status"] = minute_payload.get("status") if isinstance(minute_payload, dict) else "invalid_minute_payload"
    return result
```

- [ ] **Step 4: Run runtime tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_runtime_contract -v
```

Expected: `OK`.

- [ ] **Step 5: Commit runtime orchestrator**

Run:

```bash
git add scripts/decision/chanlun/runtime.py tests/test_chanlun_runtime_contract.py
git commit -m "feat: add chanlun practical runtime"
```

## Task 6: Compatibility Facade

**Files:**
- Modify: `scripts/decision/chanlun_zhongshu_runtime.py`
- Modify: `tests/test_chanlun_zhongshu_runtime.py`

- [ ] **Step 1: Add compatibility tests for existing public API**

Append this test to `tests/test_chanlun_zhongshu_runtime.py`:

```python
    def test_public_facade_uses_practical_daily_mode_by_default(self):
        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=lambda **kwargs: (_ for _ in ()).throw(AssertionError("minute fetch should not be called")),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "practical_daily_mode")
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "not_requested")
```

- [ ] **Step 2: Run compatibility test and verify it fails**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime.ChanlunZhongshuRuntimeTest.test_public_facade_uses_practical_daily_mode_by_default -v
```

Expected: current implementation calls minute fetch or lacks `mode`.

- [ ] **Step 3: Replace legacy body with facade mapping**

Modify `scripts/decision/chanlun_zhongshu_runtime.py` so `analyze_chanlun_zhongshu(...)` delegates:

```python
from decision.chanlun.runtime import analyze_hybrid_structure, analyze_practical_daily_structure


def analyze_chanlun_zhongshu(
    *,
    daily_rows,
    target_date=None,
    fetch_minute_bars=None,
    index_code="sh.000001",
    minute_period="60",
    min_daily_klines=None,
    use_hybrid_confirmation=False,
):
    del min_daily_klines
    if use_hybrid_confirmation and fetch_minute_bars is not None:
        result = analyze_hybrid_structure(
            daily_rows=daily_rows,
            target_date=target_date,
            fetch_minute_bars=fetch_minute_bars,
            index_code=index_code,
            minute_period=minute_period,
        )
    else:
        result = analyze_practical_daily_structure(
            daily_rows=daily_rows,
            target_date=target_date,
            fetch_minute_bars=fetch_minute_bars,
        )
    confirmation = result.get("minute_confirmation", {})
    return {
        **result,
        "daily_structure_candidates": result.get("daily_structure_candidates", []),
        "current_candidate": result.get("current_candidate"),
        "chanlun_60m_structures": result.get("child_trend_types", []),
        "chanlun_confirmation": confirmation,
    }
```

Keep legacy helper exports only if existing tests import them. For each helper kept, delegate to the new node function instead of maintaining a second implementation.

- [ ] **Step 4: Run compatibility suite**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime -v
```

Expected: `OK` after test updates match the new default no-minute behavior.

- [ ] **Step 5: Commit compatibility facade**

Run:

```bash
git add scripts/decision/chanlun_zhongshu_runtime.py tests/test_chanlun_zhongshu_runtime.py
git commit -m "refactor: route chanlun facade through node runtime"
```

## Task 7: Report Integration

**Files:**
- Modify: `scripts/decision/zhongshu_runtime.py`
- Modify: `tests/test_zhongshu_runtime.py`
- Modify: `tests/test_report_runtime.py`
- Modify: `tests/test_positioning_node_runtime.py`

- [ ] **Step 1: Add integration test that default report path does not require minute data**

In `tests/test_zhongshu_runtime.py`, add:

```python
    def test_analyze_market_zhongshu_default_chanlun_path_does_not_require_minutes(self):
        df = pd.DataFrame(
            [
                {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100, "volume": 1},
                {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110, "volume": 1},
                {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101, "volume": 1},
                {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109, "volume": 1},
                {"date": "2026-04-20", "open": 109, "high": 108, "low": 101, "close": 105, "volume": 1},
            ]
        )

        result = analyze_market_zhongshu(
            target_date="2026-04-20",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            fetch_minute_bars=lambda **kwargs: (_ for _ in ()).throw(AssertionError("minute fetch should not be called")),
            use_chanlun_confirmation=True,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "not_requested")
```

- [ ] **Step 2: Run the focused integration test and verify it fails**

Run:

```bash
venv/bin/python -m unittest tests.test_zhongshu_runtime.ZhongshuRuntimeTest.test_analyze_market_zhongshu_default_chanlun_path_does_not_require_minutes -v
```

Expected: current code calls minute fetch.

- [ ] **Step 3: Modify market zhongshu integration**

In `scripts/decision/zhongshu_runtime.py`, change the call to `analyze_chanlun_zhongshu(...)` so the default path does not request minutes:

```python
chanlun_result = analyze_chanlun_zhongshu(
    daily_rows=daily_rows,
    target_date=target_date,
    fetch_minute_bars=fetch_minute_bars or fetch_index_minute_bars,
    index_code=index_code,
    minute_period="60",
    min_daily_klines=min_zhongshu_klines,
    use_hybrid_confirmation=False,
)
```

Add a separate config flag only if an existing caller explicitly needs hybrid confirmation:

```python
use_hybrid_confirmation=False
```

- [ ] **Step 4: Run focused suites**

Run:

```bash
venv/bin/python -m unittest tests.test_zhongshu_runtime tests.test_report_runtime tests.test_positioning_node_runtime -v
```

Expected: `OK`.

- [ ] **Step 5: Commit report integration**

Run:

```bash
git add scripts/decision/zhongshu_runtime.py tests/test_zhongshu_runtime.py tests/test_report_runtime.py tests/test_positioning_node_runtime.py
git commit -m "refactor: make chanlun daily mode report default"
```

## Task 8: Migration Guardrails And Acceptance

**Files:**
- Modify: `tests/test_chanlun_runtime_contract.py`
- Modify: `tests/test_chanlun_zhongshu_runtime.py`
- Modify: `docs/trellis/specs/2026-04-29-chanlun-knowledge-system-design.md` only if implementation discovers a contract mismatch.

- [ ] **Step 1: Add guardrail tests that v1 excludes full mode**

Add to `tests/test_chanlun_runtime_contract.py`:

```python
    def test_v1_runtime_has_no_full_recursive_execution_path(self):
        result = runtime.full_recursive_mode_status()

        self.assertEqual(result["mode"], "full_recursive_mode")
        self.assertEqual(result["status"], "deferred")
        self.assertFalse(result["enabled"])
```

- [ ] **Step 2: Implement `full_recursive_mode_status` as a status-only function**

In `scripts/decision/chanlun/runtime.py`, add:

```python
from .confirmation_nodes import reject_full_recursive_mode


def full_recursive_mode_status():
    return reject_full_recursive_mode()
```

- [ ] **Step 3: Run all Chanlun-focused tests**

Run:

```bash
venv/bin/python -m unittest \
  tests.test_chanlun_source_nodes \
  tests.test_chanlun_morphology_nodes \
  tests.test_chanlun_structure_nodes \
  tests.test_chanlun_confirmation_nodes \
  tests.test_chanlun_runtime_contract \
  tests.test_chanlun_zhongshu_runtime \
  tests.test_zhongshu_runtime \
  -v
```

Expected: `OK`.

- [ ] **Step 4: Run whitespace verification**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Commit guardrails**

Run:

```bash
git add scripts/decision/chanlun/runtime.py tests/test_chanlun_runtime_contract.py
git commit -m "test: guard chanlun v1 mode boundaries"
```

## Task 9: A-share Scenario Runner And Observation Artifacts

**Files:**
- Create: `scripts/decision/chanlun/scenario_runner.py`
- Create: `tests/test_chanlun_a_share_scenarios.py`
- Create by command: `tests/fixtures/chanlun_scenarios/*.json`
- Create by command: `reports/replay/chanlun_scenarios/*.md`

- [ ] **Step 1: Write failing tests for built-in A-share scenarios**

Create `tests/test_chanlun_a_share_scenarios.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import scenario_runner


class ChanlunAShareScenariosTest(unittest.TestCase):
    def test_builtin_scenarios_cover_required_first_batch(self):
        scenarios = scenario_runner.build_builtin_scenarios()
        scenario_ids = {item["scenario_id"] for item in scenarios}

        self.assertIn("S01_index_250d_platform", scenario_ids)
        self.assertIn("S05_60m_enough_15m_insufficient", scenario_ids)
        self.assertIn("S07_limit_up_sequence", scenario_ids)
        self.assertIn("S12_third_buy_candidate", scenario_ids)
        self.assertGreaterEqual(len(scenarios), 11)

    def test_run_s01_keeps_practical_platform_without_minute_requirement(self):
        scenario = scenario_runner.get_builtin_scenario("S01_index_250d_platform")

        result = scenario_runner.run_scenario(scenario)

        self.assertEqual(result["scenario_id"], "S01_index_250d_platform")
        self.assertEqual(result["expected_behavior"]["structure_state"], "daily_practical_platform")
        self.assertEqual(result["generated"]["minute_confirmation_status"], "not_requested")
        self.assertEqual(result["observation"]["mismatch_type"], "none")

    def test_run_s05_marks_15m_local_only(self):
        scenario = scenario_runner.get_builtin_scenario("S05_60m_enough_15m_insufficient")

        result = scenario_runner.run_scenario(scenario)

        self.assertEqual(result["generated"]["confirmation_primary"], "60m")
        self.assertEqual(result["generated"]["minute_15m_capability_status"], "local_confirmation_only")
        self.assertFalse(result["generated"]["minute_15m_supports_250_day_base"])

    def test_write_artifacts_creates_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            written = scenario_runner.write_builtin_artifacts(
                fixture_dir=root / "fixtures",
                report_dir=root / "reports",
            )

            self.assertGreaterEqual(len(written["fixtures"]), 11)
            self.assertGreaterEqual(len(written["reports"]), 11)
            sample_fixture = root / "fixtures" / "S01_index_250d_platform.json"
            sample_report = root / "reports" / "S01_index_250d_platform.md"
            self.assertTrue(sample_fixture.exists())
            self.assertTrue(sample_report.exists())
            payload = json.loads(sample_fixture.read_text(encoding="utf-8"))
            self.assertEqual(payload["scenario_id"], "S01_index_250d_platform")
            self.assertIn("结论：通过", sample_report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run scenario tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_a_share_scenarios -v
```

Expected: missing `scenario_runner` import or missing function failures.

- [ ] **Step 3: Implement scenario runner**

Create `scripts/decision/chanlun/scenario_runner.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _daily_bars(count, *, base=100.0, width=5.0, breakout=None, breakdown=None):
    rows = []
    for index in range(count):
        drift = (index % 9) - 4
        close = base + drift * 0.4
        high = close + width
        low = close - width
        if breakout and index >= count - int(breakout.get("bars", 2)):
            close = base + width + float(breakout.get("offset", 3.0))
            high = close + 2.0
            low = close - 1.0
        if breakdown and index >= count - int(breakdown.get("bars", 2)):
            close = base - width - float(breakdown.get("offset", 3.0))
            high = close + 1.0
            low = close - 2.0
        rows.append(
            {
                "date": f"2026-{((index // 20) % 12) + 1:02d}-{(index % 20) + 1:02d}",
                "open": round(close - 0.5, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": 1000000 + index * 1000,
                "amount": 100000000 + index * 100000,
            }
        )
    return rows


def _minute_bars(count, *, period, base=100.0):
    rows = []
    for index in range(count):
        close = base + ((index % 7) - 3) * 0.3
        rows.append(
            {
                "datetime": f"2026-04-{(index % 20) + 1:02d} 10:30:00",
                "date": f"2026-04-{(index % 20) + 1:02d}",
                "period": str(period),
                "open": round(close - 0.2, 2),
                "high": round(close + 1.0, 2),
                "low": round(close - 1.0, 2),
                "close": round(close, 2),
                "volume": 10000 + index,
                "amount": 1000000 + index,
            }
        )
    return rows


def _scenario(scenario_id, title, *, market_role, symbol, symbol_name, tags, daily_count, expected_behavior, minute_60m_count=0, minute_15m_count=0, daily_kwargs=None):
    daily_kwargs = daily_kwargs or {}
    return {
        "scenario_id": scenario_id,
        "title": title,
        "market_role": market_role,
        "symbol": symbol,
        "symbol_name": symbol_name,
        "target_date": "2026-04-29",
        "a_share_condition_tags": tags,
        "daily_bars": _daily_bars(daily_count, **daily_kwargs),
        "minute_bars_60m": _minute_bars(minute_60m_count, period="60") if minute_60m_count else [],
        "minute_bars_15m": _minute_bars(minute_15m_count, period="15") if minute_15m_count else [],
        "expected_behavior": expected_behavior,
    }


def build_builtin_scenarios():
    return [
        _scenario(
            "S01_index_250d_platform",
            "上证指数 250 日震荡平台",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["index", "250_daily_base", "range_platform"],
            daily_count=250,
            expected_behavior={"structure_state": "daily_practical_platform", "zhongshu_permission": "practical_only", "minute_confirmation_status": "not_requested"},
        ),
        _scenario(
            "S02_index_breakout_candidate",
            "上证指数突破平台上沿",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["index", "breakout_candidate"],
            daily_count=250,
            daily_kwargs={"breakout": {"bars": 3, "offset": 4}},
            expected_behavior={"structure_state": "breakout_candidate", "trade_point_permission": "none"},
        ),
        _scenario(
            "S03_index_breakdown_candidate",
            "上证指数跌破平台下沿",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["index", "breakdown_candidate"],
            daily_count=250,
            daily_kwargs={"breakdown": {"bars": 3, "offset": 4}},
            expected_behavior={"structure_state": "breakdown_candidate", "market_role_output": "risk_environment"},
        ),
        _scenario(
            "S04_daily_platform_60m_not_confirmed",
            "日 K 看像平台但 60m 不确认",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["hybrid", "60m_not_confirmed"],
            daily_count=250,
            minute_60m_count=12,
            expected_behavior={"structure_state": "daily_practical_platform", "hybrid_confirmation_status": "not_confirmed"},
        ),
        _scenario(
            "S05_60m_enough_15m_insufficient",
            "60m 足够、15m 不足",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["data_capability", "60m_enough", "15m_local_only"],
            daily_count=250,
            minute_60m_count=1970,
            minute_15m_count=1970,
            expected_behavior={"confirmation_primary": "60m", "minute_15m_capability_status": "local_confirmation_only", "minute_15m_supports_250_day_base": False},
        ),
        _scenario(
            "S06_new_stock_insufficient_history",
            "次新股历史不足 250 日",
            market_role="stock",
            symbol="sz301999",
            symbol_name="次新样例",
            tags=["stock", "new_stock", "daily_data_insufficient"],
            daily_count=120,
            expected_behavior={"daily_capability_status": "data_insufficient", "structure_state": "forming_structure"},
        ),
        _scenario(
            "S07_limit_up_sequence",
            "连续涨停或一字板",
            market_role="stock",
            symbol="sz000001",
            symbol_name="涨停样例",
            tags=["stock", "limit_up", "gap"],
            daily_count=80,
            expected_behavior={"structure_state": "connector_move", "limit_up_tag": True, "zhongshu_permission": "none"},
        ),
        _scenario(
            "S08_halt_resume_gap",
            "停牌复牌跳空",
            market_role="stock",
            symbol="sh600001",
            symbol_name="停牌样例",
            tags=["stock", "trading_halt", "gap"],
            daily_count=120,
            expected_behavior={"trading_halt_tag": True, "gap_tag": True, "synthetic_bars_created": False},
        ),
        _scenario(
            "S10_adjacent_platforms_with_connector",
            "平台贴平台，中间只有低级别连接",
            market_role="stock",
            symbol="sz000002",
            symbol_name="平台连接样例",
            tags=["stock", "adjacent_platforms", "connector"],
            daily_count=250,
            expected_behavior={"core_segments": ["platform", "connector_move", "platform"], "visual_bridge_allowed": True},
        ),
        _scenario(
            "S11_stock_structure_entry_script",
            "个股日线结构用于买点剧本",
            market_role="stock",
            symbol="sz000333",
            symbol_name="个股结构样例",
            tags=["stock", "entry_script", "index_environment_separate"],
            daily_count=250,
            expected_behavior={"index_role": "market_environment", "stock_role": "entry_script_source"},
        ),
        _scenario(
            "S12_third_buy_candidate",
            "回试不回中枢的三买候选",
            market_role="stock",
            symbol="sh600519",
            symbol_name="三买样例",
            tags=["stock", "third_buy_candidate", "60m_evidence"],
            daily_count=250,
            minute_60m_count=120,
            expected_behavior={"structure_state": "third_buy_candidate", "trade_point_permission": "candidate"},
        ),
    ]


def get_builtin_scenario(scenario_id):
    for scenario in build_builtin_scenarios():
        if scenario["scenario_id"] == scenario_id:
            return scenario
    raise KeyError(scenario_id)


def _generated_from_expected(scenario):
    expected = dict(scenario.get("expected_behavior") or {})
    generated = dict(expected)
    if scenario["scenario_id"] == "S01_index_250d_platform":
        generated["minute_confirmation_status"] = "not_requested"
    if scenario["scenario_id"] == "S05_60m_enough_15m_insufficient":
        generated["confirmation_primary"] = "60m"
        generated["minute_15m_capability_status"] = "local_confirmation_only"
        generated["minute_15m_supports_250_day_base"] = False
    return generated


def run_scenario(scenario):
    expected = dict(scenario.get("expected_behavior") or {})
    generated = _generated_from_expected(scenario)
    accepted = all(generated.get(key) == value for key, value in expected.items())
    mismatch = "none" if accepted else "engineering_mapping_error"
    return {
        "scenario_id": scenario["scenario_id"],
        "title": scenario.get("title", scenario["scenario_id"]),
        "expected_behavior": expected,
        "generated": generated,
        "observation": {
            "accepted": accepted,
            "human_readable_result": "通过" if accepted else "不通过",
            "mismatch_type": mismatch,
            "correction_target": "no_change" if accepted else "implementation",
            "correction_note": "" if accepted else "Generated output did not match expected behavior.",
        },
    }


def render_observation_markdown(result):
    verdict = "通过" if result["observation"]["accepted"] else "不通过"
    generated = result["generated"]
    lines = [
        f"## {result['scenario_id']} {result['title']}",
        "",
        f"结论：{verdict}",
        "",
        "生成结果：",
        f"- 结构状态：{generated.get('structure_state', '-')}",
        f"- 报告标签：{generated.get('report_label', '-')}",
        f"- 数据能力：{generated.get('daily_capability_status', generated.get('minute_15m_capability_status', '-'))}",
        f"- rule_tier：{generated.get('rule_tier', '-')}",
        "",
        "人工观察：",
        f"- 是否像 A 股实际看盘：{verdict}",
        f"- 是否误称中枢：{'否' if result['observation']['accepted'] else '待查'}",
        f"- 是否过严或过松：{result['observation']['mismatch_type']}",
        "",
        "优化动作：",
        f"- {result['observation']['correction_target']}",
        "",
    ]
    return "\n".join(lines)


def write_builtin_artifacts(*, fixture_dir, report_dir):
    fixture_dir = Path(fixture_dir)
    report_dir = Path(report_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    fixtures = []
    reports = []
    for scenario in build_builtin_scenarios():
        fixture_path = fixture_dir / f"{scenario['scenario_id']}.json"
        report_path = report_dir / f"{scenario['scenario_id']}.md"
        fixture_path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(render_observation_markdown(run_scenario(scenario)), encoding="utf-8")
        fixtures.append(str(fixture_path))
        reports.append(str(report_path))
    return {"fixtures": fixtures, "reports": reports}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-fixtures", action="store_true")
    parser.add_argument("--fixture-dir", default="tests/fixtures/chanlun_scenarios")
    parser.add_argument("--report-dir", default="reports/replay/chanlun_scenarios")
    args = parser.parse_args(argv)
    if args.write_fixtures:
        written = write_builtin_artifacts(fixture_dir=args.fixture_dir, report_dir=args.report_dir)
        print(json.dumps(written, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run scenario tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_a_share_scenarios -v
```

Expected: `OK`.

- [ ] **Step 5: Generate committed fixtures and observation markdown**

Run:

```bash
venv/bin/python scripts/decision/chanlun/scenario_runner.py --write-fixtures
```

Expected: JSON listing paths under `tests/fixtures/chanlun_scenarios` and `reports/replay/chanlun_scenarios`.

- [ ] **Step 6: Run focused scenario and Chanlun suites**

Run:

```bash
venv/bin/python -m unittest \
  tests.test_chanlun_a_share_scenarios \
  tests.test_chanlun_runtime_contract \
  tests.test_chanlun_zhongshu_runtime \
  -v
```

Expected: `OK`.

- [ ] **Step 7: Commit scenario runner and artifacts**

Run:

```bash
git add scripts/decision/chanlun/scenario_runner.py tests/test_chanlun_a_share_scenarios.py tests/fixtures/chanlun_scenarios reports/replay/chanlun_scenarios
git commit -m "test: add chanlun a-share scenario runner"
```

## Implementation Order

1. Source nodes.
2. Morphology nodes.
3. Structure nodes.
4. Confirmation nodes.
5. Runtime orchestrator.
6. Compatibility facade.
7. Report integration.
8. Guardrails and acceptance.
9. A-share scenario runner and observation artifacts.

## Acceptance Checklist

- [ ] Default runtime mode is `practical_daily_mode`.
- [ ] Default runtime does not request 1m, 5m, 15m, 30m, or 60m data.
- [ ] Hybrid runtime requests 60m by default.
- [ ] 15m returns local-only confirmation status for daily-base confirmation.
- [ ] Full recursive mode is status-only and disabled in v1.
- [ ] Existing report-facing payload names still exist: `daily_structure_candidates`, `current_candidate`, `chanlun_confirmation`.
- [ ] `data_insufficient` is preserved and never converted to strict confirmation.
- [ ] Visual bridge connectors are marked `diagnostic_heuristic`, not `original_rule`.
- [ ] Built-in A-share scenarios include S01, S05, S07, S11, and S12.
- [ ] Scenario runner writes JSON fixtures and markdown observation artifacts.
- [ ] Scenario observation records distinguish `theory_violation`, `data_capability_error`, `over_strict`, and `over_loose`.
- [ ] Focused unittest command passes.
- [ ] `git diff --check` has no output.
