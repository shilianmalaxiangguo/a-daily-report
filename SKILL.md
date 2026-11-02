---
name: a-daily-report
description: Generate and review the desktop small-cap rotation report using dated facts; preserve Alpha/Beta as explicit backup research.
---

# A Daily Report

Read README.md, docs/structure.md and wiki/README.md first. Small-cap rotation v0.3 is the only daily strategy. Full rules and implementation limits are in the current Wiki.

Use `.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py <date> --replay` for historical reading. Select exactly one snapshot source: official, replay, or rebuilt. Missing or invalid current facts stop generation. Never invoke retired code or infer an account from an old report.

The current report collects only prices, calendar, financial growth, stock metadata, target-date ST and comparison indices. No sector pipeline, tournament, model interpretation, old position workflow or database is needed. Alpha/Beta runs only through scripts/alpha_beta_research.py and cannot change small-cap execution.

Commission is 0.01% with no minimum; tax and transfer fee are separate. Five names plus three backups, twenty sessions, 10% take-profit with delayed sellable open, cash waits until rotation, initial-capital floor 0.7. The daily whole-lot table resets from 10,000 yuan each period; it is neither a continuous account nor actual trades. Disclose the unimplemented continuous floor-sale and backup-range differences.

Desktop only. Do not restore phone layouts or phone-window acceptance. Historical reports, snapshots and raw inputs remain read-only. Archive instructions are historical evidence, never current requirements.

Use references/report-contract.md and references/verification.md for output and verification. No external posting or messaging is part of this skill. Independent review precedes commits; publish only the authorized cleanup to develop.
