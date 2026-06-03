# Daily Report Agent Runner Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first project-level `DailyReportAgentRunner` slice that runs the existing report flow, writes a run folder, audits the report, updates the decision ledger, and produces a review queue.

**Architecture:** Add a small orchestration layer instead of replacing the existing report engine. The runner calls existing generation functions, existing preflight/audit logic, and existing decision-ledger writers, then writes `reports/runs/<trade-date>/overview.md`, `run.json`, `review_queue.md`, and `audit.json`.

**Tech Stack:** Python 3.14, `unittest`, existing modules under `scripts/daily_report_render.py`, `scripts/report/report_acceptance_audit.py`, and `scripts/report/decision_ledger.py`.

---

## Scope

### In Scope

- Create a runner module under `scripts/agent_runner/`.
- Add a pure report-run audit wrapper under `scripts/report/`.
- Add focused unit tests for audit normalization, run artifact writing, decision-ledger integration, and pending review queue rendering.
- Preserve existing generation and ledger internals.

### Out of Scope

- No always-on service.
- No scheduler.
- No snap-ui changes.
- No automatic trading.
- No broad rewrite of `daily_report_entry_demo.py`.
- No separate decision-ledger format.

### Done Definition

- A single runner object can execute with injected fake generation functions and write:
  - `reports/runs/<trade-date>/overview.md`
  - `reports/runs/<trade-date>/run.json`
  - `reports/runs/<trade-date>/review_queue.md`
  - `reports/runs/<trade-date>/audit.json`
- The runner calls existing report audit and decision-ledger interfaces through injectable functions.
- Critical-data failures, markdown audit failures, and decision-ledger persistence failures appear in `run.json` and `review_queue.md`.
- Targeted unit tests pass using `.generated/venv-py314/bin/python3.14 -m unittest ...`.

## File Structure

- Create: `scripts/report/report_run_audit.py`
  - Pure wrapper around `build_report_preflight(...)`, `audit_report_markdown(...)`, and decision-ledger result inspection.
- Create: `scripts/agent_runner/daily_report_agent_runner.py`
  - `DailyReportAgentRequest`, `DailyReportAgentRunner`, `DailyReportAgentDependencies`, run artifact rendering.
- Create: `scripts/agent_runner/__init__.py`
  - Export runner API.
- Create: `tests/test_report_run_audit.py`
  - Unit tests for normalized audit result.
- Create: `tests/test_daily_report_agent_runner.py`
  - Unit tests with fake dependencies and temporary output roots.
- Modify only if needed: no existing runtime modules should be changed for the first slice.

## Task 1: Report Run Audit Wrapper

**Files:**
- Create: `scripts/report/report_run_audit.py`
- Test: `tests/test_report_run_audit.py`

- [x] **Step 1: Write failing tests for preflight and markdown audit aggregation**

Create `tests/test_report_run_audit.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.report_run_audit import audit_daily_report_run


class ReportRunAuditTest(unittest.TestCase):
    def test_audit_combines_preflight_and_report_findings(self):
        def fake_preflight(data, target_date):
            return {
                "target_date": target_date,
                "status": "failed",
                "failures": ["中证全指"],
                "checks": [
                    {
                        "label": "中证全指",
                        "status": "failed",
                        "provider": "unknown",
                        "value": "",
                        "row_count": 0,
                    }
                ],
            }

        def fake_report_audit(markdown, companion_html=None):
            return {
                "passed": False,
                "finding_count": 1,
                "findings": [
                    {
                        "code": "duplicate_no_trade",
                        "message": "duplicate no-participation conclusion",
                        "line": 12,
                    }
                ],
            }

        result = audit_daily_report_run(
            target_date="2026-05-24",
            data={"sample": True},
            report_markdown="# report",
            build_preflight=fake_preflight,
            audit_markdown=fake_report_audit,
            decision_ledger_result={"case_count": 1, "snapshot_path": "data/decision-ledger/2026-05-24.json"},
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["usable"])
        self.assertEqual(result["target_date"], "2026-05-24")
        self.assertEqual(
            [(finding["source"], finding["code"]) for finding in result["findings"]],
            [
                ("preflight", "critical_data_incomplete"),
                ("report_acceptance", "duplicate_no_trade"),
            ],
        )
        self.assertTrue(result["decision_ledger"]["passed"])

    def test_audit_flags_missing_decision_ledger_when_required(self):
        result = audit_daily_report_run(
            target_date="2026-05-24",
            data={},
            report_markdown="# report",
            build_preflight=lambda data, target_date: {"status": "success", "failures": [], "checks": []},
            audit_markdown=lambda markdown, companion_html=None: {"passed": True, "findings": [], "finding_count": 0},
            decision_ledger_required=True,
            decision_ledger_result=None,
        )

        self.assertFalse(result["passed"])
        self.assertTrue(result["usable"])
        self.assertFalse(result["decision_ledger"]["passed"])
        self.assertEqual(result["findings"][0]["source"], "decision_ledger")
        self.assertEqual(result["findings"][0]["code"], "decision_ledger_missing")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_run_audit
```

Expected: fails with `ModuleNotFoundError: No module named 'report.report_run_audit'`.

- [x] **Step 3: Implement minimal audit wrapper**

Create `scripts/report/report_run_audit.py`:

```python
from __future__ import annotations

from typing import Any, Callable

from daily_report_render import build_report_preflight
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
            "code": item.get("code", "report_acceptance_failed"),
            "message": item.get("message", ""),
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
        if required:
            return {
                "passed": False,
                "case_count": 0,
                "snapshot_path": "",
                "index_path": "",
                "fact_db_sync": {},
                "findings": [
                    {
                        "source": "decision_ledger",
                        "code": "decision_ledger_missing",
                        "message": "判断账本未写入，需人工确认",
                    }
                ],
            }
        return {
            "passed": True,
            "case_count": 0,
            "snapshot_path": "",
            "index_path": "",
            "fact_db_sync": {},
            "findings": [],
        }

    case_count = int(decision_ledger_result.get("case_count") or 0)
    findings: list[dict[str, Any]] = []
    fact_db_sync = decision_ledger_result.get("fact_db_sync") or {}
    if fact_db_sync.get("status") == "failed":
        findings.append(
            {
                "source": "decision_ledger",
                "code": "fact_db_sync_failed",
                "message": "本地事实库同步失败，判断账本文件已保留",
            }
        )
    return {
        "passed": not findings,
        "case_count": case_count,
        "snapshot_path": decision_ledger_result.get("snapshot_path", ""),
        "index_path": decision_ledger_result.get("index_path", ""),
        "fact_db_sync": fact_db_sync,
        "findings": findings,
    }


def audit_daily_report_run(
    *,
    target_date: str,
    data: dict[str, Any],
    report_markdown: str,
    companion_html: str | None = None,
    decision_ledger_result: dict[str, Any] | None = None,
    decision_ledger_required: bool = False,
    build_preflight: Callable[[dict[str, Any], str], dict[str, Any]] = build_report_preflight,
    audit_markdown: Callable[..., dict[str, Any]] = audit_report_markdown,
) -> dict[str, Any]:
    preflight = build_preflight(data, target_date)
    report_acceptance = audit_markdown(report_markdown, companion_html=companion_html)
    decision_ledger = _normalize_decision_ledger_result(
        decision_ledger_result,
        required=decision_ledger_required,
    )
    findings = []
    findings.extend(_normalize_preflight_findings(preflight))
    findings.extend(_normalize_report_findings(report_acceptance))
    findings.extend(decision_ledger.get("findings") or [])
    usable = preflight.get("status") != "failed"
    passed = usable and bool(report_acceptance.get("passed")) and bool(decision_ledger.get("passed"))
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
```

- [x] **Step 4: Run test to verify it passes**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_run_audit
```

Expected: `OK`.

## Task 2: Runner Artifacts And Review Queue

**Files:**
- Create: `scripts/agent_runner/__init__.py`
- Create: `scripts/agent_runner/daily_report_agent_runner.py`
- Test: `tests/test_daily_report_agent_runner.py`

- [x] **Step 1: Write failing tests for runner artifact writing**

Create `tests/test_daily_report_agent_runner.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_runner.daily_report_agent_runner import (
    DailyReportAgentDependencies,
    DailyReportAgentRequest,
    DailyReportAgentRunner,
)


class DailyReportAgentRunnerTest(unittest.TestCase):
    def test_runner_writes_run_folder_overview_json_audit_and_review_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def load_data(request):
                return {"data_status": {}, "sections": {"summary": "## 七、最终结论\n50% / 标准进攻"}}

            def build_outputs(data, target_date, **kwargs):
                return {"full": "# full report\n\n## 七、最终结论\n50% / 标准进攻", "summary": "# summary"}

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                full_path = output_root / f"{target_date}_A股日报_完整版_replay.md"
                summary_path = output_root / f"{target_date}_A股日报_执行摘要_replay.md"
                full_path.write_text(outputs["full"], encoding="utf-8")
                summary_path.write_text(outputs["summary"], encoding="utf-8")
                return {"full": str(full_path), "summary": str(summary_path)}

            def write_ledger(report_path, **kwargs):
                return {
                    "snapshot_path": str(root / "data" / "decision-ledger" / "2026-05-24.json"),
                    "index_path": str(root / "data" / "decision-ledger" / "index.json"),
                    "case_count": 1,
                    "fact_db_sync": {"status": "success", "rows": 1},
                    "index": {
                        "records": [
                            {
                                "stock_code": "300000",
                                "stock_name": "测试股份",
                                "participation_review_status": "pending",
                            }
                        ]
                    },
                }

            def audit_run(**kwargs):
                return {
                    "target_date": kwargs["target_date"],
                    "passed": True,
                    "usable": True,
                    "findings": [],
                    "finding_count": 0,
                    "preflight": {"status": "success", "failures": []},
                    "report_acceptance": {"passed": True, "findings": [], "finding_count": 0},
                    "decision_ledger": {"passed": True, "case_count": 1, "findings": []},
                }

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=load_data,
                    build_report_outputs=build_outputs,
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=write_ledger,
                    audit_run=audit_run,
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            run_dir = root / "reports" / "runs" / "2026-05-24"
            self.assertEqual(result["run_dir"], str(run_dir))
            self.assertTrue((run_dir / "overview.md").exists())
            self.assertTrue((run_dir / "run.json").exists())
            self.assertTrue((run_dir / "audit.json").exists())
            self.assertTrue((run_dir / "review_queue.md").exists())

            payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["audit"]["passed"])
            self.assertEqual(payload["decision_ledger"]["case_count"], 1)
            self.assertIn("测试股份", (run_dir / "review_queue.md").read_text(encoding="utf-8"))

    def test_runner_records_audit_failure_in_review_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {},
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=lambda outputs, target_date, mode, output_dir=None: {
                        "full": str(Path(output_dir) / "full.md")
                    },
                    write_decision_ledger_from_markdown=lambda report_path, **kwargs: {"case_count": 0},
                    audit_run=lambda **kwargs: {
                        "target_date": kwargs["target_date"],
                        "passed": False,
                        "usable": False,
                        "findings": [
                            {
                                "source": "preflight",
                                "code": "critical_data_incomplete",
                                "message": "关键数据不完整，停止生成：中证全指",
                            }
                        ],
                        "finding_count": 1,
                        "preflight": {"status": "failed", "failures": ["中证全指"]},
                        "report_acceptance": {"passed": True, "findings": [], "finding_count": 0},
                        "decision_ledger": {"passed": True, "case_count": 0, "findings": []},
                    },
                ),
            )

            runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            review_queue = root / "reports" / "runs" / "2026-05-24" / "review_queue.md"
            self.assertIn("critical_data_incomplete", review_queue.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_agent_runner
```

Expected: fails with `ModuleNotFoundError: No module named 'agent_runner'`.

- [x] **Step 3: Implement runner module**

Create `scripts/agent_runner/__init__.py`:

```python
from agent_runner.daily_report_agent_runner import (
    DailyReportAgentDependencies,
    DailyReportAgentRequest,
    DailyReportAgentRunner,
)

__all__ = [
    "DailyReportAgentDependencies",
    "DailyReportAgentRequest",
    "DailyReportAgentRunner",
]
```

Create `scripts/agent_runner/daily_report_agent_runner.py`:

```python
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
    write_decision_ledger_from_markdown: Callable[..., dict[str, Any]] = write_decision_ledger_artifacts_from_markdown_report
    audit_run: Callable[..., dict[str, Any]] = audit_daily_report_run
    now: Callable[[], datetime] = datetime.now


def _default_load_data(request: DailyReportAgentRequest) -> dict[str, Any]:
    if request.mode == "replay":
        return replay_from_snapshot(request.target_date)
    raise RuntimeError("当前 runner 仅支持 replay 模式")


class DailyReportAgentRunner:
    def __init__(self, *, root_dir: str | Path = ".", dependencies: DailyReportAgentDependencies | None = None):
        self.root_dir = Path(root_dir)
        self.dependencies = dependencies or DailyReportAgentDependencies()

    def run(self, request: DailyReportAgentRequest) -> dict[str, Any]:
        started_at = self.dependencies.now().isoformat(timespec="seconds")
        run_dir = self.root_dir / "reports" / "runs" / request.target_date
        run_dir.mkdir(parents=True, exist_ok=True)
        status = "success"
        error: dict[str, str] | None = None
        outputs: dict[str, str] = {}
        saved_paths: dict[str, str] = {}
        decision_ledger_result: dict[str, Any] | None = None
        audit_result: dict[str, Any] | None = None
        data: dict[str, Any] = {}
        try:
            data_loader = self.dependencies.load_data or _default_load_data
            data = data_loader(request)
            outputs = self.dependencies.build_report_outputs(
                data,
                request.target_date,
                run_mode=request.mode,
                emit_preflight=False,
            )
            saved_paths = self.dependencies.save_report_outputs(
                outputs,
                request.target_date,
                mode=request.mode,
                output_dir=str(run_dir),
            )
            full_report_path = saved_paths.get("full") or next(iter(saved_paths.values()), "")
            full_markdown = outputs.get("full") or Path(full_report_path).read_text(encoding="utf-8")
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
            audit_result = audit_result or {
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
            "outputs": saved_paths,
            "audit": audit_result,
            "decision_ledger": _compact_decision_ledger(decision_ledger_result),
            "error": error,
        }
        self._write_json(run_dir / "run.json", payload)
        self._write_json(run_dir / "audit.json", audit_result)
        (run_dir / "overview.md").write_text(_render_overview(payload), encoding="utf-8")
        (run_dir / "review_queue.md").write_text(_render_review_queue(audit_result, decision_ledger_result), encoding="utf-8")
        return payload

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


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
        lines.extend(["", "## Error", f"- {payload['error'].get('type')}: {payload['error'].get('message')}"])
    return "\n".join(lines).rstrip() + "\n"


def _render_review_queue(audit: dict[str, Any] | None, decision_ledger_result: dict[str, Any] | None) -> str:
    lines = ["# Review Queue", ""]
    findings = (audit or {}).get("findings") or []
    if not findings and not _pending_review_records(decision_ledger_result):
        lines.append("- [ ] No manual review items from this run.")
        return "\n".join(lines).rstrip() + "\n"
    for finding in findings:
        lines.append(f"- [ ] {finding.get('source', 'runner')}:{finding.get('code', 'unknown')}")
        message = finding.get("message", "")
        if message:
            lines.append(f"  - reason: {message}")
        lines.append("  - human judgment:")
        lines.append("  - follow-up:")
    for record in _pending_review_records(decision_ledger_result):
        stock_name = record.get("stock_name") or record.get("name") or ""
        stock_code = record.get("stock_code") or record.get("code") or ""
        lines.append(f"- [ ] participation_review pending: {stock_name}({stock_code})")
        lines.append("  - reason: prior planned participation is waiting for explicit facts.")
        lines.append("  - human judgment:")
        lines.append("  - follow-up:")
    return "\n".join(lines).rstrip() + "\n"


def _pending_review_records(decision_ledger_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    index = (decision_ledger_result or {}).get("index") or {}
    records = index.get("records") or index.get("latest_records") or []
    pending = []
    for record in records:
        if record.get("participation_review_status") in {"pending", "waiting", "waiting_for_facts", None}:
            pending.append(record)
    return pending
```

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_agent_runner
```

Expected: `OK`.

## Task 3: Integration Test Coverage And Targeted Verification

**Files:**
- Test: `tests/test_report_run_audit.py`
- Test: `tests/test_daily_report_agent_runner.py`

- [x] **Step 1: Run both new test files**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_run_audit tests.test_daily_report_agent_runner
```

Expected: all tests pass.

- [x] **Step 2: Run nearby existing tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit tests.test_decision_ledger tests.test_daily_report_render
```

Expected: all tests pass. If this is too slow, record the partial output and run the smaller failure-relevant file before reporting.

Observed in this worktree: the new runner/audit tests pass, while the nearby existing suite has two unrelated failures in `tests.test_decision_ledger` and `tests.test_daily_report_render`; both were reproduced individually and are outside this slice.

- [x] **Step 3: Inspect git diff for scope**

Run:

```bash
git diff --stat
git diff -- scripts/report/report_run_audit.py scripts/agent_runner/daily_report_agent_runner.py tests/test_report_run_audit.py tests/test_daily_report_agent_runner.py
```

Expected: only first-slice runner/audit files are changed.

## Self-Review Checklist

- Spec coverage: the plan implements run folder, audit wrapper, decision-ledger call, review queue, and no service/scheduler.
- Placeholder scan: no placeholder tokens or vague future work steps inside implementation tasks.
- Type consistency: `DailyReportAgentRequest`, `DailyReportAgentDependencies`, and `audit_daily_report_run` signatures match tests and implementation.
- Python rule: all test commands use `.generated/venv-py314/bin/python3.14`.
