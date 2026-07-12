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
    "TushareReplayProApi",
    "check_tushare_runtime_ready",
    "create_tushare_pro_api",
    "fetch_demo_frames",
    "load_local_env_file",
    "resolve_tushare_runtime_config",
]


def _load_tushare_module(ts_module=None):
    if ts_module is not None:
        return ts_module

    import tushare as ts  # type: ignore

    return ts


def _local_env_candidates():
    return [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]


def _read_env_file(env_path):
    values = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            values[key] = value
    return values


def _read_local_env_values():
    for env_path in _local_env_candidates():
        if env_path.exists():
            return _read_env_file(env_path)
    return {}


def load_local_env_file():
    for env_path in _local_env_candidates():
        if not env_path.exists():
            continue
        for key, value in _read_env_file(env_path).items():
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


def _normalize_http_urls(value):
    return [
        _normalize_http_url(item)
        for item in str(value or "").split(",")
        if _normalize_http_url(item)
    ]


def _is_replay_pro_url(value):
    return any(item.lower().endswith("/tushare/pro") for item in _normalize_http_urls(value))


def _provider_for_http_url(value):
    return "tushare.b.daily" if _is_replay_pro_url(value) else "tushare.pro.index_basic"


def resolve_tushare_runtime_config(*, token=None, http_url=None, env=None):
    """Resolve Tushare config with the local B channel taking priority."""
    if token is not None or http_url is not None:
        runtime_env = os.environ if env is None else env
        local_values = _read_local_env_values() if env is None or env is os.environ else {}
        if env is None or env is os.environ:
            load_local_env_file()
        return {
            "token": str(
                token if token is not None else runtime_env.get(TUSHARE_TOKEN_ENV) or local_values.get(TUSHARE_TOKEN_ENV) or ""
            ).strip(),
            "http_url": _normalize_http_url(
                http_url
                if http_url is not None
                else runtime_env.get(TUSHARE_HTTP_URL_ENV) or local_values.get(TUSHARE_HTTP_URL_ENV)
            ),
        }

    runtime_env = os.environ if env is None else env
    local_values = _read_local_env_values() if env is None or env is os.environ else {}
    local_http_url = _normalize_http_url(local_values.get(TUSHARE_HTTP_URL_ENV))
    runtime_http_url = _normalize_http_url(runtime_env.get(TUSHARE_HTTP_URL_ENV))

    if _is_replay_pro_url(local_http_url):
        return {
            "token": str(local_values.get(TUSHARE_TOKEN_ENV) or "").strip(),
            "http_url": local_http_url,
        }
    if _is_replay_pro_url(runtime_http_url):
        return {
            "token": str(runtime_env.get(TUSHARE_TOKEN_ENV) or "").strip(),
            "http_url": runtime_http_url,
        }

    load_local_env_file()
    return {
        "token": str(runtime_env.get(TUSHARE_TOKEN_ENV) or local_values.get(TUSHARE_TOKEN_ENV) or "").strip(),
        "http_url": _normalize_http_url(runtime_env.get(TUSHARE_HTTP_URL_ENV) or local_http_url),
    }


class TushareReplayProApi:
    """Small adapter for Replay GET endpoints shaped like Tushare Pro methods."""

    def __init__(self, *, token, base_url, timeout_seconds=TUSHARE_TIMEOUT_SECONDS, requests_module=None):
        self.token = str(token or "").strip()
        self.base_urls = _normalize_http_urls(base_url)
        self.base_url = self.base_urls[0] if self.base_urls else ""
        self.timeout_seconds = timeout_seconds
        self._requests_module = requests_module

    def __getattr__(self, api_name):
        if str(api_name).startswith("_"):
            raise AttributeError(api_name)

        def caller(**kwargs):
            return self.query(api_name, **kwargs)

        return caller

    def _request_timeout_seconds(self):
        if len(self.base_urls) <= 1:
            return self.timeout_seconds
        try:
            timeout = float(self.timeout_seconds)
        except (TypeError, ValueError):
            return self.timeout_seconds
        return max(1.0, timeout / len(self.base_urls))

    def query(self, api_name, **kwargs):
        if self._requests_module is None:
            import requests as requests_module
        else:
            requests_module = self._requests_module

        params = {}
        for key, value in (kwargs or {}).items():
            if value not in (None, ""):
                params[key] = value
        response = None
        last_error = None
        request_timeout = self._request_timeout_seconds()
        for base_url in self.base_urls:
            try:
                response = requests_module.get(
                    f"{base_url}/{api_name}",
                    headers={"X-API-Key": self.token},
                    params=params,
                    timeout=request_timeout,
                )
                response.raise_for_status()
                break
            except Exception as exc:
                response = None
                last_error = exc
        if response is None:
            raise last_error or RuntimeError(f"tushare replay {api_name} all base urls failed")
        payload = response.json()
        code = payload.get("code") if isinstance(payload, dict) else None
        if code not in (None, 0, "0"):
            raise RuntimeError(f"tushare replay {api_name} code {code}: {payload.get('msg') or payload.get('message') or ''}")
        data = payload.get("data") if isinstance(payload, dict) else payload
        try:
            import pandas as pd
        except Exception as exc:
            raise RuntimeError("pandas is required for Tushare replay adapter") from exc
        if isinstance(data, dict):
            fields = data.get("fields") or []
            items = data.get("items") or data.get("rows") or data.get("list") or data.get("records") or []
            if fields and isinstance(items, list):
                return pd.DataFrame(items, columns=fields)
            return pd.DataFrame(items if isinstance(items, list) else [])
        if isinstance(data, list):
            return pd.DataFrame(data)
        return pd.DataFrame()


def create_tushare_pro_api(
    *,
    ts_module=None,
    token=None,
    http_url=None,
    timeout_seconds=TUSHARE_TIMEOUT_SECONDS,
):
    """Create a Tushare Pro client, preferring the configured B HTTP channel."""
    config = resolve_tushare_runtime_config(token=token, http_url=http_url)
    resolved_token = config["token"]
    resolved_http_url = config["http_url"]
    if _is_replay_pro_url(resolved_http_url):
        return TushareReplayProApi(
            token=resolved_token,
            base_url=resolved_http_url,
            timeout_seconds=timeout_seconds,
        )
    ts = _load_tushare_module(ts_module)
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
    config = resolve_tushare_runtime_config(token=token, http_url=http_url)
    provider = _provider_for_http_url(config["http_url"])
    try:
        pro = create_tushare_pro_api(
            ts_module=ts_module,
            token=config["token"],
            http_url=config["http_url"],
            timeout_seconds=timeout_seconds,
        )
        if _is_replay_pro_url(config["http_url"]):
            probe_name = "daily"
            frame = pro.daily(ts_code="000001.SZ", limit=1)
        else:
            probe_name = "index_basic"
            frame = pro.index_basic(limit=1)
        row_count = _frame_row_count(frame)
        if row_count <= 0:
            return {
                "ok": False,
                "provider": provider,
                "checks": [{"name": probe_name, "row_count": 0}],
                "error_type": "EmptyResult",
                "error_message": f"{probe_name} 返回空数据",
            }
        return {
            "ok": True,
            "provider": provider,
            "checks": [{"name": probe_name, "row_count": row_count}],
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": provider,
            "checks": [{"name": "daily" if _is_replay_pro_url(config["http_url"]) else "index_basic", "row_count": 0}],
            "error_type": exc.__class__.__name__,
            "error_message": _sanitize_runtime_error(str(exc), secrets=[config["token"]]),
        }
