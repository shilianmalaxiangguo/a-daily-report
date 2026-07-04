from __future__ import annotations

import os
from pathlib import Path

TUSHARE_TOKEN_ENV = "TUSHARE_TOKEN"
TUSHARE_HTTP_URL_ENV = "TUSHARE_HTTP_URL"
TUSHARE_TOKEN = ""
TUSHARE_HTTP_URL = ""
TUSHARE_TIMEOUT_SECONDS = 8

__all__ = [
    "TUSHARE_HTTP_URL",
    "TUSHARE_HTTP_URL_ENV",
    "TUSHARE_TIMEOUT_SECONDS",
    "TUSHARE_TOKEN",
    "TUSHARE_TOKEN_ENV",
    "check_tushare_runtime_ready",
    "create_tushare_pro_api",
    "fetch_demo_frames",
    "load_local_env_file",
]


def _load_tushare_module(ts_module=None):
    if ts_module is not None:
        return ts_module

    import tushare as ts  # type: ignore

    return ts


def load_local_env_file():
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
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


def _load_local_env_file():
    load_local_env_file()


def _resolve_runtime_value(value, env_name):
    if value is not None:
        return value
    load_local_env_file()
    return str(os.environ.get(env_name) or "").strip()


def _normalize_http_url(value):
    return str(value or "").strip().rstrip("/")


def create_tushare_pro_api(
    *,
    ts_module=None,
    token=None,
    http_url=None,
    timeout_seconds=TUSHARE_TIMEOUT_SECONDS,
):
    """Create a Tushare Pro client using the local proxy configured in .env."""
    ts = _load_tushare_module(ts_module)
    resolved_token = _resolve_runtime_value(token, TUSHARE_TOKEN_ENV)
    resolved_http_url = _normalize_http_url(_resolve_runtime_value(http_url, TUSHARE_HTTP_URL_ENV))
    pro = ts.pro_api(resolved_token, timeout=timeout_seconds)
    if resolved_http_url:
        pro._DataApi__http_url = resolved_http_url
    return pro


def fetch_demo_frames(*, ts_module=None):
    """Small smoke-call helper matching the documented local proxy example."""
    ts = _load_tushare_module(ts_module)
    pro = create_tushare_pro_api(ts_module=ts)
    index_df = pro.index_basic(limit=5)
    bar_df = ts.pro_bar(api=pro, ts_code="000001.SZ", limit=3)
    return index_df, bar_df


def _frame_row_count(value):
    if value is None:
        return 0
    try:
        return int(len(value))
    except TypeError:
        return 1


def _sanitize_runtime_error(message, *, secrets=()):
    text = str(message or "")
    for secret in secrets or ():
        secret_text = str(secret or "").strip()
        if secret_text:
            text = text.replace(secret_text, "***")
    env_token = str(os.environ.get(TUSHARE_TOKEN_ENV) or "").strip()
    if env_token:
        text = text.replace(env_token, "***")
    return text


def check_tushare_runtime_ready(
    *,
    ts_module=None,
    token=None,
    http_url=None,
    timeout_seconds=3,
):
    """Run a tiny Tushare Pro call before the long daily-report fetch starts."""
    try:
        ts = _load_tushare_module(ts_module)
        pro = create_tushare_pro_api(
            ts_module=ts,
            token=token,
            http_url=http_url,
            timeout_seconds=timeout_seconds,
        )
        index_df = pro.index_basic(limit=1)
        row_count = _frame_row_count(index_df)
        if row_count <= 0:
            return {
                "ok": False,
                "provider": "tushare.pro.index_basic",
                "checks": [{"name": "index_basic", "row_count": 0}],
                "error_type": "EmptyResult",
                "error_message": "index_basic 返回空数据",
            }
        return {
            "ok": True,
            "provider": "tushare.pro.index_basic",
            "checks": [{"name": "index_basic", "row_count": row_count}],
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": "tushare.pro.index_basic",
            "checks": [{"name": "index_basic", "row_count": 0}],
            "error_type": exc.__class__.__name__,
            "error_message": _sanitize_runtime_error(str(exc), secrets=[token]),
        }
