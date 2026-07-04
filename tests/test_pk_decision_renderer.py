import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PERMISSION_LABEL = "参与资格"

from report.pk_decision_renderer import render_pk_decision_section


class PkDecisionRendererTest(unittest.TestCase):
    def test_render_pk_section_with_single_executable_candidate(self):
        lines = render_pk_decision_section(
            {
                "stage_label": "Step 5",
                "stage_title": "PK决胜局（期望值模型）",
                "decision_stack_order_text": "环境 -> 主线 -> EV",
                "scored_executable_stocks": [
                    {
                        "name": "军工一号",
                        "permission_label": PERMISSION_LABEL,
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
                "position_level": "50%条件执行",
                "display_pending_candidates": [],
                "display_observation_candidates": [],
                "conclusion_lines": [
                    "**结论**:",
                    "- **如果要买只买谁**: 军工一号(000001)",
                    "- **出手时怎么做**: 明日仅在参与窗口确认后按条件触发",
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### Step 5 - PK决胜局（期望值模型）", rendered)
        self.assertIn("> **先看结论**：真允许出手时，只保留唯一动作；不允许时，只保留观察。", rendered)
        self.assertIn("> **只看什么**：环境、主线、触发、可交易性和历史复盘表现。", rendered)
        self.assertIn("**决策栈排序**（环境 -> 主线 -> EV）:", rendered)
        self.assertIn("| 军工一号 | 9 | 8 | 7 | 8 | 7 | 8 | 参与资格 |", rendered)
        self.assertIn("**✅ 明日执行对象**: 军工一号(000001)", rendered)
        self.assertIn("**结论**:", rendered)
        self.assertNotIn("PK公式", rendered)
        self.assertNotIn("为什么这么选", rendered)

    def test_render_pk_section_only_prints_no_new_position_banner_once(self):
        lines = render_pk_decision_section(
            {
                "stage_label": "Step 5",
                "stage_title": "PK决胜局（期望值模型）",
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "observation_lines": [
                    "**观察优先对象**: 军工观察(000002)",
                    "- **原因**: 先看承接",
                ],
                "conclusion_lines": ["**结论**:", "- **明天能不能开仓**: 不开新仓"],
            }
        )

        rendered = "\n".join(lines)
        self.assertEqual(rendered.count("**⛔ 当前先不开新仓**: 0%不参与，本轮不做PK出手结论。"), 1)

    def test_render_pk_section_can_render_only_enabled_nodes(self):
        lines = render_pk_decision_section(
            {
                "stage_label": "Step 5",
                "stage_title": "PK决胜局（期望值模型）",
                "decision_stack_order_text": "环境 -> 主线 -> EV",
                "scored_executable_stocks": [
                    {
                        "name": "军工一号",
                        "permission_label": PERMISSION_LABEL,
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
                "conclusion_lines": ["**结论**:", "- **如果要买只买谁**: 军工一号(000001)"],
                "enabled_node_keys": ["overview", "decision_stack", "conclusion"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### Step 5 - PK决胜局（期望值模型）", rendered)
        self.assertIn("**决策栈排序**（环境 -> 主线 -> EV）:", rendered)
        self.assertIn("**结论**:", rendered)
        self.assertNotIn("**✅ 明天唯一能买的那只**", rendered)

    def test_render_pk_section_uses_gap_and_elimination_labels_instead_of_why(self):
        lines = render_pk_decision_section(
            {
                "stage_label": "Step 5",
                "stage_title": "PK决胜局（期望值模型）",
                "decision_stack_order_text": "环境 -> 主线 -> EV",
                "trade_gate_open": True,
                "pk_candidates": [
                    {
                        "name": "军工一号",
                        "code": "000001",
                        "win_rate": 0.62,
                        "r_reward_ratio": 2.4,
                        "ev": 1.86,
                        "profit_space": 0.9,
                        "loss_space": 0.38,
                        "position_pct": 50,
                        "composite_score": 9.8,
                        "signal": None,
                    },
                    {
                        "name": "军工二号",
                        "code": "000002",
                        "win_rate": 0.58,
                        "r_reward_ratio": 2.0,
                        "ev": 1.41,
                        "profit_space": 0.7,
                        "loss_space": 0.35,
                        "position_pct": 30,
                        "composite_score": 8.9,
                        "signal": None,
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **领先差距**: 比第二名高0.90分", rendered)
        self.assertIn("**淘汰对比**:", rendered)
        self.assertIn("**淘汰原因**:", rendered)
        self.assertNotIn("为什么它排第一", rendered)
        self.assertNotIn("为什么没选它", rendered)


if __name__ == "__main__":
    unittest.main()
