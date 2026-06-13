# Current Target Flow Research

## Question

Why can the same daily report show different target identities such as
上海石化 and 豫能控股, and where should the canonical target handoff live?

## Findings

### Current Data Flow

```text
T0 raw/process sources
|
+-- execution_stage_context.best_stock
+-- execution_stage_context.watch_anchor
+-- existing candidate_quality_panel_fields
|   `-- can produce 上海石化 as a local/process candidate
|
v
T1 runtime current-core resolver
_resolve_front_page_target_candidate(...)
|
+-- _build_front_page_selected_position_candidate(...)
+-- _resolve_runtime_current_core_candidate(...)
+-- decision-ledger fallback
+-- report-line fallback
    `-- can produce 豫能控股 as selected/current core
|
v
T2 position/account repair
_build_front_page_position_decision(...)
|
`-- may force 0% observation because of weak market, account, missing execution
    evidence, or old-position priority
|
v
T3 final target resolution
_build_runtime_final_target_resolution(...)
|
+-- new_entry_target = selected_position_candidate/current_core
+-- display_target = old position / proxy / new entry / empty
+-- watch_target = new_entry when old position or proxy blocks direct new entry
    `-- final action-facing observation authority
|
v
T4 renderers
+-- final target solution panel
+-- front page account advice
+-- daily judgment panel
+-- candidate-quality panel
+-- appendix observation anchor
    `-- historical bug: some renderers read T0 local sources instead of T3
```

### Key Runtime Functions

- `scripts/report/runtime.py::_resolve_front_page_target_candidate`
  chooses/stores `current_core_candidate` and `selected_position_candidate`.
- `scripts/report/runtime.py::_resolve_runtime_current_core_candidate`
  ranks candidates from current context, data, snapshot, selected candidate,
  and extreme conviction lists.
- `scripts/report/runtime.py::_build_runtime_final_target_resolution`
  builds final target fields such as `new_entry_target`, `display_target`, and
  `watch_target`.
- `scripts/report/runtime.py::_store_runtime_final_target_resolution`
  writes the final resolution into data, execution context, and market snapshot.
- `scripts/report/runtime.py::_runtime_selected_target_solution_lines`
  renders the current front-page target explanation.
- `scripts/domains/execution_chain/pk_decision_nodes/candidate_quality_scorecard.py::build_candidate_quality_scorecard_payload`
  can consume prebuilt panel fields or local `best_stock` / `watch_anchor`.

### Root Cause

The existing system has several candidate sources that can each look like the
final target:

- local process candidate: `best_stock`, `watch_anchor`, `candidate_quality_panel_fields`,
- runtime selected/current core: `selected_position_candidate`, `current_core_candidate`,
- final resolution: `final_target_resolution.watch_target`.

Some final-action renderers consume the final resolution, while others still
consume local process sources or stale prebuilt fields. That creates the
appearance that each step makes its own independent trading judgment.

### Recommended Fix

Create one canonical `sniper_target_derivation.v1` packet:

- build it after `final_target_resolution` exists,
- store it in data, execution context, and market research snapshot,
- have all final-action renderers consume it,
- render compact ASCII on the front page and full ASCII in the appendix,
- mark non-final candidates as process/source nodes with explicit decisions
  such as `过程候选`, `被替换`, `备选观察`, or `仅过程证据`.

### Test Implications

At minimum, tests should cover:

- local source says 上海石化 but canonical target says 豫能控股,
- front page final target solution uses only 豫能控股 as final target,
- candidate-quality panel does not render 上海石化 as final object,
- appendix observation anchor uses canonical target,
- full replay for 2026-06-04 shows compact/full ASCII chain and keeps
  豫能控股 as the only final observation target.
