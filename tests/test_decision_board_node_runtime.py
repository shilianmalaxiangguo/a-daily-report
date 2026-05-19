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


if __name__ == "__main__":
    unittest.main()
