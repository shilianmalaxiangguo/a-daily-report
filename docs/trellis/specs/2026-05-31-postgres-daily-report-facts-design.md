# PostgreSQL Daily Report Facts Design

## Goal

Move daily-report runtime facts to PostgreSQL-backed structured tables while keeping the report code behind service methods. File snapshots remain import/archive material only when PostgreSQL is selected.

## In Scope

- Batch 1: cycle calendar, mainline history, mainline turnover, sector fund flow, sector attack evidence, sector diffusion and market capacity facts.
- Batch 2: daily observation pools and lifecycle facts, including watchlist, abnormal watch, leader memory, tracking memory, GEM observation, current monitoring, shape repair, dragon rebound and A-kill cooling rows.
- Batch 3: extreme-conviction cases, mentions, participation plan, participation review, trend fate and cycle acceptance facts.
- A PostgreSQL repository selected by environment through `DatabaseService`.
- Narrow tests proving that the service methods save/read structured rows and that runtime writers call the service layer.

## Out Of Scope

- Installing a local PostgreSQL server or creating a database on the user machine.
- Rewriting unrelated report wording.
- Removing historical archive files.
- Reworking unrelated storage tests that fail because the isolated worktree does not include local ignored data.

## Non-Goals

- Do not make report rendering depend on whether the underlying store is a fake repository or PostgreSQL.
- Do not keep new runtime truth in cross-file scans when PostgreSQL is configured.
- Do not use a free-form blob as the primary store for the migrated concepts.

## Done Definition

- `DatabaseService.from_environment()` can select PostgreSQL from `A_DAILY_REPORT_DATABASE_URL` or `DATABASE_URL`.
- PostgreSQL schema contains dedicated tables for all three batches.
- Market research and daily metric paths can write cycle/mainline/sector facts through the service layer.
- Tracking memory can use PostgreSQL as the default runtime store when configured.
- Decision ledger writing can save structured PostgreSQL rows without writing daily ledger archive files.
- Tests cover the new service surface and the runtime handoff points.

## Verification

- Run focused unit tests for PostgreSQL repository/service, market research runtime, tracking memory runtime and decision ledger writer.
- Record the existing full-suite baseline separately because it currently fails before these changes in the isolated worktree.
