import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

_infer_module = importlib.import_module("domains.market_activity.infer")
build_market_activity_sector_analysis_bundle = _infer_module.build_market_activity_sector_analysis_bundle
get_standardized_sector = _infer_module.get_standardized_sector


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.1, 0.2


class MarketActivityInferTest(unittest.TestCase):
    def test_build_market_activity_sector_analysis_bundle_builds_mapping_and_tree(self):
        timer = _TimerStub()
        emitted = []
        result = build_market_activity_sector_analysis_bundle(
            {
                "sector_fund_flow": {
                    "inflow": [{"name": "高铁"}],
                    "outflow": [{"name": "券商"}],
                },
                "hot_plates": [{"name": "算电协同"}],
                "zt_pool_by_sector": {"光模块": [{"code": "000001"}]},
                "xuangubao_data": {"xuangubao_plates": [{"name": "卫星互联网"}]},
                "lianban_data": [{"plates": ["创新药"]}],
            },
            timer=timer,
            emit=emitted.append,
        )

        sector_ai_analysis = result["results"]["sector_ai_analysis"]
        self.assertEqual(sector_ai_analysis["mapping"]["高铁"], "轨道交通")
        self.assertEqual(sector_ai_analysis["mapping"]["券商"], "券商")
        self.assertEqual(sector_ai_analysis["mapping"]["算电协同"], "算电协同")
        self.assertEqual(sector_ai_analysis["mapping"]["光模块"], "光通信")
        self.assertEqual(sector_ai_analysis["mapping"]["创新药"], "创新药")
        self.assertIn("轨道交通", sector_ai_analysis["sector_tree"])
        self.assertEqual(sector_ai_analysis["sector_count"], 6)
        self.assertTrue(any("标准化板块" in line for line in emitted))
        self.assertEqual(timer.records[0], ("全局板块AI分析", 16))

    def test_get_standardized_sector_returns_original_when_mapping_missing(self):
        self.assertEqual(get_standardized_sector("军工", {"mapping": {"高铁": "轨道交通"}}), "军工")

    def test_build_market_activity_quant_signal_bundle_builds_quant_outputs(self):
        bundle = getattr(_infer_module, "build_market_activity_quant_signal_bundle", None)
        self.assertIsNotNone(bundle, "build_market_activity_quant_signal_bundle should be defined")

        timer = _TimerStub()
        emitted = []
        captured = {}

        def _analyze_volume_anomaly(stocks, _context):
            captured["volume_stocks"] = list(stocks)
            return [{"stock_code": stocks[0]["code"], "stock_name": stocks[0]["name"]}]

        def _analyze_lhb(rows, _context):
            captured["lhb_rows"] = list(rows)
            return [SimpleNamespace(stock_code="000001", stock_name="军工一号")]

        def _calculate_resonance(sectors_data):
            captured["sectors_data"] = sectors_data
            return {"军工装备": {"score": 8.8, "volume_change": sectors_data["军工装备"]["volume_change"]}}

        def _generate_trade_signals(all_data):
            captured["signal_payload"] = all_data
            return [SimpleNamespace(signal_type=SimpleNamespace(value="sector"), sector_name="军工", action="关注")]

        result = bundle(
            {
                "stocks_with_history": [
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "turnover": 20.0,
                        "hist_turnover": [5.0, 6.0, 7.0, 8.0, 10.0],
                        "sector": "军工装备",
                    },
                    {
                        "code": "000002",
                        "name": "军工二号",
                        "turnover": 12.0,
                        "hist_turnover": [1.0, 2.0, 2.0, 2.0, 2.0],
                        "sector": "军工装备",
                    },
                ],
                "lhb_net_buy_top10": [{"code": "000001", "name": "军工一号"}],
                "lhb_net_sell_top10": [{"code": "000003", "name": "消费一号"}],
                "sector_ai_analysis": {"mapping": {"军工": "军工", "军工装备": "军工"}},
                "zt_pool_by_sector": {
                    "军工装备": [{"code": "000001"}, {"code": "000002"}],
                },
                "sector_fund_flow": {"inflow": [{"name": "军工", "zljlr": 10.0, "zdf": 2.5}]},
                "hot_rank": [{"sector": "军工装备"}],
                "zt_pool": [
                    {"代码": "000001", "所属行业": "军工装备", "成交额": 300000000},
                    {"代码": "000002", "所属行业": "军工装备", "成交额": 200000000},
                ],
                "calendar": [{"title": "军工事件"}],
            },
            analyze_volume_anomaly=_analyze_volume_anomaly,
            analyze_lhb=_analyze_lhb,
            calculate_resonance=_calculate_resonance,
            generate_trade_signals=_generate_trade_signals,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["volume_anomalies"][0]["stock_code"], "000001")
        self.assertEqual(result["results"]["lhb_analysis"][0].stock_code, "000001")
        self.assertEqual(result["results"]["resonance_scores"]["军工装备"]["score"], 8.8)
        self.assertEqual(result["results"]["trade_signals"][0].sector_name, "军工")
        self.assertEqual(captured["sectors_data"]["军工装备"]["fund_flow"]["name"], "军工")
        self.assertAlmostEqual(captured["sectors_data"]["军工装备"]["volume_change"], -44.4444, places=3)
        self.assertEqual(captured["signal_payload"]["stocks"][0]["code"], "000001")
        self.assertEqual(len(captured["lhb_rows"]), 2)
        self.assertEqual(timer.records[-1], ("AI多维量化分析", 17))
        self.assertTrue(any("放量异常" in line for line in emitted))
        self.assertTrue(any(log["step"] == "infer.quant_signals" for log in result["module_logs"]))

    def test_build_market_activity_quant_signal_bundle_backfills_price_change_from_candidate_history(self):
        bundle = getattr(_infer_module, "build_market_activity_quant_signal_bundle", None)
        self.assertIsNotNone(bundle, "build_market_activity_quant_signal_bundle should be defined")

        timer = _TimerStub()

        result = bundle(
            {
                "stocks_with_history": [
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "turnover": 20.0,
                        "change_pct": 6.5,
                        "sector": "军工装备",
                        "hist_turnover": [5.0, 6.0, 7.0, 8.0, 10.0],
                    }
                ],
                "lhb_net_buy_top10": [],
                "lhb_net_sell_top10": [],
                "sector_ai_analysis": {"mapping": {"军工装备": "军工"}},
                "zt_pool_by_sector": {},
                "sector_fund_flow": {"inflow": []},
                "zt_pool": [],
                "calendar": [],
            },
            analyze_volume_anomaly=lambda stocks, _context: [
                {
                    "stock_code": stocks[0]["code"],
                    "stock_name": stocks[0]["name"],
                    "anomaly_type": "放量突破",
                    "price_change": 0,
                }
            ],
            analyze_lhb=lambda rows, _context: [],
            calculate_resonance=lambda sectors_data: {},
            generate_trade_signals=lambda payload: [],
            timer=timer,
            emit=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(result["results"]["volume_anomalies"][0]["price_change"], 6.5)

    def test_build_market_activity_quant_signal_bundle_backfills_price_change_from_raw_market_pools(self):
        bundle = getattr(_infer_module, "build_market_activity_quant_signal_bundle", None)
        self.assertIsNotNone(bundle, "build_market_activity_quant_signal_bundle should be defined")

        timer = _TimerStub()

        result = bundle(
            {
                "stocks_with_history": [
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "turnover": 20.0,
                        "sector": "军工装备",
                        "hist_turnover": [5.0, 6.0, 7.0, 8.0, 10.0],
                    }
                ],
                "lhb_net_buy_top10": [],
                "lhb_net_sell_top10": [],
                "sector_ai_analysis": {"mapping": {"军工装备": "军工"}},
                "zt_pool_by_sector": {},
                "sector_fund_flow": {"inflow": []},
                "zt_pool": [{"代码": "000777", "名称": "异常股", "涨跌幅": 7.8}],
                "dt_pool": [],
                "turnover_rank": [{"code": "sz000777", "name": "异常股", "change_pct": 7.8}],
                "lianban_data": [{"code": "000777", "name": "异常股", "change_pct": 7.8}],
                "stock_full_info": {"000777": {"name": "异常股", "change_pct": 7.8}},
                "calendar": [],
            },
            analyze_volume_anomaly=lambda stocks, _context: [
                {
                    "stock_code": "000777",
                    "stock_name": "异常股",
                    "anomaly_type": "放量突破",
                    "price_change": 0,
                }
            ],
            analyze_lhb=lambda rows, _context: [],
            calculate_resonance=lambda sectors_data: {},
            generate_trade_signals=lambda payload: [],
            timer=timer,
            emit=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(result["results"]["volume_anomalies"][0]["price_change"], 7.8)


if __name__ == "__main__":
    unittest.main()
