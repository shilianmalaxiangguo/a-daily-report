import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from selection.candidate_execution_contracts import (
    build_candidate_exit_rules,
    build_entry_timing_policy,
    build_gem_textbook_front_text,
    build_gem_textbook_next_step_text,
    build_limit_up_inertia_profile,
    build_opportunity_comparison,
    build_participation_window_from_candidate,
    build_participation_window_policy,
    build_philosophy_constraint_text,
    build_risk_reward_plan,
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
            {"target_position_pct": 30, "trigger_text": "09:50-10:10窗口"},
        )
        next_step = build_gem_textbook_next_step_text(
            candidate,
            {"target_position_pct": 30, "trigger_text": "09:50-10:10窗口"},
        )
        rules = build_candidate_exit_rules(candidate, {"effective_stop": 12.34})

        self.assertIn("A级教材", front_text)
        self.assertIn("参考样本：东山精密", front_text)
        self.assertEqual(next_step, "当前已进入50%条件执行，09:50-10:10窗口内满足条件后才允许动手，不满足转为0%不参与")
        self.assertNotIn(_m("3", "0%", "条件", "试错"), front_text)
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

        self.assertEqual(policy["required_steps"], ["交易逻辑确认", "竞价表态", "开盘前几分钟承接", "MA执行锚点", "回封/打板"])
        self.assertEqual(policy["fallback_state"], "不满足回到0%")
        self.assertIn("量能", policy["decision_reason_basis"])
        self.assertIn("MA3/MA5/MA10只优化买卖点", policy["ma_execution_anchor"])
        self.assertEqual(policy["participation_basis"]["auction"], "价格位置 / 匹配金额 / 委托稳定 / 板块同步")
        self.assertEqual(policy["participation_basis"]["first_minutes"], "主动资金继续抬价 / 承接连续")
        self.assertEqual(policy["participation_basis"]["board_or_reseal"], "大单金额持续进入 / 快速回封 / 封单质量改善")
        self.assertEqual(policy["participation_basis"]["missed_entry"], "过快封死就沿电力趋势比价链找低位承接")

        ordinary = build_participation_window_policy("60分钟确认")

        self.assertEqual(ordinary["required_steps"], ["交易逻辑确认", "主线确认", "承接", "09:50-10:10窗口", "MA执行锚点"])
        self.assertEqual(ordinary["participation_basis"]["structure"], "09:50-10:10窗口只服务普通结构，不覆盖强核心快路径")

    def test_participation_window_policy_includes_ma_reversion_probe_for_extreme_conviction(self):
        policy = build_participation_window_policy(
            "竞价表态 + 回封参与",
            "过快封死就沿电力趋势比价链找低位承接",
        )

        self.assertTrue(policy["ma_reversion_probe_allowed"])
        self.assertEqual(policy["ma_reversion_window"], "09:50-10:10")
        self.assertIn("日K MA5/MA10", policy["ma_reversion_probe"])
        self.assertIn("分时黄线", policy["intraday_yellow_line_probe"])
        self.assertIn("MA20", policy["ma20_invalidation"])
        self.assertEqual(policy["tracking_window_trade_days"], 25)
        self.assertIn("MA执行锚点", policy["required_steps"])
        self.assertIn("不能因为MA3/MA5/MA10单独买入", policy["ma_reversion_probe"])

    def test_participation_window_policy_fieldizes_intraday_cross_and_ma_roles(self):
        policy = build_participation_window_policy(
            "竞价表态 + 回封参与",
            "过快封死就沿电力趋势比价链找低位承接",
        )

        self.assertIn("09:50-10:10", policy["intraday_average_line_cross_probe"])
        self.assertIn("价格上穿分时黄色均价线", policy["intraday_average_line_cross_probe"])
        self.assertIn("水下强势修复到0轴", policy["zero_axis_reclaim_probe"])
        self.assertEqual(policy["daily_ma_role_map"]["ma3"], "极度龙头")
        self.assertEqual(policy["daily_ma_role_map"]["ma5"], "强势")
        self.assertEqual(policy["daily_ma_role_map"]["ma10"], "趋势")
        self.assertIn("MA3/MA5/MA10", policy["daily_ma_entry_probe"])
        self.assertIn("不是买入理由", policy["daily_ma_entry_probe"])

    def test_limit_up_inertia_and_risk_reward_separate_limit_up_from_ordinary_rise(self):
        limit_up_policy = build_participation_window_policy(
            "竞价表态 + 回封参与",
            "过快封死就沿电力趋势比价链找低位承接",
            candidate={
                "name": "大唐发电",
                "pattern": "T字板",
                "连板数": 2,
                "tomorrow_strength": 92,
                "ma5": 10.0,
                "ma20": 9.6,
                "limit_up_price": 11.0,
            },
        )
        ordinary_policy = build_participation_window_policy(
            "60分钟确认",
            "确认前快速拉高就跳过",
            candidate={
                "name": "普通上涨股",
                "change_pct": 3.0,
                "tomorrow_strength": 62,
            },
        )

        self.assertEqual(limit_up_policy["limit_up_inertia_level"], "高惯性")
        self.assertGreater(limit_up_policy["limit_up_inertia_score"], ordinary_policy["limit_up_inertia_score"])
        self.assertIn("昨日涨停/连板", limit_up_policy["limit_up_inertia_reason"])
        self.assertEqual(limit_up_policy["next_day_limit_probability_band"], "高于普通上涨样本")
        self.assertEqual(limit_up_policy["risk_reward_state"], "合格")
        self.assertGreaterEqual(limit_up_policy["risk_reward_ratio"], 2.0)
        self.assertIn("2:1", limit_up_policy["risk_reward_plan"])

        self.assertEqual(ordinary_policy["limit_up_inertia_level"], "低惯性")
        self.assertEqual(ordinary_policy["next_day_limit_probability_band"], "接近普通上涨样本")
        self.assertIn("只观察", ordinary_policy["risk_reward_plan"])

    def test_limit_up_inertia_does_not_add_strength_threshold_again_when_lianban_already_in_strength(self):
        profile = build_limit_up_inertia_profile(
            {
                "name": "连板样本",
                "pattern": "涨停",
                "连板数": 2,
                "base_strength_score": 72,
                "tomorrow_strength": 92,
            }
        )

        self.assertEqual(profile["limit_up_inertia_level"], "高惯性")
        self.assertEqual(profile["limit_up_inertia_score"], 92)
        self.assertIn("2连板", profile["limit_up_inertia_dedup"]["suppressed_points"][0]["label"])

    def test_risk_reward_plan_requires_two_to_one_before_ma_reversion_probe(self):
        qualified = build_risk_reward_plan(
            {
                "ma5": 10.0,
                "ma20": 9.6,
                "limit_up_price": 11.0,
            }
        )
        unqualified = build_risk_reward_plan(
            {
                "ma5": 10.0,
                "ma20": 9.2,
                "limit_up_price": 11.0,
            }
        )
        profile = build_limit_up_inertia_profile({"pattern": "涨停", "连板数": 1})

        self.assertEqual(qualified["risk_reward_state"], "合格")
        self.assertEqual(qualified["risk_reward_min_ratio"], 2.0)
        self.assertGreaterEqual(qualified["risk_reward_ratio"], 2.0)
        self.assertEqual(unqualified["risk_reward_state"], "不合格")
        self.assertLess(unqualified["risk_reward_ratio"], 2.0)
        self.assertEqual(profile["limit_up_inertia_level"], "高惯性")

        missing_price = build_risk_reward_plan({})
        self.assertIn("缺少观察位", missing_price["risk_reward_plan"])
        self.assertNotIn("缺少买点", missing_price["risk_reward_plan"])
        self.assertNotIn("当买点", missing_price["risk_reward_plan"])
        invalid_shape = build_risk_reward_plan(
            {
                "ma5": 10.0,
                "ma20": 10.5,
                "limit_up_price": 11.0,
            }
        )
        self.assertIn("观察位、作废线和上方空间", invalid_shape["risk_reward_plan"])
        self.assertNotIn("买点", invalid_shape["risk_reward_plan"])

    def test_opportunity_comparison_keeps_missing_risk_price_at_observation(self):
        comparison = build_opportunity_comparison(
            old_position={
                "name": "华电辽能",
                "code": "600396",
                "shares": 200,
                "old_logic_state": "valid",
            },
            new_target={
                "name": "华天科技",
                "code": "002185",
                "target_role": "sector_anchor",
            },
            requested_participation_pct=100,
        )

        self.assertEqual(comparison["schema_version"], "opportunity_comparison.v1")
        self.assertEqual(comparison["new_target"]["risk_reward_state"], "待计算")
        self.assertEqual(comparison["new_target"]["risk_price_comfort"], "incomplete")
        self.assertFalse(comparison["comparison"]["risk_boundary_controllable"])
        self.assertFalse(comparison["comparison"]["old_position_must_be_released"])
        self.assertEqual(comparison["comparison"]["max_participation_pct"], 0)
        self.assertIn("只保留观察", comparison["comparison"]["final_action"])
        self.assertIn("risk_price", comparison["new_target"]["missing_fields"])

    def test_opportunity_comparison_rejects_stretched_ma_risk_even_for_stronger_target(self):
        comparison = build_opportunity_comparison(
            old_position={
                "name": "华电辽能",
                "code": "600396",
                "shares": 200,
                "old_logic_state": "weakening",
            },
            new_target={
                "name": "华天科技",
                "code": "002185",
                "target_role": "core",
                "strength_evidence": ["半导体资金回流", "板块锚"],
                "probe_entry_price": 20.0,
                "ma5": 18.6,
                "ma10": 18.0,
                "vwap": 19.2,
                "stop_price": 17.4,
                "target_price": 22.0,
            },
            requested_participation_pct=100,
        )

        self.assertEqual(comparison["new_target"]["risk_price_comfort"], "unacceptable")
        self.assertGreaterEqual(comparison["new_target"]["downside_to_ma5_pct"], 5.0)
        self.assertFalse(comparison["comparison"]["risk_boundary_controllable"])
        self.assertEqual(comparison["comparison"]["max_participation_pct"], 0)
        self.assertIn("等待回踩", comparison["comparison"]["final_action"])

    def test_opportunity_comparison_allows_switch_only_when_stronger_and_risk_controlled(self):
        comparison = build_opportunity_comparison(
            old_position={
                "name": "华电辽能",
                "code": "600396",
                "shares": 200,
                "old_logic_state": "weakening",
            },
            new_target={
                "name": "华天科技",
                "code": "002185",
                "line": "半导体",
                "target_role": "core",
                "strength_evidence": ["半导体资金回流", "板块锚", "近新高结构"],
                "entry_window": "09:50-10:10",
                "probe_entry_price": 10.0,
                "ma5": 9.8,
                "ma10": 9.6,
                "vwap": 9.9,
                "stop_price": 9.5,
                "target_price": 11.5,
            },
            requested_participation_pct=100,
        )

        self.assertEqual(comparison["new_target"]["risk_reward_state"], "合格")
        self.assertEqual(comparison["new_target"]["risk_price_comfort"], "comfortable")
        self.assertTrue(comparison["comparison"]["new_target_materially_stronger"])
        self.assertTrue(comparison["comparison"]["old_position_must_be_released"])
        self.assertTrue(comparison["comparison"]["risk_boundary_controllable"])
        self.assertEqual(comparison["comparison"]["max_participation_pct"], 100)
        self.assertIn("先释放旧仓资金", comparison["comparison"]["final_action"])

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
            "开盘前几分钟 + 09:50-10:10窗口",
        )
        self.assertEqual(build_participation_window_from_candidate({}), "09:50-10:10窗口")

    def test_entry_timing_policy_fieldizes_open_ten_tail_and_no_trade(self):
        open_core = build_entry_timing_policy(
            source_tier="extreme_conviction",
            participation_window_type="auction_reseal",
            participation_window="竞价表态 + 回封参与",
        )
        ten_confirm = build_entry_timing_policy(
            source_tier="extreme_conviction",
            participation_window_type="structure_confirm",
            participation_window="60分钟确认",
        )
        tail_exception = build_entry_timing_policy(
            source_tier="extreme_conviction",
            participation_window_type="structure_confirm",
            participation_window="尾盘确认承接后才允许",
        )
        no_trade = build_entry_timing_policy(
            source_tier="crossline_watch",
            participation_window_type="structure_confirm",
            participation_window="只观察，不开新仓",
        )

        self.assertEqual(open_core["source_tier"], "extreme_conviction")
        self.assertEqual(open_core["entry_timing"], "open_core")
        self.assertEqual(open_core["buy_window"], "09:30-09:35")
        self.assertEqual(ten_confirm["entry_timing"], "ten_confirm")
        self.assertEqual(ten_confirm["buy_window"], "09:50-10:10")
        self.assertEqual(tail_exception["entry_timing"], "tail_exception")
        self.assertEqual(tail_exception["buy_window"], "14:30-14:55")
        self.assertEqual(no_trade["source_tier"], "crossline_watch")
        self.assertEqual(no_trade["entry_timing"], "no_trade")
        self.assertEqual(no_trade["buy_window"], "none")

    def test_participation_window_policy_keeps_no_trade_as_observation_only(self):
        policy = build_participation_window_policy(
            "no_trade",
            "只观察，不新增参与",
            candidate={"name": "观察样本"},
        )

        self.assertEqual(policy["participation_window_type"], "no_trade")
        self.assertFalse(policy["auction_required"])
        self.assertFalse(policy["first_minutes_required"])
        self.assertFalse(policy["board_or_reseal_required"])
        self.assertFalse(policy["ordinary_structure_confirm_allowed"])
        self.assertEqual(policy["required_steps"], ["只观察，不新增参与"])
        self.assertEqual(policy["entry_timing"], "no_trade")
        self.assertEqual(policy["buy_window"], "none")
        self.assertFalse(policy["ma_reversion_probe_allowed"])
        self.assertEqual(policy["ma_reversion_window"], "none")
        observation_fields = [
            "auction_script",
            "first_minutes_script",
            "board_script",
            "reseal_script",
            "intraday_yellow_line_probe",
            "intraday_average_line_cross_probe",
            "zero_axis_reclaim_probe",
            "daily_ma_entry_probe",
        ]
        for field in observation_fields:
            with self.subTest(field=field):
                self.assertIn("只观察", policy[field])
                self.assertNotIn("回封/打板", policy[field])
                self.assertNotIn("才允许旧小仓口径", policy[field])
                self.assertNotIn("买入资格", policy[field])


if __name__ == "__main__":
    unittest.main()
