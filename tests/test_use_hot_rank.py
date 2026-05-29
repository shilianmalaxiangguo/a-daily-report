import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.input.use_hot_rank import run
from orchestrator.context_store import build_empty_context


class UseHotRankTest(unittest.TestCase):
    @patch("hooks.input.use_hot_rank.fetch_hot_rank")
    def test_hot_rank_hook_writes_raw_and_normalized_payloads(self, mocked_fetch):
        mocked_fetch.return_value = [
            {"code": "000001", "name": "平安银行", "rank": 1}
        ]
        ctx = build_empty_context({"target_date": "2026-04-21"})

        result = run(ctx)

        mocked_fetch.assert_called_once_with(limit=50)
        self.assertEqual(result["patches"]["raw"]["hot_rank"][0]["code"], "000001")
        self.assertEqual(result["patches"]["normalized"]["market_snapshot"]["hot_rank_count"], 1)
        self.assertEqual(result["diagnostics"]["source_used"], "ths")
