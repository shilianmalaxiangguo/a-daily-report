import importlib
import sys
import time
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

    def test_quicktiny_hard_timeout_falls_back_to_baostock(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        cache = _CacheStub()
        baostock = _BaoStockStub()

        def slow_quicktiny(**_kwargs):
            time.sleep(0.2)
            return [99.0]

        result = bundle(
            "2026-05-14",
            candidates=[{"code": "000002", "name": "慢接口样本", "turnover": 9.0, "sector": "算力"}],
            stock_full_info={"000002": {"change_pct": 3.8}},
            get_cache=lambda: cache,
            fetch_quicktiny_history=slow_quicktiny,
            baostock_source_factory=lambda: baostock,
            timer=timer,
            emit=emitted.append,
            quicktiny_timeout_seconds=0.05,
        )

        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual(stocks_with_history[0]["hist_turnover"], [4.0, 5.0])
        self.assertEqual(stocks_with_history[0]["data_source"], "BaoStock")
        self.assertEqual(result["results"]["history_fetch_stats"]["quicktiny_fail"], 1)
        self.assertEqual(result["results"]["history_fetch_stats"]["baostock_success"], 1)
        self.assertTrue(any("QuickTiny超时" in line for line in emitted))

    def test_cached_history_skips_live_quicktiny_when_sufficient(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        class CacheWithEnoughHistory(_CacheStub):
            def get(self, code, target_date):
                return [float(index) for index in range(1, 31)]

        timer = _TimerStub()
        emitted = []
        cache = CacheWithEnoughHistory()
        quicktiny_calls = []

        result = bundle(
            "2026-05-14",
            candidates=[{"code": "000003", "name": "缓存样本", "turnover": 9.0, "sector": "算力"}],
            stock_full_info={"000003": {"change_pct": 3.8}},
            get_cache=lambda: cache,
            fetch_quicktiny_history=lambda **kwargs: quicktiny_calls.append(kwargs) or [99.0],
            baostock_source_factory=lambda: _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
            cached_history_min_days=20,
        )

        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual(quicktiny_calls, [])
        self.assertEqual(stocks_with_history[0]["data_source"], "缓存")
        self.assertEqual(stocks_with_history[0]["hist_turnover"], [float(index) for index in range(1, 28)])
        self.assertTrue(any("缓存足够" in line for line in emitted))

    def test_can_disable_live_quicktiny_for_main_report_path(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        quicktiny_calls = []
        baostock = _BaoStockStub()

        result = bundle(
            "2026-05-14",
            candidates=[{"code": "000004", "name": "无缓存样本", "turnover": 9.0, "sector": "算力"}],
            stock_full_info={"000004": {"change_pct": 3.8}},
            get_cache=lambda: _CacheStub(),
            fetch_quicktiny_history=lambda **kwargs: quicktiny_calls.append(kwargs) or [99.0],
            baostock_source_factory=lambda: baostock,
            timer=timer,
            emit=emitted.append,
            enable_live_quicktiny=False,
        )

        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual(quicktiny_calls, [])
        self.assertEqual(stocks_with_history[0]["hist_turnover"], [4.0, 5.0])
        self.assertEqual(stocks_with_history[0]["data_source"], "BaoStock")
        self.assertEqual(result["results"]["history_fetch_stats"]["baostock_success"], 1)
        self.assertTrue(any("跳过QuickTiny实时补充" in line for line in emitted))

    def test_can_disable_baostock_for_main_report_path(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        quicktiny_calls = []
        baostock_created = []

        result = bundle(
            "2026-05-14",
            candidates=[{"code": "000005", "name": "无历史样本", "turnover": 9.0, "sector": "算力"}],
            stock_full_info={"000005": {"change_pct": 3.8}},
            get_cache=lambda: _CacheStub(),
            fetch_quicktiny_history=lambda **kwargs: quicktiny_calls.append(kwargs) or [99.0],
            baostock_source_factory=lambda: baostock_created.append(True) or _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
            enable_live_quicktiny=False,
            enable_baostock_fallback=False,
        )

        self.assertEqual(result["results"]["stocks_with_history"], [])
        self.assertEqual(quicktiny_calls, [])
        self.assertEqual(baostock_created, [])
        self.assertTrue(any("跳过BaoStock兜底" in line for line in emitted))


if __name__ == "__main__":
    unittest.main()
