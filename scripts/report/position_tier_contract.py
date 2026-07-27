from __future__ import annotations

import math
from typing import Any


POSITION_TIER_NONE_PCT = 0
POSITION_TIER_B1_PCT = 50
POSITION_TIER_B1_B2_PCT = 100
POSITION_TIER_B1_ACTUAL_MIN_PCT = 40
POSITION_TIER_B1_ACTUAL_MAX_PCT = 60
POSITION_TIER_PCTS = (
    POSITION_TIER_NONE_PCT,
    POSITION_TIER_B1_PCT,
    POSITION_TIER_B1_B2_PCT,
)
POSITION_TIER_X_VALUES = (0, 1, 2)


def _finite_number(value: Any, *, suffix: str = "") -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        raise ValueError("position tier must be numeric")
    text = str(value).strip()
    if suffix and text.lower().endswith(suffix):
        text = text[: -len(suffix)].strip()
    try:
        number = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid position tier: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"invalid position tier: {value!r}")
    return number


def normalize_position_tier_pct(value: Any) -> int:
    position_pct = _finite_number(value, suffix="%")
    if position_pct < 0 or position_pct > POSITION_TIER_B1_B2_PCT:
        raise ValueError(f"position percentage is outside 0%-100%: {value!r}")
    if position_pct <= POSITION_TIER_NONE_PCT:
        return POSITION_TIER_NONE_PCT
    if POSITION_TIER_B1_ACTUAL_MIN_PCT <= position_pct <= POSITION_TIER_B1_ACTUAL_MAX_PCT:
        return POSITION_TIER_B1_PCT
    if position_pct == POSITION_TIER_B1_B2_PCT:
        return POSITION_TIER_B1_B2_PCT
    raise ValueError(
        "position percentage must be 0%, an actual 40%-60% B1 fill, or 100%: "
        f"{value!r}"
    )


def normalize_planned_position_tier_pct(value: Any) -> int:
    position_pct = _finite_number(value, suffix="%")
    if not position_pct.is_integer() or int(position_pct) not in POSITION_TIER_PCTS:
        raise ValueError(f"planned position percentage must be 0%, 50%, or 100%: {value!r}")
    return int(position_pct)


def planned_position_tier_cap_pct(value: Any) -> int:
    position_pct = _finite_number(value, suffix="%")
    if position_pct < POSITION_TIER_B1_PCT:
        return POSITION_TIER_NONE_PCT
    if position_pct < POSITION_TIER_B1_B2_PCT:
        return POSITION_TIER_B1_PCT
    return POSITION_TIER_B1_B2_PCT


def position_tier_pct_to_x(value: Any) -> int:
    return normalize_position_tier_pct(value) // POSITION_TIER_B1_PCT


def position_x_to_tier_pct(value: Any) -> int:
    position_x = _finite_number(value, suffix="x")
    if not position_x.is_integer() or int(position_x) not in POSITION_TIER_X_VALUES:
        raise ValueError(f"position x tier must be 0, 1x, or 2x: {value!r}")
    return int(position_x) * POSITION_TIER_B1_PCT


def position_tier_label(value: Any) -> str:
    position_pct = normalize_position_tier_pct(value)
    return {
        POSITION_TIER_NONE_PCT: "0%不参与",
        POSITION_TIER_B1_PCT: "1x/50%半仓/B1参与权",
        POSITION_TIER_B1_B2_PCT: "2x/100%满仓/B1+B2",
    }[position_pct]
