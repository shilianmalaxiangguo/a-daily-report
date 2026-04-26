# PK Decision Stage Nodeization Design

> Date: 2026-04-26
> Scope: Nodeize `scripts/domains/execution_chain/pk_decision_stage.py` without changing trading semantics or report wording.

## Goal

Turn Step 5 / PK decision from one large orchestration function into a stage-local node runtime, while preserving the existing `build_pk_decision_stage()` public entrypoint, renderer outputs, exports, and replay behavior.

The current markdown renderers are already node-based:

- `scripts/report/pk_decision_renderer.py`
- `scripts/report/pk_decision_nodes.py`
- `scripts/report/action_plan_renderer.py`
- `scripts/report/action_plan_nodes.py`

The remaining problem is upstream of those renderers: `scripts/domains/execution_chain/pk_decision_stage.py` still mixes candidate scoring, observation-anchor selection, probe/position decisions, front-page texts, PK-context assembly, action-plan-context assembly, rendering, and exports in one 900+ line stage.

## Non-Goals

- Do not change buy/sell logic, scoring formulas, position sizing, watch-anchor priority, or gate behavior.
- Do not rewrite `report/pk_decision_*` or `report/action_plan_*` render nodes.
- Do not introduce a graph workflow for Step 5 yet. A local registry/runtime is enough.
- Do not rename user-facing report sections unless required by existing tests.
- Do not delete `build_pk_decision_stage()`; callers keep using it.

## Current Responsibilities

`pk_decision_stage.py` currently does these jobs in a single function:

1. Extracts a large dependency/context surface from `stage_context`.
2. Scores executable and waiting candidates.
3. Builds keep-group observation candidates when the trade gate is closed.
4. Builds abnormal watch-anchor candidates.
5. Selects `best_stock`, `runner_up`, `watch_anchor`, and `watch_anchor_type`.
6. Builds fallback crossline watch anchor when no primary anchor exists.
7. Builds abnormal probe group, special probe verdict, and position sizing decision.
8. Builds front-summary text exports.
9. Builds MVP digest and focus summary lines.
10. Builds PK renderer context: `pending_lines`, `observation_lines`, `conclusion_lines`.
11. Builds action-plan renderer context: action rows, observation blocks, position lines, schedule lines, alert rows.
12. Calls the existing PK and action-plan renderers.
13. Returns stage-level exports used by front summary, final conclusion, tail summary, and strategy tracking.

## Proposed Architecture

Add a stage-local node layer under `scripts/domains/execution_chain/pk_decision_nodes/`, matching the existing Step 1/2/3/5 patterns.

Create:

- `scripts/domains/execution_chain/pk_decision_node_registry.py`
- `scripts/domains/execution_chain/pk_decision_node_runtime.py`
- `scripts/domains/execution_chain/pk_decision_nodes/__init__.py`
- `scripts/domains/execution_chain/pk_decision_nodes/score_candidates.py`
- `scripts/domains/execution_chain/pk_decision_nodes/observation_pool.py`
- `scripts/domains/execution_chain/pk_decision_nodes/watch_anchor.py`
- `scripts/domains/execution_chain/pk_decision_nodes/probe_position.py`
- `scripts/domains/execution_chain/pk_decision_nodes/front_texts.py`
- `scripts/domains/execution_chain/pk_decision_nodes/pk_context.py`
- `scripts/domains/execution_chain/pk_decision_nodes/action_plan_context.py`
- `scripts/domains/execution_chain/pk_decision_nodes/render_sections.py`
- `scripts/domains/execution_chain/pk_decision_nodes/export_stage_state.py`

Modify:

- `scripts/domains/execution_chain/pk_decision_stage.py`
- `tests/test_pk_decision_stage.py`

Optional focused tests:

- `tests/test_pk_decision_stage_nodes.py`

The stage module gains a focused runtime entrypoint:

```python
def build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None):
    stage_context = stage_context or {}
    stage_meta = stage_meta or {}
    node_context = {**stage_context, "stage_label": stage_meta.get("label", "Step 5")}
    node_specs = build_pk_decision_node_specs(PK_DECISION_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    runtime_result = run_pk_decision_nodes(node_specs, node_context)
    return {
        "lines": runtime_result["lines"],
        "exports": runtime_result["context"].get("stage_exports", {}),
        "module_logs": runtime_result["module_logs"],
    }
```

`build_pk_decision_stage()` remains the public compatibility wrapper. It calls `build_pk_decision_runtime()` with the default full node set, appends the final stage log, and returns the same shape it returns today.

The runtime function becomes:

1. Normalize `stage_context`.
2. Build `node_context`.
3. Resolve node specs through registry.
4. Run nodes in order.
5. Append final stage log.
6. Return `lines`, `exports`, and `module_logs`.

## Node Contract

Each node receives and returns the mutable stage `node_context` pattern already used in nearby stage runtimes:

```python
{
    "lines": ["rendered line"],
    "exports": {"best_stock": {"code": "000001"}},
    "module_logs": [{"module": "node", "step": "run", "status": "success", "message": "ok", "details": {}}],
}
```

Nodes may write intermediate values into the shared context. The runtime should merge exports and logs exactly like existing `candidate_selection_node_runtime.py`, `risk_review_node_runtime.py`, and `entry_plan_node_runtime.py`.

## Node Boundaries

### `score_candidates`

Inputs:

- `executable_stocks`
- `waiting_stocks`
- `final_gate`
- `mainline_name`
- `conviction_codes`
- `leader_memory_codes`
- `market_research_snapshot`
- scoring helpers from `stage_context`

Outputs:

- `trade_gate_open`
- `ev_calibration`
- `scored_executable_stocks`
- `scored_waiting_stocks`
- `pending_candidates`
- `pk_candidates`
- `best_stock`
- `runner_up`

Behavior must match the current candidate scoring order exactly.

### `observation_pool`

Inputs:

- `trade_gate_open`
- `keep_group`
- `scored_executable_stocks`
- `scored_waiting_stocks`
- `abnormal_watch_pool_all`
- `step2_bundle`
- tradability and waiting-plan helpers

Outputs:

- `scored_keep_watch_stocks`
- `abnormal_watch_anchor_candidates`
- `observation_candidates`
- `display_pending_candidates`
- `display_observation_candidates`

This node owns closed-gate observation pool construction. It must preserve the current `allow_conditional_30` behavior and keep-group watch generation.

### `watch_anchor`

Inputs:

- `trade_gate_open`
- `abnormal_watch_anchor_candidates`
- `pending_candidates`
- `observation_candidates`
- `waiting_stocks`
- `step2_bundle`
- crossline fallback helpers

Outputs:

- `watch_anchor`
- `watch_anchor_type`

This node must preserve the crossline fallback block that currently creates a watch anchor from `step2_bundle["crossline_observation_stocks"]` when no primary anchor exists.

### `probe_position`

Inputs:

- `watch_anchor`
- `watch_anchor_type`
- `best_stock`
- `final_gate`
- `market_research_snapshot`
- probe and position helpers

Outputs:

- `abnormal_probe_group`
- `special_probe_verdict`
- `position_decision`
- selected candidate `position_pct`
- selected candidate `candidate_feedback_ready`

This node is behavior-preserving. It should not reinterpret position sizing.

### `front_texts`

Inputs:

- `best_stock`
- `watch_anchor`
- `watch_anchor_type`
- `position_decision`
- `final_gate`
- `focus_group`
- `keep_group`
- `delete_group`
- `market_research_snapshot`

Outputs:

- `front_structure_layer_text`
- `front_follow_action_text`
- `special_probe_text`
- `philosophy_constraint_text`
- `core_mvp_digest_lines`
- `mvp_focus_summary_lines`

These exports feed front summary and final conclusion. They are high-risk and must remain byte-for-byte compatible in replay unless a test explicitly updates the expected wording.

### `pk_context`

Inputs:

- candidate and anchor outputs
- price focus helpers
- closed-gate formatter

Outputs:

- `pending_lines`
- `observation_lines`
- `conclusion_lines`

This node only builds context for existing `render_pk_decision_section()`.

### `action_plan_context`

Inputs:

- `best_stock`
- `watch_anchor`
- `display_observation_candidates`
- `waiting_stocks`
- prediction rows
- price/stop/exit helpers
- `position_level`
- `final_gate`

Outputs:

- `action_rows`
- `observation_priority_lines`
- `backup_observation_lines`
- `position_section_lines`
- `pre_market_lines`
- `opening_lines`
- `first_hour_lines`
- `intraday_lines`
- `closing_lines`
- `alert_rows`

This node only builds context for existing `render_action_plan_section()`.

### `render_sections`

Inputs:

- `render_pk_decision_section`
- `render_action_plan_section`
- PK/action context outputs

Outputs:

- report `lines`

The renderers remain external dependencies so existing renderer unit tests keep their value.

`render_pk_decision_section` and `render_action_plan_section` must continue to come from `stage_context`. Existing tests stub those functions, and `scripts/report/runtime.py` wires the real renderers into the stage context. The nodeized stage must not import and call the report renderers directly.

### `export_stage_state`

Inputs:

- all final state values

Outputs:

- stage `exports`

Must include at least:

- `trade_gate_open`
- `best_stock`
- `runner_up`
- `watch_anchor`
- `watch_anchor_type`
- `abnormal_probe_group`
- `special_probe_verdict`
- `position_decision`
- `front_structure_layer_text`
- `front_follow_action_text`
- `special_probe_text`
- `philosophy_constraint_text`
- `scored_executable_stocks`
- `core_mvp_digest_lines`
- `mvp_focus_summary_lines`

## Compatibility Requirements

The refactor is acceptable only if these remain true:

1. `build_pk_decision_stage(stage_context, stage_meta, stage_lookup=None)` remains the public entrypoint.
2. `build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None)` is available for focused tests and partial diagnostics.
3. Existing `tests/test_pk_decision_stage.py` stays meaningful and passes.
4. `reports/replay/2026-04-24_A股日报_完整版_replay.md` remains semantically identical for PK/action-plan sections.
5. Stage exports retain the same keys and values for representative open-gate and closed-gate cases.
6. Stage line order remains PK section first, action plan second, then the trailing blank line.
7. Closed-gate conditional text remains:
   - `allow_conditional_30=True` -> `等10点确认，未确认不开`
   - otherwise -> `⛔<position_level>禁止新开仓`
8. No node may call external APIs; nodes only use helpers already supplied in `stage_context`.

## Testing Design

### Keep Existing Tests

Retain and adapt:

- `tests/test_pk_decision_stage.py`

These tests already cover:

- closed-gate text formatting
- open-gate best-stock export
- watch-only conclusion wording

### Add Node Runtime Tests

Create `tests/test_pk_decision_stage_nodes.py` with:

1. Runtime aggregates node lines, exports, and logs in order.
2. Registry respects `enabled_node_keys`.
3. `build_pk_decision_runtime(stage_context, stage_meta, enabled_node_keys=["render_sections"])` can run selected nodes without rendering omitted nodes.
4. `score_candidates` preserves best-stock and runner-up selection.
5. `watch_anchor` preserves crossline fallback behavior.
6. `export_stage_state` returns all required export keys.

### Replay Acceptance

After implementation:

```bash
venv/bin/python -m unittest tests.test_pk_decision_stage tests.test_pk_decision_stage_nodes tests.test_report_runtime -q
venv/bin/python scripts/daily_report_entry_demo.py 2026-04-24 --replay
venv/bin/python scripts/report/report_acceptance_audit.py reports/replay/2026-04-24_A股日报_完整版_replay.md
git diff --check
```

## Implementation Task Outline

### Task 1: Add Node Registry and Runtime

Create the pk-decision stage registry/runtime with the same contract as candidate selection, risk review, and entry plan.

Acceptance:

- Registry orders nodes deterministically.
- `enabled_node_keys` filters nodes.
- Runtime merges lines, exports, logs.
- No business behavior moves yet.

### Task 2: Extract Candidate Scoring Node

Move executable/waiting scoring and `best_stock` selection into `score_candidates`.

Acceptance:

- Open-gate test still exports best stock.
- Runner-up selection remains identical.
- No renderer changes.

### Task 3: Extract Observation Pool Node

Move keep-group watch construction, abnormal watch-anchor candidate construction, and display candidate selection into `observation_pool`.

Acceptance:

- Closed-gate observation behavior remains identical.
- Conditional defense gate still presents observation/10点 confirmation wording.

### Task 4: Extract Watch Anchor Node

Move priority watch-anchor selection and crossline fallback into `watch_anchor`.

Acceptance:

- Existing watch-only conclusion test still passes.
- New focused test proves crossline fallback still builds an anchor when no primary anchor exists.

### Task 5: Extract Probe, Position, and Front Text Nodes

Move probe verdict, position sizing, selected-candidate annotation, front-summary texts, and MVP digest generation into `probe_position` and `front_texts`.

Acceptance:

- Exported front texts remain identical in existing tests.
- `position_pct` and `candidate_feedback_ready` annotations still attach to the selected candidate.

### Task 6: Extract PK Renderer Context Node

Move `pending_lines`, `observation_lines`, and `conclusion_lines` construction into `pk_context`.

Acceptance:

- Existing open-gate and closed-gate PK rendered sections pass.
- No duplicate “不开新仓” lines appear.

### Task 7: Extract Action Plan Context Node

Move action rows, observation priority, backup observation, position lines, schedule lines, and alert rows into `action_plan_context`.

Acceptance:

- Existing action plan renderer output is unchanged.
- `today_predictions` and `nextday_predictions` still render alert rows.

### Task 8: Wire Render and Export Nodes

Move final renderer calls into `render_sections` and final export construction into `export_stage_state`.

Acceptance:

- `build_pk_decision_stage()` becomes a thin orchestration wrapper.
- Replay generation and acceptance audit pass.

## Risks

The main risk is not rendering. It is hidden coupling through exports:

- front summary depends on `front_structure_layer_text`, `front_follow_action_text`, `special_probe_text`, and `philosophy_constraint_text`;
- tail summary and tracking snapshots depend on `watch_anchor`, `watch_anchor_type`, and `position_decision`;
- action plan depends on the exact distinction between `best_stock`, `watch_anchor`, and no-action states.

Mitigation:

- Extract in small TDD tasks.
- Preserve function names and helper calls.
- Run focused tests after each extraction.
- Use replay and acceptance audit only after all nodes are wired.

## Review Checklist

- No trade logic changes.
- No renderer rewrite.
- Node names reflect business responsibilities, not file movements.
- Each node can be tested independently.
- `enabled_node_keys` works for diagnostics.
- Stage exports remain stable.
