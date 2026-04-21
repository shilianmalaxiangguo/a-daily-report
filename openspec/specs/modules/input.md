# Input Module

## Purpose

Collect external data and apply minimal normalization.

## Responsibilities

- Fetch source payloads from market and calendar interfaces.
- Normalize facts into `raw` and `normalized` context slices.
- Keep the module free of business judgments.

## Boundaries

- May read external APIs and local caches.
- Must not write `derived`, `decision`, `sections`, or `rendered`.

