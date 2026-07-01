import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.positioning_nodes import render_positioning_section


class PositioningNodeRuntimeTest(unittest.TestCase):
    def test_render_positioning_section_can_render_only_enabled_nodes(self):
        lines = render_positioning_section(
            {
                "enabled_node_keys": ["header", "environment_status", "state_basis"],
                "compact": False,
                "display_position_level": "0%不参与",
                "display_operation_state": "观察态",
                "display_position_reason": "中枢内震荡且市场偏弱，应清仓或极轻仓观望",
                "get_execution_framework_text": lambda: "日线定环境，60分钟定买点，30分钟定止损",
                "market_zhongshu": {
                    "success": True,
                    "zhongshu_list": [
                        {"start_date": "2026-04-14", "end_date": "2026-04-22", "zg": 11.00, "zd": 10.00}
                    ],
                    "current_zhongshu": {"start_date": "2026-04-14", "end_date": "2026-04-22"},
                    "latest_structure_segment": {},
                    "structure_segments": [],
                    "signal": {
                        "status": "➖ 中枢内震荡",
                        "signal_type": "中枢震荡",
                        "zd": 10.00,
                        "zg": 11.00,
                        "today_price": 10.50,
                        "dist_to_zg": -0.045,
                        "comparison_result": "仍在中枢内",
                    },
                },
                "ascii_diagram": "test-diagram",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 📈 明天仓位怎么放（基于日线结构中枢）", rendered)
        self.assertIn("### 🟡 明日市场环境：0%不参与 / 观察态", rendered)
        self.assertIn("**状态依据**：中枢内震荡且市场偏弱，应清仓或极轻仓观望", rendered)
        self.assertNotIn("**ASCII结构图**", rendered)
        self.assertNotIn("**识别出 1 个结构中枢**", rendered)

    def test_render_positioning_section_splits_daily_box_and_chanlun_confirmation(self):
        lines = render_positioning_section(
            {
                "enabled_node_keys": ["structure_range", "zhongshu_table"],
                "compact": False,
                "market_zhongshu": {
                    "success": True,
                    "daily_structure_current": {
                        "start_date": "2026-04-14",
                        "end_date": "2026-04-24",
                        "kline_count": 9,
                        "required_kline_count": 20,
                        "zd_candidate": 3992.41,
                        "zg_candidate": 4114.84,
                        "candidate_status": "daily_candidate_forming",
                    },
                    "chanlun_confirmation": {
                        "confirmation_status": "forming_daily_level_zhongshu",
                        "confirmed": False,
                        "explanation": "日K候选仍为9/20，下级别结构只支持形成中。",
                    },
                    "current_zhongshu": {},
                    "latest_structure_segment": {},
                    "structure_segments": [],
                    "zhongshu_list": [],
                    "signal": {
                        "status": "⏳ 日K候选形成中（9/20，结构确认：forming_daily_level_zhongshu）",
                        "signal_type": "按个股信号操作",
                        "zd": 3992.41,
                        "zg": 4114.84,
                        "today_price": 4086.34,
                        "dist_to_zg": -0.0069,
                        "comparison_result": "震荡",
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("日K结构箱体", rendered)
        self.assertIn("日K结构证据", rendered)
        self.assertNotIn("60分钟", rendered)
        self.assertIn("9/20", rendered)
        self.assertNotIn("最近确认中枢", rendered)

    def test_intraday_note_does_not_show_participation_when_final_action_is_zero(self):
        lines = render_positioning_section(
            {
                "enabled_node_keys": ["execution_framework", "intraday_note"],
                "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                "candidate_snapshot": {"front_page": {"unique_object": "暂无"}},
                "get_execution_framework_text": lambda: "日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("**怎么执行**：最终0%时不按固定交易窗口执行，只观察指数图形、主攻线承接，结果进入复盘和下一份日报判断。", rendered)
        self.assertIn("不新增参与", rendered)
        self.assertIn("只观察指数图形、主攻线承接，结果进入复盘和下一份日报判断", rendered)
        self.assertNotIn("强核心走竞价表态", rendered)
        self.assertNotIn("分层参与，买入后", rendered)

    def test_final_target_resolution_overrides_stale_zero_positioning_output(self):
        lines = render_positioning_section(
            {
                "enabled_node_keys": ["execution_framework", "intraday_note"],
                "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                "final_gate": {"final_action": "明日不新增参与，只观察风险是否钝化"},
                "final_target_resolution": {
                    "new_entry_target": {"name": "工业富联", "code": "601138"},
                    "existing_position_target": {"name": "华电辽能", "code": "600396"},
                    "display_target": {"name": "工业富联", "code": "601138"},
                    "capital_priority_decision": {
                        "capital_priority": "new_entry_after_old_exit",
                        "reason": "先处理旧仓，买工业富联(601138)；按昨晚预案检查执行资格；不满足回到0%不参与",
                    },
                },
                "get_execution_framework_text": lambda: "先处理旧仓，再按固定交易窗口确认工业富联",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("**怎么执行**：先处理旧仓，再按固定交易窗口确认工业富联", rendered)
        self.assertIn("明日只按09:30-09:35、09:50-10:10、14:30-14:55三段窗口处理", rendered)
        self.assertNotIn("最终0%时不按固定交易窗口执行", rendered)
        self.assertNotIn("明日不新增参与", rendered)


if __name__ == "__main__":
    unittest.main()
