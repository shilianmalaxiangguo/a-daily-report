---
name: a-daily-report
description: Handle A-share daily reports and the current small-cap rotation strategy with dated facts and protected history.
---

# A Daily Report

Users do not need to remember commands. Read `wiki/README.md` first, then only the pages needed for the current task.

## Current scope

- Small-cap rotation v0.3 is the only active strategy: five names plus three backups, every twenty sessions from the unchanged 2024-07-01 calendar anchor, main board and ChiNext, 10% take-profit at the next sellable open, cash waits for the next rotation, account floor 0.7 of initial capital.
- The user's commission is 0.01% of turnover with no minimum. Never substitute a five-yuan minimum. Transfer fee and sell-side stamp duty are separate.
- Current evaluation uses 2025-02-28 through 2026-10-29. Earlier research is historical material, not a second current ranking.
- Build and display the frozen small-cap plan independently. Do not collect or render the old alpha/beta board, candidate buy checks, five-day advice reconciliation, model-vote interpretation, or old daily multi-strategy comparison. Preserve the Alpha/Beta algorithms, inputs and backtest evidence for explicit research runs; they are not a second daily strategy.
- A missing current plan stays missing; do not fall back to an old trading suggestion.
- The daily whole-lot table restarts from 10,000 yuan per period. It is an illustration, not a continuous account or actual holdings. Verify original buy prices and real cash before account-specific actions.
- The standalone continuous account simulation still differs in its backup range and unimplemented floor-sale process. Disclose these limits.
- The sector diffusion tournament is historical observation material, lacking a complete twenty-month executable record. Do not invent a return series or silently add it to small-cap selection or timing.
- Base market and sector charts remain chart-first factual background. A sector page is not a rule that all opportunities must begin from a sector.
- Only desktop reports are maintained. Do not restore phone layouts or phone viewport acceptance from archived instructions.

## Facts and history

Preserve fact date, announcement availability, retrieval date, sample, units and source identity. Missing is not zero. Turnover is not net inflow. A plan or simulated gain is not an actual fill. No account input does not mean cash-only.

Official reports and snapshots are read-only historical records. Replay reads exactly the selected official or replay snapshot offline; repairs write separate replay artifacts. Never use current news, membership or current quotes to fill an unverified historical date.

`full` only locates historical originals; `short` is stopped. Historical code and tests are not permission to restore retired trading rules. Alpha/Beta research is opt-in and never selected by the small-cap entry.

## Intent routes

| Intent | First reference |
|---|---|
| generate_report | wiki/README.md, references/report-contract.md, references/verification.md |
| review_report_output | references/report-contract.md and current strategy evidence |
| fix_report_defect | references/report-contract.md and the responsible loader/renderer |
| review_trade_case | wiki/交易思想/小盘轮换策略.md and supplied account facts |
| extract_workflow_memory | references/memory-governance.md |
| optimize_skill | this file and the current Wiki |

All Python commands use `.generated/venv-py314/bin/python3.14`. Verify only the affected scope, run offline replay for output changes, protect official hashes, and complete independent review before committing. Tests verify implementation, not future profitability.
