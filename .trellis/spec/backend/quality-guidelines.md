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

### Daily Report Calendar Event Evidence Contract

Calendar event classification must be evidence-first. Do not use `政策催化`
as the fallback when a title is vague, when a remote model returns `其他`, or
when a remote model returns a generic low-confidence policy label.

- Classify by the event subject first: examples include cloud, digital
  finance, data elements, unmanned logistics vehicles, industrial gases, and
  open-source software ecosystems.
- Use `政策催化` only when the title or same-event summary/content contains
  explicit policy, regulator, official document, rule, plan, standard,
  implementation, or official-department evidence.
- Words such as `会议`, `大会`, `论坛`, `展会`, `发布`, `启动`, and `开幕` are event
  forms, not policy evidence by themselves.
- Calendar rows may use existing same-row `summary`, `content`,
  `description`, `detail`, or `source_text` as source evidence. If a new live
  search or news lookup is added, it must be cached with source URL, query
  date, source date, and evidence text before it can affect historical replay.
- Calendar analysis may use existing `xuangubao_data.xuangubao_news` rows only
  as a same-report-date candidate pool. Title substring or include checks are
  candidate retrieval only; they must not be the final evidence decision. A
  news row can enter `calendar_analysis[].source_evidence` only after a
  structured AI evidence decision returns `matched == True`, a valid
  `evidence_index`, and non-low confidence. Undated, query-date-only, or
  different-date news must not affect classification. Matched output should
  include provider, query date, source date, source URL, evidence text, match
  confidence, and policy-evidence status; when the source has no URL, keep a
  stable empty `source_url` plus `source_url_missing == True`.
- The report event table must not render run-ahead wording from event-form
  words alone. Low-evidence neutral rows remain observation/confirmation rows.

Required tests:

- `tests.test_calendar_events_infer` must cover vague/low-evidence conference,
  forum, expo, product-launch, and malformed-LLM cases.
- `tests.test_report_runtime` must cover summary-sensitive calendar cache
  signatures, report-date news evidence candidate retrieval, AI evidence
  acceptance/rejection, undated/query-date-only/different-date news rejection,
  and source-evidence normalization.
- `tests.test_calendar_section_node_runtime` must cover neutral low-evidence
  meetings rendering as observation rather than run-ahead/execution wording.

### ETF Turnover Coverage Contract

`etf_turnover_series` is a sampled aggregation of per-ETF turnover. A 25-row
series is not sufficient evidence by itself; the target-date sample must also
prove coverage quality before the report can use it for institutional-capacity
judgment.

- `get_etf_turnover_series_from_sina_first(...)` must default to
  `overall_timeout_seconds=120` for live collection. Shorter one-shot fetches
  can return a smooth but incomplete sample and understate the final turnover.
- The returned payload must include coverage metadata:
  `coverage_status`, `coverage_anomaly`, `coverage_ratio`,
  `overall_coverage_ratio`, `coverage_reference_count`,
  `latest_covered_etf_count`, and `total_etf_universe_count`.
- Mark the payload partial when the target-date covered ETF count is below 70%
  of the recent prior-sample median, or when the target-date covered ETF count
  is below 95% of the extracted ETF sample pool.
- A partial ETF payload must set `data_status["ETF两市成交额趋势"] == False` and
  `step_status["ETF两市成交额趋势获取"] == False`.
- Report preflight must reject partial ETF payloads even if a request log says
  the fetch succeeded and `rows` has 25 entries.
- Market overview must not derive `机构容量放大 / 机构容量中性 / 机构容量中性偏收缩`
  from a partial ETF payload. It should render sample insufficiency and stop
  using that payload for capacity judgment.

Required tests:

- `tests.test_tushare_input_runtime.TushareInputRuntimeTest.test_etf_turnover_series_flags_latest_coverage_collapse`
- `tests.test_tushare_input_runtime.TushareInputRuntimeTest.test_etf_turnover_series_flags_low_overall_universe_coverage`
- `tests.test_input_runtime.InputRuntimeTest.test_run_input_runtime_rejects_etf_turnover_coverage_anomaly`
- `tests.test_daily_report_render.DailyReportRenderTest.test_report_preflight_fails_when_etf_turnover_series_has_coverage_anomaly`
- `tests.test_market_overview_nodes.MarketOverviewNodesTest.test_market_base_marks_etf_turnover_coverage_anomaly_as_review_needed`

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
- When `final_action` forces 0% and an observation anchor still exists, the
  rendered `不参与依据` must still include a strong reason. Do not let a bare
  “空仓等待 / 禁止参与” sentence stand alone as the only basis.
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
- If `opportunity_comparison.v1` is present and
  `comparison.max_participation_pct < 50`, front-page position repair must force
  observation even when there is no old position. Missing risk price or
  unresolved risk/reward cannot remain paired with a 50%/100% next-day action.

Required tests:

- `tests.test_report_runtime.ReportRuntimeTest.test_runtime_keeps_new_target_observational_when_risk_price_is_missing_without_old_position`
- `tests.test_report_acceptance_audit.ReportAcceptanceAuditTest.test_audit_flags_positive_participation_with_incomplete_opportunity_risk`

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
- When `anchor_reversal_decision in {"降级观察", "不参与"}` rewrites
  `participation_window` to `no_trade`, rebuild every derived execution field
  from that no-trade window: `participation_window_type == "no_trade"`,
  `entry_timing == "no_trade"`, `buy_window == "none"`,
  `ordinary_structure_confirm_allowed == False`, `required_steps ==
  ["只观察，不新增参与"]`, and `ma_reversion_probe_allowed == False`. Do not leave
  a stale `09:50-10:10` structure-confirm window on an observation-only row.
- A `no_trade` row must also overwrite old intraday script fields such as
  `auction_script`, `first_minutes_script`, `board_script`, `reseal_script`,
  `intraday_yellow_line_probe`, `intraday_average_line_cross_probe`,
  `zero_axis_reclaim_probe`, and `daily_ma_entry_probe` with observation-only
  wording. These fields may be consumed directly by report or ledger surfaces,
  so stale board/reseal, small-trial, or buy-qualification wording is a report
  correctness bug even when the top-level participation fields look correct.
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
- When `anchor_reversal_decision in {"降级观察", "不参与"}`, the candidate must
  also render `leader_speed_tier_code == "not_leader"` and
  `leader_speed_tier == "观察样本"`. Do not leave an old
  `extreme_acceleration`, `strong_trend`, or `large_capacity_trend` label on a
  downgraded limit-up / T-board sample.
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
| Candidate has `MA5 < MA7` and has not reclaimed MA7 with volume-backed high-close reversal | Keep it in repair observation; capacity, sector-anchor, or core labels must not promote it to main/backup comparison |
| Mainline anchor is in `dragon_stocks` but not watchlist / limit-up pool | Add it to evaluated candidates before scoring |
| Static industry is `通信设备` but same-day evidence says AI server / NVIDIA / data-center capacity | Preserve `raw_sector == "通信设备"`, set `trade_narrative_sector == "AI算力基础设施"`, and search the narrative-sector anchor first |
| Limit-up laggard scores, probability, or inertia rank higher than the known anchor | Anchor still ranks first; laggard stays observation |
| Candidate is low catch-up, arbitrage, or follower | `降级观察`, no main or backup identity |
| Downgraded candidate previously had a board/reseal action sentence | Replace with observation-only wording and no new participation |
| Downgraded candidate already had structure-confirm execution fields | Rebuild no-trade execution fields; no stale `09:50-10:10` window |
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
| Base MA5 below MA7 repair | 长电科技-like capacity candidate has `MA5 < MA7`, no volume-backed MA7 reclaim, and only a repair candle | repair observation; not main/backup |
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

### Daily Report Front Observation Qualification Contract

The final report has two different object layers:

- `final.execution_object`: the only source of next-day new-entry execution.
- `final_target_resolution.watch_target`: a front-page observation object that
  may be tracked when the final position is `0%`, but must not become new-entry
  execution.

Candidate rows must carry a machine-readable front-observation qualification so
runtime code does not infer front-page identity from source order, weak status
labels, or old fallback fields.

#### 1. Scope / Trigger

Use this contract when changing:

- `scripts/report/selection_workflow.py`
- `scripts/report/runtime.py`
- front-page selected candidate resolution
- candidate pool adapters from extreme-conviction, decision-ledger, or snapshot
  records
- Mermaid / audit pages that explain final object identity

#### 2. Signatures

Every `selection_workflow.v1["candidate_pool"][]` row must include:

```python
{
    "stock": {"name": "str", "code": "str", "sector": "str"},
    "status": "最终执行对象 | 降级观察 | 不参与 | 过程候选",
    "reversal_decision": "可作为主对象 | 可作为补位 | 降级观察 | 不参与 | str",
    "sector_role": "str",
    "front_observation_qualified": True | False,
    "front_observation_reason": "str",
    "observation_layer": "execution_object | front_observation | process_observation",
}
```

`_runtime_selection_workflow_observation_target(workflow)` returns the first
candidate whose `front_observation_qualified is True`; rows with
`front_observation_qualified is False` must be skipped even when their status is
`降级观察`.

#### 3. Contracts

- `_candidate_source_rows(...)` must prepend the explicit
  `selected_position_candidate` before raw candidate pools, then dedupe by stock
  key. This preserves the already-resolved runtime object before source-order
  fallback rows.
- `front_observation_qualified == True` means front-page observation only. It
  does not imply new-entry execution and must not populate `new_entry_target`
  when final position is `0%`.
- `front_observation_qualified == False` means process evidence only. Runtime,
  front-page rendering, and candidate-quality panels must keep it outside the
  final observation object.
- A `可作为主对象` row with a core role such as `板块锚`, `主线核心`, or
  `明日主买对象` may keep front-observation qualification when the final position
  is `0%`.
- A `降级观察` row may keep front-observation qualification only when its role
  still explains front-page tracking, such as `大容量中军`, `分支龙头`,
  `主线核心`, or `板块锚`.
- Roles such as `观察样本`, `跟风样本`, `过程候选`, `低位补涨`, `套利工具`, and
  `候选观察补充` default to process evidence.
- Missing sector-anchor evidence, inability to explain why not to choose the
  sector anchor, or a row that is only strong by limit-up / score / source-order
  evidence must stay process evidence.
- Legacy workflow rows without `front_observation_qualified` may only use the
  conservative compatibility path: `reversal_decision == "可作为主对象"` plus a
  core role, or an explicit current observation role that is not process-only.
- `_resolve_runtime_current_core_candidate(...)` must not let weak `best_stock`
  or `watch_anchor` fallback override a selected candidate unless that fallback
  has positive current core evidence.
- When `final.execution_object` is empty, every non-final candidate must remove
  inherited text claiming it has already entered the next-day execution
  conclusion or B1/B2 plan. Report acceptance must reject that contradiction
  before any official artifact is written.

#### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| `final.position_pct == 0` and qualified front observation exists | `watch_target` may be set; `new_entry_target` stays empty |
| Candidate is `降级观察 + 观察样本 + 本板块锚未识别` | `front_observation_qualified == False`; process evidence only |
| Candidate is `降级观察 + 大容量中军 + 主线内核` | may be front observation; still not new-entry execution |
| Candidate is `可作为主对象 + 板块锚`, but final position is `0%` | may be front observation; execution stays empty |
| Explicit selected object is also in raw pools | selected row wins source order; raw duplicate is skipped |
| Weak `best_stock` differs from selected object and has no positive core evidence | selected object is kept |
| Old workflow row lacks qualification field | use conservative compatibility path only |
| Final object is empty but a process candidate says it entered the next-day conclusion | normalize the candidate reason and fail report acceptance if the contradiction remains |

#### 5. Good / Base / Bad Cases

| Case | Input | Expected Output |
|---|---|---|
| Good front observation | 雅克科技 is `降级观察 + 大容量中军 + 主线内核` | `watch_target=雅克科技`, `new_entry_target={}` |
| Good explicit selected | 中船特气 is explicit selected and raw pool first item is 双星新材 | selected object stays ahead of raw fallback |
| Good anchor observation | 豫能控股 is `可作为主对象 + 板块锚`, final position `0%` | front-page observation allowed; no new-entry execution |
| Bad process promotion | 双星新材 is `降级观察 + 观察样本 + 本板块锚未识别` | skipped for `watch_target` |
| Bad weak fallback | `best_stock` is 双星新材, selected object is 中船特气, best stock has no core evidence | best stock does not override selected |
| Bad 0% execution | report has no execution object but a watch target exists | no execution hit, no `new_entry_target` |

#### 6. Tests Required

- `tests.test_selection_workflow.SelectionWorkflowTest.test_front_observation_qualification_separates_yake_from_shuangxing_process_sample`
- `tests.test_selection_workflow.SelectionWorkflowTest.test_limit_up_without_reversal_cannot_be_final_object`
- `tests.test_report_runtime.ReportRuntimeTest.test_final_target_resolution_skips_process_observation_and_keeps_front_observation`
- `tests.test_report_runtime.ReportRuntimeTest.test_front_page_selected_candidate_keeps_explicit_observation_before_extreme_fallback`
- `tests.test_report_runtime.ReportRuntimeTest.test_runtime_final_resolution_keeps_workflow_core_as_watch_target_when_position_is_zero`
- `tests.test_report_runtime.ReportRuntimeTest.test_zero_participation_downgraded_anchor_sample_does_not_become_final_watch_target`
- `tests.test_selection_workflow.SelectionWorkflowTest.test_zero_position_candidate_cannot_keep_stale_final_conclusion_reason`
- `tests.test_report_acceptance_audit.ReportAcceptanceAuditTest.test_audit_flags_candidate_claiming_final_conclusion_when_final_object_is_empty`

#### 7. Wrong vs Correct

Wrong:

```text
status == 降级观察 -> first candidate in source order becomes watch_target.
```

```text
best_stock exists -> overwrite selected_position_candidate even without current
core evidence.
```

Correct:

```text
candidate_pool row writes front_observation_qualified. Runtime consumes that
field first; process-only rows stay appendix/process evidence.
```

```text
Explicit selected candidate enters the candidate pool first. Weak fallback rows
can only override it with positive current core evidence.
```

### Daily Report Market Wording Consistency Contract

- When `mainline_capacity_regime_summary.mainline_regime` is `无主线`,
  `混沌轮动`, or `混沌接力`, appendix market analysis must render
  `当前主线: 暂无确认主线`. Strong sectors may remain under candidate evidence,
  but none may be relabeled as the confirmed current mainline.
- Market-volume wording must distinguish breadth from downside-tail pressure.
  When advancing stocks outnumber declining stocks but the limit-down count is
  elevated, the turnover row should state that the limit-down side remains
  under pressure; it must not call the whole profit effect weak while the next
  row calls breadth strong.
- The Markdown and Bear HTML must use the same wording because Bear HTML reads
  the finalized Markdown and must not recompute either judgment.

Required tests:

- `tests.test_market_analysis_builder.MarketAnalysisBuilderTest.test_build_market_and_sector_analysis_contract_downgrades_stale_mainline_when_capacity_regime_has_no_mainline`
- `tests.test_market_analysis_builder.MarketAnalysisBuilderTest.test_build_market_and_sector_analysis_contract_separates_positive_breadth_from_limit_down_pressure`
- `tests.test_market_overview_builder`
- `tests.test_daily_report_markdown_html`
- The generated target-date Markdown must pass
  `scripts/report/report_acceptance_audit.py`, and its Bear HTML must preserve
  the same position, execution object, and action type.

### Tushare A/B Daily Query Contract

#### 1. Scope / Trigger

Use this contract when changing Tushare environment selection, source-health
labels, or the single-day full-market `daily` query used by turnover and market
breadth calculations. It prevents a B-channel pagination contract from being
sent to an A-channel SDK POST endpoint.

#### 2. Signatures

```python
create_tushare_pro_api(
    *,
    ts_module=None,
    token=None,
    http_url=None,
    timeout_seconds=8,
) -> DataApi | TushareReplayProApi

fetch_stock_daily_turnover_records(
    trade_date,
    *,
    pro=None,
    ts_module=None,
    page_limit=1000,
    page_retry_count=5,
) -> list[dict]
```

Environment contract:

```text
TUSHARE_TOKEN=<non-empty token>
TUSHARE_HTTP_URL=<one A SDK POST endpoint or one/more comma-separated B replay endpoints>
```

#### 3. Contracts

- A configured URL that does not end with `/tushare/pro` uses the Tushare SDK
  POST client and is reported as `Tushare A 通道`.
- A single-day full-market A query must call
  `pro.daily(trade_date=YYYYMMDD, fields=...)`. It must not include
  `start_date`, `end_date`, `limit`, or `offset`.
- A configured URL ending with `/tushare/pro` uses `TushareReplayProApi` and is
  reported as `Tushare B 通道`.
- The B single-day query keeps the replay pagination contract:
  `start_date=YYYYMMDD`, `end_date=YYYYMMDD`, `limit=<page_limit>`, and an
  increasing `offset` until the returned page is shorter than `page_limit`.
- This A-channel change must not alter B pagination. The current B adapter
  treats an empty continuation page as an error; a legal exact-multiple empty
  tail remains a known pre-existing B issue for a separate change.
- Both channels normalize returned rows to the same record fields, including
  `trade_date`, `ts_code`, `stock_code`, `market`, OHLC values, `pct_chg`,
  `amount_raw_qianyuan`, `amount_yi`, and `data_source == "tushare.daily"`.
- `daily_report_source_health.py` must derive the visible A/B channel name from
  the resolved HTTP URL and pass that same token and URL into the connectivity
  check. A uses `index_basic`; B keeps its `daily` check. Missing credentials or
  a failed check must stop report generation.
- An A response with no valid daily rows is a failed attempt and must follow the
  retry path. A non-empty response alone does not prove full-market coverage;
  run-level checks must retain and review the returned row count.
- Tokens are environment-only data. Tests, logs, reports, health-check JSON,
  and Bear HTML must redact token values and credential-bearing URLs.

#### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| `trade_date` cannot be normalized | Return `[]` without a remote call |
| A URL is configured | Use one non-paginated `trade_date` request per attempt |
| A returns no valid normalized rows | Treat the attempt as failed and retry |
| A request fails before retries are exhausted | Wait briefly and retry the same non-paginated request |
| A request still fails after `page_retry_count` retries | Re-raise the last error |
| B URL is configured | Keep same-day `start_date` / `end_date` pagination |
| B page after offset zero is empty | Preserve the current retry/raise behavior in this A-only change; review exact-multiple termination separately |
| Token or HTTP URL is missing | Source health reports failure and stops generation |
| Connectivity check succeeds | Report the resolved A/B channel name and returned provider without exposing credentials |

#### 5. Good / Base / Bad Cases

| Case | Input | Expected Output |
|---|---|---|
| Good A full market | A URL plus `2026-07-10` | `daily(trade_date="20260710", fields=...)`; no pagination fields |
| Good B full market | B replay URL plus `2026-07-10`, page size 1000 | Same-day range calls with offsets `0, 1000, ...` until complete |
| Base invalid date | Empty or malformed date | `[]`; no API call |
| Base transient A failure | First A call fails, next succeeds | Same A payload retried; normalized rows returned |
| Bad mixed contract | A URL plus `start_date`, `end_date`, `limit`, or `offset` | Invalid implementation; can return incomplete or rejected data |
| Bad ambiguous tail | B offset page is empty after a full prior page | Current code raises; do not silently redefine it as complete without a separate B completeness decision |
| Bad source label | A URL rendered as `Tushare B 通道` | Health output is invalid because it hides the active source contract |

#### 6. Tests Required

- `tests.test_tushare_turnover_service.TushareTurnoverServiceTest.test_fetch_stock_daily_turnover_records_uses_trade_date_for_a_channel`
- `tests.test_tushare_turnover_service.TushareTurnoverServiceTest.test_fetch_stock_daily_turnover_records_retries_empty_a_channel_result`
- `tests.test_tushare_turnover_service.TushareTurnoverServiceTest.test_fetch_stock_daily_turnover_records_paginates_single_day_rows`
- `tests.test_daily_report_source_health.DailyReportSourceHealthTest.test_tushare_a_proxy_is_probed_and_can_pass`
- `tests.test_daily_report_source_health.DailyReportSourceHealthTest.test_tushare_health_retries_once_before_stopping_generation`
- `tests.test_tushare_client`
- A live A-channel smoke check must return at least one `index_basic` row.
- A generated target-date report must pass its consistency check and
  `scripts/report/report_acceptance_audit.py`.

#### 7. Wrong vs Correct

Wrong:

```python
pro.daily(
    start_date=trade_date,
    end_date=trade_date,
    limit=1000,
    offset=0,
)
```

Correct for A:

```python
pro.daily(trade_date=trade_date, fields=fields)
```

Correct for B:

```python
pro.daily(
    start_date=trade_date,
    end_date=trade_date,
    fields=fields,
    limit=page_limit,
    offset=offset,
)
```

## Scenario: Read-Only Market Language Research Artifact

### 1. Scope / Trigger

Use this contract when adding or changing research evidence that translates
minute price paths into force scope, pressure direction, phase, event timing,
or replay-only validation. The artifact may explain the report, but it must not
change the formal candidate, final object, position, B1/B2 plan, or exit action.

### 2. Signatures

```python
build_market_language_source_projection(
    data,
    *,
    target_date,
    analysis_mode,
) -> dict

build_market_language_translation(
    projection,
    *,
    target_date,
    analysis_mode,
    artifact_origin="computed",
    include_posthoc=False,
) -> dict

read_verified_saved_report_markdown(
    report_path,
    expected_markdown,
) -> str

PostgresDailyFactDb.replace_market_language_translation_artifact(artifact)
PostgresDailyFactDb.load_market_language_translation_artifact(target_date)

_market_stats_from_daily_rows(
    rows,
    zt_count,
    dt_count,
    *,
    target_date=None,
) -> dict

PostgresDailyFactDb.query_market_breadth_counts(trade_date) -> dict

load_fresh_market_language_translation(
    target_date,
    *,
    root_dir=".",
    service=None,
) -> dict | None
```

Stable identifiers and paths:

```text
schema_version = market_language_translation.v1
source_policy = postgresql.market_language_translation.v1
fresh path = data/market-language/fresh/<target_date>.json
replay path = snapshots/replay/market-language/<target_date>.json
```

### 3. Contracts

- Every source records `target_date`, `source_date`, `query_date`, granularity,
  time semantics, fields, and provider. A missing `source_date` does not inherit
  the target date. A missing `query_date` remains null; a non-null value must be
  an exact ISO date and cannot precede `source_date`.
- Tushare and PostgreSQL producers that answer an exact-date market-breadth
  query must stamp `market_stats.trade_date` and `market_stats.source_date` at
  that producer boundary. The translator must not infer either value from the
  outer report date. Preserve an explicit conflicting child date so validation
  can exclude it instead of silently relabeling the fact.
- Replay treats market breadth as complete only when positive up/down counts
  also carry `trade_date` or `source_date` equal to the replay target. Undated
  legacy counts must be replaced from the exact-date fact reader, preserving
  its `trade_date`, `source_date`, and `query_date` in `market_stats`.
- One-minute evidence must match the complete A-share interval-end grid:
  exactly 240 rows across `09:31-11:30` and `13:01-15:00`. Five-minute rows,
  illegal session times, internal gaps, or a missing `14:56-15:00` tail cannot
  produce `evidence_status=sufficient`.
- Direction and short/long slope comparison use a `0.05 bp/trading-minute`
  noise band. Each event stores `confirmation_basis`, `confirmation_quality`,
  and `directional_follow_through_at`. Three overlapping 15-minute slopes only
  establish slope persistence; they are not three independent observations.
- The 20-minute curvature proxy is shared by the production artifact and the
  research generator: `kappa20(t) = [s5(t) - s5(t-15)] / 15`. Classification
  uses the full-precision value; round only for rendered display.
- A confirmed event may tolerate at most two neutral minutes. A third neutral
  minute invalidates it; an opposite direction invalidates it immediately.
- When the latest minute surface is balanced or unclear and an event remains
  active, the artifact direction follows that active event. Conflicting end-of-
  day votes remain counter-evidence and cannot relabel the event or its times.
- `whole_market` requires cap-weighted direction, market breadth, and sector
  synchrony to align. Sector direction text alone is insufficient; the cross-
  sector synchrony percentage must be present and at least 50%, the semantic
  majority floor. `crowding` requires an explicit source-dated crowding fact;
  anchor cases cannot manufacture a general crowding threshold.
- The artifact remains in the entry-point local scope and reaches the final
  renderer through an explicit optional parameter. Do not write it into
  `data`, `market_research_snapshot`, or `execution_stage_context`.
- Render it only after the final `selection_workflow` and
  `final_target_resolution` pass, under `## 市场语言翻译（研究证据）`, after the
  formal action content.
- Full and summary output receive independent deep copies. Compare the original
  artifact canonical hash before and after both renders.
- Fresh persistence occurs only after both variants, report checks, and whole-day
  fact sync succeed. Replay persistence never calls the fresh writer.
- Before either entry path writes the research artifact, read the saved full
  Markdown from disk and compare it byte-for-byte with the accepted in-memory
  body. A missing, unreadable, or different file stops artifact persistence.
- Replay T+1/T+2 price ranges require an explicit open-trading-day calendar,
  source date, query date, exchange-qualified instrument identity, and distinct
  dates. Missing T+1 data does not move T+2 forward. Future price, MFE/MAE, and
  low/high-zone facts stay under `posthoc_validation`; both the fresh source
  projection and fresh artifact contain no future inputs.
- PostgreSQL replacement deletes only the exact target date plus exact research
  `source_policy`, in the same transaction as insert. Whole-day resave preserves
  those rows. Report output directories and artifact roots are separate inputs;
  the command entry always writes replay artifacts below the project root even
  when a report is saved to an absolute external directory.
- When `A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME=1`, a PostgreSQL exact-date miss is
  final for the fresh artifact reader. It must return `None` and must not read
  `data/market-language/fresh/<target_date>.json` from the local filesystem.

### 4. Validation & Error Matrix

| Situation | Required Handling |
|---|---|
| Source date is missing or differs from target date | Exclude it from derived judgment; report missing evidence |
| Query date is missing | Keep null; do not substitute target date |
| Query date is malformed or earlier than source date | Reject before render or persistence |
| Claimed one-minute path has gaps or five-minute spacing | Downgrade granularity; emit no one-minute event time |
| Minute path has 230-239 rows or misses the closing tail | Keep partial; never mark sufficient |
| Direction/phase or event quality combination is invalid | Raise validation error before rendering or persistence |
| A fixed-window direction/phase is invalid, or either evidence list references a missing id | Raise validation error before rendering or persistence |
| Exact-date breadth producer omits its child trade/source date | Fix the producer; do not make the translator inherit the outer report date |
| Replay snapshot has complete but undated market-breadth counts | Query the exact-date fact reader and replace counts while retaining source dates |
| Width disagrees with index/sector direction, or sector has direction text only | Do not emit `whole_market`; preserve counter-evidence |
| Active minute event conflicts with end-of-day votes | Keep the active event direction; preserve the vote conflict as counter-evidence |
| Fresh artifact contains posthoc facts | Reject or normalize to `posthoc_validation=null` before use |
| Fresh source projection receives future bars/calendar/overlap | Omit them from the projection; replay mode owns posthoc inputs |
| T+ calendar is absent, exchange differs, or T+1 bar is missing | Keep the affected range null; never substitute another date or exchange |
| AgentRunner receives fresh mode | Reject at `run()` entry, including custom-loader calls |
| Saved full-report path is absent, unreadable, or differs | Raise `SavedReportVerificationError`; do not write artifact |
| Report check or whole-day sync fails | Do not write fresh artifact |
| Replay final check fails | Do not write replay artifact |
| Exact target-date artifact is absent | Reconstruct only from target-date facts or return insufficient; never load nearest date |
| PostgreSQL-only fresh artifact lookup misses | Return `None`; do not fall back to local fresh JSON |

### 5. Good / Base / Bad Cases

- Good: target-date one-minute data, breadth, and sector facts align; the report
  renders a sourced research section while formal decision projections and the
  source artifact hash remain unchanged.
- Good: PostgreSQL writes the artifact, whole-day facts are saved again, and the
  artifact loads with the same canonical hash.
- Good: an exact-date Tushare or PostgreSQL breadth query returns `up_count`,
  `down_count`, `trade_date`, and `source_date`; source projection retains the
  market-breadth source with that same date.
- Good: an old replay snapshot has undated breadth counts, so replay replaces
  them from PostgreSQL and retains the exact `trade_date/source_date/query_date`.
- Base: only source-dated end-of-day facts exist; output is partial or
  insufficient and contains no invented minute timestamp.
- Base: a message shock remains inside three overlapping windows but price does
  not continue; record `slope_persistence_only`, then preserve invalidation.
- Bad: assign the artifact into shared report data and rely on call order to
  keep formal decisions unchanged.
- Bad: inspect accepted in-memory Markdown after saving, without reading the
  actual file, then persist a research artifact beside a corrupted report.
- Bad: treat a smooth index arc as `whole_market` without breadth and sector
  alignment, or infer program-trading identity from curve shape.
- Bad: omit dates from `market_stats`, then make the translator borrow the
  outer report date. That turns an unproved child fact into false same-date
  evidence and hides a broken producer contract.
- Bad: PostgreSQL-only lookup returns no artifact, then the reader silently
  loads a same-date local JSON created by another runtime.

### 6. Tests Required

- `tests.test_market_language_translation`: source dates, full minute grid,
  noise band, event quality, neutral buffer, phase legality, scope alignment,
  explicit crowding, active-event direction, future isolation, and T+1/T+2
  calendar/exchange/date rules.
- `tests.test_tushare_input_runtime` and `tests.test_postgres_daily_fact_db`:
  exact-date market-breadth producers retain child trade/source dates, and the
  real producer shape survives source projection.
- `tests.test_daily_report_render`: independent full/summary copies, real
  runtime decision-projection equality, canonical hash stability, and saved
  Markdown readback errors.
- `tests.test_daily_report_agent_runner`: replay-only enforcement, pre-save and
  post-save checks, corrupted disk report, and replay write timing.
- `tests.test_report_replay` and
  `tests.test_market_language_translation_lifecycle`: exact-date reconstruction,
  undated breadth replacement with source-date retention, PostgreSQL-only miss
  behavior, fresh/replay path separation, and persistence ordering.
- `tests.test_postgres_daily_fact_db.PostgresMarketLanguageIntegrationTest`:
  actual database round trip across whole-day resave, followed by cleanup.
- `tests.test_front_page_v2_renderer` and
  `tests.test_daily_report_markdown_html`: evidence placement and user wording.
- `tests.test_quant_pressure_one_minute_study`: anchor-case timing, formula/report
  semantics, shared full-precision curvature, formal-window shading, and
  checked-in HTML reproducibility.

### 7. Wrong vs Correct

Wrong:

```python
data["market_language_translation"] = artifact
outputs = build_report_outputs(data)
write_replay_artifact(artifact)  # trusts the in-memory body after save
```

Correct:

```python
artifact = prepare_market_language_translation(source_data, target_date=target_date)
outputs = build_report_outputs(
    source_data,
    market_language_translation=artifact,
)
saved_full = read_verified_saved_report_markdown(
    saved_paths["full"],
    outputs["full"],
)
run_final_report_check(saved_full)
write_replay_artifact(artifact)
```

Wrong for exact-date breadth:

```python
market_stats = {"up_count": up_count, "down_count": down_count}
source_date = report_data["trade_date"]  # The translator guesses ownership.
```

Correct for exact-date breadth:

```python
market_stats = {
    "up_count": up_count,
    "down_count": down_count,
    "trade_date": queried_trade_date,
    "source_date": queried_trade_date,
}
projection = build_market_language_source_projection(
    {"market_stats": market_stats},
    target_date=queried_trade_date,
    analysis_mode="fresh",
)
```

Wrong for PostgreSQL-only artifact reads:

```python
loaded = postgres_reader(target_date)
return loaded or read_local_fresh_json(target_date)
```

Correct for PostgreSQL-only artifact reads:

```python
loaded = postgres_reader(target_date)
if loaded is not None:
    return loaded
if os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1":
    return None
return read_local_fresh_json(target_date)
```

### Daily Report Index Cross-Validation Contract

Reports dated `2026-07-13` or later must not render index facts until all six
report indices pass exact-date, independent-source cross-validation:

- 上证指数 `000001`
- 深证成指 `399001`
- 创业板指 `399006`
- 中证全指 `000985`
- 中证500 `000905`
- 中证1000 `000852`

Required behavior:

- The primary index payload must carry `trade_date`, `close`, `pre_close`,
  `change_pct`, the expected six-digit index code, and a non-empty provider
  identity. Numeric evidence must be finite; `NaN` and positive or negative
  infinity are missing facts. A prior trading day's last available row is not a
  valid substitute for the target date.
- Tushare `index_daily` is the normal primary source. Tencent `fqkline` day data
  is the independent verification source. Both sides must identify the target
  date and must not belong to the same provider family.
- The maximum absolute difference is `0.05` index points for `close` and
  `pre_close`, and `0.02` percentage points for `change_pct`.
- Validation produces `report_index_cross_validation.v1` with six named checks,
  both source facts, measured differences, tolerances, status, and failure
  reasons. A conflicting result stops report generation; do not silently pick
  one source.
- Fresh collection before `2026-07-13` must not create or track this artifact.
  Older reports are revalidated only when they already carry the artifact.
- Report pre-generation checks must recompute source differences and compare the
  current report payload with the saved primary evidence, including code and
  provider identity. Every saved verification item must still identify Tencent
  `fqkline` day data. A stale `status` value cannot validate changed facts.
- A successful artifact must contain exactly one check for each expected
  name/code pair. Duplicate checks, unknown codes, non-empty failure/reason
  fields, or stored difference values that disagree with recomputation are
  contradictory evidence and must stop generation.
- `index_cross_validation` must be included in the PostgreSQL daily-report fact
  projection. A PostgreSQL reload must restore all six checks and pass the same
  validation before report generation.
- Reports before the contract start date are not batch-migrated here. If an
  older report already carries this artifact, it must still pass validation.

Required tests:

- `tests.test_tushare_input_runtime`: exact target-date selection and source
  field retention.
- `tests.test_index_cross_validation`: Tencent parsing, six-index success,
  stale dates, non-finite values, missing or replaced source identity, value
  conflicts, same-provider rejection, changed payloads, and stale-success
  rejection.
- `tests.test_market_state_request`: request result, status, and failure log
  propagation, plus no fresh validation before the contract start date.
- `tests.test_daily_report_entry_preflight`: required evidence from the contract
  start date and successful `6/6` continuation.
- `tests.test_postgres_daily_fact_db`: validation evidence survives a full fact
  save/reload and report pre-generation checks revalidate the restored artifact.

### Turnover Core Quote Completeness Contract

- The turnover core table must resolve quote fields from the structured
  `turnover_rank` / `turnover_over_100b` row before using auxiliary
  `stock_full_info`. PostgreSQL-only rendering must not lose quote fields that
  already belong to the ranked turnover fact.
- When the displayed `turnover_over_100b` row already carries quote fields,
  those fields take precedence over auxiliary quote lookup results. Auxiliary
  data may fill missing fields but must not overwrite the displayed row's own
  facts.
- `change_pct`, open, high, low, and close must remain distinguishable from
  missing data. Missing quote facts render as `待补` / `-` and skip candlestick
  analysis; they must never be converted into a synthetic `0.00%` and four
  `0.00` prices.
- Report acceptance requires a visible `涨跌幅` column in the turnover core
  table, rejects an all-zero quote row, and rejects a turnover core section with
  no recognizable ranking table. A legitimate unchanged stock remains valid
  when its prices are real and only `change_pct` is zero.
- Before saving a generated report, acceptance receives the exact turnover rows
  selected for display and compares rank, stock identity, turnover, change
  percentage, and available OHLC fields at two-decimal display precision. Any
  row-count or nonzero value mismatch stops the report from being accepted.
- Source comparison uses the same quote aliases and zero-value interpretation as
  the renderer. A zero change is factual only when that source row also carries
  four complete positive prices; otherwise it remains missing and may render as
  `待补` without a false mismatch.

Required tests:

- `tests.test_market_activity_domain_report_sections`: ranked turnover rows
  retain their quote fields, while genuinely missing quotes remain explicit.
- `tests.test_report_acceptance_audit`: missing change columns and synthetic
  all-zero quotes are rejected without rejecting a real zero-change row; every
  source-comparison field and renderer quote alias has a nonzero mismatch
  counterexample, while an incomplete placeholder zero remains missing.
- `tests.test_daily_report_entry_preflight`: report generation passes the exact
  displayed turnover rows into acceptance before writing the official report.

### Candidate Summary Consistency Contract

- The front-page candidate summary must use
  `selection_workflow.candidate_pool` as a candidate source. It must not infer
  that there are no process candidates merely because legacy execution-stage
  candidate lists are empty.
- A workflow candidate row may carry the stock under its nested `stock` field.
  Candidate summaries must preserve that identity and may use
  `eliminated_reason` as the non-winning reason.
- If the workflow reports `归一候选N只` with `N > 0`, the report must not say
  `也没有过程候选`, `无过程候选`, or equivalent zero-candidate wording. This
  contradiction must stop the official report from being accepted.
- Process candidates remain evidence only. Adding them to the summary source
  must not create an execution object, change position sizing, or promote a
  candidate into the final action.

Required tests:

- `tests.test_two_layer_decision_payload`: a zero-position workflow with nested
  candidate rows preserves a visible process-candidate summary while keeping
  the final object empty.
- `tests.test_report_acceptance_audit`: a positive normalized candidate count
  conflicts with direct and synonymous claims that there are no process
  candidates.

(To be filled by the team)

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
