# Daily Report V2 Implementation Plan

> Execute strictly in order. Each task must follow TDD: write or adjust failing tests first, watch them fail for the right reason, implement the smallest compatible change, then rerun targeted regression.

**Goal:** Rebuild the daily report into a sniper-style front page plus continuity appendices, based on `docs/superpowers/specs/2026-04-25-daily-report-v2-design.md`, while preserving existing entry compatibility and nodeized structure.

**Constraints:**

- Keep conclusion-first wording.
- Keep old entry points compatible.
- Preserve node-based runtime boundaries.
- Do not expose formulas or English trading jargon on the front page.
- Front page must stay table-first and scan-fast.

## Task 1: Front Page Shell Re-layout

**Goal:** Replace the current front-page section ordering with the new V2 order.

**Files:**
- `scripts/report/report_document_builder.py`
- `scripts/report/report_shell_nodes.py`
- `scripts/report/runtime.py`
- `tests/test_report_document_builder.py`
- `tests/test_report_runtime.py`

- [x] Add failing tests asserting new section order:
  - `交易纪律`
  - `市场基底`
  - `周期与主线`
  - `资金意图`
  - `个股解读`
  - `明日执行计划`
  - `结论总表`
- [x] Implement minimal shell/document assembly changes
- [x] Run targeted tests

## Task 2: Market Base Layer Tableization

**Goal:** Replace prose-heavy market summary with table-first index/base-color output.

**Files:**
- `scripts/report/market_overview_nodes.py`
- `scripts/report/market_overview_builder.py`
- `scripts/report/decision_board_nodes.py`
- `tests/test_market_overview_builder.py`
- `tests/test_report_runtime.py`

- [x] Add failing tests for:
  - index table fields
  - market-state summary table fields
  - no prose-only list fallback on front page
- [x] Implement minimal node/builder changes
- [x] Run targeted tests

## Task 3: Cycle Calendar Main View

**Goal:** Introduce a calendar-style cycle view using `[板块] 状态` cells.

**Files:**
- `scripts/report/market_analysis_nodes.py`
- `scripts/report/market_analysis_builder.py`
- `scripts/research/market_research_support.py`
- `tests/test_market_analysis_builder.py`
- `tests/test_market_research_support.py`

- [x] Add failing tests asserting:
  - calendar-style weekly table exists
  - mainline cells render as `[板块] 状态`
  - old glued rendering style is absent
- [x] Implement smallest compatible cycle-calendar contract and renderer
- [x] Run targeted tests

## Task 4: Cycle Interpretation and Structure Interpretation Tables

**Goal:** Replace abstract cycle labels with readable Chinese interpretation tables.

**Files:**
- `scripts/report/market_analysis_nodes.py`
- `scripts/research/market_research_runtime.py`
- `scripts/research/market_research_support.py`
- `tests/test_market_analysis_builder.py`
- `tests/test_market_research_runtime.py`

- [x] Add failing tests for:
  - `上个周期 / 当前周期` table with date range and trading-day count
  - `中枢与主线解读` table with readable interpretation sentences
  - structure states supporting more than `震荡 / 修复`
- [x] Implement minimal cycle/structure interpretation contracts
- [x] Run targeted tests

## Task 5: Double-Mainline and Turnover Share Front-Page Upgrade

**Goal:** Promote cycle-mainline vs same-day attacking-line and turnover-share trend to formal front-page tables.

**Files:**
- `scripts/report/mainline_turnover_summary_support.py`
- `scripts/report/front_summary_builder.py`
- `scripts/report/market_research_snapshot_nodes.py`
- `scripts/report/front_summary_renderer.py`
- `tests/test_front_summary_builder.py`
- `tests/test_front_summary_renderer.py`
- `tests/test_report_runtime.py`

- [x] Add failing tests for:
  - double-mainline summary table fields
  - turnover-share trend table rendered on front page
  - no missing `主线成交额 / 两市成交额 / 占比变化`
- [x] Implement minimal support/builder/renderer changes
- [x] Run targeted tests

## Task 6: LHB Capital-Intent Redesign

**Goal:** Convert 龙虎榜 output from ranking display to capital-intent interpretation tables.

**Files:**
- `scripts/report/market_research_snapshot_nodes.py`
- `scripts/report/market_research_renderer.py`
- `scripts/report/market_analysis_nodes.py`
- `scripts/research/market_research_support.py`
- `tests/test_market_research_renderer.py`
- `tests/test_market_analysis_builder.py`

- [x] Add failing tests for:
  - `龙虎榜资金状态` table
  - fields `资金强弱 / 资金力度 / 资金方向 / 资金意图 / 风格转向 / 事件属性`
  - front page no longer dumping raw LHB ranking tables
- [x] Implement minimal capital-intent rendering path
- [x] Run targeted tests

## Task 7: Execution Candidate Tables Cleanup

**Goal:** Ensure mainline candidates and cross-line candidates render as visible markdown tables, not hidden comments or fallback text.

**Files:**
- `scripts/domains/execution_chain/candidate_selection_stage.py`
- `scripts/report/context_sections_renderer.py`
- `scripts/report/front_summary_renderer.py`
- `tests/test_candidate_selection_stage.py`
- `tests/test_context_sections_renderer.py`

- [x] Add failing tests proving both tables render visibly in final markdown
- [x] Add tests for compact Chinese wording and no hidden comment-block only output
- [x] Implement minimal rendering adjustments
- [x] Run targeted tests

## Task 8: Chinese-Only Front Page Wording

**Goal:** Remove English trading jargon from all front-page sections.

**Files:**
- `scripts/hooks/report/use_report_tail_summary.py`
- `scripts/report/front_summary_renderer.py`
- `scripts/report/market_analysis_nodes.py`
- `scripts/report/market_research_snapshot_nodes.py`
- `tests/test_use_report_tail_summary.py`
- `tests/test_front_summary_renderer.py`
- `tests/test_report_runtime.py`

- [x] Add failing tests asserting forbidden English jargon is absent:
  - `act right`
  - `setup`
  - `probe`
  - `follow through`
- [x] Implement Chinese replacements on the front page only
- [x] Run targeted tests

## Task 9: Appendix B Mainline Continuity

**Goal:** Add appendix modules for historical mainline pool, switch log, full turnover-share history, and structure-to-mainline records.

**Files:**
- `scripts/report/appendix_renderer.py`
- `scripts/hooks/report/use_execution_appendix_tail.py`
- `scripts/research/market_research_support.py`
- `tests/test_use_execution_appendix_tail.py`
- `tests/test_report_runtime.py`

- [x] Add failing tests for appendix B tables:
  - `历史主线池`
  - `主线切换记录`
  - `主线成交额占比完整历史`
  - `中枢对应主线记录`
- [x] Implement minimal appendix data assembly and rendering
- [x] Run targeted tests

## Task 10: Appendix C Stock Continuity

**Goal:** Add stock monitoring continuity appendices, especially lifecycle tracking and A-kill elimination.

**Files:**
- `scripts/report/appendix_renderer.py`
- `scripts/hooks/report/use_execution_appendix_tail.py`
- `scripts/hooks/persist/use_snapshot_persistence.py`
- `scripts/research/market_research_support.py`
- `tests/test_use_execution_appendix_tail.py`
- `tests/test_use_snapshot_persistence.py`

- [x] Add failing tests for appendix C tables:
  - `当前个股观察监控池`
  - `观察对象生命周期表`
  - `A杀淘汰记录`
- [x] Add tests asserting lifecycle fields include:
  - first report date
  - source report date
  - tracked trading-day count
  - daily change series
  - cumulative change
  - volume-change summary
- [x] Implement minimal persistence/support/rendering changes
- [x] Run targeted tests

## Task 11: Front Page Compression and Deduplication

**Goal:** Remove repeated no-trade lines and push non-decision-heavy content into appendices.

**Files:**
- `scripts/daily_report_render.py`
- `scripts/report/runtime.py`
- `tests/test_daily_report_render.py`
- `tests/test_report_runtime.py`

- [x] Add failing tests for:
  - no repeated empty-position conclusion
  - no heavy ranking tables on front page
  - front page still includes required V2 summary sections
- [x] Implement minimal sanitize/routing cleanup
- [x] Run targeted tests

## Task 12: Full / Summary / Replay Compatibility Regression

**Goal:** Ensure the redesigned structure works for full report, summary report, and replay output.

**Files:**
- `scripts/replay/report_replay.py`
- `scripts/daily_report_render.py`
- `scripts/report/runtime.py`
- `tests/test_report_replay.py`
- `tests/test_daily_report_render.py`
- `tests/test_report_runtime.py`

- [x] Add failing regression tests asserting V2 front-page sections appear in:
  - full markdown
  - summary markdown
  - replay-generated output
- [x] Implement minimal compatibility fixes
- [x] Run targeted tests

## Final Acceptance

- [x] Run targeted regression suite for all touched modules
- [x] Generate a replay sample and one live-date report sample
- [x] Verify front page contains:
  - cycle calendar view
  - turnover-share table
  - LHB capital-intent table
  - visible candidate tables
- [x] Verify appendices contain:
  - historical mainline pool
  - stock lifecycle table
  - A-kill elimination log

## Post V2 Corrections: 2026-04-25

> Source: user review after the first V2 replay. Continue to execute these as nodeized, TDD-first fixes.

- [x] Move `附录：数据获取与执行步骤清单` behind Appendix B/C continuity data.
  - Acceptance: full replay renders historical mainline pool and stock lifecycle before execution/data logs.
- [x] Fix market gate over-defense when the index is still inside a rising daily zhongshu.
  - Acceptance: an index rising inside zhongshu is not forced to `一档（空仓档）` solely because same-day breadth is weak; it becomes `二档（防守档）` with 10:00 confirmation discipline.
- [x] Normalize conditional-defense wording across full report appendices.
  - Acceptance: `二档（防守档） + allow_attack_50_ready` renders as `参与窗口确认后的50%标准进攻预演`, not absolute buy-ban wording.
- [x] Make Step0 follow verdict match the conditional-defense gate.
  - Acceptance: conditional defense renders `🟡 条件防守观察` and does not reuse stale `只允许处理旧仓` reasons from the contract-state pulse.
- [x] Prevent front-page core candidates from showing execution rights when the environment gate is closed.
  - Acceptance: closed gate renders `仅观察，条件未开`; conditional-defense gate renders `观察，等10点确认`; no fallback `有条件执行` leak.
- [x] Rename misleading tracking-memory wording.
  - Acceptance: `中嘉博创` type rows render as `二次确认观察`, not `可信记忆`, and are not implied to be members of the leader-memory bank.
- [x] Make the current 60-minute confirmation formula auditable in the runtime payload.
  - Acceptance: `minute_plan` includes `confirm_basis_60m=entry_or_recent_high` and `confirm_inputs_60m` for debugging.
- [ ] Calibrate 60-minute confirmation with April success cases.
  - Samples: `中嘉博创`、`博杰股份`、`龙蟠科技`.
  - Data needed: daily涨幅、日K、60分钟K、突破/回踩/二次确认点、次日收益与最大回撤.
  - Goal: replace the current mechanical `max(入场价, 最近60分钟高点)` with a case-calibrated node that can be swapped independently.
- [x] Add entry-cycle calibration node for April success/counterexample samples.
  - Samples: success `博杰股份`、`龙蟠科技`、`中嘉博创`; counterexamples `石大胜华`、`甘肃能源`、`津药药业`.
  - Acceptance: output includes first report date, breakout/validation date, trading-day gap, max drawdown/runup, amplitude, fixed `-5%` stop result, and recommended stop mode.
  - Artifact: `reports/replay/2026-04-25_entry_cycle_calibration_replay.md`.
- [x] Wire entry-cycle calibration into the 60-minute confirmation replacement node.
  - Acceptance: candidate entry plan no longer uses a uniform fixed `-5%` stop; it chooses `结构容忍带 / 结构修复带 / 关键区失败降级 / 时间止损 / A杀出清` from calibrated case type and current K-line evidence.
  - Current progress: `entry_cycle_stop_policy` now flows through `intraday_execution_runtime` and `entry_plan_nodes/stop_anchor`; `entry_cycle_calibration` also renders in Appendix C so 2026-04-24 replay can show `中嘉博创固定-5%会误杀 / 甘肃能源关键区失败降级 / 石大胜华时间止损 / 津药药业A杀出清` even when the defensive gate has no executable stock.
- [x] Verify no English trading jargon appears on the front page

## Post-Acceptance Fixes

- [x] Full report appendix heading cleanup: legacy `# YYYY-MM-DD A股日报` is demoted under `## 八、详细附录`, and existing `附录B / 附录C` headings no longer render as `附录：附录B / 附录：附录C`.
- [x] Appendix continuity data feed: runtime now derives and passes `appendix_b / appendix_c` into `use_execution_appendix_tail`, so historical mainline records, turnover-share history, current stock monitoring pool, lifecycle rows, and A-kill rows are rendered from available atoms instead of staying as empty placeholder tables.
- [x] Missing sector-turnover truthfulness: when the board-turnover source is degraded or missing, appendix turnover share renders as `待累计` with the source status instead of pretending the share is `0.00%`.
- [x] Full report duplicate-front-page cleanup: `## 八、详细附录` now strips duplicated front-page market-base blocks, so `市场基底 / 指数与市场底色 / 市场状态结论` only appear on the report front page.
- [x] Appendix B structure-mainline enrichment: when older snapshots contain an `appendix_b` shell but no `structure_mainline_records`, runtime backfills the missing table from structured `market_research_snapshot` atoms instead of parsing old markdown.
- [x] Zhongshu-as-mainline-carrier node upgrade: `pivot_mainline_rows` now carries `中枢级别 / 主线程度 / 演化状态 / 接替关系`, and both the front-page structure table and Appendix B render the same node atoms. When there is no prior structured cycle, the relationship stays `待确认` instead of forcing a fake switch conclusion.
- [x] Calendar/title/focus consistency pass: cycle-calendar cells now map records by actual weekday, report title is `a股市场分析`, the first section is `交易纪律`, and final-conclusion focus now prefers `best_stock / core_stocks` over tracking-memory observation items to avoid conflicts like `中嘉博创` vs `富瀚微`.

## Next Structured-History Tasks

- [ ] Backfill recent replay/frozen snapshots with `mainline_history_record` using the new structured runtime; do not parse old markdown.
- [ ] Re-run the structured-history loader after backfill so `周期日历主视图`, `中枢级别`, `主线程度`, and `接替关系` can show prior-cycle context instead of `待确认`.
- [x] Tencent sector-turnover fallback: `sector_fund_flow.cje` now feeds `sector_turnover_snapshot` before `thsdk`, so 2026-04-24 半导体 renders `2638.10亿 / 10.0%` instead of `missing_dependency / 待累计`.
- [ ] Continue accumulating multi-day sector-turnover share history so `占比变化` can move from `待累计` to day-over-day trend once older snapshots carry the same `cje` atom.
