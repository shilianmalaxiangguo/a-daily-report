import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DatabaseServiceTest(unittest.TestCase):
    def test_database_service_selects_postgres_from_environment(self):
        from storage.database_service import DatabaseService

        class StubPostgresRepository:
            def __init__(self, database_url):
                self.database_url = database_url

        with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
            with patch("storage.database_service.PostgresDailyFactDb", StubPostgresRepository):
                service = DatabaseService.from_environment()

        self.assertIsInstance(service.repository, StubPostgresRepository)
        self.assertEqual(service.repository.database_url, "postgresql://unit/report")

    def test_postgres_explicit_selects_local_default_when_environment_missing(self):
        from storage.database_service import DatabaseService

        class StubPostgresRepository:
            def __init__(self, database_url, **kwargs):
                self.database_url = database_url
                self.kwargs = kwargs

        def fake_database_exists(database_name):
            return database_name == "a_daily_report_psql_529"

        with patch.dict("os.environ", {}, clear=True):
            with patch("storage.database_service.PostgresDailyFactDb", StubPostgresRepository):
                service = DatabaseService.postgres_from_environment_or_local_default(
                    database_exists=fake_database_exists,
                )

        self.assertIsInstance(service.repository, StubPostgresRepository)
        self.assertEqual(service.repository.database_url, "postgresql:///a_daily_report_psql_529")
        self.assertEqual(service.repository.kwargs, {})

    def test_from_environment_without_postgres_returns_empty_service(self):
        from storage.database_service import DatabaseService

        with patch.dict("os.environ", {}, clear=True):
            with patch("storage.database_service._local_postgres_database_exists", return_value=False):
                service = DatabaseService.from_environment()

        self.assertIsNone(service.repository)

    def test_fact_store_from_environment_without_postgres_returns_empty_service_even_with_db_path(self):
        from storage.database_service import DatabaseService

        with patch.dict("os.environ", {}, clear=True):
            with patch("storage.database_service._local_postgres_database_exists", return_value=False):
                service = DatabaseService.fact_store_from_environment("/tmp/legacy.db")

        self.assertIsNone(service.repository)

    def test_database_service_exposes_postgres_fact_store_entrypoint(self):
        from storage.database_service import DatabaseService

        self.assertTrue(callable(getattr(DatabaseService, "fact_store_from_environment", None)))


if __name__ == "__main__":
    unittest.main()
