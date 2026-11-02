import copy
import io
import json
import os
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_render import (
    REPORT_COMPANION_DOCS,
    REPORT_VARIANT_EVIDENCE_APPENDIX,
    REPORT_VARIANT_FULL,
    REPORT_VARIANT_LIGHTWEIGHT,
    REPORT_VARIANT_RUN_LOG,
    REPORT_VARIANT_SUMMARY,
    ReportCriticalDataMissingError,
    _render_report_with_display_mode,
    build_lightweight_report_text,
    build_report_outputs,
    build_report_preflight,
    build_run_log_text,
    finalize_run_log_text,
    persist_report_runtime_artifacts,
    read_verified_saved_report_markdown,
    render_report_preflight_lines,
    generate_markdown_report,
    generate_markdown_report_from_sections,
    save_report_output,
    save_report_outputs,
)
from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from domains.market_state.market_language_translation import canonical_market_language_hash
from report.cffex_index_futures_position_evidence import (
    build_unavailable_cffex_evidence,
    canonical_cffex_evidence_hash,
)
from report.formal_account_decision import (
    DECISION_PRODUCT_FREEZE_KEY,
    build_decision_product_freeze,
    canonical_decision_product_freeze_hash,
)
from report.decision_ledger import (
    build_decision_ledger_index,
    build_decision_ledger_snapshot,
    build_extreme_conviction_mention_rows,
    write_decision_ledger_artifacts,
)


def _complete_report_facts(overrides=None):
    overrides = dict(overrides or {})
    data = {
        "data_status": {
            "两市成交额": True,
            "中证全指": True,
            "中证1000": True,
            "成交额排名": True,
            "大盘涨跌统计": True,
            "热度前50个股": True,
        },
        "step_status": {
            "涨停跌停数据获取": True,
            "热度前50个股获取": True,
        },
        "total_turnover": 12345.67,
        "wind_a_alternative": {
            "price": 6686.86,
            "change_pct": 1.2,
            "data_source": "tushare.index_daily",
        },
        "csi500_index": {
            "price": 6262.0,
            "change_pct": 0.9,
            "data_source": "tushare.index_daily",
        },
        "csi1000_index": {
            "price": 6123.45,
            "change_pct": 1.1,
            "data_source": "tushare.index_daily",
        },
        "turnover_rank": [
            {"code": f"{index:06d}", "data_source": "tushare.daily"}
            for index in range(1, 51)
        ],
        "market_stats": {"up_count": 2600, "down_count": 2100, "zt_count": 102, "dt_count": 8},
        "hot_rank_top50": [{"code": f"{index:06d}"} for index in range(1, 51)],
        "hot_rank_sample_size": 50,
        "hot_rank_sample_target": 50,
        "module_logs": [
            {
                "step": "request.total_turnover",
                "status": "success",
                "details": {"provider": "tushare.daily", "total_turnover": 12345.67, "row_count": 1},
            },
            {
                "step": "request.wind_a",
                "status": "success",
                "details": {"provider": "tushare.index_daily", "price": 6686.86, "row_count": 1},
            },
            {
                "step": "request.csi500",
                "status": "success",
                "details": {"provider": "tushare.index_daily", "price": 6262.0, "row_count": 1},
            },
            {
                "step": "request.csi1000",
                "status": "success",
                "details": {"provider": "tushare.index_daily", "price": 6123.45, "row_count": 1},
            },
            {
                "step": "request.turnover_rank",
                "status": "success",
                "details": {"provider": "tushare.daily", "row_count": 50},
            },
            {
                "step": "request.market_stats",
                "status": "success",
                "details": {"provider": "tushare.daily", "row_count": 1},
            },
            {
                "step": "request.hot_rank.primary",
                "status": "success",
                "details": {"provider": "tushare.ths_hot", "hot_rank_count": 50},
            },
        ],
    }
    for key in ("data_status", "step_status"):
        if isinstance(overrides.get(key), dict):
            data[key].update(overrides.pop(key))
    if "module_logs" in overrides:
        data["module_logs"] = overrides.pop("module_logs")
    data.update(overrides)
    return data


def _market_language_test_artifact():
    return {
        "schema_version": "market_language_translation.v1",
        "target_date": "2026-07-10",
        "analysis_mode": "fresh",
        "artifact_origin": "computed",
        "data_granularity": "end_of_day",
        "evidence_status": "insufficient",
        "missing_evidence": ["one_minute_price_path"],
        "force_scope": "unclear",
        "pressure_direction": "unclear",
        "phase": "unclear",
        "phase_label": "事实不足，阶段不清楚",
        "timeline": {
            "first_candidate_at": None,
            "latest_confirmed_at": None,
            "candidate_invalidations": 0,
            "latest_transition_at": None,
            "events": [],
        },
        "aggregation_comparison": {},
        "price_pressure": {},
        "participation": {},
        "liquidity_proxies": {},
        "fixed_window_observations": [],
        "evidence": [],
        "counter_evidence": [],
        "next_window_task": "补齐事实。",
        "posthoc_validation": None,
        "sources": [],
        "as_of_time": "15:00",
    }


def _formal_decision_projection(data):
    selection_workflow = data.get("selection_workflow") or {}
    final_target_resolution = data.get("final_target_resolution") or {}
    next_day_action = (data.get("two_layer_decision_payload") or {}).get("next_day_action") or {}
    return copy.deepcopy(
        {
            "selection_workflow": selection_workflow,
            "final_target_resolution": final_target_resolution,
            "execution_object": next_day_action.get("execution_object"),
            "position_pct": next_day_action.get("position_pct"),
            "execution_nature": next_day_action.get("execution_nature"),
            "b1_action": next_day_action.get("b1_action"),
            "b2_action": next_day_action.get("b2_action"),
            "exit_action": next_day_action.get("exit_action"),
        }
    )


def _decision_product_test_data(target_date):
    stock = {"code": "603986", "name": "兆易创新"}
    outcomes = {
        action: {"selected": action == "hold", "stock": copy.deepcopy(stock)}
        for action in ("hold", "add", "replace", "cash")
    }
    return {
        "selection_workflow": {
            "schema_version": "selection_workflow.v1",
            "target_date": target_date,
            "final": {
                "execution_object": copy.deepcopy(stock),
                "position_pct": 50,
            },
        },
        "final_target_resolution": {
            "new_entry_target": copy.deepcopy(stock),
            "old_position_plan": {"action": "hold"},
            "account_options": copy.deepcopy(outcomes),
        },
        "position_decision": {
            "target_position_pct": 50,
            "execution_nature": "50%条件执行",
        },
        "two_layer_decision_payload": {
            "next_day_action": {
                "execution_object": copy.deepcopy(stock),
                "position_pct": 50,
                "b1_action": "B1先买参与权",
                "b2_action": "确认后才补B2",
            }
        },
        "formal_decision_input": {
            "schema_version": "formal_decision_input.v1",
            "report_date": target_date,
            "input_hash": "formal-input-hash",
        },
        "formal_account_decision": {
            "schema_version": "formal_account_decision.v1",
            "target_date": target_date,
            "selected_action": "hold",
            "formal_execution_object": copy.deepcopy(stock),
            "account_exposure": {
                "current_position_pct": 50,
                "planned_total_position_pct": 50,
                "executable_new_entry_pct": 0,
                "closing_target_position_pct": 50,
            },
            "outcomes": copy.deepcopy(outcomes),
            "b1": {"status": "held"},
            "b2": {"status": "not_qualified"},
            "exit_plan": {"action": "hold"},
        },
        "candidate_decision_evidence": {
            "schema_version": "candidate_decision_evidence.v1",
            "report_date": target_date,
            "volume_price_evidence": {"price_acceptance": "unconfirmed"},
        },
        "decision_robustness_version_health": {
            "schema_version": "decision_robustness_version_health.v1",
            "report_date": target_date,
        },
        "research_execution_evidence": {
            "schema_version": "research_execution_evidence.v1",
            "target_date": target_date,
        },
        "knowledge": {
            "llm_wiki": {
                "target_date": target_date,
                "knowledge_trace": {"trace_hash": "trace-hash"},
            }
        },
    }


class _DecisionLedgerMemoryFactStore:
    def __init__(self, index=None):
        self.index = index or {}
        self.mentions = []

    def is_postgres_backed(self):
        return True

    def read_decision_ledger_index(self, end_date=None, window_days=25):
        return self.index

    def replace_decision_ledger_snapshot(self, snapshot):
        self.index = build_decision_ledger_index(snapshot, previous_index=self.index)
        self.mentions = build_extreme_conviction_mention_rows(
            self.index,
            end_date=snapshot.get("trade_date"),
            window_days=25,
            exclude_a_kill=False,
        )
        return {"mentions": len(self.mentions), "cases": len((snapshot or {}).get("cases") or [])}

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        return [dict(row) for row in self.mentions]


class DailyReportRenderTest(unittest.TestCase):
    def test_build_report_outputs_passes_isolated_market_language_copies_without_shared_data(self):
        data = _complete_report_facts({"foo": "bar"})
        artifact = _market_language_test_artifact()
        original_hash = canonical_market_language_hash(artifact)
        seen = []

        def render(display_mode, payload, target_date, **kwargs):
            received = kwargs["market_language_translation"]
            seen.append(received)
            received["phase_label"] = f"mutated-{display_mode}"
            return "# summary" if display_mode else "# full"

        with patch("daily_report_render._render_report_with_display_mode", side_effect=render):
            build_report_outputs(
                data,
                "2026-07-10",
                emit_preflight=False,
                market_language_translation=artifact,
            )

        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], seen[1])
        self.assertIsNot(seen[0], artifact)
        self.assertEqual(canonical_market_language_hash(artifact), original_hash)
        self.assertNotIn("market_language_translation", data)
        self.assertNotIn("market_language_translation_artifact", data)

    def test_build_report_outputs_passes_isolated_cffex_evidence_copies(self):
        data = _complete_report_facts({"foo": "bar"})
        artifact = build_unavailable_cffex_evidence(
            "2026-07-10",
            reason="目标日事实缺失",
            query_date="2026-07-11",
        )
        original_hash = canonical_cffex_evidence_hash(artifact)
        seen = []

        def render(display_mode, payload, target_date, **kwargs):
            received = kwargs["cffex_index_futures_position_evidence"]
            seen.append(received)
            received["missing_reasons"].append(f"mutated-{display_mode}")
            return "# summary" if display_mode else "# full"

        with patch("daily_report_render._render_report_with_display_mode", side_effect=render):
            build_report_outputs(
                data,
                "2026-07-10",
                emit_preflight=False,
                cffex_index_futures_position_evidence=artifact,
            )

        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], seen[1])
        self.assertIsNot(seen[0], artifact)
        self.assertEqual(canonical_cffex_evidence_hash(artifact), original_hash)
        self.assertNotIn("cffex_index_futures_position_evidence", data)

    def test_build_report_outputs_isolates_full_and_summary_decision_freezes(self):
        target_date = "2026-08-04"
        freeze = build_decision_product_freeze(
            _decision_product_test_data(target_date),
            target_date=target_date,
        )
        self.assertEqual(freeze["availability"], "complete")
        source_hash = canonical_decision_product_freeze_hash(freeze)
        data = _complete_report_facts(
            {DECISION_PRODUCT_FREEZE_KEY: copy.deepcopy(freeze)}
        )
        seen = []

        def render(display_mode, payload, target_date, **kwargs):
            seen.append(payload[DECISION_PRODUCT_FREEZE_KEY])
            return "# 摘要版" if display_mode else "# 完整版"

        with patch(
            "daily_report_render._raise_if_critical_data_missing"
        ), patch(
            "daily_report_render._clear_quote_sensitive_derived_outputs"
        ), patch(
            "daily_report_render._render_report_with_display_mode",
            side_effect=render,
        ):
            build_report_outputs(
                data,
                target_date,
                emit_preflight=False,
                persist_runtime_artifacts=False,
            )

        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], seen[1])
        self.assertIsNot(seen[0], freeze)
        self.assertIsNot(seen[1], freeze)
        self.assertEqual(seen[0]["decision_projection"], seen[1]["decision_projection"])
        self.assertEqual(
            canonical_decision_product_freeze_hash(seen[0]),
            source_hash,
        )
        self.assertEqual(
            canonical_decision_product_freeze_hash(seen[1]),
            source_hash,
        )
        seen[0]["decision_projection"]["account_action"] = "cash"
        self.assertEqual(
            seen[1]["decision_projection"]["account_action"],
            "hold",
        )
        self.assertEqual(canonical_decision_product_freeze_hash(freeze), source_hash)
        self.assertEqual(
            canonical_decision_product_freeze_hash(
                data[DECISION_PRODUCT_FREEZE_KEY]
            ),
            source_hash,
        )

    def test_market_language_integration_keeps_full_and_summary_formal_decisions_identical(self):
        formal_decision = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {"code": "603986", "name": "兆易创新"},
                    "position_pct": 50,
                    "action_text": "50%条件执行",
                },
            },
            "final_target_resolution": {
                "new_entry_target": {"code": "603986", "name": "兆易创新"},
                "position_pct": 50,
                "execution_nature": "50%条件执行",
            },
            "two_layer_decision_payload": {
                "next_day_action": {
                    "execution_object": {"code": "603986", "name": "兆易创新"},
                    "position_pct": 50,
                    "execution_nature": "50%条件执行",
                    "b1_action": "B1先买参与权",
                    "b2_action": "确认后才补B2",
                    "exit_action": "失效条件出现则退出",
                }
            },
        }
        baseline_data = _complete_report_facts(copy.deepcopy(formal_decision))
        integrated_data = _complete_report_facts(copy.deepcopy(formal_decision))
        snapshots = []

        def render(display_mode, payload, target_date, **kwargs):
            snapshots.append(
                {
                    "display_mode": bool(display_mode),
                    "decision": _formal_decision_projection(payload),
                    "artifact": kwargs.get("market_language_translation"),
                    "artifact_in_data": any(
                        key in payload
                        for key in (
                            "market_language_translation",
                            "market_language_translation_artifact",
                        )
                    ),
                }
            )
            return "# 摘要版" if display_mode else "# 完整版"

        with patch("daily_report_render._raise_if_critical_data_missing"), patch(
            "daily_report_render._clear_quote_sensitive_derived_outputs"
        ), patch(
            "daily_report_render._render_report_with_display_mode", side_effect=render
        ):
            build_report_outputs(
                baseline_data,
                "2026-07-10",
                emit_preflight=False,
            )
            build_report_outputs(
                integrated_data,
                "2026-07-10",
                emit_preflight=False,
                market_language_translation=_market_language_test_artifact(),
            )

        expected = _formal_decision_projection(formal_decision)
        self.assertEqual([row["display_mode"] for row in snapshots], [False, True, False, True])
        for row in snapshots:
            self.assertEqual(row["decision"], expected)
            self.assertFalse(row["artifact_in_data"])
        self.assertIsNone(snapshots[0]["artifact"])
        self.assertIsNone(snapshots[1]["artifact"])
        self.assertEqual(
            snapshots[2]["artifact"]["schema_version"],
            "market_language_translation.v1",
        )
        self.assertEqual(
            snapshots[3]["artifact"]["schema_version"],
            "market_language_translation.v1",
        )

    def test_save_report_output_can_explicitly_overwrite_official_report(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            target_path = root / "2026-05-26_A股日报_完整版.md"
            target_path.write_text("# old", encoding="utf-8")

            saved_path = save_report_output(
                "# new",
                "2026-05-26",
                mode=LEDGER_MODE_FROZEN,
                variant=REPORT_VARIANT_FULL,
                output_path=str(target_path),
                overwrite_existing=True,
            )

            self.assertEqual(saved_path, str(target_path))
            self.assertEqual(target_path.read_text(encoding="utf-8"), "# new")

    def test_saved_report_verification_reads_disk_and_rejects_mismatch_or_missing_path(self):
        with TemporaryDirectory() as tempdir:
            report_path = Path(tempdir) / "full.md"
            report_path.write_text("# accepted", encoding="utf-8")

            self.assertEqual(
                read_verified_saved_report_markdown(report_path, "# accepted"),
                "# accepted",
            )
            with self.assertRaisesRegex(RuntimeError, "正文不一致"):
                read_verified_saved_report_markdown(report_path, "# expected")
            with self.assertRaisesRegex(RuntimeError, "无法读取"):
                read_verified_saved_report_markdown(Path(tempdir) / "missing.md", "# expected")

    def test_build_report_outputs_suppresses_helper_diagnostics_for_summary_render(self):
        data = _complete_report_facts({"foo": "bar"})
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            outputs = build_report_outputs(data, "2026-04-22", emit_preflight=False)

        self.assertIn(REPORT_VARIANT_FULL, outputs)
        self.assertIn(REPORT_VARIANT_SUMMARY, outputs)
        self.assertEqual(outputs[REPORT_VARIANT_FULL], "# full")
        self.assertEqual(outputs[REPORT_VARIANT_SUMMARY], "# summary")
        self.assertNotIn("阅读模式", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("阅读模式", outputs[REPORT_VARIANT_SUMMARY])
        self.assertEqual(render_mock.call_count, 2)
        self.assertTrue(render_mock.call_args_list[0].kwargs["emit_helper_diagnostics"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["emit_helper_diagnostics"])
        self.assertFalse(render_mock.call_args_list[0].kwargs["persist_strategy_tracking"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_strategy_tracking"])
        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_decision_ledger"])
        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_candidate_traces"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_candidate_traces"])
        self.assertEqual(
            Path(render_mock.call_args_list[0].kwargs["decision_ledger_root_dir"]).resolve(),
            ROOT.resolve(),
        )
        self.assertEqual(
            Path(render_mock.call_args_list[0].kwargs["candidate_trace_root_dir"]).resolve(),
            ROOT.resolve(),
        )
        self.assertIs(render_mock.call_args_list[0].kwargs["shared_runtime_cache"], render_mock.call_args_list[1].kwargs["shared_runtime_cache"])

    def test_build_report_outputs_records_internal_render_timings(self):
        data = _complete_report_facts({"foo": "bar"})
        timing_rows = []

        with patch("daily_report_render.time.monotonic", side_effect=[10.0, 11.0, 13.0, 16.0, 17.0]), \
             patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]):
            outputs = build_report_outputs(
                data,
                "2026-04-22",
                emit_preflight=False,
                build_timing_rows=timing_rows,
            )

        self.assertIn(REPORT_VARIANT_FULL, outputs)
        self.assertEqual(
            [row["phase"] for row in timing_rows],
            ["生成前检查", "完整版生成", "摘要版生成", "派生变体生成"],
        )
        self.assertEqual(
            [row["elapsed_seconds"] for row in timing_rows],
            [1.0, 2.0, 3.0, 1.0],
        )

    def test_build_report_outputs_flattens_full_runtime_timings_without_double_counting(self):
        data = _complete_report_facts({"foo": "bar"})
        timing_rows = []

        def render(display_mvp_mode, *args, runtime_timing_rows=None, **kwargs):
            if not display_mvp_mode:
                runtime_timing_rows.extend(
                    [
                        {"phase": "完整版/运行时/知识上下文准备", "elapsed_seconds": 0.5},
                        {"phase": "完整版/正文/执行阶段构建", "elapsed_seconds": 1.25},
                    ]
                )
                return "# full"
            self.assertIsNone(runtime_timing_rows)
            return "# summary"

        with patch(
            "daily_report_render.time.monotonic",
            side_effect=[10.0, 11.0, 13.0, 16.0, 17.0],
        ), patch(
            "daily_report_render._render_report_with_display_mode",
            side_effect=render,
        ):
            build_report_outputs(
                data,
                "2026-04-22",
                emit_preflight=False,
                build_timing_rows=timing_rows,
            )

        self.assertEqual(
            [row["phase"] for row in timing_rows],
            [
                "生成前检查",
                "完整版/运行时/知识上下文准备",
                "完整版/正文/执行阶段构建",
                "完整版生成/入口封装",
                "摘要版生成",
                "派生变体生成",
            ],
        )
        self.assertEqual(
            [row["elapsed_seconds"] for row in timing_rows],
            [1.0, 0.5, 1.25, 0.25, 3.0, 1.0],
        )

    def test_build_report_outputs_normalizes_inferred_previous_target_as_simulated_old_position(self):
        inferred_summary = {
            "has_position": True,
            "name": "长电科技",
            "code": "600584",
            "summary": "持有长电科技(600584)，100%仓位",
            "position_source": "previous_report_target_default_1x",
        }
        nested_copy = dict(inferred_summary)
        data = _complete_report_facts(
            {
                "personal_position_context": {"existing_position_summary": inferred_summary},
                "market_research_snapshot": {"existing_position_summary": nested_copy},
            }
        )

        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]):
            build_report_outputs(data, "2026-07-10", emit_preflight=False)

        for summary in (inferred_summary, nested_copy):
            self.assertTrue(summary["has_position"])
            self.assertFalse(summary["has_pending_position"])
            self.assertTrue(summary["inferred_from_previous_report"])
            self.assertEqual(summary["position"], 50.0)
            self.assertEqual(summary["position_pct"], 50.0)
            self.assertEqual(summary["default_position_pct"], 50.0)
            self.assertIn("持有长电科技(600584)，1x/50%半仓，上一份日报明日标的默认1x旧仓", summary["summary"])
            self.assertEqual(summary["holding_note"], "上一份日报明日标的默认1x旧仓")

    def test_build_report_outputs_prepends_position_timeline_to_full_report(self):
        data = _complete_report_facts({"foo": "bar"})
        position_report_text = (
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |\n\n"
            "# 持仓策略"
        )

        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]):
            outputs = build_report_outputs(
                data,
                "2026-07-10",
                emit_preflight=False,
                position_report_text=position_report_text,
            )

        self.assertIn("## 账户日序表", outputs[REPORT_VARIANT_FULL])
        self.assertIn("长电科技(600584)", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("## 账户日序表", outputs[REPORT_VARIANT_SUMMARY])

    def test_build_report_outputs_forwards_postgres_only_runtime_config(self):
        data = _complete_report_facts({"postgres_only": True})
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            build_report_outputs(data, "2026-05-29", emit_preflight=False)

        self.assertTrue(render_mock.call_args_list[0].kwargs["postgres_only"])
        self.assertTrue(render_mock.call_args_list[1].kwargs["postgres_only"])

    def test_build_report_outputs_validates_frozen_inputs_before_refreshing_quote_sensitive_outputs(self):
        data = _complete_report_facts(
            {
                "postgres_only": True,
                "selection_workflow": {"schema_version": "selection_workflow.v1", "final": {"position_pct": 50}},
                "final_target_resolution": {"new_entry_target": {"code": "600667"}},
                "two_layer_decision_payload": {"final_object": {"stock": {"code": "600667"}}},
                "current_sector_turnover_snapshot": {"sector": "半导体", "turnover": 100},
                "market_state_snapshot": {"market_state": "修复"},
                "mainline_turnover_summary": {"current_mainline": "半导体"},
                "position_decision": {"target_position_pct": 0},
                "front_page_final_gate": {"final_action": "0%不参与"},
                "execution_stage_context": {
                    "selection_workflow": {"schema_version": "selection_workflow.v1", "final": {"position_pct": 50}},
                    "final_target_resolution": {"new_entry_target": {"code": "600667"}},
                    "candidate_traces": [{"stock_code": "600667"}],
                },
                "market_research_snapshot": {
                    "selection_workflow": {"schema_version": "selection_workflow.v1", "final": {"position_pct": 50}},
                    "sniper_target_derivation": {"canonical_target": {"code": "600667"}},
                },
            }
        )
        seen = []
        preflight_seen = []
        original_build_report_preflight = build_report_preflight

        def capture_preflight(payload, date):
            context = payload.get("execution_stage_context") or {}
            snapshot = payload.get("market_research_snapshot") or {}
            preflight_seen.append(
                {
                    "data_selection_workflow": "selection_workflow" in payload,
                    "data_final_target_resolution": "final_target_resolution" in payload,
                    "context_selection_workflow": "selection_workflow" in context,
                    "context_candidate_traces": "candidate_traces" in context,
                    "snapshot_selection_workflow": "selection_workflow" in snapshot,
                    "snapshot_sniper_target_derivation": "sniper_target_derivation" in snapshot,
                }
            )
            return original_build_report_preflight(payload, date)

        def fake_render(_display_mode, payload, *_args, **_kwargs):
            context = payload.get("execution_stage_context") or {}
            snapshot = payload.get("market_research_snapshot") or {}
            seen.append(
                {
                    "data_selection_workflow": "selection_workflow" in payload,
                    "data_final_target_resolution": "final_target_resolution" in payload,
                    "context_selection_workflow": "selection_workflow" in context,
                    "context_candidate_traces": "candidate_traces" in context,
                    "snapshot_selection_workflow": "selection_workflow" in snapshot,
                    "snapshot_sniper_target_derivation": "sniper_target_derivation" in snapshot,
                }
            )
            return "# full" if len(seen) == 1 else "# summary"

        with patch("daily_report_render.build_report_preflight", side_effect=capture_preflight), \
             patch("daily_report_render._render_report_with_display_mode", side_effect=fake_render):
            build_report_outputs(data, "2026-07-02", emit_preflight=False)

        self.assertEqual(
            preflight_seen[0],
            {
                "data_selection_workflow": True,
                "data_final_target_resolution": True,
                "context_selection_workflow": True,
                "context_candidate_traces": True,
                "snapshot_selection_workflow": True,
                "snapshot_sniper_target_derivation": True,
            },
        )
        self.assertEqual(
            seen[0],
            {
                "data_selection_workflow": False,
                "data_final_target_resolution": False,
                "context_selection_workflow": False,
                "context_candidate_traces": False,
                "snapshot_selection_workflow": False,
                "snapshot_sniper_target_derivation": False,
            },
        )

    def test_build_report_outputs_sanitizes_final_markdown_variants(self):
        data = _complete_report_facts({"postgres_only": True})
        stale_full_report = "\n".join(
            [
                "## 日报裁决总览",
                "| 项目 | 结论 |",
                "|------|------|",
                "| 仓位姿态 | 0%不参与 |",
                "| 最终对象 | 无 |",
                "**明日继续观察**（1只，等观察位出现）:",
                "- ⏳ 和远气体(002971) - 过程候选，等观察位出现，09:50-10:10观察价52.75",
                "| 1 | 和远气体(002971) | 化工原料 | 板块锚 | 承接确认 | T字板 | 先看竞价承接，回封或结构确认命中才参与 |",
            ]
        )
        with patch("daily_report_render._render_report_with_display_mode", side_effect=[stale_full_report, "# summary"]):
            outputs = build_report_outputs(data, "2026-06-11", emit_preflight=False)

        rendered = outputs[REPORT_VARIANT_FULL]
        self.assertIn("**过程候选回看**（1只，仅保留过程回看）:（过程证据）", rendered)
        self.assertIn("过程候选，仅保留过程回看", rendered)
        self.assertIn("只观察承接，不新增参与", rendered)
        self.assertNotIn("等观察位出现", rendered)
        self.assertNotIn("命中才参与", rendered)
        self.assertNotIn("**明日继续观察**", rendered)

    def test_build_report_outputs_returns_lightweight_evidence_and_run_log_variants(self):
        data = _complete_report_facts({"sections": [{"title": "A股市场分析", "content": "正文"}]})
        full_report = "# full\n\n正文\n\n## 八、详细附录\n\n附录正文"
        with patch("daily_report_render._render_report_with_display_mode", side_effect=[full_report, "# summary"]):
            outputs = build_report_outputs(data, "2026-05-31", emit_preflight=False)

        self.assertIn(REPORT_VARIANT_FULL, outputs)
        self.assertIn(REPORT_VARIANT_SUMMARY, outputs)
        self.assertIn(REPORT_VARIANT_LIGHTWEIGHT, outputs)
        self.assertIn(REPORT_VARIANT_EVIDENCE_APPENDIX, outputs)
        self.assertIn(REPORT_VARIANT_RUN_LOG, outputs)
        self.assertIn("## 狙击手执行图", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("普通候选", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("强核心", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("已有旧仓", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("失败仓/退潮", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("## 证据附录", outputs[REPORT_VARIANT_EVIDENCE_APPENDIX])
        self.assertIn("A股日报运行日志", outputs[REPORT_VARIANT_RUN_LOG])
        self.assertIn("## 运行概览", outputs[REPORT_VARIANT_RUN_LOG])
        self.assertIn("| 项目 | 值 |", outputs[REPORT_VARIANT_RUN_LOG])

    def test_finalize_run_log_text_marks_audit_result(self):
        base = build_run_log_text({"status": "success", "target_date": "2026-05-31", "checks": [], "decision_checks": []}, "2026-05-31")
        finalized = finalize_run_log_text(base, {"passed": True, "findings": []})

        self.assertIn("## 日报一致性检查", finalized)
        self.assertIn("| 正文一致性 | 已通过 | 日报一致性检查通过 |", finalized)

    def test_run_log_discloses_status_coverage_and_request_diagnostics(self):
        data = _complete_report_facts()
        data["module_logs"] = [
            log for log in data["module_logs"] if log.get("step") != "request.market_stats"
        ] + [
            {
                "step": "request.pool_snapshot",
                "status": "success",
                "details": {"provider": "tushare.limit_list_ths", "row_count": 1},
            }
        ]
        data["request_diagnostics"] = {
            "summary": {
                "request_log_count": 33,
                "error_count": 0,
                "degraded_count": 2,
                "fallback_count": 1,
                "data_status_total": 32,
                "data_status_failed": 0,
                "step_status_total": 30,
                "step_status_failed": 0,
            },
            "failures": [],
            "degraded": [
                {
                    "step": "request.stock_quotes",
                    "provider": "tushare.daily+tencent.get_stock_batch_info",
                    "target_keys": ["stock_full_info"],
                    "message": "历史日期股票行情仍有缺口",
                    "details": {"missing_count": 1},
                }
            ],
            "fallbacks": [
                {
                    "step": "request.integrated_hot_rank",
                    "provider": "primary_hot_rank.fallback",
                    "target_keys": ["integrated_hot_list"],
                    "message": "已处理整合热榜请求",
                    "details": {"integrated_count": 50, "required_count": 50},
                }
            ],
        }

        preflight = build_report_preflight(data, "2026-08-19")
        run_log = build_run_log_text(preflight, "2026-08-19")
        market_stats = next(item for item in preflight["checks"] if item["label"] == "大盘涨跌统计")

        self.assertEqual(market_stats["provider"], "tushare.limit_list_ths")
        self.assertIn("| 数据项状态 | 32/32 |", run_log)
        self.assertIn("| 执行步骤状态 | 30/30 |", run_log)
        self.assertIn("| 请求诊断 | 错误0 / 降级2 / 回退1 |", run_log)
        self.assertIn("## 请求诊断", run_log)
        self.assertIn("primary_hot_rank.fallback", run_log)
        self.assertIn("1条目标记录仍缺失；其余可用记录保留", run_log)
        self.assertIn("备用来源完成50/50条；不单独产生买入资格", run_log)

    def test_build_run_log_text_compacts_long_detail_tables(self):
        echo_lines = ["创新高近25个交易日:"]
        for index in range(25):
            day = index + 1
            echo_lines.append(f"- 2026-05-{day:02d} {100 + day} {day:.2f}% +{day} 半导体")
        run_log = build_run_log_text(
            {
                "status": "success",
                "target_date": "2026-05-29",
                "checks": [],
                "decision_checks": [
                    {
                        "label": "创新高趋势反馈",
                        "status": "success",
                        "row_count": 25,
                        "echo_lines": echo_lines,
                    }
                ],
            },
            "2026-05-29",
        )

        self.assertIn("| 2026-05-01 | 101 | 1.00% | +1 | 半导体 |", run_log)
        self.assertIn("| 已省略 | 19 条 | 完整明细见对应数据表或报告正文 | - | - |", run_log)
        self.assertIn("| 2026-05-25 | 125 | 25.00% | +25 | 半导体 |", run_log)
        self.assertNotIn("2026-05-12", run_log)

    def test_build_lightweight_report_text_keeps_actions_but_drops_heavy_sections(self):
        full_report = """# 2026-05-29 a股市场分析

- **今日基调**: 仅观察，不给新增参与资格

## 明日账户建议
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |
| 0%原因 | 市场情绪退潮未止跌，可能还在释放风险，不继续参与 |
| 明日动作 | 先处理旧仓，不新增参与 |
| T0主对象 | 持有京能电力(600578)，500股；持有华电辽能(600396)，200股；先处理旧仓 |

## 一、交易纪律
旧交易纪律大表不该进入轻量版

### 月度攻防与进攻仓位
月度攻防长表不该进入轻量版

## 二、市场基底
### 1. 指数与市场底色
**T-004**
| 指标 | 数值 | 涨跌幅 | 解读 |
|------|------|--------|------|
| 上证指数 | 4068.57 | -0.73% | 震荡调整 |
| 涨停 / 跌停 | 49 / 50 | - | 活跃度还在，但亏钱端不轻 |

**T-005**
Top50长趋势表不该进入轻量版

### 2. 市场状态结论
**T-006**
| 项目 | 结论 | 依据 |
|------|------|------|
| 市场情绪总状态 | 震荡偏风险 | 先看指数、涨跌家数、跌停扩散 |
| 当前盈亏比 | 不值得主动参与 | 只观察主线、承接和个股结构是否同时修复 |

### 3. 价格带风格
价格带长表不该进入轻量版

## 三、周期与主线
周期长表不该进入轻量版

## 四、资金意图
资金长表不该进入轻量版

## 五、个股解读
### 1. 个股裁决
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |
| 不参与依据 | 市场情绪退潮未止跌，可能还在释放风险，不继续参与 |

## 六、明日执行计划
**T-027**
| 时间窗口 | 要看什么 | 观察资格 | 卖出/风控 | 结论 |
|----------|----------|----------|-----------|------|
| 09:50-10:10 | 观察市场底色、主线承接、观察对象强弱 | 无 | 窗口内处理弱仓/错仓 | 条件未同时满足继续0% |

## 七、最终结论
| 明日结论 | 一句话动作 |
|----------|------------|
| 0%不参与 | 盘前0%；不满足继续0% |

## 八、详细附录
附录长正文
"""

        text = build_lightweight_report_text(full_report, "")

        self.assertIn("## 阅读地图", text)
        self.assertEqual(text.count("## 阅读地图"), 1)
        self.assertLess(text.index("# 2026-05-29 a股市场分析"), text.index("## 阅读地图"))
        self.assertLess(text.index("## 阅读地图"), text.index("## 明日账户建议"))
        self.assertIn("| 1 | 日报裁决总览、明日账户建议、最终结论 |", text)
        self.assertIn("| 4 | 证据附录、运行日志 | 只作复盘证据，不新增明日对象 |", text)
        self.assertIn("## 明日账户建议", text)
        self.assertIn("## 狙击手执行图", text)
        self.assertIn("## 今日市场底色", text)
        self.assertIn("## 个股和持仓处理", text)
        self.assertIn("## 明日三窗口", text)
        self.assertIn("## 最终结论", text)
        self.assertIn("0%原因", text)
        self.assertIn("京能电力", text)
        self.assertIn("华电辽能", text)
        self.assertIn("市场情绪退潮未止跌", text)
        self.assertIn("09:50-10:10", text)
        self.assertIn("先处理旧仓 |\n\n## 狙击手执行图", text)
        self.assertLess(text.index("## 狙击手执行图"), text.index("## 今日市场底色"))
        self.assertNotIn("旧交易纪律大表不该进入轻量版", text)
        self.assertNotIn("月度攻防长表不该进入轻量版", text)
        self.assertNotIn("Top50长趋势表不该进入轻量版", text)
        self.assertNotIn("价格带长表不该进入轻量版", text)
        self.assertNotIn("周期长表不该进入轻量版", text)
        self.assertNotIn("资金长表不该进入轻量版", text)

    def test_build_lightweight_report_text_deduplicates_existing_reading_map_after_title(self):
        full_report = """# 2026-05-29 a股市场分析

## 阅读地图
| 顺序 | 模块 |
|---:|---|
| 1 | 旧地图 |

## 日报裁决总览
| 项目 | 结论 |
|------|------|
| 仓位姿态 | 0%不参与 |

## 明日账户建议
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |

## 五、个股解读
### 1. 个股裁决
无

## 六、明日执行计划
无

## 七、最终结论
无
"""

        text = build_lightweight_report_text(full_report, "")

        self.assertEqual(text.count("## 阅读地图"), 1)
        self.assertLess(text.index("# 2026-05-29 a股市场分析"), text.index("## 阅读地图"))
        self.assertLess(text.index("## 阅读地图"), text.index("## 日报裁决总览"))
        self.assertNotIn("旧地图", text)

    def test_build_lightweight_report_text_drops_top50_section_with_psql_table_label(self):
        full_report = """# 2026-05-29 a股市场分析

## 明日账户建议
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |

## 二、市场基底
### 1. 指数与市场底色
**T-004（PSQL）**
| 指标 | 数值 |
|------|------|
| 上证指数 | 4068.57 |

**T-005（PSQL）**
Top50长趋势表不该进入轻量版

### 2. 市场状态结论
| 项目 | 结论 |
|------|------|
| 市场情绪总状态 | 震荡偏风险 |
"""

        text = build_lightweight_report_text(full_report, "")

        self.assertIn("上证指数", text)
        self.assertIn("市场情绪总状态", text)
        self.assertNotIn("Top50长趋势表不该进入轻量版", text)

    def test_save_report_outputs_writes_split_variant_labels(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            outputs = {
                REPORT_VARIANT_FULL: "# full",
                REPORT_VARIANT_SUMMARY: "# summary",
                REPORT_VARIANT_LIGHTWEIGHT: "# light",
                REPORT_VARIANT_EVIDENCE_APPENDIX: "# evidence",
                REPORT_VARIANT_RUN_LOG: "# log",
            }

            saved = save_report_outputs(outputs, "2026-05-31", mode=LEDGER_MODE_REPLAY, output_dir=str(root))

            self.assertTrue((root / "2026-05-31_A股日报_完整版_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_执行摘要_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_轻量版_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_证据附录_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_运行日志_replay.md").exists())
            self.assertEqual(saved[REPORT_VARIANT_LIGHTWEIGHT], str(root / "2026-05-31_A股日报_轻量版_replay.md"))
            companion_dir = root / "2026-05-31_A股日报_伴随文档_replay"
            self.assertEqual(saved[REPORT_COMPANION_DOCS], str(companion_dir))
            for filename in ["AGENTS.md", "flow.md", "testing.md", "readme.md"]:
                self.assertTrue((companion_dir / filename).exists())

    def test_save_report_outputs_places_companion_docs_with_replay_when_any_variant_is_frozen(self):
        with TemporaryDirectory() as tempdir, patch("daily_report_render._reports_root", return_value=Path(tempdir)):
            root = Path(tempdir)
            frozen_summary = root / "2026-05-31_A股日报_执行摘要.md"
            frozen_summary.write_text("# frozen summary", encoding="utf-8")
            outputs = {
                REPORT_VARIANT_FULL: "# full",
                REPORT_VARIANT_SUMMARY: "# summary",
            }

            saved = save_report_outputs(outputs, "2026-05-31", mode=LEDGER_MODE_FROZEN)

            self.assertEqual(saved[REPORT_VARIANT_FULL], str(root / "2026-05-31_A股日报_完整版.md"))
            self.assertEqual(saved[REPORT_VARIANT_SUMMARY], str(root / "replay" / "2026-05-31_A股日报_执行摘要_replay.md"))
            self.assertEqual(saved[REPORT_COMPANION_DOCS], str(root / "replay" / "2026-05-31_A股日报_伴随文档_replay"))

    def test_save_report_outputs_backfills_run_log_paths(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            outputs = {
                REPORT_VARIANT_FULL: "# full",
                REPORT_VARIANT_SUMMARY: "# summary",
                REPORT_VARIANT_LIGHTWEIGHT: "# light",
                REPORT_VARIANT_EVIDENCE_APPENDIX: "# evidence",
                REPORT_VARIANT_RUN_LOG: "# log\n\n## 生成文件路径\n\n| 报告 | 路径 |\n|------|------|\n| 待写入 | 保存路径将在写入后由主流程打印。 |\n",
            }

            saved = save_report_outputs(outputs, "2026-05-31", mode=LEDGER_MODE_REPLAY, output_dir=str(root))

            run_log = Path(saved[REPORT_VARIANT_RUN_LOG]).read_text(encoding="utf-8")
            self.assertIn("| 轻量版 |", run_log)
            self.assertIn("2026-05-31_A股日报_轻量版_replay.md", run_log)
            self.assertIn("| 证据附录 |", run_log)
            self.assertIn("| 伴随文档 |", run_log)
            self.assertIn("2026-05-31_A股日报_伴随文档_replay", run_log)
            self.assertNotIn("保存路径将在写入后由主流程打印", run_log)

    def test_build_report_outputs_persists_decision_ledger_before_replay_full_render(self):
        data = _complete_report_facts({"foo": "bar"})
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            build_report_outputs(data, "2026-04-22", run_mode="replay", emit_preflight=False)

        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_decision_ledger"])
        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_candidate_traces"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_candidate_traces"])

    def test_build_report_outputs_can_render_without_runtime_artifact_persistence(self):
        data = _complete_report_facts({"foo": "bar"})
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            build_report_outputs(
                data,
                "2026-04-22",
                run_mode="replay",
                emit_preflight=False,
                persist_runtime_artifacts=False,
            )

        self.assertFalse(render_mock.call_args_list[0].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[0].kwargs["persist_candidate_traces"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_candidate_traces"])

    def test_build_report_outputs_reuses_one_wiki_compile_and_keeps_evidence_after_actions(self):
        from report import runtime as report_runtime
        from report.markdown_report_html import render_markdown_report_html

        data = _complete_report_facts(
            {
                "query_date": "2026-07-17",
                "knowledge_hit_facts": {
                    "market": {
                        "index_trend": "上涨",
                        "breadth": "上涨家数偏弱",
                        "turnover_distribution": "成交集中",
                    }
                },
            }
        )
        action_body = "\n".join(
            [
                "# 日报",
                "",
                "## 明日执行结论",
                "",
                "### 账户动作",
                "",
                "明日新仓 0%不参与。",
                "",
                "### 执行条件",
                "",
                "条件满足才可做。",
                "",
                "### 不执行条件",
                "",
                "条件未满足，明日不做。",
            ]
        )
        original_builder = report_runtime.build_llm_wiki_context
        with patch(
            "report.runtime.build_llm_wiki_context",
            wraps=original_builder,
        ) as context_builder, patch(
            "report.runtime._render_markdown_report_legacy_body",
            return_value=action_body,
        ), patch(
            "report.runtime.build_knowledge_hits_note",
            # Exercise legacy section ordering without requiring retired Wiki
            # content to remain a current source of trading instructions.
            return_value=["## 经验库命中", "- 目标日来源用于历史核对。"],
        ):
            outputs = build_report_outputs(
                data,
                "2026-07-12",
                emit_preflight=False,
                persist_runtime_artifacts=False,
            )

        context_builder.assert_called_once_with(
            target_date="2026-07-12",
            query_date="2026-07-17",
        )
        for variant in (REPORT_VARIANT_FULL, REPORT_VARIANT_SUMMARY):
            report = outputs[variant]
            for heading in (
                "## 明日执行结论",
                "### 账户动作",
                "### 执行条件",
                "### 不执行条件",
                "## 经验库命中",
            ):
                self.assertIn(heading, report)
            self.assertLess(report.index("## 明日执行结论"), report.index("## 经验库命中"))
            self.assertLess(report.index("### 账户动作"), report.index("## 经验库命中"))
            self.assertLess(report.index("### 执行条件"), report.index("## 经验库命中"))
            self.assertLess(report.index("### 不执行条件"), report.index("## 经验库命中"))

        bear_html = render_markdown_report_html(
            outputs[REPORT_VARIANT_FULL],
            title="日报",
            trade_date="2026-07-12",
        )
        self.assertLess(bear_html.index("明日执行结论"), bear_html.index("经验库命中"))
        self.assertIn("bear-section-action", bear_html)
        self.assertIn("bear-section-evidence", bear_html)

    def test_build_report_outputs_keeps_market_language_after_actions_in_both_variants(self):
        from report.front_page_v2_renderer import render_front_page_v2
        from report.markdown_report_html import render_markdown_report_html

        data = _complete_report_facts()
        artifact = _market_language_test_artifact()

        def render(display_mode, payload, target_date, **kwargs):
            return "\n".join(
                render_front_page_v2(
                    [],
                    target_date=target_date,
                    market_research_snapshot={},
                    market_language_translation=kwargs["market_language_translation"],
                )
            )

        with patch(
            "daily_report_render._render_report_with_display_mode",
            side_effect=render,
        ):
            outputs = build_report_outputs(
                data,
                "2026-07-10",
                emit_preflight=False,
                market_language_translation=artifact,
            )

        for variant in (REPORT_VARIANT_FULL, REPORT_VARIANT_SUMMARY):
            report = outputs[variant]
            self.assertLess(
                report.index("### 明日行动清单"),
                report.index("## 市场语言翻译（研究证据）"),
            )

        bear_html = render_markdown_report_html(
            outputs[REPORT_VARIANT_FULL],
            title="日报",
            trade_date="2026-07-10",
        )
        self.assertLess(
            bear_html.index("明日行动清单"),
            bear_html.index("市场语言翻译（研究证据）"),
        )

    def test_build_report_outputs_can_enable_decision_ledger_separately(self):
        data = _complete_report_facts({"foo": "bar"})
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            build_report_outputs(
                data,
                "2026-04-22",
                run_mode="replay",
                emit_preflight=False,
                persist_runtime_artifacts=False,
                persist_decision_ledger=True,
            )

        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_decision_ledger"])

    def test_persist_report_runtime_artifacts_reuses_report_runtime_context(self):
        data = {
            "execution_stage_context": {
                "extreme_conviction_list": [{"code": "000001"}],
                "candidate_traces": [{"code": "000001"}],
                "candidate_trace_eliminated_summary": [{"reason": "条件未满足"}],
            },
            "market_research_snapshot": {"market_branch": "冰点修复"},
        }
        decision_result = {"case_count": 1, "tracking_lines": ["记录已写入"]}
        trace_result = {"trace_count": 1}

        with patch("report.runtime._maybe_persist_decision_ledger", return_value=decision_result) as decision_mock, \
             patch("report.runtime._prune_decision_ledger_result_for_current_extreme_list", return_value=decision_result) as prune_mock, \
             patch("report.runtime._maybe_persist_candidate_traces", return_value=trace_result) as trace_mock:
            result = persist_report_runtime_artifacts(data, "2026-06-08", run_mode="replay")

        self.assertIs(result["decision_ledger_artifacts"], decision_result)
        self.assertIs(result["candidate_trace_artifact"], trace_result)
        self.assertIs(data["decision_ledger_artifacts"], decision_result)
        self.assertIs(data["candidate_trace_artifact"], trace_result)
        self.assertIs(data["execution_stage_context"]["candidate_trace_artifact"], trace_result)
        decision_mock.assert_called_once()
        prune_mock.assert_called_once()
        trace_mock.assert_called_once()
        self.assertEqual(trace_mock.call_args.kwargs["run_mode"], "replay")

    def test_persist_report_runtime_artifacts_keeps_projected_extreme_candidates(self):
        from report import runtime as report_runtime

        extreme_candidates = [
            {"code": "603005", "name": "晶方科技", "sector": "半导体", "conviction_reason": "承接清楚"},
            {"code": "600584", "name": "长电科技", "sector": "半导体", "conviction_reason": "容量核心"},
            {"code": "002185", "name": "华天科技", "sector": "半导体", "conviction_reason": "补涨观察"},
        ]
        mainline_summary = {"relationship": "半导体扩散"}
        data = {
            "extreme_conviction_list": extreme_candidates,
            "mainline_turnover_summary": mainline_summary,
            "source_report": {"path": "reports/2026-08-06_A股日报_完整版.md"},
        }
        data["execution_stage_context"] = (
            report_runtime._compact_execution_stage_context_for_persistence(
                {
                    "extreme_conviction_list": extreme_candidates,
                    "mainline_turnover_summary": mainline_summary,
                },
                canonical_data=data,
            )
        )
        self.assertNotIn("mainline_turnover_summary", data["execution_stage_context"])

        with TemporaryDirectory() as tempdir, patch(
            "daily_report_render._module_dir",
            return_value=Path(tempdir) / "scripts",
        ), patch.dict(
            "os.environ",
            {
                "A_DAILY_REPORT_DATABASE_URL": "",
                "DATABASE_URL": "",
                "A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "",
            },
        ), patch(
            "report.runtime._maybe_persist_candidate_traces",
            return_value=None,
        ), patch(
            "daily_report_render.build_topic_lifecycle_snapshot",
            return_value={},
        ):
            result = persist_report_runtime_artifacts(data, "2026-08-06")
            snapshot_path = Path(result["decision_ledger_artifacts"]["snapshot_path"])
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual([case["stock_code"] for case in snapshot["cases"]], ["603005", "600584", "002185"])
        self.assertEqual(
            {case["hypothesis"]["sector_relationship_state"] for case in snapshot["cases"]},
            {"半导体扩散"},
        )

    def test_persist_replay_runtime_artifacts_never_selects_postgres_writers(self):
        from storage.database_service import DatabaseService

        class ReadOnlyService:
            def is_postgres_backed(self):
                return True

            def query_extreme_conviction_mentions(self, *_args, **_kwargs):
                return []

            def read_decision_ledger_index(self, *_args, **_kwargs):
                return {}

            def replace_decision_ledger_snapshot(self, *_args, **_kwargs):
                raise AssertionError("replay must not write a decision ledger")

            def replace_candidate_trace_artifact(self, *_args, **_kwargs):
                raise AssertionError("replay must not write candidate traces")

            def mark_a_kill_shape_extreme_conviction_mentions(self, *_args, **_kwargs):
                raise AssertionError("replay must not update historical mentions")

        data = {
            "execution_stage_context": {
                "extreme_conviction_list": [{"code": "000001", "name": "测试股票"}],
                "candidate_traces": [{"stock_code": "000001", "stock_name": "测试股票"}],
            },
            "market_research_snapshot": {"market_branch": "修复"},
        }
        service = ReadOnlyService()
        with TemporaryDirectory() as tempdir, \
             patch("daily_report_render._module_dir", return_value=Path(tempdir) / "scripts"), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://unit-test/report"}), \
             patch.object(
                 DatabaseService,
                 "from_environment",
                 return_value=service,
             ), \
             patch.object(
                 DatabaseService,
                 "fact_store_from_environment",
                 return_value=service,
             ):
            result = persist_report_runtime_artifacts(data, "2026-06-08", run_mode="replay")

        self.assertEqual(
            result["decision_ledger_artifacts"]["fact_db_sync"]["status"],
            "not_run",
        )
        self.assertEqual(result["candidate_trace_artifact"]["trace_count"], 1)

    def test_persist_report_runtime_artifacts_writes_topic_lifecycle(self):
        data = {
            "trade_date": "2026-06-14",
            "realtime_tag_evidence_snapshot": {
                "groups": [
                    {
                        "采用名称": "PCB电子材料",
                        "大方向": "AI算力基础设施",
                        "当日主攻分支": "PCB电子材料",
                        "表层行业名": ["PCB", "电子材料"],
                        "资金证据": "资金指向：PCB电子材料",
                        "扩散证据": "同分支多只个股上涨",
                    }
                ]
            },
            "execution_stage_context": {
                "candidate_traces": [
                    {
                        "stock_name": "胜宏科技",
                        "stock_code": "300476",
                        "sector": "PCB电子材料",
                        "mainline": "AI算力基础设施",
                        "final_action": "沿PCB电子材料核心承接继续观察",
                        "anchor_reversal": {
                            "candidate_role": "趋势核心",
                            "anchor_reversal_decision": "可作为主对象",
                            "anchor_reversal_reason": "核心承接稳定",
                        },
                    }
                ]
            },
            "market_research_snapshot": {},
        }

        with TemporaryDirectory() as tempdir, \
             patch("daily_report_render._module_dir", return_value=Path(tempdir) / "scripts"), \
             patch("report.runtime._maybe_persist_decision_ledger", return_value=None), \
             patch("report.runtime._maybe_persist_candidate_traces", return_value=None):
            result = persist_report_runtime_artifacts(data, "2026-06-14", run_mode="replay")
            snapshot_path = Path(result["topic_lifecycle_artifact"]["snapshot_path"])
            index_path = Path(result["topic_lifecycle_artifact"]["index_path"])
            stored_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            stored_index = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(stored_snapshot["trade_date"], "2026-06-14")
        self.assertEqual(stored_snapshot["cards"][0]["lifecycle_phase"], "主攻期")
        self.assertEqual(stored_index["latest_trade_date"], "2026-06-14")
        self.assertIn("topic_lifecycle_artifact", data)

    def test_build_report_outputs_keeps_private_position_report_out_of_daily_reports(self):
        private_position_text = "\n## 持仓策略\n| 上峰水泥 | 100.0% | 私密动作 |\n"
        data = _complete_report_facts({"foo": "bar"})

        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]):
            outputs = build_report_outputs(
                data,
                "2026-05-19",
                position_report_text=private_position_text,
                emit_preflight=False,
            )

        self.assertNotIn("持仓策略", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("上峰水泥", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("100.0%", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("持仓策略", outputs[REPORT_VARIANT_SUMMARY])
        self.assertNotIn("上峰水泥", outputs[REPORT_VARIANT_SUMMARY])
        self.assertNotIn("100.0%", outputs[REPORT_VARIANT_SUMMARY])

    def test_build_report_outputs_passes_structured_position_context_without_private_report_text(self):
        data = _complete_report_facts({
            "personal_position_context": {
                "account_profile": {"capital_text": "1w本金；总资产10126.52；当日盈利126.52（+1.27%）"},
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有晶方科技(603005)1手，成本43.835；先处理旧仓",
                },
            }
        })

        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            outputs = build_report_outputs(
                data,
                "2026-05-26",
                has_personal_positions=True,
                position_report_text="\n## 持仓策略\n| 晶方科技 | 100.0% | 私密动作 |\n",
                emit_preflight=False,
            )

        self.assertNotIn("持仓策略", outputs[REPORT_VARIANT_FULL])
        self.assertEqual(render_mock.call_count, 2)
        self.assertTrue(render_mock.call_args_list[0].kwargs["has_personal_positions"])
        self.assertIn("personal_position_context", data)

    def test_save_replay_outputs_rebuilds_decision_ledger_from_final_full_markdown(self):
        stale_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "600850", "name": "电科数字", "sector": "数据中心", "conviction_reason": "旧名单"},
                {"code": "603082", "name": "北自科技", "sector": "机器人", "conviction_reason": "旧名单"},
            ],
            market_branch="旧结果",
            sector_relationship_state="旧结果",
        )
        fresh_report = """
**极度看好名单**（只保留最心动的少数，每只都绑定参与窗口）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|
| 1 | 合百集团 | 000417 | 股权转让 | 板块锚定龙 | 板块锚定龙 | 只盯分歧后的转强 |
| 2 | 弘信电子 | 300657 | 算力 | 弹性核心 | 主线共振 | 只盯主动转强 |
| 3 | 利仁科技 | 001259 | 家电 | 高辨识度首板 | 资金承接强 | 不追一致高潮 |
"""

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(stale_snapshot, root_dir=root)

            save_report_outputs(
                {REPORT_VARIANT_FULL: fresh_report, REPORT_VARIANT_SUMMARY: "# summary"},
                "2026-05-18",
                mode=LEDGER_MODE_REPLAY,
                output_dir=str(root),
                sync_replay_decision_ledger=True,
            )

            snapshot = json.loads((root / "data" / "decision-ledger" / "2026-05-18.json").read_text(encoding="utf-8"))
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        self.assertEqual([case["stock_code"] for case in snapshot["cases"]], ["000417", "300657", "001259"])
        same_day_rows = {
            row["stock_code"]
            for row in index["extreme_conviction_backtest_rows"]
            if row["mention_trade_date"] == "2026-05-18"
        }
        self.assertEqual(same_day_rows, {"000417", "300657", "001259"})
        self.assertNotIn("600850", index["by_stock_code"])
        self.assertNotIn("603082", index["by_stock_code"])

    def test_save_replay_outputs_markdown_sync_does_not_override_runtime_revision(self):
        runtime_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-06-12",
            extreme_conviction_list=[
                {"code": "002971", "name": "和远气体", "sector": "化工原料", "attack_state": "0%"},
            ],
            market_branch="板块资金扩散",
            sector_relationship_state="半导体扩散",
            final_action={
                "label": "50%条件执行",
                "position_pct": 50,
                "target": {"code": "600584", "name": "长电科技", "sector": "半导体"},
                "source": "sector_capital_preflight",
            },
        )
        final_report = """
**极度看好名单**（旧正文表只作过程样本）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|
| 1 | 和远气体 | 002971 | 化工原料 | 过程样本 | 炸板57次且尾盘才回封 | 只观察 |
"""

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(runtime_snapshot, root_dir=root)
            revision_path = root / "data" / "decision-ledger" / "revisions" / "2026-06-12.jsonl"
            before = revision_path.read_text(encoding="utf-8").splitlines()

            save_report_outputs(
                {REPORT_VARIANT_FULL: final_report, REPORT_VARIANT_SUMMARY: "# summary"},
                "2026-06-12",
                mode=LEDGER_MODE_REPLAY,
                output_dir=str(root),
                sync_replay_decision_ledger=True,
            )

            after = revision_path.read_text(encoding="utf-8").splitlines()
            latest = json.loads(after[-1])
            snapshot = json.loads(
                (root / "data" / "decision-ledger" / "2026-06-12.json").read_text(encoding="utf-8")
            )

        self.assertEqual(len(after), len(before))
        self.assertEqual(latest["decision_summary"]["final_action_label"], "50%条件执行")
        self.assertEqual(latest["decision_summary"]["final_target"]["stock_code"], "600584")
        self.assertEqual(snapshot["final_action"]["label"], "50%条件执行")
        self.assertEqual(snapshot["final_action"]["target"]["stock_code"], "600584")

    def test_save_replay_outputs_postgres_only_markdown_sync_keeps_runtime_final_action(self):
        runtime_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-06-12",
            extreme_conviction_list=[
                {"code": "002971", "name": "和远气体", "sector": "化工原料", "attack_state": "0%"},
            ],
            market_branch="板块资金扩散",
            sector_relationship_state="半导体扩散",
            final_action={
                "label": "50%条件执行",
                "position_pct": 50,
                "target": {"code": "600584", "name": "长电科技", "sector": "半导体"},
                "source": "sector_capital_preflight",
            },
        )
        final_report = """
**极度看好名单**（旧正文表只作过程样本）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|
| 1 | 和远气体 | 002971 | 化工原料 | 过程样本 | 炸板57次且尾盘才回封 | 只观察 |
"""

        class StubService:
            def __init__(self):
                self.saved_snapshots = []

            def is_postgres_backed(self):
                return True

            def read_decision_ledger_index(self, end_date=None, window_days=25):
                return {}

            def replace_decision_ledger_snapshot(self, payload):
                self.saved_snapshots.append(payload)
                return {"cases": len(payload.get("cases") or []), "mentions": 1}

        service = StubService()
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(
                runtime_snapshot,
                root_dir=root,
                database_service=service,
                write_json_archive=False,
            )
            revision_path = root / "data" / "decision-ledger" / "revisions" / "2026-06-12.jsonl"
            before = revision_path.read_text(encoding="utf-8").splitlines()

            with patch.dict(os.environ, {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=False):
                with patch("storage.database_service.DatabaseService.fact_store_from_environment", return_value=service):
                    save_report_outputs(
                        {REPORT_VARIANT_FULL: final_report, REPORT_VARIANT_SUMMARY: "# summary"},
                        "2026-06-12",
                        mode=LEDGER_MODE_REPLAY,
                        output_dir=str(root),
                        postgres_only=True,
                        sync_replay_decision_ledger=True,
                    )

            after = revision_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(after), len(before))
        self.assertEqual(service.saved_snapshots[-1]["final_action"]["label"], "50%条件执行")
        self.assertEqual(service.saved_snapshots[-1]["final_action"]["target"]["stock_code"], "600584")

    def test_save_replay_outputs_does_not_sync_decision_ledger_by_default(self):
        stale_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "600850", "name": "电科数字", "sector": "数据中心", "conviction_reason": "旧名单"},
            ],
            market_branch="旧结果",
            sector_relationship_state="旧结果",
        )
        fresh_report = """
**极度看好名单**（只保留最心动的少数，每只都绑定参与窗口）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|
| 1 | 合百集团 | 000417 | 股权转让 | 板块锚定龙 | 板块锚定龙 | 只盯分歧后的转强 |
"""

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(stale_snapshot, root_dir=root)

            save_report_outputs(
                {REPORT_VARIANT_FULL: fresh_report, REPORT_VARIANT_SUMMARY: "# summary"},
                "2026-05-18",
                mode=LEDGER_MODE_REPLAY,
                output_dir=str(root),
            )

            snapshot = json.loads((root / "data" / "decision-ledger" / "2026-05-18.json").read_text(encoding="utf-8"))

        self.assertEqual([case["stock_code"] for case in snapshot["cases"]], ["600850"])

    def test_save_replay_outputs_keeps_existing_decision_ledger_when_final_markdown_has_no_list(self):
        existing_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-22",
            extreme_conviction_list=[
                {
                    "code": "000636",
                    "name": "风华高科",
                    "sector": "元器件",
                    "source_tier": "extreme_conviction",
                    "execution_eligibility": "observation_only",
                    "attack_state": "0%不参与",
                    "conviction_reason": "形态健康，但最终0%只观察承接",
                }
            ],
            market_branch="空仓等待",
            sector_relationship_state="只观察",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = _DecisionLedgerMemoryFactStore()
            write_decision_ledger_artifacts(existing_snapshot, root_dir=root, database_service=service)

            save_report_outputs(
                {
                    REPORT_VARIANT_FULL: "# 2026-05-22 A股市场分析\n\n正文没有候选表。",
                    REPORT_VARIANT_SUMMARY: "# summary",
                },
                "2026-05-22",
                mode=LEDGER_MODE_REPLAY,
                output_dir=str(root),
                sync_replay_decision_ledger=True,
            )

            snapshot = json.loads((root / "data" / "decision-ledger" / "2026-05-22.json").read_text(encoding="utf-8"))
            rows = service.query_extreme_conviction_mentions("2026-05-22", window_days=25)

        self.assertEqual([case["stock_code"] for case in snapshot["cases"]], ["000636"])
        self.assertEqual([row["stock_code"] for row in rows], ["000636"])

    def test_render_report_with_display_mode_forwards_decision_ledger_config(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        captured = {}

        def _fake_generate_markdown_report(*args, **kwargs):
            captured.update(kwargs)
            return "# report"

        fake_demo.DISPLAY_MVP_MODE = False
        fake_demo.EMIT_HELPER_DIAGNOSTICS = True
        fake_demo.REPORT_RUNTIME_CACHE = None
        fake_demo.REPORT_RUNTIME_TIMING_ROWS = None
        fake_demo.generate_markdown_report = _fake_generate_markdown_report
        runtime_timing_rows = []

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = _render_report_with_display_mode(
                False,
                {"foo": "bar"},
                "2026-05-14",
                persist_decision_ledger=True,
                decision_ledger_root_dir="/tmp/decision-ledger-root",
                persist_candidate_traces=True,
                candidate_trace_root_dir="/tmp/candidate-trace-root",
                runtime_timing_rows=runtime_timing_rows,
                postgres_only=True,
            )

        self.assertEqual(rendered, "# report")
        self.assertTrue(captured["persist_decision_ledger"])
        self.assertEqual(captured["decision_ledger_root_dir"], "/tmp/decision-ledger-root")
        self.assertTrue(captured["persist_candidate_traces"])
        self.assertEqual(captured["candidate_trace_root_dir"], "/tmp/candidate-trace-root")
        self.assertTrue(captured["postgres_only"])
        self.assertIsNone(fake_demo.REPORT_RUNTIME_TIMING_ROWS)
        self.assertFalse(fake_demo._POSTGRES_ONLY_RUNTIME)

    def test_render_report_with_display_mode_sets_postgres_only_runtime_on_demo_module(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.DISPLAY_MVP_MODE = False
        fake_demo.EMIT_HELPER_DIAGNOSTICS = True
        fake_demo.REPORT_RUNTIME_CACHE = None
        fake_demo._POSTGRES_ONLY_RUNTIME = False

        def _fake_generate_markdown_report(*args, **kwargs):
            self.assertTrue(fake_demo._POSTGRES_ONLY_RUNTIME)
            return "# report"

        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = _render_report_with_display_mode(
                False,
                {"postgres_only": True},
                "2026-05-29",
                postgres_only=True,
            )

        self.assertEqual(rendered, "# report")
        self.assertFalse(fake_demo._POSTGRES_ONLY_RUNTIME)

    def test_render_report_with_display_mode_sets_postgres_only_env_guard(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.DISPLAY_MVP_MODE = False
        fake_demo.EMIT_HELPER_DIAGNOSTICS = True
        fake_demo.REPORT_RUNTIME_CACHE = None
        fake_demo._POSTGRES_ONLY_RUNTIME = False

        def _fake_generate_markdown_report(*args, **kwargs):
            self.assertEqual(os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"), "1")
            return "# report"

        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}), \
             patch.dict(os.environ, {}, clear=True):
            rendered = _render_report_with_display_mode(
                False,
                {"postgres_only": True},
                "2026-05-29",
                postgres_only=True,
            )

        self.assertEqual(rendered, "# report")
        self.assertIsNone(os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"))

    def test_build_report_outputs_can_suppress_preflight_output(self):
        data = _complete_report_facts()

        stdout = io.StringIO()
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]):
            with redirect_stdout(stdout):
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        self.assertEqual(stdout.getvalue(), "")

    def test_build_report_outputs_aborts_when_critical_data_failed(self):
        data = {
            "data_status": {
                "两市成交额": False,
                "中证全指": False,
                "成交额排名": False,
            },
            "step_status": {
                "两市成交额获取": False,
                "中证全指获取": False,
                "成交额排名获取": False,
            },
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()
        message = str(error.exception)
        self.assertIn("关键数据不完整，停止生成", message)
        self.assertIn("两市成交额", message)
        self.assertIn("中证全指", message)
        self.assertIn("成交额排名", message)

    def test_build_report_outputs_aborts_when_decision_source_failed(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "整合热榜": False,
            },
            "step_status": {"整合热榜获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "integrated_hot_list": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.integrated_hot_rank",
                    "status": "error",
                    "details": {"provider": "hot_list_integrated.get_integrated_hot_list", "error": "boom"},
                },
            ],
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()
        self.assertIn("整合热榜", str(error.exception))

    def test_build_report_outputs_aborts_when_limit_down_pool_status_failed(self):
        data = _complete_report_facts(
            {
                "data_status": {
                    "涨停池": True,
                    "涨停股板块分布": True,
                    "跌停池": False,
                    "跌停股板块分布": False,
                },
                "zt_pool": [{"代码": "000001"}],
                "zt_pool_by_sector": {"银行": [{"code": "000001"}]},
                "dt_pool": [],
                "dt_pool_by_sector": {},
            }
        )

        preflight = build_report_preflight(data, "2026-08-04")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("跌停池", preflight["failures"])
        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                build_report_outputs(data, "2026-08-04", emit_preflight=False)

        render_mock.assert_not_called()
        self.assertIn("跌停池", str(error.exception))

    def test_report_preflight_accepts_confirmed_zero_limit_pools(self):
        data = _complete_report_facts(
            {
                "data_status": {
                    "涨停池": True,
                    "涨停股板块分布": True,
                    "跌停池": True,
                    "跌停股板块分布": True,
                },
                "step_status": {"涨停跌停数据获取": True},
                "market_stats": {
                    "up_count": 2600,
                    "down_count": 2100,
                    "zt_count": 0,
                    "dt_count": 0,
                },
                "zt_pool": [],
                "zt_pool_by_sector": {},
                "dt_pool": [],
                "dt_pool_by_sector": {},
            }
        )

        with patch("daily_report_render.index_cross_validation_required", return_value=False):
            preflight = build_report_preflight(data, "2026-08-04")

        self.assertEqual(preflight["status"], "success")
        self.assertNotIn("涨停池", preflight["failures"])
        self.assertNotIn("跌停池", preflight["failures"])

    def test_report_preflight_accepts_postgres_limit_pool_facts_without_transient_step_status(self):
        data = _complete_report_facts(
            {
                "postgres_only": True,
                "data_status": {
                    "涨停池": True,
                    "涨停股板块分布": True,
                    "跌停池": True,
                    "跌停股板块分布": True,
                },
                "zt_pool": [{"代码": "000001"}],
                "zt_pool_by_sector": {"银行": [{"code": "000001"}]},
                "dt_pool": [{"代码": "000002"}],
                "dt_pool_by_sector": {"地产": [{"code": "000002"}]},
                "module_logs": [],
            }
        )
        data["step_status"].pop("涨停跌停数据获取")

        with patch("daily_report_render.index_cross_validation_required", return_value=False):
            preflight = build_report_preflight(data, "2026-08-04")

        for label in ("涨停池", "涨停股板块分布", "跌停池", "跌停股板块分布"):
            self.assertNotIn(label, preflight["failures"])

    def test_report_preflight_rejects_postgres_limit_pool_facts_from_other_date(self):
        data = _complete_report_facts(
            {
                "postgres_only": True,
                "data_status": {
                    "涨停池": True,
                    "涨停股板块分布": True,
                    "跌停池": True,
                    "跌停股板块分布": True,
                },
                "zt_pool": [{"代码": "000001", "trade_date": "2026-08-03"}],
                "zt_pool_by_sector": {
                    "银行": [{"code": "000001", "source_date": "2026-08-03"}]
                },
                "dt_pool": [{"代码": "000002", "date": "2026-08-03"}],
                "dt_pool_by_sector": {
                    "地产": [{"code": "000002", "trade_date": "2026-08-03"}]
                },
                "module_logs": [],
            }
        )
        data["step_status"].pop("涨停跌停数据获取")

        with patch("daily_report_render.index_cross_validation_required", return_value=False):
            preflight = build_report_preflight(data, "2026-08-04")

        for label in ("涨停池", "涨停股板块分布", "跌停池", "跌停股板块分布"):
            self.assertIn(label, preflight["failures"])

    def test_report_preflight_keeps_live_limit_pool_step_evidence_required(self):
        data = _complete_report_facts(
            {
                "data_status": {
                    "涨停池": True,
                    "涨停股板块分布": True,
                    "跌停池": True,
                    "跌停股板块分布": True,
                },
                "zt_pool": [{"代码": "000001"}],
                "zt_pool_by_sector": {"银行": [{"code": "000001"}]},
                "dt_pool": [{"代码": "000002"}],
                "dt_pool_by_sector": {"地产": [{"code": "000002"}]},
                "module_logs": [],
            }
        )
        data["step_status"].pop("涨停跌停数据获取")

        with patch("daily_report_render.index_cross_validation_required", return_value=False):
            preflight = build_report_preflight(data, "2026-08-04")

        for label in ("涨停池", "涨停股板块分布", "跌停池", "跌停股板块分布"):
            self.assertIn(label, preflight["failures"])

    def test_report_preflight_rejects_missing_limit_pool_status_and_payload(self):
        data = _complete_report_facts()

        with patch("daily_report_render.index_cross_validation_required", return_value=False):
            preflight = build_report_preflight(data, "2026-08-04")

        self.assertEqual(preflight["status"], "failed")
        self.assertEqual(
            preflight["failures"],
            ["涨停池", "涨停股板块分布", "跌停池", "跌停股板块分布"],
        )

    def test_report_preflight_rejects_failed_step_status_for_valid_core_payload(self):
        data = _complete_report_facts(
            {
                "step_status": {"两市成交额获取": False},
            }
        )

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("两市成交额", preflight["failures"])

    def test_report_preflight_rejects_success_status_with_missing_decision_payload(self):
        data = _complete_report_facts(
            {
                "data_status": {"雪球A股24小时热榜": True},
                "step_status": {"雪球A股24小时热榜获取": True},
            }
        )

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("雪球A股24小时热榜", preflight["failures"])

    def test_report_preflight_aborts_when_market_breadth_has_only_limit_counts(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
            },
            "step_status": {"涨停跌停数据获取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 0, "down_count": 0, "zt_count": 102, "dt_count": 8},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.market_stats",
                    "status": "degraded",
                    "details": {"provider": "akshare.stock_market_activity_legu"},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-28")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("大盘涨跌统计", preflight["failures"])

    def test_report_preflight_aborts_when_hot_rank_sample_is_short(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "热度前50个股": False,
            },
            "step_status": {"热度前50个股获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "hot_rank_top30": [{"code": f"000{idx:03d}"} for idx in range(1, 31)],
            "hot_rank_sample_size": 30,
            "hot_rank_sample_target": 50,
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.hot_rank.primary",
                    "status": "degraded",
                    "details": {"provider": "tushare.ths_hot", "hot_rank_count": 30, "required_count": 50},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-28")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("热度前50个股", preflight["failures"])
        hot_rank_check = next(check for check in preflight["checks"] if check["label"] == "热度前50个股")
        self.assertEqual(hot_rank_check["value"], "30/50")
        self.assertEqual(hot_rank_check["row_count"], 30)

    def test_report_preflight_aborts_when_legacy_hot_rank_payload_has_only_top30(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "hot_rank_top30": [{"code": f"000{idx:03d}"} for idx in range(1, 31)],
        }

        preflight = build_report_preflight(data, "2026-05-28")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("热度前50个股", preflight["failures"])

    def test_report_preflight_allows_empty_lianban_when_extraction_succeeded(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "step_status": {"连板梯队提取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "lianban_data": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.lianban_snapshot", "status": "success", "details": {"provider": "tushare.limit_list_ths", "lianban_count": 0}},
            ],
        }

        preflight = build_report_preflight(data, "2026-05-13")

        self.assertNotIn("连板梯队", preflight["failures"])

    def test_report_preflight_accepts_xuangubao_plates_and_limit_up_reasons_when_newsflash_is_empty(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "整合热榜": True,
                "预期日历": True,
                "选股通盘中异动": True,
                "顽主杯热门前十": True,
            },
            "step_status": {
                "整合热榜获取": True,
                "预期日历获取": True,
                "选股通盘中异动获取": True,
                "顽主杯热门前十获取": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "integrated_hot_list": [{"code": "000001"}],
            "calendar_events": [{"title": "产业大会"}],
            "wanzhu_top10": [{"code": "000001"}],
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [{"name": "国产芯片"}],
                "xuangubao_limit_up_reasons": [{"symbol": "600676.SS"}],
                "diagnostics": {"newsflash": "missing XUANGUBAO_IVANKA_TOKEN"},
            },
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.integrated_hot_rank", "status": "success", "details": {"provider": "primary_hot_rank.fallback", "integrated_count": 1}},
                {"step": "request.calendar_events", "status": "success", "details": {"provider": "tencent.get_calendar_events", "calendar_count": 1}},
                {
                    "step": "request.xuangubao",
                    "status": "success",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 0,
                        "plate_count": 1,
                        "limit_up_reason_count": 1,
                        "diagnostic_note": "newsflash=missing XUANGUBAO_IVANKA_TOKEN",
                    },
                },
                {"step": "request.wanzhu_top10", "status": "success", "details": {"provider": "AShareDataCollector.get_wanzhu_top10", "stock_count": 1}},
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        self.assertNotIn("选股通盘中异动", preflight["failures"])

    def test_report_preflight_ignores_stale_xuangubao_failure_log_when_payload_has_news(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "xuangubao_data": {
                "xuangubao_news": [{"title": "机器人概念股午后拉升"}],
                "xuangubao_plates": [{"name": "机器人"}],
                "xuangubao_limit_up_reasons": [{"symbol": "603082.SS"}],
            },
            "module_logs": [
                {
                    "step": "request.xuangubao",
                    "status": "failed",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 0,
                        "plate_count": 23,
                        "limit_up_reason_count": 101,
                    },
                }
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        self.assertNotIn("选股通盘中异动", preflight["failures"])

    def test_build_report_outputs_aborts_when_snapshot_envelope_contains_critical_failures(self):
        snapshot = {
            "date": "2026-05-13",
            "saved_at": "2026-05-13T18:12:15",
            "mode": "frozen",
            "data": {
                "total_turnover": 0.0,
                "wind_a_alternative": {"price": 0, "change_pct": 0},
                "turnover_rank": [],
                "data_status": {
                    "两市成交额": False,
                    "中证全指": False,
                    "成交额排名": False,
                },
            },
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError):
                build_report_outputs(snapshot, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()

    def test_build_report_outputs_aborts_when_tracked_critical_payload_is_missing_without_status(self):
        data = {
            "data_status": {"主要指数": True},
            "total_turnover": 0.0,
            "wind_a_alternative": {"price": 6686.865},
            "turnover_rank": [{"code": "000001"}],
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()
        self.assertIn("两市成交额", str(error.exception))

    def test_report_preflight_accepts_turnover_rank_fallback_but_rejects_index_provider(self):
        data = _complete_report_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "akshare.stock_zh_index_daily_em"},
            "csi1000_index": {"price": 6123.45, "data_source": "akshare.stock_zh_index_daily_em"},
            "turnover_rank": [{"code": "000001", "data_source": "eastmoney.push2.clist"}],
            "module_logs": [
                {
                    "step": "request.total_turnover",
                    "status": "success",
                    "details": {"provider": "akshare.stock_zh_index_daily_em", "total_turnover": 12345.67},
                },
                {
                    "step": "request.wind_a",
                    "status": "success",
                    "details": {"provider": "akshare.stock_zh_index_daily_em", "price": 6686.86},
                },
                {
                    "step": "request.csi1000",
                    "status": "success",
                    "details": {"provider": "akshare.stock_zh_index_daily_em", "price": 6123.45},
                },
                {
                    "step": "request.turnover_rank",
                    "status": "success",
                    "details": {"provider": "eastmoney.turnover_rank", "row_count": 50},
                },
            ],
        })

        preflight = build_report_preflight(data, "2026-05-13")

        self.assertEqual(preflight["status"], "failed")
        self.assertEqual(preflight["failures"], ["中证全指", "中证1000"])

    def test_report_preflight_accepts_quicktiny_index_target_date_fallback(self):
        data = _complete_report_facts({
            "wind_a_alternative": {
                "price": 6686.86,
                "trade_date": "2026-07-10",
                "data_source": "quicktiny.merged_kline.index_daily",
            },
            "csi1000_index": {
                "price": 8081.26,
                "trade_date": "2026-07-10",
                "data_source": "quicktiny.merged_kline.index_daily",
            },
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily", "row_count": 5523}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "quicktiny.merged_kline.index_daily", "price": 6686.86}},
                {"step": "request.csi1000", "status": "success", "details": {"provider": "quicktiny.merged_kline.index_daily", "price": 8081.26}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily", "row_count": 50}},
                {"step": "request.market_stats", "status": "success", "details": {"provider": "tushare.daily", "row_count": 5523}},
                {"step": "request.hot_rank.primary", "status": "success", "details": {"provider": "tushare.ths_hot", "hot_rank_count": 50}},
            ],
        })

        preflight = build_report_preflight(data, "2026-07-10")

        self.assertEqual(preflight["status"], "success")
        self.assertNotIn("中证全指", preflight["failures"])
        self.assertNotIn("中证1000", preflight["failures"])

    def test_report_preflight_accepts_akshare_turnover_rank_fallback(self):
        data = _complete_report_facts({
            "turnover_rank": [
                {"code": f"{index:06d}", "data_source": "akshare.stock_zh_a_spot_em"}
                for index in range(1, 51)
            ],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "storage.market_daily_totals", "row_count": 5515}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily", "price": 6119.24}},
                {"step": "request.csi1000", "status": "success", "details": {"provider": "tushare.index_daily", "price": 8081.26}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "akshare.stock_zh_a_spot_em", "row_count": 50}},
                {"step": "request.market_stats", "status": "success", "details": {"provider": "storage.stock_daily_quotes_recent", "row_count": 5515}},
                {"step": "request.hot_rank.primary", "status": "success", "details": {"provider": "tushare.ths_hot", "hot_rank_count": 50}},
            ],
        })

        preflight = build_report_preflight(data, "2026-06-11")

        self.assertEqual(preflight["status"], "success")
        self.assertNotIn("成交额排名", preflight["failures"])

    def test_report_preflight_accepts_structured_postgres_turnover_rank_source(self):
        data = _complete_report_facts({
            "turnover_rank": [{"code": "300308", "data_source": "storage.turnover_rank_daily"} for _ in range(50)],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "storage.market_daily_totals", "row_count": 5515}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily", "price": 6119.24}},
                {"step": "request.csi1000", "status": "success", "details": {"provider": "tushare.index_daily", "price": 8081.26}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "storage.turnover_rank_daily", "row_count": 50}},
                {"step": "request.market_stats", "status": "success", "details": {"provider": "storage.stock_daily_quotes_recent", "row_count": 5515}},
                {"step": "request.hot_rank.primary", "status": "success", "details": {"provider": "tushare.ths_hot", "hot_rank_count": 50}},
            ],
        })

        preflight = build_report_preflight(data, "2026-06-08")

        self.assertEqual(preflight["status"], "success")
        self.assertNotIn("成交额排名", preflight["failures"])

    def test_report_preflight_accepts_positive_total_turnover_from_legacy_provider(self):
        data = _complete_report_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 29170.74,
            "wind_a_alternative": {"price": 6477.21, "data_source": "tushare.index_daily"},
            "csi1000_index": {"price": 8408.73, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "module_logs": [
                {
                    "step": "request.total_turnover",
                    "status": "success",
                    "details": {"provider": "legacy.total_turnover", "total_turnover": 29170.74, "row_count": 0},
                },
                {
                    "step": "request.wind_a",
                    "status": "success",
                    "details": {"provider": "tushare.index_daily", "price": 6477.21},
                },
                {
                    "step": "request.csi1000",
                    "status": "success",
                    "details": {"provider": "tushare.index_daily", "price": 8408.73},
                },
                {
                    "step": "request.turnover_rank",
                    "status": "success",
                    "details": {"provider": "tushare.daily", "row_count": 50},
                },
            ],
        })

        preflight = build_report_preflight(data, "2026-05-18")

        self.assertEqual(preflight["status"], "success")
        self.assertEqual(preflight["failures"], [])

    def test_report_preflight_fails_when_new_high_feedback_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "创新高趋势反馈": False,
            },
            "step_status": {"创新高趋势反馈获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "new_high_feedback": {
                "available": False,
                "status": "upstream_empty",
                "source": "tushare.stk_factor_pro.topdays",
            },
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.new_high_feedback",
                    "status": "degraded",
                    "details": {"provider": "tushare.stk_factor_pro.topdays", "new_high_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("创新高趋势反馈", preflight["failures"])

    def test_report_preflight_echoes_new_high_recent_trend_rows(self):
        data = _complete_report_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "创新高趋势反馈": True,
            },
            "step_status": {"创新高趋势反馈获取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "new_high_feedback": {
                "available": True,
                "source": "tushare.stk_factor_pro.topdays",
                "new_high_count": 169,
                "trend_rows": [
                    {
                        "trade_date": "2026-05-18",
                        "new_high_count": 132,
                        "all_a_share_pct": 2.64,
                        "change_text": "+19",
                        "leading_sectors": "元器件、半导体、化工原料",
                    },
                    {
                        "trade_date": "2026-05-19",
                        "new_high_count": 164,
                        "all_a_share_pct": 3.28,
                        "change_text": "+32",
                        "leading_sectors": "半导体、元器件、专用机械",
                    },
                    {
                        "trade_date": "2026-05-20",
                        "new_high_count": 169,
                        "all_a_share_pct": 3.38,
                        "change_text": "+5",
                        "leading_sectors": "半导体、元器件、专用机械",
                    },
                ],
            },
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.new_high_feedback",
                    "status": "success",
                    "details": {
                        "provider": "tushare.stk_factor_pro.topdays",
                        "new_high_count": 169,
                        "trend_row_count": 3,
                    },
                },
            ],
        })

        preflight = build_report_preflight(data, "2026-05-20")
        lines = render_report_preflight_lines(preflight)
        rendered = "\n".join(lines)

        self.assertIn("创新高趋势反馈: 成功", rendered)
        self.assertIn("记录数=3", rendered)
        self.assertIn("创新高近25个交易日:", rendered)
        self.assertIn("2026-05-18 132 2.64% +19 元器件、半导体、化工原料", rendered)
        self.assertIn("2026-05-20 169 3.38% +5 半导体、元器件、专用机械", rendered)

    def test_report_preflight_lists_incomplete_new_high_identity_fields(self):
        data = _complete_report_facts({
            "data_status": {"创新高趋势反馈": True},
            "step_status": {"创新高趋势反馈获取": True},
            "new_high_feedback": {
                "available": True,
                "source": "storage.stock_daily_quotes_recent.high_break",
                "new_high_count": 1,
                "top_stocks": [
                    {"code": "600664", "name": "600664", "sector": "待补充板块"},
                ],
                "trend_rows": [
                    {"trade_date": "2026-08-12", "new_high_count": 1, "leading_sectors": "待补充板块"},
                ],
            },
            "module_logs": [
                {
                    "step": "request.new_high_feedback",
                    "status": "success",
                    "details": {"provider": "storage.stock_daily_quotes_recent.high_break"},
                }
            ],
        })

        preflight = build_report_preflight(data, "2026-08-12")
        rendered = "\n".join(render_report_preflight_lines(preflight))

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("创新高趋势反馈", preflight["failures"])
        self.assertIn("600664 缺名称、所属板块", rendered)

    def test_report_preflight_fails_when_top50_turnover_share_trend_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "Top50成交额占比趋势": False,
            },
            "step_status": {"Top50成交额占比趋势获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "top50_turnover_share_series": {"rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.top50_turnover_share_series",
                    "status": "degraded",
                    "details": {"provider": "storage.turnover_rank_daily", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("Top50成交额占比趋势", preflight["failures"])

    def test_report_preflight_fails_when_margin_pressure_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "融资承接压力": False,
            },
            "step_status": {"融资承接压力获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "margin_pressure": {"available": False, "rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.margin_pressure",
                    "status": "degraded",
                    "details": {"provider": "tushare.margin+tushare.index_daily.market_amount", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("融资承接压力", preflight["failures"])

    def test_report_preflight_fails_when_etf_turnover_series_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "ETF两市成交额趋势": False,
            },
            "step_status": {"ETF两市成交额趋势获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "etf_turnover_series": {"available": False, "rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.etf_turnover_series",
                    "status": "degraded",
                    "details": {"provider": "sina.etf.daily_amount", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("ETF两市成交额趋势", preflight["failures"])

    def test_report_preflight_fails_when_etf_turnover_series_has_coverage_anomaly(self):
        data = _complete_report_facts(
            {
                "data_status": {"ETF两市成交额趋势": True},
                "step_status": {"ETF两市成交额趋势获取": True},
                "etf_turnover_series": {
                    "available": True,
                    "coverage_anomaly": True,
                    "coverage_status": "partial",
                    "coverage_anomaly_reason": "目标日有成交ETF数520只，样本覆盖不足",
                    "rows": [{"trade_date": "2026-06-11", "etf_turnover_yi": 665.8}],
                },
                "module_logs": [
                    {
                        "step": "request.etf_turnover_series",
                        "status": "success",
                        "details": {"provider": "sina.etf.daily_amount", "row_count": 25},
                    },
                ],
            }
        )

        preflight = build_report_preflight(data, "2026-06-11")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("ETF两市成交额趋势", preflight["failures"])

    def test_report_preflight_fails_when_etf_turnover_series_stops_before_target(self):
        data = _complete_report_facts(
            {
                "data_status": {"ETF两市成交额趋势": True},
                "step_status": {"ETF两市成交额趋势获取": True},
                "etf_turnover_series": {
                    "available": True,
                    "coverage_anomaly": False,
                    "coverage_status": "normal",
                    "rows": [{"trade_date": "2026-07-24", "etf_turnover_yi": 4484.9}],
                },
                "module_logs": [
                    {
                        "step": "request.etf_turnover_series",
                        "status": "success",
                        "details": {"provider": "sina.etf.daily_amount", "row_count": 25},
                    },
                ],
            }
        )

        preflight = build_report_preflight(data, "2026-07-27")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("ETF两市成交额趋势", preflight["failures"])
        etf_check = next(
            check
            for check in preflight["decision_checks"]
            if check.get("payload_key") == "etf_turnover_series"
        )
        self.assertIn("目标日 2026-07-27", etf_check["note"])
        self.assertIn("最后事实日 2026-07-24", etf_check["note"])
        self.assertIn("最后事实日 2026-07-24", "\n".join(render_report_preflight_lines(preflight)))

    def test_report_preflight_accepts_exact_date_etf_turnover_series(self):
        data = _complete_report_facts(
            {
                "data_status": {"ETF两市成交额趋势": True},
                "step_status": {"ETF两市成交额趋势获取": True},
                "etf_turnover_series": {
                    "available": True,
                    "latest_data_date": "2026-06-11",
                    "is_stale_for_target": False,
                    "coverage_anomaly": False,
                    "coverage_status": "normal",
                    "rows": [{"trade_date": "2026-06-11", "etf_turnover_yi": 4484.9}],
                },
                "module_logs": [
                    {
                        "step": "request.etf_turnover_series",
                        "status": "success",
                        "details": {"provider": "sina.etf.daily_amount", "row_count": 25},
                    },
                ],
            }
        )

        preflight = build_report_preflight(data, "2026-06-11")

        self.assertEqual(preflight["status"], "success")
        self.assertNotIn("ETF两市成交额趋势", preflight["failures"])

    def test_report_preflight_rejects_etf_turnover_series_with_future_rows(self):
        data = _complete_report_facts(
            {
                "data_status": {"ETF两市成交额趋势": True},
                "step_status": {"ETF两市成交额趋势获取": True},
                "etf_turnover_series": {
                    "available": True,
                    "coverage_anomaly": False,
                    "coverage_status": "normal",
                    "rows": [
                        {"trade_date": "2026-07-29", "etf_turnover_yi": 4484.9},
                        {"trade_date": "2026-07-30", "etf_turnover_yi": 4588.1},
                    ],
                },
                "module_logs": [
                    {
                        "step": "request.etf_turnover_series",
                        "status": "success",
                        "details": {"provider": "sina.etf.daily_amount", "row_count": 2},
                    },
                ],
            }
        )

        preflight = build_report_preflight(data, "2026-07-29")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("ETF两市成交额趋势", preflight["failures"])
        etf_check = next(
            check
            for check in preflight["decision_checks"]
            if check.get("payload_key") == "etf_turnover_series"
        )
        self.assertIn("未来事实日 2026-07-30", etf_check["note"])

    def test_report_preflight_rejects_invalid_etf_turnover_dates(self):
        data = _complete_report_facts(
            {
                "data_status": {"ETF两市成交额趋势": True},
                "step_status": {"ETF两市成交额趋势获取": True},
                "etf_turnover_series": {
                    "available": True,
                    "coverage_anomaly": False,
                    "coverage_status": "normal",
                    "rows": [
                        {"trade_date": "2026-07-29", "etf_turnover_yi": 4484.9},
                        {"trade_date": "2026-02-30", "etf_turnover_yi": 9999.0},
                    ],
                },
                "module_logs": [
                    {
                        "step": "request.etf_turnover_series",
                        "status": "success",
                        "details": {"provider": "sina.etf.daily_amount", "row_count": 2},
                    },
                ],
            }
        )

        preflight = build_report_preflight(data, "2026-07-29")

        self.assertEqual(preflight["status"], "failed")
        etf_check = next(
            check
            for check in preflight["decision_checks"]
            if check.get("payload_key") == "etf_turnover_series"
        )
        self.assertIn("无效事实日期", etf_check["note"])
        self.assertIn("2026-02-30", etf_check["note"])

    def test_report_preflight_fails_when_lhb_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "step_status": {"龙虎榜数据获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "lhb_data_status": "upstream_empty",
            "lhb_analysis": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.lhb_snapshot",
                    "status": "degraded",
                    "details": {"provider": "legacy.lhb_snapshot", "lhb_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("龙虎榜数据", preflight["failures"])

    def test_report_preflight_fails_when_concept_fund_flow_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "概念资金流向": False,
            },
            "step_status": {"概念资金流向获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "concept_fund_flow": {"rows": [], "inflow": [], "outflow": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.concept_fund_flow",
                    "status": "degraded",
                    "details": {"provider": "tushare.ths_member+tushare.moneyflow", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-21")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("概念资金流向", preflight["failures"])

    def test_report_preflight_fails_when_xueqiu_hot_rank_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "雪球A股24小时热榜": False,
            },
            "step_status": {"雪球A股24小时热榜获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "xueqiu_hot_rank_top100": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.xueqiu_hot_rank",
                    "status": "error",
                    "details": {
                        "provider": "xueqiu.hot_stock.type22",
                        "row_count": 0,
                        "error": "雪球登录态失效或缺失，关键数据不完整，停止生成",
                    },
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("雪球A股24小时热榜", preflight["failures"])

    def test_report_preflight_fails_when_xueqiu_ai_argument_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "雪球热榜AI解释": False,
            },
            "step_status": {"雪球热榜AI解释获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "xueqiu_hot_stock_arguments": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.xueqiu_hot_stock_arguments",
                    "status": "error",
                    "details": {
                        "provider": "xueqiu.hot_stock.argument",
                        "row_count": 0,
                        "error": "雪球接口返回空，关键数据不完整，停止生成",
                    },
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("雪球热榜AI解释", preflight["failures"])

    def test_report_preflight_fails_when_any_registered_factor_status_failed(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "价格带风格趋势": False,
            },
            "step_status": {"价格带风格趋势获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "price_band_style_series": {"rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.price_band_style_series",
                    "status": "degraded",
                    "details": {"provider": "tushare.ths_daily.price_band_style", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("价格带风格趋势", preflight["failures"])

    def test_report_preflight_accepts_lhb_rank_rows_when_analysis_table_is_empty(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "step_status": {"龙虎榜数据获取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "lhb_analysis": [],
            "lhb_net_buy_top10": [{"code": "000001", "name": "军工一号"}],
            "lhb_net_sell_top10": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.lhb_snapshot",
                    "status": "success",
                    "details": {
                        "provider": "tushare.top_list",
                        "source_record_count": 85,
                        "lhb_count": 76,
                        "buy_count": 1,
                    },
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertNotIn("龙虎榜数据", preflight["failures"])
        lhb_check = next(check for check in preflight["decision_checks"] if check["label"] == "龙虎榜数据")
        self.assertEqual(lhb_check["row_count"], 85)
        self.assertEqual(lhb_check["note"], "原始85条 / 归并76只 / 净买排行1只")
        self.assertIn(
            "| 龙虎榜数据 | 成功 | tushare.top_list | 85 | 是 | 原始85条 / 归并76只 / 净买排行1只 |",
            build_run_log_text(preflight, "2026-05-19"),
        )

    def test_report_preflight_reads_persisted_lhb_counts_without_request_logs(self):
        data = _complete_report_facts(
            {
                "data_status": {"龙虎榜数据": True},
                "postgres_only": True,
                "lhb_analysis": [],
                "lhb_net_buy_top10": [
                    {"code": "000001", "name": "军工一号", "data_source": "tushare.top_list"}
                ],
                "lhb_net_sell_top10": [{"code": "000002", "name": "军工二号"}],
                "lhb_source_record_count": 85,
                "lhb_grouped_record_count": 76,
                "lhb_provider": "tushare.top_list",
                "lhb_data_status": "available",
            }
        )

        preflight = build_report_preflight(data, "2026-07-28")

        lhb_check = next(check for check in preflight["decision_checks"] if check["label"] == "龙虎榜数据")
        self.assertEqual(lhb_check["status"], "success")
        self.assertEqual(lhb_check["provider"], "tushare.top_list")
        self.assertEqual(lhb_check["row_count"], 85)
        self.assertTrue(lhb_check["step_status"])
        self.assertEqual(
            lhb_check["note"],
            "原始85条 / 归并76只 / 净买排行1只 / 净卖排行1只",
        )
        self.assertIn(
            "| 龙虎榜数据 | 成功 | tushare.top_list | 85 | 是 | 原始85条 / 归并76只 / 净买排行1只 / 净卖排行1只 |",
            build_run_log_text(preflight, "2026-07-28"),
        )

    def test_report_preflight_does_not_add_lhb_buy_and_sell_rank_counts(self):
        data = _complete_report_facts(
            {
                "data_status": {"龙虎榜数据": True},
                "lhb_analysis": [],
                "lhb_net_buy_top10": [{"code": "000001"}, {"code": "000002"}],
                "lhb_net_sell_top10": [{"code": "000003"}],
                "lhb_source_record_count": 0,
                "lhb_grouped_record_count": 0,
                "lhb_provider": "tushare.top_list",
                "lhb_data_status": "available",
                "module_logs": [
                    {
                        "step": "request.lhb_snapshot",
                        "status": "success",
                        "details": {
                            "provider": "tushare.top_list",
                            "source_record_count": 0,
                            "lhb_count": 0,
                            "buy_count": 0,
                            "sell_count": 0,
                        },
                    }
                ],
            }
        )

        preflight = build_report_preflight(data, "2026-07-28")

        lhb_check = next(check for check in preflight["decision_checks"] if check["label"] == "龙虎榜数据")
        self.assertEqual(lhb_check["row_count"], 2)
        self.assertEqual(lhb_check["note"], "净买排行2只 / 净卖排行1只")

    def test_report_preflight_fails_when_resonance_factor_not_computed(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "zt_pool": [{"code": "000001"}],
            "sector_fund_flow": {"inflow": [{"name": "机器人"}]},
            "stocks_with_history": [{"code": "000001", "turnover": 80.0}],
            "resonance_scores": {},
            "trade_signals": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "infer.quant_signals",
                    "status": "success",
                    "details": {"volume_anomaly_count": 2, "lhb_count": 0, "resonance_count": 0, "signal_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("板块共振结果", preflight["failures"])

    def test_report_preflight_allows_computed_empty_resonance_result(self):
        data = _complete_report_facts(
            {
                "zt_pool": [{"code": "000001"}],
                "sector_fund_flow": {"inflow": [{"name": "机器人"}]},
                "stocks_with_history": [{"code": "000001", "turnover": 80.0}],
                "resonance_scores": {},
                "trade_signals": [],
            }
        )
        data["module_logs"].append(
            {
                "step": "infer.quant_signals",
                "status": "success",
                "details": {
                    "volume_anomaly_count": 2,
                    "lhb_count": 0,
                    "resonance_count": 0,
                    "resonance_input_count": 1,
                    "resonance_computed": True,
                    "signal_count": 0,
                },
            }
        )

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertNotIn("板块共振结果", preflight["failures"])

    def test_build_report_outputs_emits_preflight_by_default_before_abort(self):
        data = {
            "data_status": {"两市成交额": False},
            "total_turnover": 0.0,
        }

        stdout = io.StringIO()
        with patch("daily_report_render._render_report_with_display_mode"):
            with redirect_stdout(stdout):
                with self.assertRaises(ReportCriticalDataMissingError):
                    build_report_outputs(data, "2026-05-13")

        output = stdout.getvalue()
        self.assertIn("关键数据检查: 失败 / 2026-05-13", output)
        self.assertIn("两市成交额: 失败", output)

    def test_report_preflight_renders_critical_fields_with_provider_and_row_count(self):
        data = _complete_report_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "change_pct": 1.2, "data_source": "tushare.index_daily"},
            "csi1000_index": {"price": 6123.45, "change_pct": 1.1, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"} for _ in range(50)],
            "module_logs": [
                {
                    "step": "request.total_turnover",
                    "status": "success",
                    "details": {"provider": "tushare.daily", "total_turnover": 12345.67},
                },
                {
                    "step": "request.wind_a",
                    "status": "success",
                    "details": {"provider": "tushare.index_daily", "price": 6686.86},
                },
                {
                    "step": "request.csi1000",
                    "status": "success",
                    "details": {"provider": "tushare.index_daily", "price": 6123.45},
                },
                {
                    "step": "request.turnover_rank",
                    "status": "success",
                    "details": {"provider": "tushare.daily", "row_count": 50},
                },
            ],
        })

        preflight = build_report_preflight(data, "2026-05-13")
        lines = render_report_preflight_lines(preflight)

        self.assertEqual(preflight["status"], "success")
        self.assertIn("关键数据检查: 成功", lines[0])
        self.assertTrue(any("两市成交额" in line and "tushare.daily" in line and "12345.67" in line for line in lines))
        self.assertTrue(any("中证全指" in line and "tushare.index_daily" in line and "6686.86" in line for line in lines))
        self.assertTrue(any("中证1000" in line and "tushare.index_daily" in line and "6123.45" in line for line in lines))
        self.assertTrue(any("成交额排名" in line and "tushare.daily" in line and "50" in line for line in lines))

    def test_decision_preflight_counts_xuangubao_plates_when_news_count_is_zero(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [{"name": "国产芯片"}, {"name": "光通信"}],
            },
            "module_logs": [
                {
                    "step": "request.xuangubao",
                    "status": "success",
                    "details": {"provider": "xuangubao.fetch_xuangubao_data", "news_count": 0, "plate_count": 2},
                }
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        xgb_check = next(check for check in preflight["decision_checks"] if check["label"] == "选股通盘中异动")
        self.assertEqual(xgb_check["row_count"], 2)

    def test_decision_preflight_counts_xuangubao_limit_up_reasons(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [],
                "xuangubao_limit_up_reasons": [{"name": "交运股份"}],
            },
            "module_logs": [
                {
                    "step": "request.xuangubao",
                    "status": "success",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 0,
                        "plate_count": 0,
                        "limit_up_reason_count": 1,
                    },
                }
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        xgb_check = next(check for check in preflight["decision_checks"] if check["label"] == "选股通盘中异动")
        self.assertEqual(xgb_check["row_count"], 1)

    def test_decision_preflight_accepts_postgres_xuangubao_summary_counts(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "postgres_only": True,
            "xuangubao_data": {
                "news_count": 0,
                "plate_count": 1,
                "limit_up_reason_count": 0,
                "diagnostics_status": "success",
            },
        }

        preflight = build_report_preflight(data, "2026-05-29")

        xgb_check = next(check for check in preflight["decision_checks"] if check["label"] == "选股通盘中异动")
        self.assertEqual(xgb_check["status"], "success")
        self.assertEqual(xgb_check["row_count"], 1)
        self.assertNotIn("选股通盘中异动", preflight["failures"])

    def test_decision_preflight_shows_xuangubao_breakdown_for_postgres_counts(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "postgres_only": True,
            "xuangubao_data": {
                "news_count": 46,
                "plate_count": 22,
                "limit_up_reason_count": 156,
            },
        }

        preflight = build_report_preflight(data, "2026-07-03")
        lines = render_report_preflight_lines(preflight)
        run_log = build_run_log_text(preflight, "2026-07-03")

        xgb_check = next(check for check in preflight["decision_checks"] if check["label"] == "选股通盘中异动")
        self.assertEqual(xgb_check["row_count"], 224)
        self.assertEqual(xgb_check["note"], "新闻46条 / 盘面22个 / 涨停解释156条")
        self.assertTrue(any("选股通盘中异动" in line and "备注=新闻46条 / 盘面22个 / 涨停解释156条" in line for line in lines))
        self.assertIn("| 选股通盘中异动 | 成功 | unknown | 224 | 是 | 新闻46条 / 盘面22个 / 涨停解释156条 |", run_log)

    def test_generate_markdown_report_from_sections_deduplicates_no_trade_and_filters_draft_explanations(self):
        rendered = generate_markdown_report_from_sections(
            {
                "preamble": "⛔ 当前先不开新仓: 0%不参与，本轮不做PK出手结论。",
                "execution": "⛔ 当前先不开新仓: 0%不参与，本轮不做PK出手结论。\n为什么要看这块：这是草稿解释。\n结论：空仓等待。",
            }
        )

        self.assertEqual(rendered.count("当前先不开新仓"), 1)
        self.assertIn("结论：空仓等待。", rendered)
        self.assertNotIn("为什么要看这块", rendered)
        self.assertNotIn("草稿解释", rendered)

    def test_generate_markdown_report_from_sections_keeps_expected_order(self):
        rendered = generate_markdown_report_from_sections(
            {
                "preamble": "# Preamble",
                "environment": "",
                "observation": "## Observation",
                "execution": "## Execution",
                "review": "## Review",
                "summary": "## Summary",
            },
            llm_wiki_context={
                "daily_discipline_lines": ["只展示调用方已提供的冻结交易原则。"]
            },
        )

        self.assertEqual(
            rendered,
            "# Preamble\n\n## Observation\n\n## Execution\n\n## Review\n\n### 交易原则\n"
            "- 只展示调用方已提供的冻结交易原则。\n\n"
            "## Summary",
        )
        self.assertEqual(rendered.count("只展示调用方已提供的冻结交易原则"), 1)

    def test_generate_markdown_report_from_sections_handles_none(self):
        self.assertEqual(generate_markdown_report_from_sections(None), "")

    def test_generate_markdown_report_from_sections_does_not_duplicate_daily_discipline(self):
        rendered = generate_markdown_report_from_sections(
            {
                "review": "## Review\n\n### 交易原则\n- 去弱留强是短线执行表达：卖旧仓看旧仓资格，买新仓看新仓资格；不能用FOMO把两笔判断合成一次满仓替换。",
            }
        )

        self.assertEqual(rendered.count("去弱留强是短线执行表达"), 1)

    def test_generate_markdown_report_uses_legacy_path_when_sections_are_absent(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.generate_markdown_report = lambda *args, **kwargs: "legacy report"

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = generate_markdown_report({"foo": "bar"}, "2026-04-21")

        self.assertEqual(rendered, "legacy report")

    def test_generate_markdown_report_forwards_candidate_trace_config(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        captured = {}

        def _fake_generate_markdown_report(*args, **kwargs):
            captured.update(kwargs)
            return "legacy report"

        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = generate_markdown_report(
                {"foo": "bar"},
                "2026-04-21",
                persist_candidate_traces=True,
                candidate_trace_root_dir="/tmp/candidate-trace-root",
            )

        self.assertEqual(rendered, "legacy report")
        self.assertTrue(captured["persist_candidate_traces"])
        self.assertEqual(captured["candidate_trace_root_dir"], "/tmp/candidate-trace-root")

    def test_generate_markdown_report_forwards_decision_ledger_config(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        captured = {}

        def _fake_generate_markdown_report(*args, **kwargs):
            captured.update(kwargs)
            return "legacy report"

        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = generate_markdown_report(
                {"foo": "bar"},
                "2026-04-21",
                persist_decision_ledger=True,
            )

        self.assertEqual(rendered, "legacy report")
        self.assertTrue(captured["persist_decision_ledger"])

    def test_generate_markdown_report_prefers_sections_path_when_sections_exist(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.generate_markdown_report = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy path should not run")
        )

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = generate_markdown_report(
                {
                    "sections": {
                        "preamble": "# Preamble",
                        "summary": "## Summary",
                    },
                    "knowledge": {
                        "llm_wiki": {
                            "daily_discipline_lines": ["只展示已冻结的交易原则。"]
                        }
                    },
                },
                "2026-04-21",
            )

        self.assertIn("# Preamble", rendered)
        self.assertIn("### 交易原则", rendered)
        self.assertIn("## Summary", rendered)
        self.assertEqual(rendered.count("只展示已冻结的交易原则"), 1)

    def test_generate_markdown_report_replay_sections_do_not_read_current_wiki(self):
        rendered = generate_markdown_report(
            {
                "sections": {
                    "preamble": "# Preamble",
                    "summary": "## Summary",
                }
            },
            "2026-04-21",
            run_mode=LEDGER_MODE_REPLAY,
        )

        self.assertNotIn("### 交易原则", rendered)
