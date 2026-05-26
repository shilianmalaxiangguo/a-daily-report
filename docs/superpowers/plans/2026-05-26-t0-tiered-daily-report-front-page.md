# T0 Tiered Daily Report Front Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-screen `明日账户建议` card that reduces the report to one T0 main object and one optional backup, while keeping T1/T2/T3 lists as appendix-level observation context.

**Architecture:** Implement the first slice inside `scripts/report/front_page_v2_renderer.py`, because the current front-page renderer already owns the discipline table, unique target rendering, candidate section, and execution plan. Add small pure helpers that derive a T0 card from the existing snapshot and reuse existing target resolution helpers instead of adding a new subsystem.

**Tech Stack:** Python 3.14, stdlib `unittest`, existing report renderer helpers. All verification commands must use `.generated/venv-py314/bin/python3.14`.

---

## Scope

### In Scope

- Add `明日账户建议` immediately after the report title and before `## 一、交易纪律`.
- Render account-facing rows: `账户约束`, `明日动作`, `T0主对象`, `T0备用`, `新开仓上限`, `今日不看`.
- Cap T0 display to one main object and one optional backup object.
- In 0% or observation mode, keep appendix candidates out of the T0 card and prevent old action wording from appearing in the first-screen T0 card.
- Add a 2026-05-26-style regression test: many appendix candidates exist, but T0 only shows 华天科技 and no backup.
- Add a holdings-priority regression test: when an existing position summary is present, T0 prioritizes old-position handling and moves the selected new object to backup observation.

### Out of Scope

- Do not rewrite candidate generation.
- Do not delete appendix candidates.
- Do not change historical report markdown files.
- Do not add a scoring engine.
- Do not build a standalone tier service.
- Do not normalize every appendix table in this first slice.

### Non-goals

- Do not make the report list every interesting stock on the first screen.
- Do not make T0 produce a new object every day.
- Do not let T1/T2/T3 rows create additional same-day action suggestions.

### Done Definition

- The first screen has a `## 明日账户建议` section before `## 一、交易纪律`.
- T0 main object is at most one label; T0 backup is at most one label or `暂无`.
- For 2026-05-26-style input, T0 says 华天科技 is the only condition-observation object and T0 backup is `暂无`.
- For existing-position input, T0 says old position handling comes first and the selected new object is only backup observation.
- Existing front-page tests still pass with Python 3.14.

## File Structure

- Modify `scripts/report/front_page_v2_renderer.py`
  - Add helper `_account_status_lines(snapshot=None)`.
  - Add helper `_existing_position_summary(snapshot)`.
  - Add helper `_t0_backup_target(snapshot, *, observation_target, position_state)`.
  - Call `_account_status_lines()` from `render_front_page_v2()` immediately after the title.
- Modify `tests/test_front_page_v2_renderer.py`
  - Add a 2026-05-26-style test for T0 capping and section placement.
  - Add a holdings-priority test for old-position-first behavior.

## Data Contract For This Slice

The helper should consume these optional snapshot fields:

```python
{
    "account_profile": {
        "capital_text": "约1w账户",
    },
    "existing_position_summary": {
        "has_position": True,
        "summary": "已有昨日持仓华天科技(002185)，先按持仓预案处理",
    },
    "selected_position_candidate": {
        "name": "华天科技",
        "code": "002185",
        "sector": "半导体",
    },
    "candidate_snapshot": {
        "front_page": {
            "backup_watch": [
                {"label": "步步高(002251)", "sector": "超市连锁"},
                {"label": "大众公用(600635)", "sector": "供气供热"},
            ],
        },
        "extreme_conviction_list": [
            {"name": "步步高", "code": "002251", "sniper_role": "旧主买说法"},
            {"name": "大众公用", "code": "600635", "sniper_role": "旧补位说法"},
        ],
    },
    "position_decision": {
        "signal_grade": "0",
        "target_position_pct": 0,
    },
}
```

Notes:

- `account_profile.capital_text` is optional. Default to `约1w账户`.
- `existing_position_summary` is optional. If missing or `has_position` is false, treat as no old position.
- Existing fields such as `selected_position_candidate`, `unique_action_target`, and `position_decision` remain the primary source for the T0 main object.
- This slice does not require upstream producers to emit T1/T2/T3 yet.

## Task 1: Add T0 Account Card For No-Position 2026-05-26 Sample

**Files:**
- Modify: `tests/test_front_page_v2_renderer.py`
- Modify: `scripts/report/front_page_v2_renderer.py`

- [ ] **Step 1: Write the failing test**

Add this method to `FrontPageV2RendererTest` in `tests/test_front_page_v2_renderer.py` near the other front-page unique-target tests:

```python
    def test_front_page_t0_card_caps_20260526_style_candidates(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                    "candidate_snapshot": {
                        "front_page": {
                            "backup_watch": [
                                {"label": "步步高(002251)", "sector": "超市连锁"},
                                {"label": "大众公用(600635)", "sector": "供气供热"},
                                {"label": "红星发展(600367)", "sector": "化工原料"},
                            ]
                        },
                        "extreme_conviction_list": [
                            {
                                "name": "步步高",
                                "code": "002251",
                                "sector": "超市连锁",
                                "sniper_role": "旧主买说法",
                            },
                            {
                                "name": "大众公用",
                                "code": "600635",
                                "sector": "供气供热",
                                "sniper_role": "旧补位说法",
                            },
                        ],
                    },
                },
            )
        )

        self.assertLess(rendered.index("## 明日账户建议"), rendered.index("## 一、交易纪律"))
        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；无昨日持仓先看T0对象 |", account_section)
        self.assertIn("| 明日动作 | 不新开，只做条件观察 |", account_section)
        self.assertIn("| T0主对象 | 华天科技(002185)：条件观察 |", account_section)
        self.assertIn("| T0备用 | 暂无 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)
        self.assertIn("| 今日不看 | T1/T2/T3只放附录观察，不同时盯多只，不为多个名单分散资金 |", account_section)
        self.assertNotIn("步步高", account_section)
        self.assertNotIn("大众公用", account_section)
        self.assertNotIn("红星发展", account_section)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_t0_card_caps_20260526_style_candidates
```

Expected: FAIL because `## 明日账户建议` does not exist yet.

- [ ] **Step 3: Add helper functions**

In `scripts/report/front_page_v2_renderer.py`, insert these helpers after `_candidate_section_unique_object_label()` and before `_candidate_lines()`:

```python
def _existing_position_summary(snapshot):
    snapshot = snapshot or {}
    summary = snapshot.get("existing_position_summary") or {}
    if not isinstance(summary, dict):
        return {}
    has_position = bool(summary.get("has_position"))
    text = str(summary.get("summary") or "").strip()
    if not has_position and not text:
        return {}
    return {
        "has_position": True,
        "summary": text or "已有昨日持仓，先按持仓预案处理",
    }


def _account_capital_text(snapshot):
    profile = (snapshot or {}).get("account_profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    return str(profile.get("capital_text") or "约1w账户").strip() or "约1w账户"


def _t0_main_target(snapshot, position_state):
    snapshot = snapshot or {}
    position_state = position_state or {}
    if position_state.get("grade") == "0":
        target = _conditional_observation_target(snapshot)
        role = "条件观察"
    else:
        target = _effective_unique_action_target(snapshot)
        role = "参与窗口确认"
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        return target, role
    return {}, ""


def _account_status_lines(snapshot=None):
    snapshot = snapshot or {}
    position_state = _position_state_contract(snapshot)
    holding = _existing_position_summary(snapshot)
    main_target, main_role = _t0_main_target(snapshot, position_state)
    has_main_target = isinstance(main_target, dict) and bool(main_target.get("name") or main_target.get("code"))
    capital_text = _account_capital_text(snapshot)

    if holding:
        account_constraint = f"{capital_text}；已有昨日持仓优先处理"
        tomorrow_action = "先处理旧仓，不为新候选分散资金"
        main_label = holding.get("summary") or "昨日持仓对象：先按持仓预案处理"
        backup_label = f"{_unique_target_label(main_target)}：仅作条件观察" if has_main_target else "暂无"
        new_entry_limit = "0"
    else:
        account_constraint = f"{capital_text}；无昨日持仓先看T0对象"
        if position_state.get("grade") == "0":
            tomorrow_action = "不新开，只做条件观察" if has_main_target else "不参与，只观察"
            new_entry_limit = "0"
        else:
            tomorrow_action = "只看T0对象，条件满足才新开一手"
            new_entry_limit = "1"
        main_label = f"{_unique_target_label(main_target)}：{main_role}" if has_main_target else "暂无"
        backup_label = "暂无"

    return [
        "## 明日账户建议",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 账户约束 | {account_constraint} |",
        f"| 明日动作 | {tomorrow_action} |",
        f"| T0主对象 | {main_label} |",
        f"| T0备用 | {backup_label} |",
        f"| 新开仓上限 | {new_entry_limit} |",
        "| 今日不看 | T1/T2/T3只放附录观察，不同时盯多只，不为多个名单分散资金 |",
        "",
    ]
```

- [ ] **Step 4: Render the T0 card before discipline**

In `render_front_page_v2()`, replace:

```python
    lines = [f"# {target_date} a股市场分析" if target_date else "# a股市场分析", ""]
    lines.extend(_discipline_table(final_gate=final_gate, position_level=position_level, snapshot=snapshot))
```

with:

```python
    lines = [f"# {target_date} a股市场分析" if target_date else "# a股市场分析", ""]
    lines.extend(_account_status_lines(snapshot))
    lines.extend(_discipline_table(final_gate=final_gate, position_level=position_level, snapshot=snapshot))
```

- [ ] **Step 5: Run the focused test**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_t0_card_caps_20260526_style_candidates
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/report/front_page_v2_renderer.py tests/test_front_page_v2_renderer.py
git commit -m "feat: add T0 account suggestion card"
```

## Task 2: Prioritize Existing Positions Over New Candidates

**Files:**
- Modify: `tests/test_front_page_v2_renderer.py`
- Modify: `scripts/report/front_page_v2_renderer.py`

- [ ] **Step 1: Write the failing holdings-priority test**

Add this method to `FrontPageV2RendererTest` near the test from Task 1:

```python
    def test_front_page_t0_card_prioritizes_existing_position(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "已有昨日持仓晶方科技(603005)，先按持仓预案处理",
                    },
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；已有昨日持仓优先处理 |", account_section)
        self.assertIn("| 明日动作 | 先处理旧仓，不为新候选分散资金 |", account_section)
        self.assertIn("| T0主对象 | 已有昨日持仓晶方科技(603005)，先按持仓预案处理 |", account_section)
        self.assertIn("| T0备用 | 华天科技(002185)：仅作条件观察 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)
```

- [ ] **Step 2: Run test to verify it fails or exposes missing behavior**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_t0_card_prioritizes_existing_position
```

Expected before Task 1 implementation: FAIL because no T0 section exists. Expected after Task 1 implementation: PASS if the helper was copied exactly. If it fails, continue with Step 3.

- [ ] **Step 3: Adjust `_existing_position_summary()` if needed**

If Step 2 fails because the helper does not detect existing positions, ensure `_existing_position_summary()` exactly contains:

```python
def _existing_position_summary(snapshot):
    snapshot = snapshot or {}
    summary = snapshot.get("existing_position_summary") or {}
    if not isinstance(summary, dict):
        return {}
    has_position = bool(summary.get("has_position"))
    text = str(summary.get("summary") or "").strip()
    if not has_position and not text:
        return {}
    return {
        "has_position": True,
        "summary": text or "已有昨日持仓，先按持仓预案处理",
    }
```

Ensure `_account_status_lines()` uses:

```python
    if holding:
        account_constraint = f"{capital_text}；已有昨日持仓优先处理"
        tomorrow_action = "先处理旧仓，不为新候选分散资金"
        main_label = holding.get("summary") or "昨日持仓对象：先按持仓预案处理"
        backup_label = f"{_unique_target_label(main_target)}：仅作条件观察" if has_main_target else "暂无"
        new_entry_limit = "0"
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_t0_card_prioritizes_existing_position
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/report/front_page_v2_renderer.py tests/test_front_page_v2_renderer.py
git commit -m "feat: prioritize holdings in T0 account card"
```

## Task 3: Keep Existing Front Page Behavior Passing

**Files:**
- Modify if needed: `tests/test_front_page_v2_renderer.py`
- Modify if needed: `scripts/report/front_page_v2_renderer.py`

- [ ] **Step 1: Run the full front-page renderer test module**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer
```

Expected: PASS.

- [ ] **Step 2: If tests fail because section indexes changed, update tests to slice around the new section**

Only update assertions that assumed `## 一、交易纪律` was immediately after the title. Do not weaken tests that assert action wording.

For example, if a test needs the stock section, keep this existing style:

```python
stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
```

Do not replace exact behavior assertions with broad `assertIn("华天科技", rendered)` checks.

- [ ] **Step 3: If tests fail because old action wording appears in the new T0 card, fix `_account_status_lines()` only**

The T0 card must not copy `sniper_role` from `candidate_snapshot.extreme_conviction_list`. Confirm that `_account_status_lines()` only uses:

```python
main_target, main_role = _t0_main_target(snapshot, position_state)
```

and does not iterate through appendix candidate lists.

- [ ] **Step 4: Re-run the full front-page renderer test module**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer
```

Expected: PASS.

- [ ] **Step 5: Commit if Task 3 required changes**

If Step 2 or Step 3 changed files, run:

```bash
git add scripts/report/front_page_v2_renderer.py tests/test_front_page_v2_renderer.py
git commit -m "test: preserve front page renderer behavior"
```

If no files changed, do not create an empty commit.

## Task 4: Full Verification

**Files:**
- No planned edits.

- [ ] **Step 1: Run focused regression tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_t0_card_caps_20260526_style_candidates \
  tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_t0_card_prioritizes_existing_position
```

Expected: PASS.

- [ ] **Step 2: Run the front-page renderer test module**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer
```

Expected: PASS.

- [ ] **Step 3: Run nearby report renderer tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_front_summary_renderer \
  tests.test_front_summary_builder \
  tests.test_final_conclusion_renderer
```

Expected: PASS.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git diff --stat HEAD
git diff -- scripts/report/front_page_v2_renderer.py tests/test_front_page_v2_renderer.py
```

Expected:

- Only `scripts/report/front_page_v2_renderer.py` and `tests/test_front_page_v2_renderer.py` are changed by this implementation branch.
- The T0 card appears before `## 一、交易纪律`.
- No T0 helper iterates over appendix candidate pools.

## Self-Review

Spec coverage:

- First-screen `明日账户建议`: Task 1.
- T0 capped to 1+1: Task 1 and Task 2.
- Existing holdings before new objects: Task 2.
- 1w account wording: Task 1 and Task 2 via `account_profile.capital_text` default.
- 2026-05-26 regression: Task 1.
- Appendix candidates preserved but not promoted to T0: Task 1 asserts appendix names do not enter the T0 section.

Known remaining work after this plan:

- Full T1/T2/T3 appendix table normalization is intentionally outside this first slice. The first slice creates the homepage account contract and prevents the appendix from controlling T0.

Placeholder scan:

- No `TBD`, `TODO`, or unresolved placeholders are used.
- All commands use `.generated/venv-py314/bin/python3.14`.

Type consistency:

- `existing_position_summary` is a dict with `has_position` and `summary`.
- `account_profile` is a dict with `capital_text`.
- T0 target formatting reuses `_unique_target_label()`.
