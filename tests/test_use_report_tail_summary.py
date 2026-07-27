import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_report_tail_summary import run
from report.final_conclusion_renderer import build_legacy_final_conclusion_lines


class UseReportTailSummaryTest(unittest.TestCase):
    def assertNoEnglishTradingJargon(self, rendered):
        lowered = rendered.lower()
        for forbidden in ("act right", "setup", "probe", "follow through"):
            self.assertNotIn(forbidden, lowered)

    def test_tail_summary_hook_prefers_unified_context_tail_renderer(self):
        calls = {"context_tail": 0, "supplementary": 0, "market_insight": 0}

        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "CLEAR",
                    "step0_prediction_cn": "🟢 明朗",
                    "step0_action": "允许强势跟随",
                    "final_gate": {"can_new_entry": True},
                    "mainline_name": "军工",
                    "market_research_snapshot": {},
                    "watchlist": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "front_structure_layer_text": "环境打开",
                    "trade_gate_open": True,
                    "best_stock": None,
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "front_follow_action_text": "只做唯一动作",
                    "abnormal_probe_group": {},
                    "exit_analysis": {"sector_name": "军工"},
                    "main_sectors_info": [{"name": "军工"}],
                    "risk_sectors": [{"name": "地产"}],
                    "market_trend": "震荡上行",
                    "zt_count": 10,
                    "dt_count": 1,
                    "market_state_snapshot": {
                        "energy_state": "进攻",
                        "flow_direction": "主线",
                    },
                    "supplementary_perspective": "补充视角",
                },
                "helpers": {
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": lambda context: ["legacy-final"],
                    "render_context_tail_sections": lambda context: calls.__setitem__("context_tail", calls["context_tail"] + 1) or [
                        f"tail:{context.get('mainline_name')}->{context.get('market_insight', {}).get('risk_text')}"
                    ],
                    "render_supplementary_perspective_section": lambda text: calls.__setitem__("supplementary", calls["supplementary"] + 1) or [f"supplement:{text}"],
                    "render_ai_market_insight_section": lambda context: calls.__setitem__("market_insight", calls["market_insight"] + 1) or [
                        f"ai:{context.get('mainline_text')}->{context.get('risk_text')}"
                    ],
                },
            }
        )

        rendered = "\n".join(result["value"]["lines"])
        self.assertIn("legacy-final", rendered)
        self.assertIn("tail:军工->地产", rendered)
        self.assertEqual(calls["context_tail"], 1)
        self.assertEqual(calls["supplementary"], 0)
        self.assertEqual(calls["market_insight"], 0)

    def test_tail_summary_hook_composes_conclusion_and_insight_sections(self):
        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "CLEAR",
                    "step0_prediction_cn": "🟢 明朗",
                    "step0_action": "允许强势跟随",
                    "final_gate": {"can_new_entry": True},
                    "mainline_name": "军工",
                    "market_research_snapshot": {},
                    "watchlist": [{"name": "军工一号", "code": "000001"}],
                    "core_stocks": [{"name": "军工一号", "code": "000001"}],
                    "secondary_stocks": [],
                    "step2_bundle": {"crossline_observation_stocks": [{"name": "跨线一号"}]},
                    "abnormal_watch_pool": [{"name": "异动一号", "code": "000002"}],
                    "front_structure_layer_text": "环境打开",
                    "trade_gate_open": True,
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "front_follow_action_text": "只做唯一动作",
                    "abnormal_probe_group": {
                        "mainline_abnormal_probe": {"name": "探针", "code": "000003"},
                        "crossline_abnormal_probe": {"name": "跨线探针", "code": "000004"},
                        "validation_probe": {"name": "验证探针", "code": "000005"},
                        "fallback_watch_anchor": {"name": "兜底锚点", "code": "000006"},
                    },
                    "exit_analysis": {"sector_name": "军工"},
                    "main_sectors_info": [{"name": "军工"}],
                    "risk_sectors": [{"name": "地产"}],
                    "market_trend": "震荡上行",
                    "zt_count": 10,
                    "dt_count": 1,
                    "market_state_snapshot": {
                        "energy_state": "进攻",
                        "flow_direction": "主线",
                    },
                    "supplementary_perspective": "补充视角",
                },
                "helpers": {
                    "format_abnormal_probe_text": lambda probe, role_label="", mainline_name="", fallback_watch_anchor=None: (
                        f"{probe.get('name')}({probe.get('code')})" if probe else ""
                    ),
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": lambda context: [
                        "legacy-final",
                        f"abnormal={len(context.get('abnormal_probe_parts', []))}",
                    ],
                    "render_mainline_discipline_section": lambda mainline_name: [f"discipline:{mainline_name}"],
                    "render_supplementary_perspective_section": lambda text: [f"supplement:{text}"],
                    "render_ai_market_insight_section": lambda context: [
                        f"ai:{context.get('mainline_text')}->{context.get('risk_text')}"
                    ],
                },
            }
        )

        payload = result["value"]
        rendered = "\n".join(payload["lines"])

        self.assertIn("legacy-final", rendered)
        self.assertNotIn("discipline:军工", rendered)
        self.assertIn("supplement:补充视角", rendered)
        self.assertIn("ai:军工->地产", rendered)
        self.assertEqual(payload["exports"]["mainline_text"], "军工")
        self.assertEqual(payload["exports"]["risk_text"], "地产")
        self.assertIn("主线异动里先看谁：探针(000003)", payload["exports"]["abnormal_probe_parts"])
        self.assertEqual(result["diagnostics"]["hook_name"], "report.tail_summary")
        self.assertTrue(payload["module_logs"])

    def test_tail_summary_hook_passes_tag_pool_to_market_insight_renderer(self):
        captured = {}
        tag_snapshot = {
            "groups": [
                {
                    "采用名称": "国产芯片替代",
                    "关系判断": "父子",
                    "表层行业名": ["元件", "元器件"],
                }
            ]
        }

        def _capture_context(context):
            captured["context"] = context
            return []

        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "final_gate": {},
                    "mainline_name": "",
                    "market_research_snapshot": {
                        "realtime_tag_evidence_snapshot": tag_snapshot,
                    },
                    "watchlist": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "abnormal_probe_group": {},
                    "exit_analysis": {"sector_name": "元件"},
                    "main_sectors_info": [{"name": "元件"}],
                    "risk_sectors": [],
                    "market_trend": "小幅上涨",
                    "market_state_snapshot": {
                        "energy_state": "收缩防守",
                        "flow_direction": "风险释放优先；趋势密度最强的是元器件",
                    },
                    "mainline_turnover_summary": {
                        "current_mainline": "国产芯片替代",
                        "mainline_attack_evidence_summary": {
                            "attack_state": "confirmed_attack",
                            "primary_line": "国产芯片替代",
                        },
                    },
                },
                "helpers": {
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "render_context_tail_sections": _capture_context,
                },
            }
        )

        self.assertEqual(result["value"]["exports"]["mainline_text"], "元件")
        self.assertEqual(captured["context"]["market_insight"]["realtime_tag_evidence_snapshot"], tag_snapshot)

    def test_tail_summary_hook_passes_tracking_memory_status_into_final_conclusion(self):
        captured = {}

        def _capture_context(context):
            captured["context"] = context
            return []

        result = run(
            {
                "inputs": {
                    "display_mvp_mode": True,
                    "step0_prediction": "CLEAR",
                    "step0_prediction_cn": "🟢 明朗",
                    "step0_action": "允许强势跟随",
                    "final_gate": {"can_new_entry": True},
                    "mainline_name": "军工",
                    "market_research_snapshot": {},
                    "watchlist": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "front_structure_layer_text": "环境打开",
                    "trade_gate_open": True,
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "front_follow_action_text": "只做唯一动作",
                    "abnormal_probe_group": {},
                    "tracking_memory_status": {
                        "today_validated_items": [{"name": "老龙头", "code": "000002", "follow_state": "今日再次入池"}]
                    },
                    "position_level": "0%不参与",
                    "exit_analysis": {"sector_name": "军工"},
                    "main_sectors_info": [{"name": "军工"}],
                    "risk_sectors": [],
                    "market_state_snapshot": {},
                },
                "helpers": {
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": _capture_context,
                },
            }
        )

        self.assertEqual(captured["context"]["tracking_memory_status"]["today_validated_items"][0]["code"], "000002")
        self.assertEqual(captured["context"]["position_level"], "0%不参与")
        self.assertEqual(result["diagnostics"]["hook_name"], "report.tail_summary")

    def test_tail_summary_hook_preserves_confirmed_old_position_in_final_conclusion(self):
        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "DIFFICULT",
                    "step0_prediction_cn": "只处理旧仓",
                    "step0_action": "不新增参与",
                    "final_gate": {"can_new_entry": False, "should_reduce": True},
                    "mainline_name": "半导体",
                    "market_research_snapshot": {},
                    "personal_position_context": {
                        "existing_position_summary": {
                            "has_position": True,
                            "summary": "持有长电科技(600584)，100%仓位",
                        }
                    },
                    "watchlist": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "abnormal_probe_group": {},
                    "exit_analysis": {"sector_name": "半导体"},
                    "main_sectors_info": [{"name": "半导体"}],
                    "risk_sectors": [],
                    "market_state_snapshot": {},
                },
                "helpers": {
                    "build_legacy_final_conclusion_lines": build_legacy_final_conclusion_lines,
                },
            }
        )

        rendered = "\n".join(result["value"]["lines"])
        self.assertIn("旧仓处理：持有长电科技(600584)", rendered)
        self.assertIn("| 操作风格 | 旧仓处理 |", rendered)
        self.assertNotIn("| 操作风格 | 空仓 |", rendered)

    def test_tail_summary_hook_falls_back_to_direct_summary_when_nested_summary_is_empty(self):
        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "DIFFICULT",
                    "step0_prediction_cn": "只处理旧仓",
                    "step0_action": "不新增参与",
                    "final_gate": {"can_new_entry": False, "should_reduce": True},
                    "mainline_name": "半导体",
                    "market_research_snapshot": {},
                    "personal_position_context": {"existing_position_summary": {}},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有长电科技(600584)，100%仓位",
                    },
                    "watchlist": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "abnormal_probe_group": {},
                    "exit_analysis": {"sector_name": "半导体"},
                    "main_sectors_info": [{"name": "半导体"}],
                    "risk_sectors": [],
                    "market_state_snapshot": {},
                },
                "helpers": {
                    "build_legacy_final_conclusion_lines": build_legacy_final_conclusion_lines,
                },
            }
        )

        rendered = "\n".join(result["value"]["lines"])
        self.assertIn("旧仓处理：持有长电科技(600584)", rendered)
        self.assertIn("| 操作风格 | 旧仓处理 |", rendered)
        self.assertNotIn("| 操作风格 | 空仓 |", rendered)

    def test_tail_summary_hook_passes_core_stocks_into_final_conclusion(self):
        captured = {}

        def _capture_context(context):
            captured["context"] = context
            return []

        run(
            {
                "inputs": {
                    "display_mvp_mode": True,
                    "step0_prediction": "CLEAR",
                    "step0_prediction_cn": "🟢 明朗",
                    "step0_action": "允许强势跟随",
                    "final_gate": {"can_new_entry": True},
                    "mainline_name": "半导体",
                    "market_research_snapshot": {},
                    "watchlist": [{"name": "中嘉博创", "code": "000889"}],
                    "core_stocks": [{"name": "富瀚微", "code": "300613"}],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "front_structure_layer_text": "只看主线核心",
                    "trade_gate_open": True,
                    "best_stock": None,
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "front_follow_action_text": "只观察富瀚微",
                    "abnormal_probe_group": {},
                    "tracking_memory_status": {
                        "today_validated_items": [{"name": "中嘉博创", "code": "000889", "follow_state": "新异动待观察"}]
                    },
                    "exit_analysis": {"sector_name": "半导体"},
                    "main_sectors_info": [{"name": "半导体"}],
                    "risk_sectors": [],
                    "market_state_snapshot": {},
                },
                "helpers": {
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": _capture_context,
                },
            }
        )

        self.assertEqual(captured["context"]["core_stocks"][0]["code"], "300613")

    def test_tail_summary_hook_passes_selected_target_into_final_conclusion(self):
        captured = {}

        def _capture_context(context):
            captured["context"] = context
            return []

        run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "NEUTRAL",
                    "step0_prediction_cn": "🟡 中性",
                    "step0_action": "先观察后确认",
                    "final_gate": {
                        "can_new_entry": False,
                        "allow_attack_50_ready": True,
                        "final_action": "明日目标标的保留50%条件执行：只看000586 汇源通信",
                    },
                    "mainline_name": "半导体",
                    "market_research_snapshot": {},
                    "watchlist": [{"name": "汇源通信", "code": "000586"}],
                    "core_stocks": [{"name": "景兴纸业", "code": "002067"}],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "front_structure_layer_text": "只看唯一目标",
                    "trade_gate_open": False,
                    "best_stock": None,
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "selected_position_candidate": {"name": "汇源通信", "code": "000586", "sector": "通信设备"},
                    "position_decision": {"target_position_pct": 50, "participation_mode": "attack_50_preview"},
                    "front_follow_action_text": "只看汇源通信",
                    "abnormal_probe_group": {},
                    "exit_analysis": {"sector_name": "半导体"},
                    "main_sectors_info": [{"name": "半导体"}],
                    "risk_sectors": [],
                    "market_state_snapshot": {},
                },
                "helpers": {
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": _capture_context,
                },
            }
        )

        self.assertEqual(captured["context"]["selected_position_candidate"]["code"], "000586")
        self.assertEqual(captured["context"]["position_decision"]["target_position_pct"], 50)

    def test_tail_summary_hook_passes_style_switch_into_final_conclusion(self):
        captured = {}

        def _capture_context(context):
            captured["context"] = context
            return []

        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "CLEAR",
                    "step0_prediction_cn": "🟢 明朗",
                    "step0_action": "允许强势跟随",
                    "final_gate": {"can_new_entry": True},
                    "mainline_name": "军工",
                    "market_research_snapshot": {"style_switch": {"style_label": "趋势分歧优先"}},
                    "watchlist": [],
                    "core_stocks": [{"name": "军工一号", "code": "000001"}],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "front_structure_layer_text": "趋势分歧更适合等回踩确认",
                    "trade_gate_open": True,
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "front_follow_action_text": "只做唯一动作",
                    "abnormal_probe_group": {},
                    "exit_analysis": {"sector_name": "军工"},
                    "main_sectors_info": [{"name": "军工"}],
                    "risk_sectors": [],
                    "market_state_snapshot": {},
                },
                "helpers": {
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": _capture_context,
                },
            }
        )

        self.assertEqual(captured["context"]["style_switch"]["style_label"], "趋势分歧优先")
        self.assertEqual(result["diagnostics"]["hook_name"], "report.tail_summary")

    def test_tail_summary_hook_passes_mainline_turnover_atoms_into_final_conclusion(self):
        captured = {}

        def _capture_context(context):
            captured["context"] = context
            return []

        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "CLEAR",
                    "step0_prediction_cn": "🟢 明朗",
                    "step0_action": "允许强势跟随",
                    "final_gate": {"can_new_entry": True},
                    "mainline_name": "通信",
                    "market_research_snapshot": {
                        "mainline_turnover_summary": {
                            "conclusion": "主线未切换，通信仍是中心",
                            "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%",
                            "action_text": "继续围绕通信做减法",
                        }
                    },
                    "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "通信"},
                    "recent_mainline_history": [
                        {"date": "2026-04-22", "primary_mainline": "通信"},
                        {"date": "2026-04-23", "primary_mainline": "通信"},
                    ],
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "通信",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-22", "sector_name": "通信", "turnover_share_pct": 12.4},
                        {"date": "2026-04-23", "sector_name": "通信", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "conclusion": "主线未切换，通信仍是中心",
                        "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%",
                        "action_text": "继续围绕通信做减法",
                    },
                    "watchlist": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "front_structure_layer_text": "环境打开",
                    "trade_gate_open": True,
                    "best_stock": None,
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "front_follow_action_text": "只做唯一动作",
                    "abnormal_probe_group": {},
                    "exit_analysis": {"sector_name": "通信"},
                    "main_sectors_info": [{"name": "通信"}],
                    "risk_sectors": [],
                    "market_state_snapshot": {},
                },
                "helpers": {
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": _capture_context,
                },
            }
        )

        self.assertEqual(captured["context"]["mainline_turnover_summary"]["conclusion"], "主线未切换，通信仍是中心")
        self.assertEqual(captured["context"]["current_mainline_history_record"]["primary_mainline"], "通信")
        self.assertEqual(captured["context"]["current_sector_turnover_snapshot"]["turnover_share_pct"], 18.1)
        self.assertEqual(result["diagnostics"]["hook_name"], "report.tail_summary")

    def test_tail_summary_hook_replaces_english_trading_jargon_in_final_text(self):
        result = run(
            {
                "inputs": {
                    "display_mvp_mode": False,
                    "step0_prediction": "CLEAR",
                    "step0_prediction_cn": "🟢 明朗",
                    "step0_action": "允许 follow through",
                    "final_gate": {"can_new_entry": True},
                    "mainline_name": "军工",
                    "market_research_snapshot": {},
                    "watchlist": [],
                    "core_stocks": [],
                    "secondary_stocks": [],
                    "step2_bundle": {},
                    "abnormal_watch_pool": [],
                    "front_structure_layer_text": "setup 完整后再看 act right",
                    "trade_gate_open": True,
                    "best_stock": None,
                    "watch_anchor": None,
                    "watch_anchor_type": "",
                    "front_follow_action_text": "probe 后 follow through",
                    "abnormal_probe_group": {
                        "mainline_abnormal_probe": {"name": "probe 一号", "code": "000003"},
                    },
                    "exit_analysis": {"sector_name": "军工"},
                    "main_sectors_info": [{"name": "军工"}],
                    "risk_sectors": [],
                    "market_trend": "act right 后震荡上行",
                    "market_state_snapshot": {"energy_state": "setup", "flow_direction": "follow through"},
                },
                "helpers": {
                    "format_abnormal_probe_text": lambda probe, **kwargs: (
                        f"{probe.get('name')}({probe.get('code')}) setup" if probe else ""
                    ),
                    "build_front_mainline_label": lambda market_research_snapshot, fallback_mainline="": fallback_mainline,
                    "build_legacy_final_conclusion_lines": lambda context: [
                        context["front_structure_layer_text"],
                        context["front_follow_action_text"],
                        " / ".join(context.get("abnormal_probe_parts", [])),
                    ],
                    "render_context_tail_sections": lambda context: [
                        context["market_insight"]["market_trend"],
                        context["market_insight"]["energy_state"],
                        context["market_insight"]["flow_direction"],
                    ],
                },
            }
        )

        rendered = "\n".join(result["value"]["lines"])
        self.assertNoEnglishTradingJargon(rendered)
        self.assertIn("走势符合强势标准", rendered)
        self.assertIn("形态条件", rendered)
        self.assertIn("优先观察对象", rendered)
        self.assertIn("延续承接", rendered)


if __name__ == "__main__":
    unittest.main()
