"""Compatibility notice for the retired account-report agent.

The old orchestrator and tests are archived under docs/archive/daily-report-framework/.
It must not rebuild deprecated instructions through a second production entry.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class DailyReportAgentRequest:
    target_date: str
    mode: str = "replay"
    update_decision_ledger: bool = False
    review_prior_participation: bool = False
    output_variant: str = "sector"


@dataclass(frozen=True)
class DailyReportAgentDependencies:
    load_data: Callable[[DailyReportAgentRequest], dict[str, Any]] | None = None


class DailyReportAgentRunner:
    def __init__(self, *, root_dir: str | Path = ".",
                 dependencies: DailyReportAgentDependencies | None = None):
        self.root_dir = Path(root_dir)

    def run(self, request: DailyReportAgentRequest) -> dict[str, Any]:
        # Stop before reading data or creating run folders. Historical plans
        # and dependency injection must not reactivate the retired workflow.
        command = (".generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py "
                   f"{request.target_date} --replay")
        return {
            "status": "error", "mode": request.mode, "run_dir": "",
            "error": {
                "code": "retired_report_runner",
                "message": f"旧账户日报运行器已停用，不再生成操作建议。请使用板块阅读入口：{command}",
            },
        }
