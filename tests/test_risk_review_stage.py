import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from domains.execution_chain.risk_review_stage import (
    build_risk_review_runtime,
    build_risk_review_stage,
)
from domains.execution_chain.stage_runtime import build_execution_stage_lookup


class RiskReviewStageTest(unittest.TestCase):
    def test_risk_review_stage_uses_dynamic_labels_and_exports_step3_bundle(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
                {"stage_key": "risk_review", "title": "明日风险预判"},
                {"stage_key": "entry_plan", "title": "明日买点预计算"},
            ]
        )

        result = build_risk_review_stage(
            {
                "data": {},
                "target_date": "2026-04-22",
                "mainline_name": "军工",
                "core_stocks": [{"name": "军工一号", "code": "000001"}],
                "secondary_stocks": [{"name": "军工二号", "code": "000002"}],
                "step2_bundle": {"gem_observation_stocks": [{"name": "弹性一号", "code": "300001"}]},
                "market_research_bundle": {
                    "filtered_out_gem_breathing_candidates": [{"name": "弹性二号", "code": "300002"}],
                },
                "zt_pool_by_sector": {"军工": []},
                "dt_pool_by_sector": {"军工": []},
                "build_step3_risk_bundle": lambda *args, **kwargs: {
                    "stock_rows": [
                        {
                            "name": "军工一号",
                            "code": "000001",
                            "pattern": "涨停",
                            "abnormal_light": "🟢 绿灯",
                            "tomorrow_risk": "承接正常",
                            "risk_level": "低",
                            "dest": "focus",
                        }
                    ],
                    "delete_group": [],
                    "keep_group": [{"name": "军工二号", "code": "000002", "reason": "等竞价", "tomorrow_risk": "观察竞价"}],
                    "focus_group": [{"name": "军工一号", "code": "000001", "reason": "风险可控", "tomorrow_risk": "低风险"}],
                    "abnormal_green_count": 1,
                    "abnormal_red_count": 0,
                    "risk_sectors_from_dt": [],
                    "mainline_a_kill": False,
                    "mainline_dt_stocks": [],
                    "structural_a_kill": False,
                    "structural_reason": "",
                    "a_kill_blacklist_updates": [],
                    "module_logs": [
                        {
                            "module": "risk.risk_bundle_runtime",
                            "step": "risk_grouping",
                            "status": "success",
                            "message": "已完成风险分层",
                            "details": {},
                        }
                    ],
                },
                "render_gem_breathing_pool_section": lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy gem pool renderer should not be called")),
            },
            stage_lookup["risk_review"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 3 - 明日风险预判", rendered)
        self.assertIn("> **先看结论**：先剔掉明天容易直接掉队的对象，再保留能继续进入执行层的候选。", rendered)
        self.assertIn("> **只排什么雷**：个股转弱、批量跌停和A杀风险。", rendered)
        self.assertIn("> **只看什么**：主线有没有批量跌停和结构破坏。", rendered)
        self.assertIn("**逐只预判明日风险**", rendered)
        self.assertIn("**结论**:", rendered)
        self.assertIn("进入Step 4", rendered)
        self.assertNotIn("gem-pool-section", rendered)
        self.assertNotIn("为什么要看这块", rendered)
        self.assertEqual(result["exports"]["focus_group"][0]["code"], "000001")
        self.assertEqual(result["exports"]["step3_bundle"]["abnormal_green_count"], 1)
        self.assertTrue(any(log["module"] == "risk.risk_bundle_runtime" for log in result["module_logs"]))

    def test_risk_review_gem_pool_renders_without_legacy_renderer(self):
        result = build_risk_review_runtime(
            {
                "data": {},
                "target_date": "2026-04-22",
                "mainline_name": "军工",
                "core_stocks": [],
                "secondary_stocks": [],
                "step2_bundle": {
                    "gem_observation_stocks": [
                        {
                            "name": "弹性一号",
                            "code": "300001",
                            "tier": "白银弹性",
                            "note": _m("均线", "粘合"),
                            "watch_anchor_note": "只看右侧确认",
                        }
                    ]
                },
                "market_research_bundle": {
                    "filtered_out_gem_breathing_candidates": [
                        {
                            "name": "过滤样本",
                            "code": "300002",
                            "sector": "机器人",
                            "filtered_reason": "非主线",
                        }
                    ],
                },
                "zt_pool_by_sector": {},
                "dt_pool_by_sector": {},
                "build_step3_risk_bundle": lambda *args, **kwargs: {
                    "stock_rows": [],
                    "delete_group": [],
                    "keep_group": [],
                    "focus_group": [],
                    "abnormal_green_count": 0,
                    "abnormal_red_count": 0,
                    "risk_sectors_from_dt": [],
                    "mainline_a_kill": False,
                    "mainline_dt_stocks": [],
                    "structural_a_kill": False,
                    "structural_reason": "",
                    "a_kill_blacklist_updates": [],
                    "module_logs": [],
                },
            },
            {"label": "Step 3", "title": "明日风险预判"},
            enabled_node_keys=["gem_pool"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("创业板20cm预启动观察池", rendered)
        self.assertIn("弹性一号(300001)", rendered)
        self.assertIn("过滤样本(300002)/机器人：非主线", rendered)
        self.assertIn("波动收敛，等待量价温和放大后的右侧确认", rendered)
        self.assertNotIn(_m("均线", "粘合"), rendered)

    def test_risk_review_sector_a_kill_does_not_call_unconfirmed_candidate_current_mainline(self):
        result = build_risk_review_runtime(
            {
                "data": {},
                "target_date": "2026-05-14",
                "mainline_name": "半导体",
                "core_stocks": [],
                "secondary_stocks": [],
                "step2_bundle": {"gem_observation_stocks": []},
                "market_research_bundle": {"filtered_out_gem_breathing_candidates": []},
                "zt_pool_by_sector": {},
                "dt_pool_by_sector": {},
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
                "build_step3_risk_bundle": lambda *args, **kwargs: {
                    "stock_rows": [],
                    "delete_group": [],
                    "keep_group": [],
                    "focus_group": [],
                    "abnormal_green_count": 0,
                    "abnormal_red_count": 0,
                    "risk_sectors_from_dt": [],
                    "mainline_a_kill": False,
                    "mainline_dt_stocks": [],
                    "structural_a_kill": False,
                    "structural_reason": "",
                    "a_kill_blacklist_updates": [],
                    "module_logs": [],
                },
            },
            {"label": "Step 3", "title": "明日风险预判"},
            enabled_node_keys=["sector_a_kill"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("- ✅ **主线状态**: 当前无确认主攻线，只检查候选方向是否出现批量跌停。", rendered)
        self.assertNotIn("当前主线: '半导体'", rendered)
        self.assertNotIn("当前主线'半导体'", rendered)

    def test_risk_review_sector_a_kill_uses_adopted_tag_label_for_current_mainline(self):
        result = build_risk_review_runtime(
            {
                "data": {
                    "realtime_tag_evidence_snapshot": {
                        "groups": [
                            {
                                "采用名称": "国产芯片替代",
                                "关系判断": "父子",
                                "表层行业名": ["元件", "元器件"],
                            }
                        ]
                    }
                },
                "target_date": "2026-05-22",
                "mainline_name": "元件",
                "core_stocks": [],
                "secondary_stocks": [],
                "step2_bundle": {"gem_observation_stocks": []},
                "market_research_bundle": {"filtered_out_gem_breathing_candidates": []},
                "zt_pool_by_sector": {},
                "dt_pool_by_sector": {},
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "国产芯片替代",
                        "confirmation_evidence": "国产芯片替代资金净流入靠前，涨停更集中",
                        "sector_evidence_rows": [
                            {
                                "sector_name": "国产芯片替代",
                                "surface_sector_names": ["元件", "元器件"],
                            }
                        ],
                    }
                },
                "build_step3_risk_bundle": lambda *args, **kwargs: {
                    "stock_rows": [],
                    "delete_group": [],
                    "keep_group": [],
                    "focus_group": [],
                    "abnormal_green_count": 0,
                    "abnormal_red_count": 0,
                    "risk_sectors_from_dt": [],
                    "mainline_a_kill": False,
                    "mainline_dt_stocks": [],
                    "structural_a_kill": False,
                    "structural_reason": "",
                    "a_kill_blacklist_updates": [],
                    "module_logs": [],
                },
            },
            {"label": "Step 3", "title": "明日风险预判"},
            enabled_node_keys=["sector_a_kill"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("当前主线**: '国产芯片替代'无批量跌停", rendered)
        self.assertNotIn("当前主线**: '元件'", rendered)

    def test_risk_review_runtime_can_render_only_enabled_nodes(self):
        result = build_risk_review_runtime(
            {
                "data": {},
                "target_date": "2026-04-22",
                "mainline_name": "军工",
                "core_stocks": [{"name": "军工一号", "code": "000001"}],
                "secondary_stocks": [{"name": "军工二号", "code": "000002"}],
                "step2_bundle": {"gem_observation_stocks": [{"name": "弹性一号", "code": "300001"}]},
                "market_research_bundle": {
                    "filtered_out_gem_breathing_candidates": [{"name": "弹性二号", "code": "300002"}],
                },
                "zt_pool_by_sector": {"军工": []},
                "dt_pool_by_sector": {"军工": []},
                "build_step3_risk_bundle": lambda *args, **kwargs: {
                    "stock_rows": [
                        {
                            "name": "军工一号",
                            "code": "000001",
                            "pattern": "涨停",
                            "abnormal_light": "🟢 绿灯",
                            "tomorrow_risk": "承接正常",
                            "risk_level": "低",
                            "dest": "focus",
                        }
                    ],
                    "delete_group": [],
                    "keep_group": [{"name": "军工二号", "code": "000002", "reason": "等竞价", "tomorrow_risk": "观察竞价"}],
                    "focus_group": [{"name": "军工一号", "code": "000001", "reason": "风险可控", "tomorrow_risk": "低风险"}],
                    "abnormal_green_count": 1,
                    "abnormal_red_count": 0,
                    "risk_sectors_from_dt": [],
                    "mainline_a_kill": False,
                    "mainline_dt_stocks": [],
                    "structural_a_kill": False,
                    "structural_reason": "",
                    "a_kill_blacklist_updates": [],
                    "module_logs": [],
                },
                "render_gem_breathing_pool_section": lambda gem_observation_stocks=None, filtered_out_gem_candidates=None: ["gem-pool-section"],
            },
            {"label": "Step 3", "title": "明日风险预判"},
            enabled_node_keys=["overview", "stock_risk", "conclusion"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 3 - 明日风险预判", rendered)
        self.assertIn("**逐只预判明日风险**", rendered)
        self.assertIn("**结论**:", rendered)
        self.assertNotIn("**板块级A杀预判**", rendered)
        self.assertNotIn("**明日风险分组**", rendered)


if __name__ == "__main__":
    unittest.main()
