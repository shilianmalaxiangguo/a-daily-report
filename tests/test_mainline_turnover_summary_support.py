import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.mainline_turnover_summary_support import (
    normalize_display_text_by_tag_pool,
    resolve_display_mainline_name,
    resolve_mainline_attack_evidence_rows,
    resolve_mainline_attack_evidence_summary,
    resolve_mainline_capacity_regime_summary,
    resolve_overtake_opening_tone_text,
    resolve_overtake_window_rows,
    resolve_overtake_window_summary,
    resolve_trading_arena_fit_rows,
    resolve_trading_arena_fit_summary,
    resolve_turnover_share_trend_rows,
)


class MainlineTurnoverSummarySupportTest(unittest.TestCase):
    def test_resolve_display_mainline_name_prefers_confirmed_adopted_label(self):
        context = {
            "exit_analysis": {"sector_name": "元件"},
            "mainline_turnover_summary": {
                "current_mainline": "国产芯片替代",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "国产芯片替代",
                    "confirmation_evidence": "国产芯片替代资金净流入靠前，涨停和高标更集中",
                    "sector_evidence_rows": [
                        {
                            "sector_name": "国产芯片替代",
                            "surface_sector_names": ["元件", "元器件"],
                            "net_inflow_rank": 1,
                        }
                    ],
                },
            },
        }

        self.assertEqual(resolve_display_mainline_name(context), "国产芯片替代")
        self.assertEqual(resolve_display_mainline_name(context, fallback="元件"), "国产芯片替代")

    def test_resolve_display_mainline_name_can_map_surface_label_from_tag_snapshot(self):
        context = {
            "realtime_tag_evidence_snapshot": {
                "groups": [
                    {
                        "采用名称": "国产芯片替代",
                        "关系判断": "父子",
                        "表层行业名": ["元件", "元器件"],
                    }
                ]
            }
        }

        self.assertEqual(resolve_display_mainline_name(context, fallback="元件"), "国产芯片替代")

    def test_normalize_display_text_by_tag_pool_maps_current_decision_terms(self):
        context = {
            "realtime_tag_evidence_snapshot": {
                "groups": [
                    {
                        "采用名称": "国产芯片替代",
                        "关系判断": "父子",
                        "表层行业名": ["元件", "元器件"],
                    }
                ]
            }
        }

        text = "主攻线元件 / 次强线电力；赚钱效应继续向元器件聚集；先盯元件的承接是否继续"

        self.assertEqual(
            normalize_display_text_by_tag_pool(text, context),
            "主攻线国产芯片替代 / 次强线电力；赚钱效应继续向国产芯片替代聚集；先盯国产芯片替代的承接是否继续",
        )

    def test_normalize_display_text_by_tag_pool_does_not_replace_short_term_inside_longer_word(self):
        context = {
            "realtime_tag_evidence_snapshot": {
                "groups": [
                    {
                        "采用名称": "国产芯片替代",
                        "关系判断": "父子",
                        "表层行业名": ["元件"],
                    }
                ]
            }
        }

        self.assertEqual(
            normalize_display_text_by_tag_pool("被动元件/MLCC只作原始概念观察", context),
            "被动元件/MLCC只作原始概念观察",
        )

    def test_resolve_mainline_capacity_regime_summary_derives_from_nested_legacy_double_mainline(self):
        summary = resolve_mainline_capacity_regime_summary(
            {
                "mainline_turnover_summary": {
                    "double_mainline_summary": {
                        "cycle_mainline": "电力",
                        "daily_attack_line": "半导体",
                        "relationship": "半导体尝试接替电力",
                        "tomorrow_action": "先看资金是否继续选择半导体",
                    }
                }
            }
        )

        self.assertEqual(summary["mainline_capacity"], "容量待累计")
        self.assertEqual(summary["mainline_regime"], "主线+背景线")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["other_lines"], "电力")
        self.assertEqual(summary["sector_relationship_state"], "半导体尝试接替电力")
        self.assertEqual(summary["tomorrow_action"], "先看资金是否继续选择半导体")

    def test_resolve_mainline_attack_evidence_summary_from_nested_turnover_summary(self):
        summary = resolve_mainline_attack_evidence_summary(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "background_lines": ["化学制品"],
                        "relationship_hint": "双主线竞争",
                        "evidence_labels": ["资金净流入靠前", "批量涨停"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停更集中",
                        "evidence_gaps": [],
                    }
                }
            }
        )

        self.assertEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["candidate_lines"], ["电力"])
        self.assertEqual(summary["background_lines"], ["化学制品"])

    def test_resolve_mainline_attack_evidence_rows_formats_top_three_audit_rows(self):
        rows = resolve_mainline_attack_evidence_rows(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                        "sector_evidence_rows": [
                            {
                                "sector_name": "半导体",
                                "net_inflow_rank": 1,
                                "net_inflow_amount": 45.0,
                                "limit_up_count": 5,
                                "high_anchor_height": 4,
                                "turnover_share_change": 1.6,
                            },
                            {
                                "sector_name": "电力",
                                "net_inflow_rank": 2,
                                "net_inflow_amount": 8.0,
                                "limit_up_count": 1,
                                "high_anchor_height": 1,
                                "turnover_share_change": -0.5,
                            },
                            {
                                "sector_name": "化学制品",
                                "net_inflow_rank": 5,
                                "net_inflow_amount": 3.2,
                                "limit_up_count": 2,
                                "high_anchor_height": 2,
                            },
                            {
                                "sector_name": "消费",
                                "net_inflow_rank": 8,
                                "net_inflow_amount": 1.0,
                                "limit_up_count": 1,
                            },
                        ],
                    }
                }
            }
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["sector_name"], "半导体")
        self.assertEqual(rows[0]["attack_state"], "确认主攻线")
        self.assertEqual(rows[0]["net_inflow_rank"], "第1")
        self.assertEqual(rows[0]["net_inflow_amount"], "+45.00亿")
        self.assertEqual(rows[0]["limit_up_count"], "5")
        self.assertEqual(rows[0]["high_anchor_height"], "4")
        self.assertEqual(rows[0]["turnover_share_change"], "+1.6pct")
        self.assertEqual(rows[0]["conclusion"], "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张")
        self.assertEqual(rows[1]["attack_state"], "候选线")

    def test_resolve_mainline_attack_evidence_rows_maps_stale_auto_parts_summary_to_robot_narrative(self):
        summary = {
            "mainline_turnover_summary": {
                "mainline_attack_evidence_summary": {
                    "attack_state": "chaotic_rotation",
                    "candidate_lines": ["汽车零部件", "生物制药", "白色家电"],
                    "sector_evidence_rows": [
                        {
                            "sector_name": "汽车零部件",
                            "net_inflow_rank": 1,
                            "net_inflow_amount": 30.0,
                            "sector_turnover": 778.0,
                            "turnover_share_pct": 2.22,
                        },
                        {
                            "sector_name": "电机",
                            "net_inflow_rank": 3,
                            "net_inflow_amount": 9.0,
                            "sector_turnover": 102.0,
                            "turnover_share_pct": 0.29,
                        },
                        {
                            "sector_name": "生物制药",
                            "limit_up_count": 3,
                            "high_anchor_height": 7,
                        },
                    ],
                }
            }
        }

        resolved_summary = resolve_mainline_attack_evidence_summary(summary)
        rows = resolve_mainline_attack_evidence_rows(summary)

        self.assertEqual(resolved_summary["candidate_lines"][0], "人形机器人")
        self.assertEqual(rows[0]["sector_name"], "人形机器人")
        self.assertIn("人形机器人仍是候选线", rows[0]["conclusion"])
        self.assertEqual(rows[0]["net_inflow_amount"], "+39.00亿")

    def test_resolve_mainline_attack_evidence_rows_ignores_board_labels(self):
        rows = resolve_mainline_attack_evidence_rows(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "candidate_attack",
                        "candidate_lines": ["HS", "通信设备", "元件"],
                        "sector_evidence_rows": [
                            {"sector_name": "HS", "limit_up_count": 91, "high_anchor_height": 9},
                            {"sector_name": "GEM", "limit_up_count": 9, "high_anchor_height": 3},
                            {
                                "sector_name": "通信设备",
                                "net_inflow_rank": 1,
                                "net_inflow_amount": 50.0,
                                "limit_up_count": 4,
                                "high_anchor_height": 2,
                            },
                            {"sector_name": "元件", "net_inflow_rank": 2, "net_inflow_amount": 28.0},
                        ],
                    }
                }
            }
        )

        self.assertEqual([row["sector_name"] for row in rows], ["通信设备", "元件"])

        self.assertTrue(all("HS" not in row["conclusion"] for row in rows))

    def test_resolve_mainline_attack_evidence_rows_does_not_render_missing_values_as_zero(self):
        rows = resolve_mainline_attack_evidence_rows(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "background_lines": ["软件服务"],
                        "sector_evidence_rows": [
                            {
                                "sector_name": "半导体",
                                "net_inflow_rank": 1,
                                "net_inflow_amount": 184.0,
                                "limit_up_count": 4,
                                "high_anchor_height": 300,
                                "missing_fields": ["turnover_share_change"],
                            },
                            {
                                "sector_name": "软件服务",
                                "net_inflow_amount": 0.0,
                                "net_inflow_rank": 999,
                                "limit_up_count": 8,
                                "high_anchor_height": 50,
                                "turnover_share_change": 0.0,
                                "missing_fields": [
                                    "net_inflow_amount",
                                    "net_inflow_rank",
                                    "turnover_share_change",
                                ],
                            },
                        ],
                    }
                }
            }
        )

        self.assertEqual(rows[0]["turnover_share_change"], "-")
        self.assertEqual(rows[1]["net_inflow_rank"], "-")
        self.assertEqual(rows[1]["net_inflow_amount"], "-")
        self.assertEqual(rows[1]["turnover_share_change"], "-")

    def test_resolve_turnover_share_trend_rows_preserves_history_labels_when_current_attack_unconfirmed(self):
        rows = resolve_turnover_share_trend_rows(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "confirmation_evidence": "多线分散，主攻线尚未胜出",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-05-19",
                            "cycle_mainline": "电力",
                            "daily_attack_line": "电力",
                            "mainline_turnover": "665.00亿",
                            "market_turnover": "29089.77亿",
                            "share": "2.3%",
                            "share_change": "+0.6pct",
                            "interpretation": "电力支线轮动，先看回流强度",
                        },
                        {
                            "date": "2026-05-20",
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "4050.00亿",
                            "market_turnover": "29764.59亿",
                            "share": "13.6%",
                            "share_change": "+1.5pct",
                            "interpretation": "半导体支线轮动，成交额占比明显抬升",
                        },
                    ],
                }
            }
        )

        self.assertEqual(rows[0]["cycle_mainline"], "电力")
        self.assertEqual(rows[0]["daily_attack_line"], "电力")
        self.assertEqual(rows[0]["interpretation"], "电力支线轮动，先看回流强度")
        self.assertEqual(rows[1]["cycle_mainline"], "半导体")
        self.assertEqual(rows[1]["daily_attack_line"], "半导体")
        self.assertEqual(rows[1]["interpretation"], "半导体支线轮动，成交额占比明显抬升")

    def test_resolve_overtake_window_summary_from_turnover_summary(self):
        summary = resolve_overtake_window_summary(
            {
                "mainline_turnover_summary": {
                    "overtake_window_summary": {
                        "window_state": "open",
                        "primary_line": "半导体",
                        "rival_slowdown": "旧主线承接转弱",
                        "own_stability": "半导体资金扩散，核心承接稳定",
                        "observation_maturity": "跑过一段后再判断",
                        "overtake_logic": "对手过弯打滑，我方仍能弯道加速",
                        "arena_boundary": "短线/超短主战场内主动出手",
                        "speed_gap": "失速差拉开",
                        "action": "只在半导体核心里找参与资格",
                    }
                }
            }
        )

        self.assertEqual(summary["window_state"], "open")
        self.assertEqual(summary["observation_maturity"], "跑过一段后再判断")
        self.assertEqual(summary["overtake_logic"], "对手过弯打滑，我方仍能弯道加速")
        self.assertEqual(summary["arena_boundary"], "短线/超短主战场内主动出手")
        self.assertEqual(summary["action"], "只在半导体核心里找参与资格")

    def test_resolve_overtake_opening_tone_text_compacts_window_summary(self):
        tone = resolve_overtake_opening_tone_text(
            {
                "mainline_turnover_summary": {
                    "overtake_window_summary": {
                        "window_state": "open",
                        "primary_line": "半导体",
                        "rival_slowdown": "旧主线承接转弱，竞争线冲高回落",
                        "own_stability": "半导体资金扩散，核心承接稳定",
                        "observation_maturity": "跑过一段后再判断",
                        "overtake_logic": "对手过弯打滑，我方仍能弯道加速",
                        "action": "只在半导体核心里找参与资格",
                    }
                }
            }
        )

        self.assertEqual(
            tone,
            "旧主线承接转弱，竞争线冲高回落；半导体资金扩散，核心承接稳定；只在半导体核心里找参与资格",
        )

    def test_resolve_overtake_window_rows_returns_front_table_row(self):
        rows = resolve_overtake_window_rows(
            {
                "overtake_window_summary": {
                    "window_state": "observe",
                    "rival_slowdown": "多方向都有局部热度",
                    "own_stability": "当前方向强度不足",
                    "observation_maturity": "样本不足，继续跑圈观察",
                    "overtake_logic": "未形成对手打滑、我方加速的差值",
                    "arena_boundary": "不为制造动作扩大战法",
                    "speed_gap": "未拉开",
                    "action": "仅观察，不给新增参与资格",
                }
            }
        )

        self.assertEqual(
            rows,
            [
                {
                    "rival_line": "旧主线",
                    "rival_slowdown": "多方向都有局部热度",
                    "own_line": "-",
                    "own_stability": "当前方向强度不足",
                    "observation_maturity": "样本不足，继续跑圈观察",
                    "overtake_logic": "未形成对手打滑、我方加速的差值",
                    "arena_boundary": "不为制造动作扩大战法",
                    "speed_gap": "未拉开",
                    "failure_condition": "对手重新放量回流或我方开盘不承接",
                    "action": "仅观察，不给新增参与资格",
                }
            ],
        )

    def test_resolve_trading_arena_fit_summary_from_turnover_summary(self):
        summary = resolve_trading_arena_fit_summary(
            {
                "mainline_turnover_summary": {
                    "trading_arena_fit_summary": {
                        "fit_state": "home_arena",
                        "arena_label": "短线/超短线主战场",
                        "market_style": "单主线聚焦",
                        "fit_reason": "量能、资金扩散、板块效应和核心承接进入短线/超短线可发挥区",
                        "action": "按短线/超短线主战场处理，围绕半导体核心继续寻找参与资格",
                    }
                }
            }
        )

        self.assertEqual(summary["fit_state"], "home_arena")
        self.assertEqual(summary["arena_label"], "短线/超短线主战场")

    def test_resolve_trading_arena_fit_rows_returns_front_table_row(self):
        rows = resolve_trading_arena_fit_rows(
            {
                "trading_arena_fit_summary": {
                    "fit_state": "low_fit",
                    "arena_label": "非主战场",
                    "market_style": "趋势容量",
                    "fit_reason": "更接近趋势容量、机构抱团或慢推行情，不是当前短线/超短线主战场",
                    "action": "不扩战法，不为证明全能而新增参与，只保持不拖后腿",
                }
            }
        )

        self.assertEqual(
            rows,
            [
                {
                    "arena_label": "非主战场",
                    "market_style": "趋势容量",
                    "fit_reason": "更接近趋势容量、机构抱团或慢推行情，不是当前短线/超短线主战场",
                    "action": "不扩战法，不为证明全能而新增参与，只保持不拖后腿",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
