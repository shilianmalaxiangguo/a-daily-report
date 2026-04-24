import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from portfolio.position_management_report import analyze_position_management_report


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


class PositionManagementReportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("portfolio.position_management_report", fromlist=["position_management_report"])
        except ModuleNotFoundError as error:
            self.fail(f"portfolio.position_management_report should exist: {error}")

    def test_legacy_position_management_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

positions_payload = [{"name": "军工一号", "position": 28.0}]

with patch.object(daily_report_entry_demo, "run_parse_position_string", return_value=positions_payload) as parse_mock, \
     patch.object(daily_report_entry_demo, "run_analyze_position_management", return_value="# report") as analyze_mock:
    parsed = daily_report_entry_demo.parse_position_string("我的仓位是军工一号 28%")
    report = daily_report_entry_demo.analyze_position_management({"foo": "bar"}, "2026-04-22", positions_payload)

assert parse_mock.call_args[0][0] == "我的仓位是军工一号 28%"
assert analyze_mock.call_args[0][:3] == ({"foo": "bar"}, "2026-04-22", positions_payload)
assert "helpers" in analyze_mock.call_args.kwargs
assert parsed == positions_payload
assert report == "# report"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_parse_position_string_extracts_multiple_positions(self):
        module = self._load_module()

        result = module.parse_position_string("我的仓位是军工一号 28% 消费二号 12.5%")

        self.assertEqual(
            result,
            [
                {"name": "军工一号", "position": 28.0},
                {"name": "消费二号", "position": 12.5},
            ],
        )

    def test_analyze_position_management_runtime_exposes_helper_bindings(self):
        module = self._load_module()
        exec(
            """
def _analyze_position_management_probe(data, target_date, positions):
    return runtime_test_helper(data, target_date, positions, build_trading_philosophy_lines, display_mvp_mode)
""",
            module.__dict__,
        )

        with patch(
            "portfolio.position_management_report._analyze_position_management_legacy_body",
            module._analyze_position_management_probe,
        ):
            result = module.analyze_position_management(
                {"foo": "bar"},
                "2026-04-22",
                [{"name": "军工一号", "position": 28.0}],
                helpers={
                    "runtime_test_helper": lambda data, target_date, positions, build_trading_philosophy_lines, display_mvp_mode: (
                        data,
                        target_date,
                        positions[0]["name"],
                        build_trading_philosophy_lines(False, False)[0],
                        display_mvp_mode,
                    ),
                    "build_trading_philosophy_lines": lambda include_system_requirement=False, compact=False: ["- 只做主线"],
                    "display_mvp_mode": True,
                },
            )

        self.assertEqual(result, ({"foo": "bar"}, "2026-04-22", "军工一号", "- 只做主线", True))

    def test_analyze_position_management_report_uses_hot_rank_and_sector_flow(self):
        report = analyze_position_management_report(
            data={
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 18}],
                    "outflow": [],
                },
                "hot_rank_top30": [
                    {"name": "军工一号", "code": "000001", "change_pct": 3.2, "sector": "军工"},
                ],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lhb_net_buy_top10": [],
                "lhb_net_sell_top10": [],
            },
            positions=[{"name": "军工一号", "position": 28}],
            build_trading_philosophy_lines=lambda include_system_requirement=False, compact=False: [
                "- 只做主线",
                "- 看大做小",
            ],
            display_mvp_mode=False,
        )

        self.assertIn("## 【个人持仓管理】（私密信息，仅供参考）", report)
        self.assertIn("| 军工一号 | 28% | 军工 | +3.20% | 未知天 | 🔥 强势流入 | ✅ **持有**（板块强势+个股上涨） |", report)
        self.assertIn("> 只做主线", report)
        self.assertIn("### 交易策略说明", report)


if __name__ == "__main__":
    unittest.main()
