import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.report_sections import (
    build_advanced_activity_report_sections,
    build_market_activity_report_sections,
)


class MarketActivityDomainReportSectionsTest(unittest.TestCase):
    def test_build_market_activity_report_sections_can_render_only_enabled_nodes(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [{"name": "军工一号", "code": "000001", "rate": 230000, "concepts": ["军工"], "popularity_tag": "龙头"}],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [{"name": "军工一号", "code": "sz000001", "turnover": 123.4}],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [{"name": "消费", "zljlr": -9.8, "zdf": -1.8}],
                },
                "lhb_net_buy_top10": [{"rank": 1, "code": "000001", "net_buy_amount_yi": 3.2, "name": "军工一号", "zt_status": "正常", "sector": "军工"}],
                "lhb_net_sell_top10": [{"rank": 1, "code": "000002", "net_buy_amount_yi": -2.1, "name": "消费一号", "zt_status": "正常", "sector": "消费"}],
                "lianban_data": [],
            },
            target_date="2026-04-22",
            stock_full_info={
                "000001": {"change_pct": 5.2, "high": 12.3, "low": 11.1, "open": 11.2, "close": 12.0, "name": "军工一号"},
                "000002": {"change_pct": -3.1, "high": 8.5, "low": 7.9, "open": 8.4, "close": 8.0, "name": "消费一号"},
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["hot_rank", "sector_fund_flow"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 四、热度核心结果", rendered)
        self.assertIn("## 六、板块资金流向", rendered)
        self.assertNotIn("## 五、成交核心结果", rendered)
        self.assertNotIn("## 七、龙虎榜结果", rendered)

    def test_build_market_activity_report_sections_can_render_hot_rank_header_without_table(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [{"name": "军工一号", "code": "000001", "rate": 230000, "popularity_tag": "龙头"}],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-04-22",
            stock_full_info={"000001": {"change_pct": 5.2, "high": 12.3, "low": 11.1, "open": 11.2, "close": 12.0}},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["hot_rank_header"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 四、热度核心结果", rendered)
        self.assertIn("只看热度是否继续抱团到主线核心", rendered)
        self.assertNotIn("| 1 | 军工一号 |", rendered)
        self.assertNotIn("## 五、成交核心结果", rendered)

    def test_hot_rank_table_uses_xuangubao_plate_instead_of_market_board_label(self):
        def resolve_sector(stock_name, stock_code, **kwargs):
            xgb_data = kwargs.get("xuangubao_data") or {}
            for item in xgb_data.get("xuangubao_limit_up_reasons", []) or []:
                if item.get("symbol") == "000988.SZ":
                    return item["related_plates"][0]["plate_name"]
            return "待补充板块"

        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [{"name": "华工科技", "code": "000988", "rate": 230000, "popularity_tag": "首板涨停"}],
                "zt_pool": [{"代码": "000988", "名称": "华工科技", "所属行业": "HS"}],
                "dt_pool": [],
                "turnover_rank": [],
                "xuangubao_data": {
                    "xuangubao_limit_up_reasons": [
                        {"symbol": "000988.SZ", "name": "华工科技", "related_plates": [{"plate_name": "光通信"}]},
                    ]
                },
                "lianban_data": [],
            },
            target_date="2026-05-18",
            stock_full_info={"000988": {"change_pct": 10.0, "high": 147.38, "low": 137.03, "open": 137.53, "close": 147.38}},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=resolve_sector,
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
            enabled_node_keys=["hot_rank_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 1 | 华工科技 | 000988 | 23.0w | 光通信 | +10.00% |", rendered)
        self.assertNotIn("| HS |", rendered)

    def test_hot_rank_table_prefers_current_limit_pool_status_over_stale_hot_tag(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [
                    {"name": "昊华科技", "code": "600378", "rate": 26262000, "popularity_tag": "3天2板"},
                    {"name": "洛阳钼业", "code": "603993", "rate": 18746000, "popularity_tag": "首板涨停"},
                    {"name": "旧标签样本", "code": "000001", "rate": 16000000, "popularity_tag": "持续上榜"},
                    {"name": "旧涨停标签样本", "code": "000002", "rate": 15000000, "popularity_tag": "首板涨停"},
                    {"name": "创业板样本", "code": "300001", "rate": 14000000, "popularity_tag": ""},
                ],
                "zt_pool": [{"name": "洛阳钼业", "code": "603993", "limit_status": "涨停"}],
                "dt_pool": [],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-06-12",
            stock_full_info={
                "600378": {"change_pct": -10.0, "high": 63.25, "low": 57.15, "open": 63.18, "close": 57.15},
                "603993": {"change_pct": 10.02, "high": 19.11, "low": 18.00, "open": 18.36, "close": 19.11},
                "000001": {"change_pct": 2.0, "high": 12.0, "low": 10.0, "open": 10.5, "close": 11.0},
                "000002": {"change_pct": 3.45, "high": 17.60, "low": 16.41, "open": 16.60, "close": 17.37},
                "300001": {"change_pct": 10.0, "high": 20.00, "low": 18.00, "open": 18.50, "close": 19.80},
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "测试板块",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("普通形态", 0, "普通"),
            enabled_node_keys=["hot_rank_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 1 | 昊华科技 | 600378 | 2626.2w | 测试板块 | -10.00% | 63.25 | 57.15 | 63.18 | 57.15 | 跌停 |", rendered)
        self.assertIn("| 2 | 洛阳钼业 | 603993 | 1874.6w | 测试板块 | +10.02% | 19.11 | 18.00 | 18.36 | 19.11 | 涨停 |", rendered)
        self.assertIn("| 3 | 旧标签样本 | 000001 | 1600.0w | 测试板块 | +2.00% | 12.00 | 10.00 | 10.50 | 11.00 | 持续上榜 |", rendered)
        self.assertIn("| 4 | 旧涨停标签样本 | 000002 | 1500.0w | 测试板块 | +3.45% | 17.60 | 16.41 | 16.60 | 17.37 | - |", rendered)
        self.assertIn("| 5 | 创业板样本 | 300001 | 1400.0w | 测试板块 | +10.00% | 20.00 | 18.00 | 18.50 | 19.80 | - |", rendered)

    def test_hot_rank_table_renders_top50_rows_when_sample_available(self):
        hot_rank_rows = [
            {"name": f"热股{idx}", "code": f"000{idx:03d}", "rate": 230000, "popularity_tag": "热榜"}
            for idx in range(1, 51)
        ]
        stock_full_info = {
            f"000{idx:03d}": {"change_pct": 1.0, "high": 10.0, "low": 9.0, "open": 9.5, "close": 9.8}
            for idx in range(1, 51)
        }

        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": hot_rank_rows,
                "hot_rank_sample_size": 50,
                "hot_rank_sample_target": 50,
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-05-28",
            stock_full_info=stock_full_info,
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "热榜概念",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("小阳", 60, "中"),
            enabled_node_keys=["hot_rank_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 50 | 热股50 | 000050 |", rendered)

    def test_hot_rank_table_enriches_limit_down_quote_and_status_from_context_pool(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [{"name": "利通电子", "code": "603629", "rate": 20904000, "concepts": ["消费电子"], "popularity_tag": ""}],
                "zt_pool": [],
                "dt_pool": [
                    {
                        "代码": "603629",
                        "名称": "利通电子",
                        "所属行业": "消费电子",
                        "涨跌幅": -10.0,
                        "最高价": 166.98,
                        "最低价": 162.34,
                        "开盘价": 162.34,
                        "最新价": 162.34,
                    }
                ],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-06-08",
            stock_full_info={"603629": {"change_pct": 0.0, "high": 0.0, "low": 0.0, "open": 0.0, "close": 0.0, "name": "利通电子"}},
            get_stock_status=lambda *args, **kwargs: "-10.00% 跌停",
            get_stock_sector=lambda *args, **kwargs: "消费电子",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("下跌趋势", 0, "弱"),
            enabled_node_keys=["hot_rank_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn(
            "| 1 | 利通电子 | 603629 | 2090.4w | 消费电子 | -10.00% | 166.98 | 162.34 | 162.34 | 162.34 | 跌停 | 下跌趋势(0分) |",
            rendered,
        )

    def test_lhb_table_enriches_limit_down_quote_and_status_from_normalized_sources(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [
                    {
                        "代码": "603629",
                        "名称": "利通电子",
                        "所属行业": "消费电子",
                        "涨跌幅": -10.0,
                        "最高价": 166.98,
                        "最低价": 162.34,
                        "开盘价": 162.34,
                        "最新价": 162.34,
                    }
                ],
                "turnover_rank": [],
                "lianban_data": [],
                "lhb_net_sell_top10": [
                    {
                        "rank": 1,
                        "code": "603629",
                        "net_buy_amount_yi": -4.09,
                        "name": "利通电子",
                        "zt_status": "正常",
                        "sector": "消费电子",
                    }
                ],
            },
            target_date="2026-06-08",
            stock_full_info={
                "sh603629": {
                    "change_pct": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "open": 0.0,
                    "close": 0.0,
                    "name": "利通电子",
                }
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "消费电子",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("下跌趋势", 0, "弱"),
            enabled_node_keys=["lhb_header", "lhb_sell"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn(
            "| 1 | 利通电子 | 603629 | 4.09亿 | 消费电子 | -10.00% | 166.98 | 162.34 | 162.34 | 162.34 | 跌停 | 下跌趋势(0分) |",
            rendered,
        )
        self.assertNotIn("| 1 | 利通电子 | 603629 | 4.09亿 | 消费电子 | +0.00% |", rendered)
        self.assertNotIn("| 1 | 利通电子 | 603629 | 4.09亿 | 消费电子 | -10.00% | 166.98 | 162.34 | 162.34 | 162.34 | 正常 |", rendered)

    def test_hot_rank_table_marks_missing_quote_fields_without_fake_zero_prices(self):
        def fail_if_called(*args, **kwargs):
            raise AssertionError("missing quote fields should not run candlestick analysis")

        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [{"name": "未补报价", "code": "000001", "rate": 123000, "concepts": ["热榜概念"], "popularity_tag": ""}],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-06-08",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "-",
            get_stock_sector=lambda *args, **kwargs: "热榜概念",
            analyze_candlestick_pattern=fail_if_called,
            enabled_node_keys=["hot_rank_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn(
            "| 1 | 未补报价 | 000001 | 12.3w | 热榜概念 | 待补 | - | - | - | - | - | 报价待补(0分) |",
            rendered,
        )
        self.assertNotIn("| +0.00% | 0.00 | 0.00 | 0.00 | 0.00 |", rendered)

    def test_turnover_table_uses_quote_fields_from_turnover_rank_row(self):
        turnover_row = {
            "name": "兆易创新",
            "code": "603986",
            "turnover": 377.37,
            "sector": "半导体",
            "change_pct": -10.0,
            "open": 580.0,
            "high": 600.0,
            "low": 550.8,
            "close": 550.8,
        }
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [turnover_row],
                "turnover_rank": [turnover_row],
                "lianban_data": [],
            },
            target_date="2026-07-13",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "跌停",
            get_stock_sector=lambda *args, **kwargs: "半导体",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("下跌趋势", 0, "弱"),
            enabled_node_keys=["turnover_header", "turnover_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn(
            "| 1 | 兆易创新 | 603986 | 377.37亿 | 半导体 | -10.00% | 600.00 | 550.80 | 580.00 | 550.80 |",
            rendered,
        )
        self.assertNotIn("| +0.00% | 0.00 | 0.00 | 0.00 | 0.00 |", rendered)

    def test_turnover_table_prefers_its_ranked_row_over_auxiliary_quote(self):
        turnover_row = {
            "name": "报价优先级",
            "code": "000001",
            "turnover": 188.0,
            "sector": "银行",
            "change_pct": -3.21,
            "open": 12.0,
            "high": 12.3,
            "low": 11.5,
            "close": 11.61,
        }
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [turnover_row],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-07-13",
            stock_full_info={
                "000001": {
                    "name": "报价优先级",
                    "change_pct": 8.88,
                    "open": 12.0,
                    "high": 13.2,
                    "low": 11.9,
                    "close": 13.07,
                }
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "银行",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("下跌趋势", 0, "弱"),
            enabled_node_keys=["turnover_header", "turnover_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn(
            "| 1 | 报价优先级 | 000001 | 188.00亿 | 银行 | -3.21% | 12.30 | 11.50 | 12.00 | 11.61 |",
            rendered,
        )
        self.assertNotIn("+8.88%", rendered)

    def test_turnover_table_marks_missing_quote_fields_without_fake_zero_prices(self):
        def fail_if_called(*args, **kwargs):
            raise AssertionError("missing quote fields should not run candlestick analysis")

        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [
                    {"name": "待补报价", "code": "000001", "turnover": 188.0, "sector": "银行"}
                ],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-07-13",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "-",
            get_stock_sector=lambda *args, **kwargs: "银行",
            analyze_candlestick_pattern=fail_if_called,
            enabled_node_keys=["turnover_header", "turnover_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn(
            "| 1 | 待补报价 | 000001 | 188.00亿 | 银行 | 待补 | - | - | - | - | 观望 | 报价待补(0分) |",
            rendered,
        )
        self.assertNotIn("| +0.00% | 0.00 | 0.00 | 0.00 | 0.00 |", rendered)

    def test_build_market_activity_report_sections_can_render_turnover_header_without_table(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [{"name": "军工一号", "code": "sz000001", "turnover": 123.4}],
                "turnover_rank": [],
                "lianban_data": [],
            },
            target_date="2026-04-22",
            stock_full_info={"000001": {"change_pct": 5.2, "high": 12.3, "low": 11.1, "open": 11.2, "close": 12.0}},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["turnover_header"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 五、成交核心结果", rendered)
        self.assertIn("只看真放量的成交核心", rendered)
        self.assertNotIn("| 1 | 军工一号 |", rendered)
        self.assertNotIn("## 四、热度核心结果", rendered)

    def test_build_market_activity_report_sections_can_render_sector_fund_inflow_without_outflow(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [{"name": "消费", "zljlr": -9.8, "zdf": -1.8}],
                },
                "lianban_data": [],
            },
            target_date="2026-04-22",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["sector_fund_header", "sector_fund_inflow"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 六、板块资金流向", rendered)
        self.assertIn("### 资金流入TOP10", rendered)
        self.assertIn("| 1 | 军工 | +12.30亿 | +1.23% |", rendered)
        self.assertNotIn("### 资金流出结果", rendered)
        self.assertNotIn("消费", rendered)

    def test_build_market_activity_report_sections_renders_sector_fund_alias_fields(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"sector": "半导体", "net_amount": 31.2, "change_pct": 2.45}],
                    "outflow": [{"industry": "通信设备", "net_inflow_yi": -18.6, "pct_change": -1.27}],
                },
                "lianban_data": [],
            },
            target_date="2026-06-29",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "半导体",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["sector_fund_inflow", "sector_fund_outflow"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 1 | 半导体 | +31.20亿 | +2.45% |", rendered)
        self.assertIn("| 1 | 通信设备 | 18.60亿 | -1.27% |", rendered)

    def test_build_market_activity_report_sections_exports_sector_diffusion_for_postgres(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [
                    {"name": "军工龙头", "code": "000001", "sector": "军工"},
                    {"name": "军工后排", "code": "000002", "sector": "军工"},
                ],
                "dt_pool": [],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [],
                },
                "lianban_data": [{"name": "军工龙头", "code": "000001", "sector": "军工", "height": 3}],
                "market_stats": {"up_count": 3000, "total_count": 5000},
            },
            target_date="2026-04-22",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["sector_fund_inflow"],
        )

        exported = result["exports"]["sector_internal_analysis"]["diffusion_quality"]

        self.assertTrue(exported["sectors"])
        self.assertEqual(exported["sectors"][0]["sector_name"], "军工")

    def test_build_market_activity_report_sections_exports_turnover_trend_and_quant_environment_for_postgres(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [
                    {"name": "电力一号", "code": "000001", "sector": "电力"},
                    {"name": "半导体一号", "code": "000002", "sector": "半导体"},
                    {"name": "机器人一号", "code": "000003", "sector": "机器人"},
                ],
                "dt_pool": [],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "电力", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [],
                },
                "lianban_data": [{"name": "电力一号", "code": "000001", "sector": "电力", "height": 3}],
                "market_stats": {"up_count": 1800, "total_count": 5000},
                "top50_turnover_share_pct": 22.5,
                "sector_turnover_history": [
                    {
                        "sector_name": "电力",
                        "history": [
                            {"date": "2026-05-25", "turnover_share_pct": 12.1},
                            {"date": "2026-05-26", "turnover_share_pct": 14.0},
                            {"date": "2026-05-27", "turnover_share_pct": 16.2},
                            {"date": "2026-05-28", "turnover_share_pct": 17.5},
                            {"date": "2026-05-29", "turnover_share_pct": 18.2},
                        ],
                    }
                ],
            },
            target_date="2026-05-29",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "电力",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["sector_fund_inflow"],
        )

        exported = result["exports"]["sector_internal_analysis"]

        self.assertEqual(exported["turnover_trend"]["sectors"][0]["sector_name"], "电力")
        self.assertEqual(exported["turnover_trend"]["sectors"][0]["latest_share"], 18.2)
        self.assertIn("quant_environment", exported)
        self.assertIn("### 板块成交占比趋势 (近5日)", "\n".join(result["lines"]))

    def test_sector_turnover_trend_groups_flat_recent_history_rows(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "电网设备", "zljlr": 12.3, "zdf": 1.23},
                        {"name": "电力", "zljlr": 10.1, "zdf": 0.82},
                        {"name": "半导体", "zljlr": 8.9, "zdf": -0.35},
                    ],
                    "outflow": [],
                },
                "lianban_data": [],
                "market_stats": {"up_count": 1800, "total_count": 5000},
                "top50_turnover_share_pct": 22.5,
                "recent_sector_turnover_history": [
                    {"date": "2026-05-29", "sector_name": "电网设备", "turnover_share_pct": 4.6},
                    {"date": "2026-05-27", "sector_name": "电网设备", "turnover_share_pct": 3.2},
                    {"date": "2026-05-28", "sector_name": "电网设备", "turnover_share_pct": 4.0},
                    {"date": "2026-05-29", "sector_name": "电力", "turnover_share_pct": 3.5},
                    {"date": "2026-05-28", "sector_name": "电力", "turnover_share_pct": 2.8},
                    {"date": "2026-05-29", "name": "半导体", "turnover_share_pct": 5.0},
                    {"date": "2026-05-28", "sector_name": "半导体", "turnover_share_pct": 5.8},
                ],
            },
            target_date="2026-05-29",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "电网设备",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["sector_fund_inflow"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("### 板块成交占比趋势 (近5日)", rendered)
        turnover_section = rendered.split("### 板块成交占比趋势 (近5日)", 1)[1].split("### 量化环境识别", 1)[0]
        self.assertEqual(turnover_section.count("| 电网设备 |"), 1)
        self.assertEqual(turnover_section.count("| 电力 |"), 1)
        self.assertEqual(turnover_section.count("| 半导体 |"), 1)
        self.assertIn("| 电网设备 | 4.6% | 强化 | 0.0% | 3.2% → 4.0% → 4.6% (扩张) |", turnover_section)
        self.assertLess(turnover_section.index("| 半导体 | 5.0% |"), turnover_section.index("| 电网设备 | 4.6% |"))
        self.assertLess(turnover_section.index("| 电网设备 | 4.6% |"), turnover_section.index("| 电力 | 3.5% |"))
        self.assertNotIn("| 电力 | 0.0% | 待累计 |", turnover_section)

    def test_sector_fund_flow_quant_environment_uses_weaker_csi1000_rhythm(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [{"name": "电力一号", "code": "000001", "sector": "电力"}],
                "dt_pool": [],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "电力", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [],
                },
                "lianban_data": [{"name": "电力一号", "code": "000001", "sector": "电力", "height": 3}],
                "market_stats": {"up_count": 1000, "total_count": 5000},
                "top50_turnover_share_pct": 22.5,
                "wind_a_alternative": {"change_pct": 1.5},
                "csi1000_index": {"change_pct": -2.1},
            },
            target_date="2026-05-29",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "电力",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["sector_fund_inflow"],
        )

        exported = result["exports"]["sector_internal_analysis"]["quant_environment"]

        self.assertFalse(exported["is_quant_dominant"])
        self.assertNotIn("窄池子进攻", [item["mode"] for item in exported["modes"]])

    def test_sector_fund_flow_quant_environment_renders_top_level_detector_summary(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "电力", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [],
                },
                "lianban_data": [],
                "market_stats": {"up_count": 2500, "total_count": 5000},
                "top50_turnover_share_pct": 18.0,
                "wind_a_alternative": {"change_pct": 0.2},
                "csi1000_index": {"change_pct": 0.1},
            },
            target_date="2026-05-29",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "电力",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["sector_fund_inflow"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("### 量化环境识别", rendered)
        self.assertIn("**当前环境**: 未检测到明显的量化横行特征", rendered)
        self.assertIn("**动作建议**: 按传统模式处理,个股强度和板块节奏并重", rendered)
        self.assertNotIn("**当前环境**: 待识别", rendered)

    def test_build_market_activity_report_sections_can_render_lhb_buy_without_sell(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lhb_net_buy_top10": [
                    {
                        "rank": 1,
                        "code": "000001",
                        "net_buy_amount_yi": 3.2,
                        "name": "军工一号",
                        "zt_status": "正常",
                        "sector": "军工",
                    }
                ],
                "lhb_net_sell_top10": [
                    {
                        "rank": 1,
                        "code": "000002",
                        "net_buy_amount_yi": -2.1,
                        "name": "消费一号",
                        "zt_status": "正常",
                        "sector": "消费",
                    }
                ],
                "lianban_data": [],
            },
            target_date="2026-04-22",
            stock_full_info={
                "000001": {"change_pct": 5.2, "high": 10.5, "low": 9.8, "open": 10.0, "close": 10.4, "name": "军工一号"},
                "000002": {"change_pct": -3.1, "high": 8.5, "low": 7.8, "open": 8.2, "close": 8.0, "name": "消费一号"},
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["lhb_header", "lhb_buy"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 七、龙虎榜结果", rendered)
        self.assertIn("### 净买入结果", rendered)
        self.assertIn("| 1 | 军工一号 | 000001 | 3.20亿 | 军工 | +5.20% |", rendered)
        self.assertNotIn("### 净流出结果", rendered)
        self.assertNotIn("消费一号", rendered)

    def test_lhb_rows_replace_market_board_and_unknown_sector_with_context_sector(self):
        def resolve_sector(stock_name, stock_code, **kwargs):
            self.assertIn("xuangubao_data", kwargs)
            return {
                "000988": "光通信",
                "002518": "算力",
                "300657": "云计算数据中心",
            }.get(stock_code, "半导体")

        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "xuangubao_data": {
                    "xuangubao_limit_up_reasons": [
                        {"symbol": "000988.SZ", "name": "华工科技", "related_plates": [{"plate_name": "光通信"}]},
                    ],
                    "xuangubao_news": [
                        {
                            "title": "算力方向异动",
                            "stocks": [{"symbol": "002518.SZ", "name": "科士达"}],
                            "plates": [{"name": "算力"}],
                        }
                    ],
                },
                "lhb_net_buy_top10": [
                    {"rank": 1, "code": "000988", "net_buy_amount_yi": 16.99, "name": "华工科技", "zt_status": "正常", "sector": "HS"},
                    {"rank": 2, "code": "002518", "net_buy_amount_yi": 4.92, "name": "科士达", "zt_status": "正常", "sector": "未知"},
                ],
                "lhb_net_sell_top10": [
                    {"rank": 1, "code": "300657", "net_buy_amount_yi": -4.09, "name": "弘信电子", "zt_status": "正常", "sector": "GEM"},
                ],
                "lianban_data": [],
            },
            target_date="2026-05-18",
            stock_full_info={
                "000988": {"change_pct": 10.0, "high": 147.38, "low": 137.03, "open": 137.53, "close": 147.38, "name": "华工科技"},
                "002518": {"change_pct": 9.38, "high": 63.71, "low": 58.49, "open": 58.49, "close": 63.35, "name": "科士达"},
                "300657": {"change_pct": 19.99, "high": 43.4, "low": 43.4, "open": 43.4, "close": 43.4, "name": "弘信电子"},
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=resolve_sector,
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["lhb_header", "lhb_buy", "lhb_sell"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 1 | 华工科技 | 000988 | 16.99亿 | 光通信 | +10.00% |", rendered)
        self.assertIn("| 2 | 科士达 | 002518 | 4.92亿 | 算力 | +9.38% |", rendered)
        self.assertIn("| 1 | 弘信电子 | 300657 | 4.09亿 | 云计算数据中心 | +19.99% |", rendered)
        self.assertNotIn("| HS |", rendered)
        self.assertNotIn("| GEM |", rendered)
        self.assertNotIn("| 未知 |", rendered)

    def test_lhb_rows_use_prefilled_quote_fields_when_stock_full_info_is_missing(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lhb_net_buy_top10": [
                    {
                        "rank": 1,
                        "code": "688409",
                        "net_buy_amount_yi": 7.28,
                        "name": "富创精密",
                        "sector": "半导体",
                        "change_pct": 4.67,
                        "high": 176.8,
                        "low": 155.74,
                        "open": 158.09,
                        "close": 169.85,
                    }
                ],
                "lhb_net_sell_top10": [],
                "lianban_data": [],
            },
            target_date="2026-05-18",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "半导体",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("普通形态", 0, "中"),
            enabled_node_keys=["lhb_header", "lhb_buy"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 1 | 富创精密 | 688409 | 7.28亿 | 半导体 | +4.67% | 176.80 | 155.74 | 158.09 | 169.85 |", rendered)
        self.assertNotIn("| 0.00 | 0.00 | 0.00 | 0.00 |", rendered)

    def test_lhb_seat_strength_renders_institution_broker_stock_connect_and_repeat_lists(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lhb_net_buy_top10": [
                    {
                        "rank": 1,
                        "code": "000001",
                        "name": "军工一号",
                        "net_buy_amount_yi": 3.2,
                        "sector": "军工",
                    },
                    {
                        "rank": 2,
                        "code": "000002",
                        "name": "科技二号",
                        "net_buy_amount_yi": 1.5,
                        "sector": "科技",
                    },
                ],
                "lhb_net_sell_top10": [
                    {
                        "rank": 1,
                        "code": "000003",
                        "name": "消费三号",
                        "net_buy_amount_yi": -2.0,
                        "sector": "消费",
                    },
                ],
                "lhb_analysis": [
                    {
                        "代码": "000001",
                        "name": "军工一号",
                        "net_buy_amount": 320000000,
                        "reasons": ["日涨幅偏离值达到7%", "日振幅值达到15%"],
                    },
                    {
                        "代码": "000002",
                        "name": "科技二号",
                        "net_buy_amount": 150000000,
                        "reasons": ["日涨幅偏离值达到7%"],
                    },
                    {
                        "代码": "000003",
                        "name": "消费三号",
                        "net_buy_amount": -200000000,
                        "reasons": ["日跌幅偏离值达到7%", "连续三个交易日内跌幅偏离值累计达到20%"],
                    },
                ],
                "lhb_inst_detail": [
                    {
                        "trade_date": "20260611",
                        "code": "000001",
                        "exalter": "机构专用",
                        "seat_type": "机构",
                        "net_buy_yi": 0.7,
                    },
                    {
                        "trade_date": "20260611",
                        "code": "000001",
                        "exalter": "深股通专用",
                        "seat_type": "非机构",
                        "net_buy_yi": 0.5,
                    },
                    {
                        "trade_date": "20260611",
                        "code": "000001",
                        "exalter": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                        "seat_type": "非机构",
                        "net_buy_yi": -0.2,
                    },
                    {
                        "trade_date": "20260611",
                        "code": "000002",
                        "exalter": "国泰海通证券股份有限公司总部",
                        "seat_type": "非机构",
                        "net_buy_yi": 1.1,
                    },
                    {
                        "trade_date": "20260611",
                        "code": "000002",
                        "exalter": "沪股通专用",
                        "seat_type": "非机构",
                        "net_buy_yi": -0.4,
                    },
                    {
                        "trade_date": "20260611",
                        "code": "000003",
                        "exalter": "机构专用",
                        "seat_type": "机构",
                        "net_buy_yi": -0.5,
                    },
                    {
                        "trade_date": "20260611",
                        "code": "000003",
                        "exalter": "中信证券股份有限公司上海分公司",
                        "seat_type": "非机构",
                        "net_buy_yi": 0.8,
                    },
                    {
                        "trade_date": "20260610",
                        "code": "000001",
                        "exalter": "日期不一致席位",
                        "seat_type": "机构",
                        "net_buy_yi": 9.0,
                    },
                ],
                "lianban_data": [],
            },
            target_date="2026-06-11",
            stock_full_info={},
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("普通形态", 0, "中"),
            enabled_node_keys=["lhb_seat_strength"],
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("### 席位强度解读", rendered)
        self.assertIn("#### 机构净买强榜", rendered)
        self.assertIn("| 军工一号 | 000001 | +0.70 | 1 | 机构专用 | 日涨幅偏离值达到7%；日振幅值达到15% |", rendered)
        self.assertIn("#### 非机构强榜", rendered)
        self.assertIn("| 科技二号 | 000002 | +0.70 | 2 | 国泰海通证券股份有限公司总部 | 日涨幅偏离值达到7% |", rendered)
        self.assertIn("#### 股通席位", rendered)
        self.assertIn("| 军工一号 | 000001 | +0.50 | 净买 | 深股通专用 | 日涨幅偏离值达到7%；日振幅值达到15% |", rendered)
        self.assertIn("#### 重复上榜分歧榜", rendered)
        self.assertIn("| 消费三号 | 000003 | 2 | -2.00 | -0.50 | +0.80 | 机构卖、非机构买 |", rendered)
        self.assertNotIn("日期不一致席位", rendered)

    def test_turnover_rows_preserve_valid_row_sector_and_replace_unknown(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [
                    {"name": "佰维存储", "code": "688525", "concepts": ["存储芯片"]},
                ],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [
                    {"name": "中际旭创", "code": "300308", "turnover": 255.46, "sector": "通信设备"},
                    {"name": "佰维存储", "code": "688525", "turnover": 167.86, "sector": "未知"},
                ],
                "turnover_rank": [],
                "lhb_net_buy_top10": [],
                "lhb_net_sell_top10": [],
                "lianban_data": [],
            },
            target_date="2026-05-18",
            stock_full_info={
                "300308": {"change_pct": -0.46, "high": 1075, "low": 1030.03, "open": 1030.03, "close": 1045, "name": "中际旭创"},
                "688525": {"change_pct": 8.10, "high": 345, "low": 308, "open": 308, "close": 331.1, "name": "佰维存储"},
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "不应覆盖",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
            enabled_node_keys=["turnover_header", "turnover_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 1 | 中际旭创 | 300308 | 255.46亿 | 通信设备 | -0.46% |", rendered)
        self.assertIn("| 2 | 佰维存储 | 688525 | 167.86亿 | 存储芯片 | +8.10% |", rendered)
        self.assertNotIn("| 未知 |", rendered)

    def test_turnover_table_outputs_top30_rows(self):
        turnover_rows = [
            {"name": f"成交{i:02d}", "code": f"300{i:03d}", "turnover": 300 - i, "sector": "通信设备"}
            for i in range(1, 32)
        ]
        stock_full_info = {
            row["code"]: {
                "change_pct": 1.0,
                "high": 10.0,
                "low": 9.0,
                "open": 9.5,
                "close": 9.8,
                "name": row["name"],
            }
            for row in turnover_rows
        }

        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": turnover_rows,
                "turnover_rank": [],
                "lhb_net_buy_top10": [],
                "lhb_net_sell_top10": [],
                "lianban_data": [],
            },
            target_date="2026-06-09",
            stock_full_info=stock_full_info,
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "通信设备",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("普通形态", 0, "普通"),
            enabled_node_keys=["turnover_header", "turnover_table"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 30 | 成交30 | 300030 | 270.00亿 | 通信设备 | +1.00% |", rendered)
        self.assertNotIn("| 31 | 成交31 | 300031 |", rendered)

    def test_build_market_activity_report_sections_renders_hot_rank_and_lhb(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [{"name": "军工一号", "code": "000001", "rate": 230000, "concepts": ["军工"], "popularity_tag": "龙头"}],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [{"name": "军工一号", "code": "sz000001", "turnover": 123.4}],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [{"name": "消费", "zljlr": -9.8, "zdf": -1.8}],
                },
                "lhb_net_buy_top10": [{"rank": 1, "code": "000001", "net_buy_amount_yi": 3.2, "name": "军工一号", "zt_status": "正常", "sector": "军工"}],
                "lhb_net_sell_top10": [{"rank": 1, "code": "000002", "net_buy_amount_yi": -2.1, "name": "消费一号", "zt_status": "正常", "sector": "消费"}],
                "lianban_data": [],
            },
            target_date="2026-04-22",
            stock_full_info={
                "000001": {"change_pct": 5.2, "high": 12.3, "low": 11.1, "open": 11.2, "close": 12.0, "name": "军工一号"},
                "000002": {"change_pct": -3.1, "high": 8.5, "low": 7.9, "open": 8.4, "close": 8.0, "name": "消费一号"},
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 四、热度核心结果", rendered)
        self.assertNotIn("## 四、热度前三十个股", rendered)
        self.assertIn("> **先看什么**: 只看热度是否继续抱团到主线核心，别被杂讯热榜带偏。", rendered)
        self.assertNotIn("> **数据来源**: 同花顺个股热榜", rendered)
        self.assertIn("## 五、成交核心结果", rendered)
        self.assertNotIn("## 五、成交额排名前十且>100亿个股", rendered)
        self.assertIn("**先看什么**: 只看真放量的成交核心，缩量凑热闹的不算。", rendered)
        self.assertNotIn("**筛选标准**: 成交额>100亿的个股", rendered)
        self.assertIn("| 1 | 军工一号 | 000001 | 23.0w | 军工 | +5.20% |", rendered)
        self.assertIn("## 六、板块资金流向", rendered)
        self.assertNotIn("## 六、行业资金净流向", rendered)
        fund_section = rendered.split("## 六、板块资金流向", 1)[1].split("## 七、", 1)[0]
        self.assertIn("### 资金流入TOP10", fund_section)
        self.assertNotIn("### 净流入前十", fund_section)
        self.assertIn("### 资金流出结果", fund_section)
        self.assertNotIn("### 净流出前十", fund_section)
        self.assertIn("## 七、龙虎榜结果", rendered)
        self.assertNotIn("## 七、龙虎榜数据", rendered)
        self.assertIn("### 净买入结果", rendered)
        self.assertNotIn("### 净买入前十", rendered)
        self.assertIn("### 净流出结果", rendered)
        self.assertNotIn("### 净流出前十", rendered)
        self.assertIn("| 1 | 军工一号 | 000001 | 3.20亿 | 军工 | +5.20% |", rendered)
        self.assertTrue(any(log["step"] == "render.market_activity_sections" for log in result["module_logs"]))

    def test_build_advanced_activity_report_sections_renders_lianban_and_signals(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [
                    {
                        "lianban_days": 3,
                        "name": "军工龙一",
                        "code": "000005",
                        "first_limit_time": "09:31",
                        "reason": "军工总龙头",
                        "plates": ["军工"],
                    },
                    {
                        "lianban_days": 2,
                        "name": "军工二号",
                        "code": "000003",
                        "first_limit_time": "09:45",
                        "reason": "军工主升",
                        "plates": ["军工"],
                    },
                    {
                        "lianban_days": 1,
                        "name": "军工三号",
                        "code": "000004",
                        "first_limit_time": "10:12",
                        "reason": "军工补涨",
                        "plates": ["军工"],
                    }
                ],
                "volume_anomalies": [
                    {
                        "stock_code": "000003",
                        "stock_name": "军工二号",
                        "anomaly_type": {"__enum__": "AnomalyType", "name": "VOLUME_BREAKOUT", "value": "放量突破"},
                        "strength": "高",
                        "volume_percentile": 98,
                        "price_change": 0,
                        "reason": "量价齐升",
                    }
                ],
                "lhb_analysis": [
                    {
                        "stock_name": "军工二号",
                        "net_buy": 1.5,
                        "money_type": {"__enum__": "MoneyType", "name": "HOT_MONEY", "value": "游资主导"},
                        "pattern": "接力",
                        "recent_appearances": 2,
                        "signal_strength": "强",
                    }
                ],
                "resonance_scores": {
                    "军工": {
                        "total_score": 8.0,
                        "strength_dimensions": ["fund_flow", "limit_up"],
                        "dimension_scores": {"fund_flow": 4, "limit_up": 3, "lhb": 1},
                        "resonance_level": {"__enum__": "ResonanceLevel", "name": "STRONG", "value": "强共振"},
                    },
                    "杂毛": {
                        "total_score": 6.0,
                        "strength_dimensions": ["lhb"],
                        "dimension_scores": {"fund_flow": 1, "limit_up": 1, "lhb": 4},
                        "resonance_level": {"__enum__": "ResonanceLevel", "name": "NONE", "value": "无共振"},
                    }
                },
                "trade_signals": [
                    {
                        "signal_type": {"__enum__": "SignalType", "name": "VOLUME_START", "value": "放量启动"},
                        "sector_name": "军工",
                        "score": 8.5,
                        "action": "关注",
                        "reason": "共振最强",
                        "risk_level": "中",
                    },
                    SimpleNamespace(
                        signal_type=SimpleNamespace(value="缩量回踩"),
                        sector_name="杂毛",
                        stock_code="",
                        score=3.0,
                        action="忽略",
                        reason="无效",
                        risk_level="高",
                    ),
                ],
            },
            stock_full_info={
                "000005": {"change_pct": 10.0, "high": 11.5, "low": 10.2, "open": 10.3, "close": 11.5},
                "000003": {"change_pct": 9.9, "high": 10.0, "low": 9.1, "open": 9.2, "close": 9.9},
                "000004": {"change_pct": 4.8, "high": 8.6, "low": 8.0, "open": 8.1, "close": 8.4},
            },
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 九、连板结果", rendered)
        self.assertNotIn("## 九、连板梯队", rendered)
        self.assertIn("> **先看什么**: 只看高标强度、首板扩散和连板梯队有没有继续收拢。", rendered)
        self.assertNotIn("> **数据来源**: akshare涨停池数据（支持历史日期）", rendered)
        self.assertIn("### 3连板结果(1只)", rendered)
        self.assertNotIn("### 【3连板】(1只)", rendered)
        self.assertIn("### 2连板结果(1只)", rendered)
        self.assertNotIn("### 【2连板】(1只)", rendered)
        self.assertIn("### 首板结果(1只)", rendered)
        self.assertNotIn("### 【首板/1连板】(1只)", rendered)
        self.assertIn("## 十、多维交易结果", rendered)
        self.assertNotIn("## 十、AI多维量化分析", rendered)
        self.assertIn("> **先看什么**: 只看量能异常、龙虎榜强度和板块共振能不能转成明日动作。", rendered)
        self.assertNotIn("> **核心升级**", rendered)
        self.assertIn("### 1. 放量结果", rendered)
        self.assertNotIn("### 1. 放量异常检测", rendered)
        self.assertIn("### 2. 板块共振结果", rendered)
        self.assertNotIn("### 2. 板块共振评分（多维加权模型）", rendered)
        self.assertIn("### 2. 龙虎榜结果", rendered)
        self.assertNotIn("### 2. 龙虎榜深度分析", rendered)
        self.assertIn("### 3. 交易信号结果", rendered)
        self.assertNotIn("### 3. AI量化交易信号", rendered)
        self.assertIn("| 股票 | 异常类型 | 强度 | 成交量分位 | 涨跌幅 | 当前信号 |", rendered)
        self.assertNotIn("| 股票 | 异常类型 | 强度 | 成交量分位 | 涨跌幅 | 信号说明 |", rendered)
        self.assertIn("| 信号类型 | 板块/个股 | 得分 | 操作建议 | 当前证据 | 风险等级 |", rendered)
        self.assertNotIn("| 信号类型 | 板块/个股 | 得分 | 操作建议 | 逻辑说明 | 风险等级 |", rendered)
        self.assertIn("| 军工二号 | 放量突破 | 高 | 98% | +9.90% | 量价齐升 |", rendered)
        self.assertIn("| 军工二号 | +1.50 | 游资主导 | 接力 | 2次 | 强 |", rendered)
        self.assertIn("| 军工 | 8.0 | 🔥 强共振 |", rendered)
        self.assertNotIn("无共振", rendered)
        self.assertIn("| 放量启动 | 军工 | 8.5 | 关注 | 共振最强 | 中 |", rendered)
        self.assertNotIn("__enum__", rendered)
        self.assertTrue(any(log["step"] == "render.advanced_activity_sections" for log in result["module_logs"]))

    def test_lianban_rows_use_row_price_fields_when_stock_full_info_is_missing(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [
                    {
                        "lianban_days": 1,
                        "name": "利仁科技",
                        "code": "001259",
                        "sector": "股权转让",
                        "change_pct": 10.0,
                        "high_price": 66.55,
                        "low_price": 63.01,
                        "open_price": 66.55,
                        "close_price": 66.55,
                        "first_limit_time": "09:25:00",
                        "reason": "控股股东拟协议转让股份",
                    }
                ],
                "volume_anomalies": [],
                "lhb_analysis": [],
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "股权转让",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("一字板加速", 10, "强"),
            enabled_node_keys=["lianban"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 利仁科技 | 001259 | 股权转让 | +10.00% | 09:25:00 | 66.55 | 63.01 | 66.55 | 66.55 |", rendered)
        self.assertNotIn("| 0.00 | 0.00 | 0.00 | 0.00 |", rendered)

    def test_lianban_rows_keep_trade_narrative_stocks_visible_after_default_five(self):
        ordinary_rows = [
            {
                "lianban_days": 1,
                "name": f"普通首板{index}",
                "code": f"00000{index}",
                "sector": "软件服务",
                "first_limit_time": f"09:3{index}:00",
                "reason": "普通首板",
            }
            for index in range(1, 6)
        ]
        narrative_rows = [
            {
                "lianban_days": 1,
                "name": "岩山科技",
                "code": "002195",
                "sector": "脑机接口",
                "raw_sector": "软件服务",
                "trade_narrative_sector": "脑机接口",
                "first_limit_time": "10:01:00",
                "reason": "脑机接口+AI大模型",
            },
            {
                "lianban_days": 1,
                "name": "创新医疗",
                "code": "002173",
                "sector": "脑机接口",
                "raw_sector": "医疗保健",
                "trade_narrative_sector": "脑机接口",
                "first_limit_time": "10:02:00",
                "reason": "脑机接口+医疗服务",
            },
        ]
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": ordinary_rows + narrative_rows,
                "volume_anomalies": [],
                "lhb_analysis": [],
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "软件服务",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 4, "强"),
            enabled_node_keys=["lianban"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 岩山科技 | 002195 | 脑机接口 |", rendered)
        self.assertIn("| 创新医疗 | 002173 | 脑机接口 |", rendered)

    def test_build_advanced_activity_report_sections_can_render_only_enabled_nodes(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [
                    {
                        "lianban_days": 3,
                        "name": "军工龙一",
                        "code": "000005",
                        "first_limit_time": "09:31",
                        "reason": "军工总龙头",
                        "plates": ["军工"],
                    }
                ],
                "volume_anomalies": [
                    {
                        "stock_code": "000003",
                        "stock_name": "军工二号",
                        "anomaly_type": {"__enum__": "AnomalyType", "name": "VOLUME_BREAKOUT", "value": "放量突破"},
                        "strength": "高",
                        "volume_percentile": 98,
                        "price_change": 9.9,
                        "reason": "量价齐升",
                    }
                ],
                "lhb_analysis": [
                    {
                        "stock_name": "军工二号",
                        "net_buy": 1.5,
                        "money_type": {"__enum__": "MoneyType", "name": "HOT_MONEY", "value": "游资主导"},
                        "pattern": "接力",
                        "recent_appearances": 2,
                        "signal_strength": "强",
                    }
                ],
                "resonance_scores": {
                    "军工": {
                        "total_score": 8.0,
                        "strength_dimensions": ["fund_flow", "limit_up"],
                        "dimension_scores": {"fund_flow": 4, "limit_up": 3, "lhb": 1},
                        "resonance_level": {"__enum__": "ResonanceLevel", "name": "STRONG", "value": "强共振"},
                    }
                },
                "trade_signals": [
                    {
                        "signal_type": {"__enum__": "SignalType", "name": "VOLUME_START", "value": "放量启动"},
                        "sector_name": "军工",
                        "score": 8.5,
                        "action": "关注",
                        "reason": "共振最强",
                        "risk_level": "中",
                    }
                ],
            },
            stock_full_info={
                "000005": {"change_pct": 10.0, "high": 11.5, "low": 10.2, "open": 10.3, "close": 11.5},
                "000003": {"change_pct": 9.9, "high": 10.0, "low": 9.1, "open": 9.2, "close": 9.9},
            },
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
            enabled_node_keys=["lianban", "trade_signals"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 九、连板结果", rendered)
        self.assertIn("### 3. 交易信号结果", rendered)
        self.assertNotIn("### 1. 放量结果", rendered)
        self.assertNotIn("### 2. 龙虎榜结果", rendered)
        self.assertNotIn("### 2. 板块共振结果", rendered)

    def test_build_advanced_activity_report_sections_can_render_advanced_header_without_volume_node(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [
                    {
                        "stock_code": "000003",
                        "stock_name": "军工二号",
                        "anomaly_type": "放量突破",
                        "strength": "高",
                        "volume_percentile": 98,
                        "price_change": 9.9,
                        "reason": "量价齐升",
                    }
                ],
                "lhb_analysis": [],
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
            enabled_node_keys=["advanced_header", "trade_signals"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 十、多维交易结果", rendered)
        self.assertIn("### 3. 交易信号结果", rendered)
        self.assertNotIn("### 1. 放量结果", rendered)
        self.assertNotIn("| 军工二号 | 放量突破 |", rendered)

    def test_build_advanced_activity_report_sections_uses_prefilled_volume_anomaly_change_when_quote_missing(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [
                    {
                        "stock_code": "000777",
                        "stock_name": "异常股",
                        "anomaly_type": "放量突破",
                        "strength": "高",
                        "volume_percentile": 97,
                        "price_change": 7.8,
                        "reason": "量价齐升",
                    }
                ],
                "lhb_analysis": [],
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 异常股 | 放量突破 | 高 | 97% | +7.80% | 量价齐升 |", rendered)

    def test_build_advanced_activity_report_sections_backfills_volume_anomaly_change_from_raw_market_pools(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [{"code": "000777", "name": "异常股", "change_pct": 7.8}],
                "zt_pool": [{"代码": "000777", "名称": "异常股", "涨跌幅": 7.8}],
                "dt_pool": [],
                "turnover_rank": [{"code": "sz000777", "name": "异常股", "change_pct": 7.8}],
                "volume_anomalies": [
                    {
                        "stock_code": "000777",
                        "stock_name": "异常股",
                        "anomaly_type": "放量突破",
                        "strength": "高",
                        "volume_percentile": 97,
                        "price_change": 0,
                        "reason": "量价齐升",
                    }
                ],
                "lhb_analysis": [],
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 异常股 | 放量突破 | 高 | 97% | +7.80% | 量价齐升 |", rendered)

    def test_build_advanced_activity_report_sections_uses_result_wording_for_empty_lianban_state(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [],
                "lhb_analysis": [],
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**暂无连板结果**", rendered)
        self.assertNotIn("**暂无连板梯队数据**", rendered)
        self.assertIn("| - | - | - | - | - | 当前无放量结果 |", rendered)
        self.assertNotIn("| - | - | - | - | - | 暂无显著放量异常 |", rendered)
        self.assertIn("| - | - | - | - | - | 当前无龙虎榜结果 |", rendered)
        self.assertNotIn("| - | - | - | - | - | 暂无龙虎榜数据 |", rendered)
        self.assertIn("*暂无共振结果*", rendered)
        self.assertNotIn("*暂无共振评分数据*", rendered)
        self.assertIn("*当前无交易信号*", rendered)
        self.assertNotIn("*暂无交易信号*", rendered)

    def test_build_advanced_activity_report_sections_explains_upstream_empty_lhb(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [],
                "lhb_analysis": [],
                "lhb_data_status": "upstream_empty",
                "lhb_provider": "tushare.top_list",
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("tushare.top_list 龙虎榜暂未返回数据", rendered)
        self.assertNotIn("| - | - | - | - | - | 当前无龙虎榜结果 |", rendered)

    def test_build_advanced_activity_report_sections_renders_lhb_rank_rows_when_analysis_empty(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [],
                "lhb_analysis": [],
                "lhb_net_buy_top10": [
                    {"name": "弘信电子", "net_buy_amount_yi": 9.656255, "sector": "元器件", "zt_status": "涨停"}
                ],
                "lhb_net_sell_top10": [
                    {"name": "西部材料", "net_buy_amount_yi": -3.627309, "sector": "小金属", "zt_status": "正常"}
                ],
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 弘信电子 | +9.66 | 龙虎榜净买入 | 元器件 | - | 涨停 |", rendered)
        self.assertIn("| 西部材料 | -3.63 | 龙虎榜净卖出 | 小金属 | - | 正常 |", rendered)
        self.assertNotIn("| - | - | - | - | - | 当前无龙虎榜结果 |", rendered)

    def test_build_advanced_activity_report_sections_hides_internal_lhb_provider_when_empty(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [],
                "lhb_analysis": [],
                "lhb_data_status": "upstream_empty",
                "lhb_provider": "legacy.lhb_snapshot",
                "resonance_scores": {},
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("Tushare top_list / 备用龙虎榜源 龙虎榜暂未返回数据", rendered)
        self.assertNotIn("legacy.lhb_snapshot", rendered)

    def test_build_advanced_activity_report_sections_uses_result_wording_for_low_score_trade_signals(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [],
                "lhb_analysis": [],
                "resonance_scores": {},
                "trade_signals": [
                    {
                        "signal_type": "缩量回踩",
                        "sector_name": "军工",
                        "score": 3.0,
                        "action": "忽略",
                        "reason": "强度不足",
                        "risk_level": "高",
                    }
                ],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("*当前无有效交易信号*", rendered)
        self.assertNotIn("*暂无有效交易信号（所有信号得分均≤15）*", rendered)

    def test_build_advanced_activity_report_sections_uses_result_wording_for_non_resonant_scores(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [],
                "volume_anomalies": [],
                "lhb_analysis": [],
                "resonance_scores": {
                    "军工": {
                        "total_score": 4.0,
                        "strength_dimensions": ["fund_flow"],
                        "dimension_scores": {"fund_flow": 4, "limit_up": 0, "lhb": 0},
                        "resonance_level": "无共振",
                    }
                },
                "trade_signals": [],
            },
            stock_full_info={},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("*当前无共振结果*", rendered)
        self.assertNotIn("*暂无有效共振板块（所有板块得分均为0）*", rendered)


if __name__ == "__main__":
    unittest.main()
