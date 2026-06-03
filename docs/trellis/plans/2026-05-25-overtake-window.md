# Overtake Window Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small `超车窗口判断` layer that tells the daily report when a confirmed direction can move from observation to direction-level participation search.

**Architecture:** Build `overtake_window_summary` in the market-state runtime from existing attack evidence and capacity context, resolve it through report support, then render one table directly below `主线攻击证据`. The v1 scope does not change candidate scoring, position sizing, stop logic, or snap-ui.

**Tech Stack:** Python 3.14, `unittest`, existing market-state runtime and Markdown node renderer.

---

## Scope

**In Scope**
- Add `build_overtake_window_summary(...)` to `scripts/domains/market_state/mainline_turnover_summary_runtime.py`.
- Include `overtake_window_summary` in `build_mainline_turnover_summary(...)`.
- Add resolver helpers to `scripts/report/mainline_turnover_summary_support.py`.
- Add a `#### 超车窗口判断` table after `主线攻击证据` in `scripts/report/market_research_snapshot_nodes.py`.
- Cover `open`, `confirm_next`, `observe`, and `no_trade` samples in tests.

**Out Of Scope**
- No new data source.
- No direct participation instruction, no candidate-score rewrite, no position-size change, no stop change.
- No snap-ui page.

**Done Definition**
- The runtime summary returns `overtake_window_summary`.
- The report table renders `对手失速 / 我方稳住 / 失速差 / 明日动作`.
- Tests use `.generated/venv-py314/bin/python3.14 -m unittest ...` and pass for the touched behavior.

## File Structure

- Modify `scripts/domains/market_state/mainline_turnover_summary_runtime.py`: runtime signal construction and summary injection.
- Modify `scripts/report/mainline_turnover_summary_support.py`: normalize and resolve summary / rows for rendering.
- Modify `scripts/report/market_research_snapshot_nodes.py`: render table below `主线攻击证据`.
- Modify `tests/test_mainline_turnover_summary_runtime.py`: runtime state samples.
- Modify `tests/test_mainline_turnover_summary_support.py`: resolver fallback and row normalization.
- Modify `tests/test_market_research_renderer.py` or `tests/test_market_research_runtime.py` only if the node behavior is not already covered elsewhere.

## Task 1: Runtime Summary

**Files:**
- Modify: `tests/test_mainline_turnover_summary_runtime.py`
- Modify: `scripts/domains/market_state/mainline_turnover_summary_runtime.py`

- [ ] **Step 1: Write failing tests for four samples**

```python
from domains.market_state.mainline_turnover_summary_runtime import (
    build_mainline_attack_evidence_summary,
    build_overtake_window_summary,
)


def _row(sector, *, rank, amount, limit_up, height, broad=70, strong=12, share_change=1.2):
    return {
        "sector_name": sector,
        "net_inflow_rank": rank,
        "net_inflow_amount": amount,
        "limit_up_count": limit_up,
        "high_anchor_height": height,
        "broad_rally_pct": broad,
        "strong_gain_count": strong,
        "turnover_share_change": share_change,
    }


def test_overtake_window_opens_when_rivals_slow_and_primary_holds():
    attack = build_mainline_attack_evidence_summary(
        sector_evidence_rows=[
            _row("半导体", rank=1, amount=45, limit_up=8, height=4),
            _row("机器人", rank=8, amount=-6, limit_up=1, height=1, broad=35, strong=2, share_change=-1.4),
        ]
    )
    result = build_overtake_window_summary(
        mainline_attack_evidence_summary=attack,
        mainline_capacity_regime_summary={"primary_line": "半导体", "mainline_regime": "单主线聚焦"},
        current_mainline_history_record={"primary_mainline": "半导体", "secondary_mainline": "机器人"},
    )

    assert result["window_state"] == "open"
    assert result["speed_gap"] == "失速差拉开"
    assert result["action"] == "只在半导体核心里找参与资格"


def test_overtake_window_waits_when_old_line_has_not_retreated():
    attack = build_mainline_attack_evidence_summary(
        sector_evidence_rows=[
            _row("半导体", rank=1, amount=45, limit_up=8, height=4),
            _row("机器人", rank=2, amount=28, limit_up=5, height=3, broad=68, strong=10, share_change=0.8),
        ]
    )
    result = build_overtake_window_summary(
        mainline_attack_evidence_summary=attack,
        mainline_capacity_regime_summary={"primary_line": "半导体", "mainline_regime": "双主线竞争"},
        current_mainline_history_record={"primary_mainline": "半导体", "secondary_mainline": "机器人"},
    )

    assert result["window_state"] == "confirm_next"
    assert result["speed_gap"] == "未拉开"
    assert result["action"] == "等竞价、开盘承接、回封或60分钟确认"


def test_overtake_window_observes_chaotic_rotation():
    attack = build_mainline_attack_evidence_summary(
        sector_evidence_rows=[
            _row("半导体", rank=4, amount=12, limit_up=2, height=1, broad=45, strong=4, share_change=0.2),
            _row("机器人", rank=5, amount=10, limit_up=2, height=1, broad=42, strong=4, share_change=0.1),
            _row("消费电子", rank=6, amount=9, limit_up=1, height=2, broad=40, strong=3, share_change=0.0),
        ]
    )
    result = build_overtake_window_summary(mainline_attack_evidence_summary=attack)

    assert result["window_state"] == "observe"
    assert result["action"] == "仅观察，不给新增参与资格"


def test_overtake_window_stands_down_when_everyone_slows():
    attack = build_mainline_attack_evidence_summary(
        sector_evidence_rows=[
            _row("半导体", rank=9, amount=-4, limit_up=0, height=1, broad=20, strong=1, share_change=-1.2),
            _row("机器人", rank=10, amount=-6, limit_up=0, height=1, broad=18, strong=1, share_change=-1.5),
        ]
    )
    result = build_overtake_window_summary(
        mainline_attack_evidence_summary=attack,
        current_mainline_history_record={"primary_mainline": "半导体", "secondary_mainline": "机器人"},
    )

    assert result["window_state"] == "no_trade"
    assert result["action"] == "不参与，先防风险"
```

- [ ] **Step 2: Run runtime tests and verify they fail for missing `build_overtake_window_summary`**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_runtime
```

Expected: FAIL or ERROR because `build_overtake_window_summary` is not defined/exported.

- [ ] **Step 3: Implement minimal runtime builder**

Add a public function that returns this stable shape:

```python
{
    "window_state": state,
    "primary_line": primary_line,
    "rival_slowdown": rival_slowdown_text,
    "own_stability": own_stability_text,
    "speed_gap": speed_gap_text,
    "action": action_text,
    "evidence_labels": evidence_labels,
    "evidence_gaps": evidence_gaps,
}
```

The rules are:
- `open`: confirmed attack, own fund and strength labels both exist, and at least one rival/secondary/background row has weak evidence or negative flow/share.
- `confirm_next`: confirmed attack and own side holds, but competing line still has enough evidence to require next-day confirmation.
- `observe`: chaotic rotation or candidate attack with no confirmed primary line.
- `no_trade`: no confirmed primary and weak/negative rows dominate, or confirmed primary is missing own stability.

- [ ] **Step 4: Inject summary into `build_mainline_turnover_summary(...)`**

Add `overtake_window_summary` near `mainline_attack_evidence_summary` and use the already-built capacity summary and current record.

- [ ] **Step 5: Run runtime tests and verify they pass**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_runtime
```

Expected: all tests in the file pass.

## Task 2: Resolver And Table Rendering

**Files:**
- Modify: `tests/test_mainline_turnover_summary_support.py`
- Modify: `tests/test_market_research_renderer.py` or existing node test file
- Modify: `scripts/report/mainline_turnover_summary_support.py`
- Modify: `scripts/report/market_research_snapshot_nodes.py`

- [ ] **Step 1: Write failing resolver tests**

```python
from report.mainline_turnover_summary_support import (
    resolve_overtake_window_rows,
    resolve_overtake_window_summary,
)


def test_resolve_overtake_window_summary_from_turnover_summary():
    context = {
        "mainline_turnover_summary": {
            "overtake_window_summary": {
                "window_state": "open",
                "primary_line": "半导体",
                "rival_slowdown": "旧主线承接转弱",
                "own_stability": "半导体资金扩散，核心承接稳定",
                "speed_gap": "失速差拉开",
                "action": "只在半导体核心里找参与资格",
            }
        }
    }

    result = resolve_overtake_window_summary(context)

    assert result["window_state"] == "open"
    assert result["action"] == "只在半导体核心里找参与资格"


def test_resolve_overtake_window_rows_returns_front_table_row():
    rows = resolve_overtake_window_rows(
        {
            "overtake_window_summary": {
                "window_state": "observe",
                "rival_slowdown": "多方向都有局部热度",
                "own_stability": "当前方向强度不足",
                "speed_gap": "未拉开",
                "action": "仅观察，不给新增参与资格",
            }
        }
    )

    assert rows == [
        {
            "rival_slowdown": "多方向都有局部热度",
            "own_stability": "当前方向强度不足",
            "speed_gap": "未拉开",
            "action": "仅观察，不给新增参与资格",
        }
    ]
```

- [ ] **Step 2: Write failing renderer test**

Use the existing node function directly:

```python
from report.market_research_snapshot_nodes import build_market_research_snapshot_mainline_capacity_regime_node


def test_mainline_capacity_node_renders_overtake_window_table():
    node = build_market_research_snapshot_mainline_capacity_regime_node(
        {
            "mainline_capacity_regime_summary": {
                "mainline_capacity": "单线容量",
                "mainline_regime": "单主线聚焦",
                "primary_line": "半导体",
                "other_lines": "机器人",
                "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中",
                "sector_relationship_state": "单主线聚焦",
                "mainline_process": "启动",
                "tomorrow_action": "只围绕半导体做减法",
            },
            "overtake_window_summary": {
                "window_state": "open",
                "rival_slowdown": "旧主线承接转弱，竞争线冲高回落",
                "own_stability": "半导体资金扩散，核心承接稳定",
                "speed_gap": "失速差拉开",
                "action": "只在半导体核心里找参与资格",
            },
        }
    )

    text = "\n".join(node["lines"])
    assert "#### 超车窗口判断" in text
    assert "| 对手失速 | 我方稳住 | 失速差 | 明日动作 |" in text
    assert "| 旧主线承接转弱，竞争线冲高回落 | 半导体资金扩散，核心承接稳定 | 失速差拉开 | 只在半导体核心里找参与资格 |" in text
```

- [ ] **Step 3: Run resolver and renderer tests and verify they fail**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_support tests.test_market_research_renderer
```

Expected: FAIL or ERROR because resolver/table functions do not exist or table is not rendered.

- [ ] **Step 4: Implement resolver helpers**

Add `resolve_overtake_window_summary(context=None)` and `resolve_overtake_window_rows(context=None)` to `scripts/report/mainline_turnover_summary_support.py`. They should prefer top-level `overtake_window_summary`, then `mainline_turnover_summary.overtake_window_summary`, and return one normalized row when there is summary data.

- [ ] **Step 5: Implement renderer table**

Import `resolve_overtake_window_rows`, add `_build_overtake_window_table_lines(context)`, and append it after `_build_mainline_attack_evidence_table_lines(context)`.

- [ ] **Step 6: Run resolver and renderer tests and verify they pass**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_support tests.test_market_research_renderer
```

Expected: all tests in the selected files pass.

## Task 3: Focused Verification

**Files:**
- No new files unless a test file already lacks the target coverage location.

- [ ] **Step 1: Run touched test files**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_runtime tests.test_mainline_turnover_summary_support tests.test_market_research_renderer
```

Expected: all selected tests pass.

- [ ] **Step 2: Scan user-visible wording for banned terms in touched docs and code**

Run:

```bash
rg -n "硬门[禁]|门[禁]|g[ae]te|h[a]rd g[ae]te|状[态]机|状[态]机词汇|买入动[作]|直接买[入]" docs/trellis/specs/2026-05-25-overtake-window-design.md docs/trellis/plans/2026-05-25-overtake-window.md scripts/domains/market_state/mainline_turnover_summary_runtime.py scripts/report/mainline_turnover_summary_support.py scripts/report/market_research_snapshot_nodes.py tests/test_mainline_turnover_summary_runtime.py tests/test_mainline_turnover_summary_support.py tests/test_market_research_renderer.py
```

Expected: no output.

- [ ] **Step 3: Review diff for unrelated edits**

Run:

```bash
git diff -- docs/trellis/plans/2026-05-25-overtake-window.md scripts/domains/market_state/mainline_turnover_summary_runtime.py scripts/report/mainline_turnover_summary_support.py scripts/report/market_research_snapshot_nodes.py tests/test_mainline_turnover_summary_runtime.py tests/test_mainline_turnover_summary_support.py tests/test_market_research_renderer.py
```

Expected: diff only contains the overtake-window plan, runtime summary, resolver, renderer, and tests.
