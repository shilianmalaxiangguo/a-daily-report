---
name: a-daily-report
description: Generate and review the desktop small-cap rotation report using dated facts; preserve Alpha/Beta as explicit backup research.
---

# A Daily Report

Read README.md, docs/structure.md and wiki/README.md first. Small-cap rotation v0.3 is the only daily strategy. Full rules and implementation limits are in the current Wiki.

Use `.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py <date> --replay` for historical reading. Select exactly one snapshot source: official, replay, or rebuilt. Missing or invalid current facts stop generation. Never invoke retired code or infer an account from an old report.

The current report collects only prices, calendar, financial growth, stock metadata, target-date ST, comparison indices and dated price limits/suspensions for forward tracking. No sector pipeline, tournament, model interpretation, old position workflow or database is needed. Alpha/Beta runs only through scripts/alpha_beta_research.py and cannot change small-cap execution.

Commission is 0.01% with no minimum; tax and transfer fee are separate. Five names plus three backups, twenty sessions, 10% take-profit with delayed sellable open, cash waits until rotation, initial-capital floor 0.7. From 2026-11-02 the daily report tracks five user-fixed names with equal 20% budgets and fractional units; NAV is 1 before initial purchase fees. Carry basis, cash and pending sales forward; missing preceding trading-day records stop generation. Hide the former period-reset whole-lot demo and fresh-entry ranking on tracking pages. See docs/small-cap-tracking.md. Distinguish this new forward model from actual trades and older backtests whose disclosed differences remain.

Desktop only. Do not restore phone layouts or phone-window acceptance. Historical reports, snapshots and raw inputs remain read-only. Archive instructions are historical evidence, never current requirements.

Use references/report-contract.md and references/verification.md for output and verification. No external posting or messaging is part of this skill. Independent review precedes commits; publish only the authorized cleanup to develop.
