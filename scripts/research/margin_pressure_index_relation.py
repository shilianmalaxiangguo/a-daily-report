from __future__ import annotations

import datetime
import math
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot
from input.tushare_runtime import _merge_margin_and_turnover_rows
from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api
from market_data.tushare_market_activity_service import fetch_tushare_open_trade_dates
from market_data.tushare_turnover_service import fetch_margin_balance_rows, fetch_market_index_amount_rows

__all__ = [
    "build_margin_pressure_index_relation",
    "fetch_margin_pressure_index_relation_rows",
    "render_margin_pressure_index_relation_markdown",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _mean(values):
    values = [_safe_float(value) for value in values if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _median(values):
    values = sorted(_safe_float(value) for value in values if value is not None)
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def _quantile(values, fraction):
    values = sorted(_safe_float(value) for value in values if value is not None)
    if not values:
        return None
    index = min(max(int(round((len(values) - 1) * _safe_float(fraction))), 0), len(values) - 1)
    return values[index]


def _pearson(xs, ys):
    pairs = [(_safe_float(x), _safe_float(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    mean_x = sum(x for x, _ in pairs) / len(pairs)
    mean_y = sum(y for _, y in pairs) / len(pairs)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x, _ in pairs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for _, y in pairs))
    if denom_x <= 0 or denom_y <= 0:
        return None
    return numerator / (denom_x * denom_y)


def _pct_change(current, previous):
    current = _safe_float(current)
    previous = _safe_float(previous)
    if current <= 0 or previous <= 0:
        return None
    return (current / previous - 1) * 100


def _round_or_none(value, digits=2):
    if value is None:
        return None
    return round(_safe_float(value), digits)


def _prepare_rows(rows, sample_days):
    prepared = []
    for row in rows or []:
        trade_date = normalize_kline_date_str((row or {}).get("trade_date") or (row or {}).get("date"))
        ratio = _safe_float((row or {}).get("margin_turnover_ratio_pct"))
        margin_balance = _safe_float((row or {}).get("margin_balance_yi"))
        turnover = _safe_float((row or {}).get("market_turnover_yi"))
        if ratio <= 0 and margin_balance > 0 and turnover > 0:
            ratio = margin_balance / turnover * 100
        if not trade_date or ratio <= 0:
            continue
        prepared.append(
            {
                **dict(row or {}),
                "trade_date": trade_date,
                "margin_turnover_ratio_pct": ratio,
                "margin_balance_yi": margin_balance,
                "market_turnover_yi": turnover,
                "sh_close": _safe_float((row or {}).get("sh_close")),
                "all_a_close": _safe_float((row or {}).get("all_a_close")),
            }
        )
    prepared.sort(key=lambda item: item.get("trade_date", ""))
    return prepared[-int(sample_days or 250) :]


def _add_changes(rows):
    result = []
    previous = {}
    for row in rows:
        item = dict(row)
        item["ratio_change_pct"] = (
            None
            if not previous
            else _safe_float(item.get("margin_turnover_ratio_pct")) - _safe_float(previous.get("margin_turnover_ratio_pct"))
        )
        item["margin_balance_change_pct"] = None if not previous else _pct_change(item.get("margin_balance_yi"), previous.get("margin_balance_yi"))
        item["market_turnover_change_pct"] = None if not previous else _pct_change(item.get("market_turnover_yi"), previous.get("market_turnover_yi"))
        item["sh_same_day_pct"] = None if not previous else _pct_change(item.get("sh_close"), previous.get("sh_close"))
        item["all_a_same_day_pct"] = None if not previous else _pct_change(item.get("all_a_close"), previous.get("all_a_close"))
        result.append(item)
        previous = item

    for index, item in enumerate(result):
        for days in (1, 3, 5):
            future_index = index + days
            item[f"sh_forward_{days}d_pct"] = (
                _pct_change(result[future_index].get("sh_close"), item.get("sh_close"))
                if future_index < len(result)
                else None
            )
            item[f"all_a_forward_{days}d_pct"] = (
                _pct_change(result[future_index].get("all_a_close"), item.get("all_a_close"))
                if future_index < len(result)
                else None
            )
    return result


def _bucket_stats(rows, predicate, index_prefix):
    selected = [row for row in rows if predicate(row)]
    keys = {
        "same_day": f"{index_prefix}_same_day_pct",
        "forward_1d": f"{index_prefix}_forward_1d_pct",
        "forward_3d": f"{index_prefix}_forward_3d_pct",
        "forward_5d": f"{index_prefix}_forward_5d_pct",
    }
    stats = {"sample": len(selected)}
    for label, key in keys.items():
        values = [row.get(key) for row in selected if row.get(key) is not None]
        stats[label] = {
            "sample": len(values),
            "avg_pct": _round_or_none(_mean(values)),
            "median_pct": _round_or_none(_median(values)),
            "positive_rate_pct": _round_or_none(
                sum(1 for value in values if _safe_float(value) > 0) / len(values) * 100 if values else None
            ),
        }
    return stats


def _overall_stats(rows, index_prefix):
    ratio_values = [row.get("margin_turnover_ratio_pct") for row in rows]
    result = _bucket_stats(rows, lambda row: True, index_prefix)
    horizon_keys = {
        "same_day": f"{index_prefix}_same_day_pct",
        "forward_1d": f"{index_prefix}_forward_1d_pct",
        "forward_3d": f"{index_prefix}_forward_3d_pct",
        "forward_5d": f"{index_prefix}_forward_5d_pct",
    }
    for horizon, key in horizon_keys.items():
        result[horizon]["ratio_corr"] = _round_or_none(_pearson(ratio_values, [row.get(key) for row in rows]), 4)
    return result


def build_margin_pressure_index_relation(rows, *, sample_days=250):
    rows = _add_changes(_prepare_rows(rows, sample_days))
    ratios = [row.get("margin_turnover_ratio_pct") for row in rows]
    p20 = _quantile(ratios, 0.2)
    p50 = _quantile(ratios, 0.5)
    p80 = _quantile(ratios, 0.8)

    buckets = {
        "融资承接比舒缓": lambda row: _safe_float(row.get("margin_turnover_ratio_pct")) <= _safe_float(p20),
        "融资承接比高压": lambda row: _safe_float(row.get("margin_turnover_ratio_pct")) >= _safe_float(p80),
        "融资升成交降": lambda row: (
            row.get("margin_balance_change_pct") is not None
            and row.get("market_turnover_change_pct") is not None
            and _safe_float(row.get("margin_balance_change_pct")) > 0
            and _safe_float(row.get("market_turnover_change_pct")) < 0
        ),
        "高压且成交降": lambda row: (
            _safe_float(row.get("margin_turnover_ratio_pct")) >= _safe_float(p80)
            and row.get("market_turnover_change_pct") is not None
            and _safe_float(row.get("market_turnover_change_pct")) < 0
        ),
        "压力下降": lambda row: row.get("ratio_change_pct") is not None and _safe_float(row.get("ratio_change_pct")) <= -3,
    }

    index_results = {
        "上证指数": {"overall": _overall_stats(rows, "sh")},
        "中证全指": {"overall": _overall_stats(rows, "all_a")},
    }
    for index_name, prefix in (("上证指数", "sh"), ("中证全指", "all_a")):
        for bucket_name, predicate in buckets.items():
            index_results[index_name][bucket_name] = _bucket_stats(rows, predicate, prefix)

    return {
        "available": bool(rows),
        "display_window_days": 25,
        "research_window_days": 250,
        "sample_days": len(rows),
        "ratio_stats": {
            "min_pct": _round_or_none(min(ratios) if ratios else None),
            "p20_pct": _round_or_none(p20),
            "median_pct": _round_or_none(p50),
            "p80_pct": _round_or_none(p80),
            "max_pct": _round_or_none(max(ratios) if ratios else None),
        },
        "latest": rows[-1] if rows else {},
        "buckets": {name: sum(1 for row in rows if predicate(row)) for name, predicate in buckets.items()},
        "index_results": index_results,
        "rows": rows,
    }


def _fetch_index_close_rows(pro, ts_code, start_date, end_date):
    frame = pro.index_daily(
        ts_code=ts_code,
        start_date=start_date.replace("-", ""),
        end_date=end_date.replace("-", ""),
    )
    rows = []
    if hasattr(frame, "to_dict"):
        raw_rows = frame.to_dict("records")
    else:
        raw_rows = list(frame or [])
    for row in raw_rows:
        trade_date = normalize_kline_date_str((row or {}).get("trade_date"))
        close = _safe_float((row or {}).get("close"))
        if trade_date and close > 0:
            rows.append({"trade_date": trade_date, "close": close})
    rows.sort(key=lambda item: item.get("trade_date", ""))
    return rows


def fetch_margin_pressure_index_relation_rows(target_date, *, sample_days=250, pro=None):
    target_date = normalize_kline_date_str(target_date)
    if not target_date:
        return []
    pro = pro or create_tushare_pro_api()
    target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
    start_date = (target_dt - datetime.timedelta(days=max(int(sample_days or 250) * 2, 365))).strftime("%Y-%m-%d")
    trade_dates = sorted(
        {
            normalize_kline_date_str(item)
            for item in fetch_tushare_open_trade_dates(start_date, target_date)
            if normalize_kline_date_str(item) and normalize_kline_date_str(item) <= target_date
        }
    )
    selected_dates = trade_dates[-int(sample_days or 250) :]
    if not selected_dates:
        return []
    start = selected_dates[0]
    end = selected_dates[-1]
    margin_rows = fetch_margin_balance_rows(start, end, pro=pro)
    amount_rows = fetch_market_index_amount_rows(start, end, pro=pro)
    pressure_rows = _merge_margin_and_turnover_rows(margin_rows, amount_rows)
    snapshot = build_margin_pressure_snapshot(pressure_rows, window_days=25, calibration_days=sample_days)
    calibration_rows = snapshot.get("calibration_rows") or pressure_rows
    rows_by_date = {
        row.get("trade_date"): dict(row)
        for row in calibration_rows
        if row.get("trade_date") in set(selected_dates)
    }
    sh_by_date = {row["trade_date"]: row["close"] for row in _fetch_index_close_rows(pro, "000001.SH", start, end)}
    all_a_by_date = {row["trade_date"]: row["close"] for row in _fetch_index_close_rows(pro, "000985.CSI", start, end)}
    result = []
    for trade_date in selected_dates:
        row = rows_by_date.get(trade_date)
        if not row:
            continue
        row["sh_close"] = sh_by_date.get(trade_date, 0.0)
        row["all_a_close"] = all_a_by_date.get(trade_date, 0.0)
        result.append(row)
    return result


def _format_stat(value):
    return "样本不足" if value is None else f"{_safe_float(value):.2f}%"


def render_margin_pressure_index_relation_markdown(relation):
    relation = relation or {}
    ratio_stats = relation.get("ratio_stats") or {}
    lines = [
        "## 融资承接比与指数关系校准",
        f"> 口径：日报正文仍只展示 {relation.get('display_window_days', 25)} 日表格；这里用 {relation.get('sample_days', 0)} 日历史样本研究融资承接比与上证指数、中证全指的关系。",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 样本交易日 | {relation.get('sample_days', 0)} |",
        f"| 融资承接比区间 | {_format_stat(ratio_stats.get('min_pct'))} - {_format_stat(ratio_stats.get('max_pct'))} |",
        f"| P20 / 中位 / P80 | {_format_stat(ratio_stats.get('p20_pct'))} / {_format_stat(ratio_stats.get('median_pct'))} / {_format_stat(ratio_stats.get('p80_pct'))} |",
        "",
    ]
    for index_name, index_payload in (relation.get("index_results") or {}).items():
        lines.extend(
            [
                f"### {index_name}",
                "| 场景 | 样本 | 当日均值 | T+1均值 | T+3均值 | T+5均值 | T+1胜率 |",
                "|------|------|----------|---------|---------|---------|---------|",
            ]
        )
        for scenario in ("overall", "融资承接比舒缓", "融资承接比高压", "融资升成交降", "高压且成交降", "压力下降"):
            stats = (index_payload or {}).get(scenario) or {}
            label = "全样本" if scenario == "overall" else scenario
            lines.append(
                f"| {label} | {stats.get('sample', 0)} | "
                f"{_format_stat((stats.get('same_day') or {}).get('avg_pct'))} | "
                f"{_format_stat((stats.get('forward_1d') or {}).get('avg_pct'))} | "
                f"{_format_stat((stats.get('forward_3d') or {}).get('avg_pct'))} | "
                f"{_format_stat((stats.get('forward_5d') or {}).get('avg_pct'))} | "
                f"{_format_stat((stats.get('forward_1d') or {}).get('positive_rate_pct'))} |"
            )
        lines.append("")
    return "\n".join(lines).strip()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="研究融资承接比与上证/中证全指关系")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--sample-days", type=int, default=250)
    args = parser.parse_args()
    rows = fetch_margin_pressure_index_relation_rows(args.target_date, sample_days=args.sample_days)
    relation = build_margin_pressure_index_relation(rows, sample_days=args.sample_days)
    print(render_margin_pressure_index_relation_markdown(relation))
