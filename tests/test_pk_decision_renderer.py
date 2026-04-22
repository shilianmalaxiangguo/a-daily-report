import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.pk_decision_renderer import render_pk_decision_section


class PkDecisionRendererTest(unittest.TestCase):
    def test_render_pk_section_with_single_executable_candidate(self):
        lines = render_pk_decision_section(
            {
                "decision_stack_order_text": "环境 -> 主线 -> EV",
                "scored_executable_stocks": [
                    {
                        "name": "军工一号",
                        "permission_label": "执行权",
                        "decision_stack": {
                            "environment_score": 9,
                            "mainline_score": 8,
                            "memory_score": 7,
                            "trigger_score": 8,
                            "tradability_score": 7,
                            "ev_score": 8,
                        },
                    }
                ],
                "pk_candidates": [
                    {
                        "name": "军工一号",
                        "code": "000001",
                        "win_rate": 0.62,
                        "r_reward_ratio": 2.4,
                        "ev": 1.86,
                        "signal": None,
                    }
                ],
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "display_pending_candidates": [],
                "display_observation_candidates": [],
                "conclusion_lines": [
                    "**Step 4.5 结论**:",
                    "- **如果要买只买谁**: 军工一号(000001)",
                    "- **出手时怎么做**: 明日仅在60分钟确认后按条件触发买入",
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### Step 4.5 - PK决胜局（期望值模型）", rendered)
        self.assertIn("**Step 4.5.0 决策栈排序**（环境 -> 主线 -> EV）:", rendered)
        self.assertIn("| 军工一号 | 9 | 8 | 7 | 8 | 7 | 8 | 执行权 |", rendered)
        self.assertIn("**✅ 明天唯一能买的那只**: 军工一号(000001)", rendered)
        self.assertIn("**Step 4.5 结论**:", rendered)


if __name__ == "__main__":
    unittest.main()
