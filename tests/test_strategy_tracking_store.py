import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _run_legacy_entry_probe(script_body):
    stub_setup = """
import sys
import types

def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module

sys.path.insert(0, {scripts_path!r})
sys.modules.update(
    {{
        "data_collector": _stub_module("data_collector", AShareDataCollector=type("AShareDataCollector", (), {{}})),
        "ths_hot_stock": _stub_module(
            "ths_hot_stock",
            fetch_ths_hot_stock=lambda *args, **kwargs: [],
            fetch_hot_stock_with_fallback=lambda *args, **kwargs: [],
        ),
        "ths_hot_list": _stub_module("ths_hot_list", fetch_hot_plate=lambda *args, **kwargs: []),
        "tencent_finance_data": _stub_module("tencent_finance_data", TencentFinanceData=type("TencentFinanceData", (), {{}})),
        "xuangubao_intraday": _stub_module(
            "xuangubao_intraday",
            XuangubaoIntradayAnalyzer=type("XuangubaoIntradayAnalyzer", (), {{}}),
        ),
        "limit_up_down_pool": _stub_module(
            "limit_up_down_pool",
            get_limit_up_pool=lambda *args, **kwargs: ([], set()),
            get_limit_down_pool=lambda *args, **kwargs: ([], set()),
            mark_limit_status=lambda *args, **kwargs: {{}},
        ),
        "strong_stock_pool": _stub_module(
            "strong_stock_pool",
            get_strong_stock_pool=lambda *args, **kwargs: [],
            analyze_strong_stocks_by_sector=lambda *args, **kwargs: {{}},
        ),
        "data_validator": _stub_module("data_validator", DataValidator=type("DataValidator", (), {{}})),
        "quantitative_analyzer": _stub_module(
            "quantitative_analyzer",
            VolumeAnomalyDetector=type("VolumeAnomalyDetector", (), {{}}),
            LHBAnalyzer=type("LHBAnalyzer", (), {{}}),
            ResonanceAnalyzer=type("ResonanceAnalyzer", (), {{}}),
            SignalGenerator=type("SignalGenerator", (), {{}}),
            analyze_volume_anomaly=lambda *args, **kwargs: {{}},
            analyze_lhb=lambda *args, **kwargs: {{}},
            calculate_resonance=lambda *args, **kwargs: {{}},
            generate_trade_signals=lambda *args, **kwargs: {{}},
        ),
        "hot_list_integrated": _stub_module(
            "hot_list_integrated",
            get_integrated_hot_list=lambda *args, **kwargs: {{}},
            analyze_sector_distribution=lambda *args, **kwargs: {{}},
        ),
        "history_cache": _stub_module(
            "history_cache",
            get_cache=lambda *args, **kwargs: {{}},
            HistoryCache=type("HistoryCache", (), {{}}),
        ),
        "llm_service": _stub_module("llm_service", get_llm_service=lambda *args, **kwargs: None),
    }}
)
""".format(scripts_path=str(ROOT / "scripts"))

    result = subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return result


class StrategyTrackingStoreTest(unittest.TestCase):
    def _load_store_module(self):
        try:
            return __import__("report.strategy_tracking_store", fromlist=["strategy_tracking_store"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_store should exist: {error}")

    def test_report_scoped_read_cache_reuses_by_mode_and_resets_after_scope(self):
        store = self._load_store_module()

        class StubService:
            def __init__(self):
                self.read_count = 0

            def is_postgres_backed(self):
                return True

            def load_strategy_performance_ledger(self, mode="frozen"):
                self.read_count += 1
                return {
                    "mode": mode,
                    "records": [{"report_date": "2026-08-05"}],
                }

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        cache = {}
        with patch.object(store, "DatabaseService", StubDatabaseService, create=True), patch.dict(
            "os.environ",
            {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"},
            clear=False,
        ):
            with store.strategy_performance_ledger_read_cache(cache):
                first = store.load_strategy_performance_ledger(mode="frozen")
                first["records"].append({"report_date": "mutated"})
                second = store.load_strategy_performance_ledger(mode="frozen")
                replay = store.load_strategy_performance_ledger(mode="replay")
            third = store.load_strategy_performance_ledger(mode="frozen")

        self.assertEqual(service.read_count, 3)
        self.assertEqual(second["records"], [{"report_date": "2026-08-05"}])
        self.assertEqual(replay["mode"], "replay")
        self.assertEqual(third["mode"], "frozen")

    def test_report_scoped_read_cache_invalidates_matching_mode_after_save(self):
        store = self._load_store_module()

        class StubService:
            def __init__(self):
                self.read_count = 0
                self.ledger = {"version": 1}

            def is_postgres_backed(self):
                return True

            def load_strategy_performance_ledger(self, mode="frozen"):
                self.read_count += 1
                return {**self.ledger, "mode": mode}

            def save_strategy_performance_ledger(self, ledger, mode="frozen"):
                self.ledger = dict(ledger)
                return {"saved": True, "mode": mode}

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with patch.object(store, "DatabaseService", StubDatabaseService, create=True), patch.dict(
            "os.environ",
            {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"},
            clear=False,
        ):
            with store.strategy_performance_ledger_read_cache({}):
                first = store.load_strategy_performance_ledger(mode="frozen")
                store.save_strategy_performance_ledger({"version": 2}, mode="frozen")
                second = store.load_strategy_performance_ledger(mode="frozen")

        self.assertEqual(first["version"], 1)
        self.assertEqual(second["version"], 2)
        self.assertEqual(service.read_count, 2)

    def test_postgres_configured_ledger_load_and_save_use_database_service(self):
        store = self._load_store_module()

        class StubService:
            def __init__(self):
                self.saved = None

            def is_postgres_backed(self):
                return True

            def load_strategy_performance_ledger(self, mode="frozen"):
                return {"version": "v-test", "mode": mode, "records": [{"report_date": "2026-05-29"}]}

            def save_strategy_performance_ledger(self, ledger, mode="frozen"):
                self.saved = {"ledger": dict(ledger), "mode": mode}
                return "postgresql://strategy_performance/frozen"

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tempdir:
            ledger_path = Path(tempdir) / "strategy_performance.json"
            ledger_path.write_text(json.dumps({"records": [{"report_date": "json"}]}), encoding="utf-8")
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    loaded = store.load_strategy_performance_ledger(
                        mode="frozen",
                        helpers={
                            "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                            "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                        },
                    )
                    saved = store.save_strategy_performance_ledger(
                        {"records": [{"report_date": "2026-05-30"}]},
                        mode="frozen",
                        helpers={
                            "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                            "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                        },
                    )

            self.assertEqual(loaded["records"][0]["report_date"], "2026-05-29")
            self.assertEqual(service.saved["ledger"]["records"][0]["report_date"], "2026-05-30")
            self.assertEqual(saved, "postgresql://strategy_performance/frozen")
            self.assertEqual(json.loads(ledger_path.read_text(encoding="utf-8"))["records"][0]["report_date"], "json")

    def test_postgres_only_runtime_accepts_database_service_local_default(self):
        store = self._load_store_module()

        class StubService:
            def is_postgres_backed(self):
                return True

            def load_strategy_performance_ledger(self, mode="frozen"):
                return {"version": "v-test", "mode": mode, "records": [{"report_date": "postgres"}]}

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            ledger_path = Path(tempdir) / "strategy_performance.json"
            ledger_path.write_text(json.dumps({"records": [{"report_date": "json"}]}), encoding="utf-8")
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=True):
                    loaded = store.load_strategy_performance_ledger(
                        mode="frozen",
                        helpers={
                            "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                            "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                        },
                    )

            self.assertEqual(loaded["records"][0]["report_date"], "postgres")
            self.assertEqual(json.loads(ledger_path.read_text(encoding="utf-8"))["records"][0]["report_date"], "json")

    def test_postgres_configured_factor_snapshot_uses_database_service(self):
        store = self._load_store_module()

        class StubService:
            def __init__(self):
                self.saved = None

            def is_postgres_backed(self):
                return True

            def save_factor_snapshot(self, target_date, factor_snapshot, mode="frozen"):
                self.saved = {
                    "target_date": target_date,
                    "factor_snapshot": dict(factor_snapshot),
                    "mode": mode,
                }
                return {
                    "path": "postgresql://factor-snapshots/2026-05-29",
                    "mode": mode,
                    "saved": True,
                    "version": "snapshot-v1",
                    "saved_at": "2026-05-29 15:10:00",
                }

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_path = Path(tempdir) / "2026-05-29.json"
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    result = store.save_factor_snapshot(
                        "2026-05-29",
                        {"foo": "bar"},
                        mode="frozen",
                        helpers={
                            "_get_factor_snapshot_path": lambda target_date, mode="frozen": str(snapshot_path),
                            "_make_serializable": lambda value: value,
                            "STRATEGY_FACTOR_SNAPSHOT_VERSION": "snapshot-v1",
                            "LEDGER_MODE_FROZEN": "frozen",
                            "LEDGER_MODE_REPLAY": "replay",
                        },
                    )

        self.assertEqual(service.saved["target_date"], "2026-05-29")
        self.assertEqual(service.saved["factor_snapshot"], {"foo": "bar"})
        self.assertEqual(result["path"], "postgresql://factor-snapshots/2026-05-29")
        self.assertFalse(snapshot_path.exists())

    def test_postgres_configured_service_failure_does_not_read_legacy_ledger(self):
        store = self._load_store_module()

        class BrokenDatabaseService:
            @classmethod
            def from_environment(cls):
                raise RuntimeError("database unavailable")

        with tempfile.TemporaryDirectory() as tempdir:
            ledger_path = Path(tempdir) / "strategy_performance.json"
            ledger_path.write_text(json.dumps({"records": [{"report_date": "json"}]}), encoding="utf-8")
            with patch.object(store, "DatabaseService", BrokenDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                        store.load_strategy_performance_ledger(
                            mode="frozen",
                            helpers={
                                "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                                "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                            },
                        )

    def test_postgres_configured_missing_writer_does_not_write_legacy_snapshot(self):
        store = self._load_store_module()

        class StubService:
            def is_postgres_backed(self):
                return True

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_path = Path(tempdir) / "2026-05-29.json"
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "factor snapshot writer"):
                        store.save_factor_snapshot(
                            "2026-05-29",
                            {"foo": "bar"},
                            mode="frozen",
                            helpers={
                                "_get_factor_snapshot_path": lambda target_date, mode="frozen": str(snapshot_path),
                                "_make_serializable": lambda value: value,
                                "STRATEGY_FACTOR_SNAPSHOT_VERSION": "snapshot-v1",
                                "LEDGER_MODE_FROZEN": "frozen",
                                "LEDGER_MODE_REPLAY": "replay",
                            },
                        )
            self.assertFalse(snapshot_path.exists())

    def test_postgres_configured_missing_ledger_reader_does_not_read_legacy_file(self):
        store = self._load_store_module()

        class StubService:
            def is_postgres_backed(self):
                return True

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            ledger_path = Path(tempdir) / "strategy_performance.json"
            ledger_path.write_text(json.dumps({"records": [{"report_date": "json"}]}), encoding="utf-8")
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "ledger reader"):
                        store.load_strategy_performance_ledger(
                            mode="frozen",
                            helpers={
                                "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                                "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                            },
                        )
            self.assertEqual(json.loads(ledger_path.read_text(encoding="utf-8"))["records"][0]["report_date"], "json")

    def test_postgres_configured_missing_ledger_writer_does_not_write_legacy_file(self):
        store = self._load_store_module()

        class StubService:
            def is_postgres_backed(self):
                return True

            def load_strategy_performance_ledger(self, mode="frozen"):
                return {"records": []}

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            ledger_path = Path(tempdir) / "strategy_performance.json"
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "ledger writer"):
                        store.save_strategy_performance_ledger(
                            {"records": [{"report_date": "2026-05-29"}]},
                            mode="frozen",
                            helpers={
                                "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                                "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                            },
                        )
            self.assertFalse(ledger_path.exists())

    def test_postgres_only_runtime_without_database_rejects_legacy_ledger_file(self):
        store = self._load_store_module()

        class StubService:
            def is_postgres_backed(self):
                return False

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            ledger_path = Path(tempdir) / "strategy_performance.json"
            ledger_path.write_text(json.dumps({"records": [{"report_date": "json"}]}), encoding="utf-8")
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "PostgreSQL-only strategy tracking storage"):
                        store.load_strategy_performance_ledger(
                            mode="frozen",
                            helpers={
                                "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                                "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                            },
                        )
            self.assertEqual(json.loads(ledger_path.read_text(encoding="utf-8"))["records"][0]["report_date"], "json")

    def test_postgres_only_runtime_without_database_rejects_legacy_factor_snapshot(self):
        store = self._load_store_module()

        class StubService:
            def is_postgres_backed(self):
                return False

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_path = Path(tempdir) / "2026-05-29.json"
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "PostgreSQL-only strategy tracking storage"):
                        store.save_factor_snapshot(
                            "2026-05-29",
                            {"foo": "bar"},
                            mode="frozen",
                            helpers={
                                "_get_factor_snapshot_path": lambda target_date, mode="frozen": str(snapshot_path),
                                "_make_serializable": lambda value: value,
                                "STRATEGY_FACTOR_SNAPSHOT_VERSION": "snapshot-v1",
                                "LEDGER_MODE_FROZEN": "frozen",
                                "LEDGER_MODE_REPLAY": "replay",
                            },
                        )
            self.assertFalse(snapshot_path.exists())

    def test_legacy_load_ledger_wrapper_delegates_to_store(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload = {"records": []}
with patch.object(daily_report_entry_demo, "run_load_strategy_performance_ledger", return_value=payload) as runtime_mock:
    result = daily_report_entry_demo.load_strategy_performance_ledger(mode="replay")

assert runtime_mock.call_args.kwargs["mode"] == "replay"
assert "helpers" in runtime_mock.call_args.kwargs
assert result == payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_save_ledger_wrapper_delegates_to_store(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_save_strategy_performance_ledger", return_value="/tmp/ledger.json") as runtime_mock:
    result = daily_report_entry_demo.save_strategy_performance_ledger({"records": []}, mode="replay")

assert runtime_mock.call_args[0][0] == {"records": []}
assert runtime_mock.call_args.kwargs["mode"] == "replay"
assert "helpers" in runtime_mock.call_args.kwargs
assert result == "/tmp/ledger.json"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_save_factor_snapshot_wrapper_delegates_to_store(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload = {"saved": True}
with patch.object(daily_report_entry_demo, "run_save_factor_snapshot", return_value=payload) as runtime_mock:
    result = daily_report_entry_demo.save_factor_snapshot("2026-04-23", {"foo": "bar"}, mode="replay")

assert runtime_mock.call_args[0][0] == "2026-04-23"
assert runtime_mock.call_args[0][1] == {"foo": "bar"}
assert runtime_mock.call_args.kwargs["mode"] == "replay"
assert "helpers" in runtime_mock.call_args.kwargs
assert result == payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_store_path_wrappers_delegate_to_store(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_get_strategy_performance_path", return_value="/tmp/strategy_performance_replay.json") as ledger_mock, \
     patch.object(daily_report_entry_demo, "run_get_factor_snapshot_path", return_value="/tmp/2026-04-23_replay.json") as snapshot_mock:
    ledger_path = daily_report_entry_demo._get_strategy_performance_path(mode="replay")
    snapshot_path = daily_report_entry_demo._get_factor_snapshot_path("2026-04-23", mode="replay")

assert ledger_mock.call_args.kwargs["mode"] == "replay"
assert "helpers" in ledger_mock.call_args.kwargs
assert snapshot_mock.call_args[0][0] == "2026-04-23"
assert snapshot_mock.call_args.kwargs["mode"] == "replay"
assert "helpers" in snapshot_mock.call_args.kwargs
assert ledger_path == "/tmp/strategy_performance_replay.json"
assert snapshot_path == "/tmp/2026-04-23_replay.json"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_load_strategy_performance_ledger_reads_existing_file(self):
        store = self._load_store_module()
        with tempfile.TemporaryDirectory() as tempdir:
            ledger_path = Path(tempdir) / "strategy_performance_replay.json"
            ledger_path.write_text(
                json.dumps({"updated_at": "2026-04-23 09:30:00", "records": [{"report_date": "2026-04-22"}]}),
                encoding="utf-8",
            )

            result = store.load_strategy_performance_ledger(
                mode="replay",
                helpers={
                    "_get_strategy_performance_path": lambda mode="frozen": str(ledger_path),
                    "STRATEGY_PERFORMANCE_LEDGER_VERSION": "v-test",
                },
            )

        self.assertEqual(result["version"], "v-test")
        self.assertEqual(result["mode"], "replay")
        self.assertEqual(result["records"][0]["report_date"], "2026-04-22")

    def test_save_factor_snapshot_honors_frozen_existing_file(self):
        store = self._load_store_module()
        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_path = Path(tempdir) / "2026-04-23.json"
            snapshot_path.write_text("{}", encoding="utf-8")

            result = store.save_factor_snapshot(
                "2026-04-23",
                {"foo": "bar"},
                mode="frozen",
                helpers={
                    "_get_factor_snapshot_path": lambda target_date, mode="frozen": str(snapshot_path),
                    "_make_serializable": lambda value: value,
                    "STRATEGY_FACTOR_SNAPSHOT_VERSION": "snapshot-v1",
                    "LEDGER_MODE_FROZEN": "frozen",
                    "LEDGER_MODE_REPLAY": "replay",
                },
            )

        self.assertFalse(result["saved"])
        self.assertTrue(result["frozen"])
        self.assertEqual(result["path"], str(snapshot_path))
        self.assertEqual(result["version"], "snapshot-v1")

    def test_store_path_helpers_build_mode_specific_paths(self):
        store = self._load_store_module()
        with tempfile.TemporaryDirectory() as tempdir:
            fake_file = Path(tempdir) / "scripts" / "report" / "strategy_tracking_store.py"
            fake_file.parent.mkdir(parents=True, exist_ok=True)
            fake_file.write_text("# stub", encoding="utf-8")

            ledger_path = store.get_strategy_performance_path(
                mode="replay",
                helpers={"__file__": str(fake_file), "os": os, "LEDGER_MODE_REPLAY": "replay"},
            )
            snapshot_path = store.get_factor_snapshot_path(
                "2026-04-23",
                mode="replay",
                helpers={"__file__": str(fake_file), "os": os, "LEDGER_MODE_REPLAY": "replay"},
            )

        self.assertTrue(ledger_path.endswith("data/strategy_performance_replay.json"))
        self.assertTrue(snapshot_path.endswith("data/factor_snapshots/replay/2026-04-23_replay.json"))


if __name__ == "__main__":
    unittest.main()
