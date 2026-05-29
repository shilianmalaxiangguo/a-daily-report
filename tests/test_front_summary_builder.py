import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

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
                    "overtake_window_summary": {
                        "window_state": "confirm_next",
                        "primary_line": "军工",
                        "rival_slowdown": "对手失速仍待确认",
                        "own_stability": "军工资金扩散，核心承接稳定",
                        "observation_maturity": "还在跑圈确认",
                        "overtake_logic": "我方有节奏，但对手打滑仍待确认",
                        "action": "等竞价、开盘承接、回封或09:50-10:10窗口",
                    },
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "单线容量",
                        "mainline_regime": "单主线聚焦",
                        "primary_line": "军工",
                        "other_lines": "-",
                        "confirmation_evidence": "军工净流入和涨停集中",
                        "sector_relationship_state": "单主线聚焦",
                        "mainline_process": "推进",
                        "tomorrow_action": "只围绕军工做减法",
                    },
                },
            },
            final_gate={"final_action": "只做核心"},
            position_level="三档（进攻档）",
            position_reason="环境修复",
            exit_analysis={"sector_name": "军工", "overall_level": "低风险"},
            execution_framework_text="等参与窗口确认",
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
        self.assertEqual(
            payload["opening_tone_text"],
            "对手失速仍待确认；军工资金扩散，核心承接稳定；等竞价、开盘承接、回封或09:50-10:10窗口",
        )
        self.assertEqual(payload["mainline_capacity_regime_summary"]["mainline_regime"], "单主线聚焦")
        self.assertEqual(payload["mainline_capacity_regime_summary"]["primary_line"], "军工")
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

    def test_render_mvp_focus_summary_contract_maps_missing_unique_target_to_zero_position(self):
        payload = render_mvp_focus_summary_contract(
            market_research_snapshot={"state_machine": {"leading_line": "半导体", "execution_bias": "watch_only"}, "style_switch": {}, "observation": {}},
            watchlist=[],
            abnormal_watch_pool=[],
            leader_memory_bank=[],
            core_stocks=[],
            crossline_observation_stocks=[],
            gem_breathing_candidates=[],
            filtered_out_gem_candidates=[],
            structure_layer_text="只看参与窗口是否成立",
            focus_group=[],
            keep_group=[],
            delete_group=[],
            best_stock=None,
            watch_anchor=None,
            watch_anchor_type="",
            abnormal_probe_group={},
            final_gate={"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": False},
            position_level="二档（防守档）",
            target_date="2026-04-24",
            compact=False,
            resolve_primary_mainline_name=lambda *args, **kwargs: "半导体",
            split_abnormal_watch_pool=lambda pool: (pool, []),
            build_bridge_prep_context=lambda **kwargs: {"active": False},
            build_front_structure_layer_text=lambda **kwargs: "只看参与窗口是否成立",
            build_special_probe_verdict=lambda **kwargs: {"summary_text": ""},
            build_special_probe_focus_text=lambda **kwargs: "",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "", "narrative_text": ""},
            split_candidates_by_mainline=lambda watchlist, mainline_name: ([], []),
            format_candidate_preview=lambda items, formatter, limit=2: "",
            candidate_matches_mainline=lambda item, mainline_name: False,
            build_position_sizing_decision=lambda **kwargs: {"branch_20cm": {}},
            build_cycle_triplet_texts=lambda **kwargs: {"observation_cycle": "", "intervention_cycle": "", "exit_cycle": ""},
            build_execute_anchor_window_text=lambda **kwargs: "",
            format_abnormal_probe_text=lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: "",
            build_front_follow_action_text=lambda **kwargs: "0%不参与；没有唯一对象前不抢跑",
            render_mvp_focus_summary=lambda payload: payload,
        )

        self.assertIn("0%不参与", payload["no_trade_text"])
        self.assertIn("没有唯一对象", payload["no_trade_text"])
        self.assertNotIn(_m("30%", "条件试错"), payload["no_trade_text"])
        self.assertNotIn("B档", payload["no_trade_text"])
        self.assertNotIn("只保留市场研究与观察权", payload["no_trade_text"])

    def test_render_mvp_focus_summary_contract_passes_focus_keep_counts_to_position_sizing(self):
        captured_final_gate = {}

        payload = render_mvp_focus_summary_contract(
            market_research_snapshot={"state_machine": {"leading_line": "军工"}, "style_switch": {}, "observation": {}},
            watchlist=[],
            abnormal_watch_pool=[],
            leader_memory_bank=[],
            core_stocks=[],
            crossline_observation_stocks=[],
            gem_breathing_candidates=[],
            filtered_out_gem_candidates=[],
            structure_layer_text="",
            focus_group=[{"name": "军工一号", "code": "000001"}],
            keep_group=[{"name": "军工二号", "code": "000002"}],
            delete_group=[],
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor=None,
            watch_anchor_type="明天唯一能买的那只",
            abnormal_probe_group={},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            target_date="2026-04-22",
            compact=False,
            resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
            split_abnormal_watch_pool=lambda pool: (pool or [], []),
            build_bridge_prep_context=lambda **kwargs: {"active": False},
            build_front_structure_layer_text=lambda **kwargs: "结构层通过",
            build_special_probe_verdict=lambda **kwargs: {"summary_text": ""},
            build_special_probe_focus_text=lambda **kwargs: "",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "", "narrative_text": ""},
            split_candidates_by_mainline=lambda watchlist, mainline_name: ([], []),
            format_candidate_preview=lambda items, formatter, limit=2: "",
            candidate_matches_mainline=lambda item, mainline_name: False,
            build_position_sizing_decision=lambda **kwargs: (
                captured_final_gate.update(kwargs.get("final_gate") or {}) or {"branch_20cm": {}}
            ),
            build_cycle_triplet_texts=lambda **kwargs: {"observation_cycle": "", "intervention_cycle": "", "exit_cycle": ""},
            build_execute_anchor_window_text=lambda **kwargs: "",
            format_abnormal_probe_text=lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: "",
            build_front_follow_action_text=lambda **kwargs: "只等唯一目标确认",
            render_mvp_focus_summary=lambda payload: payload,
        )

        self.assertEqual(captured_final_gate["candidate_count"], 2)
        self.assertEqual(captured_final_gate["unique_target_count"], 2)
        self.assertEqual(payload["front_follow_action_text"], "只等唯一目标确认")

    def test_render_mvp_focus_summary_contract_deduplicates_same_stock_for_unique_target_count(self):
        captured_final_gate = {}

        render_mvp_focus_summary_contract(
            market_research_snapshot={"state_machine": {"leading_line": "军工"}, "style_switch": {}, "observation": {}},
            focus_group=[{"name": "军工一号", "code": "000001"}],
            keep_group=[{"name": "军工一号", "code": "000001", "sector": "军工", "direction": "低空经济"}],
            best_stock={"name": "军工一号", "code": "000001"},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            target_date="2026-04-22",
            resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
            split_abnormal_watch_pool=lambda pool: (pool or [], []),
            build_bridge_prep_context=lambda **kwargs: {"active": False},
            build_front_structure_layer_text=lambda **kwargs: "结构层通过",
            build_special_probe_verdict=lambda **kwargs: {"summary_text": ""},
            build_special_probe_focus_text=lambda **kwargs: "",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "", "narrative_text": ""},
            split_candidates_by_mainline=lambda watchlist, mainline_name: ([], []),
            format_candidate_preview=lambda items, formatter, limit=2: "",
            candidate_matches_mainline=lambda item, mainline_name: False,
            build_position_sizing_decision=lambda **kwargs: (
                captured_final_gate.update(kwargs.get("final_gate") or {}) or {"branch_20cm": {}}
            ),
            build_cycle_triplet_texts=lambda **kwargs: {"observation_cycle": "", "intervention_cycle": "", "exit_cycle": ""},
            build_execute_anchor_window_text=lambda **kwargs: "",
            format_abnormal_probe_text=lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: "",
            build_front_follow_action_text=lambda **kwargs: "只等唯一目标确认",
            render_mvp_focus_summary=lambda payload: payload,
        )

        self.assertEqual(captured_final_gate["candidate_count"], 2)
        self.assertEqual(captured_final_gate["unique_target_count"], 1)

    def test_render_mvp_focus_summary_contract_keeps_background_core_anchor_out_of_position_sizing(self):
        captured_position_kwargs = {}

        payload = render_mvp_focus_summary_contract(
            market_research_snapshot={"state_machine": {"leading_line": "军工"}, "style_switch": {}, "observation": {}},
            watchlist=[],
            abnormal_watch_pool=[],
            leader_memory_bank=[{"name": "记忆龙头", "code": "000002", "sector": "军工"}],
            core_stocks=[{"name": "旧核心", "code": "000001", "sector": "军工", "core_level": "昨日核心"}],
            crossline_observation_stocks=[],
            gem_breathing_candidates=[],
            filtered_out_gem_candidates=[],
            structure_layer_text="",
            focus_group=[],
            keep_group=[],
            delete_group=[],
            best_stock={"name": "创业弹性", "code": "300001", "sector": "军工"},
            watch_anchor=None,
            watch_anchor_type="重点观察谁",
            abnormal_probe_group={},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            target_date="2026-04-22",
            compact=False,
            resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
            split_abnormal_watch_pool=lambda pool: (pool or [], []),
            build_bridge_prep_context=lambda **kwargs: {"active": False},
            build_front_structure_layer_text=lambda **kwargs: "结构层通过",
            build_special_probe_verdict=lambda **kwargs: {"summary_text": ""},
            build_special_probe_focus_text=lambda **kwargs: "",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "", "narrative_text": ""},
            split_candidates_by_mainline=lambda watchlist, mainline_name: ([], []),
            format_candidate_preview=lambda items, formatter, limit=2: " / ".join(formatter(item) for item in items[:limit]),
            candidate_matches_mainline=lambda item, mainline_name: item.get("sector") == mainline_name,
            build_position_sizing_decision=lambda **kwargs: (
                captured_position_kwargs.update(kwargs) or {"branch_20cm": {}}
            ),
            build_cycle_triplet_texts=lambda **kwargs: {"observation_cycle": "", "intervention_cycle": "", "exit_cycle": ""},
            build_execute_anchor_window_text=lambda **kwargs: "",
            format_abnormal_probe_text=lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: "",
            build_front_follow_action_text=lambda **kwargs: "只等唯一目标确认",
            render_mvp_focus_summary=lambda payload: payload,
        )

        self.assertEqual(captured_position_kwargs["mainline_anchor"], {})
        self.assertIn("旧核心", payload["core_preview"])
        self.assertIn("记忆龙头", payload["memory_preview"])

    def test_render_mvp_focus_summary_contract_keeps_background_memory_anchor_out_of_position_sizing(self):
        captured_position_kwargs = {}

        payload = render_mvp_focus_summary_contract(
            market_research_snapshot={"state_machine": {"leading_line": "军工"}, "style_switch": {}, "observation": {}},
            watchlist=[],
            abnormal_watch_pool=[],
            leader_memory_bank=[{"name": "记忆龙头", "code": "000002", "sector": "军工"}],
            core_stocks=[],
            crossline_observation_stocks=[],
            gem_breathing_candidates=[],
            filtered_out_gem_candidates=[],
            structure_layer_text="",
            focus_group=[],
            keep_group=[],
            delete_group=[],
            best_stock={"name": "创业弹性", "code": "300001", "sector": "军工"},
            watch_anchor=None,
            watch_anchor_type="重点观察谁",
            abnormal_probe_group={},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            target_date="2026-04-22",
            compact=False,
            resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
            split_abnormal_watch_pool=lambda pool: (pool or [], []),
            build_bridge_prep_context=lambda **kwargs: {"active": False},
            build_front_structure_layer_text=lambda **kwargs: "结构层通过",
            build_special_probe_verdict=lambda **kwargs: {"summary_text": ""},
            build_special_probe_focus_text=lambda **kwargs: "",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "", "narrative_text": ""},
            split_candidates_by_mainline=lambda watchlist, mainline_name: ([], []),
            format_candidate_preview=lambda items, formatter, limit=2: "",
            candidate_matches_mainline=lambda item, mainline_name: item.get("sector") == mainline_name,
            build_position_sizing_decision=lambda **kwargs: (
                captured_position_kwargs.update(kwargs) or {"branch_20cm": {}}
            ),
            build_cycle_triplet_texts=lambda **kwargs: {"observation_cycle": "", "intervention_cycle": "", "exit_cycle": ""},
            build_execute_anchor_window_text=lambda **kwargs: "",
            format_abnormal_probe_text=lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: "",
            build_front_follow_action_text=lambda **kwargs: "只等唯一目标确认",
            render_mvp_focus_summary=lambda payload: payload,
        )

        self.assertEqual(captured_position_kwargs["mainline_anchor"], {})
        self.assertIn("记忆龙头", payload["memory_preview"])

    def test_render_mvp_focus_summary_contract_does_not_render_fallback_watch_anchor_as_mainline_abnormal_probe(self):
        payload = render_mvp_focus_summary_contract(
            market_research_snapshot={"state_machine": {"leading_line": "军工"}, "style_switch": {}, "observation": {}},
            watchlist=[],
            abnormal_watch_pool=[],
            leader_memory_bank=[],
            core_stocks=[],
            crossline_observation_stocks=[],
            gem_breathing_candidates=[],
            filtered_out_gem_candidates=[],
            structure_layer_text="",
            focus_group=[],
            keep_group=[],
            delete_group=[],
            best_stock=None,
            watch_anchor={"name": "普通观察", "code": "000009", "watch_anchor_note": "只看强弱"},
            watch_anchor_type="重点观察谁",
            abnormal_probe_group={"fallback_watch_anchor": {"name": "普通观察", "code": "000009"}},
            final_gate={"can_new_entry": False},
            position_level="二档（防守档）",
            target_date="2026-04-22",
            compact=False,
            resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
            split_abnormal_watch_pool=lambda pool: (pool or [], []),
            build_bridge_prep_context=lambda **kwargs: {"active": False},
            build_front_structure_layer_text=lambda **kwargs: "结构层通过",
            build_special_probe_verdict=lambda **kwargs: {"summary_text": ""},
            build_special_probe_focus_text=lambda **kwargs: "",
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "", "narrative_text": ""},
            split_candidates_by_mainline=lambda watchlist, mainline_name: ([], []),
            format_candidate_preview=lambda items, formatter, limit=2: "",
            candidate_matches_mainline=lambda item, mainline_name: False,
            build_position_sizing_decision=lambda **kwargs: {"branch_20cm": {}},
            build_cycle_triplet_texts=lambda **kwargs: {"observation_cycle": "", "intervention_cycle": "", "exit_cycle": ""},
            build_execute_anchor_window_text=lambda **kwargs: "",
            format_abnormal_probe_text=lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: (
                f"{role_label}:{(probe or fallback_watch_anchor or {}).get('name', '-')}"
            ),
            build_front_follow_action_text=lambda **kwargs: "只观察不参与",
            render_mvp_focus_summary=lambda payload: payload,
        )

        self.assertEqual(payload["mainline_probe_text"], "")
        self.assertIn("普通观察(000009)", payload["watch_target_text"])
        self.assertIn("不构成买入指令", payload["watch_target_text"])


if __name__ == "__main__":
    unittest.main()
