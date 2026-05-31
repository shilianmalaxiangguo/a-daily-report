import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DailyReportSnapshotIOTest(unittest.TestCase):
    def test_save_existing_snapshot_preserves_perspective_without_full_json_parse(self):
        import daily_report_snapshot_io as snapshot_io

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_root = Path(tmp) / "snapshots"
            snapshot_root.mkdir(parents=True)
            official_path = snapshot_root / "2026-05-29.json"
            official_path.write_text(
                json.dumps(
                    {
                        "date": "2026-05-29",
                        "saved_at": "2026-05-29 15:30:00",
                        "mode": snapshot_io.LEDGER_MODE_FROZEN,
                        "data": {"rows": [{"value": index} for index in range(200)]},
                        "supplementary_perspective": "perspective line",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(snapshot_io, "_snapshot_root", return_value=snapshot_root), patch.object(
                snapshot_io.json,
                "load",
                side_effect=AssertionError("full snapshot parse should not run"),
            ):
                replay_path = snapshot_io._save_data_snapshot(
                    {"fresh": True},
                    "2026-05-29",
                    mode=snapshot_io.LEDGER_MODE_FROZEN,
                )

            replay_payload = json.loads(Path(replay_path).read_text(encoding="utf-8"))
            self.assertEqual(replay_payload["mode"], snapshot_io.LEDGER_MODE_REPLAY)
            self.assertEqual(replay_payload["supplementary_perspective"], "perspective line")


if __name__ == "__main__":
    unittest.main()
