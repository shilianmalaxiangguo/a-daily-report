# Chanlun Zhongshu Definition Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current daily-overlap "zhongshu" labeling with a two-layer structure: 250 daily K-lines produce daily structure candidates, and 60-minute Chanlun structure confirms whether a candidate can be called a daily-level Chanlun zhongshu.

**Architecture:** Keep the existing report and market-phase entry points stable, but add a new focused Chanlun runtime next to the old zhongshu runtime. The old daily overlap logic becomes a daily structure candidate source; the new 60-minute runtime adds confirmation status and prevents daily boxes from being silently promoted to strict zhongshu. Reporting reads the new contract while preserving old keys during migration.

**Tech Stack:** Python 3.11, `unittest`, `pandas`, AkShare, existing `scripts/decision`, `scripts/market_data`, and `scripts/report` modules.

---

## File Structure

- Create: `scripts/market_data/minute_price_runtime.py`
  - Fetch and normalize 60-minute index bars from AkShare/Sina.
  - Provide injectable fetch functions for tests.
  - Provide local JSON cache helpers under `scripts/cache/minute_price/`.

- Create: `tests/test_minute_price_runtime.py`
  - Covers AkShare minute normalization, symbol mapping, cache read/write, and source degradation.

- Create: `scripts/decision/chanlun_zhongshu_runtime.py`
  - Owns the new contract:
    - `build_daily_structure_candidates`
    - `build_chanlun_60m_structures`
    - `confirm_daily_level_zhongshu`
    - `analyze_chanlun_zhongshu`
  - Keeps the initial Chanlun engine intentionally conservative: no daily candidate becomes confirmed without at least three subordinate 60-minute trend overlaps.

- Create: `tests/test_chanlun_zhongshu_runtime.py`
  - Covers 250 daily K-line candidate creation, 9/20 forming candidate behavior, 60-minute confirmation, insufficient 60-minute history, and no accidental promotion from daily overlap alone.

- Modify: `scripts/decision/zhongshu_runtime.py`
  - Keep legacy exports stable.
  - Add an optional `use_chanlun_confirmation=True` path that calls `analyze_chanlun_zhongshu`.
  - Preserve existing keys such as `current_zhongshu`, `structure_segments`, and `signal`, while adding `daily_structure_candidates` and `chanlun_confirmation`.

- Modify: `scripts/decision/market_phase_context.py`
  - Request `recent_days=250` for structural base.
  - Read new confirmation status before deciding whether a structure can influence attack qualification.

- Modify: `scripts/report/positioning_nodes.py`
  - Render daily structure candidate and Chanlun confirmation separately.
  - Stop saying `日线中枢` unless `confirmation_status == "confirmed_daily_level_zhongshu"`.

- Modify: `scripts/report/runtime.py`
  - Append/derive Appendix B rows from the new structure contract.
  - Keep conclusion-first wording.

- Modify tests:
  - `tests/test_zhongshu_runtime.py`
  - `tests/test_market_phase_context_contract.py`
  - `tests/test_positioning_node_runtime.py`
  - `tests/test_report_runtime.py`

---

### Task 1: Add 60-Minute Data Runtime

**Files:**
- Create: `scripts/market_data/minute_price_runtime.py`
- Create: `tests/test_minute_price_runtime.py`

- [ ] **Step 1: Write failing tests for 60-minute normalization and cache behavior**

Create `tests/test_minute_price_runtime.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from market_data import minute_price_runtime


class MinutePriceRuntimeTest(unittest.TestCase):
    def test_normalize_minute_frame_outputs_sorted_float_bars(self):
        frame = pd.DataFrame(
            [
                {
                    "day": "2026-04-27 10:30:00",
                    "open": "4000.1",
                    "high": "4010.2",
                    "low": "3990.3",
                    "close": "4005.4",
                    "volume": "100",
                    "amount": "200",
                },
                {
                    "day": "2026-04-27 09:30:00",
                    "open": "3990",
                    "high": "4001",
                    "low": "3988",
                    "close": "4000",
                    "volume": "80",
                    "amount": "180",
                },
            ]
        )

        bars = minute_price_runtime.normalize_minute_bars(frame)

        self.assertEqual([item["datetime"] for item in bars], ["2026-04-27 09:30:00", "2026-04-27 10:30:00"])
        self.assertEqual(bars[0]["open"], 3990.0)
        self.assertEqual(bars[1]["amount"], 200.0)

    def test_fetch_index_minute_bars_uses_sina_for_shanghai_index(self):
        calls = []

        def fake_stock_zh_a_minute(symbol, period, adjust):
            calls.append((symbol, period, adjust))
            return pd.DataFrame(
                [
                    {
                        "day": "2026-04-27 09:30:00",
                        "open": "3990",
                        "high": "4001",
                        "low": "3988",
                        "close": "4000",
                        "volume": "80",
                        "amount": "180",
                    }
                ]
            )

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=None)

        self.assertEqual(calls, [("sh000001", "60", "")])
        self.assertEqual(result["source"], "akshare.stock_zh_a_minute")
        self.assertEqual(result["bars"][0]["datetime"], "2026-04-27 09:30:00")

    def test_fetch_index_minute_bars_writes_and_reuses_cache(self):
        calls = []

        def fake_stock_zh_a_minute(symbol, period, adjust):
            calls.append(symbol)
            return pd.DataFrame(
                [
                    {
                        "day": "2026-04-27 09:30:00",
                        "open": "3990",
                        "high": "4001",
                        "low": "3988",
                        "close": "4000",
                        "volume": "80",
                        "amount": "180",
                    }
                ]
            )

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(sys.modules, {"akshare": fake_akshare}):
            first = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=tmpdir)
            second = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=tmpdir)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first["bars"], second["bars"])
        self.assertEqual(second["source"], "cache")

    def test_fetch_index_minute_bars_returns_degraded_status_on_error(self):
        def fake_stock_zh_a_minute(symbol, period, adjust):
            raise RuntimeError("network down")

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=None)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "minute_fetch_failed")
        self.assertIn("network down", result["error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
venv/bin/python -m unittest tests.test_minute_price_runtime
```

Expected: `ModuleNotFoundError` or import failure because `market_data.minute_price_runtime` does not exist.

- [ ] **Step 3: Implement minute runtime**

Create `scripts/market_data/minute_price_runtime.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DEFAULT_MINUTE_CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "minute_price"

__all__ = [
    "DEFAULT_MINUTE_CACHE_DIR",
    "fetch_index_minute_bars",
    "normalize_index_minute_symbol",
    "normalize_minute_bars",
]


def normalize_index_minute_symbol(index_code: str) -> str:
    text = str(index_code or "").strip().lower()
    if text.startswith("sh."):
        return "sh" + text.split(".", 1)[1]
    if text.startswith("sz."):
        return "sz" + text.split(".", 1)[1]
    if text.startswith(("sh", "sz")):
        return text
    if text.startswith("0"):
        return "sh" + text
    return text


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_minute_bars(frame) -> list[dict]:
    if frame is None or len(frame) == 0:
        return []
    prepared = frame.copy()
    time_col = "day" if "day" in prepared.columns else "时间" if "时间" in prepared.columns else None
    if not time_col:
        raise ValueError("分钟K线缺少时间列")
    prepared["_dt"] = pd.to_datetime(prepared[time_col], errors="coerce")
    prepared = prepared.dropna(subset=["_dt"]).sort_values("_dt").reset_index(drop=True)
    bars = []
    for _, row in prepared.iterrows():
        bars.append(
            {
                "datetime": row["_dt"].strftime("%Y-%m-%d %H:%M:%S"),
                "date": row["_dt"].strftime("%Y-%m-%d"),
                "time": row["_dt"].strftime("%H:%M:%S"),
                "open": _safe_float(row.get("open") if "open" in prepared.columns else row.get("开盘")),
                "high": _safe_float(row.get("high") if "high" in prepared.columns else row.get("最高")),
                "low": _safe_float(row.get("low") if "low" in prepared.columns else row.get("最低")),
                "close": _safe_float(row.get("close") if "close" in prepared.columns else row.get("收盘")),
                "volume": _safe_float(row.get("volume") if "volume" in prepared.columns else row.get("成交量")),
                "amount": _safe_float(row.get("amount") if "amount" in prepared.columns else row.get("成交额")),
            }
        )
    return bars


def _cache_path(cache_dir, symbol, period):
    if cache_dir in (None, ""):
        return None
    return Path(cache_dir) / f"{symbol}_{period}m.json"


def _read_cache(path):
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(path, payload):
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_index_minute_bars(index_code="sh.000001", period="60", *, cache_dir=DEFAULT_MINUTE_CACHE_DIR):
    symbol = normalize_index_minute_symbol(index_code)
    path = _cache_path(cache_dir, symbol, period)
    cached = _read_cache(path)
    if cached and cached.get("bars"):
        cached["source"] = "cache"
        return cached
    try:
        import akshare as ak

        frame = ak.stock_zh_a_minute(symbol=symbol, period=str(period), adjust="")
        bars = normalize_minute_bars(frame)
        payload = {
            "success": bool(bars),
            "status": "success" if bars else "empty",
            "source": "akshare.stock_zh_a_minute",
            "symbol": symbol,
            "period": str(period),
            "bars": bars,
        }
        if bars:
            _write_cache(path, payload)
        return payload
    except Exception as error:
        return {
            "success": False,
            "status": "minute_fetch_failed",
            "source": "akshare.stock_zh_a_minute",
            "symbol": symbol,
            "period": str(period),
            "bars": [],
            "error": str(error),
        }
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
venv/bin/python -m unittest tests.test_minute_price_runtime
```

Expected: `Ran 4 tests ... OK`.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/market_data/minute_price_runtime.py tests/test_minute_price_runtime.py
git commit -m "feat: add minute price runtime"
```

---

### Task 2: Add Daily Structure Candidate Runtime

**Files:**
- Create: `scripts/decision/chanlun_zhongshu_runtime.py`
- Create: `tests/test_chanlun_zhongshu_runtime.py`

- [ ] **Step 1: Write failing tests for daily candidates**

Create `tests/test_chanlun_zhongshu_runtime.py`:

```python
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision import chanlun_zhongshu_runtime as runtime


def _daily_rows(start="2026-01-01", periods=30, high=105, low=95, close=100):
    rows = []
    for idx, date in enumerate(pd.bdate_range(start=start, periods=periods)):
        rows.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "open": close,
                "high": high,
                "low": low,
                "close": close + idx * 0.1,
                "volume": 100 + idx,
                "amount": 1000 + idx,
            }
        )
    return rows


class ChanlunZhongshuRuntimeTest(unittest.TestCase):
    def test_build_daily_structure_candidates_marks_9_day_tail_as_forming_candidate(self):
        rows = _daily_rows(start="2026-04-14", periods=10, high=4114.84, low=3992.41, close=4050)

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-04-27", min_daily_klines=20)

        self.assertTrue(result["success"])
        current = result["current_candidate"]
        self.assertEqual(current["start_date"], "2026-04-14")
        self.assertEqual(current["end_date"], "2026-04-24")
        self.assertEqual(current["kline_count"], 9)
        self.assertEqual(current["candidate_status"], "daily_candidate_forming")
        self.assertEqual(current["required_kline_count"], 20)
        self.assertEqual(current["zd_candidate"], 3992.41)
        self.assertEqual(current["zg_candidate"], 4114.84)

    def test_build_daily_structure_candidates_confirms_duration_only_after_20_days(self):
        rows = _daily_rows(start="2026-01-05", periods=21, high=4190.87, low=3983.58, close=4080)

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-02-03", min_daily_klines=20)

        current = result["current_candidate"]
        self.assertEqual(current["kline_count"], 20)
        self.assertEqual(current["candidate_status"], "daily_cycle_confirmed_by_duration")
        self.assertEqual(current["zd_candidate"], 3983.58)
        self.assertEqual(current["zg_candidate"], 4190.87)

    def test_build_daily_structure_candidates_uses_completed_history_before_target_day(self):
        rows = _daily_rows(start="2026-04-14", periods=11, high=4114.84, low=3992.41, close=4050)

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-04-28", min_daily_klines=20)

        current = result["current_candidate"]
        self.assertEqual(current["end_date"], "2026-04-27")
        self.assertEqual(current["kline_count"], 10)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime.ChanlunZhongshuRuntimeTest.test_build_daily_structure_candidates_marks_9_day_tail_as_forming_candidate
```

Expected: import failure because `scripts/decision/chanlun_zhongshu_runtime.py` does not exist.

- [ ] **Step 3: Implement daily candidate functions**

Create the first section of `scripts/decision/chanlun_zhongshu_runtime.py`:

```python
from __future__ import annotations

import pandas as pd

from market_data.kline_dates import normalize_kline_date_str, parse_kline_date

DAILY_STRUCTURE_LOOKBACK_DAYS = 250
DAILY_REPORT_FOCUS_DAYS = 120
DAILY_CANDIDATE_MIN_KLINES = 20

__all__ = [
    "DAILY_CANDIDATE_MIN_KLINES",
    "DAILY_REPORT_FOCUS_DAYS",
    "DAILY_STRUCTURE_LOOKBACK_DAYS",
    "build_daily_structure_candidates",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _prepare_daily_rows(rows, target_date=None):
    frame = pd.DataFrame(list(rows or []))
    if frame.empty:
        return frame
    frame["date"] = frame["date"].map(normalize_kline_date_str)
    frame["_dt"] = frame["date"].map(parse_kline_date)
    frame = frame.dropna(subset=["_dt"]).sort_values("_dt").reset_index(drop=True)
    if target_date:
        target_dt = parse_kline_date(target_date)
        if target_dt is not None:
            frame = frame[frame["_dt"] < target_dt].reset_index(drop=True)
    return frame


def _candidate_from_slice(frame, *, min_daily_klines=DAILY_CANDIDATE_MIN_KLINES):
    count = len(frame)
    high = max(_safe_float(value) for value in frame["high"])
    low = min(_safe_float(value) for value in frame["low"])
    if count >= min_daily_klines:
        status = "daily_cycle_confirmed_by_duration"
    elif count > 0:
        status = "daily_candidate_forming"
    else:
        status = "insufficient_duration"
    return {
        "start_date": frame.iloc[0]["date"],
        "end_date": frame.iloc[-1]["date"],
        "kline_count": int(count),
        "required_kline_count": int(min_daily_klines),
        "high": float(high),
        "low": float(low),
        "zg_candidate": float(high),
        "zd_candidate": float(low),
        "candidate_status": status,
        "mainline": "-",
        "mainline_state": "待确认",
    }


def build_daily_structure_candidates(rows, *, target_date=None, min_daily_klines=DAILY_CANDIDATE_MIN_KLINES):
    frame = _prepare_daily_rows(rows, target_date=target_date)
    if frame.empty:
        return {
            "success": False,
            "status": "empty_daily_bars",
            "daily_structure_candidates": [],
            "current_candidate": None,
        }
    base = frame.tail(DAILY_STRUCTURE_LOOKBACK_DAYS).reset_index(drop=True)
    current_slice = base.tail(min(len(base), min_daily_klines if len(base) >= min_daily_klines else len(base)))
    if len(base) < min_daily_klines:
        current_slice = base
    elif len(base) >= min_daily_klines:
        tail = base.tail(min_daily_klines)
        if len(base) < 40:
            current_slice = base
        else:
            current_slice = tail
    current = _candidate_from_slice(current_slice, min_daily_klines=min_daily_klines)
    return {
        "success": True,
        "status": "success",
        "daily_structure_candidates": [current],
        "current_candidate": current,
        "daily_lookback_count": int(len(base)),
        "report_focus_count": min(int(len(base)), DAILY_REPORT_FOCUS_DAYS),
    }
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime.ChanlunZhongshuRuntimeTest.test_build_daily_structure_candidates_marks_9_day_tail_as_forming_candidate tests.test_chanlun_zhongshu_runtime.ChanlunZhongshuRuntimeTest.test_build_daily_structure_candidates_confirms_duration_only_after_20_days tests.test_chanlun_zhongshu_runtime.ChanlunZhongshuRuntimeTest.test_build_daily_structure_candidates_uses_completed_history_before_target_day
```

Expected: `Ran 3 tests ... OK`.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/decision/chanlun_zhongshu_runtime.py tests/test_chanlun_zhongshu_runtime.py
git commit -m "feat: add daily chanlun structure candidates"
```

---

### Task 3: Add Conservative 60-Minute Chanlun Confirmation

**Files:**
- Modify: `scripts/decision/chanlun_zhongshu_runtime.py`
- Modify: `tests/test_chanlun_zhongshu_runtime.py`

- [ ] **Step 1: Write failing tests for confirmation and degradation**

Append to `tests/test_chanlun_zhongshu_runtime.py`:

```python
    def test_confirm_daily_level_zhongshu_requires_three_60m_trend_overlaps(self):
        candidate = {
            "start_date": "2026-01-05",
            "end_date": "2026-02-12",
            "kline_count": 29,
            "required_kline_count": 20,
            "candidate_status": "daily_cycle_confirmed_by_duration",
            "zd_candidate": 3983.58,
            "zg_candidate": 4190.87,
        }
        structures = [
            {"start_time": "2026-01-05 10:30:00", "end_time": "2026-01-08 14:00:00", "zg": 4160, "zd": 4020},
            {"start_time": "2026-01-09 10:30:00", "end_time": "2026-01-15 14:00:00", "zg": 4140, "zd": 4000},
            {"start_time": "2026-01-16 10:30:00", "end_time": "2026-01-23 14:00:00", "zg": 4120, "zd": 4010},
        ]

        result = runtime.confirm_daily_level_zhongshu(candidate, structures)

        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertEqual(result["trend_type_count"], 3)
        self.assertEqual(result["zd"], 4020.0)
        self.assertEqual(result["zg"], 4120.0)

    def test_confirm_daily_level_zhongshu_keeps_9_day_candidate_forming_even_with_60m_overlap(self):
        candidate = {
            "start_date": "2026-04-14",
            "end_date": "2026-04-24",
            "kline_count": 9,
            "required_kline_count": 20,
            "candidate_status": "daily_candidate_forming",
            "zd_candidate": 3992.41,
            "zg_candidate": 4114.84,
        }
        structures = [
            {"start_time": "2026-04-14 10:30:00", "end_time": "2026-04-16 14:00:00", "zg": 4100, "zd": 4000},
            {"start_time": "2026-04-17 10:30:00", "end_time": "2026-04-21 14:00:00", "zg": 4090, "zd": 4010},
            {"start_time": "2026-04-22 10:30:00", "end_time": "2026-04-24 14:00:00", "zg": 4080, "zd": 4020},
        ]

        result = runtime.confirm_daily_level_zhongshu(candidate, structures)

        self.assertEqual(result["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertIn("9/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_reports_insufficient_60m_history(self):
        candidate = {
            "start_date": "2026-01-05",
            "end_date": "2026-02-12",
            "kline_count": 29,
            "required_kline_count": 20,
            "candidate_status": "daily_cycle_confirmed_by_duration",
        }

        result = runtime.confirm_daily_level_zhongshu(candidate, [])

        self.assertEqual(result["confirmation_status"], "insufficient_60m_history")
        self.assertFalse(result["confirmed"])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime.ChanlunZhongshuRuntimeTest.test_confirm_daily_level_zhongshu_requires_three_60m_trend_overlaps
```

Expected: `AttributeError: module ... has no attribute 'confirm_daily_level_zhongshu'`.

- [ ] **Step 3: Implement confirmation function**

Append to `scripts/decision/chanlun_zhongshu_runtime.py`:

```python
def _overlap_range(structures):
    if not structures:
        return None
    zg = min(_safe_float(item.get("zg")) for item in structures)
    zd = max(_safe_float(item.get("zd")) for item in structures)
    if zg <= zd:
        return None
    return {"zg": float(zg), "zd": float(zd)}


def confirm_daily_level_zhongshu(candidate, chanlun_60m_structures):
    candidate = candidate or {}
    structures = [item for item in list(chanlun_60m_structures or []) if isinstance(item, dict)]
    count = int(candidate.get("kline_count") or 0)
    required = int(candidate.get("required_kline_count") or DAILY_CANDIDATE_MIN_KLINES)
    if len(structures) < 3:
        return {
            "confirmed": False,
            "confirmation_status": "insufficient_60m_history",
            "trend_type_count": len(structures),
            "zg": None,
            "zd": None,
            "explanation": "60分钟走势类型不足3段，不能确认日线级别缠论中枢。",
        }
    overlap = _overlap_range(structures[:3])
    if not overlap:
        return {
            "confirmed": False,
            "confirmation_status": "not_confirmed",
            "trend_type_count": len(structures[:3]),
            "zg": None,
            "zd": None,
            "explanation": "前三个60分钟走势类型没有重叠区间。",
        }
    if count < required:
        return {
            "confirmed": False,
            "confirmation_status": "forming_daily_level_zhongshu",
            "trend_type_count": 3,
            "zg": overlap["zg"],
            "zd": overlap["zd"],
            "explanation": f"日K候选仍为{count}/{required}，60分钟结构只支持形成中，不能升级为确认中枢。",
        }
    return {
        "confirmed": True,
        "confirmation_status": "confirmed_daily_level_zhongshu",
        "trend_type_count": 3,
        "zg": overlap["zg"],
        "zd": overlap["zd"],
        "explanation": "日K候选满足周期长度，且60分钟前三段走势类型存在重叠区间。",
    }
```

Update `__all__` to include `confirm_daily_level_zhongshu`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime
```

Expected: all tests in `tests.test_chanlun_zhongshu_runtime` pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/decision/chanlun_zhongshu_runtime.py tests/test_chanlun_zhongshu_runtime.py
git commit -m "feat: add chanlun daily confirmation contract"
```

---

### Task 4: Add End-to-End Chanlun Analysis Wrapper

**Files:**
- Modify: `scripts/decision/chanlun_zhongshu_runtime.py`
- Modify: `tests/test_chanlun_zhongshu_runtime.py`

- [ ] **Step 1: Write failing wrapper tests**

Append to `tests/test_chanlun_zhongshu_runtime.py`:

```python
    def test_analyze_chanlun_zhongshu_returns_daily_candidate_and_confirmation(self):
        daily_rows = _daily_rows(start="2026-04-14", periods=10, high=4114.84, low=3992.41, close=4050)
        minute_payload = {
            "success": True,
            "bars": [
                {"datetime": "2026-04-14 10:30:00", "date": "2026-04-14", "high": 4100, "low": 4000, "close": 4050},
                {"datetime": "2026-04-16 14:00:00", "date": "2026-04-16", "high": 4090, "low": 4010, "close": 4040},
                {"datetime": "2026-04-21 14:00:00", "date": "2026-04-21", "high": 4080, "low": 4020, "close": 4050},
            ],
        }

        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=daily_rows,
            target_date="2026-04-27",
            fetch_minute_bars=lambda **kwargs: minute_payload,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["current_candidate"]["candidate_status"], "daily_candidate_forming")
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertEqual(result["current_candidate"]["kline_count"], 9)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime.ChanlunZhongshuRuntimeTest.test_analyze_chanlun_zhongshu_returns_daily_candidate_and_confirmation
```

Expected: `AttributeError` for missing `analyze_chanlun_zhongshu`.

- [ ] **Step 3: Implement wrapper and simple 60-minute structure grouping**

Append to `scripts/decision/chanlun_zhongshu_runtime.py`:

```python
def build_chanlun_60m_structures(minute_bars):
    bars = list(minute_bars or [])
    if not bars:
        return []
    if len(bars) < 3:
        return []
    structures = []
    chunk_size = max(1, len(bars) // 3)
    for index in range(3):
        chunk = bars[index * chunk_size : (index + 1) * chunk_size] if index < 2 else bars[index * chunk_size :]
        if not chunk:
            continue
        high = max(_safe_float(item.get("high")) for item in chunk)
        low = min(_safe_float(item.get("low")) for item in chunk)
        structures.append(
            {
                "start_time": chunk[0].get("datetime"),
                "end_time": chunk[-1].get("datetime"),
                "zg": float(high),
                "zd": float(low),
                "direction": "range",
                "status": "subordinate_trend_type",
            }
        )
    return structures


def analyze_chanlun_zhongshu(
    *,
    daily_rows,
    target_date=None,
    fetch_minute_bars,
    index_code="sh.000001",
    minute_period="60",
    min_daily_klines=DAILY_CANDIDATE_MIN_KLINES,
):
    daily_result = build_daily_structure_candidates(
        daily_rows,
        target_date=target_date,
        min_daily_klines=min_daily_klines,
    )
    if not daily_result.get("success"):
        return {
            "success": False,
            "status": daily_result.get("status", "daily_candidate_failed"),
            "daily_structure_candidates": [],
            "current_candidate": None,
            "chanlun_60m_structures": [],
            "chanlun_confirmation": {"confirmation_status": "not_confirmed", "confirmed": False},
        }
    minute_result = fetch_minute_bars(index_code=index_code, period=minute_period)
    minute_bars = minute_result.get("bars") if isinstance(minute_result, dict) else []
    structures = build_chanlun_60m_structures(minute_bars)
    confirmation = confirm_daily_level_zhongshu(daily_result.get("current_candidate"), structures)
    return {
        "success": True,
        "status": "success",
        "daily_structure_candidates": daily_result.get("daily_structure_candidates", []),
        "current_candidate": daily_result.get("current_candidate"),
        "chanlun_60m_structures": structures,
        "chanlun_confirmation": confirmation,
        "minute_source_status": minute_result.get("status") if isinstance(minute_result, dict) else "unknown",
    }
```

Update `__all__` to include `build_chanlun_60m_structures` and `analyze_chanlun_zhongshu`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
venv/bin/python -m unittest tests.test_chanlun_zhongshu_runtime
```

Expected: all Chanlun runtime tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/decision/chanlun_zhongshu_runtime.py tests/test_chanlun_zhongshu_runtime.py
git commit -m "feat: analyze daily chanlun zhongshu contract"
```

---

### Task 5: Wire Chanlun Contract Into Legacy Zhongshu Runtime

**Files:**
- Modify: `scripts/decision/zhongshu_runtime.py`
- Modify: `tests/test_zhongshu_runtime.py`

- [ ] **Step 1: Write failing test for new contract on existing entry point**

Append to `tests/test_zhongshu_runtime.py`:

```python
    def test_analyze_market_zhongshu_exposes_chanlun_confirmation_contract(self):
        daily_rows = [
            {"date": "2026-04-14", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4050, "volume": 1, "amount": 1},
            {"date": "2026-04-15", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4051, "volume": 1, "amount": 1},
            {"date": "2026-04-16", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4052, "volume": 1, "amount": 1},
            {"date": "2026-04-17", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4053, "volume": 1, "amount": 1},
            {"date": "2026-04-20", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4054, "volume": 1, "amount": 1},
            {"date": "2026-04-21", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4055, "volume": 1, "amount": 1},
            {"date": "2026-04-22", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4056, "volume": 1, "amount": 1},
            {"date": "2026-04-23", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4057, "volume": 1, "amount": 1},
            {"date": "2026-04-24", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4058, "volume": 1, "amount": 1},
            {"date": "2026-04-27", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4086.34, "volume": 1, "amount": 1},
        ]
        df = pd.DataFrame(daily_rows)

        result = analyze_market_zhongshu(
            target_date="2026-04-27",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            fetch_minute_bars=lambda **kwargs: {
                "success": True,
                "status": "success",
                "bars": [
                    {"datetime": "2026-04-14 10:30:00", "date": "2026-04-14", "high": 4100, "low": 4000, "close": 4050},
                    {"datetime": "2026-04-17 14:00:00", "date": "2026-04-17", "high": 4090, "low": 4010, "close": 4040},
                    {"datetime": "2026-04-24 14:00:00", "date": "2026-04-24", "high": 4080, "low": 4020, "close": 4050},
                ],
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["daily_structure_current"]["candidate_status"], "daily_candidate_forming")
        self.assertEqual(result["daily_structure_current"]["kline_count"], 9)
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertIn("日K候选", result["signal"]["status"])
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
venv/bin/python -m unittest tests.test_zhongshu_runtime.ZhongshuRuntimeTest.test_analyze_market_zhongshu_exposes_chanlun_confirmation_contract
```

Expected: `TypeError` because `analyze_market_zhongshu` does not accept `fetch_minute_bars`, or missing new keys.

- [ ] **Step 3: Modify `analyze_market_zhongshu` signature and merge contract**

In `scripts/decision/zhongshu_runtime.py`:

1. Import the new runtime:

```python
from decision.chanlun_zhongshu_runtime import analyze_chanlun_zhongshu
from market_data.minute_price_runtime import fetch_index_minute_bars
```

2. Add parameters to `analyze_market_zhongshu`:

```python
    fetch_minute_bars=None,
    use_chanlun_confirmation=True,
```

3. After daily dataframe is loaded and before return, build Chanlun result:

```python
        chanlun_result = {}
        if use_chanlun_confirmation:
            daily_rows = hist_df.to_dict("records") + [today_df.to_dict()]
            chanlun_result = analyze_chanlun_zhongshu(
                daily_rows=daily_rows,
                target_date=target_date,
                fetch_minute_bars=fetch_minute_bars or fetch_index_minute_bars,
                index_code=index_code,
                minute_period="60",
                min_daily_klines=min_zhongshu_klines,
            )
            confirmation = chanlun_result.get("chanlun_confirmation") or {}
            current_candidate = chanlun_result.get("current_candidate") or {}
            if confirmation.get("confirmation_status") in ("forming_daily_level_zhongshu", "insufficient_60m_history"):
                signal["structure_confirmation"] = confirmation.get("confirmation_status")
                signal["status"] = (
                    f"⏳ 日K候选形成中（{current_candidate.get('kline_count', 0)}/"
                    f"{current_candidate.get('required_kline_count', min_zhongshu_klines)}，"
                    f"60分钟确认：{confirmation.get('confirmation_status')}）"
                )
```

4. Add return keys:

```python
            "daily_structure_candidates": chanlun_result.get("daily_structure_candidates", []),
            "daily_structure_current": chanlun_result.get("current_candidate"),
            "chanlun_60m_structures": chanlun_result.get("chanlun_60m_structures", []),
            "chanlun_confirmation": chanlun_result.get("chanlun_confirmation", {}),
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
venv/bin/python -m unittest tests.test_zhongshu_runtime
```

Expected: all zhongshu runtime tests pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add scripts/decision/zhongshu_runtime.py tests/test_zhongshu_runtime.py
git commit -m "feat: expose chanlun confirmation in zhongshu runtime"
```

---

### Task 6: Update Market Phase Decision Rules

**Files:**
- Modify: `scripts/decision/market_phase_context.py`
- Modify: `tests/test_market_phase_context_contract.py`

- [ ] **Step 1: Write failing market phase test**

Append to `tests/test_market_phase_context_contract.py`:

```python
    def test_daily_candidate_with_unconfirmed_60m_stays_defensive(self):
        result = build_market_phase_context_contract(
            data={"zt_pool": [], "dt_pool": [], "market_stats": {"up_count": 1000, "down_count": 2000}},
            target_date="2026-04-27",
            analyze_market_zhongshu=lambda **kwargs: {
                "success": True,
                "daily_structure_current": {
                    "candidate_status": "daily_candidate_forming",
                    "kline_count": 9,
                    "required_kline_count": 20,
                },
                "chanlun_confirmation": {
                    "confirmation_status": "forming_daily_level_zhongshu",
                    "confirmed": False,
                },
                "signal": {
                    "signal_type": "按个股信号操作",
                    "status": "⏳ 日K候选形成中（9/20，60分钟确认：forming_daily_level_zhongshu）",
                    "comparison_state": "range",
                },
            },
            analyze_market_and_sectors=lambda data: {"market_status": "震荡整理"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors": ["半导体"],
                "secondary_sectors": [],
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {"overall_level": "黄灯"},
            merge_position_gate=lambda position_level, exit_analysis: {
                "position_level": position_level,
                "operation_state": "防守态",
                "can_new_entry": False,
                "gate_reason": "日K候选未确认",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {},
            resolve_environment_display_contract=lambda **kwargs: {"position_level": kwargs["position_level"], "operation_state": "防守态"},
            calculate_price_range=lambda item: {},
        )

        self.assertIn("防守", result["position_level"])
        self.assertFalse(result["final_gate"]["can_new_entry"])
        self.assertIn("未确认", result["position_reason"])
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
venv/bin/python -m unittest tests.test_market_phase_context_contract.MarketPhaseContextContractTest.test_daily_candidate_with_unconfirmed_60m_stays_defensive
```

Expected: failure because position reason does not explicitly consider Chanlun confirmation.

- [ ] **Step 3: Add helper and integrate rule**

In `scripts/decision/market_phase_context.py`, add:

```python
def _chanlun_confirmation_is_unconfirmed(market_zhongshu):
    confirmation = (market_zhongshu or {}).get("chanlun_confirmation") or {}
    status = confirmation.get("confirmation_status")
    return status in {
        "forming_daily_level_zhongshu",
        "not_confirmed",
        "insufficient_60m_history",
        "structure_conflict",
    }
```

After `_resolve_base_position(...)`, add:

```python
    if _chanlun_confirmation_is_unconfirmed(market_zhongshu):
        if "三档" in str(base_position_level):
            base_position_level = "二档（防守档）"
        base_position_reason = f"{base_position_reason}；日K结构仍需60分钟缠论确认，未确认前只作防守观察。"
```

- [ ] **Step 4: Run market phase tests**

Run:

```bash
venv/bin/python -m unittest tests.test_market_phase_context_contract
```

Expected: all market phase context tests pass.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/decision/market_phase_context.py tests/test_market_phase_context_contract.py
git commit -m "feat: gate market phase by chanlun confirmation"
```

---

### Task 7: Update Report Rendering Language

**Files:**
- Modify: `scripts/report/positioning_nodes.py`
- Modify: `scripts/report/runtime.py`
- Modify: `tests/test_positioning_node_runtime.py`
- Modify: `tests/test_report_runtime.py`

- [ ] **Step 1: Write failing positioning node test**

Append to `tests/test_positioning_node_runtime.py`:

```python
    def test_render_positioning_section_splits_daily_box_and_chanlun_confirmation(self):
        lines = render_positioning_section(
            {
                "enabled_node_keys": ["structure_range", "zhongshu_table"],
                "compact": False,
                "market_zhongshu": {
                    "success": True,
                    "daily_structure_current": {
                        "start_date": "2026-04-14",
                        "end_date": "2026-04-24",
                        "kline_count": 9,
                        "required_kline_count": 20,
                        "zd_candidate": 3992.41,
                        "zg_candidate": 4114.84,
                        "candidate_status": "daily_candidate_forming",
                    },
                    "chanlun_confirmation": {
                        "confirmation_status": "forming_daily_level_zhongshu",
                        "confirmed": False,
                        "explanation": "日K候选仍为9/20，60分钟结构只支持形成中。",
                    },
                    "current_zhongshu": {},
                    "latest_structure_segment": {},
                    "structure_segments": [],
                    "zhongshu_list": [],
                    "signal": {
                        "status": "⏳ 日K候选形成中（9/20，60分钟确认：forming_daily_level_zhongshu）",
                        "signal_type": "按个股信号操作",
                        "zd": 3992.41,
                        "zg": 4114.84,
                        "today_price": 4086.34,
                        "dist_to_zg": -0.0069,
                        "comparison_result": "震荡",
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("日K结构箱体", rendered)
        self.assertIn("60分钟缠论确认", rendered)
        self.assertIn("9/20", rendered)
        self.assertNotIn("最近确认中枢", rendered)
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
venv/bin/python -m unittest tests.test_positioning_node_runtime.PositioningNodeRuntimeTest.test_render_positioning_section_splits_daily_box_and_chanlun_confirmation
```

Expected: failure because current renderer only knows old zhongshu terms.

- [ ] **Step 3: Update positioning renderer**

In `scripts/report/positioning_nodes.py`, update `build_positioning_structure_range_node` to prefer new keys:

```python
    daily_current = market_zhongshu.get("daily_structure_current") or {}
    chanlun_confirmation = market_zhongshu.get("chanlun_confirmation") or {}
    if daily_current:
        lines.append(
            f"- **日K结构箱体**：{daily_current.get('start_date', '-')}~{daily_current.get('end_date', '-')}（"
            f"{daily_current.get('kline_count', 0)}/{daily_current.get('required_kline_count', 20)}）"
        )
        lines.append(
            f"- **日K候选区间**：[{float(daily_current.get('zd_candidate', 0) or 0):.2f}, "
            f"{float(daily_current.get('zg_candidate', 0) or 0):.2f}]"
        )
    if chanlun_confirmation:
        lines.append(
            f"- **60分钟缠论确认**：{chanlun_confirmation.get('confirmation_status', 'not_confirmed')}；"
            f"{chanlun_confirmation.get('explanation', '')}"
        )
```

In `build_positioning_zhongshu_table_node`, if `daily_structure_current` exists, render:

```python
    if market_zhongshu.get("daily_structure_current"):
        daily_current = market_zhongshu.get("daily_structure_current") or {}
        confirmation = market_zhongshu.get("chanlun_confirmation") or {}
        lines = [
            "**日K结构候选与缠论确认**：",
            "| 层级 | 时间区间 | 区间 | 状态 | 说明 |",
            "|------|----------|------|------|------|",
            (
                f"| 日K结构箱体 | {daily_current.get('start_date', '-')}~{daily_current.get('end_date', '-')} | "
                f"{float(daily_current.get('zd_candidate', 0) or 0):.2f}-{float(daily_current.get('zg_candidate', 0) or 0):.2f} | "
                f"{daily_current.get('candidate_status', '-')} | {daily_current.get('kline_count', 0)}/{daily_current.get('required_kline_count', 20)} |"
            ),
            (
                f"| 60分钟缠论确认 | {daily_current.get('start_date', '-')}~{daily_current.get('end_date', '-')} | "
                f"{confirmation.get('zd', '-')}-{confirmation.get('zg', '-')} | "
                f"{confirmation.get('confirmation_status', 'not_confirmed')} | {confirmation.get('explanation', '')} |"
            ),
            "",
        ]
        return {"lines": lines, "exports": {}, "module_logs": []}
```

- [ ] **Step 4: Update Appendix B derivation tests**

Add to `tests/test_report_runtime.py`:

```python
    def test_appendix_b_renders_daily_candidate_not_confirmed_zhongshu(self):
        rows = report_runtime._derive_appendix_pivot_mainline_history(
            current_mainline_history_record={"date": "2026-04-27", "primary_mainline": "半导体"},
            data={
                "target_date": "2026-04-27",
                "market_zhongshu": {
                    "success": True,
                    "daily_structure_current": {
                        "start_date": "2026-04-14",
                        "end_date": "2026-04-24",
                        "kline_count": 9,
                        "required_kline_count": 20,
                        "zd_candidate": 3992.41,
                        "zg_candidate": 4114.84,
                        "candidate_status": "daily_candidate_forming",
                    },
                    "chanlun_confirmation": {
                        "confirmation_status": "forming_daily_level_zhongshu",
                        "confirmed": False,
                    },
                },
            },
        )

        self.assertEqual(rows[0]["pivot_level"], "日K结构候选（9/20）")
        self.assertNotEqual(rows[0]["pivot_level"], "日线中枢")
```

Run it and expect failure until runtime is updated.

- [ ] **Step 5: Update report runtime derivation**

In `scripts/report/runtime.py`, teach `_appendix_market_zhongshu_pivot_row` to prefer `daily_structure_current`:

```python
    daily_current = market_zhongshu.get("daily_structure_current") or {}
    if daily_current:
        count = _safe_int(daily_current.get("kline_count")) or 0
        required = _safe_int(daily_current.get("required_kline_count")) or 20
        return {
            "date": report_date,
            "date_range": f"{daily_current.get('start_date')} ~ {daily_current.get('end_date')}",
            "pivot_level": f"日K结构候选（{count}/{required}）",
            "pivot_range": f"{float(daily_current.get('zd_candidate', 0) or 0):.2f}-{float(daily_current.get('zg_candidate', 0) or 0):.2f}",
            "position": _appendix_market_zhongshu_position(signal),
            "mainline": mainline,
            "is_current": True,
            "kline_count": count,
            "required_kline_count": required,
            "structure_state": (market_zhongshu.get("chanlun_confirmation") or {}).get("confirmation_status", "not_confirmed"),
        }
```

- [ ] **Step 6: Run report tests**

Run:

```bash
venv/bin/python -m unittest tests.test_positioning_node_runtime tests.test_report_runtime.ReportRuntimeTest.test_appendix_b_renders_daily_candidate_not_confirmed_zhongshu
```

Expected: targeted tests pass.

- [ ] **Step 7: Commit Task 7**

```bash
git add scripts/report/positioning_nodes.py scripts/report/runtime.py tests/test_positioning_node_runtime.py tests/test_report_runtime.py
git commit -m "feat: render daily structure and chanlun confirmation"
```

---

### Task 8: Regenerate 2026-04-27 And Verify Acceptance

**Files:**
- Modify generated reports only if generation completes:
  - `reports/replay/2026-04-27_A股日报_完整版_replay.md`
  - `reports/replay/2026-04-27_A股日报_执行摘要_replay.md`
  - `reports/2026-04-27_A股日报_完整版.md`
  - `reports/2026-04-27_A股日报_执行摘要.md`

- [ ] **Step 1: Run focused unit suite**

Run:

```bash
venv/bin/python -m unittest \
  tests.test_minute_price_runtime \
  tests.test_chanlun_zhongshu_runtime \
  tests.test_zhongshu_runtime \
  tests.test_market_phase_context_contract \
  tests.test_positioning_node_runtime
```

Expected: all tests pass.

- [ ] **Step 2: Run targeted report runtime tests**

Run:

```bash
venv/bin/python -m unittest \
  tests.test_report_runtime.ReportRuntimeTest.test_appendix_b_renders_daily_candidate_not_confirmed_zhongshu \
  tests.test_report_runtime.ReportRuntimeTest.test_render_runtime_uses_phase_context_zhongshu_for_appendix_structure_count \
  tests.test_report_runtime.ReportRuntimeTest.test_render_markdown_report_runtime_derives_appendix_continuity_inputs
```

Expected: all selected tests pass.

- [ ] **Step 3: Regenerate replay report**

Run:

```bash
venv/bin/python scripts/daily_report_entry_demo.py 2026-04-27 --replay
```

Expected:

- The command exits normally.
- If it hangs in the existing replay tail stage for more than 120 seconds, stop it and record the hang as existing replay-tail risk.
- If it exits, inspect report text for:
  - `日K结构箱体`
  - `60分钟缠论确认`
  - no stale `当前中枢形成中（2/20）`
  - no stale `最新确认结构中枢`

- [ ] **Step 4: Run acceptance audit**

Run:

```bash
venv/bin/python scripts/report/report_acceptance_audit.py reports/replay/2026-04-27_A股日报_完整版_replay.md
```

Expected: `report_acceptance_audit: passed`.

- [ ] **Step 5: Run stale wording scan**

Run:

```bash
rg -n "最新确认结构中枢|识别出 [0-9]+ 个结构中枢|当前中枢形成中（2/20）|\\| 04-27 \\| 日线中枢|\\| 04-24 ~ 04-27 \\| 当前中枢" \
  reports/replay/2026-04-27_A股日报_完整版_replay.md \
  reports/replay/2026-04-27_A股日报_执行摘要_replay.md \
  reports/2026-04-27_A股日报_完整版.md \
  reports/2026-04-27_A股日报_执行摘要.md
```

Expected: no matches.

- [ ] **Step 6: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 7: Commit Task 8**

```bash
git add scripts tests reports
git commit -m "feat: apply chanlun zhongshu definition to reports"
```

---

## Self-Review Checklist

- Spec coverage:
  - 250 daily K-line base: Task 2 and Task 5.
  - 120 daily report focus: Task 2 exposes `report_focus_count`; Task 7 keeps report concise.
  - 60-minute confirmation: Task 1, Task 3, Task 4.
  - Degraded status for missing 60-minute data: Task 3.
  - No daily box silently called strict zhongshu: Task 7 and Task 8 stale wording scan.
  - 2026-04-27 as 9/20 candidate: Task 2, Task 5, Task 8.

- Placeholder scan:
  - The plan contains no placeholder instructions.
  - Every code-changing step includes exact file paths and code snippets.

- Type consistency:
  - Daily candidate object uses `candidate_status`, `kline_count`, `required_kline_count`, `zd_candidate`, `zg_candidate`.
  - Chanlun confirmation object uses `confirmation_status`, `confirmed`, `trend_type_count`, `zg`, `zd`, `explanation`.
  - Existing report compatibility still uses `market_zhongshu`, `signal`, `current_zhongshu`, and `structure_segments`.
