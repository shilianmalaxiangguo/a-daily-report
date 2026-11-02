from __future__ import annotations

import requests

from legacy_runtime_shim import load_legacy_module

_LEGACY_MODULE = load_legacy_module("tencent_finance_data")
_LEGACY_CLASS = getattr(_LEGACY_MODULE, "TencentFinanceData", None) if _LEGACY_MODULE is not None else None


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_code(raw_code):
    code = str(raw_code or "").strip()
    for prefix in ("sz", "sh", "bj", ".SZ", ".SH", ".SS"):
        code = code.replace(prefix, "")
    return code


def _quote_symbol(code):
    normalized = _normalize_code(code)
    if normalized.startswith(("6", "9")):
        return f"sh{normalized}"
    if normalized.startswith(("8", "4")):
        return f"bj{normalized}"
    return f"sz{normalized}"


class TencentFinanceData:
    """本地腾讯财经兼容层。

    旧版 TencentFinanceData 仍负责热榜、日历等已存在能力；本类补齐日报运行时
    现在依赖的批量股票补价接口，避免旧类缺方法时把请求体检打成失败。
    """

    def __init__(self):
        self._legacy = None
        if _LEGACY_CLASS is not None:
            try:
                self._legacy = _LEGACY_CLASS()
            except Exception:
                self._legacy = None
        self.session = getattr(self._legacy, "session", None) or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )

    def __getattr__(self, name):
        if self._legacy is not None:
            return getattr(self._legacy, name)
        raise AttributeError(f"TencentFinanceData has no attribute {name!r}")

    def get_calendar_events(self, target_date=None):
        if self._legacy is not None and hasattr(self._legacy, "get_calendar_events"):
            try:
                legacy_events = _normalize_calendar_events(self._legacy.get_calendar_events(target_date))
                if legacy_events:
                    return _filter_calendar_events_by_target_date(legacy_events, target_date)
                return self._fetch_calendar_events_from_cls(target_date)
            except TypeError:
                try:
                    legacy_events = _normalize_calendar_events(self._legacy.get_calendar_events())
                    if legacy_events:
                        return _filter_calendar_events_by_target_date(legacy_events, target_date)
                    return self._fetch_calendar_events_from_cls(target_date)
                except Exception:
                    return self._fetch_calendar_events_from_cls(target_date)
            except Exception:
                return self._fetch_calendar_events_from_cls(target_date)
        return self._fetch_calendar_events_from_cls(target_date)

    def _fetch_calendar_events_from_cls(self, target_date=None):
        url = "https://www.cls.cn/api/calendar/web/list"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.cls.cn/investkalendar",
            "Origin": "https://www.cls.cn",
        }
        response = self.session.get(url, headers=headers, timeout=15)
        data = response.json()
        if not isinstance(data, dict) or data.get("code") != 200:
            return []
        events = []
        for day_data in data.get("data") or []:
            if not isinstance(day_data, dict):
                continue
            calendar_day = day_data.get("calendar_day", "")
            if target_date and str(calendar_day or "") != str(target_date):
                continue
            week = day_data.get("week", "")
            for item in day_data.get("items") or []:
                if not isinstance(item, dict):
                    continue
                event_data = item.get("event")
                if not isinstance(event_data, dict):
                    continue
                title = str(event_data.get("title") or "").strip()
                if not title:
                    continue
                events.append(
                    {
                        "date": calendar_day,
                        "week": week,
                        "time": item.get("calendar_time", ""),
                        "title": title,
                        "star": event_data.get("star", 0),
                        "country": event_data.get("country", ""),
                        "type": item.get("type"),
                    }
                )
        return events

    def get_xuangubao_news(self, pages=5):
        if self._legacy is not None and hasattr(self._legacy, "get_xuangubao_news"):
            return self._legacy.get_xuangubao_news(pages)
        return []

    def get_xuangubao_plates(self):
        if self._legacy is not None and hasattr(self._legacy, "get_xuangubao_plates"):
            return self._legacy.get_xuangubao_plates()
        return []

    def get_stock_batch_info(self, codes):
        normalized_codes = [_normalize_code(code) for code in codes or []]
        normalized_codes = [code for code in normalized_codes if code]
        if not normalized_codes:
            return {}

        if self._legacy is not None and hasattr(self._legacy, "get_stock_batch_info"):
            try:
                result = self._legacy.get_stock_batch_info(normalized_codes)
                if result:
                    return result
            except Exception:
                pass

        symbols = [_quote_symbol(code) for code in normalized_codes]
        response = self.session.get(f"https://qt.gtimg.cn/q={','.join(symbols)}", timeout=10)
        return self._parse_stock_quote_text(response.text)

    def _parse_stock_quote_text(self, text):
        result = {}
        for line in str(text or "").splitlines():
            if '"' not in line or "~" not in line:
                continue
            fields = line.split('"')[1].split("~")
            if len(fields) < 4:
                continue
            code = _normalize_code(fields[2] if len(fields) > 2 else "")
            if not code:
                continue
            result[code] = {
                "name": fields[1] if len(fields) > 1 else "",
                "code": code,
                "close": _safe_float(fields[3] if len(fields) > 3 else None),
                "open": _safe_float(fields[5] if len(fields) > 5 else None),
                "change_pct": _safe_float(fields[32] if len(fields) > 32 else None),
                "high": _safe_float(fields[33] if len(fields) > 33 else None),
                "low": _safe_float(fields[34] if len(fields) > 34 else None),
                "turnover": _safe_float(fields[37] if len(fields) > 37 else None) / 10000,
                "data_source": "tencent.qt",
            }
        return result


__all__ = ["TencentFinanceData"]


def _normalize_calendar_events(events):
    normalized = []
    for event in events or []:
        if isinstance(event, dict):
            normalized.append(event)
    return normalized


def _filter_calendar_events_by_target_date(events, target_date=None):
    if not target_date:
        return list(events or [])
    target = str(target_date)
    return [
        event
        for event in (events or [])
        if str((event or {}).get("date") or (event or {}).get("calendar_day") or "") == target
    ]
