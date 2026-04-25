import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from replay.report_replay import build_replay_snapshot_contract
from daily_report_render import REPORT_VARIANT_FULL, REPORT_VARIANT_SUMMARY, save_report_outputs


def _run_legacy_entry_probe(script_body):
    stub_setup = """
import sys
import types

def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module

sys.path.insert(0, {scripts_path!r})
sys.modules.update(
    {{
        "data_collector": _stub_module("data_collector", AShareDataCollector=type("AShareDataCollector", (), {{}})),
        "ths_hot_stock": _stub_module(
            "ths_hot_stock",
            fetch_ths_hot_stock=lambda *args, **kwargs: [],
            fetch_hot_stock_with_fallback=lambda *args, **kwargs: [],
        ),
        "ths_hot_list": _stub_module("ths_hot_list", fetch_hot_plate=lambda *args, **kwargs: []),
        "tencent_finance_data": _stub_module("tencent_finance_data", TencentFinanceData=type("TencentFinanceData", (), {{}})),
        "xuangubao_intraday": _stub_module(
            "xuangubao_intraday",
            XuangubaoIntradayAnalyzer=type("XuangubaoIntradayAnalyzer", (), {{}}),
        ),
        "limit_up_down_pool": _stub_module(
            "limit_up_down_pool",
            get_limit_up_pool=lambda *args, **kwargs: ([], set()),
            get_limit_down_pool=lambda *args, **kwargs: ([], set()),
            mark_limit_status=lambda *args, **kwargs: {{}},
        ),
        "strong_stock_pool": _stub_module(
            "strong_stock_pool",
            get_strong_stock_pool=lambda *args, **kwargs: [],
            analyze_strong_stocks_by_sector=lambda *args, **kwargs: {{}},
        ),
        "data_validator": _stub_module("data_validator", DataValidator=type("DataValidator", (), {{}})),
        "quantitative_analyzer": _stub_module(
            "quantitative_analyzer",
            VolumeAnomalyDetector=type("VolumeAnomalyDetector", (), {{}}),
            LHBAnalyzer=type("LHBAnalyzer", (), {{}}),
            ResonanceAnalyzer=type("ResonanceAnalyzer", (), {{}}),
            SignalGenerator=type("SignalGenerator", (), {{}}),
            analyze_volume_anomaly=lambda *args, **kwargs: {{}},
            analyze_lhb=lambda *args, **kwargs: {{}},
            calculate_resonance=lambda *args, **kwargs: {{}},
            generate_trade_signals=lambda *args, **kwargs: {{}},
        ),
        "hot_list_integrated": _stub_module(
            "hot_list_integrated",
            get_integrated_hot_list=lambda *args, **kwargs: {{}},
            analyze_sector_distribution=lambda *args, **kwargs: {{}},
        ),
        "history_cache": _stub_module(
            "history_cache",
            get_cache=lambda *args, **kwargs: {{}},
            HistoryCache=type("HistoryCache", (), {{}}),
        ),
        "llm_service": _stub_module("llm_service", get_llm_service=lambda *args, **kwargs: None),
    }}
)
""".format(scripts_path=str(ROOT / "scripts"))

    result = subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return result


class _FakeTencentFinanceData:
    def __init__(self, calendar_events):
        self._calendar_events = calendar_events

    def get_calendar_events(self, target_date=""):
        return list(self._calendar_events)


class ReportReplayTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("replay.report_replay", fromlist=["report_replay"])
        except ModuleNotFoundError as error:
            self.fail(f"replay.report_replay should exist: {error}")

    def test_legacy_replay_wrapper_delegates_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload = {"data": {"foo": "bar"}, "target_date": "2026-04-23"}
with patch.object(daily_report_entry_demo, "run_replay_from_snapshot", return_value=payload) as runtime_mock:
    data, target_date = daily_report_entry_demo.replay_from_snapshot("2026-04-22", refresh_sources=["major_indices"])

assert runtime_mock.call_args[0][0] == "2026-04-22"
assert runtime_mock.call_args.kwargs["refresh_sources"] == ["major_indices"]
assert "helpers" in runtime_mock.call_args.kwargs
assert data == {"foo": "bar"}
assert target_date == "2026-04-23"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_replay_runtime_exposes_helper_bindings(self):
        replay_runtime = self._load_module()
        tencent_factory = object()
        major_indices_fetcher = object()
        exec(
            """
def _replay_probe(target_date, refresh_sources=None):
    return runtime_test_helper(target_date, refresh_sources, load_data_snapshot, TencentFinanceData, get_major_indices_from_iwencai, safe_float)
""",
            replay_runtime.__dict__,
        )

        with patch(
            "replay.report_replay._replay_from_snapshot_legacy_body",
            replay_runtime._replay_probe,
        ):
            result = replay_runtime.replay_from_snapshot(
                "2026-04-22",
                refresh_sources=["calendar_events"],
                helpers={
                    "runtime_test_helper": lambda target_date, refresh_sources, load_data_snapshot, tencent_factory, get_major_indices_from_iwencai, safe_float: (
                        target_date,
                        refresh_sources,
                        load_data_snapshot("x")[0],
                        tencent_factory,
                        get_major_indices_from_iwencai,
                        safe_float(1.25),
                    ),
                    "load_data_snapshot": lambda target_date: ({"snapshot": target_date}, ""),
                    "TencentFinanceData": tencent_factory,
                    "get_major_indices_from_iwencai": major_indices_fetcher,
                    "safe_float": lambda value: float(value or 0),
                },
            )

        self.assertEqual(result, ("2026-04-22", ["calendar_events"], {"snapshot": "x"}, tencent_factory, major_indices_fetcher, 1.25))

    def test_build_replay_snapshot_contract_refreshes_calendar_and_indices(self):
        snapshot = {
            "calendar_events": [{"title": "old"}],
            "indices": [],
            "data_status": {},
            "step_status": {},
            "timer_summary": {"steps": [["旧步骤", 1.0, 1.0]]},
        }

        result = build_replay_snapshot_contract(
            "2026-04-22",
            refresh_sources=["calendar_events", "major_indices"],
            load_data_snapshot=lambda target_date: (snapshot, "补充视角"),
            tencent_factory=lambda: _FakeTencentFinanceData([{"title": "new"}]),
            get_major_indices_from_iwencai=lambda target_date="": [{"code": "sh000001"}],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["supplementary_perspective"], "补充视角")
        self.assertEqual(result["data"]["calendar_events"], [{"title": "new"}])
        self.assertEqual(result["data"]["indices"], [{"code": "sh000001"}])
        self.assertTrue(result["data"]["data_status"]["主要指数"])
        self.assertTrue(result["data"]["step_status"]["主要指数获取"])
        self.assertIn("主要指数获取", [row[0] for row in result["data"]["timer_summary"]["steps"]])
        self.assertTrue(any(log["step"] == "refresh.calendar_events" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "refresh.major_indices" for log in result["module_logs"]))

    def test_build_replay_snapshot_contract_returns_not_found_when_snapshot_missing(self):
        result = build_replay_snapshot_contract(
            "2026-04-22",
            load_data_snapshot=lambda target_date: (None, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertFalse(result["found"])
        self.assertIsNone(result["data"])
        self.assertTrue(any(log["step"] == "load.snapshot" and log["status"] == "error" for log in result["module_logs"]))

    def test_build_replay_snapshot_contract_hoists_analysis_atoms_for_report_reuse(self):
        snapshot = {
            "analysis": {
                "mainline_history_record": {
                    "date": "2026-04-23",
                    "primary_mainline": "电力",
                    "leading_line": "电力",
                },
                "sector_turnover_snapshot": {
                    "date": "2026-04-23",
                    "sector_name": "电力",
                    "turnover_share_pct": 2.7,
                },
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-04-23",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["data"]["current_mainline_history_record"]["primary_mainline"], "电力")
        self.assertEqual(result["data"]["current_sector_turnover_snapshot"]["turnover_share_pct"], 2.7)

    def test_build_replay_snapshot_contract_builds_missing_mainline_atoms_for_report_reuse(self):
        snapshot = {
            "market_research_snapshot": {
                "state_machine": {"leading_line": "半导体"},
                "observation": {},
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 12834.0,
        }

        result = build_replay_snapshot_contract(
            "2026-04-24",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "build_mainline_history_record": lambda target_date, market_research_snapshot: {
                    "date": target_date,
                    "primary_mainline": "半导体",
                    "leading_line": "半导体",
                },
                "load_recent_mainline_history": lambda target_date, lookback_days=5: [
                    {"date": "2026-04-22", "primary_mainline": "电力"},
                    {"date": "2026-04-23", "primary_mainline": "半导体"},
                ],
                "get_sector_turnover_snapshot_from_ths": lambda sector_name, target_date="", total_turnover=0: {
                    "date": target_date,
                    "sector_name": sector_name,
                    "sector_turnover": 2180.0,
                    "total_turnover": total_turnover,
                    "turnover_share_pct": 18.1,
                },
                "load_recent_sector_turnover_history": lambda target_date, current_mainline_name, lookback_days=5: [
                    {"date": "2026-04-23", "sector_name": current_mainline_name, "turnover_share_pct": 15.8},
                ],
                "build_mainline_turnover_summary": lambda **kwargs: {
                    "current_mainline": kwargs["current_mainline_history_record"]["primary_mainline"],
                    "double_mainline_summary": {
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "半导体",
                        "relationship": "周期主线与当天主攻线一致",
                        "tomorrow_action": "继续围绕半导体观察承接",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-04-24",
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "2180.00亿",
                            "market_turnover": "12834.00亿",
                            "share": "18.1%",
                            "share_change": "+2.3pct",
                            "interpretation": "主线占比继续抬升",
                        }
                    ],
                },
            },
        )

        self.assertEqual(result["data"]["current_mainline_history_record"]["primary_mainline"], "半导体")
        self.assertEqual(result["data"]["recent_mainline_history"][0]["primary_mainline"], "电力")
        self.assertEqual(result["data"]["current_sector_turnover_snapshot"]["turnover_share_pct"], 18.1)
        self.assertEqual(result["data"]["recent_sector_turnover_history"][0]["turnover_share_pct"], 15.8)
        self.assertEqual(result["data"]["mainline_turnover_summary"]["current_mainline"], "半导体")

    def test_build_replay_report_outputs_contract_writes_mainline_turnover_reports(self):
        replay_runtime = self._load_module()
        captured = {}
        snapshot = {
            "analysis": {
                "mainline_history_record": {
                    "date": "2026-04-23",
                    "primary_mainline": "电力",
                    "leading_line": "电力",
                },
                "sector_turnover_snapshot": {
                    "date": "2026-04-23",
                    "sector_name": "电力",
                    "turnover_share_pct": 2.7,
                },
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        def _build_report_outputs(data, target_date, supplementary_perspective="", has_personal_positions=False, run_mode="frozen", position_report_text=""):
            captured["target_date"] = target_date
            captured["run_mode"] = run_mode
            captured["mainline"] = data["current_mainline_history_record"]["primary_mainline"]
            captured["share_pct"] = data["current_sector_turnover_snapshot"]["turnover_share_pct"]
            mainline_line = (
                "- **主线更替与占比**: 主线未切换，电力仍是中心；"
                "最近1日主线 电力；成交额占比 2.7%，节奏偏持平"
            )
            return {
                REPORT_VARIANT_FULL: "# 完整版\n" + mainline_line,
                REPORT_VARIANT_SUMMARY: "# 执行摘要\n" + mainline_line,
            }

        with TemporaryDirectory() as output_dir:
            result = replay_runtime.build_replay_report_outputs_contract(
                "2026-04-23",
                refresh_sources=["noop"],
                load_data_snapshot=lambda target_date: (snapshot, ""),
                tencent_factory=lambda: _FakeTencentFinanceData([]),
                get_major_indices_from_iwencai=lambda target_date="": [],
                safe_float=lambda value: float(value or 0),
                build_report_outputs=_build_report_outputs,
                save_report_outputs=save_report_outputs,
                output_dir=output_dir,
                print_fn=lambda *args, **kwargs: None,
            )

            full_path = Path(result["saved_paths"][REPORT_VARIANT_FULL])
            summary_path = Path(result["saved_paths"][REPORT_VARIANT_SUMMARY])

            self.assertTrue(full_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertIn("主线更替与占比", full_path.read_text(encoding="utf-8"))
            self.assertIn("主线更替与占比", summary_path.read_text(encoding="utf-8"))

        self.assertTrue(result["found"])
        self.assertEqual(captured["target_date"], "2026-04-23")
        self.assertEqual(captured["run_mode"], "replay")
        self.assertEqual(captured["mainline"], "电力")
        self.assertEqual(captured["share_pct"], 2.7)
        self.assertTrue(any(log["step"] == "render.report_outputs" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "save.report_outputs" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
