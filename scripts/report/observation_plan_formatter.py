from __future__ import annotations

__all__ = [
    "build_abnormal_follow_rule",
    "format_abnormal_observation_columns",
    "format_frozen_plan_columns",
    "refine_abnormal_follow_display",
]

_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def build_abnormal_follow_rule(abnormal_type, follow_state, anchor_price, abnormal_info, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_abnormal_follow_rule_legacy_body(abnormal_type, follow_state, anchor_price, abnormal_info)
    finally:
        _restore_runtime_bindings(previous)


def refine_abnormal_follow_display(anchor_price, action_rule, minute_plan=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _refine_abnormal_follow_display_legacy_body(anchor_price, action_rule, minute_plan=minute_plan)
    finally:
        _restore_runtime_bindings(previous)


def format_abnormal_observation_columns(item, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _format_abnormal_observation_columns_legacy_body(item)
    finally:
        _restore_runtime_bindings(previous)


def format_frozen_plan_columns(plan, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _format_frozen_plan_columns_legacy_body(plan)
    finally:
        _restore_runtime_bindings(previous)


def _build_abnormal_follow_rule(abnormal_type, follow_state, anchor_price, abnormal_info):
    return _build_abnormal_follow_rule_legacy_body(abnormal_type, follow_state, anchor_price, abnormal_info)


def _refine_abnormal_follow_display(anchor_price, action_rule, minute_plan=None):
    return _refine_abnormal_follow_display_legacy_body(anchor_price, action_rule, minute_plan=minute_plan)


def _format_abnormal_observation_columns(item):
    return _format_abnormal_observation_columns_legacy_body(item)


def _format_frozen_plan_columns(plan):
    return _format_frozen_plan_columns_legacy_body(plan)


def _build_abnormal_follow_rule_legacy_body(abnormal_type, follow_state, anchor_price, abnormal_info):
    anchor_text = f"{anchor_price:.2f}" if anchor_price else "-"
    body_mid = _safe_float(abnormal_info.get("body_mid", 0))
    body_mid_text = f"{body_mid:.2f}" if body_mid else anchor_text

    if abnormal_type == "恐怖阴线异动":
        if follow_state == "跌不下去":
            return f"只看09:50-10:10能否收回阴线实体一半（约{body_mid_text}）"
        if follow_state == "缩量消化":
            return f"只做缩量后再转强，锚点不破{anchor_text}"
        if follow_state == "新异动待观察":
            return "先看次日是否继续缩量，不急着接"
        return f"跌破{anchor_text}说明异动后无承接，先取关"

    if abnormal_type == "长上影异动":
        if follow_state == "跌不下去":
            return f"只看09:50-10:10窗口内能否重新站回实体区（约{body_mid_text}以上）"
        if follow_state == "缩量消化":
            return f"等缩量后再收复实体，不破{anchor_text}才有资格继续看"
        if follow_state == "新异动待观察":
            return "先看次日能否站回实体，不追长上影当天"
        return f"承接已经走弱，跌回{anchor_text}附近以下就先放弃"

    if follow_state == "跌不下去":
        return f"只看回踩不破{anchor_text}后，09:50-10:10窗口内能否再转强"
    if follow_state == "缩量消化":
        return f"缩量消化后再看结构确认，锚点{anchor_text}"
    if follow_state == "新异动待观察":
        return "先看次日承接，不追大阳当天"
    return f"跌破{anchor_text}说明第一波异动失效"


def _refine_abnormal_follow_display_legacy_body(anchor_price, action_rule, minute_plan=None):
    minute_plan = minute_plan or {}
    minute_guard = _round_or_none(
        minute_plan.get("confirm_support_60m") or minute_plan.get("structure_stop_30m")
    )
    base_anchor = _round_or_none(anchor_price)
    if minute_guard is not None and base_anchor is not None:
        display_anchor_price = max(base_anchor, minute_guard)
    else:
        display_anchor_price = minute_guard if minute_guard is not None else base_anchor
    display_rule = str(action_rule or "").strip()
    confirm_rule = str(minute_plan.get("confirm_rule_60m", "") or "").strip()
    if confirm_rule:
        display_rule = confirm_rule if confirm_rule.startswith("只看") else f"只看{confirm_rule}"
    return display_anchor_price, display_rule or str(action_rule or "").strip()


def _format_abnormal_observation_columns_legacy_body(item):
    item = item or {}
    history_anchor = _round_or_none(item.get("anchor_price"))
    nextday_guard = _round_or_none(item.get("display_anchor_price"))
    if nextday_guard is None:
        nextday_guard = history_anchor
    history_text = f"{history_anchor:.2f}" if history_anchor is not None else "-"
    nextday_text = f"{nextday_guard:.2f}" if nextday_guard is not None else "-"
    return history_text, nextday_text


def _format_frozen_plan_columns_legacy_body(plan):
    plan = plan or {}
    entry_low = _round_or_none(plan.get("entry_range_low"))
    entry_high = _round_or_none(plan.get("entry_range_high"))
    if entry_low is not None and entry_high is not None:
        entry_text = f"{entry_low:.2f}-{entry_high:.2f}"
    elif entry_low is not None:
        entry_text = f"{entry_low:.2f}"
    else:
        entry_text = "-"
    confirm_price = _round_or_none(plan.get("confirm_price_60m"))
    confirm_text = f"{confirm_price:.2f}" if confirm_price is not None else "-"
    history_anchor_text, nextday_guard_text = _format_abnormal_observation_columns(plan)
    execution_stop = _round_or_none(plan.get("execution_stop") or plan.get("effective_stop"))
    execution_text = f"{execution_stop:.2f}" if execution_stop is not None else "-"
    return entry_text, confirm_text, nextday_guard_text, history_anchor_text, execution_text
