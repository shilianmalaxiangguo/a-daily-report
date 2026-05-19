from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

__all__ = ["AShareDataCollector"]

_LEGACY_COLLECTOR_PATH = Path("/Users/chaixixi/.workbuddy/skills/a-daily-report/scripts/data_collector.py")
_LEGACY_COLLECTOR_CLASS = None
_LEGACY_COLLECTOR_LOAD_ATTEMPTED = False
_HUNANWANZHU_URL = "https://api.hunanwanzhu.com/api/wx/v2/hot/stock/buy/list"
_HUNANWANZHU_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49"
    ),
    "Referer": "https://servicewechat.com/",
    "Accept": "application/json, text/plain, */*",
}


def _load_legacy_collector_class():
    global _LEGACY_COLLECTOR_CLASS, _LEGACY_COLLECTOR_LOAD_ATTEMPTED
    if _LEGACY_COLLECTOR_LOAD_ATTEMPTED:
        return _LEGACY_COLLECTOR_CLASS

    _LEGACY_COLLECTOR_LOAD_ATTEMPTED = True
    if not _LEGACY_COLLECTOR_PATH.exists():
        _LEGACY_COLLECTOR_CLASS = None
        return None

    try:
        spec = importlib.util.spec_from_file_location("_legacy_workbuddy_data_collector", _LEGACY_COLLECTOR_PATH)
        if spec is None or spec.loader is None:
            _LEGACY_COLLECTOR_CLASS = None
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LEGACY_COLLECTOR_CLASS = getattr(module, "AShareDataCollector", None)
    except Exception:
        _LEGACY_COLLECTOR_CLASS = None
    return _LEGACY_COLLECTOR_CLASS


def _iter_wanzhu_candidate_dates(query_date: str, max_lookback_days: int = 10):
    try:
        base_date = datetime.strptime(str(query_date), "%Y-%m-%d").date()
    except ValueError:
        yield str(query_date)
        return
    for offset in range(max_lookback_days + 1):
        yield (base_date - timedelta(days=offset)).isoformat()


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _request_hunanwanzhu_payload(stock_date: str) -> dict:
    params = urlencode(
        {
            "stock_date": stock_date,
            "page": 1,
            "page_size": 20,
            "fund_rank": 0,
        }
    )
    request = Request(f"{_HUNANWANZHU_URL}?{params}", headers=_HUNANWANZHU_HEADERS)
    with urlopen(request, timeout=10) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload or "{}")


def _is_wanzhu_unpublished_date(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    message = str(payload.get("message") or payload.get("msg") or "")
    return payload.get("code") == 1000 and "not in list" in message


def _extract_hunanwanzhu_rows(payload: dict, *, query_date: str, source_date: str, limit: int = 10) -> list:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") or {}
    rows = data.get("list") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return []

    parsed = []
    for index, item in enumerate(rows[:limit], 1):
        if not isinstance(item, dict):
            continue
        code = str(item.get("stock_code") or item.get("code") or "").strip()
        name = str(item.get("stock_name") or item.get("name") or "").strip()
        if not code and not name:
            continue
        parsed.append(
            {
                "rank": index,
                "name": name,
                "code": code,
                "holder_count": item.get("count", 0),
                "holder_amount": _safe_float(item.get("total_fund"), 0.0),
                "desc": item.get("stock_desc", ""),
                "yes_count": item.get("yes_count", 0),
                "comments_count": item.get("comments_count", 0),
                "choice_count": item.get("choice_count", 0),
                "id": item.get("id"),
                "query_date": query_date,
                "source_date": source_date,
            }
        )
    return parsed


def _fetch_hunanwanzhu_top10(query_date: str) -> list:
    for source_date in _iter_wanzhu_candidate_dates(query_date):
        try:
            payload = _request_hunanwanzhu_payload(source_date)
        except Exception:
            continue
        rows = _extract_hunanwanzhu_rows(payload, query_date=query_date, source_date=source_date)
        if rows:
            return rows
        if not _is_wanzhu_unpublished_date(payload):
            continue
    return []


class AShareDataCollector:
    """本地兼容层：优先复用旧 skill 的 collector，缺失时只保留入口直跑所需最小接口。"""

    def __init__(self):
        legacy_cls = _load_legacy_collector_class()
        self._legacy = None
        if legacy_cls is not None:
            try:
                self._legacy = legacy_cls()
            except Exception:
                self._legacy = None

    def get_wanzhu_top10(self, query_date: str) -> list:
        if self._legacy is not None and hasattr(self._legacy, "get_wanzhu_top10"):
            try:
                result = self._legacy.get_wanzhu_top10(query_date)
                rows = list(result or [])
                if rows:
                    return rows
            except Exception:
                pass
        return _fetch_hunanwanzhu_top10(query_date)

    def __getattr__(self, name):
        if self._legacy is not None:
            return getattr(self._legacy, name)
        raise AttributeError(f"AShareDataCollector has no attribute {name!r}")
