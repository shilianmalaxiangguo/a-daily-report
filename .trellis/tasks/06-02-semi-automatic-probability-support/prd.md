# Semi Automatic Probability Support

## Goal

Add probability and base-rate support for report decisions after fieldized ledger rows and statistics coverage are reliable. The output should support judgment, not replace the daily report action.

## In Scope

- Probability/base-rate views derived from auditable historical records.
- Inputs such as mainline evidence score, sample tier, position plan, participation window, and market participation qualification.
- Confidence wording based on coverage and missing facts.
- Tests that prevent probability output when coverage is insufficient.

## Out of Scope

- Fully automated trading.
- Broker execution.
- Cost/slippage modeling.
- Factor mining or broad model selection.
- Probability output before history coverage and statistics are trustworthy.

## Non-goals

- Do not claim certainty.
- Do not recommend participation without the report action contract.
- Do not hide missing facts or short sample size.

## Requirements

- Probability rows include:
  - input segment,
  - sample count,
  - date range,
  - base rate,
  - drawdown or adverse-move context,
  - missing facts,
  - support wording.
- If sample count is too small or missing facts dominate, output must say the probability support is not ready.
- Probability support appears after the final action and statistics panel.

## Acceptance Criteria

- [ ] Tests block probability support when coverage is too short or missing facts dominate.
- [ ] Probability output includes coverage metadata.
- [ ] Report output does not turn probability into automatic action.

## Definition of Done

- Unit tests pass with Python 3.14.
- Representative replay report passes acceptance audit if rendering changes.
- User-visible wording follows terminology rules.

## Technical Approach

- Depend on the statistics panel and coverage expansion tasks.
- Use simple base-rate summaries before any model-like scoring.
- Keep this child task inactive until the coverage and statistics tasks are complete.
