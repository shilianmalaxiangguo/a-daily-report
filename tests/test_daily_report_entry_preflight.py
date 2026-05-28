import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DailyReportEntryPreflightTest(unittest.TestCase):
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
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as save_snapshot_mock, \
             patch.object(daily_report_entry_demo, "publish_snap_ui_public_data") as publish_mock:
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        save_snapshot_mock.assert_not_called()
        publish_mock.assert_not_called()

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
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as save_snapshot_mock, \
             patch.object(daily_report_entry_demo, "publish_snap_ui_public_data") as publish_mock:
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        save_snapshot_mock.assert_not_called()
        publish_mock.assert_not_called()

    def test_main_audits_full_report_with_chanlun_html_after_generation(self):
        import daily_report_entry_demo

        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_research_snapshot": {
                "front_page_final_gate": {
                    "final_action": "空仓等待，禁止参与",
                    "max_position": "0%",
                    "allow_new_entry": False,
                }
            },
        }
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0% / 不参与 |",
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
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=html_path), \
             patch.object(daily_report_entry_demo.Path, "read_text", return_value=html_text), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}) as audit_mock, \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"), \
             patch.object(daily_report_entry_demo, "publish_snap_ui_public_data"):
            daily_report_entry_demo.main()

        audit_mock.assert_called_once_with(
            report_outputs[daily_report_entry_demo.REPORT_VARIANT_FULL],
            companion_html=html_text,
        )

    def test_main_overwrite_official_keeps_frozen_mode_when_report_exists(self):
        import daily_report_entry_demo

        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
        }
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0% / 不参与 |",
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
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths) as save_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo.Path, "read_text", return_value="<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"), \
             patch.object(daily_report_entry_demo, "publish_snap_ui_public_data"):
            daily_report_entry_demo.main()

        self.assertEqual(build_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertEqual(save_mock.call_args.kwargs["mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertTrue(save_mock.call_args.kwargs["overwrite_existing"])


if __name__ == "__main__":
    unittest.main()
