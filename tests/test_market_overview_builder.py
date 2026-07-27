import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_overview_builder import build_market_trend_sections_contract
from report.market_overview_nodes import resolve_unified_market_sentiment


class _MarginPressureFactStore:
    def __init__(self):
        self.rows = []

    def upsert_margin_pressure_daily(self, row):
        self.rows.append(dict(row or {}))
        return 1

    def query_margin_pressure_series(self, end_date, *, window_days=250):
        rows = [
            dict(row)
            for row in self.rows
            if str(row.get("trade_date") or "") <= str(end_date or "")
        ]
        rows.sort(key=lambda row: str(row.get("trade_date") or ""))
        return {"rows": rows[-int(window_days or 250) :]}


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
                "csi500_index": {"点位": 6262.0, "涨跌幅": 0.90},
                "csi1000_index": {"点位": 6123.4, "涨跌幅": 1.10},
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
        self.assertIn("| 中证500 | 6262.00 | +0.90% |", rendered)
        self.assertIn("| 中证1000 | 6123.40 | +1.10% |", rendered)
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
                "csi500_index": {"price": 0, "change_pct": 0},
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
        self.assertIn("| 中证500 | 待补 | 待补 | 待补 |", rendered)
        self.assertIn("| 两市成交额 | 16888.00亿 | - | 量能不差，但跌停端压力仍高 |", rendered)
        self.assertIn("| 涨停 / 跌停 | 35 / 3 | - | 活跃度还在，但亏钱端不轻 |", rendered)
        self.assertIn("| 涨跌比 | 3600 / 1600 | - | 多头仍占优 |", rendered)
        self.assertIn("### 2. 市场状态结论", rendered)
        self.assertTrue(any(log["step"] == "render.market_trend_sections" for log in result["module_logs"]))

    def test_build_market_trend_sections_contract_renders_csi500_missing_change_as_pending(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 3200.12, "涨跌幅": 0.52},
                    "中证500": {"点位": 6262.0},
                },
                "wind_a_alternative": {"点位": 5432.1},
                "csi500_index": {"price": 6262.0},
                "csi1000_index": {"price": 6123.4},
                "total_turnover": 16888.0,
                "zt_pool": [{"code": "000001"}] * 35,
                "dt_pool": [{"code": "000002"}] * 3,
                "market_stats": {"up_count": 3600, "down_count": 1600},
            },
            target_date="2026-04-22",
            enabled_node_keys=["indices"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 中证500 | 待补 | 待补 | 待补 |", rendered)
        self.assertIn("| 中证全指 | 待补 | 待补 | 待补 |", rendered)
        self.assertIn("| 中证1000 | 待补 | 待补 | 待补 |", rendered)
        self.assertNotIn("中证500 | 6262.00 | +0.00%", rendered)

    def test_unified_market_sentiment_ignores_invalid_csi500_index_risk(self):
        base_data = {
            "indices": {"上证指数": {"点位": 3200.12, "涨跌幅": 0.52}},
            "total_turnover": 16888.0,
            "zt_pool": [],
            "dt_pool": [],
            "market_stats": {"up_count": 2600, "down_count": 1800},
        }

        invalid = resolve_unified_market_sentiment(
            {**base_data, "csi500_index": {"price": 0, "change_pct": -2.0}},
            target_date="2026-04-22",
        )
        valid = resolve_unified_market_sentiment(
            {**base_data, "csi500_index": {"price": 6262.0, "change_pct": -2.0}},
            target_date="2026-04-22",
        )

        self.assertEqual(invalid["state"], "震荡")
        self.assertEqual(valid["state"], "冰点")

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
        active_boundary = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 150.0} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
            },
            target_date="2026-05-18",
        )
        rounded_boundary = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 150.0024} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
            },
            target_date="2026-05-18",
        )
        extreme = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 150.06} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
            },
            target_date="2026-05-18",
        )

        self.assertIn("| Top50成交额占比 | 17.50% | 冰点 |", "\n".join(cold["lines"]))
        self.assertIn("| Top50成交额占比 | 19.00% | 震荡 |", "\n".join(oscillating["lines"]))
        self.assertIn("| Top50成交额占比 | 25.00% | 资金活跃期 |", "\n".join(active_boundary["lines"]))
        self.assertIn("| Top50成交额占比 | 25.00% | 资金活跃期 |", "\n".join(rounded_boundary["lines"]))
        self.assertIn(
            "| Top50成交额占比 | 25.01% | 极致 | Top50成交额占比超过25%，头部成交集中度进入极致区。 |",
            "\n".join(extreme["lines"]),
        )

    def test_unified_market_sentiment_keeps_extreme_top50_share_as_hot_evidence(self):
        result = resolve_unified_market_sentiment(
            {
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 150.06} for _ in range(50)],
                "new_high_feedback": {"available": True, "all_a_share_pct": 5.1},
                "market_stats": {"up_count": 2600, "down_count": 2200},
                "zt_pool": [],
                "dt_pool": [],
            },
            target_date="2026-05-18",
        )

        self.assertEqual(result["state"], "高潮")
        self.assertIn("资金聚焦和趋势扩散同步走热", result["local_heat"])

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
        self.assertIn("| 局部热度处理 | 创新高达到极致扩散，但指数大跌、跌多涨少、跌停扩散，只写局部过热，不把整体市场升级为高潮。 |", rendered)
        self.assertIn("| 明日总体含义 | 创新高达到极致扩散，但指数和涨跌家数破坏，先防降温，等待止跌和核心承接。 |", rendered)

    def test_unified_market_sentiment_does_not_call_low_new_high_extreme_when_margin_is_hot(self):
        result = resolve_unified_market_sentiment(
            {
                "indices": {"上证指数": {"涨跌幅": -2.04}},
                "market_stats": {"up_count": 695, "down_count": 4773},
                "turnover_rank": [],
                "dt_pool": [{"code": "000001"}] * 65,
                "new_high_feedback": {
                    "available": True,
                    "new_high_count": 9,
                    "all_a_share_pct": 0.18,
                },
                "margin_pressure": {
                    "available": True,
                    "latest_pressure_label": "高压",
                    "rows": [],
                },
            },
            target_date="2026-07-17",
        )

        self.assertIn("融资承接压力高", result["local_heat"])
        self.assertIn("融资承接压力高", result["meaning"])
        self.assertNotIn("极致扩散", result["meaning"])

    def test_build_market_trend_sections_contract_separates_0609_local_style_from_overall_temperature(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 4010.03, "涨跌幅": 1.28},
                    "深证成指": {"点位": 15268.71, "涨跌幅": 3.02},
                    "创业板指": {"点位": 3961.75, "涨跌幅": 3.93},
                },
                "wind_a_alternative": {"点位": 6254.74, "涨跌幅": 2.21},
                "csi1000_index": {"点位": 8318.70, "涨跌幅": 2.94},
                "total_turnover": 26667.33,
                "turnover_rank": [{"turnover": 116.58} for _ in range(50)],
                "zt_pool": [{"code": "000001"}] * 130,
                "dt_pool": [{"code": "000002"}] * 9,
                "market_stats": {"up_count": 3322, "down_count": 2049},
                "new_high_feedback": {
                    "available": True,
                    "new_high_count": 82,
                    "all_a_share_pct": 1.64,
                    "summary": "本地事实库记录显示阶段新高 82 只，占全A约 1.64%，主要集中在 元器件、化工原料、专用机械。",
                    "trend_rows": [
                        {
                            "trade_date": "2026-06-09",
                            "new_high_count": 82,
                            "all_a_share_pct": 1.64,
                            "change_text": "-78",
                            "leading_sectors": "元器件、化工原料、专用机械",
                        }
                    ],
                    "sector_distribution": [],
                    "top_stocks": [],
                },
                "price_band_style_series": {
                    "available": True,
                    "rows": [
                        {
                            "trade_date": "2026-06-09",
                            "high_price_pct": 1.96,
                            "low_price_pct": -0.72,
                            "spread_pct": 2.68,
                            "style_label": "高潮",
                            "absolute_label": "高价占优",
                        }
                    ],
                },
            },
            target_date="2026-06-09",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 市场情绪总状态 | 震荡 |", rendered)
        self.assertIn("| 2026-06-09 | +1.96% | -0.72% | +2.68pct | 高价相对占优 | 高价占优 |", rendered)
        self.assertIn("> 当前解读：全A占比1.64%，扩散偏冷，说明趋势赚钱效应扩散不足；同一低值仍要结合变化方向判断。", rendered)
        self.assertIn("| 2026-06-09 | 82 | 1.64% | 扩散偏冷 | -78 | 元器件、化工原料、专用机械 |", rendered)
        self.assertNotIn("最新差值 +2.68pct，当前为高潮", rendered)
        self.assertNotIn("全A占比1.64%，处于冰点", rendered)

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
            "> 近3个交易日价格带风格：最新差值 -1.38pct，相对风格价格带均衡；绝对状态同步回落；百元股累计 -3.26%，低价股累计 -1.98%。价格带只作局部风格背景，不单独说明整体市场温度，明日仍看成交额与核心承接。",
            rendered,
        )
        self.assertIn(
            "> 读法：这里先看 `百元股涨跌幅 - 低价股涨跌幅` 的相对风格，再看两组自身涨跌的绝对状态。差值越高，说明资金越偏高价核心；差值越低，说明高价核心降温、低价股相对抗跌。价格带只说明高价与低价的相对偏好，不单独代表整体市场冰点或高潮。",
            rendered,
        )
        self.assertIn("| 日期 | 百元股涨跌幅 | 低价股涨跌幅 | 当日差值 | 相对风格 | 绝对状态 |", rendered)
        self.assertIn("| 2026-05-21 | -4.26% | -2.88% | -1.38pct | 价格带均衡 | 同步回落 |", rendered)

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
            "> 用途：创新高看的是趋势赚钱效应有没有扩散。绝对水位说明覆盖广度，变化方向说明扩散是在增强、收缩还是低位修复；5%及以上若同时放量，往往偏热，次日更容易降温。",
            rendered,
        )
        self.assertIn(
            "> 读法：5%及以上为极致扩散，2%到5%为有效扩散，1%到2%为扩散偏冷，0.2%到1%为极低扩散；低于0.2%或新高数低于10只为扩散断层。绝对水位不是买卖动作，同一低值还要结合变化方向、板块成群度、核心板块同步性和来源质量。",
            rendered,
        )
        self.assertIn(
            "> 当前解读：全A占比2.52%，有效扩散，说明趋势赚钱效应已有可用宽度，但仍需观察方向能否持续。",
            rendered,
        )
        self.assertIn("> 结构判断：扩散震荡：当前126只、全A占比2.52%，绝对水位为有效扩散", rendered)
        self.assertIn("> 风险含义：当前尚未确认快速收缩", rendered)
        self.assertIn("> 主要反证：长期下跌后的低位可能对应卖压衰竭", rendered)
        self.assertIn("> 下一窗口：下一窗口复核创新高是否连续回升", rendered)
        self.assertLess(rendered.index("> 当前解读："), rendered.index("> 结构判断："))
        self.assertLess(rendered.index("> 下一窗口："), rendered.index("| 日期 | 新高数 |"))
        self.assertIn("| 日期 | 新高数 | 全A占比 | 趋势信号 | 较前日 | 板块分布前列 |", rendered)
        self.assertIn("| 2026-05-18 | 126 | 2.52% | 有效扩散 | +26 | 半导体、机器人 |", rendered)
        self.assertIn("| 半导体 | 35 | 27.78% | 趋势一号、趋势二号 |", rendered)
        self.assertIn("| 排名 | 股票 | 代码 | 所属板块 | 涨跌幅 | 成交额 | 新高跨度 |", rendered)
        self.assertNotIn("新高周期", rendered)
        self.assertIn("| 1 | 趋势一号 | 000001 | 半导体 | +5.20% | 25.00亿 | 260日新高 |", rendered)
        signal = result["node_outputs"]["new_high"]["new_high_structure_signal"]
        self.assertEqual(signal["state"], "扩散震荡")
        self.assertFalse(signal["history_comparable"])

    def test_build_market_trend_sections_contract_uses_five_absolute_breadth_levels(self):
        rows = [
            ("2026-05-01", 9, 0.18, "扩散断层"),
            ("2026-05-02", 10, 0.20, "极低扩散"),
            ("2026-05-03", 50, 1.00, "扩散偏冷"),
            ("2026-05-04", 100, 2.00, "有效扩散"),
            ("2026-05-05", 250, 5.00, "极致扩散"),
        ]
        result = build_market_trend_sections_contract(
            data={
                "new_high_feedback": {
                    "available": True,
                    "new_high_count": 250,
                    "all_a_share_pct": 5.0,
                    "summary": "创新高绝对水位边界样本。",
                    "trend_rows": [
                        {
                            "trade_date": trade_date,
                            "new_high_count": count,
                            "all_a_share_pct": pct,
                            "change_text": "待累计",
                            "leading_sectors": "待补充板块",
                        }
                        for trade_date, count, pct, _label in rows
                    ],
                    "sector_distribution": [],
                    "top_stocks": [],
                }
            },
            target_date="2026-05-05",
            enabled_node_keys=["new_high"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("> 当前解读：全A占比5.00%，极致扩散", rendered)
        for trade_date, count, pct, label in rows:
            self.assertIn(f"| {trade_date} | {count} | {pct:.2f}% | {label} |", rendered)

    def test_build_market_trend_sections_contract_marks_mixed_source_single_digit_as_structure_only(self):
        sectors = [
            {"sector": sector, "new_high_count": 1, "share_pct": 16.67}
            for sector in ["半导体", "水运", "纺织", "医药", "银行", "机械"]
        ]
        result = build_market_trend_sections_contract(
            data={
                "new_high_feedback": {
                    "available": True,
                    "new_high_count": 6,
                    "all_a_share_pct": 0.12,
                    "summary": "阶段新高6只，占全A约0.12%。",
                    "trend_rows": [
                        {
                            "trade_date": "2026-07-10",
                            "source": "tushare",
                            "new_high_count": 18,
                            "all_a_share_pct": 0.36,
                            "change_text": "-4",
                            "leading_sectors": "半导体、IT设备、元器件",
                        },
                        {
                            "trade_date": "2026-07-13",
                            "source": "akshare",
                            "new_high_count": 6,
                            "all_a_share_pct": 0.12,
                            "change_text": "-12",
                            "leading_sectors": "半导体、水运、纺织",
                            "sector_distribution": sectors,
                        },
                    ],
                    "sector_distribution": sectors,
                    "top_stocks": [],
                },
            },
            target_date="2026-07-13",
            enabled_node_keys=["new_high"],
        )

        rendered = "\n".join(result["lines"])
        structure_line = next(line for line in result["lines"] if line.startswith("> 结构判断："))
        self.assertIn("扩散断层预警", structure_line)
        self.assertIn("首次进入个位数", structure_line)
        self.assertIn("呈板块碎片化", structure_line)
        self.assertIn("跨日速度和峰值保留率只作结构观察", structure_line)
        self.assertIn("事实不足", structure_line)
        self.assertNotIn("-66.67%", structure_line)
        self.assertNotIn("半导体主导", structure_line)
        self.assertNotIn("主导板块", rendered)
        self.assertIn("不是机械卖出条件", rendered)

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
            db_path = Path(tmp) / "fact-store"
            service = _MarginPressureFactStore()
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

            with patch("report.market_overview_nodes.DatabaseService.fact_store_from_environment", return_value=service):
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
