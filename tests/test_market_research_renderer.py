import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)


def _cycle_sector_label_pattern(sector):
    return (
        r'<span class="cycle-sector-label" '
        r'style="color:#[0-9A-Fa-f]{6};border-color:#[0-9A-Fa-f]{6}">\['
        + re.escape(sector)
        + r"\]</span>"
    )


def _cycle_sector_colors(rendered, sector):
    pattern = (
        r'<span class="cycle-sector-label" '
        r'style="color:(#[0-9A-Fa-f]{6});border-color:\1">\['
        + re.escape(sector)
        + r"\]</span>"
    )
    return re.findall(pattern, rendered)


from report.market_research_renderer import (
    render_gem_breathing_pool_section,
    render_gem_breathing_step2_section,
    render_market_research_snapshot_section,
    render_step0_follow_section,
)
from report.front_page_v2_renderer import render_front_page_v2


class MarketResearchRendererTest(unittest.TestCase):
    def test_render_market_research_snapshot_section_renders_cycle_calendar_table(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "cycle_calendar"],
                "cycle_calendar_rows": [
                    {
                        "week_label": "04-14当周",
                        "monday": {"date": "04-14", "mainline": "电力", "state": "主导"},
                        "tuesday": {"date": "04-15", "mainline": "电力", "state": "主导"},
                        "wednesday": {"date": "04-16", "mainline": "电力", "state": "强化"},
                        "thursday": {"date": "04-17", "mainline": "电力", "state": "分化"},
                        "friday": {"date": "04-18", "mainline": "电力", "state": "退潮"},
                    },
                    {
                        "week_label": "04-21当周",
                        "monday": {"date": "04-21", "mainline": "半导体", "state": "接力"},
                        "tuesday": {"date": "04-22", "mainline": "半导体", "state": "修复"},
                        "wednesday": [
                            {"date": "04-23", "mainline": "电力", "state": "反抽"},
                            {"date": "04-23", "mainline": "半导体", "state": "偏弱"},
                        ],
                        "thursday": {"date": "04-24", "mainline": "半导体", "state": "回流"},
                        "friday": {"date": "04-25", "mainline": "-", "state": "-"},
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 1. 周期日历主视图", rendered)
        self.assertIn("| 周次 | 一 | 二 | 三 | 四 | 五 |", rendered)
        power_colors = _cycle_sector_colors(rendered, "电力")
        semiconductor_colors = _cycle_sector_colors(rendered, "半导体")
        self.assertGreaterEqual(len(power_colors), 2)
        self.assertGreaterEqual(len(semiconductor_colors), 2)
        self.assertEqual(len(set(power_colors)), 1)
        self.assertEqual(len(set(semiconductor_colors)), 1)
        self.assertNotEqual(power_colors[0], semiconductor_colors[0])
        self.assertIn("[电力]</span> 反抽 /", rendered)
        self.assertIn("[半导体]</span> 偏弱", rendered)
        self.assertNotIn("04-14 [电力] 主导", rendered)
        self.assertNotIn("04-23 [电力] 反抽", rendered)
        self.assertNotIn("电力主导", rendered)

    def test_cycle_calendar_assigns_unique_colors_beyond_base_palette(self):
        sector_names = [f"板块{i}" for i in range(1, 11)]
        rows = []
        for week_index in range(2):
            row = {"week_label": f"06-{1 + week_index * 7:02d}当周"}
            for field_index, field in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday")):
                sector = sector_names[week_index * 5 + field_index]
                row[field] = {"mainline": sector, "state": "观察"}
            rows.append(row)
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["cycle_calendar"],
                "cycle_calendar_rows": rows,
            }
        )

        rendered = "\n".join(lines)
        colors = {sector: _cycle_sector_colors(rendered, sector)[0] for sector in sector_names}
        self.assertEqual(len(set(colors.values())), len(sector_names))

    def test_cycle_calendar_marks_burst_and_ice_point_with_icons(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["cycle_calendar"],
                "cycle_calendar_rows": [
                    {
                        "week_label": "06-01当周",
                        "monday": {"date": "06-01", "mainline": "半导体", "state": "爆发"},
                        "tuesday": {"date": "06-02", "mainline": "电力", "state": "冰点"},
                        "wednesday": {"date": "06-03", "mainline": "机器人", "state": "🧊 冰点"},
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("🔥 爆发", rendered)
        self.assertIn("❄️ 冰点", rendered)
        self.assertIn("🧊 冰点", rendered)
        self.assertNotIn("❄️ 🧊", rendered)

    def test_cycle_calendar_escapes_state_text_before_markdown_html(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["cycle_calendar"],
                "cycle_calendar_rows": [
                    {
                        "week_label": "06-01当周",
                        "monday": {"date": "06-01", "mainline": "半导体", "state": '<script>alert(2)</script>爆发'},
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;爆发", rendered)
        self.assertNotIn("<script>alert(2)</script>", rendered)

    def test_state_summary_renders_market_performance_evidence_without_action_shortcut(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["state_summary"],
                "state_energy": "收缩防守",
                "state_reason": "跌停和涨跌比进入收缩区",
                "state_flow_direction": "风险释放优先",
                "market_performance_evidence": {
                    "summary": "资金雨量处于资金活跃期；阶段新高显示表态有效，雨区主要在半导体。",
                    "decision_boundary": "单指标不直接给买入或加仓；只作为旧市场表现、主线承接和参与窗口的证据。",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("**市场表现证据**", rendered)
        self.assertIn("资金雨量处于资金活跃期", rendered)
        self.assertIn("单指标不直接给买入或加仓", rendered)
        self.assertNotIn("Top50大于20%直接加仓", rendered)
        self.assertNotIn("新高多直接买入", rendered)

    def test_risk_preference_explains_heavy_turnover_index_drop_as_quant_stampede_mechanism(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["risk_preference"],
                "benchmark_change": -2.04,
                "turnover": 35072.8,
                "observation": {
                    "zt_count": 35,
                    "dt_count": 65,
                    "rise_fall_ratio_text": "0.15",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 盘面风险偏好 | 热点/趋势/异常 | 上证-2.04% / 涨停35 / 跌停65 / 涨跌比0.15 / 成交额35073亿 |", rendered)
        self.assertIn("有量配合的下跌更像指数图形走弱后，量化动量和风控卖出互相强化", rendered)
        self.assertIn("越跌图形越丑，越丑承接越弱，容易形成踩踏", rendered)

    def test_risk_preference_tolerates_malformed_observation(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["risk_preference"],
                "benchmark_change": -2.04,
                "turnover": 35072.8,
                "observation": "malformed",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 盘面风险偏好 | 热点/趋势/异常 | 上证-2.04% / 涨停0 / 跌停0 / 涨跌比暂无 / 成交额35073亿 |", rendered)

    def test_render_market_research_snapshot_section_renders_cycle_interpretation_table(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "cycle_interpretation"],
                "cycle_interpretation_rows": [
                    {
                        "cycle_label": "上个周期",
                        "date_range": "04-14 ~ 04-18",
                        "trading_days": "5日",
                        "mainline": "电力",
                        "market_state": "强化后分化",
                        "interpretation": "电力主导了上个周期，但后半段已经开始退潮，主导能力明显减弱",
                    },
                    {
                        "cycle_label": "当前周期",
                        "date_range": "04-21 ~ 04-24",
                        "trading_days": "4日",
                        "mainline": "半导体",
                        "market_state": "修复接力中",
                        "interpretation": "半导体正在尝试接替电力，但仍停留在修复段，没有进入舒服的攻击段",
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 2. 周期解读", rendered)
        self.assertIn("| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |", rendered)
        self.assertIn("[电力]</span> | 已结束周期 | 背景观察 | 强化后分化 |", rendered)
        self.assertIn("半导体正在尝试接替电力", rendered)

    def test_cycle_interpretation_and_turnover_share_reuse_cycle_sector_colors(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-02",
                market_research_snapshot={
                "enabled_node_keys": ["cycle_calendar", "cycle_interpretation", "mainline_turnover"],
                "cycle_calendar_rows": [
                    {
                        "week_label": "06-01当周",
                        "monday": {"date": "06-01", "mainline": "电力", "state": "爆发"},
                        "tuesday": {"date": "06-02", "mainline": "半导体", "state": "修复"},
                    }
                ],
                "cycle_interpretation_rows": [
                    {
                        "cycle_label": "上个周期",
                        "date_range": "06-01",
                        "trading_days": "1日",
                        "mainline": "电力",
                        "attack_line": "电力",
                        "market_state": "爆发",
                    },
                    {
                        "cycle_label": "当前周期",
                        "date_range": "06-02",
                        "trading_days": "1日",
                        "mainline": "半导体",
                        "attack_line": "半导体",
                        "market_state": "修复",
                    },
                ],
                "mainline_turnover_summary": {
                    "hot_sector_turnover_watch_rows": [
                        {
                            "date": "2026-06-02",
                            "sector_name": "电力",
                            "sector_turnover": "1000.00亿",
                            "market_turnover": "30000.00亿",
                            "share": "3.3%",
                            "share_change": "+0.8pct",
                            "sample_status": "同板块连续",
                            "interpretation": "电力成交占比抬升",
                        }
                    ],
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-06-02",
                            "cycle_mainline": "电力",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "4050.00亿",
                            "market_turnover": "30000.00亿",
                            "share": "13.5%",
                            "share_change": "+1.5pct",
                            "interpretation": "半导体接替电力",
                        }
                    ],
                },
                },
            )
        )

        power_colors = _cycle_sector_colors(rendered, "电力")
        semiconductor_colors = _cycle_sector_colors(rendered, "半导体")
        self.assertGreaterEqual(len(power_colors), 3)
        self.assertGreaterEqual(len(semiconductor_colors), 2)
        self.assertEqual(len(set(power_colors)), 1)
        self.assertEqual(len(set(semiconductor_colors)), 1)
        self.assertIn("#### 近期热点板块成交额连续跟踪：", rendered)
        self.assertIn("[电力]</span>", rendered)
        self.assertIn("| 2026-06-02 |", rendered)
        self.assertIn("| 4050.00亿 | 30000.00亿 | 13.5% | +1.5pct |", rendered)

    def test_new_cycle_sector_reuses_calendar_color_across_related_sections(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-02",
                market_research_snapshot={
                    "enabled_node_keys": ["cycle_calendar", "cycle_interpretation", "mainline_turnover"],
                    "cycle_calendar_rows": [
                        {
                            "week_label": "06-01当周",
                            "monday": {"date": "06-01", "mainline": "稀有新线A", "state": "爆发"},
                        }
                    ],
                    "cycle_interpretation_rows": [
                        {
                            "cycle_label": "当前周期",
                            "date_range": "06-01",
                            "trading_days": "1日",
                            "mainline": "稀有新线A",
                            "attack_line": "稀有新线A",
                            "market_state": "爆发",
                        }
                    ],
                    "mainline_turnover_summary": {
                        "hot_sector_turnover_watch_rows": [
                            {
                                "date": "2026-06-02",
                                "sector_name": "稀有新线A",
                                "sector_turnover": "1000.00亿",
                                "market_turnover": "30000.00亿",
                                "share": "3.3%",
                                "share_change": "+0.8pct",
                                "sample_status": "同板块连续",
                                "interpretation": "稀有新线A成交占比抬升",
                            }
                        ],
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-06-02",
                                "cycle_mainline": "稀有新线A",
                                "daily_attack_line": "稀有新线A",
                                "mainline_turnover": "1000.00亿",
                                "market_turnover": "30000.00亿",
                                "share": "3.3%",
                                "share_change": "+0.8pct",
                                "interpretation": "新线验证",
                            }
                        ],
                    },
                },
            )
        )

        colors = _cycle_sector_colors(rendered, "稀有新线A")
        self.assertGreaterEqual(len(colors), 4)
        self.assertEqual(len(set(colors)), 1)

    def test_render_market_research_snapshot_section_renders_cycle_attack_transfer_fields(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "cycle_interpretation"],
                "cycle_interpretation_rows": [
                    {
                        "cycle_label": "当前周期",
                        "date_range": "05-14",
                        "trading_days": "1日",
                        "mainline": "半导体",
                        "attack_line": "半导体",
                        "cycle_stage": "切换试攻",
                        "transfer_state": "首次攻击",
                        "market_state": "观察",
                        "tomorrow_validation": "看是否二次攻击，不能由单日攻击自动升级周期主线",
                        "interpretation": "半导体今日攻击成立，但传递性不足，不自动升级周期主线。",
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("[半导体]</span> | 切换试攻 | 首次攻击 | 观察 | 看是否二次攻击，不能由单日攻击自动升级周期主线 | 半导体今日攻击成立，但传递性不足，不自动升级周期主线。 |", rendered)
        self.assertNotIn("| 周期 | 时间段 | 交易日数 | 主导主线 | 市场状态 | 周期解读 |", rendered)
        self.assertNotIn("正在承担当前周期的主线观察任务", rendered)

    def test_market_research_cycle_layer_keeps_recent_five_cycles(self):
        records = [
            {"date": "2026-05-18", "primary_mainline": "电力", "market_state": "爆发"},
            {"date": "2026-05-19", "primary_mainline": "电力", "market_state": "分化"},
            {"date": "2026-05-20", "primary_mainline": "半导体", "market_state": "试攻"},
            {"date": "2026-05-21", "primary_mainline": "机器人", "market_state": "接力"},
            {"date": "2026-05-22", "primary_mainline": "电力", "market_state": "回流"},
            {"date": "2026-05-25", "primary_mainline": "光通信/CPO", "market_state": "爆发"},
        ]
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["cycle_interpretation"],
                "recent_mainline_history": records[:-1],
                "current_mainline_history_record": records[-1],
            }
        )

        rendered = "\n".join(lines)
        self.assertRegex(
            rendered,
            r"\| 近5周期-1 \| 05-18 ~ 05-19 \| 2日 \| "
            + _cycle_sector_label_pattern("电力")
            + r" \| 已结束周期 \|",
        )
        self.assertRegex(
            rendered,
            r"\| 近5周期-4 \| 05-22 \| 1日 \| "
            + _cycle_sector_label_pattern("电力")
            + r" \| 已结束周期 \|",
        )
        self.assertRegex(
            rendered,
            r"\| 当前周期 \| 05-25 \| 1日 \| "
            + _cycle_sector_label_pattern("光通信/CPO")
            + r" \|",
        )
        self.assertNotIn("| 上个周期 |", rendered)

    def test_market_research_cycle_calendar_marks_missing_elapsed_days_as_unverified(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["cycle_calendar"],
                "recent_mainline_history": [
                    {"date": "2026-05-29", "primary_mainline": "电力", "market_state": "爆发"},
                ],
                "current_mainline_history_record": {
                    "date": "2026-06-04",
                    "primary_mainline": "国产芯片替代",
                    "market_state": "支线轮动",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn(
            "| 06-01当周 | [主线记录待核验] 待确认 | [主线记录待核验] 待确认 | [主线记录待核验] 待确认 |",
            rendered,
        )
        self.assertIn("[国产芯片替代]</span> 支线轮动 | - |", rendered)

    def test_render_market_research_snapshot_section_renders_pivot_mainline_interpretation_table(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "pivot_mainline_interpretation"],
                "pivot_mainline_rows": [
                    {
                        "date_range": "04-14 ~ 04-18",
                        "pivot_level": "大中枢",
                        "pivot_range": "3992.41 - 4114.84",
                        "position": "中枢上沿",
                        "structure_state": "上沿承压",
                        "mainline": "电力",
                        "mainline_degree": "大主线",
                        "evolution": "高位分化",
                        "replacement": "中枢震荡",
                        "interpretation": "[电力] 在这一段先主导市场，随后高位分化，主导能力开始减弱",
                    },
                    {
                        "date_range": "04-21 ~ 04-23",
                        "pivot_level": "小中枢",
                        "pivot_range": "3992.41 - 4114.84",
                        "position": "中枢内",
                        "structure_state": "中枢内震荡",
                        "mainline": "半导体",
                        "mainline_degree": "小周期主线",
                        "evolution": "修复接力",
                        "replacement": "接替电力",
                        "interpretation": "[半导体] 开始接替 [电力]，但目前只是修复接力，还没有形成稳定攻击段",
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 3. 中枢与主线解读", rendered)
        self.assertIn("| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 结构解读 |", rendered)
        self.assertIn("| 04-14 ~ 04-18 | 大中枢 | 3992.41 - 4114.84 | 中枢上沿 | 电力 | 大主线 | 高位分化 | 中枢震荡 |", rendered)
        self.assertIn("| 04-21 ~ 04-23 | 小中枢 | 3992.41 - 4114.84 | 中枢内 | 半导体 | 小周期主线 | 修复接力 | 接替电力 |", rendered)
        self.assertIn("[半导体] 开始接替 [电力]", rendered)
        self.assertNotIn("震荡 / 修复", rendered)

    def test_market_research_cycle_layer_keeps_recent_three_pivots(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["pivot_mainline_interpretation"],
                "recent_mainline_history": [
                    {"date": "2026-05-20", "primary_mainline": "半导体", "market_state": "试攻"},
                    {"date": "2026-05-21", "primary_mainline": "机器人", "market_state": "接力"},
                    {"date": "2026-05-22", "primary_mainline": "电力", "market_state": "回流"},
                ],
                "pivot_mainline_history": [
                    {"date_range": "05-13 ~ 05-15", "pivot_level": "日线中枢", "mainline": "小金属", "evolution": "退潮"},
                    {"date_range": "05-18 ~ 05-19", "pivot_level": "日线中枢", "mainline": "半导体", "evolution": "试攻"},
                    {"date_range": "05-20 ~ 05-21", "pivot_level": "日线中枢", "mainline": "机器人", "evolution": "接力"},
                    {"date_range": "05-22", "pivot_level": "日线中枢", "mainline": "电力", "evolution": "回流"},
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertNotIn("05-13 ~ 05-15", rendered)
        self.assertIn("05-18 ~ 05-19", rendered)
        self.assertIn("05-20 ~ 05-21", rendered)
        self.assertIn("05-22", rendered)

    def test_render_market_research_snapshot_section_renders_mainline_turnover_node(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_turnover"],
                "mainline_turnover_summary": {
                    "conclusion": "主线未切换，通信仍是中心",
                    "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化",
                    "action_text": "继续围绕通信做减法，不追支线分流",
                    "turnover_share_trend_summary": "近25个交易日主线成交额占比趋势：当前17.0%，区间12.4%-17.0%，主线成交占比抬升，资金聚焦度走强。",
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-04-23",
                            "cycle_mainline": "电力",
                            "daily_attack_line": "电力",
                            "mainline_turnover": "2000.00亿",
                            "market_turnover": "12000.00亿",
                            "share": "16.0%",
                            "share_change": "-",
                            "interpretation": "旧周期退潮",
                        },
                        {
                            "date": "2026-04-24",
                            "cycle_mainline": "通信",
                            "daily_attack_line": "通信",
                            "mainline_turnover": "2180.00亿",
                            "market_turnover": "12834.00亿",
                            "share": "17.0%",
                            "share_change": "+1.2pct",
                            "interpretation": "主线占比继续抬升",
                        }
                    ],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |", rendered)
        self.assertIn("| 主线更替与成交额占比 | 主线未切换，通信仍是中心 |", rendered)
        self.assertIn("最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化", rendered)
        self.assertIn("继续围绕通信做减法，不追支线分流", rendered)
        self.assertIn("#### 小周期成交额与主线切换判断", rendered)
        self.assertIn("> 近25个交易日主线成交额占比趋势：当前17.0%，区间12.4%-17.0%，主线成交占比抬升，资金聚焦度走强。", rendered)
        self.assertIn("| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |", rendered)
        self.assertNotIn("| 日期 | 周期主线 | 当天主攻线 |", rendered)
        self.assertRegex(
            rendered,
            r"\| 2026-04-24 \| "
            + _cycle_sector_label_pattern("通信")
            + r" \| 2180\.00亿 \| 12834\.00亿 \| 17\.0% \| \+1\.2pct \| 大周期延续 \| 主线占比继续抬升 \|",
        )
        self.assertLess(rendered.index("2026-04-24"), rendered.index("2026-04-23"))
        self.assertNotIn("| 盘面风险偏好 |", rendered)

    def test_mainline_turnover_marks_small_cycle_attack_when_attack_line_differs(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["mainline_turnover"],
                "mainline_turnover_summary": {
                    "conclusion": "通信试攻，电力仍是周期参照",
                    "data_text": "周期主线与当天主攻线出现分化",
                    "action_text": "先看通信承接，不急着把电力移出参照",
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-04-24",
                            "cycle_mainline": "电力",
                            "daily_attack_line": "通信",
                            "mainline_turnover": "2180.00亿",
                            "market_turnover": "12834.00亿",
                            "share": "17.0%",
                            "share_change": "+1.2pct",
                            "interpretation": "通信试图接替电力",
                        }
                    ],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |", rendered)
        self.assertNotIn("| 日期 | 周期主线 | 当天主攻线 |", rendered)
        self.assertRegex(
            rendered,
            r"\| 2026-04-24 \| "
            + _cycle_sector_label_pattern("通信")
            + r" \| 2180\.00亿 \| 12834\.00亿 \| 17\.0% \| \+1\.2pct \| 小周期试攻，未确认切换 \| 通信试图接替电力 \|",
        )

    def test_mainline_turnover_skips_malformed_trend_rows(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["mainline_turnover"],
                "turnover_share_trend_rows": ["malformed"],
                "mainline_turnover_summary": {
                    "conclusion": "主线未切换，通信仍是中心",
                    "data_text": "最近3日主线 通信 -> 通信 -> 通信",
                    "action_text": "继续围绕通信做减法",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线更替与成交额占比 | 主线未切换，通信仍是中心 | 最近3日主线 通信 -> 通信 -> 通信 | 继续围绕通信做减法 |", rendered)
        self.assertNotIn("#### 主线成交额占比趋势", rendered)
        self.assertNotIn("malformed", rendered)

    def test_render_market_research_snapshot_section_renders_mainline_capacity_regime_node(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_capacity_regime"],
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "双线孕育",
                        "mainline_regime": "混沌接力",
                        "primary_line": "半导体",
                        "other_lines": "电力 / 化学制品",
                        "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                        "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                        "mainline_process": "半导体启动，电力背景线",
                        "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                    },
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                        "sector_evidence_rows": [
                            {
                                "sector_name": "半导体",
                                "net_inflow_rank": 1,
                                "net_inflow_amount": 45.0,
                                "limit_up_count": 5,
                                "high_anchor_height": 4,
                                "turnover_share_change": 1.6,
                            },
                            {
                                "sector_name": "电力",
                                "net_inflow_rank": 2,
                                "net_inflow_amount": 8.0,
                                "limit_up_count": 1,
                                "high_anchor_height": 1,
                                "turnover_share_change": -0.5,
                            },
                        ],
                    },
                    "overtake_window_summary": {
                        "window_state": "open",
                        "rival_slowdown": "旧主线承接转弱，竞争线冲高回落",
                        "own_stability": "半导体资金扩散，核心承接稳定",
                        "observation_maturity": "跑过一段后再判断",
                        "overtake_logic": "对手过弯打滑，我方仍能弯道加速",
                        "arena_boundary": "短线/超短主战场内主动出手",
                        "speed_gap": "失速差拉开",
                        "action": "只在半导体核心里找参与资格",
                    },
                    "trading_arena_fit_summary": {
                        "fit_state": "home_arena",
                        "arena_label": "短线/超短线主战场",
                        "market_style": "单主线聚焦",
                        "fit_reason": "量能、资金扩散、板块效应和核心承接进入短线/超短线可发挥区",
                        "action": "按短线/超短线主战场处理，围绕半导体核心继续寻找参与资格",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("### 4. 主线容量与格局判断", rendered)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 混沌接力 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
        self.assertIn("#### 主线攻击证据", rendered)
        self.assertIn("| 半导体 | 确认主攻线 | 第1 | +45.00亿 | 5 | 4 | +1.6pct | 半导体资金净流入靠前，涨停和高标更集中，成交占比扩张 |", rendered)
        self.assertIn("#### 超车窗口判断", rendered)
        self.assertIn("| 观察成熟度 | 对手方向 | 对手弱化证据 | 我方方向 | 我方承接证据 | 超车逻辑 | 主战场边界 | 失速差 | 不成立条件 | 明日验证 |", rendered)
        self.assertIn("| 跑过一段后再判断 | 旧主线 | 旧主线承接转弱，竞争线冲高回落 | 半导体 | 半导体资金扩散，核心承接稳定 | 对手过弯打滑，我方仍能弯道加速 | 短线/超短主战场内主动出手 | 失速差拉开 | 对手重新放量回流或半导体开盘不承接 | 只在半导体核心里找参与资格 |", rendered)
        self.assertIn("#### 能力圈匹配判断", rendered)
        self.assertIn("| 适配位置 | 行情类型 | 适配理由 | 明日动作 |", rendered)
        self.assertIn("| 短线/超短线主战场 | 单主线聚焦 | 量能、资金扩散、板块效应和核心承接进入短线/超短线可发挥区 | 按短线/超短线主战场处理，围绕半导体核心继续寻找参与资格 |", rendered)

    def test_market_capacity_evolution_enabled_node_renders_replacement_phase_summary(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["market_capacity_evolution"],
                "turnover": 12834,
                "turnover_ma5": 11800,
                "turnover_quality": "做多放量",
                "market_stats": {"up_count": 3200, "down_count": 1700},
                "capacity_evidence": "半导体成交占比连续抬升，电力占比回落。",
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "双线竞争",
                        "mainline_regime": "主线+背景线",
                        "primary_line": "半导体",
                        "other_lines": "电力",
                        "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                        "sector_relationship_state": "半导体接替电力，电力退成背景线",
                        "mainline_process": "半导体从试攻转为接替",
                        "tomorrow_action": "先看半导体承接能否继续强于电力",
                    },
                    "overtake_window_summary": {
                        "window_state": "confirm_next",
                        "rival_line": "电力",
                        "own_line": "半导体",
                        "rival_slowdown": "电力成交占比回落",
                        "own_stability": "半导体核心承接稳定",
                        "action": "半导体继续拉升则确认接替",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-05-27",
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "1900.00亿",
                            "market_turnover": "12000.00亿",
                            "share": "15.8%",
                            "share_change": "+0.8pct",
                            "interpretation": "接替试攻",
                        },
                        {
                            "date": "2026-05-28",
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "2250.00亿",
                            "market_turnover": "12834.00亿",
                            "share": "17.6%",
                            "share_change": "+1.8pct",
                            "interpretation": "接替继续",
                        },
                    ],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 市场容量演化", rendered)
        self.assertIn("**当前阶段**: 接替期（竞争关系）", rendered)
        self.assertIn("成交量质量: 做多放量", rendered)
        self.assertIn("主线容量: 双线竞争", rendered)
        self.assertIn("#### 板块竞争关系", rendered)
        self.assertIn("主攻线: 半导体", rendered)
        self.assertIn("竞争线/背景线: 电力", rendered)
        self.assertIn("半导体从试攻转为接替", rendered)
        self.assertIn("2026-05-28 半导体/半导体 17.6%（+1.8pct）", rendered)
        self.assertIn("#### 明日观察", rendered)
        self.assertIn("竞争线/背景线反超", rendered)

    def test_market_capacity_evolution_replacement_phase_wins_when_volume_quality_is_selloff(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["market_capacity_evolution"],
                "turnover_quality": "杀跌放量",
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "双线竞争",
                        "mainline_regime": "主线+背景线",
                        "primary_line": "半导体",
                        "other_lines": "电力",
                        "confirmation_evidence": "半导体承接强于电力",
                        "sector_relationship_state": "半导体接替电力",
                        "mainline_process": "接替确认中",
                        "tomorrow_action": "先看半导体承接",
                    },
                    "overtake_window_summary": {"window_state": "confirm_next"},
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("**当前阶段**: 接替期（竞争关系）", rendered)
        self.assertIn("成交量质量: 杀跌放量", rendered)

    def test_market_capacity_evolution_waits_when_turnover_quality_missing(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["market_capacity_evolution"],
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "双线竞争",
                        "mainline_regime": "主线+背景线",
                        "primary_line": "半导体",
                        "other_lines": "电力",
                        "confirmation_evidence": "半导体承接强于电力",
                        "sector_relationship_state": "半导体接替电力",
                        "mainline_process": "接替确认中",
                        "tomorrow_action": "先看半导体承接",
                    },
                    "overtake_window_summary": {"window_state": "confirm_next"},
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("**当前阶段**: 待确认", rendered)
        self.assertNotIn("**当前阶段**: 接替期（竞争关系）", rendered)

    def test_market_capacity_evolution_tolerates_malformed_optional_inputs(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["market_capacity_evolution"],
                "turnover_quality": "做多放量",
                "market_stats": "malformed",
                "observation": ["malformed"],
                "turnover_share_trend_rows": ["malformed"],
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "单线承载",
                        "mainline_regime": "单主线聚焦",
                        "primary_line": "半导体",
                        "other_lines": "-",
                        "confirmation_evidence": "半导体成交占比和高标反馈同步",
                        "sector_relationship_state": "单主线聚焦",
                        "mainline_process": "主线稳定",
                        "tomorrow_action": "只看半导体核心承接",
                    },
                    "overtake_window_summary": {"window_state": "open"},
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 市场容量演化", rendered)
        self.assertIn("**当前阶段**: 分化期（趋势确立）", rendered)
        self.assertNotIn("最近占比", rendered)

    def test_default_snapshot_order_places_market_capacity_evolution_between_capacity_and_sector_analysis(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "turnover_quality": "做多放量",
                "mainline_days": 3,
                "turnover": 12834,
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "单线承载",
                        "mainline_regime": "单主线聚焦",
                        "primary_line": "半导体",
                        "other_lines": "算力",
                        "confirmation_evidence": "半导体成交占比和高标反馈同步",
                        "sector_relationship_state": "单主线聚焦",
                        "mainline_process": "主线稳定",
                        "tomorrow_action": "只看半导体核心承接",
                    },
                    "overtake_window_summary": {
                        "window_state": "open",
                        "own_line": "半导体",
                        "own_stability": "半导体核心承接稳定",
                    },
                },
                "sector_internal_analysis": {
                    "sectors": [
                        {
                            "sector_name": "半导体",
                            "core_anchor": {"name": "芯片核心A", "code": "688001", "status": "放量上涨"},
                            "relative_position": {"leaders": [], "core_anchors": [], "followers": [], "conclusion": "资金向核心集中"},
                            "elastic_carrier": {"count": 0, "new_high_count": 0, "intraday_support": "弱", "stocks": []},
                            "follower_support": {"grade": "C", "gain_5pct_count": 0, "gain_3pct_count": 0, "volume_ratio": 0.0},
                            "second_wave_new_highs": {"count": 0, "ratio": 0.0, "stocks": [], "description": "近5日暂无二波创新高群"},
                        }
                    ],
                    "sector_fund_flow": {"flows": []},
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertLess(rendered.index("### 4. 主线容量与格局判断"), rendered.index("### 市场容量演化"))
        self.assertLess(rendered.index("### 市场容量演化"), rendered.index("### 板块内部分析"))

    def test_market_capacity_evolution_does_not_duplicate_capacity_regime_table(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "turnover_quality": "缩量",
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "容量待累计",
                        "mainline_regime": "混沌轮动",
                        "primary_line": "暂无",
                        "other_lines": "半导体 / 电力",
                        "confirmation_evidence": "多方向轮动，资金未明显胜出",
                        "sector_relationship_state": "暂未分出",
                        "mainline_process": "等待下一轮资金选择",
                        "tomorrow_action": "先看量能是否重新放大",
                    },
                    "overtake_window_summary": {"window_state": "observe"},
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 市场容量演化", rendered)
        self.assertEqual(1, rendered.count("| 主线容量 | 主线格局 |"))

    def test_sector_internal_analysis_renders_all_dimensions_when_context_allows(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis"],
                "window_state": "open",
                "mainline_regime": "单主线聚焦",
                "primary_line": "半导体",
                "turnover_quality": "做多放量",
                "mainline_days": 3,
                "sector_internal_analysis": {
                    "sectors": [
                        {"sector_name": "机器人", "core_anchor": {"name": "机器核心", "code": "300001", "status": "待观察"}},
                        {
                            "sector_name": "半导体",
                            "core_anchor": {
                                "name": "芯片核心A",
                                "code": "688001",
                                "status": "放量上涨",
                                "volume": 320.0,
                                "volume_ratio_in_sector": 0.28,
                                "change_pct": 7.2,
                            },
                            "relative_position": {
                                "leaders": [{"name": "芯片核心A", "code": "688001", "change_pct": 7.2, "volume": 320.0}],
                                "core_anchors": [{"name": "芯片核心A", "code": "688001", "status": "放量上涨"}],
                                "followers": [{"name": "后排B", "code": "688002", "change_pct": 3.5, "volume": 80.0}],
                                "leader_avg_change": 7.2,
                                "core_avg_change": 7.2,
                                "follower_avg_change": 3.5,
                                "leader_volume_ratio": 0.28,
                                "core_volume_ratio": 0.28,
                                "follower_volume_ratio": 0.42,
                                "conclusion": "资金向核心集中",
                            },
                            "elastic_carrier": {
                                "count": 2,
                                "new_high_count": 2,
                                "intraday_support": "强",
                                "stocks": [{"name": "弹性C", "code": "688003", "change_pct": 9.1}],
                            },
                            "follower_support": {
                                "grade": "B",
                                "gain_5pct_count": 3,
                                "gain_3pct_count": 6,
                                "volume_ratio": 0.42,
                                "description": "后排承接B级",
                            },
                            "second_wave_new_highs": {
                                "count": 2,
                                "ratio": 0.18,
                                "stocks": [{"name": "二波D", "code": "688004"}],
                                "description": "近5日至少2次创新高的个股有2只",
                            },
                            "total_stocks": 12,
                            "turnover_share_change": 2.5,
                        },
                    ],
                    "sector_fund_flow": {
                        "description": "算力成交占比下降，半导体成交占比上升。",
                        "flows": [
                            {
                                "from_sector": "算力",
                                "to_sector": "半导体",
                                "type": "扩散分流",
                                "volume_change": 800.0,
                            }
                        ],
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 板块内部分析", rendered)
        self.assertIn("**当前阶段**: 主线稳定期", rendered)
        self.assertIn("**分析板块**: 半导体", rendered)
        self.assertIn("#### 中军状态", rendered)
        self.assertIn("#### 板块内相对位置", rendered)
        self.assertIn("#### 弹性载体", rendered)
        self.assertIn("#### 后排承接质量", rendered)
        self.assertIn("#### 二波创新高群", rendered)
        self.assertIn("#### 板块间资金流动", rendered)

    def test_sector_internal_analysis_observe_phase_stops_before_detail_sections(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis"],
                "sector_analysis_trigger": {
                    "should_analyze": False,
                    "phase": "粘合期",
                    "reason": "条件偏观察，先不做板块内部分析。",
                    "dimensions": [],
                },
                "sector_internal_analysis": {
                    "sectors": [{"sector_name": "半导体", "core_anchor": {"name": "芯片核心A", "status": "放量上涨"}}],
                    "sector_fund_flow": {"flows": []},
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 板块内部分析", rendered)
        self.assertIn("**当前阶段**: 粘合期", rendered)
        self.assertIn("条件偏观察，先不做板块内部分析。", rendered)
        self.assertNotIn("#### 中军状态", rendered)
        self.assertNotIn("#### 板块内相对位置", rendered)
        self.assertNotIn("#### 弹性载体", rendered)
        self.assertNotIn("#### 后排承接质量", rendered)
        self.assertNotIn("#### 二波创新高群", rendered)
        self.assertNotIn("#### 板块间资金流动", rendered)

    def test_sector_internal_analysis_omits_section_without_analysis_data_by_default(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis"],
            }
        )

        rendered = "\n".join(lines)
        self.assertNotIn("### 板块内部分析", rendered)

    def test_sector_internal_analysis_explicit_analyze_without_sector_does_not_render_placeholder_sector(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis"],
                "sector_analysis_trigger": {
                    "should_analyze": True,
                    "phase": "主线稳定期",
                    "reason": "主攻线已进入可拆解区。",
                    "dimensions": [],
                },
                "sector_internal_analysis": {"sectors": [], "sector_fund_flow": {}},
            }
        )

        rendered = "\n".join(lines)
        self.assertNotIn("**分析板块**: -", rendered)

    def test_sector_internal_analysis_false_branch_hides_sector_and_core_fields(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis"],
                "sector_analysis_trigger": {
                    "should_analyze": False,
                    "phase": "粘合期",
                    "reason": "条件偏观察，先不做板块内部拆解。",
                    "dimensions": [],
                },
                "sector_internal_analysis": {
                    "sectors": [
                        {
                            "sector_name": "半导体",
                            "total_stocks": 12,
                            "turnover_share_change": 2.5,
                            "core_anchor": {"name": "芯片核心A", "status": "放量上涨"},
                        }
                    ],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 板块内部分析", rendered)
        self.assertIn("**当前阶段**: 粘合期", rendered)
        self.assertIn("**判断原因**: 条件偏观察，先不做板块内部拆解。", rendered)
        self.assertNotIn("**分析板块**", rendered)
        self.assertNotIn("**核心字段**", rendered)
        self.assertNotIn("#### 中军状态", rendered)

    def test_sector_internal_analysis_tolerates_malformed_nested_data(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis"],
                "sector_analysis_trigger": {
                    "should_analyze": True,
                    "phase": "主线稳定期",
                    "reason": "主攻线已进入可拆解区。",
                    "dimensions": [
                        "中军识别与跟踪",
                        "板块内相对位置",
                        "弹性载体识别",
                        "后排承接质量",
                        "二波创新高群",
                        "板块间资金流动",
                    ],
                },
                "sector_internal_analysis": {
                    "sectors": [
                        "半导体",
                        {
                            "sector_name": "半导体",
                            "core_anchor": "芯片核心A",
                            "relative_position": "核心更强",
                            "elastic_carrier": "弹性扩散",
                            "follower_support": "后排分化",
                            "second_wave_new_highs": "暂无",
                        },
                    ],
                    "sector_fund_flow": "半导体流入",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 板块内部分析", rendered)
        self.assertIn("**分析板块**: 半导体", rendered)
        self.assertIn("#### 中军状态", rendered)
        self.assertIn("#### 板块间资金流动", rendered)

    def test_sector_internal_analysis_formats_unit_strings(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis"],
                "sector_analysis_trigger": {
                    "should_analyze": True,
                    "phase": "主线稳定期",
                    "reason": "主攻线已进入可拆解区。",
                    "dimensions": [
                        "中军识别与跟踪",
                        "板块内相对位置",
                        "后排承接质量",
                        "二波创新高群",
                        "板块间资金流动",
                    ],
                },
                "sector_internal_analysis": {
                    "sectors": [
                        {
                            "sector_name": "半导体",
                            "total_stocks": "1,280",
                            "turnover_share_change": "+1.6pct",
                            "core_anchor": {
                                "name": "芯片核心A",
                                "code": "688001",
                                "status": "放量上涨",
                                "volume": "320.00亿",
                                "volume_ratio_in_sector": "28.0%",
                                "change_pct": "+7.2%",
                            },
                            "relative_position": {
                                "leaders": [{"name": "芯片核心A", "code": "688001"}],
                                "leader_avg_change": "+7.2%",
                                "leader_volume_ratio": "28.0%",
                                "conclusion": "资金向核心集中",
                            },
                            "follower_support": {
                                "grade": "B",
                                "volume_ratio": "28.0%",
                            },
                            "second_wave_new_highs": {
                                "count": 2,
                                "ratio": "28.0%",
                            },
                        }
                    ],
                    "sector_fund_flow": {
                        "description": "半导体成交占比上升。",
                        "flows": [{"from_sector": "算力", "to_sector": "半导体", "type": "扩散分流", "volume_change": "320.00亿"}],
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("样本1,280只；成交占比变化+1.60%", rendered)
        self.assertIn("成交额320.00亿；板块内占比28.0%；涨跌幅+7.20%", rendered)
        self.assertIn("| 领涨层 | 芯片核心A(688001) | +7.20% | 28.0% | 资金向核心集中 |", rendered)
        self.assertIn("| 算力 | 半导体 | 扩散分流 | 320.00亿 |", rendered)

    def test_sector_internal_analysis_keeps_evidence_header_with_risk_preference(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["sector_internal_analysis", "risk_preference"],
                "sector_analysis_trigger": {
                    "should_analyze": False,
                    "phase": "粘合期",
                    "reason": "先观察。",
                    "dimensions": [],
                },
                "benchmark_change": -2.04,
                "turnover": 35072.8,
                "observation": {
                    "zt_count": 35,
                    "dt_count": 65,
                    "rise_fall_ratio_text": "0.15",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |", rendered)
        self.assertIn("| 盘面风险偏好 | 热点/趋势/异常 | 上证-2.04% / 涨停35 / 跌停65 / 涨跌比0.15 / 成交额35073亿 |", rendered)
        self.assertLess(rendered.index("### 板块内部分析"), rendered.index("| 证据环节 |"))

    def test_default_snapshot_order_places_sector_internal_analysis_after_capacity(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "turnover_quality": "做多放量",
                "mainline_days": 3,
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "单线承载",
                        "mainline_regime": "单主线聚焦",
                        "primary_line": "半导体",
                        "other_lines": "算力",
                        "confirmation_evidence": "半导体成交占比和高标反馈同步",
                        "sector_relationship_state": "单主线聚焦",
                        "mainline_process": "主线稳定",
                        "tomorrow_action": "只看半导体核心承接",
                    },
                    "overtake_window_summary": {
                        "window_state": "open",
                        "own_stability": "半导体核心承接稳定",
                    },
                },
                "sector_internal_analysis": {
                    "sectors": [
                        {
                            "sector_name": "半导体",
                            "core_anchor": {"name": "芯片核心A", "code": "688001", "status": "放量上涨"},
                            "relative_position": {"leaders": [], "core_anchors": [], "followers": [], "conclusion": "资金向核心集中"},
                            "elastic_carrier": {"count": 0, "new_high_count": 0, "intraday_support": "弱", "stocks": []},
                            "follower_support": {"grade": "C", "gain_5pct_count": 0, "gain_3pct_count": 0, "volume_ratio": 0.0},
                            "second_wave_new_highs": {"count": 0, "ratio": 0.0, "stocks": [], "description": "近5日暂无二波创新高群"},
                        }
                    ],
                    "sector_fund_flow": {"flows": []},
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertLess(rendered.index("### 4. 主线容量与格局判断"), rendered.index("### 板块内部分析"))

    def test_render_market_research_snapshot_mainline_focus_downgrades_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_focus"],
                "competition_result": "主攻线 半导体",
                "competition_evidence": "趋势2只 / 强势1只 / 涨停2只",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线焦点 | 无确认主攻线 | 多方向局部活跃但资金未明显胜出 | 候选只观察，不给买入资格 |", rendered)
        self.assertNotIn("主攻线 半导体", rendered)

    def test_render_market_research_snapshot_mainline_focus_uses_confirmed_attack_over_stale_context(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["mainline_focus"],
                "competition_result": "主攻线 半导体",
                "competition_evidence": "旧焦点",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线焦点 | 主攻线 人形机器人 | 人形机器人资金净流入靠前，涨停更集中 | 优先聚焦主线对象 |", rendered)
        self.assertNotIn("主攻线 半导体", rendered)

    def test_render_market_research_snapshot_turnover_rows_downgrade_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_turnover"],
                "mainline_turnover_summary": {
                    "conclusion": "主线待确认，暂不输出成交额占比结论",
                    "data_text": "最近1日主线 半导体 -> 电力 -> 电力；成交额占比 12.4%，节奏偏持平",
                    "action_text": "先等待主线明确，再谈成交额占比趋势",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-05-14",
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "4206.70亿",
                            "market_turnover": "33880.86亿",
                            "share": "12.4%",
                            "share_change": "待累计",
                            "interpretation": "主线成交额占比可用，继续观察占比抬升或回落",
                        }
                    ],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |", rendered)
        self.assertNotIn("| 日期 | 周期主线 | 当天主攻线 |", rendered)
        self.assertRegex(
            rendered,
            r"\| 2026-05-14 \| "
            + _cycle_sector_label_pattern("半导体")
            + r" \| 4206\.70亿 \| 33880\.86亿 \| 12\.4% \| 待累计 \| 大周期延续 \| 主线成交额占比可用，继续观察占比抬升或回落 \|",
        )
        self.assertNotIn("| 2026-05-14 | 暂无确认主线 | 暂无确认主攻线 | 4206.70亿", rendered)

    def test_render_market_research_snapshot_rotation_downgrades_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "rotation"],
                "rotation_label": "爆发",
                "rotation_summary_text": "主攻线半导体 / 次强线电力 / 竞争线光伏设备",
                "rotation_action": "继续围着半导体做减法，只盯主攻线承接",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线内部轮动 | 混沌轮动 | 多方向局部活跃但资金未明显胜出 | 不围着单一方向做减法，只保留候选观察 |", rendered)
        self.assertNotIn("主攻线半导体", rendered)
        self.assertNotIn("继续围着半导体做减法", rendered)

    def test_render_market_research_snapshot_rotation_uses_countertrend_attack_line_instead_of_stale_rotation_text(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "rotation"],
                "rotation_label": "逆势攻击",
                "rotation_summary_text": "当前逆势攻击；主攻线半导体 / 次强线电力 / 竞争线证券",
                "rotation_action": "先防踩踏，只观察半导体次日是否修复承接",
                "mainline_turnover_summary": {
                    "share_trend_label": "逆势试攻",
                    "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
                    "action_text": "人形机器人只按观察主攻线处理，先防踩踏，再看次日是否修复承接",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线内部轮动 | 逆势攻击 | 人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理 | 人形机器人只按观察主攻线处理，先防踩踏，再看次日是否修复承接 |", rendered)
        self.assertNotIn("主攻线半导体", rendered)
        self.assertNotIn("只观察半导体", rendered)

    def test_rotation_node_renders_table_header_when_used_without_section_header(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["rotation"],
                "rotation_label": "分化整理",
                "rotation_summary_text": "主攻线电力 / 次强线通信设备",
                "rotation_action": "先看电力能否重新聚焦",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |", rendered)
        self.assertLess(rendered.index("| 证据环节 |"), rendered.index("| 主线内部轮动 |"))

    def test_render_market_research_snapshot_narrative_uses_countertrend_attack_line_instead_of_stale_narrative(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "narrative"],
                "narrative_label": "半导体节点",
                "narrative_reason": "半导体设备在归链里更接近半导体这一节点",
                "narrative_action": "先盯半导体的承接是否继续",
                "mainline_turnover_summary": {
                    "share_trend_label": "逆势试攻",
                    "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
                    "action_text": "人形机器人只按观察主攻线处理，先防踩踏，再看次日是否修复承接",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 叙事节点 | 逆势观察 | 人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理 | 人形机器人只按观察主攻线处理，先防踩踏，再看次日是否修复承接 |", rendered)
        self.assertNotIn("半导体节点", rendered)
        self.assertNotIn("先盯半导体", rendered)

    def test_render_market_research_snapshot_narrative_downgrades_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "narrative"],
                "narrative_label": "半导体节点",
                "narrative_reason": "产业催化发酵，半导体目前是主攻线",
                "narrative_action": "继续盯半导体",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 叙事节点 | 叙事待验证 | 题材只能做背景，先看板块攻击证据是否胜出 | 不把节点热度当主线确认 |", rendered)
        self.assertNotIn("半导体目前是主攻线", rendered)
        self.assertNotIn("继续盯半导体", rendered)

    def test_market_research_snapshot_decision_lines_use_adopted_tag_label(self):
        tag_snapshot = {
            "groups": [
                {
                    "采用名称": "国产芯片替代",
                    "关系判断": "父子",
                    "表层行业名": ["元件", "元器件"],
                }
            ]
        }
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": [
                    "rotation",
                    "narrative",
                    "state_summary",
                    "trend_density",
                    "dialectical_decision",
                ],
                "realtime_tag_evidence_snapshot": tag_snapshot,
                "rotation_label": "支线轮动",
                "rotation_summary_text": "主攻线元件 / 次强线电力；趋势密度12只",
                "rotation_action": "先盯元件的承接是否继续",
                "narrative_label": "泛半导体/硬科技电子节点",
                "narrative_reason": "元件在归链里更接近泛半导体/硬科技电子这一节点",
                "narrative_action": "先盯元件的承接是否继续",
                "state_energy": "收缩防守",
                "state_reason": "风险释放优先",
                "state_flow_direction": "趋势密度最强的是元器件",
                "observation": {"densest_sector": "元器件", "densest_sector_trend_count": 12},
                "dialectical_decision": {
                    "stage_label": "收缩防守",
                    "stage_reason": "风险释放仍优先",
                    "index_profit_relation": "指数和赚钱效应同步修复",
                    "index_profit_reason": "指数、热点聚焦同向改善",
                    "focus_label": "赚钱效应继续向元器件聚集",
                    "focus_action": "只在元器件和相关异常承接对象里继续做减法。",
                    "candidate_focus": "优先率先转强的对象",
                    "candidate_action": "先观察",
                    "falsification_conditions": ["元器件的趋势密度和承接同时走弱"],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("主攻线国产芯片替代", rendered)
        self.assertIn("先盯国产芯片替代的承接是否继续", rendered)
        self.assertIn("趋势密度最强的是国产芯片替代", rendered)
        self.assertIn("- **最强趋势密度**: 国产芯片替代 当前有12只活跃趋势股", rendered)
        self.assertIn("赚钱效应继续向国产芯片替代聚集", rendered)
        self.assertIn("国产芯片替代的趋势密度和承接同时走弱", rendered)
        self.assertNotIn("主攻线元件", rendered)
        self.assertNotIn("向元器件聚集", rendered)

    def test_render_market_research_snapshot_section_renders_lhb_capital_intent_tables(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "lhb_capital_intent"],
                "capital_intent_breakdown": {
                    "sector_fund_attitude": "半导体板块攻击资金确认",
                    "strength_feedback": "涨停5，高标4，成交占比+1.6pct",
                    "lhb_validation": "龙虎榜未验证主线",
                    "capital_consistency": "板块攻击成立，龙虎榜未验证",
                    "tomorrow_meaning": "先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决",
                },
                "lhb_capital_status": {
                    "capital_strength": "强",
                    "capital_intensity": "主线净买明显放大",
                    "capital_direction": "半导体核心",
                    "capital_intent": "资金继续加仓主线核心，不做支线扩散",
                    "style_shift": "从情绪接力转向趋势容量",
                    "event_attribute": "业绩预期叠加产业催化",
                },
                "capital_conclusion": {
                    "current_capital_state": "主线资金主动进攻",
                    "mainline_attitude": "继续确认半导体为周期主线",
                    "tomorrow_action_meaning": "明天只看半导体核心承接，不追非主线龙虎榜热票",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("#### 资金意图拆解", rendered)
        self.assertIn("| 板块攻击资金 | 强度反馈 | 龙虎榜验证 | 资金一致性 | 明日含义 |", rendered)
        self.assertIn("| 半导体板块攻击资金确认 | 涨停5，高标4，成交占比+1.6pct | 龙虎榜未验证主线 | 板块攻击成立，龙虎榜未验证 | 先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决 |", rendered)
        self.assertIn("#### 龙虎榜资金状态", rendered)
        self.assertIn("| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |", rendered)
        self.assertIn("| 强 | 主线净买明显放大 | 半导体核心 | 资金继续加仓主线核心，不做支线扩散 | 从情绪接力转向趋势容量 | 业绩预期叠加产业催化 |", rendered)
        self.assertIn("#### 资金结论", rendered)
        self.assertIn("| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |", rendered)
        self.assertIn("| 主线资金主动进攻 | 继续确认半导体为周期主线 | 明天只看半导体核心承接，不追非主线龙虎榜热票 |", rendered)

    def test_render_market_research_snapshot_section_does_not_dump_raw_lhb_ranking_when_capital_intent_exists(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["lhb_capital_intent"],
                "lhb_capital_status": {
                    "capital_strength": "偏强",
                    "capital_intensity": "榜单资金集中",
                    "capital_direction": "机器人",
                    "capital_intent": "试探新方向",
                    "style_shift": "高低切",
                    "event_attribute": "消息催化",
                },
                "lhb_rank_rows": [{"rank": 1, "stock": "原始榜一"}],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |", rendered)
        self.assertNotIn("原始榜一", rendered)
        self.assertNotIn("买入排名", rendered)

    def test_render_market_research_snapshot_section_can_render_only_enabled_nodes(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_focus", "state_summary"],
                "benchmark_change": 0.56,
                "turnover": 12834,
                "observation": {
                    "zt_count": 45,
                    "dt_count": 3,
                    "rise_fall_ratio_text": "1.42",
                    "leader_memory_count": 3,
                    "trusted_tracking_count": 2,
                },
                "competition_result": "主攻线 军工",
                "competition_evidence": "趋势密度和异常承接都在军工",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
                "state_flow_direction": "资金回流军工",
                "dialectical_decision": {
                    "stage_label": "主升试错段",
                    "stage_reason": "还没到普涨乱做",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("| 主线焦点 | 主攻线 军工 | 趋势密度和异常承接都在军工 |", rendered)
        self.assertIn("- **统一状态判断**: 修复；强分歧修复继续；资金回流军工", rendered)
        self.assertNotIn("| 盘面风险偏好 |", rendered)
        self.assertNotIn("### 🧠 辩证决策补充", rendered)

    def test_render_market_research_snapshot_section_full_mode(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "benchmark_change": 0.56,
                "turnover": 12834,
                "observation": {
                    "zt_count": 45,
                    "dt_count": 3,
                    "rise_fall_ratio_text": "1.42",
                    "leader_memory_count": 3,
                    "trusted_tracking_count": 2,
                    "densest_sector": "军工",
                    "densest_sector_trend_count": 5,
                },
                "competition_result": "主攻线 军工",
                "competition_evidence": "趋势密度和异常承接都在军工",
                "rotation_label": "主线轮动",
                "rotation_summary_text": "军工内部轮动扩散",
                "rotation_action": "优先主线内切换",
                "narrative_label": "叙事强化",
                "narrative_reason": "事件催化仍在",
                "narrative_action": "继续盯军工",
                "style_label": "趋势主导",
                "style_reason": "主线更强，边缘方向降级",
                "style_evidence_text": "军工趋势股密度最高",
                "abnormal_projection_label": "异常承接偏强",
                "abnormal_projection_reason": "承接样本明显多于失败样本",
                "follow_verdict_label": "允许跟随",
                "follow_verdict_reason": "环境未破坏",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
                "state_flow_direction": "资金回流军工",
                "dialectical_decision": {
                    "stage_label": "主升试错段",
                    "stage_reason": "还没到普涨乱做",
                    "index_profit_relation": "指数偏弱但赚钱效应修复",
                    "index_profit_reason": "主线承接好于指数",
                    "index_profit_action": "先区分核心锚、量化弹性和情绪后排。",
                    "focus_label": "主线集中",
                    "focus_action": "只做军工主线",
                    "candidate_focus": "军工核心与承接对象",
                    "candidate_action": "先盯唯一动作",
                    "falsification_conditions": ["军工高位大面积转弱"],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("| 盘面风险偏好 | 热点/趋势/异常 | 上证+0.56%", rendered)
        self.assertIn("| 主线焦点 | 主攻线 军工 | 趋势密度和异常承接都在军工 |", rendered)
        self.assertIn("### 🧠 辩证决策补充", rendered)
        self.assertIn("先区分核心锚、量化弹性和情绪后排", rendered)
        self.assertIn("什么情况下先不认这轮修复", rendered)

    def test_render_market_research_snapshot_empty_abnormal_projection_does_not_show_zero_zero_strength(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["abnormal_projection"],
                "abnormal_projection_label": "异常观察为空",
                "abnormal_projection_reason": "当前没有明确的异常承接样本，不能把孤立异动当成主线强化证据。",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 异常承接证据 | 未形成样本 | 当前没有明确的异常承接样本，不能把孤立异动当成主线强化证据。 |", rendered)
        self.assertNotIn("0强", rendered)
        self.assertNotIn("0弱", rendered)

    def test_render_step0_follow_section_compact(self):
        lines = render_step0_follow_section(
            {
                "compact": True,
                "step0_prediction_cn": "🟡 中性",
                "step0_reason": "环境未坏，但还需确认",
                "step0_action": "前30分钟只确认环境",
                "zt_count": 45,
                "dt_count": 3,
                "observation_summary": "风险偏好回暖",
                "densest_sector": "军工",
                "densest_sector_trend_count": 5,
                "resilient_abnormal_count": 4,
                "failed_abnormal_count": 1,
                "abnormal_projection_label": "异常承接偏强",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
            }
        )
        rendered = "\n".join(lines)
        self.assertIn("**明日裁决**: 🟡 中性", rendered)
        self.assertIn("**异常承接**: 4强 / 1弱；异常承接偏强", rendered)

    def test_render_step0_follow_section_uses_confirmed_attack_for_mainline_focus(self):
        lines = render_step0_follow_section(
            {
                "compact": False,
                "enabled_node_keys": ["table_header", "mainline_focus"],
                "densest_sector": "元器件",
                "densest_sector_trend_count": 6,
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线焦点 | 主攻线 人形机器人 | 人形机器人资金净流入靠前，涨停更集中 | 优先聚焦主线对象 |", rendered)
        self.assertNotIn("| 主线焦点 | 元器件 |", rendered)

    def test_render_step0_follow_section_can_render_only_enabled_nodes(self):
        lines = render_step0_follow_section(
            {
                "compact": False,
                "enabled_node_keys": ["verdict", "abnormal_projection", "conclusion"],
                "step0_prediction_cn": "🟡 中性",
                "step0_reason": "环境未坏，但还需确认",
                "step0_action": "前30分钟只确认环境",
                "zt_count": 45,
                "dt_count": 3,
                "observation_summary": "风险偏好回暖",
                "style_label": "趋势主导",
                "style_reason": "主线更强，边缘方向降级",
                "densest_sector": "军工",
                "densest_sector_trend_count": 5,
                "resilient_abnormal_count": 4,
                "failed_abnormal_count": 1,
                "abnormal_projection_label": "异常承接偏强",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
            }
        )
        rendered = "\n".join(lines)
        self.assertIn("**明日裁决**: 🟡 中性", rendered)
        self.assertIn("| 异常承接证据 | 4强 / 1弱 | 异常承接偏强 |", rendered)
        self.assertIn("> **Step 0 结论**: 环境未坏，但还需确认", rendered)
        self.assertNotIn("| 盘面风险偏好 |", rendered)
        self.assertNotIn("> **⚠️ 重要提醒**", rendered)

    def test_render_step0_follow_empty_abnormal_projection_does_not_show_zero_zero_strength(self):
        lines = render_step0_follow_section(
            {
                "compact": False,
                "enabled_node_keys": ["abnormal_projection"],
                "resilient_abnormal_count": 0,
                "failed_abnormal_count": 0,
                "abnormal_projection_label": "异常观察为空",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 异常承接证据 | 未形成样本 | 异常观察为空 |", rendered)
        self.assertNotIn("0强", rendered)
        self.assertNotIn("0弱", rendered)

    def test_render_step0_follow_reminder_respects_zero_participation(self):
        lines = render_step0_follow_section(
            {
                "compact": False,
                "enabled_node_keys": ["reminder"],
                "final_gate": {"final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想"},
                "position_decision": {"signal_grade": "0", "target_position_pct": 0},
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("明日不新增参与", rendered)
        self.assertIn("只观察风险是否钝化、主攻线承接，结果进入复盘和下一份日报判断", rendered)
        self.assertNotIn("分层参与", rendered)
        self.assertNotIn("买入后再用30分钟结构定止损", rendered)

    def test_render_gem_breathing_sections(self):
        step2_lines = render_gem_breathing_step2_section(
            {
                "display_mvp_mode": False,
                "gem_observation_stocks": [
                    {"name": "军工转债", "code": "123001", "sector": "军工", "tier": "A层", "abnormal_summary": _m("均线", "粘合"), "tomorrow_strength": 82}
                ],
                "filtered_out_gem_candidates": [],
            }
        )
        pool_lines = render_gem_breathing_pool_section(
            {
                "gem_observation_stocks": [
                    {"name": "军工转债", "code": "123001", "tier": "A层", "note": "蛇形走位", "watch_anchor_note": "先看右侧确认"}
                ],
                "filtered_out_gem_candidates": [],
            }
        )
        self.assertIn("主线侧翼弹性层", "\n".join(step2_lines))
        self.assertIn("#### Step 3.5 - 创业板20cm预启动观察池", "\n".join(pool_lines))
        self.assertIn("> **先看结论**：创业板20cm样本只保留观察权，不单列成独立战场。", "\n".join(pool_lines))
        self.assertIn("> **只看什么**：波动收敛、量价温和放大、右侧确认。", "\n".join(pool_lines))
        self.assertNotIn(_m("均线", "粘合"), "\n".join(step2_lines + pool_lines))
        self.assertNotIn("核心问题", "\n".join(pool_lines))
        self.assertIn("军工转债", "\n".join(pool_lines))


if __name__ == "__main__":
    unittest.main()
