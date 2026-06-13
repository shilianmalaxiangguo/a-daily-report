import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class _MemoryFactStore:
    def __init__(self):
        self.market_totals = {}
        self.sector_flows = {}
        self.mainlines = {}
        self.mainline_turnovers = {}
        self.new_high_feedback = {}

    @staticmethod
    def _row_date(row):
        return str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip()

    @staticmethod
    def _recent_rows(rows, end_date, window_days):
        end_text = str(end_date or "").strip()
        filtered = [dict(row) for row in rows if _MemoryFactStore._row_date(row) <= end_text]
        filtered.sort(key=_MemoryFactStore._row_date)
        return filtered[-int(window_days or 25) :]

    def is_postgres_backed(self):
        return True

    def upsert_market_daily_total(self, row):
        trade_date = self._row_date(row)
        if trade_date:
            self.market_totals[trade_date] = dict(row or {})
        return 1 if trade_date else 0

    def query_market_daily_total(self, trade_date, *, market_scope="all_a"):
        return dict(self.market_totals.get(str(trade_date or "").strip()) or {})

    def upsert_sector_fund_flow_daily(self, row):
        trade_date = self._row_date(row)
        sector_name = str((row or {}).get("sector_name") or "").strip()
        if not trade_date or not sector_name:
            return 0
        stored = dict(row or {})
        stored.setdefault("inflow", stored.get("net_inflow_yi"))
        self.sector_flows[(trade_date, sector_name)] = stored
        return 1

    def query_sector_fund_flow_series(self, end_date, sector_name, *, window_days=8):
        sector_text = str(sector_name or "").strip()
        return self._recent_rows(
            [row for (trade_date, name), row in self.sector_flows.items() if name == sector_text],
            end_date,
            window_days,
        )

    def upsert_mainline_daily(self, row):
        trade_date = self._row_date(row)
        if trade_date:
            stored = dict(row or {})
            stored.setdefault("date", trade_date)
            self.mainlines[trade_date] = stored
        return 1 if trade_date else 0

    def query_mainline_daily_series(self, end_date, *, window_days=25):
        return self._recent_rows(self.mainlines.values(), end_date, window_days)

    def upsert_mainline_turnover_daily(self, row):
        trade_date = self._row_date(row)
        sector_name = str(
            (row or {}).get("sector_name")
            or (row or {}).get("primary_mainline")
            or (row or {}).get("cycle_mainline")
            or ""
        ).strip()
        if not trade_date or not sector_name:
            return 0
        stored = dict(row or {})
        stored.setdefault("date", trade_date)
        stored.setdefault("sector_name", sector_name)
        self.mainline_turnovers[(trade_date, sector_name)] = stored
        return 1

    def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
        sector_text = str(sector_name or "").strip()
        return self._recent_rows(
            [row for (trade_date, name), row in self.mainline_turnovers.items() if name == sector_text],
            end_date,
            window_days,
        )

    def upsert_new_high_feedback_daily(self, row):
        trade_date = self._row_date(row)
        if trade_date:
            stored = dict(row or {})
            stored.setdefault("trade_date", trade_date)
            self.new_high_feedback[trade_date] = stored
        return 1 if trade_date else 0

    def query_new_high_feedback_series(self, end_date, *, window_days=25):
        return self._recent_rows(self.new_high_feedback.values(), end_date, window_days)


def _memory_fact_store_factory(service=None):
    class MemoryFactStoreFactory:
        fact_store = service or _MemoryFactStore()
        calls = []

        @classmethod
        def fact_store_from_environment(cls, db_path=None):
            cls.calls.append(db_path)
            return cls.fact_store

    return MemoryFactStoreFactory


class DailyMetricHistoryIndexTest(unittest.TestCase):
    def test_replay_snapshot_loader_blocks_postgres_only_json_read(self):
        from domains.market_state import daily_metric_history_index as index

        with patch.dict(os.environ, {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}):
            with self.assertRaisesRegex(RuntimeError, "2026-05-29"):
                index._load_replay_snapshot_data("2026-05-29")

    def test_ensure_daily_metric_history_index_rebuilds_t25_metrics_from_snapshots(self):
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index

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
            db_path = Path(tmp) / "fact-store"
            factory = _memory_fact_store_factory()
            result = ensure_daily_metric_history_index(
                end_date="2026-05-20",
                window_days=2,
                max_scan_days=2,
                db_path=db_path,
                database_service_cls=factory,
                load_snapshot_fn=lambda target_date: snapshots.get(target_date, (None, None)),
            )
            service = factory.fact_store

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
            db_path = Path(tmp) / "fact-store"
            factory = _memory_fact_store_factory()
            result = ensure_daily_metric_history_index(
                end_date="2026-05-19",
                window_days=1,
                max_scan_days=1,
                db_path=db_path,
                database_service_cls=factory,
                load_snapshot_fn=lambda target_date: ({"new_high_feedback": {"available": False}}, ""),
                load_report_markdown_fn=lambda target_date: markdowns.get(target_date, ""),
            )
            service = factory.fact_store
            new_high_rows = service.query_new_high_feedback_series("2026-05-19", window_days=1)

        self.assertEqual(result["indexed_count"], 1)
        self.assertEqual(new_high_rows[0]["trade_date"], "2026-05-19")
        self.assertEqual(new_high_rows[0]["new_high_count"], 164)
        self.assertEqual(new_high_rows[0]["all_a_share_pct"], 3.28)
        self.assertEqual(new_high_rows[0]["leading_sectors"], "半导体、元器件、专用机械")

    def test_ensure_daily_metric_history_index_keeps_existing_new_high_fact_row(self):
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fact-store"
            service = _MemoryFactStore()
            factory = _memory_fact_store_factory(service)
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
                database_service_cls=factory,
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

        snapshot = {
            "total_turnover": 29246.59,
            "market_stats": {"up_count": 3869, "down_count": 1509},
            "sector_fund_flow": {
                "inflow": [{"name": "半导体", "zljlr": 12.34}],
                "outflow": [{"name": "元器件", "zljlr": -5.67}],
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fact-store"
            factory = _memory_fact_store_factory()
            result = ensure_daily_metric_history_index(
                end_date="2026-05-22",
                window_days=1,
                max_scan_days=1,
                db_path=db_path,
                database_service_cls=factory,
                load_snapshot_fn=lambda target_date: (snapshot, ""),
                load_replay_snapshot_fn=lambda target_date: None,
                load_report_markdown_fn=lambda target_date: "",
            )
            service = factory.fact_store
            market_total = service.query_market_daily_total("2026-05-22")
            semiconductor_rows = service.query_sector_fund_flow_series("2026-05-22", "半导体", window_days=1)
            component_rows = service.query_sector_fund_flow_series("2026-05-22", "元器件", window_days=1)

        self.assertEqual(result["indexed_count"], 1)
        self.assertEqual(market_total["total_amount_yi"], 29246.59)
        self.assertEqual(market_total["stock_count"], 5378)
        self.assertEqual(semiconductor_rows[0]["inflow"], 12.34)
        self.assertEqual(component_rows[0]["inflow"], -5.67)

    def test_ensure_daily_metric_history_index_default_loader_uses_compact_snapshot(self):
        from domains.market_state import daily_metric_history_index as index
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index

        compact_snapshot = {
            "total_turnover": 29246.59,
            "market_stats": {"up_count": 3869, "down_count": 1509},
            "sector_fund_flow": {
                "inflow": [{"name": "半导体", "zljlr": 12.34}],
                "outflow": [],
            },
            "current_mainline_history_record": {
                "date": "2026-05-22",
                "primary_mainline": "半导体",
                "leading_line": "半导体",
            },
            "current_sector_turnover_snapshot": {
                "date": "2026-05-22",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29246.59,
                "turnover_share_pct": 13.85,
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fact-store"
            factory = _memory_fact_store_factory()
            with patch.object(
                index,
                "load_data_snapshot",
                side_effect=AssertionError("default index rebuild must not parse full snapshot"),
            ), patch.object(
                index,
                "_load_replay_snapshot_data",
                side_effect=AssertionError("default index rebuild must not parse full replay snapshot"),
            ), patch.object(
                index,
                "_load_compact_replay_metric_snapshot",
                return_value=None,
            ), patch.object(
                index,
                "_load_compact_metric_history_snapshot",
                return_value=(compact_snapshot, ""),
            ) as compact_loader:
                result = ensure_daily_metric_history_index(
                    end_date="2026-05-22",
                    window_days=1,
                    max_scan_days=1,
                    db_path=db_path,
                    database_service_cls=factory,
                )
            service = factory.fact_store
            market_total = service.query_market_daily_total("2026-05-22")
            turnover_rows = service.query_mainline_turnover_series("2026-05-22", "半导体", window_days=1)

        compact_loader.assert_called_once_with("2026-05-22")
        self.assertEqual(result["indexed_count"], 1)
        self.assertEqual(market_total["total_amount_yi"], 29246.59)
        self.assertEqual(turnover_rows[0]["sector_turnover"], 4050.0)

    def test_ensure_daily_metric_history_index_reuses_default_rebuild_window(self):
        from domains.market_state import daily_metric_history_index as index
        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index

        snapshot = {
            "current_sector_turnover_snapshot": {
                "date": "2026-05-22",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29246.59,
                "turnover_share_pct": 13.85,
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fact-store"
            factory = _memory_fact_store_factory()
            with patch.object(index, "_DEFAULT_REBUILD_WINDOW_CACHE", {}), patch.object(
                index,
                "_load_compact_metric_history_snapshot",
                return_value=(snapshot, ""),
            ) as compact_loader, patch.object(
                index,
                "_load_compact_replay_metric_snapshot",
                return_value=None,
            ):
                first = ensure_daily_metric_history_index(
                    end_date="2026-05-22",
                    window_days=1,
                    max_scan_days=1,
                    db_path=db_path,
                    database_service_cls=factory,
                )
                second = ensure_daily_metric_history_index(
                    end_date="2026-05-22",
                    window_days=1,
                    max_scan_days=1,
                    db_path=db_path,
                    database_service_cls=factory,
                )

        self.assertEqual(first, second)
        compact_loader.assert_called_once_with("2026-05-22")


if __name__ == "__main__":
    unittest.main()
