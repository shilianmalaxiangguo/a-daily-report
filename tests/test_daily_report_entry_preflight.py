import os
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _with_html_required_facts(data):
    data = dict(data)
    data.setdefault("top50_turnover_share_pct", 19.0)
    data.setdefault("csi500_index", {"price": 6262.0, "data_source": "tushare.index_daily"})
    data.setdefault("csi1000_index", {"price": 8408.73, "data_source": "tushare.index_daily"})
    data.setdefault("hot_rank_top50", [{"code": f"{index:06d}"} for index in range(50)])
    data.setdefault("hot_rank_sample_size", 50)
    data.setdefault("hot_rank_sample_target", 50)
    data.setdefault("mainline_context", {"confirmed_line": "电力", "attack_evidence": ["净流入居前"]})
    snapshot = dict(data.get("market_research_snapshot") or {})
    snapshot.setdefault(
        "front_page_final_gate",
        {
            "final_action": "0%不参与",
            "max_position": "0%",
            "allow_new_entry": False,
        },
    )
    data["market_research_snapshot"] = snapshot
    return data


class DailyReportEntryPreflightTest(unittest.TestCase):
    def test_chanlun_tomorrow_decision_follows_zero_position_report_summary(self):
        import daily_report_entry_demo

        decision = daily_report_entry_demo._align_chanlun_tomorrow_decision_with_report(
            {
                "final_action": "50%条件执行只围绕主线核心",
                "can_new_entry": True,
                "target_position_pct": 50,
            },
            "\n".join(
                [
                    "# 2026-06-22 a股市场分析",
                    "| 仓位姿态 | 0%不参与 |",
                    "| 最终对象 | 无 |",
                    "| 明日执行对象 | 无 |",
                    "> **最终动作**：0%不参与；最终没有新增参与对象",
                ]
            ),
        )

        self.assertEqual(decision["final_action"], "0%不参与；不新增参与")
        self.assertFalse(decision["can_new_entry"])
        self.assertEqual(decision["target_position_pct"], 0)

    def test_report_preflight_fails_when_core_fields_are_untracked_or_missing(self):
        from daily_report_render import build_report_preflight

        data = {
            "data_status": {"两市成交额": True},
            "total_turnover": 28234.29,
        }

        preflight = build_report_preflight(data, "2026-06-08")
        checks = {item["label"]: item for item in preflight["checks"]}

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("中证全指", preflight["failures"])
        self.assertIn("中证1000", preflight["failures"])
        self.assertIn("成交额排名", preflight["failures"])
        self.assertIn("大盘涨跌统计", preflight["failures"])
        self.assertIn("热度前50个股", preflight["failures"])
        self.assertEqual(checks["中证全指"]["status"], "failed")
        self.assertEqual(checks["中证1000"]["status"], "failed")
        self.assertEqual(checks["成交额排名"]["status"], "failed")
        self.assertEqual(checks["大盘涨跌统计"]["status"], "failed")
        self.assertEqual(checks["热度前50个股"]["status"], "failed")

    def test_report_preflight_rejects_empty_hot_rank_even_when_sample_size_claims_complete(self):
        from daily_report_render import build_report_preflight

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "csi1000_index": {"price": 8408.73, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "hot_rank_top50": [],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
        })

        preflight = build_report_preflight(data, "2026-06-08")
        checks = {item["label"]: item for item in preflight["checks"]}

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("热度前50个股", preflight["failures"])
        self.assertEqual(checks["热度前50个股"]["status"], "failed")

    def test_sector_first_missing_inputs_stop_generation_and_list_missing_items(self):
        from daily_report_render import (
            ReportCriticalDataMissingError,
            _raise_if_critical_data_missing,
            build_report_preflight,
            render_report_preflight_lines,
        )

        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "derivation_contract": "sector_first_strict.v1",
            },
            "market_research_snapshot": {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "derivation_contract": "sector_first_strict.v1",
                }
            },
        }

        preflight = build_report_preflight(data, "2026-06-08")
        lines = render_report_preflight_lines(preflight)

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("市场输入", preflight["failures"])
        self.assertIn("板块发酵输入", preflight["failures"])
        self.assertIn("龙头确认输入", preflight["failures"])
        self.assertTrue(any("关键数据不完整，停止生成" in line for line in lines))

        with self.assertRaises(ReportCriticalDataMissingError) as ctx:
            _raise_if_critical_data_missing(data, "2026-06-08", preflight=preflight)

        message = str(ctx.exception)
        self.assertIn("关键数据不完整，停止生成", message)
        self.assertIn("市场输入", message)
        self.assertIn("板块发酵输入", message)

    def test_sector_first_zero_final_with_persisted_chain_passes_preflight(self):
        from daily_report_render import build_report_preflight

        selection_workflow = {
            "schema_version": "selection_workflow.v1",
            "derivation_contract": "sector_first_strict.v1",
            "nodes": [
                {"id": "N1", "label": "市场氛围", "summary": "市场分歧，允许继续看板块"},
                {"id": "N3", "label": "板块发酵", "summary": "半导体有资金表态，但承接未完成"},
                {"id": "N7", "label": "价格行为", "summary": "价格未形成买入资格"},
            ],
            "candidate_pool": [
                {
                    "stock": {"code": "002971", "name": "和远气体", "sector": "化学制品"},
                    "status": "过程候选",
                    "observation_layer": "process_observation",
                }
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action": "0%不参与",
            },
        }
        final_target_resolution = {
            "schema_version": "final_target_resolution.v1",
            "capital_priority_decision": {
                "capital_priority": "wait",
                "reason": "价格行为和账户执行条件未满足",
            },
            "final_action": {
                "position_pct": 0,
                "action": "0%不参与",
            },
        }
        position_decision = {
            "target_position_pct": 0,
            "participation_mode": "observe_0",
        }
        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": True,
            },
            "total_turnover": 28234.29,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "csi1000_index": {"price": 8408.73, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "market_state_snapshot": {"breadth": "分歧"},
            "current_sector_turnover_snapshot": {"sector_name": "半导体", "turnover_share_pct": 6.4},
            "selection_workflow": selection_workflow,
            "final_target_resolution": final_target_resolution,
            "position_decision": position_decision,
            "execution_stage_context": {
                "selection_workflow": selection_workflow,
                "final_target_resolution": final_target_resolution,
                "position_decision": position_decision,
            },
            "market_research_snapshot": {
                "selection_workflow": selection_workflow,
                "final_target_resolution": final_target_resolution,
                "position_decision": position_decision,
                "front_page_final_gate": {
                    "final_action": "0%不参与",
                    "max_position": "0%",
                    "allow_new_entry": False,
                },
            },
        })

        preflight = build_report_preflight(data, "2026-06-11")
        sector_checks = {
            item["label"]: item
            for item in preflight["checks"]
            if item.get("provider") == "sector_first_strict.v1"
        }

        self.assertEqual(preflight["status"], "success")
        self.assertEqual(preflight["failures"], [])
        self.assertEqual(sector_checks["龙头确认输入"]["status"], "success")
        self.assertEqual(sector_checks["价格行为输入"]["status"], "success")
        self.assertEqual(data["selection_workflow"]["final"]["execution_object"], {})

    def test_legacy_entry_extreme_conviction_wrapper_preserves_risk_context(self):
        import daily_report_entry_demo

        captured = {}

        def capture_build(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None, helpers=None):
            captured["risk_context"] = risk_context
            return []

        risk_context = {
            "systemic_risk_warnings": [
                {
                    "risk_source": "st_resume_experience",
                    "risk_level": "high",
                    "reason": "突发ST复牌经验风险",
                }
            ]
        }

        with patch.object(daily_report_entry_demo, "run_build_extreme_conviction_list", side_effect=capture_build):
            daily_report_entry_demo.build_extreme_conviction_list(
                [{"name": "风险样本", "code": "000001"}],
                "机器人",
                sector_snapshot=[],
                top_n=3,
                risk_context=risk_context,
            )

        self.assertIs(captured["risk_context"], risk_context)

    def test_concept_fund_flow_snapshot_helper_returns_saved_rows(self):
        import daily_report_entry_demo

        snapshot_data = {
            "concept_fund_flow": {
                "rows": [{"name": "PCB概念", "net_inflow": 12.3}],
                "inflow": [{"name": "PCB概念", "net_inflow": 12.3}],
                "provider": "tushare.ths_member+tushare.moneyflow",
            }
        }

        with patch.object(daily_report_entry_demo, "load_data_snapshot", return_value=(snapshot_data, "")):
            result = daily_report_entry_demo.get_concept_fund_flow_from_snapshot("2026-05-26")

        self.assertEqual(result["rows"][0]["name"], "PCB概念")
        self.assertEqual(result["provider"], "tushare.ths_member+tushare.moneyflow")

    def test_main_aborts_before_snapshot_and_public_publish_when_critical_data_missing_even_without_report(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        bad_data = {
            "data_status": {
                "两市成交额": False,
                "中证全指": False,
                "成交额排名": False,
            },
            "total_turnover": 0,
            "wind_a_alternative": {"price": 0},
            "turnover_rank": [],
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-13", "--no-report"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=bad_data), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as save_snapshot_mock:
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        save_snapshot_mock.assert_not_called()

    def test_main_aborts_before_snapshot_when_xueqiu_factor_failed_even_without_report(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        bad_data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
                "雪球A股24小时热榜": False,
            },
            "step_status": {"雪球A股24小时热榜获取": False},
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "xueqiu_hot_rank_top100": [],
            "module_logs": [
                {
                    "step": "request.xueqiu_hot_rank",
                    "status": "error",
                    "details": {
                        "provider": "xueqiu.hot_stock.type22",
                        "row_count": 0,
                        "error": "雪球登录态失效或缺失，关键数据不完整，停止生成",
                    },
                }
            ],
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-22", "--no-report"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=bad_data), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as save_snapshot_mock:
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        save_snapshot_mock.assert_not_called()

    def test_main_audits_full_report_with_chanlun_html_after_generation(self):
        import daily_report_entry_demo

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "market_research_snapshot": {
                "front_page_final_gate": {
                    "final_action": "空仓等待，禁止参与",
                    "max_position": "0%",
                    "allow_new_entry": False,
                }
            },
        })
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }
        saved_paths = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "/tmp/summary.md",
        }
        html_path = Path("/tmp/chanlun.html")
        html_text = "<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-21", "--replay"]), \
             patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(data, "2026-05-21")), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value=html_text), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=html_path), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}) as audit_mock, \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"):
            daily_report_entry_demo.main()

        audit_mock.assert_called_once_with(
            report_outputs[daily_report_entry_demo.REPORT_VARIANT_FULL],
            companion_html=html_text,
        )

    def test_generated_report_audit_ignores_position_context_from_chanlun_companion(self):
        import daily_report_entry_demo

        full_report = "# full\n"
        companion_html = "<h2>明日抉择</h2><table><tr><td>T0对象</td><td>无昨日持仓，不涉及T0</td></tr></table>"
        captured = {}

        def capture_audit(markdown, companion_html=None):
            captured["markdown"] = markdown
            captured["companion_html"] = companion_html
            return {"passed": True, "findings": []}

        with patch.object(daily_report_entry_demo, "audit_report_markdown", side_effect=capture_audit):
            result = daily_report_entry_demo._audit_generated_report_with_chanlun_html(
                {daily_report_entry_demo.REPORT_VARIANT_FULL: full_report},
                companion_html=companion_html,
            )

        self.assertTrue(result["passed"])
        self.assertEqual(captured["markdown"], full_report)
        self.assertEqual(captured["companion_html"], companion_html)

    def test_main_treats_snapshot_position_context_as_existing_position(self):
        import daily_report_entry_demo

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "personal_position_context": {
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有京能电力(600578)，500股；先处理旧仓",
                }
            },
        })
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-29", "--replay"]), \
             patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(data, "2026-05-29")), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs) as build_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={}), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"):
            daily_report_entry_demo.main()

        self.assertTrue(build_mock.call_args.kwargs["has_personal_positions"])
        self.assertTrue(data["position_context_provided"])

    def test_main_does_not_save_report_when_generated_report_audit_fails(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
        })
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 涨跌比 | 0 / 0 | - | 多头仍占优 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-28", "--replay"]), \
             patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(data, "2026-05-28")), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={
                 "passed": False,
                 "findings": [{"code": "market_breadth_incomplete", "message": "关键数据不完整，停止生成"}],
             }), \
             patch.object(daily_report_entry_demo, "save_report_outputs") as save_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report") as save_html_mock, \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-05-28", "field_count": 1}):
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        save_mock.assert_not_called()
        save_html_mock.assert_not_called()

    def test_replay_snapshot_position_context_counts_as_personal_positions(self):
        import daily_report_entry_demo

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "personal_position_context": {
                "existing_position_summary": {"has_position": True}
            },
        })
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-29", "--replay"]), \
             patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(data, "2026-05-29")), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs) as build_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={}), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report"), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"):
            daily_report_entry_demo.main()

        self.assertTrue(build_mock.call_args.kwargs["has_personal_positions"])
        self.assertTrue(data["position_context_provided"])

    def test_main_postgres_only_reads_postgres_snapshot_and_skips_json_snapshot_write(self):
        import daily_report_entry_demo

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "postgresql.daily_report_facts"},
            "turnover_rank": [{"code": "000001", "data_source": "postgresql.daily_report_facts"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "hot_rank_top50": [{"code": f"{index:06d}"} for index in range(50)],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
        })
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-29", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=data) as load_mock, \
             patch.object(daily_report_entry_demo, "get_daily_data") as get_daily_mock, \
             patch.object(daily_report_entry_demo, "replay_from_snapshot") as replay_mock, \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={}), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report"), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as save_snapshot_mock, \
             patch.object(daily_report_entry_demo, "save_daily_report_data_to_postgres") as save_pg_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres") as import_pg_mock:
            daily_report_entry_demo.main()

        load_mock.assert_called_once_with("2026-05-29")
        get_daily_mock.assert_not_called()
        replay_mock.assert_not_called()
        save_snapshot_mock.assert_not_called()
        save_pg_mock.assert_not_called()
        import_pg_mock.assert_called_once()
        self.assertFalse(daily_report_entry_demo._POSTGRES_ONLY_RUNTIME)
        self.assertIsNone(os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"))

    def test_main_postgres_only_logs_total_report_runtime(self):
        import daily_report_entry_demo

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "postgresql.daily_report_facts"},
            "turnover_rank": [{"code": "000001", "data_source": "postgresql.daily_report_facts"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "hot_rank_top50": [{"code": f"{index:06d}"} for index in range(50)],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
        })
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            run_log_path = Path(tmpdir) / "run-log.md"
            run_log_path.write_text("# log\n", encoding="utf-8")
            saved_paths = {
                daily_report_entry_demo.REPORT_VARIANT_FULL: str(Path(tmpdir) / "full.md"),
                "run_log": str(run_log_path),
            }
            stdout = io.StringIO()

            with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-29", "--postgres-only"]), \
                 patch.object(sys, "stdout", stdout), \
                 patch.object(daily_report_entry_demo.time, "perf_counter", side_effect=[100.0, 112.345]), \
                 patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=data), \
                 patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
                 patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
                 patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs), \
                 patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"), \
                 patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths), \
                 patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report"), \
                 patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
                 patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-05-29", "field_count": 1}):
                daily_report_entry_demo.main()

            output = stdout.getvalue()
            self.assertIn("日报生成总耗时: 12.35 秒", output)
            self.assertIn("数据路径: PostgreSQL-only", output)
            run_log_text = run_log_path.read_text(encoding="utf-8")
            self.assertIn("## 耗时统计", run_log_text)
            self.assertIn("| 项目 | 值 |\n|------|------|\n| 开始到完成 | 12.35 秒 |", run_log_text)
            self.assertIn("| 开始到完成 | 12.35 秒 |", run_log_text)
            self.assertIn("| 数据路径 | PostgreSQL-only |", run_log_text)

    def test_main_postgres_only_rejects_replay_mode(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-29", "--postgres-only", "--replay"]):
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                daily_report_entry_demo.main()

        self.assertIn("PostgreSQL-only", str(error.exception))

    def test_build_sh_index_chanlun_html_for_audit_uses_postgres_structured_loaders_in_postgres_only_runtime(self):
        import daily_report_entry_demo

        captured = {}

        class FakeService:
            def query_index_daily_bars(self, index_code, target_date, *, window_days=250):
                captured["daily_query"] = (index_code, target_date, window_days)
                return [
                    {
                        "date": f"2026-01-{(index % 28) + 1:02d}",
                        "open": 1.0,
                        "high": 2.0,
                        "low": 0.5,
                        "close": 1.5,
                        "volume": 100.0,
                        "data_source": "postgresql.index_daily_bars",
                    }
                    for index in range(window_days)
                ]

            def query_index_minute_bars(self, index_code, target_date, period="60"):
                captured["minute_query"] = (index_code, target_date, period)
                return []

        def fake_runner(target_date, index_code, **kwargs):
            captured["kwargs"] = kwargs
            daily_loader = kwargs.get("sse_loader")
            self.assertTrue(callable(daily_loader))
            loaded = daily_loader(index_code, target_date, 250)
            captured["daily_loader"] = loaded
            fetch_minute_bars = kwargs.get("fetch_minute_bars")
            captured["fetch_minute_bars"] = fetch_minute_bars
            payload = fetch_minute_bars(index_code=index_code, period="60", target_date=target_date)
            captured["minute_payload"] = payload
            return {"success": True, "signal": {}}, []

        with patch.object(daily_report_entry_demo, "_POSTGRES_ONLY_RUNTIME", True), \
             patch.object(daily_report_entry_demo, "_postgres_index_bar_service", return_value=FakeService()):
            html = daily_report_entry_demo._build_sh_index_chanlun_html_for_audit(
                "2026-05-29",
                runner=fake_runner,
            )

        self.assertIn("<!doctype html>", html.lower())
        self.assertTrue(callable(captured["kwargs"]["fetch_minute_bars"]))
        self.assertFalse(captured["kwargs"].get("allow_live_fallback", True))
        self.assertEqual(captured["daily_loader"][1], "postgresql.index_daily_bars")
        self.assertFalse(captured["minute_payload"]["success"])
        self.assertEqual(captured["minute_payload"]["source"], "postgresql.index_minute_bars")

    def test_build_sh_index_chanlun_html_for_audit_does_not_retry_without_postgres_only_minute_guard(self):
        import daily_report_entry_demo

        captured = {"unguarded_retry": 0}

        def fake_runner(target_date, index_code, **kwargs):
            if not kwargs:
                captured["unguarded_retry"] += 1
                return {"success": True, "signal": {}}, []
            raise TypeError("internal runner error")

        with patch.object(daily_report_entry_demo, "_POSTGRES_ONLY_RUNTIME", True):
            with self.assertRaisesRegex(TypeError, "internal runner error"):
                daily_report_entry_demo._build_sh_index_chanlun_html_for_audit(
                    "2026-05-29",
                    runner=fake_runner,
                )

        self.assertEqual(captured["unguarded_retry"], 0)

    def test_build_sh_index_chanlun_html_for_audit_rejects_missing_postgres_daily_bars(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        def missing_runner(target_date, index_code, **kwargs):
            self.assertFalse(kwargs.get("allow_live_fallback", True))
            return {
                "success": False,
                "error": "PostgreSQL指数日K不足，停止缠论HTML生成",
                "data_source": "postgresql.index_daily_bars",
            }, []

        with patch.object(daily_report_entry_demo, "_POSTGRES_ONLY_RUNTIME", True):
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo._build_sh_index_chanlun_html_for_audit(
                    "2026-05-29",
                    runner=missing_runner,
                )

    def test_market_phase_context_uses_postgres_index_bars_in_postgres_only_runtime(self):
        import daily_report_entry_demo

        captured = {}

        class FakeService:
            def is_postgres_backed(self):
                return True

            def query_index_daily_bars(self, index_code, target_date, *, window_days=250):
                captured["daily_query"] = (index_code, target_date, window_days)
                return [
                    {
                        "date": f"2026-05-{(index % 28) + 1:02d}",
                        "open": 4060.0,
                        "high": 4075.0,
                        "low": 4050.0,
                        "close": 4068.0,
                        "volume": 100.0,
                        "amount": 1200.0,
                    }
                    for index in range(250)
                ]

            def query_index_minute_bars(self, index_code, target_date, *, period="60"):
                captured["minute_query"] = (index_code, target_date, period)
                return [
                    {
                        "datetime": "2026-05-29 10:30:00",
                        "date": "2026-05-29",
                        "time": "10:30:00",
                        "open": 4060.0,
                        "high": 4070.0,
                        "low": 4055.0,
                        "close": 4066.0,
                        "volume": 10.0,
                        "amount": 20.0,
                    }
                ]

        def fake_analyze_market_zhongshu(**kwargs):
            captured["analyze_kwargs"] = kwargs
            frame, source = kwargs["fetch_dataframe"](
                index_code=kwargs["index_code"],
                recent_days=kwargs["recent_days"],
                min_zhongshu_klines=kwargs["min_zhongshu_klines"],
                target_date=kwargs["target_date"],
            )
            captured["data_source"] = source
            captured["frame_rows"] = len(frame)
            captured["minute_payload"] = kwargs["fetch_minute_bars"](
                index_code=kwargs["index_code"],
                period="60",
                target_date=kwargs["target_date"],
            )
            return {"success": True, "data_source": source}

        def fake_contract(data, target_date, *, analyze_market_zhongshu, **_kwargs):
            market_zhongshu = analyze_market_zhongshu(
                index_code="sh.000001",
                recent_days=250,
                min_zhongshu_klines=20,
                target_date=target_date,
            )
            return {"market_zhongshu": market_zhongshu, "module_logs": []}

        with patch.object(daily_report_entry_demo, "_POSTGRES_ONLY_RUNTIME", True), \
             patch.object(daily_report_entry_demo, "_postgres_index_bar_service", return_value=FakeService()), \
             patch.object(daily_report_entry_demo, "analyze_market_zhongshu", side_effect=fake_analyze_market_zhongshu), \
             patch.object(daily_report_entry_demo, "build_market_phase_context_contract", side_effect=fake_contract):
            result = daily_report_entry_demo.build_market_phase_context({}, "2026-05-29", emit_logs=False)

        self.assertEqual(result["market_zhongshu"]["data_source"], "postgresql.index_daily_bars")
        self.assertEqual(captured["daily_query"], ("sh.000001", "2026-05-29", 250))
        self.assertEqual(captured["minute_query"], ("sh.000001", "2026-05-29", "60"))
        self.assertEqual(captured["frame_rows"], 250)
        self.assertEqual(captured["minute_payload"]["source"], "postgresql.index_minute_bars")
        self.assertIn("fetch_dataframe", captured["analyze_kwargs"])
        self.assertIn("fetch_minute_bars", captured["analyze_kwargs"])

    def test_postgres_index_bar_service_accepts_database_service_local_default(self):
        import daily_report_entry_demo

        class FakeService:
            def is_postgres_backed(self):
                return True

        class FakeDatabaseService:
            @classmethod
            def postgres(cls, database_url):
                raise AssertionError("explicit URL should not be required")

            @classmethod
            def from_environment(cls):
                return FakeService()

        with patch.object(daily_report_entry_demo, "DatabaseService", FakeDatabaseService), \
             patch.dict(os.environ, {}, clear=True):
            service = daily_report_entry_demo._postgres_index_bar_service()

        self.assertIsInstance(service, FakeService)

    def test_market_phase_context_rejects_missing_postgres_index_bars_in_postgres_only_runtime(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        class FakeService:
            def is_postgres_backed(self):
                return True

            def query_index_daily_bars(self, index_code, target_date, *, window_days=250):
                return []

        def fake_contract(data, target_date, *, analyze_market_zhongshu, **_kwargs):
            return {
                "market_zhongshu": analyze_market_zhongshu(
                    index_code="sh.000001",
                    recent_days=250,
                    min_zhongshu_klines=20,
                    target_date=target_date,
                ),
                "module_logs": [],
            }

        with patch.object(daily_report_entry_demo, "_POSTGRES_ONLY_RUNTIME", True), \
             patch.object(daily_report_entry_demo, "_postgres_index_bar_service", return_value=FakeService()), \
             patch.object(daily_report_entry_demo, "build_market_phase_context_contract", side_effect=fake_contract):
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                daily_report_entry_demo.build_market_phase_context({}, "2026-05-29", emit_logs=False)

        self.assertIn("PostgreSQL指数日K不足", str(error.exception))

    def test_postgres_only_runtime_snapshot_reader_uses_postgres_facts(self):
        import daily_report_entry_demo

        class FakeService:
            def __init__(self):
                self.loaded_dates = []

            def is_postgres_backed(self):
                return True

            def load_daily_report_snapshot(self, target_date):
                self.loaded_dates.append(target_date)
                return {
                    "source": f"postgresql://daily-report-facts/{target_date}",
                    "field_count": 1,
                    "data": {
                        "concept_fund_flow": {
                            "rows": [{"name": "电力", "net_inflow": 9.2}],
                            "provider": "postgresql.daily_report_facts",
                        }
                    },
                }

        service = FakeService()

        with patch.object(daily_report_entry_demo, "_POSTGRES_ONLY_RUNTIME", True), \
             patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=service), \
             patch.object(daily_report_entry_demo, "load_data_snapshot") as json_reader:
            result = daily_report_entry_demo.get_concept_fund_flow_from_snapshot("2026-05-29")

        json_reader.assert_not_called()
        self.assertEqual(service.loaded_dates, ["2026-05-29"])
        self.assertEqual(result["rows"][0]["name"], "电力")
        self.assertEqual(result["provider"], "postgresql.daily_report_facts")

    def test_postgres_only_load_marks_optional_broad_index_status_when_fact_exists(self):
        import daily_report_entry_demo

        class FakeService:
            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": f"postgresql://daily-report-facts/{target_date}",
                    "field_count": 6,
                    "data": {
                        "data_status": {"中证500": False, "中证1000": False},
                        "step_status": {"中证500获取": False, "中证1000获取": False},
                        "csi500_index": {
                            "price": 6262.0,
                            "change_pct": 0.9,
                            "data_source": "tushare.index_daily",
                        },
                        "csi1000_index": {
                            "price": 8408.7357,
                            "change_pct": -2.6512,
                            "data_source": "tushare.index_daily",
                        }
                    },
                }

        with patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=FakeService()):
            data = daily_report_entry_demo.load_daily_report_data_from_postgres("2026-05-29")

        self.assertTrue(data["data_status"]["中证1000"])
        self.assertTrue(data["step_status"]["中证1000获取"])
        self.assertTrue(data["data_status"]["中证500"])
        self.assertTrue(data["step_status"]["中证500获取"])
        self.assertTrue(data["postgres_only"])

    def test_postgres_only_load_restores_sector_first_runtime_packets_from_same_date_facts(self):
        import daily_report_entry_demo
        from daily_report_render import build_report_preflight

        class FakeService:
            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": f"postgresql://daily-report-facts/{target_date}",
                    "field_count": 60,
                    "target_field_count": 60,
                    "data": {
                        "data_status": {
                            "两市成交额": True,
                            "中证全指": True,
                            "中证1000": True,
                            "成交额排名": True,
                            "大盘涨跌统计": True,
                            "热度前50个股": True,
                        },
                        "total_turnover": 25749.33,
                        "wind_a_alternative": {"price": 6140.75, "data_source": "tushare.index_daily"},
                        "csi1000_index": {"price": 8159.45, "data_source": "tushare.index_daily"},
                        "turnover_rank": [{"code": "002971", "data_source": "tushare.daily"}],
                        "market_stats": {"up_count": 1370, "down_count": 4069},
                        "hot_rank_top50": [{"code": f"{index:06d}"} for index in range(50)],
                        "hot_rank_sample_size": 50,
                        "hot_rank_sample_target": 50,
                        "current_sector_turnover_snapshot": {"sector_name": "半导体", "turnover_share_pct": 6.4},
                        "mainline_turnover_summary": {"current_mainline": "半导体"},
                        "execution_stage_context": {
                            "market_state_snapshot": {"market_state": "弱分歧"},
                            "mainline_name": "半导体",
                            "position_decision": {"target_position_pct": 0, "participation_mode": "observe_0"},
                            "extreme_conviction_list": [
                                {
                                    "code": "002971",
                                    "name": "和远气体",
                                    "sector": "化学制品",
                                    "entered_reason": "板块扩散后的过程样本",
                                    "volume_pattern": "放量",
                                    "pattern": "冲高回落",
                                }
                            ],
                        },
                        "market_research_snapshot": {
                            "position_decision": {"participation_mode": "observe_0"},
                            "front_page_final_gate": {
                                "final_action": "0%不参与",
                                "max_position": "0%",
                                "allow_new_entry": False,
                            },
                        },
                    },
                }

        with patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=FakeService()):
            data = daily_report_entry_demo.load_daily_report_data_from_postgres("2026-06-11")

        preflight = build_report_preflight(data, "2026-06-11")

        self.assertEqual(data["selection_workflow"]["schema_version"], "selection_workflow.v1")
        self.assertEqual(data["selection_workflow"]["final"]["execution_object"], {})
        self.assertEqual(data["final_target_resolution"]["capital_priority_decision"]["capital_priority"], "wait")
        self.assertEqual(preflight["status"], "success")
        self.assertEqual(preflight["failures"], [])

    def test_postgres_only_load_reports_psql_fact_coverage_when_target_date_missing(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        class FakeService:
            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": "postgresql:///a_daily_report_psql_529",
                    "field_count": 0,
                    "target_field_count": 0,
                    "structured_fact_count": 0,
                    "target_structured_fact_count": 0,
                    "data": {
                        "postgres_source": "postgresql://daily-report-facts/2026-06-04",
                        "postgres_only": True,
                    },
                }

            def daily_report_fact_coverage(self, target_date):
                return {
                    "database_name": "a_daily_report_psql_529",
                    "tables": {
                        "daily_report_fact_fields": {"target_count": 0, "max_trade_date": "2026-05-29"},
                        "mainline_daily": {"target_count": 0, "max_trade_date": "2026-05-29"},
                        "market_cycle_days": {"target_count": 0, "max_trade_date": "2026-05-29"},
                        "sector_attack_evidence_daily": {"target_count": 0, "max_trade_date": "2026-05-29"},
                        "mainline_turnover_daily": {"target_count": 0, "max_trade_date": "2026-05-29"},
                        "market_daily_totals": {"target_count": 0, "max_trade_date": "2026-05-29"},
                        "candidate_trace_rows": {"target_count": 0, "max_trade_date": "2026-05-29"},
                    },
                }

        with patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=FakeService()):
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                daily_report_entry_demo.load_daily_report_data_from_postgres("2026-06-04")

        message = str(error.exception)
        self.assertIn("2026-06-04 PostgreSQL 日报事实缺失，停止生成", message)
        self.assertIn("a_daily_report_psql_529", message)
        self.assertIn("daily_report_fact_fields", message)
        self.assertIn("mainline_daily", message)
        self.assertIn("candidate_trace_rows", message)
        self.assertIn("2026-05-29", message)

    def test_postgres_only_load_rejects_history_only_structured_payload(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        class FakeService:
            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": "postgresql:///a_daily_report_psql_529",
                    "field_count": 0,
                    "target_field_count": 0,
                    "structured_fact_count": 2,
                    "target_structured_fact_count": 0,
                    "data": {
                        "recent_mainline_history": [{"date": "2026-05-29", "primary_mainline": "通信设备"}],
                        "cycle_calendar_rows": [{"week_label": "05-25当周", "friday": {"date": "05-29", "mainline": "通信设备"}}],
                        "postgres_source": "postgresql://daily-report-facts/2026-06-04",
                        "postgres_only": True,
                    },
                }

            def daily_report_fact_coverage(self, target_date):
                return {
                    "database_name": "a_daily_report_psql_529",
                    "tables": {
                        "daily_report_fact_fields": {"target_count": 0, "max_trade_date": "2026-05-29"},
                    },
                }

        with patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=FakeService()):
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.load_daily_report_data_from_postgres("2026-06-04")

    def test_postgres_only_load_rejects_market_total_only_structured_payload(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        class FakeService:
            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": "postgresql:///a_daily_report_psql_529",
                    "field_count": 0,
                    "target_field_count": 0,
                    "structured_fact_count": 52,
                    "target_structured_fact_count": 0,
                    "structured_counts": {
                        "market_daily_total": 1,
                        "market_stats_from_quotes": 1,
                        "turnover_rank_daily": 50,
                    },
                    "data": {
                        "total_turnover": 28234.29,
                        "market_daily_total": {"total_amount_yi": 28234.29, "stock_count": 5515},
                        "market_stats": {"up_count": 899, "down_count": 4591},
                        "turnover_rank": [{"code": "300308"} for _ in range(50)],
                        "postgres_only": True,
                    },
                }

            def daily_report_fact_coverage(self, target_date):
                return {
                    "database_name": "a_daily_report_psql_529",
                    "tables": {
                        "daily_report_fact_fields": {"target_count": 0, "max_trade_date": "2026-06-05"},
                        "mainline_daily": {"target_count": 0, "max_trade_date": "2026-06-05"},
                        "market_daily_totals": {"target_count": 1, "max_trade_date": "2026-06-08"},
                        "stock_daily_quotes_recent": {"target_count": 5515, "max_trade_date": "2026-06-08"},
                        "turnover_rank_daily": {"target_count": 100, "max_trade_date": "2026-06-08"},
                    },
                }

        with patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=FakeService()):
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                daily_report_entry_demo.load_daily_report_data_from_postgres("2026-06-08")

        message = str(error.exception)
        self.assertIn("2026-06-08 PostgreSQL 日报事实缺失，停止生成", message)
        self.assertIn("daily_report_fact_fields", message)
        self.assertIn("mainline_daily", message)
        self.assertNotIn("turnover_rank_daily", message)

    def test_postgres_only_load_rejects_shell_only_wide_fields(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        class FakeService:
            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": "postgresql:///a_daily_report_psql_529",
                    "field_count": 1,
                    "target_field_count": 0,
                    "structured_fact_count": 0,
                    "target_structured_fact_count": 0,
                    "data": {
                        "postgres_only": True,
                    },
                }

            def daily_report_fact_coverage(self, target_date):
                return {
                    "database_name": "a_daily_report_psql_529",
                    "tables": {
                        "daily_report_fact_fields": {"target_count": 1, "max_trade_date": "2026-06-04"},
                        "mainline_daily": {"target_count": 0, "max_trade_date": "2026-05-29"},
                    },
                }

        with patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=FakeService()):
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.load_daily_report_data_from_postgres("2026-06-04")

    def test_postgres_only_snapshot_guard_blocks_json_snapshot_reads(self):
        import daily_report_snapshot_io

        with patch.dict(os.environ, {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}):
            with self.assertRaisesRegex(RuntimeError, "2026-05-28"):
                daily_report_snapshot_io.load_data_snapshot("2026-05-28")

    def test_main_switches_to_replay_when_existing_official_report_fails_audit(self):
        import daily_report_entry_demo

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "hot_rank_top50": [{"code": f"{index:06d}"} for index in range(50)],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
        })
        stale_report = Path("/tmp/2026-05-28_A股日报_完整版.md")
        stale_report.write_text("| 涨跌比 | 0 / 0 | - | 多头仍占优 |", encoding="utf-8")
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }
        saved_paths = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "/tmp/summary.md",
        }

        def fake_exists(path):
            return str(path) == str(stale_report)

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-28"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=data), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo, "_get_report_output_path", return_value=str(stale_report)), \
             patch.object(daily_report_entry_demo.os.path, "exists", side_effect=fake_exists), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", side_effect=[
                 {
                     "passed": False,
                     "findings": [{"code": "market_breadth_incomplete", "message": "关键数据不完整，停止生成", "line": 1}],
                 },
                 {"passed": True, "findings": []},
             ]) as audit_mock, \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs) as build_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-05-28", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", return_value={}), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths) as save_mock, \
             patch.object(daily_report_entry_demo, "_try_save_elimination_tournament_html", return_value=None), \
             patch.object(daily_report_entry_demo, "_try_save_sector_capital_preflight_html", return_value=None), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", return_value=Path("/tmp/full.html")), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"):
            daily_report_entry_demo.main()

        self.assertEqual(audit_mock.call_args_list[0].args[0], stale_report.read_text(encoding="utf-8"))
        self.assertEqual(audit_mock.call_count, 2)
        self.assertEqual(build_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_REPLAY)
        self.assertEqual(save_mock.call_args.kwargs["mode"], daily_report_entry_demo.LEDGER_MODE_REPLAY)
        self.assertFalse(save_mock.call_args.kwargs["overwrite_existing"])

    def test_main_overwrite_official_keeps_frozen_mode_when_report_exists(self):
        import daily_report_entry_demo

        data = _with_html_required_facts({
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
        })
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }
        saved_paths = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "/tmp/summary.md",
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-26", "--overwrite-official"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=data), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": [{"date": "2026-05-26"}]}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=True), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs) as build_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths) as save_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"):
            daily_report_entry_demo.main()

        self.assertEqual(build_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertEqual(save_mock.call_args.kwargs["mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertTrue(save_mock.call_args.kwargs["overwrite_existing"])


if __name__ == "__main__":
    unittest.main()
