import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.candidate_execution_contracts import (
    build_candidate_exit_rules,
    build_gem_textbook_front_text,
    build_gem_textbook_next_step_text,
    build_participation_window_from_candidate,
    build_participation_window_policy,
    build_philosophy_constraint_text,
    build_weak_to_strong_context,
    candidate_has_formal_abnormal_setup,
    candidate_is_resilient_abnormal,
    format_holding_window_text,
    get_setup_execution_contract,
    get_setup_priority_score,
    infer_risk_level_from_abnormal_follow_state,
    is_bridge_priority_setup,
    map_setup_id_to_signal_type,
    resolve_candidate_follow_state,
    resolve_candidate_setup_id,
)


class CandidateExecutionContractsTest(unittest.TestCase):
    def test_gem_textbook_text_and_exit_rules_are_built_from_candidate_contract(self):
        candidate = {
            "watch_source": "gem_breathing_20cm",
            "textbook_label": "A级教材",
            "textbook_profile": {
                "last_active_date": "2026-04-20",
                "total_active_count": 4,
                "tight_count": 3,
                "loose_count": 1,
            },
            "setup_signal_id": "burst_digest",
            "follow_state": "缩量消化",
            "stop_loss": 11.8,
        }

        front_text = build_gem_textbook_front_text(
            candidate,
            {"target_position_pct": 30, "trigger_text": "首个60分钟确认"},
        )
        next_step = build_gem_textbook_next_step_text(
            candidate,
            {"target_position_pct": 30, "trigger_text": "首个60分钟确认"},
        )
        rules = build_candidate_exit_rules(candidate, {"effective_stop": 12.34})

        self.assertIn("A级教材", front_text)
        self.assertIn("参考样本：东山精密", front_text)
        self.assertEqual(next_step, "当前已进入30%条件试错候选，首个60分钟确认后才允许试错")
        self.assertEqual(rules["holding_days_min"], 2)
        self.assertEqual(rules["holding_days_max"], 4)
        self.assertEqual(rules["profit_take_pct"], 0.04)
        self.assertIn("12.34", rules["defensive_exit_rule"])
        self.assertEqual(format_holding_window_text(2, 4), "2-4天")

    def test_candidate_setup_contracts_score_signal_and_weak_to_strong_state(self):
        candidate = {
            "name": "军工一号",
            "code": "000001",
            "sector": "军工",
            "core_level": "主线核心",
            "setup_signal_id": "burst_hold",
            "follow_state": "跌不下去",
        }

        context = build_weak_to_strong_context(
            candidate,
            mainline_name="军工",
            state_machine_snapshot={"energy_state": "扩张确认", "pulse_stage": "进攻"},
        )

        self.assertEqual(resolve_candidate_setup_id(candidate), "burst_hold")
        self.assertEqual(resolve_candidate_follow_state(candidate), "跌不下去")
        self.assertTrue(candidate_has_formal_abnormal_setup(candidate))
        self.assertTrue(candidate_is_resilient_abnormal(candidate))
        self.assertTrue(is_bridge_priority_setup(candidate, "军工"))
        self.assertEqual(get_setup_priority_score("burst_hold", "跌不下去"), 92)
        self.assertEqual(get_setup_execution_contract("fresh_abnormal_probe", "新异动待观察")["holding_days_max"], 2)
        self.assertEqual(infer_risk_level_from_abnormal_follow_state("跌不下去"), "🟢 低风险")
        self.assertEqual(map_setup_id_to_signal_type("upper_shadow_reclaim"), "sweet_zone")
        self.assertTrue(context["active"])
        self.assertIn("假弱非真弱", context["summary_text"])

    def test_philosophy_constraint_text_deduplicates_execution_fragments(self):
        text = build_philosophy_constraint_text(
            final_gate={"can_new_entry": True},
            best_stock={"name": "军工一号"},
            watch_anchor=None,
            state_machine_snapshot={"energy_state": "扩张确认", "execution_bias": "allow_execute"},
        )

        self.assertIn("不为新故事切掉旧事实", text)
        self.assertIn("外部风险若已被市场脱敏", text)
        self.assertEqual(text.count("不为新故事切掉旧事实"), 1)

    def test_participation_window_policy_returns_auditable_processing_fields(self):
        policy = build_participation_window_policy(
            "竞价表态 + 回封参与",
            "过快封死就沿电力趋势比价链找低位承接",
        )

        self.assertEqual(policy["required_steps"], ["竞价表态", "开盘前几分钟承接", "回封/打板"])
        self.assertEqual(policy["fallback_state"], "不满足回到0%")
        self.assertEqual(policy["participation_basis"]["auction"], "价格位置 / 匹配金额 / 委托稳定 / 板块同步")
        self.assertEqual(policy["participation_basis"]["first_minutes"], "主动资金继续抬价 / 承接连续")
        self.assertEqual(policy["participation_basis"]["board_or_reseal"], "大单金额持续进入 / 快速回封 / 封单质量改善")
        self.assertEqual(policy["participation_basis"]["missed_entry"], "过快封死就沿电力趋势比价链找低位承接")

        ordinary = build_participation_window_policy("60分钟确认")

        self.assertEqual(ordinary["required_steps"], ["主线确认", "承接", "60分钟确认"])
        self.assertEqual(ordinary["participation_basis"]["structure"], "60分钟确认只服务普通结构，不覆盖强核心快路径")

    def test_participation_window_from_candidate_uses_fast_path_for_core_markers(self):
        self.assertEqual(
            build_participation_window_from_candidate({"pattern": "一字板最强"}),
            "打板/错过",
        )
        self.assertEqual(
            build_participation_window_from_candidate({"core_level": "主线核心"}),
            "竞价表态 + 回封参与",
        )
        self.assertEqual(
            build_participation_window_from_candidate({"sector": "电力"}, is_mainline=True),
            "开盘前几分钟 + 60分钟确认",
        )
        self.assertEqual(build_participation_window_from_candidate({}), "60分钟确认")


if __name__ == "__main__":
    unittest.main()
