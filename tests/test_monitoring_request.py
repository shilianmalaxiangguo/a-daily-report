import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.monitoring.request import collect_monitoring_request_bundle


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.1, 0.2


class _AnalyzerStub:
    def fetch_xuangubao_data(self):
        return {"xuangubao_news": [{"title": "军工异动"}]}


class _PlateOnlyAnalyzerStub:
    def fetch_xuangubao_data(self):
        return {
            "xuangubao_news": [],
            "xuangubao_plates": [{"name": "国产芯片", "description": "长鑫存储更新招股说明书"}],
            "diagnostics": {"newsflash": "非法的token"},
        }


class _LimitUpReasonOnlyAnalyzerStub:
    def fetch_xuangubao_data(self):
        return {
            "xuangubao_news": [],
            "xuangubao_plates": [],
            "xuangubao_limit_up_reasons": [
                {"symbol": "600676.SS", "name": "交运股份", "stock_reason": "拟置入文旅体育资产"}
            ],
        }


class _TargetDateAnalyzerStub:
    def __init__(self):
        self.target_date = None

    def fetch_xuangubao_data(self, target_date=None):
        self.target_date = target_date
        return {"xuangubao_news": [{"title": f"{target_date} 盘中异动"}]}


class MonitoringRequestTest(unittest.TestCase):
    def test_collect_monitoring_request_bundle_builds_monitoring_payloads(self):
        timer = _TimerStub()
        emitted = []

        result = collect_monitoring_request_bundle(
            "2026-04-22",
            analyzer_factory=_AnalyzerStub,
            fetch_wanzhu_top10=lambda target_date: [{"code": "000001", "name": "军工一号"}],
            fetch_exchange_monitor_payload=lambda: {
                "data": [
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "max_days": 3,
                        "deviation_value": 8.5,
                        "is_today": True,
                        "is_nextday": False,
                        "change_rate_target": 5.0,
                    },
                    {
                        "code": "000002",
                        "name": "消费一号",
                        "max_days": 2,
                        "deviation_value": 6.5,
                        "is_today": False,
                        "is_nextday": True,
                        "change_rate_target": 4.0,
                    },
                ]
            },
            fetch_stock_batch_info=lambda codes: {"000001": {"change_pct": 6.2}},
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["xuangubao_data"]["xuangubao_news"][0]["title"], "军工异动")
        self.assertEqual(result["results"]["wanzhu_top10"][0]["code"], "000001")
        self.assertEqual(result["results"]["exchange_monitor_today"][0]["actual_change_pct"], 6.2)
        self.assertTrue(result["results"]["exchange_monitor_today"][0]["is_triggered"])
        self.assertEqual(result["results"]["exchange_monitor_nextday"][0]["code"], "000002")
        self.assertTrue(result["data_status"]["选股通盘中异动"])
        self.assertTrue(result["data_status"]["顽主杯热门前十"])
        self.assertTrue(result["step_status"]["选股通盘中异动获取"])
        self.assertTrue(result["step_status"]["顽主杯热门前十获取"])
        self.assertTrue(any("异动检测" in line for line in emitted))

    def test_xuangubao_plates_are_success_when_newsflash_requires_token(self):
        timer = _TimerStub()

        result = collect_monitoring_request_bundle(
            "2026-04-22",
            analyzer_factory=_PlateOnlyAnalyzerStub,
            fetch_wanzhu_top10=lambda target_date: [],
            fetch_exchange_monitor_payload=lambda: {"data": []},
            fetch_stock_batch_info=lambda codes: {},
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(result["results"]["xuangubao_data"]["xuangubao_plates"][0]["name"], "国产芯片")
        self.assertTrue(result["data_status"]["选股通盘中异动"])
        self.assertTrue(result["step_status"]["选股通盘中异动获取"])
        details_by_step = {
            log.get("step"): (log.get("details") or {})
            for log in result.get("module_logs", [])
        }
        self.assertEqual(details_by_step["request.xuangubao"]["plate_count"], 1)
        self.assertEqual(details_by_step["request.xuangubao"]["news_count"], 0)
        self.assertEqual(details_by_step["request.xuangubao"]["diagnostic_note"], "newsflash=非法的token")

    def test_xuangubao_fetch_receives_target_date_for_newsflash_date_window(self):
        timer = _TimerStub()
        analyzer = _TargetDateAnalyzerStub()

        result = collect_monitoring_request_bundle(
            "2026-05-18",
            analyzer_factory=lambda: analyzer,
            fetch_wanzhu_top10=lambda target_date: [],
            fetch_exchange_monitor_payload=lambda: {"data": []},
            fetch_stock_batch_info=lambda codes: {},
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(analyzer.target_date, "2026-05-18")
        self.assertEqual(result["results"]["xuangubao_data"]["xuangubao_news"][0]["title"], "2026-05-18 盘中异动")

    def test_xuangubao_limit_up_reasons_count_as_success(self):
        timer = _TimerStub()

        result = collect_monitoring_request_bundle(
            "2026-04-22",
            analyzer_factory=_LimitUpReasonOnlyAnalyzerStub,
            fetch_wanzhu_top10=lambda target_date: [],
            fetch_exchange_monitor_payload=lambda: {"data": []},
            fetch_stock_batch_info=lambda codes: {},
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(result["results"]["xuangubao_data"]["xuangubao_limit_up_reasons"][0]["name"], "交运股份")
        self.assertTrue(result["data_status"]["选股通盘中异动"])
        self.assertTrue(result["step_status"]["选股通盘中异动获取"])
        details_by_step = {
            log.get("step"): (log.get("details") or {})
            for log in result.get("module_logs", [])
        }
        self.assertEqual(details_by_step["request.xuangubao"]["limit_up_reason_count"], 1)

    def test_exchange_monitor_uses_tushare_quotes_before_tencent_fallback(self):
        timer = _TimerStub()
        tencent_calls = []

        result = collect_monitoring_request_bundle(
            "2026-04-22",
            analyzer_factory=_AnalyzerStub,
            fetch_wanzhu_top10=lambda target_date: [],
            fetch_exchange_monitor_payload=lambda: {
                "data": [
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "max_days": 3,
                        "deviation_value": 8.5,
                        "is_today": True,
                        "is_nextday": False,
                        "change_rate_target": 5.0,
                    }
                ]
            },
            fetch_stock_batch_info=lambda codes: tencent_calls.append(codes) or {"000001": {"change_pct": 1.0}},
            fetch_tushare_stock_batch_info=lambda codes: {"000001": {"change_pct": 6.2, "data_source": "tushare.daily"}},
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(tencent_calls, [])
        self.assertEqual(result["results"]["exchange_monitor_today"][0]["actual_change_pct"], 6.2)
        self.assertTrue(result["results"]["exchange_monitor_today"][0]["is_triggered"])
        provider_by_step = {
            log.get("step"): (log.get("details") or {})
            for log in result.get("module_logs", [])
        }
        self.assertEqual(provider_by_step["request.exchange_monitor"]["provider"], "quicktiny.exchange_monitor")
        self.assertEqual(provider_by_step["request.exchange_monitor"]["quote_provider"], "tushare.daily")
        self.assertFalse(provider_by_step["request.exchange_monitor"]["quote_fallback_used"])

    def test_wanzhu_top10_enriches_quote_fields_from_tushare(self):
        timer = _TimerStub()

        result = collect_monitoring_request_bundle(
            "2026-04-22",
            analyzer_factory=_AnalyzerStub,
            fetch_wanzhu_top10=lambda target_date: [{"code": "000001", "name": "军工一号", "rank": 1}],
            fetch_exchange_monitor_payload=lambda: {"data": []},
            fetch_stock_batch_info=lambda codes: {},
            fetch_tushare_stock_batch_info=lambda codes: {
                "000001": {
                    "change_pct": 6.2,
                    "close": 12.34,
                    "turnover": 18.5,
                    "data_source": "tushare.daily",
                }
            },
            timer=timer,
            emit=lambda message: None,
        )

        row = result["results"]["wanzhu_top10"][0]
        self.assertEqual(row["change_pct"], 6.2)
        self.assertEqual(row["close"], 12.34)
        self.assertEqual(row["turnover"], 18.5)
        self.assertEqual(row["quote_source"], "tushare.daily")
        details_by_step = {
            log.get("step"): (log.get("details") or {})
            for log in result.get("module_logs", [])
        }
        self.assertEqual(details_by_step["request.wanzhu_top10"]["provider"], "AShareDataCollector.get_wanzhu_top10")
        self.assertEqual(details_by_step["request.wanzhu_top10"]["quote_provider"], "tushare.daily")
        self.assertFalse(details_by_step["request.wanzhu_top10"]["quote_fallback_used"])

    def test_exchange_monitor_falls_back_to_tencent_when_tushare_quotes_empty(self):
        timer = _TimerStub()
        tencent_calls = []

        result = collect_monitoring_request_bundle(
            "2026-04-22",
            analyzer_factory=_AnalyzerStub,
            fetch_wanzhu_top10=lambda target_date: [],
            fetch_exchange_monitor_payload=lambda: {
                "data": [
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "max_days": 3,
                        "deviation_value": 8.5,
                        "is_today": True,
                        "is_nextday": False,
                        "change_rate_target": 5.0,
                    }
                ]
            },
            fetch_stock_batch_info=lambda codes: tencent_calls.append(codes) or {"000001": {"change_pct": 6.2}},
            fetch_tushare_stock_batch_info=lambda codes: {},
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(tencent_calls, [["000001"]])
        self.assertEqual(result["results"]["exchange_monitor_today"][0]["actual_change_pct"], 6.2)
        self.assertTrue(result["results"]["exchange_monitor_today"][0]["is_triggered"])
        details_by_step = {
            log.get("step"): (log.get("details") or {})
            for log in result.get("module_logs", [])
        }
        self.assertEqual(details_by_step["request.exchange_monitor"]["quote_provider"], "tencent.get_stock_batch_info")
        self.assertTrue(details_by_step["request.exchange_monitor"]["quote_fallback_used"])


if __name__ == "__main__":
    unittest.main()
