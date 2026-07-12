import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_runner.daily_report_agent_runner import (
    DailyReportAgentDependencies,
    DailyReportAgentRequest,
    DailyReportAgentRunner,
)


class DailyReportAgentRunnerTest(unittest.TestCase):
    def test_runner_defaults_to_replay_mode_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def load_data(request):
                self.assertEqual(request.mode, "replay")
                return {}

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=load_data,
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=lambda report_path, **kwargs: {"case_count": 0},
                    audit_run=lambda **kwargs: {
                        "target_date": kwargs["target_date"],
                        "passed": True,
                        "usable": True,
                        "findings": [],
                        "finding_count": 0,
                    },
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24"))

            self.assertEqual(result["mode"], "replay")
            self.assertEqual(result["status"], "error")

    def test_runner_rejects_non_replay_mode_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="fresh"))

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["message"], "当前 runner 仅支持 replay 模式")
            self._assert_error_run_artifacts(root, expected_code="unsupported_run_mode")

    def test_runner_rejects_non_replay_mode_before_custom_loader_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            load_count = 0

            def load_data(_request):
                nonlocal load_count
                load_count += 1
                return {"sample": True}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=load_data,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(
                DailyReportAgentRequest(target_date="2026-05-24", mode="fresh")
            )

            self.assertEqual(load_count, 0)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["message"], "当前 runner 仅支持 replay 模式")

    def test_runner_stops_when_replay_snapshot_data_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def build_outputs(data, target_date, **kwargs):
                raise AssertionError("report rendering should not run without replay data")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {},
                    build_report_outputs=build_outputs,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["message"], "回放数据不存在，停止生成：2026-05-24")
            self._assert_error_run_artifacts(root, expected_code="replay_data_missing")

    def test_runner_treats_none_replay_data_as_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def build_outputs(data, target_date, **kwargs):
                raise AssertionError("report rendering should not run without replay data")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: None,
                    build_report_outputs=build_outputs,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["message"], "回放数据不存在，停止生成：2026-05-24")
            self._assert_error_run_artifacts(root, expected_code="replay_data_missing")

    def test_runner_writes_run_artifacts_and_pending_participation_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def load_data(request):
                self.assertEqual(request.target_date, "2026-05-24")
                self.assertEqual(request.mode, "replay")
                return {"sections": {"summary": "## 七、最终结论\n50%条件执行"}}

            def build_outputs(data, target_date, **kwargs):
                self.assertFalse(kwargs["emit_preflight"])
                self.assertEqual(kwargs["run_mode"], "replay")
                self.assertFalse(kwargs["persist_runtime_artifacts"])
                return {
                    "full": "# full report\n\n## 七、最终结论\n50%条件执行",
                    "summary": "# summary",
                }

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                full_path = output_root / f"{target_date}_A股日报_完整版_replay.md"
                summary_path = output_root / f"{target_date}_A股日报_执行摘要_replay.md"
                full_path.write_text(outputs["full"], encoding="utf-8")
                summary_path.write_text(outputs["summary"], encoding="utf-8")
                return {"full": str(full_path), "summary": str(summary_path)}

            def write_ledger(report_path, **kwargs):
                self.assertTrue(str(report_path).endswith("2026-05-24_A股日报_完整版_replay.md"))
                self.assertEqual(kwargs["trade_date"], "2026-05-24")
                self.assertEqual(kwargs["root_dir"], str(root))
                self.assertEqual(kwargs["generated_at"], "2026-05-24T15:01:02")
                return {
                    "snapshot_path": str(root / "data" / "decision-ledger" / "2026-05-24.json"),
                    "index_path": str(root / "data" / "decision-ledger" / "index.json"),
                    "case_count": 1,
                    "fact_db_sync": {"status": "success", "rows": 1},
                    "index": {
                        "by_stock_code": {
                            "300000": [
                                {
                                    "stock_code": "300000",
                                    "stock_name": "测试股份",
                                    "participation_review_status": "等待复盘",
                                }
                            ]
                        }
                    },
                }

            audit_calls = []

            def audit_run(**kwargs):
                audit_calls.append(bool(kwargs["decision_ledger_required"]))
                if kwargs["decision_ledger_required"]:
                    self.assertEqual(kwargs["decision_ledger_result"]["case_count"], 1)
                else:
                    self.assertIsNone(kwargs["decision_ledger_result"])
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
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
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
            self.assertEqual(audit_calls, [False, True])
            quality_ledger = payload["report_quality_score"]["local_ledger"]
            self.assertEqual(quality_ledger["status"], "written")
            quality_path = Path(quality_ledger["score_path"])
            quality_index_path = Path(quality_ledger["index_path"])
            self.assertTrue(quality_path.exists())
            self.assertTrue(quality_index_path.exists())
            self.assertEqual(quality_path.name, "2026-05-24_replay.json")
            quality_snapshot = json.loads(quality_path.read_text(encoding="utf-8"))
            self.assertEqual(quality_snapshot["run_id"], "daily-report.agent.2026-05-24")

            audit_payload = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
            self.assertTrue(audit_payload["passed"])

            review_queue = (run_dir / "review_queue.md").read_text(encoding="utf-8")
            self.assertIn("测试股份", review_queue)
            self.assertIn("300000", review_queue)

    def test_runner_records_audit_failure_in_review_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
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
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            review_queue = root / "reports" / "runs" / "2026-05-24" / "review_queue.md"
            review_text = review_queue.read_text(encoding="utf-8")
            self.assertIn("critical_data_incomplete", review_text)
            self.assertIn("关键数据不完整，停止生成：中证全指", review_text)

    def test_runner_stops_before_save_when_required_facts_are_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            calls = []

            def build_outputs(data, target_date, **kwargs):
                calls.append("build")
                self.assertFalse(kwargs["persist_runtime_artifacts"])
                return {"full": "# report"}

            def save_outputs(*args, **kwargs):
                calls.append("save")
                raise AssertionError("report save should not run")

            def write_ledger(*args, **kwargs):
                calls.append("ledger")
                raise AssertionError("decision ledger should not run")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=build_outputs,
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=write_ledger,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch(
                "agent_runner.daily_report_agent_runner.assert_report_required_facts_complete",
                side_effect=RuntimeError("2026-05-24 日报关键数据不完整，停止生成：主线证据"),
            ):
                result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self.assertEqual(result["status"], "error")
            self.assertEqual(calls, ["build"])

    def test_runner_stops_before_save_when_markdown_acceptance_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            calls = []

            def audit_run(**kwargs):
                calls.append("audit")
                self.assertFalse(kwargs["decision_ledger_required"])
                self.assertIsNone(kwargs["decision_ledger_result"])
                return {
                    "target_date": kwargs["target_date"],
                    "passed": False,
                    "usable": True,
                    "findings": [
                        {
                            "source": "report_acceptance",
                            "code": "position_inferred_rendered_as_confirmed_holding",
                            "message": "前日报计划对象被正文写成确认持仓，停止生成",
                        }
                    ],
                    "finding_count": 1,
                    "preflight": {"status": "success", "failures": []},
                    "report_acceptance": {
                        "passed": False,
                        "findings": [
                            {
                                "code": "position_inferred_rendered_as_confirmed_holding",
                                "message": "前日报计划对象被正文写成确认持仓，停止生成",
                            }
                        ],
                        "finding_count": 1,
                    },
                    "decision_ledger": {"passed": True, "case_count": 0, "findings": []},
                }

            def save_outputs(*args, **kwargs):
                calls.append("save")
                raise AssertionError("invalid report must not be saved")

            def write_ledger(*args, **kwargs):
                calls.append("ledger")
                raise AssertionError("invalid report must not update the decision ledger")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# invalid report"},
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=write_ledger,
                    audit_run=audit_run,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["outputs"], {})
            self.assertEqual(calls, ["audit"])
            self.assertEqual(
                result["audit"]["findings"][0]["code"],
                "position_inferred_rendered_as_confirmed_holding",
            )

    def test_runner_normalizes_inferred_position_before_injected_builder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audit_calls = []
            data = {
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": True,
                        "name": "长电科技",
                        "code": "600584",
                        "summary": "持有长电科技(600584)，100%仓位",
                        "position_source": "previous_report_target_default_1x",
                    }
                }
            }

            def build_outputs(data, target_date, **kwargs):
                summary = data["personal_position_context"]["existing_position_summary"]
                self.assertFalse(summary["has_position"])
                self.assertTrue(summary["has_pending_position"])
                self.assertTrue(summary["inferred_from_previous_report"])
                self.assertEqual(summary["position"], 0.0)
                self.assertEqual(summary["position_pct"], 0.0)
                return {"full": "# report"}

            def render_position_strategy(data, target_date, positions, **kwargs):
                self.assertEqual(positions, [])
                self.assertFalse(data["personal_position_context"]["existing_position_summary"]["has_position"])
                return "\n".join(
                    [
                        "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                        "|------|------|----------|----------|-------------|------|",
                        "| Td | 2026-05-24（周日） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | 未确认成交，不视为B1 | 只观察，不新增参与 |",
                        "| Te | 2026-05-25（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |",
                        "",
                        "# 持仓策略",
                    ]
                )

            def audit_run(**kwargs):
                from report.report_acceptance_audit import audit_report_markdown

                raw = audit_report_markdown(
                    kwargs["report_markdown"],
                    expected_position_summary=data["personal_position_context"]["existing_position_summary"],
                    source_path=kwargs.get("source_path"),
                )
                position_findings = [
                    item
                    for item in raw["findings"]
                    if str(item.get("code") or "").startswith("position_")
                ]
                audit_calls.append(position_findings)
                return {
                    "target_date": kwargs["target_date"],
                    "passed": not position_findings,
                    "usable": True,
                    "findings": position_findings,
                    "finding_count": len(position_findings),
                }

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: data,
                    build_report_outputs=build_outputs,
                    save_report_outputs=save_outputs,
                    render_position_strategy_report=render_position_strategy,
                    audit_run=audit_run,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                result = runner.run(
                    DailyReportAgentRequest(
                        target_date="2026-05-24",
                        mode="replay",
                        update_decision_ledger=False,
                    )
                )

            self.assertEqual(result["status"], "success")
            self.assertEqual(audit_calls, [[], []])
            saved_report = Path(result["outputs"]["full"]).read_text(encoding="utf-8")
            self.assertIn("## 账户日序表", saved_report)
            self.assertIn("前日报计划推定，待成交确认：长电科技(600584)", saved_report)

    def test_runner_writes_error_artifacts_when_rendering_fails_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def build_outputs(data, target_date, **kwargs):
                raise RuntimeError("render boom")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=build_outputs,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self._assert_error_run_artifacts(root)

    def test_runner_writes_error_artifacts_when_audit_fails_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            def audit_run(**kwargs):
                raise RuntimeError("audit boom")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=lambda report_path, **kwargs: {"case_count": 0},
                    audit_run=audit_run,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self._assert_error_run_artifacts(root)

    def test_runner_writes_replay_market_language_only_after_both_checks_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            calls = []
            artifact = {"schema_version": "market_language_translation.v1", "target_date": "2026-05-24"}

            def prepare(data, **kwargs):
                calls.append("prepare")
                self.assertEqual(kwargs["analysis_mode"], "replay")
                return artifact

            def build_outputs(data, target_date, **kwargs):
                calls.append("build")
                self.assertIs(kwargs["market_language_translation"], artifact)
                return {"full": "# report"}

            def save_outputs(outputs, target_date, mode, output_dir=None):
                calls.append("save")
                path = Path(output_dir) / "full.md"
                path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(path)}

            def audit_run(**kwargs):
                calls.append("audit")
                return {"passed": True, "usable": True, "findings": [], "finding_count": 0}

            def write_replay(received, **kwargs):
                calls.append("write_replay")
                self.assertIs(received, artifact)
                self.assertEqual(Path(kwargs["root_dir"]), root)
                return {"artifact_path": str(root / "replay.json")}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    prepare_market_language_translation=prepare,
                    build_report_outputs=build_outputs,
                    save_report_outputs=save_outputs,
                    write_replay_market_language_translation=write_replay,
                    write_decision_ledger_from_markdown=lambda *args, **kwargs: {},
                    audit_run=audit_run,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                result = runner.run(
                    DailyReportAgentRequest(
                        target_date="2026-05-24",
                        mode="replay",
                        update_decision_ledger=False,
                    )
                )

            self.assertEqual(result["status"], "success")
            self.assertEqual(calls, ["prepare", "build", "audit", "save", "audit", "write_replay"])
            self.assertEqual(result["market_language_translation"]["artifact_path"], str(root / "replay.json"))

    def test_runner_does_not_write_replay_market_language_when_either_check_fails(self):
        for failing_audit_index in (1, 2):
            with self.subTest(failing_audit_index=failing_audit_index), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                audit_count = 0
                write_count = 0

                def save_outputs(outputs, target_date, mode, output_dir=None):
                    path = Path(output_dir) / "full.md"
                    path.write_text(outputs["full"], encoding="utf-8")
                    return {"full": str(path)}

                def audit_run(**kwargs):
                    nonlocal audit_count
                    audit_count += 1
                    passed = audit_count != failing_audit_index
                    return {
                        "passed": passed,
                        "usable": passed,
                        "findings": [] if passed else [{"code": "test_failure", "message": "检查未通过"}],
                        "finding_count": 0 if passed else 1,
                    }

                def write_replay(*args, **kwargs):
                    nonlocal write_count
                    write_count += 1
                    return {}

                runner = DailyReportAgentRunner(
                    root_dir=root,
                    dependencies=DailyReportAgentDependencies(
                        load_data=lambda request: {"sample": True},
                        prepare_market_language_translation=lambda *args, **kwargs: {
                            "schema_version": "market_language_translation.v1",
                            "target_date": "2026-05-24",
                        },
                        build_report_outputs=lambda *args, **kwargs: {"full": "# report"},
                        save_report_outputs=save_outputs,
                        write_replay_market_language_translation=write_replay,
                        write_decision_ledger_from_markdown=lambda *args, **kwargs: {},
                        audit_run=audit_run,
                        now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                    ),
                )

                with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                    result = runner.run(
                        DailyReportAgentRequest(
                            target_date="2026-05-24",
                            mode="replay",
                            update_decision_ledger=False,
                        )
                    )

                self.assertEqual(write_count, 0)
                self.assertIn(result["status"], {"error", "needs_review"})

    def test_runner_rejects_corrupted_saved_markdown_before_artifact_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_count = 0

            def save_outputs(_outputs, _target_date, mode=None, output_dir=None):
                path = Path(output_dir) / "full.md"
                path.write_text("# corrupted", encoding="utf-8")
                return {"full": str(path)}

            def write_replay(*args, **kwargs):
                nonlocal write_count
                write_count += 1
                return {}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda _request: {"sample": True},
                    prepare_market_language_translation=lambda *args, **kwargs: {
                        "schema_version": "market_language_translation.v1",
                        "target_date": "2026-05-24",
                    },
                    build_report_outputs=lambda *args, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
                    write_replay_market_language_translation=write_replay,
                    write_decision_ledger_from_markdown=lambda *args, **kwargs: {},
                    audit_run=lambda **kwargs: {
                        "passed": True,
                        "usable": True,
                        "findings": [],
                        "finding_count": 0,
                    },
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch(
                "agent_runner.daily_report_agent_runner.assert_report_required_facts_complete",
                return_value={},
            ):
                result = runner.run(
                    DailyReportAgentRequest(
                        target_date="2026-05-24",
                        mode="replay",
                        update_decision_ledger=False,
                    )
                )

            self.assertEqual(result["status"], "error")
            self.assertIn("保存后的完整版日报与检查通过的正文不一致", result["error"]["message"])
            self.assertEqual(write_count, 0)

    def test_runner_records_optional_opik_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            class StubObserver:
                def __init__(self):
                    self.steps = []
                    self.finish_payload = None

                def record_step(self, name, **kwargs):
                    self.steps.append((name, kwargs))

                def finish(self, **kwargs):
                    self.finish_payload = kwargs

            observer = StubObserver()

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=lambda report_path, **kwargs: {"case_count": 0},
                    audit_run=lambda **kwargs: {
                        "target_date": kwargs["target_date"],
                        "passed": True,
                        "usable": True,
                        "findings": [],
                        "finding_count": 0,
                    },
                    build_observer=lambda **kwargs: observer,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            with patch("agent_runner.daily_report_agent_runner.assert_report_required_facts_complete", return_value={}):
                result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["report_quality_score"]["schema_version"], "report_quality_score.v1")
            self.assertEqual(result["report_quality_score"]["status"], "pass")
            self.assertEqual(
                [name for name, _ in observer.steps],
                [
                    "load_data",
                    "build_report_outputs",
                    "preflight_check",
                    "pre_save_audit",
                    "save_report_outputs",
                    "decision_ledger",
                    "audit_run",
                ],
            )
            self.assertEqual(observer.finish_payload["status"], "success")
            self.assertEqual(
                observer.finish_payload["output_payload"]["report_quality_score"]["schema_version"],
                "report_quality_score.v1",
            )

    def _assert_error_run_artifacts(self, root, expected_code="runner_error"):
        run_dir = root / "reports" / "runs" / "2026-05-24"
        self.assertTrue((run_dir / "run.json").exists())
        self.assertTrue((run_dir / "audit.json").exists())
        self.assertTrue((run_dir / "overview.md").exists())
        self.assertTrue((run_dir / "review_queue.md").exists())

        payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["audit"]["findings"][0]["code"], expected_code)

        audit_payload = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit_payload["findings"][0]["code"], expected_code)


if __name__ == "__main__":
    unittest.main()
