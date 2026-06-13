# daily report stage 1 verdict packet and opening

## Goal

Implement the smallest vertical slice of the full daily-report rewrite: create a unified verdict packet shape on top of the existing two-layer decision payload, render the opening derivation summary from that packet, and ensure opening/final/action-facing sections use one final object identity.

This stage exists to remove the current black-box break where one section can show one process candidate while another section silently lands on a different final object.

## Parent Task

Parent PRD: `.trellis/tasks/06-05-daily-report-full-rewrite/prd.md`

This stage implements only the first slice of that PRD.

## In Scope

* Extend the existing daily decision payload rather than creating a separate competing payload.
* Add or expose the following packet sections at minimum:
  * `opening_verdict`
  * `position_stance`
  * `candidate_pool_verdict`
  * `final_object`
  * `next_day_action` placeholder fields when available
* Opening summary must show:
  * market/position headline when available,
  * final object identity,
  * whether it is execution, conditional execution, observation, or none,
  * top rejected/downgraded candidates when the data is available,
  * compact reason dimensions.
* Keep existing two-layer front decision and derivation audit rendering compatible.
* Add tests around payload shape and identity consistency.

## Out of Scope

* Full market/fund/sector spine rendering. That belongs to stage 2.
* Full candidate five-dimension comparison implementation. Stage 1 may include placeholders or best-effort extraction; stage 3 owns the real same-pool candidate rewrite.
* Appendix migration, final replay flowchart, and acceptance-audit expansion. Those belong to stage 4.
* New market data collectors.
* Manual edits to generated replay markdown as the fix.

## Non-goals

* Do not hide useful current report data.
* Do not make renderer-only cosmetic changes that leave the payload inconsistent.
* Do not introduce a second final object source.

## Done Definition

* `build_two_layer_decision_payload(...)` or a nearby shared builder returns the new packet fields without breaking existing callers.
* Opening verdict renderer reads the packet and does not independently choose a different stock.
* `final_object.stock` matches the front decision execution/observation identity when present.
* A no-object result stays explicit and does not create execution conditions.
* Tests cover:
  * conditional execution object with packet identity,
  * observation/no-participation object with no B-level execution,
  * top rejected/downgraded candidate reason is not circular when available,
  * opening verdict consumes the same final object as the front decision.
* Narrow replay generation for `2026-06-04 --replay` is listed as verification after implementation.

## Likely Files

Execution agents should inspect before editing:

* `scripts/report/two_layer_decision_payload.py`
* `scripts/report/front_page_v2_renderer.py`
* `scripts/report/runtime.py`
* `scripts/report/sniper_target_derivation.py`
* `tests/test_two_layer_decision_payload.py`
* `tests/test_front_page_v2_renderer.py`
* `tests/test_report_runtime.py`

## Acceptance Criteria

* [ ] The payload contains `final_object.identity`, `final_object.stock`, `final_object.position_stance`, and `final_object.why_this_not_others`.
* [ ] Opening verdict, front decision, and derivation audit agree on the same final stock or all render no stock.
* [ ] If `position_stance` is 0%, any stock shown is rendered as observation/process evidence, not execution.
* [ ] Existing tests for two-layer decision payload still pass.
* [ ] New tests use `.generated/venv-py314/bin/python3.14 -m unittest ...`.

## Implementation Notes

Prefer expanding the existing `two_layer_daily_decision.v1` payload with backwards-compatible fields. If a schema version bump is needed, keep old keys available to existing renderers.

The visible language must use trading wording such as conditions, qualification, participation, observation object, and final object. Do not introduce user-visible engineering terminology.
