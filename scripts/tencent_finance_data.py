from __future__ import annotations

from legacy_runtime_shim import export_or_default


class _TencentFinanceDataFallback:
    def get_calendar_events(self, target_date=None):
        return []

    def get_stock_batch_info(self, codes):
        return {}

    def get_xuangubao_news(self, pages=5):
        return []

    def get_xuangubao_plates(self):
        return []


TencentFinanceData = export_or_default("tencent_finance_data", "TencentFinanceData", _TencentFinanceDataFallback)

__all__ = ["TencentFinanceData"]
