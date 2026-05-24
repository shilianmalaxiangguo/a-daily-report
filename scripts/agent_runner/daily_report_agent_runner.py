from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from daily_report_entry_demo import replay_from_snapshot
from daily_report_render import build_report_outputs, save_report_outputs
from report.decision_ledger import write_decision_ledger_artifacts_from_markdown_report
from report.report_run_audit import audit_daily_report_run


@dataclass(frozen=True)
class DailyReportAgentRequest:
    target_date: str
    mode: str = "replay"
    update_decision_ledger: bool = True
    review_prior_participation: bool = True
    output_variant: str = "full"


@dataclass(frozen=True)
class DailyReportAgentDependencies:
    load_data: Callable[[DailyReportAgentRequest], dict[str, Any]] | None = None
    build_report_outputs: Callable[..., dict[str, str]] = build_report_outputs
    save_report_outputs: Callable[..., dict[str, str]] = save_report_outputs
    write_decision_ledger_from_markdown: Callable[..., dict[str, Any]] = (
        write_decision_ledger_artifacts_from_markdown_report
    )
    audit_run: Callable[..., dict[str, Any]] = audit_daily_report_run
    now: Callable[[], datetime] = datetime.now


def _default_load_data(request: DailyReportAgentRequest) -> dict[str, Any]:
    if request.mode == "replay":
        replay_result = replay_from_snapshot(request.target_date)
        if isinstance(replay_result, tuple):
            return replay_result[0] or {}
        return replay_result or {}
    raise RuntimeError("当前 runner 仅支持 replay 模式")


class DailyReportAgentRunner:
    def __init__(
        self,
        *,
        root_dir: str | Path = ".",
        dependencies: DailyReportAgentDependencies | None = None,
    ):
        self.root_dir = Path(root_dir)
        self.dependencies = dependencies or DailyReportAgentDependencies()

    def run(self, request: DailyReportAgentRequest) -> dict[str, Any]:
        started_at = self.dependencies.now().isoformat(timespec="seconds")
        run_dir = self.root_dir / "reports" / "runs" / request.target_date
        run_dir.mkdir(parents=True, exist_ok=True)

        status = "success"
        error: dict[str, str] | None = None
        data: dict[str, Any] = {}
        report_outputs: dict[str, str] = {}
        output_paths: dict[str, str] = {}
        decision_ledger_result: dict[str, Any] | None = None
        audit_result: dict[str, Any] | None = None

        try:
            load_data = self.dependencies.load_data or _default_load_data
            data = load_data(request)
            if request.mode == "replay" and not data:
                raise RuntimeError(f"回放数据不存在，停止生成：{request.target_date}")
            report_outputs = self.dependencies.build_report_outputs(
                data,
                request.target_date,
                run_mode=request.mode,
                emit_preflight=False,
            )
            output_paths = self.dependencies.save_report_outputs(
                report_outputs,
                request.target_date,
                mode=request.mode,
                output_dir=str(run_dir),
            )
            full_report_path = _select_full_report_path(output_paths)
            full_markdown = _select_full_report_markdown(report_outputs, full_report_path)

            if request.update_decision_ledger and full_report_path:
                decision_ledger_result = self.dependencies.write_decision_ledger_from_markdown(
                    full_report_path,
                    trade_date=request.target_date,
                    market_branch="以最终日报为准",
                    sector_relationship_state="以最终日报为准",
                    root_dir=str(self.root_dir),
                    generated_at=started_at,
                )

            audit_result = self.dependencies.audit_run(
                target_date=request.target_date,
                data=data,
                report_markdown=full_markdown,
                decision_ledger_result=decision_ledger_result,
                decision_ledger_required=request.update_decision_ledger,
            )
            if not audit_result.get("passed"):
                status = "needs_review"
        except Exception as exc:
            status = "error"
            error = {"type": type(exc).__name__, "message": str(exc)}
            audit_result = {
                "target_date": request.target_date,
                "passed": False,
                "usable": False,
                "findings": [
                    {
                        "source": "runner",
                        "code": "runner_error",
                        "message": str(exc),
                    }
                ],
                "finding_count": 1,
            }

        finished_at = self.dependencies.now().isoformat(timespec="seconds")
        payload = {
            "target_date": request.target_date,
            "mode": request.mode,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "run_dir": str(run_dir),
            "outputs": output_paths,
            "audit": audit_result,
            "decision_ledger": _compact_decision_ledger(decision_ledger_result),
            "error": error,
        }

        self._write_json(run_dir / "run.json", payload)
        self._write_json(run_dir / "audit.json", audit_result)
        (run_dir / "overview.md").write_text(_render_overview(payload), encoding="utf-8")
        (run_dir / "review_queue.md").write_text(
            _render_review_queue(audit_result, decision_ledger_result),
            encoding="utf-8",
        )
        return payload

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _select_full_report_path(output_paths: dict[str, str]) -> str:
    if "full" in output_paths:
        return output_paths["full"]
    if output_paths:
        return next(iter(output_paths.values()))
    return ""


def _select_full_report_markdown(report_outputs: dict[str, str], full_report_path: str) -> str:
    if "full" in report_outputs:
        return report_outputs["full"]
    if report_outputs:
        return next(iter(report_outputs.values()))
    if full_report_path:
        return Path(full_report_path).read_text(encoding="utf-8")
    return ""


def _compact_decision_ledger(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {"case_count": 0}
    return {
        "case_count": int(result.get("case_count") or 0),
        "snapshot_path": result.get("snapshot_path", ""),
        "index_path": result.get("index_path", ""),
        "fact_db_sync": result.get("fact_db_sync") or {},
    }


def _render_overview(payload: dict[str, Any]) -> str:
    audit = payload.get("audit") or {}
    ledger = payload.get("decision_ledger") or {}
    lines = [
        f"# Daily Report Agent Run {payload.get('target_date', '')}",
        "",
        f"- status: {payload.get('status', '')}",
        f"- mode: {payload.get('mode', '')}",
        f"- usable: {audit.get('usable', False)}",
        f"- audit_passed: {audit.get('passed', False)}",
        f"- finding_count: {audit.get('finding_count', 0)}",
        f"- decision_ledger_cases: {ledger.get('case_count', 0)}",
        "",
        "## Outputs",
    ]
    for variant, path in (payload.get("outputs") or {}).items():
        lines.append(f"- {variant}: {path}")
    if payload.get("error"):
        lines.extend(
            [
                "",
                "## Error",
                f"- {payload['error'].get('type')}: {payload['error'].get('message')}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_review_queue(
    audit: dict[str, Any] | None,
    decision_ledger_result: dict[str, Any] | None,
) -> str:
    lines = ["# Review Queue", ""]
    findings = (audit or {}).get("findings") or []
    pending_records = _pending_review_records(decision_ledger_result)

    if not findings and not pending_records:
        lines.append("- [ ] No manual review items from this run.")
        return "\n".join(lines).rstrip() + "\n"

    for finding in findings:
        lines.append(f"- [ ] {finding.get('source', 'runner')}:{finding.get('code', 'unknown')}")
        message = finding.get("message") or ""
        if message:
            lines.append(f"  - reason: {message}")
        lines.append("  - human judgment:")
        lines.append("  - follow-up:")

    for record in pending_records:
        stock_name = record.get("stock_name") or record.get("name") or ""
        stock_code = record.get("stock_code") or record.get("code") or ""
        lines.append(f"- [ ] participation_review pending: {stock_name}({stock_code})")
        lines.append("  - reason: prior planned participation is waiting for explicit facts.")
        lines.append("  - human judgment:")
        lines.append("  - follow-up:")

    return "\n".join(lines).rstrip() + "\n"


def _pending_review_records(decision_ledger_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    index = (decision_ledger_result or {}).get("index") or {}
    records: list[dict[str, Any]] = []
    for source_record in index.get("records") or index.get("latest_records") or []:
        if isinstance(source_record, dict):
            records.append(source_record)
    for stock_records in (index.get("by_stock_code") or {}).values():
        if isinstance(stock_records, list):
            records.extend(record for record in stock_records if isinstance(record, dict))
        elif isinstance(stock_records, dict):
            records.append(stock_records)
    pending = []
    for record in records:
        status = record.get("participation_review_status")
        if status in {
            None,
            "",
            "pending",
            "waiting",
            "waiting_for_facts",
            "等待复盘",
            "等待窗口复盘",
        }:
            pending.append(record)
    return pending
