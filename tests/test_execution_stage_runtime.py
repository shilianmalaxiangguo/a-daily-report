import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.stage_runtime import (
    build_execution_stage_lookup,
    get_execution_stage_label,
    run_registered_execution_stages,
)


class ExecutionStageRuntimeTest(unittest.TestCase):
    def test_stage_lookup_uses_registry_order_instead_of_fixed_numbers(self):
        lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
            ]
        )

        self.assertEqual(get_execution_stage_label(lookup, "environment_follow"), "Step 0")
        self.assertEqual(get_execution_stage_label(lookup, "watch_pool"), "Step 1")
        self.assertEqual(get_execution_stage_label(lookup, "candidate_selection"), "Step 2")
        self.assertEqual(get_execution_stage_label(lookup, "candidate_selection", "5"), "Step 2.5")

    def test_runner_merges_stage_exports_and_module_logs(self):
        def build_environment(ctx, stage_meta, stage_lookup):
            self.assertEqual(stage_meta["label"], "Step 0")
            return {
                "lines": [f"#### {stage_meta['label']} - {stage_meta['title']}"],
                "exports": {"watchlist": [{"code": "000001"}], "environment_ready": True},
                "module_logs": [
                    {
                        "module": "domains.execution_chain.environment_follow_stage",
                        "step": "render.stage",
                        "status": "success",
                        "message": "已生成环境阶段",
                        "details": {"stage_key": stage_meta["stage_key"]},
                    }
                ],
            }

        def build_watch_pool(ctx, stage_meta, stage_lookup):
            self.assertTrue(ctx["environment_ready"])
            self.assertEqual(len(ctx["watchlist"]), 1)
            self.assertEqual(stage_lookup["watch_pool"]["label"], "Step 1")
            return {
                "lines": [f"#### {stage_meta['label']} - {stage_meta['title']}", "watch-count=1"],
                "exports": {"watch_count": 1},
                "module_logs": [
                    {
                        "module": "domains.execution_chain.watch_pool_stage",
                        "step": "render.stage",
                        "status": "success",
                        "message": "已生成观察池阶段",
                        "details": {"stage_key": stage_meta["stage_key"]},
                    }
                ],
            }

        result = run_registered_execution_stages(
            [
                {
                    "stage_key": "environment_follow",
                    "title": "明日环境与跟随裁决",
                    "builder": build_environment,
                },
                {
                    "stage_key": "watch_pool",
                    "title": "明天观察池",
                    "builder": build_watch_pool,
                },
            ],
            stage_context={"target_date": "2026-04-22"},
        )

        self.assertEqual(
            result["lines"],
            [
                "#### Step 0 - 明日环境与跟随裁决",
                "#### Step 1 - 明天观察池",
                "watch-count=1",
            ],
        )
        self.assertEqual(result["context"]["watch_count"], 1)
        self.assertEqual(result["stage_outputs"]["watch_pool"]["watch_count"], 1)
        self.assertEqual([item["stage_key"] for item in result["stages"]], ["environment_follow", "watch_pool"])
        self.assertGreaterEqual(len(result["module_logs"]), 2)


if __name__ == "__main__":
    unittest.main()
