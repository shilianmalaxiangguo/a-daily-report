# 持仓策略独立报告 Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an independent holding strategy Markdown file during daily report runs when positions are provided.

**Architecture:** Add a focused renderer under `scripts/portfolio/` that consumes parsed positions plus the latest `明日极度看好` candidates. Wire the daily report CLI to save the artifact next to the main report without changing snap-ui.

**Tech Stack:** Python stdlib, unittest, existing daily report CLI.

---

### Task 1: Renderer

**Files:**
- Create: `scripts/portfolio/position_strategy_report.py`
- Test: `tests/test_position_strategy_report.py`

- [x] Write failing tests for market scenario headings, separated holding/new-opportunity sections, and no swap-style wording.
- [x] Run focused tests and confirm they fail before implementation.
- [x] Implement minimal renderer and candidate extraction.
- [x] Run focused tests and confirm they pass.

### Task 2: CLI Save Hook

**Files:**
- Modify: `scripts/daily_report_entry_demo.py`
- Test: `tests/test_position_strategy_report.py`

- [x] Write failing test for saving only when positions are supplied.
- [x] Run focused tests and confirm they fail before implementation.
- [x] Wire `save_position_strategy_report` after report output generation.
- [x] Run focused tests and confirm they pass.

### Task 3: Verification

**Files:**
- Test: `tests/test_position_strategy_report.py`, `tests/test_position_management_report.py`

- [x] Run focused strategy and existing position tests.
- [x] Inspect generated/changed paths.
