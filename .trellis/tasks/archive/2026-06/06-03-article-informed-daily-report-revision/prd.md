# Article-Informed Daily Report Revision

## Goal

Revise the daily-report decision plan so the report can judge an existing holding versus a new target with explicit opportunity cost, risk price, invalidation downside, risk-reward, and account fit. The immediate calibration case is the 2026-06-03 replay report: the account has about `1w` capital, still holds `华电辽能(600396)` `200股` as `T+1仓`, and the replay promotes `华天科技(002185)` while also saying the market has no confirmed mainline.

The report must not justify abandoning the old position because it is profitable or because the account happens to have an old holding. The only valid switch reason is: the old position has weakened or become a capital/risk burden, and the new opportunity is demonstrably stronger with clearer support, cleaner invalidation, better risk-reward, and executable capital path.

## In Scope

- Rework the 2026-06-03 report plan around the actual replay facts, including:
  - old holding: `华电辽能(600396)`, `200股`, `T+1仓`, same-day 做T buy/sell facts,
  - selected new target: `华天科技(002185)`,
  - existing report candidate set such as `亨通光电(600487)` and `一博科技(301366)` when they already appear in the snapshot,
  - current report contradictions between `暂无确认主线 / 候选观察` and `100%核心进攻`.
- Add an opportunity-cost comparison contract that can be rendered and audited.
- Keep old-position handling and new-entry handling separated, then compare them only after each side has its own risk and action plan.
- Require visible risk prices before any 50% or 100% wording:
  - observation/current price,
  - MA5,
  - MA10,
  - VWAP when available,
  - invalidation price,
  - target/upside price,
  - downside percentage to each risk price,
  - risk-reward ratio and state.
- Apply the article-derived LLM Wiki doctrine already captured in:
  - `wiki/交易思想/价格行为与能量框架.md`,
  - `wiki/板块补充/板块中枢与主线延续.md`,
  - `scripts/knowledge/llm_wiki_context.py`.
- Make the following report surfaces agree:
  - final target process,
  - account advice,
  - monthly attack/sizing section,
  - individual-stock verdict,
  - tomorrow execution plan,
  - final conclusion,
  - position strategy report,
  - report acceptance audit.

## Out of Scope

- Rewriting the whole daily-report pipeline.
- Adding a new broad backtest framework.
- Adding new live data sources only for this slice.
- Treating the article as a report section or motivational prose.
- Replacing the existing `0% / 50% / 100%` participation model.
- Broker execution, order routing, or real-time trading automation.
- Committing or staging files during this planning step.

## Non-Goals

- Do not make old-position T the default answer just because a holding exists.
- Do not make new-entry promotion the default answer just because a candidate is strong.
- Do not rank a candidate as actionable when risk-reward is missing or not positive.
- Do not convert a candidate list, limit-up pool, or article "彩蛋" into a buy list.
- Do not use profit, regret, or missed-entry anxiety as a sell/switch reason.
- Do not hide a normal 5%-10% pullback risk behind generic "strong core" wording.

## Requirements

### 1. Article Rules Become Decision Rules

- Cheapness is not a buy reason. A deep drop only creates short rebound or repair observation unless trend reversal, sector fund return, and core support are confirmed.
- Empty position is an active decision. If market emotion, mainline, risk price, or participation window is incomplete, the correct output may be `0%不参与/观察`.
- A missed early reversal must not turn into chasing tail-stage followers. Late acceleration may leave only true core names worth tracking; ordinary catch-up names are feedback, not action targets.
- Violent emotion is a reassessment signal, not a direct action signal. After a sharp emotion move, the report should write the next one to two trading days' verification path.
- Rotation needs repeated evidence. One-day movement in electricity, coal, oil/gas, battery, chemical, robotics, commercial aerospace, or semiconductor lines is a clue; repeated capital conversion is the stronger proof.
- Candidate quality still requires trend, near-new-high structure, no center-of-gravity breakdown, prior activity, and limit-up gene. These features raise research priority but do not replace risk price.

### 2. Old Position And New Entry Are Evaluated Separately First

For each old holding:

- Identify sellable quantity, unsellable quantity, holding identity, recent T action, account capital, and old-position role.
- Produce a holding plan with lower defense and upper take-profit. A T plan must include both; otherwise it is not a complete T plan.
- Judge old-position weakening from price structure, MA response, sector support, relative strength, and buy-point failure, not from floating profit or loss.

For each new target:

- Identify target role: core, sector anchor, same-line follower, catch-up/follower, observation anchor, or unavailable for account execution.
- Produce an entry plan with window, observation price, invalidation price, upside target, risk-reward state, and missed-entry plan.
- If any of observation price, invalidation price, or upside target is missing, the target can remain a candidate but cannot receive unconditional 50% or 100% wording.

### 3. Opportunity-Cost Comparison Is Required Before Switching

The report must build an `opportunity_comparison.v1` record before it says to release old-position capital for a new target.

Required fields:

```python
{
    "schema_version": "opportunity_comparison.v1",
    "report_date": "YYYY-MM-DD",
    "account_capital": "str | None",
    "old_position": {
        "name": "str",
        "code": "str | None",
        "shares": "int | None",
        "sellable_shares": "int | None",
        "unsellable_shares": "int | None",
        "holding_role": "old_position | failed_entry | trend_holding | unknown",
        "old_logic_state": "valid | weakening | invalid | incomplete",
        "old_plan_action": "hold | reduce | exit | repair_once | observe",
        "old_plan_reason": "str",
        "lower_defense_price": "float | None",
        "upper_take_profit_price": "float | None",
        "missing_fields": ["str"]
    },
    "new_target": {
        "name": "str",
        "code": "str | None",
        "line": "str | None",
        "target_role": "core | sector_anchor | same_line_candidate | follower | observation | unknown",
        "strength_evidence": ["str"],
        "entry_window": "09:30-09:35 | 09:50-10:10 | 14:30-14:55 | no_trade",
        "observation_price": "float | None",
        "ma5": "float | None",
        "ma10": "float | None",
        "vwap": "float | None",
        "invalid_price": "float | None",
        "target_price": "float | None",
        "downside_to_ma5_pct": "float | None",
        "downside_to_ma10_pct": "float | None",
        "downside_to_vwap_pct": "float | None",
        "downside_to_invalid_pct": "float | None",
        "risk_reward_ratio": "float | None",
        "risk_reward_state": "合格 | 不合格 | 待计算",
        "risk_price_comfort": "comfortable | stretched | unacceptable | incomplete",
        "missing_fields": ["str"]
    },
    "comparison": {
        "new_target_materially_stronger": "bool",
        "old_position_must_be_released": "bool",
        "risk_boundary_controllable": "bool",
        "capital_efficiency_result": "new_entry_after_old_exit | old_position_t | wait | observe",
        "max_participation_pct": "0 | 50 | 100",
        "final_action": "str",
        "reason": "str"
    }
}
```

Rules:

- `new_target_materially_stronger=true` requires line strength, target role, structure, and support evidence. It cannot be based on "it has not risen much".
- `old_position_must_be_released=true` requires old-position weakening, buy-point failure, account capital conflict, or a strictly stronger new target with controllable risk. Profit alone must not set it.
- `risk_boundary_controllable=false` when the candidate is far above MA5/MA10/VWAP and normal reversion would force the account to passively carry a large loss.
- If downside to the nearest relevant risk price is around `5%-10%` and there is no precise invalidation/confirmation plan, the target cannot render unconditional `100%核心进攻`.
- If `risk_reward_state` is `待计算` or `不合格`, the target can remain in the table, but the report must render observation or no new participation until the missing prices are filled.

### 4. 2026-06-03 Target Replay Rule

The current 2026-06-03 replay snapshot shows:

- `final_target_resolution.old_position_exit_for_new_entry=true`,
- `capital_action_reason=先处理旧仓，买华天科技(002185)；固定交易窗口条件成立才参与，不满足回到0%`,
- `华天科技(002185)` has `risk_reward_state=待计算`,
- `planned_participation` is absent in the inspected matching objects,
- the market sections say `暂无确认主线`, `暂无确认主攻线`, and `只保留候选观察`,
- the execution summary still renders `100%核心进攻`.

Therefore, the minimum accepted behavior for this replay is:

- The report must not render unconditional `100%核心进攻` while risk-reward and participation records are missing.
- If implementation cannot calculate a complete risk price set from existing target-date facts, the 2026-06-03 replay should render `0%新仓/观察` for the new target and keep the old-position plan separate.
- If implementation can calculate all prices and prove the new target is a true core with controllable downside, the report may render 50% or 100%, but the opportunity-cost table must show why the new target beats the old holding and why the drawdown can be carried.
- The report must say the valid switch reason in trading terms: stronger line, better support, clearer invalidation, better risk-reward, and executable cash path.

### 5. Cross-Surface Consistency Rules

- If the final conclusion says `100%核心进攻`, every major surface must contain a complete planned participation record and a complete risk price comparison.
- If the market body says no confirmed mainline and no confirmed main attack line, a 100% result requires an explicit reason why the individual target overrides that market background. Without that reason, cap at observation or standard participation after calculation.
- Account advice cannot say `先处理旧仓，买X` while the individual-stock section says risk-reward is unknown. The missing price fields must be visible.
- Position strategy may say old holdings should be handled first, but it cannot turn that into automatic new-entry permission.
- Final target process must distinguish:
  - `process_target`: the candidate used for reasoning,
  - `display_target`: the target shown in the final action,
  - `watch_target`: observation anchor when execution is not yet qualified,
  - `existing_position_target`: old holding action.

## Acceptance Criteria

- [ ] The Spec is approved before code changes begin.
- [ ] The 2026-06-03 replay no longer shows unconditional `100%核心进攻` when risk-reward is `待计算` or planned participation is absent.
- [ ] The replay report includes an opportunity-cost table comparing at least `华电辽能(600396)` and `华天科技(002185)`.
- [ ] If additional same-day candidates already exist in the snapshot, the table can include them without adding a new data source.
- [ ] The opportunity-cost table includes observation/current price, MA5, MA10, VWAP when available, invalidation price, target price, downside percentage to each risk price, risk-reward state, and account fit.
- [ ] The report explains whether the new target beats the old position. If it does not, the report says observation/no new participation instead of forcing a switch.
- [ ] The report rejects profit as a sell reason and uses only weakening, stronger opportunity, and controllable risk as switch reasons.
- [ ] If MA5/MA10/VWAP deviation implies an unacceptable passive loss, the candidate cannot render unconditional `100%核心进攻`.
- [ ] The final target process, account advice, action plan, final conclusion, position strategy, and acceptance audit agree on the same participation percentage and action wording.
- [ ] Regression tests cover missing risk price, unacceptable MA deviation, old-position/new-entry conflict, and cross-surface report consistency.
- [ ] Replay generation and report acceptance audit are run for `2026-06-03` after implementation.

## Definition of Done

- User approves this Spec.
- Implementation is split into small, reviewable slices.
- Required task context files are curated for implementation and check.
- Code changes use Python 3.14 only.
- Focused tests pass with `.generated/venv-py314/bin/python3.14 -m unittest ...`.
- `2026-06-03 --replay` is regenerated.
- Report acceptance audit runs against the generated replay markdown.
- `git diff --check` passes for touched files.

## Technical Approach

### Recommended Approach: Compare First, Then Render

Build the opportunity-cost comparison once near the existing candidate execution / final target resolution path, then let report surfaces consume the result. This avoids each renderer making its own version of "old holding versus new opportunity".

Implementation slices:

1. **Comparison builder**
   - Reuse `build_risk_reward_plan(candidate)` for risk-reward state.
   - Add a small comparison helper that accepts old-position context, selected candidate, and target-date price facts.
   - Derive risk price comfort from distance to MA5/MA10/VWAP/invalidation.

2. **Decision repair**
   - When comparison is incomplete or unacceptable, prevent 50%/100% promotion and render the new target as observation.
   - When comparison is complete and the new target wins, keep the old-position release reason tied to stronger opportunity plus controllable risk.

3. **Rendering**
   - Add the opportunity-cost table to the front-page/action-plan area where the final action is decided.
   - Keep position strategy as old-position scenario handling, not new-entry permission.

4. **Audit and tests**
   - Extend acceptance audit to catch `100%核心进攻` with missing risk-reward or missing planned participation.
   - Add focused tests for the 2026-06-03 replay conflict.

### Alternatives Considered

**A. Patch only the wording**

- Pros: smallest visible change.
- Cons: leaves the report able to produce contradictory payloads again.
- Decision: reject.

**B. Make old-position handling always first**

- Pros: conservative for small accounts.
- Cons: repeats the mistake the user identified; it treats old-position T as the default instead of comparing stronger opportunities.
- Decision: reject.

**C. Build a full account optimizer**

- Pros: could generalize across all holdings and candidates.
- Cons: too large for this slice and would add architecture before the current report contract is coherent.
- Decision: reject for now.

## Decision (ADR-lite)

**Context**: The current report can say the market has no confirmed mainline, risk-reward is not calculated, and planned participation is absent, while still rendering `100%核心进攻` and telling a 1w account to release old-position capital for a new target.

**Decision**: Add an opportunity-cost comparison contract and make 50%/100% rendering depend on complete risk prices, calculable risk-reward, controllable drawdown, and a valid reason the new target beats the old position.

**Consequences**: Some strong-looking candidates will be shown as observation until risk prices are complete. This is intentional: strength without a controllable risk boundary is not an executable plan for a small account.

## Implementation Context

Relevant current files:

- `scripts/selection/candidate_execution_contracts.py`
- `scripts/report/runtime.py`
- `scripts/portfolio/position_strategy_report.py`
- `scripts/portfolio/position_management_report.py`
- `scripts/report/report_acceptance_audit.py`
- `scripts/domains/execution_chain/pk_decision_nodes/candidate_quality_scorecard.py`
- `tests/test_daily_report_render.py`
- `tests/test_position_management_report.py`
- `tests/test_llm_wiki_context.py`

Relevant doctrine and contracts:

- `.trellis/spec/backend/daily-report-decision-loop.md`
- `references/report-contract.md`
- `wiki/交易思想/日报术语契约.md`
- `wiki/交易思想/扣分系统与动作分层.md`
- `wiki/交易思想/极度看好参与时机.md`
- `wiki/交易思想/价格行为与能量框架.md`
- `wiki/板块补充/板块中枢与主线延续.md`

Relevant replay artifacts:

- `reports/replay/2026-06-03_A股日报_完整版_replay.md`
- `reports/replay/2026-06-03_A股日报_执行摘要_replay.md`
- `reports/replay/2026-06-03_持仓策略_replay.md`
- `snapshots/replay/2026-06-03_replay.json`

## Open Questions

No blocking question remains for the MVP. Recommended scope: compare the old holding, the selected new target, and any same-day candidates already present in the replay snapshot. Do not add external candidate discovery in this slice.
