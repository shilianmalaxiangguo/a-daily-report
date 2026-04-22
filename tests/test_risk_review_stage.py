import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.risk_review_stage import build_risk_review_stage
from domains.execution_chain.stage_runtime import build_execution_stage_lookup


class RiskReviewStageTest(unittest.TestCase):
    def test_risk_review_stage_uses_dynamic_labels_and_exports_step3_bundle(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
                {"stage_key": "risk_review", "title": "明日风险预判"},
                {"stage_key": "entry_plan", "title": "明日买点预计算"},
            ]
        )

        result = build_risk_review_stage(
            {
                "data": {},
                "target_date": "2026-04-22",
                "mainline_name": "军工",
                "core_stocks": [{"name": "军工一号", "code": "000001"}],
                "secondary_stocks": [{"name": "军工二号", "code": "000002"}],
                "step2_bundle": {"gem_observation_stocks": [{"name": "弹性一号", "code": "300001"}]},
                "market_research_bundle": {
                    "filtered_out_gem_breathing_candidates": [{"name": "弹性二号", "code": "300002"}],
                },
                "zt_pool_by_sector": {"军工": []},
                "dt_pool_by_sector": {"军工": []},
                "build_step3_risk_bundle": lambda *args, **kwargs: {
                    "stock_rows": [
                        {
                            "name": "军工一号",
                            "code": "000001",
                            "pattern": "涨停",
                            "abnormal_light": "🟢 绿灯",
                            "tomorrow_risk": "承接正常",
                            "risk_level": "低",
                            "dest": "focus",
                        }
                    ],
                    "delete_group": [],
                    "keep_group": [{"name": "军工二号", "code": "000002", "reason": "等竞价", "tomorrow_risk": "观察竞价"}],
                    "focus_group": [{"name": "军工一号", "code": "000001", "reason": "风险可控", "tomorrow_risk": "低风险"}],
                    "abnormal_green_count": 1,
                    "abnormal_red_count": 0,
                    "risk_sectors_from_dt": [],
                    "mainline_a_kill": False,
                    "mainline_dt_stocks": [],
                    "structural_a_kill": False,
                    "structural_reason": "",
                    "a_kill_blacklist_updates": [],
                    "module_logs": [
                        {
                            "module": "risk.risk_bundle_runtime",
                            "step": "risk_grouping",
                            "status": "success",
                            "message": "已完成风险分层",
                            "details": {},
                        }
                    ],
                },
                "render_gem_breathing_pool_section": lambda gem_observation_stocks=None, filtered_out_gem_candidates=None: ["gem-pool-section"],
            },
            stage_lookup["risk_review"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 3 - 明日风险预判", rendered)
        self.assertIn("**Step 3.1 逐只预判明日风险**", rendered)
        self.assertIn("**Step 3 结论**:", rendered)
        self.assertIn("进入Step 4", rendered)
        self.assertIn("gem-pool-section", rendered)
        self.assertEqual(result["exports"]["focus_group"][0]["code"], "000001")
        self.assertEqual(result["exports"]["step3_bundle"]["abnormal_green_count"], 1)
        self.assertTrue(any(log["module"] == "risk.risk_bundle_runtime" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
