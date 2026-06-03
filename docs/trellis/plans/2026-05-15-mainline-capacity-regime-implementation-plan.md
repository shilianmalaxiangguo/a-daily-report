# Mainline Capacity And Regime Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old `双层主线结论` report surface with `主线容量与格局判断`.

**Architecture:** Add one structured summary payload under `mainline_turnover_summary`, normalize it through report support helpers, and render the new table in the front page, front digest, and market research snapshot. Keep existing turnover-share trend rows unchanged so the evidence table remains stable.

**Tech Stack:** Python stdlib, existing unittest suite, existing report renderer modules.

---

## File Structure

- Modify `scripts/domains/market_state/mainline_turnover_summary_runtime.py`
  - Add structured `mainline_capacity_regime_summary` construction.
  - Keep existing `double_mainline_summary` in the payload for backward compatibility during this patch, but stop rendering it in front surfaces.
- Modify `scripts/report/mainline_turnover_summary_support.py`
  - Add `resolve_mainline_capacity_regime_summary(context)`.
  - Keep `resolve_double_mainline_summary` available for old callers until later cleanup.
- Modify `scripts/report/front_page_v2_renderer.py`
  - Replace `_double_mainline_lines` rendering with `_mainline_capacity_regime_lines`.
- Modify `scripts/report/front_summary_renderer.py`
  - Replace old double-mainline digest table with the new capacity/regime digest table.
- Modify `scripts/report/market_research_snapshot_nodes.py`
  - Add a render node for `主线容量与格局判断`.
- Modify `scripts/report/market_research_snapshot_node_registry.py`
  - Register the new node after `pivot_mainline_interpretation` and before evidence-table rows.
- Tests:
  - `tests/test_mainline_turnover_summary_runtime.py`
  - `tests/test_front_page_v2_renderer.py`
  - `tests/test_front_summary_renderer.py`
  - `tests/test_market_research_renderer.py`

## Task 1: Runtime Summary Contract

**Files:**
- Modify: `scripts/domains/market_state/mainline_turnover_summary_runtime.py`
- Test: `tests/test_mainline_turnover_summary_runtime.py`

- [ ] **Step 1: Write failing tests for capacity, no-mainline, and non-bull multi-hotspot behavior**

Append these tests to `MainlineTurnoverSummaryRuntimeTest` in `tests/test_mainline_turnover_summary_runtime.py`:

```python
    def test_build_mainline_turnover_summary_exports_capacity_regime_summary(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-14",
            current_mainline_history_record={
                "date": "2026-05-14",
                "primary_mainline": "半导体",
                "secondary_mainline": "电力",
                "competition_mainline": "化学制品",
                "sector_relationship_state": "混沌接力",
                "mainline_process": "启动",
                "mainline_confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
            },
            recent_mainline_history=[
                {"date": "2026-05-12", "primary_mainline": "电力"},
                {"date": "2026-05-13", "primary_mainline": "电力"},
            ],
            current_sector_turnover_snapshot={
                "date": "2026-05-14",
                "sector_name": "半导体",
                "sector_turnover": 4206.70,
                "total_turnover": 33880.86,
                "turnover_share_pct": 12.4,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-12", "sector_name": "电力", "total_turnover": 26000.00, "turnover_share_pct": 10.2},
                {"date": "2026-05-13", "sector_name": "电力", "total_turnover": 30000.00, "turnover_share_pct": 11.8},
            ],
        )

        summary = result["mainline_capacity_regime_summary"]
        self.assertEqual(summary["mainline_capacity"], "双线孕育")
        self.assertEqual(summary["mainline_regime"], "混沌接力")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["other_lines"], "电力 / 化学制品")
        self.assertEqual(summary["confirmation_evidence"], "半导体高标和涨停更集中，成交占比靠前")
        self.assertEqual(summary["sector_relationship_state"], "混沌接力")
        self.assertEqual(summary["mainline_process"], "启动")
        self.assertIn("今日33880.86亿", summary["capacity_evidence"])
        self.assertIn("昨日30000.00亿", summary["capacity_evidence"])
        self.assertIn("近25日中位数30000.00亿", summary["capacity_evidence"])

    def test_build_mainline_turnover_summary_can_keep_no_mainline_when_capacity_is_low(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-14",
            current_mainline_history_record={"date": "2026-05-14", "primary_mainline": ""},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-14",
                "sector_name": "",
                "total_turnover": 7800.00,
                "turnover_share_pct": 0.0,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-13", "sector_name": "机器人", "total_turnover": 9200.00, "turnover_share_pct": 4.2},
                {"date": "2026-05-12", "sector_name": "军工", "total_turnover": 9500.00, "turnover_share_pct": 4.1},
            ],
        )

        summary = result["mainline_capacity_regime_summary"]
        self.assertEqual(summary["mainline_capacity"], "低容量")
        self.assertEqual(summary["mainline_regime"], "无主线")
        self.assertEqual(summary["primary_line"], "暂无")
        self.assertEqual(summary["tomorrow_action"], "不强行找主线，只保留异常观察")

    def test_build_mainline_turnover_summary_does_not_promote_three_hotspots_to_multi_line_without_bull_market(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-14",
            current_mainline_history_record={
                "date": "2026-05-14",
                "primary_mainline": "半导体",
                "secondary_mainline": "电力",
                "competition_mainline": "化学制品",
                "market_regime": "震荡",
            },
            recent_mainline_history=[{"date": "2026-05-13", "primary_mainline": "电力"}],
            current_sector_turnover_snapshot={
                "date": "2026-05-14",
                "sector_name": "半导体",
                "total_turnover": 33880.86,
                "turnover_share_pct": 12.4,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-13", "sector_name": "电力", "total_turnover": 30000.00, "turnover_share_pct": 11.8},
                {"date": "2026-05-12", "sector_name": "化学制品", "total_turnover": 29500.00, "turnover_share_pct": 9.6},
            ],
        )

        summary = result["mainline_capacity_regime_summary"]
        self.assertNotEqual(summary["mainline_regime"], "多主线牛市")
        self.assertEqual(summary["mainline_regime"], "混沌接力")
```

- [ ] **Step 2: Run the focused runtime tests and verify they fail**

Run:

```bash
python -m unittest tests.test_mainline_turnover_summary_runtime.MainlineTurnoverSummaryRuntimeTest -v
```

Expected: FAIL because `mainline_capacity_regime_summary` does not exist.

- [ ] **Step 3: Add minimal runtime helpers**

In `scripts/domains/market_state/mainline_turnover_summary_runtime.py`, add these helpers above `build_mainline_turnover_summary`:

```python
def _format_signed_pct(value):
    value = _safe_float(value)
    return f"{value:+.1f}%"


def _median(values):
    values = sorted(_safe_float(value) for value in values if _safe_float(value) > 0)
    if not values:
        return 0.0
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _recent_total_turnover_values(recent_sector_turnover_history, current_snapshot):
    rows = list(recent_sector_turnover_history or [])
    if current_snapshot:
        rows.append(current_snapshot)
    values = []
    for item in rows[-25:]:
        total = _safe_float((item or {}).get("total_turnover"))
        if total > 0:
            values.append(total)
    return values


def _previous_total_turnover(recent_sector_turnover_history):
    for item in reversed(list(recent_sector_turnover_history or [])):
        total = _safe_float((item or {}).get("total_turnover"))
        if total > 0:
            return total
    return 0.0


def _capacity_relative_label(current_total, median_total):
    if current_total <= 0 or median_total <= 0:
        return "待累计"
    ratio = current_total / median_total
    if ratio < 0.9:
        return "缩量"
    if ratio < 1.1:
        return "常量"
    if ratio < 1.4:
        return "放量"
    return "巨量"


def _capacity_conclusion(current_total, previous_total, median_total, market_regime=""):
    if current_total <= 0:
        return "容量待累计"
    relative_label = _capacity_relative_label(current_total, median_total)
    daily_expanding = previous_total > 0 and current_total >= previous_total * 1.05
    daily_shrinking = previous_total > 0 and current_total <= previous_total * 0.95
    bull_like = str(market_regime or "").strip() in ("牛市", "超级牛市", "极强结构性行情")
    if relative_label == "巨量" and bull_like:
        return "牛市多线容量"
    if relative_label == "巨量":
        return "双线容量"
    if relative_label == "放量" and daily_expanding:
        return "双线孕育"
    if relative_label == "放量":
        return "单线容量"
    if relative_label == "缩量" or daily_shrinking:
        return "低容量"
    return "单线容量"


def _other_lines_text(current_record):
    values = []
    for key in ("secondary_mainline", "competition_mainline", "background_mainline"):
        value = str((current_record or {}).get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    return " / ".join(values) if values else "-"


def _count_other_lines(current_record):
    text = _other_lines_text(current_record)
    if text == "-":
        return 0
    return len([part for part in text.split(" / ") if part.strip()])


def _resolve_mainline_regime(current_mainline, current_record, capacity):
    if not current_mainline:
        return "无主线"
    explicit = str((current_record or {}).get("mainline_regime") or "").strip()
    if explicit:
        return explicit
    relationship = str((current_record or {}).get("sector_relationship_state") or "").strip()
    if relationship in ("混沌接力", "交替竞争", "主线+背景线"):
        return relationship
    other_count = _count_other_lines(current_record)
    market_regime = str((current_record or {}).get("market_regime") or "").strip()
    if other_count >= 2 and market_regime not in ("牛市", "超级牛市", "极强结构性行情"):
        return "混沌接力"
    if other_count >= 2:
        return "多主线牛市"
    if other_count == 1 and capacity in ("双线孕育", "双线容量", "牛市多线容量"):
        return "双主线竞争"
    if other_count == 1:
        return "主线+背景线"
    return "单主线聚焦"


def _capacity_evidence_text(current_total, previous_total, median_total, relative_label):
    parts = []
    if current_total > 0:
        parts.append(f"今日{current_total:.2f}亿")
    else:
        parts.append("今日成交额待累计")
    if previous_total > 0:
        change_pct = (current_total - previous_total) / previous_total * 100 if current_total > 0 else 0.0
        parts.append(f"昨日{previous_total:.2f}亿，日环比{_format_signed_pct(change_pct)}")
    else:
        parts.append("昨日成交额待累计")
    if median_total > 0:
        parts.append(f"近25日中位数{median_total:.2f}亿，{relative_label}")
    else:
        parts.append("近25日中位数待累计")
    return "；".join(parts)


def _default_regime_action(regime, current_mainline, action_text):
    if regime == "无主线":
        return "不强行找主线，只保留异常观察"
    if regime == "单主线聚焦":
        return f"只围绕{current_mainline}做减法" if current_mainline else action_text
    if regime == "双主线竞争":
        return "不同时押两边，先看谁继续被资金选择"
    if regime == "主线+背景线":
        return "主攻线给执行优先级，背景线只观察回流"
    if regime == "混沌接力":
        return "不把每次轮动都当新主线，候选只保留判断样本"
    if regime == "多主线牛市":
        return "多线可以同时给资格，但仍要缩到具体参与窗口"
    return action_text or "先看主线证据是否继续聚焦"


def _build_mainline_capacity_regime_summary(
    *,
    current_mainline,
    current_record,
    current_snapshot,
    recent_sector_turnover_history,
    action_text,
):
    current_total = _safe_float((current_snapshot or {}).get("total_turnover"))
    previous_total = _previous_total_turnover(recent_sector_turnover_history)
    median_total = _median(_recent_total_turnover_values(recent_sector_turnover_history, current_snapshot))
    relative_label = _capacity_relative_label(current_total, median_total)
    capacity = _capacity_conclusion(
        current_total,
        previous_total,
        median_total,
        market_regime=(current_record or {}).get("market_regime"),
    )
    regime = _resolve_mainline_regime(current_mainline, current_record, capacity)
    process = str((current_record or {}).get("mainline_process") or "").strip()
    if not process:
        process = "无" if not current_mainline else "启动" if regime in ("单主线聚焦", "主线+背景线", "混沌接力") else "待观察"
    confirmation = str((current_record or {}).get("mainline_confirmation_evidence") or "").strip()
    if not confirmation:
        share = _safe_float((current_snapshot or {}).get("turnover_share_pct"))
        if current_mainline and share > 0:
            confirmation = f"{current_mainline}成交占比{share:.1f}%"
        elif current_mainline:
            confirmation = "资金态度待补充"
        else:
            confirmation = "资金未形成明确进攻方向"
    relationship = str((current_record or {}).get("sector_relationship_state") or "").strip() or (
        "暂未分出" if not current_mainline else regime
    )
    tomorrow_action = str((current_record or {}).get("mainline_regime_action") or "").strip()
    return {
        "mainline_capacity": capacity,
        "mainline_regime": regime,
        "primary_line": current_mainline or "暂无",
        "other_lines": _other_lines_text(current_record),
        "confirmation_evidence": confirmation,
        "sector_relationship_state": relationship,
        "mainline_process": process,
        "tomorrow_action": tomorrow_action or _default_regime_action(regime, current_mainline, action_text),
        "capacity_evidence": _capacity_evidence_text(current_total, previous_total, median_total, relative_label),
    }
```

- [ ] **Step 4: Attach the new summary to the runtime payload**

Inside `build_mainline_turnover_summary`, before the final `return`, add:

```python
    capacity_regime_summary = _build_mainline_capacity_regime_summary(
        current_mainline=current_mainline,
        current_record=current_record,
        current_snapshot=current_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        action_text=action_text,
    )
```

Then add this key to the returned dictionary:

```python
        "mainline_capacity_regime_summary": capacity_regime_summary,
```

- [ ] **Step 5: Run runtime tests and verify they pass**

Run:

```bash
python -m unittest tests.test_mainline_turnover_summary_runtime.MainlineTurnoverSummaryRuntimeTest -v
```

Expected: PASS.

- [ ] **Step 6: Commit runtime contract**

```bash
git add scripts/domains/market_state/mainline_turnover_summary_runtime.py tests/test_mainline_turnover_summary_runtime.py
git commit -m "feat: add mainline capacity regime summary"
```

## Task 2: Report Support Resolver

**Files:**
- Modify: `scripts/report/mainline_turnover_summary_support.py`
- Test: `tests/test_front_summary_renderer.py`

- [ ] **Step 1: Write failing digest renderer test for the new table**

Replace `test_render_front_digest_outputs_double_mainline_and_turnover_share_tables` in `tests/test_front_summary_renderer.py` with:

```python
    def test_render_front_digest_outputs_mainline_capacity_regime_and_turnover_share_tables(self):
        lines = render_front_digest(
            {
                "headline": "只看主线核心承接",
                "state_text": "修复延续",
                "mainline_label": "半导体",
                "style_action_text": "主线内做减法",
                "risk_parts": ["跌停2只"],
                "can_open_text": "只等确认",
                "mainline_capacity_regime_summary": {
                    "mainline_capacity": "双线孕育",
                    "mainline_regime": "主线+背景线",
                    "primary_line": "半导体",
                    "other_lines": "电力 / 化学制品",
                    "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                    "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                    "mainline_process": "半导体启动，电力背景线",
                    "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                },
                "turnover_share_trend_rows": [
                    {
                        "date": "04-24",
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "算力",
                        "mainline_turnover": "2180亿",
                        "market_turnover": "12834亿",
                        "share": "17.0%",
                        "share_change": "+1.2pct",
                        "interpretation": "主线占比继续抬升，资金仍在主线内加强",
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 主线+背景线 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
        self.assertNotIn("| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |", rendered)
        self.assertIn("| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |", rendered)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
python -m unittest tests.test_front_summary_renderer.FrontSummaryRendererTest.test_render_front_digest_outputs_mainline_capacity_regime_and_turnover_share_tables -v
```

Expected: FAIL because the renderer still emits the old table.

- [ ] **Step 3: Add the resolver**

In `scripts/report/mainline_turnover_summary_support.py`, add:

```python
def resolve_mainline_capacity_regime_summary(context=None):
    context = context or {}
    source = dict(context.get("mainline_capacity_regime_summary") or {})
    if not source:
        source = dict((context.get("mainline_turnover_summary") or {}).get("mainline_capacity_regime_summary") or {})

    if not source:
        return {}

    return {
        "mainline_capacity": str(source.get("mainline_capacity") or "-").strip() or "-",
        "mainline_regime": str(source.get("mainline_regime") or "-").strip() or "-",
        "primary_line": str(source.get("primary_line") or "-").strip() or "-",
        "other_lines": str(source.get("other_lines") or "-").strip() or "-",
        "confirmation_evidence": str(source.get("confirmation_evidence") or "-").strip() or "-",
        "sector_relationship_state": str(source.get("sector_relationship_state") or "-").strip() or "-",
        "mainline_process": str(source.get("mainline_process") or "-").strip() or "-",
        "tomorrow_action": str(source.get("tomorrow_action") or "-").strip() or "-",
    }
```

- [ ] **Step 4: Run support-adjacent test and verify it still fails at renderer**

Run:

```bash
python -m unittest tests.test_front_summary_renderer.FrontSummaryRendererTest.test_render_front_digest_outputs_mainline_capacity_regime_and_turnover_share_tables -v
```

Expected: FAIL until the renderer imports and uses the new resolver.

- [ ] **Step 5: Commit resolver**

```bash
git add scripts/report/mainline_turnover_summary_support.py tests/test_front_summary_renderer.py
git commit -m "feat: resolve mainline capacity regime summary"
```

## Task 3: Front Digest Renderer

**Files:**
- Modify: `scripts/report/front_summary_renderer.py`
- Test: `tests/test_front_summary_renderer.py`

- [ ] **Step 1: Update the renderer import**

Change the import at the top of `scripts/report/front_summary_renderer.py` to:

```python
from report.mainline_turnover_summary_support import (
    resolve_mainline_capacity_regime_summary,
    resolve_turnover_share_trend_rows,
)
```

- [ ] **Step 2: Replace the old table renderer**

Replace `_render_double_mainline_summary_table` with:

```python
def _render_mainline_capacity_regime_table(context):
    summary = resolve_mainline_capacity_regime_summary(context)
    if not summary:
        return []
    return [
        "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |",
        "|----------|----------|--------|----------------|--------------|--------------|----------|----------|",
        (
            "| {mainline_capacity} | {mainline_regime} | {primary_line} | {other_lines} | "
            "{confirmation_evidence} | {sector_relationship_state} | {mainline_process} | {tomorrow_action} |"
        ).format(**summary),
    ]
```

- [ ] **Step 3: Render the new table in `render_front_digest`**

Replace:

```python
    lines.extend(_render_double_mainline_summary_table(context))
```

with:

```python
    lines.extend(_render_mainline_capacity_regime_table(context))
```

- [ ] **Step 4: Run front digest tests**

Run:

```bash
python -m unittest tests.test_front_summary_renderer.FrontSummaryRendererTest -v
```

Expected: PASS.

- [ ] **Step 5: Commit front digest renderer**

```bash
git add scripts/report/front_summary_renderer.py tests/test_front_summary_renderer.py
git commit -m "feat: render mainline capacity regime in front digest"
```

## Task 4: Front Page Renderer

**Files:**
- Modify: `scripts/report/front_page_v2_renderer.py`
- Test: `tests/test_front_page_v2_renderer.py`

- [ ] **Step 1: Write failing front page test**

Add this test to `FrontPageV2RendererTest` in `tests/test_front_page_v2_renderer.py`:

```python
    def test_front_page_replaces_double_mainline_with_capacity_regime_table(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-14",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "mainline_capacity_regime_summary": {
                            "mainline_capacity": "双线孕育",
                            "mainline_regime": "混沌接力",
                            "primary_line": "半导体",
                            "other_lines": "电力 / 化学制品",
                            "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                            "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                            "mainline_process": "半导体启动，电力背景线",
                            "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                        },
                    },
                    "unique_action_target": {
                        "name": "中船特气",
                        "code": "688146",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                },
            )
        )

        self.assertIn("### 4. 主线容量与格局判断", rendered)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 混沌接力 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
        self.assertNotIn("### 4. 双层主线结论", rendered)
        self.assertNotIn("| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |", rendered)
```

- [ ] **Step 2: Run the focused front page test and verify it fails**

Run:

```bash
python -m unittest tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_replaces_double_mainline_with_capacity_regime_table -v
```

Expected: FAIL because the old double-mainline section is still rendered.

- [ ] **Step 3: Update imports**

In `scripts/report/front_page_v2_renderer.py`, change the `report.mainline_turnover_summary_support` import to include:

```python
    resolve_mainline_capacity_regime_summary,
```

- [ ] **Step 4: Replace `_double_mainline_lines`**

Replace `_double_mainline_lines` with:

```python
def _mainline_capacity_regime_lines(snapshot):
    summary = resolve_mainline_capacity_regime_summary(snapshot.get("mainline_turnover_summary") or {})
    if not summary:
        summary = resolve_mainline_capacity_regime_summary(snapshot)
    if not summary:
        summary = {
            "mainline_capacity": "容量待累计",
            "mainline_regime": "无主线",
            "primary_line": "暂无",
            "other_lines": "-",
            "confirmation_evidence": "资金未形成明确进攻方向",
            "sector_relationship_state": "暂未分出",
            "mainline_process": "无",
            "tomorrow_action": "不强行找主线，只保留异常观察",
        }
    return [
        "### 4. 主线容量与格局判断",
        "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |",
        "|----------|----------|--------|----------------|--------------|--------------|----------|----------|",
        (
            "| {mainline_capacity} | {mainline_regime} | {primary_line} | {other_lines} | "
            "{confirmation_evidence} | {sector_relationship_state} | {mainline_process} | {tomorrow_action} |"
        ).format(**summary),
        "",
    ]
```

- [ ] **Step 5: Update the call site**

Find the section assembly in `render_front_page_v2` that calls `_double_mainline_lines(snapshot)` and replace it with:

```python
_mainline_capacity_regime_lines(snapshot)
```

- [ ] **Step 6: Run front page tests**

Run:

```bash
python -m unittest tests.test_front_page_v2_renderer.FrontPageV2RendererTest -v
```

Expected: PASS after updating old assertions that explicitly expect the old double-mainline table. Update those assertions to expect `主线容量与格局判断` only where they are testing this surface.

- [ ] **Step 7: Commit front page renderer**

```bash
git add scripts/report/front_page_v2_renderer.py tests/test_front_page_v2_renderer.py
git commit -m "feat: render mainline capacity regime on front page"
```

## Task 5: Market Research Snapshot Node

**Files:**
- Modify: `scripts/report/market_research_snapshot_nodes.py`
- Modify: `scripts/report/market_research_snapshot_node_registry.py`
- Test: `tests/test_market_research_renderer.py`

- [ ] **Step 1: Write failing market research renderer test**

Add this test to `tests/test_market_research_renderer.py`:

```python
    def test_render_market_research_snapshot_section_renders_mainline_capacity_regime_node(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_capacity_regime"],
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "双线孕育",
                        "mainline_regime": "混沌接力",
                        "primary_line": "半导体",
                        "other_lines": "电力 / 化学制品",
                        "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                        "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                        "mainline_process": "半导体启动，电力背景线",
                        "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("### 4. 主线容量与格局判断", rendered)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 混沌接力 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
```

- [ ] **Step 2: Run the focused market research test and verify it fails**

Run:

```bash
python -m unittest tests.test_market_research_renderer.MarketResearchRendererTest.test_render_market_research_snapshot_section_renders_mainline_capacity_regime_node -v
```

Expected: FAIL because the node does not exist.

- [ ] **Step 3: Add the node builder**

In `scripts/report/market_research_snapshot_nodes.py`, import `resolve_mainline_capacity_regime_summary` from `report.mainline_turnover_summary_support`, then add:

```python
def build_market_research_snapshot_mainline_capacity_regime_node(context, node_meta=None, node_lookup=None):
    summary = resolve_mainline_capacity_regime_summary(context)
    if not summary:
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = [
        "### 4. 主线容量与格局判断",
        "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |",
        "|----------|----------|--------|----------------|--------------|--------------|----------|----------|",
        (
            "| {mainline_capacity} | {mainline_regime} | {primary_line} | {other_lines} | "
            "{confirmation_evidence} | {sector_relationship_state} | {mainline_process} | {tomorrow_action} |"
        ).format(**summary),
    ]
    return {"lines": lines, "exports": {}, "module_logs": []}
```

- [ ] **Step 4: Register the node**

In `scripts/report/market_research_snapshot_node_registry.py`, add this entry after `pivot_mainline_interpretation`:

```python
    {"node_key": "mainline_capacity_regime", "title": "主线容量与格局判断"},
```

In the builder map where `market_research_snapshot_nodes` are wired, add:

```python
"mainline_capacity_regime": build_market_research_snapshot_mainline_capacity_regime_node,
```

- [ ] **Step 5: Run market research renderer tests**

Run:

```bash
python -m unittest tests.test_market_research_renderer -v
```

Expected: PASS.

- [ ] **Step 6: Commit market research node**

```bash
git add scripts/report/market_research_snapshot_nodes.py scripts/report/market_research_snapshot_node_registry.py tests/test_market_research_renderer.py
git commit -m "feat: add mainline capacity regime research node"
```

## Task 6: Remove Old Front-surface Expectations

**Files:**
- Modify: `tests/test_front_page_v2_renderer.py`
- Modify: `tests/test_front_summary_renderer.py`
- Modify: `tests/test_report_runtime.py` if failures point there

- [ ] **Step 1: Run the report renderer test subset**

Run:

```bash
python -m unittest \
  tests.test_front_page_v2_renderer \
  tests.test_front_summary_renderer \
  tests.test_market_research_renderer \
  tests.test_report_runtime \
  -v
```

Expected: Some failures may remain where tests assert the old `周期主线 | 当天主攻线 | 两者关系 | 明日动作` front-surface table.

- [ ] **Step 2: Update old table assertions**

For failures that assert this old table:

```python
self.assertIn("| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |", rendered)
```

replace with:

```python
self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
```

For old row assertions that used:

```python
"| 半导体 | 半导体 | 周期主线与当天主攻线一致 | 继续围绕半导体观察承接 |"
```

replace with a row built from `mainline_capacity_regime_summary`, for example:

```python
"| 单线容量 | 单主线聚焦 | 半导体 | - | 半导体成交占比18.1% | 单主线聚焦 | 启动 | 只围绕半导体做减法 |"
```

- [ ] **Step 3: Keep turnover-share trend assertions unchanged**

Do not change assertions for:

```python
"| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |"
```

This table remains as evidence.

- [ ] **Step 4: Re-run renderer subset**

Run:

```bash
python -m unittest \
  tests.test_front_page_v2_renderer \
  tests.test_front_summary_renderer \
  tests.test_market_research_renderer \
  tests.test_report_runtime \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit assertion cleanup**

```bash
git add tests/test_front_page_v2_renderer.py tests/test_front_summary_renderer.py tests/test_market_research_renderer.py tests/test_report_runtime.py
git commit -m "test: expect mainline capacity regime table"
```

## Task 7: Acceptance Audit And Docs Check

**Files:**
- Modify: `tests/test_report_acceptance_audit.py` if the audit has explicit old-table checks
- Modify: `scripts/report/report_acceptance_audit.py` only if needed by failing tests
- Read: `docs/trellis/specs/2026-05-15-mainline-capacity-regime-design.md`

- [ ] **Step 1: Run acceptance-audit tests**

Run:

```bash
python -m unittest tests.test_report_acceptance_audit -v
```

Expected: PASS or fail only on old double-mainline wording checks.

- [ ] **Step 2: If old-table checks fail, update them**

If an old header is required, replace it with:

```python
"| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |"
```

If the audit should forbid old rendering, add:

```python
OLD_DOUBLE_MAINLINE_HEADER = "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |"
```

and assert reports do not contain it on the front surface.

- [ ] **Step 3: Run terminology scan**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

targets = [
    Path("scripts"),
    Path("tests"),
    Path("docs/trellis/specs/2026-05-15-mainline-capacity-regime-design.md"),
]
parts = [("90", "00e"), ("1", ".5w"), ("2", "w"), ("门", "禁"), ("能量", "学"), ("能量", "释放"), ("群体", "行为")]
for target in targets:
    paths = target.rglob("*") if target.is_dir() else [target]
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for left, right in parts:
            needle = left + right
            if needle in text:
                print(f"{path}: contains forbidden wording")
PY
```

Expected: No matches in `scripts/` for forbidden front-surface output. Matches in older docs are acceptable only if they are historical specs; the new 2026-05-15 spec must not contain the old experience anchors.

- [ ] **Step 4: Run final focused verification**

Run:

```bash
python -m unittest \
  tests.test_mainline_turnover_summary_runtime \
  tests.test_front_summary_renderer \
  tests.test_front_page_v2_renderer \
  tests.test_market_research_renderer \
  tests.test_report_acceptance_audit \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit final cleanup**

```bash
git add scripts/report/report_acceptance_audit.py tests/test_report_acceptance_audit.py
git commit -m "test: audit mainline capacity regime wording"
```

## Self-review Checklist

- Spec coverage:
  - `主线容量`: Task 1 runtime, Task 4 front page, Task 5 market research.
  - `主线格局`: Task 1 runtime and all render tasks.
  - `主线确认` remains simple: Task 1 uses explicit evidence fields and fallback only from existing share.
  - `混沌接力 / 非牛市三热点`: Task 1 test.
  - Replace `双层主线结论`: Tasks 3, 4, 6.
  - Keep turnover-share trend evidence: Tasks 3, 4, 6.
- Placeholder scan:
  - No `TBD`, `TODO`, `implement later`, or unspecified "add tests" steps.
- Type consistency:
  - Structured key is `mainline_capacity_regime_summary` everywhere.
  - Table fields are `mainline_capacity`, `mainline_regime`, `primary_line`, `other_lines`, `confirmation_evidence`, `sector_relationship_state`, `mainline_process`, `tomorrow_action`.
