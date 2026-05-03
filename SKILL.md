---
name: a-daily-report
description: Use when handling natural-language A-share daily-report requests, report-output review, report defect fixes, trade-case reviews, workflow-memory extraction, or skill optimization in this repo.
---

# A Daily Report

This skill is a compact onboarding router for the daily-report repo. Treat the user request as natural-language intent; users do not need to remember commands.

## Intent Routes

| Internal intent | When to choose it | First reference |
|-----------------|-------------------|-----------------|
| `generate_report` | User asks for a daily report, replay, summary, or fresh report artifact. | `references/report-contract.md`, then `references/reasoning-mode-contract.md`, then `references/verification.md` |
| `review_report_output` | User asks whether a report reads correctly, is useful, or matches prior wording preferences. | `references/report-contract.md`, then `references/reasoning-mode-contract.md` |
| `fix_report_defect` | User points to a concrete report bug, duplicated line, fake zero, missing action contract, broken replay, or a delta spec for report behavior. | `references/report-contract.md`, then `references/reasoning-mode-contract.md`, then `references/verification.md` |
| `review_trade_case` | User asks whether to buy, wait, cut, or review a specific stock or setup. | `references/report-contract.md` |
| `extract_workflow_memory` | User asks to preserve repeated workflow lessons, preferences, or report-quality defects for future agents. | `references/memory-governance.md` |
| `optimize_skill` | User asks to improve this skill, routing, references, the report contract, or the report workflow. | `references/report-contract.md`, then `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md`, then `references/reasoning-mode-contract.md`, then `references/memory-governance.md`, then `references/verification.md` |

## Priority Order

When the user gives broad optimization direction, preserve this order unless the latest user instruction narrows scope:

1. report acceptance audit
2. structured history
3. only-focus audit
4. entry-cycle calibration
5. workflow memory
6. skill refactor

## Operating Rules

- Prefer report usefulness over process ceremony: first make the output auditable, actionable, and honest.
- Treat future report-change requests as a delta spec: default inherit `references/report-contract.md` unless the latest user instruction explicitly overrides it.
- Treat reasoning as bounded decision support: future report changes inherit both report contract and reasoning contract unless the latest user instruction explicitly overrides them.
- Treat external simulations and free-form predictions as anti-noise boundary risks: they do not enter the report main chain unless a later approved spec turns them into auditable fields. Trading experience can be absorbed only after being translated into price-action fields such as `上涨斜率`, `回撤比例`, `突破后承接`, and `加速后衰竭`.
- Keep command details out of this file. Load `references/verification.md` only when concrete checks are needed.
- For defects, write or update a focused test first, then verify against replay markdown when the output surface matters.
- For memory extraction, create reviewable artifacts only. Do not auto-apply memory or build a memory platform.
- Latest user instruction overrides older memory, older plans, and this router.

## References

- `references/report-contract.md` - report acceptance, user-facing wording, trade-case boundaries.
- `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md` - anti-noise boundary for simulation tools and price-action fieldization.
- `references/reasoning-mode-contract.md` - no-API first reasoning decision JSON, boundaries, and no chain-of-thought output.
- `references/memory-governance.md` - review-artifact memory rules and safety boundaries.
- `references/verification.md` - practical replay, audit, unittest, and diff checks.
