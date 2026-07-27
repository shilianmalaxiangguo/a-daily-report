# Cross-Layer Thinking Guide

> **Purpose**: Think through data flow across layers before implementing.

---

## The Problem

**Most bugs happen at layer boundaries**, not within layers.

Common cross-layer bugs:
- API returns format A, frontend expects format B
- Database stores X, service transforms to Y, but loses data
- Multiple layers implement the same logic differently
- A report fact is rendered in Markdown/HTML, but the acceptance audit checks
  only local formatting and never compares it with the historical source that
  owns the fact.

---

## Before Implementing Cross-Layer Features

### Step 1: Map the Data Flow

Draw out how data moves:

```
Source → Transform → Store → Retrieve → Transform → Display
```

For each arrow, ask:
- What format is the data in?
- What could go wrong?
- Who is responsible for validation?

### Step 2: Identify Boundaries

| Boundary | Common Issues |
|----------|---------------|
| API ↔ Service | Type mismatches, missing fields |
| Service ↔ Database | Format conversions, null handling |
| Backend ↔ Frontend | Serialization, date formats |
| Component ↔ Component | Props shape changes |

### Step 3: Define Contracts

For each boundary:
- What is the exact input format?
- What is the exact output format?
- What errors can occur?

---

## Common Cross-Layer Mistakes

### Mistake 1: Implicit Format Assumptions

**Bad**: Assuming date format without checking

**Good**: Explicit format conversion at boundaries

### Mistake 2: Scattered Validation

**Bad**: Validating the same thing in multiple layers

**Good**: Validate once at the entry point

### Mistake 3: Leaky Abstractions

**Bad**: Component knows about database schema

**Good**: Each layer only knows its neighbors

---

## Checklist for Cross-Layer Features

Before implementation:
- [ ] Mapped the complete data flow
- [ ] Identified all layer boundaries
- [ ] Defined format at each boundary
- [ ] Decided where validation happens

After implementation:
- [ ] Tested with edge cases (null, empty, invalid)
- [ ] Verified error handling at each boundary
- [ ] Checked data survives round-trip
- [ ] For generated reports, checked that source facts survive across generator
  output, Markdown rendering, companion HTML, and acceptance audit.

---

## Cross-Platform Template Consistency

In Trellis, command templates (e.g., `record-session.md`) exist in **multiple platforms** with identical or near-identical content. This is a cross-layer boundary.

### Checklist: After Modifying Any Command Template

- [ ] Find all platforms with the same command: `find src/templates/*/commands/trellis/ -name "<command>.*"`
- [ ] Update all platform copies (Markdown `.md` and TOML `.toml`)
- [ ] For Gemini TOML: adapt line continuations (`\\` vs `\`) and triple-quoted strings
- [ ] Run `/trellis:check-cross-layer` to verify nothing was missed

**Real-world example**: Updated `record-session.md` in Claude to use `--mode record`, but forgot iFlow, Kilo, OpenCode, and Gemini — caught by cross-layer check.

---

## Generated Runtime Template Upgrade Consistency

Some generated files are both documentation and runtime input. In Trellis,
`.trellis/workflow.md` is parsed by `get_context.py`, `workflow_phase.py`,
SessionStart filters, and per-turn hooks. Template changes must be validated
against both fresh init and upgrade paths.

### Checklist: After Modifying A Runtime-Parsed Template

- [ ] Identify every runtime parser that reads the template, not just the file
  writer that installs it
- [ ] Check whether relevant syntax lives outside obvious managed regions
  such as tag blocks
- [ ] Verify fresh `init` output and a versioned `update` scenario that writes
  the older `.trellis/.version`
- [ ] Add an upgrade regression using an older pristine template fixture, then
  assert the installed file reaches the current packaged shape
- [ ] Update the backend spec that owns the runtime contract

**Real-world example**: Codex inline mode changed workflow platform markers from
`[Codex]` / `[Kilo, Antigravity, Windsurf]` to `[codex-sub-agent]` /
`[codex-inline, Kilo, Antigravity, Windsurf]`. Fresh init was correct, but
`trellis update` only merged `[workflow-state:*]` blocks and preserved stale
markers outside those blocks. Result: upgraded projects got new hook scripts
but old workflow routing, so `get_context.py --mode phase --platform codex`
could return empty Phase 2.1 detail.

---

## Mode-Detection Probe Checklist

When a CLI auto-detects a mode by probing a remote resource (e.g., checking if `index.json` exists to decide marketplace vs direct download):

### Before implementing:
- [ ] Probe runs in **ALL** code paths that use the result (interactive, `-y`, `--flag` combos)
- [ ] 404 vs transient error are distinguished — don't treat both as "not found"
- [ ] Transient errors **abort or retry**, never silently switch modes
- [ ] Shared state (caches, prefetched data) is **reset** when context changes (e.g., user switches source)
- [ ] **Shortcut paths** (e.g., `--template` skipping picker) must have the same error-handling quality as the probed path — check that downstream functions don't call catch-all wrappers

### After implementing:
- [ ] Trace every path from probe result to the mode-decision branch — no fallthrough
- [ ] External format contracts (giget URI, raw URLs) are tested or at least documented as comments
- [ ] Metadata reads consume a complete response or use a streaming parser — never parse a fixed-size prefix as full JSON
- [ ] When reconstructing a composite identifier from parsed parts, verify **all** fields are included and in the **correct position** (e.g., `provider:repo/path#ref` not `provider:repo#ref/path`)
- [ ] Verify that **action functions** called after a shortcut don't internally use the old catch-all fetch — they must use the probe-quality variant when error distinction matters

**Real-world example**: Custom registry flow had 8 bugs across 3 review rounds: (1) probe only ran in interactive mode, (2) transient errors fell through to wrong mode, (3) giget URI had `#ref` in wrong position, (4) prefetched templates leaked across source switches, (5) `--template` shortcut bypassed probe but `downloadTemplateById` internally used catch-all `fetchTemplateIndex`, turning timeouts into "Template not found".

**Real-world example**: Agent-session update hints fetched npm `latest` metadata with `response.read(4096)` and then parsed it as complete JSON. The `@mindfoldhq/trellis` package metadata exceeded 4 KB, so the JSON was truncated, parse failed silently, and the first session injection showed no update hint. Fix: read the complete response before parsing, and add a regression where `version` is followed by an 8 KB metadata tail.

---

## Generated Report Historical Fact Consistency

Daily-report tables often display the same account fact in several artifacts:
the strategy report, the main Markdown report, companion HTML, and the
acceptance audit. Treat those as one cross-layer path, not separate display
surfaces.

### Tomorrow-Action Calendar Return Path

When the Bear calendar turns report-day targets into account returns, verify the
whole path rather than checking the HTML number in isolation:

```text
PostgreSQL final decision
  -> next two actual trading dates
  -> 1x/50% leg per target per day
  -> stock and Shanghai same-day open-to-close returns
  -> weighted daily account return
  -> independently compounded account and Shanghai totals
  -> Bear cell and summary
```

- Request one report before the visible 25-row window so its second-day leg can
  reach the first visible execution date.
- Keep report-plan classification separate from account holdings: no-new-entry
  can coexist with a prior target's second-day leg; then show the target plus a
  no-new-entry plan note. If no active leg remains, show account `空仓` while
  retaining the plan classification. Explicit tomorrow-empty clears all legs.
- Do not let calendar layout gaps masquerade as empty accounts: classify each
  weekday gap as a known holiday, sample-outside date, or in-range data gap;
  only the last one is a source-quality problem, and none is a performance
  record.
- Keep trading-date evidence separate from price completeness. A daily-bar row
  with missing prices still proves the date; it does not justify shifting the
  action to the next date.
- Require every active leg and the Shanghai benchmark to have finite,
  non-conflicting same-day open and close values before the day enters any
  average or cumulative total.
- Distinguish target-plan count from account-holding count in the payload and
  UI. These counts intentionally overlap on carry days and answer different
  questions.
- Compound daily account and Shanghai returns independently over the same valid
  dates, then subtract the two cumulative percentages. Never compound or sum
  excess percentages directly.

### Checklist: After Modifying A Historical Report Table

- [ ] Identify the owning historical artifact, not just the current report row
- [ ] Prefer the durable PostgreSQL account fact; use Markdown only as an
  explicit compatibility fallback outside PostgreSQL-only runtime
- [ ] If PostgreSQL history is unavailable in PostgreSQL-only runtime, stop and
  record the failure; do not silently read an old Markdown tomorrow plan
- [ ] Treat an empty PostgreSQL envelope (`data={}`) as unavailable and cover
  that production shape in tests; mocking only `None` can leave the real path
  unprotected
- [ ] If the renderer receives `positions=[]`, verify whether PostgreSQL already
  restored `personal_position_context.existing_position_summary`
- [ ] Treat a previous report's tomorrow target as a mandatory simulated fill on
  the next trading day; use actual `position=50`, `default_position_pct=50`,
  confirmed 1x/50% exposure, and an old-position plan
- [ ] Explicit position input wins, including explicit empty input. A report
  with no new tomorrow target does not clear the most recent unfinished old
  position; stop only on explicit empty, executed tomorrow-empty, or exit facts
- [ ] Check semantic fields as well as booleans: inherited simulated positions
  use role `旧仓处理`, enter the old-position plan, and may create sell or
  same-stock T actions according to their own evidence
- [ ] Trace every duplicated inferred record under personal context, market
  snapshot, execution context, and final resolution; normalize all copies
- [ ] If a restore or compatibility path creates an inherited record after bulk
  normalization already ran, set confirmed role/flags and actual 50% / 1x on
  construction or run normalization again before rendering or persistence
- [ ] Repair cached candidate panels, conclusions, action plans, and strategy
  rows that were derived before normalization; confirm the old position stays 1x
- [ ] Verify the generator reads that artifact when reconstructing older days
- [ ] Verify Ta/Tb/Tc preserve known inherited old-position paths while leaving
  genuinely unknown dates unknown
- [ ] Keep an unknown Ta/Tb/Tc account fact as `持仓未输入`; never backfill it
  from the current report's confirmed holding or pending plan, and reject any
  definite stock identity on that row
- [ ] Insert the table into the in-memory report before acceptance checking and
  before any report artifact is saved
- [ ] Verify command entry, standalone replay, and AgentRunner all check before
  writing the judgment ledger or report files
- [ ] Verify Markdown and companion HTML render the same day/object identity
- [ ] For an explicit tomorrow-empty instruction, verify the companion HTML
  account-action table preserves every required action instead of searching the
  whole HTML document, where a later Wiki or appendix can hide a missing row
- [ ] Verify negative/pending wording is parsed before bare B1/B2 badge tokens,
  so a 0% verification row cannot look like participation
- [ ] For inherited simulated positions, verify identity, source report date,
  confirmed wording, actual 50% / 1x, and old-position actions together
- [ ] For `external_trade_pending`, separately verify pending wording, actual 0x,
  and absence of old-position actions
- [ ] Keep Chanlun HTML and Bear HTML as separate acceptance inputs so one
  companion does not accidentally satisfy or invalidate the other's checks
- [ ] Add an acceptance-audit regression that compares the rendered row with
  the same-directory historical artifact
- [ ] Ensure a mismatch raises a stable finding code and reaches `logs/errors`
- [ ] Include an empty-current-day case so today's no-position result does not
  erase a known prior-day path

**Real-world example**: The Ta/Tb/Tc/Td/Te account day-order table was treated
as local display text. When the previous day had no new target but still carried
an old 华天科技 path, the next report rendered Tc as empty because only the
current position and the previous tomorrow target were considered. Fix: read
historical day-order paths from prior report/strategy artifacts and make the
acceptance audit fail when a known Ta/Tb/Tc path disappears.

**Real-world example**: PostgreSQL stored the 2026-07-10 current path as
长电科技(600584), but `render_position_strategy_report()` received an empty
`positions` list and rendered Td/Te without the stock identity. The first
acceptance check ran before the day-order table was inserted, so the bad report
still passed. Fix: unwrap the PostgreSQL snapshot envelope, restore the position
summary for rendering, insert the table before acceptance, compare Td and Bear
HTML with the same source fact, and preserve the finding code in the run error.

**Real-world example**: The same 2026-07-10 PostgreSQL record carried
`inferred_from_previous_report=true`, but different report layers disagreed
between pending 0x and confirmed 1x. In this simulated account, a prior report's
tomorrow target is a mandatory next-day fill. Fix: normalize all copies to
confirmed actual 50% / 1x, include old-position handling, and let only explicit
empty or exit facts end the inherited position.

### Failure Pattern: Simulated Target Incorrectly Kept Pending

- Root cause categories: cross-layer contract, propagation failure, and implicit
  assumption. The source `previous_report_target_default_1x` describes a
  mandatory simulated next-day fill, not an external pending order.
- Normalize at every load/build boundary before deriving account actions. A
  previous-report target has actual 50% / 1x and confirmed status on the next
  trading day.
- Treat narrative presence and account-fact confirmation as separate fields. A
  non-empty summary such as "exposure pending review" or "yesterday's plan"
  remains unknown unless an explicit flag, positive actual position, structured
  old-position plan, or direct holding wording proves the position.
- Renderers, opportunity comparison, final conclusions, same-stock T, and sell
  actions must branch on `position_fact_status`, not stock identity, a non-empty
  summary, or stale `has_position=true` alone.
- Explicit empty input wins over every inherited record. A no-target report does
  not terminate the old position; an explicit current-empty fact, executed
  tomorrow-empty instruction, or exit fact does.
- Regression coverage must include: a legacy zeroed inherited record, inherited
  1x plus a different new target, inherited 1x plus the same new target, no new
  target, explicit empty input, `external_trade_pending`, and an independently
  confirmed holding. Verify Markdown, Bear HTML, replay normalization,
  acceptance, and persisted PostgreSQL fields together.

---

## When to Create Flow Documentation

Create detailed flow docs when:
- Feature spans 3+ layers
- Multiple teams are involved
- Data format is complex
- Feature has caused bugs before
