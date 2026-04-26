# Reasoning Mode Contract

This reference is for bounded daily-report reasoning. It is not a prompt manual and not an API integration guide.

## Core Contract

- Use no-API first: current-conversation reasoning or deterministic artifacts may produce a reasoning decision JSON.
- Code owns deterministic facts: market snapshots, candidate pools, turnover share, source status, and replay artifacts.
- Reasoning mode owns bounded decisions: action, mainline state, unique target judgment, trigger conditions, failure conditions, exclusion reasons, and confidence.
- Reasoning must run at `reasoning_effort = xhigh`; this is the reasoning depth, not the trade-confidence label.
- The report renderer owns expression: it shows only conclusion, evidence, triggers, failures, exclusions, and reasoning effort.
- do not expose chain-of-thought, hidden reasoning traces, or long draft reasoning in the daily report.

## Decision Boundary

The only object allowed to cross from reasoning into report rendering is `reasoning_decision.v1`.

Required fields:

- `schema_version`
- `target_date`
- `input_hash`
- `prompt_version`
- `reasoning_effort`
- `model_source`
- `action`
- `mainline_state`
- `unique_target`
- `conclusion`
- `evidence`
- `trigger_conditions`
- `failure_conditions`
- `excluded_candidates`
- `confidence`

## Safety Rules

- Evidence must point to fields from the reasoning input packet.
- `reasoning_effort` must be `xhigh`.
- A unique target must come from the candidate pool.
- `conditional_entry` must include trigger and failure conditions.
- Low confidence cannot create an aggressive action.
- Missing or degraded data must not become fake certainty.
- API-backed reasoning may be added later, but it must fill the same JSON and pass the same validator before rendering.
