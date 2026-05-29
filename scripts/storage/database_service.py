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

    def upsert_market_daily_total(self, row):
        return self.repository.upsert_market_daily_total(row)

    def query_market_daily_total(self, trade_date, *, market_scope="all_a"):
        return self.repository.query_market_daily_total(
            trade_date,
            market_scope=market_scope,
        )

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

    def upsert_monthly_account_ledger(self, row):
        return self.repository.upsert_monthly_account_ledger(row)

    def query_monthly_account_ledger(self, end_date, *, account_id="main"):
        return self.repository.query_monthly_account_ledger(end_date, account_id=account_id)

    def save_report_artifact(self, artifact):
        return self.repository.save_report_artifact(artifact)

    def get_report_artifacts(self):
        return self.repository.get_report_artifacts()
