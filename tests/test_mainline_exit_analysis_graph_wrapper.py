import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.nodes.assemble_exit_analysis import run as run_assemble_exit_analysis
from domains.market_state.nodes.infer_sector_competition import run as run_infer_sector_competition


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

    def test_infer_sector_competition_handles_non_numeric_inflow_values(self):
        result = run_infer_sector_competition(
            {
                "inputs": {
                    "data": {
                        "sector_fund_flow": {
                            "inflow": [
                                {"name": "旧主线", "zljlr": "1.0"},
                                {"name": "新主线A", "zljlr": "12.5"},
                                {"name": "新主线B", "zljlr": None},
                            ]
                        },
                        "tag_distribution": {},
                    }
                },
                "state": {"tracked_sector": "旧主线", "sector_inflow": "1.5", "hot_weight": "1.0", "zt_pool_by_sector": {}},
                "helpers": {
                    "action_map": {"绿灯": "keep", "黄灯": "watch", "橙灯": "warn", "红灯": "exit"},
                    "get_sector_hotlist_weight": lambda sector, _: {"新主线A": "3.5", "新主线B": None}.get(sector, 0),
                    "safe_float": lambda value, default=0.0: float(value) if value not in (None, "") else default,
                },
            }
        )

        snapshot = result["exports"]["competition_snapshot"]
        self.assertEqual(snapshot["replacement"]["name"], "新主线A")
        self.assertEqual(snapshot["replacement"]["inflow"], 12.5)
        self.assertEqual(result["exports"]["competition_signal"]["level"], "黄灯")

    def test_assemble_exit_analysis_filters_invalid_signals_and_keeps_score_detail_consistent(self):
        result = run_assemble_exit_analysis(
            {
                "state": {
                    "tracked_sector": "军工",
                    "mainline_score_pct": "72.0",
                    "mainline_snapshot": {"star_level": "⭐⭐⭐⭐", "component_scores": {"资金": 80.0}, "trend_label": "主升"},
                    "continuity_snapshot": {
                        "leader_score": "70.0",
                        "structure_score": None,
                        "core_score": "66.0",
                        "leader_name": "龙头A",
                    },
                    "environment_signal": {"layer": "主线地位复核", "status": "主线稳定", "level": "绿灯", "action": "继续"},
                    "leader_signal": {},
                    "structure_signal": {"layer": "板块内部结构", "status": "结构可控", "level": "黄灯"},
                    "core_signal": {"layer": "持仓个股承接", "status": "承接尚可", "level": "黄灯", "action": "盯盘"},
                    "risk_signal": {"layer": "事件落地风险", "status": "无短线风险", "level": "绿灯", "action": "继续"},
                    "competition_signal": {"layer": "替代主线流向", "status": "无明显替代", "level": "绿灯", "action": "继续"},
                }
            }
        )

        exit_analysis = result["exports"]["exit_analysis"]
        self.assertNotIn("事件", exit_analysis["score_detail"])
        self.assertNotIn("替代", exit_analysis["score_detail"])
        self.assertEqual(exit_analysis["overall_score"], 52.7)
        self.assertEqual(exit_analysis["score_detail"]["结构"], 0.0)
        self.assertEqual(len(exit_analysis["signals"]), 5)
        for signal in exit_analysis["signals"]:
            self.assertTrue(signal.get("layer"))
            self.assertTrue(signal.get("status"))
            self.assertTrue(signal.get("level"))
            self.assertTrue(signal.get("action"))


if __name__ == "__main__":
    unittest.main()
