import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.action_plan_renderer import render_action_plan_section


class ActionPlanRendererTest(unittest.TestCase):
    def test_render_action_plan_section_with_watch_only_anchor(self):
        lines = render_action_plan_section(
            {
                "action_rows": [
                    {
                        "action": "👀 明天先盯哪只",
                        "name": "军工观察",
                        "code": "000002",
                        "trigger": "先看60分钟确认，再看是否走成明天唯一能买的那只",
                        "risk_window": "12.30-12.80 / 3~5日",
                    }
                ],
                "position_section_lines": [
                    "- **市场环境档位**: 二档（防守档）",
                    "- **明日裁决**: 🟡 中性",
                    "- **怎么执行**: 日线定环境，60分钟定买点，30分钟定止损",
                    "- **现在到底是什么状态**: 防守观察",
                    "- **明天仓位放多少**: 最多30%（持有但不新增）",
                ],
                "pre_market_lines": [
                    "- **跨线重点观察谁**: 军工观察(000002) - 先看60分钟确认，再看关键区间",
                    "- 查看隔夜消息、外围市场、期货走势",
                ],
                "opening_lines": [
                    "- 观察涨跌比、昨日涨停溢价率",
                    "- 这30分钟只确认环境，不抢买点",
                ],
                "first_hour_lines": [
                    "- 当前门控不允许新开仓，本时段只确认环境是否继续支持持仓/观察",
                ],
                "intraday_lines": [
                    "- 以观察和处理持仓为主，不做新开仓",
                ],
                "closing_lines": [
                    "- 若你有旧仓，确认30分钟结构止损线是否需要上移",
                ],
                "alert_rows": [
                    {
                        "name": "军工观察",
                        "code": "000002",
                        "deviation_days": 2,
                        "trigger_info": "+3.00%",
                        "actual_change_str": "-",
                        "trigger_status": "待观察",
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### Step 5 - 明日操作计划", rendered)
        self.assertIn("| 👀 明天先盯哪只 | 军工观察 | 000002 |", rendered)
        self.assertIn("**Step 5.2 明天仓位怎么放**:", rendered)
        self.assertIn("**盘前准备（08:30-09:15）**:", rendered)
        self.assertIn("**开盘前30分钟（09:30-10:00）**:", rendered)
        self.assertIn("**⚠️ 异动预警**:", rendered)
        self.assertIn("| 军工观察(000002) | 2天 | +3.00% | - | 待观察 |", rendered)


if __name__ == "__main__":
    unittest.main()
