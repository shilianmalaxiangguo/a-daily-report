import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.trend_snapshot_runtime import (
    build_extreme_conviction_list,
    build_leader_memory_bank,
    build_sector_trend_snapshot,
)


class SelectionTrendRuntimeTest(unittest.TestCase):
    def test_build_sector_trend_snapshot_prefers_dense_sector_and_anchor(self):
        result = build_sector_trend_snapshot(
            candidates=[
                {"code": "000001", "sector": "军工", "score": 75},
                {"code": "000002", "sector": "军工", "score": 55},
                {"code": "000003", "sector": "消费", "score": 42},
            ],
            watchlist=[
                {"code": "000001", "sector": "军工"},
                {"code": "000004", "sector": "军工"},
            ],
            evaluated_stocks=[
                {"code": "000001", "name": "军工一号", "sector": "军工", "tomorrow_strength": 82, "连板数": 2, "reason": "龙一", "pattern": "T字板"},
                {"code": "000003", "name": "消费一号", "sector": "消费", "tomorrow_strength": 40, "连板数": 0, "reason": "", "pattern": ""},
            ],
            dragon_stocks=[
                {"code": "000001", "name": "军工一号", "sector": "军工", "lianban": 2},
            ],
            zt_pool_by_sector={"军工": [{"code": "000001"}, {"code": "000002"}]},
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "stock_matches_sector": lambda stock, sector_name: stock.get("sector") == sector_name,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(result[0]["sector"], "军工")
        self.assertEqual(result[0]["anchor_code"], "000001")
        self.assertGreater(result[0]["density_score"], result[1]["density_score"])

    def test_build_sector_trend_snapshot_ignores_market_board_labels(self):
        result = build_sector_trend_snapshot(
            candidates=[
                {"code": "000417", "name": "合百集团", "sector": "HS", "score": 75},
                {"code": "300212", "name": "*ST易录", "sector": "GEM", "score": 70},
                {"code": "688507", "name": "索辰科技", "sector": "STAR", "score": 65},
                {"code": "000001", "name": "军工一号", "sector": "军工", "score": 55},
            ],
            watchlist=[
                {"code": "000417", "name": "合百集团", "sector": "HS"},
                {"code": "000001", "name": "军工一号", "sector": "军工"},
            ],
            evaluated_stocks=[
                {"code": "000417", "name": "合百集团", "sector": "HS", "tomorrow_strength": 90},
                {"code": "000001", "name": "军工一号", "sector": "军工", "tomorrow_strength": 60},
            ],
            dragon_stocks=[],
            zt_pool_by_sector={"HS": [{"code": "000417"}], "军工": [{"code": "000001"}]},
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "stock_matches_sector": lambda stock, sector_name: stock.get("sector") == sector_name,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        sectors = [item["sector"] for item in result]
        self.assertEqual(sectors, ["军工"])
        self.assertNotIn("HS", sectors)
        self.assertNotIn("GEM", sectors)
        self.assertNotIn("STAR", sectors)

    def test_build_conviction_and_memory_outputs_keep_mainline_priority(self):
        sector_snapshot = [{"sector": "军工", "anchor_code": "000001", "anchor_reason": "板块高标", "anchor_lianban": 3, "density_score": 78}]

        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {"code": "000001", "sector": "军工", "tomorrow_strength": 80, "连板数": 3, "reason": "龙一", "pattern": "T字板"},
                {"code": "000002", "sector": "消费", "tomorrow_strength": 75, "连板数": 0, "reason": "", "pattern": ""},
            ],
            mainline_name="军工",
            sector_snapshot=sector_snapshot,
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )
        memory = build_leader_memory_bank(
            sector_snapshot=sector_snapshot,
            watchlist=[{"code": "000001", "name": "军工一号", "sector": "军工", "reason": "龙一"}],
            dragon_stocks=[{"code": "000001", "name": "军工一号", "sector": "军工", "lianban": 3}],
            hot_rank_top30=[{"code": "000001"}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(conviction[0]["code"], "000001")
        self.assertIn("主线内核", conviction[0]["conviction_reason"])
        self.assertEqual(memory[0]["code"], "000001")
        self.assertIn("热榜第1", memory[0]["remember_reason"])

    def test_conviction_list_does_not_render_limit_up_candidates_as_unassigned(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000417",
                    "name": "合百集团",
                    "sector": "半导体",
                    "tomorrow_strength": 80,
                    "连板数": 1,
                    "reason": "间接投资长鑫科技+合肥国资+区域零售",
                    "pattern": "一字板",
                    "change_pct": 10.07,
                    "abnormal_follow_state": "缩量消化",
                    "abnormal_setup_signal_id": "burst_digest",
                }
            ],
            mainline_name="",
            sector_snapshot=[],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: bool(mainline) and sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        core = conviction[0]
        self.assertEqual(core["sector"], "半导体")
        self.assertEqual(core["core_identity"]["role"], "core_transmitter")
        self.assertEqual(core["core_identity"]["chain_position"], "middle_transmitter")
        self.assertIn("首板", core["core_identity"]["basis"])

    def test_build_conviction_list_rejects_first_day_one_word_limit_without_resilient_confirmation(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000417",
                    "name": "合百集团",
                    "sector": "国产芯片",
                    "tomorrow_strength": 98,
                    "score": 98,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "一字板",
                    "change_pct": 10.07,
                    "open": 7.87,
                    "high": 7.87,
                    "low": 7.87,
                    "close": 7.87,
                    "abnormal_follow_state": "新异动待观察",
                    "abnormal_setup_signal_id": "fresh_abnormal_probe",
                },
                {
                    "code": "001259",
                    "name": "利仁科技",
                    "sector": "股权转让",
                    "tomorrow_strength": 86,
                    "score": 86,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "T字板",
                    "change_pct": 10.0,
                    "open": 66.55,
                    "high": 66.55,
                    "low": 63.01,
                    "close": 66.55,
                    "abnormal_follow_state": "缩量消化",
                    "abnormal_setup_signal_id": "burst_digest",
                },
            ],
            mainline_name="",
            sector_snapshot=[
                {"sector": "国产芯片", "anchor_code": "000417", "density_score": 99},
                {"sector": "股权转让", "anchor_code": "001259", "density_score": 80},
            ],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: bool(mainline) and sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertNotIn("000417", [item["code"] for item in conviction])
        self.assertEqual([item["code"] for item in conviction], ["001259"])

    def test_build_conviction_list_uses_stable_tiebreaker(self):
        evaluated_stocks = [
            {"code": "000003", "name": "后入池", "sector": "军工", "tomorrow_strength": 80, "连板数": 1, "reason": "", "pattern": ""},
            {"code": "000001", "name": "先入池", "sector": "军工", "tomorrow_strength": 80, "连板数": 1, "reason": "", "pattern": ""},
            {"code": "000002", "name": "中入池", "sector": "军工", "tomorrow_strength": 80, "连板数": 1, "reason": "", "pattern": ""},
        ]

        conviction = build_extreme_conviction_list(
            evaluated_stocks=evaluated_stocks,
            mainline_name="军工",
            sector_snapshot=[],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["000001", "000002", "000003"])

    def test_build_conviction_list_adds_participation_window_playbook_fields(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "tomorrow_strength": 92,
                    "连板数": 2,
                    "reason": "龙一",
                    "pattern": "T字板",
                    "abnormal_follow_state": "跌不下去",
                }
            ],
            mainline_name="电力",
            sector_snapshot=[{"sector": "电力", "anchor_code": "601991", "density_score": 88}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        core = conviction[0]
        self.assertEqual(core["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(core["attack_state"], "100%")
        self.assertEqual(core["core_identity"]["role"], "trend_chain_anchor")
        self.assertEqual(core["core_identity"]["chain_position"], "high_anchor")
        self.assertTrue(core["core_identity"]["early_participation_allowed"])
        self.assertEqual(core["core_identity"]["position_state"], "100%")
        self.assertIn("主线内核", core["core_identity"]["basis"])
        self.assertIn("板块锚定龙", core["core_identity"]["basis"])
        self.assertIn("2连板", core["core_identity"]["basis"])
        self.assertIn("分歧转一致形态", core["core_identity"]["basis"])
        self.assertIn("09:20", core["auction_script"])
        self.assertIn("09:30-09:35", core["first_minutes_script"])
        self.assertIn("大单金额", core["board_script"])
        self.assertIn("快速回封", core["reseal_script"])
        self.assertIn("趋势比价链", core["missed_action"])
        self.assertIn("按0%不参与", core["invalid_condition"])
        self.assertEqual(core["limit_up_inertia_level"], "高惯性")
        self.assertEqual(core["next_day_limit_probability_band"], "高于普通上涨样本")
        self.assertEqual(core["risk_reward_min_ratio"], 2.0)
        self.assertIn("2:1", core["risk_reward_plan"])

    def test_build_conviction_list_rejects_limit_down_and_flat_heat_only_samples(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "-",
                    "tomorrow_strength": 96,
                    "score": 96,
                    "change_pct": 0.13,
                    "open": 7.68,
                    "high": 8.12,
                    "low": 7.63,
                    "close": 7.93,
                    "连板数": 0,
                    "reason": "",
                    "pattern": "震荡整理(0分)",
                },
                {
                    "code": "002342",
                    "name": "巨力索具",
                    "sector": "-",
                    "tomorrow_strength": 95,
                    "score": 95,
                    "change_pct": -9.98,
                    "open": 17.49,
                    "high": 17.49,
                    "low": 17.49,
                    "close": 17.49,
                    "连板数": 0,
                    "reason": "",
                    "pattern": "缩量调整(0分)",
                },
                {
                    "code": "600396",
                    "name": "华电辽能",
                    "sector": "-",
                    "tomorrow_strength": 94,
                    "score": 94,
                    "change_pct": -9.98,
                    "open": 16.50,
                    "high": 17.15,
                    "low": 15.69,
                    "close": 15.69,
                    "连板数": 0,
                    "reason": "",
                    "pattern": "下跌趋势(0分)",
                },
                {
                    "code": "000988",
                    "name": "华工科技",
                    "sector": "光通信",
                    "tomorrow_strength": 88,
                    "score": 88,
                    "change_pct": 10.0,
                    "open": 137.53,
                    "high": 147.38,
                    "low": 137.03,
                    "close": 147.38,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "光头大阳柱涨停(4分)",
                },
            ],
            mainline_name="",
            sector_snapshot=[],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["000988"])
        self.assertNotIn("趋势辨识度高", conviction[0]["conviction_reason"])

    def test_build_conviction_list_blocks_negative_news_and_marks_repair_watch_samples(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002342",
                    "name": "巨力索具",
                    "sector": "商业航天",
                    "tomorrow_strength": 99,
                    "score": 99,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "光头大阳柱涨停",
                    "news_risk_flags": ["监管立案"],
                    "negative_news_summary": "公司涉嫌信息披露违法违规被证监会立案",
                },
                {
                    "code": "600396",
                    "name": "华电辽能",
                    "sector": "超超临界发电",
                    "tomorrow_strength": 95,
                    "score": 95,
                    "change_pct": -9.98,
                    "连板数": 0,
                    "reason": "17天9板高辨识度",
                    "pattern": "下跌趋势(0分)",
                },
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "绿色电力",
                    "tomorrow_strength": 92,
                    "score": 92,
                    "change_pct": 0.13,
                    "连板数": 0,
                    "reason": "趋势辨识度高",
                    "pattern": "震荡整理(0分)",
                    "allow_extreme_conviction": True,
                },
                {
                    "code": "000988",
                    "name": "华工科技",
                    "sector": "光通信",
                    "tomorrow_strength": 88,
                    "score": 88,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "光头大阳柱涨停",
                },
            ],
            mainline_name="",
            sector_snapshot=[],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        codes = [item["code"] for item in conviction]
        self.assertNotIn("002342", codes)
        self.assertNotIn("600396", codes)
        self.assertIn("601991", codes)
        datang = next(item for item in conviction if item["code"] == "601991")
        self.assertEqual(datang["candidate_layer"], "watch_sample")
        self.assertEqual(datang["execution_eligibility"], "structure_confirm_only")
        self.assertEqual(datang["conviction_rule"], "修复观察只看09:50-10:10承接确认，未确认不参与")
        self.assertIn("修复观察", datang["conviction_reason"])

    def test_build_conviction_list_fieldizes_participation_window_policy(self):
        fast = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "tomorrow_strength": 92,
                    "连板数": 2,
                    "reason": "龙一",
                    "pattern": "T字板",
                    "abnormal_follow_state": "跌不下去",
                }
            ],
            mainline_name="电力",
            sector_snapshot=[{"sector": "电力", "anchor_code": "601991", "density_score": 88}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        ordinary = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "300001",
                    "name": "普通趋势股",
                    "sector": "消费",
                    "tomorrow_strength": 61,
                    "连板数": 0,
                    "reason": "趋势观察",
                    "pattern": "",
                }
            ],
            mainline_name="电力",
            sector_snapshot=[{"sector": "电力", "anchor_code": "601991", "density_score": 88}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        fast_core = fast[0]
        self.assertEqual(fast_core["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(fast_core["participation_window_type"], "auction_reseal")
        self.assertTrue(fast_core["auction_required"])
        self.assertTrue(fast_core["first_minutes_required"])
        self.assertTrue(fast_core["board_or_reseal_required"])
        self.assertFalse(fast_core["ordinary_structure_confirm_allowed"])
        self.assertIn("趋势比价链", fast_core["missed_entry_policy"])

        ordinary_core = ordinary[0]
        self.assertEqual(ordinary_core["participation_window"], "60分钟确认")
        self.assertEqual(ordinary_core["participation_window_type"], "structure_confirm")
        self.assertEqual(ordinary_core["core_identity"]["role"], "tracked_sample")
        self.assertEqual(ordinary_core["core_identity"]["chain_position"], "unassigned")
        self.assertFalse(ordinary_core["core_identity"]["early_participation_allowed"])
        self.assertEqual(ordinary_core["core_identity"]["position_state"], "50%")
        self.assertFalse(ordinary_core["auction_required"])
        self.assertFalse(ordinary_core["first_minutes_required"])
        self.assertFalse(ordinary_core["board_or_reseal_required"])
        self.assertTrue(ordinary_core["ordinary_structure_confirm_allowed"])
        self.assertIn("趋势比价链", ordinary_core["missed_entry_policy"])
        self.assertNotEqual(fast_core["limit_up_inertia_level"], ordinary_core["limit_up_inertia_level"])
        self.assertGreater(fast_core["limit_up_inertia_score"], ordinary_core["limit_up_inertia_score"])
        self.assertEqual(ordinary_core["limit_up_inertia_level"], "低惯性")

    def test_mainline_participation_fallback_uses_trend_chain_language_for_missed_action(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "tomorrow_strength": 92,
                    "连板数": 1,
                    "reason": "主线内核",
                    "pattern": "",
                    "core_level": "主线核心",
                }
            ],
            mainline_name="电力",
            sector_snapshot=[{"sector": "电力", "anchor_code": "601991", "density_score": 88}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        core = conviction[0]
        self.assertEqual(core["participation_window"], "竞价表态 + 回封参与")
        self.assertIn("电力", core["missed_action"])
        self.assertIn("趋势比价链", core["missed_action"])
        self.assertNotIn("不临时补票", core["missed_action"])


if __name__ == "__main__":
    unittest.main()
