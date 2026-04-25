# Daily Report Skill Memory Optimization Design

Date: 2026-04-25
Scope: `a-daily-report` skill and daily-report workflow optimization
Status: Draft for user review

## 1. Problem Statement

The current daily report has already moved toward a better front-page structure:

1. `交易纪律`
2. `市场基底`
3. `周期与主线`
4. `资金意图`
5. `个股解读`
6. `明日执行计划`
7. `最终结论`
8. `详细附录`

This solves part of the reading problem: the report is no longer only a data dump.

The remaining problem is deeper. The report still depends too much on manually maintained specs, repeated ad hoc fixes, and the agent remembering the right workflow during each session. The user's real need is not only "generate a daily report"; it is:

1. Before market open, know whether to act and what to watch.
2. During market hours, execute around the right confirmation window.
3. After market close, preserve what actually happened.
4. Across many days, learn which rules, stocks, data sources, and report wordings proved useful.
5. When asking the agent to continue, avoid re-explaining the same preferences and bugs.

The skill should therefore behave less like a fixed command manual and more like a small trading research team with memory.

## 2. User Needs

### 2.1 Decision Need

The front page must keep answering these questions first:

1. Is tomorrow tradable?
2. What is the market base color?
3. What is the cycle mainline?
4. Does the same-day attack agree with the cycle mainline?
5. Which stock is the only real focus, or should the answer be `不做`?
6. What is the default action window?
7. What invalidates the plan?

The report must not force the user to read appendices before taking the basic stance.

### 2.2 Continuity Need

The report must remember more than one day:

1. Mainline cycle history.
2. Sector turnover-share trend.
3. Stock observation lifecycle.
4. A-kill elimination and cooldown.
5. Entry-cycle calibration cases.
6. Strategy feedback from success and failure samples.

Continuity belongs in structured runtime atoms and appendices, not in front-page prose.

### 2.3 Workflow Need

The skill must let the user speak naturally:

1. `生成今天日报`
2. `按这个问题修复日报`
3. `为什么这个票没进唯一对象`
4. `把这次修复沉淀成记忆`
5. `继续上次任务`
6. `优化这个 skill`

The user should not need to remember internal command names, node names, or spec names.

### 2.4 Knowledge Need

The repo should not treat spec files as the only source of truth.

Specs are good for structural decisions, such as V2 front-page layout or node boundaries. They are bad at carrying small, repeated, experience-based facts:

1. The user wants conclusion-first wording.
2. Duplicate no-trade conclusions are bugs.
3. `可信记忆` was misleading and should render as `二次确认观察`.
4. `市场贴合度` should calibrate vision, not directly trigger buying.
5. A fixed `-5%` stop can misclassify some April success cases.
6. Replay output is the real acceptance surface for many report defects.

These facts should be extracted into memory cards and refreshed periodically.

## 3. Design Principle

Use a three-layer operating model:

1. **Skill as the router**
   - The skill describes what kind of work is being requested.
   - It stays short and intuitive.
   - It routes to references, scripts, specs, plans, and tests only when needed.

2. **Spec as the architecture**
   - Specs define durable structure.
   - Examples: front-page order, appendix boundaries, memory-card schema, promotion rules.
   - Specs should not become a daily notebook.

3. **Memory as the living knowledge base**
   - Memory captures repeated user preference, bug lessons, verification surfaces, and trading-rule refinements.
   - Memory entries expire, get promoted, or get invalidated.
   - Memory should be cheap to update and easy for the model to retrieve.

This is a hybrid model: skill-first, memory-first, spec-light.

## 4. Proposed Workflow Shape

### 4.1 Main Skill Entry Points

The optimized skill should expose intent-based workflows, not fixed command recipes.

Recommended top-level workflows:

1. `daily_report.generate`
   - Generate or replay a daily report.
   - Load current report structure, data-source status, and latest memory.

2. `daily_report.review_output`
   - Read a generated markdown report.
   - Check front-page clarity, duplicate wording, appendix placement, data truthfulness, and execution consistency.

3. `daily_report.fix_defect`
   - Start from a concrete symptom.
   - Prefer replay artifacts as acceptance evidence.
   - Use targeted tests before implementation.

4. `daily_report.reflect`
   - Convert a trading result, report defect, or repeated preference into candidate memory.
   - Do not immediately turn every reflection into a hard rule.

5. `daily_report.optimize_skill`
   - Review whether SKILL.md, references, scripts, specs, and memory are in the right places.
   - Keep SKILL.md short.

These names can remain internal. The user can still speak naturally; the agent maps the request to the workflow.

### 4.2 SKILL.md Shape

The skill should be rewritten as a compact operating guide:

1. What this skill is for.
2. How to choose the workflow.
3. Where to look for report structure.
4. Where to look for memory.
5. What verification is expected.
6. What not to do.

Detailed rules should move into one-level references:

1. `references/report-output.md`
2. `references/trading-rhythm.md`
3. `references/memory-cards.md`
4. `references/verification.md`
5. `references/data-sources.md`

The main skill should not restate every report field.

## 5. Memory Card Design

### 5.1 Memory Card Types

Use a small set of memory types:

1. `user_preference`
   - Stable user preference.
   - Example: conclusion first, then why.

2. `report_wording`
   - Wording or rendering rule.
   - Example: avoid draft-style formula explanations on the front page.

3. `workflow_lesson`
   - How to work in this repo.
   - Example: replay markdown is the acceptance surface for report-output bugs.

4. `market_rule`
   - Trading-rule refinement.
   - Example: `市场贴合度` only calibrates view; it does not directly grant buy permission.

5. `data_source_lesson`
   - Data-source availability or degradation behavior.
   - Example: sector turnover should render `待累计` when source status is degraded.

6. `bug_pattern`
   - Repeated defect and its likely location.
   - Example: front-page focus can conflict with tracking-memory observation items.

7. `retired_rule`
   - A previous rule that should no longer be applied.
   - Example: uniform fixed `-5%` stop should not be the only stop mode.

### 5.2 Memory Card Fields

Each memory card should include:

| Field | Meaning |
|-------|---------|
| `id` | Stable card id |
| `type` | One of the memory types |
| `summary` | One-sentence usable rule |
| `details` | Short supporting detail |
| `source` | Session, report, test, spec, or replay file |
| `scope` | `report_output`, `runtime`, `skill`, `trading_rule`, `data_source` |
| `confidence` | `candidate`, `validated`, `retired` |
| `last_seen` | Date last reinforced |
| `evidence_count` | Number of independent confirmations |
| `expires_after_days` | Optional expiry window |
| `apply_when` | When the model should use it |
| `do_not_apply_when` | Boundary to avoid overreach |

### 5.3 Promotion Rules

Do not promote everything immediately.

1. New extraction starts as `candidate`.
2. A card becomes `validated` after repeated user confirmation, replay evidence, or passing tests tied to the behavior.
3. A card becomes `retired` when a newer user instruction or test/spec supersedes it.
4. Cards with stale market-specific content should expire faster than workflow or wording preferences.

## 6. Periodic Extraction Design

### 6.1 Extraction Sources

The periodic memory extractor should read only bounded sources:

1. Recent conversation/session summaries.
2. Recent specs and plans under `docs/superpowers/`.
3. Recent replay reports under `reports/replay/`.
4. Recent test failures and fixes when available.
5. Current memory cards.

It should not scan the entire repo every time.

### 6.2 Extraction Output

The extractor should produce a reviewable markdown or JSON artifact:

1. New candidate cards.
2. Cards to promote.
3. Cards to retire.
4. Conflicts requiring human or agent review.
5. Suggested SKILL.md/reference updates only when the same memory becomes stable.

### 6.3 Timing

Recommended triggers:

1. Manual: when the user says `把这次沉淀成记忆`.
2. Session-end: after a substantial report fix or design session.
3. Scheduled: daily or every few sessions.
4. Pre-report: lightweight read of validated memory only, not a full extraction.

## 7. Integration With Current Repo

### 7.1 Existing Assets To Reuse

The current repo already has useful foundations:

1. V2 report structure in `docs/superpowers/specs/2026-04-25-daily-report-v2-design.md`.
2. V2 execution plan in `docs/superpowers/plans/2026-04-25-daily-report-v2-implementation-plan.md`.
3. Stock tracking memory in `scripts/research/tracking_memory_runtime.py`.
4. Strategy tracking under `scripts/report/strategy_tracking_*`.
5. Mainline and market-state runtime under `scripts/domains/market_state/`.
6. Replay verification under `scripts/replay/report_replay.py`.
7. Report nodeization under `scripts/report/` and `scripts/domains/execution_chain/`.

The memory optimization should not create a disconnected parallel system.

### 7.2 New Components

Add these components in a later implementation plan:

1. `scripts/research/workflow_memory_runtime.py`
   - Reads and writes workflow/report memory cards.
   - Separate from stock tracking memory.

2. `data/workflow_memory.json`
   - Stores validated and candidate workflow memory.

3. `scripts/research/session_memory_extractor.py`
   - Extracts candidate cards from bounded sources.

4. `references/memory-cards.md`
   - Documents memory card types, promotion, retirement, and examples.

5. `tests/test_workflow_memory_runtime.py`
   - Covers promotion, retirement, expiry, and conflict behavior.

### 7.3 Relationship To Stock Tracking Memory

Do not mix stock tracking and workflow memory.

`tracking_memory_runtime.py` is about market objects:

1. Stocks.
2. Watchlist continuity.
3. Leader memory.
4. Abnormal observation.

The new workflow memory is about operating knowledge:

1. User preferences.
2. Report wording rules.
3. Repo lessons.
4. Data-source lessons.
5. Trading-rule refinements.

They can both feed the report, but they answer different questions.

## 8. Better Daily Report Optimization Path

The next meaningful optimization of the daily report should happen in this order:

### Step 1: Clarify The Report Contract

Keep V2 front page as the canonical reader path.

Acceptance:

1. The front page remains short.
2. The front page has one clear action stance.
3. The unique focus object is either one stock or `暂无 / 不做`.
4. Appendices do not duplicate front-page sections.

### Step 2: Stabilize Structured History

Backfill and maintain structured history without parsing old markdown.

Acceptance:

1. `周期日历主视图` can show prior-cycle context.
2. `主线成交额占比趋势` can show day-over-day change instead of `待累计` when history exists.
3. `中枢与主线解读` can distinguish `待确认`, `接替`, `强化`, `退潮`.

### Step 3: Improve The Only-Focus Decision

Make the final object selection auditable.

Acceptance:

1. The report can explain why a stock became the only focus.
2. The report can explain why a stock was only cross-line observation.
3. Tracking-memory observation items cannot override the current best/core stock unless rules explicitly allow it.

### Step 4: Add Workflow Memory

Extract and apply validated memory before report generation and repair sessions.

Acceptance:

1. Repeated wording defects are caught earlier.
2. The agent remembers report acceptance surfaces.
3. New specs are only written when the change is structural.
4. Small preferences become memory, not new process.

### Step 5: Simplify The Skill Interface

Rewrite the skill as a concise router with references.

Acceptance:

1. The skill is easy for an agent to load quickly.
2. Detailed rules are discoverable without bloating the first context load.
3. User prompts can remain natural.

## 9. What Not To Do

1. Do not add a rigid command grammar that the user must memorize.
2. Do not turn every repeated preference into a new spec.
3. Do not merge workflow memory with stock tracking memory.
4. Do not parse old markdown as the primary source for new structured history.
5. Do not let appendices grow back into the main report.
6. Do not let memory silently override current user instructions.
7. Do not make scheduled extraction mutate stable memory without a reviewable artifact.

## 10. Acceptance Criteria For This Design

This design is successful when:

1. The user can understand the optimization direction without reading implementation code.
2. The distinction between skill, spec, and memory is clear.
3. The next implementation plan can be split into small TDD tasks.
4. Existing V2 report work is preserved.
5. The workflow becomes more intuitive, not more ceremonial.

## 11. Recommended Next Plan

After the user approves this design, write an implementation plan with these tasks:

1. Add workflow-memory card contracts and tests.
2. Implement `workflow_memory_runtime.py`.
3. Add a bounded extractor that emits reviewable candidate cards.
4. Wire validated workflow memory into report generation/review context.
5. Rewrite or create the daily-report skill entry as a compact router.
6. Add verification commands and replay checks.

