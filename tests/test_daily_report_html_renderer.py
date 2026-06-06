import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from report.html_report_renderer import (
    DailyReportHtmlDataMissingError,
    build_daily_report_html_path,
    render_daily_report_html,
    save_daily_report_html,
)


def _view():
    return {
        "meta": {
            "trade_date": "2026-06-05",
            "report_title": "2026-06-05 A股日报",
            "run_mode": LEDGER_MODE_REPLAY,
            "source": "postgresql://daily-report-facts/2026-06-05",
        },
        "tomorrow_action": {
            "position_state": "0%",
            "can_participate": False,
            "primary_target": {"stock_name": "豫能控股", "stock_code": "001896"},
            "participation_window": "09:50-10:10",
            "action_summary": "不参与 <script>alert(1)</script>",
            "cancel_conditions": ["成交额继续萎缩"],
            "risk_boundary": "跌破认错线",
        },
        "market_spine": {
            "turnover_summary": "1000",
            "breadth_summary": "上涨2600 / 下跌2100",
            "market_phase": "等待承接",
        },
        "mainline_evidence": {
            "confirmed_line": "电力",
            "attack_evidence": ["净流入居前", "高位锚点保持"],
        },
        "candidate_actions": [
            {
                "stock_name": "豫能控股",
                "stock_code": "001896",
                "role": "电力前排",
                "buy_window": "09:50-10:10",
                "invalidation": "跌破认错线",
                "missed_action": "条件不成立就不做",
            }
        ],
        "participation_reviews": [
            {
                "stock_name": "豫能控股",
                "stock_code": "001896",
                "review_status": "等待更多事实",
                "missed_action": "不追",
            }
        ],
        "data_sources": [
            {
                "source_label": "PSQL日报事实",
                "source_policy": "postgresql.daily_report_facts",
                "trade_date": "2026-06-05",
                "source_date": "2026-06-05",
                "status": "success",
                "warning": "",
            }
        ],
        "diagnostics": {
            "missing_required_facts": [],
            "degraded_facts": [],
            "render_warnings": [],
            "large_json_artifact": False,
        },
    }


class DailyReportHtmlRendererTest(unittest.TestCase):
    def test_build_path_uses_report_mode_and_html_extension(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            frozen_path = build_daily_report_html_path("2026-06-05", root=root, run_mode=LEDGER_MODE_FROZEN)
            replay_path = build_daily_report_html_path("2026-06-05", root=root, run_mode=LEDGER_MODE_REPLAY)

        self.assertEqual(frozen_path.name, "2026-06-05_A股日报_完整版.html")
        self.assertEqual(frozen_path.parent.name, "reports")
        self.assertEqual(replay_path.name, "2026-06-05_A股日报_完整版_replay.html")
        self.assertEqual(replay_path.parent.name, "replay")

    def test_render_escapes_text_and_contains_reader_design_tokens(self):
        html = render_daily_report_html(_view())

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("--accent: #c20c0c", html)
        self.assertIn("--reader-bg: #ffffff", html)
        self.assertIn("--reader-text: #111111", html)
        self.assertIn("--editor-width: 720px", html)
        self.assertIn('class="bear-shell"', html)
        self.assertIn('class="bear-sidebar"', html)
        self.assertIn('class="note-rail"', html)
        self.assertIn('class="note-item is-active"', html)
        self.assertIn('border-left-color: var(--accent-red)', html)
        self.assertIn('@media (max-width: 640px)', html)
        self.assertIn('<div class="reader-table"><table>', html)
        self.assertIn("明日动作", html)
        self.assertIn("PSQL日报事实", html)

    def test_save_refuses_missing_required_facts(self):
        view = _view()
        view["diagnostics"]["missing_required_facts"] = ["明日动作"]

        with TemporaryDirectory() as tmp:
            with self.assertRaises(DailyReportHtmlDataMissingError):
                save_daily_report_html(view, root=Path(tmp))

            self.assertEqual(list(Path(tmp).glob("**/*.html")), [])
            self.assertEqual(list(Path(tmp).glob("**/*.json")), [])

    def test_save_writes_only_html(self):
        with TemporaryDirectory() as tmp:
            path = save_daily_report_html(_view(), root=Path(tmp))

            self.assertTrue(path.exists())
            self.assertEqual(path.suffix, ".html")
            self.assertIn("2026-06-05_A股日报_完整版_replay.html", str(path))
            self.assertEqual(list(path.parent.glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
