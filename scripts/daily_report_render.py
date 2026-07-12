#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render/output helpers for the A股日报 pipeline.

This module owns the public report rendering facade and the filesystem layout
for generated markdown artifacts. The heavy market-analysis logic still lives in
scripts/daily_report_entry_demo.py; this layer only orchestrates display-mode
switching, report variants, and persistence.
"""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any, Dict
import types

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from knowledge.llm_wiki_context import build_llm_wiki_context
from knowledge.topic_lifecycle import (
    build_topic_lifecycle_snapshot,
    write_topic_lifecycle_artifact,
)
from hooks.report.use_report_sections import build_daily_discipline_note
from report.html_report_view import build_daily_report_view, missing_required_fact_labels
from report.position_context import (
    extract_position_timeline_markdown,
    normalize_inferred_previous_target_records,
    prepend_position_timeline_markdown,
)
from report.surface_wording import sanitize_user_visible_text
from domains.market_state.market_language_translation import canonical_market_language_hash
try:
    import daily_report_analysis_utils as analysis_utils
except ImportError:  # pragma: no cover - local compatibility shim for this repo snapshot
    analysis_utils = types.SimpleNamespace(
        normalize_stock_code=lambda code: str(code or "").strip(),
    )

REPORT_VARIANT_FULL = "full"
REPORT_VARIANT_SUMMARY = "summary"
REPORT_VARIANT_LIGHTWEIGHT = "lightweight"
REPORT_VARIANT_EVIDENCE_APPENDIX = "evidence_appendix"
REPORT_VARIANT_RUN_LOG = "run_log"


class SavedReportVerificationError(RuntimeError):
    """Raised when a saved report cannot be verified against its accepted text."""


def read_verified_saved_report_markdown(report_path, expected_markdown):
    path_text = str(report_path or "").strip()
    if not path_text:
        raise SavedReportVerificationError("保存后的完整版日报路径缺失，研究证据不写入")
    path = Path(path_text)
    try:
        saved_markdown = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SavedReportVerificationError(
            "保存后的完整版日报无法读取，研究证据不写入"
        ) from exc
    if saved_markdown != str(expected_markdown or ""):
        raise SavedReportVerificationError(
            "保存后的完整版日报与检查通过的正文不一致，研究证据不写入"
        )
    return saved_markdown


REPORT_COMPANION_DOCS = "companion_docs"
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
    "turnover_rank": (
        "tushare.",
        "postgresql.daily_report_facts",
        "postgresql.",
        "storage.turnover_rank_daily",
        "eastmoney.turnover_rank",
        "eastmoney.push2.clist",
        "iwencai.",
        "akshare.stock_zh_a_spot_em",
    ),
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
SECTOR_FIRST_CRITICAL_INPUTS = (
    ("市场输入", ("market_state_snapshot", "market_research_snapshot", "mainline_turnover_summary")),
    ("板块发酵输入", ("sector_trend_snapshot", "mainline_turnover_summary", "current_sector_turnover_snapshot")),
    ("龙头确认输入", ("selected_position_candidate", "current_core_candidate", "final_target_resolution")),
    ("价格行为输入", ("selection_workflow", "selected_position_candidate", "current_core_candidate")),
    ("账户执行输入", ("position_decision", "final_target_resolution", "front_page_final_gate")),
)
FAILED_REQUEST_STATUSES = {"error", "degraded"}
ALLOW_EMPTY_DATA_STATUS_LABELS = {
    "涨停池",
    "涨停股板块分布",
    "跌停池",
    "跌停股板块分布",
    "中证500",
    "异动检测数据",
}


class ReportCriticalDataMissingError(RuntimeError):
    """Raised when a report would render with missing market-critical data."""

__all__ = [
    "REPORT_VARIANT_FULL",
    "REPORT_VARIANT_SUMMARY",
    "REPORT_VARIANT_LIGHTWEIGHT",
    "REPORT_VARIANT_EVIDENCE_APPENDIX",
    "REPORT_VARIANT_RUN_LOG",
    "REPORT_COMPANION_DOCS",
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
    "assert_report_required_facts_complete",
    "persist_report_runtime_artifacts",
    "save_report_output",
    "save_report_companion_docs",
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


def _report_variant_label(variant: str) -> str:
    labels = {
        REPORT_VARIANT_FULL: "完整版",
        REPORT_VARIANT_SUMMARY: "执行摘要",
        REPORT_VARIANT_LIGHTWEIGHT: "轻量版",
        REPORT_VARIANT_EVIDENCE_APPENDIX: "证据附录",
        REPORT_VARIANT_RUN_LOG: "运行日志",
        REPORT_COMPANION_DOCS: "伴随文档",
    }
    return labels.get(variant, str(variant or "报告"))


def _companion_docs_dir(saved_paths, target_date: str, mode: str = LEDGER_MODE_FROZEN) -> Path:
    path_values = [
        Path(path)
        for path in (saved_paths or {}).values()
        if isinstance(path, (str, Path)) and str(path)
    ]
    replay_paths = [path for path in path_values if path.name.endswith("_replay.md")]
    replay_suffix = mode == LEDGER_MODE_REPLAY or bool(replay_paths)
    if replay_paths:
        base_dir = replay_paths[0].parent
    elif path_values:
        base_dir = path_values[0].parent
    else:
        base_dir = Path(_get_report_output_path(target_date, mode=mode)).parent
    suffix = "_replay" if replay_suffix else ""
    return base_dir / f"{target_date}_A股日报_伴随文档{suffix}"


def _format_saved_report_paths(saved_paths) -> str:
    rows = []
    for variant, path in (saved_paths or {}).items():
        if variant == REPORT_COMPANION_DOCS:
            continue
        rows.append(f"- {_report_variant_label(variant)}: `{path}`")
    return "\n".join(rows) if rows else "- 暂无已保存报告路径"


def save_report_companion_docs(saved_paths, target_date: str, mode: str = LEDGER_MODE_FROZEN) -> str:
    companion_dir = _companion_docs_dir(saved_paths, target_date, mode=mode)
    companion_dir.mkdir(parents=True, exist_ok=True)
    mode_label = "replay" if mode == LEDGER_MODE_REPLAY or companion_dir.name.endswith("_replay") else "official"
    report_paths = _format_saved_report_paths(saved_paths)
    docs = {
        "AGENTS.md": "\n".join(
            [
                f"# {target_date} 日报协作说明",
                "",
                "- 目标：本次日报生成必须保留可复盘的边界、流程、验证和入口说明。",
                "- 协作边界：不覆盖项目根目录协作说明；本文件只记录本次产物的执行纪律。",
                "- 数据纪律：历史 replay 不混入当前盘面；关键数据不完整时停止生成。",
                "- 交易口径：旧仓、新机会和最终动作分开表达，避免把观察信号写成买入资格。",
            ]
        ),
        "flow.md": "\n".join(
            [
                f"# {target_date} 日报流程",
                "",
                f"- 运行模式：`{mode_label}`。",
                "- 输入：行情、板块、候选、旧仓和运行时补充事实。",
                "- 处理：先做数据检查，再做旧仓风险复核，然后比较新机会，最后输出唯一明日动作。",
                "- 输出：Markdown/HTML 报告、运行日志和本目录四个伴随文件。",
                "",
                "## 已保存报告",
                "",
                report_paths,
            ]
        ),
        "testing.md": "\n".join(
            [
                f"# {target_date} 日报验证",
                "",
                "- 最小验证：日报生成命令完成，运行日志可追到报告路径和伴随文档目录。",
                "- 规则覆盖：边界、流程、验证和入口四类说明均已落盘。",
                "- 人工复核：若日报暴露新规则、新 bug 或新口径，需要把具体证据补进本目录对应文件。",
                "- 剩余风险：本文件不替代单元测试、数据源核验或盘后人工复盘。",
            ]
        ),
        "readme.md": "\n".join(
            [
                f"# {target_date} 日报伴随文档",
                "",
                "本目录随日报生成，用来记录本次产物的协作边界、流程、验证和复用入口。",
                "",
                "- `AGENTS.md`：本次协作边界和执行纪律。",
                "- `flow.md`：本次日报从输入到输出的流程。",
                "- `testing.md`：本次最小验证和未覆盖风险。",
                "- `readme.md`：下次使用者的入口说明。",
            ]
        ),
    }
    for filename, text in docs.items():
        (companion_dir / filename).write_text(f"{text.rstrip()}\n", encoding="utf-8")
    return str(companion_dir)


def _get_report_output_path(target_date: str, mode: str = LEDGER_MODE_FROZEN, variant: str = REPORT_VARIANT_FULL) -> str:
    reports_dir = _reports_root()
    if mode == LEDGER_MODE_REPLAY:
        reports_dir = reports_dir / "replay"
    reports_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    variant_label = _report_variant_label(variant)
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
    if payload_key in {"wind_a_alternative", "csi500_index", "csi1000_index"}:
        payload = data.get(payload_key) or {}
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
        rows = data.get("hot_rank_top50") or data.get("hot_rank_top30") or []
        if not isinstance(rows, (list, tuple)):
            return False
        return len(rows) >= target
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
        if data_status.get(label) is False or not _critical_payload_valid(data, payload_key):
            failures.append(label)
    failures.extend(_sector_first_input_failures(data))
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


def _xuangubao_item_count(payload, list_key, count_key):
    if not isinstance(payload, dict):
        return 0
    rows = payload.get(list_key)
    if isinstance(rows, list):
        return len(rows)
    return int(_safe_float(payload.get(count_key), 0))


def _xuangubao_count_breakdown(payload):
    return {
        "news_count": _xuangubao_item_count(payload, "xuangubao_news", "news_count"),
        "plate_count": _xuangubao_item_count(payload, "xuangubao_plates", "plate_count"),
        "limit_up_reason_count": _xuangubao_item_count(
            payload,
            "xuangubao_limit_up_reasons",
            "limit_up_reason_count",
        ),
    }


def _xuangubao_breakdown_note(payload):
    counts = _xuangubao_count_breakdown(payload)
    if not any(counts.values()):
        return ""
    return "新闻{}条 / 盘面{}个 / 涨停解释{}条".format(
        counts["news_count"],
        counts["plate_count"],
        counts["limit_up_reason_count"],
    )


def _etf_turnover_series_has_coverage_anomaly(payload):
    if not isinstance(payload, dict):
        return False
    if payload.get("coverage_anomaly") is True or str(payload.get("coverage_status") or "") == "partial":
        return True
    rows = payload.get("rows") or payload.get("trend_rows") or []
    if not isinstance(rows, (list, tuple)):
        return False
    return any(isinstance(row, dict) and row.get("coverage_anomaly") is True for row in rows)


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
        return (
            isinstance(payload, dict)
            and bool(payload.get("rows") or [])
            and not _etf_turnover_series_has_coverage_anomaly(payload)
        )
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
                "note": _xuangubao_breakdown_note(data.get(payload_key)) if payload_key == "xuangubao_data" else "",
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


def _as_mapping(value):
    return value if isinstance(value, dict) else {}


QUOTE_SENSITIVE_DERIVED_KEYS = (
    "selection_workflow",
    "final_target_resolution",
    "final_target_resolution_audit",
    "two_layer_decision_payload",
    "sniper_target_derivation",
    "candidate_traces",
)


def _clear_quote_sensitive_derived_outputs(data):
    if not isinstance(data, dict):
        return
    targets = [data]
    context = data.get("execution_stage_context")
    snapshot = data.get("market_research_snapshot")
    if isinstance(context, dict):
        targets.append(context)
        nested_snapshot = context.get("market_research_snapshot")
        if isinstance(nested_snapshot, dict):
            targets.append(nested_snapshot)
    if isinstance(snapshot, dict):
        targets.append(snapshot)
    seen = set()
    for target in targets:
        marker = id(target)
        if marker in seen:
            continue
        seen.add(marker)
        for key in QUOTE_SENSITIVE_DERIVED_KEYS:
            target.pop(key, None)


def _has_meaningful_payload(value):
    if value is None:
        return False
    if isinstance(value, dict):
        return any(_has_meaningful_payload(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful_payload(item) for item in value)
    return bool(str(value).strip())


def _sector_first_sources(data):
    data = data if isinstance(data, dict) else {}
    context = _as_mapping(data.get("execution_stage_context"))
    snapshot = _as_mapping(data.get("market_research_snapshot"))
    workflow = data.get("selection_workflow") or context.get("selection_workflow") or snapshot.get("selection_workflow")
    if workflow and "selection_workflow" not in data:
        data = {**data, "selection_workflow": workflow}
    return data, context, snapshot


def _sector_first_chain_tracked(data):
    data, context, snapshot = _sector_first_sources(data)
    workflow = data.get("selection_workflow")
    if isinstance(workflow, dict) and (
        workflow.get("derivation_contract") == "sector_first_strict.v1"
        or workflow.get("schema_version") == "selection_workflow.v1"
    ):
        return True
    tracked_keys = {
        "market_state_snapshot",
        "mainline_turnover_summary",
        "current_sector_turnover_snapshot",
        "recent_sector_turnover_history",
        "sector_trend_snapshot",
        "sector_trend_snapshot_step1",
        "leader_memory_bank",
        "selected_position_candidate",
        "current_core_candidate",
        "position_decision",
        "final_target_resolution",
        "sniper_target_derivation",
    }
    return any(key in source for source in (data, context, snapshot) for key in tracked_keys)


def _sector_first_payload_for_key(data, context, snapshot, key):
    if key == "selection_workflow":
        workflow = data.get(key) or context.get(key) or snapshot.get(key)
        if isinstance(workflow, dict) and set(workflow.keys()) <= {"schema_version", "derivation_contract"}:
            return {}
        return workflow
    if key == "front_page_final_gate":
        return (
            data.get(key)
            or context.get(key)
            or snapshot.get(key)
            or _as_mapping(snapshot.get("final_gate"))
        )
    if key == "market_research_snapshot":
        payload = data.get(key) or context.get(key) or snapshot.get(key)
        if isinstance(payload, dict) and set(payload.keys()) <= {"selection_workflow", "sector_first_missing_fields", "missing_fields"}:
            return {}
        return payload
    if key == "selected_position_candidate":
        candidate_snapshot = _as_mapping(snapshot.get("candidate_snapshot"))
        return data.get(key) or context.get(key) or snapshot.get(key) or candidate_snapshot.get(key)
    if key == "current_core_candidate":
        candidate_snapshot = _as_mapping(snapshot.get("candidate_snapshot"))
        return data.get(key) or context.get(key) or snapshot.get(key) or candidate_snapshot.get(key)
    return data.get(key) or context.get(key) or snapshot.get(key)


def _sector_first_input_failures(data):
    if not _sector_first_chain_tracked(data):
        return []
    data, context, snapshot = _sector_first_sources(data)
    failures = []
    for label, keys in SECTOR_FIRST_CRITICAL_INPUTS:
        if not any(
            _has_meaningful_payload(_sector_first_payload_for_key(data, context, snapshot, key))
            for key in keys
        ):
            failures.append(label)
    return failures


def _build_sector_first_critical_checks(data):
    if not _sector_first_chain_tracked(data):
        return []
    data, context, snapshot = _sector_first_sources(data)
    checks = []
    for label, keys in SECTOR_FIRST_CRITICAL_INPUTS:
        present_keys = [
            key
            for key in keys
            if _has_meaningful_payload(_sector_first_payload_for_key(data, context, snapshot, key))
        ]
        checks.append(
            {
                "label": label,
                "step_label": "板块优先推导",
                "payload_key": ",".join(keys),
                "status": "success" if present_keys else "failed",
                "provider": "sector_first_strict.v1",
                "row_count": len(present_keys),
                "step_status": bool(present_keys),
            }
        )
    return checks


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
    if payload_key in {"wind_a_alternative", "csi500_index", "csi1000_index"}:
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
        if label in failures:
            status = "failed"
        elif tracked:
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
    sector_first_checks = _build_sector_first_critical_checks(data)
    checks.extend(sector_first_checks)
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
        "关键数据检查: {} / {}".format(
            _run_log_status(preflight.get("status", "unknown")),
            preflight.get("target_date", ""),
        )
    ]
    for check in preflight.get("checks") or []:
        lines.append(
            "- {label}: {status} | 来源={provider} | 数值={value} | 记录数={row_count}".format(
                label=check.get("label", ""),
                status=_run_log_status(check.get("status", "")),
                provider=check.get("provider", "unknown"),
                value=check.get("value", ""),
                row_count=check.get("row_count", ""),
            )
        )
    if preflight.get("decision_checks"):
        lines.append("决策数据检查:")
        for check in preflight.get("decision_checks") or []:
            line = "- {label}: {status} | 来源={provider} | 记录数={row_count} | 采集结果={step_status}".format(
                label=check.get("label", ""),
                status=_run_log_status(check.get("status", "")),
                provider=check.get("provider", "unknown"),
                row_count=check.get("row_count", ""),
                step_status=_run_log_status(check.get("step_status", "")),
            )
            if check.get("note"):
                line = f"{line} | 备注={check.get('note')}"
            lines.append(line)
            lines.extend(check.get("echo_lines") or [])
    if preflight.get("failures"):
        failures = "、".join(preflight.get("failures") or [])
        lines.append("关键数据不完整，停止生成；缺失项：{}；请优先修复数据缺失问题".format(failures))
    return lines


SNIPER_ASCII_FLOW = """```text
T日收盘候选
    |
    v
先分型
    |
    +-- 普通候选
    |      -> T+1等MA5回踩
    |      -> 09:50-10:10收回MA5/VWAP/0轴
    |      -> 成立50%，不成立不做
    |
    +-- 强核心
    |      -> 优先MA5回踩
    |      -> 健康低开转强可50%
    |      -> 全天强且偏离不大，尾盘最多25%
    |
    +-- 已有旧仓
    |      -> 先处理可卖旧仓
    |      -> 强势周期MA5入/MA7清/MA5T
    |
    +-- 失败仓/退潮
           -> 买点失败仓先处理
           -> 只给一次修复窗口
           -> 不修复就降风险
```"""


def _section_before(text: str, marker: str) -> str:
    text = str(text or "")
    if marker in text:
        return text.split(marker, 1)[0].rstrip()
    return text.strip()


def _section_from(text: str, marker: str) -> str:
    text = str(text or "")
    if marker in text:
        return text.split(marker, 1)[1].strip()
    return ""


def _markdown_heading_level(line: str) -> int | None:
    stripped = str(line or "").strip()
    if not stripped.startswith("#"):
        return None
    level = len(stripped) - len(stripped.lstrip("#"))
    if level <= 0 or level >= len(stripped) or stripped[level] != " ":
        return None
    return level


def _extract_markdown_section(text: str, heading: str) -> str:
    lines = str(text or "").splitlines()
    target = str(heading or "").strip()
    if not target:
        return ""
    target_level = _markdown_heading_level(target)
    if target_level is None:
        return ""

    start = None
    for index, line in enumerate(lines):
        if line.strip() == target:
            start = index
            break
    if start is None:
        return ""

    end = len(lines)
    for index in range(start + 1, len(lines)):
        level = _markdown_heading_level(lines[index])
        if level is not None and level <= target_level:
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _strip_first_markdown_heading(section: str) -> str:
    lines = str(section or "").splitlines()
    if lines and _markdown_heading_level(lines[0]) is not None:
        lines = lines[1:]
    return "\n".join(lines).strip()


def _rename_markdown_section(section: str, heading: str) -> str:
    body = _strip_first_markdown_heading(section)
    if not body:
        return ""
    return f"{heading}\n{body}"


def _section_before_any(text: str, markers: tuple[str, ...]) -> str:
    result = str(text or "")
    for marker in markers:
        if marker in result:
            result = result.split(marker, 1)[0].rstrip()
    return result.strip()


def _build_lightweight_market_section(full_report: str) -> str:
    market_section = _extract_markdown_section(full_report, "## 二、市场基底")
    index_section = _extract_markdown_section(market_section, "### 1. 指数与市场底色")
    index_section = _section_before_any(
        index_section,
        (
            "\n> 近25个交易日Top50成交额占比趋势",
            "\n**T-005**",
            "\n**T-005（PSQL）**",
        ),
    )
    status_section = _extract_markdown_section(market_section, "### 2. 市场状态结论")
    body = "\n\n".join(part for part in (index_section, status_section) if part.strip())
    if not body.strip():
        return ""
    return f"## 今日市场底色\n{body.strip()}"


def _build_lightweight_reading_map() -> str:
    return "\n".join(
        [
            "## 阅读地图",
            "| 顺序 | 先看什么 | 用途 |",
            "|---:|---|---|",
            "| 1 | 日报裁决总览、明日账户建议、最终结论 | 先确认仓位、旧仓和明日动作 |",
            "| 2 | 今日市场底色、周期与主线摘要 | 再判断市场和板块条件 |",
            "| 3 | 个股和持仓处理、明日三窗口 | 最后看观察对象、确认条件和取消条件 |",
            "| 4 | 证据附录、运行日志 | 只作复盘证据，不新增明日对象 |",
        ]
    )


def _remove_lightweight_reading_maps(text: str) -> str:
    lines = str(text or "").splitlines()
    cleaned = []
    index = 0
    while index < len(lines):
        if lines[index].strip() != "## 阅读地图":
            cleaned.append(lines[index])
            index += 1
            continue
        index += 1
        while index < len(lines):
            candidate = lines[index]
            if candidate.startswith("# ") or candidate.startswith("## "):
                break
            index += 1
    return "\n".join(cleaned).strip()


def _insert_lightweight_reading_map(text: str) -> str:
    base = _remove_lightweight_reading_maps(text).strip()
    reading_map_lines = _build_lightweight_reading_map().splitlines()
    if not base:
        return _build_lightweight_reading_map().strip() + "\n"
    lines = base.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            tail_start = index + 1
            while tail_start < len(lines) and not lines[tail_start].strip():
                tail_start += 1
            merged = (
                lines[: index + 1]
                + [""]
                + reading_map_lines
                + [""]
                + lines[tail_start:]
            )
            return "\n".join(merged).strip() + "\n"
    return "\n\n".join((_build_lightweight_reading_map().strip(), base)).strip() + "\n"


def build_lightweight_report_text(full_report: str, summary_report: str = "") -> str:
    full_report = str(full_report or "")
    intro = _section_before(full_report, "## 明日账户建议").strip() if "## 明日账户建议" in full_report else ""
    intro = _remove_lightweight_reading_maps(intro)
    account_section = _extract_markdown_section(full_report, "## 明日账户建议")
    market_section = _build_lightweight_market_section(full_report)
    stock_section = _rename_markdown_section(
        _extract_markdown_section(full_report, "## 五、个股解读"),
        "## 个股和持仓处理",
    )
    execution_section = _rename_markdown_section(
        _extract_markdown_section(full_report, "## 六、明日执行计划"),
        "## 明日三窗口",
    )
    conclusion_section = _rename_markdown_section(
        _extract_markdown_section(full_report, "## 七、最终结论"),
        "## 最终结论",
    )

    extracted_sections = [
        part
        for part in (
            intro,
            account_section,
            market_section,
            stock_section,
            execution_section,
            conclusion_section,
        )
        if part.strip()
    ]
    sniper_section = f"## 狙击手执行图\n{SNIPER_ASCII_FLOW}"
    if extracted_sections:
        parts = [*extracted_sections[:2], sniper_section, *extracted_sections[2:]]
    else:
        base = _section_before(full_report, "## 八、详细附录")
        if not base.strip():
            base = str(summary_report or full_report or "").strip()
        parts = [_remove_lightweight_reading_maps(base.rstrip()), sniper_section]
    parts.append(
        "## 证据与运行文件\n"
        "- 证据附录：同目录下 `A股日报_证据附录` 文件。\n"
        "- 运行日志：同目录下 `A股日报_运行日志` 文件。"
    )
    return _insert_lightweight_reading_map(
        "\n\n".join(part.strip() for part in parts if str(part).strip())
    )


def build_evidence_appendix_text(full_report: str, target_date: str = "") -> str:
    appendix = _section_from(full_report, "## 八、详细附录")
    if appendix:
        body = appendix
    else:
        body = "完整版未找到详细附录，保留原始报告供复盘检查。\n\n" + str(full_report or "").strip()
    title = f"# {target_date} A股日报证据附录".strip()
    return f"{title}\n\n## 证据附录\n\n{body.strip()}\n"


RUN_LOG_SAVED_PATH_PLACEHOLDER = "保存路径将在写入后由主流程打印。"
RUN_LOG_DETAIL_HEAD_ROWS = 5


def _run_log_cell(value) -> str:
    if value is None or value == "":
        return "-"
    text = str(value).replace("\n", "<br>")
    return text.replace("|", "\\|")


def _run_log_status(value) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    status = str(value or "").strip()
    return {
        "success": "成功",
        "failed": "失败",
        "unknown": "未知",
    }.get(status, status or "-")


def _markdown_table(headers, rows):
    headers = [str(header) for header in headers]
    lines = [
        "| " + " | ".join(_run_log_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows or []:
        values = list(row)
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        lines.append("| " + " | ".join(_run_log_cell(value) for value in values[: len(headers)]) + " |")
    return lines


def _preflight_failures_text(preflight):
    failures = preflight.get("failures") or []
    return "、".join(failures) if failures else "无"


def _render_run_log_overview_table(preflight, target_date):
    return _markdown_table(
        ["项目", "值"],
        [
            ("日期", target_date),
            ("关键数据检查", _run_log_status(preflight.get("status", "unknown"))),
            ("缺失项", _preflight_failures_text(preflight)),
        ],
    )


def _render_run_log_key_data_table(preflight):
    rows = []
    for check in preflight.get("checks") or []:
        rows.append(
            (
                check.get("label", ""),
                _run_log_status(check.get("status", "")),
                check.get("provider", "unknown"),
                check.get("value", ""),
                check.get("row_count", ""),
                _run_log_status(check.get("data_status")),
            )
        )
    if not rows:
        rows.append(("无", "-", "-", "-", "-", "-"))
    return _markdown_table(["指标", "状态", "来源", "数值", "记录数", "采集状态"], rows)


def _decision_check_note(check):
    note = str((check or {}).get("note") or "").strip()
    if note:
        return note
    echo_lines = check.get("echo_lines") or []
    if not echo_lines:
        return "-"
    first_line = str(echo_lines[0] or "").strip().rstrip(":：")
    detail_count = max(len(echo_lines) - 1, 0)
    if first_line and detail_count:
        return f"{first_line} {detail_count} 条"
    if first_line:
        return first_line
    return f"{len(echo_lines)} 条明细"


def _render_run_log_decision_data_table(preflight):
    rows = []
    for check in preflight.get("decision_checks") or []:
        rows.append(
            (
                check.get("label", ""),
                _run_log_status(check.get("status", "")),
                check.get("provider", "unknown"),
                check.get("row_count", ""),
                _run_log_status(check.get("step_status")),
                _decision_check_note(check),
            )
        )
    if not rows:
        rows.append(("无", "-", "-", "-", "-", "-"))
    return _markdown_table(["指标", "状态", "来源", "记录数", "采集结果", "备注"], rows)


def _parse_dash_detail_line(line):
    text = str(line or "").strip()
    if text.startswith("- "):
        text = text[2:].strip()
    match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)$", text)
    if not match:
        return None
    return match.groups()


def _compact_run_log_detail_rows(rows, *, head_rows=RUN_LOG_DETAIL_HEAD_ROWS):
    rows = list(rows or [])
    if len(rows) <= head_rows + 1:
        return rows
    omitted_count = len(rows) - head_rows - 1
    column_count = len(rows[0]) if rows and isinstance(rows[0], (list, tuple)) else 1
    omitted_row = ["已省略", f"{omitted_count} 条", "完整明细见对应数据表或报告正文"]
    if column_count > len(omitted_row):
        omitted_row.extend(["-"] * (column_count - len(omitted_row)))
    return [*rows[:head_rows], tuple(omitted_row[:column_count]), rows[-1]]


def _render_run_log_echo_tables(preflight):
    lines = []
    for check in preflight.get("decision_checks") or []:
        echo_lines = [str(line or "").strip() for line in (check.get("echo_lines") or []) if str(line or "").strip()]
        if not echo_lines:
            continue
        label = str(check.get("label") or "明细")
        title = echo_lines[0].rstrip(":：") or label
        detail_lines = echo_lines[1:] if len(echo_lines) > 1 else echo_lines
        parsed_rows = [_parse_dash_detail_line(line) for line in detail_lines]
        lines.extend(["", f"### {label}明细", ""])
        if parsed_rows and all(row is not None for row in parsed_rows):
            lines.extend(_markdown_table(["日期", "数量", "占比", "变化", "领先方向"], _compact_run_log_detail_rows(parsed_rows)))
        else:
            detail_rows = [(line.lstrip("- ").strip(),) for line in detail_lines]
            lines.extend(_markdown_table([title], _compact_run_log_detail_rows(detail_rows)))
    return lines


def _run_log_saved_path_rows(saved_paths):
    if not saved_paths:
        return [("待写入", RUN_LOG_SAVED_PATH_PLACEHOLDER)]
    return [(_report_variant_label(variant), saved_path) for variant, saved_path in (saved_paths or {}).items()]


def _render_run_log_saved_paths_table(saved_paths):
    return _markdown_table(["报告", "路径"], _run_log_saved_path_rows(saved_paths))


def build_run_log_text(preflight: dict, target_date: str, saved_paths: dict | None = None) -> str:
    preflight = preflight or {}
    lines = [
        f"# {target_date} A股日报运行日志",
        "",
        "## 运行概览",
        "",
        *_render_run_log_overview_table(preflight, target_date),
        "",
        "## 关键数据检查",
        "",
        *_render_run_log_key_data_table(preflight),
        "",
        "## 决策与辅助数据检查",
        "",
        *_render_run_log_decision_data_table(preflight),
        *_render_run_log_echo_tables(preflight),
        "",
        "## 日报一致性检查",
        "",
        *_markdown_table(["项目", "状态", "说明"], [("正文一致性", "待完成", "待主流程完成后以终端输出为准。")]),
        "",
        "## 生成文件路径",
        "",
        *_render_run_log_saved_paths_table(saved_paths),
    ]
    return "\n".join(lines).strip() + "\n"


def finalize_run_log_text(run_log_text: str, audit_result: dict | None = None) -> str:
    passed = bool((audit_result or {}).get("passed"))
    findings = (audit_result or {}).get("findings") or []
    status = "已通过" if passed else "未通过"
    if passed:
        note = "日报一致性检查通过"
    elif findings:
        note = "；".join(
            str(finding.get("message") or finding.get("code") or "检查未通过")
            for finding in findings
            if isinstance(finding, dict)
        )
    else:
        note = "检查结果待确认"
    old_table = "\n".join(
        _markdown_table(["项目", "状态", "说明"], [("正文一致性", "待完成", "待主流程完成后以终端输出为准。")])
    )
    new_table = "\n".join(_markdown_table(["项目", "状态", "说明"], [("正文一致性", status, note)]))
    return str(run_log_text or "").replace(old_table, new_table, 1)


def _raise_if_critical_data_missing(data, target_date, preflight=None):
    preflight = preflight or build_report_preflight(data, target_date)
    failures = preflight.get("failures") or []
    if not failures:
        return
    raise ReportCriticalDataMissingError(
        "关键数据不完整，停止生成：{}。\n日期：{}\n{}".format(
            "、".join(failures),
            target_date,
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
    market_language_translation: dict | None = None,
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
            market_language_translation=market_language_translation,
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


def _append_daily_discipline_to_sections(sections):
    sections = dict(sections or {})
    if not sections:
        return sections
    rendered = "\n".join(str(value or "") for value in sections.values())
    if "去弱留强是短线执行表达" in rendered:
        return sections
    discipline_lines = build_daily_discipline_note(build_llm_wiki_context())
    if not discipline_lines:
        return sections
    review_note = "\n".join(
        [discipline_lines[0].replace("## ", "### ", 1), *discipline_lines[1:]]
    )
    review = str(sections.get("review") or "").strip()
    sections["review"] = "\n\n".join(part for part in (review, review_note) if part).strip()
    return sections


def generate_markdown_report_from_sections(sections):
    sections = _append_daily_discipline_to_sections(sections or {})
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
    return sanitize_user_visible_text("\n\n".join(rendered_sections))


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
    persist_decision_ledger: bool = False,
    persist_candidate_traces: bool = False,
    candidate_trace_root_dir: str | None = None,
    postgres_only: bool = False,
    market_language_translation: dict | None = None,
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
        persist_decision_ledger=persist_decision_ledger,
        persist_candidate_traces=persist_candidate_traces,
        candidate_trace_root_dir=candidate_trace_root_dir,
        postgres_only=postgres_only,
        market_language_translation=market_language_translation,
    )


def build_report_outputs(
    data: Dict[str, Any],
    target_date: str,
    supplementary_perspective: str = "",
    has_personal_positions: bool = False,
    run_mode: str = LEDGER_MODE_FROZEN,
    position_report_text: str = "",
    emit_preflight: bool = True,
    persist_runtime_artifacts: bool = True,
    persist_decision_ledger: bool | None = None,
    market_language_translation: dict | None = None,
):
    if isinstance(data, dict):
        normalize_inferred_previous_target_records(data)
    preflight = build_report_preflight(data, target_date)
    if emit_preflight:
        for line in render_report_preflight_lines(preflight):
            print(line)
    _raise_if_critical_data_missing(data, target_date, preflight=preflight)
    if isinstance(data, dict):
        data["enable_selection_workflow_quote_backfill"] = True
        if data.get("enable_selection_workflow_quote_backfill"):
            _clear_quote_sensitive_derived_outputs(data)
    shared_runtime_cache = {}
    postgres_only = bool((data or {}).get("postgres_only"))
    persist_decision_ledger = bool(persist_runtime_artifacts) if persist_decision_ledger is None else bool(persist_decision_ledger)
    market_language_hash = (
        canonical_market_language_hash(market_language_translation)
        if isinstance(market_language_translation, dict)
        else ""
    )
    full_report = _render_report_with_display_mode(
        False,
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=False,
        persist_decision_ledger=bool(persist_decision_ledger),
        decision_ledger_root_dir=str(_module_dir().parent),
        persist_candidate_traces=bool(persist_runtime_artifacts),
        candidate_trace_root_dir=str(_module_dir().parent),
        emit_helper_diagnostics=True,
        shared_runtime_cache=shared_runtime_cache,
        postgres_only=postgres_only,
        market_language_translation=(
            copy.deepcopy(market_language_translation)
            if isinstance(market_language_translation, dict)
            else None
        ),
    )
    if market_language_hash and canonical_market_language_hash(market_language_translation) != market_language_hash:
        raise RuntimeError("市场语言研究证据在完整版渲染期间被改写，停止生成")
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
        market_language_translation=(
            copy.deepcopy(market_language_translation)
            if isinstance(market_language_translation, dict)
            else None
        ),
    )
    if market_language_hash and canonical_market_language_hash(market_language_translation) != market_language_hash:
        raise RuntimeError("市场语言研究证据在摘要版渲染期间被改写，停止生成")
    full_report = _sanitize_final_report_text(full_report, postgres_only=postgres_only)
    summary_report = _sanitize_final_report_text(summary_report, postgres_only=postgres_only)
    position_timeline = extract_position_timeline_markdown(position_report_text)
    if position_timeline:
        full_report = prepend_position_timeline_markdown(full_report, position_timeline)

    return {
        REPORT_VARIANT_FULL: _inject_report_variant_banner(full_report, REPORT_VARIANT_FULL),
        REPORT_VARIANT_SUMMARY: _inject_report_variant_banner(summary_report, REPORT_VARIANT_SUMMARY),
        REPORT_VARIANT_LIGHTWEIGHT: build_lightweight_report_text(full_report, summary_report),
        REPORT_VARIANT_EVIDENCE_APPENDIX: build_evidence_appendix_text(full_report, target_date),
        REPORT_VARIANT_RUN_LOG: build_run_log_text(preflight, target_date),
    }


def _sanitize_final_report_text(report_text: str, *, postgres_only: bool = False) -> str:
    try:
        from report import runtime as report_runtime
    except (ImportError, ModuleNotFoundError):
        return str(report_text or "")
    sanitizer = getattr(report_runtime, "_sanitize_report_lines", None)
    if not callable(sanitizer):
        return str(report_text or "")
    return "\n".join(
        sanitizer(
            str(report_text or "").splitlines(),
            postgres_only=postgres_only,
        )
    )


def persist_report_runtime_artifacts(
    data: Dict[str, Any],
    target_date: str,
    run_mode: str = LEDGER_MODE_FROZEN,
):
    """Persist render-time artifacts after required report facts are verified."""

    if not isinstance(data, dict):
        return {}

    execution_stage_context = data.get("execution_stage_context")
    if not isinstance(execution_stage_context, dict):
        execution_stage_context = {}
    market_research_snapshot = data.get("market_research_snapshot")
    if not isinstance(market_research_snapshot, dict):
        market_research_snapshot = {}

    try:
        from report import runtime as report_runtime
    except (ImportError, ModuleNotFoundError):
        return {}

    missing = object()
    previous_values = {
        "persist_decision_ledger": getattr(report_runtime, "persist_decision_ledger", missing),
        "persist_candidate_traces": getattr(report_runtime, "persist_candidate_traces", missing),
        "decision_ledger_root_dir": getattr(report_runtime, "decision_ledger_root_dir", missing),
        "candidate_trace_root_dir": getattr(report_runtime, "candidate_trace_root_dir", missing),
        "decision_ledger_postgres_only": getattr(report_runtime, "decision_ledger_postgres_only", missing),
    }

    root_dir = str(_module_dir().parent)
    postgres_only = bool(data.get("postgres_only"))
    try:
        report_runtime.persist_decision_ledger = True
        report_runtime.persist_candidate_traces = True
        report_runtime.decision_ledger_root_dir = root_dir
        report_runtime.candidate_trace_root_dir = root_dir
        report_runtime.decision_ledger_postgres_only = postgres_only
        decision_ledger_result = report_runtime._maybe_persist_decision_ledger(
            data=data,
            target_date=target_date,
            execution_stage_context=execution_stage_context,
            market_research_snapshot=market_research_snapshot,
        )
        if isinstance(decision_ledger_result, dict):
            decision_ledger_result = report_runtime._prune_decision_ledger_result_for_current_extreme_list(
                decision_ledger_result,
                target_date=target_date,
                execution_stage_context=execution_stage_context,
            )
            data["decision_ledger_artifacts"] = decision_ledger_result
        candidate_trace_result = report_runtime._maybe_persist_candidate_traces(
            data=data,
            target_date=target_date,
            execution_stage_context=execution_stage_context,
            run_mode=run_mode,
        )
        if isinstance(candidate_trace_result, dict):
            data["candidate_trace_artifact"] = candidate_trace_result
            execution_stage_context["candidate_trace_artifact"] = candidate_trace_result
        topic_lifecycle_snapshot = data.get("topic_lifecycle")
        if not isinstance(topic_lifecycle_snapshot, dict) or not topic_lifecycle_snapshot.get("cards"):
            try:
                topic_lifecycle_snapshot = build_topic_lifecycle_snapshot(data)
            except (TypeError, ValueError, KeyError):
                topic_lifecycle_snapshot = {}
            if isinstance(topic_lifecycle_snapshot, dict) and topic_lifecycle_snapshot.get("cards"):
                data["topic_lifecycle"] = topic_lifecycle_snapshot
        topic_lifecycle_result = None
        if isinstance(topic_lifecycle_snapshot, dict) and topic_lifecycle_snapshot.get("cards"):
            topic_lifecycle_result = write_topic_lifecycle_artifact(topic_lifecycle_snapshot, root_dir=root_dir)
            data["topic_lifecycle_artifact"] = topic_lifecycle_result
        return {
            "decision_ledger_artifacts": decision_ledger_result,
            "candidate_trace_artifact": candidate_trace_result,
            "topic_lifecycle_artifact": topic_lifecycle_result,
        }
    finally:
        for key, value in previous_values.items():
            if value is missing:
                try:
                    delattr(report_runtime, key)
                except AttributeError:
                    pass
            else:
                setattr(report_runtime, key, value)


class _InMemoryDailyReportHtmlFactService:
    def __init__(self, data):
        self.data = data if isinstance(data, dict) else {}

    def load_daily_report_snapshot(self, target_date):
        return {
            "source": f"in-memory.daily-report/{target_date}",
            "field_count": 1 if self.data else 0,
            "target_field_count": 1 if self.data else 0,
            "data": self.data,
        }

    def daily_report_fact_coverage(self, target_date):
        return {
            "tables": {
                "in_memory_daily_report": {
                    "target_count": 1 if self.data else 0,
                    "max_trade_date": target_date if self.data else "",
                }
            }
        }

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        mentions = self.data.get("extreme_conviction_mentions") or self.data.get("candidate_mentions") or []
        return mentions if isinstance(mentions, list) else []


def assert_report_required_facts_complete(data, target_date, *, run_mode=LEDGER_MODE_FROZEN):
    view = build_daily_report_view(
        target_date,
        _InMemoryDailyReportHtmlFactService(data),
        run_mode=run_mode,
    )
    missing = missing_required_fact_labels(view)
    if missing:
        raise ReportCriticalDataMissingError(
            "{} 日报关键数据不完整，停止生成：{}".format(target_date, "、".join(missing))
        )
    return view


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
    sync_replay_decision_ledger: bool = False,
):
    saved_paths = {}
    for variant, report_text in (report_outputs or {}).items():
        if output_dir:
            variant_label = _report_variant_label(variant)
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
    saved_paths[REPORT_COMPANION_DOCS] = save_report_companion_docs(saved_paths, target_date, mode=mode)
    _backfill_run_log_saved_paths(saved_paths)
    if mode == LEDGER_MODE_REPLAY and sync_replay_decision_ledger:
        _sync_replay_decision_ledger_from_full_report(
            saved_paths,
            target_date,
            output_dir=output_dir,
            postgres_only=postgres_only,
        )
    return saved_paths


def _backfill_run_log_saved_paths(saved_paths):
    run_log_path = (saved_paths or {}).get(REPORT_VARIANT_RUN_LOG)
    if not run_log_path:
        return None
    path = Path(run_log_path)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    table = "\n".join(_render_run_log_saved_paths_table(saved_paths))
    marker = "## 生成文件路径"
    if marker in text:
        lines = text.splitlines()
        start = next((index for index, line in enumerate(lines) if line.strip() == marker), None)
        if start is not None:
            end = len(lines)
            for index in range(start + 1, len(lines)):
                if lines[index].startswith("## "):
                    end = index
                    break
            text = "\n".join([*lines[:start], marker, "", *table.splitlines(), *lines[end:]]).strip() + "\n"
        elif RUN_LOG_SAVED_PATH_PLACEHOLDER in text:
            text = text.replace(RUN_LOG_SAVED_PATH_PLACEHOLDER, "", 1)
    path.write_text(text, encoding="utf-8")
    return str(path)


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
        write_decision_revision=False,
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
