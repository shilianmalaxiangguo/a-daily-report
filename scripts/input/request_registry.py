from __future__ import annotations

import datetime as _dt
import inspect

DEFAULT_INPUT_REQUEST_KEYS = (
    "total_turnover",
    "major_indices",
    "wind_a",
    "csi1000",
    "turnover_rank",
    "stock_hot_rank",
    "limit_pool_snapshot",
    "sector_hot_plates",
    "concept_fund_flow",
    "sector_change_rank",
    "sector_fund_flow",
    "lhb_snapshot",
    "new_stock_calendar",
    "stock_risk_map",
    "new_high_feedback",
    "top50_turnover_share_series",
    "etf_turnover_series",
    "price_band_style_series",
    "margin_pressure",
)

_HELPER_NAME_BY_REQUEST_KEY = {
    "total_turnover": "get_total_turnover_from_tushare_first",
    "major_indices": "get_major_indices_from_tushare_first",
    "wind_a": "get_wind_a_from_tushare_first",
    "csi1000": "get_csi1000_from_tushare_first",
    "turnover_rank": "get_turnover_rank_from_tushare_first",
    "stock_hot_rank": "get_stock_hot_rank_from_tushare_first",
    "limit_pool_snapshot": "get_limit_pool_snapshot_from_tushare_first",
    "sector_hot_plates": "get_sector_hot_plates_from_tushare_first",
    "concept_fund_flow": "get_hot_concept_fund_flow_from_tushare_first",
    "sector_change_rank": "get_sector_change_rank_from_tushare_first",
    "sector_fund_flow": "get_sector_fund_flow_from_tushare_first",
    "lhb_snapshot": "get_lhb_snapshot_from_tushare_first",
    "new_stock_calendar": "get_new_stock_calendar_from_tushare_first",
    "stock_risk_map": "get_stock_risk_map_from_tushare_first",
    "new_high_feedback": "get_new_high_feedback_from_tushare_first",
    "top50_turnover_share_series": "get_top50_turnover_share_series_from_tushare_first",
    "etf_turnover_series": "get_etf_turnover_series_from_sina_first",
    "price_band_style_series": "get_price_band_style_series_from_tushare_first",
    "margin_pressure": "get_margin_pressure_from_tushare_first",
}

_FALLBACK_KWARG_BY_REQUEST_KEY = {
    "total_turnover": ("legacy_get_total_turnover_fn", "get_total_turnover_from_iwencai"),
    "major_indices": ("legacy_get_major_indices_fn", "get_major_indices_from_iwencai"),
    "wind_a": ("legacy_get_wind_a_fn", "get_wind_a_from_iwencai"),
    "csi1000": ("legacy_get_csi1000_fn", "get_csi1000_from_iwencai"),
    "turnover_rank": ("legacy_get_turnover_rank_fn", "get_turnover_rank_from_iwencai"),
    "stock_hot_rank": ("legacy_fetch_hot_rank_fn", "fetch_ths_hot_stock"),
    "limit_pool_snapshot": ("legacy_get_limit_pool_snapshot_fn", "get_legacy_limit_pool_snapshot"),
    "sector_hot_plates": ("legacy_fetch_hot_plates_fn", "fetch_hot_plate"),
    "sector_change_rank": ("legacy_get_sector_change_fn", "get_sector_change_from_iwencai"),
    "sector_fund_flow": ("legacy_get_sector_fund_flow_fn", "get_legacy_sector_fund_flow"),
    "lhb_snapshot": ("legacy_get_lhb_snapshot_fn", "get_legacy_lhb_snapshot"),
    "new_stock_calendar": ("legacy_get_new_stock_calendar_fn", "get_legacy_new_stock_calendar"),
}

_EXTRA_KWARGS_BY_REQUEST_KEY = {
    "concept_fund_flow": (("snapshot_fallback_fn", "get_concept_fund_flow_from_snapshot"),),
}


def _wrap_tushare_first_helper(request_key, helper, helpers):
    wrapped = helper
    fallback_kwarg = _FALLBACK_KWARG_BY_REQUEST_KEY.get(request_key)
    if fallback_kwarg:
        kwarg_name, fallback_helper_name = fallback_kwarg
        fallback_helper = helpers.get(fallback_helper_name)
        if callable(fallback_helper) and _helper_accepts_kwarg(wrapped, kwarg_name):
            wrapped = _wrap_default_kwarg(wrapped, kwarg_name, fallback_helper)

    for kwarg_name, helper_name in _EXTRA_KWARGS_BY_REQUEST_KEY.get(request_key, ()):
        extra_helper = helpers.get(helper_name)
        if callable(extra_helper) and _helper_accepts_kwarg(wrapped, kwarg_name):
            wrapped = _wrap_default_kwarg(wrapped, kwarg_name, extra_helper)

    return wrapped


def _wrap_default_kwarg(helper, kwarg_name, value):
    def _wrapped(*args, **kwargs):
        kwargs.setdefault(kwarg_name, value)
        return helper(*args, **kwargs)

    return _wrapped


def _helper_accepts_kwarg(helper, kwarg_name):
    try:
        signature = inspect.signature(helper)
    except (TypeError, ValueError):
        return True
    parameters = signature.parameters
    if kwarg_name in parameters:
        return True
    return any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())


def resolve_request_target_date(target_date=None, *, now=None):
    if target_date is not None:
        return str(target_date)

    now = now or _dt.datetime.now()
    yesterday = now - _dt.timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def build_input_request_registry(helpers=None):
    helpers = helpers or {}
    registry = {}

    for request_key in DEFAULT_INPUT_REQUEST_KEYS:
        helper_name = _HELPER_NAME_BY_REQUEST_KEY[request_key]
        helper = helpers.get(helper_name)
        if not callable(helper):
            raise KeyError(f"Missing input request helper: {helper_name}")
        registry[request_key] = _wrap_tushare_first_helper(request_key, helper, helpers)

    return registry
