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
