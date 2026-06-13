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
    "create_tushare_pro_api",
    "fetch_demo_frames",
]


def _load_tushare_module(ts_module=None):
    if ts_module is not None:
        return ts_module

    import tushare as ts  # type: ignore

    return ts


def _load_local_env_file():
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


def _resolve_runtime_value(value, env_name):
    if value is not None:
        return value
    _load_local_env_file()
    return str(os.environ.get(env_name) or "").strip()


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
    resolved_http_url = _resolve_runtime_value(http_url, TUSHARE_HTTP_URL_ENV)
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
