import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.markdown_report_html import render_markdown_report_file, render_markdown_report_html


class DailyReportMarkdownHtmlTest(unittest.TestCase):
    def test_render_builds_bear_outline_and_escapes_text(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-06-05 A股日报",
                    "",
                    "## 市场基底",
                    "<script>alert(1)</script>",
                    "",
                    "| 指标 | 数值 |",
                    "|------|------|",
                    "| Top50成交额占比 | 23.28% |",
                    "| 涨跌比 | 4501 / 900 |",
                    "| 涨跌比 | 1000 / 4301 |",
                    "| ETF两市成交额 | 4406.74亿 |",
                    "",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "|------|------|--------|------|",
                    "| 两市成交额 | 31006.90亿 | +11.57% | 成交额重新放大 |",
                    "| 两市成交额 | 27800.10亿 | -4.20% | 成交额收缩 |",
                    "",
                    "| 指数 | 收盘 | 涨跌幅 | 解读 |",
                    "|------|------|--------|------|",
                    "| 上证指数 | 3385.36 | +0.45% | 小幅修复 |",
                    "| 中证1000 | 6210.12 | -1.25% | 小票承压 |",
                    "",
                    "| 日期 | ETF两市成交额 | 较前日 | 有成交ETF数 |",
                    "|------|----------------|--------|------------|",
                    "| 2026-06-05 | 4406.74亿 | +1.65% | 1544 |",
                    "| 2026-06-02 | 5198.92亿 | +3.18% | 1541 |",
                    "| 2026-05-15 | 5552.59亿 | +14.06% | 1518 |",
                    "",
                    "| 日期 | 当日差值 | 全A占比 |",
                    "|------|----------|---------|",
                    "| 2026-06-05 | +2.30pct | 1.96% |",
                    "| 2026-06-04 | -2.40pct | 5.20% |",
                    "",
                    "```sql",
                    "select * from daily_report_fact_fields where value > 20;",
                    "```",
                    "",
                    "---",
                    "",
                    "### 今日判断",
                    "> 只观察，不新增参与",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-05",
            source_label="Markdown日报",
        )

        self.assertIn("当前日报", html)
        self.assertIn("outline-sticky", html)
        self.assertIn("position: sticky", html)
        self.assertIn("is-active", html)
        self.assertIn('class="level-1 is-active" aria-current="true"', html)
        self.assertIn("scrollIntoView", html)
        self.assertIn('target.scrollIntoView({ block: "start", inline: "nearest", behavior: "auto" })', html)
        self.assertIn("requestAnimationFrame", html)
        self.assertIn("event.preventDefault()", html)
        self.assertIn("replaceState", html)
        self.assertIn("forcedActiveId", html)
        self.assertIn("releaseForcedActive", html)
        self.assertIn("scrollActiveIntoOutline", html)
        self.assertIn("outline.scrollTo", html)
        self.assertNotIn('behavior: "smooth"', html)
        self.assertNotIn("scroll-behavior: smooth", html)
        self.assertNotIn("clickScrollLockUntil", html)
        self.assertNotIn("clickScrollTargetId", html)
        self.assertNotIn("isNearScrollTarget", html)
        self.assertNotIn("window.setTimeout", html)
        self.assertNotIn("activeLink.scrollIntoView", html)
        self.assertIn(".outline-nav a.is-active::before", html)
        self.assertIn("background: var(--accent)", html)
        self.assertIn("transform: translateY(-50%)", html)
        self.assertIn("hashAnchor", html)
        self.assertNotIn('link.style.setProperty("color"', html)
        self.assertNotIn('link.style.setProperty("background-color"', html)
        self.assertNotIn('link.style.setProperty("border-left-color"', html)
        self.assertNotIn(".outline-nav a.is-active {\n", html)
        self.assertIn('window.addEventListener("wheel"', html)
        self.assertIn('window.addEventListener("mousedown"', html)
        self.assertIn('window.addEventListener("hashchange"', html)
        self.assertIn('const outlineMarker = "$" + "outline_nav"', html)
        self.assertNotIn('includes("<nav class=', html)
        self.assertIn('href="#市场基底"', html)
        self.assertIn('data-outline-anchor="市场基底"', html)
        self.assertIn('class="level-3" href="#今日判断" data-outline-anchor="今日判断"', html)
        self.assertIn("--editor-width: 1120px", html)
        self.assertIn("--reader-text: #444444", html)
        self.assertIn("--accent: #DD4C4F", html)
        self.assertIn("--accent-soft-text: #DD4C4F", html)
        self.assertIn("--signal-green: #07C160", html)
        self.assertIn("font-size: 15px", html)
        self.assertIn("pre.fenced-code", html)
        self.assertIn('<pre class="fenced-code"><code class="fenced-code-content" lang="sql">', html)
        self.assertIn("select * from daily_report_fact_fields where value &gt; 20;", html)
        self.assertIn("<hr>", html)
        self.assertNotIn('content: "📝"', html)
        self.assertIn("box-decoration-break: clone", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertGreaterEqual(html.count('class="signal-marker signal-hot"'), 4)
        self.assertGreaterEqual(html.count('class="signal-marker signal-cold"'), 3)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">+11.57%</span></td>', html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-cold">-4.20%</span></td>', html)
        self.assertIn("<td>31006.90亿</td>", html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">+0.45%</span></td>', html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-cold">-1.25%</span></td>', html)
        self.assertIn("<td>3385.36</td>", html)
        self.assertEqual(html.count('<td class="has-signal"><span class="signal-marker signal-cold">4406.74亿</span></td>'), 2)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">5552.59亿</span></td>', html)
        self.assertIn("<td>5198.92亿</td>", html)
        self.assertNotIn('td class="signal-hot"', html)
        self.assertNotIn("snapshots/replay", html)
        self.assertNotIn(".json", html)

    def test_render_marks_stock_name_code_references_as_inline_code(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 个股引用",
                    "",
                    "正文里：大有能源(600403)要像代码一样醒目，普通说明(不是代码)不变。",
                    "",
                    "- 保留：宇环数控(002903)",
                    "- 已有反引号：`华电辽能(600396)`",
                    "",
                    "| 标的 | 说明 |",
                    "|------|------|",
                    "| 天娱数科(002354) | 观察 |",
                    "",
                    "| 股票 | 代码 |",
                    "|------|------|",
                    "| 兆易创新 | 603986 |",
                    "",
                    "关系：未证明比兆易创新(603986)更值得参与。",
                ]
            ),
            title="个股引用",
            trade_date="2026-06-05",
        )

        self.assertIn('<code class="stock-ref">大有能源(600403)</code>', html)
        self.assertIn('<code class="stock-ref">宇环数控(002903)</code>', html)
        self.assertIn('<code class="stock-ref">天娱数科(002354)</code>', html)
        self.assertIn('<td><code class="stock-ref">兆易创新</code></td>', html)
        self.assertIn('<td><code class="stock-ref">603986</code></td>', html)
        self.assertIn('未证明比<code class="stock-ref">兆易创新(603986)</code>更值得参与', html)
        self.assertNotIn('<code class="stock-ref">未证明比兆易创新(603986)</code>', html)
        self.assertIn("<code>华电辽能(600396)</code>", html)
        self.assertNotIn('<code class="stock-ref">华电辽能(600396)</code>', html)
        self.assertIn("普通说明(不是代码)不变", html)

    def test_render_marks_etf_turnover_only_at_extreme_boundaries(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# ETF阈值",
                    "",
                    "| 日期 | ETF两市成交额 |",
                    "|------|----------------|",
                    "| 2026-06-01 | 4499.99亿 |",
                    "| 2026-06-02 | 4500.00亿 |",
                    "| 2026-06-03 | 5000.00亿 |",
                    "| 2026-06-04 | 5500.00亿 |",
                    "| 2026-06-05 | 5500.01亿 |",
                ]
            ),
            title="ETF阈值",
            trade_date="2026-06-05",
        )

        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-cold">4499.99亿</span></td>',
            html,
        )
        self.assertIn("<td>4500.00亿</td>", html)
        self.assertIn("<td>5000.00亿</td>", html)
        self.assertIn("<td>5500.00亿</td>", html)
        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-hot">5500.01亿</span></td>',
            html,
        )

    def test_render_marks_heat_core_change_column_from_limit_pools_only(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "### 附录：四、热度核心结果",
                    "| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 收盘价 |",
                    "|------|------|------|-----------|----------|--------|--------|",
                    "| 1 | 大有能源 | 600403 | 1548.6w | 煤炭开采 | +10.00% | 8.14 |",
                    "| 2 | 华电能源 | 600726 | 1880.5w | 电力 | -10.01% | 9.35 |",
                    "| 3 | 兆易创新 | 603986 | 1313.2w | 存储芯片 | -7.80% | 488.00 |",
                    "",
                    "### 附录：五、成交核心结果",
                    "| 排名 | 股票 | 代码 | 涨跌幅 |",
                    "|------|------|------|--------|",
                    "| 1 | 大有能源 | 600403 | +10.00% |",
                    "",
                    "### 附录：九、连板结果",
                    "| 股票 | 代码 | 所属板块 | 涨跌幅 |",
                    "|------|------|----------|--------|",
                    "| 大有能源 | 600403 | 煤炭开采 | +10.00% |",
                    "",
                    "### 附录：跌停池结果",
                    "| 股票 | 代码 | 所属板块 | 涨跌幅 |",
                    "|------|------|----------|--------|",
                    "| 华电能源 | 600726 | 电力 | -10.01% |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">大有能源</code></td><td><code class=\"stock-ref\">600403</code></td><td>1548.6w</td><td>煤炭开采</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+10.00%</span></td><td>8.14</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">华电能源</code></td><td><code class=\"stock-ref\">600726</code></td><td>1880.5w</td><td>电力</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">-10.01%</span></td><td>9.35</td></tr>',
            html,
        )
        self.assertIn("<td>-7.80%</td><td>488.00</td>", html)
        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">大有能源</code></td><td><code class=\"stock-ref\">600403</code></td><td>+10.00%</td></tr>",
            html,
        )

    def test_render_demotes_judgment_review_internal_headings_from_outline(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "## 判断纠偏与今日五项结论",
                    "### 近5个已结算交易日正确率（2026-05-29至2026-06-04）",
                    "| 判断项 | 正确率 |",
                    "|--------|--------|",
                    "| 市场状态判断 | 60.00% |",
                    "",
                    "### 结算上一交易日：2026-06-04",
                    "| 判断项 | 结论 |",
                    "|--------|------|",
                    "| 主线判断 | 正确 |",
                    "",
                    "### 今日判断（2026-06-05，等待下一交易日验证）",
                    "| 判断项 | 今日结论 |",
                    "|--------|----------|",
                    "| 核心候选判断 | 大有能源(600403) |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn('href="#判断纠偏与今日五项结论"', html)
        self.assertNotIn('href="#近5个已结算交易日正确率2026-05-29至2026-06-04"', html)
        self.assertNotIn('href="#结算上一交易日2026-06-04"', html)
        self.assertNotIn('href="#今日判断2026-06-05等待下一交易日验证"', html)
        self.assertIn("<p><strong>今日判断（2026-06-05，等待下一交易日验证）</strong></p>", html)

    def test_render_file_defaults_to_html_sibling(self):
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            source.write_text("# 标题\n\n## 二级\n正文", encoding="utf-8")

            output = render_markdown_report_file(source, title="标题", trade_date="2026-06-05")

            self.assertEqual(output, source.with_suffix(".html"))
            self.assertTrue(output.exists())
            self.assertIn("标题", output.read_text(encoding="utf-8"))

    def test_render_omits_stale_price_band_section_for_target_date(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-06-05 A股日报",
                    "",
                    "## 二、市场基底",
                    "### 3. 价格带风格",
                    "> 最近可用窗口（截至2026-05-27）：近25个交易日价格带风格：最新差值 +0.32pct，当前为震荡。",
                    "",
                    "| 日期 | 百元股涨跌幅 | 低价股涨跌幅 | 当日差值 | 相对风格 | 绝对状态 |",
                    "|------|--------------|--------------|--------------|----------|----------|",
                    "| 2026-05-27 | -1.55% | -1.87% | +0.32pct | 震荡 | 同步回落 |",
                    "",
                    "### 4. 创新高趋势反馈",
                    "目标日新高反馈正常展示。",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-05",
        )

        self.assertNotIn('href="#3-价格带风格"', html)
        self.assertNotIn('<h3 id="3-价格带风格">3. 价格带风格</h3>', html)
        self.assertNotIn("最近可用窗口", html)
        self.assertNotIn("2026-05-27", html)
        self.assertIn("创新高趋势反馈", html)


if __name__ == "__main__":
    unittest.main()
