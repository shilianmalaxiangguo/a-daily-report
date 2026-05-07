import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge.llm_wiki_context import build_llm_wiki_context


class LlmWikiContextTest(unittest.TestCase):
    def test_build_llm_wiki_context_materializes_compact_chinese_nodes(self):
        context = build_llm_wiki_context()

        self.assertEqual(context["version"], "2026-05-07")
        self.assertEqual(context["source"], "llm_wiki")
        self.assertEqual(context["language"], "zh-CN")
        self.assertIn("wiki/交易思想/缠论体系.md", context["source_paths"])
        self.assertIn("wiki/交易思想/价格行为与能量框架.md", context["source_paths"])
        self.assertIn("wiki/交易思想/日报术语契约.md", context["source_paths"])
        self.assertIn("日线结构中枢定环境 -> 60分钟确认 -> 30分钟止损", context["field_mappings"])
        self.assertIn("稳定知识写入 LLM Wiki", context["write_boundaries"])
        self.assertIn("原文不直接进入日报主链", context["report_boundaries"])
        self.assertIn("MACD只能作为辅助", context["report_boundaries"])
        self.assertIn("用户可见输出不用门控/闸门/执行权/开闸/放行，改用资格/条件/可做", context["report_boundaries"])

    def test_build_llm_wiki_context_keeps_report_digest_short_and_fieldized(self):
        context = build_llm_wiki_context()
        digest = context["report_digest_text"]

        self.assertIn("角度与幅度", digest)
        self.assertIn("60分钟确认", digest)
        self.assertIn("30分钟止损", digest)
        self.assertIn("资格/条件/可做", digest)
        self.assertLess(len(digest), 260)
        self.assertNotIn("缠论原文", digest)
        self.assertNotIn("能量学", digest)
        self.assertNotIn("教你炒股票", digest)


if __name__ == "__main__":
    unittest.main()
