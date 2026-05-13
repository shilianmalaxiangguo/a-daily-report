import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SnapUiStaticSyncTest(unittest.TestCase):
    def _source(self):
        return (ROOT / "scripts" / "daily_report_entry_demo.py").read_text(encoding="utf-8")

    def test_daily_entry_imports_publish_node(self):
        source = self._source()

        self.assertIn("from publish.snap_ui_public_data import publish_snap_ui_public_data", source)

    def test_report_onion_publisher_contract_is_present(self):
        publisher_path = ROOT / "scripts" / "report_onion" / "publisher.py"
        self.assertTrue(publisher_path.exists())
        source = publisher_path.read_text(encoding="utf-8")

        for required_text in [
            "def publish_report_onion(",
            "def build_public_brief_payload(",
            'SOURCE_POLICY_PUBLIC = "snapshot-allowlist"',
            "def contains_forbidden_public_text(",
            "full-markdown-private",
        ]:
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, source)

    def test_static_data_failure_is_not_swallowed(self):
        source = self._source()

        self.assertNotIn("def sync_snap_ui_static_data(", source)
        self.assertNotIn("日报已生成但前端静态数据未刷新", source)

    def test_daily_entry_calls_sync_after_snapshot_save(self):
        source = self._source()
        save_index = source.index("_save_data_snapshot(data, target_date, mode=run_mode)")
        publish_index = source.index("publish_snap_ui_public_data(", save_index)
        self.assertGreater(publish_index, save_index)


if __name__ == "__main__":
    unittest.main()
