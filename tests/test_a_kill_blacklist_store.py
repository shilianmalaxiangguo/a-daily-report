import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from risk import a_kill_blacklist_store as store
from risk.a_kill_blacklist_store import (
    get_active_a_kill_records,
    is_stock_in_a_kill_cooldown,
    load_a_kill_blacklist,
    update_a_kill_blacklist,
)


class AKillBlacklistStoreTest(unittest.TestCase):
    def test_update_and_get_active_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a_kill_blacklist.json"
            updated = update_a_kill_blacklist(
                "2026-04-20",
                [{"name": "军工一号", "code": "SZ000001"}],
                sector_name="军工",
                path=str(path),
            )
            self.assertEqual(updated[0]["code"], "000001")

            data = load_a_kill_blacklist(path=str(path))
            self.assertEqual(len(data["records"]), 1)

            active = get_active_a_kill_records("2026-04-22", path=str(path))
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["remaining_days"], 23)

            in_cooldown, record = is_stock_in_a_kill_cooldown({"code": "000001"}, active)
            self.assertTrue(in_cooldown)
            self.assertEqual(record["name"], "军工一号")

    def test_postgres_configured_update_and_active_records_use_database_service(self):
        class StubService:
            def __init__(self):
                self.saved = []

            def is_postgres_backed(self):
                return True

            def replace_a_kill_cooling_records(self, records):
                self.saved = list(records)
                return len(self.saved)

            def query_a_kill_cooling_records(self):
                return []

            def query_active_a_kill_cooling_records(self, target_date):
                return [
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "sector": "军工",
                        "a_kill_date": "2026-04-20",
                        "ban_until": "2026-05-15",
                        "remaining_days": 23,
                    }
                ]

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tempdir:
            json_path = Path(tempdir) / "a_kill_blacklist.json"
            json_path.write_text(json.dumps({"records": []}), encoding="utf-8")
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    updated = update_a_kill_blacklist(
                        "2026-04-20",
                        [{"name": "军工一号", "code": "SZ000001"}],
                        sector_name="军工",
                        path=str(json_path),
                    )
                    active = get_active_a_kill_records("2026-04-22", path=str(json_path))

            self.assertEqual(updated[0]["code"], "000001")
            self.assertEqual(service.saved[0]["name"], "军工一号")
            self.assertEqual(active[0]["remaining_days"], 23)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["records"], [])

    def test_postgres_configured_missing_writer_does_not_write_json(self):
        class StubService:
            def is_postgres_backed(self):
                return True

            def query_a_kill_cooling_records(self):
                return []

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            json_path = Path(tempdir) / "a_kill_blacklist.json"
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "A-kill cooling writer"):
                        update_a_kill_blacklist(
                            "2026-04-20",
                            [{"name": "军工一号", "code": "SZ000001"}],
                            sector_name="军工",
                            path=str(json_path),
                        )
            self.assertFalse(json_path.exists())

    def test_postgres_configured_missing_active_reader_does_not_read_json(self):
        class StubService:
            def is_postgres_backed(self):
                return True

            def query_a_kill_cooling_records(self):
                return []

            def replace_a_kill_cooling_records(self, records):
                return len(records)

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            json_path = Path(tempdir) / "a_kill_blacklist.json"
            json_path.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "code": "000001",
                                "name": "json",
                                "a_kill_date": "2026-04-20",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(store, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "A-kill cooling reader"):
                        get_active_a_kill_records("2026-04-22", path=str(json_path))
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["records"][0]["name"], "json")

    def test_postgres_only_runtime_without_database_rejects_json_reader(self):
        with tempfile.TemporaryDirectory() as tempdir:
            json_path = Path(tempdir) / "a_kill_blacklist.json"
            json_path.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "code": "000001",
                                "name": "json",
                                "a_kill_date": "2026-04-20",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "PostgreSQL-only A-kill cooling storage"):
                    get_active_a_kill_records("2026-04-22", path=str(json_path))
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["records"][0]["name"], "json")


if __name__ == "__main__":
    unittest.main()
