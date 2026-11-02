from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agent_runner.daily_report_agent_runner import DailyReportAgentRequest, DailyReportAgentRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="旧账户日报运行器已停用；请使用当前板块阅读入口。")
    parser.add_argument("target_date")
    parser.add_argument("--root-dir", default=".")
    args = parser.parse_args(argv)
    runner = DailyReportAgentRunner(root_dir=Path(args.root_dir))
    result = runner.run(DailyReportAgentRequest(target_date=args.target_date))
    print(f"run_dir: {result.get('run_dir', '')}")
    print(f"status: {result.get('status', '')}")
    message = (result.get("error") or {}).get("message")
    if message:
        print(message)
    return 2 if result.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
