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

from decision.security_zhongshu_node import analyze_security_zhongshu_from_frame, strict_chanlun_policy_for_security
from export.zhongshu_visual_snapshot import (
    REPORT_DISPLAY_DAILY_BARS,
    STRUCTURAL_BASE_DAILY_BARS,
    _normalize_row,
    _start_date_for,
)
from market_data.daily_price_runtime import fetch_daily_price_bars
from market_data.kline_dates import normalize_kline_date_str

STOCK_OBSERVATION_LOOKBACK_CALENDAR_DAYS = 220
SECURITY_ZHONGSHU_VISUAL_ALGORITHM_VERSION = "security-zhongshu-effective-departure-v1"


def _stock_to_bs_code(stock_code: str) -> str:
    code = str(stock_code or "").strip()
    if code.startswith(("sh.", "sz.")):
        return code
    if code.startswith("6"):
        return f"sh.{code}"
    if code.startswith(("0", "3")):
        return f"sz.{code}"
    return code


def _load_cached_stock_kline_rows(target_date: str, security_code: str) -> list[dict[str, Any]]:
    cache_path = SCRIPTS_ROOT.parent / "data" / "snap-ui" / "stock-klines" / f"{target_date}-{security_code}.json"
    rows: list[dict[str, Any]] = []
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        payload = None
    if isinstance(payload, dict):
        root = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        rows_by_code = root.get("stock_klines") or root.get("stockKlines") or {}
        cached_rows = rows_by_code.get(security_code) if isinstance(rows_by_code, dict) else []
        if isinstance(cached_rows, list):
            rows = cached_rows

    snapshot_path = SCRIPTS_ROOT.parent / "snapshots" / f"{target_date}.json"
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        snapshot = None
    if isinstance(snapshot, dict):
        root = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else snapshot
        rows_by_code = root.get("stock_klines") or root.get("stockKlines") or {}
        snapshot_rows = rows_by_code.get(security_code) if isinstance(rows_by_code, dict) else []
        if isinstance(snapshot_rows, list):
            rows = _merge_kline_rows_by_date(rows, snapshot_rows)
    return rows


def _start_date_for_security(target_date: str, security_type: str) -> str:
    if security_type == "stock":
        parsed = dt.datetime.strptime(target_date, "%Y-%m-%d").date()
        return (parsed - dt.timedelta(days=STOCK_OBSERVATION_LOOKBACK_CALENDAR_DAYS)).isoformat()
    return _start_date_for(target_date, STRUCTURAL_BASE_DAILY_BARS)


def _merge_kline_rows_by_date(*row_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_date: dict[str, dict[str, Any]] = {}
    for rows in row_groups:
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            date_text = normalize_kline_date_str(row.get("date") or row.get("trade_date"))
            if not date_text:
                continue
            rows_by_date[date_text] = {**row, "date": date_text}
    return [rows_by_date[key] for key in sorted(rows_by_date.keys())]


def normalize_security_visual_payload(
    security_zhongshu: dict[str, Any],
    kline_rows: list[dict[str, Any]],
    *,
    date: str,
    security_code: str,
    security_name: str = "",
    security_type: str = "stock",
) -> dict[str, Any]:
    normalized_rows = [
        row
        for row in (_normalize_row(row) for row in kline_rows)
        if row["date"] and row["open"] is not None and row["high"] is not None and row["low"] is not None and row["close"] is not None
    ]
    return {
        "date": date,
        "algorithm_version": SECURITY_ZHONGSHU_VISUAL_ALGORITHM_VERSION,
        "security_code": security_code,
        "security_name": security_name,
        "security_type": security_type,
        "security_zhongshu": security_zhongshu,
        "security_klines": {security_code: normalized_rows},
        "stock_klines": {security_code: normalized_rows} if security_type == "stock" else {},
        "calculation_windows": {
            "structural_base_daily_bars": STRUCTURAL_BASE_DAILY_BARS,
            "report_display_daily_bars": REPORT_DISPLAY_DAILY_BARS,
            "display_row_count": len(normalized_rows),
        },
        "strict_chanlun_policy": strict_chanlun_policy_for_security(security_type),
        "source_status": "success" if normalized_rows else "missing",
    }


def run_analysis(
    target_date: str,
    security_code: str,
    *,
    security_name: str = "",
    security_type: str = "stock",
    fetch_bars: Callable[..., list[dict[str, Any]]] = fetch_daily_price_bars,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import pandas as pd
    from decision.zhongshu_runtime import split_zhongshu_history_and_today

    start_date = _start_date_for_security(target_date, security_type)
    source_code = _stock_to_bs_code(security_code) if security_type == "stock" else security_code
    try:
        bars = fetch_bars(
            source_code,
            start_date,
            target_date,
            is_index=security_type == "index",
            prefer_fast=True,
            allow_baostock_fallback=False,
        ) or []
    except TypeError:
        bars = fetch_bars(
            source_code,
            start_date,
            target_date,
            is_index=security_type == "index",
            prefer_fast=True,
        ) or []
    data_source = "market_data.daily_price_runtime.fetch_daily_price_bars"
    if security_type == "stock":
        has_fast_bars = bool(bars)
        cached_rows = _load_cached_stock_kline_rows(target_date, security_code)
        if cached_rows:
            bars = _merge_kline_rows_by_date(bars, cached_rows)
            data_source = (
                "market_data.daily_price_runtime.fetch_daily_price_bars + data/snap-ui/stock-klines"
                if has_fast_bars
                else "data/snap-ui/stock-klines"
            )
    frame = pd.DataFrame(bars)
    if frame.empty:
        return {"success": False, "error": "无法获取证券K线数据"}, []

    if "date" in frame.columns:
        frame = frame.copy()
        frame["date"] = frame["date"].map(normalize_kline_date_str)
        normalized_target = normalize_kline_date_str(target_date)
        if normalized_target:
            frame = frame[frame["date"] <= normalized_target].reset_index(drop=True)

    result = analyze_security_zhongshu_from_frame(
        frame,
        security_code=security_code,
        security_name=security_name,
        security_type=security_type,
        recent_days=STRUCTURAL_BASE_DAILY_BARS,
        target_date=target_date,
        data_source=data_source,
        print_fn=lambda *_args, **_kwargs: None,
    )
    try:
        recent_df, _hist_df, _today_df = split_zhongshu_history_and_today(
            frame,
            recent_days=REPORT_DISPLAY_DAILY_BARS,
            target_date=target_date,
        )
        rows = recent_df.drop(columns=[col for col in ["_date_obj"] if col in recent_df.columns]).to_dict("records")
    except Exception:
        rows = frame.to_dict("records")
    return result, rows


def main(
    argv: list[str] | None = None,
    *,
    runner: Callable[..., tuple[dict[str, Any], list[dict[str, Any]]]] = run_analysis,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--security-code", required=True)
    parser.add_argument("--security-name", default="")
    parser.add_argument("--security-type", default="stock", choices=["stock", "index"])
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    security_zhongshu, rows = runner(
        args.date,
        args.security_code,
        security_name=args.security_name,
        security_type=args.security_type,
    )
    payload = normalize_security_visual_payload(
        security_zhongshu,
        rows,
        date=args.date,
        security_code=args.security_code,
        security_name=args.security_name,
        security_type=args.security_type,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
