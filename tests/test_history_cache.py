import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class HistoryCacheTest(unittest.TestCase):
    def test_history_cache_persists_source_tagged_turnover_by_code_and_date(self):
        from history_cache import HistoryCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = HistoryCache(cache_dir=Path(tmpdir))
            cache.set("tushare:000001", "2026-05-14", [1.0, 2.0, 3.0], source="tushare_full_window")

            restored = HistoryCache(cache_dir=Path(tmpdir))

            self.assertEqual(restored.get("tushare:000001", "2026-05-14"), [1.0, 2.0, 3.0])
            self.assertEqual(restored.get_cache_stats("2026-05-14")["count"], 1)

    def test_postgres_only_history_cache_without_database_rejects_file_cache(self):
        import history_cache as module
        from history_cache import HistoryCache

        class StubService:
            def is_postgres_backed(self):
                return False

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(module, "DatabaseService", StubDatabaseService), patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
                clear=True,
            ):
                with self.assertRaisesRegex(RuntimeError, "PostgreSQL-only history cache"):
                    HistoryCache(cache_dir=Path(tmpdir)).set(
                        "tushare:000001",
                        "2026-05-14",
                        [1.0],
                    )

            self.assertEqual(list(Path(tmpdir).glob("*.json")), [])

    def test_postgres_configured_history_cache_uses_runtime_cache_table(self):
        import history_cache as module
        from history_cache import HistoryCache

        class StubService:
            def __init__(self):
                self.entries = {}

            def is_postgres_backed(self):
                return True

            def get_runtime_cache_entry(self, namespace, cache_key, target_date):
                return self.entries.get((namespace, cache_key, target_date))

            def set_runtime_cache_entry(self, namespace, cache_key, target_date, payload, *, source="", ttl_seconds=None):
                self.entries[(namespace, cache_key, target_date)] = {
                    "payload": dict(payload),
                    "source": source,
                }
                return True

            def delete_expired_runtime_cache_entries(self):
                return 0

            def get_runtime_cache_stats(self, namespace, target_date):
                return {
                    "count": sum(
                        1
                        for item_namespace, _, item_date in self.entries
                        if item_namespace == namespace and item_date == target_date
                    ),
                    "size_mb": 0.0,
                }

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(module, "DatabaseService", StubDatabaseService), patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"},
                clear=True,
            ):
                cache = HistoryCache(cache_dir=Path(tmpdir))
                cache.set("tushare:000001", "2026-05-14", [1.0, 2.0, 3.0], source="tushare_full_window")

                restored = HistoryCache(cache_dir=Path(tmpdir))

                self.assertEqual(restored.get("tushare:000001", "2026-05-14"), [1.0, 2.0, 3.0])
                self.assertEqual(restored.get_entry("tushare:000001", "2026-05-14")["source"], "tushare_full_window")
                self.assertEqual(restored.get_cache_stats("2026-05-14")["count"], 1)
                self.assertEqual(list(Path(tmpdir).glob("*.json")), [])

    def test_postgres_only_history_cache_accepts_database_service_local_default(self):
        import history_cache as module
        from history_cache import HistoryCache

        class StubService:
            def __init__(self):
                self.entries = {}

            def is_postgres_backed(self):
                return True

            def get_runtime_cache_entry(self, namespace, cache_key, target_date):
                return self.entries.get((namespace, cache_key, target_date))

            def set_runtime_cache_entry(self, namespace, cache_key, target_date, payload, *, source="", ttl_seconds=None):
                self.entries[(namespace, cache_key, target_date)] = {
                    "payload": dict(payload),
                    "source": source,
                }
                return True

            def delete_expired_runtime_cache_entries(self):
                return 0

            def get_runtime_cache_stats(self, namespace, target_date):
                return {
                    "count": sum(
                        1
                        for item_namespace, _, item_date in self.entries
                        if item_namespace == namespace and item_date == target_date
                    ),
                    "size_mb": 0.0,
                }

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(module, "DatabaseService", StubDatabaseService), patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
                clear=True,
            ):
                cache = HistoryCache(cache_dir=Path(tmpdir))
                cache.set("tushare:000001", "2026-05-14", [1.0, 2.0, 3.0], source="tushare_full_window")
                restored = HistoryCache(cache_dir=Path(tmpdir))

                self.assertEqual(restored.get("tushare:000001", "2026-05-14"), [1.0, 2.0, 3.0])
                self.assertEqual(restored.get_cache_stats("2026-05-14")["count"], 1)
                self.assertEqual(list(Path(tmpdir).glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
