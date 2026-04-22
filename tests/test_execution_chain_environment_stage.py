import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.environment_follow_stage import build_environment_follow_stage
from domains.execution_chain.stage_runtime import build_execution_stage_lookup


class ExecutionChainEnvironmentStageTest(unittest.TestCase):
    def test_build_environment_follow_stage_renders_dynamic_heading_and_exports_bundle_fields(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
            ]
        )

        result = build_environment_follow_stage(
            {
                "market_research_bundle": {
                    "watchlist": [{"name": "军工一号", "code": "000001"}],
                    "candidates": [{"name": "军工一号", "code": "000001"}],
                    "abnormal_watch_map": {"000001": {"follow_state": "跌不下去"}},
                    "sector_trend_snapshot_step1": [{"sector": "军工", "trend_count": 2}],
                    "mainline_competition_snapshot": [{"sector": "军工"}],
                    "leader_memory_bank": [{"name": "老龙头", "code": "000002"}],
                    "tracking_memory_status": {"today_seen_count": 2},
                    "abnormal_watch_pool": [{"name": "军工一号", "code": "000001"}],
                    "abnormal_projection_summary": {"projection_label": "承接强化"},
                    "step0_plan": {
                        "step0_prediction": "CLEAR",
                        "step0_prediction_cn": "🟢 跟随主线",
                        "step0_reason": "主线承接强",
                        "step0_action": "先看主线承接",
                    },
                    "market_research_snapshot": {"state_machine": {"leading_line": "军工"}},
                },
                "display_mvp_mode": False,
                "render_market_research_snapshot_section": lambda snapshot, compact=False: ["snapshot-section"],
                "render_step0_follow_section": lambda step0_plan, snapshot, compact=False: ["follow-section"],
            },
            stage_lookup["environment_follow"],
            stage_lookup,
        )

        self.assertEqual(result["lines"][:3], ["#### Step 0 - 明日环境与跟随裁决", "> **核心问题**：今天的市场研究结果，到了明天开盘前，究竟是该跟、该等等，还是根本不该参与？", "> **重要提示**：T日收盘生成的报告，分析的是T+1日（明天）的操作。Step 0 不再单独猜市场，而是直接引用统一市场研究快照。"])
        self.assertIn("snapshot-section", result["lines"])
        self.assertIn("follow-section", result["lines"])
        self.assertEqual(result["exports"]["step0_action"], "先看主线承接")
        self.assertEqual(result["exports"]["watchlist"][0]["code"], "000001")
        self.assertTrue(any(log["step"] == "render.stage" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
