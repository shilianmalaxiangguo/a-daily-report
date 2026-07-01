import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class NewHighRuntimeTest(unittest.TestCase):
    def test_build_new_high_feedback_snapshot_filters_and_aggregates_sectors(self):
        from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot

        snapshot = build_new_high_feedback_snapshot(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260518",
                    "close": 12.3,
                    "high": 12.8,
                    "pct_chg": 5.2,
                    "amount": 2500000,
                    "topdays": 260,
                },
                {
                    "ts_code": "000002.SZ",
                    "trade_date": "20260518",
                    "close": 21.0,
                    "high": 21.5,
                    "pct_chg": 3.1,
                    "amount": 1100000,
                    "topdays": 250,
                },
                {"ts_code": "000003.SZ", "trade_date": "20260518", "topdays": 249, "amount": 900000},
                {"ts_code": "000004.SZ", "trade_date": "20260518", "name": "ST样本", "topdays": 270, "amount": 800000},
                {"ts_code": "000005.SZ", "trade_date": "20260518", "topdays": 300, "amount": 700000},
                {"ts_code": "000006.SZ", "trade_date": "20260518", "topdays": 280, "amount": 600000},
            ],
            stock_basic_map={
                "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
                "000002": {"name": "趋势二号", "industry": "机器人", "list_date": "20200102"},
                "000003": {"name": "未新高", "industry": "通信设备", "list_date": "20200102"},
                "000004": {"name": "ST样本", "industry": "环保", "list_date": "20200102"},
                "000005": {"name": "次新样本", "industry": "军工", "list_date": "20260110"},
                "000006": {"name": "风险样本", "industry": "电力设备", "list_date": "20200102"},
            },
            stock_risk_map={"000006": {"risk_flags": ["st_warning"]}},
            target_date="2026-05-18",
            all_a_denominator=5000,
        )

        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["new_high_count"], 2)
        self.assertAlmostEqual(snapshot["all_a_share_pct"], 0.04)
        self.assertEqual(snapshot["excluded_counts"]["below_topdays_threshold"], 1)
        self.assertEqual(snapshot["excluded_counts"]["st_or_risk"], 2)
        self.assertEqual(snapshot["excluded_counts"]["new_or_recent"], 1)
        self.assertEqual([row["sector"] for row in snapshot["sector_distribution"]], ["半导体", "机器人"])
        self.assertEqual(snapshot["sector_distribution"][0]["new_high_count"], 1)
        self.assertEqual(snapshot["sector_distribution"][0]["representative_stocks"], ["趋势一号"])
        self.assertEqual([row["code"] for row in snapshot["top_stocks"]], ["000001", "000002"])
        self.assertIn("半导体、机器人", snapshot["summary"])
        self.assertEqual(snapshot["trend_rows"][-1]["new_high_count"], 2)
        self.assertEqual(snapshot["trend_rows"][-1]["change_text"], "待累计")

    def test_build_new_high_feedback_snapshot_marks_empty_factor_rows_upstream_empty(self):
        from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot

        snapshot = build_new_high_feedback_snapshot([], target_date="2026-05-18")

        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["status"], "upstream_empty")
        self.assertIn("stk_factor_pro 当前未返回 2026-05-18", snapshot["message"])

    def test_build_new_high_feedback_snapshot_keeps_recent_25_trend_rows(self):
        from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot

        history_rows = [
            {
                "trade_date": f"2026-04-{day:02d}",
                "new_high_count": 80 + index,
                "all_a_share_pct": 1.6 + index * 0.02,
                "leading_sectors": "电力",
            }
            for index, day in enumerate(range(1, 25))
        ]

        snapshot = build_new_high_feedback_snapshot(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260520",
                    "pct_chg": 5.2,
                    "amount": 2500000,
                    "topdays": 260,
                }
            ],
            stock_basic_map={"000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"}},
            target_date="2026-05-20",
            all_a_denominator=5000,
            history_rows=history_rows,
        )

        self.assertEqual(len(snapshot["trend_rows"]), 25)
        self.assertEqual(snapshot["trend_rows"][0]["trade_date"], "2026-04-01")
        self.assertEqual(snapshot["trend_rows"][-1]["trade_date"], "2026-05-20")

    def test_build_new_high_feedback_snapshot_enriches_sector_and_amount_from_quote_rows(self):
        from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot

        snapshot = build_new_high_feedback_snapshot(
            [
                {
                    "stock_code": "300706",
                    "trade_date": "20260629",
                    "name": "阿石创",
                    "pct_chg": 19.06,
                    "topdays": 250,
                },
                {
                    "stock_code": "300346",
                    "trade_date": "20260629",
                    "name": "南大光电",
                    "pct_chg": 15.21,
                    "topdays": 250,
                },
            ],
            stock_basic_map={
                "300706": {"name": "阿石创", "list_date": "20200102"},
                "300346": {"name": "南大光电", "list_date": "20200102"},
            },
            quote_rows=[
                {"code": "300706", "sector": "半导体", "turnover": 36.8},
                {"stock_code": "300346", "所属行业": "电子化学品", "amount_yi": 55.4},
            ],
            target_date="2026-06-29",
        )

        self.assertEqual(snapshot["leading_sectors"], "电子化学品、半导体")
        self.assertNotEqual(snapshot["sector_distribution"][0]["sector"], "待补充板块")
        by_code = {row["code"]: row for row in snapshot["top_stocks"]}
        self.assertGreater(by_code["300706"]["amount_yi"], 0)
        self.assertGreater(by_code["300346"]["amount_yi"], 0)


if __name__ == "__main__":
    unittest.main()
