# Research: 2026-06-29 Precommit Audit Findings

## Question

Which concrete report surfaces and code paths caused the 2026-06-29 precommit audit to block submission?

## Sources

- `reports/2026-06-29_A股日报_完整版.md`
- `reports/2026-06-29_A股日报_完整版.html`
- `scripts/domains/market_activity/request.py`
- `scripts/domains/market_activity/report_section_nodes.py`
- `scripts/report/decision_statistics.py`
- `scripts/report/runtime.py`
- `scripts/templates/daily_report_markdown_reader.html`
- Subagent audit summaries from current Codex session.

## Findings

- Bear HTML already contains a `position-timeline` block with 2026-06-28, 2026-06-29, 2026-06-30, Ta=太极实业 and Tb=深科技.
- Markdown does not contain the same Ta/Tb/Tc readable table; it only contains generic Ta/Tb/Tc doctrine near the end.
- Markdown account section still says the holding was not input, while the HTML timeline asserts the old path is 太极实业.
- Sector fund-flow rendering reads `zljlr` and `zdf`, while the newer request path can carry `net_amount`, `net_inflow_yi`, `change_pct`, or `pct_change`.
- Existing acceptance audit can pass a report whose sector flow visible table is all zero.
- The daily judgment panel intentionally separates resolved and unresolved rows, but the formal report currently exposes too many `待补事实` lines for the user's expected submission quality.

## Recommendation

Fix the current boundaries rather than introducing a new report subsystem:

- normalize sector-flow aliases at request/render boundaries;
- render the same Ta/Tb/Tc truth in Markdown and HTML;
- derive old-holding front-page text from the same old-path facts used by the timeline;
- extend acceptance audit to catch visible all-zero flow tables and old-holding conflicts;
- regenerate the 2026-06-29 official artifacts.

## Impact

- PRD: establishes R1-R6 and acceptance checks.
- Design: data flow must cross request -> runtime -> Markdown -> HTML -> audit.
- Implementation: start with regression tests around the exact failure forms, then patch the smallest existing functions.
