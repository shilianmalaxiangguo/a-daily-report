from __future__ import annotations

import daily_report_analysis_utils as analysis_utils

__all__ = [
    "append_observation_price_focus_note",
    "append_price_focus_note",
    "build_trade_price_focus",
    "build_observation_price_focus_text",
    "build_observation_price_note_text",
    "compose_observation_focus_text",
    "normalize_observation_zone_badge",
    "should_surface_price_note",
]

_MISSING = object()


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _round_or_none(value, digits=2):
    return analysis_utils._round_or_none(value, digits)


def _same_price_level(a, b, tolerance=0.011):
    return analysis_utils._same_price_level(a, b, tolerance)


def _is_near_anchor_price(value, anchor, pct=0.01, min_abs=0.03):
    return analysis_utils._is_near_anchor_price(value, anchor, pct=pct, min_abs=min_abs)


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


def normalize_observation_zone_badge(zone_badge, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _normalize_observation_zone_badge_legacy_body(zone_badge)
    finally:
        _restore_runtime_bindings(previous)


def build_trade_price_focus(minute_plan=None, stop_plan=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_trade_price_focus_legacy_body(minute_plan=minute_plan, stop_plan=stop_plan)
    finally:
        _restore_runtime_bindings(previous)


def build_observation_price_focus_text(price_focus, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_observation_price_focus_text_legacy_body(price_focus)
    finally:
        _restore_runtime_bindings(previous)


def build_observation_price_note_text(price_focus, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_observation_price_note_text_legacy_body(price_focus)
    finally:
        _restore_runtime_bindings(previous)


def should_surface_price_note(price_focus, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _should_surface_price_note_legacy_body(price_focus)
    finally:
        _restore_runtime_bindings(previous)


def append_price_focus_note(lines, price_focus, prefix="  ", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _append_price_focus_note_legacy_body(lines, price_focus, prefix=prefix)
    finally:
        _restore_runtime_bindings(previous)


def append_observation_price_focus_note(lines, price_focus, prefix="  ", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _append_observation_price_focus_note_legacy_body(lines, price_focus, prefix=prefix)
    finally:
        _restore_runtime_bindings(previous)


def compose_observation_focus_text(confirm_text, price_focus_text="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compose_observation_focus_text_legacy_body(confirm_text, price_focus_text=price_focus_text)
    finally:
        _restore_runtime_bindings(previous)


def _normalize_observation_zone_badge(zone_badge):
    return _normalize_observation_zone_badge_legacy_body(zone_badge)


def _build_trade_price_focus(minute_plan=None, stop_plan=None):
    return _build_trade_price_focus_legacy_body(minute_plan=minute_plan, stop_plan=stop_plan)


def _build_observation_price_focus_text(price_focus):
    return _build_observation_price_focus_text_legacy_body(price_focus)


def _build_observation_price_note_text(price_focus):
    return _build_observation_price_note_text_legacy_body(price_focus)


def _should_surface_price_note(price_focus):
    return _should_surface_price_note_legacy_body(price_focus)


def _append_price_focus_note(lines, price_focus, prefix="  "):
    return _append_price_focus_note_legacy_body(lines, price_focus, prefix=prefix)


def _append_observation_price_focus_note(lines, price_focus, prefix="  "):
    return _append_observation_price_focus_note_legacy_body(lines, price_focus, prefix=prefix)


def _compose_observation_focus_text(confirm_text, price_focus_text=""):
    return _compose_observation_focus_text_legacy_body(confirm_text, price_focus_text=price_focus_text)


def _normalize_observation_zone_badge_legacy_body(zone_badge):
    badge_text = str(zone_badge or "").strip()
    if not badge_text:
        return ""

    labels = []
    for raw_label in badge_text.split("/"):
        label = "失效" if raw_label == "止损" else raw_label
        if label and label not in labels:
            labels.append(label)
    return "/".join(labels)


def _append_trade_price_component(components, label, price):
    price = _round_or_none(price)
    if price is None or price <= 0:
        return
    for item in components:
        if _same_price_level(item.get("price"), price):
            labels = item.setdefault("labels", [])
            if label and label not in labels:
                labels.append(label)
            return
    components.append(
        {
            "price": price,
            "labels": [label] if label else [],
        }
    )


def _order_trade_price_labels(labels):
    preferred = ["前低", "支撑", "止损"]
    ordered = []
    for label in preferred:
        if label in labels and label not in ordered:
            ordered.append(label)
    for label in labels:
        if label not in ordered:
            ordered.append(label)
    return ordered


def _build_trade_price_focus_legacy_body(minute_plan=None, stop_plan=None):
    minute_plan = minute_plan or {}
    stop_plan = stop_plan or {}

    confirm_price = _safe_float(minute_plan.get("confirm_price_60m"))
    support_price = _safe_float(minute_plan.get("confirm_support_60m"))
    structure_stop_30m = _safe_float(minute_plan.get("structure_stop_30m"))
    plan_structure_stop = _safe_float(stop_plan.get("structure_stop"))
    plan_structure_label = str(stop_plan.get("structure_label", "") or "").strip()
    daily_anchor_stop = _safe_float(stop_plan.get("daily_anchor_stop"))
    breakout_open_anchor = _safe_float(stop_plan.get("breakout_open_anchor"))
    breakout_limit_anchor = _safe_float(stop_plan.get("breakout_limit_anchor"))
    effective_stop = _safe_float(stop_plan.get("effective_stop"))
    hard_stop = _safe_float(stop_plan.get("hard_stop"))

    raw_structure_stop = structure_stop_30m or plan_structure_stop
    execution_stop = effective_stop if effective_stop > 0 else (raw_structure_stop or hard_stop or 0.0)
    stop_overridden_to_hard = (
        raw_structure_stop > 0
        and hard_stop > 0
        and execution_stop > 0
        and _same_price_level(execution_stop, hard_stop)
        and raw_structure_stop < hard_stop - 0.011
    )

    components = []
    confluence_reasons = []
    if execution_stop > 0:
        _append_trade_price_component(components, "止损", execution_stop)

    if not stop_overridden_to_hard and execution_stop > 0:
        if support_price > 0 and _is_near_anchor_price(support_price, execution_stop):
            _append_trade_price_component(components, "支撑", support_price)
        if daily_anchor_stop > 0 and _is_near_anchor_price(daily_anchor_stop, execution_stop):
            _append_trade_price_component(components, "前低", daily_anchor_stop)
        if breakout_open_anchor > 0 and _is_near_anchor_price(breakout_open_anchor, execution_stop, pct=0.015, min_abs=0.05):
            _append_trade_price_component(components, "支撑", breakout_open_anchor)
            confluence_reasons.append("关键大阳开盘价")
        if breakout_limit_anchor > 0 and _is_near_anchor_price(breakout_limit_anchor, execution_stop, pct=0.015, min_abs=0.05):
            _append_trade_price_component(components, "支撑", breakout_limit_anchor)
            confluence_reasons.append("涨停价")
        if plan_structure_stop > 0 and not _same_price_level(plan_structure_stop, structure_stop_30m):
            anchor_label = "前低" if plan_structure_label and "30分钟" not in plan_structure_label else "止损"
            if _is_near_anchor_price(plan_structure_stop, execution_stop):
                _append_trade_price_component(components, anchor_label, plan_structure_stop)

    if not components and support_price > 0:
        _append_trade_price_component(components, "支撑", support_price)

    zone_prices = [item.get("price") for item in components if item.get("price")]
    zone_low = min(zone_prices) if zone_prices else 0.0
    zone_high = max(zone_prices) if zone_prices else 0.0
    key_zone_display = "-"
    if zone_low > 0 and zone_high > 0:
        if _same_price_level(zone_low, zone_high):
            key_zone_display = f"{zone_low:.2f}"
        else:
            key_zone_display = f"{zone_low:.2f}~{zone_high:.2f}"

    raw_labels = []
    for item in components:
        raw_labels.extend(item.get("labels", []))
    ordered_labels = _order_trade_price_labels(raw_labels)

    zone_badge = ""
    note_text = ""
    if stop_overridden_to_hard:
        zone_badge = "结构过深"
        note_text = "原结构止损过深，执行上收至单笔-5%硬止损。"
    elif len(ordered_labels) >= 2:
        zone_badge = "/".join(ordered_labels)
        note_text = f"{zone_badge}靠近，视为同一关键带。"
    elif ordered_labels:
        note_text = f"当前关键位主要看{ordered_labels[0]}。"
    if confluence_reasons:
        confluence_text = "、".join(dict.fromkeys(confluence_reasons))
        note_text = f"{note_text}且贴近{confluence_text}附近。" if note_text else f"该位置贴近{confluence_text}附近。"

    discipline_text = ""
    if execution_stop > 0:
        discipline_text = "如果这笔交易还对，不该失守执行止损。"
        note_text = f"{note_text}{discipline_text}" if note_text else discipline_text

    execution_stop_display = f"{execution_stop:.2f}" if execution_stop > 0 else "-"
    hard_stop_display = "-"
    if hard_stop > 0:
        hard_stop_display = "同执行止损" if execution_stop > 0 and _same_price_level(hard_stop, execution_stop) else f"{hard_stop:.2f}"

    compact_parts = []
    if key_zone_display != "-":
        zone_part = f"关键位/带{key_zone_display}"
        if zone_badge:
            zone_part += f"（{zone_badge}）"
        compact_parts.append(zone_part)
    if execution_stop_display != "-":
        compact_parts.append(f"执行止损{execution_stop_display}")
    if hard_stop_display not in ("-", "同执行止损"):
        compact_parts.append(f"最晚硬止损{hard_stop_display}")
    compact_text = "；".join(compact_parts) if compact_parts else "-"

    action_stop_text = "-"
    if execution_stop_display != "-":
        action_stop_text = f"执行止损{execution_stop_display}"
    elif hard_stop_display not in ("-", "同执行止损"):
        action_stop_text = f"最晚硬止损{hard_stop_display}"

    return {
        "confirm_price": _round_or_none(confirm_price),
        "support_price": _round_or_none(support_price),
        "key_zone_low": _round_or_none(zone_low) if zone_low > 0 else None,
        "key_zone_high": _round_or_none(zone_high) if zone_high > 0 else None,
        "key_zone_display": key_zone_display,
        "execution_stop": _round_or_none(execution_stop) if execution_stop > 0 else None,
        "execution_stop_display": execution_stop_display,
        "hard_stop": _round_or_none(hard_stop) if hard_stop > 0 else None,
        "hard_stop_display": hard_stop_display,
        "zone_badge": zone_badge,
        "note_text": note_text,
        "compact_text": compact_text,
        "action_stop_text": action_stop_text,
        "stop_overridden_to_hard": stop_overridden_to_hard,
        "confluence_reasons": list(dict.fromkeys(confluence_reasons)),
    }


def _build_observation_price_focus_text_legacy_body(price_focus):
    price_focus = price_focus or {}

    key_zone_display = str(price_focus.get("key_zone_display", "-") or "-")
    zone_badge = _normalize_observation_zone_badge(price_focus.get("zone_badge", ""))
    execution_stop = _safe_float(price_focus.get("execution_stop"))
    hard_stop = _safe_float(price_focus.get("hard_stop"))
    key_zone_low = _safe_float(price_focus.get("key_zone_low"))
    key_zone_high = _safe_float(price_focus.get("key_zone_high"))

    compact_parts = []
    if key_zone_display != "-":
        zone_part = f"关键位/带{key_zone_display}"
        if zone_badge:
            zone_part += f"（{zone_badge}）"
        compact_parts.append(zone_part)

    zone_covers_execution = False
    if execution_stop > 0 and key_zone_low > 0 and key_zone_high > 0:
        zone_covers_execution = (
            execution_stop >= min(key_zone_low, key_zone_high) - 0.011
            and execution_stop <= max(key_zone_low, key_zone_high) + 0.011
        )
    if execution_stop > 0 and (key_zone_display == "-" or not zone_covers_execution or "失效" not in zone_badge):
        compact_parts.append(f"观察失效位{execution_stop:.2f}")

    if hard_stop > 0 and not _same_price_level(hard_stop, execution_stop):
        compact_parts.append(f"最晚失效位{hard_stop:.2f}")

    return "；".join(compact_parts) if compact_parts else "-"


def _build_observation_price_note_text_legacy_body(price_focus):
    price_focus = price_focus or {}
    note_parts = []

    if price_focus.get("stop_overridden_to_hard"):
        note_parts.append("原结构过深，前台先看最晚失效位。")
    else:
        zone_badge = _normalize_observation_zone_badge(price_focus.get("zone_badge", ""))
        if "/" in zone_badge:
            note_parts.append(f"{zone_badge}靠近，视为同一关键带。")

    confluence_reasons = price_focus.get("confluence_reasons") or []
    if confluence_reasons:
        note_parts.append(f"该位置贴近{'、'.join(dict.fromkeys(confluence_reasons))}附近。")

    if _safe_float(price_focus.get("execution_stop")) > 0:
        note_parts.append("如果这个观察对象继续强，就不该失守这条关键位。")

    return "".join(note_parts)


def _should_surface_price_note_legacy_body(price_focus):
    if not price_focus:
        return False
    if price_focus.get("confluence_reasons"):
        return True
    zone_badge = str(price_focus.get("zone_badge", "") or "")
    return "前低" in zone_badge


def _append_price_focus_note_legacy_body(lines, price_focus, prefix="  "):
    if not _should_surface_price_note(price_focus):
        return
    note_text = str(price_focus.get("note_text", "") or "").strip()
    if note_text:
        lines.append(f"{prefix}价格怎么看：{note_text}")


def _append_observation_price_focus_note_legacy_body(lines, price_focus, prefix="  "):
    if not _should_surface_price_note(price_focus):
        return
    note_text = _build_observation_price_note_text(price_focus)
    if note_text:
        lines.append(f"{prefix}价格怎么看：{note_text}")


def _compose_observation_focus_text_legacy_body(confirm_text, price_focus_text=""):
    parts = [f"09:50-10:10观察价{confirm_text}"]
    price_focus_text = str(price_focus_text or "").strip()
    if price_focus_text and price_focus_text != "-":
        parts.append(price_focus_text)
    return "；".join(parts)
