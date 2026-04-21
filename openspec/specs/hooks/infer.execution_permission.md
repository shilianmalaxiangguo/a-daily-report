# infer.execution_permission

## Purpose

Decide whether execution is permitted for the current run.

## Requires

- `derived.market_phase`
- `derived.mainline`

## Provides

- `derived.execution_permission`
- `diagnostics.derivations.execution_permission`

## Forbidden Reads

- `sections.*`
- `rendered.*`

## Failure Policy

- degradable

## Diagnostics Fields

- `status`
- `duration_ms`
- `confidence`
- `warnings`

