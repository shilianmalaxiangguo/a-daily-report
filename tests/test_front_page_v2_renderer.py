import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.front_page_v2_renderer import render_front_page_v2


class FrontPageV2RendererTest(unittest.TestCase):
    def test_candidate_section_uses_observation_title_when_unique_target_is_empty(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                    },
                },
            )
        )

        self.assertIn("### 1. 主线内观察候选", rendered)
        self.assertNotIn("### 1. 主线内可执行候选", rendered)
        self.assertIn("| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |", rendered)

    def test_turnover_share_lines_derives_share_change_from_structured_same_mainline_history(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2180.00亿",
                                "market_turnover": "12834.00亿",
                                "share": "18.1%",
                                "share_change": "待累计",
                                "interpretation": "主线占比继续抬升",
                            }
                        ],
                    },
                },
            )
        )

        self.assertIn(
            "| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 主线占比继续抬升 |",
            rendered,
        )

    def test_turnover_share_lines_keeps_pending_when_previous_history_is_different_mainline(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "电力", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2180.00亿",
                                "market_turnover": "12834.00亿",
                                "share": "18.1%",
                                "share_change": "+2.3pct",
                                "interpretation": "新主线刚切换，先累计半导体自身占比",
                            }
                        ],
                    },
                },
            )
        )

        self.assertIn(
            "| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | 待累计 | 新主线刚切换，先累计半导体自身占比 |",
            rendered,
        )
        self.assertNotIn("| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct |", rendered)

    def test_market_fit_embeds_in_existing_sections_without_standalone_modules(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 上证指数 | 4079.90 | -0.33% | 震荡修复 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 市场状态 | 收缩防守 |",
                    "## 三、周期与主线",
                    "**主线内可执行候选**:",
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                    "| 华特气体 | 688268 | 电子化学 | 放量大阳线 | 未完全爆发 | 明日验证承接 | 链内跟随 | 观察 |",
                    "| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |",
                    "| 恩捷股份 | 002812 | 电池 | 轮动试探 | 只看强弱，不给买入指令 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "market_fit_calibration": {
                        "fit_label": "主线有效，池子偏窄",
                        "evidence_text": "强势样本3只，主线命中2只，观察池命中0只",
                        "cycle_note": "强势样本集中半导体，主线成交额占比抬升时优先看承接",
                        "action_text": "只扩主线内强票池",
                    },
                    "cycle_interpretation_rows": [
                        {
                            "cycle_label": "当前周期",
                            "date_range": "04-21 ~ 04-24",
                            "trading_days": "4日",
                            "mainline": "半导体",
                            "market_state": "修复接力",
                            "interpretation": "半导体接替电力，等待承接确认",
                        }
                    ],
                    "mainline_turnover_summary": {
                        "double_mainline_summary": {
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "relationship": "周期主线与当天主攻线一致",
                            "tomorrow_action": "继续围绕半导体观察承接",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-23",
                                "cycle_mainline": "电力",
                                "daily_attack_line": "电力",
                                "mainline_turnover": "2100亿",
                                "market_turnover": "12000亿",
                                "share": "17.5%",
                                "share_change": "-",
                                "interpretation": "上个周期退潮",
                            },
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2638.10亿",
                                "market_turnover": "26414.92亿",
                                "share": "10.0%",
                                "share_change": "抬升",
                                "interpretation": "主线成交额占比抬升，强势样本开始集中",
                            },
                        ],
                    },
                    "unique_action_target": {
                        "name": "富瀚微",
                        "code": "300613",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                },
                final_gate={"can_new_entry": False, "allow_conditional_30": True, "final_action": "观察，等10点确认"},
                position_level="轻仓",
            )
        )

        self.assertIn("| 市场贴合度 | 主线有效，池子偏窄 |", rendered)
        self.assertIn("强势样本集中半导体", rendered)
        self.assertIn("| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |", rendered)
        turnover_section = rendered[rendered.index("### 5. 主线成交额占比趋势") :]
        self.assertLess(turnover_section.index("2026-04-23"), turnover_section.index("2026-04-24"))
        self.assertIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", rendered)
        self.assertIn("| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)
        for forbidden in ("## 市场贴合度校准", "## 大阳线与承接", "## 主力画图", "执行权", "闸门", "门控", "开闸", "放行"):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
