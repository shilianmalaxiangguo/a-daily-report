# Report Optimization Subagent Task List

Date: 2026-04-25
Scope: `/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report`
Mode: sequential subagent execution, each implementation subtask on `gpt-5.5` with `xhigh`
Baseline: `2b6d8e9 tighten report acceptance audit`

## Goal

Continue optimizing the daily report as a trading-useful product: first make the front page auditable and actionable, then improve structured continuity, only-focus reasoning, entry-cycle calibration, and only then minimal workflow memory / skill routing.

## Execution Rules

1. Execute one task at a time.
2. Use TDD for each behavior change.
3. Commit each clean batch.
4. Verify with targeted unit tests and `reports/replay/2026-04-24_A股日报_完整版_replay.md`.
5. Do not revive the abandoned workflow-memory implementation from the backup branch.

## Tasks

- [x] Task 1: Strengthen intraday execution-condition audit.
  - User benefit: the report cannot pass if the front page has time windows but lacks the real action contract: 10点确认, 60分钟确认, 30分钟结构止损, and no-action fallback.
  - Likely files: `scripts/report/report_acceptance_audit.py`, `tests/test_report_acceptance_audit.py`.
  - Verification: audit unit tests plus real replay audit.

- [x] Task 2: Complete structured mainline / turnover history continuity.
  - User benefit: front page and appendix can show whether the mainline is strengthening or weakening across days instead of saying `待累计` whenever history exists.
  - Likely files: `scripts/report/runtime.py`, `scripts/report/front_page_v2_renderer.py`, `tests/test_report_runtime.py`, `tests/test_front_page_v2_renderer.py`.
  - Verification: unit tests for day-over-day `占比变化`, replay audit still passes.

- [ ] Task 3: Add only-focus decision audit.
  - User benefit: when the report names a unique target, it must be explainable by source, mainline consistency,承接,资金痕迹,60分钟条件, and excluded-object reasons.
  - Likely files: `scripts/report/report_acceptance_audit.py`, `scripts/report/front_page_v2_renderer.py`, execution-chain candidate or pk decision nodes, related tests.
  - Verification: audit flags unsupported unique target, real replay passes or honestly reports `暂无`.

- [ ] Task 4: Add entry-cycle calibration surface.
  - User benefit: 60分钟买点 and stop logic become case-aware; the report stops implying fixed `-5%` is the only risk rule.
  - Likely files: `scripts/research/entry_cycle_calibration_runtime.py`, `scripts/domains/execution_chain/entry_plan_stage.py`, entry-plan node tests.
  - Verification: April success/counterexample classification tests plus report runtime tests.

- [ ] Task 5: Minimal workflow memory and skill routing only after Tasks 1-4.
  - User benefit: repeated report bugs and wording preferences become reviewable memory artifacts without forcing users to remember commands.
  - Likely files: `SKILL.md` or skill references, a small review-artifact script, tests for schema/routing if present.
  - Verification: generated review artifact only, no auto-apply to formal memory.
