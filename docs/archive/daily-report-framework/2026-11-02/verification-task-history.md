# Verification

Use the repository Python 3.14 interpreter for every Python command. Verify current output against the current Wiki; do not restore retired strategy text to satisfy an old test.

## Current strategy checks (2026-11-01)

- Small-cap v0.3 is the only active strategy. Assert that collection and rendering never call the old trading board, daily multi-strategy backtest, model interpretation or five-day advice writer.
- The plan must display independently of market-regime calculations. A missing current plan must stay a data gap, not a fallback suggestion.
- Test all-missing turnover, the five-name plus three-backup limit, pool completeness and commission 0.01% with no minimum. A 1,000-yuan purchase has 0.10 yuan commission plus the separately modelled transfer fee.
- Check that the daily account table says single-period simulation, discloses missing prior cash/holdings/buy prices, and never claims actual fills.
- Only the last twenty months are current evaluation evidence. Tournament observations without a complete executable history receive no invented return.
- Use desktop 1440px for visible-output checks. No phone layout or phone-window acceptance is maintained.
- Historical module tests may validate archives; passing them does not make their old strategy current.

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_current_strategy_scope tests.test_small_cap_plan tests.test_sector_daily_report tests.test_market_reading_entry tests.test_daily_report_skill_docs
```

## Wiki-first checks

- Read `wiki/README.md` and the relevant current Wiki pages before judging report text or strategy-related behavior. The Wiki is the authority for the user's route; the report is a dated fact adapter.
- Check that user-confirmed positions, assistant suggestions, market facts, historical judgments and actual fills remain distinct. “Not a value-investing route” is a personal boundary, not a universal claim about all value methods.
- Check that “method-neutral” language means comparison by realizable net result, costs, risk, opportunity cost and later feedback. Do not treat a single investor case, a model vote or a chart as proof of a whole method.
- For every changed principle, identify its source, the decision it is meant to improve, its limits and the evidence that would revise it. A polished explanation without a revision path is not evidence of usefulness.
- Run the current-document routing check when Wiki or task-boundary files change. The broad legacy Wiki suites still point at archived pages and are not a reason to restore them:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_skill_docs
```

## Current reading checks

Select the relevant checks below when report generation, facts or reading behavior changes. Pure Wiki or contract edits do not require replay, rendering, collection or browser checks.

### Compact reading regression

- Run `tests.test_sector_reading_compact` with the current renderer, focus, concept, member, alpha and choice suites. Large-universe cases must retain four complete-window top-five groups, recent turns and real attention outside ranks, without raw price inputs or duplicate native archives in the HTML. Compare selected numeric nodes by identity to full sources; do not weaken raw-derived validation to make pruning pass.
- Check last-row heat clicks after index remapping, original input immutability, full validation of unselected bad facts, missing selected sources, re-signed display tampering, and two successive replays. Native pages resolve only against the selected snapshot; legacy pages retain their only full evidence archive.
- For this October 27 slimming task, use the desktop 1440px window. Compare saved before/after HTML bytes, payload sizes, DOM size, load timing, heap and scroll-frame intervals in the same browser; a byte reduction is not proof of a scroll-jank fix. Check actual code/date selection, concept linkage, stock/sector comparison and unchanged market controls. Evidence belongs in `.generated/sector-reading-compact-20261027/`; official history and both selected snapshots stay unchanged.

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_daily_chart_first tests.test_market_reading_entry tests.test_sector_daily_cleanup tests.test_sector_daily_report tests.test_sector_reading_baseline tests.test_sector_reading_restoration
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-20 --replay
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-16 --replay
```

The default replay must read the frozen target-date snapshot, write only the replay page and isolated diagnostics, and not call old account/selection/report-refresh code. Check the saved HTML structurally for directly visible charts, no reader-facing source/numeric inventories, no repetitive analysis or retired action card, and no malformed output. Historical evidence may mention earlier viewport checks, but run a browser check only when the current change is explicitly about layout or interaction. Hash the target's official report files, snapshot, hypothesis records, trends, and chart-fact files before and after.

### Baseline preservation

- For the October 28 market-relationship correction, run `tests.test_sector_market_relation` with alpha, choice, member, compact-reading and entry/render tests. Independently recompute stock-minus-market versus stock-minus-sector, conditional means, same-direction counts and full-window coverage; missing facts never become zero. Preserve old five-session projections and choice fingerprints. Verify the independent raw-history fingerprint, member identity, benchmark identity, index-input identity, actual query date and conflicts with frozen prices. The PC 1440px saved page must support twenty/five-session changes, sector and stock switches, legend toggles, sidebar collapse/reopen, and clearing/restoring unavailable historical selections. Sixty-session member comparison remains disabled until its complete window exists. No new raw member-history table is embedded. Hash official files before/after and retain a separate replay. Evidence lives in `.generated/market-relation-20261028/`; do not perform phone-viewport debugging for this task.

- For the later October 27 beta/alpha correction, add `tests.test_sector_alpha`: recompute the same five daily returns, member median and median excluding the maximum, daily relative differences and within-window drawdown. Cover one-day winners, absolute losses with positive relative differences, gaps, incomplete calendars, escaped script-closing names and input immutability. Actual browser clicks must cover sector/stock tags, stock bars, date buttons, both directions of concept/price linkage and old comparison clearing for uncovered sectors/dates. Verify no visible selects/raw disclosures, accurate Top50 previous-session deltas without skipping gaps/scopes, and preserved frozen snapshot hashes. Cross-sector overview remains explicitly fixed at the report date when historical details are selected.

- For the October 27 decision-reading correction, run `tests.test_sector_choice` and `tests.test_sector_top50` with affected entry/render/chart tests. Cover persistence versus a one-day winner, genuine previous attention versus missing history, same-window stock differences and latest-only members. Missing prior facts must clear the new priority/default override, keep other directions only as comparisons and preserve the unresolved prior reference. An unverified calendar cannot support five/twenty-session persistence. Recompute all 25 Top50 dates from raw amounts and a complete open-session calendar; independently align the Chinext dates, reject conflicting dates/units/duplicates, preserve genuine gaps and verify two independently selectable lines on the corrected page.
- Check Top50's positive-amount SH/SZ code set against the explicitly dated `daily_basic` response before caching or computing a denominator. A legal 50-row partial daily response must fail this comparison, not become 100% market concentration; missing, truncated, duplicate or wrong-date coverage must also fail. Preserve invalid cache bytes before retrying. This comparison uses two endpoints on the same configured service, not an independent vendor; identical upstream omissions remain outside that guarantee.
- Inspect the saved page's priority buttons, name/code search with keyboard selection and Escape after a no-match search, previous/next dates and slider, chart-to-detail linkage, selected cell outline, and real lower-right hover geometry without tooltip movement over the selected cell. All-empty breadth must have neither a chart nor metric slots. Long fingerprints and raw tables are absent from the reading surface while validation payloads remain; technical exception names remain in raw diagnostics, not reading captions. Verify offline replay and official-file hashes separately; correct rendering and arithmetic do not demonstrate profitable future choices.

- For the October 27 concept-first change, use `tests.test_concept_first_daily` plus the affected loader, chart, member and replay tests. Explicitly test new concept-code prefixes, exclusion of named sample baskets, no industry fallback relabeling, wrong dates/timestamps/units, conflicting net amounts in both orders, missing sessions versus zero, and raw-to-view recomputation. Preserve industry historical fixtures independently.
- The first concept acceptance target is October 26: `--replay --snapshot-source replay` after explicit dated augmentation. Record raw request/response fingerprints, actual compatible-service host, current-directory limitations, coverage and unchanged official fingerprints. Verify no network attempts and repeated output consistency. Do not re-collect all market facts during replay.
- Inspect actual concept cell/date and selector interactions, exact-code price linkage, preserved source identities in frozen data, independent same-name legend toggles, Top50 scope segmentation and same-window member differences. Keep market chart values and futures controls; use the established page design.
- Concept price inputs must reject conflicting `trade_date`, `date` and `source_date` before normalization, while allowing an honest later query date. Rehashed retained-page assets must still match the selected snapshot's native history. In the actual browser, selecting a price date outside the seven-session net window must clear the old amount and highlight; returning must restore the correct day. Reverse concept selection must synchronize text, selector and matrix without needlessly collapsing an already-visible multi-row comparison.

- The October 20 sample has thirteen chart canvases, twenty sector facts, thirty paths, and sixty-six heat rows over thirty dates. Test their actual values and source fingerprints, not merely container presence. The October 16 sample has twenty-four paths and a 24-by-29 heat matrix. These are sample inventories, not daily quotas.
- Exercise relay range/channel filters, real node/edge clicks, mapped and unmapped heat-row clicks, date selection, one-curve hover/click, all heat-row sizes, legend toggles, and disclosures. An unmapped row should show its own facts without silently switching the selected path.
- Current visible lists follow the October 22 user correction: monthly recent strength/upward turns and the four five/twenty/sixty-session heat groups, not every collected sector. Test complete compounded windows, missing/short/negative/zero samples, identity merging, ranking provenance and date boundaries, filtered-series clicks, and the last selected heat row. Full source matrices and paths remain intact in frozen data; reading chart JSON carries selected projections, without a reader-facing numeric disclosure.
- Check featured-sector member-board return compounding, amount units, previous-five-session activity denominators, duplicated board labels, partial coverage, escaped stock names, and pinned click/keyboard selection when those controls are in scope. Clearly separate latest membership query date, report-day stock prices and the curve's selected historical node; unavailable historical constituents cannot become a contemporaneous ranking. Validate both stored fingerprints and recomputed projections.
- Verify that the price comparison alone has no dataZoom and does not change its interval under wheel, drag or touch; keep monthly/drawdown/breadth controls. For fresh CFFEX, test exact-date official collection without writes, retained history and target point, and persisted unavailable reasons; replay must still never collect or write. Inspect three net-short panels, sixty/twenty toggles and independent legends on the saved page.
- Distinguish sixty recorded CFFEX fact dates from sixty consecutive trading sessions. Existing historical omissions must remain disclosed, not be called full consecutive coverage; a readable target point does not prove all intervening dates were recovered. A read-only historical-query failure must preserve the valid fresh day and its diagnostic explanation, not silently shrink history.
- Check turnover colors at 14999/15000/19999/20000/zero/missing and both 15000/20000 reference lines; Top30 shows names, not code-as-name. Market breadth must have no new-high series or legend/tooltip entry. Independent new highs retain 5/2/1/0.2% references and genuine gaps. Use a dated historical fixture if today's new-high facts are missing, and label that verification separately.
- For new highs, test independent live collection, actual sample denominator, exact-date ST and listing exclusions, zero versus missing, empty/truncated/duplicate/wrong-date inputs, honest later queries, calendar holes, insufficient open sessions, failure retries and raw-cache recomputation. A corrupt cache must preserve its original bytes and retry the source; failed independent collection must not reuse an old target-day value. A validated repair must survive repeated offline replay without letting unrelated snapshot changes through or retaining the old fixed-denominator caption. Verify every plotted date against the selected open-session calendar and retained source hashes, not just a nonempty canvas.
- For member colors, test positive, negative, zero, missing, escaped names and opposite target-day/five-session signs. Inspect real hover and pinned details when those interactions are in scope: stock names follow the target-day sign; each percentage follows its own period; amount/activity remain neutral.
- Check complete Top30 including its last row, labels, CFFEX sixty-day default and twenty-day toggle with no zoom, independent legends, gaps rather than zeros, and breadth colors at 4999/5000/5001/zero/missing. Non-market boundary samples must remain clearly separate from report facts.
- Check the breadth capsule's actual rendered geometry: both halves share the same date center, width and zero baseline, with only the outer ends rounded. Verify both reference lines and legend toggles when the chart layout is in scope. Manual annotation scripts, styles, controls and selection tools must be absent; normal text selection and existing stored annotation records remain unchanged.
- Test chart/snapshot conflicts, trend/heat fingerprint tampering, truthful historical timestamps without a separately recorded query date, snapshot-native chart provenance, inherited group-date validation, valid footer links, and repeated replay preservation.
- Test successful independent fresh collection with offline source substitutes and no legacy HTML. Report live-source permissions, availability, units, and database coverage separately; offline tests cannot prove those.
- Chart-first checks must cover separate sector-source groups, ties, negative and zero values, every retained row, dated industry-net-amount facts, conflicting duplicates, escaped labels, missing input without empty charts, and no fixed current-understanding/next-observation paragraphs. Market charts must have no closed chart ancestor. Reader-facing numeric and provenance disclosures are removed; underlying facts, provenance JSON and replay identity remain intact.
- Fresh collection treats conflicting optional historical relay records as dated gaps, not a failure of independently valid current facts. Keep all versions and their containing snapshot dates in `reading_history_conflicts`, disclose the excluded dates, and never choose a version by input order. Identical historical records still merge; direct relay projection continues to reject unresolved duplicate records.
- Live-source regression checks cover the `ths_daily` 3000-row page size, offsets advanced by actual returned rows, full-page continuation, short/empty-page termination, and a usable common-window starting value. A drawn canvas alone does not prove that normalized price paths contain facts; inspect non-null values and visible curves.
- Normalize non-finite seal prices, changes, and amounts to missing values without changing genuine zeros. Keep valid nonnegative integer `company_num` as `stock_count`; show missing samples explicitly. Exercise relay initialization without an optional source-name dictionary, including label escaping and bound controls.

Local evidence for this restoration lives in `.generated/sector-baseline-restore-20261022/`. Earlier stripped-page checks in `.generated/framework-rebuild-20261022/` describe the first stage, not acceptance of the restored content. October 21 Wiki comparison hashes likewise describe that dated stage, not today's edited documents.

The subsequent chart-first change has separate evidence in `.generated/sector-chart-first-20261022/`. The thirteen original October 20 charts remain; the factual sector-change and industry-net-amount views add charts rather than delete the twenty same-day facts. Do not use the older restoration screenshots as evidence for the changed layout.

The October 22 first live generation has separate evidence in `.generated/sector-daily-20261022/`. Use `artifact-inventory-accepted.json`, `browser-accepted-results.json`, and the accepted screenshots for its final page; earlier inventories and screenshots there record failed or superseded checks. The live repair retains the original collection time and separately records the later sector-history query. It does not refill unavailable futures, new-high breadth, sector-member breadth, or missing seal amounts with zeros or another date's facts.

## Related regression checks

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_source_health tests.test_daily_report_render tests.test_compact_bear_report tests.test_daily_report_skill_docs
```

Run `git diff --check` separately. Do not claim the whole repository test suite passes when only focused tests ran. Distinguish newly introduced defects, old incompatible strategy expectations, source unavailability, historical-compatibility limits, and claims that belong to the Wiki rather than the report. No document, page or test result proves a trading method profitable.

## Explicit historical compatibility

`--output-mode full` only locates an existing historical original; it does not select or run the old full chain. `short` is stopped. Tests for archived code must run against archived fixtures or explicitly named historical modules, not through the current entry. Use the independent sector page checks for current work.

The former LLM Wiki suites are now named `tests.legacy_llm_wiki_*`; they validate the archived knowledge graph and are not part of current strategy verification. Current Wiki checks use the active pages under `wiki/` and the small-cap scope tests.

## Delivery evidence

1. Define the changed behavior and applicable checks; identify target date, fact availability and current/official/replay paths only for report work.
2. Run focused tests. For generated-output changes or actual report requests, use a snapshot/replay or lightweight render before considering any expensive collection. Pure Wiki or contract edits need document, source and link checks instead.
3. Complete independent review and fix concrete findings.
4. For generated-output changes or actual report requests, check the actual saved page, provenance and content exclusions; check official-file hashes for historical replay.
5. Report exactly what passed and what remains unverified. No automatic commit or historical overwrite.

For a generated-report response, include the complete request wall clock under `### 生成耗时回顾`; include a separate successful-generation timing table only if a run log was produced. The successful run's internal duration never substitutes for the full request duration.
