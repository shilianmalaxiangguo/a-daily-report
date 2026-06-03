# Opportunity-Cost Report Revision Implementation Plan

**Goal:** Make the daily report compare old-position handling and new-entry promotion through risk price, risk-reward, and account fit before rendering 50% or 100%.

**Architecture:** Add one opportunity comparison helper near the existing candidate execution contracts. Feed that result into report runtime repair/rendering and acceptance audit, so the report does not produce different answers in different sections.

**Tech Stack:** Python 3.14, `unittest`, existing replay markdown/report runtime modules.

---

### Task 1: Comparison Helper

**Files:**
- Modify: `scripts/selection/candidate_execution_contracts.py`
- Test: `tests/test_candidate_execution_contracts.py` or the existing closest test module if present

- [ ] Write tests for `build_opportunity_comparison` with:
  - missing risk prices keeps `risk_reward_state=待计算` and caps participation at `0`,
  - stretched downside to MA5/MA10 marks risk comfort unacceptable,
  - complete positive risk-reward allows 50/100 only when stronger opportunity and controllable risk are both true.
- [ ] Run the focused test and confirm it fails because the helper is missing.
- [ ] Add the minimal helper and formatter fields.
- [ ] Run the focused test and confirm it passes.

### Task 2: Runtime Decision Repair

**Files:**
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_daily_report_render.py`

- [ ] Add a failing test for the 2026-06-03 conflict: risk-reward is missing, planned participation is absent, and rendered output must not contain unconditional `100%核心进攻`.
- [ ] Add the opportunity comparison to the existing final target / position decision path.
- [ ] Ensure missing or unacceptable risk comparison turns the new target into observation/no new participation.
- [ ] Ensure a complete, qualified comparison can still preserve 50% or 100%.
- [ ] Run the focused render test and confirm it passes.

### Task 3: Report Table Rendering

**Files:**
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_daily_report_render.py`

- [ ] Add a failing test that rendered replay markdown contains an opportunity-cost table with `华电辽能(600396)` and `华天科技(002185)`.
- [ ] Render the table before the final action sections that decide participation percentage.
- [ ] Include observation/current price, MA5, MA10, VWAP if available, invalidation price, target price, downside percentages, risk-reward state, and account conclusion.
- [ ] Run focused render tests.

### Task 4: Acceptance Audit

**Files:**
- Modify: `scripts/report/report_acceptance_audit.py`
- Test: relevant acceptance-audit test module

- [ ] Add a failing test that flags 50%/100% output when risk-reward is missing or planned participation is absent.
- [ ] Add the smallest audit check for the new contradiction.
- [ ] Run the focused audit test.

### Task 5: Replay Verification

**Files:**
- Generated replay outputs only after implementation passes unit tests.

- [ ] Run focused unit tests.
- [ ] Run `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-03 --replay`.
- [ ] Run report acceptance audit against `reports/replay/2026-06-03_A股日报_完整版_replay.md`.
- [ ] Run `git diff --check` for touched files.
