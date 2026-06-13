# Stage 3 Explorer Notes

只读探索完成，未改文件，未运行测试。

## Current chain

* Candidate pool mainly comes from `scripts/domains/execution_chain/candidate_selection_stage.py`, where `step2_bundle` produces `core_stocks`, `secondary_stocks`, `crossline_observation_stocks`, `gem_observation_stocks`, and related lists.
* `scripts/report/two_layer_decision_payload.py` currently turns those process candidates into derivation-layer rows.
* Scoring/layering comes from candidate quality scorecard and candidate quality contracts, but current rendering is not a same-pool five-dimension verdict.
* Final object comes from runtime `final_target_resolution`, then `two_layer_decision_payload` and `sniper_target_derivation` store it into `data`, `execution_stage_context`, and `market_research_snapshot`.
* `sniper_target_derivation` already creates a canonical target.

## Root cause of Shanghai Petrochemical / Yuneng chain break

Shanghai Petrochemical is rendered as `过程候选 / 被替换`, but the reason is generic: the final parser did not select it. That is circular and does not explain same-pool differences.

The replay therefore shows a path replacement but not why the replacement happened.

## Minimal stage 3 recommendation

Use existing `sniper_target_derivation` or a thin shared helper to generate `candidate_pool_verdict`; do not rewrite the candidate generation chain first.

Recommended fields:

* `pool_source`: why each stock entered the same pool.
* `final_object`: reuse canonical target.
* `dimension_verdicts`: fixed five columns:
  * mainline/sector fit,
  * stock structure,
  * funds confirmation,
  * account fit,
  * risk/missing data.
* `winner`: the final object candidate.
* `downgraded_or_rejected_top3`: important rejected/downgraded candidates.
* `why_this_not_others`: one sentence from five-dimension differences, not a circular replacement reason.

Recommended rendering order:

1. final object;
2. same-pool five-dimension table;
3. path graph.

Candidate quality rendering can stay as process evidence, but should prefer the verdict packet and not recompute winners.

## Recommended tests and replay checks

* `tests/test_two_layer_decision_payload.py`: when candidate pool contains Shanghai Petrochemical and Yuneng, output same-pool five-dimension verdict with a concrete Shanghai Petrochemical losing dimension.
* `tests/test_report_runtime.py`: when final target is Yuneng but old best/watch candidate is Shanghai Petrochemical, front page, final target process, candidate quality, and appendix final object agree.
* `tests/test_action_plan_renderer.py`: candidate quality area renders Shanghai Petrochemical only as process evidence and shows its five-dimension issue.
* `tests/test_report_acceptance_audit.py`: require `why_this_not_others` or equivalent five-dimension explanation instead of bare replacement wording.

Replay checks:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_report_runtime tests.test_action_plan_renderer tests.test_report_acceptance_audit
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-04_A股日报_完整版_replay.md
```

Key grep checks:

* `上海石化` should not appear only with `被替换`.
* It must have five-dimension or equivalent concrete reason.
* `豫能控股` must be the only final observation object.

## Risk points

These may bypass the unified final object:

* `best_stock`
* `watch_anchor`
* `selected_position_candidate`
* `unique_action_target`
* `candidate_quality_panel_fields.primary_buy_candidate`
* `candidate_quality_panel_fields.backup_candidate`
* `action_rows`
* final conclusion fallback paths
* two runtime packet build/store sites

Stage 3 must ensure the new verdict packet is stored in both runtime construction paths.
