from __future__ import annotations

import inspect
from typing import Any, Callable

from daily_report_render import build_report_preflight
from report.position_context import existing_position_summary_from_context
from report.report_acceptance_audit import audit_report_markdown


def _normalize_preflight_findings(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for label in preflight.get("failures") or []:
        findings.append(
            {
                "source": "preflight",
                "code": "critical_data_incomplete",
                "message": f"关键数据不完整，停止生成：{label}",
                "label": label,
            }
        )
    return findings


def _normalize_report_findings(report_acceptance: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in report_acceptance.get("findings") or []:
        finding = {
            "source": "report_acceptance",
            "code": item.get("code") or "report_acceptance_failed",
            "message": item.get("message") or "",
        }
        if "line" in item:
            finding["line"] = item.get("line")
        findings.append(finding)
    return findings


def _normalize_decision_ledger_result(
    decision_ledger_result: dict[str, Any] | None,
    *,
    required: bool,
) -> dict[str, Any]:
    if not decision_ledger_result:
        finding = {
            "source": "decision_ledger",
            "code": "decision_ledger_missing",
            "message": "判断账本未写入，需人工确认",
        }
        return {
            "passed": not required,
            "case_count": 0,
            "snapshot_path": "",
            "index_path": "",
            "fact_db_sync": {},
            "findings": [finding] if required else [],
        }

    fact_db_sync = decision_ledger_result.get("fact_db_sync") or {}
    findings = list(decision_ledger_result.get("findings") or [])
    fact_db_sync_passed = fact_db_sync.get("status") != "failed"
    if not fact_db_sync_passed:
        findings.append(
            {
                "source": "decision_ledger",
                "code": "fact_db_sync_failed",
                "message": "本地事实库同步失败，判断账本文件已保留",
            }
        )

    return {
        "passed": bool(decision_ledger_result.get("passed", True)) and fact_db_sync_passed,
        "case_count": int(decision_ledger_result.get("case_count") or 0),
        "snapshot_path": decision_ledger_result.get("snapshot_path", ""),
        "index_path": decision_ledger_result.get("index_path", ""),
        "fact_db_sync": fact_db_sync,
        "findings": findings,
    }


def _audit_markdown(
    audit_markdown: Callable[..., dict[str, Any]],
    report_markdown: str,
    companion_html: str | None,
    *,
    expected_position_summary: dict[str, Any] | None = None,
    source_path: str | None = None,
    prefer_postgres_history: bool = False,
) -> dict[str, Any]:
    try:
        parameters = inspect.signature(audit_markdown).parameters
    except (TypeError, ValueError):
        return audit_markdown(report_markdown)

    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    kwargs: dict[str, Any] = {}
    if companion_html is not None and ("companion_html" in parameters or accepts_kwargs):
        kwargs["companion_html"] = companion_html
    if expected_position_summary and ("expected_position_summary" in parameters or accepts_kwargs):
        kwargs["expected_position_summary"] = expected_position_summary
    if source_path is not None and ("source_path" in parameters or accepts_kwargs):
        kwargs["source_path"] = source_path
    if "prefer_postgres_history" in parameters or accepts_kwargs:
        kwargs["prefer_postgres_history"] = bool(prefer_postgres_history)
    return audit_markdown(report_markdown, **kwargs)


def audit_daily_report_run(
    *,
    target_date: str,
    data: dict[str, Any],
    report_markdown: str,
    companion_html: str | None = None,
    source_path: str | None = None,
    prefer_postgres_history: bool = False,
    decision_ledger_result: dict[str, Any] | None = None,
    decision_ledger_required: bool = False,
    build_preflight: Callable[[dict[str, Any], str], dict[str, Any]] = build_report_preflight,
    audit_markdown: Callable[..., dict[str, Any]] = audit_report_markdown,
) -> dict[str, Any]:
    preflight = build_preflight(data, target_date)
    report_acceptance = _audit_markdown(
        audit_markdown,
        report_markdown,
        companion_html,
        expected_position_summary=existing_position_summary_from_context(data),
        source_path=source_path,
        prefer_postgres_history=prefer_postgres_history,
    )
    decision_ledger = _normalize_decision_ledger_result(
        decision_ledger_result,
        required=decision_ledger_required,
    )

    findings = []
    findings.extend(_normalize_preflight_findings(preflight))
    findings.extend(_normalize_report_findings(report_acceptance))
    findings.extend(decision_ledger.get("findings") or [])

    usable = preflight.get("status") != "failed"
    passed = (
        usable
        and bool(report_acceptance.get("passed"))
        and bool(decision_ledger.get("passed"))
    )

    return {
        "target_date": target_date,
        "passed": passed,
        "usable": usable,
        "preflight": preflight,
        "report_acceptance": report_acceptance,
        "decision_ledger": decision_ledger,
        "findings": findings,
        "finding_count": len(findings),
    }
