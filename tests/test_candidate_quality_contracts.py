import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.candidate_quality_contracts import (
    ACTION_CEILINGS,
    build_candidate_quality_review_record,
    build_candidate_quality_contract,
    build_daily_quality_decision_panel,
    evaluate_sample_protection_change,
    evaluate_candidate_quality_sample,
    evaluate_candidate_quality_sample_contract,
    resolve_intraday_action_update,
)


class CandidateQualityContractsTest(unittest.TestCase):
    def test_daily_panel_uses_chinese_visible_fields_and_account_first_order(self):
        panel = build_daily_quality_decision_panel(
            market_emotion_label="分歧轮动",
            account_attention_load="高",
            holding_priority_action="先处理汇源通信风险仓",
            daily_new_entry_limit=0,
            primary_buy_candidate=None,
            backup_candidate={"name": "晶方科技", "code": "603005"},
            forbidden_actions=["亏损后补仓", "计划外追高"],
            ignored_noise_items=["外盘上涨但A股未确认"],
        )

        self.assertEqual(
            list(panel["visible_fields"].keys()),
            [
                "市场情绪状态",
                "账户后台任务负担",
                "持仓优先动作",
                "今日新增上限",
                "主买对象",
                "补位对象",
                "禁止动作",
                "忽略清单",
            ],
        )
        self.assertEqual(panel["visible_fields"]["主买对象"], "暂无")
        self.assertEqual(panel["visible_fields"]["补位对象"], "晶方科技(603005)")
        self.assertEqual(panel["visible_fields"]["今日新增上限"], 0)
        self.assertEqual(panel["data"]["daily_new_entry_limit"], 0)
        self.assertEqual(panel["data"]["account_attention_load"], "高")

    def test_daily_panel_treats_single_string_items_as_one_item(self):
        panel = build_daily_quality_decision_panel(
            forbidden_actions="计划外追高",
            ignored_noise_items="外盘大涨但A股未确认",
        )

        self.assertEqual(panel["visible_fields"]["禁止动作"], "计划外追高")
        self.assertEqual(panel["visible_fields"]["忽略清单"], "外盘大涨但A股未确认")
        self.assertEqual(panel["data"]["forbidden_actions"], ["计划外追高"])
        self.assertEqual(panel["data"]["ignored_noise_items"], ["外盘大涨但A股未确认"])

    def test_daily_panel_filters_empty_string_items_from_data(self):
        panel = build_daily_quality_decision_panel(
            forbidden_actions=["计划外追高", "", None],
            ignored_noise_items="",
        )

        self.assertEqual(panel["visible_fields"]["禁止动作"], "计划外追高")
        self.assertEqual(panel["visible_fields"]["忽略清单"], "")
        self.assertEqual(panel["data"]["forbidden_actions"], ["计划外追高"])
        self.assertEqual(panel["data"]["ignored_noise_items"], [])

    def test_candidate_contract_separates_selection_entry_risk_cost_and_actions(self):
        contract = build_candidate_quality_contract(
            {
                "name": "晶方科技",
                "code": "603005",
                "current_position_shares": 100,
                "sellable_shares": 0,
                "locked_shares": 100,
            },
            selection_quality_label="高",
            entry_quality_label="不舒服",
            action_ceiling="核心观察",
            risk_items=[{"类型": "B类风险", "证据": "一字后买点太远"}],
            cost_items=[{"类型": "C类成本", "证据": "远离MA/VWAP"}],
            holding_action="不可卖，按明日失效线处理",
            new_entry_action="不追高，等回踩确认",
            recovery_conditions=["回踩不破VWAP", "板块同步回流"],
            removal_conditions=["放量跌破MA7且收不回"],
            latest_review_at="2026-05-25 10:00",
            worst_case_plan={
                "最坏情境": "高开低走",
                "触发条件": "跌破VWAP且无法收回",
                "应对动作": "不新增参与",
            },
        )

        row = contract["visible_row"]
        self.assertEqual(row["候选"], "晶方科技(603005)")
        self.assertEqual(row["当前持仓"], 100)
        self.assertEqual(row["可卖数量"], 0)
        self.assertEqual(row["不可卖数量"], 100)
        self.assertEqual(row["仓位性质"], "已有仓")
        self.assertEqual(row["选股质量"], "高")
        self.assertEqual(row["买点质量"], "不舒服")
        self.assertEqual(row["风险项"], "B类风险：一字后买点太远")
        self.assertEqual(row["成本项"], "C类成本：远离MA/VWAP")
        self.assertEqual(row["动作上限"], "核心观察")
        self.assertEqual(row["持仓动作"], "不可卖，按明日失效线处理")
        self.assertEqual(row["新开仓动作"], "不追高，等回踩确认")
        self.assertIn("回踩不破VWAP", row["恢复条件"])
        self.assertIn("放量跌破MA7且收不回", row["取关条件"])

        self.assertEqual(contract["data"]["selection_quality_label"], "高")
        self.assertEqual(contract["data"]["entry_quality_label"], "不舒服")
        self.assertEqual(contract["data"]["action_ceiling"], "核心观察")
        self.assertEqual(contract["single_stock_fields"]["当前上涨发动机"], "")
        self.assertEqual(contract["single_stock_fields"]["最坏情境"], "高开低走")
        self.assertEqual(contract["single_stock_fields"]["触发条件"], "跌破VWAP且无法收回")
        self.assertEqual(contract["single_stock_fields"]["应对动作"], "不新增参与")

    def test_candidate_contract_keeps_explicit_position_nature_when_present(self):
        contract = build_candidate_quality_contract(
            {
                "name": "上峰水泥",
                "code": "000672",
                "current_position_shares": 400,
                "position_nature": "风险仓",
            },
            action_ceiling="修复观察",
        )

        self.assertEqual(contract["visible_row"]["仓位性质"], "风险仓")

    def test_candidate_contract_treats_single_string_fields_as_one_item(self):
        contract = build_candidate_quality_contract(
            {"name": "字符串样本", "code": "000003"},
            risk_items="风险信息缺失",
            cost_items="远离MA/VWAP",
            recovery_conditions="站回VWAP",
            removal_conditions="跌破MA7",
            action_ceiling="修复观察",
        )

        row = contract["visible_row"]
        self.assertEqual(row["风险项"], "风险信息缺失")
        self.assertEqual(row["成本项"], "远离MA/VWAP")
        self.assertEqual(row["恢复条件"], "站回VWAP")
        self.assertEqual(row["取关条件"], "跌破MA7")
        self.assertEqual(contract["data"]["risk_items"], ["风险信息缺失"])
        self.assertEqual(contract["data"]["cost_items"], ["远离MA/VWAP"])
        self.assertEqual(contract["data"]["recovery_conditions"], ["站回VWAP"])
        self.assertEqual(contract["data"]["removal_conditions"], ["跌破MA7"])

    def test_candidate_contract_filters_empty_string_items_from_data(self):
        contract = build_candidate_quality_contract(
            {"name": "空项样本", "code": "000004"},
            risk_items=["风险信息缺失", "", None],
            cost_items="",
            recovery_conditions=["站回VWAP", ""],
            removal_conditions="",
            action_ceiling="修复观察",
        )

        self.assertEqual(contract["visible_row"]["风险项"], "风险信息缺失")
        self.assertEqual(contract["visible_row"]["成本项"], "")
        self.assertEqual(contract["data"]["risk_items"], ["风险信息缺失"])
        self.assertEqual(contract["data"]["cost_items"], [])
        self.assertEqual(contract["data"]["recovery_conditions"], ["站回VWAP"])
        self.assertEqual(contract["data"]["removal_conditions"], [])

    def test_candidate_contract_treats_string_zero_position_as_no_position(self):
        no_position = build_candidate_quality_contract(
            {
                "name": "空仓样本",
                "code": "000000",
                "current_position_shares": "0",
            },
            action_ceiling="不参与",
        )
        existing_position = build_candidate_quality_contract(
            {
                "name": "已有仓样本",
                "code": "000001",
                "current_position_shares": "100",
            },
            action_ceiling="修复观察",
        )

        self.assertEqual(no_position["visible_row"]["仓位性质"], "无仓")
        self.assertEqual(existing_position["visible_row"]["仓位性质"], "已有仓")

    def test_candidate_contract_normalizes_string_position_numbers_for_visible_row(self):
        contract = build_candidate_quality_contract(
            {
                "name": "已有仓样本",
                "code": "000001",
                "current_position_shares": "100",
                "sellable_shares": "0",
                "locked_shares": "100",
            },
            action_ceiling="修复观察",
        )

        self.assertEqual(contract["visible_row"]["当前持仓"], 100)
        self.assertEqual(contract["visible_row"]["可卖数量"], 0)
        self.assertEqual(contract["visible_row"]["不可卖数量"], 100)

    def test_candidate_contract_keeps_half_position_grade_when_one_lot_over_half_cash(self):
        contract = build_candidate_quality_contract(
            {
                "name": "半仓超配样本",
                "code": "000001",
                "target_position_pct": 50,
                "latest_price": 60,
                "available_cash": 10000,
            },
            action_ceiling="补位",
        )

        row = contract["visible_row"]
        self.assertEqual(row["计划仓位档"], "50%")
        self.assertEqual(row["实际仓位"], "60%")
        self.assertEqual(row["仓位偏离"], "一手颗粒度超配10pct，仍按半仓档")
        self.assertEqual(contract["data"]["target_position_pct"], 50)
        self.assertEqual(contract["data"]["actual_position_pct"], 60)

    def test_candidate_contract_keeps_half_position_grade_when_one_lot_under_half_cash(self):
        contract = build_candidate_quality_contract(
            {
                "name": "半仓低配样本",
                "code": "000002",
                "planned_position_pct": 50,
                "latest_price": 40,
                "available_cash": 10000,
            },
            action_ceiling="补位",
        )

        row = contract["visible_row"]
        self.assertEqual(row["计划仓位档"], "50%")
        self.assertEqual(row["实际仓位"], "40%")
        self.assertEqual(row["仓位偏离"], "一手颗粒度低配10pct，仍按半仓档")
        self.assertEqual(contract["data"]["target_position_pct"], 50)
        self.assertEqual(contract["data"]["actual_position_pct"], 40)

    def test_market_core_stays_in_pool_when_account_cannot_actually_buy(self):
        contract = evaluate_candidate_quality_sample_contract(
            {
                "name": "宏和科技",
                "code": "603256",
                "cycle_identity": "市场核心",
                "quality_role": "主买对象",
                "selection_quality": "高",
                "latest_price": 172.87,
                "available_cash": 10000,
                "can_trade_star_market": False,
            }
        )

        row = contract["visible_row"]
        self.assertEqual(row["候选"], "宏和科技(603256)")
        self.assertEqual(row["周期身份"], "市场核心")
        self.assertEqual(row["账户状态"], "实际不可买")
        self.assertEqual(row["动作上限"], "主买")
        self.assertEqual(row["新开仓动作"], "账户条件不适配，只观察强度，不参与")
        self.assertEqual(contract["single_stock_fields"]["账户状态"], "实际不可买")
        self.assertEqual(contract["data"]["account_trade_status"], "实际不可买")
        self.assertIn("一手约17287", contract["data"]["account_trade_reason"])

    def test_star_market_candidate_stays_visible_but_actual_unbuyable_without_star_access(self):
        contract = evaluate_candidate_quality_sample_contract(
            {
                "name": "索辰科技",
                "code": "688507",
                "cycle_identity": "弹性核心",
                "quality_role": "核心观察",
                "selection_quality": "高",
                "latest_price": 181.5,
                "available_cash": 10000,
                "can_trade_star_market": False,
            }
        )

        row = contract["visible_row"]
        self.assertEqual(row["候选"], "索辰科技(688507)")
        self.assertEqual(row["周期身份"], "弹性核心")
        self.assertEqual(row["账户状态"], "实际不可买")
        self.assertEqual(row["动作上限"], "核心观察")
        self.assertIn("688不适配", contract["data"]["account_trade_reason"])

    def test_action_ceiling_values_are_fixed_chinese_layers(self):
        self.assertEqual(
            ACTION_CEILINGS,
            ("主买", "补位", "核心观察", "修复观察", "不参与"),
        )
        with self.assertRaises(ValueError):
            build_candidate_quality_contract({"name": "后排票"}, action_ceiling="随便看看")

    def test_jingfang_good_stock_high_cost_keeps_core_watch_without_chasing(self):
        result = evaluate_candidate_quality_sample(
            {
                "name": "晶方科技",
                "code": "603005",
                "selection_quality": "高",
                "entry_cost_state": "高成本",
                "is_core": True,
                "risk_flags": [],
                "cost_flags": ["远离MA/VWAP", "一字后买点太远"],
            }
        )

        self.assertEqual(result["action_ceiling"], "核心观察")
        self.assertEqual(result["selection_quality_label"], "高")
        self.assertEqual(result["entry_quality_label"], "不舒服")
        self.assertIn("不追高", result["new_entry_action"])
        self.assertIn("保护选股资格", result["decision_reason"])

    def test_primary_quality_role_defaults_to_primary_buy_when_risk_and_cost_are_clean(self):
        result = evaluate_candidate_quality_sample(
            {
                "name": "主线核心",
                "code": "000001",
                "quality_role": "主买对象",
                "selection_quality": "高",
                "entry_cost_state": "确认中",
                "is_core": True,
            }
        )

        self.assertEqual(result["action_ceiling"], "主买")
        self.assertIn("主买对象", result["decision_reason"])

    def test_primary_quality_role_still_downgrades_when_key_risk_is_missing(self):
        result = evaluate_candidate_quality_sample(
            {
                "name": "主线核心",
                "code": "000001",
                "quality_role": "主买对象",
                "selection_quality": "高",
                "entry_cost_state": "确认中",
                "is_core": True,
                "risk_flags": ["风险信息缺失"],
            }
        )

        self.assertEqual(result["action_ceiling"], "修复观察")
        self.assertIn("风险信息缺失", result["decision_reason"])

    def test_huiyuan_bad_stock_low_cost_blocks_new_entry(self):
        result = evaluate_candidate_quality_sample(
            {
                "name": "汇源通信",
                "selection_quality": "低",
                "entry_cost_state": "低成本",
                "is_core": False,
                "risk_flags": ["风险信息缺失", "非核心高波动"],
                "cost_flags": ["靠近VWAP", "周K MA5"],
                "current_position_shares": 500,
                "sellable_shares": 100,
            }
        )

        self.assertEqual(result["action_ceiling"], "不参与")
        self.assertIn("不新增参与", result["new_entry_action"])
        self.assertIn("已有仓", result["holding_action"])
        self.assertIn("差票低成本", result["decision_reason"])

    def test_sample_evaluation_treats_string_zero_position_as_no_holding_action(self):
        result = evaluate_candidate_quality_sample(
            {
                "name": "空仓样本",
                "selection_quality": "中",
                "entry_cost_state": "确认中",
                "current_position_shares": "0",
                "sellable_shares": "0",
                "locked_shares": "0",
            }
        )

        self.assertEqual(result["holding_action"], "无仓")

    def test_shengyang_engine_clarification_limits_action(self):
        core_result = evaluate_candidate_quality_sample(
            {
                "name": "圣阳股份",
                "selection_quality": "高",
                "is_core": True,
                "risk_flags": ["当前上涨发动机被澄清"],
                "engine_clarified": True,
            }
        )
        weak_result = evaluate_candidate_quality_sample(
            {
                "name": "圣阳股份",
                "selection_quality": "中",
                "is_core": False,
                "risk_flags": ["当前上涨发动机被澄清"],
                "engine_clarified": True,
            }
        )

        self.assertEqual(core_result["action_ceiling"], "核心观察")
        self.assertIn("发动机澄清", core_result["decision_reason"])
        self.assertEqual(weak_result["action_ceiling"], "不参与")

    def test_shangfeng_holding_rhythm_requires_sellable_quantity_context(self):
        result = evaluate_candidate_quality_sample(
            {
                "name": "上峰水泥",
                "selection_quality": "中",
                "entry_cost_state": "确认中",
                "is_core": False,
                "current_position_shares": 400,
                "sellable_shares": 300,
                "locked_shares": 100,
                "trend_context": "冲高后回踩MA/VWAP",
            }
        )

        self.assertEqual(result["action_ceiling"], "修复观察")
        self.assertIn("可卖300", result["holding_action"])
        self.assertIn("不可卖100", result["holding_action"])
        self.assertIn("MA/VWAP", result["decision_reason"])

    def test_sample_evaluation_can_materialize_candidate_contract_row(self):
        contract = evaluate_candidate_quality_sample_contract(
            {
                "name": "汇源通信",
                "code": "000586",
                "selection_quality": "低",
                "entry_cost_state": "低成本",
                "risk_flags": ["风险信息缺失"],
                "cost_flags": ["靠近VWAP"],
                "current_position_shares": 500,
                "sellable_shares": 100,
                "locked_shares": 400,
            }
        )

        row = contract["visible_row"]
        self.assertEqual(row["候选"], "汇源通信(000586)")
        self.assertEqual(row["选股质量"], "低")
        self.assertEqual(row["买点质量"], "看似便宜")
        self.assertEqual(row["动作上限"], "不参与")
        self.assertIn("不新增参与", row["新开仓动作"])
        self.assertIn("已有仓", row["持仓动作"])
        self.assertIn("风险项：风险信息缺失", row["风险项"])
        self.assertIn("成本项：靠近VWAP", row["成本项"])

    def test_intraday_inheritance_blocks_no_participation_direct_upgrade(self):
        result = resolve_intraday_action_update(
            "不参与",
            daily_new_entry_limit=1,
            risk_clean=True,
            sector_sync=True,
            reclaimed_vwap_or_ma=True,
            volume_healthy=True,
            recovery_hit=True,
            primary_failed=True,
            strongest_same_mainline=True,
            comfortable_entry=True,
        )

        self.assertEqual(result["visible_fields"]["前一晚动作层级"], "不参与")
        self.assertEqual(result["visible_fields"]["盘中动作"], "不参与")
        self.assertEqual(result["visible_fields"]["变化方向"], "保持")
        self.assertFalse(result["data"]["new_entry_allowed"])
        self.assertIn("不能直接升为主买或补位", result["visible_fields"]["原因"])

    def test_core_watch_can_upgrade_to_backup_when_recovery_conditions_hit(self):
        result = resolve_intraday_action_update(
            "核心观察",
            daily_new_entry_limit=1,
            risk_clean=True,
            sector_sync=True,
            reclaimed_vwap_or_ma=True,
            volume_healthy=True,
            recovery_hit=True,
        )

        self.assertEqual(result["visible_fields"]["盘中动作"], "补位")
        self.assertEqual(result["visible_fields"]["变化方向"], "上调")
        self.assertTrue(result["data"]["new_entry_allowed"])
        self.assertIn("恢复条件命中", result["visible_fields"]["原因"])

    def test_repair_watch_upgrades_only_to_core_watch(self):
        result = resolve_intraday_action_update(
            "修复观察",
            daily_new_entry_limit=1,
            strong_line_reclaimed=True,
            sector_returned=True,
            risk_repaired=True,
            risk_clean=True,
            sector_sync=True,
            reclaimed_vwap_or_ma=True,
            volume_healthy=True,
            recovery_hit=True,
        )

        self.assertEqual(result["visible_fields"]["盘中动作"], "核心观察")
        self.assertEqual(result["visible_fields"]["变化方向"], "上调")
        self.assertFalse(result["data"]["new_entry_allowed"])

    def test_backup_can_upgrade_to_primary_when_primary_failed_and_best_substitute(self):
        result = resolve_intraday_action_update(
            "补位",
            daily_new_entry_limit=1,
            primary_failed=True,
            strongest_same_mainline=True,
            comfortable_entry=True,
        )

        self.assertEqual(result["visible_fields"]["盘中动作"], "主买")
        self.assertEqual(result["visible_fields"]["变化方向"], "上调")
        self.assertTrue(result["data"]["new_entry_allowed"])
        self.assertIn("同主线最强替代", result["visible_fields"]["原因"])

    def test_daily_new_entry_limit_zero_blocks_new_entry_upgrade(self):
        result = resolve_intraday_action_update(
            "核心观察",
            daily_new_entry_limit=0,
            risk_clean=True,
            sector_sync=True,
            reclaimed_vwap_or_ma=True,
            volume_healthy=True,
            recovery_hit=True,
        )

        self.assertEqual(result["visible_fields"]["盘中动作"], "核心观察")
        self.assertEqual(result["visible_fields"]["变化方向"], "保持")
        self.assertFalse(result["data"]["new_entry_allowed"])
        self.assertIn("今日新增上限为0", result["visible_fields"]["原因"])

    def test_daily_new_entry_limit_string_zero_blocks_new_entry_upgrade(self):
        result = resolve_intraday_action_update(
            "核心观察",
            daily_new_entry_limit="0",
            risk_clean=True,
            sector_sync=True,
            reclaimed_vwap_or_ma=True,
            volume_healthy=True,
            recovery_hit=True,
        )

        self.assertEqual(result["visible_fields"]["盘中动作"], "核心观察")
        self.assertEqual(result["visible_fields"]["变化方向"], "保持")
        self.assertFalse(result["data"]["new_entry_allowed"])
        self.assertEqual(result["data"]["daily_new_entry_limit"], 0)
        self.assertIn("今日新增上限为0", result["visible_fields"]["原因"])

    def test_daily_new_entry_limit_string_positive_allows_core_watch_upgrade(self):
        result = resolve_intraday_action_update(
            "核心观察",
            daily_new_entry_limit="1",
            risk_clean=True,
            sector_sync=True,
            reclaimed_vwap_or_ma=True,
            volume_healthy=True,
            recovery_hit=True,
        )

        self.assertEqual(result["visible_fields"]["盘中动作"], "补位")
        self.assertEqual(result["visible_fields"]["变化方向"], "上调")
        self.assertTrue(result["data"]["new_entry_allowed"])
        self.assertEqual(result["data"]["daily_new_entry_limit"], 1)

    def test_removal_condition_triggered_downgrades_first(self):
        result = resolve_intraday_action_update(
            "核心观察",
            daily_new_entry_limit=1,
            removal_triggered=True,
            risk_clean=True,
            sector_sync=True,
            reclaimed_vwap_or_ma=True,
            volume_healthy=True,
            recovery_hit=True,
        )

        self.assertEqual(result["visible_fields"]["盘中动作"], "不参与")
        self.assertEqual(result["visible_fields"]["变化方向"], "下调")
        self.assertFalse(result["data"]["new_entry_allowed"])
        self.assertIn("原观察失败", result["visible_fields"]["原因"])

    def test_review_record_keeps_original_decision_actual_outcome_and_attribution(self):
        record = build_candidate_quality_review_record(
            sample_date="2026-05-22",
            candidate={"name": "晶方科技", "code": "603005"},
            market_emotion_label="科技线强分歧后回流",
            selection_quality_snapshot="高：半导体核心辨识度",
            entry_quality_snapshot="不舒服：远离MA/VWAP",
            risk_items_snapshot=["一字后成本太高"],
            cost_items_snapshot=["追高盈亏比不舒服"],
            action_ceiling_snapshot="核心观察",
            holding_action_snapshot="已有1手不可卖，按失效线处理",
            new_entry_action_snapshot="不追高，等回踩确认",
            actual_outcome={"次日": "高开震荡", "3日": "待复盘", "5日": "待复盘", "10日": "待复盘"},
            entry_window_result="计划买点未出现",
            user_deviation="无偏离",
            error_category="买点问题",
            improvement_owner="仅记录",
            sample_protection_result="保护：好票高成本没有被删除视野",
        )

        fields = record["visible_fields"]
        self.assertEqual(
            list(fields.keys()),
            [
                "样本日期",
                "样本",
                "当时市场情绪",
                "当时选股质量",
                "当时买点质量",
                "当时风险项",
                "当时成本项",
                "当时动作上限",
                "当时持仓动作",
                "当时新开仓动作",
                "实际走势",
                "买点是否出现",
                "用户是否偏离",
                "错误原因",
                "改进归因",
                "样本保护结果",
            ],
        )
        self.assertEqual(fields["样本"], "晶方科技(603005)")
        self.assertIn("次日：高开震荡", fields["实际走势"])
        self.assertIn("3日：待复盘", fields["实际走势"])
        self.assertEqual(record["data"]["action_ceiling_snapshot"], "核心观察")
        self.assertNotIn("weight_adjustment", record["data"])

    def test_sample_protection_change_blocks_rule_change_when_core_sample_is_harmed(self):
        result = evaluate_sample_protection_change(
            changed_sample="后排边角样本",
            fixed_samples=["后排边角样本"],
            harmed_protected_samples=["晶方科技：好票高成本被误删核心视野"],
            preserved_samples=["汇源通信：差票低成本仍不新增参与"],
        )

        self.assertEqual(result["visible_fields"]["是否可进入V1"], "否")
        self.assertIn("破坏基础保护样本", result["visible_fields"]["结论"])
        self.assertIn("晶方科技", result["visible_fields"]["受损保护样本"])

    def test_sample_protection_change_allows_record_only_when_protection_is_preserved(self):
        result = evaluate_sample_protection_change(
            changed_sample="汇源通信低位反抽",
            fixed_samples=[],
            harmed_protected_samples=[],
            preserved_samples=[
                "晶方科技：高成本仍保留核心观察",
                "汇源通信：低成本反抽仍不新增参与",
                "上峰水泥：持仓动作和新开仓动作分开",
            ],
        )

        self.assertEqual(result["visible_fields"]["是否可进入V1"], "是")
        self.assertIn("仅记录", result["visible_fields"]["结论"])
        self.assertIn("不自动调权重", result["visible_fields"]["处理动作"])


if __name__ == "__main__":
    unittest.main()
