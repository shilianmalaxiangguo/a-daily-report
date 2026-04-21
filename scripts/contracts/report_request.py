from typing import TypedDict


class ReportRequest(TypedDict, total=False):
    target_date: str
    run_mode: str
    variant: str
    persist_strategy_tracking: bool
