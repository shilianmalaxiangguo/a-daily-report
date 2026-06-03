# PostgreSQL Daily Report Facts Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three approved PostgreSQL migration batches for daily-report persistent facts.

**Architecture:** Add a PostgreSQL repository behind `DatabaseService`, then route cycle/mainline/sector, observation lifecycle and decision-ledger persistence through that service. Existing report code should keep calling service/runtime helpers instead of knowing the concrete database.

**Tech Stack:** Python 3.14, optional `psycopg`, PostgreSQL SQL, `unittest`.

---

### Task 1: PostgreSQL Service And Batch 1 Tables

**Files:**
- Create: `scripts/storage/postgres_daily_fact_db.py`
- Modify: `scripts/storage/database_service.py`
- Modify: `scripts/research/market_research_runtime.py`
- Modify: `scripts/research/market_research_support.py`
- Modify: `scripts/domains/market_state/daily_metric_history_index.py`
- Test: `tests/test_postgres_daily_fact_db.py`
- Test: `tests/test_database_service.py`
- Test: `tests/test_market_research_runtime.py`

- [ ] Write failing tests for environment selection and structured cycle/mainline/sector persistence.
- [ ] Implement PostgreSQL schema and repository methods.
- [ ] Route market research cycle context saves through an injected service callback.
- [ ] Run the focused tests.

### Task 2: Observation Pools And Lifecycle

**Files:**
- Modify: `scripts/storage/postgres_daily_fact_db.py`
- Modify: `scripts/storage/database_service.py`
- Modify: `scripts/research/tracking_memory_runtime.py`
- Modify: `scripts/research/market_research_context_bundle.py`
- Modify: `scripts/risk/a_kill_blacklist_store.py`
- Test: `tests/test_tracking_memory_runtime.py`
- Test: `tests/test_market_research_context_bundle.py`

- [ ] Write failing tests for PostgreSQL-backed tracking memory and daily pool persistence.
- [ ] Add structured observation and lifecycle tables.
- [ ] Persist the known report pools for each trade date.
- [ ] Keep file state as fallback only when PostgreSQL is not configured.
- [ ] Run the focused tests.

### Task 3: Extreme Conviction Decision Ledger

**Files:**
- Modify: `scripts/storage/postgres_daily_fact_db.py`
- Modify: `scripts/storage/database_service.py`
- Modify: `scripts/report/decision_ledger.py`
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_decision_ledger.py`
- Test: `tests/test_database_service.py`

- [ ] Write failing tests for structured ledger case, mention and participation persistence.
- [ ] Add decision-ledger tables and repository methods.
- [ ] Let the writer use PostgreSQL as runtime source when configured.
- [ ] Keep archive writing available only when explicitly requested or no PostgreSQL store is configured.
- [ ] Run the focused tests.
