import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DailyMetricHistoryIndexTest(unittest.TestCase):
    def test_ensure_daily_metric_history_index_rebuilds_t25_metrics_from_snapshots(self):
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index
        from storage.database_service import DatabaseService

        snapshots = {
            "2026-05-20": (
                {
                    "recent_mainline_history": [
                        {
                            "date": "2026-05-18",
                            "primary_mainline": "电力",
                            "leading_line": "电力",
                            "source": "snapshot_index",
                        },
                        {
                            "date": "2026-05-19",
                            "primary_mainline": "电力",
                            "leading_line": "电力",
                            "source": "snapshot_index",
                        },
                    ],
                    "current_mainline_history_record": {
                        "date": "2026-05-20",
                        "primary_mainline": "半导体",
                        "leading_line": "半导体",
                        "source": "market_research_snapshot",
                    },
                    "current_sector_turnover_snapshot": {
                        "date": "2026-05-20",
                        "sector_name": "半导体",
                        "sector_turnover": 4050.0,
                        "total_turnover": 29764.59,
                        "turnover_share_pct": 13.61,
                        "matched_sector_names": ["半导体"],
                        "source": "tushare.moneyflow_ind_ths",
                    },
                    "new_high_feedback": {
                        "available": True,
                        "new_high_count": 126,
                        "all_a_share_pct": 2.52,
                        "leading_sectors": "半导体、机器人",
                        "source": "tushare.stk_factor_pro.topdays",
                    },
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-05-18",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "3900.00亿",
                                "market_turnover": "29170.74亿",
                                "share": "13.4%",
                                "interpretation": "Tushare行业资金流入+流出口径",
                            },
                            {
                                "date": "2026-05-20",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "4050.00亿",
                                "market_turnover": "29764.59亿",
                                "share": "13.6%",
                                "interpretation": "Tushare行业资金流入+流出口径",
                            },
                        ]
                    },
                },
                "",
            ),
            "2026-05-19": (
                {
                    "current_mainline_history_record": {
                        "date": "2026-05-19",
                        "primary_mainline": "电力",
                        "leading_line": "电力",
                    },
                    "current_sector_turnover_snapshot": {
                        "date": "2026-05-19",
                        "sector_name": "电力",
                        "sector_turnover": 1000.0,
                        "total_turnover": 29089.77,
                        "turnover_share_pct": 3.44,
                    },
                },
                "",
            ),
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "daily.db"
            result = ensure_daily_metric_history_index(
                end_date="2026-05-20",
                window_days=2,
                max_scan_days=2,
                db_path=db_path,
                load_snapshot_fn=lambda target_date: snapshots.get(target_date, (None, None)),
            )
            service = DatabaseService.sqlite_d1_compatible(db_path)

            mainline_rows = service.query_mainline_daily_series("2026-05-20", window_days=3)
            turnover_rows = service.query_mainline_turnover_series("2026-05-20", "半导体", window_days=2)
            new_high_rows = service.query_new_high_feedback_series("2026-05-20", window_days=2)

        self.assertEqual(result["indexed_count"], 2)
        self.assertEqual([row["date"] for row in mainline_rows], ["2026-05-18", "2026-05-19", "2026-05-20"])
        self.assertEqual(mainline_rows[0]["primary_mainline"], "电力")
        self.assertEqual(mainline_rows[-1]["primary_mainline"], "半导体")
        self.assertEqual([row["date"] for row in turnover_rows], ["2026-05-18", "2026-05-20"])
        self.assertEqual(turnover_rows[-1]["sector_turnover"], 4050.0)
        self.assertEqual(new_high_rows[-1]["new_high_count"], 126)

    def test_ensure_daily_metric_history_index_backfills_new_high_from_report_markdown(self):
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index
        from storage.database_service import DatabaseService

        markdowns = {
            "2026-05-19": """
### 3. 创新高趋势反馈
> 今日非ST非新股非次新阶段新高 164 只，占全A约 3.28%，主要集中在 半导体、元器件、专用机械。

| 日期 | 新高数 | 全A占比 | 较前日 | 主导板块 |
|------|--------|---------|--------|----------|
| 2026-05-19 | 164 | 3.28% | 待累计 | 半导体、元器件、专用机械 |
""",
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "daily.db"
            result = ensure_daily_metric_history_index(
                end_date="2026-05-19",
                window_days=1,
                max_scan_days=1,
                db_path=db_path,
                load_snapshot_fn=lambda target_date: ({"new_high_feedback": {"available": False}}, ""),
                load_report_markdown_fn=lambda target_date: markdowns.get(target_date, ""),
            )
            service = DatabaseService.sqlite_d1_compatible(db_path)
            new_high_rows = service.query_new_high_feedback_series("2026-05-19", window_days=1)

        self.assertEqual(result["indexed_count"], 1)
        self.assertEqual(new_high_rows[0]["trade_date"], "2026-05-19")
        self.assertEqual(new_high_rows[0]["new_high_count"], 164)
        self.assertEqual(new_high_rows[0]["all_a_share_pct"], 3.28)
        self.assertEqual(new_high_rows[0]["leading_sectors"], "半导体、元器件、专用机械")

    def test_ensure_daily_metric_history_index_keeps_existing_new_high_fact_row(self):
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index
        from storage.database_service import DatabaseService

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "daily.db"
            service = DatabaseService.sqlite_d1_compatible(db_path)
            service.upsert_new_high_feedback_daily(
                {
                    "trade_date": "2026-05-20",
                    "new_high_count": 169,
                    "all_a_share_pct": 3.38,
                    "leading_sectors": "半导体、元器件、专用机械",
                    "source": "tushare.stk_factor_pro.topdays",
                }
            )

            ensure_daily_metric_history_index(
                end_date="2026-05-20",
                window_days=1,
                max_scan_days=1,
                db_path=db_path,
                load_snapshot_fn=lambda target_date: (
                    {
                        "new_high_feedback": {
                            "available": True,
                            "new_high_count": 286,
                            "all_a_share_pct": 5.2,
                            "leading_sectors": "待补充板块",
                            "source": "report_markdown.new_high_feedback",
                        }
                    },
                    "",
                ),
            )
            new_high_rows = service.query_new_high_feedback_series("2026-05-20", window_days=1)

        self.assertEqual(new_high_rows[0]["new_high_count"], 169)
        self.assertEqual(new_high_rows[0]["all_a_share_pct"], 3.38)
        self.assertEqual(new_high_rows[0]["leading_sectors"], "半导体、元器件、专用机械")

    def test_ensure_daily_metric_history_index_writes_market_total_and_sector_fund_flow(self):
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index
        from storage.database_service import DatabaseService

        snapshot = {
            "total_turnover": 29246.59,
            "market_stats": {"up_count": 3869, "down_count": 1509},
            "sector_fund_flow": {
                "inflow": [{"name": "半导体", "zljlr": 12.34}],
                "outflow": [{"name": "元器件", "zljlr": -5.67}],
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "daily.db"
            result = ensure_daily_metric_history_index(
                end_date="2026-05-22",
                window_days=1,
                max_scan_days=1,
                db_path=db_path,
                load_snapshot_fn=lambda target_date: (snapshot, ""),
                load_replay_snapshot_fn=lambda target_date: None,
                load_report_markdown_fn=lambda target_date: "",
            )
            service = DatabaseService.sqlite_d1_compatible(db_path)
            market_total = service.query_market_daily_total("2026-05-22")
            semiconductor_rows = service.query_sector_fund_flow_series("2026-05-22", "半导体", window_days=1)
            component_rows = service.query_sector_fund_flow_series("2026-05-22", "元器件", window_days=1)

        self.assertEqual(result["indexed_count"], 1)
        self.assertEqual(market_total["total_amount_yi"], 29246.59)
        self.assertEqual(market_total["stock_count"], 5378)
        self.assertEqual(semiconductor_rows[0]["inflow"], 12.34)
        self.assertEqual(component_rows[0]["inflow"], -5.67)


if __name__ == "__main__":
    unittest.main()
