import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.market_language_translation import (
    build_market_language_source_projection,
    build_market_language_translation,
    canonical_market_language_hash,
)
from report.market_language_translation_artifacts import (
    fresh_market_language_path,
    load_fresh_market_language_translation,
    prepare_market_language_translation,
    replay_market_language_path,
    write_fresh_market_language_translation,
    write_replay_market_language_translation,
)


def _eod_data(target_date="2026-07-10"):
    return {
        "indices": {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": -0.8,
                "trade_date": target_date,
                "data_source": "tushare.index_daily",
            }
        },
        "market_stats": {
            "up_count": 1200,
            "down_count": 3400,
            "flat_count": 100,
            "trade_date": target_date,
            "data_source": "tushare.daily",
        },
    }


def _fresh_artifact(target_date="2026-07-10"):
    projection = build_market_language_source_projection(
        _eod_data(target_date),
        target_date=target_date,
        analysis_mode="fresh",
    )
    return build_market_language_translation(
        projection,
        target_date=target_date,
        analysis_mode="fresh",
    )


def _minute_data(code, name, target_date="2026-07-10"):
    rows = []
    price = 100.0
    timestamp = dt.datetime.fromisoformat(f"{target_date} 09:31:00")
    for _ in range(70):
        open_price = price
        price *= 0.999
        rows.append(
            {
                "datetime": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "open": open_price,
                "high": open_price,
                "low": price,
                "close": price,
                "volume": 1000.0,
                "amount": price * 1000.0,
            }
        )
        timestamp += dt.timedelta(minutes=1)
    return {
        "trade_date": target_date,
        "bar_period_minutes": 1,
        "instrument": {"type": "stock", "code": code, "name": name},
        "source": {
            "provider": "unit_test.one_minute",
            "source_date": target_date,
            "query_date": target_date,
            "bar_time_semantics": "interval_end",
        },
        "minute_bars": rows,
    }


class _MemoryPostgresService:
    def __init__(self):
        self.rows = {}
        self.write_count = 0

    def is_postgres_backed(self):
        return True

    def replace_market_language_translation_artifact(self, artifact):
        self.write_count += 1
        self.rows[artifact["target_date"]] = copy.deepcopy(artifact)
        return {"source": "postgresql.market_language_translation.v1", "field_count": 1}

    def load_market_language_translation_artifact(self, target_date):
        return copy.deepcopy(self.rows.get(target_date) or {})


class MarketLanguageTranslationLifecycleTest(unittest.TestCase):
    def test_prepare_fresh_builds_once_without_writing_into_shared_data(self):
        data = _eod_data()
        before = copy.deepcopy(data)

        artifact = prepare_market_language_translation(
            data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertEqual(data, before)
        self.assertNotIn("market_language_translation", data)
        self.assertEqual(artifact["artifact_origin"], "computed")
        self.assertIsNone(artifact["posthoc_validation"])

    def test_prepare_replay_extracts_legacy_artifact_and_keeps_posthoc_separate(self):
        artifact = _fresh_artifact()
        data = _eod_data()
        data["market_language_translation"] = copy.deepcopy(artifact)
        data["market_language_translation_artifact"] = copy.deepcopy(artifact)

        replay = prepare_market_language_translation(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )

        self.assertNotIn("market_language_translation", data)
        self.assertNotIn("market_language_translation_artifact", data)
        self.assertEqual(replay["artifact_origin"], "loaded")
        self.assertEqual(replay["analysis_mode"], "replay")
        self.assertIsNotNone(replay["posthoc_validation"])
        self.assertIsNone(artifact["posthoc_validation"])

    def test_loaded_artifact_does_not_join_posthoc_from_another_instrument(self):
        source_data = _minute_data("600000.SH", "甲标的")
        source_projection = build_market_language_source_projection(
            source_data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        source_artifact = build_market_language_translation(
            source_projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        replay_data = _minute_data("300001.SZ", "乙标的")
        replay_data["market_language_translation"] = copy.deepcopy(source_artifact)

        replay = prepare_market_language_translation(
            replay_data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )

        self.assertEqual(replay["artifact_origin"], "loaded")
        self.assertEqual(replay["primary_instrument"]["code"], "600000.SH")
        self.assertEqual(replay["posthoc_validation"]["validation_status"], "insufficient")
        self.assertEqual(replay["posthoc_validation"]["event_reviews"], [])
        self.assertEqual(
            replay["posthoc_validation"]["missing_evidence"],
            ["primary_instrument_identity_match"],
        )

    def test_loaded_artifact_does_not_join_posthoc_from_different_minute_content(self):
        source_data = _minute_data("600000.SH", "甲标的")
        source_projection = build_market_language_source_projection(
            source_data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        source_artifact = build_market_language_translation(
            source_projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        replay_data = _minute_data("600000.SH", "甲标的")
        changed_row = replay_data["minute_bars"][30]
        changed_row["close"] *= 0.98
        changed_row["low"] = min(changed_row["low"], changed_row["close"])
        changed_row["amount"] = changed_row["close"] * changed_row["volume"]
        replay_data["market_language_translation"] = copy.deepcopy(source_artifact)

        replay = prepare_market_language_translation(
            replay_data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )

        self.assertEqual(replay["artifact_origin"], "loaded")
        self.assertEqual(replay["primary_instrument"]["code"], "600000.SH")
        self.assertEqual(replay["posthoc_validation"]["validation_status"], "insufficient")
        self.assertEqual(replay["posthoc_validation"]["event_reviews"], [])
        self.assertEqual(
            replay["posthoc_validation"]["missing_evidence"],
            ["primary_minute_content_hash_match"],
        )

    def test_loaded_artifact_joins_posthoc_from_matching_minute_content(self):
        source_data = _minute_data("600000.SH", "甲标的")
        source_projection = build_market_language_source_projection(
            source_data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        source_artifact = build_market_language_translation(
            source_projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        replay_data = copy.deepcopy(source_data)
        replay_data["market_language_translation"] = copy.deepcopy(source_artifact)

        replay = prepare_market_language_translation(
            replay_data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )

        self.assertEqual(replay["artifact_origin"], "loaded")
        self.assertEqual(replay["posthoc_validation"]["validation_status"], "available")
        self.assertTrue(replay["posthoc_validation"]["event_reviews"])
        self.assertNotIn(
            "primary_minute_content_hash_match",
            replay["posthoc_validation"].get("missing_evidence") or [],
        )

    def test_local_fresh_round_trip_is_exact_date_and_replay_uses_separate_path(self):
        artifact = _fresh_artifact()
        with TemporaryDirectory() as tempdir:
            fresh_result = write_fresh_market_language_translation(
                artifact,
                root_dir=tempdir,
                service=False,
            )
            loaded = load_fresh_market_language_translation(
                "2026-07-10",
                root_dir=tempdir,
                service=False,
            )

            self.assertTrue(fresh_market_language_path(tempdir, "2026-07-10").exists())
            self.assertEqual(
                canonical_market_language_hash(loaded),
                canonical_market_language_hash(artifact),
            )
            self.assertIsNone(
                load_fresh_market_language_translation(
                    "2026-07-09",
                    root_dir=tempdir,
                    service=False,
                )
            )

            replay_artifact = copy.deepcopy(artifact)
            replay_artifact["analysis_mode"] = "replay"
            replay_artifact["artifact_origin"] = "reconstructed"
            replay_result = write_replay_market_language_translation(
                replay_artifact,
                root_dir=tempdir,
            )
            self.assertTrue(replay_market_language_path(tempdir, "2026-07-10").exists())
            self.assertNotEqual(fresh_result["artifact_path"], replay_result["artifact_path"])

    def test_postgres_fresh_writer_round_trips_without_local_fallback(self):
        artifact = _fresh_artifact()
        service = _MemoryPostgresService()
        with TemporaryDirectory() as tempdir:
            result = write_fresh_market_language_translation(
                artifact,
                root_dir=tempdir,
                service=service,
            )
            loaded = load_fresh_market_language_translation(
                "2026-07-10",
                root_dir=tempdir,
                service=service,
            )

            self.assertEqual(service.write_count, 1)
            self.assertEqual(result["storage"], "postgresql")
            self.assertFalse(fresh_market_language_path(tempdir, "2026-07-10").exists())
            self.assertEqual(
                canonical_market_language_hash(loaded),
                canonical_market_language_hash(artifact),
            )

    def test_postgres_only_fresh_reader_does_not_fall_back_to_local_json_on_miss(self):
        artifact = _fresh_artifact()
        service = _MemoryPostgresService()
        with TemporaryDirectory() as tempdir:
            write_fresh_market_language_translation(
                artifact,
                root_dir=tempdir,
                service=False,
            )

            with patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
                clear=False,
            ):
                loaded = load_fresh_market_language_translation(
                    "2026-07-10",
                    root_dir=tempdir,
                    service=service,
                )

            self.assertIsNone(loaded)


if __name__ == "__main__":
    unittest.main()
