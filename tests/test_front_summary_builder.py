import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.front_summary_builder import (
    build_double_mainline_summary_contract,
    build_turnover_share_trend_contract,
    render_core_mvp_digest_contract,
    render_mvp_focus_summary_contract,
)


class FrontSummaryBuilderTest(unittest.TestCase):
    def test_build_double_mainline_summary_contract_promotes_cycle_and_attack_line(self):
        payload = build_double_mainline_summary_contract(
            {
                "cycle_mainline": "半导体",
                "daily_attack_line": "算力",
                "relationship": "当天主攻线是周期主线内部加强，不是新主线切换",
                "tomorrow_action": "明天继续围绕半导体做减法，只看算力核心承接",
            }
        )

        self.assertEqual(payload["cycle_mainline"], "半导体")
        self.assertEqual(payload["daily_attack_line"], "算力")
        self.assertEqual(payload["relationship"], "当天主攻线是周期主线内部加强，不是新主线切换")
        self.assertEqual(payload["tomorrow_action"], "明天继续围绕半导体做减法，只看算力核心承接")

    def test_build_turnover_share_trend_contract_keeps_required_amount_fields(self):
        rows = build_turnover_share_trend_contract(
            [
                {
                    "date": "04-24",
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "算力",
                    "mainline_turnover": "2180亿",
                    "market_turnover": "12834亿",
                    "share": "17.0%",
                    "share_change": "+1.2pct",
                    "interpretation": "主线占比继续抬升，资金仍在主线内加强",
                }
            ]
        )

        self.assertEqual(rows[0]["mainline_turnover"], "2180亿")
        self.assertEqual(rows[0]["market_turnover"], "12834亿")
        self.assertEqual(rows[0]["share_change"], "+1.2pct")

    def test_render_core_mvp_digest_contract_composes_digest_payload(self):
        payload = render_core_mvp_digest_contract(
            market_research_snapshot={
                "observation": {},
                "style_switch": {"high_board_count": 2},
                "state_machine": {"energy_state": "修复", "state_reason": "主线回流"},
                "follow_verdict": {"label": "🟢 跟随主线"},
                "dialectical_decision": {"stage_label": "主升", "stage_action": "继续跟随", "index_profit_relation": "指数和赚钱效应同向"},
                "mainline_turnover_summary": {
                    "conclusion": "主线未切换，军工仍是中心",
                    "data_text": "成交额占比 10.2% -> 12.8% -> 15.1%，节奏偏强化",
                },
            },
            final_gate={"final_action": "只做核心"},
            position_level="三档（进攻档）",
            position_reason="环境修复",
            exit_analysis={"sector_name": "军工", "overall_level": "低风险"},
            execution_framework_text="等60分钟确认",
            high_board_count=3,
            structure_layer_text="结构层通过",
            front_follow_action_text="只做核心",
            special_probe_text="先看异常承接",
            philosophy_constraint_text="不抢跑",
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor={"name": "观察股"},
            watch_anchor_type="重点观察谁",
            target_date="2026-04-22",
            compact=True,
            build_front_mainline_label=lambda market_research_snapshot, fallback_mainline="": "主攻线军工",
            build_gem_textbook_next_step_text=lambda watch_anchor, position_decision=None: "20cm只观察",
            build_front_style_action_text=lambda **kwargs: "轮动；先缩范围",
            build_alignment_pool_text=lambda **kwargs: "月度站队池：军工",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "军工继续聚焦", "narrative_text": "资金抱团"},
            resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
            build_weak_to_strong_context=lambda **kwargs: {"active": True, "summary_text": "弱转强只看唯一目标"},
            get_contract_logic_digest_text=lambda: "环境 -> 主线 -> 执行",
            render_front_digest=lambda payload: payload,
            safe_float=lambda value: float(value or 0),
        )

        self.assertEqual(payload["mainline_label"], "主攻线军工")
        self.assertEqual(payload["mainline_turnover_text"], "主线未切换，军工仍是中心；成交额占比 10.2% -> 12.8% -> 15.1%，节奏偏强化")
        self.assertEqual(payload["rotation_summary_text"], "军工继续聚焦")
        self.assertTrue(payload["weak_to_strong_active"])
        self.assertIn("跌停", " / ".join(payload["risk_parts"]))
        self.assertEqual(payload["compact"], True)

    def test_render_mvp_focus_summary_contract_builds_target_sections(self):
        payload = render_mvp_focus_summary_contract(
            market_research_snapshot={"state_machine": {"state_code": "expand"}, "style_switch": {}, "observation": {}},
            watchlist=[
                {"name": "军工一号", "sector": "军工"},
                {"name": "机器人一号", "sector": "机器人"},
            ],
            abnormal_watch_pool=[{"name": "军工一号", "follow_state": "承接"}, {"name": "降级样本", "follow_state": "观察"}],
            leader_memory_bank=[{"name": "记忆龙头", "sector": "军工"}],
            core_stocks=[{"name": "军工一号", "sector": "军工", "core_level": "明日核心"}],
            crossline_observation_stocks=[{"name": "跨线一号", "core_level": "观察"}],
            gem_breathing_candidates=[{"name": "创业观察", "code": "300001", "tier": "T1", "note": "有预热"}],
            filtered_out_gem_candidates=[{"name": "非主线创业", "code": "300002", "sector": "机器人", "filtered_reason": "非主线"}],
            structure_layer_text="结构只看唯一目标",
            focus_group=[],
            keep_group=[],
            delete_group=[{"name": "弱股一号"}],
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor={"name": "观察股", "code": "000009"},
            watch_anchor_type="重点观察谁",
            abnormal_probe_group={"fallback_watch_anchor": {"name": "观察股", "code": "000009"}},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            target_date="2026-04-22",
            compact=False,
            resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
            split_abnormal_watch_pool=lambda pool: (pool[:1], pool[1:]),
            build_bridge_prep_context=lambda **kwargs: {
                "active": True,
                "priority_keep": True,
                "candidate_label": "观察股",
                "upgrade_text": "确认后升级",
            },
            build_front_structure_layer_text=lambda **kwargs: "结构只看唯一目标",
            build_special_probe_verdict=lambda **kwargs: {"summary_text": "先看主线异动", "action": "看军工异常"},
            build_special_probe_focus_text=lambda **kwargs: "先看军工异常股",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "军工轮动", "narrative_text": "主线抱团"},
            split_candidates_by_mainline=lambda watchlist, mainline_name: ([watchlist[0]], [watchlist[1]]),
            format_candidate_preview=lambda items, formatter, limit=2: " / ".join(formatter(item) for item in items[:limit]),
            candidate_matches_mainline=lambda item, mainline_name: item.get("sector") == mainline_name,
            build_position_sizing_decision=lambda **kwargs: {"branch_20cm": {}},
            build_cycle_triplet_texts=lambda **kwargs: {
                "observation_cycle": "日线",
                "intervention_cycle": "60分钟",
                "exit_cycle": "30分钟",
            },
            build_execute_anchor_window_text=lambda **kwargs: "",
            format_abnormal_probe_text=lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: (
                f"{role_label}:{(probe or fallback_watch_anchor or {}).get('name', '-')}"
            ),
            build_front_follow_action_text=lambda **kwargs: "只等唯一目标确认",
            render_mvp_focus_summary=lambda payload: payload,
        )

        self.assertEqual(payload["mainline_watch_preview"], "军工一号(军工)")
        self.assertIn("创业观察", payload["gem_breathing_text"])
        self.assertIn("军工一号(000001)", payload["buy_target_text"])
        self.assertEqual(payload["bridge_prep_label"], "条件执行预备态（优先保留）")
        self.assertIn("弱股一号", payload["delete_preview"])
        self.assertEqual(payload["front_follow_action_text"], "只等唯一目标确认")


if __name__ == "__main__":
    unittest.main()
