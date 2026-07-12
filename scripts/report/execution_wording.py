"""Shared user-facing wording for next-day execution plans."""

TWO_B_CONFIRMATION_CLAUSE = "B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1"
TWO_B_CONFIRMATION_SHORT_CLAUSE = "B1参与权，B2确认权；不确认不补B2"
SAME_STOCK_T_CONFIRMATION_CLAUSE = "已有1x先视为B1参与权，强表态存活才临时加B2；走弱先取消B2并卖可卖旧仓"

PREMARKET_50_EXECUTION_TEXT = (
    f"已决定50%条件执行；50%只是最大参与上限；{TWO_B_CONFIRMATION_CLAUSE}；盘中不满足取消，回到0%不参与"
)
PREMARKET_50_EXECUTION_SHORT_TEXT = (
    f"已决定50%条件执行；最大上限50%；{TWO_B_CONFIRMATION_SHORT_CLAUSE}；不满足回到0%"
)
PREMARKET_50_TRIGGER_TEXT = (
    f"按昨晚预案检查执行资格；{TWO_B_CONFIRMATION_CLAUSE}；不满足回到0%不参与"
)
PREMARKET_FIXED_EXECUTION_TEXT = (
    f"已决定执行；按昨晚预案检查执行资格；{TWO_B_CONFIRMATION_CLAUSE}；不满足取消，回到0%不参与"
)
PREMARKET_FULL_EXECUTION_TEXT = (
    f"已决定满仓条件执行；最大可到100%，先B1再B2；{TWO_B_CONFIRMATION_CLAUSE}；盘中不满足取消，回到0%不参与"
)
PREMARKET_FULL_EXECUTION_SHORT_TEXT = (
    f"已决定满仓条件执行；最大可到100%；{TWO_B_CONFIRMATION_SHORT_CLAUSE}；不满足回到0%"
)
