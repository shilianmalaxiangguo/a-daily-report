# Memory Governance

Workflow memory exists to help future agents remember stable workflow lessons. It is review support, not a database, scheduler, or trading ledger.

## Rules

- Extraction creates review artifacts only.
- Application is manual apply only.
- Promotion requires independent evidence, such as user confirmation, a replay artifact, tests tied to behavior, or the same issue recurring on different dates.
- The latest user instruction overrides memory.
- workflow memory is not stock tracking memory.
- Use no auto-apply behavior.
- Rule: do not build a memory platform for this repo-level skill router.

## Boundaries

- Memory can preserve report wording preferences, recurring defects, repo workflow lessons, data-source truthfulness rules, and skill-routing lessons.
- Memory must not silently override a spec, a failing test, replay output, or live/current market evidence.
- Memory must not become stock lifecycle tracking, watch-pool state, or a substitute for structured history.
- A repeated artifact from the same source refreshes recency; it does not count as new independent evidence.

## Review Artifact Shape

A useful review artifact is short and source-aware:

- candidate rule
- scope
- why it matters
- evidence sources
- apply when
- do not apply when
- confidence: candidate, validated, or retired
