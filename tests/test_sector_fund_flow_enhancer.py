import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state import sector_fund_flow_enhancer as enhancer


def _build_market_data():
    return {
        "sector_stocks": {
            "机器人": [
                {
                    "代码": "300001",
                    "名称": "核心A",
                    "成交额": 320,
                    "涨跌幅": 11.0,
                    "量比": 1.3,
                    "high": 10.0,
                    "close": 9.9,
                },
                {
                    "code": "300002",
                    "name": "核心B",
                    "turnover": 250,
                    "change_pct": 9.0,
                    "volume_ratio": 2.1,
                    "is_new_high": True,
                    "intraday_high": 20.0,
                    "close": 19.8,
                },
                {
                    "stock_code": "300003",
                    "stock_name": "弹性C",
                    "amount_yi": 120,
                    "zdf": 6.2,
                    "new_high": True,
                    "new_high_dates": ["2026-05-26", "2026-05-29"],
                    "intraday_high": 12.0,
                    "close": 11.8,
                },
                {
                    "code": "300004",
                    "name": "弹性D",
                    "volume": 90,
                    "change_pct": 6.0,
                    "is_new_high": True,
                    "new_high_dates": ["2026-05-25", "2026-05-28"],
                    "intraday_high": 9.0,
                    "close": 8.8,
                },
                {
                    "code": "300005",
                    "name": "弹性E",
                    "volume": 80,
                    "change_pct": 5.5,
                    "is_new_high": True,
                    "intraday_high": 8.0,
                    "close": 7.8,
                },
                {"code": "300006", "name": "后排F", "volume": 70, "change_pct": 4.0},
                {"code": "300007", "name": "后排G", "volume": 60, "change_pct": 3.5},
                {"code": "300008", "name": "后排H", "volume": 55, "change_pct": 3.2},
                {"code": "300009", "name": "后排I", "volume": 45, "change_pct": 3.1},
                {"code": "300010", "name": "后排J", "volume": 35, "change_pct": -1.0},
            ]
        }
    }


class SectorFundFlowEnhancerTest(unittest.TestCase):
    def test_internal_analysis_exposes_spec_keys(self):
        build_analysis = getattr(enhancer, "build_sector_internal_analysis_data", None)
        self.assertIsNotNone(build_analysis, "缺少板块内部分析构建函数")

        result = build_analysis(
            {"inflow": [{"name": "机器人"}]},
            market_data=_build_market_data(),
        )
        robot = result["sectors"][0]

        missing_keys = [
            key
            for key in ("follower_support", "second_wave_new_highs")
            if key not in robot
        ]
        self.assertEqual(missing_keys, [])

    def test_builds_sector_internal_analysis_with_six_dimensions(self):
        build_analysis = getattr(enhancer, "build_sector_internal_analysis_data", None)
        self.assertIsNotNone(build_analysis, "缺少板块内部分析构建函数")

        result = build_analysis(
            {
                "market_turnover": 10000,
                "inflow": [
                    {
                        "name": "机器人",
                        "today_turnover_share": 54.0,
                        "yesterday_turnover_share": 42.0,
                        "total_turnover_change_pct": 12.5,
                    },
                    {
                        "name": "算力",
                        "today_turnover_share": 20.0,
                        "yesterday_turnover_share": 28.0,
                        "total_turnover_change_pct": 12.5,
                    },
                ]
            },
            market_data=_build_market_data(),
        )

        robot = result["sectors"][0]
        self.assertEqual(robot["sector_name"], "机器人")

        self.assertEqual(robot["core_anchor"]["code"], "300001")
        self.assertEqual(robot["core_anchor"]["name"], "核心A")
        self.assertEqual(robot["core_anchor"]["status"], "放量上涨")
        self.assertAlmostEqual(robot["core_anchor"]["volume_ratio_in_sector"], 320 / 1125, places=4)

        self.assertEqual(
            [stock["name"] for stock in robot["relative_position"]["leaders"]],
            ["核心A", "核心B"],
        )
        self.assertEqual(
            [stock["name"] for stock in robot["relative_position"]["core_anchors"]],
            ["核心A", "核心B"],
        )
        self.assertEqual(robot["relative_position"]["conclusion"], "资金向核心集中")

        self.assertEqual(robot["elastic_carrier"]["count"], 3)
        self.assertEqual(robot["elastic_carrier"]["new_high_count"], 3)
        self.assertEqual(robot["elastic_carrier"]["intraday_support"], "强")
        self.assertEqual(
            [stock["name"] for stock in robot["elastic_carrier"]["stocks"]],
            ["弹性C", "弹性D", "弹性E"],
        )

        follower = robot["follower_support"]
        self.assertEqual(follower["grade"], "B")
        self.assertEqual(follower["gain_5pct_count"], 3)
        self.assertEqual(follower["gain_3pct_count"], 7)
        self.assertAlmostEqual(follower["volume_ratio"], 555 / 1125, places=4)
        self.assertEqual(robot["follower_support_quality"], follower)

        second_wave = robot["second_wave_new_highs"]
        self.assertIsInstance(second_wave, dict)
        self.assertEqual(second_wave["count"], 2)
        self.assertAlmostEqual(second_wave["ratio"], 0.2)
        self.assertEqual([stock["name"] for stock in second_wave["stocks"]], ["弹性C", "弹性D"])
        self.assertEqual(robot["second_wave_new_high_group"], second_wave)

        flow = result["sector_fund_flow"]["flows"][0]
        self.assertEqual(flow["from_sector"], "算力")
        self.assertEqual(flow["to_sector"], "机器人")
        self.assertEqual(flow["type"], "扩散分流")
        self.assertAlmostEqual(flow["volume_change"], 800.0)

    def test_reads_sector_components_and_stock_pool_shapes(self):
        build_analysis = getattr(enhancer, "build_sector_internal_analysis_data", None)
        self.assertIsNotNone(build_analysis, "缺少板块内部分析构建函数")

        component_result = build_analysis(
            {"inflow": [{"name": "半导体"}]},
            market_data={
                "sector_components": {
                    "半导体": [
                        {"code": "688001", "name": "芯片A", "volume": 130, "change_pct": -0.5, "volume_ratio": 0.9},
                        {"code": "688002", "name": "芯片B", "volume": 90, "change_pct": 5.8, "new_high": True},
                    ]
                }
            },
        )
        self.assertEqual(component_result["sectors"][0]["core_anchor"]["status"], "横住不破")
        self.assertEqual(component_result["sectors"][0]["elastic_carrier"]["intraday_support"], "中")

        pool_result = build_analysis(
            {"inflow": [{"name": "低空经济"}]},
            market_data={
                "stock_pool": [
                    {"code": "000001", "name": "低空A", "sector_name": "低空经济", "volume": 160, "change_pct": -3.5, "volume_ratio": 1.4},
                    {"code": "000002", "name": "低空B", "sector": "低空经济,军工", "volume": 60, "change_pct": 1.0},
                    {"code": "000003", "name": "其他A", "sector_name": "其他", "volume": 200, "change_pct": 9.0},
                ]
            },
        )
        self.assertEqual(pool_result["sectors"][0]["core_anchor"]["name"], "低空A")
        self.assertEqual(pool_result["sectors"][0]["core_anchor"]["status"], "放量下杀")
        self.assertEqual(pool_result["sectors"][0]["total_stocks"], 2)

    def test_keeps_legacy_scoring_contract(self):
        sector_fund_flow = {"inflow": [{"name": "机器人", "turnover_share_change": 1.2}]}

        sectors_data = enhancer.extract_sector_data_from_fund_flow(
            sector_fund_flow,
            zt_pool=[{"sector": "机器人", "code": "300099"}],
            lianban_data=[
                {"sector": "机器人", "code": "300003", "is_new_high": True, "new_high_dates": ["2026-05-26", "2026-05-29"]},
                {"sector": "机器人", "code": "300004", "is_new_high": True, "new_high_dates": ["2026-05-25", "2026-05-28"]},
            ],
            market_data=_build_market_data(),
        )

        sector_data = sectors_data[0]["data"]
        self.assertIsInstance(sector_data["second_wave_new_highs"], int)
        self.assertEqual(sector_data["second_wave_new_highs"], 2)
        self.assertEqual(sector_data["core_anchor"]["status"], "放量上涨")
        self.assertEqual(sector_data["elastic_carrier"]["new_high_count"], 3)
        self.assertEqual(sector_data["total_stocks"], 10)

        report = enhancer.build_enhanced_sector_fund_flow_report(
            sector_fund_flow,
            zt_pool=[{"sector": "机器人", "code": "300099"}],
            lianban_data=[
                {"sector": "机器人", "code": "300003", "is_new_high": True, "new_high_dates": ["2026-05-26", "2026-05-29"]},
                {"sector": "机器人", "code": "300004", "is_new_high": True, "new_high_dates": ["2026-05-25", "2026-05-28"]},
            ],
            market_data=_build_market_data(),
        )
        scored = report["diffusion_quality"]["sectors"][0]
        self.assertEqual(scored["details"]["core_anchor"]["score"], 30)
        self.assertGreater(scored["total_score"], 0)

    def test_legacy_elastic_carrier_keeps_lianban_fallback(self):
        sectors_data = enhancer.extract_sector_data_from_fund_flow(
            {"inflow": [{"name": "机器人"}]},
            lianban_data=[{"sector": "机器人", "code": "300011", "is_new_high": True}],
            market_data={
                "sector_stocks": {
                    "机器人": [
                        {"code": "300001", "name": "普通A", "volume": 180, "change_pct": 1.0},
                    ]
                }
            },
        )

        self.assertEqual(sectors_data[0]["data"]["elastic_carrier"]["new_high_count"], 1)

    def test_sector_fund_flow_volume_change_defaults_to_zero_without_turnover(self):
        build_analysis = getattr(enhancer, "build_sector_internal_analysis_data", None)
        self.assertIsNotNone(build_analysis, "缺少板块内部分析构建函数")

        result = build_analysis(
            {
                "inflow": [
                    {"name": "机器人", "today_turnover_share": 54.0, "yesterday_turnover_share": 42.0},
                    {"name": "算力", "today_turnover_share": 20.0, "yesterday_turnover_share": 28.0},
                ]
            },
            market_data=_build_market_data(),
        )

        self.assertEqual(result["sector_fund_flow"]["flows"][0]["volume_change"], 0.0)

    def test_sector_fund_flow_uses_yi_turnover_alias_for_volume_change(self):
        result = enhancer.build_sector_internal_analysis_data(
            {
                "market_turnover_yi": 10000,
                "inflow": [
                    {"name": "机器人", "today_turnover_share": 54.0, "yesterday_turnover_share": 42.0},
                    {"name": "算力", "today_turnover_share": 20.0, "yesterday_turnover_share": 28.0},
                ],
            },
            market_data=_build_market_data(),
        )

        self.assertAlmostEqual(result["sector_fund_flow"]["flows"][0]["volume_change"], 800.0)

    def test_distributes_sector_fund_flow_without_reusing_pct_change(self):
        result = enhancer.build_sector_internal_analysis_data(
            {
                "market_turnover": 10000,
                "inflow": [
                    {"name": "机器人", "today_turnover_share": 15.0, "yesterday_turnover_share": 10.0},
                    {"name": "半导体", "today_turnover_share": 14.0, "yesterday_turnover_share": 10.0},
                    {"name": "算力", "today_turnover_share": 20.0, "yesterday_turnover_share": 28.0},
                    {"name": "传媒", "today_turnover_share": 7.0, "yesterday_turnover_share": 10.0},
                ],
            },
            market_data=_build_market_data(),
        )

        flows = result["sector_fund_flow"]["flows"]
        outflow_by_source = {}
        for flow in flows:
            outflow_by_source[flow["from_sector"]] = (
                outflow_by_source.get(flow["from_sector"], 0.0) + flow["volume_change"]
            )

        self.assertLessEqual(outflow_by_source["算力"], 800.0)
        self.assertAlmostEqual(outflow_by_source["算力"], 800.0)
        self.assertAlmostEqual(sum(flow["volume_change"] for flow in flows), 900.0)

    def test_none_fund_flow_inputs_return_empty_structures(self):
        self.assertEqual(enhancer.extract_sector_data_from_fund_flow(None), [])

        report = enhancer.build_enhanced_sector_fund_flow_report(None)

        self.assertEqual(report["original_fund_flow"], {})
        self.assertEqual(report["diffusion_quality"]["sectors"], [])
        self.assertEqual(report["markdown_sections"][-1], "")

    def test_turnover_summary_merges_mixed_history_without_duplicate_sectors(self):
        report = enhancer.build_enhanced_sector_fund_flow_report(
            {"inflow": [{"name": "电力"}, {"name": "煤炭"}]},
            sector_turnover_history=[
                {
                    "sector_name": "电力",
                    "history": [{"date": "2026-05-27", "turnover_share_pct": 2.0}],
                },
                {"date": "2026-05-28", "sector_name": "电力", "turnover_share_pct": 2.8},
                {"date": "2026-05-29", "sector_name": "电力", "turnover_share_pct": 3.5},
                {"date": "2026-05-29", "sector_name": "煤炭"},
            ],
        )

        turnover_summary = report["turnover_trend"]
        sectors = turnover_summary["sectors"]
        self.assertEqual([sector["sector_name"] for sector in sectors], ["电力", "煤炭"])
        self.assertEqual(sectors[0]["latest_share"], 3.5)
        self.assertEqual(sectors[0]["formatted_series"], "2.0% → 2.8% → 3.5% (扩张)")
        self.assertEqual(sectors[1]["latest_share"], 0.0)
        self.assertEqual(sectors[1]["formatted_series"], "待累计")

    def test_turnover_summary_sorts_all_normalized_sectors_before_top5_cut(self):
        report = enhancer.build_enhanced_sector_fund_flow_report(
            {"inflow": [{"name": f"板块{i}"} for i in range(1, 7)]},
            sector_turnover_history=[
                {"date": "2026-05-29", "sector_name": "板块1", "turnover_share_pct": 1.0},
                {"date": "2026-05-29", "sector_name": "板块2", "turnover_share_pct": 2.0},
                {"date": "2026-05-29", "sector_name": "板块3", "turnover_share_pct": 3.0},
                {"date": "2026-05-29", "sector_name": "板块4", "turnover_share_pct": 4.0},
                {"date": "2026-05-29", "sector_name": "板块5", "turnover_share_pct": 5.0},
                {"date": "2026-05-29", "sector_name": "板块6", "turnover_share_pct": 9.0},
            ],
        )

        sectors = report["turnover_trend"]["sectors"]
        self.assertEqual([sector["sector_name"] for sector in sectors], ["板块6", "板块5", "板块4", "板块3", "板块2"])
        self.assertNotIn("板块1", [sector["sector_name"] for sector in sectors])

    def test_markdown_quant_environment_uses_top_level_when_nested_environment_is_empty(self):
        sections = enhancer._build_markdown_sections(
            sector_fund_flow={"inflow": [], "outflow": []},
            diffusion_summary={},
            turnover_summary={},
            quant_environment={
                "environment": {},
                "summary": "未检测到明显的量化横行特征",
                "modes": [],
                "action": "按传统模式处理",
            },
        )

        rendered = "\n".join(sections)
        self.assertIn("**当前环境**: 未检测到明显的量化横行特征", rendered)
        self.assertIn("**动作建议**: 按传统模式处理", rendered)
        self.assertNotIn("**当前环境**: 待识别", rendered)

    def test_normalizes_raw_yuan_turnover_to_yi_without_dividing_yi_fields(self):
        result = enhancer.build_sector_internal_analysis_data(
            {"inflow": [{"name": "机器人"}]},
            market_data={
                "sector_stocks": {
                    "机器人": [
                        {"code": "300001", "name": "原始成交额A", "成交额": 12_000_000_000, "change_pct": 2.0},
                        {"code": "300002", "name": "亿字段B", "amount_yi": 80, "change_pct": 1.0},
                    ]
                }
            },
        )

        leaders = result["sectors"][0]["relative_position"]["leaders"]
        self.assertEqual([stock["volume"] for stock in leaders], [120.0, 80.0])

    def test_combined_support_uses_majority_instead_of_single_weak_stock(self):
        result = enhancer.build_sector_internal_analysis_data(
            {"inflow": [{"name": "机器人"}]},
            market_data={
                "sector_stocks": {
                    "机器人": [
                        {
                            "code": "300001",
                            "name": "强承接A",
                            "volume": 140,
                            "change_pct": 6.0,
                            "is_new_high": True,
                            "intraday_high": 10.0,
                            "close": 9.8,
                        },
                        {
                            "code": "300002",
                            "name": "强承接B",
                            "volume": 90,
                            "change_pct": 6.5,
                            "is_new_high": True,
                            "intraday_high": 12.0,
                            "close": 11.8,
                        },
                        {
                            "code": "300003",
                            "name": "弱承接C",
                            "volume": 50,
                            "change_pct": 7.0,
                            "is_new_high": True,
                            "intraday_high": 8.0,
                            "close": 6.5,
                        },
                    ]
                }
            },
        )

        self.assertEqual(result["sectors"][0]["elastic_carrier"]["intraday_support"], "强")


if __name__ == "__main__":
    unittest.main()
