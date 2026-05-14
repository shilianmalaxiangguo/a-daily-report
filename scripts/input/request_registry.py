from __future__ import annotations

import datetime as _dt
import inspect

DEFAULT_INPUT_REQUEST_KEYS = (
    "total_turnover",
    "major_indices",
    "wind_a",
    "turnover_rank",
)

_HELPER_NAME_BY_REQUEST_KEY = {
    "total_turnover": "get_total_turnover_from_tushare_first",
    "major_indices": "get_major_indices_from_tushare_first",
    "wind_a": "get_wind_a_from_tushare_first",
    "turnover_rank": "get_turnover_rank_from_tushare_first",
}

_FALLBACK_KWARG_BY_REQUEST_KEY = {
    "total_turnover": ("legacy_get_total_turnover_fn", "get_total_turnover_from_iwencai"),
    "major_indices": ("legacy_get_major_indices_fn", "get_major_indices_from_iwencai"),
    "wind_a": ("legacy_get_wind_a_fn", "get_wind_a_from_iwencai"),
    "turnover_rank": ("legacy_get_turnover_rank_fn", "get_turnover_rank_from_iwencai"),
}


def _wrap_tushare_first_helper(request_key, helper, helpers):
    fallback_kwarg = _FALLBACK_KWARG_BY_REQUEST_KEY.get(request_key)
    if not fallback_kwarg:
        return helper
    kwarg_name, fallback_helper_name = fallback_kwarg
    fallback_helper = helpers.get(fallback_helper_name)
    if not callable(fallback_helper):
        return helper
    if not _helper_accepts_kwarg(helper, kwarg_name):
        return helper

    def _wrapped(*args, **kwargs):
        kwargs.setdefault(kwarg_name, fallback_helper)
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
