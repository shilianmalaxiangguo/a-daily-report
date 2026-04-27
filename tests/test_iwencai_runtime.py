import os
import sys
import unittest
import urllib.error
from io import BytesIO
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from input.iwencai_runtime import (
    _default_fetch_daily_price_bars,
    get_major_indices_from_iwencai,
    get_sector_change_from_iwencai,
    get_total_turnover_from_iwencai,
    get_turnover_rank_from_iwencai,
    get_wind_a_from_iwencai,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        import json

        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _raise_skill_version_low(*args, **kwargs):
    raise urllib.error.HTTPError(
        url="https://openapi.iwencai.com/v1/query2data",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=BytesIO("当前 Skill 版本过低，本次请求无法执行。".encode("utf-8")),
    )


def _raise_network_blocked(*args, **kwargs):
    raise AssertionError("network call should have been routed through injected urlopen_fn")


class IwencaiRuntimeTest(unittest.TestCase):
    def test_default_fetch_daily_price_bars_passes_normalization_helpers(self):
        captured = {}

        def fake_fetch_daily_price_bars(code, start_date, end_date, is_index=False, helpers=None):
            captured["helpers"] = helpers or {}
            return []

        with patch("market_data.daily_price_runtime.fetch_daily_price_bars", side_effect=fake_fetch_daily_price_bars):
            _default_fetch_daily_price_bars("000001", "2026-04-01", "2026-04-22", is_index=True)

        self.assertIn("normalize_stock_code", captured["helpers"])
        self.assertIn("_safe_float", captured["helpers"])
        self.assertIn("_normalize_kline_date_str", captured["helpers"])
        self.assertIn("_parse_kline_date", captured["helpers"])
        self.assertIn("_daily_price_bar_cache", captured["helpers"])
        self.assertIn("_ensure_baostock_login", captured["helpers"])
        self.assertIn("_logout_baostock_silently", captured["helpers"])

    def test_major_indices_falls_back_to_price_bars_when_akshare_and_api_key_missing(self):
        bar_map = {
            "000001": [
                {"date": "2026-04-21", "open": 3200, "high": 3220, "low": 3190, "close": 3210},
                {"date": "2026-04-22", "open": 3210, "high": 3250, "low": 3205, "close": 3240},
            ],
            "399001": [
                {"date": "2026-04-21", "open": 10000, "high": 10080, "low": 9980, "close": 10020},
                {"date": "2026-04-22", "open": 10020, "high": 10120, "low": 10000, "close": 10100},
            ],
            "399006": [
                {"date": "2026-04-21", "open": 2100, "high": 2120, "low": 2090, "close": 2110},
                {"date": "2026-04-22", "open": 2110, "high": 2140, "low": 2105, "close": 2130},
            ],
        }

        with patch.dict(os.environ, {"IWENCAI_API_KEY": ""}, clear=False), patch.dict(
            sys.modules,
            {"akshare": SimpleNamespace()},
        ):
            result = get_major_indices_from_iwencai(
                target_date="2026-04-22",
                fetch_daily_price_bars_fn=lambda code, start_date, end_date, is_index=False: list(bar_map.get(code, [])),
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(set(result.keys()), {"上证指数", "深证成指", "创业板指"})
        self.assertEqual(result["上证指数"]["data_source"], "price_bar_fallback")
        self.assertAlmostEqual(result["上证指数"]["change_pct"], (3240 - 3210) / 3210 * 100)
        self.assertEqual(result["创业板指"]["trade_date"], "2026-04-22")

    def test_major_indices_falls_back_without_traceback_when_akshare_empty_and_skill_version_low(self):
        bar_map = {
            "000001": [{"date": "2026-04-27", "open": 4074, "high": 4092, "low": 4071, "close": 4086}],
            "399001": [{"date": "2026-04-27", "open": 14960, "high": 15054, "low": 14919, "close": 14995}],
            "399006": [{"date": "2026-04-27", "open": 3677, "high": 3686, "low": 3640, "close": 3648}],
        }

        logs = []

        with patch("traceback.print_exc") as trace_mock, patch.dict(sys.modules, {"akshare": SimpleNamespace()}):
            result = get_major_indices_from_iwencai(
                target_date="2026-04-27",
                api_key="recognized-but-version-low",
                urlopen_fn=_raise_skill_version_low,
                fetch_daily_price_bars_fn=lambda code, start_date, end_date, is_index=False: list(bar_map.get(code, [])),
                print_fn=logs.append,
            )

        trace_mock.assert_not_called()
        self.assertEqual(result["上证指数"]["data_source"], "price_bar_fallback")
        self.assertEqual(set(result.keys()), {"上证指数", "深证成指", "创业板指"})
        self.assertTrue(any("Skill 版本过低" in line for line in logs))

    def test_total_turnover_falls_back_to_akshare_when_skill_version_low(self):
        import pandas as pd

        def fake_index_daily_em(symbol):
            rows = {
                "sh000001": [
                    {"date": "2026-04-27", "amount": 1.136052e12},
                ],
                "sz399001": [
                    {"date": "2026-04-27", "amount": 1.453399e12},
                ],
            }
            return pd.DataFrame(rows.get(symbol, []))

        fake_akshare = SimpleNamespace(stock_zh_index_daily_em=fake_index_daily_em)

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = get_total_turnover_from_iwencai(
                target_date="2026-04-27",
                api_key="recognized-but-version-low",
                urlopen_fn=_raise_skill_version_low,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertAlmostEqual(result, 25894.51, places=2)

    def test_total_turnover_uses_akshare_primary_without_calling_iwencai(self):
        import pandas as pd

        iwencai_calls = []

        def fake_index_daily_em(symbol):
            rows = {
                "sh000001": [{"date": "2026-04-27", "amount": 1.136052e12}],
                "sz399001": [{"date": "2026-04-27", "amount": 1.453399e12}],
            }
            return pd.DataFrame(rows.get(symbol, []))

        def fail_iwencai(*args, **kwargs):
            iwencai_calls.append(args)
            raise AssertionError("iwencai should not be called when AkShare primary succeeds")

        fake_akshare = SimpleNamespace(stock_zh_index_daily_em=fake_index_daily_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = get_total_turnover_from_iwencai(
                target_date="2026-04-27",
                api_key="ok",
                urlopen_fn=fail_iwencai,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(iwencai_calls, [])
        self.assertAlmostEqual(result, 25894.51, places=2)

    def test_major_indices_use_akshare_primary_without_calling_iwencai(self):
        import pandas as pd

        iwencai_calls = []
        index_rows = {
            "sh000001": [
                {"date": "2026-04-26", "open": 4070, "high": 4090, "low": 4060, "close": 4079, "amount": 1.10e12},
                {"date": "2026-04-27", "open": 4074, "high": 4092, "low": 4071, "close": 4086, "amount": 1.13e12},
            ],
            "sz399001": [
                {"date": "2026-04-26", "open": 14900, "high": 15010, "low": 14880, "close": 14940, "amount": 1.40e12},
                {"date": "2026-04-27", "open": 14960, "high": 15054, "low": 14919, "close": 14995, "amount": 1.45e12},
            ],
            "sz399006": [
                {"date": "2026-04-26", "open": 3680, "high": 3700, "low": 3625, "close": 3667, "amount": 7.33e11},
                {"date": "2026-04-27", "open": 3677, "high": 3686, "low": 3640, "close": 3648, "amount": 6.77e11},
            ],
        }

        def fake_index_daily_em(symbol):
            return pd.DataFrame(index_rows.get(symbol, []))

        def fail_iwencai(*args, **kwargs):
            iwencai_calls.append(args)
            raise AssertionError("iwencai should not be called when AkShare primary succeeds")

        fake_akshare = SimpleNamespace(stock_zh_index_daily_em=fake_index_daily_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = get_major_indices_from_iwencai(
                target_date="2026-04-27",
                api_key="ok",
                urlopen_fn=fail_iwencai,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(iwencai_calls, [])
        self.assertEqual(set(result.keys()), {"上证指数", "深证成指", "创业板指"})
        self.assertEqual(result["上证指数"]["data_source"], "akshare.stock_zh_index_daily_em")

    def test_wind_a_uses_akshare_primary_without_calling_iwencai(self):
        import pandas as pd

        iwencai_calls = []

        def fake_index_daily_em(symbol):
            rows = {
                "sh000985": [
                    {"date": "2026-04-26", "close": 6271.17},
                    {"date": "2026-04-27", "close": 6296.45},
                ],
            }
            return pd.DataFrame(rows.get(symbol, []))

        def fail_iwencai(*args, **kwargs):
            iwencai_calls.append(args)
            raise AssertionError("iwencai should not be called when AkShare primary succeeds")

        fake_akshare = SimpleNamespace(stock_zh_index_daily_em=fake_index_daily_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = get_wind_a_from_iwencai(
                target_date="2026-04-27",
                api_key="ok",
                urlopen_fn=fail_iwencai,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(iwencai_calls, [])
        self.assertEqual(result["data_source"], "akshare.stock_zh_index_daily_em")
        self.assertAlmostEqual(result["change_pct"], (6296.45 - 6271.17) / 6271.17 * 100)

    def test_turnover_rank_uses_eastmoney_primary_with_sector(self):
        def fake_eastmoney_urlopen(request, timeout=30):
            return _Response(
                {
                    "data": {
                        "diff": [
                            {
                                "f12": "300750",
                                "f14": "宁德时代",
                                "f6": 14514326132.36,
                                "f3": -225,
                                "f100": "电池",
                            },
                            {
                                "f12": "688041",
                                "f14": "海光信息",
                                "f6": 13849159127.0,
                                "f3": 395,
                                "f100": "半导体",
                            },
                        ]
                    }
                }
            )

        def fail_iwencai(*args, **kwargs):
            raise AssertionError("iwencai should not be called when Eastmoney primary succeeds")

        result = get_turnover_rank_from_iwencai(
            limit=2,
            target_date="2026-04-27",
            eastmoney_urlopen_fn=fake_eastmoney_urlopen,
            urlopen_fn=fail_iwencai,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual([item["name"] for item in result], ["宁德时代", "海光信息"])
        self.assertAlmostEqual(result[0]["turnover"], 145.1432613236)
        self.assertAlmostEqual(result[0]["change_pct"], -2.25)
        self.assertEqual(result[0]["sector"], "电池")
        self.assertEqual(result[0]["data_source"], "eastmoney.push2.clist")

    def test_turnover_rank_falls_back_to_akshare_when_primary_empty_and_iwencai_unavailable(self):
        import pandas as pd

        def fake_empty_eastmoney_urlopen(request, timeout=30):
            return _Response({"data": {"diff": []}})

        def fake_stock_spot_em():
            return pd.DataFrame(
                [
                    {"代码": "300750", "名称": "宁德时代", "成交额": 14514326132.36, "涨跌幅": -2.25, "所属行业": "电池"},
                    {"代码": "688041", "名称": "海光信息", "成交额": 13849159127.0, "涨跌幅": 3.95, "所属行业": "半导体"},
                ]
            )

        fake_akshare = SimpleNamespace(stock_zh_a_spot_em=fake_stock_spot_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = get_turnover_rank_from_iwencai(
                limit=2,
                target_date="2026-04-27",
                api_key="",
                eastmoney_urlopen_fn=fake_empty_eastmoney_urlopen,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual([item["name"] for item in result], ["宁德时代", "海光信息"])
        self.assertAlmostEqual(result[0]["turnover"], 145.1432613236)
        self.assertEqual(result[0]["sector"], "电池")
        self.assertEqual(result[0]["data_source"], "akshare.stock_zh_a_spot_em")

    def test_turnover_rank_uses_urlopen_fn_for_eastmoney_primary_when_specific_injection_omitted(self):
        import pandas as pd

        def fake_stock_spot_em():
            return pd.DataFrame(
                [
                    {"代码": "300750", "名称": "宁德时代", "成交额": 14514326132.36, "涨跌幅": -2.25, "所属行业": "电池"},
                ]
            )

        fake_akshare = SimpleNamespace(stock_zh_a_spot_em=fake_stock_spot_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = get_turnover_rank_from_iwencai(
                limit=1,
                target_date="2026-04-27",
                api_key="",
                urlopen_fn=_raise_network_blocked,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(result[0]["data_source"], "akshare.stock_zh_a_spot_em")

    def test_turnover_rank_skips_eastmoney_primary_for_historical_target_date(self):
        eastmoney_calls = []

        def fake_eastmoney_urlopen(request, timeout=30):
            eastmoney_calls.append(request)
            return _Response({"data": {"diff": []}})

        def fake_iwencai_urlopen(request, timeout=30):
            return _Response(
                {
                    "datas": [
                        {
                            "股票代码": "300750.SZ",
                            "股票简称": "宁德时代",
                            "成交额[19990101]": 14514326132.36,
                            "涨跌幅[19990101]": -2.25,
                            "所属同花顺行业": ["电池"],
                        }
                    ]
                }
            )

        result = get_turnover_rank_from_iwencai(
            limit=1,
            target_date="1999-01-01",
            api_key="ok",
            eastmoney_urlopen_fn=fake_eastmoney_urlopen,
            urlopen_fn=fake_iwencai_urlopen,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(eastmoney_calls, [])
        self.assertEqual(result[0]["name"], "宁德时代")
        self.assertEqual(result[0]["data_source"], "iwencai.query2data")

    def test_sector_change_uses_tencent_fund_flow_primary(self):
        def fake_tencent_urlopen(request, timeout=30):
            return _Response(
                {
                    "data": {
                        "data": [
                            {"name": "半导体", "zdf": "4.23", "cje": "30079933.00", "lzg": {"name": "帝奥微"}},
                            {"name": "消费电子", "zdf": "3.87", "cje": "10865439.00", "lzg": {"name": "科森科技"}},
                            {"name": "白酒Ⅱ", "zdf": "-3.00", "cje": "1633121.00", "lzg": {"name": "*ST岩石"}},
                        ]
                    }
                }
            )

        def fail_iwencai(*args, **kwargs):
            raise AssertionError("iwencai should not be called when Tencent primary succeeds")

        up = get_sector_change_from_iwencai(
            rank_type="up",
            limit=2,
            tencent_urlopen_fn=fake_tencent_urlopen,
            urlopen_fn=fail_iwencai,
            print_fn=lambda *args, **kwargs: None,
        )
        down = get_sector_change_from_iwencai(
            rank_type="down",
            limit=1,
            tencent_urlopen_fn=fake_tencent_urlopen,
            urlopen_fn=fail_iwencai,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual([item["name"] for item in up], ["半导体", "消费电子"])
        self.assertAlmostEqual(up[0]["turnover"], 3007.9933)
        self.assertEqual(up[0]["leader_stock"], "帝奥微")
        self.assertEqual(up[0]["data_source"], "tencent.fundflow.getHyRank")
        self.assertEqual(down[0]["name"], "白酒Ⅱ")
        self.assertAlmostEqual(down[0]["change_pct"], -3.0)

    def test_sector_change_falls_back_to_akshare_when_primary_empty_and_iwencai_unavailable(self):
        import pandas as pd

        def fake_empty_tencent_urlopen(request, timeout=30):
            return _Response({"data": {"data": []}})

        def fake_industry_name_em():
            return pd.DataFrame(
                [
                    {"板块名称": "通信设备", "涨跌幅": 1.12},
                    {"板块名称": "半导体", "涨跌幅": 4.23},
                    {"板块名称": "白酒Ⅱ", "涨跌幅": -3.0},
                ]
            )

        fake_akshare = SimpleNamespace(stock_board_industry_name_em=fake_industry_name_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            up = get_sector_change_from_iwencai(
                rank_type="up",
                limit=2,
                api_key="",
                tencent_urlopen_fn=fake_empty_tencent_urlopen,
                print_fn=lambda *args, **kwargs: None,
            )
            down = get_sector_change_from_iwencai(
                rank_type="down",
                limit=1,
                api_key="",
                tencent_urlopen_fn=fake_empty_tencent_urlopen,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual([item["name"] for item in up], ["半导体", "通信设备"])
        self.assertEqual(down[0]["name"], "白酒Ⅱ")
        self.assertEqual(up[0]["data_source"], "akshare.stock_board_industry_name_em")

    def test_sector_change_uses_urlopen_fn_for_tencent_primary_when_specific_injection_omitted(self):
        import pandas as pd

        def fake_industry_name_em():
            return pd.DataFrame([{"板块名称": "半导体", "涨跌幅": 4.23}])

        fake_akshare = SimpleNamespace(stock_board_industry_name_em=fake_industry_name_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = get_sector_change_from_iwencai(
                rank_type="up",
                limit=1,
                api_key="",
                urlopen_fn=_raise_network_blocked,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(result[0]["data_source"], "akshare.stock_board_industry_name_em")

    def test_sector_change_skips_tencent_primary_for_historical_target_date(self):
        tencent_calls = []

        def fake_tencent_urlopen(request, timeout=30):
            tencent_calls.append(request)
            return _Response({"data": {"data": []}})

        def fake_iwencai_urlopen(request, timeout=30):
            return _Response(
                {
                    "status_code": 0,
                    "datas": [
                        {"指数简称": "半导体", "涨跌幅[19990101]": 4.23},
                    ],
                }
            )

        result = get_sector_change_from_iwencai(
            rank_type="up",
            limit=1,
            target_date="1999-01-01",
            api_key="ok",
            tencent_urlopen_fn=fake_tencent_urlopen,
            urlopen_fn=fake_iwencai_urlopen,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(tencent_calls, [])
        self.assertEqual(result[0]["name"], "半导体")
        self.assertEqual(result[0]["data_source"], "iwencai.query2data")


if __name__ == "__main__":
    unittest.main()
