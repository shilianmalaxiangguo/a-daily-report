import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
