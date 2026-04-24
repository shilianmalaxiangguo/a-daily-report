import subprocess
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


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

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class StrategyTrackingSnapshotSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("report.strategy_tracking_snapshot_support", fromlist=["strategy_tracking_snapshot_support"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_snapshot_support should exist: {error}")

    def test_legacy_strategy_tracking_snapshot_wrappers_delegate_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

candidate = {"name": "军工一号", "code": "000001"}

with patch.object(daily_report_entry_demo, "run_build_abnormal_setup_distribution", return_value=[{"id": "burst_hold", "count": 2}]) as dist_mock, \
     patch.object(daily_report_entry_demo, "run_snapshot_candidate_brief", return_value={"code": "sz000001"}) as brief_mock:
    distribution = daily_report_entry_demo._build_abnormal_setup_distribution([{"setup_signal_id": "burst_hold"}])
    brief = daily_report_entry_demo._snapshot_candidate_brief(candidate)

assert dist_mock.call_args[0][0] == [{"setup_signal_id": "burst_hold"}]
assert "helpers" in dist_mock.call_args.kwargs
assert brief_mock.call_args[0][0] == candidate
assert "helpers" in brief_mock.call_args.kwargs
assert distribution == [{"id": "burst_hold", "count": 2}]
assert brief == {"code": "sz000001"}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_tracking_snapshot_support_builds_distribution_and_candidate_brief(self):
        support = self._load_module()

        distribution = support.build_abnormal_setup_distribution(
            [
                {"setup_signal_id": "burst_hold", "setup_signal_label": "恐怖阴线异动"},
                {"setup_signal_id": "burst_hold", "setup_signal_label": "恐怖阴线异动"},
                {"setup_signal_id": "upper_shadow_reclaim", "setup_signal_label": "长上影异动"},
                {"setup_signal_id": "upper_shadow_reclaim", "setup_signal_label": "长上影异动", "is_degraded_snapshot": True},
            ],
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (
                    [item for item in pool if not item.get("is_degraded_snapshot")],
                    [item for item in pool if item.get("is_degraded_snapshot")],
                )
            },
        )

        candidate = {
            "name": "军工一号",
            "code": "000001",
            "sector": "军工",
            "permission_label": "允许试错",
            "watch_anchor_type": "主线重点观察谁",
            "watch_anchor_note": "先看承接",
            "signal_type": "burst_hold",
            "abnormal_setup_signal_id": "burst_hold",
            "abnormal_setup_signal_label": "恐怖阴线异动",
            "abnormal_follow_state": "跌不下去",
            "minute_plan": {"confirm_price_60m": 10.66, "confirm_support_60m": 10.22},
            "stop_plan": {"execution_stop": 9.88},
            "signal": types.SimpleNamespace(signal_type="burst_hold"),
        }
        brief = support.snapshot_candidate_brief(
            candidate,
            helpers={
                "normalize_stock_code": lambda code: f"sz{code}",
                "_resolve_candidate_contract_prices": lambda item, signal=None: {
                    "entry_range_low": 10.1,
                    "entry_range_high": 10.5,
                    "observe_anchor_price": 10.2,
                    "upgrade_trigger_price": 10.66,
                    "invalidation_price": 9.88,
                    "reset_breakout_price": 10.9,
                },
                "_build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "key_zone_low": 10.1,
                    "key_zone_high": 10.5,
                    "key_zone_display": "10.10-10.50",
                    "execution_stop": stop_plan.get("execution_stop"),
                },
                "_round_or_none": lambda value, digits=4: None if value is None else round(float(value), digits),
            },
        )

        self.assertEqual(distribution[0], {"id": "burst_hold", "label": "恐怖阴线异动", "count": 2})
        self.assertEqual(distribution[1], {"id": "upper_shadow_reclaim", "label": "长上影异动", "count": 1})
        self.assertEqual(brief["code"], "sz000001")
        self.assertEqual(brief["setup_signal_id"], "burst_hold")
        self.assertEqual(brief["setup_signal_label"], "恐怖阴线异动")
        self.assertEqual(brief["entry_range_low"], 10.1)
        self.assertEqual(brief["entry_range_high"], 10.5)
        self.assertEqual(brief["confirm_price_60m"], 10.66)
        self.assertEqual(brief["confirm_support_60m"], 10.22)
        self.assertEqual(brief["key_zone_display"], "10.10-10.50")
        self.assertEqual(brief["execution_stop"], 9.88)


if __name__ == "__main__":
    unittest.main()
