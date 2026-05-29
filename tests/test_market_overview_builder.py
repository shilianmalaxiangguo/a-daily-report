import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_overview_builder import build_market_trend_sections_contract
from storage.database_service import DatabaseService


class MarketOverviewBuilderTest(unittest.TestCase):
    def test_build_market_trend_sections_contract_renders_market_base_tables(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 3200.12, "涨跌幅": 0.52},
                    "深证成指": {"点位": 10123.45, "涨跌幅": -0.21},
                    "创业板指": {"点位": 2123.45, "涨跌幅": -1.35},
                },
                "wind_a_alternative": {"点位": 5432.1, "涨跌幅": 0.31},
                "total_turnover": 16888.0,
                "zt_pool": [{"code": "000001"}] * 35,
                "dt_pool": [{"code": "000002"}] * 3,
                "market_stats": {"up_count": 3600, "down_count": 1600},
            },
            target_date="2026-04-22",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 二、市场基底", rendered)
        self.assertIn("### 1. 指数与市场底色", rendered)
        self.assertIn("| 指标 | 数值 | 涨跌幅 | 解读 |", rendered)
        self.assertIn("| 上证指数 | 3200.12 | +0.52% |", rendered)
        self.assertIn("| 两市成交额 | 16888.00亿 | - |", rendered)
        self.assertIn("| 涨停 / 跌停 | 35 / 3 | - |", rendered)
        self.assertIn("### 2. 市场状态结论", rendered)
        self.assertIn("| 项目 | 结论 |", rendered)
        self.assertIn("读法：市场情绪总状态先看盘面亏钱效应，再看局部热度；指数大跌、跌多涨少、跌停扩散时，单个指标高潮只写局部过热，不能单独把整体市场升级为高潮。", rendered)
        self.assertIn("| 市场情绪总状态 |", rendered)
        self.assertIn("| 当前盈亏比 |", rendered)

    def test_build_market_trend_sections_contract_can_render_only_enabled_nodes(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 3200.12, "涨跌幅": 0.52},
                    "深证成指": {"点位": 10123.45, "涨跌幅": -0.21},
                },
                "wind_a_alternative": {"点位": 5432.1, "涨跌幅": 0.31},
                "total_turnover": 16888.0,
                "zt_pool": [{"code": "000001"}] * 35,
                "dt_pool": [{"code": "000002"}] * 3,
                "market_stats": {"up_count": 3600, "down_count": 1600},
            },
            target_date="2026-04-22",
            enabled_node_keys=["header", "indices", "sentiment"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 二、市场基底", rendered)
        self.assertIn("### 1. 指数与市场底色", rendered)
        self.assertNotIn("### 2. 市场状态结论", rendered)

    def test_build_market_trend_sections_contract_renders_indices_volume_and_sentiment(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 3200.12, "涨跌幅": 0.52},
                    "深证成指": {"点位": 10123.45, "涨跌幅": -0.21},
                },
                "wind_a_alternative": {"点位": 5432.1, "涨跌幅": 0.31},
                "total_turnover": 16888.0,
                "zt_pool": [{"code": "000001"}] * 35,
                "dt_pool": [{"code": "000002"}] * 3,
                "market_stats": {"up_count": 3600, "down_count": 1600},
            },
            target_date="2026-04-22",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 二、市场基底", rendered)
        self.assertIn("| 上证指数 | 3200.12 | +0.52% | 温和修复 |", rendered)
        self.assertIn("| 中证全指 | 5432.10 | +0.31% | 温和修复 |", rendered)
        self.assertIn("| 两市成交额 | 16888.00亿 | - | 量能不差，但赚钱效应不足 |", rendered)
        self.assertIn("| 涨停 / 跌停 | 35 / 3 | - | 活跃度还在，但亏钱端不轻 |", rendered)
        self.assertIn("| 涨跌比 | 3600 / 1600 | - | 多头仍占优 |", rendered)
        self.assertIn("### 2. 市场状态结论", rendered)
        self.assertTrue(any(log["step"] == "render.market_trend_sections" for log in result["module_logs"]))

    def test_build_market_trend_sections_contract_labels_small_deep_v_as_intraday_repair(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {
                        "点位": 4098.64,
                        "涨跌幅": 0.12,
                        "open": 4080.30,
                        "high": 4110.78,
                        "low": 4055.83,
                        "close": 4098.64,
                    },
                },
                "total_turnover": 29873.26,
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 3018, "down_count": 2365},
            },
            target_date="2026-05-28",
            enabled_node_keys=["header", "indices"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 上证指数 | 4098.64 | +0.12% | 探底回升 |", rendered)
        self.assertNotIn("强势上涨", rendered)

    def test_build_market_trend_sections_contract_keeps_high_turnover_weak_breadth_wording_consistent(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 4131.53, "涨跌幅": -0.09},
                    "深证成指": {"点位": 15530.23, "涨跌幅": -0.20},
                    "创业板指": {"点位": 3914.88, "涨跌幅": -0.36},
                },
                "wind_a_alternative": {"点位": 6477.21, "涨跌幅": -0.06},
                "total_turnover": 29170.74,
                "zt_pool": [{"code": "000001"}] * 101,
                "dt_pool": [{"code": "000002"}] * 53,
                "market_stats": {"up_count": 2375, "down_count": 3003},
            },
            target_date="2026-05-18",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 两市成交额 | 29170.74亿 | - | 量能充沛，但赚钱效应不足 |", rendered)

    def test_build_market_trend_sections_contract_renders_turnover_history_comparison(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {"上证指数": {"点位": 4131.53, "涨跌幅": -2.04}},
                "total_turnover": 35072.8,
                "market_turnover_history": [
                    {"date": "2026-05-19", "turnover": 29089.77},
                    {"date": "2026-05-20", "turnover": 29764.59},
                ],
                "zt_pool": [{"code": "000001"}] * 35,
                "dt_pool": [{"code": "000002"}] * 65,
                "market_stats": {"up_count": 800, "down_count": 4600},
            },
            target_date="2026-05-21",
            enabled_node_keys=["indices"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn(
            "| 两市成交额 | 35072.80亿 | +17.83% | 成交额继续回升；量能充沛，但赚钱效应不足 |",
            rendered,
        )
        self.assertNotIn("### 2. 市场状态结论", rendered)
        self.assertEqual(result["context"]["two_market_turnover_comparison"]["state"], "rising")
        self.assertAlmostEqual(
            result["node_outputs"]["indices"]["two_market_turnover_comparison"]["previous_change_pct"],
            17.83,
            places=2,
        )

    def test_build_market_trend_sections_contract_renders_top50_turnover_share_regime(self):
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 123.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2600, "down_count": 2200},
            },
            target_date="2026-05-18",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| Top50成交额占比 | 20.50% | 资金活跃期 | Top50成交额占比超过20%，雨量变大，资金处于活跃期。 |", rendered)
        self.assertIn("| 头部成交状态 | 资金活跃期 |", rendered)

    def test_build_market_trend_sections_contract_renders_top20_capacity_summary(self):
        top20_amounts = [
            372.54,
            301.25,
            293.88,
            275.43,
            266.33,
            244.33,
            240.28,
            224.99,
            210.49,
            201.05,
            186.17,
            184.56,
            178.98,
            169.43,
            166.20,
            159.80,
            158.36,
            154.79,
            153.43,
            149.80,
        ]
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 32269.52,
                "turnover_rank": [{"turnover": amount} for amount in top20_amounts]
                + [{"turnover": 90.0} for _ in range(30)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2600, "down_count": 2200},
            },
            target_date="2026-05-25",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| Top20成交容量 | 19/20只150亿级 | 高容量聚焦 |", rendered)
        self.assertIn("Top20第20名149.80亿", rendered)
        self.assertIn("作为Top50后的补充观察，只说明资金选择方向，不单独给参与资格。", rendered)
        self.assertIn("| Top20成交容量 | 高容量聚焦 |", rendered)

    def test_build_market_trend_sections_contract_renders_top50_turnover_share_trend_rows(self):
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 123.0} for _ in range(50)],
                "top50_turnover_share_series": {
                    "rows": [
                        {
                            "trade_date": "2026-05-15",
                            "top_amount_yi": 5340.0,
                            "market_amount_yi": 30000.0,
                            "share_pct": 17.8,
                        },
                        {
                            "trade_date": "2026-05-18",
                            "top_amount_yi": 6150.0,
                            "market_amount_yi": 30000.0,
                            "share_pct": 20.5,
                        },
                    ]
                },
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2600, "down_count": 2200},
            },
            target_date="2026-05-18",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |", rendered)
        self.assertIn("| 2026-05-15 | 17.80% | 冰点 | 待累计 | 5340.00亿 | 30000.00亿 |", rendered)
        self.assertIn("| 2026-05-18 | 20.50% | 资金活跃期 | +2.70pct | 6150.00亿 | 30000.00亿 |", rendered)
        self.assertLess(rendered.index("2026-05-18"), rendered.index("2026-05-15"))

    def test_build_market_trend_sections_contract_renders_top50_recent_25_rows_through_target_date(self):
        start = date(2026, 4, 20)
        source_rows = []
        for offset in range(25):
            trade_date = (start + timedelta(days=offset)).isoformat()
            source_rows.append(
                {
                    "trade_date": trade_date,
                    "top_amount_yi": 1000.0 + offset,
                    "market_amount_yi": 10000.0,
                    "share_pct": 10.0 + offset / 10,
                }
            )

        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 123.0} for _ in range(50)],
                "top50_turnover_share_series": {"rows": source_rows},
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2600, "down_count": 2200},
            },
            target_date="2026-05-20",
        )

        lines = result["lines"]
        table_start = lines.index("| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |")
        table_rows = []
        for line in lines[table_start + 2:]:
            if not line.startswith("|"):
                break
            table_rows.append(line)

        self.assertEqual(len(table_rows), 25)
        self.assertNotIn("| 2026-04-20 |", "\n".join(table_rows))
        self.assertIn("| 2026-05-20 | 20.50% | 资金活跃期 |", "\n".join(table_rows))
        self.assertTrue(table_rows[0].startswith("| 2026-05-20 |"))
        self.assertIn(
            "> 近25个交易日Top50成交额占比趋势：当前20.50%，近5日+8.40pct，区间10.10%-20.50%，头部成交集中度抬升。",
            "\n".join(result["lines"]),
        )

    def test_build_market_trend_sections_contract_does_not_fabricate_top50_trend_without_series(self):
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 29170.74,
                "turnover_rank": [{"turnover": 114.3714} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
            },
            target_date="2026-05-18",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| Top50成交额占比 | 19.60% | 震荡 |", rendered)
        self.assertNotIn("| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |", rendered)

    def test_build_market_trend_sections_contract_maps_top50_share_thresholds(self):
        cold = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 105.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 1200, "down_count": 3600},
            },
            target_date="2026-05-18",
        )
        oscillating = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 114.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
            },
            target_date="2026-05-18",
        )

        self.assertIn("| Top50成交额占比 | 17.50% | 冰点 |", "\n".join(cold["lines"]))
        self.assertIn("| Top50成交额占比 | 19.00% | 震荡 |", "\n".join(oscillating["lines"]))

    def test_build_market_trend_sections_contract_marks_top50_share_missing_as_pending(self):
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
            },
            target_date="2026-05-18",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| Top50成交额占比 | 待累计 | 待累计 | 缺少成交额前50明细，暂不判断头部成交集中度。 |", rendered)

    def test_build_market_trend_sections_contract_unifies_conflicting_sentiment_signals(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 4077.28, "涨跌幅": -2.04},
                },
                "wind_a_alternative": {"点位": 6368.44, "涨跌幅": -2.40},
                "total_turnover": 35072.8,
                "turnover_rank": [{"turnover": 135.776} for _ in range(50)],
                "zt_pool": [{"code": "000001"}] * 35,
                "dt_pool": [{"code": "000002"}] * 65,
                "market_stats": {"up_count": 695, "down_count": 4773},
                "new_high_feedback": {
                    "available": True,
                    "all_a_share_pct": 11.43,
                    "new_high_count": 629,
                    "trend_rows": [],
                    "sector_distribution": [],
                    "top_stocks": [],
                },
            },
            target_date="2026-05-21",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 市场情绪总状态 | 震荡偏风险 |", rendered)
        self.assertIn("| 局部热度处理 | 创新高高潮，但指数大跌、跌多涨少、跌停扩散，只写局部过热，不把整体市场升级为高潮。 |", rendered)
        self.assertIn("| 明日总体含义 | 趋势扩散偏热，但指数和涨跌家数破坏，先防降温，等待止跌和核心承接。 |", rendered)

    def test_build_market_trend_sections_contract_renders_price_band_style_series(self):
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 114.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
                "price_band_style_series": {
                    "available": True,
                    "summary": "近3个交易日价格带风格：最新差值 -1.38pct，当前为震荡；百元股累计 -3.26%，低价股累计 -1.98%。价格带只作风格背景，不单独说明明日走势，明日仍看成交额与核心承接。",
                    "rows": [
                        {
                            "trade_date": "2026-05-18",
                            "high_price_pct": 3.0,
                            "low_price_pct": 0.0,
                            "spread_pct": 3.0,
                            "style_label": "高潮",
                        },
                        {
                            "trade_date": "2026-05-19",
                            "high_price_pct": -2.0,
                            "low_price_pct": 0.9,
                            "spread_pct": -2.9,
                            "style_label": "冰点",
                        },
                        {
                            "trade_date": "2026-05-21",
                            "high_price_pct": -4.2563,
                            "low_price_pct": -2.8785,
                            "spread_pct": -1.3778,
                            "style_label": "震荡",
                        },
                    ],
                },
            },
            target_date="2026-05-21",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("### 3. 价格带风格", rendered)
        self.assertIn(
            "> 近3个交易日价格带风格：最新差值 -1.38pct，当前为震荡；百元股累计 -3.26%，低价股累计 -1.98%。价格带只作风格背景，不单独说明明日走势，明日仍看成交额与核心承接。",
            rendered,
        )
        self.assertIn(
            "> 读法：这里先看 `百元股涨跌幅 - 低价股涨跌幅` 的相对风格，再看两组自身涨跌的绝对状态。差值越高，说明资金越偏高价核心；差值越低，说明高价核心降温、低价股相对抗跌。-2pct 以下看冰点，-2pct 到 +2pct 看震荡，+2pct 以上看高潮。",
            rendered,
        )
        self.assertIn("| 日期 | 百元股涨跌幅 | 低价股涨跌幅 | 当日差值 | 相对风格 | 绝对状态 |", rendered)
        self.assertIn("| 2026-05-21 | -4.26% | -2.88% | -1.38pct | 震荡 | 同步回落 |", rendered)

    def test_build_market_trend_sections_contract_renders_new_high_feedback(self):
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 114.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
                "new_high_feedback": {
                    "available": True,
                    "new_high_count": 126,
                    "all_a_share_pct": 2.52,
                    "summary": "今日非ST非新股非次新阶段新高 126 只，占全A约 2.52%，主要集中在半导体、机器人。",
                    "sector_distribution": [
                        {
                            "sector": "半导体",
                            "new_high_count": 35,
                            "share_pct": 27.78,
                            "representative_stocks": ["趋势一号", "趋势二号"],
                        },
                        {
                            "sector": "机器人",
                            "new_high_count": 21,
                            "share_pct": 16.67,
                            "representative_stocks": ["机器一号"],
                        },
                    ],
                    "trend_rows": [
                        {
                            "trade_date": "2026-05-15",
                            "new_high_count": 100,
                            "all_a_share_pct": 2.0,
                            "change_text": "待累计",
                            "leading_sectors": "机器人",
                        },
                        {
                            "trade_date": "2026-05-18",
                            "new_high_count": 126,
                            "all_a_share_pct": 2.52,
                            "change_text": "+26",
                            "leading_sectors": "半导体、机器人",
                        },
                    ],
                    "top_stocks": [
                        {"name": "趋势一号", "code": "000001", "sector": "半导体", "pct_chg": 5.2, "amount_yi": 25.0, "topdays": 260}
                    ],
                },
            },
            target_date="2026-05-18",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("### 4. 创新高趋势反馈", rendered)
        self.assertIn("今日非ST非新股非次新阶段新高 126 只，占全A约 2.52%", rendered)
        self.assertIn(
            "> 用途：创新高看的是趋势赚钱效应有没有扩散。全A占比越高，说明越多股票突破过去约250个交易日高点；但超过5%后若同时放量，往往偏热，次日更容易降温。",
            rendered,
        )
        self.assertIn(
            "> 读法：全A占比低于2%看冰点，2%到5%看震荡，5%以上看高潮。这个指标只作趋势扩散背景，明日仍要结合成交额、指数位置、涨跌家数和核心承接。",
            rendered,
        )
        self.assertIn(
            "> 当前解读：全A占比2.52%，处于震荡，说明趋势扩散存在但还不是极端热度。",
            rendered,
        )
        self.assertIn("| 日期 | 新高数 | 全A占比 | 状态 | 较前日 | 主导板块 |", rendered)
        self.assertIn("| 2026-05-18 | 126 | 2.52% | 震荡 | +26 | 半导体、机器人 |", rendered)
        self.assertIn("| 半导体 | 35 | 27.78% | 趋势一号、趋势二号 |", rendered)
        self.assertIn("| 排名 | 股票 | 代码 | 所属板块 | 涨跌幅 | 成交额 | 新高跨度 |", rendered)
        self.assertNotIn("新高周期", rendered)
        self.assertIn("| 1 | 趋势一号 | 000001 | 半导体 | +5.20% | 25.00亿 | 260日新高 |", rendered)

    def test_build_market_trend_sections_contract_renders_margin_pressure(self):
        margin_rows = []
        for index in range(6):
            day = date(2026, 5, 16) + timedelta(days=index)
            margin_rows.append(
                {
                    "trade_date": day.isoformat(),
                    "margin_balance_yi": 28000 + index * 100,
                    "market_turnover_yi": 32000 - index * 500,
                    "margin_turnover_ratio_pct": 87.50 + index * 2.50,
                    "pressure_diff_pct": -12.50 + index * 2.50,
                    "pressure_label": "舒缓" if index < 2 else "中性" if index < 5 else "高压",
                    "change_text": "待累计" if index == 0 else "+2.50pct",
                }
            )
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 114.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
                "margin_pressure": {
                    "available": True,
                    "summary": "近250日融资承接压力：当前融资承接比 105.00%，250日分位 91.20%，处于高压。",
                    "usage_note": "融资余额上升、成交额下降时，市场承接压力加重。",
                    "latest_pressure_label": "高压",
                    "calibration": {"latest_percentile": 91.2},
                    "rows": margin_rows,
                },
            },
            target_date="2026-05-21",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("### 5. 融资承接与成交量", rendered)
        self.assertIn("当前融资承接比 105.00%，250日分位 91.20%", rendered)
        self.assertIn("| 观察项 | 当前 | 近5日变化 | 近20日变化 | 解读 |", rendered)
        self.assertIn("| 250日关系校验 | 弱相关 | - | - | 不单独给方向，只作承接背景 |", rendered)
        self.assertIn("近10日融资承接表", rendered)
        self.assertIn("| 2026-05-21 | 28500.00亿 | 29500.00亿 | 100.00% | 高压 |", rendered)
        self.assertIn("| 2026-05-16 |", rendered)
        self.assertLess(rendered.index("2026-05-21"), rendered.index("2026-05-20"))
        self.assertIn("| 融资承接压力 | 高压 |", rendered)

    def test_build_market_trend_sections_contract_loads_recent_margin_pressure_from_fact_db(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "daily.db"
            service = DatabaseService.sqlite_d1_compatible(db_path)
            for index in range(12):
                day = date(2026, 5, 10) + timedelta(days=index)
                market_turnover = 30000.0 + index * 100.0
                margin_balance = market_turnover * (0.86 + index * 0.004)
                service.upsert_margin_pressure_daily(
                    {
                        "trade_date": day.isoformat(),
                        "margin_balance_yi": margin_balance,
                        "market_turnover_yi": market_turnover,
                        "exchange_count": 3,
                        "source_policy": "test.margin+test.turnover",
                    }
                )
            data = {
                "total_turnover": 29033.20,
                "turnover_rank": [{"turnover": 114.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
                "margin_pressure": {
                    "available": False,
                    "message": "融资承接压力数据为空，暂不判断市场杠杆承接。",
                    "rows": [],
                },
            }

            result = build_market_trend_sections_contract(
                data=data,
                target_date="2026-05-22",
                daily_fact_db_path=db_path,
            )

        rendered = "\n".join(result["lines"])
        self.assertTrue(data["margin_pressure"]["available"])
        self.assertEqual(data["margin_pressure"]["latest_data_date"], "2026-05-21")
        self.assertIn("截至2026-05-21", rendered)
        self.assertIn("较报告日2026-05-22滞后一交易日", rendered)
        self.assertIn("| 项目 | 结论 | 依据 |", rendered)
        self.assertIn("| 融资承接压力 | 中性 | 截至2026-05-21，融资承接比 90.40%；较报告日2026-05-22滞后一交易日。 |", rendered)
        self.assertIn("**近10日融资承接表**", rendered)
        self.assertIn("| 2026-05-21 |", rendered)
        self.assertIn("| 2026-05-12 |", rendered)
        self.assertNotIn("| 2026-05-11 |", rendered)
        self.assertLess(rendered.index("2026-05-21"), rendered.index("2026-05-20"))

    def test_build_market_trend_sections_contract_explains_empty_new_high_provider(self):
        result = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 114.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
                "new_high_feedback": {
                    "available": False,
                    "status": "upstream_empty",
                    "source": "tushare.stk_factor_pro.topdays",
                    "message": "Tushare stk_factor_pro 当前未返回 2026-05-19 技术因子，暂不判断阶段新高反馈。",
                },
            },
            target_date="2026-05-19",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("Tushare stk_factor_pro 当前未返回 2026-05-19 技术因子", rendered)
        self.assertNotIn("缺少 Tushare stk_factor_pro 技术因子", rendered)


if __name__ == "__main__":
    unittest.main()
