import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.candidate_selection_stage import (
    build_candidate_selection_stage,
    build_candidate_selection_runtime,
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
                    "extreme_conviction_list": [{"name": "军工一号", "code": "000001", "sector": "军工", "conviction_reason": "主线最强", "conviction_rule": "只等60分钟确认"}],
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
        self.assertIn("> **只留什么**：主线最强的留核心，跨线对象只留观察。", rendered)
        self.assertIn("**主线内可执行候选**", rendered)
        self.assertIn("**极度看好名单**", rendered)
        self.assertNotIn("gem-section", rendered)
        self.assertEqual(result["exports"]["step2_bundle"]["mainline_name"], "军工")
        self.assertEqual(result["exports"]["core_stocks"][0]["code"], "000001")
        self.assertEqual(result["exports"]["mainline_in_quadrant"], None)
        self.assertTrue(any(log["module"] == "selection.candidate_bundle_runtime" for log in result["module_logs"]))

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
                            "abnormal_summary": "均线粘合",
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
        self.assertIn("| 1 | 创业弹性 | 300001 | 军工 | 白银弹性 | 均线粘合 | 76分 |", rendered)

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
                    "extreme_conviction_list": [{"name": "军工一号", "code": "000001", "sector": "军工", "conviction_reason": "主线最强", "conviction_rule": "只等60分钟确认"}],
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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | - | - | 10点看承接 | 溢价候选 | 仅观察，条件未满足 |", rendered)
        self.assertNotIn("有条件执行", rendered)
        self.assertNotIn("闸门", rendered)

    def test_candidate_selection_marks_core_candidates_as_ten_oclock_watch_when_conditional_gate_exists(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-24",
                "exit_analysis": {"sector_name": "半导体"},
                "final_gate": {"can_new_entry": False, "allow_conditional_30": True, "operation_state": "防守态"},
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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | - | - | 10点看承接 | 溢价候选 | 观察，等10点确认 |", rendered)
        self.assertNotIn("有条件执行", rendered)

    def test_candidate_selection_infers_volume_t_board_signature_from_price_shape(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-24",
                "exit_analysis": {"sector_name": "半导体"},
                "final_gate": {"can_new_entry": False, "allow_conditional_30": True},
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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | 放量T字板 | - | 明日可能高开溢价 | 溢价候选 | 观察，等10点确认 |", rendered)

    def test_candidate_selection_core_candidates_render_market_fit_fields_without_standalone_drawing_table(self):
        result = build_candidate_selection_runtime(
            {
                "data": {"sector_quadrant": {}},
                "target_date": "2026-04-24",
                "exit_analysis": {"sector_name": "半导体"},
                "final_gate": {"can_new_entry": False, "allow_conditional_30": True},
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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |", rendered)
        self.assertNotIn("主力画图", rendered)
        self.assertNotIn("执行权", rendered)

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
                "position_level": "三档（进攻档）",
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
        self.assertIn("**AI板块归并结果**", rendered)
        self.assertIn("> **只看什么**: 哪些分散标签其实指向同一条主线。", rendered)
        self.assertIn("| 大方向 | 包含标签 | 主线依据 | 资金状态 |", rendered)
        self.assertNotIn("数据来源", rendered)
        self.assertNotIn("判断口径", rendered)
        self.assertNotIn("产业链逻辑", rendered)
        self.assertNotIn("资金博弈逻辑", rendered)
        self.assertNotIn("分析目的", rendered)


if __name__ == "__main__":
    unittest.main()
