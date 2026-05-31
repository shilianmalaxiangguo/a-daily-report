import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from storage.postgres_daily_fact_db import POSTGRES_SCHEMA_STATEMENTS, PostgresDailyFactDb


class _FakeCursor:
    def __init__(self):
        self.calls = []
        self.rows = []
        self.row_batches = []

    def execute(self, sql, params=None):
        self.calls.append(("execute", " ".join(str(sql).split()), params))
        return self

    def executemany(self, sql, rows):
        self.calls.append(("executemany", " ".join(str(sql).split()), list(rows or [])))
        return self

    def fetchall(self):
        if self.row_batches:
            return list(self.row_batches.pop(0))
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.commit_count = 0

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.commit_count += 1

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class PostgresDailyFactDbTest(unittest.TestCase):
    def test_schema_has_three_migration_batches_without_blob_primary_store(self):
        schema = "\n".join(POSTGRES_SCHEMA_STATEMENTS).lower()

        for table_name in (
            "market_cycle_days",
            "market_cycle_periods",
            "mainline_switch_events",
            "sector_attack_evidence_daily",
            "sector_diffusion_score_daily",
            "daily_observation_pool_items",
            "observation_pool_lifecycle",
            "leader_memory_items",
            "tracking_memory_daily_status",
            "a_kill_cooling_items",
            "extreme_conviction_cases",
            "extreme_conviction_mentions",
            "planned_participation_steps",
            "participation_reviews",
            "trend_fates",
            "cycle_acceptance_reviews",
        ):
            self.assertIn(f"create table if not exists {table_name}", schema)

        self.assertNotIn("payload_json", schema)

    def test_replaces_market_cycle_context_with_structured_rows(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        saved = db.replace_market_cycle_context(
            "2026-05-29",
            {
                "cycle_calendar_rows": [
                    {
                        "week_label": "05-25当周",
                        "monday": {"date": "05-25", "mainline": "电力", "state": "主导"},
                    }
                ],
                "cycle_interpretation_rows": [
                    {
                        "cycle_label": "当前周期",
                        "time_range": "05-25 ~ 05-29",
                        "trading_days": "5日",
                        "attack_line": "电力",
                        "cycle_stage": "主导",
                        "transfer_state": "扩散",
                        "market_state": "强化",
                        "tomorrow_validation": "看扩散",
                        "interpretation": "电力继续扩散",
                    }
                ],
                "current_mainline_history_record": {
                    "date": "2026-05-29",
                    "primary_mainline": "电力",
                    "daily_attack_line": "电力",
                    "market_state": "强化",
                },
                "recent_mainline_history": [
                    {"date": "2026-05-28", "primary_mainline": "电力", "market_state": "主导"}
                ],
                "current_sector_turnover_snapshot": {
                    "date": "2026-05-29",
                    "sector_name": "电力",
                    "sector_turnover": 320.5,
                    "total_turnover": 10500,
                    "turnover_share_pct": 3.05,
                },
                "recent_sector_turnover_history": [
                    {
                        "date": "2026-05-28",
                        "sector_name": "电力",
                        "sector_turnover": 280,
                        "total_turnover": 9800,
                        "turnover_share_pct": 2.86,
                    }
                ],
                "sector_attack_evidence_rows": [
                    {
                        "sector_name": "电力",
                        "net_inflow_rank": 1,
                        "net_inflow_amount": 18.2,
                        "limit_up_count": 4,
                        "high_anchor_height": 3,
                        "turnover_share_pct": 3.05,
                        "turnover_share_change": 0.19,
                    }
                ],
            },
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO market_cycle_days", sql)
        self.assertIn("INSERT INTO market_cycle_periods", sql)
        self.assertIn("INSERT INTO mainline_daily", sql)
        self.assertIn("INSERT INTO mainline_turnover_daily", sql)
        self.assertIn("INSERT INTO sector_attack_evidence_daily", sql)
        self.assertEqual(saved["cycle_days"], 1)
        self.assertEqual(saved["cycle_periods"], 1)
        self.assertEqual(saved["mainline_records"], 2)
        self.assertEqual(saved["turnover_records"], 2)
        self.assertEqual(saved["sector_attack_records"], 1)
        self.assertGreater(conn.commit_count, 0)

    def test_replaces_observation_pool_items_and_tracking_memory_structurally(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        pool_count = db.replace_observation_pool_items_for_trade_date(
            "2026-05-29",
            {
                "watchlist": [{"code": "600011", "name": "华能国际", "sector": "电力", "score": 81}],
                "leader_memory_bank": [
                    {
                        "code": "601991",
                        "name": "大唐发电",
                        "sector": "电力",
                        "remember_score": 92,
                        "remember_reason": "龙头记忆",
                    }
                ],
            },
        )
        memory_count = db.save_tracking_memory_state(
            {
                "updated_at": "2026-05-29",
                "items": [
                    {
                        "code": "601991",
                        "name": "大唐发电",
                        "sector": "电力",
                        "status": "validated",
                        "first_seen_date": "2026-05-25",
                        "last_seen_date": "2026-05-29",
                        "confirmations": 2,
                        "failures": 0,
                        "appearances": 3,
                        "sources": ["leader_memory", "watchlist"],
                        "last_reason": "龙头记忆",
                        "follow_state": "跌不下去",
                        "evidence_score": 6,
                    }
                ],
            }
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO daily_observation_pool_items", sql)
        self.assertIn("INSERT INTO observation_pool_lifecycle", sql)
        self.assertIn("INSERT INTO leader_memory_items", sql)
        self.assertIn("INSERT INTO tracking_memory_daily_status", sql)
        self.assertEqual(pool_count, 2)
        self.assertEqual(memory_count, 1)

    def test_replaces_decision_ledger_snapshot_with_structured_rows(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.replace_decision_ledger_snapshot(
            {
                "trade_date": "2026-05-29",
                "cases": [
                    {
                        "case_id": "2026-05-29-601991-01",
                        "stock_code": "601991",
                        "stock_name": "大唐发电",
                        "first_seen_trade_date": "2026-05-25",
                        "cycle_start_trade_date": "2026-05-25",
                        "cycle_day": 5,
                        "cycle_length_trade_days": 25,
                        "hypothesis": {"sector_candidate": "电力", "stock_setup": "趋势加速"},
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-29",
                                "rank": 1,
                                "source_section": "极度看好名单",
                                "reason": "趋势强化",
                                "planned_participation": {
                                    "participation_window": "09:50-10:10窗口",
                                    "auction": "看竞价",
                                    "first_minutes": "看承接",
                                    "board": "强封才看",
                                    "reseal": "回封再看",
                                    "missed_action": "错过不追",
                                    "cancellation": "承接失败不参与",
                                },
                            }
                        ],
                        "participation_review": {"status": "待复盘", "reason": "等次日"},
                        "trend_fate": {"status": "未完成", "reason": "仍在周期内"},
                        "cycle_acceptance": {"status": "观察", "reason": "扩散待确认"},
                    }
                ],
            }
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO extreme_conviction_cases", sql)
        self.assertIn("INSERT INTO extreme_conviction_mentions", sql)
        self.assertIn("INSERT INTO planned_participations", sql)
        self.assertIn("INSERT INTO planned_participation_steps", sql)
        self.assertIn("INSERT INTO participation_reviews", sql)
        self.assertIn("INSERT INTO trend_fates", sql)
        self.assertIn("INSERT INTO cycle_acceptance_reviews", sql)
        self.assertEqual(result["cases"], 1)
        self.assertEqual(result["mentions"], 1)

    def test_loads_tracking_memory_from_psycopg_tuple_rows(self):
        conn = _FakeConnection()
        conn.cursor_obj.rows = [
            (
                "601991",
                "大唐发电",
                "电力",
                "validated",
                "2026-05-25",
                "2026-05-29",
                2,
                0,
                3,
                "leader_memory,watchlist",
                "龙头记忆",
                "跌不下去",
                6.0,
                "",
            )
        ]
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        state = db.load_tracking_memory_state()

        self.assertEqual(state["items"][0]["code"], "601991")
        self.assertEqual(state["items"][0]["sources"], ["leader_memory", "watchlist"])
        self.assertEqual(state["items"][0]["evidence_score"], 6.0)

    def test_queries_runtime_market_series_from_structured_tables(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        conn.cursor_obj.rows = [
            (
                "2026-05-29",
                "电力",
                "电力",
                "",
                "",
                "强化",
                "电力",
                "dominant",
                0.8,
                "继续强化",
                "snapshot_index",
                12,
            ),
            (
                "2026-05-28",
                "电力",
                "电力",
                "",
                "",
                "主导",
                "电力",
                "dominant",
                0.7,
                "持续扩散",
                "snapshot_index",
                11,
            ),
        ]
        mainline_rows = db.query_mainline_daily_series("2026-05-29", window_days=2)

        conn.cursor_obj.rows = [
            ("2026-05-29", "电力", "电力", "电力", 320.5, 10500.0, 3.05, "snapshot_index", 12),
            ("2026-05-28", "电力", "电力", "电力", 280.0, 9800.0, 2.86, "snapshot_index", 11),
        ]
        turnover_rows = db.query_mainline_turnover_series("2026-05-29", "电力", window_days=2)

        conn.cursor_obj.rows = [
            ("2026-05-29", "all_a", 10500.0, 5504, "snapshot.total_turnover", 12)
        ]
        total = db.query_market_daily_total("2026-05-29")

        conn.cursor_obj.rows = [
            ("2026-05-29", "电力", -3.4),
            ("2026-05-28", "电力", 18.2),
        ]
        flow_rows = db.query_sector_fund_flow_series("2026-05-29", "电力", window_days=2)

        self.assertEqual([row["date"] for row in mainline_rows], ["2026-05-28", "2026-05-29"])
        self.assertEqual(mainline_rows[-1]["primary_mainline"], "电力")
        self.assertEqual(turnover_rows[-1]["sector_turnover"], 320.5)
        self.assertEqual(total["total_amount_yi"], 10500.0)
        self.assertEqual(flow_rows[-1]["inflow"], -3.4)

    def test_queries_extreme_conviction_mentions_from_structured_rows(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        conn.cursor_obj.rows = [("2026-05-29",), ("2026-05-28",)]

        dates = db._query_recent_extreme_conviction_dates(conn.cursor_obj, "2026-05-29", window_days=2)

        conn.cursor_obj.rows = [
            (
                "2026-05-28:601991:1",
                "2026-05-28",
                "601991",
                "大唐发电",
                1,
                "电力",
                "09:30-09:35",
                "竞价表态",
                "等待复盘",
                "看承接",
                "有效跌破日K MA20取消幻想",
                "趋势强化",
                "极度看好名单",
                False,
                "2026-05-31T00:00:00Z",
            ),
            (
                "2026-05-29:600578:1",
                "2026-05-29",
                "600578",
                "京能电力",
                1,
                "电力",
                "09:50-10:10",
                "回封参与",
                "等待复盘",
                "看回封",
                "有效跌破日K MA20取消幻想",
                "板块扩散",
                "极度看好名单",
                True,
                "2026-05-31T00:00:00Z",
            ),
        ]
        rows = db.query_extreme_conviction_mentions("2026-05-29", window_days=2, include_a_kill=True)

        self.assertEqual(dates, ["2026-05-28", "2026-05-29"])
        self.assertEqual([row["stock_code"] for row in rows], ["601991", "600578"])
        self.assertTrue(rows[-1]["is_a_kill_eliminated"])
        self.assertEqual(rows[0]["payload"]["stock_code"], "601991")

    def test_reads_decision_ledger_index_from_structured_rows(self):
        conn = _FakeConnection()
        conn.cursor_obj.row_batches = [
            [("2026-05-29",)],
            [
                (
                    "case-601991",
                    "2026-05-29",
                    "601991",
                    "大唐发电",
                    "2026-05-25",
                    "2026-05-25",
                    5,
                    25,
                    "电力",
                    "趋势强化",
                )
            ],
            [
                (
                    "2026-05-29:601991:1",
                    "case-601991",
                    "2026-05-29",
                    "601991",
                    "大唐发电",
                    1,
                    "电力",
                    "09:30-09:35",
                    "竞价表态",
                    "等待复盘",
                    "看承接",
                    "有效跌破日K MA20取消幻想",
                    "趋势强化",
                    "极度看好名单",
                    False,
                )
            ],
            [
                (
                    "case-601991",
                    "电力",
                    "趋势强化",
                    "电力主攻",
                    "板块扩散",
                )
            ],
            [
                (
                    "2026-05-29:601991:1",
                    "case-601991",
                    "竞价表态",
                    "50%",
                    "extreme_conviction",
                    "开盘确认",
                    "09:30-09:35",
                    "错过不追",
                    "承接失败不参与",
                )
            ],
            [
                ("2026-05-29:601991:1", "auction", "看竞价"),
                ("2026-05-29:601991:1", "first_minutes", "看承接"),
            ],
            [
                (
                    "case-601991",
                    "case-601991",
                    "2026-05-30",
                    "等待复盘",
                    "等次日窗口",
                    "还缺分钟事实",
                    "继续观察",
                )
            ],
            [("case-601991", "观察", "还在周期内", "扩散未结束")],
            [("case-601991", "open", "周期未闭合", "继续观察")],
        ]
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        index = db.read_decision_ledger_index(end_date="2026-05-29", window_days=25)

        record = index["by_stock_code"]["601991"][0]
        self.assertEqual(index["latest_trade_date"], "2026-05-29")
        self.assertEqual(record["case_id"], "case-601991")
        self.assertEqual(record["hypothesis"]["sector_candidate"], "电力")
        self.assertEqual(record["planned_participation"]["auction"], "看竞价")
        self.assertEqual(record["participation_review"]["status"], "等待复盘")
        self.assertEqual(record["mentions"][0]["source_section"], "极度看好名单")


if __name__ == "__main__":
    unittest.main()
