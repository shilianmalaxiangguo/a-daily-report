import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_report_stages import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseReportStagesTest(unittest.TestCase):
    def test_report_stages_are_built_from_dynamic_stage_registry(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "observe"},
                    "mainline": {"primary_line": "军工"},
                    "strategy_contract": {"contract_label": "conditional_entry"},
                },
                "decision": {
                    "execution_permission": {"label": "attack_50_ready"},
                    "action_plan": {
                        "action_label": "conditional_entry",
                        "headline": "沿军工进入50%标准进攻预演",
                        "trigger": "次日完成参与窗口确认",
                    },
                },
            },
        )

        result = run(ctx)

        stages = result["patches"]["derived"]["report_stages"]
        self.assertEqual([stage["stage_key"] for stage in stages], ["market_environment", "selection_focus", "execution_gate"])
        self.assertEqual(stages[0]["title"], "市场环境")
        self.assertEqual(stages[1]["title"], "主线与筛选")
        self.assertEqual(stages[2]["title"], "执行条件")
        self.assertTrue(all("summary" in stage for stage in stages))


if __name__ == "__main__":
    unittest.main()
