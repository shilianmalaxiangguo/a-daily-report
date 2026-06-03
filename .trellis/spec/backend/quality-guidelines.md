# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

### T0 Account Advice Contract

The front-page `T0` row is the next-day account action layer. It is not a
synonym for existing holdings.

- Existing holdings still take priority when present, but a no-holding account
  may render a `T0主对象` when a candidate has a 50% or 100% position-state
  decision or explicit next-day action evidence.
- Unknown position context must stay explicit: render a separate confirmation
  row before execution instead of rewriting the account as no-holding.
- A 0% conclusion needs a strong reason such as weak market, ice point, invalid
  trend, incomplete key data, account mismatch, old-position handling, or risk
  reduction. Do not use 0% as the default when a candidate already has a fixed
  trading window and invalidation condition.
- Runtime front-page normalization must check candidate evidence before turning
  a previous 0% context into observation-only output. Extreme downside,
  countertrend attack, and account-unbuyable cases may still remain 0%.
- Front-page account advice should state the direct next-day result. Do not wrap
  the final position choice in preview wording when the decision is already
  formed.
- When adapting candidates from extreme-conviction lists or decision-ledger
  records, preserve `planned_participation`, `attack_state`, and explicit
  position percentage fields. Dropping these fields makes the front page treat a
  valid 50%/100% setup as a plain observation object.
- Candidate position reconstruction must prefer positive 50%/100% evidence
  from `planned_participation` / `participation_script` over stale top-level
  `0` fields. A stale top-level zero must not erase a valid nested attack plan.
- Do not promote a selected candidate from 0% observation into 50%/100%
  participation unless all three facts exist: explicit position evidence,
  a fixed trading window, and a fallback / invalidation condition that returns
  the plan to 0% when conditions fail.
- Account-buyability checks must use concrete `cash_available` and
  `one_lot_amount` facts when present. A missing knowledge hit must not allow an
  account that cannot buy one lot to be rendered as 50%/100% participation.

### Daily Report Action Plan Presentation Contract

The report must make the final next-day action easier to find than any process
table.

- `DEFAULT_ACTION_PLAN_NODE_SPECS` must render `action_table` before
  `candidate_quality`.
- `build_action_plan_candidate_quality_node` must mark its section and nested
  tables with `（过程证据）` when rendered inside the action plan.
- Candidate-quality process evidence that carries anchor-reversal payloads must
  render an ASCII `狙击手最终标的路径图` before trace tables, and the action-plan
  wrapper must mark that heading with `（过程证据）`.
- `_sanitize_report_lines` must mark appendix candidate, risk, and observation
  tables with `（过程证据）` while preserving the original table title text.
- `report_acceptance_audit.py` must fail reports where appendix candidate,
  risk, observation, or tracking headings appear without `（过程证据）`.
- The final action area must show each stock only once with its final identity:
  main observation, backup observation, old-position handling, or not watched.
- A `0%` final result may keep observation anchors only as process evidence; it
  must not make candidate, risk, or observation-position tables look like the
  final action.

Required tests:

- `tests.test_action_plan_renderer.ActionPlanRendererTest.test_action_table_stays_before_candidate_quality_process_evidence`
- `tests.test_report_runtime.ReportRuntimeTest.test_sanitize_report_lines_marks_process_tables_as_evidence`
- A generated replay report, such as `2026-05-29 --replay`, must pass
  `scripts/report/report_acceptance_audit.py`.

### Daily Report Anchor Reversal Candidate Selection Contract

The final next-day candidate layer must prefer sector-anchor reversal over raw
score ranking. Scores and multi-source pools remain evidence; they do not by
themselves create a main-buy or backup-buy identity.

#### 1. Scope / Trigger

Use this contract when changing:

- extreme-conviction candidate generation,
- sector trend snapshot anchor selection,
- candidate trace payloads,
- candidate-quality tables,
- action-plan or candidate-selection rendering.

#### 2. Signatures

`build_anchor_reversal_decision(candidate, sector_snapshot=None, mainline_name="")`
returns:

```python
{
    "sector_anchor": "str",
    "candidate_role": "板块锚 | 分支龙头 | 大容量中军 | 低位补涨 | 套利工具 | 跟风样本 | 修复观察 | 观察样本",
    "relationship_to_anchor": "str",
    "why_not_anchor": "str",
    "repair_priority": "优先修复 | 次优先修复 | 后排修复 | 待识别 | 风险放大",
    "anchor_reversal_decision": "可作为主对象 | 可作为补位 | 降级观察 | 不参与",
    "anchor_reversal_reason": "str",
    "ma_binding_strategy": "str",
    "leader_certainty_path": "str",
    "limit_up_evidence_role": "str",
}
```

`build_extreme_conviction_list(...)` must merge those fields into every returned
candidate before sorting and assigning `sniper_role`.

`build_candidate_trace(candidate)` must preserve the same fields under
`trace["anchor_reversal"]`.

`build_sector_trend_snapshot(...)` must prefer known sector-anchor identity,
large-capacity trend participation, repeatable acceptance, and MA binding paths
over one-day limit-up laggards when choosing `anchor_code`.

`candidate_trade_narrative_fields.v1`:

```python
{
    "sector": "str",  # display and selection sector after same-day narrative enrichment
    "raw_sector": "str",  # original industry / source-board sector, preserved when sector is rewritten
    "trade_narrative_sector": "str",  # same-day trading narrative sector, e.g. "AI算力基础设施"
    "trade_narrative_reason": "str",  # concise evidence label, source-dated by the surrounding replay snapshot
    "xueqiu_hot_stock_argument": "str",
}
```

`build_candidate_bundle_contract(...)` must add explicit anchor-source candidates
from `dragon_stocks` and anchor-like `candidates` into the evaluation universe
before scoring, deduped against `watchlist` and recent extreme mentions. The
final candidate universe must not be only the watchlist or limit-up-derived
pool.

#### 3. Contracts

- `build_anchor_reversal_decision(...)` must prefer the current `mainline_name`
  anchor row over the candidate's own sector row when both exist. A crossline
  stock that is the anchor of its own sector is still measured against the
  current mainline anchor before it can be considered for action.
- Candidate enrichment must separate static industry from same-day trading
  narrative. When same-day evidence such as `xueqiu_hot_stock_argument`,
  concepts, or hot reasons points to a stronger trading narrative than the
  static industry, set `trade_narrative_sector`, preserve the old label in
  `raw_sector`, and use the narrative sector for candidate display, trace, and
  anchor reversal.
- Exception: if `raw_sector` matches the current mainline only because the source
  industry is stale/static, while `trade_narrative_sector` is backed by same-day
  evidence and differs from the mainline, treat this as a trading-narrative
  migration. In that case, anchor reversal must search the narrative sector
  first so a stock like 工业富联 is compared as an AI server / capacity anchor
  instead of being captured by a generic communication-equipment anchor.
- A candidate may receive `sniper_role == "明日主买对象"` only when
  `anchor_reversal_decision == "可作为主对象"` or no anchor-reversal payload is
  present in legacy data.
- A candidate may receive `sniper_role == "明日补位对象"` only when
  `anchor_reversal_decision == "可作为补位"` or it is the next valid non-downgraded
  legacy candidate.
- `anchor_reversal_decision in {"降级观察", "不参与"}` must set both
  `primary_buy_candidate` and `backup_buy_candidate` to `False`.
- `anchor_reversal_decision == "降级观察"` must render as observation-only
  process evidence. It must not keep a legacy board/reseal action sentence that
  implies new participation; use `participation_window == "no_trade"` or an
  explicit no-new-entry action surface.
- If the sector anchor has failed, low catch-up, arbitrage, and follower samples
  must render `anchor_reversal_decision == "不参与"` and
  `repair_priority == "风险放大"`; they are not cheaper substitutes for the
  anchor.
- Missing sector-anchor evidence must downgrade the candidate to observation
  until the anchor can be identified; it must not keep the old score-only
  comparison as a main-buy path.
- The evaluation source must include mainline anchors from `dragon_stocks` and
  anchor-like `candidates` even when they are not in the watchlist / limit-up
  pool. A limit-up laggard cannot become the only comparable object merely
  because the real anchor was absent from the watchlist.
- Limit-up, multi-board, T-board, next-day limit-up probability, and inertia
  score can improve confidence only after the candidate has a valid anchor role.
  They are evidence, not the source of a main-buy identity.
- An identified sector anchor with repeatable acceptance, capacity evidence, or
  `MA5入/MA7清/MA5T` may enter the final comparison even when the current-day
  actual rise is small. The MA path is an execution anchor; it must not bypass
  fixed-window acceptance, sector sync, or final risk review.
- Candidate-quality contracts must render anchor-reversal downgrades as
  `action_ceiling == "不参与"` and `new_entry_action == "只观察，不新增参与"`.
- Report tables that show candidate process evidence must include the anchor,
  role, relationship, repair priority, decision, MA binding strategy, leader
  certainty path, limit-up evidence role, and reason when present.
- Candidate process evidence must also include an ASCII path graph when
  anchor-reversal payloads are present: raw candidate pool -> mainline/sector ->
  sector anchor -> main-buy / backup / observation-or-no-participation branches.
  Downgraded rows must show their `why_not_anchor` or reversal reason as the
  bias/blocking point so the final target is not opaque.
- The front page must also render one concise `最终标的解题过程` block from the
  resolved runtime `selected_position_candidate` / `current_core_candidate`.
  Its final result, daily judgment core row, individual-stock verdict,
  next-day action plan, and ASCII path must all use the same stock identity.
  Candidate-quality graphs are process evidence; they must not introduce a
  different front-page result.
- When the final conclusion already has one selected target, it must render the
  selected-target sentence as an anchor-reversal contraction result. Do not prefix
  that target with legacy visible counts such as core / backup / crossline
  buckets; those counts are process evidence and can otherwise reintroduce the
  old score-first identity.
- The current daily judgment panel must prefer the runtime-selected main or
  backup candidate over same-day decision-ledger records. Ledger records are only
  a fallback when the current runtime context provides no candidate rows.
- Runtime observation rows still count as current context. If every current row
  is observation-only or not participating, the panel must not refill the core
  candidate row from older same-day ledger records; render no current core
  candidate rather than promoting stale process evidence.

#### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| Candidate is the sector anchor | `可作为主对象`, `优先修复` |
| Candidate is its own crossline anchor while a current mainline anchor exists | Compare against the current mainline anchor; downgrade unless it explains why not the mainline anchor |
| Candidate is a large-capacity center or branch leader with `why_not_anchor` | `可作为补位`, `次优先修复` |
| Sector anchor has capacity/acceptance/MA binding but small actual rise | Keep it eligible for main/backup comparison |
| Mainline anchor is in `dragon_stocks` but not watchlist / limit-up pool | Add it to evaluated candidates before scoring |
| Static industry is `通信设备` but same-day evidence says AI server / NVIDIA / data-center capacity | Preserve `raw_sector == "通信设备"`, set `trade_narrative_sector == "AI算力基础设施"`, and search the narrative-sector anchor first |
| Limit-up laggard scores, probability, or inertia rank higher than the known anchor | Anchor still ranks first; laggard stays observation |
| Candidate is low catch-up, arbitrage, or follower | `降级观察`, no main or backup identity |
| Downgraded candidate previously had a board/reseal action sentence | Replace with observation-only wording and no new participation |
| Sector anchor has failed and candidate is low catch-up, arbitrage, or follower | `不参与`, `repair_priority == "风险放大"` |
| Sector anchor is missing | `降级观察`, `repair_priority == "待识别"` |
| Candidate-quality sees `降级观察` or `不参与` | Render `不参与` and `只观察，不新增参与` |
| Report renderer receives anchor-reversal payload | Show all user-facing reversal fields as process evidence |
| Report renderer receives anchor-reversal payloads for multiple candidates | Render the ASCII path graph before trace tables, with main-buy, backup, and observation/no-participation branches |
| Front page has one resolved final target | Render `最终标的解题过程` before account advice; result, judgment row, verdict, action plan, and graph all show that target |
| Final conclusion has one selected target | Render the anchor-reversal contraction sentence, without legacy candidate-count prefix |
| Current panel has one runtime-selected target and same-day ledger has older extra records | Render only the runtime-selected target |
| Current panel has only observation/no-participation rows | Do not refill the core candidate row from same-day ledger fallback |

#### 5. Good / Base / Bad Cases

| Case | Input | Expected Output |
|---|---|---|
| Good anchor | 大唐发电 is the sector anchor | main object, first repair priority |
| Good slow anchor | 大唐发电 rises only about 1% but has acceptance and `MA5入/MA7清/MA5T` | main comparison remains valid |
| Good source expansion | 大唐发电 is supplied by `dragon_stocks` while 京能电力 is the watchlist limit-up laggard | 大唐发电 enters evaluation and ranks as main object |
| Good narrative migration | 工业富联 has static industry `通信设备` plus same-day evidence `英伟达AI平台` / `AI服务器` | display sector becomes `AI算力基础设施`, `raw_sector` remains `通信设备`, and its anchor is 工业富联 |
| Good backup | 华电辽能 has an explicit reason to choose it over 大唐发电 | backup object |
| Base missing anchor | Candidate has no comparable sector anchor | observation until anchor is identified |
| Bad crossline anchor override | 大有能源 is the coal anchor while 通信设备 has 意华股份 as current anchor | 大有能源 compares against 意华股份 and stays observation |
| Bad limit-up override | 京能电力 limit-up score is higher than the known sector anchor | observation; limit-up is evidence only |
| Bad score-only laggard | 京能电力 scores highest but is an arbitrage/catch-up sample | observation, never main or backup |
| Bad failed-anchor laggard | 晶方科技 rallies after 华天科技 / 长电科技 fail | no participation; risk amplification |
| Bad process table | Trace says observation but candidate-quality table says backup | render as not participating |
| Good path graph | Anchor-reversal traces include main, backup, and downgraded rows | ASCII graph shows raw pool -> sector anchor -> final branches and downgrade bias/blocking point |
| Good front-page solution | Runtime final target is 工业富联 | `最终标的解题过程`, core judgment row, verdict, and action plan all show 工业富联 |
| Bad final conclusion | Selected target is shown after legacy core / backup / crossline counts | selected-target line starts with anchor-reversal contraction |
| Bad split result | Front page says 工业富联 but process graph result says 中际旭创 | Report is invalid; process graph must use the resolved final target or remain appendix evidence only |
| Bad current judgment panel | Current context selects 工业富联 but same-day ledger also has 亨通光电 / 中天科技 | core candidate row shows only 工业富联; the others remain process evidence |
| Bad static-industry capture | 工业富联 is kept under `通信设备` even though same-day evidence says AI server capacity | candidate trace and decision ledger show the wrong sector and anchor comparison becomes misleading |

#### 6. Tests Required

- `tests.test_anchor_reversal_contracts`
- `tests.test_candidate_bundle_runtime.CandidateBundleRuntimeTest.test_extreme_conviction_uses_anchor_reversal_before_score_ranking`
- `tests.test_anchor_reversal_contracts.AnchorReversalContractsTest.test_crossline_own_anchor_cannot_replace_current_mainline_anchor`
- `tests.test_candidate_bundle_runtime.CandidateBundleRuntimeTest.test_mainline_dragon_source_enters_evaluation_before_limit_up_laggard`
- `tests.test_candidate_bundle_runtime.CandidateBundleRuntimeTest.test_anchor_reversal_downgrade_never_becomes_primary_when_alone`
- `tests.test_candidate_bundle_runtime.CandidateBundleRuntimeTest.test_candidate_bundle_uses_ai_server_narrative_over_raw_communication_industry`
- `tests.test_anchor_reversal_contracts.AnchorReversalContractsTest.test_trade_narrative_migration_uses_narrative_anchor_before_raw_mainline_anchor`
- `tests.test_candidate_trace_contracts.CandidateTraceContractsTest.test_trade_narrative_sector_is_used_as_visible_sector`
- `tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_sector_snapshot_keeps_known_anchor_above_limit_up_laggard`
- `tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_anchor_with_ma_roll_path_enters_comparison_ahead_of_limit_up_laggard`
- `tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_anchor_reversal_downgrade_cannot_be_primary_when_only_laggard_passes_shape`
- `tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_failed_anchor_laggard_arbitrage_is_no_participation`
- `tests.test_candidate_trace_contracts`
- `tests.test_candidate_quality_renderer.CandidateQualityRendererTest.test_renderer_outputs_sniper_ascii_selection_graph`
- `tests.test_final_conclusion_renderer.FinalConclusionRendererTest.test_candidate_trade_directive_replaces_legacy_counts_when_selected_target_exists`
- `tests.test_action_plan_renderer.ActionPlanRendererTest.test_candidate_quality_trace_renders_anchor_reversal_fields`
- `tests.test_action_plan_renderer.ActionPlanRendererTest.test_candidate_quality_blocks_entry_when_anchor_reversal_is_no_participation`
- `tests.test_candidate_selection_stage.CandidateSelectionStageTest.test_conviction_list_renders_anchor_reversal_inside_reason`
- `tests.test_decision_statistics.DecisionStatisticsTest.test_daily_panel_prefers_current_primary_over_stale_same_day_ledger_records`
- `tests.test_report_runtime.ReportRuntimeTest.test_runtime_inserts_single_final_target_solution_before_account_advice`
- `tests.test_report_runtime.ReportRuntimeTest.test_daily_judgment_front_panel_uses_anchor_primary_not_same_day_observation_records`

#### 7. Wrong vs Correct

Wrong:

```text
High score + limit-up shape -> assign 明日主买对象, even when the stock is only a
low catch-up or arbitrage sample relative to the sector anchor.
```

```text
One-day limit-up laggard -> replace a lower-rising sector anchor, even when the
anchor has repeatable acceptance, capacity, and MA binding.
```

Correct:

```text
Find the sector anchor first, classify the candidate relative to that anchor,
then assign main/backup/observation. If the candidate cannot explain why it is
better than watching the anchor, keep it as observation.
```

```text
Use limit-up as supporting evidence only after anchor identity is valid. When a
known sector anchor has repeatable acceptance and MA binding, keep it in the
main comparison even if the daily actual rise is modest.
```

(To be filled by the team)

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
