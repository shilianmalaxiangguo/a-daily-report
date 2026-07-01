from __future__ import annotations

import os
import subprocess

from storage.postgres_daily_fact_db import PostgresDailyFactDb

__all__ = [
    "DatabaseService",
]


_DEFAULT_LOCAL_POSTGRES_DATABASES = ("a_daily_report_psql_529",)


def _postgres_url_from_environment():
    database_url = (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if database_url.startswith(("postgres://", "postgresql://")):
        return database_url
    return ""


def _postgres_only_runtime_configured():
    return os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1"


def _local_postgres_database_exists(database_name):
    database_name = str(database_name or "").strip()
    if not database_name:
        return False
    try:
        result = subprocess.run(
            ["psql", "-d", database_name, "-Atqc", "select 1"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


class DatabaseService:
    """Application-facing database service facade.

    The fact store is PostgreSQL-backed. When PostgreSQL is unavailable, the
    facade returns an empty service instead of falling back to retired local
    database files.
    """

    def __init__(self, repository):
        self.repository = repository

    @classmethod
    def postgres(cls, database_url):
        return cls(PostgresDailyFactDb(database_url))

    @classmethod
    def from_environment(cls, db_path=None):
        database_url = _postgres_url_from_environment()
        if database_url:
            return cls(PostgresDailyFactDb(database_url))
        checker = _local_postgres_database_exists
        for database_name in _DEFAULT_LOCAL_POSTGRES_DATABASES:
            if checker(database_name):
                return cls(PostgresDailyFactDb(f"postgresql:///{database_name}"))
        return cls(None)

    @classmethod
    def postgres_from_environment_or_local_default(
        cls,
        *,
        local_database_names=None,
        database_exists=None,
    ):
        database_url = _postgres_url_from_environment()
        if database_url:
            return cls(PostgresDailyFactDb(database_url))
        checker = database_exists or _local_postgres_database_exists
        for database_name in local_database_names or _DEFAULT_LOCAL_POSTGRES_DATABASES:
            if checker(database_name):
                return cls(PostgresDailyFactDb(f"postgresql:///{database_name}"))
        return cls(None)

    @classmethod
    def fact_store_from_environment(
        cls,
        db_path=None,
        *,
        local_database_names=None,
        database_exists=None,
    ):
        service = cls.postgres_from_environment_or_local_default(
            local_database_names=local_database_names,
            database_exists=database_exists,
        )
        if getattr(service, "repository", None) is not None:
            return service
        return service

    def is_postgres_backed(self):
        checker = getattr(self.repository, "is_postgres_backed", None)
        return bool(callable(checker) and checker())

    def get_runtime_cache_entry(self, namespace, cache_key, target_date=""):
        reader = getattr(self.repository, "get_runtime_cache_entry", None)
        if not callable(reader):
            return None
        return reader(namespace, cache_key, target_date)

    def set_runtime_cache_entry(self, namespace, cache_key, target_date, payload, *, source="", ttl_seconds=None):
        writer = getattr(self.repository, "set_runtime_cache_entry", None)
        if not callable(writer):
            return False
        return writer(
            namespace,
            cache_key,
            target_date,
            payload,
            source=source,
            ttl_seconds=ttl_seconds,
        )

    def delete_expired_runtime_cache_entries(self):
        deleter = getattr(self.repository, "delete_expired_runtime_cache_entries", None)
        if not callable(deleter):
            return 0
        return deleter()

    def get_runtime_cache_stats(self, namespace, target_date=""):
        reader = getattr(self.repository, "get_runtime_cache_stats", None)
        if not callable(reader):
            return {"count": 0, "size_mb": 0.0}
        return reader(namespace, target_date)

    def save_provider_source_run(self, run):
        return self.repository.save_provider_source_run(run)

    def upsert_stock_daily_quotes_recent(self, rows, *, source_run_id=0):
        return self.repository.upsert_stock_daily_quotes_recent(rows, source_run_id=source_run_id)

    def query_stock_daily_quotes_recent(self, trade_date, stock_codes=None):
        reader = getattr(self.repository, "query_stock_daily_quotes_recent", None)
        if not callable(reader):
            return []
        return reader(trade_date, stock_codes=stock_codes)

    def rebuild_market_daily_total(self, trade_date, *, market_scope="all_a", source_run_id=0):
        return self.repository.rebuild_market_daily_total(
            trade_date,
            market_scope=market_scope,
            source_run_id=source_run_id,
        )

    def upsert_market_daily_total(self, row):
        return self.repository.upsert_market_daily_total(row)

    def query_market_daily_total(self, trade_date, *, market_scope="all_a"):
        return self.repository.query_market_daily_total(
            trade_date,
            market_scope=market_scope,
        )

    def upsert_index_daily_bars(self, index_code, rows, *, source_policy="", source_run_id=0):
        writer = getattr(self.repository, "upsert_index_daily_bars", None)
        if not callable(writer):
            return 0
        return writer(index_code, rows, source_policy=source_policy, source_run_id=source_run_id)

    def query_index_daily_bars(self, index_code, end_date, *, window_days=250):
        reader = getattr(self.repository, "query_index_daily_bars", None)
        if not callable(reader):
            return []
        return reader(index_code, end_date, window_days=window_days)

    def upsert_index_minute_bars(self, index_code, trade_date, period, rows, *, source_policy="", source_run_id=0):
        writer = getattr(self.repository, "upsert_index_minute_bars", None)
        if not callable(writer):
            return 0
        return writer(
            index_code,
            trade_date,
            period,
            rows,
            source_policy=source_policy,
            source_run_id=source_run_id,
        )

    def query_index_minute_bars(self, index_code, trade_date, *, period="60"):
        reader = getattr(self.repository, "query_index_minute_bars", None)
        if not callable(reader):
            return []
        return reader(index_code, trade_date, period=period)

    def query_market_breadth_counts(self, trade_date):
        return self.repository.query_market_breadth_counts(trade_date)

    def rebuild_turnover_rank_daily(self, trade_date, *, rank_scope="all_a", rank_limit=100, source_run_id=0):
        return self.repository.rebuild_turnover_rank_daily(
            trade_date,
            rank_scope=rank_scope,
            rank_limit=rank_limit,
            source_run_id=source_run_id,
        )

    def query_top_turnover_share_series(self, end_date, *, window_days=30, limit=50, rank_scope="all_a"):
        return self.repository.query_top_turnover_share_series(
            end_date,
            window_days=window_days,
            limit=limit,
            rank_scope=rank_scope,
        )

    def query_turnover_rank_rows(self, trade_date, *, limit=50, rank_scope="all_a"):
        return self.repository.query_turnover_rank_rows(
            trade_date,
            limit=limit,
            rank_scope=rank_scope,
        )

    def save_turnover_share_series(self, payload):
        return self.repository.save_turnover_share_series(payload)

    def upsert_mainline_daily(self, row):
        return self.repository.upsert_mainline_daily(row)

    def query_mainline_daily_series(self, end_date, *, window_days=25):
        return self.repository.query_mainline_daily_series(end_date, window_days=window_days)

    def upsert_mainline_turnover_daily(self, row):
        return self.repository.upsert_mainline_turnover_daily(row)

    def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
        return self.repository.query_mainline_turnover_series(
            end_date,
            sector_name,
            window_days=window_days,
        )

    def upsert_sector_fund_flow_daily(self, row):
        return self.repository.upsert_sector_fund_flow_daily(row)

    def query_sector_fund_flow_series(self, end_date, sector_name, *, window_days=8):
        return self.repository.query_sector_fund_flow_series(
            end_date,
            sector_name,
            window_days=window_days,
        )

    def upsert_price_band_style_daily(self, row):
        return self.repository.upsert_price_band_style_daily(row)

    def query_price_band_style_series(self, end_date, *, window_days=25):
        return self.repository.query_price_band_style_series(end_date, window_days=window_days)

    def upsert_margin_pressure_daily(self, row):
        return self.repository.upsert_margin_pressure_daily(row)

    def query_margin_pressure_series(self, end_date, *, window_days=25):
        return self.repository.query_margin_pressure_series(end_date, window_days=window_days)

    def upsert_new_high_feedback_daily(self, row):
        return self.repository.upsert_new_high_feedback_daily(row)

    def query_new_high_feedback_series(self, end_date, *, window_days=25):
        return self.repository.query_new_high_feedback_series(end_date, window_days=window_days)

    def build_new_high_feedback_from_recent_quotes(self, trade_date, **kwargs):
        builder = getattr(self.repository, "build_new_high_feedback_from_recent_quotes", None)
        if not callable(builder):
            return {}
        return builder(trade_date, **kwargs)

    def delete_new_high_feedback_outside_dates(self, valid_dates, *, end_date=None):
        delete_fn = getattr(self.repository, "delete_new_high_feedback_outside_dates", None)
        if not callable(delete_fn):
            return 0
        return delete_fn(valid_dates, end_date=end_date)

    def upsert_extreme_conviction_mentions(self, rows):
        return self.repository.upsert_extreme_conviction_mentions(rows)

    def replace_extreme_conviction_mentions_for_trade_date(self, trade_date, rows):
        return self.repository.replace_extreme_conviction_mentions_for_trade_date(trade_date, rows)

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        return self.repository.query_extreme_conviction_mentions(
            end_date,
            window_days=window_days,
            include_a_kill=include_a_kill,
        )

    def mark_a_kill_shape_extreme_conviction_mentions(self, end_date, *, window_days=25, return_details=False):
        marker = getattr(self.repository, "mark_a_kill_shape_extreme_conviction_mentions", None)
        if not callable(marker):
            if return_details:
                return {"updated_count": 0, "updated_records": []}
            return 0
        return marker(end_date, window_days=window_days, return_details=return_details)

    def replace_market_cycle_context(self, trade_date, snapshot):
        writer = getattr(self.repository, "replace_market_cycle_context", None)
        if not callable(writer):
            return {}
        return writer(trade_date, snapshot)

    def replace_observation_pool_items_for_trade_date(self, trade_date, pools):
        writer = getattr(self.repository, "replace_observation_pool_items_for_trade_date", None)
        if not callable(writer):
            return 0
        return writer(trade_date, pools)

    def load_tracking_memory_state(self):
        reader = getattr(self.repository, "load_tracking_memory_state", None)
        if not callable(reader):
            return {}
        return reader()

    def save_tracking_memory_state(self, state):
        writer = getattr(self.repository, "save_tracking_memory_state", None)
        if not callable(writer):
            return 0
        return writer(state)

    def replace_decision_ledger_snapshot(self, snapshot):
        writer = getattr(self.repository, "replace_decision_ledger_snapshot", None)
        if not callable(writer):
            return {}
        return writer(snapshot)

    def read_decision_ledger_index(self, end_date=None, window_days=25):
        reader = getattr(self.repository, "read_decision_ledger_index", None)
        if not callable(reader):
            return {}
        return reader(end_date=end_date, window_days=window_days)

    def query_a_kill_cooling_records(self):
        reader = getattr(self.repository, "query_a_kill_cooling_records", None)
        if not callable(reader):
            return []
        return reader()

    def replace_a_kill_cooling_records(self, records):
        writer = getattr(self.repository, "replace_a_kill_cooling_records", None)
        if not callable(writer):
            return 0
        return writer(records)

    def query_active_a_kill_cooling_records(self, target_date):
        reader = getattr(self.repository, "query_active_a_kill_cooling_records", None)
        if not callable(reader):
            return []
        return reader(target_date)

    def load_strategy_performance_ledger(self, mode="frozen"):
        reader = getattr(self.repository, "load_strategy_performance_ledger", None)
        if not callable(reader):
            return {}
        return reader(mode=mode)

    def save_strategy_performance_ledger(self, ledger, mode="frozen"):
        writer = getattr(self.repository, "save_strategy_performance_ledger", None)
        if not callable(writer):
            return ""
        return writer(ledger, mode=mode)

    def save_factor_snapshot(self, target_date, factor_snapshot, mode="frozen"):
        writer = getattr(self.repository, "save_factor_snapshot", None)
        if not callable(writer):
            return {"path": "", "mode": mode, "saved": False}
        return writer(target_date, factor_snapshot, mode=mode)

    def replace_candidate_trace_artifact(self, payload):
        writer = getattr(self.repository, "replace_candidate_trace_artifact", None)
        if not callable(writer):
            return {}
        return writer(payload)

    def load_candidate_trace_artifact(self, trade_date):
        reader = getattr(self.repository, "load_candidate_trace_artifact", None)
        if not callable(reader):
            return {}
        return reader(trade_date)

    def save_daily_report_snapshot(self, trade_date, data):
        writer = getattr(self.repository, "save_daily_report_facts", None)
        if not callable(writer):
            writer = getattr(self.repository, "save_daily_report_snapshot", None)
        if not callable(writer):
            return {"source": "", "field_count": 0}
        return writer(trade_date, data)

    def load_daily_report_snapshot(self, trade_date):
        reader = getattr(self.repository, "load_daily_report_facts", None)
        if not callable(reader):
            reader = getattr(self.repository, "load_daily_report_snapshot", None)
        if not callable(reader):
            return {}
        return reader(trade_date)

    def daily_report_fact_coverage(self, trade_date):
        reader = getattr(self.repository, "daily_report_fact_coverage", None)
        if not callable(reader):
            return {}
        return reader(trade_date)

    def import_daily_report_facts(self, trade_date, data):
        writer = getattr(self.repository, "import_daily_report_facts", None)
        if not callable(writer):
            return self.save_daily_report_snapshot(trade_date, data)
        return writer(trade_date, data)

    def upsert_monthly_account_ledger(self, row):
        return self.repository.upsert_monthly_account_ledger(row)

    def query_monthly_account_ledger(self, end_date, *, account_id="main"):
        return self.repository.query_monthly_account_ledger(end_date, account_id=account_id)

    def save_report_artifact(self, artifact):
        return self.repository.save_report_artifact(artifact)

    def get_report_artifacts(self):
        return self.repository.get_report_artifacts()
