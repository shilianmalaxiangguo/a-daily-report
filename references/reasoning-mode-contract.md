# Reasoning Mode Contract

Updated: 2026-10-22. This file describes the boundary between current reading and the old reasoning implementation.

## Current reading

The default sector reading path uses dated facts. It does not call a model, construct an account decision, choose one mandatory target, or require a particular model/reasoning depth. A human-requested interpretation may be explicit, but must distinguish facts, alternatives, costs, unknowns, and the user's decision. Do not expose private reasoning traces.

The current Wiki governs trading ideas. Do not impose a trend chain, sector-first sequence, fixed confirmation period, fixed sizing, or old account prescription through a reasoning schema.

## Historical implementation

`reasoning_decision.v1` and its validator still belong to the explicit full-report compatibility chain. Required schema fields describe that implementation, not the current trading philosophy. Do not populate them merely to make a sector reading page pass, and do not treat a valid historical schema as proof of profitability or a current instruction.

## Multiple samples

The user favors simple repeated comparisons and feedback. Agreement among model outputs is an agreement ratio, not a market probability or a position size. A shared factual error cannot be voted away. No new sampling program or model/provider requirement is authorized by this document.
