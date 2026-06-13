# fix: Sector Turnover Share Trend

## Goal

Make `板块成交占比趋势 (近5日)` correctly consume both grouped sector-history input and flat `recent_sector_turnover_history` rows, so the report does not render duplicate sectors with fake `0.0% / 待累计` when valid historical turnover-share facts exist.

## What I Already Know

* The user saw T-068 rows such as duplicate `电力` and duplicate `半导体`, all with `0.0%`, `待累计`, and `0.0%` MA5.
* Explorer reproduced the symptom with flat rows in memory.
* `build_sector_fund_inflow_node()` passes:
  `sector_turnover_history=data.get("sector_turnover_history") or data.get("recent_sector_turnover_history") or []`.
* `build_top5_sector_turnover_summary()` currently expects items shaped like:
  `{"sector_name": "...", "history": [{"date": "...", "turnover_share_pct": ...}]}`.
* `recent_sector_turnover_history` is flat:
  `{"date": "...", "sector_name": "...", "turnover_share_pct": ...}`.

## In Scope

* Normalize flat sector turnover rows into grouped per-sector histories before trend calculation.
* Preserve existing grouped input behavior.
* Deduplicate repeated same-sector rows in the top-five output.
* Sort each grouped history by date before calculating latest share, MA3/MA5, and trend sequence.
* Add focused tests for the user-visible report path and, if useful, the tracker function.

## Out of Scope

* Adding a new turnover data source.
* Changing PostgreSQL fact storage.
* Rewriting the whole sector-fund-flow report.
* Changing unrelated mainline turnover summary tables.

## Non-goals

* Do not turn missing or source-failed turnover-share values into positive facts.
* Do not hide missing data behind `0.0%`.
* Do not change table numbering or PSQL source labels in this task.

## Requirements

* `build_top5_sector_turnover_summary()` accepts:
  * grouped rows with `history`;
  * flat rows with `sector_name/name`, `date`, and `turnover_share_pct`.
* Flat rows for the same `sector_name` are grouped into one sector result.
* Rows with missing or non-positive `turnover_share_pct` do not create fake positive trends.
* The rendered table includes one row per sector and real latest/series values when at least one valid share exists.
* The result ordering remains by latest share descending after normalization.

## Acceptance Criteria

* [ ] A test using flat `recent_sector_turnover_history` with repeated `电网设备/电力/半导体` rows renders one row per sector.
* [ ] The same test shows real latest share and formatted sequence instead of `0.0% / 待累计`.
* [ ] Existing grouped-history test still passes.
* [ ] Missing-share rows still render as waiting for accumulation rather than positive facts.

## Definition of Done

* Focused tests pass with Python 3.14.
* The implementation changes only the turnover trend normalization/rendering path and its tests.
* The parent task can cite the test output as evidence for T-068.

## Verification

* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_domain_report_sections`
* `.generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_fund_flow_enhancer`

## Technical Approach

* Preferred implementation point: `scripts/domains/market_state/sector_turnover_trend_tracker.py`.
* Add a small normalizer that detects flat rows and groups them by sector name.
* Keep date sorting local to each sector history.
* User-visible path test should live near `tests/test_market_activity_domain_report_sections.py` existing sector internal-analysis tests.
