import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_render import generate_markdown_report_from_sections


class DailyReportRenderTest(unittest.TestCase):
    def test_generate_markdown_report_from_sections_keeps_expected_order(self):
        rendered = generate_markdown_report_from_sections(
            {
                "preamble": "# Preamble",
                "environment": "",
                "observation": "## Observation",
                "execution": "## Execution",
                "review": "## Review",
                "summary": "## Summary",
            }
        )

        self.assertEqual(rendered, "# Preamble\n\n## Observation\n\n## Execution\n\n## Review\n\n## Summary")
