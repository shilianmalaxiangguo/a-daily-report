from __future__ import annotations

import datetime

__all__ = [
    "normalize_kline_date_str",
    "parse_kline_date",
    "short_kline_date",
]


def normalize_kline_date_str(date_value):
    """标准化K线日期到 YYYY-MM-DD，兼容 YYYYMMDD / YYYY-MM-DD / datetime。"""
    if date_value is None:
        return ""

    if hasattr(date_value, "strftime"):
        return date_value.strftime("%Y-%m-%d")

    date_str = str(date_value).strip()
    if not date_str:
        return ""

    date_str = date_str.split(" ")[0].replace("/", "-")

    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    if len(date_str) >= 10 and date_str[4] == "-" and date_str[7] == "-":
        return date_str[:10]

    return date_str


def parse_kline_date(date_value):
    """解析K线日期，失败时返回None。"""
    normalized = normalize_kline_date_str(date_value)
    if not normalized:
        return None

    try:
        return datetime.datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError:
        return None


def short_kline_date(date_value):
    """将 YYYY-MM-DD 缩短为 MM-DD，便于结构图展示。"""
    normalized = normalize_kline_date_str(date_value)
    if len(normalized) >= 10:
        return normalized[5:10]
    return normalized
