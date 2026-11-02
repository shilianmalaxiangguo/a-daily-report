import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.assertEqual(result["stage_timing_rows"], [])

    def test_runner_records_each_stage_timing_when_requested(self):
        def build_stage(ctx, stage_meta, stage_lookup):
            return {"exports": {stage_meta["stage_key"]: True}}

        with patch(
            "domains.execution_chain.stage_runtime.monotonic",
            side_effect=[10.0, 10.4, 20.0, 20.6],
        ):
            result = run_registered_execution_stages(
                [
                    {
                        "stage_key": "environment_follow",
                        "title": "明日环境与跟随裁决",
                        "builder": build_stage,
                    },
                    {
                        "stage_key": "watch_pool",
                        "title": "明天观察池",
                        "builder": build_stage,
                    },
                ],
                capture_timings=True,
            )

        self.assertEqual(
            [row["stage_key"] for row in result["stage_timing_rows"]],
            ["environment_follow", "watch_pool"],
        )
        self.assertEqual(
            [row["phase"] for row in result["stage_timing_rows"]],
            ["明日环境与跟随裁决", "明天观察池"],
        )
        self.assertAlmostEqual(result["stage_timing_rows"][0]["elapsed_seconds"], 0.4)
        self.assertAlmostEqual(result["stage_timing_rows"][1]["elapsed_seconds"], 0.6)

    def test_runner_flattens_nested_stage_timings_without_double_counting(self):
        def build_pk_stage(ctx, stage_meta, stage_lookup):
            return {
                "timing_rows": [
                    {"phase": "候选决策栈", "elapsed_seconds": 1.5},
                    {"phase": "渲染", "elapsed_seconds": 0.5},
                ]
            }

        with patch(
            "domains.execution_chain.stage_runtime.monotonic",
            side_effect=[10.0, 14.0],
        ):
            result = run_registered_execution_stages(
                [
                    {
                        "stage_key": "pk_decision",
                        "title": "PK决胜局（期望值模型）",
                        "builder": build_pk_stage,
                    }
                ],
                capture_timings=True,
            )

        self.assertEqual(
            [row["phase"] for row in result["stage_timing_rows"]],
            [
                "PK决胜局（期望值模型）/候选决策栈",
                "PK决胜局（期望值模型）/渲染",
                "PK决胜局（期望值模型）/入口封装",
            ],
        )
        self.assertEqual(
            [row["elapsed_seconds"] for row in result["stage_timing_rows"]],
            [1.5, 0.5, 2.0],
        )


if __name__ == "__main__":
    unittest.main()
