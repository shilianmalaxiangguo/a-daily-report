# Daily Report Node Runtime Contract Design

> Date: 2026-05-27
> Scope: Define the reusable node contract for `a-daily-report`, then use one small vertical slice as the reference sample before replacing more modules.

## Goal

Turn daily-report generation from a mixed legacy entry plus local node runtimes into a repeatable, Dify-like node workflow: each important unit can be replaced, upgraded, tested, replayed, and exposed through a stable report or artifact surface.

The goal is not to make the system look abstract. The goal is to make every important trading decision unit behave like a dependable building block:

- clear input
- clear output
- clear diagnostics
- clear report or artifact surface
- focused tests
- replay proof when it affects the daily report

## In Scope

- Define what counts as a real daily-report node.
- Define the minimum node input and output contract.
- Define the role of registry, runtime, workflow graph, and compatibility wrappers.
- Define how to migrate old modules without changing trading semantics.
- Define a reference sample path for the first implementation slice.
- Define acceptance checks that future module replacements can copy.

## Out of Scope

- No browser-based visual workflow editor.
- No cross-process service rewrite.
- No full replacement of `scripts/daily_report_entry_demo.py` in this slice.
- No change to buy/sell logic, scoring formulas, report conclusions, or trading vocabulary.
- No broad formatting rewrite of existing report sections.

## Non-goals

- Do not clone Dify.
- Do not wrap every helper function as a node.
- Do not add a new abstraction unless it removes present-time replacement or verification risk.
- Do not move deterministic report runtime logic into a Codex skill only because the workflow is reusable.

## Done Definition

- This spec defines the node contract and migration rules.
- This spec names a first reference sample path.
- The reference sample can be implemented as a narrow follow-up plan.
- Future modules can copy the same checklist without reading this whole repo first.
- Existing public entrypoints keep working while internals move toward nodes.

## Current Baseline

The repository already has several partial node patterns:

- `scripts/workflow_graph/` contains a generic workflow executor foundation.
- `scripts/orchestrator/report_orchestrator.py` and `scripts/orchestrator/pipeline_runner.py` contain a hook-based pipeline.
- `scripts/domains/execution_chain/*_node_runtime.py` contains stage-local ordered node runtimes.
- `scripts/report/*_node_runtime.py` contains report-section node runtimes.
- `enabled_node_keys` is already used as the compatibility switch for partial rendering.

The remaining weakness is consistency. Some modules have request logic but no report node. Some have report nodes but upstream logic is still a large wrapper. Some emit data, but there is no visible artifact or replay acceptance proving the node is actually live.

This spec standardizes the rule: a module is not fully node-ready until it has a stable runtime boundary, structured outputs, diagnostics, tests, and a visible report or artifact path when its result matters to the daily report.

## Core Model

Daily-report workflows should use this layered model:

```text
input request nodes
  -> analysis nodes
  -> decision nodes
  -> report nodes
  -> artifact nodes
  -> audit nodes
```

Each layer may have its own local runtime when that is enough. A full workflow graph is required only when there are real dependency branches, multiple upstream sources, or repeated replacement needs.

## Node Contract

Each node has one stable key:

```text
domain.area.node_name
```

Examples:

```text
input.new_stock_calendar.request
selection.new_stock_narrative.score
watch_candidates.new_stock_upgrade.merge
report.new_stock_research.render
audit.new_stock_replay.check
```

Each node receives a single context dictionary. The exact fields may vary by domain, but the shape should stay recognizable:

```python
{
    "node": {
        "key": "selection.new_stock_narrative.score",
        "version": "1.0.0",
        "workflow_key": "new_stock_reference_v1",
        "run_id": "report:2026-05-06",
    },
    "inputs": {},
    "context": {},
    "upstream": {},
    "helpers": {},
    "config": {},
}
```

Each node returns a dictionary:

```python
{
    "exports": {},
    "context_patch": {},
    "report_sections": {},
    "artifacts": {},
    "diagnostics": {},
    "module_logs": [],
    "errors": [],
}
```

### Required Output Meaning

| Field | Meaning |
| --- | --- |
| `exports` | Public structured values downstream nodes can consume. |
| `context_patch` | Values merged into the local workflow context. |
| `report_sections` | Optional markdown-ready section fragments or structured render input. |
| `artifacts` | File paths, JSON exports, HTML outputs, or persisted ledgers. |
| `diagnostics` | Provider, row counts, fallback source, missing fields, or timing metadata. |
| `module_logs` | Human-readable runtime trace entries. |
| `errors` | Recoverable errors that should be visible to the caller. |

Nodes may return only the fields they need, but a node that touches the daily report must at least expose `exports`, `diagnostics`, and `module_logs`.

## What Counts As Real Node-Ready

A module is node-ready only when all of these are true:

1. It has a named node key.
2. It has a registry entry or a local node-spec builder.
3. Its runtime can execute only that node or a selected node subset.
4. It returns structured exports instead of only mutating a large dictionary.
5. It records diagnostics that explain source, row count, and degraded data.
6. It has focused unit tests.
7. If it affects the report, replay output proves the section or artifact is visible.
8. If it is optional, missing data degrades to an explicit empty result instead of silent disappearance.

Not node-ready:

- A helper function hidden inside `daily_report_entry_demo.py`.
- A wrapper that calls old logic but has no structured exports.
- A request module that writes data but has no report or artifact surface.
- A report renderer that cannot be selected with `enabled_node_keys`.
- A module that only passes tests but cannot be located in generated replay output.

## Registry Contract

Each replaceable area needs a registry. The registry owns binding, not business logic.

```python
NODE_BUILDERS = {
    "request": build_new_stock_request_node,
    "score": build_new_stock_score_node,
    "merge": build_new_stock_candidate_merge_node,
    "render": build_new_stock_report_node,
}
```

Registry rules:

- Add a node by adding a new key.
- Replace a node by changing the key binding or version alias.
- Keep old public wrappers until replay and report checks prove the replacement.
- Do not hide direct business calls inside the runtime when the behavior is supposed to be replaceable.

## Runtime Contract

The runtime is not a business brain. It should only:

1. Normalize inputs.
2. Resolve node specs.
3. Execute nodes in order or workflow order.
4. Merge `context_patch`.
5. Collect `exports`, `report_sections`, `artifacts`, `diagnostics`, `module_logs`, and `errors`.
6. Return a stable result shape.

Local ordered runtime is enough when a section is linear:

```text
request -> score -> merge -> render
```

Workflow graph runtime is preferred when there are branches:

```text
market request -> source A score -> assemble
market request -> source B score -> assemble
```

## Compatibility Wrappers

Existing public functions should remain as thin wrappers while migration is happening.

Example:

```python
def build_new_stock_research_pool(...):
    return run_new_stock_reference_workflow(...).exports["new_stock_research_pool"]
```

Rules:

- Keep old names until callers are migrated.
- Wrappers should call node runtimes, not duplicate logic.
- Wrappers may adapt old argument lists into node context.
- Wrappers should not add new trading semantics.

## Report Surface Contract

If a node changes the daily report, it must have one of these visible surfaces:

- a report section node
- a row inside an existing report table
- a companion JSON artifact
- a companion HTML artifact
- an audit row proving why it did not appear

For the daily report, "data exists in a snapshot" is not enough. If the user expects to inspect it, the report or companion artifact must expose the conclusion or the absence reason.

Report text remains conclusion-first:

1. Say what to do or not do.
2. Say why using compact evidence.
3. Do not explain internal formulas unless a diagnostic artifact is requested.

## Testing Contract

Every migration slice should have four levels of checks, scaled to risk:

1. Node unit test: selected node returns expected exports and diagnostics.
2. Runtime test: `enabled_node_keys` or equivalent selected execution works.
3. Integration test: old public wrapper still returns the expected shape.
4. Replay or artifact check: generated output exposes the section, row, artifact, or absence reason.

The first red test should usually assert selective execution:

```python
result = run_new_stock_nodes(context, enabled_node_keys=["score"])
self.assertIn("new_stock_research_pool", result["context"])
self.assertNotIn("rendered_section", result["context"])
```

This protects the building-block property directly.

All Python commands in this repo use:

```bash
.generated/venv-py314/bin/python3.14 -m unittest ...
```

## First Reference Sample: New Stock Module

The first reference sample should be the new-stock module because it already shows the exact failure mode this contract wants to prevent:

- request data exists
- scoring exists
- candidate upgrades can be produced
- raw research can remain hidden
- report exposure can still be incomplete

### Current New-Stock Path

```text
domains.new_stock_calendar.request
  -> input.runtime
  -> selection.new_stock_narrative_runtime
  -> new_stock_research_pool
  -> new_stock_candidate_upgrades
  -> domains.watch_candidates.infer
```

### Reference Target Path

```text
input.new_stock_calendar.request
  -> selection.new_stock_narrative.score
  -> watch_candidates.new_stock_upgrade.merge
  -> report.new_stock_research.render
  -> audit.new_stock_replay.check
```

### Sample Done Definition

- `new_stock_calendar` request remains deterministic and testable.
- `new_stock_research_pool` has factor-level exports.
- `new_stock_candidate_upgrades` enters watch candidates only after explicit qualification.
- The report has a compact row or absence reason:
  - "有新股研究升级，进入观察。"
  - "有新股研究池，但今日未形成买入资格。"
  - "上市日期缺失，不参与。"
- Replay for a known date proves the visible result.
- Old callers of `build_new_stock_research_pool()` and watch-candidate inference still work.

## Migration Order

Use this order after the new-stock sample proves the contract:

1. New-stock research path.
2. Two-market turnover history comparison.
3. Mainline turnover and capacity regime.
4. Candidate quality scorecard.
5. PK decision action-plan context.
6. Remaining `daily_report_entry_demo.py` orchestration blocks.

This order starts with small, high-signal slices before touching the main entry file.

## Implementation Plan Template For Future Slices

Each future slice should start with this small scope block:

```markdown
## In Scope

- Node keys:
- Existing wrappers preserved:
- Report or artifact surface:
- Replay date:

## Out of Scope

- Trading semantics unchanged:
- No broad report rewrite:
- No unrelated data source changes:

## Done Definition

- Focused node tests:
- Runtime selective execution test:
- Wrapper compatibility test:
- Replay or artifact proof:
```

## Review Checklist

Before calling a slice node-ready, answer yes to all:

- Can I run only this node or selected nodes?
- Can I replace this node without editing the main entry script?
- Can I inspect its exports without reading rendered markdown?
- Can I see provider/source quality in diagnostics?
- Can I tell why no report row appeared?
- Can replay prove the result?
- Does the visible wording stay conclusion-first?

## Merge Strategy

Keep each replacement slice small:

1. Spec or plan update.
2. Failing focused test.
3. Node runtime or registry change.
4. Wrapper compatibility.
5. Replay or artifact check.
6. Merge into `develop` only after the slice proves its own output.

If a slice expands beyond this done definition, split it. Merge the smallest proven node first, then move the expansion to a follow-up branch.
