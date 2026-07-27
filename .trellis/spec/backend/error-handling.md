# Error Handling

> How errors are handled in this project.

---

## Overview

Daily-report generation uses explicit failure findings and raises before
persisting an invalid report. The command wrapper records uncaught failures in
`logs/errors/<run-key>.json`, updates `logs/latest_failure.json`, and keeps the
full terminal trace in `logs/runs/<run-key>.log`.

---

## Error Types

- `ReportCriticalDataMissingError`: required report facts or acceptance
  conditions are incomplete, so generation stops.
- Acceptance findings use stable codes, such as
  `position_day_order_current_position_missing` and
  `position_day_order_html_current_position_missing`.
- Bear HTML that omits the complete account day-order section uses
  `position_timeline_html_missing`; a non-Bear companion without that section
  must not be rejected by this check.
- External-pending provenance failures keep the existing stable compatibility codes
  `position_day_order_inferred_confirmation_missing`,
  `position_inferred_rendered_as_confirmed_holding`, and
  `position_day_order_html_inferred_confirmation_missing`.
- Te execution-target conflicts use stable, surface-specific codes:
  `position_day_order_inferred_target_conflict` when Markdown Te promotes a
  pending external record; `position_day_order_html_inferred_target_conflict`
  when Bear does so; and `position_day_order_html_target_conflict` for a general
  Bear/Markdown Te mismatch. The historical code names remain stable, but a
  simulated previous-report target is confirmed 1x and must not trigger them.

---

## Error Handling Patterns

- Build the complete in-memory report, including late-rendered account tables,
  before the first acceptance check.
- Print every finding code and message, save the failed draft under
  `.generated/report-audit-failures/`, then raise
  `ReportCriticalDataMissingError` with the same codes and messages.
- Do not reduce the raised error to a generic message. The run wrapper stores
  `str(error)` in the JSON error record, so stable finding codes must survive.
- A failed acceptance check must happen before PostgreSQL import, Markdown save,
  companion HTML save, or runtime-artifact persistence whenever possible.
- The command entry, standalone replay, and AgentRunner must all finish
  acceptance before writing the judgment ledger or any report artifact. A
  renderer option must not bypass this order by persisting during construction.

---

## API Error Responses

This project is command-line driven. The durable error JSON contains:

- `started_at`, `failed_at`, and redacted `argv`;
- `run_log_path`;
- `error_type` and `error_message`;
- a redacted traceback.

---

## Common Mistakes

- Running acceptance before a late-rendered table is inserted.
- Logging only a generic failure and losing the finding code.
- Passing Bear HTML as the Chanlun companion, which creates unrelated companion
  findings and hides the intended account-table check.
- Skipping Te target checks when an external PostgreSQL position summary was not
  passed; the independent CLI must derive pending-plan status from Td/Te text.
- Saving a report first and checking its account identity afterward.
