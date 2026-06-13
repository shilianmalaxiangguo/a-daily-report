# Retired Local Fact Store Plan

This historical plan is retired and must not be used as implementation guidance.

Current contract:

- Daily-report fact reads use PostgreSQL through `DatabaseService.fact_store_from_environment()`.
- If the PostgreSQL fact store is unavailable, report generation must surface missing data instead of reading a retired local database file.
- Tests should use PostgreSQL-style fake fact stores or focused repository fakes, never retired local database adapters.

Keep this file only as a pointer that the May 2026 local-store stepping-stone plan has been superseded by the PostgreSQL-primary runtime.
