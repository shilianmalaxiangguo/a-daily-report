import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_markdown_document import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseMarkdownDocumentTest(unittest.TestCase):
    def test_markdown_document_concatenates_section_blocks_only(self):
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(
            ctx,
            {
                "sections": {
                    "preamble": "# 2026-04-21 A股日报",
                    "summary": "## Summary\n- watch only",
                }
            },
        )

        result = run(ctx)

        rendered = result["patches"]["rendered"]["markdown_document"]
        self.assertIn("# 2026-04-21 A股日报", rendered)
        self.assertIn("## Summary", rendered)
