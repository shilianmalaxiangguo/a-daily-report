# Retired Daily Report JSON Export Plan

This historical design is retired and must not be used as implementation guidance.

Current contract:

- Daily-report structured facts use PostgreSQL through `DatabaseService` and `PostgresDailyFactDb`.
- Fresh report generation writes reports, snapshots, and PostgreSQL facts.
- Replay should read durable PostgreSQL facts when running in PostgreSQL-only mode.
- If PostgreSQL facts are unavailable or incomplete, report generation must expose the missing data instead of reading retired local stores or retired static publish artifacts.

Keep this file only as a pointer that the May 2026 JSON export stepping-stone plan has been superseded by the PostgreSQL-primary runtime.
