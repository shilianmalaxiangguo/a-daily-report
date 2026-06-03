# New Stock Node Reference Slice Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing new-stock request, scoring, candidate merge, report, and audit path into the first reusable node-reference slice for the daily-report node contract.

**Architecture:** Keep existing business functions as compatibility wrappers, then add a thin node registry/runtime around them. The slice proves the contract by supporting selected-node execution, structured exports/diagnostics, report visibility, and an audit check that can explain both upgraded and research-only cases.

**Tech Stack:** Python 3.14, `unittest`, existing `scripts/` package layout, existing report appendix renderer, existing report acceptance audit.

---

## Scope

### In Scope

- Node keys:
  - `input.new_stock_calendar.request`
  - `selection.new_stock_narrative.score`
  - `watch_candidates.new_stock_upgrade.merge`
  - `report.new_stock_research.render`
  - `audit.new_stock_replay.check`
- Existing wrappers preserved:
  - `collect_new_stock_calendar_request_bundle(...)`
  - `build_new_stock_research_pool(...)`
  - `build_watch_candidate_pool_bundle(...)`
  - execution appendix rendering through `render_execution_appendix(...)`
- Report or artifact surface:
  - compact appendix row for research pool, upgrades, and absence reason
  - audit helper that validates the report text contains either upgrade proof or absence proof
- Replay date:
  - `2026-05-06`, because existing history already proved the new-stock request/scoring path could run while visible report coverage was incomplete.

### Out of Scope

- No buy/sell semantic changes.
- No scoring formula changes.
- No broad report rewrite.
- No unrelated data source changes.
- No full replacement of `scripts/daily_report_entry_demo.py`.
- No visual workflow editor.

### Done Definition

- Focused node tests cover selected execution.
- Runtime test proves only chosen new-stock nodes execute.
- Wrapper compatibility tests still pass.
- Report test proves the new-stock appendix surface renders upgrade and research-only reasons.
- Audit test proves the report text has a new-stock proof row or a clear absence row.
- Existing new-stock request, scoring, watch-candidate, appendix, and audit tests pass.

## File Structure

- Create: `scripts/domains/new_stock_reference/__init__.py`
  - Package marker for the reference node slice.
- Create: `scripts/domains/new_stock_reference/node_registry.py`
  - Defines the node builders and `enabled_node_keys` filtering.
- Create: `scripts/domains/new_stock_reference/node_runtime.py`
  - Runs selected nodes, merges context, exports diagnostics and logs.
- Create: `scripts/domains/new_stock_reference/nodes.py`
  - Thin node adapters around existing request, scoring, candidate merge, report, and audit helpers.
- Create: `tests/test_new_stock_reference_node_runtime.py`
  - Proves selected-node execution, exports, and diagnostics.
- Modify: `scripts/report/appendix_renderer.py`
  - Improve the existing `new_stock_cycle_review` node so it renders a compact absence reason when research rows exist but no upgrade appears.
- Modify: `tests/test_use_execution_appendix_tail.py`
  - Add assertion that research-only rows still reach the report surface.
- Modify: `scripts/report/report_acceptance_audit.py`
  - Add a small audit helper for new-stock report visibility.
- Modify: `tests/test_report_acceptance_audit.py`
  - Add success and failure cases for the new-stock visibility helper.

## Task 1: Add Reference Node Runtime Skeleton

**Files:**
- Create: `scripts/domains/new_stock_reference/__init__.py`
- Create: `scripts/domains/new_stock_reference/node_registry.py`
- Create: `scripts/domains/new_stock_reference/node_runtime.py`
- Create: `scripts/domains/new_stock_reference/nodes.py`
- Test: `tests/test_new_stock_reference_node_runtime.py`

- [ ] **Step 1: Write the failing selected-runtime test**

Add `tests/test_new_stock_reference_node_runtime.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.new_stock_reference.node_registry import build_new_stock_reference_node_specs
from domains.new_stock_reference.node_runtime import run_new_stock_reference_nodes


class NewStockReferenceNodeRuntimeTest(unittest.TestCase):
    def test_runtime_can_execute_only_selected_score_node(self):
        node_specs = build_new_stock_reference_node_specs(enabled_node_keys=["score"])
        context = {
            "target_date": "2026-04-29",
            "new_stock_calendar": [
                {
                    "code": "301608",
                    "name": "N理奇智能",
                    "listing_date": "2026-04-30",
                    "issue_price": 20.0,
                    "fundraising_yi": 2.944,
                    "source": "sina_new_stock_calendar",
                    "source_status": "success",
                }
            ],
            "new_stock_context": {
                "mainline_name": "电池",
                "potential_mainline": ["锂电池", "新能源"],
                "new_stock_money_making_effect": "strong",
                "sector_resonance": {"status": "strong"},
                "new_stock_profiles": {
                    "301608": {
                        "sector": "电池",
                        "concept_tags": ["锂电池", "新能源"],
                        "customer_anchors": ["宁德时代", "比亚迪"],
                        "supply_chain_role": "锂电池设备/材料链",
                        "domestic_advantage": "国产制造和成本优势",
                        "new_stock_cycle_state": "扩散",
                        "c_stage_acceptance": "confirmed",
                        "emotion_outlet_status": "market_flag",
                        "new_stock_recognition_status": "emotion_flag",
                    }
                },
            },
        }

        result = run_new_stock_reference_nodes(node_specs, context)

        self.assertEqual([node["node_key"] for node in result["nodes"]], ["score"])
        self.assertIn("new_stock_research_pool", result["context"])
        self.assertIn("new_stock_candidate_upgrades", result["context"])
        self.assertNotIn("new_stock_report_lines", result["context"])
        self.assertEqual(result["diagnostics"]["score"]["research_count"], 1)
        self.assertGreaterEqual(result["diagnostics"]["score"]["upgrade_count"], 1)
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_new_stock_reference_node_runtime.NewStockReferenceNodeRuntimeTest.test_runtime_can_execute_only_selected_score_node -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'domains.new_stock_reference'`.

- [ ] **Step 3: Add package marker**

Create `scripts/domains/new_stock_reference/__init__.py`:

```python
"""Reference node slice for new-stock daily-report workflow."""
```

- [ ] **Step 4: Add node registry**

Create `scripts/domains/new_stock_reference/node_registry.py`:

```python
from domains.new_stock_reference.nodes import (
    build_new_stock_audit_node,
    build_new_stock_candidate_merge_node,
    build_new_stock_report_node,
    build_new_stock_request_node,
    build_new_stock_score_node,
)


NEW_STOCK_REFERENCE_NODE_BUILDERS = {
    "request": build_new_stock_request_node,
    "score": build_new_stock_score_node,
    "merge": build_new_stock_candidate_merge_node,
    "render": build_new_stock_report_node,
    "audit": build_new_stock_audit_node,
}


def build_new_stock_reference_node_specs(builder_map=None, enabled_node_keys=None):
    builder_map = builder_map or NEW_STOCK_REFERENCE_NODE_BUILDERS
    enabled = list(enabled_node_keys or builder_map.keys())
    specs = []
    for node_key in enabled:
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append(
            {
                "node_key": node_key,
                "title": node_key,
                "builder": builder,
            }
        )
    return specs
```

- [ ] **Step 5: Add node runtime**

Create `scripts/domains/new_stock_reference/node_runtime.py`:

```python
def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.new_stock_reference.node_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_new_stock_reference_node_lookup(node_specs):
    lookup = {}
    for index, spec in enumerate(node_specs or []):
        node_key = str(spec.get("node_key", "") or "").strip()
        if not node_key:
            continue
        lookup[node_key] = {
            "node_key": node_key,
            "title": str(spec.get("title", "") or node_key).strip() or node_key,
            "node_no": index,
        }
    return lookup


def run_new_stock_reference_nodes(node_specs, node_context=None, node_lookup=None):
    node_specs = list(node_specs or [])
    node_lookup = node_lookup or build_new_stock_reference_node_lookup(node_specs)
    current_context = dict(node_context or {})
    aggregated_logs = []
    node_outputs = {}
    diagnostics = {}
    report_sections = {}
    artifacts = {}
    executed_nodes = []

    for spec in node_specs:
        node_key = str(spec.get("node_key", "") or "").strip()
        builder = spec.get("builder")
        if not node_key or builder is None:
            continue
        node_meta = dict(node_lookup.get(node_key) or {"node_key": node_key, "title": node_key})
        result = builder(current_context, node_meta, node_lookup) or {}
        exports = dict(result.get("exports") or {})
        current_context.update(exports)
        node_outputs[node_key] = exports
        diagnostics[node_key] = dict(result.get("diagnostics") or {})
        report_sections.update(result.get("report_sections") or {})
        artifacts.update(result.get("artifacts") or {})
        aggregated_logs.extend(result.get("module_logs") or [])
        executed_nodes.append(node_meta)
        _append_log(
            aggregated_logs,
            f"run.{node_key}",
            "success",
            "已执行 new stock reference node",
            node_key=node_key,
            export_keys=sorted(exports.keys()),
        )

    return {
        "context": current_context,
        "node_outputs": node_outputs,
        "diagnostics": diagnostics,
        "report_sections": report_sections,
        "artifacts": artifacts,
        "module_logs": aggregated_logs,
        "node_lookup": node_lookup,
        "nodes": executed_nodes,
    }
```

- [ ] **Step 6: Add score node adapter**

Create `scripts/domains/new_stock_reference/nodes.py`:

```python
from selection.new_stock_narrative_runtime import build_new_stock_research_pool


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.new_stock_reference.nodes",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_new_stock_request_node(context, node_meta=None, node_lookup=None):
    calendar = list((context or {}).get("new_stock_calendar") or [])
    logs = []
    _append_log(
        logs,
        "request.new_stock_calendar",
        "success",
        "已复用新股上市日历",
        calendar_count=len(calendar),
    )
    return {
        "exports": {"new_stock_calendar": calendar},
        "diagnostics": {"calendar_count": len(calendar)},
        "module_logs": logs,
    }


def build_new_stock_score_node(context, node_meta=None, node_lookup=None):
    result = build_new_stock_research_pool(
        (context or {}).get("new_stock_calendar", []),
        target_date=(context or {}).get("target_date", ""),
        context=(context or {}).get("new_stock_context", {}),
    )
    research_pool = list((result or {}).get("new_stock_research_pool") or [])
    upgrades = list((result or {}).get("new_stock_candidate_upgrades") or [])
    logs = []
    _append_log(
        logs,
        "score.new_stock_narrative",
        "success",
        "已完成新股研究池评分",
        research_count=len(research_pool),
        upgrade_count=len(upgrades),
    )
    return {
        "exports": {
            "new_stock_research_pool": research_pool,
            "new_stock_candidate_upgrades": upgrades,
        },
        "diagnostics": {
            "research_count": len(research_pool),
            "upgrade_count": len(upgrades),
        },
        "module_logs": logs,
    }


def build_new_stock_candidate_merge_node(context, node_meta=None, node_lookup=None):
    upgrades = list((context or {}).get("new_stock_candidate_upgrades") or [])
    return {
        "exports": {"new_stock_candidate_upgrades": upgrades},
        "diagnostics": {"upgrade_count": len(upgrades)},
        "module_logs": [],
    }


def build_new_stock_report_node(context, node_meta=None, node_lookup=None):
    research_pool = list((context or {}).get("new_stock_research_pool") or [])
    upgrades = list((context or {}).get("new_stock_candidate_upgrades") or [])
    if upgrades:
        lines = ["有新股研究升级，进入观察。"]
    elif research_pool:
        lines = ["有新股研究池，但今日未形成买入资格。"]
    else:
        lines = ["新股研究池为空，今日不参与。"]
    return {
        "exports": {"new_stock_report_lines": lines},
        "report_sections": {"new_stock_research": lines},
        "diagnostics": {
            "research_count": len(research_pool),
            "upgrade_count": len(upgrades),
        },
        "module_logs": [],
    }


def build_new_stock_audit_node(context, node_meta=None, node_lookup=None):
    lines = list((context or {}).get("new_stock_report_lines") or [])
    passed = bool(lines)
    return {
        "exports": {"new_stock_audit_passed": passed},
        "diagnostics": {"passed": passed, "line_count": len(lines)},
        "module_logs": [],
    }
```

- [ ] **Step 7: Run the focused test and verify it passes**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_new_stock_reference_node_runtime.NewStockReferenceNodeRuntimeTest.test_runtime_can_execute_only_selected_score_node -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add scripts/domains/new_stock_reference tests/test_new_stock_reference_node_runtime.py
git commit -m "feat: add new stock reference node runtime"
```

## Task 2: Add Full Reference Slice Runtime Coverage

**Files:**
- Modify: `tests/test_new_stock_reference_node_runtime.py`
- Modify: `scripts/domains/new_stock_reference/nodes.py`

- [ ] **Step 1: Add full-slice test**

Append this test to `NewStockReferenceNodeRuntimeTest`:

```python
    def test_full_reference_slice_exports_report_and_audit(self):
        node_specs = build_new_stock_reference_node_specs()
        context = {
            "target_date": "2026-04-29",
            "new_stock_calendar": [
                {
                    "code": "301608",
                    "name": "N理奇智能",
                    "listing_date": "2026-04-30",
                    "issue_price": 20.0,
                    "fundraising_yi": 2.944,
                    "source": "sina_new_stock_calendar",
                    "source_status": "success",
                }
            ],
            "new_stock_context": {
                "mainline_name": "电池",
                "new_stock_money_making_effect": "strong",
                "sector_resonance": {"status": "strong"},
                "new_stock_profiles": {
                    "301608": {
                        "sector": "电池",
                        "concept_tags": ["锂电池", "新能源"],
                        "customer_anchors": ["宁德时代", "比亚迪"],
                        "supply_chain_role": "锂电池设备/材料链",
                        "domestic_advantage": "国产制造和成本优势",
                        "new_stock_cycle_state": "扩散",
                        "c_stage_acceptance": "confirmed",
                        "emotion_outlet_status": "market_flag",
                        "new_stock_recognition_status": "emotion_flag",
                    }
                },
            },
        }

        result = run_new_stock_reference_nodes(node_specs, context)

        self.assertEqual(
            [node["node_key"] for node in result["nodes"]],
            ["request", "score", "merge", "render", "audit"],
        )
        self.assertIn("有新股研究升级，进入观察。", result["context"]["new_stock_report_lines"])
        self.assertTrue(result["context"]["new_stock_audit_passed"])
        self.assertEqual(result["diagnostics"]["render"]["upgrade_count"], 1)
        self.assertIn("new_stock_research", result["report_sections"])
```

- [ ] **Step 2: Run the full-slice test**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_new_stock_reference_node_runtime.NewStockReferenceNodeRuntimeTest.test_full_reference_slice_exports_report_and_audit -v
```

Expected: PASS. If it fails because the audit node cannot see `new_stock_report_lines`, update `build_new_stock_report_node()` to export that field exactly as shown in Task 1.

- [ ] **Step 3: Add research-only selected execution test**

Append:

```python
    def test_research_only_slice_explains_absence_reason(self):
        node_specs = build_new_stock_reference_node_specs(enabled_node_keys=["score", "render", "audit"])
        context = {
            "target_date": "2026-04-29",
            "new_stock_calendar": [
                {
                    "code": "301608",
                    "name": "N理奇智能",
                    "listing_date": "2026-04-30",
                    "issue_price": 20.0,
                    "fundraising_yi": 2.944,
                    "source": "sina_new_stock_calendar",
                    "source_status": "success",
                }
            ],
            "new_stock_context": {
                "mainline_name": "电池",
                "new_stock_profiles": {
                    "301608": {
                        "sector": "电池",
                        "concept_tags": ["锂电池"],
                        "customer_anchors": ["宁德时代"],
                    }
                },
            },
        }

        result = run_new_stock_reference_nodes(node_specs, context)

        self.assertEqual(result["diagnostics"]["score"]["research_count"], 1)
        self.assertEqual(result["diagnostics"]["score"]["upgrade_count"], 0)
        self.assertIn("有新股研究池，但今日未形成买入资格。", result["context"]["new_stock_report_lines"])
        self.assertTrue(result["context"]["new_stock_audit_passed"])
```

- [ ] **Step 4: Run all new reference node tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_new_stock_reference_node_runtime -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add scripts/domains/new_stock_reference tests/test_new_stock_reference_node_runtime.py
git commit -m "test: cover new stock reference slice"
```

## Task 3: Improve Report Appendix New-Stock Surface

**Files:**
- Modify: `scripts/report/appendix_renderer.py`
- Modify: `tests/test_use_execution_appendix_tail.py`

- [ ] **Step 1: Add report surface test for research-only rows**

Append to `tests/test_use_execution_appendix_tail.py`:

```python
    def test_execution_appendix_tail_renders_new_stock_absence_reason(self):
        from report.appendix_renderer import render_execution_appendix

        lines = render_execution_appendix(
            {
                "new_stock_research_pool": [
                    {
                        "code": "301608",
                        "name": "理奇智能",
                        "listing_window": "tomorrow_listing",
                        "new_stock_cycle_state": "not_started",
                        "c_stage_acceptance": "insufficient",
                        "emotion_outlet_status": "none",
                        "new_stock_recognition_status": "ordinary_new_stock",
                        "upgrade_eligible": False,
                        "candidate_upgrade_reason": "新股周期证明不足",
                    }
                ],
                "new_stock_candidate_upgrades": [],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录A：新股周期判定", rendered)
        self.assertIn("理奇智能", rendered)
        self.assertIn("今日未形成买入资格", rendered)
        self.assertIn("新股周期证明不足", rendered)
```

- [ ] **Step 2: Run the new report surface test and verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_use_execution_appendix_tail.ExecutionAppendixTailHookTest.test_execution_appendix_tail_renders_new_stock_absence_reason -v
```

Expected: FAIL because the current appendix table does not include the compact absence reason wording.

- [ ] **Step 3: Update appendix renderer**

Modify `_build_new_stock_cycle_review_node()` in `scripts/report/appendix_renderer.py` so the table includes a compact conclusion column. Replace the table header and row construction with:

```python
    _append_table(
        lines,
        "### 附录A：新股周期判定",
        ["标的", "上市窗口", "新股周期", "C阶段承接", "情绪出口", "辨识度", "是否升级", "结论"],
        [
            [
                _stock_label(item),
                item.get("listing_window"),
                item.get("new_stock_cycle_state"),
                item.get("c_stage_acceptance"),
                item.get("emotion_outlet_status"),
                item.get("new_stock_recognition_status"),
                "是" if item.get("upgrade_eligible") else "否",
                "有新股研究升级，进入观察。"
                if item.get("upgrade_eligible")
                else "有新股研究池，但今日未形成买入资格。{}".format(
                    item.get("candidate_upgrade_reason") or ""
                ),
            ]
            for item in research_pool
        ],
    )
```

- [ ] **Step 4: Run report surface test**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_use_execution_appendix_tail.ExecutionAppendixTailHookTest.test_execution_appendix_tail_renders_new_stock_absence_reason -v
```

Expected: PASS.

- [ ] **Step 5: Run appendix and existing new-stock tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_use_execution_appendix_tail tests.test_new_stock_narrative_runtime tests.test_watch_candidates_infer -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add scripts/report/appendix_renderer.py tests/test_use_execution_appendix_tail.py
git commit -m "feat: expose new stock research absence reason"
```

## Task 4: Add New-Stock Report Audit Helper

**Files:**
- Modify: `scripts/report/report_acceptance_audit.py`
- Modify: `tests/test_report_acceptance_audit.py`

- [ ] **Step 1: Add audit tests**

Append to `tests/test_report_acceptance_audit.py`:

```python
class NewStockReportVisibilityAuditTest(unittest.TestCase):
    def test_new_stock_visibility_audit_accepts_upgrade_or_absence_reason(self):
        from report.report_acceptance_audit import audit_new_stock_visibility

        upgrade_report = "### 附录A：新股周期判定\n有新股研究升级，进入观察。"
        absence_report = "### 附录A：新股周期判定\n有新股研究池，但今日未形成买入资格。"

        self.assertTrue(audit_new_stock_visibility(upgrade_report)["passed"])
        self.assertTrue(audit_new_stock_visibility(absence_report)["passed"])

    def test_new_stock_visibility_audit_fails_when_heading_exists_without_reason(self):
        from report.report_acceptance_audit import audit_new_stock_visibility

        report = "### 附录A：新股周期判定\n| 标的 | 是否升级 |\n| 理奇智能 | 否 |"

        result = audit_new_stock_visibility(report)

        self.assertFalse(result["passed"])
        self.assertEqual(result["findings"][0]["code"], "new_stock_visibility_missing")
```

- [ ] **Step 2: Run the audit tests and verify they fail**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit.NewStockReportVisibilityAuditTest -v
```

Expected: FAIL with `ImportError` or `AttributeError` for `audit_new_stock_visibility`.

- [ ] **Step 3: Implement audit helper**

Add this function to `scripts/report/report_acceptance_audit.py` near other small audit helpers:

```python
def audit_new_stock_visibility(markdown_text):
    text = str(markdown_text or "")
    heading = "### 附录A：新股周期判定"
    if heading not in text:
        return {"passed": True, "findings": []}

    proof_markers = (
        "有新股研究升级，进入观察。",
        "有新股研究池，但今日未形成买入资格。",
        "新股研究池为空，今日不参与。",
        "上市日期缺失，不参与。",
    )
    if any(marker in text for marker in proof_markers):
        return {"passed": True, "findings": []}

    return {
        "passed": False,
        "findings": [
            {
                "code": "new_stock_visibility_missing",
                "message": "新股周期判定缺少升级或不参与原因",
            }
        ],
    }
```

- [ ] **Step 4: Run audit tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit.NewStockReportVisibilityAuditTest -v
```

Expected: PASS.

- [ ] **Step 5: Run full audit test module**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit tests.test_report_acceptance_audit_cli -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add scripts/report/report_acceptance_audit.py tests/test_report_acceptance_audit.py
git commit -m "test: audit new stock report visibility"
```

## Task 5: Final Verification And Merge Prep

**Files:**
- Verify: all files changed above.
- Verify: `docs/trellis/specs/2026-05-27-daily-report-node-runtime-contract-design.md`
- Verify: `docs/trellis/plans/2026-05-28-new-stock-node-reference-slice.md`

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_new_stock_reference_node_runtime \
  tests.test_new_stock_calendar_request \
  tests.test_new_stock_narrative_runtime \
  tests.test_watch_candidates_infer \
  tests.test_use_execution_appendix_tail \
  tests.test_report_acceptance_audit \
  tests.test_report_acceptance_audit_cli \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run report-render regression**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_daily_report_render \
  tests.test_report_replay \
  tests.test_report_runtime \
  -v
```

Expected: PASS.

- [ ] **Step 3: Check for forbidden report-contract wording in changed docs and code**

Run:

```bash
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  docs/trellis/specs/2026-05-27-daily-report-node-runtime-contract-design.md
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py \
  docs/trellis/plans/2026-05-28-new-stock-node-reference-slice.md
```

Expected: both commands pass. If an existing file reports unrelated old wording outside the changed lines, note it in the final review and do not broaden the slice.

- [ ] **Step 4: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Inspect branch diff**

Run:

```bash
git status --short --branch
git diff --stat develop...HEAD
```

Expected: branch is clean, diff contains the spec, plan, new-stock reference runtime, tests, appendix renderer, and audit helper only.

- [ ] **Step 6: Commit plan if it is still unstaged**

If this plan file is not committed yet, run:

```bash
git add docs/trellis/plans/2026-05-28-new-stock-node-reference-slice.md
git commit -m "docs: plan new stock node reference slice"
```

Expected: commit succeeds.

- [ ] **Step 7: Merge to develop after implementation is complete**

Only after all tests pass and the branch is clean:

```bash
git switch develop
git merge --no-ff codex/node-runtime-spec
```

Expected: merge succeeds. If the main checkout still has unrelated local changes, do not merge from that dirty checkout; use a clean integration worktree or ask before proceeding.
