from __future__ import annotations

import datetime as _dt

DEFAULT_INPUT_REQUEST_KEYS = (
    "total_turnover",
    "major_indices",
    "wind_a",
)

_HELPER_NAME_BY_REQUEST_KEY = {
    "total_turnover": "get_total_turnover_from_tushare_first",
    "major_indices": "get_major_indices_from_tushare_first",
    "wind_a": "get_wind_a_from_tushare_first",
}


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
        registry[request_key] = helper

    return registry
