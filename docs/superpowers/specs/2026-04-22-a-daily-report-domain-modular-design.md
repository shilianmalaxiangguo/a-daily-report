# A Daily Report Domain Modular Design

Date: 2026-04-22
Scope: `a-daily-report`
Status: Approved by user direction and in execution

## Why the previous direction was wrong

Simply cutting `daily_report_entry_demo.py` by chapter number is not enough.

That style can reduce entry-file length, but it does not create stable replacement units.
If later we want to swap out one trading idea, one anomaly rule, one data source, or one report block, we still end up chasing logic across unrelated chapter files.

The user requirement is stronger:

- modules should be replaceable
- modules should be traceable
- modules should be aligned with business meaning
- the entry file should become a thin orchestrator made of function calls

## Three decomposition options

### Option A: Pure functional layering

Structure:

- `request/`
- `infer/`
- `report/`
- `persist/`
- `trace/`

Pros:

- very clear execution pipeline
- easy to understand by stage

Cons:

- one business capability gets split across many folders
- replacing a single business idea still requires cross-folder edits

### Option B: Pure business-domain layering

Structure:

- `market/`
- `sector/`
- `anomaly/`
- `execution/`
- `report/`

Pros:

- business concepts are grouped together
- easier to swap one domain

Cons:

- request, inference, rendering, and persistence can collapse back into mini-monoliths

### Option C: Recommended hybrid matrix

Structure:

- top level by business domain
- inside each domain by function

Example:

- `domains/market_activity/request.py`
- `domains/market_activity/infer.py`
- `domains/market_activity/report_sections.py`
- `domains/market_activity/contracts.py`

Pros:

- replacement unit is a business domain
- each domain still preserves functional boundaries
- fits AI maintenance best because files stay smaller and more local

## Chosen architecture

Use the hybrid matrix.

### Top-level domains

1. `market_state`
   - environment
   - market phase
   - major indices
   - board-level state

2. `market_activity`
   - hot rank
   - turnover leaders
   - sector fund flow
   - lhb
   - lianban
   - quantitative activity signals

3. `calendar_events`
   - expected events
   - event direction mapping
   - event-driven sector grouping

4. `watch_candidates`
   - abnormal watch
   - leader memory
   - candidate pool
   - conviction list

5. `execution_chain`
   - step 0-4 inference
   - execution permission
   - final verdict
   - action plan

6. `snapshot_replay`
   - replay loading
   - snapshot writing
   - replay refresh

7. `single_stock_diagnostic`
   - single-stock snapshot
   - single-stock inference
   - single-stock rendering

8. `report_shell`
   - report preamble
   - prohibition section
   - markdown skeleton

9. `monitoring`
   - exchange monitor
   - runtime diagnostics
   - trace/log hooks

## Refactor rule

From now on, each extraction must satisfy both checks:

1. `What business domain does this belong to?`
2. `Within that domain, is it request / infer / report / persist / trace?`

If a proposed extraction cannot answer both clearly, it should not be created.

## Immediate migration order

1. `market_activity`
2. `market_state`
3. `monitoring`
4. `execution_chain`
5. `request-layer breakup of get_daily_data`

## End-state for the entry file

`daily_report_entry_demo.py` should eventually contain only:

- CLI argument parsing
- `run_*` entry functions
- domain orchestration calls
- top-level save / replay wiring

It should not contain:

- raw API request details
- business inference logic
- long markdown rendering blocks
- domain-specific decision rules
