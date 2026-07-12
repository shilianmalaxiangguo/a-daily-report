from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".agents/skills/daily-report-wechat-draft/scripts/daily_report_wechat_draft.py"


def load_skill_module():
    spec = importlib.util.spec_from_file_location("daily_report_wechat_draft", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DailyReportWechatDraftSkillTest(unittest.TestCase):
    def setUp(self):
        self.module = load_skill_module()

    def test_extract_sector_html_capture_uses_rendered_html_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "2099-01-02_A股日报_完整版.html"
            html_path.write_text(
                """<!doctype html>
<html><head><style>.reader-table{color:#123}</style></head><body>
<h2 id="板块资金扩散淘汰赛">板块资金扩散淘汰赛</h2>
<p><strong>T-001</strong></p>
<div class="reader-table"><table><tr><th>层级</th></tr><tr><td>市场资金结构</td></tr></table></div>
<blockquote>最终动作：0%不参与</blockquote>
<h2 id="下一节">下一节</h2>
</body></html>""",
                encoding="utf-8",
            )

            capture = self.module.extract_sector_html_capture(html_path)

        self.assertIn("reader-table", capture.capture_html)
        self.assertIn("最终动作", capture.capture_html)
        self.assertNotIn("下一节", capture.capture_html)

    def test_extract_account_day_order_capture_uses_bear_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "2099-01-02_A股日报_完整版.html"
            html_path.write_text(
                """<!doctype html>
<html><head><style>.position-timeline-shell{color:#123}</style></head><body>
<h2 id="账户日序表">账户日序表</h2>
<div class="position-timeline-shell is-day-order"><table><tr><td>Ta</td><td>Te</td></tr></table></div>
<ul><li>顶部账户日序表按近5个交易日展示。</li></ul>
<h2 id="下一节">下一节</h2>
</body></html>""",
                encoding="utf-8",
            )

            capture = self.module.extract_section_html_capture(html_path, self.module.ACCOUNT_DAY_ORDER_SECTION)

        self.assertIn("position-timeline-shell", capture.capture_html)
        self.assertIn("顶部账户日序表", capture.capture_html)
        self.assertNotIn("下一节", capture.capture_html)

    def test_extract_sector_html_capture_reports_missing_section_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "2099-01-02_A股日报_完整版.html"
            html_path.write_text("<html><body><h2>别的章节</h2></body></html>", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, str(html_path)):
                self.module.extract_sector_html_capture(html_path)

    def test_report_context_accepts_html_without_markdown_peer(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "2099-01-03_A股日报_完整版.html"
            html_path.write_text("<html><body></body></html>", encoding="utf-8")

            context = self.module.report_context_from_input(html_path)

        self.assertEqual(context.trade_date, "2099-01-03")
        self.assertEqual(context.report_path, html_path.resolve())

    def test_empty_target_defaults_to_empty_position_post_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "2099-01-03_A股日报_完整版.md"
            report_path.write_text(
                """# 2099-01-03 a股市场分析

| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |
| 明日执行对象 | 无 |
""",
                encoding="utf-8",
            )
            context = self.module.report_context_from_input(report_path)

        self.assertEqual(self.module.default_title(context), "今日空仓")
        self.assertEqual(self.module.default_digest(context), "今日空仓")
        html = self.module.build_article_html(
            [("账户日序表", "file:///tmp/a.png"), ("板块资金扩散淘汰赛", "file:///tmp/b.png")],
            context,
        )
        self.assertEqual(html.count("<img "), 2)
        self.assertIn("今日标的：空仓", html)
        self.assertIn("模拟持仓，不作为投资买卖依据", html)

    def test_non_empty_target_defaults_to_strategy_post_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "2099-01-03_A股日报_完整版.md"
            report_path.write_text(
                """# 2099-01-03 a股市场分析

| 项目 | 结论 |
|------|------|
| 明日仓位 | B1先参与 |
| 明日执行对象 | 长电科技(600584) |
""",
                encoding="utf-8",
            )
            context = self.module.report_context_from_input(report_path)

        self.assertEqual(self.module.default_title(context), "今日策略")
        self.assertEqual(self.module.default_digest(context), "今日策略")
        html = self.module.build_article_html([("账户日序表", "file:///tmp/a.png")], context)
        self.assertIn("今日标的：长电科技(600584)", html)

    def test_build_outputs_stops_when_matching_html_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "2099-01-04_A股日报_完整版.md"
            report_path.write_text("# 2099-01-04 a股市场分析\n", encoding="utf-8")
            args = argparse.Namespace(
                report=str(report_path),
                out_dir=str(Path(tmp) / "out"),
                title="",
                digest="",
                author="",
                html_report="",
                create_draft=False,
                cover_media_id="",
                env_file=None,
                account_slot="1",
                json=True,
            )

            with self.assertRaisesRegex(FileNotFoundError, "未找到可截图的日报 HTML"):
                self.module.build_outputs(args)

    def test_ensure_not_truncated_raises_when_content_reaches_bottom(self):
        with tempfile.TemporaryDirectory() as tmp:
            png_path = Path(tmp) / "raw.png"
            image = Image.new("RGB", (100, 100), "#ffffff")
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 80, 90, 99), fill="#fff9ef")
            image.save(png_path)

            with self.assertRaisesRegex(RuntimeError, "可能被截断"):
                self.module.ensure_not_truncated(png_path, Path(tmp) / "source.html")

    def test_create_draft_posts_utf8_json_without_unicode_escapes(self):
        class FakeResponse:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        calls = []

        def fake_request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith("/cgi-bin/token"):
                return FakeResponse({"access_token": "TOKEN"})
            return FakeResponse({"media_id": "MEDIA_ID"})

        payload = {
            "articles": [
                {
                    "title": "今日空仓",
                    "digest": "今日空仓",
                    "content": "<p>今日标的：空仓</p>",
                    "thumb_media_id": "THUMB",
                }
            ]
        }

        with patch.object(self.module.requests, "request", side_effect=fake_request):
            media_id = self.module.WeChatDraftClient("APPID", "SECRET").create_draft(payload)

        self.assertEqual(media_id, "MEDIA_ID")
        draft_kwargs = calls[-1][2]
        self.assertNotIn("json", draft_kwargs)
        self.assertIn("application/json; charset=utf-8", draft_kwargs["headers"]["Content-Type"])
        self.assertIn("今日标的".encode("utf-8"), draft_kwargs["data"])
        self.assertNotIn(b"\\u4eca", draft_kwargs["data"])


if __name__ == "__main__":
    unittest.main()
