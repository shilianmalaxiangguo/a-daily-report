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

    def test_database_service_exposes_consensus_writer_and_readers(self):
        from storage.database_service import DatabaseService

        class StubRepository:
            def __init__(self):
                self.calls = []

            def append_daily_report_consensus(
                self, batch, reviews, funnel_records, *, file_hashes=None
            ):
                self.calls.append(
                    ("append", batch, reviews, funnel_records, file_hashes)
                )
                return {"status": "inserted", "write_performed": True}

            def query_daily_report_consensus_batches(
                self, target_date=None, *, run_id=None, limit=100
            ):
                self.calls.append(("batches", target_date, run_id, limit))
                return [{"run_id": run_id}]

            def query_daily_report_consensus_reviews(self, run_id, *, sequence=None):
                self.calls.append(("reviews", run_id, sequence))
                return [{"sequence": sequence}]

            def query_daily_report_consensus_funnel_records(
                self, *, run_id=None, target_date=None
            ):
                self.calls.append(("funnel", run_id, target_date))
                return [{"run_id": run_id}]

        repository = StubRepository()
        service = DatabaseService(repository)
        batch = {"run_id": "run-1", "target_date": "2026-08-21"}

        written = service.append_daily_report_consensus(
            batch,
            [{"sequence": 1}],
            [{"sample_id": "sample-1"}],
            file_hashes={"batch.json": "a" * 64},
        )
        batches = service.query_daily_report_consensus_batches(
            "2026-08-21", run_id="run-1", limit=5
        )
        reviews = service.query_daily_report_consensus_reviews("run-1", sequence=3)
        funnel = service.query_daily_report_consensus_funnel_records(
            run_id="run-1", target_date="2026-08-21"
        )

        self.assertEqual(written["status"], "inserted")
        self.assertEqual(batches, [{"run_id": "run-1"}])
        self.assertEqual(reviews, [{"sequence": 3}])
        self.assertEqual(funnel, [{"run_id": "run-1"}])
        self.assertEqual(
            [call[0] for call in repository.calls],
            ["append", "batches", "reviews", "funnel"],
        )

    def test_database_service_skips_consensus_writer_for_replay(self):
        from storage.database_service import DatabaseService

        class StubRepository:
            def append_daily_report_consensus(self, *args, **kwargs):
                raise AssertionError("replay must not call the PostgreSQL writer")

        service = DatabaseService(StubRepository())

        result = service.append_daily_report_consensus(
            {"run_id": "replay-run", "target_date": "2026-08-21"},
            [],
            [],
            allow_postgres=False,
        )

        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["write_performed"])
        self.assertEqual(result["reason"], "replay_read_only")

    def test_database_service_exposes_stock_daily_quote_history_reader(self):
        from storage.database_service import DatabaseService

        class StubRepository:
            def query_stock_daily_quote_history(self, stock_code, end_date, *, limit=10):
                return [{"date": end_date, "stock_code": stock_code, "limit": limit}]

        service = DatabaseService(StubRepository())

        result = service.query_stock_daily_quote_history("000001", "2026-08-05", limit=120)

        self.assertEqual(
            result,
            [{"date": "2026-08-05", "stock_code": "000001", "limit": 120}],
        )

    def test_database_service_stock_daily_quote_history_without_reader_is_empty(self):
        from storage.database_service import DatabaseService

        service = DatabaseService(None)

        self.assertEqual(
            service.query_stock_daily_quote_history("000001", "2026-08-05", limit=10),
            [],
        )

    def test_database_service_index_daily_reader_only_passes_close_filter_when_requested(self):
        from storage.database_service import DatabaseService

        class StubRepository:
            def __init__(self):
                self.calls = []

            def query_index_daily_bars(self, index_code, end_date, **kwargs):
                self.calls.append((index_code, end_date, kwargs))
                return []

        repository = StubRepository()
        service = DatabaseService(repository)

        service.query_index_daily_bars("sh000001", "2026-08-12", window_days=5)
        service.query_index_daily_bars(
            "sz399006",
            "2026-08-12",
            window_days=25,
            finite_positive_close_only=True,
        )

        self.assertEqual(
            repository.calls,
            [
                ("sh000001", "2026-08-12", {"window_days": 5}),
                (
                    "sz399006",
                    "2026-08-12",
                    {"window_days": 25, "finite_positive_close_only": True},
                ),
            ],
        )

    def test_database_service_exposes_cffex_replace_and_history_readers(self):
        from storage.database_service import DatabaseService

        class StubRepository:
            def __init__(self):
                self.calls = []

            def replace_cffex_index_futures_day(
                self, trade_date, contract_rows, member_rank_rows, **kwargs
            ):
                self.calls.append(("replace", trade_date, kwargs))
                return {"replaced_products": ["IF"]}

            def query_cffex_index_futures_day(self, trade_date):
                self.calls.append(("day", trade_date))
                return {"trade_date": trade_date}

            def query_cffex_index_futures_history(self, end_date, *, window_days=60):
                self.calls.append(("history", end_date, window_days))
                return {"trade_dates": [end_date]}

            def query_cffex_index_futures_history_summaries(
                self, end_date, *, window_days=60
            ):
                self.calls.append(("history_summaries", end_date, window_days))
                return {"summaries": [{"trade_date": end_date}]}

        repository = StubRepository()
        service = DatabaseService(repository)

        replaced = service.replace_cffex_index_futures_day(
            "2026-08-19", [], [], replace_products=["IF"]
        )
        day = service.query_cffex_index_futures_day("2026-08-19")
        history = service.query_cffex_index_futures_history("2026-08-19", window_days=20)
        summaries = service.query_cffex_index_futures_history_summaries(
            "2026-08-19", window_days=60
        )

        self.assertEqual(replaced, {"replaced_products": ["IF"]})
        self.assertEqual(day, {"trade_date": "2026-08-19"})
        self.assertEqual(history, {"trade_dates": ["2026-08-19"]})
        self.assertEqual(summaries, {"summaries": [{"trade_date": "2026-08-19"}]})
        self.assertEqual(
            repository.calls,
            [
                ("replace", "2026-08-19", {"replace_products": ["IF"]}),
                ("day", "2026-08-19"),
                ("history", "2026-08-19", 20),
                ("history_summaries", "2026-08-19", 60),
            ],
        )

    def test_database_service_without_repository_returns_empty_cffex_history(self):
        from storage.database_service import DatabaseService

        service = DatabaseService(None)

        self.assertEqual(service.replace_cffex_index_futures_day("2026-08-19", [], []), {})
        self.assertEqual(service.query_cffex_index_futures_day("2026-08-19"), {})
        history = service.query_cffex_index_futures_history("2026-08-19", window_days=60)
        self.assertEqual(history["trade_dates"], [])
        self.assertEqual(history["requested_window"], 60)
        summaries = service.query_cffex_index_futures_history_summaries(
            "2026-08-19", window_days=60
        )
        self.assertEqual(summaries["summaries"], [])
        self.assertEqual(summaries["requested_window"], 60)


if __name__ == "__main__":
    unittest.main()
