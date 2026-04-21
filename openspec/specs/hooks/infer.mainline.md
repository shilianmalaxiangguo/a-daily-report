# infer.mainline

## Purpose

Translate normalized and derived facts into the mainline judgment.

## Requires

- `normalized.market_snapshot`
- `derived.market_phase`

## Provides

- `derived.mainline`
- `diagnostics.derivations.mainline`

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

