# A Daily Report Hook Refactor Design

Date: 2026-04-21
Scope: `a-daily-report`
Status: Proposed and user-aligned

## 1. Problem Statement

The current implementation concentrates data fetching, normalization, inference, execution gating, markdown generation, persistence, and runtime logging inside a single oversized entry file:

- `scripts/daily_report_entry_demo.py`

This creates four major problems:

1. The execution chain is too long for humans and AI to hold in context reliably.
2. Module boundaries exist only partially, then get re-coupled through a giant shared dictionary.
3. Replacing one data source or one decision rule risks breaking unrelated parts of the pipeline.
4. Runtime failures are not isolated cleanly enough for fast root-cause location.

The target architecture must feel like building blocks: each unit should be replaceable, testable, and traceable without understanding the whole system.

## 2. Goals

### Primary goals

1. Refactor the skill from monolithic orchestration to composable Python hooks.
2. Make the decision chain behave like a math derivation:
   `facts -> inference -> verdict -> report`.
3. Make each smallest replaceable unit independently testable and observable.
4. Introduce OpenSpec as the contract layer that defines how modules must behave.
5. Preserve existing business capability while enabling gradual migration.

### Secondary goals

1. Improve AI maintainability by reducing file size and narrowing context windows.
2. Improve fault localization through standardized trace events and per-hook diagnostics.
3. Allow selective migration and mixed legacy/new execution during transition.

## 3. Non-Goals

1. Do not fully rewrite the skill in one pass.
2. Do not change the trading philosophy, report intent, or decision framework during architectural refactor.
3. Do not migrate the core implementation to JavaScript or TypeScript.
4. Do not require every existing helper to become a hook immediately.

## 4. Language Decision

The core system remains Python.

Reasons:

1. The current codebase, data adapters, and A-share ecosystem already live in Python.
2. Existing dependencies such as `akshare`, `finshare`, pandas-based transformations, and current scripts are Python-native.
3. Mixing Python and JavaScript inside one skill would increase debugging and maintenance cost.
4. The user's real goal is not to read every implementation detail, but to gain replaceability, traceability, and maintainability.

Rule:

- Inside this skill, core execution stays single-language Python.
- Cross-skill integration may be language-agnostic, but must cross stable protocol boundaries such as CLI JSON, file JSON, or HTTP JSON.

## 5. Core Design Principles

1. Single responsibility per hook.
2. Explicit contracts over implicit conventions.
3. Pure input/output where possible; shared mutable state where unavoidable must be tightly constrained.
4. Derived conclusions must be explainable from upstream facts.
5. Rendering must consume decisions, not recompute them.
6. Persistence must never participate in decision logic.
7. Traceability is a first-class system capability, not an afterthought.

## 6. Target Architecture

The target system is organized into three layers:

1. `OpenSpec contracts`
2. `Thin orchestrator`
3. `Composable module hooks`

Execution shape:

```text
OpenSpec Contracts
  -> Orchestrator
    -> Input
    -> Inference
    -> Report
    -> Persist

Cross-cutting:
Trace / Log / Diagnostics
```

High-level pipeline:

```text
Source Facts
-> Market Snapshot
-> Market Phase
-> Mainline Analysis
-> Candidate Evaluation
-> Execution Permission
-> Final Action
-> Report Sections
-> Markdown Document
-> Persistence
```

## 7. Module Model

### 7.1 Input module

Purpose:

- Call external interfaces.
- Collect source data.
- Apply minimal normalization.
- Never make business judgments.

Typical hooks:

- `input.indices`
- `input.turnover`
- `input.hot_rank`
- `input.limit_pools`
- `input.sector_flow`
- `input.calendar`
- `input.lhb`

Writes only:

- `ctx.raw`
- `ctx.normalized`

### 7.2 Inference module

Purpose:

- Convert facts into structured intermediate conclusions.
- Behave like a math derivation chain.
- Produce business judgments, but not report formatting.

Typical hooks:

- `infer.market_phase`
- `infer.mainline`
- `infer.candidate_pool`
- `infer.abnormal_watch`
- `infer.execution_permission`
- `infer.exit_rules`
- `infer.final_action`

Writes only:

- `ctx.derived`
- `ctx.decision`

### 7.3 Report module

Purpose:

- Build report sections from already derived conclusions.
- Never re-run domain reasoning.

Typical hooks:

- `report.preamble`
- `report.environment`
- `report.observation`
- `report.execution`
- `report.review`
- `report.summary`
- `report.markdown_document`

Writes only:

- `ctx.sections`
- `ctx.rendered`

### 7.4 Persist module

Purpose:

- Save markdown, snapshots, ledgers, replay artifacts, and factor snapshots.
- Never change business decisions.

Typical hooks:

- `persist.report_output`
- `persist.snapshot`
- `persist.factor_snapshot`
- `persist.ledger`

### 7.5 Trace module

Purpose:

- Record every meaningful step in a consistent machine-readable way.
- Support fast debugging and AI-assisted root-cause tracing.

Typical trace events:

- `trace.start_run`
- `trace.before_hook`
- `trace.after_hook`
- `trace.on_warning`
- `trace.on_error`
- `trace.finish_run`

## 8. Hook Contract

Each hook is a smallest replaceable unit. It is more than a helper function: it is a contract-bound module.

### 8.1 Interface

```python
class HookResult(TypedDict):
    value: dict
    patches: dict
    diagnostics: dict
    artifacts: dict

class ReportHook(Protocol):
    name: str
    requires: list[str]
    provides: list[str]

    def run(self, ctx: "ReportContext") -> HookResult: ...
```

### 8.2 Contract rules

Each hook must define:

1. `purpose`
2. `requires`
3. `provides`
4. `forbidden_reads`
5. `failure_policy`
6. `diagnostics_fields`
7. `fixture_examples`

Each hook should remain small enough to understand in isolation. A preferred target size is roughly `150-300` lines. If a hook grows beyond that because it is doing multiple jobs, it should be split further.

## 9. Context Model

The system may still share a top-level execution context, but it must be partitioned and controlled.

```python
class ReportContext(TypedDict):
    request: dict
    raw: dict
    normalized: dict
    derived: dict
    decision: dict
    sections: dict
    rendered: dict
    diagnostics: dict
    runtime: dict
```

Field meanings:

- `request`: run parameters such as date, mode, output variants
- `raw`: untouched source results
- `normalized`: source data mapped into internal schema
- `derived`: intermediate inference outputs
- `decision`: final actionable conclusions
- `sections`: section-level report content
- `rendered`: final output artifacts such as markdown strings
- `diagnostics`: run-level warnings, confidence, missing fields, fallback usage
- `runtime`: timers, mode flags, cache hits, execution metadata

Hard rule:

- Hooks may only write into declared contract zones.
- No hook may silently mutate unrelated zones.

## 10. Derivation Model

To make the system behave like solving a math problem, every important inference hook should emit an explicit derivation record.

```python
class DerivationRecord(TypedDict):
    hook_name: str
    inputs: list[str]
    assumptions: list[str]
    formula: str
    output_keys: list[str]
    confidence: float
    warnings: list[str]
```

Example reasoning chain:

```text
final_action = watch_only
<- execution_permission = watch_only
<- market_phase = defend
<- turnover weak + breadth weak + zhongshu not open
```

Benefits:

1. Easier AI debugging
2. Easier human explanation
3. Easier replay comparison
4. Easier threshold tuning without hidden side effects

## 11. OpenSpec Role

OpenSpec is not a replacement for the runtime architecture. It is the contract system that governs the architecture.

OpenSpec should manage three levels:

### 11.1 System specs

- `pipeline-overview`
- `context-model`
- `error-handling`
- `observability`

### 11.2 Module family specs

- `input`
- `inference`
- `report`
- `persist`
- `trace`

### 11.3 Critical hook specs

At minimum:

- `infer.market_phase`
- `infer.mainline`
- `infer.execution_permission`
- `report.markdown_document`

Each critical hook spec must state:

1. Purpose
2. Inputs
3. Outputs
4. Forbidden dependencies
5. Failure and fallback policy
6. Diagnostics fields
7. Fixture examples

## 12. Recommended Directory Structure

To minimize migration shock, the first refactor stage should stay under the existing `scripts/` tree instead of forcing an immediate `src/` conversion.

```text
scripts/
  orchestrator/
    report_orchestrator.py
    hook_registry.py
    context_store.py
    pipeline_runner.py

  hooks/
    input/
      use_indices.py
      use_turnover.py
      use_limit_pools.py
      use_hot_rank.py
      use_sector_fund_flow.py
    normalize/
      use_market_snapshot.py
      use_stock_meta_map.py
    infer/
      use_market_phase.py
      use_mainline_analysis.py
      use_candidate_pool.py
      use_abnormal_watch_pool.py
      use_execution_permission.py
      use_exit_rules.py
      use_final_action.py
    report/
      use_report_preamble.py
      use_environment_section.py
      use_observation_section.py
      use_execution_section.py
      use_review_section.py
      use_markdown_document.py
    persist/
      use_snapshot_persistence.py
      use_factor_snapshot.py
      use_strategy_ledger.py
    trace/
      trace_runtime.py
      trace_events.py

  contracts/
    report_request.py
    report_context.py
    hook_result.py
    derivation_record.py
    schemas.py

  adapters/
    ths/
    tencent/
    akshare/
    finshare/
    llm/

  legacy/
    daily_report_entry_demo_legacy_bridge.py
```

OpenSpec root:

```text
openspec/
  specs/
    architecture/
      pipeline-overview.md
      context-model.md
      error-handling.md
      observability.md
    modules/
      input.md
      inference.md
      report.md
      persist.md
      trace.md
    hooks/
      infer.market_phase.md
      infer.mainline.md
      infer.execution_permission.md
      report.markdown_document.md
```

## 13. Error Handling and Fallback Policy

The system should stop treating all failures the same.

Every hook must declare one of these failure modes:

1. `fatal`
   The run cannot continue meaningfully.
2. `degradable`
   The run may continue with explicit fallback and lower confidence.
3. `optional`
   The run may continue without the artifact, but the trace must record omission.

Required diagnostics fields:

- `status`
- `duration_ms`
- `source_used`
- `fallback_used`
- `missing_inputs`
- `warnings`
- `confidence`

Required error questions answered by trace:

1. Which hook failed?
2. Which inputs were missing or malformed?
3. Was fallback attempted?
4. May the pipeline continue?
5. Which downstream sections should be skipped or degraded?

## 14. Observability and Trace

The current system already prints progress, but the future system needs structured trace, not only console output.

Recommended event shape:

```python
{
  "run_id": "...",
  "hook": "infer.market_phase",
  "status": "success",
  "started_at": "...",
  "duration_ms": 82,
  "inputs": ["normalized.market_snapshot"],
  "outputs": ["derived.market_phase"],
  "warnings": [],
  "fallback_used": False
}
```

This trace must serve both:

1. Human debugging
2. AI-assisted reasoning and localized repair

## 15. Testing Strategy

Testing must prove equivalence and stability during migration, not just syntax correctness.

### 15.1 Test types

1. Contract tests
   Verify each hook respects `requires`, `provides`, and output schema.

2. Fixture tests
   Feed known input snapshots into one hook and verify deterministic outputs.

3. Golden-day comparison tests
   Re-run historically important dates and compare:
   - source facts
   - key inferences
   - final report sections

4. Trace tests
   Verify each hook emits required trace fields.

5. Legacy parity tests
   During migration, compare legacy and refactored outputs for the same run date.

### 15.2 Golden-day coverage

Maintain a small fixed set of representative market days:

1. strong mainline day
2. divergence day
3. defensive day
4. failed setup day
5. replay or ledger-heavy day

### 15.3 Acceptance standard

A migrated hook is accepted only when:

1. It satisfies its OpenSpec contract.
2. It emits required diagnostics.
3. It passes fixture tests.
4. It does not introduce unexplained regressions on golden-day comparisons.

## 16. Migration Strategy

This refactor should use a strangler-fig migration, not a big-bang rewrite.

### Phase 0: Foundation

1. Establish OpenSpec root specs and hook contracts.
2. Establish trace and diagnostics foundation.
3. Confirm Python-only core strategy.

### Phase 1: Extract trace first

1. Replace scattered print-based runtime logging with trace helpers.
2. Keep business logic unchanged.
3. Gain immediate visibility into step timing and failure locations.

### Phase 2: Extract input hooks

Priority:

1. `use_indices`
2. `use_turnover`
3. `use_limit_pools`
4. `use_hot_rank`

Goal:

- Match legacy facts with isolated modules before changing inference.

### Phase 3: Extract inference hooks

Priority:

1. `infer.market_phase`
2. `infer.mainline`
3. `infer.execution_permission`

Goal:

- Move the most important reasoning out of the monolith while preserving behavior.

### Phase 4: Extract report hooks

1. Convert report sections to consumers of `derived` and `decision`.
2. Remove business re-computation from markdown assembly.

### Phase 5: Extract persist hooks

1. Move snapshot, ledger, and output writing behind contracts.

### Phase 6: Replace entrypoint

1. Keep legacy bridge until mixed runs are stable.
2. Allow selective routing, for example:

```text
infer.market_phase = new
infer.mainline = legacy
infer.execution_permission = new
```

3. Switch the primary orchestrator only after parity confidence is sufficient.

## 17. Initial Module Priority

The first modules that must receive OpenSpec contracts and migration attention are:

1. `trace`
2. `input.hot_rank`
3. `infer.market_phase`
4. `infer.mainline`
5. `infer.execution_permission`
6. `report.markdown_document`

This order gives the highest payoff for maintainability, AI readability, and debugging speed.

## 18. Execution Readiness Notes

The current directory is not a Git repository, so this design can be written locally but cannot be committed until the workspace is placed under Git or linked to an existing repository root.

This is a workflow blocker for the "commit the design doc" step, not for the design itself.

## 19. Summary

The future architecture should not be "a bigger but cleaner file." It should be:

1. Python-only core execution
2. OpenSpec-governed contracts
3. Thin orchestration
4. Hook-based replaceable modules
5. Math-like derivation records
6. Trace-first observability
7. Gradual migration with legacy parity checks

That is the architecture most aligned with the user's goals:

- faster localization
- easier maintenance
- better AI collaboration
- smallest-unit replacement and upgrade

## Implementation Link

- Plan: `docs/superpowers/plans/2026-04-21-a-daily-report-hook-refactor.md`
