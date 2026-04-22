# Market State Workflow Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reusable workflow-graph foundation and migrate `build_mainline_exit_analysis()` onto a `market_state` graph-backed runtime without breaking the legacy report contract.

**Architecture:** Introduce a shared `workflow_graph` package with registry, validator, executor, and trace helpers, then add a first graph-driven business domain at `scripts/domains/market_state`. Keep the existing `build_mainline_exit_analysis()` function name as a compatibility wrapper; the implementation should delegate to `run_market_state_analysis()` and consume stable workflow exports.

**Tech Stack:** Python 3, `unittest`, existing dict-based runtime patterns, legacy helper functions already present in `scripts/daily_report_entry_demo.py`

---

## File Map

**Create**

- `scripts/workflow_graph/trace.py`
- `scripts/workflow_graph/registry.py`
- `scripts/workflow_graph/workflow_contract.py`
- `scripts/workflow_graph/node_contract.py`
- `scripts/workflow_graph/run_store.py`
- `scripts/workflow_graph/executor.py`
- `scripts/domains/market_state/contracts.py`
- `scripts/domains/market_state/graph.py`
- `scripts/domains/market_state/registry.py`
- `scripts/domains/market_state/runtime.py`
- `scripts/domains/market_state/trace.py`
- `scripts/domains/market_state/nodes/infer_mainline_candidates.py`
- `scripts/domains/market_state/nodes/infer_environment_signal.py`
- `scripts/domains/market_state/nodes/infer_mainline_continuity.py`
- `scripts/domains/market_state/nodes/infer_risk_pressure.py`
- `scripts/domains/market_state/nodes/infer_sector_competition.py`
- `scripts/domains/market_state/nodes/assemble_exit_analysis.py`
- `tests/test_workflow_graph_executor.py`
- `tests/test_market_state_workflow_graph.py`
- `tests/test_market_state_nodes.py`
- `tests/test_mainline_exit_analysis_graph_wrapper.py`

**Modify**

- `scripts/daily_report_entry_demo.py`
- `docs/superpowers/plans/2026-04-22-entry-modularization-roadmap.md`

## Task 1: Add Workflow Graph Happy-Path Executor

**Files:**

- Create: `tests/test_workflow_graph_executor.py`
- Create: `scripts/workflow_graph/trace.py`
- Create: `scripts/workflow_graph/registry.py`
- Create: `scripts/workflow_graph/executor.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workflow_graph.executor import execute_workflow_graph


class WorkflowGraphExecutorTest(unittest.TestCase):
    def test_execute_workflow_graph_runs_nodes_in_dependency_order_and_merges_state(self):
        workflow = {
            "workflow_key": "demo_v1",
            "nodes": [
                {"key": "start", "kind": "infer"},
                {"key": "double", "kind": "infer"},
            ],
            "edges": [
                {"from": "start", "to": "double"},
            ],
            "exports": ["double_value"],
        }
        call_order = []

        def start_node(ctx):
            call_order.append("start")
            return {
                "value": {"start_value": 3},
                "exports": {"start_value": 3},
                "state_patch": {"start_value": 3},
                "module_logs": [],
                "errors": [],
                "control": {"status": "success"},
            }

        def double_node(ctx):
            call_order.append("double")
            upstream = ctx.get("upstream", {})
            start_value = upstream["start"]["start_value"]
            return {
                "value": {"double_value": start_value * 2},
                "exports": {"double_value": start_value * 2},
                "state_patch": {"double_value": start_value * 2},
                "module_logs": [],
                "errors": [],
                "control": {"status": "success"},
            }

        result = execute_workflow_graph(
            workflow,
            {"start": start_node, "double": double_node},
            {"inputs": {"target_date": "2026-04-22"}},
        )

        self.assertEqual(call_order, ["start", "double"])
        self.assertEqual(result["exports"]["double_value"], 6)
        self.assertEqual(result["state"]["start_value"], 3)
        self.assertEqual(result["state"]["double_value"], 6)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_workflow_graph_executor.WorkflowGraphExecutorTest.test_execute_workflow_graph_runs_nodes_in_dependency_order_and_merges_state -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'workflow_graph'`

- [ ] **Step 3: Write minimal implementation**

`scripts/workflow_graph/trace.py`

```python
def make_workflow_node_log(module, node_key, step, status, message, **details):
    return {
        "module": module,
        "node_key": node_key,
        "step": step,
        "status": status,
        "message": message,
        "details": details,
    }
```

`scripts/workflow_graph/registry.py`

```python
def resolve_workflow_node(registry, node_key):
    if node_key not in (registry or {}):
        raise KeyError(f"workflow node not registered: {node_key}")
    return registry[node_key]
```

`scripts/workflow_graph/executor.py`

```python
from workflow_graph.registry import resolve_workflow_node
from workflow_graph.trace import make_workflow_node_log


def _build_execution_order(workflow):
    nodes = [item["key"] for item in workflow.get("nodes", [])]
    edges = workflow.get("edges", [])
    indegree = {key: 0 for key in nodes}
    children = {key: [] for key in nodes}
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        children[source].append(target)
        indegree[target] += 1
    queue = [key for key in nodes if indegree[key] == 0]
    ordered = []
    while queue:
        node_key = queue.pop(0)
        ordered.append(node_key)
        for child in children[node_key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return ordered


def execute_workflow_graph(workflow, registry, ctx=None):
    ctx = ctx or {}
    inputs = dict(ctx.get("inputs") or {})
    state = dict(ctx.get("state") or {})
    helpers = dict(ctx.get("helpers") or {})
    config = dict(ctx.get("config") or {})
    node_results = {}
    module_logs = []
    errors = []
    edges = workflow.get("edges", [])

    for node_key in _build_execution_order(workflow):
        node_impl = resolve_workflow_node(registry, node_key)
        upstream = {}
        for edge in edges:
            if edge["to"] == node_key:
                upstream_key = edge["from"]
                upstream[upstream_key] = dict(
                    (node_results.get(upstream_key) or {}).get("exports") or {}
                )
        node_ctx = {
            "node": {
                "key": node_key,
                "workflow_key": workflow.get("workflow_key", ""),
                "run_id": ctx.get("run_id", ""),
            },
            "inputs": inputs,
            "state": state,
            "upstream": upstream,
            "helpers": helpers,
            "config": config,
        }
        result = node_impl(node_ctx) or {}
        state.update(result.get("state_patch") or {})
        node_results[node_key] = result
        module_logs.extend(result.get("module_logs") or [])
        errors.extend(result.get("errors") or [])
        module_logs.append(
            make_workflow_node_log(
                "workflow_graph.executor",
                node_key,
                f"run.{node_key}",
                "success",
                "workflow node executed",
                export_keys=sorted((result.get("exports") or {}).keys()),
            )
        )

    exports = {}
    for export_key in workflow.get("exports", []):
        for node_key in reversed(_build_execution_order(workflow)):
            node_exports = (node_results.get(node_key) or {}).get("exports") or {}
            if export_key in node_exports:
                exports[export_key] = node_exports[export_key]
                break

    return {
        "workflow_key": workflow.get("workflow_key", ""),
        "state": state,
        "node_results": node_results,
        "exports": exports,
        "module_logs": module_logs,
        "errors": errors,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_workflow_graph_executor.WorkflowGraphExecutorTest.test_execute_workflow_graph_runs_nodes_in_dependency_order_and_merges_state -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_workflow_graph_executor.py scripts/workflow_graph/trace.py scripts/workflow_graph/registry.py scripts/workflow_graph/executor.py
git commit -m "feat: add workflow graph executor happy path"
```

## Task 2: Add Workflow Validation, Context Helpers, And Control Statuses

**Files:**

- Modify: `tests/test_workflow_graph_executor.py`
- Create: `scripts/workflow_graph/workflow_contract.py`
- Create: `scripts/workflow_graph/node_contract.py`
- Create: `scripts/workflow_graph/run_store.py`
- Modify: `scripts/workflow_graph/executor.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/test_workflow_graph_executor.py`:

```python
    def test_execute_workflow_graph_rejects_cycle(self):
        workflow = {
            "workflow_key": "cycle_v1",
            "nodes": [
                {"key": "a", "kind": "infer"},
                {"key": "b", "kind": "infer"},
            ],
            "edges": [
                {"from": "a", "to": "b"},
                {"from": "b", "to": "a"},
            ],
            "exports": [],
        }

        with self.assertRaises(ValueError):
            execute_workflow_graph(workflow, {"a": lambda ctx: {}, "b": lambda ctx: {}}, {})

    def test_execute_workflow_graph_skips_disabled_nodes_and_records_status(self):
        workflow = {
            "workflow_key": "skip_v1",
            "nodes": [
                {"key": "start", "kind": "infer"},
                {"key": "optional", "kind": "infer", "enabled": False},
            ],
            "edges": [],
            "exports": ["start_value"],
        }

        def start_node(ctx):
            return {
                "value": {"start_value": 1},
                "exports": {"start_value": 1},
                "state_patch": {"start_value": 1},
                "module_logs": [],
                "errors": [],
                "control": {"status": "success"},
            }

        result = execute_workflow_graph(workflow, {"start": start_node}, {})

        self.assertEqual(result["exports"]["start_value"], 1)
        self.assertNotIn("optional", result["node_results"])
        self.assertTrue(
            any(
                log.get("node_key") == "optional" and log.get("status") == "skipped"
                for log in result["module_logs"]
            )
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_workflow_graph_executor -v`

Expected: FAIL with cycle test not raising `ValueError` and skipped-node test missing the `skipped` log

- [ ] **Step 3: Write minimal implementation**

`scripts/workflow_graph/workflow_contract.py`

```python
def validate_workflow_graph(workflow):
    workflow = workflow or {}
    node_keys = [item.get("key", "") for item in workflow.get("nodes", [])]
    if len(node_keys) != len(set(node_keys)):
        raise ValueError("workflow graph contains duplicate node keys")
    for edge in workflow.get("edges", []):
        if edge.get("from") not in node_keys or edge.get("to") not in node_keys:
            raise ValueError("workflow graph edge points to unknown node")


def build_execution_order(workflow):
    validate_workflow_graph(workflow)
    nodes = [item["key"] for item in workflow.get("nodes", [])]
    edges = workflow.get("edges", [])
    indegree = {key: 0 for key in nodes}
    children = {key: [] for key in nodes}
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        children[source].append(target)
        indegree[target] += 1
    queue = [key for key in nodes if indegree[key] == 0]
    ordered = []
    while queue:
        node_key = queue.pop(0)
        ordered.append(node_key)
        for child in children[node_key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(ordered) != len(nodes):
        raise ValueError("workflow graph contains a cycle")
    return ordered
```

`scripts/workflow_graph/node_contract.py`

```python
def build_node_context(node_key, workflow_key, run_id, inputs, state, upstream, helpers, config):
    return {
        "node": {
            "key": node_key,
            "workflow_key": workflow_key,
            "run_id": run_id,
        },
        "inputs": dict(inputs or {}),
        "state": dict(state or {}),
        "upstream": dict(upstream or {}),
        "helpers": dict(helpers or {}),
        "config": dict(config or {}),
    }
```

`scripts/workflow_graph/run_store.py`

```python
def collect_upstream_exports(node_key, edges, node_results):
    upstream = {}
    for edge in edges or []:
        if edge.get("to") != node_key:
            continue
        upstream_key = edge.get("from")
        upstream[upstream_key] = dict(
            (node_results.get(upstream_key) or {}).get("exports") or {}
        )
    return upstream


def merge_state_patch(state, state_patch):
    state = dict(state or {})
    state.update(dict(state_patch or {}))
    return state
```

Replace `scripts/workflow_graph/executor.py` with:

```python
from workflow_graph.node_contract import build_node_context
from workflow_graph.registry import resolve_workflow_node
from workflow_graph.run_store import collect_upstream_exports, merge_state_patch
from workflow_graph.trace import make_workflow_node_log
from workflow_graph.workflow_contract import build_execution_order


def execute_workflow_graph(workflow, registry, ctx=None):
    ctx = ctx or {}
    inputs = dict(ctx.get("inputs") or {})
    state = dict(ctx.get("state") or {})
    helpers = dict(ctx.get("helpers") or {})
    config = dict(ctx.get("config") or {})
    run_id = str(ctx.get("run_id", "") or "")
    node_results = {}
    module_logs = []
    errors = []
    edges = workflow.get("edges", [])
    ordered_nodes = build_execution_order(workflow)
    node_meta_map = {item["key"]: item for item in workflow.get("nodes", [])}

    for node_key in ordered_nodes:
        node_meta = node_meta_map[node_key]
        if node_meta.get("enabled", True) is False:
            module_logs.append(
                make_workflow_node_log(
                    "workflow_graph.executor",
                    node_key,
                    f"run.{node_key}",
                    "skipped",
                    "workflow node disabled",
                    workflow_key=workflow.get("workflow_key", ""),
                )
            )
            continue

        node_impl = resolve_workflow_node(registry, node_key)
        upstream = collect_upstream_exports(node_key, edges, node_results)
        node_ctx = build_node_context(
            node_key,
            workflow.get("workflow_key", ""),
            run_id,
            inputs,
            state,
            upstream,
            helpers,
            config,
        )
        result = node_impl(node_ctx) or {}
        control = dict(result.get("control") or {})
        status = str(control.get("status", "success") or "success")
        state = merge_state_patch(state, result.get("state_patch") or {})
        node_results[node_key] = result
        module_logs.extend(result.get("module_logs") or [])
        errors.extend(result.get("errors") or [])
        module_logs.append(
            make_workflow_node_log(
                "workflow_graph.executor",
                node_key,
                f"run.{node_key}",
                status,
                "workflow node executed",
                workflow_key=workflow.get("workflow_key", ""),
                export_keys=sorted((result.get("exports") or {}).keys()),
            )
        )

    exports = {}
    for export_key in workflow.get("exports", []):
        for node_key in reversed(ordered_nodes):
            node_exports = (node_results.get(node_key) or {}).get("exports") or {}
            if export_key in node_exports:
                exports[export_key] = node_exports[export_key]
                break

    return {
        "workflow_key": workflow.get("workflow_key", ""),
        "state": state,
        "node_results": node_results,
        "exports": exports,
        "module_logs": module_logs,
        "errors": errors,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_workflow_graph_executor -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_workflow_graph_executor.py scripts/workflow_graph/workflow_contract.py scripts/workflow_graph/node_contract.py scripts/workflow_graph/run_store.py scripts/workflow_graph/executor.py
git commit -m "feat: add workflow graph validation and control statuses"
```

## Task 3: Add Market State Graph Shell, Registry, And Runtime Wrapper

**Files:**

- Create: `tests/test_market_state_workflow_graph.py`
- Create: `scripts/domains/market_state/contracts.py`
- Create: `scripts/domains/market_state/graph.py`
- Create: `scripts/domains/market_state/registry.py`
- Create: `scripts/domains/market_state/runtime.py`
- Create: `scripts/domains/market_state/trace.py`
- Create: `scripts/domains/market_state/nodes/infer_mainline_candidates.py`
- Create: `scripts/domains/market_state/nodes/infer_environment_signal.py`
- Create: `scripts/domains/market_state/nodes/infer_mainline_continuity.py`
- Create: `scripts/domains/market_state/nodes/infer_risk_pressure.py`
- Create: `scripts/domains/market_state/nodes/infer_sector_competition.py`
- Create: `scripts/domains/market_state/nodes/assemble_exit_analysis.py`

- [ ] **Step 1: Write the failing tests**

```python
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.contracts import (
    MARKET_STATE_EXPORT_KEYS,
    NODE_ASSEMBLE_EXIT_ANALYSIS,
    NODE_ENVIRONMENT_SIGNAL,
    NODE_MAINLINE_CANDIDATES,
    NODE_MAINLINE_CONTINUITY,
    NODE_RISK_PRESSURE,
    NODE_SECTOR_COMPETITION,
    WORKFLOW_KEY,
)
from domains.market_state.graph import build_market_state_graph
from domains.market_state.runtime import run_market_state_analysis


class MarketStateWorkflowGraphTest(unittest.TestCase):
    def test_build_market_state_graph_declares_expected_nodes_and_exports(self):
        workflow = build_market_state_graph()
        node_keys = [item["key"] for item in workflow["nodes"]]

        self.assertEqual(workflow["workflow_key"], WORKFLOW_KEY)
        self.assertEqual(
            node_keys,
            [
                NODE_MAINLINE_CANDIDATES,
                NODE_ENVIRONMENT_SIGNAL,
                NODE_MAINLINE_CONTINUITY,
                NODE_RISK_PRESSURE,
                NODE_SECTOR_COMPETITION,
                NODE_ASSEMBLE_EXIT_ANALYSIS,
            ],
        )
        self.assertEqual(workflow["exports"], MARKET_STATE_EXPORT_KEYS)

    @patch("domains.market_state.runtime.execute_workflow_graph")
    def test_run_market_state_analysis_delegates_to_graph_executor(self, execute_mock):
        execute_mock.return_value = {
            "workflow_key": WORKFLOW_KEY,
            "exports": {"exit_analysis": {"sector_name": "军工"}},
            "state": {},
            "node_results": {},
            "module_logs": [],
            "errors": [],
        }

        result = run_market_state_analysis({"inputs": {"data": {}}})

        self.assertEqual(result["exports"]["exit_analysis"]["sector_name"], "军工")
        execute_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_market_state_workflow_graph -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'domains.market_state'`

- [ ] **Step 3: Write minimal implementation**

`scripts/domains/market_state/contracts.py`

```python
WORKFLOW_KEY = "market_state_v1"

NODE_MAINLINE_CANDIDATES = "mainline_candidates"
NODE_ENVIRONMENT_SIGNAL = "environment_signal"
NODE_MAINLINE_CONTINUITY = "mainline_continuity"
NODE_RISK_PRESSURE = "risk_pressure"
NODE_SECTOR_COMPETITION = "sector_competition"
NODE_ASSEMBLE_EXIT_ANALYSIS = "assemble_exit_analysis"

MARKET_STATE_EXPORT_KEYS = [
    "environment_signal",
    "mainline_candidates",
    "continuity_snapshot",
    "risk_snapshot",
    "competition_snapshot",
    "exit_analysis",
]


def build_market_state_action_map():
    return {
        "绿灯": "主线健康，可继续做",
        "黄灯": "主升强化，优先做核心",
        "橙灯": "退潮预警，禁止新增",
        "红灯": "退潮确认，尽快退出",
    }


def build_market_state_severity_map():
    return {"绿灯": 0, "黄灯": 1, "橙灯": 2, "红灯": 3}
```

`scripts/domains/market_state/graph.py`

```python
from domains.market_state.contracts import (
    MARKET_STATE_EXPORT_KEYS,
    NODE_ASSEMBLE_EXIT_ANALYSIS,
    NODE_ENVIRONMENT_SIGNAL,
    NODE_MAINLINE_CANDIDATES,
    NODE_MAINLINE_CONTINUITY,
    NODE_RISK_PRESSURE,
    NODE_SECTOR_COMPETITION,
    WORKFLOW_KEY,
)


def build_market_state_graph():
    return {
        "workflow_key": WORKFLOW_KEY,
        "version": "1.0.0",
        "entry_nodes": [NODE_MAINLINE_CANDIDATES],
        "nodes": [
            {"key": NODE_MAINLINE_CANDIDATES, "kind": "infer"},
            {"key": NODE_ENVIRONMENT_SIGNAL, "kind": "infer"},
            {"key": NODE_MAINLINE_CONTINUITY, "kind": "infer"},
            {"key": NODE_RISK_PRESSURE, "kind": "infer"},
            {"key": NODE_SECTOR_COMPETITION, "kind": "infer"},
            {"key": NODE_ASSEMBLE_EXIT_ANALYSIS, "kind": "assemble"},
        ],
        "edges": [
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_ENVIRONMENT_SIGNAL},
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_MAINLINE_CONTINUITY},
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_RISK_PRESSURE},
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_SECTOR_COMPETITION},
            {"from": NODE_ENVIRONMENT_SIGNAL, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
            {"from": NODE_MAINLINE_CONTINUITY, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
            {"from": NODE_RISK_PRESSURE, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
            {"from": NODE_SECTOR_COMPETITION, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
        ],
        "exports": MARKET_STATE_EXPORT_KEYS,
    }
```

`scripts/domains/market_state/trace.py`

```python
from workflow_graph.trace import make_workflow_node_log


def make_market_state_log(node_key, step, status, message, **details):
    return make_workflow_node_log(
        f"domains.market_state.nodes.{node_key}",
        node_key,
        step,
        status,
        message,
        **details,
    )
```

`scripts/domains/market_state/nodes/infer_mainline_candidates.py`

```python
def run(ctx):
    return {
        "value": {},
        "exports": {},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
```

`scripts/domains/market_state/nodes/infer_environment_signal.py`

```python
def run(ctx):
    return {
        "value": {},
        "exports": {},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
```

`scripts/domains/market_state/nodes/infer_mainline_continuity.py`

```python
def run(ctx):
    return {
        "value": {},
        "exports": {},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
```

`scripts/domains/market_state/nodes/infer_risk_pressure.py`

```python
def run(ctx):
    return {
        "value": {},
        "exports": {},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
```

`scripts/domains/market_state/nodes/infer_sector_competition.py`

```python
def run(ctx):
    return {
        "value": {},
        "exports": {},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
```

`scripts/domains/market_state/nodes/assemble_exit_analysis.py`

```python
def run(ctx):
    return {
        "value": {"exit_analysis": {}},
        "exports": {"exit_analysis": {}},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
```

`scripts/domains/market_state/registry.py`

```python
from domains.market_state.contracts import (
    NODE_ASSEMBLE_EXIT_ANALYSIS,
    NODE_ENVIRONMENT_SIGNAL,
    NODE_MAINLINE_CANDIDATES,
    NODE_MAINLINE_CONTINUITY,
    NODE_RISK_PRESSURE,
    NODE_SECTOR_COMPETITION,
)
from domains.market_state.nodes.assemble_exit_analysis import run as run_assemble_exit_analysis
from domains.market_state.nodes.infer_environment_signal import run as run_environment_signal
from domains.market_state.nodes.infer_mainline_candidates import run as run_mainline_candidates
from domains.market_state.nodes.infer_mainline_continuity import run as run_mainline_continuity
from domains.market_state.nodes.infer_risk_pressure import run as run_risk_pressure
from domains.market_state.nodes.infer_sector_competition import run as run_sector_competition


def build_market_state_registry():
    return {
        NODE_MAINLINE_CANDIDATES: run_mainline_candidates,
        NODE_ENVIRONMENT_SIGNAL: run_environment_signal,
        NODE_MAINLINE_CONTINUITY: run_mainline_continuity,
        NODE_RISK_PRESSURE: run_risk_pressure,
        NODE_SECTOR_COMPETITION: run_sector_competition,
        NODE_ASSEMBLE_EXIT_ANALYSIS: run_assemble_exit_analysis,
    }
```

`scripts/domains/market_state/runtime.py`

```python
from domains.market_state.graph import build_market_state_graph
from domains.market_state.registry import build_market_state_registry
from workflow_graph.executor import execute_workflow_graph


def run_market_state_analysis(ctx):
    workflow = build_market_state_graph()
    registry = build_market_state_registry()
    return execute_workflow_graph(workflow, registry, ctx)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_market_state_workflow_graph -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_market_state_workflow_graph.py scripts/domains/market_state
git commit -m "feat: add market state workflow graph shell"
```

## Task 4: Extract Candidate, Environment, And Continuity Nodes

**Files:**

- Create: `tests/test_market_state_nodes.py`
- Modify: `scripts/domains/market_state/nodes/infer_mainline_candidates.py`
- Modify: `scripts/domains/market_state/nodes/infer_environment_signal.py`
- Modify: `scripts/domains/market_state/nodes/infer_mainline_continuity.py`

- [ ] **Step 1: Write the failing tests**

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.contracts import build_market_state_action_map
from domains.market_state.nodes.infer_environment_signal import run as run_environment_signal
from domains.market_state.nodes.infer_mainline_candidates import run as run_mainline_candidates
from domains.market_state.nodes.infer_mainline_continuity import run as run_mainline_continuity


class MarketStateNodesTest(unittest.TestCase):
    def test_infer_mainline_candidates_selects_tracked_sector_and_snapshot(self):
        result = run_mainline_candidates(
            {
                "inputs": {
                    "data": {
                        "sector_fund_flow": {
                            "inflow": [{"name": "军工", "zljlr": 12.5}],
                            "outflow": [{"name": "地产", "zljlr": -8.1}],
                        },
                        "zt_pool_by_sector": {"军工": [{"name": "A"}, {"name": "B"}]},
                        "dt_pool_by_sector": {"军工": []},
                        "tag_distribution": {},
                        "target_date": "2026-04-22",
                    },
                    "market_analysis": {"main_sectors": [{"name": "军工"}]},
                    "enhanced_main_sectors": [],
                },
                "helpers": {
                    "get_sector_hotlist_weight": lambda sector, tags: 7.5,
                    "load_recent_sector_flow_history": lambda target_date, sector, lookback_days=2: [{"inflow": 10.0}],
                    "get_mainline_star_level": lambda inflow, zt_count, dt_count=0, hot_weight=0, inflow_history=None: {
                        "star_level": "⭐⭐⭐⭐",
                        "star_rank": 4,
                        "score_pct": 82.0,
                        "flow_trend": "stable",
                        "trend_label": "主升延续",
                        "component_scores": {"资金": 85.0},
                    },
                    "safe_float": float,
                },
            }
        )

        exports = result["exports"]
        self.assertEqual(exports["tracked_sector"], "军工")
        self.assertEqual(exports["sector_inflow"], 12.5)
        self.assertEqual(exports["sector_zt_count"], 2)
        self.assertEqual(exports["mainline_snapshot"]["star_rank"], 4)

    def test_infer_environment_signal_generates_mainline_review_signal(self):
        result = run_environment_signal(
            {
                "state": {
                    "tracked_sector": "军工",
                    "sector_inflow": 12.5,
                    "sector_outflow": 0,
                    "sector_zt_count": 2,
                    "sector_dt_count": 0,
                    "hot_weight": 7.5,
                    "mainline_snapshot": {
                        "score_pct": 82.0,
                        "flow_trend": "stable",
                        "trend_label": "主升延续",
                    },
                },
                "helpers": {
                    "action_map": build_market_state_action_map(),
                    "score_to_level": lambda score: "绿灯" if score >= 70 else "黄灯",
                },
            }
        )

        signal = result["exports"]["environment_signal"]
        self.assertEqual(signal["layer"], "主线地位复核")
        self.assertEqual(signal["level"], "绿灯")
        self.assertIn("军工", signal["status"])

    def test_infer_mainline_continuity_generates_leader_structure_and_core_signals(self):
        result = run_mainline_continuity(
            {
                "inputs": {
                    "data": {
                        "lhb_net_sell_top10": [],
                        "stock_full_info": {"000001": {"open": 10.0, "high": 10.8, "low": 9.8, "close": 10.5}},
                        "hot_rank_top30": [{"name": "军工一号", "code": "000001"}],
                        "target_date": "2026-04-22",
                    }
                },
                "state": {
                    "tracked_sector": "军工",
                    "sector_zt_count": 6,
                    "sector_dt_count": 0,
                    "hot_weight": 8.0,
                },
                "helpers": {
                    "action_map": build_market_state_action_map(),
                    "get_sector_leader": lambda tracked_sector, dragon_stocks, dt_pool_by_sector: {
                        "name": "军工一号",
                        "code": "000001",
                        "zt_type": "换手板",
                        "lianban": 3,
                        "is_limit_down": False,
                    },
                    "get_sector_core_hot_stock": lambda tracked_sector, hot_rank_top30: {
                        "name": "军工一号",
                        "code": "000001",
                        "hot_rank": 4,
                        "change_pct": 5.2,
                    },
                    "normalize_stock_code": lambda code: code,
                    "calculate_exit_price_lines": lambda price_anchor_stock, stock_full_info: {"anchor_name": "军工一号"},
                    "fetch_recent_price_bars": lambda code, target_date, lookback_days=13: [{"low": 9.5}],
                    "compute_stop_loss_mainline_anchor": lambda recent_bars: (9.5, "2026-04-18", "最近前低"),
                    "safe_float": float,
                    "clamp": lambda value, lower, upper: max(lower, min(value, upper)),
                    "level_to_score": lambda level: {"绿灯": 85.0, "黄灯": 65.0, "橙灯": 35.0, "红灯": 10.0}[level],
                },
            }
        )

        exports = result["exports"]
        self.assertEqual(exports["leader_signal"]["level"], "绿灯")
        self.assertEqual(exports["structure_signal"]["level"], "黄灯")
        self.assertEqual(exports["core_signal"]["level"], "绿灯")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_market_state_nodes -v`

Expected: FAIL because the placeholder nodes return empty exports

- [ ] **Step 3: Write minimal implementation**

Replace `scripts/domains/market_state/nodes/infer_mainline_candidates.py` with:

```python
from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    helpers = ctx.get("helpers") or {}
    data = inputs.get("data") or {}
    market_analysis = inputs.get("market_analysis") or {}
    enhanced_main_sectors = list(inputs.get("enhanced_main_sectors") or [])

    sector_fund_flow = data.get("sector_fund_flow", {}) or {}
    inflow_sectors = sector_fund_flow.get("inflow", []) or []
    outflow_sectors = sector_fund_flow.get("outflow", []) or []

    if enhanced_main_sectors:
        tracked_sector = str(enhanced_main_sectors[0] or "").strip()
    else:
        main_sectors = market_analysis.get("main_sectors", []) if market_analysis else []
        tracked_sector = str(((main_sectors[0] or {}).get("name", "")) if main_sectors else "").strip()
    if not tracked_sector and inflow_sectors:
        tracked_sector = str((inflow_sectors[0] or {}).get("name", "") or "").strip()

    inflow_map = {item.get("name", ""): item.get("zljlr", 0) for item in inflow_sectors}
    outflow_map = {item.get("name", ""): abs(item.get("zljlr", 0)) for item in outflow_sectors}
    zt_pool_by_sector = data.get("zt_pool_by_sector", {}) or {}
    dt_pool_by_sector = data.get("dt_pool_by_sector", {}) or {}

    get_sector_hotlist_weight = helpers["get_sector_hotlist_weight"]
    load_recent_sector_flow_history = helpers["load_recent_sector_flow_history"]
    get_mainline_star_level = helpers["get_mainline_star_level"]

    sector_inflow = inflow_map.get(tracked_sector, 0)
    sector_outflow = outflow_map.get(tracked_sector, 0)
    sector_zt_count = len(zt_pool_by_sector.get(tracked_sector, []) or [])
    sector_dt_count = len(dt_pool_by_sector.get(tracked_sector, []) or [])
    hot_weight = get_sector_hotlist_weight(tracked_sector, data.get("tag_distribution", {})) if tracked_sector else 0
    inflow_history = load_recent_sector_flow_history(data.get("target_date", ""), tracked_sector, lookback_days=2) if tracked_sector else []
    mainline_snapshot = get_mainline_star_level(
        sector_inflow,
        sector_zt_count,
        dt_count=sector_dt_count,
        hot_weight=hot_weight,
        inflow_history=inflow_history,
    ) if tracked_sector else {}

    exports = {
        "tracked_sector": tracked_sector,
        "sector_inflow": sector_inflow,
        "sector_outflow": sector_outflow,
        "sector_zt_count": sector_zt_count,
        "sector_dt_count": sector_dt_count,
        "hot_weight": hot_weight,
        "inflow_history": inflow_history,
        "mainline_snapshot": mainline_snapshot,
        "zt_pool_by_sector": zt_pool_by_sector,
        "dt_pool_by_sector": dt_pool_by_sector,
    }
    return {
        "value": exports,
        "exports": exports,
        "state_patch": exports,
        "module_logs": [
            make_market_state_log(
                "mainline_candidates",
                "infer.mainline_candidates",
                "success",
                "tracked sector derived",
                tracked_sector=tracked_sector,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
```

Replace `scripts/domains/market_state/nodes/infer_environment_signal.py` with:

```python
from domains.market_state.trace import make_market_state_log


def run(ctx):
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers["action_map"]
    score_to_level = helpers["score_to_level"]

    tracked_sector = state.get("tracked_sector", "")
    mainline_snapshot = state.get("mainline_snapshot", {}) or {}
    mainline_score_pct = float(mainline_snapshot.get("score_pct", 0) or 0)
    sector_inflow = float(state.get("sector_inflow", 0) or 0)
    sector_outflow = float(state.get("sector_outflow", 0) or 0)
    sector_zt_count = int(state.get("sector_zt_count", 0) or 0)
    sector_dt_count = int(state.get("sector_dt_count", 0) or 0)
    hot_weight = float(state.get("hot_weight", 0) or 0)

    status = (
        f"{tracked_sector} {mainline_snapshot.get('star_level', '⭐')}（综合{mainline_score_pct:.0f}分），"
        f"净流入{sector_inflow:+.1f}亿，涨停{sector_zt_count}只，跌停{sector_dt_count}只，热榜占比{hot_weight:.1f}%"
    )
    level = "红灯" if sector_outflow > 12 and sector_dt_count >= 2 else score_to_level(mainline_score_pct)
    if mainline_snapshot.get("flow_trend") == "shrinking" and level == "绿灯":
        level = "黄灯"
    if mainline_snapshot.get("trend_label"):
        status += f"，{mainline_snapshot.get('trend_label')}"

    signal = {
        "layer": "主线地位复核",
        "status": status,
        "level": level,
        "action": action_map[level],
    }
    return {
        "value": signal,
        "exports": {"environment_signal": signal, "mainline_level": level, "mainline_score_pct": mainline_score_pct},
        "state_patch": {"environment_signal": signal, "mainline_level": level, "mainline_score_pct": mainline_score_pct},
        "module_logs": [
            make_market_state_log(
                "environment_signal",
                "infer.environment_signal",
                "success",
                "environment signal derived",
                tracked_sector=tracked_sector,
                level=level,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
```

Replace `scripts/domains/market_state/nodes/infer_mainline_continuity.py` with:

```python
from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers["action_map"]
    level_to_score = helpers["level_to_score"]
    clamp = helpers["clamp"]

    data = inputs.get("data") or {}
    tracked_sector = state.get("tracked_sector", "")
    sector_zt_count = int(state.get("sector_zt_count", 0) or 0)
    sector_dt_count = int(state.get("sector_dt_count", 0) or 0)
    hot_weight = float(state.get("hot_weight", 0) or 0)
    dragon_stocks = list(inputs.get("dragon_stocks") or [])
    dt_pool_by_sector = state.get("dt_pool_by_sector", {}) or {}

    leader = helpers["get_sector_leader"](tracked_sector, dragon_stocks, dt_pool_by_sector)
    lhb_net_sell_codes = {
        helpers["normalize_stock_code"](item.get("code", ""))
        for item in data.get("lhb_net_sell_top10", [])
    }
    if leader and leader.get("is_limit_down"):
        leader_level = "红灯"
        leader_status = f"{leader.get('name', '-')}({leader.get('zt_type', '-')})，龙头已跌停失守"
    elif leader and leader.get("code", "") in lhb_net_sell_codes:
        leader_level = "橙灯"
        leader_status = f"{leader.get('name', '-')}({leader.get('zt_type', '-')})，龙虎榜出现净卖出"
    elif leader and float(leader.get("lianban", 0) or 0) >= 3:
        leader_level = "绿灯"
        leader_status = f"{leader.get('name', '-')}({leader.get('zt_type', '-')})，连板高度{int(leader.get('lianban', 0))}板"
    else:
        leader_level = "黄灯"
        leader_status = f"{tracked_sector}暂无明确涨停龙头，板块承接偏弱"

    if sector_zt_count >= 15 and sector_dt_count == 0:
        structure_level = "绿灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，主升结构完整"
    elif sector_zt_count >= 5 and sector_dt_count <= 1:
        structure_level = "黄灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，正常分歧，仍有反复空间"
    elif sector_dt_count >= 3:
        structure_level = "红灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，跌停扩散，退潮明显"
    else:
        structure_level = "橙灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，涨停回落，结构开始松动"

    core_stock = helpers["get_sector_core_hot_stock"](tracked_sector, data.get("hot_rank_top30", []))
    if core_stock and float(core_stock.get("change_pct", 0) or 0) > 0 and int(core_stock.get("hot_rank", 99) or 99) <= 10:
        core_level = "绿灯"
        core_status = f"{core_stock.get('name', '-')}热榜第{int(core_stock.get('hot_rank', 0))}，涨幅{float(core_stock.get('change_pct', 0)):+.2f}%，仍是板块交易核心"
    elif core_stock:
        core_level = "黄灯"
        core_status = f"{core_stock.get('name', '-')}热榜第{int(core_stock.get('hot_rank', 0))}，涨幅{float(core_stock.get('change_pct', 0)):+.2f}%，承接尚可但需要盯紧"
    elif hot_weight >= 1:
        core_level = "橙灯"
        core_status = f"{tracked_sector}在热榜核心区缺少明确承接，热榜占比仅{hot_weight:.1f}%"
    else:
        core_level = "红灯"
        core_status = f"{tracked_sector}在热榜核心区缺少明确承接，主线关注度明显流失"

    leader_score = clamp(level_to_score(leader_level), 0.0, 100.0)
    structure_score = clamp(level_to_score(structure_level), 0.0, 100.0)
    core_score = clamp(level_to_score(core_level), 0.0, 100.0)

    exports = {
        "leader_signal": {"layer": "龙头健康度", "status": leader_status, "level": leader_level, "action": action_map[leader_level]},
        "structure_signal": {"layer": "板块内部结构", "status": structure_status, "level": structure_level, "action": action_map[structure_level]},
        "core_signal": {"layer": "持仓个股承接", "status": core_status, "level": core_level, "action": action_map[core_level]},
        "continuity_snapshot": {
            "leader_score": leader_score,
            "structure_score": structure_score,
            "core_score": core_score,
            "leader_name": leader.get("name", "-") if leader else "-",
        },
    }
    return {
        "value": exports,
        "exports": exports,
        "state_patch": exports,
        "module_logs": [
            make_market_state_log(
                "mainline_continuity",
                "infer.mainline_continuity",
                "success",
                "continuity signals derived",
                tracked_sector=tracked_sector,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_market_state_nodes.MarketStateNodesTest.test_infer_mainline_candidates_selects_tracked_sector_and_snapshot tests.test_market_state_nodes.MarketStateNodesTest.test_infer_environment_signal_generates_mainline_review_signal tests.test_market_state_nodes.MarketStateNodesTest.test_infer_mainline_continuity_generates_leader_structure_and_core_signals -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_market_state_nodes.py scripts/domains/market_state/nodes/infer_mainline_candidates.py scripts/domains/market_state/nodes/infer_environment_signal.py scripts/domains/market_state/nodes/infer_mainline_continuity.py
git commit -m "feat: extract market state candidate and continuity nodes"
```

## Task 5: Extract Risk, Competition, Assembly, And Wrap Legacy Entry

**Files:**

- Modify: `scripts/domains/market_state/nodes/infer_risk_pressure.py`
- Modify: `scripts/domains/market_state/nodes/infer_sector_competition.py`
- Modify: `scripts/domains/market_state/nodes/assemble_exit_analysis.py`
- Create: `tests/test_mainline_exit_analysis_graph_wrapper.py`
- Modify: `scripts/daily_report_entry_demo.py`
- Modify: `docs/superpowers/plans/2026-04-22-entry-modularization-roadmap.md`

- [ ] **Step 1: Write the failing tests**

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_entry_demo import build_mainline_exit_analysis


class MainlineExitAnalysisGraphWrapperTest(unittest.TestCase):
    def test_build_mainline_exit_analysis_keeps_no_mainline_fallback_contract(self):
        result = build_mainline_exit_analysis(
            {
                "target_date": "2026-04-22",
                "sector_fund_flow": {"inflow": [], "outflow": []},
                "zt_pool_by_sector": {},
                "dt_pool_by_sector": {},
                "calendar_events": [],
                "hot_rank_top30": [],
                "lhb_net_sell_top10": [],
                "tag_distribution": {},
                "stock_full_info": {},
            },
            {"main_sectors": []},
            [],
            enhanced_main_sectors=[],
        )

        self.assertEqual(result["sector_name"], "暂无明确主线")
        self.assertEqual(result["overall_level"], "红灯")
        self.assertEqual(result["leader_name"], "-")
        self.assertEqual(len(result["signals"]), 6)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_mainline_exit_analysis_graph_wrapper -v`

Expected: FAIL because placeholder nodes and assembly do not yet preserve the legacy fallback contract

- [ ] **Step 3: Write minimal implementation**

Replace `scripts/domains/market_state/nodes/infer_risk_pressure.py` with:

```python
from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers["action_map"]

    data = inputs.get("data") or {}
    tracked_sector = state.get("tracked_sector", "")
    event_status = "未发现与当前主线强相关的临近兑现事件"
    event_level = "绿灯"
    for event in data.get("calendar_events", [])[:10]:
        title = str(event.get("title", "") or "").strip()
        if not title:
            continue
        event_sector = helpers["analyze_event_sector"](title, "", data.get("xuangubao_data"), data.get("hot_rank_top30", []))
        if tracked_sector and event_sector and (tracked_sector in event_sector or event_sector in tracked_sector):
            event_status = f"{title}进入博弈窗口，注意抢跑后兑现"
            event_level = "黄灯"
            break

    signal = {
        "layer": "事件落地风险",
        "status": event_status,
        "level": event_level,
        "action": action_map[event_level],
    }
    return {
        "value": signal,
        "exports": {"risk_signal": signal, "risk_snapshot": {"event_status": event_status, "event_level": event_level}},
        "state_patch": {"risk_signal": signal, "risk_snapshot": {"event_status": event_status, "event_level": event_level}},
        "module_logs": [
            make_market_state_log(
                "risk_pressure",
                "infer.risk_pressure",
                "success",
                "risk signal derived",
                tracked_sector=tracked_sector,
                level=event_level,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
```

Replace `scripts/domains/market_state/nodes/infer_sector_competition.py` with:

```python
from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers["action_map"]

    data = inputs.get("data") or {}
    tracked_sector = state.get("tracked_sector", "")
    sector_inflow = float(state.get("sector_inflow", 0) or 0)
    hot_weight = float(state.get("hot_weight", 0) or 0)
    zt_pool_by_sector = state.get("zt_pool_by_sector", {}) or {}
    replacement_candidates = []
    for sector in (data.get("sector_fund_flow", {}) or {}).get("inflow", []):
        sector_name = sector.get("name", "")
        if not sector_name or sector_name == tracked_sector:
            continue
        replacement_candidates.append(
            {
                "name": sector_name,
                "inflow": sector.get("zljlr", 0),
                "zt_count": len(zt_pool_by_sector.get(sector_name, []) or []),
                "hot_weight": helpers["get_sector_hotlist_weight"](sector_name, data.get("tag_distribution", {})),
            }
        )
    replacement_candidates.sort(
        key=lambda item: (item.get("inflow", 0), item.get("zt_count", 0), item.get("hot_weight", 0)),
        reverse=True,
    )

    replacement = replacement_candidates[0] if replacement_candidates else None
    if not replacement:
        level = "绿灯"
        status = "未见明显替代主线，资金仍未完成切换"
    elif replacement.get("inflow", 0) > sector_inflow or replacement.get("hot_weight", 0) > hot_weight + 1:
        level = "黄灯"
        status = f"{replacement.get('name', '')}开始试探承接旧主线资金"
    else:
        level = "绿灯"
        status = f"{replacement.get('name', '')}暂未形成有效替代"

    signal = {
        "layer": "替代主线流向",
        "status": status,
        "level": level,
        "action": action_map[level],
    }
    return {
        "value": signal,
        "exports": {"competition_signal": signal, "competition_snapshot": {"replacement": replacement or {}, "level": level}},
        "state_patch": {"competition_signal": signal, "competition_snapshot": {"replacement": replacement or {}, "level": level}},
        "module_logs": [
            make_market_state_log(
                "sector_competition",
                "infer.sector_competition",
                "success",
                "competition signal derived",
                tracked_sector=tracked_sector,
                level=level,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
```

Replace `scripts/domains/market_state/nodes/assemble_exit_analysis.py` with:

```python
from domains.market_state.contracts import build_market_state_action_map
from domains.market_state.trace import make_market_state_log


def run(ctx):
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = build_market_state_action_map()

    tracked_sector = state.get("tracked_sector", "")
    if not tracked_sector:
        exit_analysis = {
            "sector_name": "暂无明确主线",
            "star_level": "-",
            "leader_name": "-",
            "event_risk_summary": "无主线，无需评估事件兑现风险",
            "overall_level": "红灯",
            "overall_action": action_map["红灯"],
            "exit_conditions": ["暂无明确主线，不值得死在里面，优先空仓或等待新主线"],
            "signals": [
                {"layer": "主线地位复核", "status": "暂无明确主线", "level": "红灯", "action": "没有主线就不能参与，已有仓位也要退出"},
                {"layer": "龙头健康度", "status": "无可跟踪龙头", "level": "红灯", "action": "不能新开仓，已有仓位不做旧线自救"},
                {"layer": "板块内部结构", "status": "主线结构不存在", "level": "红灯", "action": "不参与杂毛补涨，已有仓位按退场处理"},
                {"layer": "持仓个股承接", "status": "无主线核心可跟踪", "level": "红灯", "action": "没有承接就不参与，已有仓位直接退出"},
                {"layer": "事件落地风险", "status": "无主线，无需评估事件风险", "level": "黄灯", "action": action_map["黄灯"]},
                {"layer": "替代主线流向", "status": "等待新主线承接", "level": "黄灯", "action": action_map["黄灯"]},
            ],
        }
    else:
        leader_signal = state.get("leader_signal", {})
        structure_signal = state.get("structure_signal", {})
        core_signal = state.get("core_signal", {})
        risk_signal = state.get("risk_signal", {})
        competition_signal = state.get("competition_signal", {})
        environment_signal = state.get("environment_signal", {})
        continuity_snapshot = state.get("continuity_snapshot", {})
        mainline_score_pct = float(state.get("mainline_score_pct", 0) or 0)
        overall_score = round(
            mainline_score_pct * 0.4
            + continuity_snapshot.get("leader_score", 0) * 0.2
            + continuity_snapshot.get("structure_score", 0) * 0.15
            + continuity_snapshot.get("core_score", 0) * 0.15,
            1,
        )
        overall_level = "绿灯" if overall_score >= 70 else "黄灯" if overall_score >= 50 else "橙灯"
        exit_analysis = {
            "sector_name": tracked_sector,
            "star_level": (state.get("mainline_snapshot", {}) or {}).get("star_level", "⭐"),
            "leader_name": continuity_snapshot.get("leader_name", "-"),
            "event_risk_summary": risk_signal.get("status", ""),
            "overall_level": overall_level,
            "overall_score": overall_score,
            "mainline_score_pct": round(mainline_score_pct, 1),
            "score_detail": {
                "主线": round(mainline_score_pct, 1),
                "龙头": round(float(continuity_snapshot.get("leader_score", 0) or 0), 1),
                "结构": round(float(continuity_snapshot.get("structure_score", 0) or 0), 1),
                "承接": round(float(continuity_snapshot.get("core_score", 0) or 0), 1),
                "事件": 65.0 if risk_signal.get("level") == "黄灯" else 85.0,
                "替代": 65.0 if competition_signal.get("level") == "黄灯" else 85.0,
            },
            "mainline_component_scores": (state.get("mainline_snapshot", {}) or {}).get("component_scores", {}),
            "mainline_trend_label": (state.get("mainline_snapshot", {}) or {}).get("trend_label", ""),
            "overall_action": action_map[overall_level],
            "participation_advice": {
                "绿灯": "可参与，可继续粘住最强趋势",
                "黄灯": "优先围绕主线核心，继续持有最强",
                "橙灯": "禁止新增，旧仓去弱留强，不强就卖",
                "红灯": "停止参与，已有仓位尽快退出",
            }[overall_level],
            "exit_conditions": [
                "跌破止损线（最近前低）立即卖出，不讨论",
                "买入后仅3~5个交易日观察期，走势不及预期即卖（卖出线即止损线）",
                "当日放量大阳线为理想主动卖点：他人眼中的确定性买点，本模式作减仓/清仓点",
            ],
            "price_lines": None,
            "signals": [
                environment_signal,
                leader_signal,
                structure_signal,
                core_signal,
                risk_signal,
                competition_signal,
            ],
        }

    return {
        "value": exit_analysis,
        "exports": {"exit_analysis": exit_analysis},
        "state_patch": {"exit_analysis": exit_analysis},
        "module_logs": [
            make_market_state_log(
                "assemble_exit_analysis",
                "assemble.exit_analysis",
                "success",
                "legacy exit analysis assembled",
                tracked_sector=tracked_sector or "暂无明确主线",
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
```

Modify `scripts/daily_report_entry_demo.py` by importing the runtime and replacing the body of `build_mainline_exit_analysis()`:

```python
from domains.market_state.runtime import run_market_state_analysis
```

```python
def build_mainline_exit_analysis(data, market_analysis, dragon_stocks, enhanced_main_sectors=None):
    result = run_market_state_analysis(
        {
            "inputs": {
                "data": data,
                "market_analysis": market_analysis,
                "dragon_stocks": dragon_stocks,
                "enhanced_main_sectors": enhanced_main_sectors or [],
            },
            "helpers": {
                "action_map": {
                    "绿灯": "主线健康，可继续做",
                    "黄灯": "主升强化，优先做核心",
                    "橙灯": "退潮预警，禁止新增",
                    "红灯": "退潮确认，尽快退出",
                },
                "get_sector_hotlist_weight": get_sector_hotlist_weight,
                "load_recent_sector_flow_history": load_recent_sector_flow_history,
                "get_mainline_star_level": get_mainline_star_level,
                "score_to_level": _score_to_level,
                "level_to_score": _level_to_score,
                "safe_float": _safe_float,
                "clamp": _clamp,
                "get_sector_leader": get_sector_leader,
                "get_sector_core_hot_stock": get_sector_core_hot_stock,
                "normalize_stock_code": normalize_stock_code,
                "calculate_exit_price_lines": calculate_exit_price_lines,
                "fetch_recent_price_bars": fetch_recent_price_bars,
                "compute_stop_loss_mainline_anchor": compute_stop_loss_mainline_anchor,
                "analyze_event_sector": analyze_event_sector,
            },
        }
    )
    return (result.get("exports") or {}).get("exit_analysis") or {}
```

Update `docs/superpowers/plans/2026-04-22-entry-modularization-roadmap.md` by replacing:

```markdown
- [ ] 落地 `market_state`，把环境判断相关的请求/推导/输出收敛到同一域
- [ ] 提取分析层第一批模块：从 `build_mainline_exit_analysis()` 拆出连续性、风险、主线判定子模块
```

with:

```markdown
- [x] 落地 `market_state` 首域 graph：`scripts/domains/market_state/graph.py`
- [x] 把 `build_mainline_exit_analysis()` 迁移成 graph wrapper：`scripts/domains/market_state/runtime.py`
- [ ] 继续细化 `market_state` node：把连续性、风险、替代主线判断从粗节点升级成更细粒度 node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_mainline_exit_analysis_graph_wrapper tests.test_market_state_workflow_graph tests.test_market_state_nodes -v`

Expected: PASS

Then run: `python3 -m unittest discover -s tests -v`

Expected: PASS for the full suite

- [ ] **Step 5: Commit**

```bash
git add tests/test_mainline_exit_analysis_graph_wrapper.py scripts/domains/market_state/nodes/infer_risk_pressure.py scripts/domains/market_state/nodes/infer_sector_competition.py scripts/domains/market_state/nodes/assemble_exit_analysis.py scripts/daily_report_entry_demo.py docs/superpowers/plans/2026-04-22-entry-modularization-roadmap.md
git commit -m "feat: migrate market state analysis to workflow graph"
```
