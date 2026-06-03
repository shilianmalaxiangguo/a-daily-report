# PK Decision Stage Nodeization Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nodeize `scripts/domains/execution_chain/pk_decision_stage.py` so Step 5 uses a stage-local registry/runtime while preserving report output, exports, and trading semantics.

**Architecture:** Keep `build_pk_decision_stage()` as the compatibility entrypoint and add `build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None)`. Move the current large stage body into ordered nodes under `scripts/domains/execution_chain/pk_decision_nodes/`; keep the already-nodeized report renderers injected through `stage_context`.

**Tech Stack:** Python unittest, existing execution-chain node registry/runtime pattern, existing report PK/action-plan render nodes, replay acceptance audit.

---

## File Structure

- Create `scripts/domains/execution_chain/pk_decision_node_registry.py`: ordered node specs and `enabled_node_keys` filtering.
- Create `scripts/domains/execution_chain/pk_decision_node_runtime.py`: runs node specs, merges lines/exports/logs, returns final context.
- Create `scripts/domains/execution_chain/pk_decision_nodes/__init__.py`: package marker.
- Create `scripts/domains/execution_chain/pk_decision_nodes/score_candidates.py`: executable/waiting candidate scoring and `best_stock` selection.
- Create `scripts/domains/execution_chain/pk_decision_nodes/observation_pool.py`: closed-gate keep-group observation pool and abnormal anchor candidates.
- Create `scripts/domains/execution_chain/pk_decision_nodes/watch_anchor.py`: priority anchor selection and crossline fallback.
- Create `scripts/domains/execution_chain/pk_decision_nodes/probe_position.py`: abnormal probe, special verdict, position decision, selected-candidate annotations.
- Create `scripts/domains/execution_chain/pk_decision_nodes/front_texts.py`: front summary, special probe, philosophy, MVP digest exports.
- Create `scripts/domains/execution_chain/pk_decision_nodes/pk_context.py`: `pending_lines`, `observation_lines`, `conclusion_lines`.
- Create `scripts/domains/execution_chain/pk_decision_nodes/action_plan_context.py`: action rows, observation lines, position lines, schedule lines, alert rows.
- Create `scripts/domains/execution_chain/pk_decision_nodes/render_sections.py`: call injected renderers, preserve line order.
- Create `scripts/domains/execution_chain/pk_decision_nodes/export_stage_state.py`: collect stable stage exports.
- Modify `scripts/domains/execution_chain/pk_decision_stage.py`: import registry/runtime/nodes, add runtime wrapper, thin public stage function.
- Modify `tests/test_pk_decision_stage.py`: keep existing tests and add runtime partial-node coverage.
- Create `tests/test_pk_decision_node_runtime.py`: registry/runtime unit tests.
- Create `tests/test_pk_decision_stage_nodes.py`: focused node contract tests.

---

### Task 1: Add Registry and Runtime

**Files:**
- Create: `scripts/domains/execution_chain/pk_decision_node_registry.py`
- Create: `scripts/domains/execution_chain/pk_decision_node_runtime.py`
- Create: `tests/test_pk_decision_node_runtime.py`

- [ ] **Step 1: Write the failing registry/runtime tests**

Add `tests/test_pk_decision_node_runtime.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.pk_decision_node_registry import build_pk_decision_node_specs
from domains.execution_chain.pk_decision_node_runtime import run_pk_decision_nodes


class PkDecisionNodeRuntimeTest(unittest.TestCase):
    def test_registry_filters_enabled_node_keys_in_default_order(self):
        builders = {
            "score_candidates": lambda context, meta, lookup: {},
            "watch_anchor": lambda context, meta, lookup: {},
            "render_sections": lambda context, meta, lookup: {},
        }

        specs = build_pk_decision_node_specs(builders, enabled_node_keys=["render_sections", "score_candidates"])

        self.assertEqual([spec["node_key"] for spec in specs], ["score_candidates", "render_sections"])

    def test_runtime_aggregates_lines_exports_logs_and_updates_context(self):
        def first(context, meta, lookup):
            return {
                "lines": ["first"],
                "exports": {"value": 1},
                "module_logs": [{"module": "first", "step": "run", "status": "success", "message": "ok", "details": {}}],
            }

        def second(context, meta, lookup):
            return {
                "lines": [f"second:{context['value']}"],
                "exports": {"done": True},
                "module_logs": [],
            }

        result = run_pk_decision_nodes(
            [
                {"node_key": "first", "title": "First", "builder": first},
                {"node_key": "second", "title": "Second", "builder": second},
            ],
            {},
        )

        self.assertEqual(result["lines"], ["first", "second:1"])
        self.assertEqual(result["context"]["value"], 1)
        self.assertEqual(result["context"]["done"], True)
        self.assertEqual([node["node_key"] for node in result["nodes"]], ["first", "second"])
        self.assertTrue(any(log["step"] == "run.first" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "run.second" for log in result["module_logs"]))
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
venv/bin/python -m unittest tests.test_pk_decision_node_runtime -q
```

Expected: import failure for `domains.execution_chain.pk_decision_node_registry`.

- [ ] **Step 3: Implement registry**

Create `scripts/domains/execution_chain/pk_decision_node_registry.py`:

```python
DEFAULT_PK_DECISION_NODE_SPECS = [
    {"node_key": "score_candidates", "title": "候选决策栈"},
    {"node_key": "observation_pool", "title": "观察池"},
    {"node_key": "watch_anchor", "title": "观察锚点"},
    {"node_key": "probe_position", "title": "探针与仓位"},
    {"node_key": "front_texts", "title": "前摘要文本"},
    {"node_key": "pk_context", "title": "PK渲染上下文"},
    {"node_key": "action_plan_context", "title": "操作计划上下文"},
    {"node_key": "render_sections", "title": "渲染"},
    {"node_key": "export_stage_state", "title": "阶段导出"},
]


def build_pk_decision_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_PK_DECISION_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
```

- [ ] **Step 4: Implement runtime**

Create `scripts/domains/execution_chain/pk_decision_node_runtime.py` by mirroring `entry_plan_node_runtime.py`, changing module/log wording:

```python
def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.pk_decision_node_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_pk_decision_node_lookup(node_specs):
    lookup = {}
    for index, spec in enumerate(node_specs or []):
        node_key = str(spec.get("node_key", "") or "").strip()
        if not node_key:
            continue
        title = str(spec.get("title", "") or node_key).strip() or node_key
        lookup[node_key] = {
            "node_key": node_key,
            "title": title,
            "node_no": index,
        }
    return lookup


def run_pk_decision_nodes(node_specs, node_context=None, node_lookup=None):
    node_specs = list(node_specs or [])
    node_lookup = node_lookup or build_pk_decision_node_lookup(node_specs)
    current_context = dict(node_context or {})
    aggregated_lines = []
    aggregated_logs = []
    node_outputs = {}
    executed_nodes = []

    for spec in node_specs:
        node_key = str(spec.get("node_key", "") or "").strip()
        builder = spec.get("builder")
        if not node_key or builder is None:
            continue

        node_meta = dict(node_lookup.get(node_key) or {})
        if not node_meta:
            node_meta = {
                "node_key": node_key,
                "title": str(spec.get("title", "") or node_key).strip() or node_key,
                "node_no": len(executed_nodes),
            }

        try:
            result = builder(current_context, node_meta, node_lookup) or {}
        except Exception as error:
            _append_log(
                aggregated_logs,
                f"run.{node_key}",
                "error",
                "执行 pk decision node 失败",
                node_key=node_key,
                error=str(error),
            )
            raise

        lines = list(result.get("lines") or [])
        exports = dict(result.get("exports") or {})
        module_logs = list(result.get("module_logs") or [])

        aggregated_lines.extend(lines)
        aggregated_logs.extend(module_logs)
        node_outputs[node_key] = exports
        current_context.update(exports)
        executed_nodes.append(node_meta)
        _append_log(
            aggregated_logs,
            f"run.{node_key}",
            "success",
            "已执行 pk decision node",
            node_key=node_key,
            line_count=len(lines),
            export_keys=sorted(exports.keys()),
        )

    return {
        "lines": aggregated_lines,
        "context": current_context,
        "module_logs": aggregated_logs,
        "node_outputs": node_outputs,
        "node_lookup": node_lookup,
        "nodes": executed_nodes,
    }
```

- [ ] **Step 5: Verify tests pass**

Run:

```bash
venv/bin/python -m unittest tests.test_pk_decision_node_runtime -q
```

Expected: both tests pass with unittest reporting `OK`.

- [ ] **Step 6: Commit**

```bash
git add scripts/domains/execution_chain/pk_decision_node_registry.py scripts/domains/execution_chain/pk_decision_node_runtime.py tests/test_pk_decision_node_runtime.py
git commit -m "add pk decision node runtime"
```

---

### Task 2: Add Runtime Wrapper and Empty Node Shells

**Files:**
- Create: `scripts/domains/execution_chain/pk_decision_nodes/__init__.py`
- Create node shell files under `scripts/domains/execution_chain/pk_decision_nodes/`
- Modify: `scripts/domains/execution_chain/pk_decision_stage.py`
- Modify: `tests/test_pk_decision_stage.py`

- [ ] **Step 1: Write failing runtime partial-node test**

In `tests/test_pk_decision_stage.py`, import `build_pk_decision_runtime`:

```python
from domains.execution_chain.pk_decision_stage import (
    build_pk_decision_runtime,
    build_pk_decision_stage,
    format_closed_gate_buy_limit_text,
)
```

Add:

```python
    def test_pk_decision_runtime_can_run_only_render_node_for_diagnostics(self):
        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk-rendered"],
                "render_action_plan_section": lambda context: ["action-rendered"],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        self.assertEqual(result["lines"], ["pk-rendered", "action-rendered", ""])
        self.assertEqual(result["exports"], {})
```

- [ ] **Step 2: Run failing test**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage.PkDecisionStageTest.test_pk_decision_runtime_can_run_only_render_node_for_diagnostics
```

Expected: import failure for `build_pk_decision_runtime`.

- [ ] **Step 3: Add node shells**

Create `scripts/domains/execution_chain/pk_decision_nodes/__init__.py` empty.

Create all node files with this temporary shape, except `render_sections.py`:

```python
def build_pk_decision_<name>_node(context, node_meta=None, node_lookup=None):
    return {"lines": [], "exports": {}, "module_logs": []}
```

Create `render_sections.py`:

```python
def build_pk_decision_render_sections_node(context, node_meta=None, node_lookup=None):
    render_pk_decision_section = context["render_pk_decision_section"]
    render_action_plan_section = context["render_action_plan_section"]
    lines = []
    lines.extend(render_pk_decision_section(context))
    lines.extend(render_action_plan_section(context))
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
```

- [ ] **Step 4: Add runtime wrapper**

Modify `scripts/domains/execution_chain/pk_decision_stage.py` to import the registry/runtime and shell node builders. Add `PK_DECISION_NODE_BUILDERS` and:

```python
def build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None):
    stage_context = stage_context or {}
    stage_meta = stage_meta or {}
    node_context = {
        **stage_context,
        "stage_label": str(stage_meta.get("label", "") or "Step 5").strip() or "Step 5",
        "stage_title": str(stage_meta.get("title", "") or "PK决胜局（期望值模型）").strip() or "PK决胜局（期望值模型）",
    }
    node_specs = build_pk_decision_node_specs(PK_DECISION_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    runtime_result = run_pk_decision_nodes(node_specs, node_context)
    return {
        "lines": runtime_result["lines"],
        "exports": dict(runtime_result.get("context", {}).get("stage_exports", {}) or {}),
        "module_logs": list(runtime_result.get("module_logs") or []),
    }
```

Do not change `build_pk_decision_stage()` yet.

- [ ] **Step 5: Verify focused tests**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage.PkDecisionStageTest.test_pk_decision_runtime_can_run_only_render_node_for_diagnostics tests.test_pk_decision_node_runtime -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/domains/execution_chain/pk_decision_stage.py scripts/domains/execution_chain/pk_decision_nodes tests/test_pk_decision_stage.py
git commit -m "add pk decision runtime wrapper"
```

---

### Task 3: Extract Candidate Scoring Node

**Files:**
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/score_candidates.py`
- Modify: `scripts/domains/execution_chain/pk_decision_stage.py`
- Test: `tests/test_pk_decision_stage.py`

- [ ] **Step 1: Write failing enabled-node test for scoring**

Add to `tests/test_pk_decision_stage.py`:

```python
    def test_pk_decision_runtime_score_candidates_exports_best_stock(self):
        candidate = {"name": "军工一号", "code": "000001"}
        result = build_pk_decision_runtime(
            {
                "target_date": "2026-04-22",
                "run_mode": "replay",
                "final_gate": {"can_new_entry": True},
                "mainline_name": "军工",
                "market_research_snapshot": {"state_machine": {}},
                "executable_stocks": [candidate],
                "waiting_stocks": [],
                "conviction_codes": set(),
                "leader_memory_codes": set(),
                "build_strategy_ev_calibration": lambda target_date, ledger_mode=None: {"source": "ledger"},
                "score_execution_candidate": lambda stock, ev_calibration: {**stock, "score": 90},
                "score_candidate_decision_stack": lambda stock, **kwargs: {**stock, "decision_stack_score": 90},
                "sort_decision_stack_candidates": lambda candidates: list(candidates),
                "sort_watch_anchor_candidates": lambda candidates, **kwargs: list(candidates),
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["score_candidates", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["best_stock"]["code"], "000001")
        self.assertEqual(result["exports"]["trade_gate_open"], True)
```

- [ ] **Step 2: Run failing test**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage.PkDecisionStageTest.test_pk_decision_runtime_score_candidates_exports_best_stock
```

Expected: `KeyError: 'best_stock'` or missing export.

- [ ] **Step 3: Implement `score_candidates`**

Move the exact scoring block from the top of `build_pk_decision_stage()` into `build_pk_decision_score_candidates_node()`. It must export:

```python
{
    "trade_gate_open": trade_gate_open,
    "ev_calibration": ev_calibration,
    "scored_executable_stocks": scored_executable_stocks,
    "scored_waiting_stocks": scored_waiting_stocks,
    "pending_candidates": pending_candidates,
    "pk_candidates": pk_candidates,
    "best_stock": best_stock,
    "runner_up": runner_up,
}
```

Also implement `export_stage_state` enough to expose these keys when only scoring is enabled:

```python
def build_pk_decision_export_stage_state_node(context, node_meta=None, node_lookup=None):
    export_keys = [
        "trade_gate_open",
        "best_stock",
        "runner_up",
        "watch_anchor",
        "watch_anchor_type",
        "abnormal_probe_group",
        "special_probe_verdict",
        "position_decision",
        "front_structure_layer_text",
        "front_follow_action_text",
        "special_probe_text",
        "philosophy_constraint_text",
        "scored_executable_stocks",
        "core_mvp_digest_lines",
        "mvp_focus_summary_lines",
    ]
    stage_exports = {key: context.get(key) for key in export_keys if key in context}
    return {"lines": [], "exports": {"stage_exports": stage_exports}, "module_logs": []}
```

- [ ] **Step 4: Verify focused tests**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage.PkDecisionStageTest.test_pk_decision_runtime_score_candidates_exports_best_stock tests.test_pk_decision_node_runtime -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/domains/execution_chain/pk_decision_nodes/score_candidates.py scripts/domains/execution_chain/pk_decision_nodes/export_stage_state.py scripts/domains/execution_chain/pk_decision_stage.py tests/test_pk_decision_stage.py
git commit -m "extract pk decision candidate scoring node"
```

---

### Task 4: Extract Observation Pool and Watch Anchor Nodes

**Files:**
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/observation_pool.py`
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/watch_anchor.py`
- Modify: `tests/test_pk_decision_stage.py`

- [ ] **Step 1: Add failing crossline fallback test**

Add a focused runtime test that enables `score_candidates`, `observation_pool`, `watch_anchor`, and `export_stage_state`; use `final_gate={"can_new_entry": False}`, empty primary anchors, and `step2_bundle={"crossline_observation_stocks": [{"name": "跨线股", "code": "000009", "tmr_forecast": "只看承接"}]}`. Assert:

```python
self.assertEqual(result["exports"]["watch_anchor"]["code"], "000009")
self.assertEqual(result["exports"]["watch_anchor_type"], "重点观察谁")
```

The test context must provide these helpers:

```python
"safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
"get_trade_permission": lambda *args, **kwargs: {"permission_label": "跨线观察权", "permission_reason": "只观察"},
"fetch_recent_price_bars": lambda *args, **kwargs: [],
"evaluate_live_tradability": lambda *args, **kwargs: {"can_trade": True, "report_day_is_one_word": False},
"analyze_buy_signal": lambda *args, **kwargs: None,
"quant_system_available": False,
"build_waiting_stock_plan": lambda seed, *args, **kwargs: dict(seed),
"derive_watch_anchor_type": lambda candidate, mainline_name="": "重点观察谁",
"derive_watch_anchor_note": lambda candidate, mainline_name="": "先看承接",
"build_abnormal_watch_anchor_candidates": lambda **kwargs: [],
"select_priority_watch_anchor": lambda **kwargs: ({}, ""),
```

- [ ] **Step 2: Run failing test**

Expected: missing `watch_anchor`.

- [ ] **Step 3: Implement nodes**

Move the closed-gate keep-group observation logic and abnormal anchor construction into `observation_pool`. Move priority anchor selection and crossline fallback into `watch_anchor`.

Do not simplify helper calls. Preserve these exact watch-anchor update keys:

```python
"permission_label"
"permission_reason"
"tradability_guard"
"report_day_is_one_word"
"watch_source"
"signal"
"signal_type"
"position_pct"
"entry_price"
"entry_range"
"watch_anchor_note"
```

- [ ] **Step 4: Verify focused and existing tests**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/domains/execution_chain/pk_decision_nodes/observation_pool.py scripts/domains/execution_chain/pk_decision_nodes/watch_anchor.py tests/test_pk_decision_stage.py
git commit -m "extract pk decision observation anchor nodes"
```

---

### Task 5: Extract Probe, Position, and Front Text Nodes

**Files:**
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/probe_position.py`
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/front_texts.py`
- Modify: `tests/test_pk_decision_stage.py`

- [ ] **Step 1: Add failing export stability test**

Extend the existing open-gate test or add a new runtime test enabling:

```python
enabled_node_keys=[
    "score_candidates",
    "watch_anchor",
    "probe_position",
    "front_texts",
    "export_stage_state",
]
```

Assert:

```python
self.assertEqual(result["exports"]["front_structure_layer_text"], "环境打开，只等唯一动作")
self.assertEqual(result["exports"]["core_mvp_digest_lines"], ["core-digest"])
self.assertEqual(result["exports"]["mvp_focus_summary_lines"], ["focus-summary"])
self.assertEqual(result["exports"]["position_decision"]["target_position_pct"], 50)
self.assertEqual(result["exports"]["best_stock"]["position_pct"], 50)
self.assertEqual(result["exports"]["best_stock"]["candidate_feedback_ready"], True)
```

- [ ] **Step 2: Run failing test**

Expected: missing front text or position exports.

- [ ] **Step 3: Implement `probe_position`**

Move the existing abnormal probe group, special probe verdict, position sizing, and selected candidate mutation block. Export:

```python
{
    "abnormal_probe_group": abnormal_probe_group,
    "special_probe_verdict": special_probe_verdict,
    "position_decision": position_decision,
    "selected_position_candidate": selected_position_candidate,
}
```

- [ ] **Step 4: Implement `front_texts`**

Move the existing front text and MVP digest block. Export:

```python
{
    "front_structure_layer_text": front_structure_layer_text,
    "front_follow_action_text": front_follow_action_text,
    "special_probe_text": special_probe_text,
    "philosophy_constraint_text": philosophy_constraint_text,
    "core_mvp_digest_lines": core_mvp_digest_lines,
    "mvp_focus_summary_lines": mvp_focus_summary_lines,
}
```

- [ ] **Step 5: Verify tests**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage tests.test_front_summary_builder tests.test_final_conclusion_renderer -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/domains/execution_chain/pk_decision_nodes/probe_position.py scripts/domains/execution_chain/pk_decision_nodes/front_texts.py tests/test_pk_decision_stage.py
git commit -m "extract pk decision probe and front text nodes"
```

---

### Task 6: Extract PK Context and Action Plan Context Nodes

**Files:**
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/pk_context.py`
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/action_plan_context.py`
- Modify: `tests/test_pk_decision_stage.py`

- [ ] **Step 1: Add failing renderer-captured context test**

Add a runtime test that enables `pk_context`, `action_plan_context`, and `render_sections`, then captures the dictionaries sent to the injected renderers:

```python
    def test_pk_decision_runtime_builds_pk_and_action_plan_contexts_for_renderers(self):
        captured = {}

        def render_pk(context):
            captured["pk"] = dict(context)
            return ["pk"]

        def render_action(context):
            captured["action"] = dict(context)
            return ["action"]

        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": render_pk,
                "render_action_plan_section": render_action,
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["pk_context", "action_plan_context", "render_sections"],
        )

        self.assertEqual(result["lines"], ["pk", "action", ""])
        self.assertIn("conclusion_lines", captured["pk"])
        self.assertIn("action_rows", captured["action"])
        self.assertIn("position_section_lines", captured["action"])
```

- [ ] **Step 2: Prefer behavior-preserving extraction over new logic**

Move the current code that builds:

```python
pending_lines
observation_lines
conclusion_lines
action_rows
observation_priority_lines
backup_observation_lines
position_section_lines
pre_market_lines
opening_lines
first_hour_lines
intraday_lines
closing_lines
alert_rows
```

into the two node files. Do not rewrite wording branches.

- [ ] **Step 3: Export context values**

Each context node returns its built values through `exports`. Do not append report lines here.

- [ ] **Step 4: Verify renderer-focused tests remain green**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage tests.test_pk_decision_node_runtime tests.test_action_plan_renderer tests.test_pk_decision_node_runtime -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/domains/execution_chain/pk_decision_nodes/pk_context.py scripts/domains/execution_chain/pk_decision_nodes/action_plan_context.py tests/test_pk_decision_stage.py
git commit -m "extract pk decision render contexts"
```

---

### Task 7: Wire Render, Export, and Thin Stage Wrapper

**Files:**
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/render_sections.py`
- Modify: `scripts/domains/execution_chain/pk_decision_nodes/export_stage_state.py`
- Modify: `scripts/domains/execution_chain/pk_decision_stage.py`
- Test: `tests/test_pk_decision_stage.py`

- [ ] **Step 1: Add stage wrapper assertion**

In the existing full-stage tests, keep assertions that:

```python
self.assertIn("#### Step 5 - PK决胜局（期望值模型）", rendered)
self.assertIn("#### 明日操作计划", rendered)
self.assertEqual(result["exports"]["best_stock"]["code"], "000001")
self.assertTrue(any(log["module"] == "domains.execution_chain.pk_decision_stage" for log in result["module_logs"]))
```

- [ ] **Step 2: Wire `render_sections`**

Ensure `render_sections` calls injected functions:

```python
pk_context = {
    "decision_stack_order_text": context.get("decision_stack_order_text"),
    "scored_executable_stocks": context.get("scored_executable_stocks", []),
    "pk_candidates": context.get("pk_candidates", []),
    "stage_label": context.get("stage_label", "Step 5"),
    "stage_title": context.get("stage_title", "PK决胜局（期望值模型）"),
    "trade_gate_open": context.get("trade_gate_open", False),
    "position_level": context.get("position_level", ""),
    "pending_lines": context.get("pending_lines", []),
    "observation_lines": context.get("observation_lines", []),
    "conclusion_lines": context.get("conclusion_lines", []),
}
action_context = {
    "section_title": "明日操作计划",
    "action_rows": context.get("action_rows", []),
    "observation_priority_lines": context.get("observation_priority_lines", []),
    "backup_observation_lines": context.get("backup_observation_lines", []),
    "position_section_lines": context.get("position_section_lines", []),
    "pre_market_lines": context.get("pre_market_lines", []),
    "opening_lines": context.get("opening_lines", []),
    "first_hour_lines": context.get("first_hour_lines", []),
    "intraday_lines": context.get("intraday_lines", []),
    "closing_lines": context.get("closing_lines", []),
    "alert_rows": context.get("alert_rows", []),
}
lines.extend(context["render_pk_decision_section"](pk_context))
lines.extend(context["render_action_plan_section"](action_context))
lines.append("")
```

The render payloads must match the original dictionary keys from `pk_decision_stage.py`.

- [ ] **Step 3: Wire `export_stage_state`**

Return `stage_exports` with all compatibility keys listed in the spec.

- [ ] **Step 4: Replace large stage body**

Refactor `build_pk_decision_stage()` to:

```python
def build_pk_decision_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    logs = []
    result = build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=stage_lookup)
    exports = dict(result.get("exports") or {})
    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成PK决策阶段",
        stage_key=(stage_meta or {}).get("stage_key", "pk_decision"),
        trade_gate_open=bool(exports.get("trade_gate_open")),
        has_best_stock=bool(exports.get("best_stock")),
        has_watch_anchor=bool(exports.get("watch_anchor")),
    )
    return {
        "lines": list(result.get("lines") or []),
        "exports": exports,
        "module_logs": list(result.get("module_logs") or []) + logs,
    }
```

- [ ] **Step 5: Verify focused tests**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage tests.test_pk_decision_node_runtime tests.test_action_plan_renderer tests.test_pk_decision_node_runtime -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/domains/execution_chain/pk_decision_stage.py scripts/domains/execution_chain/pk_decision_nodes/render_sections.py scripts/domains/execution_chain/pk_decision_nodes/export_stage_state.py tests/test_pk_decision_stage.py
git commit -m "wire pk decision stage nodes"
```

---

### Task 8: Replay Verification and Diff Hygiene

**Files:**
- No source edits expected unless verification finds a regression.

- [ ] **Step 1: Run focused unit suite**

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage tests.test_pk_decision_node_runtime tests.test_action_plan_renderer tests.test_report_runtime -q
```

Expected: `OK`.

- [ ] **Step 2: Regenerate replay**

```bash
venv/bin/python scripts/daily_report_entry_demo.py 2026-04-24 --replay
```

Expected: report saved to `reports/replay/2026-04-24_A股日报_完整版_replay.md`.

- [ ] **Step 3: Run acceptance audit**

```bash
venv/bin/python scripts/report/report_acceptance_audit.py reports/replay/2026-04-24_A股日报_完整版_replay.md
```

Expected: `report_acceptance_audit: passed`.

- [ ] **Step 4: Run diff hygiene**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended source/test files plus regenerated replay artifacts if the repo tracks them.

- [ ] **Step 5: Commit final verification fixes when verification changes source or tests**

When verification changes source or tests, stage the exact changed files and commit them:

```bash
git status --short
git add scripts/domains/execution_chain/pk_decision_stage.py scripts/domains/execution_chain/pk_decision_nodes tests/test_pk_decision_stage.py tests/test_pk_decision_node_runtime.py
git commit -m "verify pk decision nodeization"
```

When verification does not change source or tests, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan covers runtime/registry, stage wrapper, candidate scoring, observation pool, watch anchor, probe/position, front texts, PK context, action-plan context, render wiring, stable exports, and replay verification.
- Completeness scan: No task uses unresolved fill-ins. Task 6 uses renderer-captured verification rather than debug-only exports.
- Type consistency: Node names match the design spec and registry order. Public API remains `build_pk_decision_stage()` plus new `build_pk_decision_runtime()`.
- Scope check: This plan does not rewrite existing report render nodes and does not change trading logic.
