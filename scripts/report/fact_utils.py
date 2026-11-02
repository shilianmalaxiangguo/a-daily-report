"""Shared factual primitives, without report or strategy dependencies."""
import datetime as dt
import hashlib
import json
import math

from market_data.kline_dates import normalize_kline_date_str


def evidence_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                                    allow_nan=False).encode()).hexdigest()


def _date(value):
    return normalize_kline_date_str(value) or ""


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _target_date(value):
    normalized = _date(value)
    if not normalized:
        raise ValueError("目标日期格式不符")
    parsed = dt.date.fromisoformat(normalized)
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    if parsed > today:
        raise ValueError("目标日期不能晚于当前上海日期")
    return normalized


def html_text(soup, tag, text):
    node = soup.new_tag(tag)
    node.string = text
    return node
