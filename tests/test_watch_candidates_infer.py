import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.watch_candidates import infer as watch_candidates_infer
from domains.watch_candidates.infer import build_watch_candidate_pool_bundle


class WatchCandidatesInferTest(unittest.TestCase):
    def test_build_watch_candidate_pool_bundle_collects_multi_source_candidates(self):
        emitted = []
        result = build_watch_candidate_pool_bundle(
            {
                "zt_pool": [
                    {"代码": "000001", "名称": "军工一号", "成交额": 230000000, "所属行业": "军工"},
                ],
                "turnover_rank": [
                    {"code": "000002", "name": "成交额二号", "turnover": 123.4},
                    {"code": "000006", "name": "热榜六号", "turnover": 88.8},
                ],
                "lianban_data": [
                    {"code": "000003", "name": "连板三号", "turnover": 45.6, "sector": "军工"},
                ],
                "hot_rank_top30": [
                    {"code": "000006", "name": "热榜六号", "sector": "AI"},
                ],
                "lhb_net_buy_top10": [
                    {"code": "000005", "name": "龙虎榜五号", "sector": "金融"},
                ],
            },
            emit=emitted.append,
        )

        candidates = result["results"]["candidates"]
        codes = [item["code"] for item in candidates]
        self.assertEqual(codes, ["000001", "000002", "000006", "000003"])
        self.assertEqual(candidates[0]["turnover"], 2.3)
        self.assertEqual(next(item for item in candidates if item["code"] == "000006")["turnover"], 88.8)
        self.assertEqual(result["results"]["added_count"]["zt"], 1)
        self.assertEqual(result["results"]["added_count"]["tr"], 2)
        self.assertEqual(result["results"]["added_count"]["lb"], 1)
        self.assertEqual(result["results"]["added_count"]["hot"], 0)
        self.assertEqual(result["results"]["added_count"]["lhb"], 0)
        self.assertTrue(any("候选池" in line for line in emitted))
        self.assertTrue(any(log["step"] == "infer.watch_candidate_pool" for log in result["module_logs"]))

    def test_build_abnormal_watch_pool_returns_degraded_snapshot_when_recent_bars_missing(self):
        builder = getattr(watch_candidates_infer, "build_abnormal_watch_pool", None)
        self.assertIsNotNone(builder)

        result = builder(
            "2026-04-22",
            [
                {
                    "code": "sz000001",
                    "name": "军工一号",
                    "sector": "军工",
                    "tomorrow_strength": 82,
                    "close": 12.34,
                    "source": "热榜",
                }
            ],
            mainline_name="军工",
            allow_degraded_snapshot=True,
            helpers={
                "normalize_stock_code": lambda code: str(code or "").replace("sz", "").replace("sh", ""),
                "fetch_recent_price_bars": lambda *args, **kwargs: [{"date": "2026-04-22"}] * 3,
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "_resolve_abnormal_setup_signal": lambda abnormal_type, follow_state: {
                    "id": "burst_hold",
                    "label": f"{abnormal_type}-{follow_state}",
                    "phase": "观察池",
                },
            },
        )

        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item["code"], "000001")
        self.assertEqual(item["follow_state"], "跌不下去")
        self.assertEqual(item["setup_signal_id"], "burst_hold")
        self.assertEqual(item["anchor_price"], 12.34)
        self.assertEqual(item["abnormal_score"], 64)
        self.assertTrue(item["is_mainline"])
        self.assertTrue(item["is_degraded_snapshot"])
        self.assertFalse(item["formal_decision_eligible"])


if __name__ == "__main__":
    unittest.main()
