import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PERMISSION_LABEL = "参与资格"

from domains.execution_chain.entry_plan_stage import build_entry_plan_runtime, build_entry_plan_stage
from domains.execution_chain.stage_runtime import build_execution_stage_lookup


class EntryPlanStageTest(unittest.TestCase):
    def test_entry_plan_stage_uses_dynamic_labels_and_exports_execution_candidates(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
                {"stage_key": "risk_review", "title": "明日风险预判"},
                {"stage_key": "entry_plan", "title": "明日买点预计算"},
                {"stage_key": "pk_decision", "title": "PK决胜局（期望值模型）"},
            ]
        )

        result = build_entry_plan_stage(
            {
                "target_date": "2026-04-22",
                "mainline_name": "军工",
                "position_level": "三档（进攻档）",
                "final_gate": {"can_new_entry": True},
                "focus_group": [{"name": "军工一号", "code": "000001", "change": 9.9, "close": 10.0, "volume": 1000}],
                "keep_group": [],
                "delete_group": [],
                "extreme_conviction_list": [{"name": "军工一号", "code": "000001"}],
                "leader_memory_bank": [{"name": "老龙头", "code": "000002"}],
                "market_research_snapshot": {"state_machine": {"leading_line": "军工"}},
                "quant_system_available": False,
                "stop_prior_low_trading_days": 3,
                "normalize_stock_code": lambda code: str(code or "").strip(),
                "get_execution_framework_text": lambda: "先60分钟确认，再看30分钟止损",
                "get_trade_permission": lambda *args, **kwargs: {
                    "permission_label": PERMISSION_LABEL,
                    "permission_reason": "主线最强，可执行",
                    "can_execute": True,
                },
                "fetch_recent_price_bars": lambda code, target_date, lookback_days=4: [],
                "evaluate_live_tradability": lambda stock, target_date, recent_bars=None: {
                    "can_trade": True,
                    "report_day_is_one_word": False,
                },
                "build_intraday_execution_plan": lambda code, target_date, entry_price, signal_type=None, fallback_stop=None: {
                    "confirm_price_60m": 10.5,
                    "confirm_rule_60m": "站上10.50再执行",
                    "stop_plan": {"effective_stop": 9.8},
                },
                "build_stop_execution_plan": lambda entry_price, stop_loss=None, structure_label=None: {
                    "effective_stop": 9.8,
                },
                "enrich_stop_plan_with_reference_anchors": lambda stop_plan, code, target_date, recent_bars=None: stop_plan,
                "build_waiting_stock_plan": lambda *args, **kwargs: {
                    "name": "军工一号",
                    "code": "000001",
                    "reason": "等待信号",
                    "minute_plan": {"confirm_price_60m": 10.5},
                    "stop_plan": {"effective_stop": 9.8},
                },
                "finalize_waiting_candidate": lambda waiting_item, stock, permission: {
                    **waiting_item,
                    "permission_label": permission.get("permission_label", ""),
                },
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "compact_text": "盯10.50与9.80",
                    "key_zone_display": "10.20-10.50",
                    "execution_stop_display": "9.80",
                    "hard_stop_display": "9.50",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("compact_text", "-"),
                "append_price_focus_note": lambda report_lines, price_focus: report_lines.append("  note-execute"),
                "append_observation_price_focus_note": lambda report_lines, price_focus: report_lines.append("  note-watch"),
                "compose_observation_focus_text": lambda confirm_text, price_focus_text: f"{confirm_text} / {price_focus_text}",
                "build_front_structure_layer_text": lambda **kwargs: "环境打开，但只允许唯一动作",
            },
            stage_lookup["entry_plan"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 4 - 明日买点预计算", rendered)
        self.assertIn("> **先看结论**：只给仍有资格的候选预设买点、确认点和止损锚。", rendered)
        self.assertIn("> **怎么执行**：先把价格区间和纪律定好，盘中只按“先09:50-10:10窗口，再看失效价和单笔-5%底线”执行。", rendered)
        self.assertIn("**买点判断**", rendered)
        self.assertIn("**结论**:", rendered)
        self.assertIn("继续进入Step 5", rendered)
        self.assertEqual(len(result["exports"]["executable_stocks"]), 1)
        self.assertEqual(result["exports"]["executable_stocks"][0]["code"], "000001")
        self.assertEqual(result["exports"]["conviction_codes"], {"000001"})
        self.assertEqual(result["exports"]["leader_memory_codes"], {"000002"})
        self.assertEqual(result["exports"]["step4_structure_layer_text"], "环境打开，但只允许唯一动作")
        self.assertTrue(any(log["module"] == "domains.execution_chain.entry_plan_stage" for log in result["module_logs"]))

    def test_entry_plan_runtime_can_render_only_enabled_nodes(self):
        result = build_entry_plan_runtime(
            {
                "target_date": "2026-04-22",
                "mainline_name": "军工",
                "position_level": "三档（进攻档）",
                "final_gate": {"can_new_entry": True},
                "focus_group": [{"name": "军工一号", "code": "000001", "change": 9.9, "close": 10.0, "volume": 1000}],
                "keep_group": [],
                "delete_group": [],
                "extreme_conviction_list": [{"name": "军工一号", "code": "000001"}],
                "leader_memory_bank": [{"name": "老龙头", "code": "000002"}],
                "market_research_snapshot": {"state_machine": {"leading_line": "军工"}},
                "quant_system_available": False,
                "stop_prior_low_trading_days": 3,
                "normalize_stock_code": lambda code: str(code or "").strip(),
                "get_execution_framework_text": lambda: "先60分钟确认，再看30分钟止损",
                "get_trade_permission": lambda *args, **kwargs: {
                    "permission_label": PERMISSION_LABEL,
                    "permission_reason": "主线最强，可执行",
                    "can_execute": True,
                },
                "fetch_recent_price_bars": lambda code, target_date, lookback_days=4: [],
                "evaluate_live_tradability": lambda stock, target_date, recent_bars=None: {
                    "can_trade": True,
                    "report_day_is_one_word": False,
                },
                "build_intraday_execution_plan": lambda code, target_date, entry_price, signal_type=None, fallback_stop=None: {
                    "confirm_price_60m": 10.5,
                    "confirm_rule_60m": "站上10.50再执行",
                    "stop_plan": {"effective_stop": 9.8},
                },
                "build_stop_execution_plan": lambda entry_price, stop_loss=None, structure_label=None: {
                    "effective_stop": 9.8,
                },
                "enrich_stop_plan_with_reference_anchors": lambda stop_plan, code, target_date, recent_bars=None: stop_plan,
                "build_waiting_stock_plan": lambda *args, **kwargs: {
                    "name": "军工一号",
                    "code": "000001",
                    "reason": "等待信号",
                    "minute_plan": {"confirm_price_60m": 10.5},
                    "stop_plan": {"effective_stop": 9.8},
                },
                "finalize_waiting_candidate": lambda waiting_item, stock, permission: {
                    **waiting_item,
                    "permission_label": permission.get("permission_label", ""),
                },
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "compact_text": "盯10.50与9.80",
                    "key_zone_display": "10.20-10.50",
                    "execution_stop_display": "9.80",
                    "hard_stop_display": "9.50",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("compact_text", "-"),
                "append_price_focus_note": lambda report_lines, price_focus: report_lines.append("  note-execute"),
                "append_observation_price_focus_note": lambda report_lines, price_focus: report_lines.append("  note-watch"),
                "compose_observation_focus_text": lambda confirm_text, price_focus_text: f"{confirm_text} / {price_focus_text}",
                "build_front_structure_layer_text": lambda **kwargs: "环境打开，但只允许唯一动作",
            },
            {"label": "Step 4", "title": "明日买点预计算"},
            enabled_node_keys=["overview", "entry_judgement", "conclusion"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 4 - 明日买点预计算", rendered)
        self.assertIn("**买点判断**", rendered)
        self.assertIn("**结论**:", rendered)
        self.assertNotIn("**交易优先级纪律**", rendered)
        self.assertNotIn("**明日止损锚定**", rendered)


if __name__ == "__main__":
    unittest.main()
