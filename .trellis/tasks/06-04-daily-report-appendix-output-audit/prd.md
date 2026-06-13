# brainstorm: Daily Report Appendix Output Consistency Audit

## Goal

Fix the report output defects the user found in the generated A-share daily report appendices and process-evidence tables. The work should restore one coherent report surface: sector turnover trends must use real historical rows, quant-environment and volume wording must not hide shrinkage or source mismatch, and observation-review tables must not show stale placeholder rows or a different stock from the resolved report target.

## Mainline Context

This task is part of the daily report decision-loop work, especially the front-page and appendix rule that the final action must be easier to find than process evidence. It also touches the anchor-reversal and small-account target-resolution work because the observed T-116 mismatch is a final-object consistency defect, not only a table-rendering defect.

## What I Already Know

* T-068 `板块成交占比趋势 (近5日)` showed duplicate sectors and all `0.0% / 待累计`.
* Read-only subagent evidence confirms the likely root cause: flat `recent_sector_turnover_history` rows are passed into `build_top5_sector_turnover_summary()` as if each row were a grouped sector object with a `history` list.
* `量化环境识别` rendered `当前环境: 待识别`; local inspection shows `detect_quant_environment()` returns top-level `summary/modes/action`, while the renderer currently reads `quant_environment["environment"]`.
* `市场与板块分析` rendered high absolute turnover as `量能充沛，但赚钱效应不足`; local inspection shows `describe_market_turnover_condition()` uses absolute turnover thresholds and the market-analysis section does not use the existing two-market turnover comparison path.
* T-109 `重点观察复核脚本` rendered repeated `no_trade` rows with long placeholder wording.
* T-116 `今日总决策面板` rendered `上海石化(600688)` even though the user expected the prior resolved object `豫能控股(001896)`.
* The repository has many existing dirty changes. This task must preserve them and only add the minimal code needed for these defects.

## Requirements

* Split implementation into focused child tasks:
  * `06-04-fix-sector-turnover-share-trend`
  * `06-04-fix-volume-regime-and-quant-env`
  * `06-04-fix-review-script-final-observer-mismatch`
* Use Python 3.14 for every diagnostic and test command:
  `.generated/venv-py314/bin/python3.14`.
* Keep each child task independently testable with focused unit tests before replay verification.
* Preserve the user-visible trading-language contract in `wiki/交易思想/日报术语契约.md`.
* Do not rewrite unrelated report sections or clean unrelated dirty files.

## Acceptance Criteria

* [ ] T-068 no longer renders duplicate sector rows with fake `0.0% / 待累计` when valid flat historical rows exist.
* [ ] `量化环境识别` renders the detector's real summary/action instead of `待识别` when detector output exists.
* [ ] Market-analysis volume wording uses relative turnover context when history is available, so a large absolute amount can still be described as shrinkage.
* [ ] T-109 no longer exposes repeated `no_trade` placeholders as if they were actionable review rows.
* [ ] T-116 uses the same resolved observation target as the front-page/final target context and does not fall back to stale same-day evidence.
* [ ] Focused tests pass for all three child tasks.
* [ ] A replay or report-sanitization verification confirms the relevant headings/tables render coherently.

## Definition of Done

* Child PRDs exist and are linked from this parent task.
* A written implementation plan exists under `docs/superpowers/plans/`.
* Implement/check context is curated for subagents.
* Implementation subagents complete the child tasks.
* A review subagent audits the combined diff before commit.
* The final summary reports verification commands and any remaining risk.

## Out of Scope

* Rebuilding all historical official reports.
* Overwriting official `reports/` outputs.
* Adding new data providers.
* Broad refactors of report runtime, candidate selection, or database storage.
* Changing trading doctrine beyond what is needed to fix the listed report output defects.

## Non-goals

* Do not use current-only data to fill historical replay facts.
* Do not turn process evidence into the final next-day action.
* Do not suppress missing data by replacing it with `0.0%`.
* Do not make `0%不参与` the default when a valid fixed observation path exists.

## Technical Notes

* Relevant specs:
  * `.trellis/spec/backend/quality-guidelines.md`
  * `.trellis/spec/backend/daily-report-decision-loop.md`
  * `.trellis/spec/guides/cross-layer-thinking-guide.md`
  * `.trellis/spec/guides/code-reuse-thinking-guide.md`
* Read-only explorer result for T-068 identified the path:
  `runtime.py -> build_market_activity_report_sections -> build_sector_fund_inflow_node -> build_enhanced_sector_fund_flow_report -> build_top5_sector_turnover_summary`.
* Worktree note: `using-git-worktrees` was reviewed. A separate clean worktree would miss the current dirty WIP that these report defects are part of, so this task proceeds in the current workspace with narrow file ownership and explicit dirty-file preservation.
