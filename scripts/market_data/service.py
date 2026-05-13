from __future__ import annotations

from market_data.tushare_turnover_service import (
    fetch_stock_daily_turnover_records,
    fetch_stock_industry_map,
    fetch_stock_moneyflow_map,
    fetch_stock_name_map,
)

__all__ = [
    "MarketDataService",
]


class MarketDataService:
    """Provider-facing market data service; Tushare is the default provider."""

    def __init__(self, *, pro=None, ts_module=None):
        self.pro = pro
        self.ts_module = ts_module

    def get_stock_daily_turnover_records(self, trade_date):
        return fetch_stock_daily_turnover_records(
            trade_date,
            pro=self.pro,
            ts_module=self.ts_module,
        )

    def get_stock_industry_map(self):
        return fetch_stock_industry_map(
            pro=self.pro,
            ts_module=self.ts_module,
        )

    def get_stock_moneyflow_map(self, trade_date):
        return fetch_stock_moneyflow_map(
            trade_date,
            pro=self.pro,
            ts_module=self.ts_module,
        )

    def get_stock_name_map(self):
        return fetch_stock_name_map(
            pro=self.pro,
            ts_module=self.ts_module,
        )
