# brainstorm: sniper target derivation chain

## Goal

Fix the historical daily-report bug where the sniper perspective can render
different target identities in different sections because candidate selection,
quality scoring, final target resolution, front-page rendering, and appendix
process evidence each make local decisions. The report must expose one complete
target-derivation chain, preferably as an ASCII flow, so every target shown in
the final action surface can be traced to its source, role, decision, and
handoff.

## What I already know

* The user observed `上海石化` and `豫能控股` appearing as different "final" or
  observation objects across the same report.
* This is a real bug class, not merely a trading disagreement: multiple report
  modules consume different candidate sources without one visible authority
  record.
* `上海石化` can come from local process-evidence sources such as `best_stock`,
  `watch_anchor`, or prebuilt `candidate_quality_panel_fields`.
* `豫能控股` can come from the later runtime target resolution path:
  `_resolve_front_page_target_candidate(...)` ->
  `_build_runtime_final_target_resolution(...)` ->
  `final_target_resolution.watch_target`.
* Yesterday's fix aligned several renderers to prefer
  `final_target_resolution.watch_target`, but it did not create a complete
  derivation-chain contract.
* Existing spec already expects an ASCII `狙击手最终标的路径图`, but the runtime
  does not yet make every handoff and winner/loser reason visible as one
  auditable chain.

## Assumptions (temporary)

* The desired authority model is not "each section chooses its own best stock";
  it is one resolved target packet that all final/action-facing sections must
  consume.
* Process tables may still show other candidates such as 上海石化, but they must
  be clearly labeled as source pool / rejected / backup / process evidence and
  must not masquerade as the final observation target.
* The primary MVP should repair the target-chain contract before optimizing
  prose or broad candidate ranking logic.

## Open Questions

* None currently blocking.

## Requirements (evolving)

* MVP authority model: enforce one canonical final target for all final-action
  surfaces.
* Build or normalize one canonical target-derivation packet for the daily report.
* Packet must carry every handoff: raw candidate source, source rank, candidate
  identity, role, anchor-reversal decision, account/position decision, final
  action role, and why it won/lost.
* Final-action sections must consume the canonical packet instead of independently
  reselecting from stale `best_stock`, `watch_anchor`, ledger fallback, or
  process panel fields.
* Process-evidence tables may retain non-final candidates only as chain nodes:
  source candidate, rejected candidate, backup observation, or process evidence.
  They must not render like the final observation target.
* The report should render a compact ASCII chain before long explanatory text.
* Render depth decision: front page shows a compact derivation chain; appendix
  shows the full derivation chain with all process candidates and handoff fields.
* Any mismatch between final target and process-evidence target should become an
  explicit warning/test failure, not a silent render correction.
* The ASCII chain should be the primary explanation surface. Long prose may
  follow only as supporting notes, not as the main way to explain the target.

## Acceptance Criteria (evolving)

* [ ] A report fixture with `best_stock/watch_anchor = 上海石化` and
  `final_target_resolution.watch_target = 豫能控股` renders one final target:
  `豫能控股`, while 上海石化 appears only as process evidence or rejected/alternate
  if present.
* [ ] The report includes an ASCII derivation chain that identifies each step and
  each source value used to reach the final target.
* [ ] The front page includes a compact ASCII chain before or adjacent to the
  final target explanation.
* [ ] The appendix includes the full ASCII chain, including non-final candidates
  and why they did not become the canonical target.
* [ ] Candidate-quality panel, final decision panel, front page account advice,
  appendix observation anchor, and daily judgment panel all consume the same
  canonical target identity.
* [ ] 上海石化-like non-final candidates can appear only under process/source
  nodes with labels such as `过程候选`, `被替换`, `备选观察`, or `仅过程证据`.
* [ ] If a renderer receives a stale target that conflicts with the canonical
  packet, tests assert it is either rewritten with an explicit source note or
  excluded from final-action surfaces.
* [ ] Historical replay for `2026-06-04 --replay` keeps `豫能控股(001896)` as the
  observation target and shows where 上海石化 entered the process pool if present.

## Definition of Done (team quality bar)

* Tests added/updated for runtime, front-page renderer, candidate-quality
  renderer, and report acceptance/audit where appropriate.
* Python commands use `.generated/venv-py314/bin/python3.14`.
* Fresh focused tests and `git diff --check` pass.
* Replay output checked for the target-date sample.
* `.trellis/spec/` updated with the new target-derivation-chain contract.
* Implementation done through `trellis-start` Phase 2 with subagents, after this
  PRD is confirmed and context files are curated.

## Out of Scope (explicit)

* Re-ranking the entire stock-selection algorithm.
* Replacing all candidate scoring modules.
* Editing generated reports as the fix.
* Introducing new live data sources.
* Hiding process candidates that are useful for audit; they should be relabeled,
  not silently erased.

## Expansion Sweep

### Future evolution

* The canonical target packet can later feed structured decision-ledger rows and
  replay audits.
* The same packet can support a visual renderer, but the current task should
  keep ASCII output as the durable text contract.

### Related scenarios

* Front page, action plan, candidate-quality process evidence, daily judgment
  panel, appendix observation anchor, and report acceptance audit must agree on
  the same final target.
* Final conclusion and legacy summary nodes that still resolve
  `selected_position_candidate` locally should either consume the packet or be
  explicitly marked as process-only.

### Failure and edge cases

* Empty final target: render `暂无` as the canonical final target and keep all
  candidates below it as process evidence.
* Conflicting local sources: render one final target from the packet and mark
  the conflicting source as `被替换` / `过程候选`, with source field and reason.
* Replay historical dates: never refill the chain with current live facts.

## Feasible Approaches

### Approach A: compact front page plus full appendix (chosen)

How:

* Front page renders a short ASCII chain with final target, role, action, and
  main replacement reason.
* Appendix renders the full chain with all source candidates and handoff fields.

Pros:

* User can immediately see the final object.
* Full audit detail remains available without making the first page too long.

Cons:

* Requires two render depths for the same packet.

### Approach B: front page only

How:

* Render one complete ASCII chain on the front page.

Pros:

* The explanation is impossible to miss.

Cons:

* The front page may become too dense when many process candidates exist.

### Approach C: appendix only

How:

* Keep front page very short and put the full ASCII chain in the appendix.

Pros:

* Least disruption to front-page layout.

Cons:

* It is easier to miss the chain when debugging target mismatch.

## Technical Notes

* Relevant runtime functions:
  * `scripts/report/runtime.py::_resolve_front_page_target_candidate`
  * `scripts/report/runtime.py::_resolve_runtime_current_core_candidate`
  * `scripts/report/runtime.py::_build_runtime_final_target_resolution`
  * `scripts/report/runtime.py::_store_runtime_final_target_resolution`
  * `scripts/report/runtime.py::_runtime_selected_target_solution_lines`
  * `scripts/report/runtime.py::_build_daily_judgment_front_panel_lines`
* Relevant panel function:
  * `scripts/domains/execution_chain/pk_decision_nodes/candidate_quality_scorecard.py::build_candidate_quality_scorecard_payload`
* Current observed derivation:

```text
T0 raw/process sources
|
+-- execution_stage_context.best_stock
+-- execution_stage_context.watch_anchor
+-- existing candidate_quality_panel_fields
|   `-- can produce 上海石化 as local/process candidate
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

v
T3 final target resolution
_build_runtime_final_target_resolution(...)
|
+-- new_entry_target = selected_position_candidate/current_core
+-- display_target = old position / proxy / new entry / empty
+-- watch_target = new_entry when old position or proxy blocks direct new entry
    `-- final action-facing observation authority

v
T4 renderers
+-- final target solution panel
+-- front page account advice
+-- daily judgment panel
+-- candidate-quality panel
+-- appendix observation anchor
    `-- historical bug: some T4 renderers read T0 local sources instead of T3
```

* Existing quality spec mentions ASCII path graph and same-identity requirement
  under `.trellis/spec/backend/quality-guidelines.md`.
* Yesterday's task added a partial prevention section to
  `.trellis/spec/backend/daily-report-decision-loop.md`, but this new task needs
  a deeper chain contract.

## Research Notes

### Why 上海石化 and 豫能控股 both appeared

`上海石化` was not necessarily invented by one renderer. It can legitimately
enter from raw/process sources such as `best_stock`, `watch_anchor`, or
prebuilt `candidate_quality_panel_fields`. Those sources are local scoring or
process-evidence surfaces.

`豫能控股` came from the later runtime resolution path after the report selected
or reselected the current core / observation target and then built
`final_target_resolution.watch_target`.

The bug is that the renderers did not all consume the same final packet. Some
renderers read T0/T1 local sources; others read T3 final resolution. That makes
the report feel like each step is judging independently.

### Minimal architecture implication

The durable fix should not be another local "prefer this field" patch. It should
introduce a canonical target-derivation packet and require all final-action
surfaces to read from it. Local process candidates remain visible only below the
chain with a role label.

## Decision (ADR-lite)

**Context**: The same report can currently show one stock from local
process-evidence sources and another from final runtime resolution. This makes
the sniper perspective look like several independent judgments instead of one
auditable flow.

**Decision**: Use one canonical final target packet for the MVP. All final-action
surfaces must consume that packet. Non-final candidates remain visible only as
role-labeled process/source nodes in the ASCII chain or process tables.

**Consequences**: The report becomes stricter and easier to audit. Some previous
process tables will need to stop rendering local `best_stock` / `watch_anchor`
values as final targets. This may expose existing disagreements as explicit
warnings or test failures, which is intended.

## Technical Approach

Create one canonical target-derivation packet and make final-action renderers
consume it.

Proposed packet shape:

```python
{
    "schema_version": "sniper_target_derivation.v1",
    "target_date": "YYYY-MM-DD",
    "canonical_target": {"code": "001896", "name": "豫能控股", "role": "观察锚"},
    "final_action": {"position_pct": 0, "action": "只观察，不新增参与", "reason": "..."},
    "steps": [
        {
            "step_id": "T0",
            "label": "原始候选",
            "source": "execution_stage_context.best_stock",
            "candidate": {"code": "600688", "name": "上海石化"},
            "role": "过程候选",
            "decision": "被替换",
            "reason": "最终解析未选为观察锚",
        },
        {
            "step_id": "T1",
            "label": "当前核心解析",
            "source": "_resolve_front_page_target_candidate",
            "candidate": {"code": "001896", "name": "豫能控股"},
            "role": "当前核心",
            "decision": "保留",
            "reason": "...",
        },
        {
            "step_id": "T3",
            "label": "最终对象解析",
            "source": "final_target_resolution.watch_target",
            "candidate": {"code": "001896", "name": "豫能控股"},
            "role": "观察锚",
            "decision": "最终",
            "reason": "...",
        },
    ],
    "warnings": [],
}
```

Compact front-page rendering:

```text
原始候选
|
+-- 上海石化(600688): 过程候选 / 被替换
|
+-- 豫能控股(001896): 当前核心解析 / 保留
|
`-- 最终观察锚: 豫能控股(001896), 0%只观察
```

Full appendix rendering:

```text
T0 原始候选
|-- source=best_stock          上海石化(600688) role=过程候选 decision=被替换
|-- source=watch_anchor        上海石化(600688) role=过程候选 decision=被替换
|
T1 当前核心解析
|-- source=_resolve_front_page_target_candidate 豫能控股(001896) decision=保留
|
T2 仓位/账户修正
|-- position_pct=0 action=只观察，不新增参与 reason=...
|
T3 最终对象解析
`-- canonical_target=豫能控股(001896) role=观察锚
```

## Implementation Plan (small PRs)

* PR1: Add canonical target-derivation packet builder and focused unit tests.
* PR2: Wire front page, final target solution, candidate-quality panel, daily
  judgment panel, and appendix observation anchor to consume the packet.
* PR3: Render compact/full ASCII chains and add acceptance/replay checks.
* PR4: Update `.trellis/spec/` with `sniper_target_derivation.v1` contract and
  add report-audit checks for mismatched final targets.
