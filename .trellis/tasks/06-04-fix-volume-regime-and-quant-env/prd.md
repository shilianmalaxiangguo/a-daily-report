# fix: Volume Regime And Quant Environment

## Goal

Make the market-analysis and sector-internal-analysis output describe the real relative volume context and render the real quant-environment detector output. A large absolute two-market turnover number must not automatically become `量能充沛` when the historical comparison says shrinkage, and quant-environment output must not show `待识别` when detector results exist.

## What I Already Know

* The user saw `量能水平: 27791.64亿元，量能充沛，但赚钱效应不足` and stated the real context was severe shrinkage.
* `describe_market_turnover_condition()` currently uses absolute turnover thresholds first.
* The newer market overview path already has `build_turnover_comparison()` in `scripts/domains/market_state/two_market_turnover/nodes.py`, which can label relative states from `market_turnover_history` / `recent_market_turnover_history`.
* Explorer found the 2026-06-04 snapshot lacks `market_turnover_history`, but `top50_turnover_share_series.rows` contains market amount rows for 2026-06-03 and 2026-06-04, enough to identify the `27791.64` vs `31531.25` shrinkage without live data.
* The older `八、市场与板块分析` section currently calls `describe_market_turnover_condition(data)` directly and does not include that relative label.
* `detect_quant_environment()` returns a top-level dict with `summary`, `modes`, and `action`.
* `_build_markdown_sections()` currently reads `quant_environment.get("environment")`, so top-level detector output renders `当前环境: 待识别`.

## In Scope

* Fix quant-environment rendering to support the detector's current top-level output.
* Add relative turnover wording to `市场与板块分析` when history is available.
* Reuse the existing two-market turnover comparison helper instead of inventing a second comparison formula.
* Add focused tests for both user-visible outputs.

## Out of Scope

* Recalibrating all market capacity thresholds.
* Adding new history collection.
* Rewriting `市场基底` or the Top50/Top20 capacity modules.
* Changing official/replay snapshot persistence.

## Non-goals

* Do not claim shrinkage without previous-turnover evidence.
* Do not discard absolute turnover context; combine it with relative context when both exist.
* Do not call live/current data sources from replay-only paths.

## Requirements

* `量化环境识别` should render:
  * `summary` from top-level detector output when present;
  * `modes` and `action` from top-level detector output when present;
  * legacy nested `environment` shape if it still appears.
* `市场与板块分析` should use `build_turnover_comparison(data, target_date)` or equivalent existing comparison output when `market_turnover_history` / `recent_market_turnover_history` exists.
* If explicit market-turnover history is absent but `top50_turnover_share_series.rows` has adjacent `market_amount_yi` values through the target date, derive a local comparison from those rows instead of falling back to absolute turnover wording.
* If the comparison label is `成交额连续回落`, `成交额冲高后回落`, or another shrink/pullback label, it must appear before or inside the volume wording.
* If no history exists, existing absolute-turnover wording can remain.

## Acceptance Criteria

* [ ] A sector-internal-analysis test renders `当前环境: 未检测到明显的量化横行特征` or detected-mode summary instead of `待识别` for top-level detector output.
* [ ] A market-analysis test with current turnover below the previous row renders relative shrink/pullback wording and does not render only `量能充沛，但赚钱效应不足`.
* [ ] Existing market-overview turnover comparison tests still pass.
* [ ] The fix does not create duplicate volume wording in `市场基底`.

## Definition of Done

* Focused tests pass with Python 3.14.
* The implementation reuses existing helpers and touches only the relevant report/wording paths.
* The parent task can cite the test output as evidence for the volume and quant-environment defects.

## Verification

* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_analysis_builder`
* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_domain_report_sections`
* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_overview_builder`

## Technical Approach

* Likely files:
  * `scripts/domains/market_state/sector_fund_flow_enhancer.py`
  * `scripts/report/market_analysis_nodes.py`
  * `scripts/report/market_analysis_builder.py` if `target_date` needs to be passed into node context
  * existing comparison helper in `scripts/domains/market_state/two_market_turnover/nodes.py`
  * `tests/test_market_analysis_builder.py` around the existing market-state wording tests
* Prefer adding `target_date` through the market-analysis builder context over re-parsing dates elsewhere.
