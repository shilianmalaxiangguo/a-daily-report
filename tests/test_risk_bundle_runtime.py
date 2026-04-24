import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from risk.risk_bundle_runtime import (
    build_risk_bundle_contract,
    build_step3_risk_bundle,
    evaluate_limit_up_friction,
    format_step3_risk_reason,
    parse_limit_time_to_minutes,
)


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

import unittest


class RiskBundleRuntimeTest(unittest.TestCase):
    def test_legacy_step3_risk_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_parse_limit_time_to_minutes", return_value=875) as parse_mock, \
     patch.object(daily_report_entry_demo, "run_evaluate_limit_up_friction", return_value={"penalty": 38, "reason": "炸板4次且尾盘才回封"}) as friction_mock, \
     patch.object(daily_report_entry_demo, "run_format_step3_risk_reason", return_value="风险项：炸板4次") as reason_mock, \
     patch.object(daily_report_entry_demo, "run_build_step3_risk_bundle", return_value={"focus_group": []}) as bundle_mock:
    minutes = daily_report_entry_demo._parse_limit_time_to_minutes("14:35")
    friction = daily_report_entry_demo._evaluate_limit_up_friction(4, last_limit_time="14:35", turnover=16, board_count=3)
    reason = daily_report_entry_demo._format_step3_risk_reason(["炸板4次"], ["承接强"], "🟡 中风险")
    bundle = daily_report_entry_demo.build_step3_risk_bundle({}, "2026-04-22", "军工", [], [])

assert parse_mock.call_args[0][0] == "14:35"
assert friction_mock.call_args[0][0] == 4
assert friction_mock.call_args.kwargs["last_limit_time"] == "14:35"
assert "helpers" in friction_mock.call_args.kwargs
assert reason_mock.call_args[0][0] == ["炸板4次"]
assert "helpers" in reason_mock.call_args.kwargs
assert bundle_mock.call_args[0][:5] == ({}, "2026-04-22", "军工", [], [])
assert "helpers" in bundle_mock.call_args.kwargs
assert minutes == 875
assert friction == {"penalty": 38, "reason": "炸板4次且尾盘才回封"}
assert reason == "风险项：炸板4次"
assert bundle == {"focus_group": []}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_public_risk_runtime_helpers_cover_time_friction_and_reason(self):
        helpers = {
            "safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            "clamp": lambda value, low, high: max(low, min(high, value)),
        }

        minutes = parse_limit_time_to_minutes("14:35")
        friction = evaluate_limit_up_friction(
            4,
            last_limit_time="14:35",
            turnover=16,
            board_count=3,
            helpers=helpers,
        )
        reason = format_step3_risk_reason(
            ["炸板4次", "高换手连板"],
            ["承接强"],
            "🟡 中风险",
        )

        self.assertEqual(minutes, 14 * 60 + 35)
        self.assertEqual(friction["reason"], "炸板4次且尾盘才回封")
        self.assertEqual(friction["penalty"], 48)
        self.assertEqual(reason, "风险项：炸板4次、高换手连板；缓冲项：承接强；仍需观察")

    def test_build_step3_risk_bundle_runtime_delegates_to_contract_with_helpers(self):
        with patch("risk.risk_bundle_runtime.build_risk_bundle_contract", return_value={"focus_group": []}) as contract_mock:
            result = build_step3_risk_bundle(
                {},
                "2026-04-22",
                "军工",
                [],
                [],
                helpers={
                    "normalize_stock_code": lambda code: code,
                    "safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                    "clamp": lambda value, low, high: max(low, min(high, value)),
                    "get_abnormal_follow_risk_signal": lambda stock: {"light": "🟡 黄灯", "delta": 0, "reason": "", "forecast": ""},
                    "update_a_kill_blacklist": lambda target_date, stocks, sector_name="": [],
                },
            )

        self.assertEqual(result, {"focus_group": []})
        self.assertIn("format_risk_reason", contract_mock.call_args.kwargs)
        self.assertTrue(callable(contract_mock.call_args.kwargs["normalize_stock_code"]))

    def test_risk_bundle_contract_groups_candidates_by_risk_level(self):
        result = build_risk_bundle_contract(
            data={
                "zt_pool": [
                    {"代码": "000001", "最新价": 10, "成交额": 5, "开盘价": 10, "最高价": 10.5, "最低价": 9.8, "封单额": 200000000, "换手率": 8, "炸板次数": 0},
                    {"代码": "000002", "最新价": 8, "成交额": 20, "开盘价": 8.1, "最高价": 8.5, "最低价": 7.5, "封单额": 10000000, "换手率": 35, "炸板次数": 3, "最后封板时间": "14:45"},
                ],
                "zt_pool_by_sector": {"军工": [{"代码": "000001"}], "机器人": [{"代码": "000002"}]},
                "dt_pool_by_sector": {"机器人": [{"name": "机器人二号"}] * 3},
                "sector_fund_flow": {"outflow": [{"name": "机器人", "zdf": -5.2}]},
            },
            target_date="2026-04-22",
            mainline_name="军工",
            core_stocks=[{"name": "军工一号", "code": "000001", "sector": "军工", "pattern": "普通涨停", "change": 9.9, "连板数": 1}],
            secondary_stocks=[{"name": "机器人二号", "code": "000002", "sector": "机器人", "pattern": "一字板", "change": 3.0, "连板数": 3}],
            gem_observation_stocks=[],
            zt_pool_by_sector={"军工": [{"代码": "000001"}], "机器人": [{"代码": "000002"}]},
            dt_pool_by_sector={"机器人": [{"name": "机器人二号"}] * 3},
            persist_a_kill=False,
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            safe_float=lambda value, default=0.0: default if value in (None, "") else float(value),
            clamp=lambda value, low, high: max(low, min(high, value)),
            get_abnormal_follow_risk_signal=lambda stock: (
                {"light": "🟢 绿灯", "delta": -12, "reason": "承接强", "forecast": "等60分钟确认"}
                if stock.get("code") == "000001"
                else {"light": "🔴 红灯", "delta": 22, "reason": "承接弱", "forecast": "可能低开"}
            ),
            format_risk_reason=lambda risk_penalties=None, repair_buffers=None, risk_level="": f"{risk_level}:{','.join(risk_penalties or [])}",
            update_a_kill_blacklist=lambda target_date, stocks, sector_name="": [{"sector": sector_name, "count": len(stocks)}],
        )

        self.assertEqual(result["focus_group"][0]["code"], "000001")
        self.assertEqual(result["delete_group"][0]["code"], "000002")
        self.assertTrue(result["mainline_a_kill"] is False or isinstance(result["mainline_a_kill"], bool))
        self.assertEqual(result["abnormal_green_count"], 1)
        self.assertEqual(result["abnormal_red_count"], 1)
        self.assertTrue(any(log["step"] == "risk_scoring" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
