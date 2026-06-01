import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.reasoning_decision_cache import (
    load_reasoning_decision_cache,
    reasoning_cache_key,
    save_reasoning_decision_cache,
)


class ReasoningDecisionCacheTest(unittest.TestCase):
    def test_cache_key_is_stable_and_filename_safe(self):
        key = reasoning_cache_key(
            target_date="2026-04-24",
            input_hash="abcdef1234567890",
            schema_version="reasoning_decision.v1",
            prompt_version="manual-current-conversation-v1",
            model_source="manual",
        )

        self.assertEqual(key, "2026-04-24_abcdef1234567890_reasoning_decision.v1_manual-current-conversation-v1_manual")

    def test_cache_key_uses_full_input_hash_to_avoid_prefix_collision(self):
        first = reasoning_cache_key(
            target_date="2026-04-24",
            input_hash="abcdef1234560000",
            schema_version="reasoning_decision.v1",
            prompt_version="manual-current-conversation-v1",
            model_source="manual",
        )
        second = reasoning_cache_key(
            target_date="2026-04-24",
            input_hash="abcdef1234569999",
            schema_version="reasoning_decision.v1",
            prompt_version="manual-current-conversation-v1",
            model_source="manual",
        )

        self.assertNotEqual(first, second)

    def test_rejects_unsafe_raw_string_cache_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_reasoning_decision_cache(Path(tmp), "../escape")
            with self.assertRaises(ValueError):
                load_reasoning_decision_cache(Path(tmp), "already.json")

    def test_saves_and_loads_reasoning_decision_cache_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            decision = {
                "schema_version": "reasoning_decision.v1",
                "target_date": "2026-04-24",
                "input_hash": "abcdef1234567890",
                "prompt_version": "manual-current-conversation-v1",
                "reasoning_effort": "xhigh",
                "model_source": "manual",
                "action": "observe",
                "mainline_state": "unclear",
                "unique_target": None,
                "conclusion": "先观察。",
                "evidence": [],
                "trigger_conditions": ["10点确认"],
                "failure_conditions": ["主线回落"],
                "excluded_candidates": [],
                "confidence": "medium",
            }

            saved_path = save_reasoning_decision_cache(cache_dir, decision)
            loaded = load_reasoning_decision_cache(cache_dir, decision)

            self.assertEqual(saved_path.name, "2026-04-24_abcdef1234567890_reasoning_decision.v1_manual-current-conversation-v1_manual.json")
            created_at = datetime.fromisoformat(loaded["created_at"])
            self.assertIsNotNone(created_at.tzinfo)
            self.assertEqual(loaded["decision"], decision)
            for key in ["target_date", "input_hash", "schema_version", "prompt_version", "model_source", "decision"]:
                self.assertIn(key, loaded)
            self.assertEqual(loaded["decision"]["conclusion"], "先观察。")
            self.assertEqual(loaded["target_date"], "2026-04-24")

    def test_postgres_configured_reasoning_decision_cache_uses_runtime_cache_table(self):
        import report.reasoning_decision_cache as module

        decision = {
            "schema_version": "reasoning_decision.v1",
            "target_date": "2026-04-24",
            "input_hash": "abcdef1234567890",
            "prompt_version": "manual-current-conversation-v1",
            "model_source": "manual",
            "action": "observe",
            "conclusion": "先观察。",
        }

        class StubService:
            def __init__(self):
                self.saved = []
                self.entries = {}

            def is_postgres_backed(self):
                return True

            def get_runtime_cache_entry(self, namespace, cache_key, target_date):
                return self.entries.get((namespace, cache_key, target_date))

            def set_runtime_cache_entry(self, namespace, cache_key, target_date, payload, *, source="", ttl_seconds=None):
                self.saved.append((namespace, cache_key, target_date, payload, source, ttl_seconds))
                self.entries[(namespace, cache_key, target_date)] = {
                    "payload": dict(payload),
                    "source": source,
                }
                return True

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            with patch.object(module, "DatabaseService", StubDatabaseService, create=True), patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"},
                clear=True,
            ):
                saved_path = module.save_reasoning_decision_cache(cache_dir, decision)
                loaded = module.load_reasoning_decision_cache(cache_dir, decision)

            self.assertEqual(service.saved[0][0], "reasoning_decision")
            self.assertEqual(service.saved[0][1], "2026-04-24_abcdef1234567890_reasoning_decision.v1_manual-current-conversation-v1_manual")
            self.assertEqual(service.saved[0][2], "2026-04-24")
            self.assertEqual(service.saved[0][3]["decision"], decision)
            self.assertEqual(loaded["decision"], decision)
            self.assertEqual(saved_path.name, "2026-04-24_abcdef1234567890_reasoning_decision.v1_manual-current-conversation-v1_manual.json")
            self.assertEqual(list(cache_dir.glob("*.json")), [])

    def test_postgres_only_reasoning_decision_cache_rejects_local_json(self):
        import report.reasoning_decision_cache as module

        decision = {
            "schema_version": "reasoning_decision.v1",
            "target_date": "2026-04-24",
            "input_hash": "abcdef1234567890",
            "prompt_version": "manual-current-conversation-v1",
            "model_source": "manual",
        }

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            with patch.dict("os.environ", {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "PostgreSQL-only reasoning cache"):
                    module.save_reasoning_decision_cache(cache_dir, decision)

            self.assertEqual(list(cache_dir.glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
