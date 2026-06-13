import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.quote_lookup import build_market_quote_lookup, resolve_market_quote


class MarketActivityQuoteLookupTest(unittest.TestCase):
    def test_complete_pool_quote_replaces_incomplete_zero_stock_info(self):
        lookup = build_market_quote_lookup(
            stock_full_info={
                "sh603629": {
                    "name": "利通电子",
                    "change_pct": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "open": 0.0,
                    "close": 0.0,
                }
            },
            dt_pool=[
                {
                    "代码": "603629",
                    "名称": "利通电子",
                    "涨跌幅": -10.0,
                    "最高价": 166.98,
                    "最低价": 162.34,
                    "开盘价": 162.34,
                    "最新价": 162.34,
                }
            ],
        )

        quote = resolve_market_quote(lookup, stock_code="603629", stock_name="利通电子")
        self.assertEqual(quote["change_pct"], -10.0)
        self.assertEqual(quote["最高价"], 166.98)


if __name__ == "__main__":
    unittest.main()
