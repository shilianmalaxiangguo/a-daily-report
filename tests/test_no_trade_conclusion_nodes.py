import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.no_trade_conclusion_nodes import render_no_trade_conclusion_section


class NoTradeConclusionNodesTest(unittest.TestCase):
    def test_render_no_trade_conclusion_section_can_render_only_enabled_nodes(self):
        lines = render_no_trade_conclusion_section(
            {
                "reason": "跌停扩散",
                "candidate_stage_label": "候选筛选",
                "enabled_node_keys": ["table"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### 最终结论", rendered)
        self.assertIn("| 明日环境预判 | 🔴 极度困难 | 跌停扩散 |", rendered)
        self.assertIn("| 明日核心股 | 无 | 未进入候选筛选 |", rendered)
        self.assertNotIn("**明日计划**", rendered)


if __name__ == "__main__":
    unittest.main()
