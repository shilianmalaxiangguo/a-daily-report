# Report Contract

This reference is for report quality judgment. It is not a command manual.

## User-Facing Contract

- Say the conclusion first, then explain why.
- Keep the front page usable within two minutes.
- Make the action contract explicit: what to do, what confirms it, and what to do when conditions fail.
- Treat replay markdown as the acceptance surface for report-output defects.
- Do not hide missing data behind fake precision such as `0.00%`.
- Do not repeat empty-position or no-trade conclusions.

## Future Change Inheritance

- Future daily-report requests use a delta spec by default: describe only the new or changed behavior.
- New requests default inherit this report contract unless the latest user instruction explicitly overrides it.
- Future report changes inherit both report contract and reasoning contract unless the latest user instruction explicitly overrides them.
- In practice, new report requests do not need to restate existing guardrails.

## Optimization Order

Use this order for broad report optimization:

1. report acceptance audit
2. structured history
3. only-focus audit
4. entry-cycle calibration
5. workflow memory
6. skill refactor

Workflow memory belongs after report acceptance, structured continuity, only-focus reasoning, and entry-cycle calibration are working well enough to preserve.

## Intent Notes

- `generate_report`: produce or replay the report artifact, then inspect whether the result reads like a trading decision surface.
- `review_report_output`: audit the generated markdown before trusting unit tests alone.
- `fix_report_defect`: isolate the visible defect, add a narrow test, patch the smallest responsible surface, and rerun replay/audit checks.
- `review_trade_case`: honor current position details, cost basis, account size, and the user's chosen trading frame. Do not convert workflow memory into stock observation continuity.
