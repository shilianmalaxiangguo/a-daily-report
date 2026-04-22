import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_report_tail_summary import run


class UseReportTailSummaryTest(unittest.TestCase):
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
        self.assertIn("discipline:军工", rendered)
        self.assertIn("supplement:补充视角", rendered)
        self.assertIn("ai:军工->地产", rendered)
        self.assertEqual(payload["exports"]["mainline_text"], "军工")
        self.assertEqual(payload["exports"]["risk_text"], "地产")
        self.assertIn("主线异动里先看谁：探针(000003)", payload["exports"]["abnormal_probe_parts"])
        self.assertEqual(result["diagnostics"]["hook_name"], "report.tail_summary")
        self.assertTrue(payload["module_logs"])


if __name__ == "__main__":
    unittest.main()
