import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.positioning_nodes import render_positioning_section


class PositioningNodeRuntimeTest(unittest.TestCase):
    def test_render_positioning_section_can_render_only_enabled_nodes(self):
        lines = render_positioning_section(
            {
                "enabled_node_keys": ["header", "environment_status", "state_basis"],
                "compact": False,
                "display_position_level": "二档（防守档）",
                "display_operation_state": "观察态",
                "display_position_reason": "中枢内震荡且市场偏弱，应清仓或极轻仓观望",
                "get_execution_framework_text": lambda: "日线定环境，60分钟定买点，30分钟定止损",
                "market_zhongshu": {
                    "success": True,
                    "zhongshu_list": [
                        {"start_date": "2026-04-14", "end_date": "2026-04-22", "zg": 11.00, "zd": 10.00}
                    ],
                    "current_zhongshu": {"start_date": "2026-04-14", "end_date": "2026-04-22"},
                    "latest_structure_segment": {},
                    "structure_segments": [],
                    "signal": {
                        "status": "➖ 中枢内震荡",
                        "signal_type": "中枢震荡",
                        "zd": 10.00,
                        "zg": 11.00,
                        "today_price": 10.50,
                        "dist_to_zg": -0.045,
                        "comparison_result": "仍在中枢内",
                    },
                },
                "ascii_diagram": "test-diagram",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 📈 明天仓位怎么放（基于日线结构中枢）", rendered)
        self.assertIn("### 🟡 明日市场环境：二档（防守档） / 观察态", rendered)
        self.assertIn("**状态依据**：中枢内震荡且市场偏弱，应清仓或极轻仓观望", rendered)
        self.assertNotIn("**ASCII结构图**", rendered)
        self.assertNotIn("**识别出 1 个结构中枢**", rendered)


if __name__ == "__main__":
    unittest.main()
