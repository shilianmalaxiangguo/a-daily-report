from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic

import requests

__all__ = ["XuangubaoIntradayAnalyzer"]

_LEGACY_ANALYZER_PATH = Path("/Users/chaixixi/.workbuddy/skills/a-daily-report/scripts/xuangubao_intraday.py")
_LEGACY_ANALYZER_CLASS = None
_LEGACY_ANALYZER_LOAD_ATTEMPTED = False
_NEWSFLASH_URL = "https://baoer-api.xuangubao.com.cn/api/v6/message/newsflash"
_MARKET_REAL_URL = "https://api-ddc-wscn.xuangubao.com.cn/market/real"
_PLATES_URL = "https://flash-api.xuangubao.com.cn/api/surge_stock/plates"
_LIMIT_UP_POOL_URL = "https://flash-api.xuangubao.com.cn/api/pool/detail"
_MARKET_REAL_FIELDS = "prod_name,last_px,px_change,px_change_rate,symbol,trade_status,market_type"
_NEWSFLASH_PAGE_SIZE = 100
_DIRECT_FACT_DIAGNOSTIC_KEYS = {
    "xuangubao_news": "newsflash",
    "xuangubao_plates": "plates",
    "xuangubao_limit_up_reasons": "limit_up_reasons",
}


def _load_local_env_file() -> None:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
        return


def _get_ivanka_token():
    _load_local_env_file()
    return str(os.environ.get("XUANGUBAO_IVANKA_TOKEN") or "").strip()


def _target_date_window_ms(target_date):
    if not target_date:
        return None
    try:
        start = datetime.fromisoformat(str(target_date)).replace(tzinfo=timezone(timedelta(hours=8)))
    except ValueError:
        return None
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _timestamp_to_ms(value):
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    if timestamp < 10_000_000_000:
        timestamp *= 1000
    return int(timestamp)


def _load_legacy_analyzer_class():
    global _LEGACY_ANALYZER_CLASS, _LEGACY_ANALYZER_LOAD_ATTEMPTED
    if _LEGACY_ANALYZER_LOAD_ATTEMPTED:
        return _LEGACY_ANALYZER_CLASS

    _LEGACY_ANALYZER_LOAD_ATTEMPTED = True
    if not _LEGACY_ANALYZER_PATH.exists():
        _LEGACY_ANALYZER_CLASS = None
        return None

    try:
        spec = importlib.util.spec_from_file_location("_legacy_workbuddy_xuangubao_intraday", _LEGACY_ANALYZER_PATH)
        if spec is None or spec.loader is None:
            _LEGACY_ANALYZER_CLASS = None
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LEGACY_ANALYZER_CLASS = getattr(module, "XuangubaoIntradayAnalyzer", None)
    except Exception:
        _LEGACY_ANALYZER_CLASS = None
    return _LEGACY_ANALYZER_CLASS


class XuangubaoIntradayAnalyzer:
    """本地兼容层：优先复用旧 skill 的选股通分析器，缺失时回退为空结果。"""

    def __init__(self):
        legacy_cls = _load_legacy_analyzer_class()
        self._legacy = None
        self._session = requests.Session()
        self._request_counts = {}
        self._request_timings_ms = {}
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.5",
                "Origin": "https://xuangutong.com.cn",
                "Referer": "https://xuangutong.com.cn/",
                "origin": "https://xuangutong.com.cn",
                "referer": "https://xuangutong.com.cn/",
                "x-appgo-platform": "device=pc",
                "x-track-info": '{"AppId":"com.xuangutong.web","AppVersion":"1.0.0"}',
            }
        )
        token = _get_ivanka_token()
        if token:
            self._session.headers.update({"x-ivanka-token": token})
        if legacy_cls is not None:
            try:
                self._legacy = legacy_cls()
            except Exception:
                self._legacy = None

    def _request_json(self, label, url, **kwargs):
        started_at = monotonic()
        try:
            return self._session.get(url, **kwargs).json()
        finally:
            elapsed_ms = (monotonic() - started_at) * 1000
            self._request_counts[label] = self._request_counts.get(label, 0) + 1
            self._request_timings_ms[label] = round(
                self._request_timings_ms.get(label, 0.0) + elapsed_ms,
                1,
            )

    def _reset_request_diagnostics(self):
        self._request_counts = {}
        self._request_timings_ms = {}

    def _attach_request_diagnostics(self, result):
        diagnostics = result.setdefault("diagnostics", {})
        diagnostics["request_counts"] = dict(self._request_counts)
        diagnostics["request_timings_ms"] = dict(self._request_timings_ms)
        return result

    def _fetch_news(self, pages=20, target_date=None):
        token = _get_ivanka_token()
        if not token:
            return [], "missing XUANGUBAO_IVANKA_TOKEN"
        self._session.headers.setdefault("x-ivanka-token", token)
        target_window = _target_date_window_ms(target_date)
        all_news = []
        quote_symbols = []
        seen_symbols = set()
        cursor = None
        diagnostics = []
        reached_older_than_target = False
        for _page in range(pages):
            params = {
                "limit": _NEWSFLASH_PAGE_SIZE,
                "subj_ids": "10,35",
                "has_explain": "false",
                "platform": "pcweb",
            }
            if cursor:
                params["cursor"] = cursor
            data = self._request_json("newsflash", _NEWSFLASH_URL, params=params, timeout=10)
            if data.get("code") != 20000:
                diagnostics.append(str(data.get("message") or data.get("code") or "newsflash failed"))
                break
            payload = data.get("data") or {}
            messages = payload.get("messages") or []
            if not messages:
                break
            for message in messages:
                if not isinstance(message, dict):
                    continue
                created_at_ms = _timestamp_to_ms(message.get("created_at"))
                if target_window and created_at_ms is not None:
                    start_ms, end_ms = target_window
                    if created_at_ms >= end_ms:
                        continue
                    if created_at_ms < start_ms:
                        reached_older_than_target = True
                        continue
                stocks = list(message.get("stocks") or message.get("all_stocks") or [])
                for stock in (message.get("stocks") or []) + (message.get("all_stocks") or []):
                    if not isinstance(stock, dict):
                        continue
                    symbol = str(stock.get("symbol") or "").strip()
                    if symbol and symbol not in seen_symbols:
                        seen_symbols.add(symbol)
                        quote_symbols.append(symbol)
                all_news.append(
                    {
                        "title": message.get("title", ""),
                        "summary": message.get("summary", ""),
                        "time": message.get("created_at", 0),
                        "stocks": stocks,
                        "all_stocks": message.get("all_stocks", []),
                        "plates": message.get("bkj_infos", []),
                    }
                )
            cursor = payload.get("next_cursor")
            if not cursor or reached_older_than_target:
                break
        else:
            if cursor:
                diagnostics.append("newsflash page limit reached before target date window ended")
        if quote_symbols:
            quote_map, quote_diag = self._fetch_market_real_quotes(quote_symbols)
            if quote_diag:
                diagnostics.append(f"market_real={quote_diag}")
            if quote_map:
                self._enrich_news_stocks(all_news, quote_map)
        return all_news, "; ".join(diagnostics)

    def _fetch_market_real_quotes(self, symbols):
        quote_map = {}
        for start in range(0, len(symbols or []), 80):
            batch = [symbol for symbol in symbols[start : start + 80] if symbol]
            if not batch:
                continue
            params = {
                "fields": _MARKET_REAL_FIELDS,
                "prod_code": ",".join(batch),
            }
            data = self._request_json("market_real", _MARKET_REAL_URL, params=params, timeout=10)
            if data.get("code") != 20000:
                return quote_map, str(data.get("message") or data.get("code") or "market real failed")
            payload = data.get("data") or {}
            fields = payload.get("fields") or []
            snapshot = payload.get("snapshot") or {}
            for symbol, values in snapshot.items():
                if not isinstance(values, (list, tuple)):
                    continue
                quote = dict(zip(fields, values))
                quote["symbol"] = quote.get("symbol") or symbol
                quote["quote_source"] = "xuangubao.market_real"
                quote_map[str(symbol)] = quote
        return quote_map, ""

    def _enrich_news_stocks(self, news_items, quote_map):
        for news in news_items or []:
            enriched = []
            for stock in news.get("stocks") or []:
                if not isinstance(stock, dict):
                    continue
                item = dict(stock)
                quote = quote_map.get(str(item.get("symbol") or ""))
                if quote:
                    item.update(quote)
                enriched.append(item)
            news["stocks"] = enriched

    def _fetch_plates(self):
        data = self._request_json("plates", _PLATES_URL, timeout=10)
        if data.get("code") != 20000:
            return [], str(data.get("message") or data.get("code") or "plates failed")
        payload = data.get("data") or {}
        plates = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            plates.append(
                {
                    "id": item.get("id", 0),
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                }
            )
        return plates, ""

    def _fetch_limit_up_reasons(self):
        data = self._request_json(
            "limit_up_reasons",
            _LIMIT_UP_POOL_URL,
            params={"pool_name": "limit_up"},
            timeout=10,
        )
        if data.get("code") != 20000:
            return [], str(data.get("message") or data.get("code") or "limit up pool failed")
        items = data.get("data") or []
        if not isinstance(items, list):
            return [], "limit up pool data is not list"
        reasons = []
        for item in items:
            if not isinstance(item, dict):
                continue
            surge_reason = item.get("surge_reason") or {}
            if not isinstance(surge_reason, dict):
                surge_reason = {}
            reasons.append(
                {
                    "symbol": item.get("symbol", ""),
                    "name": item.get("stock_chi_name", ""),
                    "price": item.get("price"),
                    "change_percent": item.get("change_percent"),
                    "limit_up_days": item.get("limit_up_days", 0),
                    "first_limit_up": item.get("first_limit_up", 0),
                    "last_limit_up": item.get("last_limit_up", 0),
                    "break_limit_up_times": item.get("break_limit_up_times", 0),
                    "stock_reason": surge_reason.get("stock_reason", ""),
                    "related_plates": surge_reason.get("related_plates", []) or [],
                    "surge_reason": surge_reason,
                }
            )
        return reasons, ""

    def _fetch_direct_xuangubao_data(self, target_date=None):
        self._reset_request_diagnostics()
        diagnostics = {}
        try:
            news, news_diag = self._fetch_news(target_date=target_date)
        except Exception as error:
            news = []
            news_diag = str(error)
        if news_diag:
            diagnostics["newsflash"] = news_diag

        try:
            plates, plates_diag = self._fetch_plates()
        except Exception as error:
            plates = []
            plates_diag = str(error)
        if plates_diag:
            diagnostics["plates"] = plates_diag

        try:
            limit_up_reasons, limit_up_diag = self._fetch_limit_up_reasons()
        except Exception as error:
            limit_up_reasons = []
            limit_up_diag = str(error)
        if limit_up_diag:
            diagnostics["limit_up_reasons"] = limit_up_diag

        return self._attach_request_diagnostics({
            "xuangubao_news": news,
            "xuangubao_plates": plates,
            "xuangubao_limit_up_reasons": limit_up_reasons,
            "diagnostics": diagnostics,
        })

    def fetch_xuangubao_data(self, target_date=None):
        direct_result = self._fetch_direct_xuangubao_data(target_date=target_date)
        direct_diagnostics = direct_result.get("diagnostics") or {}
        incomplete_direct_keys = {
            fact_key
            for fact_key, diagnostic_key in _DIRECT_FACT_DIAGNOSTIC_KEYS.items()
            if direct_diagnostics.get(diagnostic_key) not in (None, "", {})
        }
        if all(direct_result.get(key) for key in _DIRECT_FACT_DIAGNOSTIC_KEYS) and not incomplete_direct_keys:
            return direct_result

        legacy_result = {}
        if self._legacy is not None and hasattr(self._legacy, "fetch_xuangubao_data"):
            legacy_started_at = monotonic()
            try:
                try:
                    legacy_result = dict(self._legacy.fetch_xuangubao_data(target_date=target_date) or {})
                except TypeError:
                    legacy_result = dict(self._legacy.fetch_xuangubao_data() or {})
            except Exception:
                legacy_result = {}
            finally:
                legacy_elapsed_ms = (monotonic() - legacy_started_at) * 1000
                self._request_counts["legacy"] = self._request_counts.get("legacy", 0) + 1
                self._request_timings_ms["legacy"] = round(
                    self._request_timings_ms.get("legacy", 0.0) + legacy_elapsed_ms,
                    1,
                )
                self._attach_request_diagnostics(direct_result)
        if not legacy_result:
            return direct_result
        merged_result = dict(legacy_result)
        for key, value in direct_result.items():
            if key == "diagnostics" or not value:
                continue
            if key in incomplete_direct_keys and legacy_result.get(key):
                continue
            merged_result[key] = value
        merged_result["diagnostics"] = {
            **(legacy_result.get("diagnostics") or {}),
            **direct_diagnostics,
        }
        return merged_result

    def __getattr__(self, name):
        if self._legacy is not None:
            return getattr(self._legacy, name)
        raise AttributeError(f"XuangubaoIntradayAnalyzer has no attribute {name!r}")
