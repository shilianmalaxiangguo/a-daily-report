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


class _FakeDatabaseService:
    market_breadth = {}

    @classmethod
    def fact_store_from_environment(cls, db_path=None):
        del db_path
        return cls()

    def query_market_breadth_counts(self, target_date):
        del target_date
        return dict(self.market_breadth)


class _TencentStub:
    def __init__(self, hot_stocks=None):
        self._hot_stocks = hot_stocks or []

    def get_hot_stocks(self, num=30):
        return list(self._hot_stocks[:num])


def _hot_rank_rows(count, *, sector="军工", source="同花顺热榜", name_prefix=None):
    name_prefix = name_prefix or sector
    return [
        {
            "name": f"{name_prefix}{idx}",
            "code": f"000{idx:03d}",
            "rate": 230000,
            "concepts": [sector],
            "popularity_tag": "热榜",
            "data_source": source,
        }
        for idx in range(1, count + 1)
    ]


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

    def test_collect_market_activity_pool_request_bundle_marks_market_breadth_incomplete_when_stats_fail(self):
        timer = _TimerStub()
        emitted = []

        result = collect_market_activity_pool_request_bundle(
            "2026-05-27",
            get_limit_up_pool=lambda date_str: (
                _FrameStub([{"代码": "000001", "名称": "涨停一号", "所属行业": "半导体", "涨停统计": "首板"}]),
                {"000001"},
            ),
            get_limit_down_pool=lambda date_str: (
                _FrameStub([{"代码": "000002", "名称": "跌停一号", "所属行业": "白酒Ⅱ"}]),
                {"000002"},
            ),
            fetch_market_activity_df=lambda: (_ for _ in ()).throw(AttributeError("'NoneType' object has no attribute 'text'")),
            timer=timer,
            emit=emitted.append,
        )

        self.assertTrue(result["step_status"]["涨停跌停数据获取"])
        self.assertTrue(result["data_status"]["涨停池"])
        self.assertTrue(result["data_status"]["跌停池"])
        self.assertFalse(result["data_status"]["大盘涨跌统计"])
        self.assertEqual(result["results"]["zt_pool"][0]["代码"], "000001")
        self.assertEqual(result["results"]["dt_pool"][0]["代码"], "000002")
        self.assertEqual(result["results"]["market_stats"]["up_count"], 0)
        self.assertEqual(result["results"]["market_stats"]["down_count"], 0)
        self.assertEqual(result["results"]["market_stats"]["zt_count"], 1)
        self.assertEqual(result["results"]["market_stats"]["dt_count"], 1)
        self.assertTrue(any(log["step"] == "request.market_stats" and log["status"] == "degraded" for log in result["module_logs"]))

    def test_collect_market_activity_pool_request_bundle_uses_postgres_breadth_when_stats_fail(self):
        timer = _TimerStub()
        emitted = []
        _FakeDatabaseService.market_breadth = {
            "up_count": 899,
            "down_count": 4591,
            "flat_count": 25,
            "zt_count": 82,
            "dt_count": 86,
            "stock_count": 5515,
            "source": "storage.stock_daily_quotes_recent",
        }

        result = collect_market_activity_pool_request_bundle(
            "2026-06-08",
            get_limit_up_pool=lambda date_str: (
                _FrameStub([{"代码": "000001", "名称": "涨停一号", "所属行业": "半导体", "涨停统计": "首板"}]),
                {"000001"},
            ),
            get_limit_down_pool=lambda date_str: (
                _FrameStub([{"代码": "000002", "名称": "跌停一号", "所属行业": "白酒Ⅱ"}]),
                {"000002"},
            ),
            fetch_market_activity_df=lambda: (_ for _ in ()).throw(RuntimeError("akshare timeout")),
            request_registry={"database_service_cls": _FakeDatabaseService},
            timer=timer,
            emit=emitted.append,
        )

        self.assertTrue(result["data_status"]["大盘涨跌统计"])
        self.assertEqual(result["results"]["market_stats"]["up_count"], 899)
        self.assertEqual(result["results"]["market_stats"]["down_count"], 4591)
        self.assertTrue(
            any(
                log["step"] == "request.market_stats"
                and log["status"] == "success"
                and log["details"].get("provider") == "storage.stock_daily_quotes_recent"
                for log in result["module_logs"]
            )
        )

    def test_collect_market_activity_pool_request_bundle_uses_postgres_breadth_when_stats_are_zero(self):
        timer = _TimerStub()
        emitted = []
        _FakeDatabaseService.market_breadth = {
            "up_count": 2469,
            "down_count": 2933,
            "flat_count": 108,
            "zt_count": 196,
            "dt_count": 83,
            "stock_count": 5510,
            "source": "storage.stock_daily_quotes_recent",
        }

        result = collect_market_activity_pool_request_bundle(
            "2026-06-29",
            get_limit_up_pool=lambda date_str: (
                _FrameStub([{"代码": "000001", "名称": "涨停一号", "所属行业": "半导体", "涨停统计": "首板"}]),
                {"000001"},
            ),
            get_limit_down_pool=lambda date_str: (
                _FrameStub([{"代码": "000002", "名称": "跌停一号", "所属行业": "白酒Ⅱ"}]),
                {"000002"},
            ),
            fetch_market_activity_df=lambda: _MarketActivityFrameStub(
                [
                    {"item": "上涨", "value": 0},
                    {"item": "下跌", "value": 0},
                ]
            ),
            request_registry={"database_service_cls": _FakeDatabaseService},
            timer=timer,
            emit=emitted.append,
        )

        self.assertTrue(result["data_status"]["大盘涨跌统计"])
        self.assertEqual(result["results"]["market_stats"]["up_count"], 2469)
        self.assertEqual(result["results"]["market_stats"]["down_count"], 2933)
        self.assertTrue(
            any(
                log["step"] == "request.market_stats"
                and log["status"] == "success"
                and log["details"].get("provider") == "storage.stock_daily_quotes_recent"
                for log in result["module_logs"]
            )
        )

    def test_historical_pool_request_reads_postgres_breadth_before_current_market_activity(self):
        timer = _TimerStub()
        emitted = []
        current_market_activity_calls = []
        _FakeDatabaseService.market_breadth = {
            "up_count": 899,
            "down_count": 4591,
            "flat_count": 25,
            "zt_count": 82,
            "dt_count": 86,
            "stock_count": 5515,
            "source": "storage.stock_daily_quotes_recent",
        }

        result = collect_market_activity_pool_request_bundle(
            "2026-06-08",
            get_limit_up_pool=lambda date_str: (
                _FrameStub([{"代码": "000001", "名称": "涨停一号", "所属行业": "半导体", "涨停统计": "首板"}]),
                {"000001"},
            ),
            get_limit_down_pool=lambda date_str: (
                _FrameStub([{"代码": "000002", "名称": "跌停一号", "所属行业": "白酒Ⅱ"}]),
                {"000002"},
            ),
            fetch_market_activity_df=lambda: current_market_activity_calls.append("current")
            or _MarketActivityFrameStub(
                [
                    {"item": "上涨", "value": 3200},
                    {"item": "下跌", "value": 1800},
                ]
            ),
            request_registry={"database_service_cls": _FakeDatabaseService},
            current_date="2026-06-09",
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(current_market_activity_calls, [])
        self.assertTrue(result["data_status"]["大盘涨跌统计"])
        self.assertEqual(result["results"]["market_stats"]["up_count"], 899)
        self.assertEqual(result["results"]["market_stats"]["down_count"], 4591)
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.market_stats"], "storage.stock_daily_quotes_recent")

    def test_collect_market_activity_pool_request_bundle_uses_tushare_registry_before_legacy_sources(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []
        registry_calls = []

        result = collect_market_activity_pool_request_bundle(
            "2026-05-13",
            get_limit_up_pool=lambda date_str: legacy_calls.append(("limit_up", date_str)) or (_FrameStub([]), set()),
            get_limit_down_pool=lambda date_str: legacy_calls.append(("limit_down", date_str)) or (_FrameStub([]), set()),
            fetch_market_activity_df=lambda: legacy_calls.append(("market_activity", None)) or _MarketActivityFrameStub([]),
            request_registry={
                "limit_pool_snapshot": lambda *, target_date: registry_calls.append(target_date)
                or {
                    "zt_pool": [{"代码": "000001", "名称": "平安银行", "所属行业": "银行", "涨停统计": "首板"}],
                    "dt_pool": [{"代码": "000002", "名称": "万科A", "所属行业": "地产"}],
                    "limit_up_codes": {"000001"},
                    "limit_down_codes": {"000002"},
                    "market_stats": {"up_count": 3100, "down_count": 1900, "zt_count": 1, "dt_count": 1},
                    "provider": "tushare.limit_list_ths",
                    "fallback_used": False,
                },
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(registry_calls, ["2026-05-13"])
        self.assertEqual(legacy_calls, [])
        self.assertEqual(result["results"]["zt_pool"][0]["代码"], "000001")
        self.assertEqual(result["results"]["dt_pool"][0]["代码"], "000002")
        self.assertEqual(result["results"]["market_stats"]["up_count"], 3100)
        self.assertEqual(result["artifacts"]["limit_up_df"].to_dict("records")[0]["代码"], "000001")
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.pool_snapshot"], "tushare.limit_list_ths")

    def test_collect_market_activity_pool_request_bundle_uses_legacy_sources_when_registry_empty(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []

        result = collect_market_activity_pool_request_bundle(
            "2026-05-27",
            get_limit_up_pool=lambda date_str: legacy_calls.append(("limit_up", date_str))
            or (_FrameStub([{"代码": "000001", "名称": "平安银行", "所属行业": "银行", "涨停统计": "首板"}]), {"000001"}),
            get_limit_down_pool=lambda date_str: legacy_calls.append(("limit_down", date_str))
            or (_FrameStub([{"代码": "000002", "名称": "万科A", "所属行业": "地产"}]), {"000002"}),
            fetch_market_activity_df=lambda: legacy_calls.append(("market_activity", None))
            or _MarketActivityFrameStub(
                [
                    {"item": "上涨", "value": 3100},
                    {"item": "下跌", "value": 1900},
                    {"item": "涨停", "value": 1},
                    {"item": "跌停", "value": 1},
                ]
            ),
            request_registry={
                "limit_pool_snapshot": lambda *, target_date: {
                    "zt_pool": [],
                    "dt_pool": [],
                    "market_stats": {},
                    "provider": "legacy.limit_pool_snapshot",
                    "fallback_used": True,
                    "source_status": "empty",
                },
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(legacy_calls, [("limit_up", "20260527"), ("limit_down", "20260527"), ("market_activity", None)])
        self.assertTrue(result["step_status"]["涨停跌停数据获取"])
        self.assertTrue(result["data_status"]["涨停池"])
        self.assertTrue(result["data_status"]["跌停池"])
        self.assertTrue(result["data_status"]["大盘涨跌统计"])
        self.assertEqual(result["results"]["zt_pool"][0]["代码"], "000001")
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.pool_snapshot"], "akshare.limit_up_down+akshare.stock_market_activity_legu")

    def test_collect_market_activity_pool_request_bundle_uses_snapshot_daily_breadth_when_legacy_stats_fail(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []

        result = collect_market_activity_pool_request_bundle(
            "2026-05-29",
            get_limit_up_pool=lambda date_str: legacy_calls.append(("limit_up", date_str)) or (
                _FrameStub([{"代码": "000001", "名称": "涨停一号", "所属行业": "电力", "涨停统计": "首板"}]),
                {"000001"},
            ),
            get_limit_down_pool=lambda date_str: legacy_calls.append(("limit_down", date_str)) or (
                _FrameStub([{"代码": "000002", "名称": "跌停一号", "所属行业": "半导体"}]),
                {"000002"},
            ),
            fetch_market_activity_df=lambda: (_ for _ in ()).throw(RuntimeError("legacy stats unavailable")),
            request_registry={
                "limit_pool_snapshot": lambda *, target_date: {
                    "zt_pool": [],
                    "dt_pool": [],
                    "market_stats": {"up_count": 2100, "down_count": 3200, "zt_count": 49, "dt_count": 50},
                    "provider": "legacy.limit_pool_snapshot",
                    "fallback_used": True,
                    "source_status": "empty",
                },
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(legacy_calls, [("limit_up", "20260529"), ("limit_down", "20260529")])
        self.assertEqual(result["results"]["zt_pool"][0]["名称"], "涨停一号")
        self.assertEqual(result["results"]["market_stats"]["up_count"], 2100)
        self.assertEqual(result["results"]["market_stats"]["down_count"], 3200)
        self.assertTrue(result["data_status"]["大盘涨跌统计"])

    def test_collect_market_activity_pool_request_bundle_infers_sector_from_limit_reason(self):
        timer = _TimerStub()
        emitted = []

        result = collect_market_activity_pool_request_bundle(
            "2026-05-27",
            get_limit_up_pool=lambda date_str: (_FrameStub([]), set()),
            get_limit_down_pool=lambda date_str: (_FrameStub([]), set()),
            fetch_market_activity_df=lambda: _MarketActivityFrameStub([]),
            request_registry={
                "limit_pool_snapshot": lambda *, target_date: {
                    "zt_pool": [
                        {
                            "代码": "603005",
                            "名称": "晶方科技",
                            "所属行业": "未知",
                            "涨停统计": "首板",
                            "涨停原因": "长鑫存储概念带动，国产芯片封测走强",
                        },
                        {
                            "代码": "000901",
                            "名称": "航天科技",
                            "涨停统计": "商业航天与卫星互联网方向活跃",
                        },
                    ],
                    "dt_pool": [],
                    "limit_up_codes": {"603005", "000901"},
                    "limit_down_codes": set(),
                    "market_stats": {"up_count": 2600, "down_count": 2400, "zt_count": 2, "dt_count": 0},
                    "provider": "tushare.limit_list_ths",
                },
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertIn("国产芯片", result["results"]["zt_pool_by_sector"])
        self.assertIn("商业航天", result["results"]["zt_pool_by_sector"])
        self.assertNotEqual(set(result["results"]["zt_pool_by_sector"]), {"未知"})
        self.assertEqual(result["results"]["zt_pool_by_sector"]["国产芯片"][0]["code"], "603005")
        self.assertTrue(result["data_status"]["涨停股板块分布"])

    def test_collect_market_activity_hot_rank_request_bundle_builds_hot_rank_and_integrated_snapshot(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub(hot_stocks=_hot_rank_rows(50, sector="备用", name_prefix="备用热榜"))

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-04-22",
            existing_results={
                "zt_pool": [{"代码": "000001", "所属行业": "军工"}],
            },
            fetch_ths_hot_stock=lambda num=30: _hot_rank_rows(num, sector="军工", name_prefix="军工热股"),
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
        self.assertEqual(result["results"]["integrated_hot_list_sample_target"], 100)
        self.assertTrue(result["data_status"]["热度前50个股"])
        self.assertTrue(result["data_status"]["整合热榜"])
        self.assertTrue(result["step_status"]["热度前50个股获取"])
        self.assertTrue(result["step_status"]["整合热榜获取"])
        self.assertEqual(timer.records[0], ("热度前50个股获取", 5))
        self.assertTrue(any("热榜" in line for line in emitted))

    def test_collect_market_activity_hot_rank_request_bundle_records_primary_failure_and_fallback_success(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub(hot_stocks=_hot_rank_rows(50, sector="腾讯", name_prefix="腾讯兜底"))

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-04-22",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: (_ for _ in ()).throw(RuntimeError("ths timeout")),
            get_integrated_hot_list=lambda limit=100: ([], {}, {}, []),
            tencent=tencent,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["hot_rank_top30"][0]["name"], "腾讯兜底1")
        self.assertTrue(result["data_status"]["热度前50个股"])
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

    def test_collect_market_activity_hot_rank_request_bundle_uses_tushare_registry_before_legacy_sources(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []
        tencent = _TencentStub(hot_stocks=[])
        registry_calls = []

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-05-13",
            existing_results={"zt_pool": [{"代码": "600519", "所属行业": "白酒"}]},
            fetch_ths_hot_stock=lambda num=30: legacy_calls.append(("ths", num)) or [],
            get_integrated_hot_list=lambda limit=100: ([], {}, {}, []),
            tencent=tencent,
            request_registry={
                "stock_hot_rank": lambda *, target_date, limit=30: registry_calls.append((target_date, limit))
                or [{"rank": 1, "name": "贵州茅台", "code": "600519", "data_source": "tushare.ths_hot"}],
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(registry_calls, [("2026-05-13", 50)])
        self.assertEqual(legacy_calls, [("ths", 50)])
        self.assertEqual(result["results"]["hot_rank_top30"][0]["sector"], "白酒")
        self.assertFalse(result["data_status"]["热度前50个股"])
        hot_rank_providers = [
            log["details"].get("provider")
            for log in result["module_logs"]
            if log["step"] == "request.hot_rank.primary"
        ]
        self.assertEqual(hot_rank_providers[:2], ["tushare.ths_hot", "ths_hot_stock"])

    def test_collect_market_activity_hot_rank_request_bundle_requests_top50_sample(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []
        registry_calls = []

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-05-28",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: legacy_calls.append(num) or [],
            get_integrated_hot_list=lambda limit=100: ([], {}, {}, []),
            tencent=_TencentStub(),
            request_registry={
                "stock_hot_rank": lambda *, target_date, limit=30: registry_calls.append((target_date, limit))
                or [
                    {"rank": idx, "name": f"热股{idx}", "code": f"000{idx:03d}", "data_source": "tushare.ths_hot"}
                    for idx in range(1, limit + 1)
                ],
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(registry_calls, [("2026-05-28", 50)])
        self.assertEqual(legacy_calls, [])
        self.assertEqual(len(result["results"]["hot_rank_top30"]), 50)
        self.assertEqual(result["results"]["hot_rank_sample_size"], 50)
        self.assertEqual(result["results"]["hot_rank_sample_target"], 50)
        self.assertTrue(result["data_status"]["热度前50个股"])
        self.assertTrue(result["step_status"]["热度前50个股获取"])

    def test_integrated_hot_rank_requests_top100_even_when_primary_hot_rank_is_top50(self):
        timer = _TimerStub()
        emitted = []
        integrated_calls = []

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-06-09",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: _hot_rank_rows(num, sector="军工", name_prefix="基础热榜"),
            get_integrated_hot_list=lambda limit=100: integrated_calls.append(limit)
            or (
                _hot_rank_rows(limit, sector="算力", name_prefix="整合热榜"),
                {"算力": limit},
                {"热榜": limit},
                [],
            ),
            tencent=_TencentStub(),
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(integrated_calls, [100])
        self.assertEqual(len(result["results"]["hot_rank_top50"]), 50)
        self.assertEqual(len(result["results"]["integrated_hot_list"]), 100)
        self.assertEqual(result["results"]["integrated_hot_list_sample_size"], 100)
        self.assertEqual(result["results"]["integrated_hot_list_sample_target"], 100)
        self.assertEqual(result["results"]["tag_distribution"], {"算力": 100})
        integrated_log = next(log for log in result["module_logs"] if log["step"] == "request.integrated_hot_rank")
        self.assertEqual(integrated_log["details"]["provider"], "hot_list_integrated.get_integrated_hot_list")
        self.assertFalse(integrated_log["details"]["fallback_used"])

    def test_integrated_hot_rank_falls_back_to_primary_when_top100_returns_empty(self):
        timer = _TimerStub()
        emitted = []
        integrated_calls = []

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-06-09",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: _hot_rank_rows(num, sector="军工", name_prefix="基础热榜"),
            get_integrated_hot_list=lambda limit=100: integrated_calls.append(limit) or ([], {}, {}, []),
            tencent=_TencentStub(),
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(integrated_calls, [100])
        self.assertEqual(len(result["results"]["integrated_hot_list"]), 50)
        self.assertEqual(result["results"]["integrated_hot_list_sample_size"], 50)
        self.assertEqual(result["results"]["integrated_hot_list_sample_target"], 50)
        self.assertEqual(result["results"]["tag_distribution"], {"军工": 50})
        integrated_log = next(log for log in result["module_logs"] if log["step"] == "request.integrated_hot_rank")
        self.assertEqual(integrated_log["details"]["provider"], "primary_hot_rank.fallback")
        self.assertTrue(integrated_log["details"]["fallback_used"])

    def test_integrated_hot_rank_reuses_tushare_hot_rank_before_legacy_integrator(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []
        tencent = _TencentStub(hot_stocks=[])

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-05-13",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: legacy_calls.append(("ths", num)) or [],
            get_integrated_hot_list=lambda limit=100: legacy_calls.append(("integrated", limit)) or ([], {}, {}, []),
            tencent=tencent,
            request_registry={
                "stock_hot_rank": lambda *, target_date, limit=30: [
                    {
                        "rank": 1,
                        "name": "大唐发电",
                        "code": "601991",
                        "concepts": ["绿色电力", "风电"],
                        "data_source": "tushare.ths_hot",
                    }
                ],
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(legacy_calls, [("ths", 50), ("integrated", 100)])
        self.assertEqual(result["results"]["integrated_hot_list"][0]["code"], "601991")
        self.assertEqual(result["results"]["tag_distribution"], {"绿色电力": 1, "风电": 1})
        self.assertTrue(result["data_status"]["整合热榜"])
        self.assertFalse(result["data_status"]["热度前50个股"])
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.integrated_hot_rank"], "tushare.ths_hot.primary_hot_rank")
        fallback_by_step = {log["step"]: log["details"].get("fallback_used") for log in result["module_logs"]}
        self.assertTrue(fallback_by_step["request.integrated_hot_rank"])

    def test_integrated_hot_rank_reuses_primary_hot_rank_even_when_source_label_is_chinese(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []
        tencent = _TencentStub()

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-05-18",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: [
                {
                    "rank": 1,
                    "name": "大唐发电",
                    "code": "601991",
                    "concepts": ["绿色电力", "风电"],
                    "data_source": "同花顺热榜",
                }
            ],
            get_integrated_hot_list=lambda limit=100: legacy_calls.append(("integrated", limit)) or ([], {}, {}, []),
            tencent=tencent,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(legacy_calls, [("integrated", 100)])
        self.assertEqual(result["results"]["integrated_hot_list"][0]["code"], "601991")
        self.assertEqual(result["results"]["tag_distribution"], {"绿色电力": 1, "风电": 1})
        self.assertFalse(result["data_status"]["热度前50个股"])
        integrated_log = next(log for log in result["module_logs"] if log["step"] == "request.integrated_hot_rank")
        self.assertEqual(integrated_log["details"]["provider"], "primary_hot_rank.fallback")
        self.assertTrue(integrated_log["details"]["fallback_used"])

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
        self.assertIn("  8️⃣ 获取板块涨跌幅排行（Tushare 优先）...", emitted)
        self.assertIn("  9️⃣ 获取成交额排行（Tushare 优先）...", emitted)
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.sector_change_rank"], "tencent.sector_change_rank")
        self.assertEqual(provider_by_step["request.turnover_rank"], "eastmoney.turnover_rank")

    def test_collect_market_activity_sector_snapshot_request_bundle_uses_tushare_registry_for_turnover_rank(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()
        tencent.get_sector_fund_flow = lambda flow_type="in", limit=50: []
        legacy_calls = []
        registry_calls = []

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-05-13",
            fetch_hot_plate=lambda: [],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: [],
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: legacy_calls.append((target_date, limit)) or [],
            request_registry={
                "turnover_rank": lambda *, target_date, limit=50: registry_calls.append((target_date, limit)) or [
                    {"rank": 1, "code": "600000", "name": "浦发银行", "turnover": 320.25, "data_source": "tushare.daily"}
                ]
            },
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-05-13", "2026-05-12"),
        )

        self.assertEqual(registry_calls, [("2026-05-13", 50)])
        self.assertEqual(legacy_calls, [])
        self.assertTrue(result["data_status"]["成交额排名"])
        self.assertEqual(result["results"]["turnover_rank"][0]["data_source"], "tushare.daily")
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.turnover_rank"], "tushare.daily")

    def test_collect_market_activity_sector_snapshot_request_bundle_uses_tushare_registry_for_sector_views(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()
        legacy_calls = []
        registry_calls = []

        tencent.get_sector_fund_flow = lambda flow_type="in", limit=50: legacy_calls.append(("tencent_flow", flow_type, limit)) or []

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-05-13",
            fetch_hot_plate=lambda: legacy_calls.append(("hot_plate", None)) or [],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: legacy_calls.append(
                ("sector_change", rank_type, target_date)
            )
            or [],
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: [],
            request_registry={
                "sector_hot_plates": lambda *, target_date, limit=20: registry_calls.append(("hot", target_date, limit))
                or [{"name": "人形机器人", "rank": 1, "data_source": "tushare.ths_hot"}],
                "concept_fund_flow": lambda *, target_date, hot_plates=None, limit=20: registry_calls.append(
                    ("concept_flow", target_date, tuple(item.get("name") for item in hot_plates or []), limit)
                )
                or {
                    "rows": [
                        {
                            "name": "人形机器人",
                            "net_inflow": 6.5,
                            "data_source": "tushare.ths_member+tushare.moneyflow",
                        }
                    ],
                    "provider": "tushare.ths_member+tushare.moneyflow",
                },
                "sector_fund_flow": lambda *, target_date, limit=50: registry_calls.append(("flow", target_date, limit))
                or {
                    "inflow": [{"name": "证券", "net_amount": 12.5, "data_source": "tushare.moneyflow_ind_ths"}],
                    "outflow": [{"name": "工业金属", "net_amount": -8.0, "data_source": "tushare.moneyflow_ind_ths"}],
                    "provider": "tushare.moneyflow_ind_ths",
                    "fallback_used": False,
                },
                "sector_change_rank": lambda *, target_date, rank_type="up", limit=10: registry_calls.append(
                    ("change", rank_type, target_date, limit)
                )
                or (
                    [{"name": "工业金属", "change_pct": 4.16, "data_source": "tushare.ths_daily"}]
                    if rank_type == "up"
                    else [{"name": "养殖业", "change_pct": -2.25, "data_source": "tushare.ths_daily"}]
                ),
                "turnover_rank": lambda *, target_date, limit=50: [],
            },
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-05-13", "2026-05-12"),
        )

        self.assertEqual(
            registry_calls,
            [
                ("hot", "2026-05-13", 20),
                ("flow", "2026-05-13", 50),
                ("concept_flow", "2026-05-13", ("人形机器人",), 20),
                ("change", "up", "2026-05-13", 10),
                ("change", "down", "2026-05-13", 10),
            ],
        )
        self.assertEqual(legacy_calls, [])
        self.assertEqual(result["results"]["hot_plates"][0]["data_source"], "tushare.ths_hot")
        self.assertEqual(result["results"]["sector_fund_flow"]["inflow"][0]["data_source"], "tushare.moneyflow_ind_ths")
        self.assertEqual(result["results"]["sector_fund_flow"]["inflow"][0]["zljlr"], 12.5)
        self.assertEqual(result["results"]["sector_fund_flow"]["outflow"][0]["zljlr"], -8.0)
        self.assertEqual(result["results"]["sector_fund_flow"]["provider"], "tushare.moneyflow_ind_ths")
        self.assertFalse(result["results"]["sector_fund_flow"]["fallback_used"])
        self.assertEqual(result["results"]["concept_fund_flow"]["rows"][0]["data_source"], "tushare.ths_member+tushare.moneyflow")
        self.assertEqual(result["results"]["sector_change_up"][0]["data_source"], "tushare.ths_daily")
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.hot_plates"], "tushare.ths_hot")
        self.assertEqual(provider_by_step["request.sector_fund_flow"], "tushare.moneyflow_ind_ths")
        self.assertEqual(provider_by_step["request.concept_fund_flow"], "tushare.ths_member+tushare.moneyflow")
        self.assertEqual(provider_by_step["request.sector_change_rank"], "tushare.ths_daily")

    def test_collect_market_activity_hot_rank_request_bundle_builds_integrated_from_primary_hot_rank(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()
        tencent.get_hot_stocks = lambda num=30: []

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-05-18",
            existing_results={"zt_pool": [{"代码": "000001", "所属行业": "电力"}]},
            fetch_ths_hot_stock=lambda num=30: [
                {"code": "000001", "name": "京能电力", "rank": 1, "data_source": "同花顺热榜"},
            ],
            get_integrated_hot_list=lambda limit=100: {},
            tencent=tencent,
            timer=timer,
            emit=emitted.append,
        )

        self.assertTrue(result["data_status"]["整合热榜"])
        self.assertTrue(result["step_status"]["整合热榜获取"])
        self.assertEqual(result["results"]["integrated_hot_list"][0]["name"], "京能电力")
        self.assertEqual(result["results"]["tag_distribution"], {"电力": 1})
        integrated_log = next(log for log in result["module_logs"] if log["step"] == "request.integrated_hot_rank")
        self.assertEqual(integrated_log["status"], "success")
        self.assertEqual(integrated_log["details"]["provider"], "primary_hot_rank.fallback")
        self.assertTrue(integrated_log["details"]["fallback_used"])

    def test_collect_market_activity_hot_rank_request_bundle_collects_xueqiu_factors(self):
        timer = _TimerStub()
        emitted = []
        argument_calls = []

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-05-22",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: [
                {"code": "300476", "full_code": "SZ300476", "name": "胜宏科技", "rank": 1, "data_source": "tushare.ths_hot"},
            ],
            get_integrated_hot_list=lambda limit=100: {},
            tencent=_TencentStub(),
            xueqiu_hot_rank_fetcher=lambda: {
                "provider": "xueqiu.hot_stock.type22",
                "status": "ok",
                "rows": [{"code": "300476", "full_code": "SZ300476", "name": "胜宏科技"}],
                "can_continue_report": True,
                "diagnostic_note": "",
            },
            xueqiu_argument_fetcher=lambda symbols: argument_calls.append(list(symbols))
            or {
                "provider": "xueqiu.hot_stock.argument",
                "status": "ok",
                "rows": [{"code": "300476", "full_code": "SZ300476", "argument": "AI服务器PCB"}],
                "can_continue_report": True,
                "diagnostic_note": "",
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["xueqiu_hot_rank_top100"][0]["full_code"], "SZ300476")
        self.assertEqual(result["results"]["xueqiu_hot_stock_arguments"][0]["argument"], "AI服务器PCB")
        self.assertEqual(argument_calls, [["SZ300476"]])
        self.assertTrue(result["data_status"]["雪球A股24小时热榜"])
        self.assertTrue(result["data_status"]["雪球热榜AI解释"])
        self.assertTrue(result["step_status"]["雪球A股24小时热榜获取"])
        self.assertTrue(result["step_status"]["雪球热榜AI解释获取"])
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.xueqiu_hot_rank"], "xueqiu.hot_stock.type22")
        self.assertEqual(provider_by_step["request.xueqiu_hot_stock_arguments"], "xueqiu.hot_stock.argument")

    def test_collect_market_activity_hot_rank_request_bundle_marks_xueqiu_factor_failure(self):
        timer = _TimerStub()
        emitted = []

        result = collect_market_activity_hot_rank_request_bundle(
            "2026-05-22",
            existing_results={},
            fetch_ths_hot_stock=lambda num=30: [
                {"code": "300476", "full_code": "SZ300476", "name": "胜宏科技", "rank": 1, "data_source": "tushare.ths_hot"},
            ],
            get_integrated_hot_list=lambda limit=100: {},
            tencent=_TencentStub(),
            xueqiu_hot_rank_fetcher=lambda: {
                "provider": "xueqiu.hot_stock.type22",
                "status": "error",
                "rows": [],
                "can_continue_report": False,
                "diagnostic_note": "雪球接口返回空，关键数据不完整，停止生成",
            },
            xueqiu_argument_fetcher=lambda symbols: {
                "provider": "xueqiu.hot_stock.argument",
                "status": "error",
                "rows": [],
                "can_continue_report": False,
                "diagnostic_note": "雪球接口返回空，关键数据不完整，停止生成",
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["xueqiu_hot_rank_top100"], [])
        self.assertEqual(result["results"]["xueqiu_hot_stock_arguments"], [])
        self.assertFalse(result["data_status"]["雪球A股24小时热榜"])
        self.assertFalse(result["data_status"]["雪球热榜AI解释"])
        self.assertFalse(result["step_status"]["雪球A股24小时热榜获取"])
        self.assertFalse(result["step_status"]["雪球热榜AI解释获取"])
        xueqiu_logs = [log for log in result["module_logs"] if log["step"].startswith("request.xueqiu")]
        self.assertEqual([log["status"] for log in xueqiu_logs], ["error", "error"])
        self.assertTrue(all("关键数据不完整，停止生成" in log["details"].get("error", "") for log in xueqiu_logs))

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

    def test_collect_market_activity_sector_snapshot_request_bundle_marks_historical_sector_flow_as_incomplete(self):
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

        self.assertFalse(result["data_status"]["行业资金流向"])
        self.assertFalse(result["step_status"]["行业资金流向获取"])
        self.assertFalse(result["data_status"]["板块涨幅排行"])
        self.assertFalse(result["data_status"]["板块跌幅排行"])
        self.assertFalse(result["step_status"]["板块涨跌幅排行获取"])
        self.assertNotIn("is_historical", result["results"]["sector_fund_flow"])
        self.assertTrue(any("关键数据不完整，停止生成" in message for message in emitted))

    def test_collect_market_activity_sector_snapshot_request_bundle_marks_historical_registry_empty_flow_as_incomplete(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-05-29",
            fetch_hot_plate=lambda: [],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: [],
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: [],
            request_registry={
                "sector_fund_flow": lambda *, target_date, limit=50: {
                    "inflow": [],
                    "outflow": [],
                    "provider": "tushare.moneyflow_ind_ths",
                    "fallback_used": False,
                },
            },
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-05-31", "2026-05-30"),
        )

        self.assertFalse(result["data_status"]["行业资金流向"])
        self.assertFalse(result["step_status"]["行业资金流向获取"])
        self.assertFalse(result["data_status"]["板块涨幅排行"])
        self.assertFalse(result["data_status"]["板块跌幅排行"])
        self.assertFalse(result["step_status"]["板块涨跌幅排行获取"])
        self.assertNotIn("is_historical", result["results"]["sector_fund_flow"])
        self.assertTrue(any("关键数据不完整，停止生成" in message for message in emitted))

    def test_collect_market_activity_sector_snapshot_request_bundle_derives_sector_change_from_fund_flow(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-05-27",
            fetch_hot_plate=lambda: [],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: [],
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: [],
            request_registry={
                "sector_fund_flow": lambda *, target_date, limit=50: {
                    "inflow": [
                        {"name": "电力", "net_amount": 22.0, "change_pct": 0.95, "data_source": "tushare.moneyflow_ind_ths"},
                        {"name": "白酒", "net_amount": 6.0, "change_pct": 3.37, "data_source": "tushare.moneyflow_ind_ths"},
                    ],
                    "outflow": [
                        {"name": "工业金属", "net_amount": -59.0, "change_pct": -3.68, "data_source": "tushare.moneyflow_ind_ths"},
                        {"name": "贵金属", "net_amount": -37.0, "change_pct": -5.59, "data_source": "tushare.moneyflow_ind_ths"},
                    ],
                    "provider": "tushare.moneyflow_ind_ths",
                }
            },
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-05-27", "2026-05-26"),
        )

        self.assertEqual([item["name"] for item in result["results"]["sector_change_up"][:2]], ["白酒", "电力"])
        self.assertEqual([item["name"] for item in result["results"]["sector_change_down"][:2]], ["贵金属", "工业金属"])
        self.assertEqual(result["results"]["sector_change_up"][0]["data_source"], "tushare.moneyflow_ind_ths.derived_change")
        self.assertEqual(result["results"]["sector_fund_flow"]["inflow"][0]["zljlr"], 22.0)
        self.assertEqual(result["results"]["sector_fund_flow"]["inflow"][0]["zdf"], 0.95)
        self.assertEqual(result["results"]["sector_fund_flow"]["outflow"][0]["zljlr"], -59.0)
        self.assertEqual(result["results"]["sector_fund_flow"]["outflow"][0]["zdf"], -3.68)
        self.assertTrue(result["data_status"]["板块涨幅排行"])
        self.assertTrue(result["data_status"]["板块跌幅排行"])
        self.assertTrue(result["step_status"]["板块涨跌幅排行获取"])
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.sector_change_rank"], "tushare.moneyflow_ind_ths.derived_change")

    def test_collect_market_activity_sector_snapshot_request_bundle_uses_tencent_when_registry_flow_empty(self):
        timer = _TimerStub()
        emitted = []
        tencent = _TencentStub()
        tencent.get_sector_fund_flow = lambda flow_type="in", limit=50: (
            [{"name": "电力", "zljlr": 18.0, "zdf": 2.1, "cje": 3200000.0}]
            if flow_type == "in"
            else [{"name": "半导体", "zljlr": -12.0, "zdf": -1.8, "cje": 2100000.0}]
        )

        result = collect_market_activity_sector_snapshot_request_bundle(
            "2026-05-28",
            fetch_hot_plate=lambda: [],
            tencent=tencent,
            get_sector_change_from_iwencai=lambda rank_type="up", limit=10, target_date=None: [],
            get_turnover_rank_from_iwencai=lambda limit=50, target_date=None: [],
            request_registry={
                "sector_fund_flow": lambda *, target_date, limit=50: {
                    "inflow": [],
                    "outflow": [],
                    "provider": "legacy.sector_fund_flow",
                    "fallback_used": True,
                }
            },
            timer=timer,
            emit=emitted.append,
            current_dates=("2026-05-28", "2026-05-27"),
        )

        self.assertEqual(result["results"]["sector_fund_flow"]["inflow"][0]["name"], "电力")
        self.assertEqual(result["results"]["sector_fund_flow"]["outflow"][0]["name"], "半导体")
        self.assertTrue(result["data_status"]["行业资金流向"])
        self.assertTrue(result["step_status"]["行业资金流向获取"])
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.sector_fund_flow"], "tencent.get_sector_fund_flow")

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

    def test_lianban_snapshot_keeps_first_board_for_spread_view(self):
        timer = _TimerStub()
        limit_up_df = _FrameStub(
            [
                {
                    "代码": "000988",
                    "名称": "华工科技",
                    "连板数": 1,
                    "涨跌幅": 10.0,
                    "成交额": 88.8,
                    "所属行业": "光通信",
                    "涨停统计": "光模块+CPO",
                    "开盘价": 137.53,
                    "最新价": 147.38,
                    "最高价": 147.38,
                    "最低价": 137.03,
                    "首次封板时间": "092500",
                }
            ]
        )

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-18",
            limit_up_df=limit_up_df,
            existing_results={},
            fetch_lhb_rows=lambda target_date: [],
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(result["results"]["lianban_data"][0]["code"], "000988")
        self.assertEqual(result["results"]["lianban_data"][0]["lianban_days"], 1)
        self.assertEqual(result["results"]["lianban_data"][0]["first_limit_time"], "09:25:00")

    def test_collect_market_activity_capital_snapshot_request_bundle_logs_limit_up_provider_for_lianban(self):
        timer = _TimerStub()
        emitted = []

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-13",
            limit_up_df=_FrameStub([]),
            existing_results={},
            fetch_lhb_rows=lambda target_date: [],
            limit_up_provider="tushare.limit_list_ths",
            timer=timer,
            emit=emitted.append,
        )

        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.lianban_snapshot"], "tushare.limit_list_ths")
        self.assertTrue(result["step_status"]["连板梯队提取"])

    def test_lianban_snapshot_uses_xuangubao_limit_up_reason_when_available(self):
        timer = _TimerStub()
        limit_up_df = _FrameStub(
            [
                {
                    "代码": "600676",
                    "名称": "交运股份",
                    "连板数": 2,
                    "涨跌幅": 10.0,
                    "成交额": 45.6,
                    "所属行业": "交通运输",
                    "涨停统计": "2连板",
                    "开盘价": 7.8,
                    "最新价": 8.09,
                    "最高价": 8.09,
                    "最低价": 7.8,
                    "首次封板时间": "093000",
                }
            ]
        )

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-18",
            limit_up_df=limit_up_df,
            existing_results={
                "xuangubao_data": {
                    "xuangubao_limit_up_reasons": [
                        {
                            "symbol": "600676.SS",
                            "stock_reason": "拟置入文旅体育资产",
                            "related_plates": [{"plate_name": "资产重组"}],
                            "limit_up_days": 2,
                        }
                    ]
                }
            },
            fetch_lhb_rows=lambda target_date: [],
            timer=timer,
            emit=lambda message: None,
        )

        lianban = result["results"]["lianban_data"][0]
        self.assertEqual(lianban["reason"], "拟置入文旅体育资产")
        self.assertEqual(lianban["xuangubao_stock_reason"], "拟置入文旅体育资产")
        self.assertEqual(lianban["xuangubao_related_plate_names"], ["资产重组"])

    def test_lianban_snapshot_replaces_market_board_sector_from_xuangubao_plate(self):
        timer = _TimerStub()
        limit_up_df = _FrameStub(
            [
                {
                    "代码": "000988",
                    "名称": "华工科技",
                    "连板数": 1,
                    "涨跌幅": 10.0,
                    "成交额": 88.8,
                    "所属行业": "HS",
                    "涨停统计": "首板",
                    "开盘价": 137.53,
                    "最新价": 147.38,
                    "最高价": 147.38,
                    "最低价": 137.03,
                    "首次封板时间": "092500",
                }
            ]
        )

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-18",
            limit_up_df=limit_up_df,
            existing_results={
                "xuangubao_data": {
                    "xuangubao_limit_up_reasons": [
                        {
                            "symbol": "000988.SZ",
                            "stock_reason": "算力光模块方向走强",
                            "related_plates": [{"plate_name": "光通信"}],
                        }
                    ]
                }
            },
            fetch_lhb_rows=lambda target_date: [],
            timer=timer,
            emit=lambda message: None,
        )

        lianban = result["results"]["lianban_data"][0]
        self.assertEqual(lianban["sector"], "光通信")
        self.assertNotEqual(lianban["sector"], "HS")

    def test_lianban_snapshot_infers_sector_from_limit_reason_when_pool_sector_missing(self):
        timer = _TimerStub()
        limit_up_df = _FrameStub(
            [
                {
                    "代码": "000417",
                    "名称": "合百集团",
                    "连板数": 1,
                    "涨跌幅": 10.0,
                    "成交额": 23.0,
                    "所属行业": "未知",
                    "涨停统计": "间接投资长鑫科技+合肥国资+区域零售",
                    "开盘价": 7.87,
                    "最新价": 7.87,
                    "最高价": 7.87,
                    "最低价": 7.87,
                    "首次封板时间": "092500",
                },
                {
                    "代码": "001259",
                    "名称": "利仁科技",
                    "连板数": 1,
                    "涨跌幅": 10.0,
                    "成交额": 18.0,
                    "所属行业": "待补充板块",
                    "涨停统计": "股份转让+小家电+露营经济",
                    "开盘价": 66.55,
                    "最新价": 66.55,
                    "最高价": 66.55,
                    "最低价": 63.01,
                    "首次封板时间": "092500",
                },
            ]
        )

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-18",
            limit_up_df=limit_up_df,
            existing_results={},
            fetch_lhb_rows=lambda target_date: [],
            timer=timer,
            emit=lambda message: None,
        )

        by_code = {item["code"]: item for item in result["results"]["lianban_data"]}
        self.assertEqual(by_code["000417"]["sector"], "国产芯片")
        self.assertEqual(by_code["001259"]["sector"], "家用电器")
        self.assertNotEqual(by_code["001259"]["sector"], "待补充板块")

    def test_collect_market_activity_capital_snapshot_request_bundle_uses_tushare_registry_before_finshare(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []
        registry_calls = []

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-13",
            limit_up_df=_FrameStub([]),
            existing_results={"zt_pool": [{"代码": "000001", "所属行业": "银行"}]},
            fetch_lhb_rows=lambda target_date: legacy_calls.append(target_date) or [],
            request_registry={
                "lhb_snapshot": lambda *, target_date: registry_calls.append(target_date)
                or {
                    "lhb_net_buy_top10": [
                        {
                            "rank": 1,
                            "code": "000001",
                            "name": "平安银行",
                            "net_buy_amount_yi": 5.0,
                            "change_pct": 10.0,
                            "sector": "未知",
                            "data_source": "tushare.top_list",
                        }
                    ],
                    "lhb_net_sell_top10": [],
                    "lhb_analysis": [{"代码": "000001", "data_source": "tushare.top_list"}],
                    "provider": "tushare.top_list",
                    "fallback_used": False,
                },
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(registry_calls, ["2026-05-13"])
        self.assertEqual(legacy_calls, [])
        self.assertEqual(result["results"]["lhb_net_buy_top10"][0]["code"], "000001")
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.lhb_snapshot"], "tushare.top_list")

    def test_collect_market_activity_capital_snapshot_request_bundle_keeps_lhb_inst_detail(self):
        timer = _TimerStub()

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-13",
            limit_up_df=_FrameStub([]),
            existing_results={},
            fetch_lhb_rows=lambda target_date: [],
            request_registry={
                "lhb_snapshot": lambda *, target_date: {
                    "lhb_net_buy_top10": [
                        {
                            "rank": 1,
                            "code": "000001",
                            "name": "平安银行",
                            "net_buy_amount_yi": 3.2,
                            "sector": "银行",
                        }
                    ],
                    "lhb_net_sell_top10": [],
                    "lhb_analysis": [{"代码": "000001", "data_source": "tushare.top_list"}],
                    "lhb_inst_detail": [
                        {
                            "trade_date": "2026-05-13",
                            "code": "000001",
                            "exalter": "机构专用",
                            "seat_type": "机构",
                            "net_buy_yi": 0.7,
                            "data_source": "tushare.top_inst",
                        }
                    ],
                    "lhb_inst_detail_status": "available",
                    "provider": "tushare.top_list+top_inst",
                    "fallback_used": False,
                },
            },
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(result["results"]["lhb_inst_detail"][0]["exalter"], "机构专用")
        self.assertEqual(result["results"]["lhb_inst_detail_status"], "available")
        log = next(item for item in result["module_logs"] if item["step"] == "request.lhb_snapshot")
        self.assertIn("lhb_inst_detail", log["details"]["target_keys"])
        self.assertEqual(log["details"]["inst_detail_count"], 1)

    def test_collect_market_activity_capital_snapshot_request_bundle_marks_empty_lhb_as_degraded(self):
        timer = _TimerStub()
        emitted = []

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-18",
            limit_up_df=_FrameStub([]),
            existing_results={},
            fetch_lhb_rows=lambda target_date: [],
            request_registry={
                "lhb_snapshot": lambda *, target_date: {
                    "lhb_net_buy_top10": [],
                    "lhb_net_sell_top10": [],
                    "lhb_analysis": [],
                    "provider": "legacy.lhb_snapshot",
                    "fallback_used": True,
                },
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertFalse(result["step_status"]["龙虎榜数据获取"])
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        status_by_step = {log["step"]: log["status"] for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.lhb_snapshot"], "legacy.lhb_snapshot")
        self.assertEqual(status_by_step["request.lhb_snapshot"], "degraded")
        self.assertTrue(any("龙虎榜" in line and "空" in line for line in emitted))

    def test_lhb_snapshot_replaces_unknown_and_board_sector_from_xuangubao_context(self):
        timer = _TimerStub()

        result = collect_market_activity_capital_snapshot_request_bundle(
            "2026-05-18",
            limit_up_df=_FrameStub([]),
            existing_results={
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
                }
            },
            fetch_lhb_rows=lambda target_date: [],
            request_registry={
                "lhb_snapshot": lambda *, target_date: {
                    "lhb_net_buy_top10": [
                        {"rank": 1, "code": "000988", "name": "华工科技", "net_buy_amount_yi": 16.99, "sector": "HS"},
                        {"rank": 2, "code": "002518", "name": "科士达", "net_buy_amount_yi": 4.92, "sector": "未知"},
                    ],
                    "lhb_net_sell_top10": [],
                    "lhb_analysis": [],
                    "provider": "tushare.top_list",
                },
            },
            timer=timer,
            emit=lambda message: None,
        )

        rows = result["results"]["lhb_net_buy_top10"]
        self.assertEqual(rows[0]["sector"], "光通信")
        self.assertEqual(rows[1]["sector"], "算力")

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

    def test_stock_quote_request_includes_and_backfills_all_report_stock_sources(self):
        timer = _TimerStub()
        captured_codes = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "hot_rank_top30": [],
                "hot_rank_top50": [
                    {"rank": 46, "code": "sh600255", "name": "鑫科材料", "rate": 12155000},
                ],
                "lhb_net_buy_top10": [],
                "lhb_net_sell_top10": [],
                "lianban_data": [],
                "display_observation_candidates": [{"code": "001896", "name": "豫能控股"}],
            },
            fetch_stock_batch_info=lambda codes: (
                captured_codes.extend(sorted(codes))
                or {
                    "001896": {
                        "name": "豫能控股",
                        "change_pct": -1.41,
                        "high": 21.50,
                        "low": 19.00,
                        "open": 19.87,
                        "close": 19.60,
                        "zt_status": "正常",
                    },
                    "600255": {
                        "name": "鑫科材料",
                        "change_pct": 2.67,
                        "high": 4.83,
                        "low": 4.30,
                        "open": 4.35,
                        "close": 4.61,
                        "zt_status": "正常",
                    }
                }
            ),
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(captured_codes, ["001896", "600255"])
        self.assertEqual(result["results"]["stock_full_info"]["001896"]["close"], 19.60)
        self.assertEqual(result["results"]["stock_full_info"]["600255"]["close"], 4.61)
        self.assertEqual(result["results"]["hot_rank_top50"][0]["change_pct"], 2.67)
        self.assertEqual(result["results"]["hot_rank_top50"][0]["high"], 4.83)
        self.assertEqual(result["results"]["hot_rank_top50"][0]["close"], 4.61)
        self.assertEqual(result["results"]["display_observation_candidates"][0]["change_pct"], -1.41)
        self.assertEqual(result["results"]["display_observation_candidates"][0]["close"], 19.60)

    def test_stock_quote_request_fetches_single_non_hot_report_stock(self):
        timer = _TimerStub()
        captured_codes = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "selected_position_candidate": {"code": "001896", "name": "豫能控股"},
            },
            fetch_stock_batch_info=lambda codes: (
                captured_codes.extend(sorted(codes))
                or {
                    "001896": {
                        "name": "豫能控股",
                        "change_pct": -1.41,
                        "high": 21.50,
                        "low": 19.00,
                        "open": 19.87,
                        "close": 19.60,
                    }
                }
            ),
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(captured_codes, ["001896"])
        self.assertEqual(result["results"]["selected_position_candidate"]["change_pct"], -1.41)
        self.assertEqual(result["results"]["selected_position_candidate"]["close"], 19.60)

    def test_stock_quote_request_backfills_deep_execution_candidate_sources(self):
        timer = _TimerStub()
        captured_codes = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "execution_stage_context": {
                    "watch_anchor": {"code": "001896", "name": "豫能控股"},
                    "candidate_quality_panel_fields": {
                        "backup_candidate": {"code": "600255", "name": "鑫科材料"},
                    },
                },
            },
            fetch_stock_batch_info=lambda codes: (
                captured_codes.extend(sorted(codes))
                or {
                    "001896": {
                        "name": "豫能控股",
                        "change_pct": -1.41,
                        "high": 21.50,
                        "low": 19.00,
                        "open": 19.87,
                        "close": 19.60,
                    },
                    "600255": {
                        "name": "鑫科材料",
                        "change_pct": 2.67,
                        "high": 4.83,
                        "low": 4.30,
                        "open": 4.35,
                        "close": 4.61,
                    },
                }
            ),
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(captured_codes, ["001896", "600255"])
        stage = result["results"]["execution_stage_context"]
        self.assertEqual(stage["watch_anchor"]["change_pct"], -1.41)
        self.assertEqual(stage["watch_anchor"]["close"], 19.60)
        self.assertEqual(stage["candidate_quality_panel_fields"]["backup_candidate"]["change_pct"], 2.67)
        self.assertEqual(stage["candidate_quality_panel_fields"]["backup_candidate"]["close"], 4.61)

    def test_stock_quote_request_preserves_existing_quotes_and_fetches_only_incomplete_codes(self):
        timer = _TimerStub()
        captured_codes = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "stock_full_info": {
                    "001896": {
                        "name": "豫能控股",
                        "change_pct": 0.0,
                        "high": 21.50,
                        "low": 19.00,
                        "open": 19.87,
                        "close": 19.60,
                    },
                    "600255": {
                        "name": "鑫科材料",
                        "change_pct": 0.0,
                        "high": 0,
                        "low": 4.30,
                        "open": 4.35,
                        "close": 4.61,
                    },
                },
                "selected_position_candidate": {"code": "001896", "name": "豫能控股"},
                "watch_anchor": {"code": "600255", "name": "鑫科材料"},
            },
            fetch_stock_batch_info=lambda codes: (
                captured_codes.extend(sorted(codes))
                or {
                    "600255": {
                        "name": "鑫科材料",
                        "change_pct": 2.67,
                        "high": 4.83,
                        "low": 4.30,
                        "open": 4.35,
                        "close": 4.61,
                    },
                }
            ),
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(captured_codes, ["600255"])
        self.assertEqual(result["results"]["stock_full_info"]["001896"]["change_pct"], 0.0)
        self.assertEqual(result["results"]["selected_position_candidate"]["close"], 19.60)
        self.assertEqual(result["results"]["stock_full_info"]["600255"]["high"], 4.83)
        self.assertEqual(result["results"]["watch_anchor"]["change_pct"], 2.67)

    def test_collect_market_activity_stock_quote_request_bundle_uses_tushare_before_tencent(self):
        timer = _TimerStub()
        emitted = []
        tushare_calls = []
        tencent_calls = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "hot_rank_top30": [{"code": "sz000001"}],
                "lhb_net_buy_top10": [{"code": "000001", "name": ""}],
            },
            fetch_stock_batch_info=lambda codes: tencent_calls.append(codes) or {},
            fetch_tushare_stock_batch_info=lambda codes, target_date=None: (
                tushare_calls.append((sorted(codes), target_date))
                or {
                    "000001": {
                        "name": "平安银行",
                        "change_pct": 5.0,
                        "high": 11.0,
                        "low": 9.8,
                        "open": 10.0,
                        "close": 10.5,
                        "zt_status": "正常",
                        "data_source": "tushare.daily",
                        "trade_date": target_date,
                    }
                }
            ),
            target_date="2026-06-09",
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(tushare_calls, [(["000001"], "2026-06-09")])
        self.assertEqual(tencent_calls, [])
        self.assertEqual(result["results"]["stock_full_info"]["000001"]["name"], "平安银行")
        self.assertEqual(result["results"]["lhb_net_buy_top10"][0]["name"], "平安银行")
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.stock_quotes"], "tushare.daily")

    def test_collect_market_activity_stock_quote_request_bundle_backfills_tushare_gaps_with_tencent(self):
        timer = _TimerStub()
        tencent_codes = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "lhb_net_buy_top10": [
                    {"code": "000001", "name": "", "sector": "银行"},
                    {"code": "688409", "name": "富创精密", "sector": "半导体"},
                ],
            },
            fetch_stock_batch_info=lambda codes: tencent_codes.extend(sorted(codes)) or {
                "688409": {
                    "name": "富创精密",
                    "change_pct": 4.67,
                    "high": 176.8,
                    "low": 155.74,
                    "open": 158.09,
                    "close": 169.85,
                    "data_source": "tencent.qt",
                }
            },
            fetch_tushare_stock_batch_info=lambda codes, target_date=None: {
                "000001": {
                    "name": "平安银行",
                    "change_pct": 5.0,
                    "high": 11.0,
                    "low": 9.8,
                    "open": 10.0,
                    "close": 10.5,
                    "data_source": "tushare.daily",
                    "trade_date": target_date,
                }
            },
            target_date="2026-06-09",
            current_date="2026-06-09",
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(tencent_codes, ["688409"])
        stock_full_info = result["results"]["stock_full_info"]
        self.assertEqual(stock_full_info["000001"]["data_source"], "tushare.daily")
        self.assertEqual(stock_full_info["688409"]["data_source"], "tencent.qt")
        self.assertEqual(result["results"]["lhb_net_buy_top10"][1]["high"], 176.8)
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.stock_quotes"], "tushare.daily+tencent.get_stock_batch_info")

    def test_stock_quote_request_does_not_use_realtime_tencent_for_historical_target_date(self):
        timer = _TimerStub()
        tencent_calls = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "selected_position_candidate": {"code": "001896", "name": "豫能控股"},
            },
            fetch_stock_batch_info=lambda codes: tencent_calls.append(sorted(codes)) or {
                "001896": {
                    "name": "豫能控股",
                    "change_pct": 8.88,
                    "high": 22.00,
                    "low": 20.00,
                    "open": 20.50,
                    "close": 21.80,
                    "data_source": "tencent.qt",
                }
            },
            fetch_tushare_stock_batch_info=lambda codes, target_date=None: {},
            target_date="2026-06-08",
            current_date="2026-06-09",
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(tencent_calls, [])
        self.assertEqual(result["results"]["stock_full_info"], {})
        self.assertNotIn("selected_position_candidate", result["results"])
        by_step = {log["step"]: log for log in result["module_logs"]}
        self.assertEqual(by_step["request.stock_quotes"]["status"], "degraded")
        self.assertFalse(by_step["request.stock_quotes"]["details"]["realtime_quote_allowed"])

    def test_stock_quote_request_treats_undated_tushare_rows_as_incomplete_for_historical_target(self):
        timer = _TimerStub()
        tencent_calls = []

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "selected_position_candidate": {"code": "001896", "name": "豫能控股"},
            },
            fetch_stock_batch_info=lambda codes: tencent_calls.append(sorted(codes)) or {},
            fetch_tushare_stock_batch_info=lambda codes, target_date=None: {
                "001896": {
                    "name": "豫能控股",
                    "change_pct": -1.41,
                    "high": 21.50,
                    "low": 19.00,
                    "open": 19.87,
                    "close": 19.60,
                    "data_source": "tushare.daily",
                }
            },
            target_date="2026-06-08",
            current_date="2026-06-09",
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(tencent_calls, [])
        self.assertEqual(result["results"]["stock_full_info"], {})
        self.assertNotIn("selected_position_candidate", result["results"])
        by_step = {log["step"]: log for log in result["module_logs"]}
        self.assertEqual(by_step["request.stock_quotes"]["status"], "degraded")
        self.assertEqual(by_step["request.stock_quotes"]["details"]["missing_count"], 1)

    def test_stock_quote_request_backfills_lhb_sector_from_tushare_industry(self):
        timer = _TimerStub()

        result = collect_market_activity_stock_quote_request_bundle(
            existing_results={
                "lhb_net_buy_top10": [
                    {"rank": 1, "code": "000988", "name": "华工科技", "sector": "HS"},
                    {"rank": 2, "code": "688409", "name": "富创精密", "sector": "未知"},
                ],
                "lhb_net_sell_top10": [],
            },
            fetch_stock_batch_info=lambda codes: {},
            fetch_tushare_stock_batch_info=lambda codes, target_date=None: {
                "000988": {
                    "name": "华工科技",
                    "industry": "通信设备",
                    "change_pct": 10.0,
                    "high": 12.0,
                    "low": 10.0,
                    "open": 10.5,
                    "close": 11.8,
                    "trade_date": target_date,
                },
                "688409": {
                    "name": "富创精密",
                    "所属行业": "半导体",
                    "change_pct": 4.67,
                    "high": 176.8,
                    "low": 155.74,
                    "open": 158.09,
                    "close": 169.85,
                    "trade_date": target_date,
                },
            },
            target_date="2026-06-09",
            timer=timer,
            emit=lambda message: None,
        )

        rows = result["results"]["lhb_net_buy_top10"]
        self.assertEqual(rows[0]["sector"], "通信设备")
        self.assertEqual(rows[1]["sector"], "半导体")


if __name__ == "__main__":
    unittest.main()
