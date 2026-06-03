# Small Account Opportunity Cost Between Old-Position T and New Entry

## Goal

Make the daily report and follow-up trading guidance explicitly compare old-position T expectations against new-entry opportunities when the account is small, especially around a 1w account where funds cannot cover both actions. The report should not evaluate a held stock and a new target in parallel without deciding which use of capital is better.

This task is coupled with `.trellis/tasks/06-02-rewrite-selection-logic`: leader/anchor reverse selection decides which new target is strongest, while this task decides whether a 1w account can actually allocate capital to that new target after considering old-position T and T+1 risk. The two tasks must feed one final target resolution instead of rendering separate, competing answers.

## What I already know

* User has a roughly 1w account, so buying a new higher-priced target can require selling all current holdings.
* The concrete failure case was 2026-06-03: held 华电辽能 and considered 工业富联 after the 2026-06-02 report.
* The assistant compared sector strength and individual buy position, but missed the required opportunity-cost step: old-position T versus new-entry capital allocation.
* Existing report text already has separate concepts for old positions, new opportunities, T+1, MA5/MA7/MA5T, and "先处理旧仓，不为新候选分散资金".
* The related final-target task now proposes a `final_target_resolution` payload with role-separated identities. This task should supply the `capital_priority_decision` part of that payload, not create a standalone table that can disagree with the final result.
* Existing likely implementation areas include:
  * `scripts/portfolio/position_strategy_report.py`
  * `scripts/report/action_plan_nodes.py`
  * `scripts/report/front_page_v2_renderer.py`
  * `scripts/selection/position_sizing_runtime.py`
  * tests around candidate quality, report runtime, and position strategy.

## Requirements

* Add an explicit small-account opportunity-cost comparison before or alongside action guidance when both an existing position and a new target exist.
* The comparison must cover at least:
  * account capacity / one-position constraint;
  * old-position identity and T expectation;
  * new-entry identity and target strength;
  * sector/mainline strength;
  * buy-point quality and MA distance;
  * T+1 sellability / newly bought shares cannot be sold today;
  * expected return elasticity versus downside control;
  * final priority action.
* The output must choose one priority action, not merely list both opportunities.
* Existing position handling and new-entry handling remain separate decisions, but the report must add a cross-decision capital allocation layer for small accounts.
* The opportunity-cost comparison must be upstream of the rendered final action. If old-position T wins, the selected new target must be rendered as observation-only. If the new target wins, old-position handling must be rendered as the funding/risk action, not as a competing T0 main target.
* The visible explanation should read as one chain: `板块锚反推选出强对象 -> 小账户资金取舍 -> 明日唯一动作`.
* User-visible wording must follow the trading-language contract in `wiki/交易思想/日报术语契约.md`.

## Acceptance Criteria

* [ ] A small-account report scenario with an existing position and a new target renders a comparison table or concise decision block.
* [ ] The decision block explicitly states which action gets capital priority: old-position T, new entry, or waiting.
* [ ] A scenario where the new target has stronger mainline evidence but a worse buy point can state that it is higher priority to observe, but not to chase.
* [ ] A scenario where the held stock is only a weak old-position repair cannot silently consume new-entry capital without being compared against the new target.
* [ ] The same scenario also updates final-target rendering: account advice, execution plan, final conclusion, ASCII explanation, and statistics cannot present a different action target unless it is labeled as old-position handling or observation-only.
* [ ] Tests cover at least one `华电辽能`/`工业富联` style conflict or an equivalent old-position-vs-new-entry conflict.
* [ ] Generated user-facing text avoids forbidden engineering terms from the terminology contract.

## Definition of Done

* Relevant unit tests added or updated.
* Narrow Python 3.14 test command passes using `.generated/venv-py314/bin/python3.14 -m unittest ...`.
* Related report output is reviewed for wording and table ordering.
* If a durable rule is learned, update `.trellis/spec/` or wiki notes.

## Out of Scope

* Rewriting the full stock selection system.
* Adding new real-time data providers.
* Changing the core MA5/MA7/MA5T rules beyond how they are compared against a new-entry opportunity.
* Changing official historical reports unless separately requested.
* Building a portfolio optimizer or multi-position simulator.

## Technical Notes

* Python commands in this repo must use `.generated/venv-py314/bin/python3.14`.
* Relevant spec indexes inspected:
  * `.trellis/spec/guides/index.md`
  * `.trellis/spec/backend/index.md`
  * `.trellis/spec/frontend/index.md`
* `wiki/交易思想/做T与风险控制.md` already documents small-account T discipline and the MA5/MA7/MA5T distinction.
* `wiki/交易思想/交易错题本.md` already records the risk of mixing old-position handling with new-entry chasing.
* The first implementation pass should search existing renderers before adding new layers.
* Likely integration points from the related final-target task:
  * `scripts/domains/execution_chain/pk_decision_nodes/probe_position.py` currently exports `selected_position_candidate` before opportunity-cost comparison.
  * `scripts/selection/position_sizing_runtime.py` decides target position percentage but does not know the old-position opportunity-cost comparison.
  * `scripts/report/front_page_v2_renderer.py::_account_status_lines` already renders old-position-first text and selected candidate text; it needs the shared final target resolution to avoid contradictory rows.
  * `scripts/report/runtime.py` should build or attach the final target resolution before rendering front page and before building the daily judgment panel.

## Coupled Design Constraint

This task should not ship as a standalone report block only. It must produce structured output consumed by the final target resolution:

* `capital_priority`: `old_position_t`, `new_entry`, or `wait`.
* `old_position_target`: held stock and old-position handling plan.
* `new_entry_target`: anchor-reversal selected target.
* `capital_reason`: concise comparison across mainline strength, buy-point quality, MA distance, T+1 sellability, downside boundary, and expected elasticity.
* `render_role`: whether each target is action, observation, or old-position handling.

The user-facing report may show a compact table, but the table is secondary. The primary contract is that downstream final-result rendering uses this decision.
