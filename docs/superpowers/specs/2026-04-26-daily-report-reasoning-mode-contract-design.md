# Daily Report Reasoning Mode Contract Design

Date: 2026-04-26
Scope: `a-daily-report` skill, report contract, and future reasoning-decision workflow
Status: Draft for user review
Baseline: `e17d86b inherit report contract for future changes`

## 1. Problem

Reasoning models changed the useful shape of this skill. The daily report should not only assemble data; it should use stronger model judgment for questions such as:

1. 今天到底做不做？
2. 主线是在增强、分歧、退潮，还是不明？
3. 为什么没有唯一标的？
4. 候选股为什么只观察、不执行？
5. 10点确认、60分钟确认、30分钟止损之间有没有矛盾？

But the report cannot become a free-form model essay. If a model directly rewrites the report every time, the same input can produce drifting wording, drifting criteria, and hard-to-review decisions.

The right target is therefore not "let the model write the report." The target is:

> code owns deterministic facts; reasoning mode owns bounded decisions; the report contract owns the guardrails; audit owns verification.

## 2. Chosen Direction

Use a no-API first `2.5` design.

The first implementation should create the structure for reasoning decisions without requiring a model API:

```text
deterministic snapshot
  -> reasoning input packet
  -> reasoning decision JSON
  -> deterministic validator
  -> replay cache
  -> report renderer
  -> report acceptance audit
```

In the first version, the reasoning decision can be produced by the current conversation, a fixture, or a deterministic fallback. Later, an API-backed reasoning model can fill the same JSON schema without changing the renderer or audit contract.

## 3. Non-Goals

This design does not:

1. call OpenAI, DeepSeek, or any third-party model API during report generation;
2. expose full chain-of-thought in the daily report;
3. let a model write the final report body directly;
4. replace deterministic data calculations such as涨跌幅、成交额占比、历史对比;
5. make daily output random or dependent on hidden conversation state;
6. build a general prompt platform.

## 4. Reasoning Boundaries

### 4.1 Deterministic Code Owns

Code remains responsible for:

1. market and stock snapshots;
2.涨跌幅、成交额、主线占比、历史占比变化;
3. candidate pools and source status;
4. 60分钟确认条件 and 30分钟止损 fields when already computable;
5. replay artifact generation;
6. schema validation and audit failures.

### 4.2 Reasoning Mode Owns

Reasoning mode is allowed to decide:

1. `action`: `do_nothing`, `observe`, or `conditional_entry`;
2. `mainline_state`: `strengthening`, `diverging`, `fading`, or `unclear`;
3. whether a unique target exists;
4. why the chosen target is or is not executable;
5. which candidates are excluded and why;
6. whether execution conditions contradict each other;
7. whether the front-page conclusion reads like a trading decision surface.

### 4.3 Report Output Owns

The report may show:

1. conclusion;
2. key evidence;
3. trigger conditions;
4. failure conditions;
5. excluded-candidate reasons;
6. confidence label.

The report must not show hidden chain-of-thought or long draft reasoning.

## 5. Reasoning Input Packet

The reasoning layer receives a small structured packet, not raw report prose.

Required packet fields:

```json
{
  "target_date": "2026-04-24",
  "market_base": {},
  "mainline_snapshot": {},
  "turnover_share_history": [],
  "candidate_pool": [],
  "execution_contract": {},
  "risk_context": {},
  "source_status": {}
}
```

Rules:

1. Every candidate must include a stable `id` such as stock code.
2. Evidence-bearing fields must be named, not embedded only in prose.
3. Missing data must be explicit through `source_status`.
4. The input packet should be serializable and hashable.
5. The packet should be small enough for a reasoning model to inspect without reading appendices.

## 6. Decision JSON

The reasoning decision is the only object that crosses from reasoning into rendering.

Schema shape:

```json
{
  "schema_version": "reasoning_decision.v1",
  "target_date": "2026-04-24",
  "input_hash": "sha256...",
  "prompt_version": "manual-current-conversation-v1",
  "model_source": "manual | deterministic_fallback | api",
  "action": "do_nothing | observe | conditional_entry",
  "mainline_state": "strengthening | diverging | fading | unclear",
  "unique_target": null,
  "conclusion": "主线未给出可执行唯一对象，明天只观察承接。",
  "evidence": [
    {
      "field": "mainline_snapshot.relationship",
      "summary": "周期主线与当天主攻线未形成稳定共振"
    }
  ],
  "trigger_conditions": [
    "10点后主线继续放量",
    "候选股完成60分钟确认"
  ],
  "failure_conditions": [
    "主线回落",
    "候选股承接失败"
  ],
  "excluded_candidates": [
    {
      "id": "300613",
      "name": "富瀚微",
      "reason": "承接与60分钟确认未同时满足"
    }
  ],
  "confidence": "high | medium | low"
}
```

Rules:

1. `unique_target` must be null when action is `do_nothing`.
2. `conditional_entry` must include trigger and failure conditions.
3. Evidence must reference fields present in the input packet.
4. Excluded candidates must come from the candidate pool.
5. Low confidence should degrade to `observe` or `do_nothing` unless the latest user instruction explicitly overrides it.

## 7. Validator And Audit

The validator checks the decision object before rendering.

Required checks:

1. schema version is supported;
2. `target_date` matches the input packet;
3. `input_hash` matches the input packet;
4. action is compatible with unique target;
5. evidence references known input fields;
6. excluded candidates exist in the packet;
7. conditional entry has trigger and failure conditions;
8. low-confidence decisions do not create aggressive actions;
9. missing or degraded data does not become fake certainty.

The report acceptance audit should then check rendered markdown for the existing contract:

1. conclusion-first;
2. 10点确认;
3. 60分钟确认;
4. 30分钟结构止损;
5. no hard-forced unique target;
6. no fake `0.00%`;
7. no duplicate no-trade conclusion.

## 8. Replay Cache

Reasoning output should be replayable.

Cache key:

```text
target_date + input_hash + schema_version + prompt_version + model_source
```

Cache record:

```json
{
  "created_at": "2026-04-26T00:00:00+08:00",
  "target_date": "2026-04-24",
  "input_hash": "sha256...",
  "schema_version": "reasoning_decision.v1",
  "prompt_version": "manual-current-conversation-v1",
  "model_source": "manual",
  "decision": {}
}
```

Rules:

1. Replay should reuse the cached decision when input hash is unchanged.
2. Changed input should create a new decision record.
3. The report should be able to show whether a decision came from manual current-conversation reasoning, deterministic fallback, or API reasoning.
4. Cache records are evidence artifacts, not user-facing report prose.

## 9. API Path Later

When the structure is stable, API-backed reasoning can be added behind the same contract.

API integration must:

1. send only the reasoning input packet;
2. request only the decision JSON schema;
3. record model name, reasoning effort, prompt version, and input hash;
4. validate before rendering;
5. fall back to cached/manual/deterministic decision on validation failure;
6. never let a model write the final report body directly.

This keeps API reasoning useful without turning the report into a black box.

## 10. User Workflow

### 10.1 Current Conversation Workflow

The user can ask:

```text
基于今天的 snapshot，用推理模式给我一个 reasoning decision JSON。
```

The agent can then produce a decision JSON that the code validates, caches, and renders.

### 10.2 Script Workflow Without API

The report script can run with:

1. deterministic fallback decision;
2. a cached/manual decision artifact;
3. validation and audit.

This gives stable output before automatic reasoning exists.

### 10.3 Future Script Workflow With API

The report script can later call a reasoning model to fill the same JSON. The output path remains unchanged.

## 11. Testing Strategy

The first implementation should use TDD around contract behavior:

1. input packet builder creates stable, hashable packets;
2. validator rejects invalid unique targets;
3. validator rejects evidence fields not present in the packet;
4. validator rejects conditional entry without trigger/failure conditions;
5. renderer shows conclusion, evidence, trigger, failure, and exclusions without chain-of-thought;
6. audit fails if the rendered report violates existing report contract;
7. cache reuses unchanged input and creates a new record for changed input.

## 12. Success Criteria

This design succeeds when:

1. future report changes default inherit both report contract and reasoning contract;
2. reasoning decisions are structured, replayable, and auditable;
3. users can benefit from current-conversation reasoning without API setup;
4. later API integration does not require changing report rendering;
5. the daily report remains stable in form while becoming smarter in judgment.

## 13. Recommended Implementation Plan Shape

After user approval, create a plan with these task slices:

1. add `references/reasoning-mode-contract.md` and route it from `SKILL.md`;
2. add tests that future delta specs inherit the reasoning contract;
3. add reasoning input packet builder;
4. add decision schema and validator;
5. add manual/cache decision artifact support;
6. add renderer integration for front-page decision surface;
7. extend report acceptance audit for reasoning-decision output;
8. run replay verification.
