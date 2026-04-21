import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.persist.use_snapshot_persistence import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseSnapshotPersistenceTest(unittest.TestCase):
    def test_snapshot_persistence_hook_saves_rendered_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = build_empty_context({"target_date": "2026-04-21"})
            ctx = merge_hook_patches(
                ctx,
                {
                    "rendered": {"markdown_document": "# report"},
                    "decision": {"execution_permission": {"label": "watch_only"}},
                },
            )

            with patch("hooks.persist.use_snapshot_persistence._save_data_snapshot", return_value=str(Path(tmpdir) / "snap.json")) as mocked:
                result = run(ctx)

        self.assertTrue(result["patches"]["runtime"]["snapshot_path"].endswith("snap.json"))
        mocked.assert_called_once()
