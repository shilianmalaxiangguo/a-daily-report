from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


QUALITY_SCORE_SCHEMA = "report_quality_score.v1"
QUALITY_LEDGER_RECORD_SCHEMA = "report_quality_ledger_record.v1"
QUALITY_LEDGER_WRITE_SCHEMA = "report_quality_ledger_write.v1"
QUALITY_LEDGER_DIR = Path(".generated") / "report-quality"
QUALITY_LEDGER_INDEX = "index.jsonl"


def build_report_quality_score(
    *,
    target_date: str,
    run_status: str,
    mode: str = "",
    preflight: Mapping[str, Any] | None = None,
    audit_result: Mapping[str, Any] | None = None,
    decision_ledger_result: Mapping[str, Any] | None = None,
    output_paths: Mapping[str, Any] | None = None,
    error: BaseException | str | None = None,
    report_expected: bool = True,
    decision_ledger_expected: bool = True,
) -> dict[str, Any]:
    preflight = preflight or {}
    audit_result = audit_result or {}
    decision_ledger_result = decision_ledger_result or {}
    output_paths = output_paths or {}

    categories = _build_categories(
        run_status=run_status,
        preflight=preflight,
        audit_result=audit_result,
        decision_ledger_result=decision_ledger_result,
        output_paths=output_paths,
        error=error,
        report_expected=report_expected,
        decision_ledger_expected=decision_ledger_expected,
    )
    score = _score_categories(categories)
    return {
        "schema_version": QUALITY_SCORE_SCHEMA,
        "target_date": target_date,
        "mode": mode,
        "status": _quality_status(score, categories),
        "score": score,
        "max_score": 100,
        "finding_count": _finding_count(preflight, audit_result, error),
        "categories": categories,
        "top_findings": _top_findings(preflight, audit_result, error),
    }


def persist_report_quality_score(
    score: Mapping[str, Any],
    *,
    root_dir: str | Path = ".",
    run_id: str = "",
    recorded_at: str = "",
) -> dict[str, Any]:
    recorded_at = recorded_at or datetime.now().isoformat(timespec="seconds")
    try:
        ledger_dir = Path(root_dir) / QUALITY_LEDGER_DIR
        ledger_dir.mkdir(parents=True, exist_ok=True)
        score_path = ledger_dir / _quality_score_file_name(score)
        index_path = ledger_dir / QUALITY_LEDGER_INDEX
        record = _build_quality_ledger_record(
            score,
            score_path=score_path,
            recorded_at=recorded_at,
            run_id=run_id,
        )
        snapshot_payload = {
            "schema_version": QUALITY_LEDGER_RECORD_SCHEMA,
            "recorded_at": recorded_at,
            "run_id": run_id,
            "record": record,
            "report_quality_score": dict(score),
        }
        score_path.write_text(
            json.dumps(snapshot_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        return {
            "schema_version": QUALITY_LEDGER_WRITE_SCHEMA,
            "status": "written",
            "score_path": str(score_path),
            "index_path": str(index_path),
            "recorded_at": recorded_at,
        }
    except Exception as exc:
        return {
            "schema_version": QUALITY_LEDGER_WRITE_SCHEMA,
            "status": "error",
            "error": str(exc),
            "recorded_at": recorded_at,
        }


def _build_categories(
    *,
    run_status: str,
    preflight: Mapping[str, Any],
    audit_result: Mapping[str, Any],
    decision_ledger_result: Mapping[str, Any],
    output_paths: Mapping[str, Any],
    error: BaseException | str | None,
    report_expected: bool,
    decision_ledger_expected: bool,
) -> dict[str, dict[str, Any]]:
    preflight_failures = list(preflight.get("failures") or [])
    audit_findings = list(audit_result.get("findings") or [])
    decision_ledger_findings = list(decision_ledger_result.get("findings") or [])
    return {
        "run_completion": {
            "passed": run_status in {"success", "needs_review"} and error is None,
            "weight": 20,
            "finding_count": 1 if error is not None else 0,
        },
        "data_readiness": {
            "passed": not preflight_failures and preflight.get("status") != "failed",
            "weight": 20,
            "finding_count": len(preflight_failures),
        },
        "report_acceptance": {
            "passed": bool(audit_result.get("passed", run_status == "success")),
            "weight": 25,
            "finding_count": len(audit_findings),
        },
        "decision_ledger": {
            "passed": (
                _decision_ledger_passed(audit_result, decision_ledger_result)
                if decision_ledger_expected
                else True
            ),
            "weight": 20,
            "finding_count": (
                _decision_ledger_finding_count(audit_result, decision_ledger_result, decision_ledger_findings)
                if decision_ledger_expected
                else 0
            ),
        },
        "artifact_integrity": {
            "passed": bool(output_paths) or run_status == "error" or not report_expected,
            "weight": 15,
            "finding_count": 0 if (bool(output_paths) or run_status == "error" or not report_expected) else 1,
        },
    }


def _build_quality_ledger_record(
    score: Mapping[str, Any],
    *,
    score_path: Path,
    recorded_at: str,
    run_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": QUALITY_LEDGER_RECORD_SCHEMA,
        "recorded_at": recorded_at,
        "run_id": run_id,
        "target_date": str(score.get("target_date") or ""),
        "mode": str(score.get("mode") or ""),
        "status": str(score.get("status") or ""),
        "score": score.get("score"),
        "max_score": score.get("max_score"),
        "finding_count": score.get("finding_count"),
        "top_findings": list(score.get("top_findings") or [])[:10],
        "score_path": str(score_path),
    }


def _quality_score_file_name(score: Mapping[str, Any]) -> str:
    target_date = _safe_file_token(score.get("target_date"), default="unknown-date")
    mode = _safe_file_token(score.get("mode"), default="default")
    return f"{target_date}_{mode}.json"


def _safe_file_token(value: Any, *, default: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    text = str(value or "").strip()
    cleaned = "".join(char if char in allowed else "_" for char in text).strip("._")
    return cleaned or default


def _decision_ledger_passed(
    audit_result: Mapping[str, Any],
    decision_ledger_result: Mapping[str, Any],
) -> bool:
    audit_ledger = audit_result.get("decision_ledger")
    if isinstance(audit_ledger, Mapping):
        return bool(audit_ledger.get("passed"))
    if not decision_ledger_result:
        return False
    fact_db_sync = decision_ledger_result.get("fact_db_sync") or {}
    return bool(decision_ledger_result.get("passed", True)) and fact_db_sync.get("status") != "failed"


def _decision_ledger_finding_count(
    audit_result: Mapping[str, Any],
    decision_ledger_result: Mapping[str, Any],
    decision_ledger_findings: list[Any],
) -> int:
    if isinstance(audit_result.get("decision_ledger"), Mapping):
        return len(list(audit_result.get("decision_ledger", {}).get("findings") or []))
    if not decision_ledger_result:
        return 1
    return len(decision_ledger_findings)


def _score_categories(categories: Mapping[str, Mapping[str, Any]]) -> int:
    total = 0
    for category in categories.values():
        weight = int(category.get("weight") or 0)
        if category.get("passed"):
            total += weight
    return total


def _quality_status(score: int, categories: Mapping[str, Mapping[str, Any]]) -> str:
    if not categories.get("run_completion", {}).get("passed"):
        return "error"
    if score >= 100:
        return "pass"
    if score >= 75:
        return "needs_review"
    return "fail"


def _finding_count(
    preflight: Mapping[str, Any],
    audit_result: Mapping[str, Any],
    error: BaseException | str | None,
) -> int:
    count = int(audit_result.get("finding_count") or len(audit_result.get("findings") or []))
    count += len(preflight.get("failures") or [])
    if error is not None:
        count += 1
    return count


def _top_findings(
    preflight: Mapping[str, Any],
    audit_result: Mapping[str, Any],
    error: BaseException | str | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for label in list(preflight.get("failures") or [])[:10]:
        findings.append({"source": "preflight", "code": "critical_data_incomplete", "message": str(label)})
    for item in list(audit_result.get("findings") or [])[:10]:
        if isinstance(item, Mapping):
            findings.append(
                {
                    "source": str(item.get("source") or "audit"),
                    "code": str(item.get("code") or "audit_finding"),
                    "message": str(item.get("message") or ""),
                }
            )
    if error is not None:
        findings.append({"source": "run", "code": "run_error", "message": str(error)})
    return findings[:10]
