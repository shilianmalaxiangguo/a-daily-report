import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.decision_board_nodes import render_decision_board_section


class DecisionBoardNodeRuntimeTest(unittest.TestCase):
    def test_render_decision_board_section_can_render_only_enabled_nodes(self):
        lines = render_decision_board_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_section", "risk_section"],
                "high_board_count": 2,
                "exit_analysis": {
                    "sector_name": "军工",
                },
                "main_sectors": ["军工"],
                "dt_count": 6,
                "turnover": 6800,
                "rise_fall_ratio": 0.42,
                "up_count": 900,
                "down_count": 2100,
                "abnormal_risk": [{"code": "000001"}],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 一、核心结论（决策看板）", rendered)
        self.assertIn("### 🎯 主线方向", rendered)
        self.assertIn("- **核心主攻线**: 军工", rendered)
        self.assertIn("### ⚠️ 明天要防什么", rendered)
        self.assertIn("跌停数较多（6只）", rendered)
        self.assertNotIn("### 💰 仓位决策", rendered)
        self.assertNotIn("<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->", rendered)

    def test_render_decision_board_section_downgrades_mainline_when_attack_evidence_is_chaotic(self):
        lines = render_decision_board_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_section"],
                "high_board_count": 2,
                "exit_analysis": {"sector_name": "半导体"},
                "main_sectors": ["半导体"],
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **核心主攻线**: 暂无确认主攻线", rendered)
        self.assertIn("- **主线确认**: 多方向局部活跃但资金未明显胜出", rendered)
        self.assertNotIn("- **核心主攻线**: 半导体", rendered)

    def test_zero_participation_labels_positive_mainline_as_research_only(self):
        lines = render_decision_board_section(
            {
                "compact": False,
                "enabled_node_keys": ["positioning_section"],
                "position_level": "0%不参与",
                "overall_level": "黄灯",
                "exit_analysis": {
                    "overall_action": "主升强化，优先做核心",
                },
                "final_gate": {
                    "can_new_entry": False,
                    "operation_state": "撤退态",
                    "final_action": "明日不新增参与",
                },
                "display_position_reason": "整体环境条件未满足",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **主线状态**: 黄灯（局部主线偏强，仅作研究证据）", rendered)
        self.assertNotIn("主升强化，优先做核心", rendered)

    def test_risk_section_keeps_failed_limit_down_source_pending(self):
        lines = render_decision_board_section(
            {
                "compact": False,
                "enabled_node_keys": ["risk_section"],
                "dt_count": None,
                "dt_count_available": False,
                "turnover": 25598.98,
                "rise_fall_ratio": 6.44,
                "up_count": 4691,
                "down_count": 728,
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("跌停事实待确认", rendered)
        self.assertNotIn("暂无明显风险信号", rendered)

    def test_render_decision_board_section_uses_adopted_mainline_label(self):
        lines = render_decision_board_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_section"],
                "high_board_count": 2,
                "exit_analysis": {"sector_name": "元件"},
                "main_sectors": ["元件"],
                "mainline_turnover_summary": {
                    "current_mainline": "国产芯片替代",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "国产芯片替代",
                        "confirmation_evidence": "国产芯片替代资金净流入靠前，涨停和高标更集中",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **核心主攻线**: 国产芯片替代", rendered)
        self.assertNotIn("- **核心主攻线**: 元件", rendered)


if __name__ == "__main__":
    unittest.main()
