import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.request import (
    collect_market_activity_capital_snapshot_request_bundle,
    collect_market_activity_hot_rank_request_bundle,
    collect_market_activity_pool_request_bundle,
    collect_market_activity_sector_snapshot_request_bundle,
    collect_market_activity_stock_quote_request_bundle,
)


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.1, 0.2


class _FrameStub:
    def __init__(self, rows):
        self._rows = list(rows)

    @property
    def empty(self):
        return not self._rows

    def to_dict(self, orient):
        assert orient == "records"
        return list(self._rows)

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, row

    def __len__(self):
        return len(self._rows)


class _MarketActivityFrameStub:
    def __init__(self, rows):
        self._rows = list(rows)

    @property
    def empty(self):
        return not self._rows

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, [row["item"], row["value"]]

    def __len__(self):
        return len(self._rows)


class _TencentStub:
    def __init__(self, hot_stocks=None):
        self._hot_stocks = hot_stocks or []

    def get_hot_stocks(self, num=30):
        return list(self._hot_stocks[:num])


class MarketActivityRequestTest(unittest.TestCase):
    def test_collect_market_activity_pool_request_bundle_builds_pool_and_stats(self):
        timer = _TimerStub()
        emitted = []

        result = collect_market_activity_pool_request_bundle(
            "2026-04-22",
            get_limit_up_pool=lambda date_str: (
                _FrameStub(
                    [
                        {"代码": "000001", "名称": "军工一号", "所属行业": "军工", "涨停统计": "2连板"},
                        {"代码": "000002", "名称": "算力一号", "所属行业": "算力", "涨停统计": "首板"},
                    ]
                ),
                {"000001", "000002"},
            ),
            get_limit_down_pool=lambda date_str: (
                _FrameStub([{"代码": "000003", "名称": "消费一号", "所属行业": "消费"}]),
                {"000003"},
            ),
            fetch_market_activity_df=lambda: _MarketActivityFrameStub(
                [
                    {"item": "上涨", "value": 3200},
                    {"item": "下跌", "value": 1800},
                    {"item": "涨停", "value": 95},
                    {"item": "跌停", "value": 3},
                ]
            ),
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(len(result["results"]["zt_pool"]), 2)
        self.assertEqual(result["results"]["zt_pool_by_sector"]["军工"][0]["zt_type"], "2连板")
        self.assertEqual(result["results"]["dt_pool_by_sector"]["消费"][0]["code"], "000003")
        self.assertEqual(result["results"]["market_stats"]["up_count"], 3200)
        self.assertTrue(result["data_status"]["涨停池"])
        self.assertTrue(result["data_status"]["跌停池"])
        self.assertTrue(result["data_status"]["大盘涨跌统计"])
        self.assertTrue(result["step_status"]["涨停跌停数据获取"])
        self.assertEqual(result["artifacts"]["limit_up_df"].__class__.__name__, "_FrameStub")
        self.assertTrue(any("涨停池" in line for line in emitted))
        self.assertEqual(timer.records[-1], ("涨停跌停数据获取", 4))

    def test_collect_market_activity_pool_request_bundle_parses_akshare_market_activity_columns(self):
        import pandas as pd

        timer = _TimerStub()
        emitted = []

        result = collect_market_activity_pool_request_bundle(
            "2026-04-27",
            get_limit_up_pool=lambda date_str: (
                _FrameStub([{"代码": "000001", "名称": "涨停一号", "所属行业": "半导体", "涨停统计": "首板"}]),
                {"000001"},
            ),
            get_limit_down_pool=lambda date_str: (
                _FrameStub([{"代码": "000002", "名称": "跌停一号", "所属行业": "白酒Ⅱ"}]),
                {"000002"},
            ),
            fetch_market_activity_df=lambda: pd.DataFrame(
                [
                    {"item": "上涨", "value": 3182.0},
                    {"item": "涨停", "value": 85.0},
                    {"item": "下跌", "value": 1900.0},
                    {"item": "跌停", "value": 54.0},
                ]
            ),
            timer=timer,
            emit=emitted.append,
        )

        self.assertTrue(result["step_status"]["涨停跌停数据获取"])
        self.assertTrue(result["data_status"]["涨停池"])
        self.assertTrue(result["data_status"]["跌停池"])
        self.assertTrue(result["data_status"]["大盘涨跌统计"])
        self.assertEqual(len(result["results"]["zt_pool"]), 1)
        self.assertEqual(len(result["results"]["dt_pool"]), 1)
        self.assertEqual(result["results"]["market_stats"]["up_count"], 3182)
        self.assertEqual(result["results"]["market_stats"]["down_count"], 1900)
        self.assertEqual(result["results"]["market_stats"]["zt_count"], 85)
        self.assertEqual(result["results"]["market_stats"]["dt_count"], 54)
        self.assertEqual(result["module_logs"][0]["status"], "success")

    def test_collect_market_activity_hot_rank_request_bundle_builds_hot_rank_and_integrated_snapshot(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub(hot_stocks=[{"name": "备用热榜", "code": "000009"}])

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-04-22",
            existing_results={
                "zt_pool": [{"代码": "000001", "所属行业": "军工"}],
            },
            fetch_ths_hot_stock=lambda num=30: [
                {"name": "军工一号", "code": "000001", "rate": 230000, "concepts": ["军工"], "popularity_tag": "龙头"}
            ],
            get_integrated_hot_list=lambda limit=100: (
                [{"name": "军工一号", "code": "000001", "change_pct": 5.2, "sector_tags": ["军工"]}],
                {"军工": 1},
                {"龙头": 1},
                [{"name": "军工一号", "code": "000001"}],
            ),
            tencent=tencent,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["hot_rank_top30"][0]["sector"], "军工")
        self.assertEqual(result["results"]["code_to_sector"]["000001"], "军工")
        self.assertEqual(result["results"]["integrated_hot_list"][0]["code"], "000001")
        self.assertEqual(result["results"]["tag_distribution"]["军工"], 1)
        self.assertTrue(result["data_status"]["热度前三十个股"])
        self.assertTrue(result["data_status"]["整合热榜"])
        self.assertTrue(result["step_status"]["热度前三十个股获取"])
        self.assertTrue(result["step_status"]["整合热榜获取"])
        self.assertEqual(timer.records[0], ("热度前三十个股获取", 5))
        self.assertTrue(any("热榜" in line for line in emitted))

    def test_collect_market_activity_hot_rank_request_bundle_records_primary_failure_and_fallback_success(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub(hot_stocks=[{"name": "腾讯兜底", "code": "000009"}])

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-04-22",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: (_ for _ in ()).throw(RuntimeError("ths timeout")),
            get_integrated_hot_list=lambda limit=100: ([], {}, {}, []),
            tencent=tencent,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["hot_rank_top30"][0]["name"], "腾讯兜底")
        self.assertTrue(result["data_status"]["热度前三十个股"])
        self.assertTrue(any(log["step"] == "request.hot_rank.primary" and log["status"] == "error" for log in result["module_logs"]))
        self.assertTrue(
            any(
                log["step"] == "request.hot_rank.fallback"
                and log["status"] == "success"
                and log["details"].get("fallback_used") is True
                for log in result["module_logs"]
            )
        )
        self.assertTrue(any("腾讯备用" in line or "腾讯热榜成功" in line for line in emitted))

    def test_collect_market_activity_sector_snapshot_request_bundle_builds_sector_and_turnover_views(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()
        tencent.get_sector_fund_flow = lambda flow_type="in", limit=50: (
            [{"name": "军工", "code": "pt01801000", "zljlr": 12.3, "zdf": 1.5, "cje": 1234567.0}]
            if flow_type == "in"
            else [{"name": "消费", "code": "pt01801001", "zljlr": -8.1, "zdf": -1.2, "cje": 880000.0}]
        )

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-04-22",
            fetch_hot_plate=lambda: [{"name": "军工", "rate": 32.0, "tag": "2涨停", "hot_tag": "持续上榜"}],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: (
                [{"name": "军工", "change_pct": 4.5, "data_source": "tencent.fundflow.getHyRank"}]
                if rank_type == "up"
                else [{"name": "消费", "change_pct": -3.2, "data_source": "tencent.fundflow.getHyRank"}]
            ),
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: [
                {"name": "军工一号", "code": "000001", "turnover": 123.4, "data_source": "eastmoney.push2.clist"},
                {"name": "消费一号", "code": "000002", "turnover": 88.0, "data_source": "eastmoney.push2.clist"},
            ],
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-04-22", "2026-04-21"),
        )

        self.assertEqual(result["results"]["hot_plates"][0]["name"], "军工")
        self.assertEqual(result["results"]["sector_fund_flow"]["inflow"][0]["name"], "军工")
        self.assertEqual(result["results"]["sector_fund_flow"]["inflow"][0]["turnover_yi"], 123.46)
        self.assertEqual(result["results"]["sector_fund_flow"]["outflow"][0]["turnover_yi"], 88.0)
        self.assertEqual(result["results"]["sector_change_up"][0]["name"], "军工")
        self.assertEqual(len(result["results"]["turnover_over_100b"]), 1)
        self.assertTrue(result["data_status"]["板块热榜"])
        self.assertTrue(result["data_status"]["行业资金流向"])
        self.assertTrue(result["data_status"]["板块涨幅排行"])
        self.assertTrue(result["data_status"]["板块跌幅排行"])
        self.assertTrue(result["data_status"]["成交额排名"])
        self.assertTrue(result["step_status"]["板块热榜获取"])
        self.assertTrue(result["step_status"]["行业资金流向获取"])
        self.assertTrue(result["step_status"]["板块涨跌幅排行获取"])
        self.assertTrue(result["step_status"]["成交额排名获取"])
        self.assertEqual(timer.records[-1], ("成交额排名获取", 9))
        self.assertTrue(any("板块热榜" in line for line in emitted))
        self.assertIn("  8️⃣ 获取板块涨跌幅排行（腾讯行业资金流）...", emitted)
        self.assertIn("  9️⃣ 获取东方财富成交额排行...", emitted)
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.sector_change_rank"], "tencent.sector_change_rank")
        self.assertEqual(provider_by_step["request.turnover_rank"], "eastmoney.turnover_rank")

    def test_collect_market_activity_sector_snapshot_request_bundle_passes_target_date_and_logs_actual_providers(self):
        timer = _TimerStub()
        emitted = []
        captured_sector_dates = []
        captured_turnover_dates = []
        tencent = _TencentStub()
        tencent.get_sector_fund_flow = lambda flow_type="in", limit=50: []

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-04-18",
            fetch_hot_plate=lambda: [],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: (
                captured_sector_dates.append(target_date)
                or [{"name": "半导体", "change_pct": 4.23, "data_source": "akshare.stock_board_industry_name_em"}]
            ),
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: (
                captured_turnover_dates.append(target_date)
                or [{"name": "宁德时代", "code": "300750", "turnover": 145.1, "data_source": "akshare.stock_zh_a_spot_em"}]
            ),
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-04-22", "2026-04-21"),
        )

        self.assertEqual(captured_sector_dates, ["2026-04-18", "2026-04-18"])
        self.assertEqual(captured_turnover_dates, ["2026-04-18"])
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.sector_change_rank"], "akshare.stock_board_industry_name_em")
        self.assertEqual(provider_by_step["request.turnover_rank"], "akshare.stock_zh_a_spot_em")

    def test_collect_market_activity_sector_snapshot_request_bundle_marks_historical_sector_flow_as_handled(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()
        tencent.get_sector_fund_flow = lambda flow_type="in", limit=50: []

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-04-18",
            fetch_hot_plate=lambda: [],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: [],
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: [],
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-04-22", "2026-04-21"),
        )

        self.assertTrue(result["data_status"]["行业资金流向"])
        self.assertTrue(result["step_status"]["行业资金流向获取"])
        self.assertTrue(result["results"]["sector_fund_flow"]["is_historical"])

    def test_collect_market_activity_capital_snapshot_request_bundle_builds_lianban_and_lhb_views(self):
        timer = _TimerStub()
        emitted = []
        limit_up_df = _FrameStub(
            [
                {
                    "代码": "000001",
                    "名称": "军工一号",
                    "连板数": 3,
                    "涨跌幅": 10.0,
                    "成交额": 45.6,
                    "所属行业": "军工",
                    "涨停统计": "3连板",
                    "开盘价": 10.0,
                    "最新价": 11.0,
                    "最高价": 11.0,
                    "最低价": 9.8,
                    "首次封板时间": "093000",
                }
            ]
        )

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-04-22",
            limit_up_df=limit_up_df,
            existing_results={
                "zt_pool": [{"代码": "000001", "所属行业": "军工"}],
                "dt_pool": [{"代码": "000002", "所属行业": "消费"}],
            },
            fetch_lhb_rows=lambda target_date: [
                {"fs_code": "000001.SZ", "net_buy_amount": 320000000, "close_price": 11.0, "change_rate": 10.0},
                {"fs_code": "000001.SZ", "net_buy_amount": 180000000, "close_price": 11.0, "change_rate": 10.0},
                {"fs_code": "000002.SZ", "net_buy_amount": -150000000, "close_price": 8.0, "change_rate": -5.0},
            ],
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["lianban_data"][0]["lianban_days"], 3)
        self.assertEqual(result["results"]["lianban_data"][0]["first_limit_time"], "09:30:00")
        self.assertEqual(result["results"]["lhb_net_buy_top10"][0]["code"], "000001")
        self.assertEqual(result["results"]["lhb_net_buy_top10"][0]["net_buy_amount_yi"], 5.0)
        self.assertEqual(result["results"]["lhb_net_sell_top10"][0]["code"], "000002")
        self.assertEqual(result["results"]["lhb_net_sell_top10"][0]["sector"], "消费")
        self.assertTrue(result["step_status"]["连板梯队提取"])
        self.assertTrue(result["step_status"]["龙虎榜数据获取"])
        self.assertTrue(any("龙虎榜" in line for line in emitted))

    def test_collect_market_activity_stock_quote_request_bundle_builds_quote_map_and_backfills_lhb_names(self):
        timer = _TimerStub()
        emitted = []
        captured_codes = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "hot_rank_top30": [{"code": "sz000001"}],
                "turnover_rank": [{"code": "sh600001"}],
                "lhb_net_buy_top10": [{"code": "000001", "name": ""}],
                "lhb_net_sell_top10": [{"code": "600001", "name": ""}],
                "lianban_data": [{"code": "000003"}],
            },
            fetch_stock_batch_info=lambda codes: (
                captured_codes.extend(sorted(codes))
                or {
                    "000001": {"name": "军工一号", "change_pct": 6.2},
                    "600001": {"name": "金融一号", "change_pct": 2.1},
                    "000003": {"name": "算力一号", "change_pct": 4.3},
                }
            ),
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(captured_codes, ["000001", "000003", "600001"])
        self.assertEqual(result["results"]["stock_full_info"]["000001"]["name"], "军工一号")
        self.assertEqual(result["results"]["lhb_net_buy_top10"][0]["name"], "军工一号")
        self.assertEqual(result["results"]["lhb_net_sell_top10"][0]["name"], "金融一号")
        self.assertEqual(timer.records[0], ("批量获取股票信息", 15))
        self.assertTrue(any("股票" in line for line in emitted))


if __name__ == "__main__":
    unittest.main()
