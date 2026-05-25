from __future__ import annotations

import json
import os
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

XUEQIU_A_SHARE_24H_HOT_PROVIDER = "xueqiu.hot_stock.type22"
XUEQIU_A_SHARE_24H_HOT_TYPE = 22
XUEQIU_HOT_STOCK_ARGUMENT_PROVIDER = "xueqiu.hot_stock.argument"
XUEQIU_HOT_STOCK_ARGUMENT_SOURCE_ROLE = "雪球AI炒作理由候选"
XUEQIU_HOT_STOCK_ENDPOINT = "https://stock.xueqiu.com/v5/stock/hot_stock/list.json"
XUEQIU_HOT_STOCK_ARGUMENT_ENDPOINT = "https://api.xueqiu.com/rainbow/ai/question/generate/hot_stock_argument.json"
XUEQIU_COOKIE_ENV = "XUEQIU_COOKIE"
XUEQIU_COOKIE_CAPTURE_DIR_ENV = "XUEQIU_COOKIE_CAPTURE_DIR"


class XueqiuCriticalFactorEmptyError(RuntimeError):
    pass


def build_xueqiu_hot_stock_url(*, page=1, size=100, hot_type=XUEQIU_A_SHARE_24H_HOT_TYPE, detail=1, include=1) -> str:
    params = {
        "detail": int(detail),
        "include": int(include),
        "page": int(page),
        "size": int(size),
        "type": int(hot_type),
    }
    return f"{XUEQIU_HOT_STOCK_ENDPOINT}?{urllib.parse.urlencode(params)}"


def build_xueqiu_hot_stock_argument_url(symbols: list[str] | tuple[str, ...]) -> str:
    cleaned = [_clean_text(symbol).upper() for symbol in symbols if _clean_text(symbol)]
    params = {"symbols": ",".join(cleaned)}
    return f"{XUEQIU_HOT_STOCK_ARGUMENT_ENDPOINT}?{urllib.parse.urlencode(params)}"


def normalize_xueqiu_hot_stock_payload(payload, *, provider=XUEQIU_A_SHARE_24H_HOT_PROVIDER) -> list[dict]:
    rows = _extract_hot_stock_items(payload)
    normalized = []
    for rank, row in enumerate(rows, start=1):
        quote = row.get("quote") if isinstance(row.get("quote"), dict) else row
        full_code = _clean_text(quote.get("symbol") or quote.get("code") or row.get("symbol") or row.get("code"))
        name = _clean_text(quote.get("name") or row.get("name"))
        if not full_code and not name:
            continue
        normalized.append(
            {
                "rank": rank,
                "code": _short_code(full_code),
                "full_code": full_code,
                "name": name,
                "price": _safe_float(quote.get("current") or quote.get("last_close") or row.get("current")),
                "change_pct": _safe_float(quote.get("percent") or row.get("percent")),
                "change_amount": _safe_float(quote.get("chg") or row.get("chg")),
                "provider": provider,
            }
        )
    return normalized


def normalize_xueqiu_hot_stock_argument_payload(payload, *, provider=XUEQIU_HOT_STOCK_ARGUMENT_PROVIDER) -> list[dict]:
    data = (payload or {}).get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return []

    normalized = []
    for full_code, row in data.items():
        if not isinstance(row, dict):
            continue
        clean_full_code = _clean_text(full_code).upper()
        argument = _clean_text(row.get("content") or row.get("argument") or row.get("reason"))
        question = _clean_text(row.get("question"))
        if not clean_full_code or not argument:
            continue
        normalized.append(
            {
                "code": _short_code(clean_full_code),
                "full_code": clean_full_code,
                "argument": argument,
                "reason": argument,
                "question": question,
                "score": _safe_int(row.get("score")),
                "url": _clean_text(row.get("url")),
                "record_id": _clean_text(row.get("record_id")),
                "share_id": _clean_text(row.get("share_id")),
                "pc_display": _safe_bool(row.get("pc_display")),
                "provider": provider,
                "source_role": XUEQIU_HOT_STOCK_ARGUMENT_SOURCE_ROLE,
            }
        )
    return normalized


def fetch_xueqiu_a_share_hot_24h(*, cookie="", page=1, size=100, timeout=10, opener=None) -> list[dict]:
    resolved_cookie = cookie or get_xueqiu_cookie()
    request = urllib.request.Request(
        build_xueqiu_hot_stock_url(page=page, size=size),
        headers=_build_headers(resolved_cookie),
    )
    open_fn = opener or urllib.request.urlopen
    with open_fn(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalize_xueqiu_hot_stock_payload(payload)


def fetch_xueqiu_hot_stock_arguments(symbols: list[str] | tuple[str, ...], *, cookie="", timeout=10, opener=None) -> list[dict]:
    resolved_cookie = cookie or get_xueqiu_cookie()
    request = urllib.request.Request(
        build_xueqiu_hot_stock_argument_url(symbols),
        headers=_build_headers(resolved_cookie),
    )
    open_fn = opener or urllib.request.urlopen
    with open_fn(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalize_xueqiu_hot_stock_argument_payload(payload)


def try_fetch_xueqiu_a_share_hot_24h(*, cookie="", page=1, size=100, timeout=10, opener=None) -> dict:
    provider = XUEQIU_A_SHARE_24H_HOT_PROVIDER
    try:
        rows = fetch_xueqiu_a_share_hot_24h(cookie=cookie, page=page, size=size, timeout=timeout, opener=opener)
        if not rows:
            raise XueqiuCriticalFactorEmptyError(provider)
        return _success_result(provider, rows)
    except Exception as exc:
        return _degraded_result(provider, exc)


def try_fetch_xueqiu_hot_stock_arguments(
    symbols: list[str] | tuple[str, ...], *, cookie="", timeout=10, opener=None
) -> dict:
    provider = XUEQIU_HOT_STOCK_ARGUMENT_PROVIDER
    try:
        rows = fetch_xueqiu_hot_stock_arguments(symbols, cookie=cookie, timeout=timeout, opener=opener)
        if not rows:
            raise XueqiuCriticalFactorEmptyError(provider)
        return _success_result(provider, rows)
    except Exception as exc:
        return _degraded_result(provider, exc)


def get_xueqiu_cookie() -> str:
    _load_local_env_file()
    capture_cookie = _read_cookie_from_capture_dir(os.environ.get(XUEQIU_COOKIE_CAPTURE_DIR_ENV, ""))
    if capture_cookie:
        return capture_cookie
    cookie = str(os.environ.get(XUEQIU_COOKIE_ENV) or "").strip()
    if cookie:
        return cookie
    return ""


def _load_local_env_file() -> None:
    candidates = (
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    )
    for env_path in candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def _read_cookie_from_capture_dir(capture_dir: str) -> str:
    if not capture_dir:
        return ""
    header_path = Path(capture_dir) / "request_header_raw.txt"
    if not header_path.exists():
        return ""
    for line in header_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.lower().startswith("cookie:"):
            return line.split(":", 1)[1].strip()
    return ""


def _build_headers(cookie):
    headers = {
        "Accept": "application/json",
        "User-Agent": "Xueqiu iPhone 14.90.2",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _success_result(provider: str, rows: list[dict]) -> dict:
    return {
        "provider": provider,
        "status": "ok",
        "rows": rows,
        "diagnostic_note": "",
        "can_continue_report": True,
    }


def _degraded_result(provider: str, exc: Exception) -> dict:
    return {
        "provider": provider,
        "status": "error",
        "rows": [],
        "diagnostic_note": _diagnostic_note(exc),
        "can_continue_report": False,
    }


def _diagnostic_note(exc: Exception) -> str:
    if isinstance(exc, XueqiuCriticalFactorEmptyError):
        return "雪球接口返回空，关键数据不完整，停止生成"
    if isinstance(exc, urllib.error.HTTPError):
        detail = _read_http_error_preview(exc)
        if exc.code in {400, 401, 403} and ("400016" in detail or "登录" in detail or "login" in detail.lower()):
            return "雪球登录态失效或缺失，关键数据不完整，停止生成"
        return f"雪球接口返回 HTTP {exc.code}，关键数据不完整，停止生成"
    return f"雪球接口异常：{type(exc).__name__}，关键数据不完整，停止生成"


def _read_http_error_preview(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    finally:
        try:
            exc.close()
        except Exception:
            pass


def _extract_hot_stock_items(payload) -> list[dict]:
    data = (payload or {}).get("data") if isinstance(payload, dict) else {}
    if isinstance(data, dict):
        for key in ("items", "list", "stocks"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _clean_text(value) -> str:
    return str(value or "").strip()


def _short_code(full_code: str) -> str:
    text = _clean_text(full_code)
    if len(text) >= 8 and text[:2].upper() in {"SH", "SZ", "BJ"}:
        return text[2:]
    return text


def _safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value):
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    return bool(value)


__all__ = [
    "XUEQIU_A_SHARE_24H_HOT_PROVIDER",
    "XUEQIU_A_SHARE_24H_HOT_TYPE",
    "XUEQIU_COOKIE_ENV",
    "XUEQIU_COOKIE_CAPTURE_DIR_ENV",
    "XUEQIU_HOT_STOCK_ARGUMENT_PROVIDER",
    "XUEQIU_HOT_STOCK_ARGUMENT_SOURCE_ROLE",
    "XueqiuCriticalFactorEmptyError",
    "build_xueqiu_hot_stock_url",
    "build_xueqiu_hot_stock_argument_url",
    "fetch_xueqiu_a_share_hot_24h",
    "fetch_xueqiu_hot_stock_arguments",
    "get_xueqiu_cookie",
    "normalize_xueqiu_hot_stock_argument_payload",
    "normalize_xueqiu_hot_stock_payload",
    "try_fetch_xueqiu_a_share_hot_24h",
    "try_fetch_xueqiu_hot_stock_arguments",
]
