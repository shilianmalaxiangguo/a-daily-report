import importlib
import sys
import threading
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

    def get_entry(self, code, target_date):
        saved = self.saved.get((code, target_date))
        return dict(saved) if saved else {}

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
    def test_tushare_turnover_history_cache_reuses_successful_same_day_result(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        class ReusableCache(_CacheStub):
            def get(self, code, target_date):
                saved = self.saved.get((code, target_date))
                if saved:
                    return list(saved["data"])
                return []

        timer = _TimerStub()
        cache = ReusableCache()
        tushare_calls = []

        kwargs = {
            "target_date": "2026-05-14",
            "candidates": [{"code": "000009", "name": "缓存复用样本", "turnover": 18.0, "sector": "军工"}],
            "stock_full_info": {"000009": {"change_pct": 6.2}},
            "get_cache": lambda: cache,
            "fetch_tushare_turnover_history": lambda code, start_date, end_date: (
                tushare_calls.append((code, start_date, end_date)) or [9.0, 10.0, 11.0, 12.0]
            ),
            "fetch_quicktiny_history": lambda **kwargs: [99.0],
            "baostock_source_factory": lambda: _BaoStockStub(),
            "timer": timer,
            "emit": lambda _message: None,
            "enable_live_quicktiny": False,
            "enable_baostock_fallback": False,
        }

        first = bundle(**kwargs)
        second = bundle(**kwargs)

        first_stock = first["results"]["stocks_with_history"][0]
        second_stock = second["results"]["stocks_with_history"][0]
        second_stats = second["results"]["history_fetch_stats"]
        second_log = second["module_logs"][0]["details"]
        self.assertEqual(tushare_calls, [("000009", "2026-04-19", "2026-05-14")])
        self.assertEqual(cache.saved[("tushare:000009", "2026-05-14")]["data"], [9.0, 10.0, 11.0, 12.0])
        self.assertEqual(cache.saved[("tushare:000009", "2026-05-14")]["source"], "tushare_full_window")
        self.assertEqual(first_stock["data_source"], "Tushare")
        self.assertEqual(second_stock["hist_turnover"], [9.0, 10.0, 11.0, 12.0])
        self.assertEqual(second_stock["data_source"], "Tushare缓存")
        self.assertEqual(second_stats["tushare_cache_hits"], 1)
        self.assertEqual(second_stats["tushare_success"], 0)
        self.assertEqual(second_log["provider"], "tushare.daily(cache)")
        self.assertIn("Tushare缓存命中1只", second_log["diagnostic_note"])

    def test_incompatible_cache_object_is_ignored_without_breaking_tushare_primary(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        tushare_calls = []

        result = bundle(
            "2026-05-14",
            candidates=[{"code": "000010", "name": "无缓存实现样本", "turnover": 18.0, "sector": "军工"}],
            stock_full_info={"000010": {"change_pct": 6.2}},
            get_cache=lambda: {},
            fetch_tushare_turnover_history=lambda code, start_date, end_date: (
                tushare_calls.append((code, start_date, end_date)) or [10.0, 11.0, 12.0]
            ),
            fetch_quicktiny_history=lambda **kwargs: [99.0],
            baostock_source_factory=lambda: _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
            enable_live_quicktiny=False,
            enable_baostock_fallback=False,
        )

        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual(tushare_calls, [("000010", "2026-04-19", "2026-05-14")])
        self.assertEqual(stocks_with_history[0]["hist_turnover"], [10.0, 11.0, 12.0])
        self.assertEqual(stocks_with_history[0]["data_source"], "Tushare")
        self.assertTrue(any("历史缓存不可用" in line for line in emitted))

    def test_tushare_turnover_history_is_primary_before_quicktiny_and_baostock(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        quicktiny_calls = []
        baostock_created = []
        tushare_calls = []

        result = bundle(
            "2026-05-14",
            candidates=[{"code": "000001", "name": "Tushare样本", "turnover": 18.0, "sector": "军工"}],
            stock_full_info={"000001": {"change_pct": 6.2}},
            get_cache=lambda: _CacheStub(),
            fetch_tushare_turnover_history=lambda code, start_date, end_date: (
                tushare_calls.append((code, start_date, end_date)) or [11.0, 12.0, 13.0]
            ),
            fetch_quicktiny_history=lambda **kwargs: quicktiny_calls.append(kwargs) or [99.0],
            baostock_source_factory=lambda: baostock_created.append(True) or _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
        )

        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual(tushare_calls, [("000001", "2026-04-19", "2026-05-14")])
        self.assertEqual(quicktiny_calls, [])
        self.assertEqual(baostock_created, [])
        self.assertEqual(stocks_with_history[0]["hist_turnover"], [11.0, 12.0, 13.0])
        self.assertEqual(stocks_with_history[0]["data_source"], "Tushare")
        self.assertEqual(result["results"]["history_fetch_stats"]["tushare_success"], 1)
        self.assertEqual(result["module_logs"][0]["details"]["provider"], "tushare.daily")
        self.assertTrue(any("Tushare优先" in line for line in emitted))

    def test_tushare_turnover_history_runs_with_bounded_concurrency(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        quicktiny_calls = []
        baostock_created = []
        lock = threading.Lock()
        concurrent_gate = threading.Event()
        active_calls = 0
        max_active_calls = 0

        def fetch_tushare(code, start_date, end_date):
            nonlocal active_calls, max_active_calls
            with lock:
                active_calls += 1
                max_active_calls = max(max_active_calls, active_calls)
                if active_calls >= 2:
                    concurrent_gate.set()
            concurrent_gate.wait(timeout=0.2)
            time.sleep(0.02)
            with lock:
                active_calls -= 1
            return [float(int(code[-1]))]

        result = bundle(
            "2026-05-14",
            candidates=[
                {"code": "000011", "name": "并发一号", "turnover": 18.0, "sector": "军工"},
                {"code": "000012", "name": "并发二号", "turnover": 17.0, "sector": "军工"},
                {"code": "000013", "name": "并发三号", "turnover": 16.0, "sector": "军工"},
                {"code": "000014", "name": "并发四号", "turnover": 15.0, "sector": "军工"},
            ],
            stock_full_info={
                "000011": {"change_pct": 1.1},
                "000012": {"change_pct": 1.2},
                "000013": {"change_pct": 1.3},
                "000014": {"change_pct": 1.4},
            },
            get_cache=lambda: _CacheStub(),
            fetch_tushare_turnover_history=fetch_tushare,
            fetch_quicktiny_history=lambda **kwargs: quicktiny_calls.append(kwargs) or [99.0],
            baostock_source_factory=lambda: baostock_created.append(True) or _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
            tushare_history_max_workers=2,
        )

        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual([item["code"] for item in stocks_with_history], ["000011", "000012", "000013", "000014"])
        self.assertEqual([item["hist_turnover"] for item in stocks_with_history], [[1.0], [2.0], [3.0], [4.0]])
        self.assertGreater(max_active_calls, 1)
        self.assertLessEqual(max_active_calls, 2)
        self.assertEqual(quicktiny_calls, [])
        self.assertEqual(baostock_created, [])
        self.assertEqual(result["results"]["history_fetch_stats"]["tushare_success"], 4)

    def test_tushare_empty_history_records_failed_codes_for_diagnostics(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []

        result = bundle(
            "2026-05-14",
            candidates=[
                {"code": "000021", "name": "有数据样本", "turnover": 18.0, "sector": "军工"},
                {"code": "000022", "name": "空数据样本", "turnover": 17.0, "sector": "军工"},
            ],
            stock_full_info={},
            get_cache=lambda: _CacheStub(),
            fetch_tushare_turnover_history=lambda code, start_date, end_date: [21.0] if code == "000021" else [],
            fetch_quicktiny_history=lambda **kwargs: [],
            baostock_source_factory=lambda: _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
            enable_live_quicktiny=False,
            enable_baostock_fallback=False,
        )

        stats = result["results"]["history_fetch_stats"]
        self.assertEqual(stats["tushare_success"], 1)
        self.assertEqual(stats["tushare_fail"], 1)
        self.assertEqual(stats["tushare_failed_codes"], ["000022"])
        self.assertEqual(result["module_logs"][0]["details"]["tushare_failed_codes"], ["000022"])
        self.assertTrue(any("Tushare成交额历史空数据: 000022" in line for line in emitted))

    def test_tushare_empty_history_retries_once_before_fallback(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        calls_by_code = {}
        quicktiny_calls = []

        def fetch_tushare(code, start_date, end_date):
            calls_by_code[code] = calls_by_code.get(code, 0) + 1
            if calls_by_code[code] == 1:
                return []
            return [22.0]

        result = bundle(
            "2026-05-14",
            candidates=[{"code": "000022", "name": "重试样本", "turnover": 17.0, "sector": "军工"}],
            stock_full_info={},
            get_cache=lambda: _CacheStub(),
            fetch_tushare_turnover_history=fetch_tushare,
            fetch_quicktiny_history=lambda **kwargs: quicktiny_calls.append(kwargs) or [99.0],
            baostock_source_factory=lambda: _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
            enable_live_quicktiny=False,
            enable_baostock_fallback=False,
            tushare_history_empty_retries=1,
        )

        stats = result["results"]["history_fetch_stats"]
        stocks_with_history = result["results"]["stocks_with_history"]
        log_details = result["module_logs"][0]["details"]
        self.assertEqual(calls_by_code, {"000022": 2})
        self.assertEqual(stats["tushare_success"], 1)
        self.assertEqual(stats["tushare_fail"], 0)
        self.assertEqual(stats["tushare_failed_codes"], [])
        self.assertEqual(stocks_with_history[0]["hist_turnover"], [22.0])
        self.assertEqual(log_details["tushare_history_max_workers"], 1)
        self.assertEqual(log_details["tushare_history_empty_retries"], 1)
        self.assertIn("Tushare并发1", log_details["diagnostic_note"])
        self.assertIn("空数据重试1次", log_details["diagnostic_note"])
        self.assertEqual(quicktiny_calls, [])
        self.assertTrue(any("Tushare成交额历史空数据重试" in line for line in emitted))

    def test_high_tushare_empty_rate_triggers_serial_rescue_before_fallback(self):
        request_module = importlib.import_module("domains.watch_candidates.request")
        bundle = request_module.collect_watch_candidate_history_request_bundle

        timer = _TimerStub()
        emitted = []
        calls_by_code = {}
        calls_lock = threading.Lock()
        quicktiny_calls = []

        def fetch_tushare(code, start_date, end_date):
            with calls_lock:
                calls_by_code[code] = calls_by_code.get(code, 0) + 1
                call_count = calls_by_code[code]
            if code in {"000031", "000032"} and call_count == 1:
                return []
            return [float(int(code[-1]))]

        result = bundle(
            "2026-05-14",
            candidates=[
                {"code": "000031", "name": "补救一号", "turnover": 18.0, "sector": "军工"},
                {"code": "000032", "name": "补救二号", "turnover": 17.0, "sector": "军工"},
                {"code": "000033", "name": "正常三号", "turnover": 16.0, "sector": "军工"},
                {"code": "000034", "name": "正常四号", "turnover": 15.0, "sector": "军工"},
            ],
            stock_full_info={},
            get_cache=lambda: _CacheStub(),
            fetch_tushare_turnover_history=fetch_tushare,
            fetch_quicktiny_history=lambda **kwargs: quicktiny_calls.append(kwargs) or [99.0],
            baostock_source_factory=lambda: _BaoStockStub(),
            timer=timer,
            emit=emitted.append,
            enable_live_quicktiny=False,
            enable_baostock_fallback=False,
            tushare_history_max_workers=4,
            tushare_history_empty_retries=0,
            tushare_empty_rate_rescue_threshold=0.5,
        )

        stats = result["results"]["history_fetch_stats"]
        log_details = result["module_logs"][0]["details"]
        stocks_with_history = result["results"]["stocks_with_history"]
        self.assertEqual(calls_by_code, {"000031": 2, "000032": 2, "000033": 1, "000034": 1})
        self.assertEqual(stats["tushare_success"], 4)
        self.assertEqual(stats["tushare_fail"], 0)
        self.assertEqual(stats["tushare_rescue_success"], 2)
        self.assertEqual(stats["tushare_rescue_triggered"], 1)
        self.assertEqual(stats["tushare_failed_codes"], [])
        self.assertEqual([item["code"] for item in stocks_with_history], ["000031", "000032", "000033", "000034"])
        self.assertEqual(log_details["tushare_rescue_triggered"], 1)
        self.assertIn("串行补救2只", log_details["diagnostic_note"])
        self.assertIn("补救阈值50%", log_details["diagnostic_note"])
        self.assertEqual(log_details["tushare_empty_rate_rescue_threshold"], 0.5)
        self.assertEqual(quicktiny_calls, [])
        self.assertTrue(any("Tushare空返回率50.0%" in line for line in emitted))

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
