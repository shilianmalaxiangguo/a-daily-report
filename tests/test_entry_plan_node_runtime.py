import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from domains.execution_chain.entry_plan_node_runtime import run_entry_plan_nodes
from domains.execution_chain.entry_plan_nodes.conclusion import build_entry_plan_conclusion_node
from domains.execution_chain.entry_plan_nodes.stop_anchor import build_entry_plan_stop_anchor_node
from execution.entry_cycle_stop_runtime import build_entry_cycle_stop_policy


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

    def test_legacy_conditional_gate_renders_50_attack_window_not_30_trial(self):
        base_context = {
            "position_level": "二档（防守档）",
            "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
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

        self.assertIn("50%标准进攻", stop_lines)
        self.assertIn("50%标准进攻", conclusion_lines)
        self.assertIn("参与窗口", stop_lines)
        self.assertIn("参与窗口", conclusion_lines)
        self.assertNotIn(_m("30%", "条件试错"), stop_lines)
        self.assertNotIn(_m("30%", "条件试错"), conclusion_lines)
        self.assertNotIn("二档（防守档）", stop_lines)
        self.assertNotIn("二档（防守档）", conclusion_lines)
        self.assertNotIn("二档（防守档）禁止买入", stop_lines)
        self.assertNotIn("禁止任何买入操作", conclusion_lines)

    def test_entry_conclusion_names_layered_participation_windows_not_universal_wait(self):
        context = {
            "position_level": "三档（进攻档）",
            "final_gate": {"can_new_entry": True},
            "keep_group": [],
            "executable_stocks": [{"name": "大唐发电", "code": "601991"}],
            "waiting_stocks": [],
            "untradable_stocks": [],
            "step4_structure_layer_text": "趋势比价链核心，允许围绕参与窗口预演",
            "get_execution_framework_text": lambda: "日线定环境；竞价/开盘前几分钟/回封/60分钟分层参与；30分钟定止损",
        }

        rendered = "\n".join(build_entry_plan_conclusion_node(context)["lines"])

        self.assertIn("竞价/开盘前几分钟/回封/60分钟分层参与", rendered)
        self.assertIn("参与窗口", rendered)
        self.assertIn("30分钟结构止损", rendered)
        self.assertNotIn(_m("即便满足价格条件，也要", "等60", "分钟确认后再买"), rendered)
        self.assertNotIn(_m("买点必须", "等60分钟"), rendered)

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

    def test_stop_anchor_surfaces_all_april_stop_mode_labels_with_risk_floor(self):
        stop_cases = [
            ("中嘉博创", 4.35, "structure_repair_band", "结构修复带"),
            ("博杰股份", 86.90, "structure_band", "结构容忍带"),
            ("龙蟠科技", 25.05, "structure_band", "结构容忍带"),
            ("甘肃能源", 8.00, "reclaim_failure_exit", "关键区失败降级"),
            ("津药药业", 6.97, "a_kill_exit", "A杀出清"),
            ("石大胜华", 98.52, "time_stop_or_downgrade", "时间止损/降级"),
        ]
        executable_stocks = []
        for name, entry_price, stop_mode, expected_label in stop_cases:
            policy = build_entry_cycle_stop_policy(
                entry_price,
                {"effective_stop": round(entry_price * 0.97, 2), "hard_stop": round(entry_price * 0.95, 2)},
                {"recommended_stop_mode": stop_mode},
            )
            self.assertEqual(policy.get("stop_mode_label"), expected_label)
            executable_stocks.append(
                {
                    "name": name,
                    "entry_price": entry_price,
                    "minute_plan": {
                        "confirm_price_60m": entry_price,
                        "entry_cycle_stop_policy": policy,
                    },
                    "stop_plan": {"effective_stop": round(entry_price * 0.97, 2)},
                }
            )

        context = {
            "position_level": "二档（防守档）",
            "final_gate": {"can_new_entry": True},
            "build_stop_execution_plan": lambda *args, **kwargs: {},
            "build_trade_price_focus": lambda minute_plan, stop_plan: {
                "key_zone_display": "结构带",
                "execution_stop_display": "30分钟结构",
                "hard_stop_display": "最晚硬止损",
            },
            "executable_stocks": executable_stocks,
        }

        rendered = "\n".join(build_entry_plan_stop_anchor_node(context)["lines"])

        self.assertIn("止损模式", rendered)
        for _, _, _, expected_label in stop_cases:
            self.assertIn(expected_label, rendered)
        self.assertIn("固定-5%只作为风险底线", rendered)
        self.assertIn("最晚硬止损", rendered)
        self.assertNotIn("-5%清仓", rendered)


if __name__ == "__main__":
    unittest.main()
