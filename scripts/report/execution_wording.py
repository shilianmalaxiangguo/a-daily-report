"""Shared user-facing wording for next-day execution plans."""

from report.position_tier_contract import (
    POSITION_TIER_B1_B2_PCT,
    POSITION_TIER_B1_PCT,
    normalize_planned_position_tier_pct,
)

TWO_B_CONFIRMATION_CLAUSE = "B1先到1x/50%取得参与权，B2只在确认后补到2x/100%；B1未变强不补B2，走弱先取消B2并检查B1"
TWO_B_CONFIRMATION_SHORT_CLAUSE = "B1到1x/50%，B2确认后才补到2x/100%；不确认不补B2"
SAME_STOCK_T_CONFIRMATION_CLAUSE = "已有1x/50%先视为B1参与权，强表态存活才加B2至2x/100%；走弱先取消B2并卖可卖旧仓"
ONE_B_EXECUTION_CLAUSE = "B1只执行到1x/50%；1x是本计划仓位上限，不追加B2"
ZERO_POSITION_EXECUTION_CLAUSE = "0%不参与，只观察或处理旧仓"
UNKNOWN_POSITION_EXECUTION_CLAUSE = "仓位档未明确时不新增参与"


def execution_clause_for_position_pct(position_pct):
    if position_pct in (None, ""):
        return UNKNOWN_POSITION_EXECUTION_CLAUSE
    try:
        normalized_pct = normalize_planned_position_tier_pct(position_pct)
    except (TypeError, ValueError):
        return UNKNOWN_POSITION_EXECUTION_CLAUSE
    if normalized_pct >= POSITION_TIER_B1_B2_PCT:
        return TWO_B_CONFIRMATION_CLAUSE
    if normalized_pct >= POSITION_TIER_B1_PCT:
        return ONE_B_EXECUTION_CLAUSE
    return ZERO_POSITION_EXECUTION_CLAUSE

PREMARKET_50_EXECUTION_TEXT = (
    "已决定1x/50%半仓条件执行；B1取得参与权，1x是本计划仓位上限，不追加B2；"
    "盘中不满足取消，回到0%不参与"
)
PREMARKET_50_EXECUTION_SHORT_TEXT = (
    "已决定1x/50%半仓条件执行；B1参与权，本计划不追加B2；不满足回到0%"
)
PREMARKET_50_TRIGGER_TEXT = (
    "按昨晚1x/50%半仓预案检查B1执行资格；本计划不追加B2；不满足回到0%不参与"
)
PREMARKET_FIXED_EXECUTION_TEXT = (
    "已决定执行；按昨晚预案检查既定仓位档与执行资格；不满足取消，回到0%不参与"
)
PREMARKET_FULL_EXECUTION_TEXT = (
    f"已决定2x/100%满仓计划；{TWO_B_CONFIRMATION_CLAUSE}；盘中不满足取消，回到0%不参与"
)
PREMARKET_FULL_EXECUTION_SHORT_TEXT = (
    f"已决定2x/100%满仓计划；{TWO_B_CONFIRMATION_SHORT_CLAUSE}；不满足回到0%"
)
PREMARKET_FULL_TRIGGER_TEXT = (
    f"按昨晚2x/100%满仓预案执行；{TWO_B_CONFIRMATION_SHORT_CLAUSE}；不满足回到0%不参与"
)
