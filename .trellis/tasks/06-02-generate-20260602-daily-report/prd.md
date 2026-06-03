# Generate 2026-06-02 Daily Report

## Goal

Generate the 2026-06-02 A-share daily report using the current official report path, compare it against the previous trading day 2026-06-01, and include the user's same-day Huadian Liaoneng T operation: bought 2 lots and sold 2 lots.

## In Scope

- Run the existing daily report entrypoint for `2026-06-02`.
- Pass the position context through the supported `--position` input.
- Produce the report, summaries, evidence appendix, run log, snapshot, and position strategy artifacts that the entrypoint normally emits.
- Verify that the generated report references the 2026-06-01 comparison/review surface and includes the Huadian Liaoneng T operation.

## Out of Scope

- Changing report generation code.
- Rebuilding or overwriting official historical reports for earlier dates.
- Importing historical JSON snapshots into PostgreSQL.
- Publishing snap-ui static data unless explicitly requested.
- Adding new data sources or broadening historical replay behavior.

## Non-goals

- Do not mix future or current-only data into a historical target date.
- Do not hand-edit market facts after generation.
- Do not include unrelated dirty worktree changes in any verification summary.

## Acceptance Criteria

- [x] `reports/2026-06-02_A股日报_完整版.md` or replay fallback equivalent is generated.
- [x] Generated artifacts use `2026-06-01` as the previous trading day comparison/review target.
- [x] The generated report or position strategy artifact includes `华电辽能` and `今日做T买入2手、卖出2手`.
- [x] A matching snapshot is written for `2026-06-02`.
- [x] The report consistency audit command passes for the generated full report.

## Technical Approach

Run:

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-02 --position "华电辽能 做T 买2手 卖2手"
```

Use the default official path because 2026-06-02 has no existing official report or snapshot at task start.

## Verification

- Inspect generated artifact paths and content for date comparison and Huadian Liaoneng T text.
- Run the report acceptance audit against the generated full markdown.
- Record any unavailable source facts explicitly in the final summary.
