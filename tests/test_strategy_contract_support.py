import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_report_markdown_hooks as markdown_hooks


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


class StrategyContractSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("report.strategy_contract_support", fromlist=["strategy_contract_support"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_contract_support should exist: {error}")

    def test_legacy_entry_contract_helpers_resolve_to_support_exports(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from report import strategy_contract_support

assert daily_report_entry_demo._build_trading_philosophy_lines is strategy_contract_support.build_trading_philosophy_lines
assert daily_report_entry_demo._build_strategy_positioning_lines is strategy_contract_support.build_strategy_positioning_lines
assert daily_report_entry_demo._get_contract_logic_digest_text is strategy_contract_support.get_contract_logic_digest_text
assert daily_report_entry_demo._build_alignment_pool_text is strategy_contract_support.build_alignment_pool_text
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_contract_support_reuses_markdown_hook_exports(self):
        support = self._load_module()

        self.assertEqual(
            support.build_trading_philosophy_lines(include_system_requirement=False, compact=True),
            markdown_hooks.use_trading_philosophy_lines(include_system_requirement=False, compact=True),
        )
        self.assertEqual(
            support.build_strategy_positioning_lines(compact=True),
            markdown_hooks.use_strategy_positioning_lines(compact=True),
        )
        self.assertEqual(
            support.get_contract_logic_digest_text(),
            markdown_hooks.use_contract_logic_digest_text(),
        )

    def test_build_alignment_pool_text_composes_primary_and_probe_pools(self):
        support = self._load_module()

        rendered = support.build_alignment_pool_text(
            market_research_snapshot={
                "observation": {
                    "mainline_competition_snapshot": [
                        {"role": "主攻线", "sector": "军工"},
                        {"role": "次强线", "sector": "机器人"},
                        {"role": "竞争线", "sector": "消费电子"},
                    ],
                    "secondary_candidates": ["消费电子", "算力"],
                    "sector_trend_snapshot": [{"sector": "算力"}, {"sector": "低空经济"}],
                },
                "state_machine": {"leading_line": "军工"},
            },
            watch_anchor={"sector": "军工"},
        )

        self.assertEqual(
            rendered,
            "月度站队池：军工 / 机器人；本周发酵方向：消费电子 / 算力 / 低空经济；探针方向：军工",
        )

    def test_build_alignment_pool_text_falls_back_to_state_machine_and_probe_candidate(self):
        support = self._load_module()

        rendered = support.build_alignment_pool_text(
            market_research_snapshot={
                "observation": {
                    "mainline_candidates": ["军工", "机器人"],
                    "secondary_candidates": ["低空经济"],
                },
                "state_machine": {"leading_line": "军工"},
            },
            special_probe_verdict={"probe_candidate": {"sector_name": "低空经济"}},
        )

        self.assertEqual(
            rendered,
            "月度站队池：军工 / 机器人；本周发酵方向：低空经济；探针方向：低空经济",
        )


if __name__ == "__main__":
    unittest.main()
