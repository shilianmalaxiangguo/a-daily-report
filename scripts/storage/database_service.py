from __future__ import annotations

from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

__all__ = [
    "DatabaseService",
]


class DatabaseService:
    """Application-facing database service facade.

    The first implementation is SQLite-backed and mirrors the Cloudflare D1
    schema; callers should depend on this facade instead of the concrete store.
    """

    def __init__(self, repository):
        self.repository = repository

    @classmethod
    def sqlite_d1_compatible(cls, db_path=None):
        return cls(CloudflareFreeDailyDb(db_path))

    def save_provider_source_run(self, run):
        return self.repository.save_provider_source_run(run)

    def upsert_stock_daily_quotes_recent(self, rows, *, source_run_id=0):
        return self.repository.upsert_stock_daily_quotes_recent(rows, source_run_id=source_run_id)

    def rebuild_market_daily_total(self, trade_date, *, market_scope="all_a", source_run_id=0):
        return self.repository.rebuild_market_daily_total(
            trade_date,
            market_scope=market_scope,
            source_run_id=source_run_id,
        )

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

    def save_report_artifact(self, artifact):
        return self.repository.save_report_artifact(artifact)

    def get_report_artifacts(self):
        return self.repository.get_report_artifacts()
