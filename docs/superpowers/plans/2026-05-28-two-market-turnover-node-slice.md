# Two-Market Turnover Node Slice Implementation Record

> **For agentic workers:** This record follows the node runtime contract in `docs/superpowers/specs/2026-05-27-daily-report-node-runtime-contract-design.md`. It is intentionally narrow and should be used as a reference for the next market-state node slice.

**Goal:** Make two-market turnover history comparison a replaceable node with stable exports, diagnostics, unit tests, and report visibility.

**Architecture:** Add a local node package under `scripts/domains/market_state/two_market_turnover/`. The node owns comparison state, source diagnostics, and report-ready summary data; existing market overview and market style wrappers reuse the same comparison helper without changing trading semantics.

**Tech Stack:** Python 3.14, `unittest`, existing report node runtime conventions.

---

## In Scope

- Node key: `compare`.
- Stable export: `two_market_turnover_comparison`.
- Existing wrappers preserved:
  - `build_market_trend_sections_contract(...)`
  - `build_market_style_switch_snapshot(...)`
  - `load_recent_market_turnover_history(...)`
- Report surface: the `两市成交额` row now shows prior-day change when history exists.
- Replay/artifact surface: the market overview wrapper now returns `context` and `node_outputs`, so replay builders can preserve structured node output.

## Out of Scope

- No change to turnover thresholds.
- No change to market style decision semantics.
- No data provider rewrite.
- No broad `daily_report_entry_demo.py` orchestration replacement.

## Done Definition

- `tests.test_two_market_turnover_node_runtime` proves selected-node execution, stable export, diagnostics, and missing-history behavior.
- `tests.test_market_overview_builder` proves the report row exposes history comparison and still supports selected report nodes.
- `tests.test_market_state_support` proves style-switch logic reuses the shared comparison path.
- Existing market overview, market state support, and mainline turnover summary tests remain green.

## Next Slice

The next planned slice remains `mainline_turnover_and_capacity_regime`, using the same pattern:

- isolate the comparison/capacity output first;
- preserve old wrappers;
- expose structured `context` and diagnostics;
- prove report visibility with a focused test before touching broader orchestration.
