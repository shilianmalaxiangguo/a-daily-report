# infer.market_phase

## Purpose

Translate normalized market facts into a structured market phase judgment.

## Requires

- `normalized.market_snapshot`

## Provides

- `derived.market_phase`
- `diagnostics.derivations.market_phase`

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

