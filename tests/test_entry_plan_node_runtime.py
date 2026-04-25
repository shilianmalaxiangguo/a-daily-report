import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.entry_plan_node_runtime import run_entry_plan_nodes
from domains.execution_chain.entry_plan_nodes.conclusion import build_entry_plan_conclusion_node
from domains.execution_chain.entry_plan_nodes.stop_anchor import build_entry_plan_stop_anchor_node


class EntryPlanNodeRuntimeTest(unittest.TestCase):
    def test_run_entry_plan_nodes_aggregates_lines_exports_and_logs_in_order(self):
        def build_first_node(context, node_meta, node_lookup=None):
            self.assertEqual(context.get("seed"), "entry-plan")
            self.assertEqual(node_meta["node_key"], "first")
            return {
                "lines": ["first-line"],
                "exports": {"first_value": 1},
                "module_logs": [{"module": "entry_plan.first", "step": "run", "status": "success", "message": "first ok", "details": {}}],
            }

        def build_second_node(context, node_meta, node_lookup=None):
            self.assertEqual(context.get("first_value"), 1)
            self.assertEqual(node_lookup["first"]["title"], "First Node")
            return {
                "lines": ["second-line"],
                "exports": {"second_value": 2},
                "module_logs": [{"module": "entry_plan.second", "step": "run", "status": "success", "message": "second ok", "details": {}}],
            }

        result = run_entry_plan_nodes(
            [
                {"node_key": "first", "title": "First Node", "builder": build_first_node},
                {"node_key": "second", "title": "Second Node", "builder": build_second_node},
            ],
            {"seed": "entry-plan"},
        )

        self.assertEqual(result["lines"], ["first-line", "second-line"])
        self.assertEqual(result["context"]["first_value"], 1)
        self.assertEqual(result["context"]["second_value"], 2)
        self.assertEqual(result["node_outputs"]["first"]["first_value"], 1)
        self.assertEqual(result["node_outputs"]["second"]["second_value"], 2)
        self.assertEqual([node["node_key"] for node in result["nodes"]], ["first", "second"])
        self.assertTrue(any(log["module"] == "entry_plan.first" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "run.second" for log in result["module_logs"]))

    def test_conditional_defense_gate_does_not_render_absolute_buy_ban(self):
        base_context = {
            "position_level": "二档（防守档）",
            "final_gate": {"can_new_entry": False, "allow_conditional_30": True},
            "build_stop_execution_plan": lambda *args, **kwargs: {},
            "build_trade_price_focus": lambda *args, **kwargs: {},
            "keep_group": [],
            "executable_stocks": [],
            "waiting_stocks": [{"name": "观察股"}],
            "untradable_stocks": [],
            "step4_structure_layer_text": "防守观察，只看主线核心",
            "get_execution_framework_text": lambda: "先60分钟确认，再看30分钟止损",
        }

        stop_lines = "\n".join(build_entry_plan_stop_anchor_node(base_context)["lines"])
        conclusion_lines = "\n".join(build_entry_plan_conclusion_node(base_context)["lines"])

        self.assertIn("10点确认后的30%条件试错", stop_lines)
        self.assertIn("10点确认后的30%条件试错", conclusion_lines)
        self.assertNotIn("二档（防守档）禁止买入", stop_lines)
        self.assertNotIn("禁止任何买入操作", conclusion_lines)

    def test_stop_anchor_renders_entry_cycle_stop_policy_instead_of_uniform_five_percent(self):
        context = {
            "position_level": "二档（防守档）",
            "final_gate": {"can_new_entry": True},
            "build_stop_execution_plan": lambda *args, **kwargs: {},
            "build_trade_price_focus": lambda minute_plan, stop_plan: {
                "key_zone_display": "4.13~4.35",
                "execution_stop_display": "4.13",
                "hard_stop_display": "风险底线",
            },
            "executable_stocks": [
                {
                    "name": "中嘉博创",
                    "entry_price": 4.35,
                    "minute_plan": {
                        "confirm_price_60m": 4.35,
                        "entry_cycle_stop_policy": {
                            "primary_exit_mode": "结构修复带",
                            "report_action_text": "先看修复/再突破，固定-5%只作为风险底线。",
                        },
                    },
                    "stop_plan": {"effective_stop": 4.13},
                },
                {
                    "name": "甘肃能源",
                    "entry_price": 8.00,
                    "minute_plan": {
                        "confirm_price_60m": 8.34,
                        "entry_cycle_stop_policy": {
                            "primary_exit_mode": "关键区失败降级",
                            "report_action_text": "关键区失败就降级，不把未触发-5%当成继续持有理由。",
                        },
                    },
                    "stop_plan": {"effective_stop": 7.60},
                },
                {
                    "name": "石大胜华",
                    "entry_price": 98.52,
                    "minute_plan": {
                        "confirm_price_60m": 98.52,
                        "entry_cycle_stop_policy": {
                            "primary_exit_mode": "时间止损/降级",
                            "report_action_text": "按时间止损/降级处理，不继续按趋势票处理。",
                        },
                    },
                    "stop_plan": {"effective_stop": 93.59},
                },
            ],
        }

        rendered = "\n".join(build_entry_plan_stop_anchor_node(context)["lines"])

        self.assertIn("结构修复带", rendered)
        self.assertIn("关键区失败降级", rendered)
        self.assertIn("时间止损/降级", rendered)
        self.assertNotIn("-5%清仓", rendered)


if __name__ == "__main__":
    unittest.main()
