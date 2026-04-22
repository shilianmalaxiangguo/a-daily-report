import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_execution_appendix_tail import run


class UseExecutionAppendixTailTest(unittest.TestCase):
    def test_execution_appendix_tail_hook_normalizes_timer_steps_and_renders_appendix(self):
        captured = {}

        def fake_normalize(timer_summary, step_status=None):
            captured["timer_summary"] = timer_summary
            captured["step_status"] = step_status
            return [["market_environment", 1.2, 1.2]]

        def fake_render(context):
            captured["render_context"] = context
            return [f"appendix:{context.get('report_version')}:{context.get('total_time')}"]

        result = run(
            {
                "inputs": {
                    "data_status": {"hot_rank": "success"},
                    "step_status": {"market_environment": True},
                    "timer_summary": {
                        "steps": [("market_environment", 1.2, 1.2)],
                        "total_time": 3.8,
                    },
                    "target_date": "2026-04-22",
                    "generated_at": "2026-04-22 21:00:00",
                    "report_version": "v2.5.0",
                },
                "helpers": {
                    "normalize_report_timer_steps": fake_normalize,
                    "render_execution_appendix": fake_render,
                },
            }
        )

        payload = result["value"]
        self.assertEqual(payload["exports"]["normalized_timer_steps"], [["market_environment", 1.2, 1.2]])
        self.assertEqual(payload["exports"]["total_time"], 3.8)
        self.assertIn("appendix:v2.5.0:3.8", "\n".join(payload["lines"]))
        self.assertEqual(captured["step_status"], {"market_environment": True})
        self.assertEqual(captured["render_context"]["target_date"], "2026-04-22")
        self.assertEqual(result["diagnostics"]["hook_name"], "report.execution_appendix_tail")
        self.assertTrue(payload["module_logs"])


if __name__ == "__main__":
    unittest.main()
