# Decision Cockpit Front Page

## Goal

Rebuild the daily report front page into a decision cockpit that answers five questions before detailed analysis: whether participation is qualified, what the mainline is, what to do tomorrow, when not to do it, and how yesterday's rehearsal settled.

## In Scope

- Front-page structure and rendering.
- Final action ordering and clarity.
- Display of prior rehearsal result using explicit review facts.
- Display of current coverage sample when historical review is referenced.
- Tests for rendered ordering and required fields.

## Out of Scope

- Historical coverage expansion implementation.
- Full statistics panel.
- Probability support.
- Broker execution or automated trading.

## Non-goals

- Do not bury final action under process evidence.
- Do not use statistics to invent a new action.
- Do not rewrite unrelated report sections.

## Requirements

- The first decision surface answers:
  - participation qualification,
  - mainline,
  - tomorrow action,
  - cancellation condition,
  - prior rehearsal result.
- 0% / 50% / 100% position plans are visible and backed by explanation.
- 50% and 100% plans must include participation window and cancellation conditions.
- Missing facts render as waiting for facts, not as success/failure.

## Acceptance Criteria

- [ ] Front-page tests assert final action appears before process evidence.
- [ ] Rendered report includes position plan, window/no-trade state, confirmation conditions, and cancellation conditions.
- [ ] Prior rehearsal result appears only when explicit facts exist, otherwise missing facts are visible.
- [ ] Replay sample and report acceptance audit pass.

## Definition of Done

- Relevant renderer tests pass with Python 3.14.
- Representative replay report is regenerated and audited.
- User-visible wording follows the terminology contract.

## Technical Approach

- Start with existing front-page and action-plan renderers.
- Reuse decision-ledger records rather than adding a separate action model.
- Keep historical statistics as supporting evidence after the final action.
