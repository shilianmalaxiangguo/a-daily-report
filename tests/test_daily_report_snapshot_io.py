import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DailyReportSnapshotIOTest(unittest.TestCase):
    def test_make_serializable_stops_cycles_and_preserves_shared_values(self):
        import daily_report_snapshot_io as snapshot_io

        shared = {"value": 7}
        data = {"left": shared, "right": shared}
        data["execution_stage_context"] = {"data": data}

        serialized = snapshot_io._make_serializable(data)

        self.assertEqual(serialized["left"], {"value": 7})
        self.assertEqual(serialized["right"], {"value": 7})
        self.assertEqual(
            serialized["execution_stage_context"]["data"],
            "<circular_reference>",
        )

    def test_save_snapshot_writes_valid_json_atomically(self):
        import daily_report_snapshot_io as snapshot_io

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_root = Path(tmp) / "snapshots"
            with patch.object(snapshot_io, "_snapshot_root", return_value=snapshot_root):
                snapshot_path = snapshot_io._save_data_snapshot(
                    {"rows": [{"value": 1}]},
                    "2026-07-29",
                    mode=snapshot_io.LEDGER_MODE_FROZEN,
                )

            payload = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["data"], {"rows": [{"value": 1}]})
            self.assertEqual(list(snapshot_root.glob(".*.tmp")), [])
            with patch.object(snapshot_io, "_snapshot_root", return_value=snapshot_root):
                loaded_data, perspective = snapshot_io.load_data_snapshot("2026-07-29")
            self.assertEqual(loaded_data, {"rows": [{"value": 1}]})
            self.assertEqual(perspective, "")

    def test_size_limited_writer_counts_utf8_bytes(self):
        import daily_report_snapshot_io as snapshot_io

        buffer = io.StringIO()
        writer = snapshot_io._SizeLimitedTextWriter(
            buffer,
            6,
            snapshot_path=Path("snapshot.json"),
            mode=snapshot_io.LEDGER_MODE_FROZEN,
        )

        writer.write("汉")
        writer.write("字")

        self.assertEqual(writer.bytes_written, 6)
        with self.assertRaises(snapshot_io.SnapshotWriteError) as raised:
            writer.write("a")
        self.assertTrue(raised.exception.size_limited)
        self.assertEqual(raised.exception.bytes_written, 6)
        self.assertEqual(raised.exception.attempted_size_bytes, 7)

    def test_save_snapshot_size_limit_preserves_existing_target(self):
        import daily_report_snapshot_io as snapshot_io

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_root = Path(tmp) / "snapshots"
            replay_root = snapshot_root / "replay"
            replay_root.mkdir(parents=True)
            replay_path = replay_root / "2026-07-29_replay.json"
            original_bytes = b'{"existing": true}\n'
            replay_path.write_bytes(original_bytes)

            with patch.object(snapshot_io, "_snapshot_root", return_value=snapshot_root), patch.object(
                snapshot_io,
                "MAX_SNAPSHOT_BYTES",
                256,
            ):
                with self.assertRaisesRegex(RuntimeError, "超过写入上限"):
                    snapshot_io._save_data_snapshot(
                        {"blob": "x" * 2048},
                        "2026-07-29",
                        mode=snapshot_io.LEDGER_MODE_REPLAY,
                    )

            self.assertEqual(replay_path.read_bytes(), original_bytes)
            self.assertEqual(list(replay_root.glob(".*.tmp")), [])

    def test_save_snapshot_size_limit_does_not_create_new_target(self):
        import daily_report_snapshot_io as snapshot_io

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_root = Path(tmp) / "snapshots"
            with patch.object(snapshot_io, "_snapshot_root", return_value=snapshot_root), patch.object(
                snapshot_io,
                "MAX_SNAPSHOT_BYTES",
                256,
            ):
                with self.assertRaises(snapshot_io.SnapshotWriteError):
                    snapshot_io._save_data_snapshot(
                        {"blob": "汉" * 2048},
                        "2026-07-29",
                        mode=snapshot_io.LEDGER_MODE_FROZEN,
                    )

            self.assertFalse((snapshot_root / "2026-07-29.json").exists())
            self.assertEqual(list(snapshot_root.glob(".*.tmp")), [])

    def test_atomic_write_failures_preserve_existing_target_and_cleanup_temp(self):
        import daily_report_snapshot_io as snapshot_io

        failure_points = (
            ("json.dump", snapshot_io.json, "dump"),
            ("os.fsync", snapshot_io.os, "fsync"),
            ("os.replace", snapshot_io.os, "replace"),
        )
        for label, owner, attribute in failure_points:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                snapshot_path = Path(tmp) / "snapshot.json"
                original_bytes = b'{"existing": true}\n'
                snapshot_path.write_bytes(original_bytes)
                with patch.object(owner, attribute, side_effect=OSError(f"{label} failed")):
                    with self.assertRaises(snapshot_io.SnapshotWriteError):
                        snapshot_io._write_snapshot_payload(
                            snapshot_path,
                            {"value": 1},
                            mode=snapshot_io.LEDGER_MODE_REPLAY,
                        )
                self.assertEqual(snapshot_path.read_bytes(), original_bytes)
                self.assertEqual(list(snapshot_path.parent.glob(".*.tmp")), [])

    def test_frozen_publish_race_preserves_competing_official_and_writes_replay(self):
        import daily_report_snapshot_io as snapshot_io

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_root = Path(tmp) / "snapshots"
            official_path = snapshot_root / "2026-07-29.json"
            real_link = snapshot_io.os.link

            def publish_competing_snapshot_then_link(source, target):
                official_path.write_text(
                    json.dumps(
                        {
                            "date": "2026-07-29",
                            "mode": snapshot_io.LEDGER_MODE_FROZEN,
                            "data": {"writer": "competing"},
                            "supplementary_perspective": "competing perspective",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                return real_link(source, target)

            with patch.object(snapshot_io, "_snapshot_root", return_value=snapshot_root), patch.object(
                snapshot_io.os,
                "link",
                side_effect=publish_competing_snapshot_then_link,
            ):
                replay_path = snapshot_io._save_data_snapshot(
                    {"writer": "current"},
                    "2026-07-29",
                    mode=snapshot_io.LEDGER_MODE_FROZEN,
                )

            official_payload = json.loads(official_path.read_text(encoding="utf-8"))
            replay_payload = json.loads(Path(replay_path).read_text(encoding="utf-8"))
            self.assertEqual(official_payload["data"], {"writer": "competing"})
            self.assertEqual(replay_payload["data"], {"writer": "current"})
            self.assertEqual(replay_payload["mode"], snapshot_io.LEDGER_MODE_REPLAY)
            self.assertEqual(
                replay_payload["supplementary_perspective"],
                "competing perspective",
            )
            self.assertEqual(list(snapshot_root.glob(".*.tmp")), [])

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
