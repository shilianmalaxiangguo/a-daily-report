import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.candidate_bundle_runtime import build_candidate_bundle_contract


class CandidateBundleRuntimeTest(unittest.TestCase):
    def test_candidate_bundle_contract_builds_mainline_and_crossline_groups(self):
        result = build_candidate_bundle_contract(
            data={
                "lianban_data": {
                    "stocks": [
                        {"code": "000001", "连板数": 2},
                        {"code": "000002", "连板数": 1},
                    ]
                }
            },
            exit_analysis={"sector_name": "军工"},
            candidates=[{"code": "000001"}, {"code": "000002"}],
            watchlist=[
                {"name": "军工一号", "code": "000001", "sector": "军工", "score": 70},
                {"name": "机器人一号", "code": "000002", "sector": "机器人", "score": 60},
            ],
            abnormal_watch_map={
                "000001": {"follow_state": "跌不下去", "abnormal_type": "恐怖阴线异动"},
                "000002": {"follow_state": "缩量消化", "abnormal_type": "长上影异动"},
            },
            dragon_stocks=[{"name": "军工龙头", "code": "000001", "sector": "军工"}],
            zt_pool_by_sector={"军工": [{"代码": "000001"}]},
            gem_breathing_candidates=[{"name": "创业板样本", "code": "300001"}],
            target_date="2026-04-22",
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            get_abnormal_rank_adjustment=lambda item: (
                18 if item.get("follow_state") == "跌不下去" else 10,
                item.get("follow_state", ""),
                "rule",
            ),
            split_candidates_by_mainline=lambda stocks, mainline_name: (
                [item for item in stocks if item.get("sector") == mainline_name],
                [item for item in stocks if item.get("sector") != mainline_name],
            ),
            build_gem_observation_pool=lambda candidates, target_date="": [{"code": "300001", "name": "创业板样本"}],
            build_sector_trend_snapshot=lambda *args, **kwargs: [{"sector": "军工", "trend_count": 2}],
            build_extreme_conviction_list=lambda evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3: evaluated_stocks[:1],
        )

        self.assertEqual(result["mainline_name"], "军工")
        self.assertEqual(result["core_stocks"][0]["code"], "000001")
        self.assertEqual(result["crossline_observation_stocks"][0]["code"], "000002")
        self.assertEqual(result["gem_observation_stocks"][0]["code"], "300001")
        self.assertEqual(result["extreme_conviction_list"][0]["code"], "000001")
        self.assertTrue(any(log["step"] == "candidate_scoring" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
