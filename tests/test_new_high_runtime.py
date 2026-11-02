import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class NewHighRuntimeTest(unittest.TestCase):
    def test_reconcile_new_high_feedback_identity_uses_only_target_date_facts(self):
        from domains.market_activity.new_high_runtime import reconcile_new_high_feedback_identity

        feedback = {
            "available": True,
            "source": "storage.stock_daily_quotes_recent.high_break",
            "new_high_count": 2,
            "all_a_share_pct": 0.04,
            "leading_sectors": "待补充板块",
            "sector_distribution": [{"sector": "待补充板块", "new_high_count": 2}],
            "top_stocks": [
                {"code": "600664", "name": "600664", "sector": "待补充板块", "amount_yi": 51.91},
                {"code": "001258", "name": "001258", "sector": "待补充板块", "amount_yi": 32.45},
            ],
            "trend_rows": [
                {"trade_date": "2026-08-12", "new_high_count": 2, "leading_sectors": "待补充板块"},
            ],
        }

        patched, identity = reconcile_new_high_feedback_identity(
            feedback,
            {
                "600664": {
                    "name": "哈药股份",
                    "industry": "化学制药",
                    "trade_date": "2026-08-12",
                },
                "001258": {
                    "name": "立新能源",
                    "industry": "新型电力",
                    "trade_date": "2026-08-13",
                },
            },
            target_date="2026-08-12",
        )

        self.assertFalse(identity["complete"])
        self.assertEqual(patched["top_stocks"][0]["name"], "哈药股份")
        self.assertEqual(patched["top_stocks"][0]["sector"], "化学制药")
        self.assertEqual(patched["top_stocks"][1]["name"], "001258")
        self.assertEqual(identity["issues"][0]["code"], "001258")

    def test_reconcile_new_high_feedback_identity_rebuilds_t019_aggregates(self):
        from domains.market_activity.new_high_runtime import reconcile_new_high_feedback_identity

        feedback = {
            "available": True,
            "source": "storage.stock_daily_quotes_recent.high_break",
            "new_high_count": 2,
            "all_a_share_pct": 0.04,
            "leading_sectors": "待补充板块",
            "sector_distribution": [{"sector": "待补充板块", "new_high_count": 2}],
            "top_stocks": [
                {"code": "600664", "name": "600664", "sector": "待补充板块", "amount_yi": 51.91},
                {"code": "001258", "name": "001258", "sector": "待补充板块", "amount_yi": 32.45},
            ],
            "trend_rows": [
                {"trade_date": "2026-08-12", "new_high_count": 2, "leading_sectors": "待补充板块"},
            ],
        }
        stock_info = {
            "600664": {"name": "哈药股份", "industry": "化学制药", "trade_date": "2026-08-12"},
            "001258": {"name": "立新能源", "industry": "新型电力", "trade_date": "2026-08-12"},
        }

        patched, identity = reconcile_new_high_feedback_identity(
            feedback,
            stock_info,
            target_date="2026-08-12",
        )

        self.assertTrue(identity["complete"])
        self.assertEqual([row["name"] for row in patched["top_stocks"]], ["哈药股份", "立新能源"])
        self.assertEqual([row["sector"] for row in patched["sector_distribution"]], ["化学制药", "新型电力"])
        self.assertEqual(patched["leading_sectors"], "化学制药、新型电力")
        self.assertEqual(patched["trend_rows"][-1]["leading_sectors"], "化学制药、新型电力")

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

    def test_build_new_high_feedback_snapshot_normalizes_missing_history_sectors(self):
        from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot

        snapshot = build_new_high_feedback_snapshot(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260813",
                    "pct_chg": 5.2,
                    "amount": 2500000,
                    "topdays": 260,
                }
            ],
            stock_basic_map={"000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"}},
            target_date="2026-08-13",
            history_rows=[
                {
                    "trade_date": "2026-08-11",
                    "new_high_count": 2,
                    "all_a_share_pct": 0.04,
                    "leading_sectors": "待补充板块",
                },
                {
                    "trade_date": "2026-08-12",
                    "new_high_count": 0,
                    "all_a_share_pct": 0.0,
                    "leading_sectors": "待补充板块",
                },
            ],
        )

        self.assertEqual(snapshot["trend_rows"][0]["leading_sectors"], "缺少逐股板块映射")
        self.assertEqual(snapshot["trend_rows"][1]["leading_sectors"], "无阶段新高")
        self.assertNotIn("待补充板块", str(snapshot["trend_rows"]))

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

    def test_build_new_high_feedback_snapshot_rejects_explicit_new_stock_and_short_unproven_history(self):
        from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot

        snapshot = build_new_high_feedback_snapshot(
            [
                {
                    "stock_code": "301677",
                    "trade_date": "20260731",
                    "name": "C欣兴",
                    "industry": float("nan"),
                    "topdays": 250,
                    "history_trade_days": 1,
                },
                {
                    "stock_code": "300001",
                    "trade_date": "20260731",
                    "name": "短历史样本",
                    "industry": "机械基件",
                    "topdays": 250,
                    "history_trade_days": 2,
                },
                {
                    "stock_code": "000001",
                    "trade_date": "20260731",
                    "name": "长期样本",
                    "industry": "银行",
                    "topdays": 250,
                    "history_trade_days": 249,
                },
            ],
            stock_basic_map={
                "301677": {"name": "C欣兴", "industry": float("nan"), "list_date": "19700101"},
                "300001": {"name": "短历史样本", "industry": "机械基件", "list_date": "nan"},
                "000001": {"name": "长期样本", "industry": "银行", "list_date": "<NA>"},
            },
            target_date="2026-07-31",
        )

        self.assertEqual(snapshot["new_high_count"], 1)
        self.assertEqual([row["code"] for row in snapshot["top_stocks"]], ["000001"])
        self.assertEqual(snapshot["excluded_counts"]["new_or_recent"], 1)
        self.assertEqual(snapshot["excluded_counts"]["insufficient_stock_history"], 1)
        self.assertNotIn("nan", snapshot["leading_sectors"].lower())


if __name__ == "__main__":
    unittest.main()
