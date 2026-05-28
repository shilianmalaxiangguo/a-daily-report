import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from selection.gem_breathing_runtime import (
    build_gem_elasticity_context,
    build_gem_breathing_contract,
    build_gem_breathing_prep_context,
    build_gem_breathing_watch_anchor,
    build_gem_observation_pool,
    build_gem_breathing_textbook_profile,
    classify_20cm_branch,
    discover_all_gem_breathing_candidates,
    discover_filtered_out_gem_breathing_candidates,
    discover_gem_breathing_candidates,
    evaluate_gem_breathing_window,
    is_20cm_stock,
    resolve_candidate_contract_prices,
    should_hide_gem_execution_entry_range,
)


class GemBreathingRuntimeTest(unittest.TestCase):
    def test_build_gem_elasticity_context_requires_matching_mainline(self):
        active = build_gem_elasticity_context(
            {"sector": "军工"},
            mainline_name="军工",
            mainline_anchor={"name": "成飞集成"},
            helpers={"sector_name_matches": lambda left, right: left == right},
        )
        inactive = build_gem_elasticity_context(
            {"sector": "机器人"},
            mainline_name="军工",
            helpers={"sector_name_matches": lambda left, right: left == right},
        )

        self.assertTrue(active["active"])
        self.assertEqual(active["anchor_name"], "成飞集成")
        self.assertIn("白银弹性层", active["reason"])
        self.assertEqual(inactive, {"active": False})

    def test_resolve_candidate_contract_prices_hides_gem_entry_range_before_upgrade(self):
        prices = resolve_candidate_contract_prices(
            {
                "watch_source": "gem_breathing_20cm",
                "position_pct": 0,
                "entry_price": 12.11,
                "entry_range": (11.88, 12.66),
                "minute_plan": {
                    "confirm_price_60m": 12.45,
                    "confirm_support_60m": 11.72,
                },
                "gem_breathing_contract": {
                    "right_side_trigger_price": 12.53,
                    "void_price": 11.55,
                    "reset_breakout_price": 12.8,
                },
            },
            helpers={
                "_safe_float": lambda value, default=0.0: float(value or default),
                "_round_or_none": lambda value, digits=2: None if value in (None, "") else round(float(value), digits),
            },
        )

        self.assertTrue(
            should_hide_gem_execution_entry_range(
                {"watch_source": "gem_breathing_20cm", "position_pct": 0},
                helpers={"_safe_float": lambda value, default=0.0: float(value or default)},
            )
        )
        self.assertIsNone(prices["entry_range_low"])
        self.assertIsNone(prices["entry_range_high"])
        self.assertEqual(prices["observe_anchor_price"], 12.11)
        self.assertEqual(prices["upgrade_trigger_price"], 12.53)
        self.assertEqual(prices["invalidation_price"], 11.55)
        self.assertEqual(prices["reset_breakout_price"], 12.8)

    def test_classify_20cm_branch_allows_attack_50_ready_for_textbook_ready_sample(self):
        result = classify_20cm_branch(
            {
                "code": "300001",
                "sector": "军工",
                "textbook_label": "A级教材",
                "textbook_summary": "近60日出现4次",
                "abnormal_follow_state": "横盘等待",
            },
            mainline_name="军工",
            confirm_price=12.3,
            support_price=11.8,
            feedback_ready=True,
            allow_attack_50_ready=True,
            target_date="2026-04-22",
            mainline_anchor={"name": "成飞集成"},
            helpers={
                "sector_name_matches": lambda left, right: left == right,
                "_build_gem_breathing_prep_context": lambda candidate=None, target_date="", lookback_days=10: {
                    "active": True,
                    "note": "创业板20cm呼吸感预启动。",
                },
            },
        )

        self.assertTrue(result["is_20cm"])
        self.assertTrue(result["allow_watch_pool"])
        self.assertTrue(result["allow_attack_50_ready"])
        self.assertFalse(result["direct_ban"])
        self.assertIn("教材样本", result["reason"])
        self.assertIn("50%标准进攻", result["reason"])
        self.assertNotIn(_m("30%", "条件试错"), result["reason"])

    def test_build_gem_breathing_contract_normalizes_prices_and_upgrade_text(self):
        contract = build_gem_breathing_contract(
            {
                "minute_plan": {
                    "confirm_price_60m": 12.356,
                    "confirm_support_60m": 11.224,
                },
                "entry_range": (11.8, 12.98),
                "holding_days_max": 7,
            },
            helpers={
                "_safe_float": lambda value, default=0.0: float(value or default),
                "_round_or_none": lambda value, digits=2: None if value in (None, "") else round(float(value), digits),
                "STRATEGY_HOLDING_DAYS_MAX": 4,
            },
        )

        self.assertTrue(contract["active"])
        self.assertEqual(contract["contract_kind"], "gem_breathing_20cm")
        self.assertEqual(contract["active_window_days"], 5)
        self.assertEqual(contract["right_side_trigger_price"], 12.36)
        self.assertEqual(contract["void_price"], 11.22)
        self.assertEqual(contract["reset_breakout_price"], 12.98)
        self.assertIn("12.36", contract["upgrade_condition_text"])
        self.assertIn("11.22", contract["upgrade_condition_text"])
        self.assertIn("50%标准进攻", contract["upgrade_condition_text"])
        self.assertNotIn(_m("30%", "条件试错"), contract["upgrade_condition_text"])

    def test_build_gem_breathing_watch_anchor_assembles_waiting_plan_and_contract(self):
        watch_anchor = build_gem_breathing_watch_anchor(
            {
                "code": "300001",
                "name": "弹性龙",
                "close": 12.3,
                "volume": 3.2,
                "note": "盘中观察到呼吸感",
                "tier": "tight",
                "textbook_summary": "近60日出现4次",
            },
            target_date="2026-04-22",
            mainline_name="军工",
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "_safe_float": lambda value, default=0.0: float(value or default),
                "_round_or_none": lambda value, digits=2: None if value in (None, "") else round(float(value), digits),
                "fetch_recent_price_bars": lambda code, target_date, lookback_days=10: [{"close": 12.0, "low": 11.5}],
                "evaluate_live_tradability": lambda gem_candidate, target_date, recent_bars=None: {"report_day_is_one_word": True},
                "build_waiting_stock_plan": lambda payload, target_date, reason="", signal_type="", recent_bars=None: {
                    "entry_price": payload.get("entry_price"),
                    "entry_range": (11.7, 12.9),
                    "minute_plan": {
                        "confirm_price_60m": 12.66,
                        "confirm_support_60m": 11.88,
                    },
                    "watch_anchor_note": "初始观察说明",
                },
                "_build_gem_breathing_contract": lambda candidate=None: {
                    "contract_kind": "gem_breathing_20cm",
                    "upgrade_condition_text": "09:50-10:10站上12.66且不破11.88",
                    "void_price": 11.88,
                    "reset_breakout_price": 12.9,
                },
                "STOP_PRIOR_LOW_TRADING_DAYS": 5,
                "QUANT_SYSTEM_AVAILABLE": False,
                "analyze_buy_signal": lambda *args, **kwargs: None,
            },
        )

        self.assertEqual(watch_anchor["watch_source"], "gem_breathing_20cm")
        self.assertEqual(watch_anchor["permission_label"], "创业板20cm预启动观察权")
        self.assertTrue(watch_anchor["report_day_is_one_word"])
        self.assertEqual(watch_anchor["breathing_tier"], "tight")
        self.assertEqual(watch_anchor["gem_breathing_contract"]["contract_kind"], "gem_breathing_20cm")
        self.assertIn("近60日出现4次", watch_anchor["watch_anchor_note"])
        self.assertIn("11.88", watch_anchor["watch_anchor_note"])
        self.assertIn("右侧确认", watch_anchor["watch_anchor_note"])

    def test_is_20cm_stock_and_evaluate_window_identify_tight_breathing_pattern(self):
        bars = [
            {"close": 10.00, "high": 10.10, "low": 9.90},
            {"close": 10.12, "high": 10.22, "low": 10.02},
            {"close": 10.03, "high": 10.13, "low": 9.93},
            {"close": 10.15, "high": 10.25, "low": 10.05},
            {"close": 10.06, "high": 10.16, "low": 9.96},
            {"close": 10.18, "high": 10.28, "low": 10.08},
            {"close": 10.09, "high": 10.19, "low": 9.99},
            {"close": 10.17, "high": 10.27, "low": 10.07},
            {"close": 10.11, "high": 10.21, "low": 10.01},
            {"close": 10.16, "high": 10.26, "low": 10.06},
        ]

        result = evaluate_gem_breathing_window(bars, lookback_days=10)

        self.assertTrue(is_20cm_stock({"code": "300001"}))
        self.assertFalse(is_20cm_stock({"code": "000001"}))
        self.assertTrue(result["active"])
        self.assertEqual(result["tier"], "tight")
        self.assertTrue(result["compression_ready"])
        self.assertIn("预启动", result["note"])

    def test_build_gem_breathing_prep_context_uses_filtered_bars_before_target_date(self):
        calls = []

        result = build_gem_breathing_prep_context(
            {"code": "300001"},
            target_date="2026-04-22",
            lookback_days=10,
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "_normalize_kline_date_str": lambda value: str(value or ""),
                "_parse_kline_date": lambda value: None,
                "fetch_daily_price_bars": lambda *args, **kwargs: [
                    {"date": "2026-04-21", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-23", "close": 10, "high": 10.1, "low": 9.9},
                ],
                "_evaluate_gem_breathing_window": lambda bars, lookback_days=10: calls.append([bar["date"] for bar in bars]) or {"active": True, "tier": "tight"},
            },
        )

        self.assertEqual(calls, [["2026-04-21"]])
        self.assertEqual(result, {"active": True, "tier": "tight"})

    def test_discover_gem_breathing_candidates_merges_meta_and_supports_mainline_filter(self):
        all_items = discover_all_gem_breathing_candidates(
            {
                "300001": {"sector": "军工", "score": 88, "close": 12.3},
                "300002": {"sector": "机器人", "score": 66, "close": 9.8},
                "000001": {"sector": "银行", "score": 99, "close": 10.0},
            },
            target_date="2026-04-22",
            helpers={
                "_get_gem_stock_universe": lambda: [
                    {"code": "300001", "name": "军工弹性"},
                    {"code": "300002", "name": "机器人弹性"},
                ],
                "_build_gem_breathing_prep_context": lambda candidate, target_date="": {
                    "active": candidate.get("code") == "300001",
                    "tier": "tight" if candidate.get("code") == "300001" else "",
                    "note": "呼吸感预启动" if candidate.get("code") == "300001" else "",
                    "avg_spread_pct": 1.5 if candidate.get("code") == "300001" else 9.9,
                    "sign_changes": 4 if candidate.get("code") == "300001" else 1,
                },
                "normalize_stock_code": lambda code: str(code or ""),
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )
        mainline_items = discover_gem_breathing_candidates(
            {"300001": {"sector": "军工", "score": 88, "close": 12.3}, "300002": {"sector": "机器人", "score": 66, "close": 9.8}},
            target_date="2026-04-22",
            mainline_name="军工",
            limit=3,
            helpers={
                "_discover_all_gem_breathing_candidates": lambda stock_meta_map, target_date="": all_items,
                "_candidate_matches_mainline": lambda item, mainline_name="": item.get("sector") == mainline_name,
            },
        )
        filtered_items = discover_filtered_out_gem_breathing_candidates(
            {"300001": {"sector": "军工", "score": 88, "close": 12.3}, "300002": {"sector": "机器人", "score": 66, "close": 9.8}},
            target_date="2026-04-22",
            mainline_name="军工",
            limit=3,
            helpers={
                "_discover_all_gem_breathing_candidates": lambda stock_meta_map, target_date="": [
                    {"code": "300001", "name": "军工弹性", "sector": "军工"},
                    {"code": "300002", "name": "机器人弹性", "sector": "机器人"},
                ],
                "_candidate_matches_mainline": lambda item, mainline_name="": item.get("sector") == mainline_name,
            },
        )

        self.assertEqual(len(all_items), 1)
        self.assertEqual(all_items[0]["code"], "300001")
        self.assertEqual(all_items[0]["name"], "军工弹性")
        self.assertEqual(mainline_items[0]["code"], "300001")
        self.assertEqual(filtered_items[0]["code"], "300002")
        self.assertIn("当前主线是军工", filtered_items[0]["filtered_reason"])

    def test_build_gem_observation_pool_enriches_textbook_profile(self):
        pool = build_gem_observation_pool(
            [{"code": "300001", "name": "军工弹性", "tier": "tight", "note": "有预热", "score": 80, "close": 12.3, "volume": 3.2, "change_pct": 4.5}],
            target_date="2026-04-22",
            helpers={
                "build_gem_breathing_textbook_profile": lambda item, target_date="", lookback_days=10, review_days=60: {
                    "label": "A级教材",
                    "total_active_count": 4,
                    "tight_count": 2,
                    "loose_count": 2,
                    "last_active_date": "2026-04-20",
                    "score_bonus": 8,
                    "summary_text": "A级教材：近60日出现4次，tight 2次 / loose 2次，最近一次2026-04-20",
                },
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(pool[0]["watch_source"], "gem_breathing_20cm")
        self.assertEqual(pool[0]["textbook_label"], "A级教材")
        self.assertIn("A级教材", pool[0]["core_level"])
        self.assertIn("近60日出现4次", pool[0]["watch_anchor_note"])
        self.assertGreater(pool[0]["tomorrow_strength"], 80)

    def test_build_gem_breathing_textbook_profile_summarizes_active_points(self):
        profile = build_gem_breathing_textbook_profile(
            {"code": "300001"},
            target_date="2026-04-22",
            lookback_days=10,
            review_days=60,
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "_normalize_kline_date_str": lambda value: str(value or ""),
                "fetch_daily_price_bars": lambda *args, **kwargs: [
                    {"date": "2026-04-10", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-11", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-12", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-13", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-14", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-15", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-16", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-17", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-18", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-19", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-20", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-21", "close": 10, "high": 10.1, "low": 9.9},
                    {"date": "2026-04-22", "close": 10, "high": 10.1, "low": 9.9},
                ],
                "_evaluate_gem_breathing_window": lambda bars, lookback_days=10: {
                    "active": len(bars) in (10, 11, 13),
                    "tier": "tight" if len(bars) == 13 else "loose",
                },
            },
        )

        self.assertEqual(profile["label"], "B级教材")
        self.assertEqual(profile["total_active_count"], 3)
        self.assertEqual(profile["tight_count"], 1)
        self.assertEqual(profile["last_active_date"], "2026-04-22")
        self.assertIn("近60日出现3次", profile["summary_text"])


if __name__ == "__main__":
    unittest.main()
