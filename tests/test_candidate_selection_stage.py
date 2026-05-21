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
        self.assertIn("> **只留什么**：主线最强的留核心，跨线对象只留观察。", rendered)
        self.assertIn("**主线内可执行候选**", rendered)
        self.assertIn("**重点观察名单**", rendered)
        self.assertIn("执行分层", rendered)
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
        self.assertIn("| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 执行分层 | 观察理由 | 明日原则 |", rendered)
        self.assertIn("| 1 | 大唐发电 | 601991 | 电力 | 趋势比价链锚点 / 高位锚 | 可执行候选 | 趋势比价链锚定龙 / 分歧转一致 | 竞价表态强且开盘承接继续才参与 |", rendered)
        self.assertIn("| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 最终复核 |", rendered)
        self.assertIn("| 明日主买对象 | 大唐发电(601991) | 极致加速龙头 | MA3 | MA5 | 缩量回撤到MA3附近，站回VWAP | 通过 |", rendered)
        self.assertNotIn("极看理由", rendered)
        self.assertIn("| 参与窗口 | 仓位三态 | 量化锚点动作 | 涨停惯性 | 盈亏比 | 检查步骤 | 加工依据 | 集合竞价 | 开盘前几分钟 | 均线回归试错 | 打板策略 | 回封参与 | 错过后动作 | MA20作废 | 跟踪周期 | 作废条件 |", rendered)
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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | - | - | 10点看承接 | 溢价候选 | 仅观察，条件未满足 |", rendered)
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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | - | - | 10点看承接 | 溢价候选 | 观察，等10点确认 |", rendered)
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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | 放量T字板 | - | 明日可能高开溢价 | 溢价候选 | 观察，等10点确认 |", rendered)

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
        self.assertIn("| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |", rendered)
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
