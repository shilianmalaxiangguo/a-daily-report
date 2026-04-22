import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

def _build_stub_module(module_name, attrs):
    module = types.ModuleType(module_name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class MainlineExitAnalysisGraphWrapperTest(unittest.TestCase):
    def test_build_mainline_exit_analysis_keeps_no_mainline_fallback_contract(self):
        stub_modules = {
            "data_collector": _build_stub_module("data_collector", {"AShareDataCollector": object}),
            "ths_hot_stock": _build_stub_module(
                "ths_hot_stock",
                {"fetch_ths_hot_stock": lambda *args, **kwargs: [], "fetch_hot_stock_with_fallback": lambda *args, **kwargs: []},
            ),
            "ths_hot_list": _build_stub_module("ths_hot_list", {"fetch_hot_plate": lambda *args, **kwargs: []}),
            "tencent_finance_data": _build_stub_module("tencent_finance_data", {"TencentFinanceData": object}),
            "xuangubao_intraday": _build_stub_module("xuangubao_intraday", {"XuangubaoIntradayAnalyzer": object}),
            "limit_up_down_pool": _build_stub_module(
                "limit_up_down_pool",
                {
                    "get_limit_up_pool": lambda *args, **kwargs: [],
                    "get_limit_down_pool": lambda *args, **kwargs: [],
                    "mark_limit_status": lambda *args, **kwargs: [],
                },
            ),
            "strong_stock_pool": _build_stub_module(
                "strong_stock_pool",
                {"get_strong_stock_pool": lambda *args, **kwargs: [], "analyze_strong_stocks_by_sector": lambda *args, **kwargs: {}},
            ),
            "data_validator": _build_stub_module("data_validator", {"DataValidator": object}),
            "quantitative_analyzer": _build_stub_module(
                "quantitative_analyzer",
                {
                    "VolumeAnomalyDetector": object,
                    "LHBAnalyzer": object,
                    "ResonanceAnalyzer": object,
                    "SignalGenerator": object,
                    "analyze_volume_anomaly": lambda *args, **kwargs: {},
                    "analyze_lhb": lambda *args, **kwargs: {},
                    "calculate_resonance": lambda *args, **kwargs: {},
                    "generate_trade_signals": lambda *args, **kwargs: [],
                },
            ),
            "hot_list_integrated": _build_stub_module(
                "hot_list_integrated",
                {"get_integrated_hot_list": lambda *args, **kwargs: [], "analyze_sector_distribution": lambda *args, **kwargs: {}},
            ),
            "history_cache": _build_stub_module("history_cache", {"get_cache": lambda *args, **kwargs: {}, "HistoryCache": object}),
            "llm_service": _build_stub_module("llm_service", {"get_llm_service": lambda *args, **kwargs: None}),
        }
        with patch.dict(sys.modules, stub_modules):
            sys.modules.pop("daily_report_entry_demo", None)
            entry = importlib.import_module("daily_report_entry_demo")
            result = entry.build_mainline_exit_analysis(
                {
                    "target_date": "2026-04-22",
                    "sector_fund_flow": {"inflow": [], "outflow": []},
                    "zt_pool_by_sector": {},
                    "dt_pool_by_sector": {},
                    "calendar_events": [],
                    "hot_rank_top30": [],
                    "lhb_net_sell_top10": [],
                    "tag_distribution": {},
                    "stock_full_info": {},
                },
                {"main_sectors": []},
                [],
                enhanced_main_sectors=[],
            )

        self.assertEqual(result["sector_name"], "暂无明确主线")
        self.assertEqual(result["overall_level"], "红灯")
        self.assertEqual(result["leader_name"], "-")
        self.assertEqual(len(result["signals"]), 6)


if __name__ == "__main__":
    unittest.main()
