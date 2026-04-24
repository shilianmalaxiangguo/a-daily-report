import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.1, 0.2


class _CacheStub:
    def __init__(self):
        self.saved = {}
        self.cleaned_keep_days = []

    def clean_old_cache(self, keep_days=7):
        self.cleaned_keep_days.append(keep_days)

    def get_cache_stats(self, target_date):
        return {"count": 1, "size_mb": 1.5}

    def get(self, code, target_date):
        if code == "000001":
            return [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        return []

    def set(self, code, target_date, data, source="mixed_partial", max_length=120):
        self.saved[(code, target_date)] = {
            "data": list(data),
            "source": source,
            "max_length": max_length,
        }


class _BaoHistoryItem:
    def __init__(self, amount):
        self.amount = amount


class _BaoStockStub:
    def __init__(self):
        self.calls = []

    def get_historical_data(self, code, start_date, end_date):
        self.calls.append((code, start_date, end_date))
        return [_BaoHistoryItem(4e8), _BaoHistoryItem(5e8)]


class WatchCandidatesRequestTest(unittest.TestCase):
    def test_collect_watch_candidate_history_request_bundle_merges_cache_quicktiny_and_baostock(self):
        try:
            request_module = importlib.import_module("domains.watch_candidates.request")
        except ModuleNotFoundError as error:
            self.fail(f"domains.watch_candidates.request should exist: {error}")

        bundle = getattr(request_module, "collect_watch_candidate_history_request_bundle", None)
        self.assertIsNotNone(bundle, "collect_watch_candidate_history_request_bundle should be defined")

        timer = _TimerStub()
        emitted = []
        cache = _CacheStub()
        baostock = _BaoStockStub()

        result = bundle(
            "2026-04-22",
            candidates=[
                {"code": "000001", "name": "军工一号", "turnover": 18.0, "sector": "军工"},
                {"code": "000002", "name": "算力二号", "turnover": 9.0, "sector": "算力"},
            ],
            stock_full_info={
                "000001": {"change_pct": 6.2},
                "000002": {"change_pct": 3.8},
            },
            get_cache=lambda: cache,
            fetch_quicktiny_history=lambda *, full_code, code, target_date, days=30: (
                [8.0, 10.0, 12.0] if code == "000001" else (_ for _ in ()).throw(RuntimeError("quicktiny down"))
            ),
            baostock_source_factory=lambda: baostock,
            timer=timer,
            emit=emitted.append,
        )

        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual([item["code"] for item in stocks_with_history], ["000001", "000002"])
        self.assertEqual(stocks_with_history[0]["hist_turnover"], [1.0, 2.0, 8.0, 10.0, 12.0])
        self.assertEqual(stocks_with_history[0]["data_source"], "缓存+QuickTiny")
        self.assertEqual(stocks_with_history[0]["change_pct"], 6.2)
        self.assertEqual(stocks_with_history[1]["hist_turnover"], [4.0, 5.0])
        self.assertEqual(stocks_with_history[1]["data_source"], "BaoStock")
        self.assertEqual(result["results"]["history_fetch_stats"]["quicktiny_success"], 1)
        self.assertEqual(result["results"]["history_fetch_stats"]["baostock_success"], 1)
        self.assertEqual(result["results"]["history_fetch_stats"]["cache_hits"], 1)
        self.assertEqual(result["results"]["history_fetch_stats"]["cache_partial"], 1)
        self.assertEqual(cache.cleaned_keep_days, [7])
        self.assertEqual(cache.saved[("000001", "2026-04-22")]["data"], [1.0, 2.0])
        self.assertEqual(len(baostock.calls), 1)
        self.assertEqual(timer.records[-1], ("候选股历史成交额获取", 15))
        self.assertTrue(any("候选股" in line for line in emitted))
        self.assertTrue(any(log["step"] == "request.candidate_history" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
