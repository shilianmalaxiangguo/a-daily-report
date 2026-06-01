import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from storage.postgres_daily_fact_db import (
    POSTGRES_SCHEMA_STATEMENTS,
    PostgresDailyFactDb,
    _recent_replay_min_trade_date,
)


_RECENT_25_TRADING_DATES_THROUGH_2026_05_29 = [
    "2026-04-22",
    "2026-04-23",
    "2026-04-24",
    "2026-04-27",
    "2026-04-28",
    "2026-04-29",
    "2026-04-30",
    "2026-05-06",
    "2026-05-07",
    "2026-05-08",
    "2026-05-11",
    "2026-05-12",
    "2026-05-13",
    "2026-05-14",
    "2026-05-15",
    "2026-05-18",
    "2026-05-19",
    "2026-05-20",
    "2026-05-21",
    "2026-05-22",
    "2026-05-25",
    "2026-05-26",
    "2026-05-27",
    "2026-05-28",
    "2026-05-29",
]


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
        if self.row_batches:
            batch = self.row_batches.pop(0)
            return batch[0] if batch else None
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
            "strategy_performance_ledger",
            "strategy_performance_record_fields",
            "strategy_factor_snapshots",
            "strategy_factor_snapshot_fields",
            "strategy_factor_snapshot_pool_items",
            "candidate_trace_artifacts",
            "candidate_trace_rows",
            "candidate_trace_eliminated_groups",
            "candidate_trace_row_fields",
            "daily_report_fact_fields",
            "extreme_conviction_cases",
            "extreme_conviction_mentions",
            "planned_participation_steps",
            "participation_reviews",
            "trend_fates",
            "cycle_acceptance_reviews",
            "runtime_cache_entries",
        ):
            self.assertIn(f"create table if not exists {table_name}", schema)

        self.assertNotIn("payload_json", schema)

    def test_runtime_cache_entries_schema_has_ttl_and_namespace_key(self):
        schema = "\n".join(POSTGRES_SCHEMA_STATEMENTS).lower()

        self.assertIn("create table if not exists runtime_cache_entries", schema)
        self.assertIn("namespace text not null", schema)
        self.assertIn("cache_key text not null", schema)
        self.assertIn("expires_at timestamptz not null", schema)
        self.assertIn("primary key (namespace, cache_key, target_date)", schema)
        self.assertIn("create index if not exists idx_runtime_cache_entries_expires_at", schema)

    def test_runtime_cache_methods_round_trip_payload_and_stats(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        saved = db.set_runtime_cache_entry(
            "history_cache",
            "tushare:000001",
            "2026-05-14",
            {"data": [1.0, 2.0], "source": "tushare_full_window"},
            source="tushare_full_window",
            ttl_seconds=3600,
        )

        self.assertTrue(saved)
        self.assertEqual(conn.commit_count, 1)
        self.assertIn("insert into runtime_cache_entries", conn.cursor_obj.calls[0][1].lower())
        self.assertEqual(conn.cursor_obj.calls[0][2][0:4], ("history_cache", "tushare:000001", "2026-05-14", "tushare_full_window"))

        conn.cursor_obj.row_batches = [
            [
                {
                    "namespace": "history_cache",
                    "cache_key": "tushare:000001",
                    "target_date": "2026-05-14",
                    "payload": {"data": [1.0, 2.0]},
                    "source": "tushare_full_window",
                }
            ],
            [{"entry_count": 1}],
        ]

        entry = db.get_runtime_cache_entry("history_cache", "tushare:000001", "2026-05-14")
        stats = db.get_runtime_cache_stats("history_cache", "2026-05-14")

        self.assertEqual(entry["payload"], {"data": [1.0, 2.0]})
        self.assertEqual(entry["source"], "tushare_full_window")
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["size_mb"], 0.0)

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
                "diffusion_quality": {
                    "sectors": [
                        {
                            "sector_name": "电力",
                            "total_score": 76,
                            "level": "强扩散",
                            "conclusion": "电力扩散质量优秀",
                            "action": "围绕核心做减法",
                            "details": {
                                "core_anchor": {
                                    "score": 18,
                                    "label": "核心稳定",
                                    "detail": "锚定龙头承接稳定",
                                },
                                "turnover_share_change": {
                                    "score": 15,
                                    "label": "占比抬升",
                                    "detail": "成交占比连续抬升",
                                },
                            },
                        }
                    ]
                },
                "observation": {
                    "mainline_competition_snapshot": [
                        {
                            "role": "主攻线",
                            "sector": "电力",
                            "evidence": "趋势7只 / 强势3只 / 涨停8只",
                        },
                        {
                            "role": "竞争线",
                            "sector": "半导体",
                            "evidence": "成交占比回升",
                        },
                    ]
                },
                "turnover_quality": "做多放量",
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "双线竞争",
                        "mainline_regime": "主线+背景线",
                        "primary_line": "电力",
                        "other_lines": "半导体",
                        "confirmation_evidence": "电力成交占比连续抬升",
                        "sector_relationship_state": "电力接替半导体",
                        "mainline_process": "接替确认中",
                        "capacity_evidence": "成交额放大且主攻线占比抬升",
                    },
                    "overtake_window_summary": {
                        "window_state": "confirm_next",
                    },
                },
            },
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO market_cycle_days", sql)
        self.assertIn("INSERT INTO market_cycle_periods", sql)
        self.assertIn("INSERT INTO mainline_daily", sql)
        self.assertIn("INSERT INTO mainline_turnover_daily", sql)
        self.assertIn("INSERT INTO sector_attack_evidence_daily", sql)
        self.assertIn("sector_turnover_yi", sql)
        self.assertIn("total_turnover_yi", sql)
        self.assertIn("INSERT INTO sector_diffusion_score_daily", sql)
        self.assertIn("INSERT INTO sector_diffusion_score_components", sql)
        self.assertIn("INSERT INTO sector_competition_daily", sql)
        self.assertIn("INSERT INTO market_capacity_evolution_daily", sql)
        self.assertEqual(saved["cycle_days"], 2)
        self.assertEqual(saved["cycle_periods"], 1)
        self.assertEqual(saved["mainline_records"], 2)
        self.assertEqual(saved["turnover_records"], 2)
        self.assertEqual(saved["sector_attack_records"], 1)
        self.assertEqual(saved["sector_diffusion_records"], 1)
        self.assertEqual(saved["sector_diffusion_components"], 2)
        self.assertEqual(saved["sector_competition_records"], 2)
        self.assertEqual(saved["market_capacity_evolution_records"], 1)
        self.assertGreater(conn.commit_count, 0)

    def test_market_cycle_context_fills_target_day_from_mainline_record_when_calendar_missing(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        saved = db.replace_market_cycle_context(
            "2026-05-27",
            {
                "cycle_calendar_rows": [],
                "current_mainline_history_record": {
                    "trade_date": "2026-05-27",
                    "primary_mainline": "电力",
                    "daily_attack_line": "电力",
                    "rotation_label": "支线轮动",
                    "market_state": "支线轮动",
                    "source_policy": "market_research_snapshot",
                },
            },
        )

        inserted = next(
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO market_cycle_days" in call[1]
        )
        self.assertEqual(saved["cycle_days"], 1)
        self.assertEqual(inserted[0][0], "2026-05-27")
        self.assertEqual(inserted[0][1], "05-25当周")
        self.assertEqual(inserted[0][2], "wednesday")
        self.assertEqual(inserted[0][3], "电力")

    def test_market_cycle_context_without_attack_rows_does_not_clear_existing_attack_evidence(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        saved = db.replace_market_cycle_context(
            "2026-05-29",
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "candidate_lines": ["电力"],
                    }
                }
            },
        )

        delete_attack_calls = [
            call for call in conn.cursor_obj.calls
            if call[0] == "execute" and "DELETE FROM sector_attack_evidence_daily" in call[1]
        ]
        self.assertEqual(delete_attack_calls, [])
        self.assertEqual(saved["sector_attack_records"], 0)

    def test_import_daily_report_facts_prunes_before_recent_25_day_window(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        trend_dates = ["2026-04-21", *_RECENT_25_TRADING_DATES_THROUGH_2026_05_29]

        result = db.import_daily_report_facts(
            "2026-05-29",
            {
                "new_high_feedback": {
                    "trend_rows": [{"trade_date": trade_date} for trade_date in trend_dates],
                },
                "market_research_snapshot": {
                    "recent_mainline_history": [
                        {"trade_date": "2026-04-21", "primary_mainline": "旧主线"},
                        {"trade_date": "2026-04-22", "primary_mainline": "电力"},
                    ],
                    "current_mainline_history_record": {
                        "trade_date": "2026-05-29",
                        "primary_mainline": "电力",
                    },
                    "recent_sector_turnover_history": [
                        {
                            "trade_date": "2026-04-21",
                            "sector_name": "旧主线",
                            "sector_turnover": 100,
                            "total_turnover": 10000,
                            "turnover_share_pct": 1,
                        },
                        {
                            "trade_date": "2026-04-22",
                            "sector_name": "电力",
                            "sector_turnover": 200,
                            "total_turnover": 10000,
                            "turnover_share_pct": 2,
                        },
                    ],
                },
            },
        )

        self.assertEqual(result["structured_counts"]["recent_replay_min_trade_date"], "2026-04-22")
        mainline_batches = [
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO mainline_daily" in call[1]
        ]
        self.assertTrue(mainline_batches)
        inserted_mainline_dates = {row[0] for row in mainline_batches[0]}
        self.assertNotIn("2026-04-21", inserted_mainline_dates)
        self.assertIn("2026-04-22", inserted_mainline_dates)
        self.assertIn("2026-05-29", inserted_mainline_dates)
        self.assertTrue(
            any(
                call[0] == "execute"
                and call[1] == "DELETE FROM mainline_daily WHERE trade_date < %s"
                and call[2] == ("2026-04-22",)
                for call in conn.cursor_obj.calls
            )
        )
        self.assertTrue(
            any(
                call[0] == "execute"
                and call[1] == "DELETE FROM a_kill_cooling_items WHERE a_kill_date < %s"
                and call[2] == ("2026-04-22",)
                for call in conn.cursor_obj.calls
            )
        )
        self.assertFalse(
            any(
                call[0] == "execute"
                and call[1] == "DELETE FROM a_kill_cooling_items WHERE trade_date < %s"
                for call in conn.cursor_obj.calls
            )
        )
        self.assertFalse(
            any(
                call[0] == "execute"
                and "daily_report_snapshot_fields" in call[1]
                for call in conn.cursor_obj.calls
            )
        )
        self.assertTrue(
            any(
                call[0] == "execute"
                and "DELETE FROM extreme_conviction_hypotheses" in call[1]
                for call in conn.cursor_obj.calls
            )
        )
        self.assertTrue(
            any(
                call[0] == "execute"
                and "DELETE FROM observation_pool_lifecycle" in call[1]
                and call[2] == ("2026-04-22",)
                for call in conn.cursor_obj.calls
            )
        )

    def test_import_daily_report_facts_reports_insufficient_recent_window_without_pruning(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.import_daily_report_facts(
            "2026-05-29",
            {
                "new_high_feedback": {
                    "trend_rows": [
                        {"trade_date": "2026-05-28"},
                        {"trade_date": "2026-05-29"},
                    ],
                },
                "market_research_snapshot": {
                    "current_mainline_history_record": {
                        "trade_date": "2026-05-29",
                        "primary_mainline": "新型电力",
                    },
                },
            },
        )

        window_status = result["structured_counts"]["recent_replay_window_status"]
        self.assertEqual(window_status["status"], "insufficient")
        self.assertEqual(window_status["available_days"], 2)
        self.assertEqual(window_status["min_trade_date"], "2026-05-28")
        self.assertEqual(window_status["max_trade_date"], "2026-05-29")
        self.assertEqual(window_status["required_days"], 25)
        self.assertFalse(
            any(
                call[0] == "execute"
                and call[1] == "DELETE FROM mainline_daily WHERE trade_date < %s"
                for call in conn.cursor_obj.calls
            )
        )

    def test_recent_replay_min_trade_date_handles_cyclic_context(self):
        trend_dates = ["2026-04-21", *_RECENT_25_TRADING_DATES_THROUGH_2026_05_29]
        cyclic = {"trade_date": "2026-05-29"}
        cyclic["self"] = cyclic

        min_trade_date = _recent_replay_min_trade_date(
            "2026-05-29",
            {
                "new_high_feedback": {
                    "trend_rows": [{"trade_date": trade_date} for trade_date in trend_dates],
                },
                "calendar_events": [
                    {"date": "2026-06-06"},
                    {"date": "2026-06-07"},
                ],
                "cyclic_context": cyclic,
            },
        )

        self.assertEqual(min_trade_date, "2026-04-22")

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

    def test_replaces_remaining_primary_fact_stores_structurally(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        a_kill_count = db.replace_a_kill_cooling_records(
            [
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "a_kill_date": "2026-05-29",
                    "ban_until": "2026-06-23",
                    "reason": "日K连续破位",
                }
            ]
        )
        ledger_result = db.save_strategy_performance_ledger(
            {
                "version": "v2",
                "updated_at": "2026-05-29 15:10:00",
                "records": [
                    {
                        "report_date": "2026-05-29",
                        "action_type": "execute",
                        "stock_code": "601991",
                        "stock_name": "大唐发电",
                        "entry_range_low": 8.2,
                        "confirm_price_60m": 8.8,
                        "candidate_feedback_ready": True,
                        "factor_snapshot": {
                            "version": "v2",
                            "environment": {"score": 80, "position_level": "50%"},
                            "selection": {"participation_mode": "attack_50_ready"},
                            "core_stocks": [{"code": "601991", "name": "大唐发电", "sector": "电力"}],
                        },
                    }
                ],
            },
            mode="frozen",
        )
        snapshot_result = db.save_factor_snapshot(
            "2026-05-29",
            {"report_date": "2026-05-29", "market_branch": "电力主攻"},
            mode="frozen",
        )
        trace_result = db.replace_candidate_trace_artifact(
            {
                "artifact_version": 1,
                "trade_date": "2026-05-29",
                "visible_scope": "T0_T1_T2_T3",
                "generated_at": "2026-05-29T15:10:00+08:00",
                "source_report": {"path": "reports/2026-05-29_A股日报_完整版.md"},
                "traces": [
                    {
                        "stock_code": "601991",
                        "stock_name": "大唐发电",
                        "tier": "T0",
                        "key_inputs": [{"field": "账户适配", "value": "实际可买", "source": "account_context"}],
                        "checks": [{"label": "市场条件", "result": "满足", "evidence": "电力承接"}],
                        "branch_path": ["市场条件满足", "进入 T0 条件观察"],
                        "missing_data": [],
                        "final_action": "进入 T0 条件观察",
                    }
                ],
                "eliminated_summary": [
                    {"reason": "主线不匹配", "count": 2, "representatives": ["样本一"], "treatment": "保留观察"}
                ],
            }
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO a_kill_cooling_items", sql)
        self.assertIn("INSERT INTO strategy_performance_ledger", sql)
        self.assertIn("INSERT INTO strategy_performance_record_fields", sql)
        self.assertIn("INSERT INTO strategy_factor_snapshots", sql)
        self.assertIn("INSERT INTO strategy_factor_snapshot_fields", sql)
        self.assertIn("INSERT INTO strategy_factor_snapshot_pool_items", sql)
        self.assertIn("INSERT INTO candidate_trace_artifacts", sql)
        self.assertIn("INSERT INTO candidate_trace_rows", sql)
        self.assertIn("INSERT INTO candidate_trace_row_fields", sql)
        self.assertIn("INSERT INTO candidate_trace_eliminated_groups", sql)
        candidate_field_rows = [
            row
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO candidate_trace_row_fields" in call[1]
            for row in call[2]
        ]
        candidate_field_names = {row[2] for row in candidate_field_rows}
        self.assertIn("key_inputs[0].field", candidate_field_names)
        self.assertIn("checks[0].result", candidate_field_names)
        self.assertIn("branch_path[1]", candidate_field_names)
        self.assertEqual(a_kill_count, 1)
        self.assertEqual(ledger_result, "postgresql://strategy_performance/frozen")
        self.assertTrue(snapshot_result["saved"])
        self.assertEqual(trace_result["trace_count"], 1)

    def test_loads_structured_strategy_ledger_without_json_payload(self):
        conn = _FakeConnection()
        conn.cursor_obj.row_batches = [
            [
                (
                    "frozen",
                    "2026-05-29",
                    "execute",
                    "明天唯一能买的那只",
                    "50%",
                    "进攻",
                    "",
                    True,
                    "执行",
                    "电力",
                    "601991",
                    "大唐发电",
                    "电力",
                    "postgresql://factor-snapshots/2026-05-29",
                    "v2",
                    "2026-05-29 15:10:00",
                )
            ],
            [
                ("2026-05-29", "entry_range_low", "", 8.2, None, "number"),
                ("2026-05-29", "confirm_price_60m", "", 8.8, None, "number"),
                ("2026-05-29", "candidate_feedback_ready", "", None, True, "bool"),
            ],
            [
                ("2026-05-29", "environment.score", "", 80.0, None, "number"),
                ("2026-05-29", "environment.position_level", "50%", None, None, "text"),
                ("2026-05-29", "selection.participation_mode", "attack_50_ready", None, None, "text"),
            ],
            [
                (
                    "2026-05-29",
                    "core_stocks",
                    0,
                    "601991",
                    "大唐发电",
                    "电力",
                    "execute",
                    "attack_50_ready",
                    50,
                    "setup-a",
                    "主升",
                    "active",
                    "电力核心",
                    "执行",
                    "站上8.80",
                )
            ],
            [("frozen", "2026-05-29", "v2", "电力", "", "2026-05-29 15:10:00")],
        ]
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.load_strategy_performance_ledger(mode="frozen")

        record = result["records"][0]
        self.assertEqual(result["version"], "v2")
        self.assertEqual(record["stock_code"], "601991")
        self.assertEqual(record["entry_range_low"], 8.2)
        self.assertEqual(record["confirm_price_60m"], 8.8)
        self.assertTrue(record["candidate_feedback_ready"])
        self.assertEqual(record["factor_snapshot"]["environment"]["score"], 80)
        self.assertEqual(record["factor_snapshot"]["selection"]["participation_mode"], "attack_50_ready")
        self.assertEqual(record["factor_snapshot"]["core_stocks"][0]["stock_name"], "大唐发电")

    def test_loads_structured_candidate_trace_artifact(self):
        conn = _FakeConnection()
        conn.cursor_obj.row_batches = [
            [
                (
                    "2026-05-29",
                    1,
                    "T0_T1_T2_T3",
                    "2026-05-29T15:10:00+08:00",
                    "reports/2026-05-29_A股日报_完整版.md",
                    "replay",
                )
            ],
            [
                (
                    "601991",
                    "大唐发电",
                    "T0",
                    "电力",
                    "电力",
                    "进入 T0 条件观察",
                    "电力核心",
                    "站上8.80",
                    "跌破8.20",
                )
            ],
            [
                ("601991", "key_inputs[0].field", "账户适配", None, None, "text"),
                ("601991", "key_inputs[0].value", "实际可买", None, None, "text"),
                ("601991", "key_inputs[0].source", "account_context", None, None, "text"),
                ("601991", "checks[0].label", "市场条件", None, None, "text"),
                ("601991", "checks[0].result", "满足", None, None, "text"),
                ("601991", "checks[0].evidence", "电力承接", None, None, "text"),
                ("601991", "branch_path[0]", "市场条件满足", None, None, "text"),
                ("601991", "branch_path[1]", "进入 T0 条件观察", None, None, "text"),
                ("601991", "missing_data[0]", "account_context", None, None, "text"),
            ],
            [("主线不匹配", 2, "样本一、样本二", "保留观察")],
        ]
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.load_candidate_trace_artifact("2026-05-29")

        self.assertEqual(result["source_report"]["variant"], "replay")
        self.assertEqual(result["traces"][0]["stock_code"], "601991")
        self.assertEqual(
            result["traces"][0]["checks"],
            [{"label": "市场条件", "result": "满足", "evidence": "电力承接"}],
        )
        self.assertEqual(
            result["traces"][0]["key_inputs"],
            [{"field": "账户适配", "value": "实际可买", "source": "account_context"}],
        )
        self.assertEqual(result["traces"][0]["branch_path"], ["市场条件满足", "进入 T0 条件观察"])
        self.assertEqual(result["traces"][0]["missing_data"], ["account_context"])
        self.assertEqual(result["eliminated_summary"][0]["count"], 2)
        self.assertEqual(result["eliminated_summary"][0]["representatives"], ["样本一", "样本二"])

    def test_saves_and_loads_daily_report_fact_projection(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        saved = db.save_daily_report_snapshot(
            "2026-05-29",
            {
                "data_status": {"两市成交额": True, "中证全指": True},
                "total_turnover": 33408.58,
                "turnover_rank": [
                    {
                        "code": "601991",
                        "name": "大唐发电",
                        "amount": 12.3,
                        "raw_detail": {"skip": True},
                        "debug_payload": {"skip": True},
                    },
                ],
                "extreme_conviction_list": [
                    {
                        "code": "601991",
                        "name": "大唐发电",
                        "sector": "电力",
                        "conviction_reason": "趋势强化",
                        "recent_bars": [{"close": 1}],
                        "risk_reward_plan": "只在窗口内观察",
                    }
                ],
                "market_stats": {
                    "up_count": 1542,
                    "down_count": 3884,
                    "raw_payload": {"skip": True},
                    "cache_snapshot": {"skip": True},
                },
                "concept_fund_flow": {"rows": [{"name": "火力发电", "net_inflow": 3.2, "raw_detail": {"skip": True}}]},
                "sector_fund_flow": {
                    "inflow": [{"name": "电力", "zljlr": 18.2, "net_buy_amount": 20, "net_sell_amount": 1}],
                    "outflow": [{"name": "半导体", "zljlr": -6.5, "net_buy_amount": 1, "net_sell_amount": 7}],
                },
                "indices": {"000001.SH": {"name": "上证指数", "price": 4068.57}},
                "csi1000_index": {"name": "中证1000", "code": "000852", "price": 6123.4, "change_pct": 1.1},
                "exchange_monitor_today": [
                    {
                        "code": "000001",
                        "name": "异动一号",
                        "trigger_pct": 5.0,
                        "raw_notice": {"skip": True},
                    }
                ],
                "exchange_monitor_nextday": [
                    {
                        "code": "000002",
                        "name": "次日一号",
                        "trigger_pct": 4.0,
                        "payload": {"skip": True},
                    }
                ],
                "xuangubao_data": {"xuangubao_news": [{"title": "raw news"}], "diagnostics": {"raw": "skip"}},
                "new_high_feedback": {
                    "available": True,
                    "status": "success",
                    "new_high_count": 157,
                    "all_a_share_pct": 2.85,
                    "leading_sectors": "元器件",
                    "sector_distribution": [{"sector": "元器件", "new_high_count": 11, "representative_stocks": ["A"]}],
                    "top_stocks": [{"code": "000001", "name": "样本", "recent_bars": [{"close": 1}]}],
                    "trend_rows": [{"trade_date": "2026-05-29", "new_high_count": 157, "top_stocks": [{"code": "skip"}]}],
                },
                "margin_pressure": {
                    "status": "success",
                    "latest_pressure_label": "中性",
                    "latest_data_date": "2026-05-28",
                    "latest_margin_turnover_ratio_pct": 98.4,
                    "rows": [{"trade_date": "2026-05-28", "margin_turnover_ratio_pct": 98.4}],
                    "calibration_rows": [{"trade_date": "2025-01-01", "margin_turnover_ratio_pct": 80.0}],
                },
                "sector_quadrant": {"quadrants": {"highStrong": [{"sector": "电力", "stocks": [{"code": "raw"}]}]}},
                "sector_ai_analysis": {"sector_tree": {"电力": {"raw": "skip"}}, "sector_count": 148},
                "entry_cycle_calibration": {"cases": [{"code": "000001", "day_rows": [{"date": "raw"}]}]},
                "step_status": {"request.foo": {"status": "success"}},
                "request_diagnostics": [{"request": "foo", "payload": "skip"}],
                "module_logs": [{"step": "runtime.cache", "details": {"payload": "skip"}}],
                "appendix_b": {"rendered_tail": "skip"},
                "appendix_c": {"rendered_tail": "skip"},
                "decision_ledger_artifacts": {"index": {"by_stock_code": {"000001": [{"case_id": "skip"}]}}},
                "candidate_trace_artifact": {
                    "artifact_path": "postgresql://candidate-traces/2026-05-29",
                    "trace_count": 1,
                    "payload": {"traces": [{"stock_code": "601991", "raw": "skip"}]},
                },
                "recent_extreme_conviction_mentions": [
                    {
                        "record_id": "2026-05-12:601991",
                        "stock_code": "601991",
                        "stock_name": "大唐发电",
                        "rank_no": 1,
                        "payload": {"stock_code": "601991", "raw": "skip"},
                        "payload_json": "{\"raw\":\"skip\"}",
                    }
                ],
                "mainline_turnover_summary": {
                    "date": "2026-05-29",
                    "conclusion": "主线待确认",
                    "mainline_attack_evidence_summary": {
                        "sector_evidence_rows": [
                            {"sector_name": "电力", "net_inflow_amount": 18.2, "extra": "kept-out"},
                        ],
                    },
                    "turnover_share_trend_rows": [
                        {"date": "2026-05-28", "cycle_mainline": "电力", "mainline_turnover": "300亿", "raw": {"skip": True}},
                    ],
                    "hot_sector_turnover_watch_summary": "近期热点板块成交额连续跟踪：电力待累计",
                    "hot_sector_turnover_watch_rows": [
                        {
                            "date": "2026-05-29",
                            "sector_name": "电力",
                            "sector_turnover": "320.50亿",
                            "market_turnover": "10500.00亿",
                            "share": "3.1%",
                            "share_change": "待累计",
                            "sample_status": "待累计",
                            "interpretation": "电力只记录本板块当日点位",
                            "raw": {"skip": True},
                        }
                    ],
                },
                "market_research_snapshot": {
                    "cycle_calendar_rows": [{"weekday": "skip"}],
                    "large_rendered_context": "skip",
                    "mainline_turnover_summary": {
                        "mainline_attack_evidence_summary": {
                            "sector_evidence_rows": [
                                {"sector_name": "电力", "net_inflow_amount": 18.2, "extra": "kept-out"},
                            ],
                        },
                    },
                },
                "execution_stage_context": {
                    "data": {"huge_cache": "skip"},
                    "market_research_snapshot": {"duplicate": "skip"},
                    "market_research_bundle": {"market_research_snapshot": {"duplicate": "skip"}},
                    "step2_bundle": {"huge_cache": "skip"},
                    "step3_bundle": {"huge_cache": "skip"},
                    "core_stocks": [{"code": "000539", "recent_bars": [{"x": 1}]}],
                    "selected_position_candidate": {"code": "000539", "name": "粤电力A", "recent_bars": [{"x": 1}]},
                    "watch_anchor": {"code": "000539", "name": "粤电力A", "recent_bars": [{"x": 1}]},
                    "special_probe_verdict": {"probe_candidate": {"code": "000539", "recent_bars": [{"x": 1}]}},
                },
            },
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO daily_report_fact_fields", sql)
        inserted = next(
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
        )
        field_paths = {row[1] for row in inserted}
        self.assertTrue(any("000001.SH" in path for path in field_paths))
        self.assertTrue(any("csi1000_index" in path and "price" in path for path in field_paths))
        self.assertFalse(any("huge_cache" in str(row) for row in inserted))
        self.assertFalse(any("runtime.cache" in str(row) for row in inserted))
        self.assertFalse(any("appendix_b" in str(row) for row in inserted))
        self.assertFalse(any("decision_ledger_artifacts" in str(row) for row in inserted))
        self.assertFalse(any("case_id" in str(row) for row in inserted))
        self.assertFalse(any("payload_json" in str(row) for row in inserted))
        self.assertFalse(any("candidate_trace_artifact" in row[1] and "raw" in str(row) for row in inserted))
        self.assertFalse(any("candidate_trace_artifact" in row[1] and "payload" in row[1] for row in inserted))
        self.assertFalse(any("large_rendered_context" in str(row) for row in inserted))
        self.assertFalse(any("duplicate" in str(row) for row in inserted))
        self.assertFalse(any("step_status" in str(row) for row in inserted))
        self.assertFalse(any("request_diagnostics" in str(row) for row in inserted))
        self.assertFalse(any("xuangubao_news" in str(row) for row in inserted))
        self.assertTrue(any("xuangubao_data" in path and "news_count" in path for path in field_paths))
        self.assertFalse(any("diagnostics_status" in str(row) for row in inserted))
        self.assertFalse(any("diagnostics_error" in str(row) for row in inserted))
        self.assertFalse(any("raw_detail" in str(row) for row in inserted))
        self.assertFalse(any("raw_payload" in str(row) for row in inserted))
        self.assertFalse(any("cache_snapshot" in str(row) for row in inserted))
        self.assertFalse(any("raw_notice" in str(row) for row in inserted))
        self.assertFalse(any("debug_payload" in str(row) for row in inserted))
        self.assertFalse(any("payload" in str(row) and "candidate_trace_artifact" not in str(row) for row in inserted))
        self.assertFalse(any("calibration_rows" in str(row) for row in inserted))
        self.assertFalse(any("sector_tree" in str(row) for row in inserted))
        self.assertFalse(any("quadrants" in str(row) for row in inserted))
        self.assertFalse(any("day_rows" in str(row) for row in inserted))
        self.assertFalse(any("recent_bars" in str(row) for row in inserted))
        self.assertFalse(any("net_buy_amount" in str(row) for row in inserted))
        self.assertFalse(any("sector_evidence_rows" in str(row) for row in inserted))
        self.assertFalse(any("sector_attack_evidence_rows" in str(row) for row in inserted))
        self.assertTrue(any("new_high_feedback/k:14:new_high_count" in path for path in field_paths))
        self.assertTrue(any("margin_pressure/k:21:latest_pressure_label" in path for path in field_paths))
        self.assertTrue(any("extreme_conviction_list" in path and "risk_reward_plan" in path for path in field_paths))
        self.assertTrue(any("candidate_trace_artifact" in path and "trace_count" in path for path in field_paths))
        self.assertTrue(any("recent_extreme_conviction_mentions" in path and "stock_code" in path for path in field_paths))
        self.assertTrue(any("sector_fund_flow" in path and "net_inflow_yi" in path for path in field_paths))
        self.assertTrue(any("hot_sector_turnover_watch_rows" in path and "sector_name" in path for path in field_paths))
        self.assertTrue(any("hot_sector_turnover_watch_rows" in path and "total_turnover" in path for path in field_paths))
        self.assertTrue(any("exchange_monitor_today" in path for path in field_paths))
        self.assertTrue(any("exchange_monitor_nextday" in path for path in field_paths))
        self.assertEqual(saved["source"], "postgresql://daily-report-facts/2026-05-29")

        conn.cursor_obj.row_batches = [[
            ("k:11:data_status/k:5:两市成交额", "", None, True, "bool"),
            ("k:11:data_status/k:4:中证全指", "", None, True, "bool"),
            ("k:14:total_turnover", "", 33408.58, None, "number"),
            ("k:13:turnover_rank/#0/k:4:code", "601991", None, None, "text"),
            ("k:13:turnover_rank/#0/k:4:name", "大唐发电", None, None, "text"),
            ("k:13:turnover_rank/#0/k:6:amount", "", 12.3, None, "number"),
            ("k:12:market_stats/k:8:up_count", "", 1542.0, None, "number"),
            ("k:12:market_stats/k:10:down_count", "", 3884.0, None, "number"),
            ("k:17:concept_fund_flow/k:4:rows/#0/k:4:name", "火力发电", None, None, "text"),
            ("k:17:concept_fund_flow/k:4:rows/#0/k:10:net_inflow", "", 3.2, None, "number"),
            ("k:7:indices/k:9:000001.SH/k:5:price", "", 4068.57, None, "number"),
            ("k:13:csi1000_index/k:4:name", "中证1000", None, None, "text"),
            ("k:13:csi1000_index/k:5:price", "", 6123.4, None, "number"),
            ("k:22:exchange_monitor_today/#0/k:4:code", "000001", None, None, "text"),
            ("k:24:exchange_monitor_nextday/#0/k:4:code", "000002", None, None, "text"),
        ], [], []]

        loaded = db.load_daily_report_snapshot("2026-05-29")

        self.assertEqual(loaded["source"], "postgresql://daily-report-facts/2026-05-29")
        self.assertEqual(loaded["data"]["total_turnover"], 33408.58)
        self.assertEqual(loaded["data"]["turnover_rank"][0]["code"], "601991")
        self.assertEqual(loaded["data"]["market_stats"]["up_count"], 1542)
        self.assertEqual(loaded["data"]["indices"]["000001.SH"]["price"], 4068.57)
        self.assertEqual(loaded["data"]["csi1000_index"]["price"], 6123.4)
        self.assertEqual(loaded["data"]["exchange_monitor_today"][0]["code"], "000001")
        self.assertEqual(loaded["data"]["exchange_monitor_nextday"][0]["code"], "000002")
        self.assertEqual(loaded["field_count"], 15)

    def test_load_daily_report_snapshot_enriches_hot_sector_history_from_structured_tables(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        conn.cursor_obj.row_batches = [
            [
                ("k:30:recent_sector_turnover_history/#0/k:4:date", "2026-05-28", None, None, "text"),
                ("k:30:recent_sector_turnover_history/#0/k:11:sector_name", "光通信/CPO", None, None, "text"),
                ("k:30:recent_sector_turnover_history/#0/k:18:turnover_share_pct", "", 29.6, None, "number"),
                ("k:32:current_sector_turnover_snapshot/k:11:sector_name", "新型电力", None, None, "text"),
                ("k:27:sector_attack_evidence_rows/#0/k:11:sector_name", "陈旧电力", None, None, "text"),
                ("k:27:sector_attack_evidence_rows/#0/k:19:sector_turnover", "", 296.49, None, "number"),
                ("k:34:recent_hot_sector_turnover_history/#0/k:4:date", "2026-05-29", None, None, "text"),
                ("k:34:recent_hot_sector_turnover_history/#0/k:11:sector_name", "新型电力", None, None, "text"),
                ("k:34:recent_hot_sector_turnover_history/#0/k:18:turnover_share_pct", "", 0.89, None, "number"),
            ],
            [
                (
                    "2026-05-29",
                    "通信设备",
                    80,
                    -44.56,
                    0,
                    0,
                    3062.15,
                    33408.58,
                    9.17,
                    0.0,
                    "sector_attack_evidence_daily",
                    0,
                )
            ],
            [
                ("2026-05-28", "光通信/CPO", 8841.18, 29873.26, 29.6, "mainline_turnover_daily"),
                ("2026-05-29", "通信设备", 3062.15, 33408.58, 9.17, "sector_attack_evidence_daily"),
            ],
        ]

        loaded = db.load_daily_report_snapshot("2026-05-29")

        self.assertEqual(loaded["data"]["sector_attack_evidence_rows"][0]["sector_name"], "通信设备")
        self.assertEqual(loaded["data"]["sector_attack_evidence_rows"][0]["sector_turnover"], 3062.15)
        history = loaded["data"]["recent_hot_sector_turnover_history"]
        self.assertEqual([row["sector_name"] for row in history], ["光通信/CPO", "通信设备"])
        self.assertEqual(history[1]["turnover_share_pct"], 9.17)

    def test_load_daily_report_snapshot_enriches_candidate_trace_from_structured_tables(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        conn.cursor_obj.row_batches = [
            [],
            [],
            [("2026-05-29", 1, "public", "2026-05-29T15:30:00", "reports/replay.md", "full")],
            [("601991", "大唐发电", "T0", "新型电力", "电力", "继续观察", "结构化轨迹完整", "触发条件", "失败条件")],
            [],
            [],
        ]

        loaded = db.load_daily_report_snapshot("2026-05-29")

        artifact = loaded["data"]["candidate_trace_artifact"]
        self.assertEqual(artifact["trade_date"], "2026-05-29")
        self.assertEqual(artifact["traces"][0]["stock_code"], "601991")
        self.assertEqual(artifact["traces"][0]["mainline"], "新型电力")
        self.assertEqual(artifact["traces"][0]["visible_summary"], "结构化轨迹完整")

    def test_hot_sector_history_keeps_power_concepts_separate_and_skips_empty_points(self):
        cursor = _FakeCursor()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: _FakeConnection(),
            ensure_schema=False,
        )
        cursor.rows = [
            ("2026-05-29", "电力储能", 0, 33408.58, 0, "sector_attack_evidence_daily"),
            ("2026-05-29", "新型电力", 296.49, 33408.58, 0.89, "mainline_turnover_daily"),
            ("2026-05-29", "电力", 296.49, 33408.58, 0.89, "sector_attack_evidence_daily"),
        ]

        history = db._load_recent_hot_sector_turnover_history(
            cursor,
            "2026-05-29",
            ["电力", "新型电力"],
            window_days=25,
        )

        query_params = cursor.calls[0][2]
        self.assertIn("新型电力", query_params[3])
        self.assertIn("电力", query_params[3])
        self.assertEqual(len(history), 2)
        by_sector = {row["sector_name"]: row for row in history}
        self.assertEqual(by_sector["新型电力"]["sector_turnover"], 296.49)
        self.assertEqual(by_sector["电力"]["sector_turnover"], 296.49)

    def test_saves_postgres_xuangubao_summary_without_zeroing_counts(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        db.save_daily_report_snapshot(
            "2026-05-29",
            {
                "postgres_only": True,
                "xuangubao_data": {
                    "news_count": 0,
                    "plate_count": 1,
                    "limit_up_reason_count": 2,
                    "diagnostics_status": "success",
                    "diagnostics_error": "",
                },
            },
        )

        inserted = next(
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
        )
        numeric_by_path = {row[1]: row[3] for row in inserted}
        self.assertEqual(
            numeric_by_path["k:14:xuangubao_data/k:11:plate_count"],
            1,
        )
        self.assertEqual(
            numeric_by_path["k:14:xuangubao_data/k:21:limit_up_reason_count"],
            2,
        )

    def test_import_daily_report_facts_populates_structured_market_and_sector_tables(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.import_daily_report_facts(
            "2026-05-29",
            {
                "total_turnover": 33408.58,
                "market_stats": {"up_count": 1542, "down_count": 3884},
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "电力", "zljlr": 18.2, "data_source": "tushare.moneyflow_ind_ths"},
                    ],
                    "outflow": [
                        {"name": "半导体", "zljlr": -6.5, "data_source": "tushare.moneyflow_ind_ths"},
                    ],
                },
                "market_research_snapshot": {
                    "mainline_turnover_summary": {
                        "mainline_attack_evidence_summary": {
                            "sector_evidence_rows": [
                                {"sector_name": "电力", "net_inflow_rank": 1, "net_inflow_amount": 18.2},
                            ],
                        },
                    },
                    "diffusion_quality": {
                        "sectors": [
                            {"sector_name": "电力", "total_score": 76, "level": "强扩散"},
                        ],
                    },
                },
                "candidate_trace_artifact": {
                    "artifact_version": 1,
                    "trade_date": "2026-05-29",
                    "visible_scope": "T0_T1_T2_T3",
                    "payload": {
                        "trade_date": "2026-05-29",
                        "traces": [{"stock_code": "601991", "stock_name": "大唐发电"}],
                    },
                },
            },
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO market_daily_totals", sql)
        self.assertIn("INSERT INTO sector_fund_flow_daily", sql)
        self.assertIn("INSERT INTO sector_attack_evidence_daily", sql)
        self.assertIn("INSERT INTO sector_diffusion_score_daily", sql)
        self.assertIn("INSERT INTO candidate_trace_rows", sql)
        self.assertEqual(result["structured_counts"]["market_daily_total"], 1)
        self.assertEqual(result["structured_counts"]["sector_fund_flow"], 2)
        self.assertEqual(result["structured_counts"]["market_cycle"]["sector_attack_records"], 1)
        self.assertEqual(result["structured_counts"]["market_cycle"]["sector_diffusion_records"], 1)
        self.assertEqual(result["structured_counts"]["candidate_trace"]["trace_count"], 1)

    def test_import_daily_report_facts_reads_runtime_sector_internal_analysis(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.import_daily_report_facts(
            "2026-05-29",
            {
                "sector_internal_analysis": {
                    "diffusion_quality": {
                        "sectors": [
                            {"sector_name": "电力", "total_score": 76, "level": "强扩散"},
                        ],
                    },
                },
            },
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO sector_diffusion_score_daily", sql)
        self.assertEqual(result["structured_counts"]["market_cycle"]["sector_diffusion_records"], 1)

    def test_import_daily_report_facts_preserves_runtime_sector_internal_analysis_fields(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        db.import_daily_report_facts(
            "2026-05-29",
            {
                "market_research_snapshot": {"market_branch": "混沌轮动"},
                "sector_internal_analysis": {
                    "diffusion_quality": {
                        "sectors": [
                            {"sector_name": "电力", "total_score": 76, "level": "强扩散"},
                        ],
                    },
                    "turnover_trend": {"summary": "电力成交占比抬升"},
                    "quant_environment": {"environment": "弱扩散"},
                },
            },
        )

        inserted = next(
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
        )
        field_paths = [row[1] for row in inserted]

        self.assertTrue(any("sector_internal_analysis" in path and "turnover_trend" in path for path in field_paths))
        self.assertTrue(any("sector_internal_analysis" in path and "quant_environment" in path for path in field_paths))


if __name__ == "__main__":
    unittest.main()
