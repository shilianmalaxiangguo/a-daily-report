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
- [ ] Distinguish a confirmed position from a previous-report plan: inferred
  records keep identity but use `has_position=false`, pending status,
  `position=0`, `position_pct=0`, and 0x exposure until成交 confirmation;
  preserve any nonzero scenario only in `default_position_pct`
- [ ] Check semantic fields as well as booleans: an inferred plan uses role
  `前日报计划待成交确认`, and its two-layer next-day action says
  `只核实成交记录；未确认成交前按0x`, never old-position handling
- [ ] Trace every duplicated inferred record under personal context, market
  snapshot, execution context, and final resolution; normalize all copies
- [ ] If a restore or compatibility path creates an inferred record after bulk
  normalization already ran, set the pending role/flags and 0x fields on
  construction or run normalization again before rendering or persistence
- [ ] Repair cached candidate panels, conclusions, action plans, and strategy
  rows that were derived before normalization; confirm the pending plan is 0x
- [ ] Verify the generator reads that artifact when reconstructing older days
- [ ] Verify Ta/Tb/Tc keep an unconfirmed historical plan pending instead of
  silently promoting it to a historical B1 position
- [ ] Keep an unknown Ta/Tb/Tc account fact as `持仓未输入`; never backfill it
  from the current report's confirmed holding or pending plan, and reject any
  definite stock identity on that row
- [ ] Insert the table into the in-memory report before acceptance checking and
  before any report artifact is saved
- [ ] Verify command entry, standalone replay, and AgentRunner all check before
  writing the judgment ledger or report files
- [ ] Verify Markdown and companion HTML render the same day/object identity
- [ ] Verify negative/pending wording is parsed before bare B1/B2 badge tokens,
  so a 0% verification row cannot look like participation
- [ ] For inferred plans, verify identity and provenance wording together; the
  correct code with confirmed-holding wording is still a failure
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
`inferred_from_previous_report=true`, yet final resolution promoted it to an
old-position 1x and the report simultaneously said `待成交确认` and `持有100%`.
Fix: keep the pending identity, set confirmed position false, calculate 0x until
成交 confirmation, preserve that pending status across Ta/Tb/Tc, and make
acceptance reject code-correct but provenance-wrong output.

---

## When to Create Flow Documentation

Create detailed flow docs when:
- Feature spans 3+ layers
- Multiple teams are involved
- Data format is complex
- Feature has caused bugs before
