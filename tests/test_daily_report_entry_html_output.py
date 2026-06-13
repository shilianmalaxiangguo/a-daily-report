import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_report_entry_demo


class DailyReportEntryHtmlOutputTest(unittest.TestCase):
    def _valid_data(self):
        return {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "market_research_snapshot": {
                "front_page_final_gate": {
                    "final_action": "0% / 不参与",
                    "can_new_entry": False,
                }
            },
        }

    def _report_outputs(self):
        return {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0% / 不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }

    def test_postgres_only_saves_html_after_postgres_fact_sync(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def save_chanlun(*args, **kwargs):
            order.append("chanlun")
            return Path("/tmp/chanlun.html")

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            return {"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}

        def save_html(*args, **kwargs):
            order.append("html")
            return Path("/tmp/2026-06-05_A股日报_完整版.html")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", side_effect=save_chanlun), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", side_effect=save_html) as html_mock:
            daily_report_entry_demo.main()

        self.assertEqual(order, ["markdown", "chanlun", "sync", "html"])
        html_mock.assert_called_once_with(
            "2026-06-05",
            run_mode=daily_report_entry_demo.LEDGER_MODE_FROZEN,
            saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"},
        )

    def test_saved_markdown_html_sync_overwrites_existing_reader_html(self):
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-06-05_A股日报_完整版_replay.md"
            html_path = full_path.with_suffix(".html")
            full_path.write_text("# 2026-06-05 A股日报\n\n## 市场脊梁\n\n正文", encoding="utf-8")
            html_path.write_text("<html><body>OLD_POSTGRES_SHORT_HTML</body></html>", encoding="utf-8")

            path = daily_report_entry_demo._try_save_daily_report_html_from_saved_markdown(
                "2026-06-05",
                run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
                saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
            )

            html = html_path.read_text(encoding="utf-8")

        self.assertEqual(path, html_path)
        self.assertNotIn("OLD_POSTGRES_SHORT_HTML", html)
        self.assertIn("bear-shell", html)
        self.assertIn("Markdown日报", html)
        self.assertIn("市场脊梁", html)

    def test_normal_path_skips_snapshot_when_postgres_fact_sync_succeeds(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def save_chanlun(*args, **kwargs):
            order.append("chanlun")
            return Path("/tmp/chanlun.html")

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            return {"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}

        def save_html(*args, **kwargs):
            order.append("html")
            return Path("/tmp/2026-06-05_A股日报_完整版.html")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", side_effect=save_chanlun), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as snapshot_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", side_effect=save_html):
            daily_report_entry_demo.main()

        self.assertEqual(order, ["markdown", "chanlun", "sync", "html"])
        snapshot_mock.assert_not_called()

    def test_html_failure_does_not_prevent_markdown_save(self):
        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", return_value=None):
            daily_report_entry_demo.main()

        save_markdown_mock.assert_called_once()

    def test_replay_path_postgres_sync_failure_stops_without_snapshot_fallback(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            raise ValueError("connection closed")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--replay"]), \
             patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(self._valid_data(), "2026-06-05")), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as snapshot_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            with self.assertRaises(daily_report_entry_demo.ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        self.assertEqual(order, ["markdown", "sync"])
        save_markdown_mock.assert_called_once()
        snapshot_mock.assert_not_called()
        html_mock.assert_not_called()

    def test_live_path_postgres_sync_failure_stops_without_snapshot_fallback(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            raise ValueError("connection closed")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as snapshot_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            with self.assertRaises(daily_report_entry_demo.ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        self.assertEqual(order, ["markdown", "sync"])
        save_markdown_mock.assert_called_once()
        snapshot_mock.assert_not_called()
        html_mock.assert_not_called()

    def test_no_report_does_not_save_html(self):
        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--no-report"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", create=True) as html_mock:
            daily_report_entry_demo.main()

        html_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
