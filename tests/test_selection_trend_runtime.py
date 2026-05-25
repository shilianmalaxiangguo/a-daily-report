import sys
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.trend_snapshot_runtime import (
    build_extreme_conviction_groups,
    _build_trend_aesthetic_review,
    build_extreme_conviction_list,
    build_leader_memory_bank,
    build_sector_trend_snapshot,
)


def _bars(closes, *, start=1, pct_changes=None, highs=None, lows=None):
    rows = []
    for idx, close in enumerate(closes, start=start):
        prev = closes[idx - start - 1] if idx > start else close
        pct_chg = pct_changes[idx - start] if pct_changes else ((close / prev - 1) * 100 if prev else 0)
        high = highs[idx - start] if highs else close * 1.03
        low = lows[idx - start] if lows else close * 0.97
        rows.append(
            {
                "date": f"2026-01-{idx:02d}",
                "open": prev,
                "high": high,
                "low": low,
                "close": close,
                "pct_chg": pct_chg,
                "volume": 10000 + idx,
            }
        )
    return rows


def _weak_rebound_below_ma20_bars():
    closes = [10 + idx * 0.12 for idx in range(20)] + [
        12.4,
        12.7,
        13.0,
        13.3,
        13.6,
        13.9,
        14.2,
        14.5,
        14.8,
        15.1,
        15.4,
        15.2,
        15.0,
        14.8,
        14.6,
        14.4,
        14.2,
        12.78,
        13.0,
        13.1,
    ]
    return _bars(closes)


def _sqlite_recent_bars(code, *, end_date="2026-05-21", limit=120):
    db_path = ROOT / "data" / "cloudflare_free_daily.db"
    if not db_path.exists():
        raise unittest.SkipTest("local daily quote database is not available")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT trade_date AS date, open, high, low, close, pct_chg, vol AS volume
            FROM stock_daily_quotes_recent
            WHERE stock_code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (code, end_date, limit),
        ).fetchall()
    finally:
        conn.close()
    bars = [dict(row) for row in reversed(rows)]
    if len(bars) < 8:
        raise unittest.SkipTest(f"not enough local daily bars for {code}")
    return bars


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

    def test_sector_trend_snapshot_deduplicates_front_row_strength_components(self):
        result = build_sector_trend_snapshot(
            candidates=[
                {"code": "000001", "name": "军工一号", "sector": "军工", "score": 70},
            ],
            watchlist=[
                {"code": "000001", "name": "军工一号", "sector": "军工"},
            ],
            evaluated_stocks=[
                {
                    "code": "000001",
                    "name": "军工一号",
                    "sector": "军工",
                    "tomorrow_strength": 130,
                    "base_strength_score": 60,
                    "score": 60,
                    "连板数": 2,
                    "reason": "龙一",
                    "pattern": "T字板",
                },
            ],
            dragon_stocks=[
                {"code": "000001", "name": "军工一号", "sector": "军工", "lianban": 2},
            ],
            zt_pool_by_sector={"军工": [{"code": "000001"}]},
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "stock_matches_sector": lambda stock, sector_name: stock.get("sector") == sector_name,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        sector = result[0]
        old_full_stack_score = 10 + 8 + 10 + 12 + 4 + int(130 / 20)
        self.assertLess(sector["density_score"], old_full_stack_score)
        self.assertEqual(sector["density_score"], 30)
        self.assertEqual(sector["base_strength_sum"], 60)
        self.assertIn("density_dedup", sector)
        self.assertEqual(sector["density_dedup"]["group_scores"]["sector_strength"], 12)
        self.assertEqual(sector["density_dedup"]["repeated_advantage_count"], 3)

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

    def test_extreme_conviction_score_deduplicates_market_selection_labels(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000001",
                    "name": "军工一号",
                    "sector": "军工",
                    "tomorrow_strength": 92,
                    "score": 92,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "龙一，主线锚定",
                    "pattern": "T字板",
                }
            ],
            mainline_name="军工",
            sector_snapshot=[{"sector": "军工", "anchor_code": "000001", "density_score": 88}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        core = conviction[0]
        old_full_stack_score = 92 + 18 + 12 + 8 + 6 + 4
        self.assertLess(core["conviction_score"], old_full_stack_score)
        self.assertEqual(core["conviction_score"], 114)
        self.assertIn("advantage_dedup", core)
        self.assertEqual(core["advantage_dedup"]["group_scores"]["market_selection"], 18)
        self.assertEqual(core["advantage_dedup"]["group_scores"]["shape_confirmation"], 4)
        self.assertEqual(core["advantage_dedup"]["repeated_advantage_count"], 3)
        self.assertEqual(
            {point["label"] for point in core["advantage_dedup"]["suppressed_points"]},
            {"板块锚定龙", "2连板", "首波先锋"},
        )

    def test_extreme_conviction_score_does_not_add_lianban_again_when_strength_already_contains_it(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000002",
                    "name": "连板样本",
                    "sector": "军工",
                    "base_strength_score": 72,
                    "tomorrow_strength": 92,
                    "score": 72,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "换手连板",
                    "pattern": "光头大阳柱涨停",
                }
            ],
            mainline_name="",
            sector_snapshot=[],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        core = conviction[0]
        self.assertEqual(core["conviction_score"], 92)
        self.assertNotIn("market_selection", core["advantage_dedup"]["group_scores"])
        self.assertEqual(
            {point["label"] for point in core["advantage_dedup"]["suppressed_points"]},
            {"2连板"},
        )

    def test_build_conviction_list_keeps_sniper_window_but_marks_systemic_st_resume_risk(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000001",
                    "name": "军工一号",
                    "sector": "军工",
                    "tomorrow_strength": 96,
                    "score": 96,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "龙一",
                    "pattern": "T字板",
                }
            ],
            mainline_name="军工",
            sector_snapshot=[{"sector": "军工", "anchor_code": "000001", "density_score": 88}],
            risk_context={
                "systemic_risk_warnings": [
                    {
                        "name": "全市场",
                        "risk_level": "high",
                        "risk_source": "st_resume_experience",
                        "reason": "2只突发ST复牌，经验上容易触发量化/风控卖出，明日有4000+下跌风险。",
                    }
                ]
            },
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(len(conviction), 1)
        core = conviction[0]
        self.assertEqual(core["candidate_layer"], "executable_candidate")
        self.assertEqual(core["execution_eligibility"], "auction_reseal")
        self.assertEqual(core["attack_state"], "100%")
        self.assertEqual(core["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(core["systemic_risk_review"]["status"], "降主动性")
        self.assertEqual(core["systemic_risk_review"]["position_cap_pct"], 50)
        self.assertIn("4000+下跌风险", core["systemic_risk_review"]["reason"])
        self.assertEqual(core["final_risk_review"]["status"], "通过")

    def test_conviction_list_does_not_render_limit_up_candidates_as_unassigned(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000417",
                    "name": "合百集团",
                    "sector": "半导体",
                    "tomorrow_strength": 80,
                    "连板数": 1,
                    "reason": "间接投资长鑫科技+合肥国资+区域零售，平台震荡后放量突破",
                    "pattern": "一字板涨停，低点上移",
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
            {
                "code": "000003",
                "name": "后入池",
                "sector": "军工",
                "tomorrow_strength": 80,
                "连板数": 1,
                "reason": "趋势比价链样本",
                "pattern": "上升趋势后平台震荡，低点上移",
            },
            {
                "code": "000001",
                "name": "先入池",
                "sector": "军工",
                "tomorrow_strength": 80,
                "连板数": 1,
                "reason": "趋势比价链样本",
                "pattern": "上升趋势后平台震荡，低点上移",
            },
            {
                "code": "000002",
                "name": "中入池",
                "sector": "军工",
                "tomorrow_strength": 80,
                "连板数": 1,
                "reason": "趋势比价链样本",
                "pattern": "上升趋势后平台震荡，低点上移",
            },
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

    def test_build_conviction_list_assigns_primary_and_backup_with_sniper_fields(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "tomorrow_strength": 96,
                    "score": 96,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "龙一",
                    "pattern": "T字板",
                    "abnormal_follow_state": "跌不下去",
                },
                {
                    "code": "600396",
                    "name": "华电辽能",
                    "sector": "电力",
                    "tomorrow_strength": 90,
                    "score": 90,
                    "change_pct": 6.5,
                    "连板数": 0,
                    "reason": "趋势比价链核心",
                    "pattern": "放量大阳线",
                    "abnormal_follow_state": "缩量消化",
                    "close_ma_alignment": "MA5",
                    "turnover_capacity": "large",
                },
            ],
            mainline_name="电力",
            sector_snapshot=[{"sector": "电力", "anchor_code": "601991", "density_score": 88}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["sniper_role"] for item in conviction[:2]], ["明日主买对象", "明日补位对象"])
        primary = conviction[0]
        backup = conviction[1]
        self.assertTrue(primary["primary_buy_candidate"])
        self.assertFalse(primary["backup_buy_candidate"])
        self.assertFalse(backup["primary_buy_candidate"])
        self.assertTrue(backup["backup_buy_candidate"])
        self.assertEqual(primary["leader_speed_tier"], "极致加速龙头")
        self.assertEqual(primary["buy_ma_line"], "MA3")
        self.assertEqual(primary["sell_ma_line"], "MA5")
        self.assertEqual(backup["leader_speed_tier"], "大容量趋势龙头")
        self.assertEqual(backup["buy_ma_line"], "MA10")
        self.assertEqual(backup["sell_ma_line"], "MA20")
        self.assertIn("缩量回撤", primary["acceptance_repair_required"])
        self.assertIn("持筹者", primary["common_selection_check"])
        self.assertEqual(primary["final_risk_review"]["status"], "通过")

    def test_build_conviction_list_excludes_unrepaired_upper_shadow_and_broken_sell_line(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "600749",
                    "name": "西藏旅游",
                    "sector": "旅游",
                    "tomorrow_strength": 99,
                    "score": 99,
                    "change_pct": 3.2,
                    "连板数": 0,
                    "reason": "高辨识度题材核心",
                    "pattern": "连续长上影",
                    "upper_shadow_unrepaired": True,
                },
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "通信设备",
                    "tomorrow_strength": 98,
                    "score": 98,
                    "change_pct": -3.5,
                    "连板数": 0,
                    "reason": "龙头回头样本",
                    "pattern": "跌破MA10收不回",
                    "broken_sell_ma_line": True,
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

        self.assertEqual([item["code"] for item in conviction], ["000988"])

    def test_build_conviction_list_blocks_a_kill_shape_even_when_score_and_anchor_are_high(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "光通信",
                    "tomorrow_strength": 118,
                    "score": 99,
                    "change_pct": 4.2,
                    "连板数": 0,
                    "reason": "龙头回头样本",
                    "pattern": "A杀后弱反抽，反抽不过MA3/MA7，低点下移，高点下移，放量下杀后承接不足",
                },
                {
                    "code": "002281",
                    "name": "光迅科技",
                    "sector": "光通信",
                    "tomorrow_strength": 88,
                    "score": 88,
                    "change_pct": 5.6,
                    "连板数": 0,
                    "reason": "趋势比价链核心",
                    "pattern": "上升趋势后平台震荡，缩量回踩MA5不破，低点上移，蛇形走位有呼吸",
                    "abnormal_follow_state": "缩量消化",
                },
            ],
            mainline_name="光通信",
            sector_snapshot=[{"sector": "光通信", "anchor_code": "000586", "density_score": 99}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["002281"])
        kept = conviction[0]
        self.assertEqual(kept["trend_aesthetic_review"]["status"], "通过")
        self.assertIn("上升趋势", kept["trend_aesthetic_review"]["reasons"])
        self.assertIn("平台震荡", kept["trend_aesthetic_review"]["reasons"])

    def test_build_conviction_list_keeps_breathing_trend_samples_with_shape_review(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002975",
                    "name": "博杰股份",
                    "sector": "机器人",
                    "tomorrow_strength": 92,
                    "score": 92,
                    "change_pct": 3.8,
                    "连板数": 0,
                    "reason": "主线核心，趋势比价链核心",
                    "pattern": "上升趋势后平台震荡，沿MA5蛇形走位，缩量回踩不破，低点上移",
                    "abnormal_follow_state": "缩量消化",
                }
            ],
            mainline_name="机器人",
            sector_snapshot=[{"sector": "机器人", "anchor_code": "002975", "density_score": 92}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["002975"])
        core = conviction[0]
        self.assertEqual(core["trend_aesthetic_review"]["status"], "通过")
        self.assertEqual(core["trend_aesthetic_review"]["action"], "保留极度看好比较资格")
        self.assertEqual(core["selection_shape_review"]["name"], "选股形态审美")
        self.assertEqual(core["selection_shape_review"]["status"], "通过")
        self.assertIn("呼吸感", core["selection_shape_review"]["focus"])
        self.assertIn("蛇形走位", core["selection_shape_review"]["focus"])
        self.assertIn("A杀", core["selection_shape_review"]["avoid"])
        self.assertIn("趋势审美", core["core_identity"]["basis"])

    def test_build_conviction_list_uses_recent_120_day_bars_to_block_a_kill_shape(self):
        weak_bars = _bars(
            [40, 42, 44, 46, 48, 45, 43, 41, 39, 36, 34, 33, 32, 31, 30, 29, 28, 30, 27, 24],
            pct_changes=[0, 5, 4.8, 4.5, 4.3, -6.2, -4.4, -4.7, -4.9, -7.7, -5.6, -2.9, -3.0, -3.1, -3.2, -3.3, -3.4, 7.1, -10.0, -11.1],
            highs=[41, 43, 45, 47, 49, 46, 44, 42, 40, 37, 35, 34, 33, 32, 31, 30, 29, 31, 28, 25],
            lows=[39, 41, 43, 45, 47, 44, 42, 40, 38, 35, 33, 32, 31, 30, 29, 28, 27, 29, 26, 23],
        )
        healthy_bars = _bars(
            [30, 31, 32, 34, 35, 36, 35, 36, 37, 39, 40, 41, 40, 41, 43, 44, 45, 46, 47, 48],
            pct_changes=[0, 3.3, 3.2, 6.2, 2.9, 2.8, -2.8, 2.9, 2.8, 5.4, 2.6, 2.5, -2.4, 2.5, 4.9, 2.3, 2.3, 2.2, 2.2, 2.1],
        )
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "光通信",
                    "tomorrow_strength": 118,
                    "score": 99,
                    "change_pct": 4.2,
                    "连板数": 0,
                    "reason": "龙头回头样本",
                    "pattern": "强势反抽",
                    "recent_bars": weak_bars,
                },
                {
                    "code": "002281",
                    "name": "光迅科技",
                    "sector": "光通信",
                    "tomorrow_strength": 88,
                    "score": 88,
                    "change_pct": 5.6,
                    "连板数": 0,
                    "reason": "趋势比价链核心",
                    "pattern": "放量大阳线",
                    "recent_bars": healthy_bars,
                },
            ],
            mainline_name="光通信",
            sector_snapshot=[{"sector": "光通信", "anchor_code": "000586", "density_score": 99}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["002281"])
        review = conviction[0]["trend_aesthetic_review"]
        self.assertEqual(review["source"], "recent_bars")
        self.assertEqual(review["status"], "通过")

    def test_build_conviction_list_uses_recent_bars_to_downgrade_good_history_but_weak_current_shape(self):
        closes = (
            list(range(80, 100))
            + [100, 105, 110, 115, 120, 125, 130, 126, 122, 118, 114, 110, 106, 111, 116, 112, 108, 113, 118, 111]
        )
        slipping_bars = _bars(
            closes,
            pct_changes=[0] + [(closes[idx] / closes[idx - 1] - 1) * 100 for idx in range(1, len(closes) - 1)] + [-6.0],
            highs=[close + 3 for close in closes],
            lows=[close - 3 for close in closes],
        )
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002975",
                    "name": "博杰股份",
                    "sector": "机器人",
                    "tomorrow_strength": 99,
                    "score": 99,
                    "change_pct": -7.1,
                    "连板数": 0,
                    "reason": "历史好形态样本，趋势比价链核心",
                    "pattern": "上升趋势后平台震荡，但最近跌破短线承接",
                    "recent_bars": slipping_bars,
                }
            ],
            mainline_name="机器人",
            sector_snapshot=[{"sector": "机器人", "anchor_code": "002975", "density_score": 92}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(conviction, [])

    def test_extreme_conviction_groups_keep_shape_repair_samples_outside_formal_list(self):
        groups = build_extreme_conviction_groups(
            evaluated_stocks=[
                {
                    "code": "002975",
                    "name": "博杰股份",
                    "sector": "机器人",
                    "tomorrow_strength": 99,
                    "score": 99,
                    "change_pct": -7.1,
                    "连板数": 0,
                    "reason": "龙回头样本，历史好形态",
                    "pattern": "上升趋势后平台震荡，但最近跌破短线承接",
                    "recent_bars": _sqlite_recent_bars("002975"),
                },
                {
                    "code": "601869",
                    "name": "长飞光纤",
                    "sector": "光通信",
                    "tomorrow_strength": 96,
                    "score": 96,
                    "change_pct": -5.56,
                    "连板数": 0,
                    "reason": "龙回头样本，历史好形态",
                    "pattern": "上升趋势后平台震荡，但最近跌破短线承接",
                    "recent_bars": _sqlite_recent_bars("601869"),
                },
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "通信设备",
                    "tomorrow_strength": 118,
                    "score": 118,
                    "change_pct": -10.01,
                    "连板数": 0,
                    "reason": "龙回头样本",
                    "pattern": "强势反抽",
                    "recent_bars": _sqlite_recent_bars("000586"),
                },
                {
                    "code": "002281",
                    "name": "光迅科技",
                    "sector": "光通信",
                    "tomorrow_strength": 88,
                    "score": 88,
                    "change_pct": 5.6,
                    "连板数": 0,
                    "reason": "趋势比价链核心",
                    "pattern": "趋势核心",
                    "recent_bars": _sqlite_recent_bars("002281"),
                },
            ],
            mainline_name="光通信",
            sector_snapshot=[{"sector": "光通信", "anchor_code": "002281", "density_score": 99}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in groups["extreme_conviction_list"]], ["002281"])
        self.assertEqual({item["code"] for item in groups["shape_repair_pool"]}, {"002975", "601869"})
        self.assertEqual([item["code"] for item in groups["dragon_rebound_watch_pool"]], ["000586"])
        self.assertNotIn("000586", [item["code"] for item in groups["shape_repair_pool"]])
        rebound = groups["dragon_rebound_watch_pool"][0]
        self.assertEqual(rebound["candidate_layer"], "dragon_rebound_watch_pool")
        self.assertEqual(rebound["execution_eligibility"], "dragon_rebound_watch_only")
        self.assertEqual(rebound["repair_status"], "龙回头观察")
        self.assertIn("A杀未修复前不进正式名单", rebound["next_action"])
        repair = next(item for item in groups["shape_repair_pool"] if item["code"] == "002975")
        self.assertEqual(repair["candidate_layer"], "shape_repair_pool")
        self.assertEqual(repair["execution_eligibility"], "shape_repair_only")
        self.assertEqual(repair["repair_status"], "待修复")
        self.assertEqual(repair["next_action"], "保留跟踪，重新站回短中线承接后再评估；继续走坏再取关淘汰")
        self.assertTrue(
            {"短线承接转弱", "大跌跌破短中线承接"} & set(repair["trend_aesthetic_review"]["reasons"])
        )

    def test_trend_aesthetic_review_marks_currently_weak_good_history_sample_as_repairing(self):
        closes = (
            list(range(80, 100))
            + [100, 105, 110, 115, 120, 125, 130, 126, 122, 118, 114, 110, 106, 111, 116, 112, 108, 113, 118, 111]
        )
        slipping_bars = _bars(
            closes,
            pct_changes=[0] + [(closes[idx] / closes[idx - 1] - 1) * 100 for idx in range(1, len(closes) - 1)] + [-6.0],
            highs=[close + 3 for close in closes],
            lows=[close - 3 for close in closes],
        )

        review = _build_trend_aesthetic_review(
            {
                "code": "002975",
                "name": "博杰股份",
                "pattern": "上升趋势后平台震荡，但最近跌破短线承接",
                "recent_bars": slipping_bars,
            }
        )

        self.assertEqual(review["status"], "不通过")
        self.assertEqual(review["action"], "历史趋势样本待修复，重新站回短中线承接后再评估")
        self.assertIn("短线承接转弱", review["reasons"])

    def test_trend_aesthetic_review_downgrades_big_drop_below_ma5_and_ma20_even_with_mid_range_position(self):
        closes = (
            list(range(80, 100))
            + [100, 105, 110, 115, 120, 125, 130, 126, 122, 118, 114, 110, 106, 111, 116, 112, 108, 113, 118, 111]
        )
        slipping_bars = _bars(
            closes,
            pct_changes=[0] + [(closes[idx] / closes[idx - 1] - 1) * 100 for idx in range(1, len(closes) - 1)] + [-7.2],
            highs=[close + 3 for close in closes],
            lows=[close - 18 for close in closes],
        )

        review = _build_trend_aesthetic_review({"recent_bars": slipping_bars})

        self.assertEqual(review["status"], "不通过")
        self.assertIn("大跌跌破短中线承接", review["reasons"])

    def test_real_120_day_shape_calibration_preserves_healthy_samples_and_marks_repairing_samples(self):
        samples = {
            "603897": "长城科技",
            "603629": "利通电子",
            "300136": "信维通信",
            "002384": "东山精密",
            "002281": "光迅科技",
            "603986": "兆易创新",
            "603256": "宏和科技",
        }
        for code, name in samples.items():
            with self.subTest(code=code, name=name):
                review = _build_trend_aesthetic_review(
                    {"code": code, "name": name, "recent_bars": _sqlite_recent_bars(code)}
                )
                self.assertEqual(review["source"], "recent_bars")
                self.assertEqual(review["status"], "通过")
                self.assertIn("MA20上方或趋势未破", review["reasons"])
                self.assertIn("高低点上移", review["reasons"])
                self.assertNotEqual(review["reasons"], ["未见形态破坏"])

    def test_real_120_day_shape_calibration_exposes_breathing_and_snake_walk_reasons(self):
        breathing_samples = {
            "603897": "长城科技",
            "603629": "利通电子",
            "300136": "信维通信",
            "002384": "东山精密",
            "002281": "光迅科技",
            "603986": "兆易创新",
            "603256": "宏和科技",
        }
        for code, name in breathing_samples.items():
            with self.subTest(code=code, name=name):
                review = _build_trend_aesthetic_review(
                    {"code": code, "name": name, "recent_bars": _sqlite_recent_bars(code)}
                )

                self.assertEqual(review["status"], "通过")
                self.assertIn("平台呼吸", review["reasons"])
                self.assertIn("蛇形走位", review["reasons"])
                self.assertIn("range_contraction_ratio", review["metrics"])
                self.assertIn("pullback_repair_count", review["metrics"])

    def test_conviction_reason_exposes_breathing_shape_terms_from_recent_bars(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002281",
                    "name": "光迅科技",
                    "sector": "光通信",
                    "tomorrow_strength": 88,
                    "score": 88,
                    "change_pct": 5.6,
                    "连板数": 0,
                    "reason": "趋势比价链核心",
                    "pattern": "趋势核心",
                    "recent_bars": _sqlite_recent_bars("002281"),
                }
            ],
            mainline_name="光通信",
            sector_snapshot=[{"sector": "光通信", "anchor_code": "002281", "density_score": 99}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["002281"])
        reason = conviction[0]["conviction_reason"]
        self.assertIn("趋势审美", reason)
        self.assertIn("平台呼吸", reason)
        self.assertIn("蛇形走位", reason)

        for code, name in (("002975", "博杰股份"), ("601869", "长飞光纤")):
            with self.subTest(code=code, name=name):
                review = _build_trend_aesthetic_review(
                    {"code": code, "name": name, "recent_bars": _sqlite_recent_bars(code)}
                )
                self.assertEqual(review["source"], "recent_bars")
                self.assertEqual(review["status"], "不通过")
                self.assertTrue({"短线承接转弱", "大跌跌破短中线承接"} & set(review["reasons"]))
                self.assertEqual(review["action"], "历史趋势样本待修复，重新站回短中线承接后再评估")

    def test_real_available_daily_bars_calibrate_new_leader_samples(self):
        samples = {
            "301666": "大普微",
            "603459": "红板科技",
        }
        for code, name in samples.items():
            with self.subTest(code=code, name=name):
                review = _build_trend_aesthetic_review(
                    {"code": code, "name": name, "recent_bars": _sqlite_recent_bars(code)}
                )
                self.assertEqual(review["source"], "recent_bars")
                self.assertEqual(review["status"], "通过")
                self.assertGreaterEqual(review["metrics"]["bars"], 8)
                self.assertLess(review["metrics"]["bars"], 120)
                self.assertIn("MA20上方或趋势未破", review["reasons"])
                self.assertIn("20日区间位置健康", review["reasons"])
                self.assertIn("攻击有辨识度", review["reasons"])
                self.assertNotEqual(review["reasons"], ["未见形态破坏"])

    def test_real_120_day_shape_calibration_rejects_huiyuan_a_kill_sample(self):
        review = _build_trend_aesthetic_review(
            {
                "code": "000586",
                "name": "汇源通信",
                "reason": "龙头回头样本",
                "pattern": "强势反抽",
                "recent_bars": _sqlite_recent_bars("000586"),
            }
        )

        self.assertEqual(review["source"], "recent_bars")
        self.assertEqual(review["status"], "不通过")
        self.assertIn("放量或急跌破坏", review["reasons"])
        self.assertIn("20日区间低位", review["reasons"])
        self.assertIn("MA20下方", review["reasons"])
        self.assertEqual(review["action"], "降级观察，重新站回关键线并有承接修复后再评估")

    def test_real_leader_samples_still_need_shape_review_before_comparison(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "600578",
                    "name": "京能电力",
                    "sector": "电力",
                    "tomorrow_strength": 98,
                    "score": 98,
                    "change_pct": 9.95,
                    "连板数": 1,
                    "reason": "龙一，板块锚定龙",
                    "pattern": "光头大阳柱涨停",
                    "recent_bars": _sqlite_recent_bars("600578"),
                },
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "通信设备",
                    "tomorrow_strength": 118,
                    "score": 118,
                    "change_pct": -10.01,
                    "连板数": 1,
                    "reason": "龙头回头样本",
                    "pattern": "强势反抽",
                    "recent_bars": _sqlite_recent_bars("000586"),
                },
            ],
            mainline_name="电力",
            sector_snapshot=[{"sector": "电力", "anchor_code": "600578", "density_score": 98}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["600578"])
        leader = conviction[0]
        self.assertEqual(leader["trend_aesthetic_review"]["status"], "通过")
        self.assertEqual(leader["selection_shape_review"]["status"], "通过")
        self.assertNotEqual(leader["trend_aesthetic_review"]["reasons"], ["未见形态破坏"])

    def test_build_conviction_list_rejects_plain_high_score_sample_without_positive_shape_evidence(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "300001",
                    "name": "普通高分样本",
                    "sector": "消费电子",
                    "tomorrow_strength": 99,
                    "score": 99,
                    "change_pct": 4.6,
                    "连板数": 0,
                    "reason": "热度高",
                    "pattern": "普通形态",
                    "allow_extreme_conviction": True,
                },
                {
                    "code": "002281",
                    "name": "光迅科技",
                    "sector": "光通信",
                    "tomorrow_strength": 88,
                    "score": 88,
                    "change_pct": 5.6,
                    "连板数": 0,
                    "reason": "趋势比价链核心",
                    "pattern": "上升趋势后平台震荡，缩量回踩MA5不破，低点上移，蛇形走位有呼吸",
                    "abnormal_follow_state": "缩量消化",
                },
            ],
            mainline_name="光通信",
            sector_snapshot=[{"sector": "光通信", "anchor_code": "002281", "density_score": 99}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual([item["code"] for item in conviction], ["002281"])
        self.assertNotIn("300001", [item["code"] for item in conviction])

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
                    "reason": "趋势辨识度高，上升趋势后平台震荡",
                    "pattern": "震荡整理，缩量回踩不破，低点上移",
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

    def test_build_conviction_list_blocks_structured_tushare_risk_events(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000001",
                    "name": "ST风险样本",
                    "sector": "机器人",
                    "tomorrow_strength": 99,
                    "score": 99,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "光头大阳柱涨停",
                    "stock_risk": {
                        "risk_flags": ["st_warning"],
                        "risk_summary": "实施其他风险警示",
                        "source_endpoints": ["tushare.st", "tushare.stock_st"],
                    },
                },
                {
                    "code": "000002",
                    "name": "减持样本",
                    "sector": "机器人",
                    "tomorrow_strength": 98,
                    "score": 98,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "光头大阳柱涨停",
                    "risk_events": [
                        {
                            "risk_type": "holder_reduce",
                            "title": "控股股东拟减持不超过3%公司股份",
                            "source": "tushare.stk_holdertrade",
                        }
                    ],
                },
                {
                    "code": "000003",
                    "name": "异常波动样本",
                    "sector": "机器人",
                    "tomorrow_strength": 97,
                    "score": 97,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "光头大阳柱涨停",
                    "announcement_risks": [
                        {
                            "risk_type": "abnormal_volatility",
                            "title": "股票交易异常波动暨风险提示公告",
                            "url": "https://example.invalid/a.pdf",
                            "source": "tushare.anns_d",
                        }
                    ],
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

        self.assertEqual([item["code"] for item in conviction], ["000988"])

    def test_build_conviction_list_blocks_judicial_forced_sale_announcement(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "通信设备",
                    "tomorrow_strength": 120,
                    "score": 120,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "通信设备辨识度样本",
                    "pattern": "光头大阳柱涨停",
                    "announcement_risks": [
                        {
                            "risk_type": "judicial_forced_sale",
                            "title": "持股5%以上股东所持股份将被法院通过集中竞价方式强制执行卖出",
                            "source": "tushare.anns_d",
                        }
                    ],
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

        self.assertEqual([item["code"] for item in conviction], ["000988"])

    def test_build_conviction_list_blocks_hype_expectation_downgrade_clarification(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "sector": "储能",
                    "tomorrow_strength": 120,
                    "score": 120,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "液冷储能+钠离子电池+固态电池热门题材",
                    "pattern": "光头大阳柱涨停",
                    "announcement_risks": [
                        {
                            "risk_type": "clarification",
                            "title": "关于市场传闻及业务情况的澄清公告",
                            "summary": "液冷储能系统尚未完成交付，尚未形成营业收入；钠离子电池、固态电池处于试点阶段，尚未产生营业收入，距离批量化生产还需要较长周期。",
                            "source": "tushare.anns_d",
                        }
                    ],
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

        self.assertEqual([item["code"] for item in conviction], ["000988"])

    def test_build_conviction_list_blocks_investor_qa_theme_clarification(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "sector": "储能",
                    "tomorrow_strength": 120,
                    "score": 120,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "AIDC数据中心专用电源和储能系统，美国客户合作预期",
                    "pattern": "光头大阳柱涨停",
                    "investor_qa_risks": [
                        {
                            "source": "同花顺金融研究中心问董秘",
                            "question": "公司在AIDC数据中心的专用电源和储能系统和美国客户有合作吗",
                            "answer": "截至目前，公司在AIDC数据中心领域尚未与美国客户达成合作。",
                        }
                    ],
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

        self.assertEqual([item["code"] for item in conviction], ["000988"])

    def test_build_conviction_list_keeps_core_after_hype_downgrade_but_marks_observation(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "sector": "储能",
                    "tomorrow_strength": 132,
                    "score": 132,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "龙一+主线锚定，市场火热但AIDC美国客户合作预期被澄清",
                    "pattern": "T字板",
                    "risk_flags": ["hype_expectation_downgrade"],
                    "investor_qa_risks": [
                        {
                            "source": "tushare.irm_qa_sz",
                            "question": "公司在AIDC数据中心领域是否与美国客户合作？",
                            "answer": "截至目前，公司在AIDC数据中心领域尚未与美国客户达成合作。",
                        }
                    ],
                },
                {
                    "code": "000988",
                    "name": "华工科技",
                    "sector": "光通信",
                    "tomorrow_strength": 92,
                    "score": 92,
                    "change_pct": 10.0,
                    "连板数": 1,
                    "reason": "龙一",
                    "pattern": "光头大阳柱涨停",
                },
            ],
            mainline_name="储能",
            sector_snapshot=[{"sector": "储能", "anchor_code": "002580", "density_score": 95}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        core = next(item for item in conviction if item["code"] == "002580")
        review = core["final_risk_review"]
        self.assertEqual(review["status"], "降级观察")
        self.assertEqual(review["risk_level"], "B")
        self.assertEqual(review["score_penalty"], 30)
        self.assertEqual(review["hype_driver_match"], "current_driver_hit")
        self.assertIn("炒作预期降维", review["reasons"])
        self.assertLess(core["conviction_score"], 132 + 18 + 12 + 8)

    def test_hype_downgrade_penalty_increases_when_clarification_hits_current_driver(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "sector": "储能",
                    "concepts": ["AIDC", "数据中心", "固态电池", "鸿蒙"],
                    "current_driver_tags": ["AIDC", "美国客户", "数据中心"],
                    "tomorrow_strength": 132,
                    "score": 132,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "龙一+主线锚定，当前上涨来自AIDC美国客户合作预期",
                    "pattern": "T字板",
                    "risk_flags": ["hype_expectation_downgrade"],
                    "investor_qa_risks": [
                        {
                            "source": "tushare.irm_qa_sz",
                            "question": "公司在AIDC数据中心领域是否与美国客户合作？",
                            "answer": "截至目前，公司在AIDC数据中心领域尚未与美国客户达成合作。",
                        }
                    ],
                }
            ],
            mainline_name="AIDC",
            sector_snapshot=[{"sector": "AIDC", "anchor_code": "002580", "density_score": 95}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        review = conviction[0]["final_risk_review"]
        self.assertEqual(review["hype_driver_match"], "current_driver_hit")
        self.assertEqual(review["score_penalty"], 30)
        self.assertIn("澄清命中当前上涨主线", review["reasons"])

    def test_current_driver_tags_are_inferred_from_mainline_concepts_and_reason(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "sector": "储能",
                    "concepts": ["AIDC", "数据中心", "固态电池", "鸿蒙"],
                    "xuangubao_related_plate_names": ["AIDC电源", "数据中心"],
                    "tomorrow_strength": 132,
                    "score": 132,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "龙一+主线锚定，当前上涨来自AIDC美国客户合作预期",
                    "pattern": "T字板",
                    "risk_flags": ["hype_expectation_downgrade"],
                    "investor_qa_risks": [
                        {
                            "source": "tushare.irm_qa_sz",
                            "question": "公司在AIDC数据中心领域是否与美国客户合作？",
                            "answer": "截至目前，公司在AIDC数据中心领域尚未与美国客户达成合作。",
                        }
                    ],
                }
            ],
            mainline_name="AIDC",
            sector_snapshot=[{"sector": "AIDC", "anchor_code": "002580", "density_score": 95}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        core = conviction[0]
        self.assertIn("AIDC", core["current_driver_tags"])
        self.assertIn("美国客户", core["current_driver_tags"])
        self.assertIn("数据中心", core["current_driver_tags"])
        self.assertEqual(core["final_risk_review"]["hype_driver_match"], "current_driver_hit")

    def test_hype_downgrade_only_prompts_when_clarification_misses_current_driver(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "sector": "鸿蒙",
                    "concepts": ["AIDC", "数据中心", "固态电池", "鸿蒙"],
                    "current_driver_tags": ["鸿蒙", "开源鸿蒙"],
                    "tomorrow_strength": 132,
                    "score": 132,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "龙一+主线锚定，当前上涨来自鸿蒙生态",
                    "pattern": "T字板",
                    "risk_flags": ["hype_expectation_downgrade"],
                    "investor_qa_risks": [
                        {
                            "source": "tushare.irm_qa_sz",
                            "question": "公司在航天卫星电池产业链是否有计划？",
                            "answer": "截至目前，公司没有进入航天卫星电池产业链的相关计划。",
                        }
                    ],
                }
            ],
            mainline_name="鸿蒙",
            sector_snapshot=[{"sector": "鸿蒙", "anchor_code": "002580", "density_score": 95}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        review = conviction[0]["final_risk_review"]
        self.assertEqual(review["status"], "通过")
        self.assertEqual(review["hype_driver_match"], "driver_miss")
        self.assertEqual(review["score_penalty"], 0)
        self.assertIn("澄清未命中当前上涨主线", review["notes"])

    def test_build_conviction_list_blocks_weak_rebound_below_key_mas_even_with_high_score(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "通信设备",
                    "tomorrow_strength": 120,
                    "score": 120,
                    "change_pct": 1.2,
                    "连板数": 0,
                    "reason": "龙头回头样本",
                    "pattern": "强势反抽",
                    "allow_extreme_conviction": True,
                    "recent_bars": _weak_rebound_below_ma20_bars(),
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

        self.assertEqual([item["code"] for item in conviction], ["000988"])

    def test_trend_aesthetic_rejects_weak_rebound_below_ma20(self):
        review = _build_trend_aesthetic_review(
            {
                "code": "000586",
                "name": "汇源通信",
                "reason": "龙头回头样本",
                "pattern": "强势反抽",
                "recent_bars": _weak_rebound_below_ma20_bars(),
            }
        )

        self.assertEqual(review["status"], "不通过")
        self.assertIn("弱反抽未收回短中线", review["reasons"])
        self.assertIn("MA20下方", review["reasons"])

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
                    "reason": "趋势观察，上升趋势后平台震荡",
                    "pattern": "缩量回踩不破，低点上移",
                    "allow_extreme_conviction": True,
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
                    "reason": "主线内核，趋势比价链核心",
                    "pattern": "上升趋势后平台震荡，缩量回踩不破，低点上移",
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
