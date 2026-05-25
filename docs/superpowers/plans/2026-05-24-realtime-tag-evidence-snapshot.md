# Realtime Tag Evidence Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared realtime tag evidence snapshot so daily-report mainline, sector flow, DeepSeek context, and candidate wording consume the same industry/concept/tag interpretation.

**Architecture:** Add a pure knowledge-layer snapshot builder that reuses the existing sector narrative alias rules, then thread its output into market activity analysis and mainline attack evidence. Keep this first slice in-memory only; SQLite history stays out of this implementation.

**Tech Stack:** Python 3.14, unittest, existing `scripts/knowledge`, `scripts/domains/market_activity`, `scripts/domains/market_state`, and `scripts/domains/market_activity/sector_chain_runtime` modules.

---

## File Structure

- Create `scripts/knowledge/realtime_tag_evidence_snapshot.py`: builds normalized tag groups from existing daily-report data.
- Create `tests/test_realtime_tag_evidence_snapshot.py`: covers electronic-chain, conservative component labels, consumer electronics, AI compute multi-branch, and contradiction text.
- Modify `scripts/domains/market_activity/infer.py`: builds and exports `realtime_tag_evidence_snapshot`, and uses it for sector standardization when available.
- Modify `tests/test_market_activity_infer.py`: verifies the snapshot is exported and electronic labels reconcile consistently.
- Modify `scripts/domains/market_state/mainline_turnover_summary_runtime.py`: lets attack evidence rows prefer snapshot adoption names and keeps surface names visible.
- Modify `tests/test_mainline_turnover_summary_runtime.py`: verifies a `元器件 + PCB + 国产芯片替代` evidence set confirms the adopted branch instead of raw surface label.
- Modify `scripts/domains/market_activity/sector_chain_runtime.py`: adds a compact tag snapshot context for LLM sector relationship analysis.
- Modify `tests/test_market_activity_sector_chain_runtime.py`: verifies remote context receives the snapshot summary and local fallback still works.
- Modify `docs/superpowers/plans/2026-05-24-realtime-tag-evidence-snapshot.md`: this plan only.

## Task 1: Build Realtime Tag Evidence Snapshot

**Files:**
- Create: `scripts/knowledge/realtime_tag_evidence_snapshot.py`
- Test: `tests/test_realtime_tag_evidence_snapshot.py`

- [ ] **Step 1: Write failing tests for snapshot behavior**

Add tests that call `build_realtime_tag_evidence_snapshot(data)` with small in-memory data:

```python
from knowledge.realtime_tag_evidence_snapshot import build_realtime_tag_evidence_snapshot

result = build_realtime_tag_evidence_snapshot({
    "sector_fund_flow": {"inflow": [{"name": "元器件", "zljlr": 42.0}]},
    "concept_fund_flow": {"inflow": [{"name": "PCB", "zljlr": 21.0}, {"name": "国产芯片替代", "zljlr": 18.0}]},
    "hot_rank_top30": [{"name": "样本A", "concepts": ["芯片", "PCB"]}],
    "xueqiu_hot_stock_arguments": [{"stock_name": "样本A", "argument": "国产芯片替代和PCB订单预期"}],
})

self.assertEqual(result["groups"][0]["采用名称"], "国产芯片替代")
self.assertEqual(result["groups"][0]["大方向"], "泛半导体/硬科技电子")
self.assertIn("元器件", result["groups"][0]["表层行业名"])
```

- [ ] **Step 2: Run test and verify missing module failure**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_realtime_tag_evidence_snapshot -v
```

Expected: FAIL because `knowledge.realtime_tag_evidence_snapshot` does not exist.

- [ ] **Step 3: Implement minimal snapshot builder**

Create focused helpers:

```python
def build_realtime_tag_evidence_snapshot(data):
    ...
```

The output must include `groups`, `adopted_labels`, and `summary_text`.

- [ ] **Step 4: Run snapshot tests until green**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_realtime_tag_evidence_snapshot tests.test_sector_narrative_alias -v
```

Expected: PASS.

## Task 2: Export Snapshot From Market Activity

**Files:**
- Modify: `scripts/domains/market_activity/infer.py`
- Test: `tests/test_market_activity_infer.py`

- [ ] **Step 1: Write failing market activity test**

Add a test that calls `build_market_activity_sector_analysis_bundle(...)` and asserts:

```python
snapshot = result["results"]["realtime_tag_evidence_snapshot"]
self.assertEqual(snapshot["groups"][0]["采用名称"], "国产芯片替代")
self.assertIn("元器件", snapshot["groups"][0]["表层行业名"])
self.assertIn("国产芯片替代", result["results"]["sector_ai_analysis"]["standard_sectors"])
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_infer.MarketActivityInferTest.test_build_market_activity_sector_analysis_bundle_exports_realtime_tag_snapshot -v
```

Expected: FAIL because the result does not export `realtime_tag_evidence_snapshot`.

- [ ] **Step 3: Thread snapshot into market activity analysis**

Import `build_realtime_tag_evidence_snapshot`, build it inside `analyze_sectors_comprehensive`, and merge its `adopted_labels` into `mapping`/`standard_sectors` conservatively.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_infer tests.test_realtime_tag_evidence_snapshot -v
```

Expected: PASS.

## Task 3: Use Snapshot In Mainline Evidence And LLM Context

**Files:**
- Modify: `scripts/domains/market_state/mainline_turnover_summary_runtime.py`
- Modify: `scripts/domains/market_activity/sector_chain_runtime.py`
- Test: `tests/test_mainline_turnover_summary_runtime.py`
- Test: `tests/test_market_activity_sector_chain_runtime.py`

- [ ] **Step 1: Write failing mainline test**

Add a test that passes sector evidence rows for `元器件`, `PCB`, and `国产芯片替代`, plus `realtime_tag_evidence_snapshot`, then asserts `current_mainline == "国产芯片替代"` and surface names remain visible in evidence rows.

- [ ] **Step 2: Write failing LLM context test**

Add a test that enables remote sector LLM with a fake client and asserts `context_info` contains `实时tag证据快照` and `采用名称：国产芯片替代`.

- [ ] **Step 3: Run tests and verify expected failures**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_runtime tests.test_market_activity_sector_chain_runtime -v
```

Expected: FAIL for the new assertions.

- [ ] **Step 4: Implement minimal integration**

Add optional parameters where needed:

```python
build_mainline_attack_evidence_summary(..., realtime_tag_evidence_snapshot=None)
build_mainline_turnover_summary(..., realtime_tag_evidence_snapshot=None)
ai_analyze_sector_relationships(..., tag_evidence_snapshot=None)
```

Use snapshot adopted names only when evidence rows match surface names or branches from the same group.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_mainline_turnover_summary_runtime tests.test_market_activity_sector_chain_runtime tests.test_market_activity_infer tests.test_realtime_tag_evidence_snapshot -v
```

Expected: PASS.

## Task 4: Final Verification

**Files:**
- All modified files above.

- [ ] **Step 1: Run full relevant regression set**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_realtime_tag_evidence_snapshot tests.test_sector_narrative_alias tests.test_market_activity_infer tests.test_market_activity_sector_chain_runtime tests.test_mainline_turnover_summary_runtime tests.test_report_runtime -v
```

Expected: PASS.

- [ ] **Step 2: Check user-visible terminology**

Run:

```bash
.generated/venv-py314/bin/python3.14 - <<'PY'
from pathlib import Path
terms = [
    "\u786c\u95e8\u7981",
    "\u95e8\u7981",
    "\u72b6\u6001\u673a",
    chr(103) + chr(97) + chr(116) + chr(101),
]
paths = [
    Path("scripts/knowledge/realtime_tag_evidence_snapshot.py"),
    Path("tests/test_realtime_tag_evidence_snapshot.py"),
    Path("docs/superpowers/plans/2026-05-24-realtime-tag-evidence-snapshot.md"),
]
hits = []
for path in paths:
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    hits.extend(f"{path}: {term}" for term in terms if term in text)
if hits:
    raise SystemExit("\n".join(hits))
PY
```

Expected: no matches.

- [ ] **Step 3: Review diff**

Run:

```bash
git diff -- scripts/knowledge/realtime_tag_evidence_snapshot.py scripts/domains/market_activity/infer.py scripts/domains/market_state/mainline_turnover_summary_runtime.py scripts/domains/market_activity/sector_chain_runtime.py tests/test_realtime_tag_evidence_snapshot.py tests/test_market_activity_infer.py tests/test_mainline_turnover_summary_runtime.py tests/test_market_activity_sector_chain_runtime.py docs/superpowers/plans/2026-05-24-realtime-tag-evidence-snapshot.md
```

Expected: diff only contains realtime tag evidence snapshot slice.
