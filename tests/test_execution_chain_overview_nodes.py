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


if __name__ == "__main__":
    unittest.main()
