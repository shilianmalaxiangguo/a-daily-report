import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_report_tail_summary import run


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
                    "position_level": "一档（空仓档）",
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
        self.assertEqual(captured["context"]["position_level"], "一档（空仓档）")
        self.assertEqual(result["diagnostics"]["hook_name"], "report.tail_summary")

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
