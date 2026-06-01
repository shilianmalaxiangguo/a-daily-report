#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render/output helpers for the A股日报 pipeline.

This module owns the public report rendering facade and the filesystem layout
for generated markdown artifacts. The heavy market-analysis logic still lives in
scripts/daily_report_entry_demo.py; this layer only orchestrates display-mode
switching, report variants, and persistence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
import types

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
try:
    import daily_report_analysis_utils as analysis_utils
except ImportError:  # pragma: no cover - local compatibility shim for this repo snapshot
    analysis_utils = types.SimpleNamespace(
        normalize_stock_code=lambda code: str(code or "").strip(),
    )

REPORT_VARIANT_FULL = "full"
REPORT_VARIANT_SUMMARY = "summary"
CRITICAL_REPORT_DATA_FIELDS = (
    ("两市成交额", "total_turnover"),
    ("中证全指", "wind_a_alternative"),
    ("中证1000", "csi1000_index"),
    ("成交额排名", "turnover_rank"),
    ("大盘涨跌统计", "market_stats"),
    ("热度前50个股", "hot_rank_top50"),
)
CRITICAL_TUSHARE_PROVIDER_PREFIXES = {
    "wind_a_alternative": ("tushare.", "postgresql.daily_report_facts", "postgresql."),
    "csi1000_index": ("tushare.", "postgresql.daily_report_facts", "postgresql."),
    "turnover_rank": ("tushare.", "postgresql.daily_report_facts", "postgresql."),
}
DECISION_CRITICAL_REPORT_DATA_FIELDS = (
    ("整合热榜", "整合热榜获取", ("request.integrated_hot_rank",), "integrated_hot_list", False),
    ("预期日历", "预期日历获取", ("request.calendar_events",), "calendar_events", False),
    ("选股通盘中异动", "选股通盘中异动获取", ("request.xuangubao",), "xuangubao_data", False),
    ("顽主杯热门前十", "顽主杯热门前十获取", ("request.wanzhu_top10",), "wanzhu_top10", False),
    ("连板梯队", "连板梯队提取", ("request.lianban_snapshot",), "lianban_data", True),
    ("创新高趋势反馈", "创新高趋势反馈获取", ("request.new_high_feedback",), "new_high_feedback", False),
    ("Top50成交额占比趋势", "Top50成交额占比趋势获取", ("request.top50_turnover_share_series",), "top50_turnover_share_series", False),
    ("ETF两市成交额趋势", "ETF两市成交额趋势获取", ("request.etf_turnover_series",), "etf_turnover_series", False),
    ("龙虎榜数据", "龙虎榜数据获取", ("request.lhb_snapshot",), "lhb_analysis", False),
    ("概念资金流向", "概念资金流向获取", ("request.concept_fund_flow",), "concept_fund_flow", False),
    ("雪球A股24小时热榜", "雪球A股24小时热榜获取", ("request.xueqiu_hot_rank",), "xueqiu_hot_rank_top100", False),
    ("雪球热榜AI解释", "雪球热榜AI解释获取", ("request.xueqiu_hot_stock_arguments",), "xueqiu_hot_stock_arguments", False),
    ("融资承接压力", "融资承接压力获取", ("request.margin_pressure",), "margin_pressure", False),
)
FAILED_REQUEST_STATUSES = {"error", "degraded"}
ALLOW_EMPTY_DATA_STATUS_LABELS = {
    "涨停池",
    "涨停股板块分布",
    "跌停池",
    "跌停股板块分布",
}


class ReportCriticalDataMissingError(RuntimeError):
    """Raised when a report would render with missing market-critical data."""

__all__ = [
    "REPORT_VARIANT_FULL",
    "REPORT_VARIANT_SUMMARY",
    "ReportCriticalDataMissingError",
    "_get_report_output_path",
    "_get_stock_diagnostic_output_path",
    "_inject_report_variant_banner",
    "_render_report_with_display_mode",
    "generate_markdown_report_from_sections",
    "generate_markdown_report",
    "build_report_preflight",
    "render_report_preflight_lines",
    "build_report_outputs",
    "save_report_output",
    "save_report_outputs",
    "save_stock_diagnostic_output",
]


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _reports_root() -> Path:
    return _module_dir().parent / "reports"


def _diagnostics_root() -> Path:
    return _reports_root() / "stock_diagnostics"


def _ensure_parent_dir(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_report_output_path(target_date: str, mode: str = LEDGER_MODE_FROZEN, variant: str = REPORT_VARIANT_FULL) -> str:
    reports_dir = _reports_root()
    if mode == LEDGER_MODE_REPLAY:
        reports_dir = reports_dir / "replay"
    reports_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    variant_label = "完整版" if variant == REPORT_VARIANT_FULL else "执行摘要"
    return str(reports_dir / f"{target_date}_A股日报_{variant_label}{suffix}.md")


def _get_stock_diagnostic_output_path(target_date: str, stock_code: str, mode: str = LEDGER_MODE_FROZEN) -> str:
    diagnostics_dir = _diagnostics_root()
    if mode == LEDGER_MODE_REPLAY:
        diagnostics_dir = diagnostics_dir / "replay"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""

    return str(diagnostics_dir / f"{target_date}_{analysis_utils.normalize_stock_code(stock_code)}_单票诊断{suffix}.md")


def _inject_report_variant_banner(report_text: str, variant: str) -> str:
    return report_text


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _critical_payload_valid(data, payload_key):
    data = data or {}
    if payload_key == "total_turnover":
        return _safe_float(data.get("total_turnover")) > 0
    if payload_key in {"wind_a_alternative", "csi1000_index"}:
        payload = data.get("wind_a_alternative") or {}
        if payload_key == "csi1000_index":
            payload = data.get("csi1000_index") or {}
        if not isinstance(payload, dict):
            return False
        return _safe_float(payload.get("price", payload.get("点位", 0))) > 0
    if payload_key == "turnover_rank":
        return bool(data.get("turnover_rank"))
    if payload_key == "market_stats":
        payload = data.get("market_stats") or {}
        if not isinstance(payload, dict):
            return False
        return _safe_float(payload.get("up_count")) > 0 and _safe_float(payload.get("down_count")) > 0
    if payload_key == "hot_rank_top50":
        target = int(_safe_float(data.get("hot_rank_sample_target"), 50) or 50)
        sample_size = int(_safe_float(data.get("hot_rank_sample_size"), 0))
        if sample_size <= 0:
            sample_size = len(data.get("hot_rank_top50") or data.get("hot_rank_top30") or [])
        return sample_size >= target
    return True


def _report_data_payload(data):
    if not isinstance(data, dict):
        return {}
    payload = data.get("data")
    if isinstance(payload, dict) and ("data_status" in payload or "step_status" in payload):
        return payload
    return data


def _critical_data_failures(data):
    data = _report_data_payload(data)
    data_status = data.get("data_status") or {}
    failures = []
    for label, payload_key in CRITICAL_REPORT_DATA_FIELDS:
        if not _critical_field_tracked(data, label, payload_key):
            continue
        if data_status.get(label) is False or not _critical_payload_valid(data, payload_key):
            failures.append(label)
    return failures


def _critical_field_tracked(data, label, payload_key):
    data_status = (data or {}).get("data_status") or {}
    if payload_key == "market_stats":
        step_status = (data or {}).get("step_status") or {}
        return (
            label in data_status
            or payload_key in (data or {})
            or "涨停跌停数据获取" in step_status
            or bool(_request_logs_for_steps(data or {}, ("request.market_stats",)))
        )
    if payload_key == "hot_rank_top50":
        step_status = (data or {}).get("step_status") or {}
        return (
            label in data_status
            or "热度前50个股获取" in step_status
            or "hot_rank_top50" in (data or {})
            or "hot_rank_top30" in (data or {})
            or "hot_rank_sample_size" in (data or {})
            or bool(_request_logs_for_steps(data or {}, ("request.hot_rank.primary", "request.hot_rank.fallback")))
        )
    return label in data_status or payload_key in (data or {})


def _provider_allowed_for_critical_payload(payload_key, provider):
    provider = str(provider or "").strip()
    allowed_prefixes = CRITICAL_TUSHARE_PROVIDER_PREFIXES.get(payload_key, ())
    if not allowed_prefixes:
        return True
    return any(provider.startswith(prefix) for prefix in allowed_prefixes)


def _provider_for_step(data, step):
    for log in (data.get("module_logs") or []):
        if not isinstance(log, dict) or log.get("step") != step:
            continue
        details = log.get("details") or {}
        return details.get("provider") or ""
    return ""


def _request_logs_for_steps(data, steps):
    steps = set(steps or [])
    return [
        log
        for log in (data.get("module_logs") or [])
        if isinstance(log, dict) and log.get("step") in steps
    ]


def _provider_for_steps(data, steps):
    providers = []
    for log in _request_logs_for_steps(data, steps):
        details = log.get("details") or {}
        provider = details.get("provider") or details.get("source") or ""
        if provider:
            providers.append(str(provider))
    unique = sorted(set(providers))
    if not unique:
        return ""
    return ",".join(unique)


def _xuangubao_summary_count(payload):
    if not isinstance(payload, dict):
        return 0
    return (
        int(_safe_float(payload.get("news_count"), 0))
        + int(_safe_float(payload.get("plate_count"), 0))
        + int(_safe_float(payload.get("limit_up_reason_count"), 0))
    )


def _row_count_for_step(data, step, payload_key):
    for log in (data.get("module_logs") or []):
        if not isinstance(log, dict) or log.get("step") != step:
            continue
        details = log.get("details") or {}
        for key in ("row_count", "rank_count", "index_count", "hot_rank_count", "count"):
            if details.get(key) not in (None, ""):
                return details.get(key)
    payload = data.get(payload_key)
    if isinstance(payload, (list, tuple)):
        return len(payload)
    if isinstance(payload, dict):
        return 1 if payload else 0
    return 1 if payload not in (None, "", 0, 0.0) else 0


def _row_count_for_steps(data, steps, payload_key):
    for log in _request_logs_for_steps(data, steps):
        details = log.get("details") or {}
        if "news_count" in details or "plate_count" in details or "limit_up_reason_count" in details:
            return (
                int(_safe_float(details.get("news_count"), 0))
                + int(_safe_float(details.get("plate_count"), 0))
                + int(_safe_float(details.get("limit_up_reason_count"), 0))
            )
        for key in ("row_count", "rank_count", "index_count", "hot_rank_count", "count", "integrated_count", "calendar_count", "news_count", "stock_count", "lianban_count"):
            if details.get(key) not in (None, ""):
                return details.get(key)
    payload = data.get(payload_key)
    if payload_key == "new_high_feedback" and isinstance(payload, dict):
        return len(payload.get("trend_rows") or []) or (1 if payload else 0)
    if payload_key == "margin_pressure" and isinstance(payload, dict):
        return len(payload.get("rows") or []) or (1 if payload else 0)
    if payload_key == "etf_turnover_series" and isinstance(payload, dict):
        return len(payload.get("rows") or []) or (1 if payload else 0)
    if payload_key == "xuangubao_data" and isinstance(payload, dict):
        summary_count = _xuangubao_summary_count(payload)
        if summary_count:
            return summary_count
    if isinstance(payload, (list, tuple)):
        return len(payload)
    if isinstance(payload, dict):
        return 1 if payload else 0
    return 1 if payload not in (None, "", 0, 0.0) else 0


def _decision_payload_valid(data, payload_key, allow_empty):
    if payload_key not in data:
        return True
    payload = data.get(payload_key)
    if payload_key == "xuangubao_data":
        if not isinstance(payload, dict):
            return False
        if _xuangubao_summary_count(payload) > 0:
            return True
        return any(
            payload.get(key)
            for key in ("xuangubao_news", "xuangubao_plates", "xuangubao_limit_up_reasons")
        )
    if payload_key == "new_high_feedback":
        return isinstance(payload, dict) and payload.get("available") is True
    if payload_key == "top50_turnover_share_series":
        return isinstance(payload, dict) and bool(payload.get("rows") or [])
    if payload_key == "etf_turnover_series":
        return isinstance(payload, dict) and bool(payload.get("rows") or [])
    if payload_key == "concept_fund_flow":
        if not isinstance(payload, dict):
            return False
        return bool(payload.get("rows") or [])
    if payload_key == "margin_pressure":
        return isinstance(payload, dict) and payload.get("available") is True and bool(payload.get("rows") or [])
    if payload_key == "lhb_analysis":
        return bool(
            payload
            or data.get("lhb_net_buy_top10")
            or data.get("lhb_net_sell_top10")
        )
    if allow_empty:
        return payload is not None
    if isinstance(payload, (list, tuple, dict)):
        return bool(payload)
    return payload not in (None, "", 0, 0.0)


def _format_preflight_pct(value):
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "待累计"


def _new_high_recent_trend_echo(data, limit=25):
    payload = (data or {}).get("new_high_feedback") or {}
    if not isinstance(payload, dict):
        return []
    rows = [row for row in payload.get("trend_rows") or [] if isinstance(row, dict)]
    if not rows:
        return []
    lines = ["  创新高近25个交易日:"]
    for row in rows[-int(limit or 25):]:
        date = str(row.get("trade_date") or row.get("date") or "").strip()
        count = row.get("new_high_count", "")
        pct = _format_preflight_pct(row.get("all_a_share_pct"))
        change_text = str(row.get("change_text") or "待累计").strip()
        leading = str(row.get("leading_sectors") or "待补充板块").strip()
        lines.append(f"  - {date} {count} {pct} {change_text} {leading}")
    return lines


def _decision_request_failed(data, steps):
    logs = _request_logs_for_steps(data, steps)
    if not logs:
        return False
    return not any(str(log.get("status") or "").strip() == "success" for log in logs)


def _decision_request_failure_blocks(data, steps, payload_key, allow_empty):
    if not _decision_request_failed(data, steps):
        return False
    step_status = (data or {}).get("step_status") or {}
    step_success = any(
        step_label in step_status and step_status.get(step_label) is True
        for _, step_label, configured_steps, configured_payload_key, _ in DECISION_CRITICAL_REPORT_DATA_FIELDS
        if configured_payload_key == payload_key and tuple(configured_steps) == tuple(steps)
    )
    if step_success and _decision_payload_valid(data, payload_key, allow_empty):
        return False
    return True


def _decision_field_tracked(data, label, step_label, steps, payload_key):
    data_status = (data or {}).get("data_status") or {}
    step_status = (data or {}).get("step_status") or {}
    return (
        label in data_status
        or step_label in step_status
        or payload_key in (data or {})
        or bool(_request_logs_for_steps(data or {}, steps))
    )


def _build_decision_critical_checks(data):
    data = data or {}
    data_status = data.get("data_status") or {}
    step_status = data.get("step_status") or {}
    checks = []
    for label, step_label, steps, payload_key, allow_empty in DECISION_CRITICAL_REPORT_DATA_FIELDS:
        tracked = _decision_field_tracked(data, label, step_label, steps, payload_key)
        if not tracked:
            continue
        data_failed = label in data_status and data_status.get(label) is False
        step_failed = step_label in step_status and step_status.get(step_label) is False
        payload_failed = not _decision_payload_valid(data, payload_key, allow_empty)
        request_failed = _decision_request_failure_blocks(data, steps, payload_key, allow_empty)
        status = "failed" if data_failed or step_failed or request_failed or payload_failed else "success"
        checks.append(
            {
                "label": label,
                "step_label": step_label,
                "payload_key": payload_key,
                "status": status,
                "provider": _provider_for_steps(data, steps) or "unknown",
                "row_count": _row_count_for_steps(data, steps, payload_key),
                "echo_lines": _new_high_recent_trend_echo(data) if payload_key == "new_high_feedback" else [],
                "data_status": data_status.get(label),
                "step_status": step_status.get(step_label),
            }
        )
    return checks


def _has_quant_signal_inputs(data):
    sector_fund_flow = data.get("sector_fund_flow") or {}
    return bool(data.get("zt_pool")) and bool(sector_fund_flow.get("inflow") or []) and bool(data.get("stocks_with_history"))


def _build_quant_factor_checks(data):
    data = data or {}
    logs = _request_logs_for_steps(data, ("infer.quant_signals",))
    if not logs:
        return []
    latest = logs[-1]
    details = latest.get("details") or {}
    checks = []
    resonance_count = int(_safe_float(details.get("resonance_count"), 0))
    if _has_quant_signal_inputs(data) and resonance_count <= 0:
        checks.append(
            {
                "label": "板块共振结果",
                "step_label": "AI多维量化分析",
                "payload_key": "resonance_scores",
                "status": "failed",
                "provider": "quantitative_analyzer.calculate_resonance",
                "row_count": resonance_count,
                "step_status": latest.get("status"),
            }
        )
    return checks


def _status_label_to_factor_label(label):
    text = str(label or "").strip()
    for suffix in ("获取", "提取"):
        if text.endswith(suffix):
            return text[: -len(suffix)] or text
    return text


def _dedupe_labels(labels):
    deduped = []
    seen = set()
    for label in labels or []:
        text = str(label or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _build_registered_status_failure_checks(data, known_labels=None):
    data = data or {}
    known = set(known_labels or [])
    checks = []
    seen = set()

    for label, status in (data.get("data_status") or {}).items():
        factor_label = str(label or "").strip()
        if not factor_label or factor_label in known or factor_label in seen:
            continue
        if factor_label in ALLOW_EMPTY_DATA_STATUS_LABELS:
            continue
        if status is False:
            seen.add(factor_label)
            checks.append(
                {
                    "label": factor_label,
                    "step_label": "",
                    "payload_key": "",
                    "status": "failed",
                    "provider": "status.data_status",
                    "row_count": 0,
                    "step_status": "",
                }
            )

    for step_label, status in (data.get("step_status") or {}).items():
        factor_label = _status_label_to_factor_label(step_label)
        if not factor_label or factor_label in known or factor_label in seen:
            continue
        if factor_label in ALLOW_EMPTY_DATA_STATUS_LABELS:
            continue
        if status is False:
            seen.add(factor_label)
            checks.append(
                {
                    "label": factor_label,
                    "step_label": step_label,
                    "payload_key": "",
                    "status": "failed",
                    "provider": "status.step_status",
                    "row_count": 0,
                    "step_status": status,
                }
            )
    return checks


def _critical_value(data, payload_key):
    if payload_key == "total_turnover":
        return round(_safe_float(data.get("total_turnover")), 2)
    if payload_key in {"wind_a_alternative", "csi1000_index"}:
        payload = data.get(payload_key) or {}
        if isinstance(payload, dict):
            return round(_safe_float(payload.get("price", payload.get("点位", 0))), 2)
        return 0.0
    if payload_key == "turnover_rank":
        return _row_count_for_step(data, "request.turnover_rank", payload_key)
    if payload_key == "market_stats":
        payload = data.get("market_stats") or {}
        if isinstance(payload, dict):
            up_count = int(_safe_float(payload.get("up_count")))
            down_count = int(_safe_float(payload.get("down_count")))
            return f"{up_count}/{down_count}"
        return "0/0"
    if payload_key == "hot_rank_top50":
        target = int(_safe_float(data.get("hot_rank_sample_target"), 50) or 50)
        sample_size = int(_safe_float(data.get("hot_rank_sample_size"), 0))
        if sample_size <= 0:
            sample_size = len(data.get("hot_rank_top50") or data.get("hot_rank_top30") or [])
        return f"{sample_size}/{target}"
    return ""


def build_report_preflight(data, target_date):
    data = _report_data_payload(data)
    data_status = data.get("data_status") or {}
    step_by_payload_key = {
        "total_turnover": "request.total_turnover",
        "wind_a_alternative": "request.wind_a",
        "csi1000_index": "request.csi1000",
        "turnover_rank": "request.turnover_rank",
        "market_stats": "request.market_stats",
        "hot_rank_top50": "request.hot_rank.primary",
    }
    checks = []
    failures = set(_critical_data_failures(data))
    for label, payload_key in CRITICAL_REPORT_DATA_FIELDS:
        step = step_by_payload_key[payload_key]
        tracked = _critical_field_tracked(data, label, payload_key)
        provider = _provider_for_step(data, step)
        if not provider:
            payload = data.get(payload_key)
            provider = payload.get("data_source") if isinstance(payload, dict) else ""
            if not provider and isinstance(payload, list) and payload and isinstance(payload[0], dict):
                provider = payload[0].get("data_source") or ""
            if not provider and hasattr(payload, "data_source"):
                provider = getattr(payload, "data_source", "")
        provider_failed = tracked and not _provider_allowed_for_critical_payload(payload_key, provider)
        status = "未采集"
        if tracked:
            status = "failed" if label in failures or provider_failed else "success"
        checks.append(
            {
                "label": label,
                "payload_key": payload_key,
                "status": status,
                "provider": provider or "unknown",
                "value": _critical_value(data, payload_key),
                "row_count": _row_count_for_step(data, step, payload_key),
                "data_status": data_status.get(label),
            }
        )
    decision_checks = _build_decision_critical_checks(data) + _build_quant_factor_checks(data)
    known_labels = [check["label"] for check in checks + decision_checks]
    decision_checks.extend(_build_registered_status_failure_checks(data, known_labels=known_labels))
    decision_failures = [check["label"] for check in decision_checks if check["status"] == "failed"]
    all_failures = _dedupe_labels([
        check["label"]
        for check in checks
        if check["label"] in failures or check["status"] == "failed"
    ] + decision_failures)
    return {
        "target_date": target_date,
        "status": "failed" if all_failures else "success",
        "checks": checks,
        "decision_checks": decision_checks,
        "failures": all_failures,
    }


def render_report_preflight_lines(preflight):
    preflight = preflight or {}
    lines = [
        "日报关键数据 preflight: {} / {}".format(
            preflight.get("status", "unknown"),
            preflight.get("target_date", ""),
        )
    ]
    for check in preflight.get("checks") or []:
        lines.append(
            "- {label}: {status} | provider={provider} | value={value} | row_count={row_count}".format(
                label=check.get("label", ""),
                status=check.get("status", ""),
                provider=check.get("provider", "unknown"),
                value=check.get("value", ""),
                row_count=check.get("row_count", ""),
            )
        )
    if preflight.get("decision_checks"):
        lines.append("决策数据 preflight:")
        for check in preflight.get("decision_checks") or []:
            lines.append(
                "- {label}: {status} | provider={provider} | row_count={row_count} | step_status={step_status}".format(
                    label=check.get("label", ""),
                    status=check.get("status", ""),
                    provider=check.get("provider", "unknown"),
                    row_count=check.get("row_count", ""),
                    step_status=check.get("step_status", ""),
                )
            )
            lines.extend(check.get("echo_lines") or [])
    if preflight.get("failures"):
        lines.append("失败字段: {}".format("、".join(preflight.get("failures") or [])))
    return lines


def _raise_if_critical_data_missing(data, target_date, preflight=None):
    preflight = preflight or build_report_preflight(data, target_date)
    failures = preflight.get("failures") or []
    if not failures:
        return
    raise ReportCriticalDataMissingError(
        "{} 日报生成已终止：关键数据缺失或获取失败（{}）。\n{}".format(
            target_date,
            "、".join(failures),
            "\n".join(render_report_preflight_lines(preflight)),
        )
    )


def _render_report_with_display_mode(
    display_mvp_mode: bool,
    data: Dict[str, Any],
    target_date: str,
    supplementary_perspective: str = "",
    has_personal_positions: bool = False,
    run_mode: str = LEDGER_MODE_FROZEN,
    persist_strategy_tracking: bool = True,
    persist_decision_ledger: bool = False,
    decision_ledger_root_dir: str | None = None,
    persist_candidate_traces: bool = False,
    candidate_trace_root_dir: str | None = None,
    emit_helper_diagnostics: bool = True,
    shared_runtime_cache: dict | None = None,
    postgres_only: bool = False,
) -> str:
    import daily_report_entry_demo as _demo

    original_display_mode = getattr(_demo, "DISPLAY_MVP_MODE", False)
    original_emit_helper_diagnostics = getattr(_demo, "EMIT_HELPER_DIAGNOSTICS", True)
    original_runtime_cache = getattr(_demo, "REPORT_RUNTIME_CACHE", None)
    original_postgres_only_runtime = getattr(_demo, "_POSTGRES_ONLY_RUNTIME", False)
    previous_postgres_only_guard = os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME")
    _demo.DISPLAY_MVP_MODE = bool(display_mvp_mode)
    _demo.EMIT_HELPER_DIAGNOSTICS = bool(emit_helper_diagnostics)
    _demo.REPORT_RUNTIME_CACHE = shared_runtime_cache
    if postgres_only:
        _demo._POSTGRES_ONLY_RUNTIME = True
        os.environ["A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"] = "1"
    try:
        return _demo.generate_markdown_report(
            data,
            target_date,
            supplementary_perspective=supplementary_perspective,
            has_personal_positions=has_personal_positions,
            run_mode=run_mode,
            persist_strategy_tracking=persist_strategy_tracking,
            persist_decision_ledger=persist_decision_ledger,
            decision_ledger_root_dir=decision_ledger_root_dir,
            persist_candidate_traces=persist_candidate_traces,
            candidate_trace_root_dir=candidate_trace_root_dir,
            postgres_only=postgres_only,
        )
    finally:
        _demo.DISPLAY_MVP_MODE = original_display_mode
        _demo.EMIT_HELPER_DIAGNOSTICS = original_emit_helper_diagnostics
        _demo.REPORT_RUNTIME_CACHE = original_runtime_cache
        _demo._POSTGRES_ONLY_RUNTIME = original_postgres_only_runtime
        if postgres_only:
            if previous_postgres_only_guard is None:
                os.environ.pop("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME", None)
            else:
                os.environ["A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"] = previous_postgres_only_guard


def _sanitize_report_section_lines(lines):
    sanitized_lines = []
    seen_no_trade_conclusion = False
    blocked_markers = ("为什么要看这块", "草稿解释", "判断口径", "分析目的")

    for raw_line in lines:
        line = str(raw_line or "").rstrip()
        if any(marker in line for marker in blocked_markers):
            continue
        if "当前先不开新仓" in line:
            if seen_no_trade_conclusion:
                continue
            seen_no_trade_conclusion = True
        sanitized_lines.append(line)
    return sanitized_lines


def _sanitize_report_section_text(text):
    return "\n".join(_sanitize_report_section_lines(str(text or "").splitlines())).strip()


def generate_markdown_report_from_sections(sections):
    sections = sections or {}
    ordered_keys = ["preamble", "environment", "observation", "execution", "review", "summary"]
    rendered_sections = []
    seen_no_trade_conclusion = False
    for key in ordered_keys:
        if not sections.get(key):
            continue
        section_lines = []
        for line in _sanitize_report_section_text(sections.get(key)).splitlines():
            if "当前先不开新仓" in line:
                if seen_no_trade_conclusion:
                    continue
                seen_no_trade_conclusion = True
            section_lines.append(line)
        section_text = "\n".join(section_lines).strip()
        if section_text:
            rendered_sections.append(section_text)
    return "\n\n".join(rendered_sections)


def _extract_sections(data):
    if not isinstance(data, dict):
        return {}

    sections = data.get("sections")
    if isinstance(sections, dict) and sections:
        return sections

    extracted = {key: data.get(key, "") for key in ("preamble", "environment", "observation", "execution", "review", "summary")}
    return {key: value for key, value in extracted.items() if value}


def generate_markdown_report(
    data: Dict[str, Any],
    target_date: str,
    supplementary_perspective: str = "",
    has_personal_positions: bool = False,
    run_mode: str = LEDGER_MODE_FROZEN,
    persist_strategy_tracking: bool = True,
    persist_candidate_traces: bool = False,
    candidate_trace_root_dir: str | None = None,
    postgres_only: bool = False,
) -> str:
    """Render the default report text.

    This is a thin facade over the legacy implementation so callers can depend
    on a smaller, stable module instead of the huge entry script.
    """

    sections = _extract_sections(data)
    if sections:
        return generate_markdown_report_from_sections(sections)

    try:
        import daily_report_entry_demo as _demo
    except (ImportError, ModuleNotFoundError):
        return generate_markdown_report_from_sections(_extract_sections(data))

    return _demo.generate_markdown_report(
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=persist_strategy_tracking,
        persist_candidate_traces=persist_candidate_traces,
        candidate_trace_root_dir=candidate_trace_root_dir,
        postgres_only=postgres_only,
    )


def build_report_outputs(
    data: Dict[str, Any],
    target_date: str,
    supplementary_perspective: str = "",
    has_personal_positions: bool = False,
    run_mode: str = LEDGER_MODE_FROZEN,
    position_report_text: str = "",
    emit_preflight: bool = True,
):
    preflight = build_report_preflight(data, target_date)
    if emit_preflight:
        for line in render_report_preflight_lines(preflight):
            print(line)
    _raise_if_critical_data_missing(data, target_date, preflight=preflight)
    shared_runtime_cache = {}
    postgres_only = bool((data or {}).get("postgres_only"))
    full_report = _render_report_with_display_mode(
        False,
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=False,
        persist_decision_ledger=True,
        decision_ledger_root_dir=str(_module_dir().parent),
        persist_candidate_traces=True,
        candidate_trace_root_dir=str(_module_dir().parent),
        emit_helper_diagnostics=True,
        shared_runtime_cache=shared_runtime_cache,
        postgres_only=postgres_only,
    )
    summary_report = _render_report_with_display_mode(
        True,
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=False,
        persist_decision_ledger=False,
        decision_ledger_root_dir=str(_module_dir().parent),
        persist_candidate_traces=False,
        candidate_trace_root_dir=str(_module_dir().parent),
        emit_helper_diagnostics=False,
        shared_runtime_cache=shared_runtime_cache,
        postgres_only=postgres_only,
    )

    return {
        REPORT_VARIANT_FULL: _inject_report_variant_banner(full_report, REPORT_VARIANT_FULL),
        REPORT_VARIANT_SUMMARY: _inject_report_variant_banner(summary_report, REPORT_VARIANT_SUMMARY),
    }


def save_report_output(
    report_text: str,
    target_date: str,
    mode: str = LEDGER_MODE_FROZEN,
    variant: str = REPORT_VARIANT_FULL,
    output_path: str | None = None,
    overwrite_existing: bool = False,
):
    target_path = Path(output_path) if output_path else Path(_get_report_output_path(target_date, mode=mode, variant=variant))
    _ensure_parent_dir(target_path)

    if not overwrite_existing and output_path is None and mode == LEDGER_MODE_FROZEN and target_path.exists():
        replay_path = Path(_get_report_output_path(target_date, mode=LEDGER_MODE_REPLAY, variant=variant))
        _ensure_parent_dir(replay_path)
        replay_path.write_text(report_text, encoding="utf-8")
        print(f"\n🧊 官方报告已冻结，未覆盖历史: {target_path}")
        print(f"🧪 当前结果已转存为实验报告: {replay_path}")
        print(f"📄 报告长度: {len(report_text)} 字符")
        return str(replay_path)

    target_path.write_text(report_text, encoding="utf-8")
    print(f"\n✅ 报告已保存: {target_path}")
    print(f"📄 报告长度: {len(report_text)} 字符")
    return str(target_path)


def save_report_outputs(
    report_outputs,
    target_date: str,
    mode: str = LEDGER_MODE_FROZEN,
    output_dir: str | None = None,
    overwrite_existing: bool = False,
    postgres_only: bool = False,
):
    saved_paths = {}
    for variant, report_text in (report_outputs or {}).items():
        if output_dir:
            variant_label = "完整版" if variant == REPORT_VARIANT_FULL else "执行摘要"
            suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
            custom_path = Path(output_dir) / f"{target_date}_A股日报_{variant_label}{suffix}.md"
            saved_paths[variant] = save_report_output(
                report_text,
                target_date,
                mode=mode,
                variant=variant,
                output_path=str(custom_path),
                overwrite_existing=overwrite_existing,
            )
        else:
            saved_paths[variant] = save_report_output(
                report_text,
                target_date,
                mode=mode,
                variant=variant,
                overwrite_existing=overwrite_existing,
            )
    if mode == LEDGER_MODE_REPLAY:
        _sync_replay_decision_ledger_from_full_report(
            saved_paths,
            target_date,
            output_dir=output_dir,
            postgres_only=postgres_only,
        )
    return saved_paths


def _sync_replay_decision_ledger_from_full_report(saved_paths, target_date: str, *, output_dir: str | None = None, postgres_only: bool = False):
    full_report_path = (saved_paths or {}).get(REPORT_VARIANT_FULL)
    if not full_report_path:
        return None
    from report.decision_ledger import write_decision_ledger_artifacts_from_markdown_report

    root_dir = Path(output_dir) if output_dir else _module_dir().parent
    result = write_decision_ledger_artifacts_from_markdown_report(
        full_report_path,
        trade_date=target_date,
        market_branch="回放正文重建",
        sector_relationship_state="以最终报告重点观察名单为准",
        root_dir=root_dir,
        write_json_archive=not bool(postgres_only),
        review_market_facts_by_stock_code={} if postgres_only else None,
    )
    if result.get("skipped_empty_markdown"):
        print(f"🧾 replay 决策台账保留已有结构化样本: {result.get('case_count', 0)} 个样本")
    else:
        print(f"🧾 replay 决策台账已按最终完整版日报同步: {result.get('case_count', 0)} 个样本")
    return result


def save_stock_diagnostic_output(
    report_text: str,
    target_date: str,
    stock_code: str,
    mode: str = LEDGER_MODE_FROZEN,
    output_path: str | None = None,
):
    target_path = Path(output_path) if output_path else Path(_get_stock_diagnostic_output_path(target_date, stock_code, mode=mode))
    _ensure_parent_dir(target_path)
    target_path.write_text(report_text, encoding="utf-8")
    print(f"\n✅ 单票诊断已保存: {target_path}")
    print(f"📄 诊断长度: {len(report_text)} 字符")
    return str(target_path)
