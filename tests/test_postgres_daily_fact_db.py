import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from storage.postgres_daily_fact_db import (
    POSTGRES_SCHEMA_STATEMENTS,
    PostgresDailyFactDb,
    _recent_replay_min_trade_date,
)
from daily_report_render import build_report_preflight
from input.index_cross_validation import REPORT_INDEX_SPECS, build_report_index_cross_validation
from domains.market_state.market_language_translation import (
    MARKET_LANGUAGE_SOURCE_POLICY,
    build_market_language_source_projection,
    build_market_language_translation,
    canonical_market_language_hash,
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


class _MemoryDailyFactCursor:
    def __init__(self, state):
        self.state = state
        self.last_rows = []

    def execute(self, sql, params=None):
        normalized_sql = " ".join(str(sql).split())
        params = tuple(params or ())
        self.last_rows = []
        if "INSERT INTO stock_daily_quotes_recent" in normalized_sql:
            (
                trade_date,
                ts_code,
                stock_code,
                market,
                name,
                open_price,
                high,
                low,
                close,
                pct_chg,
                vol,
                amount_yi,
                source_run_id,
            ) = params
            self.state["quotes"][(trade_date, ts_code)] = {
                "trade_date": trade_date,
                "ts_code": ts_code,
                "stock_code": stock_code,
                "market": market,
                "name": name,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "pct_chg": pct_chg,
                "vol": vol,
                "amount_yi": amount_yi,
                "source_run_id": source_run_id,
            }
        elif "SELECT COALESCE(SUM(amount_yi), 0) AS total_amount_yi, COUNT(*) AS stock_count FROM stock_daily_quotes_recent" in normalized_sql:
            trade_date = params[0]
            rows = [row for row in self.state["quotes"].values() if row["trade_date"] == trade_date]
            self.last_rows = [{"total_amount_yi": sum(float(row["amount_yi"]) for row in rows), "stock_count": len(rows)}]
        elif "INSERT INTO market_daily_totals" in normalized_sql:
            trade_date, market_scope, total_amount_yi, stock_count, source_policy, source_run_id = params
            self.state["totals"][(trade_date, market_scope)] = {
                "trade_date": trade_date,
                "market_scope": market_scope,
                "total_amount_yi": total_amount_yi,
                "stock_count": stock_count,
                "source_policy": source_policy,
                "source_run_id": source_run_id,
            }
        elif "SELECT total_amount_yi FROM market_daily_totals" in normalized_sql:
            trade_date, market_scope = params
            row = self.state["totals"].get((trade_date, market_scope))
            self.last_rows = [{"total_amount_yi": row["total_amount_yi"]}] if row else []
        elif "SELECT COUNT(*) AS total_count, COUNT(*) FILTER (WHERE pct_chg > 0) AS up_count" in normalized_sql:
            trade_date = params[0]
            rows = [row for row in self.state["quotes"].values() if row["trade_date"] == trade_date]
            self.last_rows = [
                {
                    "total_count": len(rows),
                    "up_count": len([row for row in rows if float(row["pct_chg"]) > 0]),
                    "down_count": len([row for row in rows if float(row["pct_chg"]) < 0]),
                    "flat_count": len([row for row in rows if float(row["pct_chg"]) == 0]),
                    "zt_count": len([row for row in rows if float(row["pct_chg"]) >= 9.8]),
                    "dt_count": len([row for row in rows if float(row["pct_chg"]) <= -9.8]),
                }
            ]
        elif "SELECT trade_date, ts_code, stock_code, name, amount_yi FROM stock_daily_quotes_recent" in normalized_sql:
            trade_date, limit = params
            rows = [
                row for row in self.state["quotes"].values()
                if row["trade_date"] == trade_date and float(row["amount_yi"]) > 0
            ]
            rows = sorted(rows, key=lambda row: (-float(row["amount_yi"]), row["ts_code"]))[: int(limit)]
            self.last_rows = [
                {
                    "trade_date": row["trade_date"],
                    "ts_code": row["ts_code"],
                    "stock_code": row["stock_code"],
                    "name": row["name"],
                    "amount_yi": row["amount_yi"],
                }
                for row in rows
            ]
        elif "DELETE FROM turnover_rank_daily" in normalized_sql:
            trade_date, rank_scope = params
            self.state["ranks"] = [
                row for row in self.state["ranks"]
                if not (row["trade_date"] == trade_date and row["rank_scope"] == rank_scope)
            ]
        elif "INSERT INTO turnover_rank_daily" in normalized_sql:
            (
                trade_date,
                rank_scope,
                rank_no,
                ts_code,
                stock_code,
                name,
                amount_yi,
                total_amount_yi,
                amount_share_pct,
                source_run_id,
            ) = params
            self.state["ranks"].append(
                {
                    "trade_date": trade_date,
                    "rank_scope": rank_scope,
                    "rank_no": rank_no,
                    "ts_code": ts_code,
                    "stock_code": stock_code,
                    "name": name,
                    "amount_yi": amount_yi,
                    "total_amount_yi": total_amount_yi,
                    "amount_share_pct": amount_share_pct,
                    "source_run_id": source_run_id,
                }
            )
        elif "SELECT DISTINCT trade_date FROM turnover_rank_daily" in normalized_sql:
            end_date, rank_scope, window_days = params
            dates = sorted(
                {
                    row["trade_date"]
                    for row in self.state["ranks"]
                    if row["trade_date"] <= end_date and row["rank_scope"] == rank_scope
                },
                reverse=True,
            )[: int(window_days)]
            self.last_rows = [{"trade_date": date} for date in dates]
        elif "SELECT COALESCE(SUM(amount_yi), 0) AS top_amount_yi, COALESCE(MAX(total_amount_yi), 0) AS market_amount_yi FROM turnover_rank_daily" in normalized_sql:
            trade_date, rank_scope, limit = params
            rows = [
                row for row in self.state["ranks"]
                if row["trade_date"] == trade_date
                and row["rank_scope"] == rank_scope
                and int(row["rank_no"]) <= int(limit)
            ]
            self.last_rows = [
                {
                    "top_amount_yi": sum(float(row["amount_yi"]) for row in rows),
                    "market_amount_yi": max([float(row["total_amount_yi"]) for row in rows] or [0.0]),
                }
            ]
        elif "SELECT DISTINCT source_run_id FROM turnover_rank_daily" in normalized_sql:
            trade_date, rank_scope, limit = params
            ids = sorted(
                {
                    int(row["source_run_id"])
                    for row in self.state["ranks"]
                    if row["trade_date"] == trade_date
                    and row["rank_scope"] == rank_scope
                    and int(row["rank_no"]) <= int(limit)
                    and int(row["source_run_id"]) > 0
                }
            )
            self.last_rows = [{"source_run_id": value} for value in ids]
        elif "SELECT trade_date, rank_scope, rank_no, ts_code, stock_code, name, amount_yi, total_amount_yi, amount_share_pct, source_run_id FROM turnover_rank_daily" in normalized_sql:
            trade_date, rank_scope, limit = params
            rows = [
                row for row in self.state["ranks"]
                if row["trade_date"] == trade_date
                and row["rank_scope"] == rank_scope
                and int(row["rank_no"]) <= int(limit)
            ]
            self.last_rows = sorted(rows, key=lambda row: row["rank_no"])
        elif "SELECT trade_date, ts_code, stock_code, market, name, open, high, low, close, pct_chg, vol, amount_yi FROM stock_daily_quotes_recent WHERE trade_date = %s AND high > 0" in normalized_sql:
            trade_date = params[0]
            self.last_rows = [
                dict(row) for row in self.state["quotes"].values()
                if row["trade_date"] == trade_date and float(row["high"]) > 0
            ]
        elif "SELECT COUNT(DISTINCT trade_date) AS available_trade_days FROM stock_daily_quotes_recent WHERE trade_date < %s" in normalized_sql:
            trade_date = params[0]
            self.last_rows = [
                {
                    "available_trade_days": len(
                        {row["trade_date"] for row in self.state["quotes"].values() if row["trade_date"] < trade_date}
                    )
                }
            ]
        elif "SELECT stock_code, MAX(high) AS previous_high FROM stock_daily_quotes_recent" in normalized_sql:
            trade_date = params[0]
            stock_codes = set(params[1:])
            by_code = {}
            for row in self.state["quotes"].values():
                if row["trade_date"] < trade_date and row["stock_code"] in stock_codes and float(row["high"]) > 0:
                    by_code[row["stock_code"]] = max(float(row["high"]), by_code.get(row["stock_code"], 0.0))
            self.last_rows = [
                {"stock_code": stock_code, "previous_high": previous_high}
                for stock_code, previous_high in by_code.items()
            ]
        elif "SELECT COUNT(*) AS total_count FROM stock_daily_quotes_recent WHERE trade_date = %s" in normalized_sql:
            trade_date = params[0]
            self.last_rows = [
                {"total_count": len([row for row in self.state["quotes"].values() if row["trade_date"] == trade_date])}
            ]
        elif "INSERT INTO new_high_feedback_daily" in normalized_sql:
            (
                trade_date,
                source_date,
                query_date,
                requested_trade_date,
                new_high_count,
                all_a_share_pct,
                leading_sectors,
                sector_distribution_json,
                top_stocks_json,
                source_policy,
                source_run_id,
            ) = params
            self.state["new_high"][trade_date] = {
                "trade_date": trade_date,
                "source_date": source_date,
                "query_date": query_date,
                "requested_trade_date": requested_trade_date,
                "new_high_count": new_high_count,
                "all_a_share_pct": all_a_share_pct,
                "leading_sectors": leading_sectors,
                "sector_distribution_json": sector_distribution_json,
                "top_stocks_json": top_stocks_json,
                "source_policy": source_policy,
                "source_run_id": source_run_id,
            }
        elif "FROM new_high_feedback_daily" in normalized_sql and "SELECT trade_date, source_date, query_date, requested_trade_date" in normalized_sql:
            end_date, window_days = params
            rows = [row for row in self.state["new_high"].values() if row["trade_date"] <= end_date]
            self.last_rows = sorted(rows, key=lambda row: row["trade_date"], reverse=True)[: int(window_days)]
        return self

    def executemany(self, sql, rows):
        for row in rows or []:
            self.execute(sql, row)
        return self

    def fetchall(self):
        return list(self.last_rows)

    def fetchone(self):
        return self.last_rows[0] if self.last_rows else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _MemoryDailyFactConnection:
    def __init__(self):
        self.state = {"quotes": {}, "totals": {}, "ranks": [], "new_high": {}}
        self.commit_count = 0

    def cursor(self, *args, **kwargs):
        return _MemoryDailyFactCursor(self.state)

    def commit(self):
        self.commit_count += 1

    def close(self):
        pass


class PostgresDailyFactDbTest(unittest.TestCase):
    def test_schema_has_three_migration_batches_without_blob_primary_store(self):
        schema = "\n".join(POSTGRES_SCHEMA_STATEMENTS).lower()

        for table_name in (
            "market_cycle_days",
            "market_cycle_periods",
            "mainline_switch_events",
            "monthly_account_ledger",
            "index_daily_bars",
            "index_minute_bars",
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
            "price_band_style_daily",
            "extreme_conviction_cases",
            "extreme_conviction_mentions",
            "planned_participation_steps",
            "participation_reviews",
            "trend_fates",
            "cycle_acceptance_reviews",
            "runtime_cache_entries",
        ):
            self.assertIn(f"create table if not exists {table_name}", schema)
        for table_name in (
            "stock_daily_quotes_recent",
            "turnover_rank_daily",
            "new_high_feedback_daily",
        ):
            self.assertIn(f"create table if not exists {table_name}", schema)

        self.assertNotIn("payload_json", schema)

    def test_stock_daily_quotes_rebuild_top50_share_series(self):
        conn = _MemoryDailyFactConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        inserted = db.upsert_stock_daily_quotes_recent(
            [
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "601138.SH",
                    "stock_code": "601138",
                    "name": "工业富联",
                    "amount_yi": 420.0,
                    "high": 50,
                    "close": 48,
                    "pct_chg": 2.1,
                },
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "601991.SH",
                    "stock_code": "601991",
                    "name": "大唐发电",
                    "amount_yi": 180.0,
                    "high": 8,
                    "close": 7.8,
                    "pct_chg": 1.4,
                },
            ],
            source_run_id=11,
        )
        total = db.rebuild_market_daily_total("2026-06-08", source_run_id=11)
        ranks = db.rebuild_turnover_rank_daily("2026-06-08", rank_limit=100, source_run_id=11)
        series = db.query_top_turnover_share_series("2026-06-08", window_days=25, limit=50)

        self.assertEqual(inserted, 2)
        self.assertEqual(total["total_amount_yi"], 600.0)
        self.assertEqual([row["stock_code"] for row in ranks], ["601138", "601991"])
        self.assertEqual(series["source"], "storage.turnover_rank_daily")
        self.assertEqual(series["rows"][0]["trade_date"], "2026-06-08")
        self.assertEqual(series["rows"][0]["top_amount_yi"], 600.0)
        self.assertEqual(series["rows"][0]["market_amount_yi"], 600.0)
        self.assertEqual(series["rows"][0]["share_pct"], 100.0)
        self.assertEqual(series["source_run_ids"], [11])

    def test_query_market_breadth_counts_prefers_structured_recent_quotes(self):
        conn = _MemoryDailyFactConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        db.upsert_stock_daily_quotes_recent(
            [
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "000001.SZ",
                    "stock_code": "000001",
                    "name": "平安银行",
                    "amount_yi": 100.0,
                    "high": 12.0,
                    "close": 11.0,
                    "pct_chg": 2.1,
                },
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "000002.SZ",
                    "stock_code": "000002",
                    "name": "万科A",
                    "amount_yi": 80.0,
                    "high": 9.0,
                    "close": 8.0,
                    "pct_chg": -1.2,
                },
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "000003.SZ",
                    "stock_code": "000003",
                    "name": "平盘样本",
                    "amount_yi": 20.0,
                    "high": 5.0,
                    "close": 5.0,
                    "pct_chg": 0.0,
                },
            ],
            source_run_id=11,
        )

        with patch.object(
            PostgresDailyFactDb,
            "_load_daily_report_fact_value",
            return_value={"up_count": 111, "down_count": 222, "source": "daily_report_fact_fields"},
        ):
            result = db.query_market_breadth_counts("2026-06-08")

        self.assertEqual(result["up_count"], 1)
        self.assertEqual(result["down_count"], 1)
        self.assertEqual(result["flat_count"], 1)
        self.assertEqual(result["stock_count"], 3)
        self.assertEqual(result["trade_date"], "2026-06-08")
        self.assertEqual(result["source_date"], "2026-06-08")
        self.assertEqual(result["source"], "storage.stock_daily_quotes_recent")

    def test_top50_share_series_merges_structured_target_date_with_previous_report_window(self):
        conn = _MemoryDailyFactConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        previous_rows = [
            {
                "trade_date": trade_date,
                "top_amount_yi": 5000.0 + index,
                "market_amount_yi": 30000.0,
                "share_pct": 18.0 + index / 10.0,
            }
            for index, trade_date in enumerate(_RECENT_25_TRADING_DATES_THROUGH_2026_05_29)
        ]
        db.upsert_stock_daily_quotes_recent(
            [
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "601138.SH",
                    "stock_code": "601138",
                    "name": "工业富联",
                    "amount_yi": 420.0,
                    "high": 50,
                    "close": 48,
                    "pct_chg": 2.1,
                },
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "601991.SH",
                    "stock_code": "601991",
                    "name": "大唐发电",
                    "amount_yi": 180.0,
                    "high": 8,
                    "close": 7.8,
                    "pct_chg": 1.4,
                },
            ],
            source_run_id=11,
        )
        db.rebuild_market_daily_total("2026-06-08", source_run_id=11)
        db.rebuild_turnover_rank_daily("2026-06-08", rank_limit=100, source_run_id=11)

        with patch.object(
            PostgresDailyFactDb,
            "_load_daily_report_fact_value",
            return_value={"source": "postgres.daily_report_facts.top50_turnover_share_series", "rows": previous_rows},
        ):
            series = db.query_top_turnover_share_series("2026-06-08", window_days=25, limit=50)

        self.assertEqual(series["source"], "storage.turnover_rank_daily+postgres.daily_report_facts.top50_turnover_share_series")
        self.assertEqual(len(series["rows"]), 25)
        self.assertEqual(series["rows"][0]["trade_date"], "2026-04-23")
        self.assertEqual(series["rows"][-1]["trade_date"], "2026-06-08")
        self.assertEqual(series["rows"][-1]["top_amount_yi"], 600.0)
        self.assertEqual(series["rows"][-1]["market_amount_yi"], 600.0)
        self.assertEqual(series["rows"][-1]["share_pct"], 100.0)

    def test_top50_share_series_looks_back_to_latest_previous_report_window(self):
        conn = _MemoryDailyFactConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        previous_rows = [
            {
                "trade_date": trade_date,
                "top_amount_yi": 5000.0 + index,
                "market_amount_yi": 30000.0,
                "share_pct": 18.0 + index / 10.0,
            }
            for index, trade_date in enumerate(_RECENT_25_TRADING_DATES_THROUGH_2026_05_29)
        ]
        encoded_rows = []
        for index, row in enumerate(previous_rows):
            for key, value in row.items():
                encoded_rows.append((
                    f"k:27:top50_turnover_share_series/k:4:rows/#{index}/k:{len(key)}:{key}",
                    value if isinstance(value, str) else "",
                    None if isinstance(value, str) else value,
                    None,
                    "text" if isinstance(value, str) else "number",
                ))
        db.upsert_stock_daily_quotes_recent(
            [
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "601138.SH",
                    "stock_code": "601138",
                    "name": "工业富联",
                    "amount_yi": 420.0,
                    "high": 50,
                    "close": 48,
                    "pct_chg": 2.1,
                },
            ],
            source_run_id=11,
        )
        db.rebuild_market_daily_total("2026-06-08", source_run_id=11)
        db.rebuild_turnover_rank_daily("2026-06-08", rank_limit=100, source_run_id=11)
        original_execute = _MemoryDailyFactCursor.execute

        def execute_with_previous_report_window(cursor, sql, params=None):
            normalized_sql = " ".join(str(sql).split())
            if "SELECT max(trade_date) AS trade_date FROM daily_report_fact_fields" in normalized_sql:
                cursor.last_rows = [{"trade_date": "2026-06-05"}]
                return cursor
            if "FROM daily_report_fact_fields" in normalized_sql and "field_path LIKE" in normalized_sql:
                cursor.last_rows = [
                    {
                        "field_path": field_path,
                        "value_text": value_text,
                        "value_number": value_number,
                        "value_bool": value_bool,
                        "value_kind": value_kind,
                    }
                    for field_path, value_text, value_number, value_bool, value_kind in encoded_rows
                ]
                return cursor
            return original_execute(cursor, sql, params)

        with patch.object(_MemoryDailyFactCursor, "execute", execute_with_previous_report_window):
            series = db.query_top_turnover_share_series("2026-06-08", window_days=25, limit=50)

        self.assertEqual(series["source"], "storage.turnover_rank_daily+postgres.daily_report_facts.top50_turnover_share_series")
        self.assertEqual(len(series["rows"]), 25)
        self.assertEqual(series["rows"][0]["trade_date"], "2026-04-23")
        self.assertEqual(series["rows"][-1]["trade_date"], "2026-06-08")

    def test_new_high_feedback_rebuilds_from_postgres_recent_quotes(self):
        conn = _MemoryDailyFactConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        history_rows = [
            {"trade_date": f"2026-05-{day:02d}", "new_high_count": 1, "all_a_share_pct": 50.0}
            for day in range(1, 26)
        ]
        quote_rows = []
        for index, date in enumerate([row["trade_date"] for row in history_rows], start=1):
            quote_rows.append(
                {
                    "trade_date": date,
                    "ts_code": "601138.SH",
                    "stock_code": "601138",
                    "name": "工业富联",
                    "high": 40.0 + index / 100,
                    "close": 39.0,
                    "pct_chg": 0.1,
                    "amount_yi": 100.0,
                }
            )
            quote_rows.append(
                {
                    "trade_date": date,
                    "ts_code": "601991.SH",
                    "stock_code": "601991",
                    "name": "大唐发电",
                    "high": 9.0,
                    "close": 8.8,
                    "pct_chg": 0.1,
                    "amount_yi": 20.0,
                }
            )
        quote_rows.extend(
            [
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "601138.SH",
                    "stock_code": "601138",
                    "name": "工业富联",
                    "high": 45.0,
                    "close": 44.5,
                    "pct_chg": 4.2,
                    "amount_yi": 520.0,
                },
                {
                    "trade_date": "2026-06-08",
                    "ts_code": "601991.SH",
                    "stock_code": "601991",
                    "name": "大唐发电",
                    "high": 8.5,
                    "close": 8.2,
                    "pct_chg": -1.0,
                    "amount_yi": 80.0,
                },
            ]
        )
        db.upsert_stock_daily_quotes_recent(quote_rows, source_run_id=12)

        feedback = db.build_new_high_feedback_from_recent_quotes(
            "2026-06-08",
            stock_basic_map={
                "601138": {"name": "工业富联", "industry": "AI算力基础设施", "list_date": "20180608"},
                "601991": {"name": "大唐发电", "industry": "电力", "list_date": "20061220"},
            },
            stock_risk_map={},
            history_rows=history_rows,
            lookback_days=25,
        )
        stored = db.upsert_new_high_feedback_daily(feedback)
        series = db.query_new_high_feedback_series("2026-06-08", window_days=25)

        self.assertTrue(feedback["available"])
        self.assertEqual(feedback["source"], "storage.stock_daily_quotes_recent.high_break")
        self.assertEqual(feedback["new_high_count"], 1)
        self.assertEqual(feedback["leading_sectors"], "AI算力基础设施")
        self.assertEqual(feedback["trend_rows"][-1]["trade_date"], "2026-06-08")
        self.assertEqual(stored["trade_date"], "2026-06-08")
        self.assertEqual(series[-1]["trade_date"], "2026-06-08")
        self.assertEqual(stored["source_date"], "2026-06-08")
        self.assertEqual(stored["query_date"], "2026-06-08")
        self.assertEqual(stored["requested_trade_date"], "2026-06-08")
        self.assertEqual(series[-1]["source_date"], "2026-06-08")
        self.assertEqual(series[-1]["query_date"], "2026-06-08")
        self.assertEqual(series[-1]["requested_trade_date"], "2026-06-08")
        self.assertEqual(series[-1]["new_high_count"], 1)

    def test_psycopg_connection_prefers_python_impl_when_unspecified(self):
        import os

        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            ensure_schema=False,
        )

        class FakePsycopg:
            @staticmethod
            def connect(database_url, **kwargs):
                return {"database_url": database_url, "kwargs": kwargs}

        class FakeRows:
            dict_row = object()

        def fake_import(name):
            if name == "psycopg":
                return FakePsycopg
            if name == "psycopg.rows":
                return FakeRows
            raise ImportError(name)

        with patch.dict(os.environ, {}, clear=True):
            with patch("storage.postgres_daily_fact_db.importlib.import_module", side_effect=fake_import):
                conn = db._connect_with_psycopg()
                self.assertEqual(os.environ.get("PSYCOPG_IMPL"), "python")

        self.assertEqual(conn["database_url"], "postgresql://unit-test")
        self.assertEqual(conn["kwargs"]["row_factory"], FakeRows.dict_row)

    def test_psycopg_connection_preserves_explicit_impl(self):
        import os

        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            ensure_schema=False,
        )

        class FakePsycopg:
            @staticmethod
            def connect(database_url, **kwargs):
                return {"database_url": database_url, "kwargs": kwargs}

        def fake_import(name):
            if name == "psycopg":
                return FakePsycopg
            raise ImportError(name)

        with patch.dict(os.environ, {"PSYCOPG_IMPL": "binary"}, clear=True):
            with patch("storage.postgres_daily_fact_db.importlib.import_module", side_effect=fake_import):
                db._connect_with_psycopg()
                self.assertEqual(os.environ.get("PSYCOPG_IMPL"), "binary")

    def test_runtime_cache_entries_schema_has_ttl_and_namespace_key(self):
        schema = "\n".join(POSTGRES_SCHEMA_STATEMENTS).lower()

        self.assertIn("create table if not exists runtime_cache_entries", schema)
        self.assertIn("namespace text not null", schema)
        self.assertIn("cache_key text not null", schema)
        self.assertIn("expires_at timestamptz not null", schema)
        self.assertIn("primary key (namespace, cache_key, target_date)", schema)
        self.assertIn("create index if not exists idx_runtime_cache_entries_expires_at", schema)

    def test_query_price_band_style_series_reads_daily_report_fact_snapshot(self):
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: _FakeConnection(),
            ensure_schema=False,
        )
        snapshot = {
            "data": {
                "price_band_style_series": {
                    "source": "postgres.daily_report_fact_fields",
                    "rows": [
                        {
                            "trade_date": "2026-06-04",
                            "high_price_pct": 1.2,
                            "low_price_pct": -0.4,
                        }
                    ],
                }
            }
        }

        with patch.object(PostgresDailyFactDb, "load_daily_report_snapshot", return_value=snapshot):
            result = db.query_price_band_style_series("2026-06-05", window_days=25)

        self.assertEqual(result["source"], "postgres.daily_report_fact_fields")
        self.assertEqual(result["rows"][0]["trade_date"], "2026-06-04")

    def test_price_band_style_daily_round_trip_uses_structured_rows_before_snapshot(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        db.upsert_price_band_style_daily(
            {
                "trade_date": "2026-06-05",
                "high_price_code": "883916.TI",
                "low_price_code": "883960.TI",
                "high_price_pct": -1.07,
                "low_price_pct": -0.87,
                "spread_pct": -0.2,
                "style_label": "震荡",
                "source_policy": "ths.history_line.price_band_style",
                "source_run_id": 12,
            }
        )
        conn.cursor_obj.row_batches.append(
            [
                {
                    "trade_date": "2026-06-05",
                    "high_price_code": "883916.TI",
                    "low_price_code": "883960.TI",
                    "high_price_pct": -1.07,
                    "low_price_pct": -0.87,
                    "spread_pct": -0.2,
                    "style_label": "震荡",
                    "source_policy": "ths.history_line.price_band_style",
                    "source_run_id": 12,
                }
            ]
        )

        with patch.object(PostgresDailyFactDb, "load_daily_report_snapshot", side_effect=AssertionError("snapshot should not be read")):
            result = db.query_price_band_style_series("2026-06-05", window_days=25)

        self.assertEqual(result["source"], "postgres.price_band_style_daily")
        self.assertEqual(result["rows"][0]["trade_date"], "2026-06-05")
        self.assertAlmostEqual(result["rows"][0]["spread_pct"], -0.2)
        sql = "\n".join(call[1] for call in conn.cursor_obj.calls if call[0] == "execute")
        self.assertIn("INSERT INTO price_band_style_daily", sql)
        self.assertIn("FROM price_band_style_daily", sql)

    def test_import_daily_report_facts_writes_price_band_style_rows_to_structured_table(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.import_daily_report_facts(
            "2026-06-05",
            {
                "price_band_style_series": {
                    "source": "ths.history_line.price_band_style",
                    "rows": [
                        {
                            "trade_date": "2026-06-04",
                            "high_price_code": "883916.TI",
                            "low_price_code": "883960.TI",
                            "high_price_pct": 1.2,
                            "low_price_pct": 0.2,
                            "spread_pct": 1.0,
                            "style_label": "震荡",
                        },
                        {
                            "trade_date": "2026-06-05",
                            "high_price_pct": -1.07,
                            "low_price_pct": -0.87,
                            "spread_pct": -0.2,
                            "style_label": "震荡",
                            "source_policy": "tushare.ths_daily.price_band_style",
                        },
                    ],
                },
            },
        )

        price_band_inserts = [
            call for call in conn.cursor_obj.calls
            if call[0] == "execute" and "INSERT INTO price_band_style_daily" in call[1]
        ]
        self.assertEqual(len(price_band_inserts), 2)
        self.assertEqual(result["structured_counts"]["price_band_style_daily"], 2)
        self.assertIn("price_band_style_daily", "\n".join(call[1] for call in conn.cursor_obj.calls))

    def test_monthly_account_ledger_schema_migrates_existing_cumulative_column(self):
        schema = "\n".join(POSTGRES_SCHEMA_STATEMENTS).lower()

        self.assertIn(
            "alter table monthly_account_ledger add column if not exists simulated_cumulative_return_pct",
            schema,
        )

    def test_monthly_account_ledger_round_trip_computes_simulated_cumulative_return(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        conn.cursor_obj.row_batches = [
            [
                {
                    "month_key": "2026-04",
                    "trade_date": "2026-04-30",
                    "month_return_pct": 2.4,
                }
            ]
        ]

        saved = db.upsert_monthly_account_ledger(
            {
                "trade_date": "2026-05-20",
                "account_id": "main",
                "month_key": "2026-05",
                "month_return_pct": 6.8,
                "equity": 106800.0,
                "cash": 50000.0,
                "position_market_value": 56800.0,
                "source_policy": "manual_review",
            }
        )

        self.assertEqual(saved["month_key"], "2026-05")
        self.assertAlmostEqual(saved["simulated_cumulative_return_pct"], 9.3632, places=4)
        self.assertEqual(conn.commit_count, 1)
        self.assertIn("INSERT INTO monthly_account_ledger", "\n".join(call[1] for call in conn.cursor_obj.calls))

        conn.cursor_obj.row_batches = [
            [
                {
                    "trade_date": "2026-05-20",
                    "account_id": "main",
                    "month_key": "2026-05",
                    "month_return_pct": 6.8,
                    "simulated_cumulative_return_pct": 9.3632,
                    "equity": 106800.0,
                    "cash": 50000.0,
                    "position_market_value": 56800.0,
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "max_drawdown_pct": -1.2,
                    "planned_trade_count": 3,
                    "unplanned_trade_count": 1,
                    "note": "manual_review",
                    "source_policy": "manual_review",
                    "updated_at": "2026-05-20T00:00:00Z",
                }
            ],
            [
                {
                    "month_key": "2026-04",
                    "trade_date": "2026-04-30",
                    "month_return_pct": 2.4,
                },
                {
                    "month_key": "2026-05",
                    "trade_date": "2026-05-20",
                    "month_return_pct": 6.8,
                },
            ],
        ]

        queried = db.query_monthly_account_ledger("2026-05-20")

        self.assertEqual(queried["trade_date"], "2026-05-20")
        self.assertAlmostEqual(queried["simulated_cumulative_return_pct"], 9.3632, places=4)
        self.assertEqual(queried["source_policy"], "manual_review")

    def test_monthly_account_ledger_query_recomputes_after_out_of_order_backfill(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        conn.cursor_obj.row_batches = [
            [
                {
                    "trade_date": "2026-05-20",
                    "account_id": "main",
                    "month_key": "2026-05",
                    "month_return_pct": 6.8,
                    "simulated_cumulative_return_pct": 6.8,
                    "equity": 106800.0,
                    "cash": 50000.0,
                    "position_market_value": 56800.0,
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "max_drawdown_pct": -1.2,
                    "planned_trade_count": 3,
                    "unplanned_trade_count": 1,
                    "note": "manual_review",
                    "source_policy": "manual_review",
                    "updated_at": "2026-05-20T00:00:00Z",
                }
            ],
            [
                {
                    "month_key": "2026-04",
                    "trade_date": "2026-04-30",
                    "month_return_pct": 2.4,
                },
                {
                    "month_key": "2026-05",
                    "trade_date": "2026-05-20",
                    "month_return_pct": 6.8,
                },
            ],
        ]

        queried = db.query_monthly_account_ledger("2026-05-20")

        self.assertAlmostEqual(queried["simulated_cumulative_return_pct"], 9.3632, places=4)

    def test_index_bar_tables_are_structured_without_cache_payloads(self):
        schema = "\n".join(POSTGRES_SCHEMA_STATEMENTS).lower()

        self.assertIn("create table if not exists index_daily_bars", schema)
        self.assertIn("primary key (index_code, trade_date)", schema)
        self.assertIn("create table if not exists index_minute_bars", schema)
        self.assertIn("primary key (index_code, trade_date, period, bar_time)", schema)
        self.assertNotIn("index_daily_bars(\n        payload", schema)
        self.assertNotIn("index_minute_bars(\n        payload", schema)

    def test_index_daily_bars_round_trip_as_structured_rows(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        saved_count = db.upsert_index_daily_bars(
            "sh.000001",
            [
                {
                    "date": "2026-05-28",
                    "open": 4050.0,
                    "high": 4070.0,
                    "low": 4040.0,
                    "close": 4060.0,
                    "volume": 100.0,
                    "amount": 1000.0,
                }
            ],
            source_policy="sse_index_dayk",
        )

        self.assertEqual(saved_count, 1)
        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO index_daily_bars", sql)

        conn.cursor_obj.row_batches = [
            [
                {
                    "index_code": "sh000001",
                    "trade_date": "2026-05-29",
                    "open": 4061.0,
                    "high": 4080.0,
                    "low": 4050.0,
                    "close": 4075.0,
                    "volume": 120.0,
                    "amount": 1200.0,
                    "source_policy": "sse_index_dayk",
                    "source_run_id": 0,
                },
                {
                    "index_code": "sh000001",
                    "trade_date": "2026-05-28",
                    "open": 4050.0,
                    "high": 4070.0,
                    "low": 4040.0,
                    "close": 4060.0,
                    "volume": 100.0,
                    "amount": 1000.0,
                    "source_policy": "sse_index_dayk",
                    "source_run_id": 0,
                },
            ]
        ]

        rows = db.query_index_daily_bars("sh.000001", "2026-05-29", window_days=250)

        self.assertEqual([row["date"] for row in rows], ["2026-05-28", "2026-05-29"])
        self.assertEqual(rows[0]["close"], 4060.0)
        self.assertEqual(rows[0]["data_source"], "postgresql.index_daily_bars")

    def test_import_daily_report_facts_writes_current_index_daily_bars(self):
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
                "indices": {
                    "上证指数": {
                        "trade_date": "2026-05-29",
                        "code": "000001",
                        "name": "上证指数",
                        "open": 4110.52,
                        "high": 4112.96,
                        "low": 4055.89,
                        "close": 4068.57,
                        "turnover": 0,
                        "data_source": "tushare.index_daily",
                    }
                },
            },
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO index_daily_bars", sql)
        self.assertEqual(result["structured_counts"]["index_daily_bars"], 1)

    def test_import_daily_report_facts_reads_execution_position_monthly_rhythm(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        result = db.import_daily_report_facts(
            "2026-05-29",
            {
                "execution_stage_context": {
                    "position_decision": {
                        "monthly_rhythm": {
                            "month_key": "2026-05",
                            "month_return_pct": 6.8,
                            "source_policy": "manual_review",
                        },
                    },
                },
            },
        )

        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO monthly_account_ledger", sql)
        self.assertEqual(result["structured_counts"]["monthly_account_ledger"], 1)

    def test_index_minute_bars_round_trip_as_structured_rows(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        saved_count = db.upsert_index_minute_bars(
            "sh.000001",
            "2026-05-29",
            "60",
            [
                {
                    "datetime": "2026-05-29 10:30:00",
                    "date": "2026-05-29",
                    "time": "10:30:00",
                    "open": 4050.0,
                    "high": 4070.0,
                    "low": 4040.0,
                    "close": 4060.0,
                    "volume": 100.0,
                    "amount": 1000.0,
                }
            ],
            source_policy="tushare.stock_mins",
        )

        self.assertEqual(saved_count, 1)
        sql = "\n".join(call[1] for call in conn.cursor_obj.calls)
        self.assertIn("INSERT INTO index_minute_bars", sql)

        conn.cursor_obj.row_batches = [
            [
                {
                    "index_code": "sh000001",
                    "trade_date": "2026-05-29",
                    "period": "60",
                    "bar_time": "10:30:00",
                    "open": 4050.0,
                    "high": 4070.0,
                    "low": 4040.0,
                    "close": 4060.0,
                    "volume": 100.0,
                    "amount": 1000.0,
                    "source_policy": "tushare.stock_mins",
                    "source_run_id": 0,
                }
            ]
        ]

        rows = db.query_index_minute_bars("sh.000001", "2026-05-29", period="60")

        self.assertEqual(rows[0]["datetime"], "2026-05-29 10:30:00")
        self.assertEqual(rows[0]["data_source"], "postgresql.index_minute_bars")

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
                ("2026-05-29", "tomorrow_account_empty", "", None, True, "bool"),
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
        self.assertTrue(record["tomorrow_account_empty"])
        self.assertEqual(record["factor_snapshot"]["environment"]["score"], 80)
        self.assertEqual(record["factor_snapshot"]["selection"]["participation_mode"], "attack_50_ready")
        self.assertEqual(record["factor_snapshot"]["core_stocks"][0]["stock_name"], "大唐发电")

    def test_queries_tomorrow_action_history_from_final_decision_snapshot_fields(self):
        conn = _FakeConnection()
        conn.cursor_obj.row_batches = [
            [
                (
                    "2026-06-01",
                    "two_layer_decision_payload.next_day_action.final_object_identity",
                    "无",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-01",
                    "two_layer_decision_payload.next_day_action.position_stance",
                    "0%不参与",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-01",
                    "two_layer_decision_payload.next_day_action.stock.code",
                    "000001",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-01",
                    "two_layer_decision_payload.next_day_action.stock.name",
                    "残留旧标的",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-02",
                    "two_layer_decision_payload.next_day_action.final_object_identity",
                    "明日执行对象",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-02",
                    "two_layer_decision_payload.next_day_action.position_stance",
                    "50%条件执行",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-02",
                    "two_layer_decision_payload.next_day_action.stock.code",
                    "600584",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-02",
                    "two_layer_decision_payload.next_day_action.stock.name",
                    "长电科技",
                    None,
                    None,
                    "text",
                ),
                (
                    "2026-06-03",
                    "two_layer_decision_payload.tomorrow_account_action.action",
                    "empty",
                    None,
                    None,
                    "text",
                ),
                ("2026-06-04", None, None, None, None, None),
            ]
        ]
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        records = db.query_tomorrow_action_history(
            "2026-06-03",
            mode="frozen",
            limit=25,
        )

        self.assertEqual(
            ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"],
            [row["report_date"] for row in records],
        )
        self.assertEqual("no_trade", records[0]["action_type"])
        self.assertFalse(records[0]["can_new_entry"])
        self.assertEqual("execute", records[1]["action_type"])
        self.assertEqual("600584", records[1]["stock_code"])
        self.assertEqual("长电科技", records[1]["stock_name"])
        self.assertTrue(records[2]["tomorrow_account_empty"])
        self.assertEqual("", records[3]["action_type"])
        self.assertIsNone(records[3]["can_new_entry"])
        sql = conn.cursor_obj.calls[0][1]
        self.assertIn("LEFT JOIN strategy_factor_snapshot_fields", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertEqual(("frozen", "2026-06-03", 25, "frozen"), conn.cursor_obj.calls[0][2])

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
                "tag_distribution": {"光纤概念": 8, "共封装光学(CPO)": 7},
                "integrated_hot_list_sample_size": 50,
                "integrated_hot_list_sample_target": 50,
                "hot_rank_sample_size": 50,
                "hot_rank_sample_target": 50,
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
                "index_cross_validation": {
                    "schema_version": "report_index_cross_validation.v1",
                    "target_date": "2026-05-29",
                    "status": "success",
                    "verification_provider": "tencent.fqkline.day",
                    "checks": [
                        {
                            "name": "上证指数",
                            "code": "000001",
                            "status": "success",
                            "primary": {
                                "provider": "tushare.index_daily",
                                "trade_date": "2026-05-29",
                                "close": 4068.57,
                                "pre_close": 4060.0,
                                "change_pct": 0.21,
                            },
                            "verification": {
                                "provider": "tencent.fqkline.day",
                                "trade_date": "2026-05-29",
                                "close": 4068.57,
                                "pre_close": 4060.0,
                                "change_pct": 0.21,
                            },
                        }
                    ],
                    "failures": [],
                },
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
                "lhb_inst_detail": [
                    {
                        "trade_date": "2026-05-29",
                        "code": "002837",
                        "exalter": "机构专用",
                        "seat_type": "机构",
                        "net_buy_yi": 0.7,
                    }
                ],
                "lhb_inst_detail_status": "available",
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
        self.assertTrue(
            any(
                "index_cross_validation" in path
                and "checks" in path
                and "primary" in path
                and "trade_date" in path
                for path in field_paths
            )
        )
        self.assertTrue(
            any(
                "index_cross_validation" in path
                and "verification_provider" in path
                for path in field_paths
            )
        )
        self.assertTrue(any("tag_distribution" in path and "光纤概念" in path for path in field_paths))
        self.assertTrue(any("integrated_hot_list_sample_size" in path for path in field_paths))
        self.assertTrue(any("integrated_hot_list_sample_target" in path for path in field_paths))
        self.assertTrue(any("hot_rank_sample_size" in path for path in field_paths))
        self.assertTrue(any("hot_rank_sample_target" in path for path in field_paths))
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
        self.assertTrue(any("lhb_inst_detail" in path and "exalter" in path for path in field_paths))
        self.assertTrue(any("lhb_inst_detail_status" in path for path in field_paths))
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
            ("k:15:lhb_inst_detail/#0/k:4:code", "002837", None, None, "text"),
            ("k:15:lhb_inst_detail/#0/k:7:exalter", "机构专用", None, None, "text"),
            ("k:22:lhb_inst_detail_status", "available", None, None, "text"),
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
        self.assertEqual(loaded["data"]["lhb_inst_detail"][0]["exalter"], "机构专用")
        self.assertEqual(loaded["data"]["lhb_inst_detail_status"], "available")
        self.assertEqual(loaded["data"]["exchange_monitor_today"][0]["code"], "000001")
        self.assertEqual(loaded["data"]["exchange_monitor_nextday"][0]["code"], "000002")
        self.assertEqual(loaded["field_count"], 18)

    def test_index_validation_survives_fact_round_trip_and_preflight_rechecks_it(self):
        values = {
            "上证指数": ("000001", 3913.7940, 3996.1616, -2.0612),
            "深证成指": ("399001", 14522.8547, 15046.6695, -3.4813),
            "创业板指": ("399006", 3723.5166, 3842.7314, -3.1023),
            "中证全指": ("000985", 6001.6528, 6215.1138, -3.4345),
            "中证500": ("000905", 8138.1443, 8503.9705, -4.3018),
            "中证1000": ("000852", 7787.8529, 8198.3078, -5.0066),
        }

        def payload(name):
            code, close, pre_close, change_pct = values[name]
            return {
                "name": name,
                "code": code,
                "trade_date": "2026-07-13",
                "price": close,
                "close": close,
                "pre_close": pre_close,
                "change_pct": change_pct,
                "data_source": "tushare.index_daily",
            }

        data = {
            "indices": {
                "上证指数": payload("上证指数"),
                "深证成指": payload("深证成指"),
                "创业板指": payload("创业板指"),
            },
            "wind_a_alternative": payload("中证全指"),
            "csi500_index": payload("中证500"),
            "csi1000_index": payload("中证1000"),
            "data_status": {"指数交叉核对": True},
            "step_status": {"指数交叉核对": True},
        }
        verification = {}
        for spec in REPORT_INDEX_SPECS:
            primary = (
                data["indices"][spec["name"]]
                if spec["container_key"] == "indices"
                else data[spec["container_key"]]
            )
            verification[spec["tencent_symbol"]] = {
                "provider": "tencent.fqkline.day",
                "trade_date": "2026-07-13",
                "close": primary["close"],
                "pre_close": primary["pre_close"],
                "change_pct": primary["change_pct"],
            }
        data["index_cross_validation"] = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )

        def round_trip(source):
            conn = _FakeConnection()
            db = PostgresDailyFactDb(
                "postgresql://unit-test",
                connect=lambda: conn,
                ensure_schema=False,
            )
            db.save_daily_report_snapshot("2026-07-13", source)
            inserted = next(
                call[2]
                for call in conn.cursor_obj.calls
                if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
            )
            conn.cursor_obj.row_batches = [[tuple(row[1:6]) for row in inserted], [], []]
            return db.load_daily_report_snapshot("2026-07-13")["data"]

        restored = round_trip(data)
        restored_check = next(
            check
            for check in build_report_preflight(restored, "2026-07-13")["checks"]
            if check["label"] == "指数交叉核对"
        )
        self.assertEqual(restored_check["status"], "success")
        self.assertEqual(restored_check["value"], "6/6")

        contradictory = copy.deepcopy(data)
        contradictory["index_cross_validation"]["checks"][0]["code"] = "999999"
        restored_contradiction = round_trip(contradictory)
        contradiction_check = next(
            check
            for check in build_report_preflight(restored_contradiction, "2026-07-13")["checks"]
            if check["label"] == "指数交叉核对"
        )
        self.assertEqual(contradiction_check["status"], "failed")

    def test_save_daily_report_snapshot_derives_hot_tag_distribution_from_hot_rank_rows(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        db.save_daily_report_snapshot(
            "2026-06-08",
            {
                "integrated_hot_list": [
                    {"code": "600522", "name": "中天科技", "tags": ["光纤概念", "铜缆高速连接"]},
                    {"code": "600487", "name": "亨通光电", "concepts": ["光纤概念", "F5G概念"]},
                ],
                "hot_rank_top50": [
                    {"code": "600522", "name": "中天科技", "concepts": ["光纤概念"]},
                    {"code": "600487", "name": "亨通光电", "concepts": ["光纤概念"]},
                ],
            },
        )

        inserted = next(
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
        )
        field_paths = {row[1] for row in inserted}
        distribution_rows = [row for row in inserted if "tag_distribution" in row[1]]

        self.assertTrue(any("tag_distribution" in path and "光纤概念" in path for path in field_paths))
        self.assertTrue(any(row[3] == 2.0 for row in distribution_rows))
        self.assertTrue(any("integrated_hot_list_sample_size" in path for path in field_paths))
        self.assertTrue(any("integrated_hot_list_sample_target" in path for path in field_paths))
        self.assertTrue(any("hot_rank_sample_size" in path for path in field_paths))
        self.assertTrue(any("hot_rank_sample_target" in path for path in field_paths))

    def test_save_daily_report_snapshot_derives_hot_tags_from_largest_hot_rank_sample(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        db.save_daily_report_snapshot(
            "2026-06-08",
            {
                "integrated_hot_list": [{"code": "000001", "name": "小样本", "tags": ["小样本"]}],
                "hot_rank_top50": [
                    {"code": "600522", "name": "中天科技", "concepts": ["光纤概念"]},
                    {"code": "600487", "name": "亨通光电", "concepts": ["光纤概念"]},
                ],
            },
        )

        inserted = next(
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
        )
        distribution_rows = [row for row in inserted if "tag_distribution" in row[1]]

        self.assertTrue(any("光纤概念" in row[1] and row[3] == 2.0 for row in distribution_rows))
        self.assertFalse(any("小样本" in row[1] for row in distribution_rows))

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
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
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
            [],
            [],
        ]

        loaded = db.load_daily_report_snapshot("2026-05-29")

        self.assertEqual(loaded["data"]["sector_attack_evidence_rows"][0]["sector_name"], "通信设备")
        self.assertEqual(loaded["data"]["sector_attack_evidence_rows"][0]["sector_turnover"], 3062.15)
        history = loaded["data"]["recent_hot_sector_turnover_history"]
        self.assertEqual([row["sector_name"] for row in history], ["光通信/CPO", "通信设备"])
        self.assertEqual(history[1]["turnover_share_pct"], 9.17)

    def test_load_daily_report_snapshot_uses_structured_mainline_cycle_rows_when_wide_facts_empty(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        conn.cursor_obj.row_batches = [
            [],
            [
                (
                    "2026-06-03",
                    "电力",
                    "火电",
                    "",
                    "",
                    "主线扩散",
                    "电力",
                    "expand",
                    "强化",
                    0.8,
                    "电力承接强于大盘",
                    "mainline_daily",
                    0,
                ),
                (
                    "2026-06-04",
                    "电力",
                    "火电",
                    "",
                    "",
                    "主线扩散",
                    "电力",
                    "expand",
                    "强化",
                    0.82,
                    "大盘深跌时仍翻红",
                    "mainline_daily",
                    0,
                ),
            ],
            [
                (
                    "2026-06-03",
                    "06-01当周",
                    "wednesday",
                    "电力",
                    "火电",
                    "强化",
                    "当前周期",
                    "延续验证",
                    "扩散",
                    "观察核心承接",
                    "电力扩散验证",
                ),
                (
                    "2026-06-04",
                    "06-01当周",
                    "thursday",
                    "电力",
                    "火电",
                    "强化",
                    "当前周期",
                    "延续验证",
                    "扩散",
                    "观察核心承接",
                    "大盘深跌时电力承接延续",
                ),
            ],
            [
                (
                    "2026-06-04",
                    "当前周期",
                    "06-03 ~ 06-04",
                    2,
                    "电力",
                    "火电",
                    "延续验证",
                    "扩散",
                    "强化",
                    "观察核心承接",
                    "华电辽能翻红，电力线仍有承接",
                )
            ],
            [
                (
                    "2026-06-04",
                    "all_a",
                    10500.0,
                    5300,
                    "market_daily_totals",
                    0,
                )
            ],
            [(5400, 2600, 2500, 300, 80, 12)],
            [
                ("2026-06-04", "all_a", 1, "600578.SH", "600578", "京能电力", 90.0, 10500.0, 0.86, 0),
                ("2026-06-04", "all_a", 2, "001896.SZ", "001896", "豫能控股", 80.0, 10500.0, 0.76, 0),
            ],
            [("sh000985", "2026-06-04", 5000.0, 5100.0, 4980.0, 5088.8, 100.0, 200.0, "postgresql.index_daily_bars", 0)],
            [("sh000905", "2026-06-04", 5600.0, 5680.0, 5580.0, 5666.6, 100.0, 200.0, "postgresql.index_daily_bars", 0)],
            [("sh000852", "2026-06-04", 6000.0, 6120.0, 5980.0, 6108.6, 100.0, 200.0, "postgresql.index_daily_bars", 0)],
            [
                (
                    "2026-06-04",
                    "电力",
                    1,
                    12.6,
                    5,
                    2,
                    330.0,
                    10500.0,
                    3.14,
                    0.22,
                    "sector_attack_evidence_daily",
                    0,
                )
            ],
            [
                ("2026-06-03", "电力", 300.0, 10000.0, 3.0, "mainline_turnover_daily"),
                ("2026-06-04", "电力", 330.0, 10500.0, 3.14, "sector_attack_evidence_daily"),
            ],
            [],
            [],
        ]

        loaded = db.load_daily_report_snapshot("2026-06-04")

        data = loaded["data"]
        self.assertEqual(loaded["field_count"], 0)
        self.assertEqual(loaded["target_field_count"], 0)
        self.assertEqual(loaded["structured_counts"]["current_mainline_history_record"], 1)
        self.assertEqual(loaded["structured_counts"]["cycle_calendar_rows"], 1)
        self.assertEqual(loaded["structured_counts"]["cycle_interpretation_rows"], 1)
        self.assertEqual(loaded["structured_counts"]["sector_attack_evidence_rows"], 1)
        self.assertEqual(loaded["structured_counts"]["market_daily_total"], 1)
        self.assertEqual(loaded["structured_counts"]["market_stats_from_quotes"], 1)
        self.assertEqual(loaded["structured_counts"]["turnover_rank_daily"], 2)
        self.assertEqual(loaded["structured_counts"]["wind_a_alternative_index_daily_bar"], 1)
        self.assertEqual(loaded["structured_counts"]["csi500_index_daily_bar"], 1)
        self.assertEqual(loaded["structured_counts"]["csi1000_index_daily_bar"], 1)
        self.assertGreaterEqual(loaded["structured_fact_count"], 7)
        self.assertEqual(data["current_mainline_history_record"]["primary_mainline"], "电力")
        self.assertEqual(data["recent_mainline_history"][0]["date"], "2026-06-03")
        self.assertEqual(data["cycle_calendar_rows"][0]["wednesday"]["mainline"], "电力")
        self.assertEqual(data["cycle_calendar_rows"][0]["thursday"]["state"], "强化")
        self.assertEqual(data["cycle_interpretation_rows"][0]["attack_line"], "火电")
        self.assertEqual(data["market_stats"]["up_count"], 2600)
        self.assertEqual(data["market_stats"]["trade_date"], "2026-06-04")
        self.assertEqual(data["market_stats"]["source_date"], "2026-06-04")
        self.assertEqual(data["turnover_rank"][0]["code"], "600578")
        self.assertEqual(data["wind_a_alternative"]["price"], 5088.8)
        self.assertEqual(data["csi500_index"]["price"], 5666.6)
        self.assertEqual(data["csi1000_index"]["price"], 6108.6)
        self.assertEqual(data["sector_attack_evidence_rows"][0]["sector_name"], "电力")
        self.assertEqual(data["recent_hot_sector_turnover_history"][-1]["turnover_share_pct"], 3.14)

    def test_load_daily_report_snapshot_market_total_only_does_not_count_as_target_spine(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        conn.cursor_obj.row_batches = [
            [],
            [],
            [],
            [],
            [
                (
                    "2026-06-08",
                    "all_a",
                    28234.29,
                    5515,
                    "stock_sum",
                    0,
                )
            ],
            [(5515, 899, 4591, 25, 82, 86)],
            [
                ("2026-06-08", "all_a", 1, "300308.SZ", "300308", "", 389.23, 28234.29, 1.38, 0),
            ],
            [],
            [],
            [],
            [],
            [],
            [],
        ]

        loaded = db.load_daily_report_snapshot("2026-06-08")

        self.assertEqual(loaded["field_count"], 0)
        self.assertEqual(loaded["target_field_count"], 0)
        self.assertEqual(loaded["structured_counts"]["market_daily_total"], 1)
        self.assertEqual(loaded["structured_counts"]["market_stats_from_quotes"], 1)
        self.assertEqual(loaded["structured_counts"]["turnover_rank_daily"], 1)
        self.assertEqual(loaded["target_structured_fact_count"], 0)
        self.assertEqual(loaded["data"]["total_turnover"], 28234.29)
        self.assertEqual(loaded["data"]["market_stats"]["down_count"], 4591)
        self.assertEqual(loaded["data"]["turnover_rank"][0]["code"], "300308")

    def test_load_daily_report_snapshot_does_not_treat_history_only_rows_as_target_facts(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        conn.cursor_obj.row_batches = [
            [],
            [
                (
                    "2026-05-29",
                    "通信设备",
                    "光通信",
                    "",
                    "",
                    "主线延续",
                    "通信设备",
                    "trend",
                    "强化",
                    0.8,
                    "历史主线记录",
                    "mainline_daily",
                    0,
                ),
            ],
            [
                (
                    "2026-05-29",
                    "05-25当周",
                    "friday",
                    "通信设备",
                    "光通信",
                    "强化",
                    "上一周期",
                    "延续",
                    "",
                    "",
                    "历史周期记录",
                ),
            ],
            [],
            [],
            [],
            [
                ("2026-05-29", "通信设备", 3062.15, 33408.58, 9.17, "mainline_turnover_daily"),
            ],
            [],
            [],
        ]

        loaded = db.load_daily_report_snapshot("2026-06-04")

        self.assertEqual(loaded["field_count"], 0)
        self.assertEqual(loaded["target_field_count"], 0)
        self.assertEqual(loaded["structured_counts"]["current_mainline_history_record"], 0)
        self.assertGreater(loaded["structured_counts"]["recent_mainline_history"], 0)
        self.assertGreater(loaded["structured_counts"]["cycle_calendar_rows"], 0)
        self.assertEqual(loaded["target_structured_fact_count"], 0)

    def test_load_daily_report_snapshot_shell_fields_do_not_count_as_target_fields(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        conn.cursor_obj.row_batches = [
            [
                ("k:13:postgres_only", "", None, True, "bool"),
            ],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        ]

        loaded = db.load_daily_report_snapshot("2026-06-04")

        self.assertEqual(loaded["field_count"], 1)
        self.assertEqual(loaded["target_field_count"], 0)
        self.assertEqual(loaded["target_structured_fact_count"], 0)

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
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [("2026-05-29", 1, "public", "2026-05-29T15:30:00", "reports/replay.md", "full")],
            [("601991", "大唐发电", "T0", "新型电力", "电力", "继续观察", "结构化轨迹完整", "触发条件", "失败条件")],
            [],
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

    def test_save_daily_report_snapshot_preserves_sector_first_runtime_packets(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )
        selection_workflow = {
            "schema_version": "selection_workflow.v1",
            "derivation_contract": "sector_first_strict.v1",
            "nodes": [
                {"id": "N1", "summary": "市场分歧，继续看板块"},
                {"id": "N7", "summary": "价格未形成买入资格"},
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action": "0%不参与",
            },
        }
        final_target_resolution = {
            "schema_version": "final_target_resolution.v1",
            "capital_priority_decision": {
                "capital_priority": "wait",
                "reason": "条件未满足",
            },
            "final_action": {
                "position_pct": 0,
                "action": "0%不参与",
            },
        }
        two_layer_payload = {
            "schema_version": "two_layer_decision_payload.v1",
            "final_object": {"identity": "无"},
        }
        sniper_packet = {
            "schema_version": "sniper_target_derivation.v1",
            "canonical_target": {},
            "final_action": {"position_pct": 0, "action": "0%不参与"},
        }

        db.save_daily_report_snapshot(
            "2026-06-11",
            {
                "selection_workflow": selection_workflow,
                "final_target_resolution": final_target_resolution,
                "two_layer_decision_payload": two_layer_payload,
                "sniper_target_derivation": sniper_packet,
                "execution_stage_context": {
                    "selection_workflow": selection_workflow,
                    "final_target_resolution": final_target_resolution,
                    "two_layer_decision_payload": two_layer_payload,
                    "sniper_target_derivation": sniper_packet,
                },
                "market_research_snapshot": {
                    "selection_workflow": selection_workflow,
                    "final_target_resolution": final_target_resolution,
                    "two_layer_decision_payload": two_layer_payload,
                    "sniper_target_derivation": sniper_packet,
                },
            },
        )

        inserted = next(
            call[2]
            for call in conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
        )
        field_paths = {row[1] for row in inserted}

        self.assertTrue(any("selection_workflow" in path and "derivation_contract" in path for path in field_paths))
        self.assertTrue(any("selection_workflow" in path and "final" in path and "position_pct" in path for path in field_paths))
        self.assertTrue(any("final_target_resolution" in path and "capital_priority_decision" in path for path in field_paths))
        self.assertTrue(any("two_layer_decision_payload" in path and "final_object" in path for path in field_paths))
        self.assertTrue(any("sniper_target_derivation" in path and "final_action" in path for path in field_paths))
        self.assertTrue(any("execution_stage_context" in path and "selection_workflow" in path for path in field_paths))
        self.assertTrue(any("market_research_snapshot" in path and "final_target_resolution" in path for path in field_paths))

    def test_market_language_writer_uses_exact_source_policy_and_round_trips_structure(self):
        projection = build_market_language_source_projection(
            {
                "market_stats": {
                    "up_count": 900,
                    "down_count": 3600,
                    "flat_count": 100,
                    "trade_date": "2026-07-10",
                }
            },
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        write_conn = _FakeConnection()
        writer = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: write_conn,
            ensure_schema=False,
        )

        result = writer.replace_market_language_translation_artifact(artifact)

        delete_call = next(
            call
            for call in write_conn.cursor_obj.calls
            if call[0] == "execute" and "DELETE FROM daily_report_fact_fields" in call[1]
        )
        self.assertIn("source_policy = %s", delete_call[1])
        self.assertNotIn("LIKE", delete_call[1])
        self.assertEqual(delete_call[2], ("2026-07-10", MARKET_LANGUAGE_SOURCE_POLICY))
        inserted = next(
            call[2]
            for call in write_conn.cursor_obj.calls
            if call[0] == "executemany" and "INSERT INTO daily_report_fact_fields" in call[1]
        )
        self.assertEqual(result["field_count"], len(inserted))
        self.assertTrue(all(row[-1] == MARKET_LANGUAGE_SOURCE_POLICY for row in inserted))

        read_conn = _FakeConnection()
        read_conn.cursor_obj.rows = [
            (row[1], row[2], row[3], row[4], row[5])
            for row in inserted
        ]
        reader = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: read_conn,
            ensure_schema=False,
        )
        loaded = reader.load_market_language_translation_artifact("2026-07-10")

        select_call = next(
            call
            for call in read_conn.cursor_obj.calls
            if call[0] == "execute" and "SELECT field_path" in call[1]
        )
        self.assertIn("source_policy = %s", select_call[1])
        self.assertEqual(select_call[2], ("2026-07-10", MARKET_LANGUAGE_SOURCE_POLICY))
        self.assertEqual(
            canonical_market_language_hash(loaded),
            canonical_market_language_hash(artifact),
        )

    def test_whole_day_save_and_load_exclude_market_language_source_policy(self):
        save_conn = _FakeConnection()
        saver = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: save_conn,
            ensure_schema=False,
        )

        saver.save_daily_report_snapshot("2026-07-10", {"total_turnover": 12345.0})

        delete_call = next(
            call
            for call in save_conn.cursor_obj.calls
            if call[0] == "execute" and "DELETE FROM daily_report_fact_fields" in call[1]
        )
        self.assertIn("source_policy <> %s", delete_call[1])
        self.assertEqual(delete_call[2], ("2026-07-10", MARKET_LANGUAGE_SOURCE_POLICY))

        load_conn = _FakeConnection()
        load_conn.cursor_obj.row_batches = [
            [("k:14:total_turnover", "", 12345.0, None, "number")],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        ]
        loader = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: load_conn,
            ensure_schema=False,
        )
        loaded = loader.load_daily_report_snapshot("2026-07-10")
        select_call = next(
            call
            for call in load_conn.cursor_obj.calls
            if call[0] == "execute" and "SELECT field_path" in call[1]
        )
        self.assertIn("source_policy <> %s", select_call[1])
        self.assertEqual(select_call[2], ("2026-07-10", MARKET_LANGUAGE_SOURCE_POLICY))
        self.assertNotIn("market_language_translation", loaded["data"])

    def test_daily_report_fact_coverage_does_not_count_market_language_rows_as_report_spine(self):
        conn = _FakeConnection()
        db = PostgresDailyFactDb(
            "postgresql://unit-test",
            connect=lambda: conn,
            ensure_schema=False,
        )

        db.daily_report_fact_coverage("2026-07-10")

        coverage_call = next(
            call
            for call in conn.cursor_obj.calls
            if call[0] == "execute" and "FROM daily_report_fact_fields" in call[1]
        )
        self.assertIn("source_policy <> %s", coverage_call[1])
        self.assertEqual(
            coverage_call[2],
            ("2026-07-10", MARKET_LANGUAGE_SOURCE_POLICY),
        )


@unittest.skipUnless(
    os.environ.get("A_DAILY_REPORT_RUN_POSTGRES_INTEGRATION") == "1",
    "set A_DAILY_REPORT_RUN_POSTGRES_INTEGRATION=1 to run PostgreSQL integration",
)
class PostgresMarketLanguageIntegrationTest(unittest.TestCase):
    database_url = os.environ.get("A_DAILY_REPORT_DATABASE_URL") or (
        "postgresql:///a_daily_report_psql_529"
    )
    trade_date = "2099-12-30"

    def setUp(self):
        self.db = PostgresDailyFactDb(self.database_url, ensure_schema=False)
        self._delete_test_rows()

    def tearDown(self):
        self._delete_test_rows()

    def _delete_test_rows(self):
        with self.db._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM daily_report_fact_fields WHERE trade_date = %s",
                    (self.trade_date,),
                )
            conn.commit()

    def test_artifact_survives_whole_day_resave_in_same_database(self):
        projection = build_market_language_source_projection(
            {
                "market_stats": {
                    "up_count": 900,
                    "down_count": 3600,
                    "flat_count": 100,
                    "trade_date": self.trade_date,
                    "query_date": self.trade_date,
                }
            },
            target_date=self.trade_date,
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date=self.trade_date,
            analysis_mode="fresh",
        )

        self.db.replace_market_language_translation_artifact(artifact)
        before_resave = self.db.load_market_language_translation_artifact(
            self.trade_date
        )
        self.db.save_daily_report_snapshot(
            self.trade_date,
            {"total_turnover": 12345.0, "source_date": self.trade_date},
        )
        after_resave = self.db.load_market_language_translation_artifact(
            self.trade_date
        )

        expected_hash = canonical_market_language_hash(artifact)
        self.assertEqual(canonical_market_language_hash(before_resave), expected_hash)
        self.assertEqual(canonical_market_language_hash(after_resave), expected_hash)


if __name__ == "__main__":
    unittest.main()
