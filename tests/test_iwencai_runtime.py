import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from input.iwencai_runtime import _default_fetch_daily_price_bars, get_major_indices_from_iwencai


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

    def test_major_indices_falls_back_to_price_bars_when_api_key_missing(self):
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

        with patch.dict(os.environ, {"IWENCAI_API_KEY": ""}, clear=False):
            result = get_major_indices_from_iwencai(
                target_date="2026-04-22",
                fetch_daily_price_bars_fn=lambda code, start_date, end_date, is_index=False: list(bar_map.get(code, [])),
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(set(result.keys()), {"上证指数", "深证成指", "创业板指"})
        self.assertEqual(result["上证指数"]["data_source"], "price_bar_fallback")
        self.assertAlmostEqual(result["上证指数"]["change_pct"], (3240 - 3210) / 3210 * 100)
        self.assertEqual(result["创业板指"]["trade_date"], "2026-04-22")


if __name__ == "__main__":
    unittest.main()
