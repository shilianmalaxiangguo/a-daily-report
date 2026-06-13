import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from domains.execution_chain.candidate_selection_stage import (
    build_candidate_selection_stage,
    build_candidate_selection_runtime,
)
from domains.execution_chain.candidate_selection_nodes.conviction_list import (
    build_candidate_selection_conviction_list_node,
)
from domains.execution_chain.stage_runtime import build_execution_stage_lookup


class CandidateSelectionStageTest(unittest.TestCase):
    def test_candidate_selection_stage_uses_dynamic_stage_labels_and_exports_step2_bundle(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
            ]
        )

        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-22",
                "exit_analysis": {"sector_name": "军工"},
                "candidates": [{"name": "军工一号", "code": "000001"}],
                "watchlist": [{"name": "军工一号", "code": "000001", "sector": "军工", "score": 91}],
                "abnormal_watch_map": {"000001": {"follow_state": "跌不下去"}},
                "dragon_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工"}],
                "zt_pool_by_sector": {"军工": [{"name": "军工一号"}]},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["军工"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy gem renderer should not be called")),
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "tomorrow_strength": 91}],
                    "core_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "pattern": "涨停", "abnormal_summary": "跌不下去", "tomorrow_strength": 91, "core_level": "🔥 连板核心", "tmr_forecast": "2进3"}],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [{"sector": "军工", "trend_count": 3, "core_count": 1, "anchor_name": "军工一号", "anchor_code": "000001", "density_score": 88, "anchor_reason": "主线龙头"}],
                    "extreme_conviction_list": [{"name": "军工一号", "code": "000001", "sector": "军工", "conviction_reason": "主线最强", "conviction_rule": _m("只等", "60分钟确认")}],
                    "mainline_name": "军工",
                    "module_logs": [{"module": "selection.candidate_bundle_runtime", "step": "candidate_grouping", "status": "success", "message": "已完成主线分组", "details": {}}],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            stage_lookup["candidate_selection"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 2 - 明日核心标的", rendered)
        self.assertIn("> **先看结论**：从观察池继续缩到明日核心、次核心和跨线观察。", rendered)
        self.assertIn("> **只留什么**：主线最强的留核心，跨线观察只留观察。", rendered)
        self.assertIn("**主线内可执行候选**", rendered)
        self.assertIn("**龙头资格反推结果**", rendered)
        self.assertIn("板块锚与身份", rendered)
        self.assertIn("均线回归试错", rendered)
        self.assertIn("MA20作废", rendered)
        self.assertIn("跟踪周期", rendered)
        self.assertIn("分时黄线", rendered)
        self.assertNotIn("gem-section", rendered)
        self.assertEqual(result["exports"]["step2_bundle"]["mainline_name"], "军工")
        self.assertEqual(result["exports"]["core_stocks"][0]["code"], "000001")
        self.assertEqual(result["exports"]["mainline_in_quadrant"], None)
        self.assertTrue(any(log["module"] == "selection.candidate_bundle_runtime" for log in result["module_logs"]))

    def test_candidate_selection_summary_downgrades_primary_line_when_attack_evidence_is_chaotic(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-05-14",
                "exit_analysis": {"sector_name": "半导体"},
                "candidates": [{"name": "中船特气", "code": "688146"}],
                "watchlist": [{"name": "中船特气", "code": "688146", "sector": "半导体", "score": 65}],
                "abnormal_watch_map": {},
                "dragon_stocks": [{"name": "中船特气", "code": "688146", "sector": "半导体"}],
                "zt_pool_by_sector": {"半导体": [{"name": "中船特气"}]},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda *args, **kwargs: [],
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    },
                    "mainline_capacity_regime_summary": {
                        "mainline_regime": "无主线",
                        "primary_line": "暂无",
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    },
                },
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [{"name": "中船特气", "code": "688146", "sector": "半导体", "tomorrow_strength": 65}],
                    "core_stocks": [{"name": "中船特气", "code": "688146", "sector": "半导体", "tomorrow_strength": 65}],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["mainline_summary"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**明日核心方向预判**: 无确认主攻线", rendered)
        self.assertIn("多方向局部活跃但资金未明显胜出", rendered)
        self.assertNotIn("认准'半导体'", rendered)
        self.assertNotIn("主线内1只", rendered)

    def test_candidate_selection_summary_uses_confirmed_attack_line_over_stale_exit_sector(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-05-21",
                "exit_analysis": {"sector_name": "半导体"},
                "candidates": [{"name": "华微电子", "code": "600360"}],
                "watchlist": [{"name": "华微电子", "code": "600360", "sector": "半导体", "score": 65}],
                "abnormal_watch_map": {},
                "dragon_stocks": [{"name": "华微电子", "code": "600360", "sector": "半导体"}],
                "zt_pool_by_sector": {"半导体": [{"name": "华微电子"}]},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda *args, **kwargs: [],
                "mainline_turnover_summary": {
                    "share_trend_label": "逆势试攻",
                    "current_mainline": "人形机器人",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    },
                },
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [{"name": "华微电子", "code": "600360", "sector": "半导体", "tomorrow_strength": 50}],
                    "core_stocks": [{"name": "华微电子", "code": "600360", "sector": "半导体", "tomorrow_strength": 50}],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["mainline_summary"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**明日核心方向预判**: 人形机器人", rendered)
        self.assertIn("局部逆势活跃只按观察处理", rendered)
        self.assertIn("不把局部强势当成参与资格", rendered)
        self.assertNotIn("可执行爆发", rendered)
        self.assertNotIn("**明日核心方向预判**: 半导体", rendered)
        self.assertNotIn("认准'半导体'", rendered)

    def test_candidate_selection_summary_and_quadrant_use_adopted_mainline_label(self):
        result = build_candidate_selection_runtime(
            {
                "data": {
                    "sector_quadrant": {
                        "high_strong_analysis": {
                            "tier1_count": 1,
                            "tier2_count": 0,
                            "tier3_count": 0,
                            "tier4_count": 0,
                            "tier1_best": [{"name": "国产芯片替代", "quality_score": 88}],
                            "tier2_good": [],
                            "tier3_normal": [],
                        }
                    }
                },
                "target_date": "2026-05-22",
                "exit_analysis": {"sector_name": "元件"},
                "candidates": [{"name": "风华高科", "code": "000636"}],
                "watchlist": [{"name": "风华高科", "code": "000636", "sector": "元器件", "score": 65}],
                "abnormal_watch_map": {},
                "dragon_stocks": [{"name": "风华高科", "code": "000636", "sector": "元器件"}],
                "zt_pool_by_sector": {"元器件": [{"name": "风华高科"}]},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["元件"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda *args, **kwargs: [],
                "mainline_turnover_summary": {
                    "current_mainline": "国产芯片替代",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "国产芯片替代",
                        "confirmation_evidence": "国产芯片替代资金净流入靠前，涨停和高标更集中",
                    },
                },
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [{"name": "风华高科", "code": "000636", "sector": "元器件", "tomorrow_strength": 40}],
                    "core_stocks": [{"name": "风华高科", "code": "000636", "sector": "元器件", "tomorrow_strength": 40}],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "元件",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["mainline_summary", "quadrant_analysis"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**明日核心方向预判**: 国产芯片替代", rendered)
        self.assertIn("**主线位置判断**: 当前主线'国产芯片替代'位于", rendered)
        self.assertNotIn("**明日核心方向预判**: 元件", rendered)
        self.assertNotIn("当前主线'元件'", rendered)

    def test_candidate_selection_summary_does_not_sum_composite_stock_strength_as_sector_strength(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-05-24",
                "exit_analysis": {"sector_name": "机器人"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["机器人"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [
                        {"name": "机器人一号", "code": "000001", "sector": "机器人", "tomorrow_strength": 92},
                        {"name": "机器人二号", "code": "000002", "sector": "机器人", "tomorrow_strength": 88},
                    ],
                    "secondary_stocks": [
                        {"name": "机器人三号", "code": "000003", "sector": "机器人", "tomorrow_strength": 76},
                    ],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "机器人",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["mainline_summary"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**明日核心方向预判**: 机器人（主线内3只，最强样本92分）", rendered)
        self.assertIn("综合分只用于个股排序，不累加成板块分", rendered)
        self.assertNotIn("主线内强度256分", rendered)
        self.assertNotIn("板块强度256分", rendered)

    def test_conviction_list_renders_quant_anchor_action_from_participation_script(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "锚点样本",
                        "code": "300001",
                        "sector": "半导体",
                        "conviction_reason": "区间顶部观察",
                        "conviction_rule": "等价格确认后再参与",
                        "participation_script": {
                            "anchor_zone_role": "区间顶部",
                            "anchor_line_confluence": "533.33对子锚点接近前高与MA5",
                            "hidden_liquidity_read": "隐藏卖盘更强",
                            "anchor_action_plan": "冲不过先止盈，放量吃掉并回踩不破再恢复候选",
                        },
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("量化锚点动作", rendered)
        self.assertIn("533.33对子锚点接近前高与MA5", rendered)
        self.assertIn("冲不过先止盈", rendered)

    def test_conviction_list_does_not_upgrade_core_labels_to_full_attack_without_position_decision(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "核心样本",
                        "code": "000001",
                        "sector": "机器人",
                        "a_grade_candidate": True,
                        "pattern": "2连板",
                        "conviction_reason": "主线内核 / 连板 / 龙一",
                        "conviction_rule": "只在竞价表态和开盘承接同时成立后再参与",
                        "participation_window": "竞价表态 + 回封参与",
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("主线内核 / 连板 / 龙一", rendered)
        self.assertIn("| 竞价表态 + 回封参与 | 50% |", rendered)
        self.assertNotIn("| 竞价表态 + 回封参与 | 100% |", rendered)

    def test_conviction_list_zero_observation_rewrites_participation_rule(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "和远气体",
                        "code": "002971",
                        "sector": "化工原料",
                        "pattern": "T字板",
                        "conviction_reason": "板块锚定龙 / 3连板",
                        "conviction_rule": "先看竞价承接，回封或结构确认命中才参与",
                        "attack_state": "0%不参与",
                        "candidate_layer": "watch_sample",
                        "execution_eligibility": "observation_only",
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("只观察承接，不新增参与", rendered)
        self.assertNotIn("命中才参与", rendered)

    def test_conviction_list_renders_anchor_reversal_inside_reason(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "sector": "电力",
                        "conviction_reason": "低位补涨",
                        "conviction_rule": "只观察承接",
                        "candidate_role": "套利工具",
                        "sector_anchor": "大唐发电(601991)",
                        "relationship_to_anchor": "被大唐发电(601991)带动，只能反馈板块强度",
                        "repair_priority": "后排修复",
                        "anchor_reversal_decision": "降级观察",
                        "anchor_reversal_reason": "套利工具不能替代板块锚",
                        "ma_binding_strategy": "MA5入/MA7清/MA5T",
                        "leader_certainty_path": "板块锚优先，MA5入/MA7清/MA5T和承接路径明确",
                        "limit_up_evidence_role": "涨停只是证据，不能替代板块锚和承接路径",
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("板块锚反推：降级观察", rendered)
        self.assertIn("身份：套利工具", rendered)
        self.assertIn("大唐发电(601991)", rendered)
        self.assertIn("被大唐发电(601991)带动，只能反馈板块强度", rendered)
        self.assertIn("后排修复", rendered)
        self.assertIn("套利工具不能替代板块锚", rendered)
        self.assertIn("MA5入/MA7清/MA5T", rendered)
        self.assertIn("板块锚优先", rendered)
        self.assertIn("涨停只是证据", rendered)

    def test_conviction_list_renders_anchor_identity_before_limit_evidence(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "大有能源",
                        "code": "600403",
                        "sector": "煤炭",
                        "pattern": "涨停",
                        "leader_speed_tier": "观察样本",
                        "anchor_reversal_decision": "降级观察",
                        "sector_anchor": "兆易创新(603986)",
                        "candidate_role": "跟风样本",
                        "relationship_to_anchor": "非同主线锚",
                        "why_not_anchor": "无法替代板块锚",
                        "limit_up_evidence_role": "涨停只作观察证据",
                        "conviction_rule": "只观察承接",
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("**龙头资格反推结果**", rendered)
        self.assertIn("大有能源(600403)", rendered)
        self.assertLess(rendered.index("板块锚"), rendered.index("涨停只作观察证据"))
        self.assertIn("无法替代板块锚", rendered)
        self.assertNotIn("明日主买对象", rendered)

    def test_conviction_list_anchor_reversal_downgrade_overrides_stale_executable_layer(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "sector": "电力",
                        "candidate_layer": "executable_candidate",
                        "execution_eligibility": "auction_reseal",
                        "conviction_reason": "低位补涨",
                        "conviction_rule": "只观察承接",
                        "candidate_role": "套利工具",
                        "sector_anchor": "大唐发电(601991)",
                        "anchor_reversal_decision": "降级观察",
                        "anchor_reversal_reason": "套利工具不能替代板块锚",
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 1 | 京能电力(600578) | 电力 |", rendered)
        self.assertIn("板块锚反推：降级观察", rendered)
        self.assertIn("身份依据：低位补涨", rendered)
        self.assertNotIn("可执行候选", rendered)

    def test_conviction_list_compacts_duplicate_no_trade_placeholder_review_rows(self):
        placeholder = {
            "sector": "电力",
            "participation_window": "09:50-10:10",
            "participation_window_type": "no_trade",
            "attack_state": "50%",
            "conviction_reason": "只观察，不新增参与",
            "conviction_rule": "只观察，不新增参与",
            "auction_script": "竞价表态强且匹配金额放大",
            "first_minutes_script": "开盘前几分钟主动资金继续抬价",
            "board_script": "只做首次强封",
            "reseal_script": "开板释放抛压后快速回封",
            "missed_action": "错过后等低位承接",
            "invalid_condition": "保持0%不参与",
        }
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    dict(placeholder),
                    dict(placeholder),
                    {
                        **placeholder,
                        "name": "豫能控股",
                        "code": "001896",
                        "conviction_reason": "电力观察对象，保留承接证据",
                    },
                    {
                        **placeholder,
                        "name": "泛观察样本",
                        "code": "",
                    },
                ]
            }
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("**重点观察复核脚本**:", rendered)
        self.assertEqual(rendered.count("| no_trade | 0% |"), 1)
        self.assertNotIn("| no_trade | 0% |\n| no_trade | 0% |", rendered)
        self.assertNotIn("| 09:50-10:10 | 50% |", rendered)
        self.assertNotIn("竞价表态强且匹配金额放大", rendered)
        self.assertNotIn("只做首次强封", rendered)
        self.assertNotIn("快速回封", rendered)

    def test_conviction_list_no_trade_policy_forces_zero_position_when_triggered_by_action_text(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "participation_window": "09:50-10:10",
                        "attack_state": "50%",
                        "missed_action": "只观察，不新增参与",
                        "conviction_reason": "观察对象",
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("| no_trade | 0% |", rendered)
        self.assertNotIn("| 09:50-10:10 | 50% |", rendered)

    def test_conviction_list_nested_anchor_reversal_overrides_stale_executable_layer(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "sector": "电力",
                        "candidate_layer": "executable_candidate",
                        "execution_eligibility": "auction_reseal",
                        "conviction_reason": "低位补涨",
                        "conviction_rule": "只观察承接",
                        "anchor_reversal": {
                            "sector_anchor": "大唐发电(601991)",
                            "candidate_role": "套利工具",
                            "relationship_to_anchor": "被大唐发电(601991)带动，只能反馈板块强度",
                            "why_not_anchor": "不能证明比板块锚更值得参与",
                            "anchor_reversal_decision": "降级观察",
                            "anchor_reversal_reason": "套利工具不能替代板块锚",
                        },
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("板块锚反推：降级观察", rendered)
        self.assertIn("不做锚原因：不能证明比板块锚更值得参与", rendered)
        self.assertNotIn("可执行候选", rendered)

    def test_candidate_selection_renders_shape_repair_pool_separately(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-05-21",
                "exit_analysis": {"sector_name": "光通信"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["光通信"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [{"name": "光迅科技", "code": "002281", "sector": "光通信"}],
                    "shape_repair_pool": [
                        {
                            "name": "博杰股份",
                            "code": "002975",
                            "sector": "机器人",
                            "repair_status": "待修复",
                            "trend_aesthetic_review": {
                                "reasons": ["短线承接转弱", "历史好形态"],
                                "action": "历史趋势样本待修复，重新站回短中线承接后再评估",
                            },
                            "next_action": "保留跟踪，重新站回短中线承接后再评估；继续走坏再取关淘汰",
                        }
                    ],
                    "mainline_name": "光通信",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["conviction_list"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**形态待修复池**", rendered)
        self.assertIn("| 博杰股份 | 002975 | 机器人 | 待修复 | 短线承接转弱 / 历史好形态 | 历史趋势样本待修复，重新站回短中线承接后再评估 | 保留跟踪，重新站回短中线承接后再评估；继续走坏再取关淘汰 |", rendered)
        self.assertEqual(result["exports"]["shape_repair_pool"][0]["code"], "002975")

    def test_candidate_selection_renders_historical_extreme_review_destinations(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-05-21",
                "exit_analysis": {"sector_name": "光通信"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["光通信"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [{"name": "光迅科技", "code": "002281", "sector": "光通信"}],
                    "shape_repair_pool": [],
                    "historical_extreme_review": [
                        {
                            "mention_trade_date": "2026-05-20",
                            "name": "光迅科技",
                            "code": "002281",
                            "sector": "光通信",
                            "source_section": "极度看好名单",
                            "destination": "过程观察样本",
                            "review_status": "当前观察样本",
                            "review_basis": "进入过程观察样本池",
                            "next_action": "按最终仓位结论统一收口；不作为明日新增参与依据",
                        },
                        {
                            "mention_trade_date": "2026-05-19",
                            "name": "汇源通信",
                            "code": "000586",
                            "sector": "通信设备",
                            "source_section": "极度看好名单",
                            "destination": "龙回头观察池",
                            "review_status": "龙回头观察",
                            "review_basis": "龙回头样本 / A杀未修复",
                            "next_action": "单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰",
                        },
                    ],
                    "dragon_rebound_watch_pool": [
                        {
                            "name": "汇源通信",
                            "code": "000586",
                            "sector": "通信设备",
                            "repair_status": "龙回头观察",
                            "trend_aesthetic_review": {
                                "reasons": ["龙回头样本", "A杀未修复"],
                                "action": "重新站回短中线承接后再评估",
                            },
                            "next_action": "单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰",
                        }
                    ],
                    "mainline_name": "光通信",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["conviction_list"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**历史过程观察样本去向**", rendered)
        self.assertIn("**龙回头观察池**", rendered)
        self.assertIn("| 汇源通信 | 000586 | 通信设备 | 龙回头观察 | 龙回头样本 / A杀未修复 | 重新站回短中线承接后再评估 | 单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰 |", rendered)
        self.assertIn("| 2026-05-20 | 光迅科技 | 002281 | 光通信 | 极度看好名单 | 过程观察样本 | 当前观察样本 | 进入过程观察样本池 | 按最终仓位结论统一收口；不作为明日新增参与依据 |", rendered)
        self.assertNotIn("正式重点观察名单 | 当前合格", rendered)
        self.assertIn("| 2026-05-19 | 汇源通信 | 000586 | 通信设备 | 极度看好名单 | 龙回头观察池 | 龙回头观察 | 龙回头样本 / A杀未修复 | 单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰 |", rendered)
        self.assertEqual(result["exports"]["dragon_rebound_watch_pool"][0]["code"], "000586")
        self.assertEqual(result["exports"]["historical_extreme_review"][1]["code"], "000586")

    def test_extreme_conviction_list_renders_quantified_participation_script(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-05-15",
                "exit_analysis": {"sector_name": "电力"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["电力"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [
                        {
                            "name": "大唐发电",
                            "code": "601991",
                            "sector": "电力",
                            "sniper_role": "明日主买对象",
                            "leader_speed_tier": "极致加速龙头",
                            "buy_ma_line": "MA3",
                            "sell_ma_line": "MA5",
                            "acceptance_repair_required": "缩量回撤到MA3附近，站回VWAP",
                            "final_risk_review": {"status": "通过"},
                            "pattern": "T字板",
                            "conviction_reason": "趋势比价链锚定龙 / 分歧转一致",
                            "conviction_rule": "竞价表态强且开盘承接继续才参与",
                            "participation_window": "竞价表态",
                            "attack_state": "100%",
                            "auction_script": "09:20后封单稳定且匹配金额继续放大",
                            "first_minutes_script": "09:30-09:35不回落到昨收附近，主动买单继续抬价",
                            "board_script": "首次封板只看大单金额持续进入，弱封不追",
                            "reseal_script": "开板释放抛压后快速回封且板块同步走强",
                            "missed_action": "一字或T字过快封死则转向电力低位补涨，不补杂毛",
                            "invalid_condition": "竞价量价背离或开盘跌回昨日强承接区",
                        }
                    ],
                    "mainline_name": "电力",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["conviction_list"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 优先级 | 标的 | 所属板块 | 板块锚与身份 | 承接结果 | 速度证据 | 明日原则 |", rendered)
        self.assertIn("| 1 | 大唐发电(601991) | 电力 | 身份依据：趋势比价链锚定龙 / 分歧转一致 | 缩量回撤到MA3附近，站回VWAP | 极致加速龙头；T字板 | 竞价表态强且开盘承接继续才参与 |", rendered)
        self.assertIn("| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 最终复核 |", rendered)
        self.assertIn("| 明日主买对象 | 大唐发电(601991) | 极致加速龙头 | MA3 | MA5 | 缩量回撤到MA3附近，站回VWAP | 通过 |", rendered)
        self.assertNotIn("极看理由", rendered)
        self.assertIn("| 固定交易窗口 | 仓位三态 | 量化锚点动作 | 涨停惯性 | 盈亏比 | 检查步骤 | 加工依据 | 集合竞价 | 开盘前几分钟 | 均线回归观察 | 封板策略 | 回封观察 | 错过后动作 | MA20作废 | 跟踪周期 | 作废条件 |", rendered)
        self.assertIn("高惯性；高于普通上涨样本", rendered)
        self.assertIn("默认要求盈亏比不低于2:1", rendered)
        self.assertIn("交易逻辑确认 / 竞价表态 / 开盘前几分钟承接 / MA执行锚点 / 回封/打板", rendered)
        self.assertIn("价格位置 / 匹配金额 / 委托稳定 / 板块同步；主动资金继续抬价 / 承接连续；量能、情绪、板块、资金、辨识度和承接已经给出买入资格后，才看日K MA5/MA10与分时黄线优化买点；大单金额持续进入 / 快速回封 / 封单质量改善", rendered)
        self.assertIn("| 竞价表态 | 100% | - | 高惯性；高于普通上涨样本", rendered)
        self.assertIn("09:50-10:10均线回归试错", rendered)
        self.assertIn("MA只是执行锚点", rendered)
        self.assertIn("分时黄线只作为日内承接确认线", rendered)
        self.assertIn("有效跌破日K MA20", rendered)
        self.assertIn("25个交易日", rendered)
        for forbidden in (
            _m("门", "控"),
            _m("闸", "门"),
            _m("开", "闸"),
            _m("放", "行"),
            _m("执行", "权"),
            _m("执行", "权限"),
            _m("买入", "权限"),
            _m("开", "火"),
            _m("不", "开", "火"),
        ):
            self.assertNotIn(forbidden, rendered)

    def test_extreme_conviction_defaults_t_board_to_auction_reseal_instead_of_wait_only(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-05-15",
                "exit_analysis": {"sector_name": "电力"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["电力"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [
                        {
                            "name": "大唐发电",
                            "code": "601991",
                            "sector": "电力",
                            "pattern": "T字板",
                            "conviction_reason": "趋势比价链锚定龙 / 高低切反哺核心",
                            "conviction_rule": "观察竞价强弱",
                        }
                    ],
                    "mainline_name": "电力",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["conviction_list"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("竞价表态 + 回封参与", rendered)
        self.assertIn("09:20后看价格位置、匹配金额、委托稳定和板块同步", rendered)
        self.assertIn("09:30-09:35只看主动资金是否继续抬价", rendered)
        self.assertIn("过快封死就沿电力趋势比价链找低位承接", rendered)
        self.assertNotIn(_m("只等", "60分钟确认"), rendered)

    def test_candidate_selection_mainline_summary_renders_gem_observation_without_legacy_renderer(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-22",
                "exit_analysis": {"sector_name": "军工"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["军工"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [
                        {
                            "name": "军工一号",
                            "code": "000001",
                            "sector": "军工",
                            "tomorrow_strength": 91,
                        }
                    ],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [
                        {
                            "name": "创业弹性",
                            "code": "300001",
                            "sector": "军工",
                            "tier": "白银弹性",
                            "abnormal_summary": _m("均线", "粘合"),
                            "tomorrow_strength": 76,
                        }
                    ],
                    "filtered_out_gem_candidates": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "军工",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["mainline_summary"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**明日核心方向预判**: 军工", rendered)
        self.assertIn("主线侧翼弹性层", rendered)
        self.assertIn("| 1 | 创业弹性 | 300001 | 军工 | 白银弹性 | 波动收敛，等待量价温和放大后的右侧确认 | 76分 |", rendered)
        self.assertNotIn(_m("均线", "粘合"), rendered)

    def test_candidate_selection_runtime_can_render_only_enabled_nodes(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-22",
                "exit_analysis": {"sector_name": "军工"},
                "candidates": [{"name": "军工一号", "code": "000001"}],
                "watchlist": [{"name": "军工一号", "code": "000001", "sector": "军工", "score": 91}],
                "abnormal_watch_map": {"000001": {"follow_state": "跌不下去"}},
                "dragon_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工"}],
                "zt_pool_by_sector": {"军工": [{"name": "军工一号"}]},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["军工"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda gem_observation_stocks, filtered_out_gem_candidates=None, display_mvp_mode=None: ["gem-section"],
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "tomorrow_strength": 91}],
                    "core_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "pattern": "涨停", "abnormal_summary": "跌不下去", "tomorrow_strength": 91, "core_level": "🔥 连板核心", "tmr_forecast": "2进3"}],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [{"sector": "军工", "trend_count": 3, "core_count": 1, "anchor_name": "军工一号", "anchor_code": "000001", "density_score": 88, "anchor_reason": "主线龙头"}],
                    "extreme_conviction_list": [{"name": "军工一号", "code": "000001", "sector": "军工", "conviction_reason": "主线最强", "conviction_rule": _m("只等", "60分钟确认")}],
                    "mainline_name": "军工",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["overview", "core_candidates", "conclusion"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 2 - 明日核心标的", rendered)
        self.assertIn("**主线内可执行候选**", rendered)
        self.assertIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", rendered)
        self.assertNotIn("| 序号 | 股票 | 代码 | 板块 | 今日形态 | 异动跟踪 | 预判强度 | 核心级别 | 明日预判 |", rendered)
        self.assertIn("**结论**:", rendered)
        self.assertNotIn("**主线趋势密度复核**", rendered)
        self.assertNotIn("**极度看好名单**", rendered)

    def test_candidate_selection_marks_core_candidates_as_watch_only_when_gate_is_closed(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-24",
                "exit_analysis": {"sector_name": "半导体"},
                "final_gate": {"can_new_entry": False, "operation_state": "防守态"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [
                        {
                            "name": "富瀚微",
                            "code": "300613",
                            "sector": "半导体",
                            "core_level": "溢价候选",
                            "tmr_forecast": "10点看承接",
                        }
                    ],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["core_candidates"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 富瀚微 | 300613 | 半导体 | - | - | 09:50-10:10看承接 | 溢价候选 | 仅观察，条件未满足 |", rendered)
        self.assertNotIn("有条件执行", rendered)
        self.assertNotIn(_m("闸", "门"), rendered)

    def test_candidate_selection_marks_core_candidates_as_ten_oclock_watch_when_conditional_gate_exists(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-24",
                "exit_analysis": {"sector_name": "半导体"},
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True, "operation_state": "防守态"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [
                        {"name": "富瀚微", "code": "300613", "sector": "半导体", "core_level": "溢价候选", "tmr_forecast": "10点看承接"}
                    ],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["core_candidates"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 富瀚微 | 300613 | 半导体 | - | - | 09:50-10:10看承接 | 溢价候选 | 观察，等09:50-10:10窗口 |", rendered)
        self.assertNotIn("有条件执行", rendered)

    def test_candidate_selection_infers_volume_t_board_signature_from_price_shape(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-24",
                "exit_analysis": {"sector_name": "半导体"},
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [
                        {
                            "name": "富瀚微",
                            "code": "300613",
                            "sector": "半导体",
                            "open": 55.90,
                            "high": 56.08,
                            "low": 54.21,
                            "close": 56.08,
                            "change": 20.01,
                            "abnormal_summary": "显著放量6.0倍，涨停，强启动信号",
                            "core_level": "溢价候选",
                            "tmr_forecast": "明日可能高开溢价",
                        }
                    ],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["core_candidates"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 富瀚微 | 300613 | 半导体 | 放量T字板 | - | 明日可能高开溢价 | 溢价候选 | 观察，等09:50-10:10窗口 |", rendered)

    def test_candidate_selection_core_candidates_render_market_fit_fields_without_standalone_drawing_table(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-24",
                "exit_analysis": {"sector_name": "半导体"},
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [
                        {
                            "name": "富瀚微",
                            "code": "300613",
                            "sector": "半导体",
                            "signature_big_yangline": "放量涨停",
                            "five_day_burst_state": "未完全爆发",
                            "acceptance_state": "明日验证承接",
                            "capital_trace": "主线资金主动进攻",
                            "qualification_text": "观察，等10点确认",
                        }
                    ],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["core_candidates"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", rendered)
        self.assertIn("| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等09:50-10:10窗口 |", rendered)
        self.assertNotIn("主力画图", rendered)
        self.assertNotIn(_m("执行", "权"), rendered)

    def test_candidate_selection_stage_renders_crossline_watch_as_visible_v2_table(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-22",
                "exit_analysis": {"sector_name": "半导体"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda *args, **kwargs: [],
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [
                        {"name": "华电能源", "code": "600726", "sector": "电力", "abnormal_summary": "旧主线反抽", "tomorrow_strength": 60},
                    ],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["crossline_watch"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**跨线观察候选**", rendered)
        self.assertIn("| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |", rendered)
        self.assertIn("| 华电能源 | 600726 | 电力 |", rendered)
        self.assertNotIn("| 序号 | 股票 | 代码 | 板块 | 异动跟踪 | 预判强度 | 观察意义 | 明日原则 |", rendered)

    def test_candidate_selection_stage_uses_action_labels_for_ai_group_analysis(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
            ]
        )

        result = build_candidate_selection_stage(
            {
                "data": {
                    "sector_quadrant": {
                        "high_strong_analysis": {
                            "tier1_count": 1,
                            "tier2_count": 0,
                            "tier3_count": 0,
                            "tier4_count": 0,
                            "tier1_best": [{"name": "军工", "quality_score": 88}],
                            "tier2_good": [],
                            "tier3_normal": [],
                        }
                    }
                },
                "target_date": "2026-04-22",
                "exit_analysis": {"sector_name": "军工"},
                "position_level": "50%条件执行",
                "candidates": [{"name": "军工一号", "code": "000001"}],
                "watchlist": [{"name": "军工一号", "code": "000001", "sector": "军工", "score": 91}],
                "abnormal_watch_map": {"000001": {"follow_state": "跌不下去"}},
                "dragon_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工"}],
                "zt_pool_by_sector": {"军工": [{"name": "军工一号"}]},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["军工"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda gem_observation_stocks, filtered_out_gem_candidates=None, display_mvp_mode=None: [],
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "tomorrow_strength": 91}],
                    "core_stocks": [{"name": "军工一号", "code": "000001", "sector": "军工", "pattern": "涨停", "abnormal_summary": "跌不下去", "tomorrow_strength": 91, "core_level": "🔥 连板核心", "tmr_forecast": "2进3"}],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [{"sector": "军工", "trend_count": 3, "core_count": 1, "anchor_name": "军工一号", "anchor_code": "000001", "density_score": 88, "anchor_reason": "主线龙头"}],
                    "extreme_conviction_list": [],
                    "mainline_name": "军工",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {
                    "groups": [
                        {
                            "name": "军工主线",
                            "sectors": ["军工", "高端装备"],
                            "reason": "同属军工订单链",
                            "investment_logic": "资金继续聚焦主线强者",
                        }
                    ],
                    "insights": "",
                },
            },
            stage_lookup["candidate_selection"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**击球区结果**", rendered)
        self.assertIn("> **只看什么**: 当前主线在不在击球区，得分够不够。", rendered)
        self.assertIn("**板块归并结果**", rendered)
        self.assertIn("> **只看什么**: 哪些分散标签其实指向同一条主线。", rendered)
        self.assertIn("| 大方向 | 包含标签 | 主线依据 | 资金状态 |", rendered)
        self.assertNotIn("数据来源", rendered)
        self.assertNotIn("判断口径", rendered)
        self.assertNotIn("产业链逻辑", rendered)
        self.assertNotIn("资金博弈逻辑", rendered)
        self.assertNotIn("分析目的", rendered)

    def test_candidate_selection_quadrant_analysis_does_not_score_unconfirmed_mainline_as_current_mainline(self):
        result = build_candidate_selection_runtime(
            {
                "data": {
                    "sector_quadrant": {
                        "high_strong_analysis": {
                            "tier1_count": 0,
                            "tier2_count": 1,
                            "tier3_count": 0,
                            "tier4_count": 0,
                            "tier1_best": [],
                            "tier2_good": [{"name": "半导体", "quality_score": 70}],
                            "tier3_normal": [],
                        }
                    }
                },
                "target_date": "2026-05-14",
                "exit_analysis": {"sector_name": "半导体"},
                "candidates": [],
                "watchlist": [],
                "abnormal_watch_map": {},
                "dragon_stocks": [],
                "zt_pool_by_sector": {},
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "main_sectors": ["半导体"],
                "display_mvp_mode": False,
                "safe_float": float,
                "render_gem_breathing_step2_section": lambda *args, **kwargs: [],
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
                "build_step2_candidate_bundle": lambda *args, **kwargs: {
                    "evaluated_stocks": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "ignored_stocks": [],
                    "crossline_observation_stocks": [],
                    "gem_observation_stocks": [],
                    "sector_trend_snapshot": [],
                    "extreme_conviction_list": [],
                    "mainline_name": "半导体",
                    "module_logs": [],
                },
                "ai_analyze_sector_relationships": lambda sector_names, context: {"groups": [], "insights": ""},
            },
            {"label": "Step 2", "title": "明日核心标的"},
            enabled_node_keys=["quadrant_analysis"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**主线位置判断**: 当前无确认主攻线，击球区只作为候选板块质量参考", rendered)
        self.assertNotIn("当前主线'半导体'位于", rendered)


if __name__ == "__main__":
    unittest.main()
