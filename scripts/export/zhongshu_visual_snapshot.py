from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

STRUCTURAL_BASE_DAILY_BARS = 250
REPORT_DISPLAY_DAILY_BARS = 250
PRACTICAL_SOURCE_ALGORITHM = "practical_daily_node_runtime; full_recursive_mode_deferred"


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


def _sse_index_symbol(index_code: str) -> str | None:
    text = str(index_code or "").lower().replace(".", "")
    if not text.startswith("sh"):
        return None
    symbol = text[2:] if text.startswith("sh") else text
    return symbol if symbol.isdigit() and len(symbol) == 6 else None


def _load_sse_index_rows(
    index_code: str,
    target_date: str,
    recent_days: int,
    *,
    urlopen_fn: Callable[..., Any] | None = None,
    timeout: int = 12,
) -> list[dict[str, Any]]:
    symbol = _sse_index_symbol(index_code)
    if symbol is None:
        return []

    import urllib.request

    row_count = max(int(recent_days) + 10, 260)
    url = f"https://yunhq.sse.com.cn:32042/v1/sh1/dayk/{symbol}?begin=-{row_count}&end=-1&period=day"
    request = urllib.request.Request(
        url,
        headers={
            "Referer": "https://www.sse.com.cn/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    opener = urlopen_fn or urllib.request.urlopen
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    target_key = target_date.replace("-", "")
    rows = []
    for item in payload.get("kline") or []:
        if not isinstance(item, list) or len(item) < 7:
            continue
        date_key = str(item[0])
        if target_key and date_key > target_key:
            continue
        rows.append(
            {
                "date": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}",
                "open": _safe_float(item[1]),
                "high": _safe_float(item[2]),
                "low": _safe_float(item[3]),
                "close": _safe_float(item[4]),
                "volume": _safe_float(item[5]),
                "amount": _safe_float(item[6]),
            }
        )
    return rows[-int(recent_days) :]


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


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
        "calculation_windows": {
            "structural_base_daily_bars": STRUCTURAL_BASE_DAILY_BARS,
            "report_display_daily_bars": REPORT_DISPLAY_DAILY_BARS,
            "display_row_count": len(normalized_rows),
        },
        "strict_chanlun_policy": {
            "source_algorithm": PRACTICAL_SOURCE_ALGORITHM,
            "default_mode": "practical_daily_mode",
            "daily_level_confirmation": "日线平台由日线走势类型重叠识别",
            "minute_confirmation": "not_requested",
            "full_recursive_mode": "deferred",
            "execution_reference": "下级别结构仅作执行与止损辅助，当前画布不请求额外交易时间",
            "market_index_role": "上证指数决定市场参与条件",
            "stock_position_role": "个股自身结构决定单票仓位",
        },
        "source_status": "success" if normalized_rows else "missing",
    }


def run_analysis(
    target_date: str,
    index_code: str,
    *,
    sse_loader: Callable[..., list[dict[str, Any]]] = _load_sse_index_rows,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import pandas as pd
    from decision.zhongshu_runtime import analyze_market_zhongshu, split_zhongshu_history_and_today, _load_iwencai_index_dataframe
    from market_data.kline_dates import normalize_kline_date_str
    from market_data.daily_price_runtime import fetch_daily_price_bars

    bars = sse_loader(index_code, target_date, STRUCTURAL_BASE_DAILY_BARS)
    frame = pd.DataFrame(bars or [])
    data_source = "sse_index_dayk" if len(frame) >= STRUCTURAL_BASE_DAILY_BARS else "market_data.daily_price_runtime.fetch_daily_price_bars"
    if len(frame) < STRUCTURAL_BASE_DAILY_BARS:
        bars = fetch_daily_price_bars(
            _index_to_bs_code(index_code),
            _start_date_for(target_date, STRUCTURAL_BASE_DAILY_BARS),
            target_date,
            is_index=True,
            prefer_fast=True,
        )
        frame = pd.DataFrame(bars or [])
        data_source = "market_data.daily_price_runtime.fetch_daily_price_bars"
    if len(frame) < STRUCTURAL_BASE_DAILY_BARS:
        try:
            iwencai_frame, iwencai_source = _load_iwencai_index_dataframe(STRUCTURAL_BASE_DAILY_BARS)
            if iwencai_frame is not None and len(iwencai_frame) > len(frame):
                iwencai_frame = iwencai_frame.copy()
                iwencai_frame["date"] = iwencai_frame["date"].map(normalize_kline_date_str)
                normalized_target = normalize_kline_date_str(target_date)
                if normalized_target:
                    iwencai_frame = iwencai_frame[iwencai_frame["date"] <= normalized_target].reset_index(drop=True)
                if len(iwencai_frame) >= max(len(frame), 2):
                    frame = iwencai_frame
                    data_source = iwencai_source
        except Exception:
            pass
    if frame.empty:
        return {"success": False, "error": "无法获取指数K线数据"}, []

    result = analyze_market_zhongshu(
        index_code=index_code,
        recent_days=STRUCTURAL_BASE_DAILY_BARS,
        target_date=target_date,
        fetch_dataframe=lambda **_: (frame, data_source),
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
