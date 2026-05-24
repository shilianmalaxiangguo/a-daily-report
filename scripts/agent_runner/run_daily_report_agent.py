from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agent_runner.daily_report_agent_runner import DailyReportAgentRequest, DailyReportAgentRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the daily report agent once.")
    parser.add_argument("target_date")
    parser.add_argument("--root-dir", default=".")
    args = parser.parse_args(argv)

    root_dir = Path(args.root_dir)
    runner = DailyReportAgentRunner(root_dir=root_dir)
    result = runner.run(DailyReportAgentRequest(target_date=args.target_date, mode="replay"))
    print(f"run_dir: {result.get('run_dir', '')}")
    print(f"status: {result.get('status', '')}")

    if result.get("status") == "error":
        return 2
    if result.get("status") == "needs_review":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
