import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _shanghai_ms(date_text, hour=0, minute=0, second=0):
    dt = datetime.fromisoformat(date_text).replace(
        hour=hour,
        minute=minute,
        second=second,
        microsecond=0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    return int(dt.timestamp() * 1000)


class XuangubaoIntradayShimTest(unittest.TestCase):
    def test_local_xuangubao_intraday_shim_imports_for_entry_runtime(self):
        try:
            module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        except ModuleNotFoundError as error:
            self.fail(f"xuangubao_intraday shim should exist for entry runtime: {error}")

        self.assertTrue(hasattr(module, "XuangubaoIntradayAnalyzer"))
        analyzer = module.XuangubaoIntradayAnalyzer()
        self.assertTrue(hasattr(analyzer, "fetch_xuangubao_data"))

    def test_fetch_xuangubao_data_keeps_plate_items_when_news_token_invalid(self):
        module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        module._load_legacy_analyzer_class = lambda: None

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, params=None, timeout=0):
                if "newsflash" in url:
                    return _Response({"code": 50008, "message": "非法的token", "data": {}})
                return _Response(
                    {
                        "code": 20000,
                        "message": "OK",
                        "data": {
                            "items": [
                                {
                                    "id": 31765737,
                                    "name": "国产芯片",
                                    "description": "长鑫存储更新招股说明书",
                                }
                            ]
                        },
                    }
                )

        class _Requests:
            Session = _Session

        module.requests = _Requests

        data = module.XuangubaoIntradayAnalyzer().fetch_xuangubao_data()

        self.assertEqual(data["xuangubao_news"], [])
        self.assertEqual(data["xuangubao_plates"][0]["name"], "国产芯片")
        self.assertIn("newsflash", data["diagnostics"])

    def test_fetch_xuangubao_news_uses_login_token_header_when_available(self):
        module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        module._load_legacy_analyzer_class = lambda: None
        captured = {}

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, params=None, timeout=0):
                captured.setdefault("calls", []).append((url, dict(params or {}), dict(self.headers)))
                if "newsflash" in url:
                    return _Response(
                        {
                            "code": 20000,
                            "data": {
                                "messages": [
                                    {
                                        "title": "盘中异动",
                                        "summary": "半导体拉升",
                                        "created_at": 123,
                                        "stocks": [],
                                    }
                                ],
                                "next_cursor": "",
                            },
                        }
                    )
                return _Response({"code": 20000, "data": {"items": []}})

        class _Requests:
            Session = _Session

        module.requests = _Requests
        with patch.dict("os.environ", {"XUANGUBAO_IVANKA_TOKEN": "token-value"}):
            data = module.XuangubaoIntradayAnalyzer().fetch_xuangubao_data()

        news_call = next(call for call in captured["calls"] if "newsflash" in call[0])
        self.assertEqual(news_call[1]["subj_ids"], "10,35")
        self.assertEqual(news_call[1]["has_explain"], "false")
        self.assertEqual(news_call[2]["x-ivanka-token"], "token-value")
        self.assertEqual(news_call[2]["origin"], "https://xuangutong.com.cn")
        self.assertEqual(data["xuangubao_news"][0]["title"], "盘中异动")

    def test_fetch_xuangubao_news_uses_next_cursor_for_next_page(self):
        module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        module._load_legacy_analyzer_class = lambda: None
        captured = {}

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, params=None, timeout=0):
                calls = captured.setdefault("calls", [])
                calls.append((url, dict(params or {}), dict(self.headers)))
                if "newsflash" in url and len([call for call in calls if "newsflash" in call[0]]) == 1:
                    return _Response(
                        {
                            "code": 20000,
                            "data": {
                                "messages": [{"title": "第一页", "summary": "", "created_at": 1, "stocks": []}],
                                "next_cursor": "1779084120582",
                            },
                        }
                    )
                if "newsflash" in url:
                    return _Response(
                        {
                            "code": 20000,
                            "data": {
                                "messages": [{"title": "第二页", "summary": "", "created_at": 2, "stocks": []}],
                                "next_cursor": "",
                            },
                        }
                    )
                return _Response({"code": 20000, "data": {"items": []}})

        class _Requests:
            Session = _Session

        module.requests = _Requests
        with patch.dict("os.environ", {"XUANGUBAO_IVANKA_TOKEN": "token-value"}):
            data = module.XuangubaoIntradayAnalyzer().fetch_xuangubao_data()

        news_calls = [call for call in captured["calls"] if "newsflash" in call[0]]
        self.assertEqual(len(news_calls), 2)
        self.assertNotIn("cursor", news_calls[0][1])
        self.assertEqual(news_calls[0][1]["subj_ids"], "10,35")
        self.assertEqual(news_calls[1][1]["cursor"], "1779084120582")
        self.assertEqual(news_calls[1][1]["subj_ids"], "10,35")
        self.assertEqual([item["title"] for item in data["xuangubao_news"]], ["第一页", "第二页"])

    def test_fetch_xuangubao_news_filters_to_target_date_and_stops_after_older_page(self):
        module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        module._load_legacy_analyzer_class = lambda: None
        captured = {}

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        pages = [
            {
                "messages": [
                    {
                        "title": "明日新闻不应进入今日日报",
                        "summary": "",
                        "created_at": _shanghai_ms("2026-05-19", 9, 0),
                        "stocks": [],
                    },
                    {
                        "title": "今日尾盘新闻",
                        "summary": "",
                        "created_at": _shanghai_ms("2026-05-18", 23, 50),
                        "stocks": [],
                    },
                ],
                "next_cursor": "cursor-page-2",
            },
            {
                "messages": [
                    {
                        "title": "今日早盘新闻",
                        "summary": "",
                        "created_at": _shanghai_ms("2026-05-18", 9, 30),
                        "stocks": [],
                    },
                    {
                        "title": "昨日新闻不应进入今日日报",
                        "summary": "",
                        "created_at": _shanghai_ms("2026-05-17", 23, 59),
                        "stocks": [],
                    },
                ],
                "next_cursor": "cursor-page-3",
            },
            {
                "messages": [
                    {
                        "title": "更早新闻不应再请求",
                        "summary": "",
                        "created_at": _shanghai_ms("2026-05-17", 9, 30),
                        "stocks": [],
                    }
                ],
                "next_cursor": "",
            },
        ]

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, params=None, timeout=0):
                captured.setdefault("calls", []).append((url, dict(params or {})))
                if "newsflash" in url:
                    page = pages[len([call for call in captured["calls"] if "newsflash" in call[0]]) - 1]
                    return _Response({"code": 20000, "data": page})
                return _Response({"code": 20000, "data": {"items": []}})

        class _Requests:
            Session = _Session

        module.requests = _Requests
        with patch.dict("os.environ", {"XUANGUBAO_IVANKA_TOKEN": "token-value"}):
            data = module.XuangubaoIntradayAnalyzer().fetch_xuangubao_data(target_date="2026-05-18")

        news_calls = [call for call in captured["calls"] if "newsflash" in call[0]]
        self.assertEqual(len(news_calls), 2)
        self.assertEqual(news_calls[1][1]["cursor"], "cursor-page-2")
        self.assertEqual(
            [item["title"] for item in data["xuangubao_news"]],
            ["今日尾盘新闻", "今日早盘新闻"],
        )

    def test_fetch_xuangubao_news_loads_login_token_from_local_env_file(self):
        module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        module._load_legacy_analyzer_class = lambda: None
        captured = {}

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, params=None, timeout=0):
                captured.setdefault("calls", []).append((url, dict(params or {}), dict(self.headers)))
                if "newsflash" in url:
                    return _Response(
                        {
                            "code": 20000,
                            "data": {
                                "messages": [
                                    {
                                        "title": "盘中异动",
                                        "summary": "半导体拉升",
                                        "created_at": 123,
                                        "stocks": [],
                                    }
                                ],
                                "next_cursor": "",
                            },
                        }
                    )
                return _Response({"code": 20000, "data": {"items": []}})

        class _Requests:
            Session = _Session

        module.requests = _Requests
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("XUANGUBAO_IVANKA_TOKEN=dotenv-token\n", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True), patch.object(module.Path, "cwd", return_value=Path(tmpdir)):
                data = module.XuangubaoIntradayAnalyzer().fetch_xuangubao_data()

        news_call = next(call for call in captured["calls"] if "newsflash" in call[0])
        self.assertEqual(news_call[2]["x-ivanka-token"], "dotenv-token")
        self.assertEqual(data["xuangubao_news"][0]["title"], "盘中异动")

    def test_fetch_xuangubao_news_enriches_stocks_from_market_real(self):
        module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        module._load_legacy_analyzer_class = lambda: None
        captured = {}

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, params=None, timeout=0):
                captured.setdefault("calls", []).append((url, dict(params or {})))
                if "newsflash" in url:
                    return _Response(
                        {
                            "code": 20000,
                            "data": {
                                "messages": [
                                    {
                                        "title": "三大运营商异动拉升",
                                        "summary": "中国联通涨超5%",
                                        "created_at": 123,
                                        "stocks": [
                                            {"name": "中国联通", "symbol": "600050.SS", "market": ""},
                                            {"name": "中国移动", "symbol": "600941.SS", "market": ""},
                                        ],
                                        "all_stocks": [
                                            {"name": "中国联通", "symbol": "600050.SS", "market": "mdc"},
                                            {"name": "中国移动", "symbol": "600941.SS", "market": "mdc"},
                                        ],
                                        "bkj_infos": [{"id": 1, "name": "运营商"}],
                                    }
                                ],
                                "next_cursor": "",
                            },
                        }
                    )
                if "market/real" in url:
                    return _Response(
                        {
                            "code": 20000,
                            "data": {
                                "fields": [
                                    "prod_name",
                                    "last_px",
                                    "px_change",
                                    "px_change_rate",
                                    "symbol",
                                    "trade_status",
                                    "market_type",
                                ],
                                "snapshot": {
                                    "600050.SS": ["中国联通", 4.92, 0.26, 5.58, "600050.SS", "BREAK", "mdc"],
                                    "600941.SS": ["中国移动", 100.35, 2.38, 2.43, "600941.SS", "BREAK", "mdc"],
                                },
                            },
                        }
                    )
                return _Response({"code": 20000, "data": {"items": []}})

        class _Requests:
            Session = _Session

        module.requests = _Requests
        with patch.dict("os.environ", {"XUANGUBAO_IVANKA_TOKEN": "token-value"}):
            data = module.XuangubaoIntradayAnalyzer().fetch_xuangubao_data()

        market_call = next(call for call in captured["calls"] if "market/real" in call[0])
        self.assertEqual(market_call[1]["prod_code"], "600050.SS,600941.SS")
        news = data["xuangubao_news"][0]
        self.assertEqual(news["plates"][0]["name"], "运营商")
        self.assertEqual(news["stocks"][0]["last_px"], 4.92)
        self.assertEqual(news["stocks"][0]["px_change_rate"], 5.58)

    def test_fetch_xuangubao_data_includes_limit_up_stock_reasons(self):
        module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        module._load_legacy_analyzer_class = lambda: None

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, params=None, timeout=0):
                if "newsflash" in url:
                    return _Response({"code": 50008, "message": "非法的token", "data": {}})
                if "pool/detail" in url:
                    return _Response(
                        {
                            "code": 20000,
                            "data": [
                                {
                                    "symbol": "600676.SS",
                                    "stock_chi_name": "交运股份",
                                    "price": 8.09,
                                    "change_percent": 0.1006802721,
                                    "limit_up_days": 1,
                                    "first_limit_up": 1779067959,
                                    "last_limit_up": 1779067959,
                                    "break_limit_up_times": 0,
                                    "surge_reason": {
                                        "symbol": "600676.SS",
                                        "stock_reason": "拟置入文旅体育资产",
                                        "related_plates": [
                                            {"plate_id": 15030162, "plate_name": "资产重组"}
                                        ],
                                    },
                                }
                            ],
                        }
                    )
                return _Response({"code": 20000, "data": {"items": []}})

        class _Requests:
            Session = _Session

        module.requests = _Requests

        data = module.XuangubaoIntradayAnalyzer().fetch_xuangubao_data()

        reasons = data["xuangubao_limit_up_reasons"]
        self.assertEqual(reasons[0]["symbol"], "600676.SS")
        self.assertEqual(reasons[0]["name"], "交运股份")
        self.assertEqual(reasons[0]["stock_reason"], "拟置入文旅体育资产")
        self.assertEqual(reasons[0]["related_plates"][0]["plate_name"], "资产重组")
        self.assertEqual(reasons[0]["limit_up_days"], 1)
        self.assertEqual(reasons[0]["surge_reason"]["stock_reason"], "拟置入文旅体育资产")


if __name__ == "__main__":
    unittest.main()
