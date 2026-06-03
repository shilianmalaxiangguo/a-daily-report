# Capital Carrier Mismatch Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add capital-carrier mismatch and new-theme window logic to wiki, runtime LLM context, tests, and the 2026-05-25 replay report.

**Architecture:** Keep the change as a small knowledge-layer slice: wiki owns the full rule wording, `llm_wiki_context.py` exposes compact runtime phrases, and existing report generation consumes the context without adding new data infrastructure.

**Tech Stack:** Python 3.14 via `.generated/venv-py314/bin/python3.14`, unittest, Markdown wiki/spec files, existing replay report generator.

---

## File Map

- Modify `wiki/板块补充/板块中枢与主线延续.md`: add capital-carrier mismatch and core-anchor/elastic-carrier rules.
- Modify `wiki/板块补充/实时Tag池维护与使用.md`: add new-theme identification and early-window usage.
- Modify `scripts/knowledge/llm_wiki_context.py`: expose compact field mappings and digest hints.
- Modify `tests/test_llm_wiki_context.py`: assert the runtime context contains the new phrases.
- Regenerate `reports/replay/2026-05-25_A股日报_完整版_replay.md` and `reports/replay/2026-05-25_A股日报_执行摘要_replay.md`.

## Task 1: Wiki Rules

**Files:**
- Modify: `wiki/板块补充/板块中枢与主线延续.md`
- Modify: `wiki/板块补充/实时Tag池维护与使用.md`

- [x] Add `资金载体错配` to board rhythm rules.
- [x] Add `核心锚` and `弹性载体` language to observation fields and report expressions.
- [x] Add `新题材窗口` to real-time tag maintenance.
- [x] Check the edited markdown avoids forbidden visible wording.

## Task 2: Runtime Context

**Files:**
- Modify: `scripts/knowledge/llm_wiki_context.py`
- Test: `tests/test_llm_wiki_context.py`

- [x] Add failing assertions for `资金载体错配`, `新题材早信或不信`, `核心锚`, and `弹性载体`.
- [x] Run `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context` and confirm failure.
- [x] Add compact field mappings and digest phrases.
- [x] Re-run the same test and confirm success.

## Task 3: Verification And Replay

**Files:**
- Update generated reports under `reports/replay/`.

- [x] Run focused tests for LLM wiki context.
- [x] Run any nearby market-research/report tests affected by context projection if needed.
- [x] Regenerate 2026-05-25 replay report with `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-05-25 --replay`.
- [x] Run report acceptance audit if the generated report path exists.
- [x] Review generated report for the new insight and compare the change against the previous 2026-05-25 report.

## Task 4: Git

- [x] Review `git diff`.
- [ ] Commit the wiki, runtime, test, spec/plan, and regenerated report changes.
- [ ] Push `develop` to the remote.
