import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_analysis_builder import build_market_and_sector_analysis_contract


class MarketAnalysisBuilderTest(unittest.TestCase):
    def test_build_market_and_sector_analysis_contract_can_render_only_enabled_nodes(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={
                "market_status": "震荡修复",
                "risk_sectors": [{"name": "地产", "risk_level": "high", "net_outflow": 12.5, "change": -2.13}],
                "hot_sectors": [("军工", 5), ("航空", 3), ("机器人", 2)],
            },
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={"sector_name": "军工"},
            main_sectors_info=[],
            secondary_sectors_info=[{"name": "机器人", "zt_count": 6, "change": 2.1, "net_inflow": 4.2}],
            ai_group_concepts_into_chains=lambda concepts: {"军工链": ["军工", "航空"], "机器人链": ["机器人"]},
            enabled_node_keys=["header", "market_state", "risk_sectors"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 八、市场与板块分析", rendered)
        self.assertIn("### 1. 市场整体状态", rendered)
        self.assertIn("### 4. 风险板块分析", rendered)
        self.assertNotIn("### 2. 主线板块分析", rendered)
        self.assertNotIn("### 3. 次强板块分析", rendered)
        self.assertNotIn("### 5. 市场关注度分析", rendered)

    def test_build_market_and_sector_analysis_contract_renders_mainline_and_risk(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={
                "market_status": "震荡修复",
                "risk_sectors": [{"name": "地产", "risk_level": "high", "net_outflow": 12.5, "change": -2.13}],
                "hot_sectors": [("军工", 5), ("航空", 3), ("机器人", 2)],
            },
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={"sector_name": "军工"},
            main_sectors_info=[],
            secondary_sectors_info=[{"name": "机器人", "zt_count": 6, "change": 2.1, "net_inflow": 4.2}],
            ai_group_concepts_into_chains=lambda concepts: {"军工链": ["军工", "航空"], "机器人链": ["机器人"]},
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 八、市场与板块分析", rendered)
        self.assertIn("- **现在是什么情况**: 震荡修复", rendered)
        self.assertIn("**当前主线**: 军工", rendered)
        self.assertIn("**次强候选板块**", rendered)
        self.assertIn("🔴高风险", rendered)
        self.assertIn("**热榜关注产业链**", rendered)
        self.assertTrue(any(log["step"] == "render.market_and_sector_analysis" for log in result["module_logs"]))

    def test_build_market_and_sector_analysis_contract_renders_mainline_candidate_evidence(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={"market_status": "震荡修复"},
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={"sector_name": "半导体"},
            main_sectors_info=[
                {"name": "半导体", "zt_count": 4, "change": 2.85, "net_inflow": 184.0},
                {
                    "name": "共封装光学(CPO)",
                    "zt_count": 0,
                    "change": 1.43,
                    "net_inflow": 84.63,
                    "net_inflow_source": "concept_member_moneyflow",
                },
            ],
            secondary_sectors_info=[],
            ai_group_concepts_into_chains=lambda concepts: {},
            enabled_node_keys=["mainline"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**当前主线**: 半导体", rendered)
        self.assertIn("**主线候选证据**", rendered)
        self.assertIn("**共封装光学(CPO)**: 涨停0只，涨幅+1.43%，净流入84.6亿", rendered)

    def test_build_market_and_sector_analysis_contract_uses_adopted_mainline_label(self):
        result = build_market_and_sector_analysis_contract(
            data={
                "total_turnover": 29246.59,
                "mainline_turnover_summary": {
                    "current_mainline": "国产芯片替代",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "国产芯片替代",
                        "confirmation_evidence": "国产芯片替代资金净流入靠前，涨停和高标更集中",
                    },
                },
            },
            market_analysis={"market_status": "小幅上涨"},
            sh_change=0.87,
            indices={"深证成指": {"涨跌幅": 2.30}, "创业板指": {"涨跌幅": 2.84}},
            exit_analysis={"sector_name": "元件"},
            main_sectors_info=[{"name": "元件", "zt_count": 30, "change": 7.85, "net_inflow": 174.0}],
            secondary_sectors_info=[],
            ai_group_concepts_into_chains=lambda concepts: {},
            enabled_node_keys=["mainline"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**当前主线**: 国产芯片替代", rendered)
        self.assertNotIn("**当前主线**: 元件", rendered)

    def test_build_market_and_sector_analysis_contract_marks_missing_secondary_fund_flow(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={"market_status": "震荡修复"},
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={},
            main_sectors_info=[],
            secondary_sectors_info=[
                {
                    "name": "共封装光学(CPO)",
                    "zt_count": 0,
                    "change": 1.43,
                    "change_source": "hot_plate",
                    "net_inflow": 0.0,
                    "net_inflow_available": False,
                }
            ],
            ai_group_concepts_into_chains=lambda concepts: {},
            enabled_node_keys=["secondary"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**次强候选板块**", rendered)
        self.assertIn("**共封装光学(CPO)**: 涨停0只，涨幅+1.43%，净流入未匹配", rendered)
        self.assertNotIn("净流入0.0亿", rendered)

    def test_build_market_and_sector_analysis_contract_renders_event_driven_risk_line(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={
                "market_status": "震荡修复",
                "risk_sectors": [
                    {
                        "name": "次新股",
                        "risk_level": "high",
                        "risk_source": "stock_risk_event",
                        "trigger_stock": "大普微",
                        "trigger_code": "301666",
                        "reason": "大普微触发异常波动：股票交易异常波动，停牌核查。",
                        "action": "只做风险观察，不追次新一致加速",
                    }
                ],
            },
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={},
            main_sectors_info=[],
            secondary_sectors_info=[],
            ai_group_concepts_into_chains=lambda concepts: {},
            enabled_node_keys=["risk_sectors"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**次新股**: 大普微(301666)触发风险预告", rendered)
        self.assertIn("停牌核查", rendered)
        self.assertIn("只做风险观察，不追次新一致加速", rendered)
        self.assertNotIn("净流出0.0亿", rendered)

    def test_build_market_and_sector_analysis_contract_renders_st_resume_experience_warning(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={
                "market_status": "震荡修复",
                "risk_sectors": [
                    {
                        "name": "全市场",
                        "risk_level": "high",
                        "risk_source": "st_resume_experience",
                        "trigger_count": 2,
                        "trigger_stocks": ["*ST样本A(000001)", "ST样本B(000002)"],
                        "reason": "2只突发ST复牌，经验上容易触发量化/风控卖出，明日有4000+下跌风险。",
                        "action": "降低明日主动出手预期，先看跌停/ST扩散是否钝化",
                    }
                ],
            },
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={},
            main_sectors_info=[],
            secondary_sectors_info=[],
            ai_group_concepts_into_chains=lambda concepts: {},
            enabled_node_keys=["risk_sectors"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**全市场**: 2只突发ST复牌", rendered)
        self.assertIn("4000+下跌风险", rendered)
        self.assertIn("降低明日主动出手预期", rendered)
        self.assertNotIn("净流出0.0亿", rendered)

    def test_build_market_and_sector_analysis_contract_downgrades_mainline_when_attack_evidence_is_chaotic(self):
        result = build_market_and_sector_analysis_contract(
            data={
                "total_turnover": 33880,
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            },
            market_analysis={"market_status": "大幅下跌"},
            sh_change=-1.52,
            indices={"深证成指": {"涨跌幅": -2.14}, "创业板指": {"涨跌幅": -2.16}},
            exit_analysis={"sector_name": "半导体"},
            main_sectors_info=[],
            secondary_sectors_info=[],
            ai_group_concepts_into_chains=lambda concepts: {},
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**当前主线**: 暂无确认主线", rendered)
        self.assertIn("> 多方向局部活跃但资金未明显胜出", rendered)
        self.assertNotIn("**当前主线**: 半导体", rendered)

    def test_build_market_and_sector_analysis_contract_keeps_high_turnover_weak_breadth_wording_consistent(self):
        result = build_market_and_sector_analysis_contract(
            data={
                "total_turnover": 29170.74,
                "market_stats": {"up_count": 2375, "down_count": 3003},
                "zt_pool": [{"code": "000001"}] * 101,
                "dt_pool": [{"code": "000002"}] * 53,
            },
            market_analysis={"market_status": "震荡整理"},
            sh_change=-0.09,
            indices={"深证成指": {"涨跌幅": -0.20}, "创业板指": {"涨跌幅": -0.36}},
            exit_analysis={},
            main_sectors_info=[],
            secondary_sectors_info=[],
            ai_group_concepts_into_chains=lambda concepts: {},
            enabled_node_keys=["market_state"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("- **量能水平**: 29170.74亿元，量能充沛，但赚钱效应不足", rendered)


if __name__ == "__main__":
    unittest.main()
