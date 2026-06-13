import json
import re
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

    def test_render_cycle_calendar_keeps_sector_color_markup_safe(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 周期日历",
                    "",
                    "### 1. 周期日历主视图",
                    "| 周次 | 一 | 二 |",
                    "|------|------|------|",
                    (
                        '| 06-01当周 | <span class="cycle-sector-dot" style="color:#D84E42; border-color:#D84E42">●</span><br />'
                        '<span class="cycle-sector-label" style="color:#D84E42; border-color:#D84E42">[电力]</span><br>🔥 爆发 | '
                        "<script>alert(1)</script> |"
                    ),
                ]
            ),
            title="周期日历",
            trade_date="2026-06-05",
        )

        self.assertIn('<div class="cycle-sector-legend" aria-label="板块颜色图例">', html)
        self.assertIn(
            '<span class="cycle-sector-legend-item" style="--cycle-sector-color:#DD4C4F">'
            '<span class="cycle-sector-legend-dot" aria-hidden="true"></span><span>电力</span></span>',
            html,
        )
        self.assertIn('<span class="cycle-sector-label" style="--cycle-sector-color:#DD4C4F">[电力]</span> 🔥 爆发', html)
        self.assertNotIn('class="cycle-sector-dot"', html)
        self.assertNotIn("<br>🔥 爆发", html)
        self.assertIn(".cycle-sector-label", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_render_cycle_calendar_markup_only_applies_to_cycle_calendar_section(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 普通表格",
                    "",
                    "### 普通说明",
                    "| 项目 | 内容 |",
                    "|------|------|",
                    (
                        '| 样本 | <span class="cycle-sector-dot" style="color:#D84E42">●</span><br>'
                        '<span class="cycle-sector-label" style="color:#D84E42;border-color:#D84E42">[电力]</span> |'
                    ),
                ]
            ),
            title="普通表格",
            trade_date="2026-06-05",
        )

        self.assertNotIn('<div class="cycle-sector-legend"', html)
        self.assertNotIn('<td><span class="cycle-sector-label" style="--cycle-sector-color:#DD4C4F">[电力]</span></td>', html)
        self.assertIn("&lt;span class=&quot;cycle-sector-label&quot;", html)

    def test_render_cycle_sector_markup_applies_to_interpretation_and_turnover_surfaces(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 周期色联动",
                    "",
                    "### 2. 周期解读",
                    "| 周期 | 攻击线 |",
                    "|------|--------|",
                    '| 当前周期 | <span class="cycle-sector-label" style="color:#2F7FB8;border-color:#2F7FB8">[半导体]</span> |',
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#DD4C4F;border-color:#DD4C4F">[电力]</span>',
                    "| 日期 | 板块成交额 |",
                    "|------|------------|",
                    "| 2026-06-02 | 1000.00亿 |",
                    "",
                    "#### 小周期成交额与主线切换判断",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 |",
                    "|------|------------|------------|------------|------|----------|----------|",
                    '| 2026-06-02 | <span class="cycle-sector-label" style="color:#2F7FB8;border-color:#2F7FB8">[半导体]</span> | 4050.00亿 | 30000.00亿 | 13.5% | +1.5pct | 小周期试攻，未确认切换 |',
                ]
            ),
            title="周期色联动",
            trade_date="2026-06-05",
        )

        self.assertIn('<span class="cycle-sector-label" style="--cycle-sector-color:#2F7FB8">[半导体]</span>', html)
        self.assertIn('<span class="cycle-sector-label" style="--cycle-sector-color:#DD4C4F">[电力]</span>', html)
        self.assertIn("<td>4050.00亿</td>", html)
        self.assertIn("<td>30000.00亿</td>", html)
        self.assertIn("<td>13.5%</td>", html)
        self.assertNotIn("&lt;span class=&quot;cycle-sector-label&quot;", html)

    def test_render_adds_bear_echarts_for_sector_share_and_turnover_top30(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                    "> 目标日热点板块占比。",
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-06-09 | 7685.41亿 | 26667.33亿 | 28.8% | +6.2pct | 同板块连续 | 国产芯片替代资金容量扩张 |",
                    "| 2026-06-04 | 数据暂缺 | 数据暂缺 | 待累计 | 待累计 | 待累计 | 不参与图表 |",
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#DD4C4F;border-color:#DD4C4F">[电力]</span>',
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-06-08 | 300.00亿 | 28000.00亿 | 1.1% | 待累计 | 待累计 | 非目标日 |",
                    "",
                    "### 附录：五、成交核心结果",
                    "**先看什么**: 只看真放量的成交核心。",
                    "| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 隔日判断 | 蜡烛图形态 |",
                    "|------|------|------|--------|----------|--------|--------|--------|--------|--------|----------|------------|",
                    "| 1 | 中天科技 | 600522 | 249.78亿 | 通信设备 | +9.99% | 54.48 | 48.56 | 50.53 | 54.48 | 观望 | 光头大阳柱涨停(4分) |",
                    "| 2 | 春秋电子 | 603890 | 88.10亿 | AI PC | -9.57% | 28.00 | 25.31 | 27.50 | 25.43 | 谨慎 | 下跌趋势(0分) |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-09",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="sector_turnover_share"', html)
        self.assertIn('data-bear-chart="turnover_sector_share"', html)
        self.assertIn('data-bear-chart="turnover_top30"', html)
        self.assertIn("renderSectorTurnoverShareChart", html)
        self.assertIn("renderTurnoverSectorShareChart", html)
        self.assertIn("renderTurnoverTop30Chart", html)
        self.assertIn("confine: true", html)
        self.assertEqual(payload["sector_turnover_share"]["items"][0]["sector"], "国产芯片替代")
        self.assertEqual(payload["sector_turnover_share"]["items"][0]["share_pct"], 28.8)
        self.assertEqual(len(payload["sector_turnover_share"]["items"]), 1)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["sector"], "通信设备")
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["share_pct"], 73.9)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["count"], 1)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["leaders"][0]["name"], "中天科技")
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["leaders"][0]["status"], "涨停")
        self.assertEqual(payload["turnover_top30"]["items"][0]["name"], "中天科技")
        self.assertEqual(payload["turnover_top30"]["items"][0]["status"], "涨停")
        self.assertEqual(payload["turnover_top30"]["items"][1]["status"], "")

    def test_render_adds_bear_echarts_for_top50_trend_and_lhb_flow(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 1. 指数与市场底色",
                    "> 近25个交易日Top50成交额占比趋势。",
                    "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |",
                    "|------|-----------|------|--------|-------------|------------|",
                    "| 2026-06-09 | 21.86% | 资金活跃期 | +0.75pct | 5828.45亿 | 26667.33亿 |",
                    "| 2026-06-08 | 21.11% | 资金活跃期 | -2.17pct | 5958.98亿 | 28234.29亿 |",
                    "",
                    "### 附录：七、龙虎榜结果",
                    "",
                    "#### 附录：净买入结果",
                    "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                    "|------|------|------|-----------|----------|--------|----------|------------|",
                    "| 1 | 英维克 | 002837 | 8.01亿 | 专用机械 | +10.00% | 涨停 | 光头大阳柱涨停(4分) |",
                    "| 2 | 科泰电源 | 300153 | 0.35亿 | 电源设备 | +3.21% | 正常 | 震荡上行(2分) |",
                    "",
                    "#### 附录：净流出结果",
                    "| 排名 | 股票 | 代码 | 净流出(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                    "|------|------|------|-----------|----------|--------|----------|------------|",
                    "| 1 | 北玻股份 | 002613 | 2.31亿 | 专用机械 | -4.95% | 正常 | 下跌趋势(0分) |",
                    "| 2 | 华映科技 | 000536 | 0.12亿 | 面板 | -1.02% | 正常 | 弱势整理(1分) |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-09",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="market_turnover_top50_trend"', html)
        self.assertIn('data-bear-chart="lhb_net_flow"', html)
        self.assertIn("renderMarketTurnoverTop50TrendChart", html)
        self.assertIn("renderLhbNetFlowChart", html)
        self.assertIn('formatter: (value) => value === 0 ? "" : `${Math.abs(value)}亿`', html)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][0]["date"], "2026-06-08")
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["top50_share_pct"], 21.86)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["total_turnover"], 26667.33)
        self.assertEqual(payload["lhb_net_flow"]["items"][0]["name"], "英维克")
        self.assertEqual(payload["lhb_net_flow"]["items"][0]["amount"], 8.01)
        self.assertEqual(payload["lhb_net_flow"]["items"][1]["name"], "科泰电源")
        self.assertEqual(payload["lhb_net_flow"]["items"][1]["amount"], 0.35)
        self.assertEqual(payload["lhb_net_flow"]["items"][2]["name"], "华映科技")
        self.assertEqual(payload["lhb_net_flow"]["items"][2]["amount"], -0.12)
        self.assertEqual(payload["lhb_net_flow"]["items"][3]["name"], "北玻股份")
        self.assertEqual(payload["lhb_net_flow"]["items"][3]["amount"], -2.31)

    def test_render_adds_bear_echarts_for_board_tag_rank_bar(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 附录：十一、板块标签分析",
                    "",
                    "#### 附录：标签热度排行榜",
                    "> 按标签出现次数排序。",
                    "",
                    "| 排名 | 标签 | 出现次数 | 全标签占比 | 热度条 |",
                    "|------|------|----------|----------|--------|",
                    "| 1 | 光纤概念 | 9 | 8.3% | `####################` |",
                    "| 2 | PCB概念 | 7 | 6.5% | `################` |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-11",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="board_tag_rank_bar"', html)
        self.assertIn("renderBoardTagRankBarChart", html)
        self.assertNotIn('type: "treemap"', html)
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["tag"], "光纤概念")
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["count"], 9)
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["share_pct"], 8.3)

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

    def test_heat_core_limit_signal_ignores_status_columns_outside_limit_pools(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "### 附录：四、热度核心结果",
                    "| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 收盘价 | 连板标签 |",
                    "|------|------|------|-----------|----------|--------|--------|----------|",
                    "| 1 | 绿的谐波 | 688017 | 1397.5w | 自动化设 | +20.00% | 393.00 | 首板涨停 |",
                    "| 2 | 麦捷科技 | 300319 | 907.3w | 东数西算/算力 | +14.43% | 22.28 |  |",
                    "| 3 | 未入池样本 | 301111 | 800.0w | 测试板块 | +20.00% | 20.00 |  |",
                    "| 4 | 否定样本 | 301112 | 700.0w | 测试板块 | +20.00% | 21.00 | 未涨停 |",
                    "| 5 | 金安国纪 | 002636 | 2407.7w | PCB概念 | +9.53% | 84.80 | 4天3板 |",
                    "| 6 | 有研新材 | 600206 | 1200.0w | 半导体 | +8.20% | 30.18 | 2天1板 |",
                    "",
                    "### 附录：资金流入个股TOP10",
                    "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 |",
                    "|------|------|------|------------|----------|--------|----------|",
                    "| 1 | 麦捷科技 | 300319 | 8.80亿 | 元器件 | +14.43% | 涨停 |",
                    "",
                    "### 附录：九、首板结果",
                    "| 股票 | 代码 | 所属板块 | 涨跌幅 | 首次涨停 |",
                    "|------|------|----------|--------|----------|",
                    "| 绿的谐波 | 688017 | 自动化设 | +20.00% | 14:01:00 |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">绿的谐波</code></td><td><code class=\"stock-ref\">688017</code></td><td>1397.5w</td><td>自动化设</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+20.00%</span></td><td>393.00</td><td>首板涨停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">麦捷科技</code></td><td><code class=\"stock-ref\">300319</code></td><td>907.3w</td><td>东数西算/算力</td>"
            "<td>+14.43%</td><td>22.28</td><td></td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>3</td><td><code class=\"stock-ref\">未入池样本</code></td><td><code class=\"stock-ref\">301111</code></td><td>800.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>20.00</td><td></td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>4</td><td><code class=\"stock-ref\">否定样本</code></td><td><code class=\"stock-ref\">301112</code></td><td>700.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>21.00</td><td>未涨停</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>5</td><td><code class=\"stock-ref\">金安国纪</code></td><td><code class=\"stock-ref\">002636</code></td><td>2407.7w</td><td>PCB概念</td>"
            "<td>+9.53%</td><td>84.80</td><td>4天3板</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>6</td><td><code class=\"stock-ref\">有研新材</code></td><td><code class=\"stock-ref\">600206</code></td><td>1200.0w</td><td>半导体</td>"
            "<td>+8.20%</td><td>30.18</td><td>2天1板</td></tr>",
            html,
        )

    def test_heat_core_change_column_uses_row_limit_label_when_pool_table_is_absent(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "### 附录：四、热度核心结果",
                    "| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 收盘价 | 连板标签 |",
                    "|------|------|------|-----------|----------|--------|--------|----------|",
                    "| 1 | 达实智能 | 002421 | 2766.1w | IT服务Ⅱ | -10.02% | 4.40 | 跌停 |",
                    "| 2 | 洛阳钼业 | 603993 | 1874.6w | 工业金属 | +10.02% | 19.11 | 首板涨停 |",
                    "| 3 | 未入池样本 | 301111 | 800.0w | 测试板块 | +20.00% | 20.00 |  |",
                    "| 4 | 否定样本 | 301112 | 700.0w | 测试板块 | +20.00% | 21.00 | 未涨停 |",
                    "| 5 | 旧涨停标签样本 | 603993 | 1874.6w | 工业金属 | +3.45% | 17.37 | 首板涨停 |",
                ]
            ),
            title="日报",
            trade_date="2026-06-12",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">达实智能</code></td><td><code class=\"stock-ref\">002421</code></td><td>2766.1w</td><td>IT服务Ⅱ</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">-10.02%</span></td><td>4.40</td><td>跌停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">洛阳钼业</code></td><td><code class=\"stock-ref\">603993</code></td><td>1874.6w</td><td>工业金属</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+10.02%</span></td><td>19.11</td><td>首板涨停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>3</td><td><code class=\"stock-ref\">未入池样本</code></td><td><code class=\"stock-ref\">301111</code></td><td>800.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>20.00</td><td></td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>4</td><td><code class=\"stock-ref\">否定样本</code></td><td><code class=\"stock-ref\">301112</code></td><td>700.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>21.00</td><td>未涨停</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>5</td><td><code class=\"stock-ref\">旧涨停标签样本</code></td><td><code class=\"stock-ref\">603993</code></td><td>1874.6w</td><td>工业金属</td>"
            "<td>+3.45%</td><td>17.37</td><td>首板涨停</td></tr>",
            html,
        )

    def test_lhb_change_column_uses_limit_status_color(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "## 七、龙虎榜结果",
                    "",
                    "### 净买入结果",
                    "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 |",
                    "|------|------|------|------------|----------|--------|----------|",
                    "| 1 | 华工科技 | 000988 | 16.99亿 | 光通信 | +10.00% | 涨停 |",
                    "| 2 | 科士达 | 002518 | 4.92亿 | 算力 | +9.38% | 正常 |",
                    "",
                    "### 净流出结果",
                    "| 排名 | 股票 | 代码 | 净流出(亿) | 所属板块 | 涨跌幅 | 涨停状态 |",
                    "|------|------|------|------------|----------|--------|----------|",
                    "| 1 | 利通电子 | 603629 | 4.09亿 | 消费电子 | -10.00% | 跌停 |",
                    "| 2 | 否定样本 | 603111 | 1.00亿 | 测试板块 | +10.00% | 未涨停 |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">华工科技</code></td><td><code class=\"stock-ref\">000988</code></td><td>16.99亿</td><td>光通信</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+10.00%</span></td><td>涨停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">利通电子</code></td><td><code class=\"stock-ref\">603629</code></td><td>4.09亿</td><td>消费电子</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">-10.00%</span></td><td>跌停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">科士达</code></td><td><code class=\"stock-ref\">002518</code></td><td>4.92亿</td><td>算力</td>"
            "<td>+9.38%</td><td>正常</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">否定样本</code></td><td><code class=\"stock-ref\">603111</code></td><td>1.00亿</td><td>测试板块</td>"
            "<td>+10.00%</td><td>未涨停</td></tr>",
            html,
        )

    def test_lhb_signal_strength_column_uses_limit_status_color(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "### 2. 龙虎榜结果",
                    "| 股票 | 净买入(亿) | 资金性质 | 行为模式 | 近3日上榜 | 信号强度 |",
                    "|------|-----------|----------|----------|-----------|----------|",
                    "| 华工科技 | +16.99 | 龙虎榜净买入 | 光通信 | - | 涨停 |",
                    "| 利通电子 | -4.09 | 龙虎榜净卖出 | 消费电子 | - | 跌停 |",
                    "| 科士达 | +4.92 | 龙虎榜净买入 | 算力 | - | 正常 |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>华工科技</td><td>+16.99</td><td>龙虎榜净买入</td><td>光通信</td><td>-</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">涨停</span></td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>利通电子</td><td>-4.09</td><td>龙虎榜净卖出</td><td>消费电子</td><td>-</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">跌停</span></td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>科士达</td><td>+4.92</td><td>龙虎榜净买入</td><td>算力</td><td>-</td><td>正常</td></tr>",
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
