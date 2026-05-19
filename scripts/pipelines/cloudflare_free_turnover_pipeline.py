from __future__ import annotations

from export.cloudflare_free_json_export import CloudflareFreeJsonExportService
from market_data.service import MarketDataService
from storage.database_service import DatabaseService

__all__ = [
    "TurnoverPipelineDataUnavailableError",
    "run_turnover_pipeline",
]


class TurnoverPipelineDataUnavailableError(RuntimeError):
    pass


def run_turnover_pipeline(
    trade_date,
    *,
    db_path=None,
    artifact_root,
    pro=None,
    market_data_service=None,
    database_service=None,
    rank_limit=100,
    export_limit=50,
    window_days=25,
):
    market_data_service = market_data_service or MarketDataService(pro=pro)
    database_service = database_service or DatabaseService.sqlite_d1_compatible(db_path)
    warnings = []
    rows = market_data_service.get_stock_daily_turnover_records(trade_date)
    run_id = database_service.save_provider_source_run(
        {
            "trade_date": trade_date,
            "provider": "tushare",
            "endpoint": "daily",
            "status": "success" if rows else "empty",
            "row_count": len(rows),
        }
    )
    if not rows:
        raise TurnoverPipelineDataUnavailableError(
            f"Tushare daily returned no turnover rows for {trade_date}; aborting Top50 turnover export"
        )
    quote_count = database_service.upsert_stock_daily_quotes_recent(rows, source_run_id=run_id)
    market_total = database_service.rebuild_market_daily_total(trade_date, source_run_id=run_id)
    ranks = database_service.rebuild_turnover_rank_daily(trade_date, rank_limit=rank_limit, source_run_id=run_id)
    industry_map_loader = getattr(market_data_service, "get_stock_industry_map", None)
    stock_industry_map = industry_map_loader() if callable(industry_map_loader) else {}
    name_map_loader = getattr(market_data_service, "get_stock_name_map", None)
    stock_name_map = name_map_loader() if callable(name_map_loader) else {}
    moneyflow_loader = getattr(market_data_service, "get_stock_moneyflow_map", None)
    try:
        stock_moneyflow_map = moneyflow_loader(trade_date) if callable(moneyflow_loader) else {}
    except Exception as error:
        warnings.append(f"moneyflow unavailable: {error}")
        stock_moneyflow_map = {}
    export_result = CloudflareFreeJsonExportService(
        database_service,
        artifact_root=artifact_root,
    ).export_turnover_share_series(
        trade_date,
        window_days=window_days,
        limit=export_limit,
        stock_industry_map=stock_industry_map,
        stock_moneyflow_map=stock_moneyflow_map,
        stock_name_map=stock_name_map,
    )
    return {
        "trade_date": trade_date,
        "source_run_id": run_id,
        "quote_count": quote_count,
        "market_total": market_total,
        "rank_count": len(ranks),
        "export": export_result,
        "warnings": warnings,
    }
