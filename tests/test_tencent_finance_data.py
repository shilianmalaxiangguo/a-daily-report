import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class TencentFinanceDataTest(unittest.TestCase):
    def test_get_stock_batch_info_exists_even_when_legacy_class_lacks_it(self):
        module = __import__("tencent_finance_data", fromlist=["tencent_finance_data"])

        self.assertTrue(hasattr(module.TencentFinanceData(), "get_stock_batch_info"))

    def test_get_stock_batch_info_parses_tencent_quote_lines(self):
        module = __import__("tencent_finance_data", fromlist=["tencent_finance_data"])

        class _Response:
            text = (
                'v_sz000001="51~平安银行~000001~12.34~11.90~12.00~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~3.70~12.80~11.70~0~0~1850000";'
            )

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=0):
                self.url = url
                return _Response()

        data = module.TencentFinanceData()
        data.session = _Session()

        result = data.get_stock_batch_info(["000001"])

        self.assertEqual(result["000001"]["name"], "平安银行")
        self.assertEqual(result["000001"]["change_pct"], 3.7)
        self.assertEqual(result["000001"]["close"], 12.34)
        self.assertEqual(result["000001"]["open"], 12.0)
        self.assertEqual(result["000001"]["high"], 12.8)
        self.assertEqual(result["000001"]["low"], 11.7)

    def test_get_calendar_events_filters_cls_fallback_to_target_date_when_legacy_fails(self):
        module = __import__("tencent_finance_data", fromlist=["tencent_finance_data"])

        class _Legacy:
            def get_calendar_events(self, target_date=None):
                raise AttributeError("'NoneType' object has no attribute 'get'")

        class _Response:
            def json(self):
                return {
                    "code": 200,
                    "data": [
                        {
                            "calendar_day": "2026-06-18",
                            "week": "星期四",
                            "items": [
                                {
                                    "calendar_time": "2026-06-18 00:00:00",
                                    "type": 2,
                                    "event": {
                                        "title": "目标日事件",
                                        "star": 4,
                                        "country": "中国",
                                    },
                                },
                                {"calendar_time": "2026-06-18 00:00:00", "type": 2, "event": None},
                            ],
                        },
                        {
                            "calendar_day": "2026-06-19",
                            "week": "星期五",
                            "items": [
                                {
                                    "calendar_time": "2026-06-19 00:00:00",
                                    "type": 2,
                                    "event": {
                                        "title": "腾讯云数据库商业化计费",
                                        "star": 5,
                                        "country": "中国",
                                    },
                                },
                                {"calendar_time": "2026-06-19 00:00:00", "type": 2, "event": None},
                            ],
                        }
                    ],
                }

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, headers=None, timeout=0):
                self.url = url
                self.headers_arg = headers
                self.timeout = timeout
                return _Response()

        data = module.TencentFinanceData()
        data._legacy = _Legacy()
        data.session = _Session()

        result = data.get_calendar_events("2026-06-18")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "目标日事件")
        self.assertEqual(result[0]["date"], "2026-06-18")
        self.assertEqual(data.session.headers_arg["Referer"], "https://www.cls.cn/investkalendar")

    def test_get_calendar_events_keeps_all_cls_days_without_target_date(self):
        module = __import__("tencent_finance_data", fromlist=["tencent_finance_data"])

        class _Legacy:
            def get_calendar_events(self, target_date=None):
                raise AttributeError("legacy calendar unavailable")

        class _Response:
            def json(self):
                return {
                    "code": 200,
                    "data": [
                        {
                            "calendar_day": "2026-08-05",
                            "week": "星期三",
                            "items": [
                                {
                                    "calendar_time": "2026-08-05 00:00:00",
                                    "type": 2,
                                    "event": {"title": "当日事件", "star": 5, "country": "中国"},
                                }
                            ],
                        },
                        {
                            "calendar_day": "2026-08-28",
                            "week": "星期五",
                            "items": [
                                {
                                    "calendar_time": "2026-08-28 00:00:00",
                                    "type": 2,
                                    "event": {"title": "月末事件", "star": 4, "country": "中国"},
                                }
                            ],
                        },
                    ],
                }

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, headers=None, timeout=0):
                return _Response()

        data = module.TencentFinanceData()
        data._legacy = _Legacy()
        data.session = _Session()

        result = data.get_calendar_events()

        self.assertEqual([event["date"] for event in result], ["2026-08-05", "2026-08-28"])
        self.assertEqual([event["title"] for event in result], ["当日事件", "月末事件"])

    def test_get_calendar_events_uses_cls_fallback_when_legacy_returns_empty(self):
        module = __import__("tencent_finance_data", fromlist=["tencent_finance_data"])

        class _Legacy:
            def get_calendar_events(self, target_date=None):
                return []

        class _Response:
            def json(self):
                return {
                    "code": 200,
                    "data": [
                        {
                            "calendar_day": "2026-08-05",
                            "week": "星期三",
                            "items": [
                                {
                                    "calendar_time": "2026-08-05 00:00:00",
                                    "type": 2,
                                    "event": {"title": "本地回补事件", "star": 5, "country": "中国"},
                                }
                            ],
                        }
                    ],
                }

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, headers=None, timeout=0):
                self.headers_arg = headers
                return _Response()

        data = module.TencentFinanceData()
        data._legacy = _Legacy()
        data.session = _Session()

        result = data.get_calendar_events()

        self.assertEqual([event["title"] for event in result], ["本地回补事件"])
        self.assertEqual(data.session.headers_arg["Referer"], "https://www.cls.cn/investkalendar")


if __name__ == "__main__":
    unittest.main()
