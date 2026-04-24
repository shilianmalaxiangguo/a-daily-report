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


if __name__ == "__main__":
    unittest.main()
