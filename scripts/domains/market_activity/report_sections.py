from domains.market_activity.quote_lookup import (
    build_market_quote_lookup,
    normalize_stock_code as normalize_quote_code,
    normalize_stock_name,
    resolve_change_pct,
)
from domains.market_activity.report_section_nodes import (
    build_market_activity_advanced_section_result,
    build_market_activity_basic_section_result,
)


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_activity.report_sections",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _normalize_stock_code(value):
    return normalize_quote_code(value)


def _display_text(value):
    current = value
    for _ in range(4):
        if isinstance(current, dict):
            if current.get("value") not in (None, ""):
                current = current.get("value")
                continue
            if current.get("name") not in (None, ""):
                current = current.get("name")
                continue
            break
        nested_value = getattr(current, "value", None)
        if nested_value not in (None, "") and nested_value is not current:
            current = nested_value
            continue
        break
    return str(current or "").strip()


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resolve_stock_info(stock_full_info, stock_code="", stock_name=""):
    normalized_code = _normalize_stock_code(stock_code)
    if normalized_code and normalized_code in stock_full_info:
        return stock_full_info.get(normalized_code) or {}

    normalized_name = normalize_stock_name(stock_name)
    if normalized_name:
        for info in (stock_full_info or {}).values():
            if normalize_stock_name((info or {}).get("name", "")) == normalized_name:
                return info or {}
    return {}


def build_market_activity_report_sections(
    data,
    target_date,
    stock_full_info,
    *,
    get_stock_status,
    get_stock_sector,
    analyze_candlestick_pattern,
    enabled_node_keys=None,
):
    data = data or {}
    stock_full_info = stock_full_info or {}
    node_result = build_market_activity_basic_section_result(
        {
            "data": data,
            "target_date": target_date,
            "stock_full_info": stock_full_info,
            "get_stock_status": get_stock_status,
            "get_stock_sector": get_stock_sector,
            "analyze_candlestick_pattern": analyze_candlestick_pattern,
            "enabled_node_keys": enabled_node_keys,
        }
    )
    lines = list(node_result.get("lines") or [])
    logs = list(node_result.get("module_logs") or [])
    exports = dict(node_result.get("node_outputs", {}).get("sector_fund_inflow") or {})
    over_100b = data.get("turnover_over_100b", []) or [stock for stock in data.get("turnover_rank", []) if stock.get("turnover", 0) > 100]

    _append_log(
        logs,
        "render.market_activity_sections",
        "success",
        "已生成 market_activity 业务域的基础活跃度章节",
        hot_rank_count=len(data.get("hot_rank_top30", []) or []),
        turnover_count=len(over_100b or []),
        lhb_buy_count=len(data.get("lhb_net_buy_top10", []) or []),
    )
    return {
        "lines": lines,
        "module_logs": logs,
        "exports": exports,
    }


def build_advanced_activity_report_sections(
    data,
    stock_full_info,
    *,
    get_stock_sector,
    analyze_candlestick_pattern,
    enabled_node_keys=None,
):
    data = data or {}
    stock_full_info = stock_full_info or {}
    node_result = build_market_activity_advanced_section_result(
        {
            "data": data,
            "stock_full_info": stock_full_info,
            "get_stock_sector": get_stock_sector,
            "analyze_candlestick_pattern": analyze_candlestick_pattern,
            "enabled_node_keys": enabled_node_keys,
        }
    )
    lines = list(node_result.get("lines") or [])
    logs = list(node_result.get("module_logs") or [])
    volume_anomalies = data.get("volume_anomalies", [])

    _append_log(
        logs,
        "render.advanced_activity_sections",
        "success",
        "已生成 market_activity 业务域的高阶活跃度章节",
        lianban_count=len(data.get("lianban_data", []) or []),
        anomaly_count=len(volume_anomalies or []),
        signal_count=len(data.get("trade_signals", []) or []),
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
