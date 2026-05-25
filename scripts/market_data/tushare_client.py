from __future__ import annotations

TUSHARE_TOKEN = "0490fd7723b48c5f0cf35cab1842ecfb4f95e6a7ebea7cc827397f91"
TUSHARE_HTTP_URL = "http://121.40.135.59:8010/"
TUSHARE_TIMEOUT_SECONDS = 8

__all__ = [
    "TUSHARE_HTTP_URL",
    "TUSHARE_TIMEOUT_SECONDS",
    "TUSHARE_TOKEN",
    "create_tushare_pro_api",
    "fetch_demo_frames",
]


def _load_tushare_module(ts_module=None):
    if ts_module is not None:
        return ts_module

    import tushare as ts  # type: ignore

    return ts


def create_tushare_pro_api(
    *,
    ts_module=None,
    token=TUSHARE_TOKEN,
    http_url=TUSHARE_HTTP_URL,
    timeout_seconds=TUSHARE_TIMEOUT_SECONDS,
):
    """Create a Tushare Pro client using the custom HTTP gateway required locally."""
    ts = _load_tushare_module(ts_module)
    pro = ts.pro_api(token, timeout=timeout_seconds)
    pro._DataApi__http_url = http_url
    return pro


def fetch_demo_frames(*, ts_module=None):
    """Small smoke-call helper matching the documented local gateway example."""
    ts = _load_tushare_module(ts_module)
    pro = create_tushare_pro_api(ts_module=ts)
    index_df = pro.index_basic(limit=5)
    bar_df = ts.pro_bar(api=pro, ts_code="000001.SZ", limit=3)
    return index_df, bar_df
