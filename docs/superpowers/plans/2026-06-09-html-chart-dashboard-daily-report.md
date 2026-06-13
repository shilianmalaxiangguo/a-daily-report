# HTML 图表驾驶舱日报实施计划

> **给代理执行用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用复选框（`- [ ]`）格式跟踪。

**目标：** 把现有 HTML 日报第一屏改成 ECharts 图表驾驶舱，并保留 Markdown 阅读区的既有信息。

**实现思路：** 先在 `DailyReportView` 中新增 `charts` 字段，只从已保存的日报事实组装图表 payload。再在 HTML 渲染层复用本地 ECharts 优先、CDN 兜底的加载方式，把安全 JSON 注入模板，由前端脚本完成图表、解释面板和缺失提示。核心图缺少数据时停止 HTML 生成，解释图缺少数据时页面保留缺失原因。

**技术栈：** Python 3.14、`unittest`、`string.Template`、ECharts 5、本地静态 HTML。

---

## 范围

**In Scope**

- 修改 `scripts/report/html_report_view.py`，新增五张首屏图和一个周视图下钻 payload。
- 修改 `scripts/report/html_report_renderer.py`，新增 ECharts 加载、安全 JSON 注入、图表替换字段。
- 修改 `scripts/templates/daily_report_reader.html`，加入图表区域、解释面板和最小交互脚本。
- 修改 `tests/test_daily_report_html_view.py` 和 `tests/test_daily_report_html_renderer.py`，覆盖数据结构、缺失处理、安全嵌入和容器渲染。

**Out of Scope**

- 不改交易判断逻辑。
- 不改采集顺序。
- 不新增独立前端应用或构建系统。
- 不覆盖正式历史日报。
- 不新增每日完整大 JSON 附属文件。

**Non-goals**

- 图表不重新判断参与资格。
- 热榜 tag 不直接等同板块强度确认。
- 周视图不参与当天板块热力计算。
- 解释图缺数据时不伪装成完整证据。

**Done Definition**

- `view["charts"]` 包含 `market_capacity`、`mainline_turnover_share`、`sector_heatmap`、`mainline_attack_scatter`、`hot_tag_composition`、`cycle_week_view`。
- 市场容量趋势和主线成交占比趋势缺数据时，`missing_required_fact_labels(view)` 返回对应缺失项。
- HTML 包含六个图表容器、ECharts 加载脚本、图表 JSON 和解释面板。
- 图表 JSON 中的 `<script>` 文本被安全转义。
- 聚焦单测使用 `.generated/venv-py314/bin/python3.14` 通过。

---

### 任务 1：View 层新增图表 payload

**文件：**

- 修改：`tests/test_daily_report_html_view.py`
- 修改：`scripts/report/html_report_view.py`

- [ ] **步骤 1：先写失败测试**

在 `DailyReportHtmlViewTest` 中新增测试，构造包含核心图和解释图事实的 snapshot：

```python
def test_builds_chart_payloads_from_saved_daily_facts(self):
    service = FakePostgresDailyReportService(
        snapshot={
            "market_research_snapshot": {
                "front_page_decision": {"final_action": "0%不参与", "allow_new_entry": False},
                "mainline_turnover_summary": {
                    "current_mainline": "AI算力",
                    "turnover_share_trend_rows": [
                        {
                            "trade_date": "2026-06-04",
                            "mainline_name": "AI算力",
                            "mainline_turnover": 3200,
                            "market_turnover": 12000,
                            "turnover_share_pct": 26.67,
                            "share_delta_pct": 1.2,
                        },
                        {
                            "trade_date": "2026-06-05",
                            "mainline_name": "AI算力",
                            "mainline_turnover": 3500,
                            "market_turnover": 12500,
                            "turnover_share_pct": 28.0,
                            "share_delta_pct": 1.33,
                        },
                    ],
                    "mainline_attack_evidence_summary": {
                        "primary_line": "AI算力",
                        "evidence_rows": [
                            {
                                "sector": "CPO",
                                "role": "主攻线",
                                "turnover_share_delta_pct": 2.1,
                                "fund_strength": 82,
                                "limit_up_count": 5,
                                "height": 4,
                            }
                        ],
                    },
                    "cycle_calendar_rows": [
                        {"week_label": "06-01当周", "mainline": "AI算力", "phase": "强化"}
                    ],
                },
            },
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "total_turnover": 12500,
            "top50_turnover_share_series": {
                "rows": [
                    {
                        "trade_date": "2026-06-04",
                        "total_turnover": 12000,
                        "share_pct": 19.0,
                        "up_count": 2400,
                        "down_count": 2300,
                    },
                    {
                        "trade_date": "2026-06-05",
                        "total_turnover": 12500,
                        "share_pct": 20.2,
                        "up_count": 2600,
                        "down_count": 2100,
                    },
                ]
            },
            "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
            "sector_fund_flow": {
                "inflow": [
                    {"name": "CPO", "amount": 58.5, "change_pct": 3.2, "limit_up_count": 5},
                    {"name": "电力", "amount": 21.0, "change_pct": 1.1, "limit_up_count": 1},
                ]
            },
            "tag_distribution": {"CPO": 8, "算力": 6, "电力": 2},
            "integrated_hot_list": [
                {"stock_name": "新易盛", "code": "300502", "tags": ["CPO", "算力"]},
                {"stock_name": "华电辽能", "code": "600396", "tags": ["电力"]},
            ],
            "realtime_tag_evidence_snapshot": {
                "tag_rows": [
                    {"tag": "CPO", "role": "主tag", "stock_count": 8, "sample_stocks": ["新易盛"]}
                ]
            },
        }
    )

    view = build_daily_report_view("2026-06-05", service, run_mode="replay")
    charts = view["charts"]

    self.assertEqual(charts["market_capacity"]["status"], "ready")
    self.assertEqual(charts["market_capacity"]["points"][-1]["top50_share_pct"], 20.2)
    self.assertEqual(charts["mainline_turnover_share"]["status"], "ready")
    self.assertEqual(charts["mainline_turnover_share"]["points"][-1]["mainline"], "AI算力")
    self.assertEqual(charts["sector_heatmap"]["status"], "ready")
    self.assertEqual(charts["sector_heatmap"]["rows"][0]["sector"], "CPO")
    self.assertEqual(charts["sector_heatmap"]["columns"][-1]["key"], "attention")
    self.assertIn("注意力", charts["sector_heatmap"]["calculation_note"])
    self.assertEqual(charts["mainline_attack_scatter"]["points"][0]["sector"], "CPO")
    self.assertEqual(charts["hot_tag_composition"]["tags"][0]["tag"], "CPO")
    self.assertEqual(charts["cycle_week_view"]["rows"][0]["week_label"], "06-01当周")
    self.assertEqual(missing_required_fact_labels(view), [])
```

新增两个缺失测试：

```python
def test_missing_market_capacity_chart_stops_html_dashboard_generation(self):
    service = FakePostgresDailyReportService(
        snapshot={
            "market_research_snapshot": {
                "front_page_decision": {"final_action": "0%不参与", "allow_new_entry": False},
                "mainline_turnover_summary": {
                    "turnover_share_trend_rows": [
                        {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 18.2}
                    ]
                },
            },
            "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["净流入居前"]},
        }
    )

    view = build_daily_report_view("2026-06-05", service, run_mode="replay")

    self.assertEqual(view["charts"]["market_capacity"]["status"], "missing")
    self.assertIn("市场容量趋势", missing_required_fact_labels(view))

def test_missing_explanation_charts_degrades_without_required_fact_missing(self):
    service = FakePostgresDailyReportService(
        snapshot={
            "market_research_snapshot": {
                "front_page_decision": {"final_action": "0%不参与", "allow_new_entry": False},
                "mainline_turnover_summary": {
                    "turnover_share_trend_rows": [
                        {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 18.2}
                    ]
                },
            },
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "total_turnover": 1000,
            "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 19.0}]},
            "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["净流入居前"]},
        }
    )

    view = build_daily_report_view("2026-06-05", service, run_mode="replay")

    self.assertNotIn("板块热力矩阵", missing_required_fact_labels(view))
    self.assertEqual(view["charts"]["sector_heatmap"]["status"], "missing")
    self.assertIn("板块热力矩阵", view["diagnostics"]["degraded_facts"])
```

- [ ] **步骤 2：运行测试，确认它按预期失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py
```

预期：新增测试失败，错误包含 `KeyError: 'charts'` 或图表字段不存在。

- [ ] **步骤 3：写最小实现**

在 `scripts/report/html_report_view.py` 中新增这些 helper：

```python
def _chart_payload(status: str, *, title: str, missing_reasons: list[str] | None = None, **payload: Any) -> dict[str, Any]:
    return {"status": status, "title": title, "missing_reasons": missing_reasons or [], **payload}

def _extract_charts(data: dict[str, Any], target_date: str) -> dict[str, Any]:
    return {
        "market_capacity": _build_market_capacity_chart(data, target_date),
        "mainline_turnover_share": _build_mainline_turnover_share_chart(data),
        "sector_heatmap": _build_sector_heatmap_chart(data),
        "mainline_attack_scatter": _build_mainline_attack_scatter_chart(data),
        "hot_tag_composition": _build_hot_tag_composition_chart(data),
        "cycle_week_view": _build_cycle_week_view_chart(data),
    }
```

实现中只读取 `data` 中已有字段，不调用外部服务。`build_daily_report_view()` 增加：

```python
"charts": _extract_charts(data, target_date),
```

并在 `_missing_required_facts()` 读取：

```python
charts = view.get("charts") if isinstance(view.get("charts"), dict) else {}
if (charts.get("market_capacity") or {}).get("status") != "ready":
    missing.append("市场容量趋势")
if (charts.get("mainline_turnover_share") or {}).get("status") != "ready":
    missing.append("主线成交占比趋势")
```

解释图缺失时只写入 `diagnostics["degraded_facts"]`，不加入 `missing_required_facts`。

- [ ] **步骤 4：运行测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py
```

预期：`OK`。

---

### 任务 2：Renderer 层安全注入 ECharts 和图表 JSON

**文件：**

- 修改：`tests/test_daily_report_html_renderer.py`
- 修改：`scripts/report/html_report_renderer.py`

- [ ] **步骤 1：先写失败测试**

在 `_view()` fixture 中加入 `charts` 字段，包含五张首屏图和周视图。新增测试：

```python
def test_render_includes_chart_dashboard_and_safe_payload(self):
    view = _view()
    view["charts"]["hot_tag_composition"]["tags"][0]["tag"] = "<script>alert(1)</script>"

    html = render_daily_report_html(view)

    self.assertIn('id="daily-chart-market-capacity"', html)
    self.assertIn('id="daily-chart-mainline-share"', html)
    self.assertIn('id="daily-chart-sector-heatmap"', html)
    self.assertIn('id="daily-chart-attack-scatter"', html)
    self.assertIn('id="daily-chart-hot-tag"', html)
    self.assertIn('id="daily-chart-cycle-week"', html)
    self.assertIn('id="daily-chart-payload"', html)
    self.assertIn("\\u003cscript\\u003ealert(1)\\u003c/script\\u003e", html)
    self.assertNotIn("<script>alert(1)</script>", html)
    self.assertIn("daily-dashboard-panel", html)

def test_render_uses_local_echarts_before_cdn_when_available(self):
    html = render_daily_report_html(_view())

    if (ROOT / ".generated" / "vendor" / "echarts" / "echarts.min.js").exists():
        self.assertIn("<script>", html)
        self.assertNotIn("cdn.jsdelivr.net/npm/echarts", html)
    else:
        self.assertIn("cdn.jsdelivr.net/npm/echarts@5.6.0", html)

def test_render_shows_missing_reason_for_explanation_chart(self):
    view = _view()
    view["charts"]["sector_heatmap"] = {
        "status": "missing",
        "title": "板块热力矩阵",
        "missing_reasons": ["板块资金事实不足"],
        "columns": [],
        "rows": [],
    }

    html = render_daily_report_html(view)

    self.assertIn("板块资金事实不足", html)
```

- [ ] **步骤 2：运行测试，确认它按预期失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_renderer.py
```

预期：新增测试失败，错误包含图表容器或 `daily-chart-payload` 不存在。

- [ ] **步骤 3：写最小实现**

在 `scripts/report/html_report_renderer.py` 中增加：

```python
import json

def _echarts_source_path() -> Path:
    return _repo_root() / ".generated" / "vendor" / "echarts" / "echarts.min.js"

def _echarts_loader_html() -> str:
    source_path = _echarts_source_path()
    if source_path.exists():
        source = source_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
        return f"<script>\n{source}\n</script>"
    return '<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>'

def _json_for_html_script(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
```

`render_daily_report_html()` 增加替换字段：

```python
echarts_loader=_echarts_loader_html(),
charts_payload=_json_for_html_script(_as_dict(view.get("charts"))),
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_renderer.py
```

预期：`OK`。

---

### 任务 3：模板加入图表驾驶舱和最小交互

**文件：**

- 修改：`scripts/templates/daily_report_reader.html`
- 验证：`tests/test_daily_report_html_renderer.py`

- [ ] **步骤 1：更新模板结构**

在导航中增加：

```html
<a href="#chart-dashboard">图表驾驶舱</a>
```

在 `reader-header` 后、`tomorrow-action` 前增加：

```html
<section id="chart-dashboard" class="chart-dashboard">
  <div class="dashboard-summary">
    <div>
      <h2>图表驾驶舱</h2>
      <p class="muted">先看容量与主线，再看板块、攻击证据和热榜注意力。</p>
    </div>
    <div id="daily-dashboard-panel" class="daily-dashboard-panel" aria-live="polite">点击图表元素查看解释。</div>
  </div>
  <div class="chart-grid chart-grid-core">
    <div class="chart-panel"><h3>市场容量趋势</h3><div id="daily-chart-market-capacity" class="daily-chart" data-chart-key="market_capacity"></div></div>
    <div class="chart-panel"><h3>主线成交占比趋势</h3><div id="daily-chart-mainline-share" class="daily-chart" data-chart-key="mainline_turnover_share"></div></div>
  </div>
  <div class="chart-grid chart-grid-explain">
    <div class="chart-panel"><h3>板块热力矩阵</h3><div id="daily-chart-sector-heatmap" class="daily-chart" data-chart-key="sector_heatmap"></div></div>
    <div class="chart-panel"><h3>主线攻击证据</h3><div id="daily-chart-attack-scatter" class="daily-chart" data-chart-key="mainline_attack_scatter"></div></div>
    <div class="chart-panel"><h3>热榜 Tag 构成</h3><div id="daily-chart-hot-tag" class="daily-chart" data-chart-key="hot_tag_composition"></div></div>
  </div>
  <div class="chart-panel chart-panel-wide"><h3>板块周视图</h3><div id="daily-chart-cycle-week" class="daily-chart daily-chart-short" data-chart-key="cycle_week_view"></div></div>
</section>
<script type="application/json" id="daily-chart-payload">$charts_payload</script>
```

- [ ] **步骤 2：加入 CSS**

增加图表容器固定高度、双列/三列布局、移动端单列布局：

```css
.chart-dashboard { padding-top: 0; }
.dashboard-summary { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 280px); gap: 16px; align-items: start; margin-bottom: 16px; }
.daily-dashboard-panel { min-height: 88px; padding: 10px 12px; border: 1px solid var(--reader-line); border-radius: 8px; background: var(--reader-surface); color: var(--reader-muted); font-size: 13px; line-height: 1.55; }
.chart-grid { display: grid; gap: 14px; margin-bottom: 14px; }
.chart-grid-core { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.chart-grid-explain { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.chart-panel { min-width: 0; border: 1px solid var(--reader-line); border-radius: 8px; background: var(--reader-bg); padding: 12px; }
.chart-panel h3 { margin: 0 0 8px; font-size: 14px; line-height: 1.35; }
.daily-chart { width: 100%; height: 260px; }
.daily-chart-short { height: 210px; }
.chart-missing { display: grid; place-items: center; height: 100%; padding: 12px; color: var(--reader-muted); text-align: center; font-size: 13px; }
```

移动端：

```css
.dashboard-summary,
.chart-grid-core,
.chart-grid-explain { grid-template-columns: 1fr; }
.daily-chart { height: 240px; }
```

- [ ] **步骤 3：加入最小交互脚本**

在 `</body>` 前加入 `$echarts_loader` 和脚本。脚本只做：

- 解析 `daily-chart-payload`。
- 缺失图显示 `.chart-missing`。
- 初始化五张图和周视图。
- 悬停使用 ECharts tooltip。
- 点击事件更新 `daily-dashboard-panel`。
- resize 时调用 `chart.resize()`。

- [ ] **步骤 4：运行 renderer 测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_renderer.py
```

预期：`OK`。

---

### 任务 4：入口兼容和聚焦验证

**文件：**

- 验证：`tests/test_daily_report_entry_html_output.py`

- [ ] **步骤 1：运行入口层测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_entry_html_output.py
```

预期：`OK`。

- [ ] **步骤 2：运行完整聚焦测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
```

预期：`OK`。

- [ ] **步骤 3：做提交前审计**

如果当前环境有可用的子代理工具，使用 `gpt-5.5` 和 `xhigh` 对本次改动做审计。审计重点：

- 是否只触碰当前范围需要的文件。
- 核心图缺失是否停止 HTML 生成。
- 解释图缺失是否只降级显示原因。
- 热榜 tag 是否只作为注意力入口。
- JSON 注入是否安全。
- 测试是否覆盖主路径和缺失路径。

如果当前环境没有可用的子代理工具，用本会话完成同等审计并说明限制。

- [ ] **步骤 4：提交前等待用户确认**

本计划不自动执行 `git add` 或 `git commit`。如果用户明确要求提交，再单独处理。

---

## 自检

- 规格覆盖：五张首屏图、周视图下钻、核心图缺失处理、解释图缺失处理、ECharts 加载、安全 JSON、热榜 tag 计算边界均有任务覆盖。
- 占位符扫描：无 `TBD`、`TODO`、`implement later`、`fill in details`。
- 类型一致性：`charts` 键、图表 `status`、`missing_reasons`、`points`、`rows`、`tags` 命名在测试和实现中保持一致。
