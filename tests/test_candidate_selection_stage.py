import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.candidate_selection_stage import build_candidate_selection_stage
from domains.execution_chain.stage_runtime import build_execution_stage_lookup


class CandidateSelectionStageTest(unittest.TestCase):
    def test_candidate_selection_stage_uses_dynamic_stage_labels_and_exports_step2_bundle(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
            ]
        )

        result = build_candidate_selection_stage(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-22",
                "exit_analysis": {"sector_name": "军工"},
                "candidates": [{"name": "军工一号", "code": "000001"}],
                "watchlist": [{"name": "军工一号", "code": "000001", "sector": "军工", "score": 91}],
                "abnormal_watch_map": {"000001": {"follow_state": "跌不下去"}},
                "dragon_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工"}],
                "zt_pool_by_sector": {"军工": [{"name": "军工一号"}]},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["军工"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda gem_observation_stocks, filtered_out_gem_candidates=None, display_mvp_mode=None: ["gem-section"],
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "tomorrow_strength": 91}],
                    "core_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "pattern": "涨停", "abnormal_summary": "跌不下去", "tomorrow_strength": 91, "core_level": "🔥 连板核心", "tmr_forecast": "2进3"}],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [{"sector": "军工", "trend_count": 3, "core_count": 1, "anchor_name": "军工一号", "anchor_code": "000001", "density_score": 88, "anchor_reason": "主线龙头"}],
                    "extreme_conviction_list": [{"name": "军工一号", "code": "000001", "sector": "军工", "conviction_reason": "主线最强", "conviction_rule": "只等60分钟确认"}],
                    "mainline_name": "军工",
                    "module_logs": [{"module": "selection.candidate_bundle_runtime", "step": "candidate_grouping", "status": "success", "message": "已完成主线分组", "details": {}}],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            stage_lookup["candidate_selection"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 2 - 明日核心标的", rendered)
        self.assertIn("**Step 2.1 明日核心预判**", rendered)
        self.assertIn("**Step 2.5 极度看好名单**", rendered)
        self.assertIn("gem-section", rendered)
        self.assertEqual(result["exports"]["step2_bundle"]["mainline_name"], "军工")
        self.assertEqual(result["exports"]["core_stocks"][0]["code"], "000001")
        self.assertEqual(result["exports"]["mainline_in_quadrant"], None)
        self.assertTrue(any(log["module"] == "selection.candidate_bundle_runtime" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
