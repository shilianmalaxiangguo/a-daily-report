from __future__ import annotations

import re

from diagnostics.helper_diagnostics_runtime import record_helper_log

__all__ = [
    "get_stock_sector",
    "get_stock_status",
]

_stock_industry_cache = {}
_eastmoney_warning_emitted = False


def get_stock_status(stock_name, stock_code, zt_pool, dt_pool, change_pct=None):
    """Return formatted limit-up/down status with optional change percentage."""
    if zt_pool:
        for stock in zt_pool:
            if stock.get("代码") == stock_code or stock.get("名称") == stock_name:
                zt_type = stock.get("涨停统计", "")
                if change_pct is not None:
                    if zt_type:
                        return f"{change_pct:+.2f}% 涨停({zt_type})"
                    return f"{change_pct:+.2f}% 涨停"
                if zt_type:
                    return f"涨停({zt_type})"
                return "涨停"

    if dt_pool:
        for stock in dt_pool:
            if stock.get("代码") == stock_code or stock.get("名称") == stock_name:
                if change_pct is not None:
                    return f"{change_pct:+.2f}% 跌停"
                return "跌停"

    if change_pct is not None:
        return f"{change_pct:+.2f}%"
    return "-"


def _resolve_market_code(pure_code):
    if pure_code.startswith("0") or pure_code.startswith("3"):
        return "SZ"
    if pure_code.startswith("68"):
        return "SH"
    if pure_code.startswith("6"):
        return "SH"
    if pure_code.startswith("8") or pure_code.startswith("9"):
        return "BJ"
    return "SH"


def get_stock_sector(
    stock_name,
    stock_code,
    hot_rank_data=None,
    zt_pool_data=None,
    lianban_data=None,
    lhb_data=None,
    sector_fund_flow=None,
    zt_pool_raw=None,
    dt_pool_raw=None,
    skip_api_call=False,
):
    """Resolve stock sector from structured sources before optional API fallback."""
    if zt_pool_raw:
        for stock in zt_pool_raw:
            if stock.get("代码") == stock_code or stock.get("名称") == stock_name:
                sector = stock.get("所属行业", "")
                if sector and sector != "未知":
                    return sector

    if dt_pool_raw:
        for stock in dt_pool_raw:
            if stock.get("代码") == stock_code or stock.get("名称") == stock_name:
                sector = stock.get("所属行业", "")
                if sector and sector != "未知":
                    return sector

    if hot_rank_data:
        for stock in hot_rank_data:
            if stock.get("code") == stock_code or stock.get("name") == stock_name:
                concepts = stock.get("concepts", [])
                if concepts:
                    return concepts[0]

    if zt_pool_data:
        for sector_name, stocks in zt_pool_data.items():
            for stock in stocks:
                if stock.get("code") == stock_code or stock.get("name") == stock_name:
                    return sector_name

    if lianban_data:
        for stock in lianban_data:
            if stock.get("code") == stock_code or stock.get("name") == stock_name:
                plates = stock.get("plates", [])
                if plates:
                    return plates[0]
                reason = stock.get("reason", "")
                if reason and "概念" in reason:
                    match = re.search(r"(\S+?概念)", reason)
                    if match:
                        return match.group(1)

    if lhb_data:
        for stock in lhb_data:
            if stock.get("code") == stock_code or stock.get("name") == stock_name:
                sector = stock.get("sector", "")
                if sector and sector != "未知":
                    return sector

    if sector_fund_flow:
        for flow in sector_fund_flow.get("inflow", []):
            leading_stock = flow.get("leading_stock", "")
            if stock_name in leading_stock or stock_code in leading_stock:
                return flow.get("name", "")

    if not skip_api_call:
        global _eastmoney_warning_emitted
        cache_key = stock_code if stock_code else stock_name
        if cache_key in _stock_industry_cache:
            return _stock_industry_cache[cache_key]

        try:
            import requests

            pure_code = (
                stock_code.replace("sz", "")
                .replace("sh", "")
                .replace("SZ", "")
                .replace("SH", "")
                if stock_code
                else ""
            )
            if pure_code:
                full_code = f"{_resolve_market_code(pure_code)}{pure_code}"
                resp = requests.get(
                    "https://emweb.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax",
                    params={"code": full_code},
                    timeout=5,
                )
                data = resp.json()
                if data.get("jbzl"):
                    industry = data["jbzl"].get("sshy", "")
                    if industry:
                        _stock_industry_cache[cache_key] = industry
                        return industry
        except Exception as error:
            if not _eastmoney_warning_emitted:
                print(f"   ⚠️ Eastmoney行业接口失败，将返回未知: {error}")
                _eastmoney_warning_emitted = True
            record_helper_log(
                "domains.market_activity.support",
                "helper.stock_sector.eastmoney",
                "error",
                "Eastmoney行业接口失败",
                provider="eastmoney.company_survey",
                target_keys=["sector"],
                error=str(error),
                stock_code=stock_code,
                stock_name=stock_name,
            )
            _stock_industry_cache[cache_key] = "未知"
            return "未知"

    return "未知"
