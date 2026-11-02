"""Current dated market/sector checks without the historical account renderer."""
from __future__ import annotations

import datetime as _dt


class ReportCriticalDataMissingError(RuntimeError):
    """Raised when a report would render with missing market-critical data."""


def _report_data_payload(data):
    if not isinstance(data, dict):
        return {}
    payload = data.get("data")
    if isinstance(payload, dict) and ("data_status" in payload or "step_status" in payload):
        return payload
    return data


def build_market_reading_preflight(data, target_date, *, historical_snapshot=False):
    """Validate only dated market and sector facts used by the reading page."""
    target_date = str(target_date or "").strip()
    try:
        parsed_target_date = _dt.date.fromisoformat(target_date)
    except ValueError as error:
        raise ReportCriticalDataMissingError("目标日期格式不符，关键数据不完整，停止生成") from error
    if parsed_target_date.isoformat() != target_date:
        raise ReportCriticalDataMissingError("目标日期格式不符，关键数据不完整，停止生成")
    shanghai_today = _dt.datetime.now(
        _dt.timezone(_dt.timedelta(hours=8))
    ).date()
    if parsed_target_date > shanghai_today:
        raise ReportCriticalDataMissingError("目标日期晚于当前上海日期，关键数据不完整，停止生成")

    if not isinstance(data, dict):
        raise ReportCriticalDataMissingError("板块阅读资料格式不符，关键数据不完整，停止生成")
    payload = _report_data_payload(data)
    for key in ("target_date", "source_date"):
        value = str(payload.get(key) or "").strip()
        if value and value != target_date:
            raise ReportCriticalDataMissingError(
                f"板块阅读数据的{key}与目标日期不一致，关键数据不完整，停止生成"
            )

    from report.sector_reading_content import sector_facts

    rows = sector_facts({"date": target_date, "data": payload}, target_date, recorded=historical_snapshot)

    from report.sector_daily_report import market_background_facts

    background = market_background_facts(payload, target_date, recorded=historical_snapshot)

    checks = [
        {"label": "板块样本", "status": "available" if rows else "missing", "row_count": len(rows)},
        {
            "label": "指数背景",
            "status": "available" if background["change_pct"] is not None else "missing",
            "row_count": 1 if background["change_pct"] is not None else 0,
        },
        {
            "label": "涨跌家数",
            "status": "available" if background["up_count"] is not None and background["down_count"] is not None else "missing",
            "row_count": 1 if background["up_count"] is not None and background["down_count"] is not None else 0,
        },
        {
            "label": "两市成交额",
            "status": "available" if background["amount_yi"] is not None else "missing",
            "row_count": 1 if background["amount_yi"] is not None else 0,
        },
    ]
    return {
        "target_date": target_date,
        "status": "success",
        "checks": checks,
        "decision_checks": [],
        "failures": [],
        "sector_row_count": len(rows),
        "request_diagnostics": {},
    }
