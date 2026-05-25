import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.infer import (
    analyze_market_and_sectors,
    resolve_market_mainline_context,
)


class MarketActivityInferAnalysisTest(unittest.TestCase):
    def test_analyze_market_and_sectors_builds_status_mainlines_risk_and_hot_concepts(self):
        result = analyze_market_and_sectors(
            {
                "indices": {
                    "上证指数": {"涨跌幅": 0.8},
                    "深证成指": {"涨跌幅": 0.7},
                    "创业板指": {"涨跌幅": 0.2},
                },
                "sector_fund_flow": {
                    "outflow": [
                        {"name": "地产", "zljlr": -12.5, "zdf": -3.2},
                        {"name": "消费", "zljlr": -5.0, "zdf": -1.0},
                    ]
                },
                "hot_rank_top30": [
                    {"name": "军工一号", "concepts": ["军工", "低空"]},
                    {"name": "军工二号", "concepts": ["军工", "商业航天"]},
                ],
            },
            helpers={
                "_build_unified_sector_strength_rows": lambda data: [
                    {"name": "军工", "role": "main", "unified_score": 88},
                    {"name": "机器人", "role": "secondary", "unified_score": 55},
                    {"name": "低空", "role": "observe", "unified_score": 32},
                ]
            },
        )

        self.assertEqual(result["market_status"], "小幅上涨")
        self.assertEqual(result["main_sectors"][0]["name"], "军工")
        self.assertEqual(result["secondary_sectors"][0]["name"], "机器人")
        self.assertEqual(result["sector_analysis"]["军工"]["unified_score"], 88)
        self.assertEqual(result["risk_sectors"][0]["name"], "地产")
        self.assertEqual(result["risk_sectors"][0]["risk_level"], "medium")
        self.assertEqual(result["hot_sectors"][0], ("军工", 2))

    def test_analyze_market_and_sectors_propagates_new_stock_risk_event_to_theme_line(self):
        result = analyze_market_and_sectors(
            {
                "stock_risk_map": {
                    "301666": {
                        "code": "301666",
                        "risk_flags": ["abnormal_volatility"],
                        "risk_summary": "股票交易异常波动，停牌核查。",
                        "risk_events": [
                            {
                                "risk_type": "abnormal_volatility",
                                "title": "大普微：公司股票将于5月19日停牌核查",
                                "source": "cyberfininvest.news",
                            }
                        ],
                        "source_endpoints": ["cyberfininvest.news"],
                    }
                },
                "new_stock_research_pool": [
                    {
                        "code": "301666",
                        "name": "大普微",
                        "listing_window": "recently_listed",
                        "concept_tags": ["次新股", "存储芯片"],
                    }
                ],
                "sector_fund_flow": {
                    "outflow": [
                        {"name": "地产", "zljlr": -12.5, "zdf": -3.2},
                    ]
                },
            }
        )

        impact = result["risk_theme_impacts"][0]
        self.assertEqual(impact["name"], "次新股")
        self.assertEqual(impact["risk_source"], "stock_risk_event")
        self.assertEqual(impact["trigger_code"], "301666")
        self.assertEqual(impact["trigger_stock"], "大普微")
        self.assertEqual(impact["risk_type"], "abnormal_volatility")
        self.assertIn("停牌核查", impact["reason"])
        self.assertEqual(impact["action"], "只做风险观察，不追次新一致加速")
        self.assertEqual(result["risk_sectors"][0]["name"], "次新股")

    def test_analyze_market_and_sectors_flags_st_resume_as_experience_market_risk(self):
        result = analyze_market_and_sectors(
            {
                "stock_risk_map": {
                    "000001": {
                        "code": "000001",
                        "risk_flags": ["st_warning"],
                        "risk_summary": "*ST样本A突发实施其他风险警示，昨日停牌，今日复牌。",
                        "risk_events": [
                            {
                                "risk_type": "st_warning",
                                "title": "*ST样本A：公司股票实施其他风险警示并复牌",
                            }
                        ],
                    },
                    "000002": {
                        "code": "000002",
                        "risk_flags": ["risk_warning"],
                        "risk_summary": "ST样本B突发其他风险警示，停牌一天后复牌。",
                        "risk_events": [
                            {
                                "risk_type": "risk_warning",
                                "title": "ST样本B：股票交易停牌暨复牌公告",
                            }
                        ],
                    },
                }
            }
        )

        st_impact = result["risk_theme_impacts"][0]
        market_impact = result["systemic_risk_warnings"][0]
        self.assertEqual(st_impact["name"], "ST股")
        self.assertEqual(st_impact["risk_source"], "st_resume_experience")
        self.assertEqual(st_impact["trigger_count"], 2)
        self.assertIn("突发ST", st_impact["reason"])
        self.assertIn("复牌", st_impact["reason"])
        self.assertEqual(market_impact["name"], "全市场")
        self.assertEqual(market_impact["risk_source"], "st_resume_experience")
        self.assertEqual(market_impact["risk_level"], "high")
        self.assertIn("4000+下跌", market_impact["reason"])
        self.assertEqual(result["risk_sectors"][0]["name"], "全市场")
        self.assertEqual(result["risk_sectors"][1]["name"], "ST股")

    def test_resolve_market_mainline_context_forces_top_row_and_extracts_dragons(self):
        result = resolve_market_mainline_context(
            {
                "zt_pool": [
                    {"代码": "000001", "名称": "军工龙头", "所属板块": "军工", "连板数": 3},
                    {"代码": "000002", "名称": "机器人一号", "所属板块": "机器人", "连板数": 1},
                ]
            },
            {
                "main_sectors": [],
                "secondary_sectors": [],
                "unified_sector_rows": [
                    {"name": "军工", "unified_score": 40},
                    {"name": "机器人", "unified_score": 33},
                    {"name": "消费", "unified_score": 20},
                ],
            },
            helpers={"normalize_stock_code": lambda code: str(code or "")},
        )

        self.assertEqual(result["main_sectors_info"][0]["name"], "军工")
        self.assertEqual(result["main_sectors"], ["军工"])
        self.assertEqual(result["secondary_sectors"], ["机器人", "消费"])
        self.assertEqual(result["dragon_stocks"][0]["code"], "000001")
        self.assertEqual(result["dragon_stocks"][0]["lianban"], 3)


if __name__ == "__main__":
    unittest.main()
