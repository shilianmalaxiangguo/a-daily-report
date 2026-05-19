import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.execution_chain_overview_nodes import render_execution_chain_overview_section


class ExecutionChainOverviewNodesTest(unittest.TestCase):
    def test_render_execution_chain_overview_section_can_render_only_enabled_nodes(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": 1.23,
                "market_trend": "强分歧修复",
                "primary_mainline": "军工",
                "enabled_node_keys": ["header", "market_summary"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 十三、统一执行链（狙击手视角）", rendered)
        self.assertIn("### 总-市场整体判断", rendered)
        self.assertIn("- **基准指数**: 中证全指涨跌幅+1.23%", rendered)
        self.assertNotIn("### 分-六步决策路径", rendered)

    def test_render_execution_chain_overview_section_does_not_call_primary_mainline_when_attack_evidence_is_chaotic(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": -1.23,
                "market_trend": "大幅下跌",
                "primary_mainline": "半导体",
                "enabled_node_keys": ["header", "market_summary"],
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
        self.assertIn("- **市场特征**: 大幅下跌，多方向局部活跃但资金未明显胜出", rendered)
        self.assertNotIn("主攻线半导体领涨", rendered)


if __name__ == "__main__":
    unittest.main()
