from __future__ import annotations

import datetime as _dt

from market_data.kline_dates import normalize_kline_date_str


EXPECTED_MARGIN_EXCHANGE_COUNT = 3


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return int(default)
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _format_pct(value):
    return f"{_safe_float(value):.2f}%"


def _calendar_trading_days_between(latest_date, target_date, trade_dates=None):
    latest = normalize_kline_date_str(latest_date)
    target = normalize_kline_date_str(target_date)
    if not latest or not target or latest >= target:
        return 0
    normalized_trade_dates = sorted(
        {
            normalize_kline_date_str(value)
            for value in trade_dates or []
            if normalize_kline_date_str(value) and normalize_kline_date_str(value) <= target
        }
    )
    if normalized_trade_dates:
        if latest not in normalized_trade_dates or target not in normalized_trade_dates:
            return None
        return sum(1 for value in normalized_trade_dates if latest < value <= target)
    try:
        start = _dt.date.fromisoformat(latest)
        end = _dt.date.fromisoformat(target)
    except ValueError:
        return 0
    count = 0
    day = start + _dt.timedelta(days=1)
    while day <= end:
        if day.weekday() < 5:
            count += 1
        day += _dt.timedelta(days=1)
    return count


def _pressure_label(ratio_pct):
    ratio_pct = _safe_float(ratio_pct)
    if ratio_pct >= 100:
        return "高压"
    if ratio_pct >= 85:
        return "中性"
    return "舒缓"


def _percentile_rank(values, current):
    values = sorted(_safe_float(item) for item in values if _safe_float(item) > 0)
    if not values:
        return 0.0
    current = _safe_float(current)
    below_or_equal = sum(1 for item in values if item <= current)
    return below_or_equal / len(values) * 100.0


def _normalize_source_row(row):
    row = dict(row or {})
    trade_date = normalize_kline_date_str(row.get("trade_date") or row.get("date"))
    margin_balance = _safe_float(row.get("margin_balance_yi", row.get("rzye_yi", row.get("rzye"))))
    short_balance = _safe_float(row.get("short_selling_balance_yi", row.get("rqye_yi", row.get("rqye"))))
    margin_trading_balance = _safe_float(
        row.get("margin_trading_balance_yi", row.get("rzrqye_yi", row.get("rzrqye")))
    )
    market_turnover = _safe_float(row.get("market_turnover_yi", row.get("total_amount_yi", row.get("amount_yi"))))
    if margin_balance > 10_000_000:
        margin_balance /= 1e8
    if short_balance > 10_000_000:
        short_balance /= 1e8
    if margin_trading_balance > 10_000_000:
        margin_trading_balance /= 1e8
    if market_turnover > 10_000_000:
        market_turnover /= 1e8
    exchange_count = _safe_int(row.get("exchange_count"), EXPECTED_MARGIN_EXCHANGE_COUNT)
    source_policy = str(row.get("source_policy") or row.get("source") or "tushare.margin+tushare.daily")
    ratio_pct = margin_balance / market_turnover * 100.0 if margin_balance > 0 and market_turnover > 0 else 0.0
    result = {
        "trade_date": trade_date,
        "margin_balance_yi": margin_balance,
        "short_selling_balance_yi": short_balance,
        "margin_trading_balance_yi": margin_trading_balance or margin_balance + short_balance,
        "market_turnover_yi": market_turnover,
        "margin_turnover_ratio_pct": ratio_pct,
        "pressure_diff_pct": ratio_pct - 100.0 if ratio_pct > 0 else 0.0,
        "pressure_label": _pressure_label(ratio_pct),
        "exchange_count": exchange_count,
        "source_policy": source_policy,
        "is_market_level_margin_balance": bool(row.get("is_market_level_margin_balance")) or "eastmoney.rzrq.total.RZYE" in source_policy,
    }
    for key in ("margin_source_date", "turnover_source_date", "query_date"):
        value = normalize_kline_date_str(row.get(key))
        if value:
            result[key] = value
    return result


def _valid_row(row):
    return bool(
        (row or {}).get("trade_date")
        and _safe_float((row or {}).get("margin_balance_yi")) > 0
        and _safe_float((row or {}).get("market_turnover_yi")) > 0
    )


def _apply_change_text(rows):
    previous_ratio = None
    result = []
    for row in rows:
        item = dict(row)
        current_ratio = _safe_float(item.get("margin_turnover_ratio_pct"))
        if previous_ratio is None:
            item["change_text"] = item.get("change_text") or "待累计"
        else:
            item["change_text"] = item.get("change_text") or f"{current_ratio - previous_ratio:+.2f}pct"
        previous_ratio = current_ratio
        result.append(item)
    return result


def _source_from_rows(rows, fallback="tushare.margin+tushare.index_daily.market_amount"):
    sources = []
    for row in rows or []:
        source = str((row or {}).get("source_policy") or (row or {}).get("source") or "").strip()
        if source:
            sources.append(source)
    unique = sorted(set(sources))
    if not unique:
        return fallback
    if len(unique) == 1:
        return unique[0]
    return ",".join(unique)


def _build_calibration(rows, latest_row):
    ratios = [_safe_float(row.get("margin_turnover_ratio_pct")) for row in rows if _safe_float(row.get("margin_turnover_ratio_pct")) > 0]
    latest_ratio = _safe_float((latest_row or {}).get("margin_turnover_ratio_pct"))
    if not ratios:
        return {
            "sample_days": 0,
            "latest_percentile": 0.0,
            "low_ratio_pct": 0.0,
            "mid_ratio_pct": 0.0,
            "high_ratio_pct": 0.0,
        }
    sorted_ratios = sorted(ratios)

    def _pick(frac):
        index = min(max(int(round((len(sorted_ratios) - 1) * frac)), 0), len(sorted_ratios) - 1)
        return sorted_ratios[index]

    return {
        "sample_days": len(ratios),
        "latest_percentile": round(_percentile_rank(ratios, latest_ratio), 2),
        "low_ratio_pct": round(_pick(0.2), 2),
        "mid_ratio_pct": round(_pick(0.5), 2),
        "high_ratio_pct": round(_pick(0.8), 2),
    }


def build_margin_pressure_snapshot(
    rows,
    *,
    window_days=25,
    calibration_days=250,
    expected_exchange_count=EXPECTED_MARGIN_EXCHANGE_COUNT,
    target_date="",
    trade_dates=None,
    max_stale_trade_days=1,
):
    target_date = normalize_kline_date_str(target_date)
    normalized = [_normalize_source_row(row) for row in rows or []]
    normalized = [row for row in normalized if _valid_row(row)]
    normalized.sort(key=lambda item: item.get("trade_date", ""))
    if not normalized:
        return {
            "available": False,
            "status": "upstream_empty",
            "source": "tushare.margin+tushare.index_daily.market_amount",
            "message": "融资承接压力数据为空，暂不判断市场杠杆承接。",
            "rows": [],
            "calibration_rows": [],
        }
    source = _source_from_rows(normalized)
    incomplete = [
        row
        for row in normalized
        if not row.get("is_market_level_margin_balance")
        and _safe_int(row.get("exchange_count")) < int(expected_exchange_count or EXPECTED_MARGIN_EXCHANGE_COUNT)
    ]
    if incomplete:
        return {
            "available": False,
            "status": "incomplete_exchange_rows",
            "source": source,
            "message": "交易所融资数据不完整，暂不判断融资承接压力。",
            "rows": [],
            "calibration_rows": normalized[-int(calibration_days or 250):],
        }
    calibration_rows = normalized[-int(calibration_days or 250):]
    visible_rows = _apply_change_text(normalized[-int(window_days or 25):])
    latest = visible_rows[-1]
    latest_date = latest.get("trade_date") or ""
    is_stale_for_target = bool(target_date and latest_date and latest_date < target_date)
    stale_trade_days = _calendar_trading_days_between(latest_date, target_date, trade_dates=trade_dates)
    if is_stale_for_target and (
        stale_trade_days is None or stale_trade_days > int(max_stale_trade_days or 0)
    ):
        lag_text = f"{stale_trade_days}个交易日" if stale_trade_days is not None else "无法确认的交易日数"
        return {
            "available": False,
            "status": "stale_fact_date",
            "source": source,
            "message": (
                f"融资承接压力最新事实截至{latest_date}，较目标日{target_date}滞后{lag_text}，"
                "关键数据不完整，停止生成。"
            ),
            "rows": [],
            "calibration_rows": calibration_rows,
            "latest_data_date": latest_date,
            "target_date": target_date,
            "is_stale_for_target": True,
            "stale_trade_days": stale_trade_days,
        }
    calibration = _build_calibration(calibration_rows, latest)
    latest_ratio = _safe_float(latest.get("margin_turnover_ratio_pct"))
    latest_label = latest.get("pressure_label") or _pressure_label(latest_ratio)
    date_note = f"截至{latest_date}" if latest_date else "当前"
    summary = (
        f"近{calibration.get('sample_days', 0)}个交易日融资承接压力："
        f"{date_note}融资承接比 {_format_pct(latest_ratio)}，"
        f"250日分位 {calibration.get('latest_percentile', 0):.2f}%，"
        f"处于{latest_label}。"
    )
    usage_note = "融资余额是杠杆存量，两市成交额是承接流量；融资余额上升、成交额下降时，市场承接压力加重。"
    if is_stale_for_target:
        usage_note = f"{usage_note} 本项数据截至{latest_date}，较目标日{target_date}滞后{stale_trade_days}个交易日。"
    normalized_trade_dates = sorted({
        normalize_kline_date_str(value)
        for value in (trade_dates or [])
        if normalize_kline_date_str(value)
        and latest_date <= normalize_kline_date_str(value) <= target_date
    })
    return {
        "available": True,
        "status": "success",
        "source": source,
        "rows": visible_rows,
        "calibration_rows": calibration_rows,
        "calibration": calibration,
        "latest_pressure_label": latest_label,
        "latest_data_date": latest_date,
        "target_date": target_date,
        "is_stale_for_target": is_stale_for_target,
        "stale_trade_days": stale_trade_days,
        **({"trade_dates": normalized_trade_dates} if normalized_trade_dates else {}),
        "latest_margin_turnover_ratio_pct": latest_ratio,
        "latest_pressure_diff_pct": _safe_float(latest.get("pressure_diff_pct")),
        "summary": summary,
        "usage_note": usage_note,
    }
