from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Callable

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _index_to_bs_code(index_code: str) -> str:
    text = str(index_code or "sh000001").lower().replace(".", "")
    if text.startswith("sh"):
        return f"sh.{text[2:]}"
    if text.startswith("sz"):
        return f"sz.{text[2:]}"
    return text


def _start_date_for(target_date: str, recent_days: int) -> str:
    parsed = dt.datetime.strptime(target_date, "%Y-%m-%d").date()
    return (parsed - dt.timedelta(days=recent_days * 2)).isoformat()


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_date(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value or "")[:10]


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": _normalize_date(row.get("date") or row.get("trade_date")),
        "open": _safe_float(row.get("open")),
        "high": _safe_float(row.get("high")),
        "low": _safe_float(row.get("low")),
        "close": _safe_float(row.get("close")),
        "volume": _safe_float(row.get("volume")),
        "amount": _safe_float(row.get("amount")),
    }


def normalize_visual_payload(
    market_zhongshu: dict[str, Any],
    kline_rows: list[dict[str, Any]],
    *,
    date: str,
    index_code: str,
) -> dict[str, Any]:
    normalized_rows = [
        row
        for row in (_normalize_row(row) for row in kline_rows)
        if row["date"] and row["open"] is not None and row["high"] is not None and row["low"] is not None and row["close"] is not None
    ]
    return {
        "date": date,
        "index_code": index_code,
        "market_zhongshu": market_zhongshu,
        "index_klines": {index_code: normalized_rows},
        "source_status": "success" if normalized_rows else "missing",
    }


def run_analysis(target_date: str, index_code: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import pandas as pd
    from decision.zhongshu_runtime import analyze_market_zhongshu, split_zhongshu_history_and_today
    from market_data.daily_price_runtime import fetch_daily_price_bars

    bars = fetch_daily_price_bars(
        _index_to_bs_code(index_code),
        _start_date_for(target_date, 120),
        target_date,
        is_index=True,
        prefer_fast=True,
    )
    if not bars:
        return {"success": False, "error": "无法获取指数K线数据"}, []

    frame = pd.DataFrame(bars)
    result = analyze_market_zhongshu(
        index_code=index_code,
        target_date=target_date,
        fetch_dataframe=lambda **_: frame,
        print_fn=lambda *_args, **_kwargs: None,
    )
    try:
        recent_df, _hist_df, _today_df = split_zhongshu_history_and_today(frame, recent_days=120, target_date=target_date)
        rows = recent_df.drop(columns=[col for col in ["_date_obj"] if col in recent_df.columns]).to_dict("records")
    except Exception:
        rows = frame.to_dict("records")
    return result, rows


def main(
    argv: list[str] | None = None,
    *,
    runner: Callable[[str, str], tuple[dict[str, Any], list[dict[str, Any]]]] = run_analysis,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--index-code", default="sh000001")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    market_zhongshu, rows = runner(args.date, args.index_code)
    payload = normalize_visual_payload(market_zhongshu, rows, date=args.date, index_code=args.index_code)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
