# daily report stage 2 market fund sector spine

## Goal

Render the upstream decision spine before candidate selection: market stage, fund structure, sector relationships, `超车 / 失速 / 窗口`, and leader/core validation. This stage makes individual stocks downstream of market/funds/sectors.

## Parent Task

Parent PRD: `.trellis/tasks/06-05-daily-report-full-rewrite/prd.md`

## In Scope

* Build or render packet-backed sections for:
  * `market_stage`
  * `fund_structure`
  * `sector_relationships`
  * `overtake_slowdown_window`
  * `leader_core_validation`
* Use cycle labels:
  * `启动`
  * `发酵`
  * `高潮`
  * `退潮`
  * `冰点`
* Fund structure must separate:
  * market-level risk appetite,
  * sector-level fund migration.
* Sector relationship table should compare the top 3 directions by default:
  * mainline,
  * rival line,
  * potential overtake line.
* `超车 / 失速 / 窗口` must be a main-body module after sector relationships and before leader/core validation.
* Leader/core validation should show one core anchor and one elastic vehicle for each key direction when data exists.

## Out of Scope

* Candidate pool final rewrite. Stage 3 owns this.
* Full appendix migration. Stage 4 owns this.
* New data sources.
* Rebuilding historical snapshots.

## Non-goals

* Do not let a sector section independently name a final stock.
* Do not treat the topic window as the same thing as trading time windows.
* Do not collapse market ice point and strongest-mainline ice point into generic weak wording.

## Done Definition

* Report body can show the upstream spine in this order:
  1. market-wide stage,
  2. fund structure,
  3. sector relationships,
  4. overtake / slowdown / topic window,
  5. leader/core stock validation.
* Position-stake inputs can later consume these section conclusions.
* Existing market research tables remain available as supporting evidence.
* Tests cover rendering order and presence of the `超车 / 失速 / 窗口` main-body section.

## Likely Files

Execution agents should inspect before editing:

* `scripts/report/front_page_v2_renderer.py`
* `scripts/report/market_research_snapshot_nodes.py`
* `scripts/report/mainline_turnover_summary_support.py`
* `scripts/report/market_structure_judgement.py`
* `scripts/report/runtime.py`
* `tests/test_front_page_v2_renderer.py`
* `tests/test_market_research_renderer.py`
* `tests/test_report_runtime.py`

## Acceptance Criteria

* [ ] Individual candidate sections appear after market/fund/sector sections.
* [ ] Both market-wide and sector/mainline cycle labels are visible where data exists.
* [ ] Fund structure renders market risk appetite separately from sector migration.
* [ ] `超车 / 失速 / 窗口` appears in the main body and does not use trading time-window language.
* [ ] Full evidence tables stay available but do not compete with the final answer.

## Implementation Notes

Prefer reusing existing market snapshot and mainline turnover support functions. This stage should mostly reorganize and normalize conclusions, not invent new market facts.
