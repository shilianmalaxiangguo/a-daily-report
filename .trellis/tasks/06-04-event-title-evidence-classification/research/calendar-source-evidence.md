# Calendar Source Evidence Note

## Finding

Current target-date calendar snapshots store event rows with only:

```text
country, date, star, title
```

There is no source URL, source article body, fetched news text, or query-date evidence attached to the calendar event rows themselves.

The same report input may already contain `xuangubao_data.xuangubao_news` rows. Those rows can be used as a source-evidence candidate pool only when the news row carries a source date that matches the report target date.

## Consequence

The safe fix for this task is to stop false policy-catalyst fallback and keep low-evidence rows as pending/neutral unless title semantics identify a concrete sector, the title/summary contains explicit policy evidence, or an existing report-date news row is accepted by structured AI evidence judgment.

Adding live web search inside report generation is out of scope for this bug fix because it would mix current web results into historical replay unless the search result is cached with source date, query date, URL, and evidence text.

The implemented bridge uses only already-present `xuangubao_news` rows, requires report-date evidence candidates, and treats title substring/include checks as retrieval only. The final source-evidence decision is a structured AI judgment with `matched`, `evidence_index`, `confidence`, `match_reason`, `classification_hint`, `related_sectors`, and `policy_evidence`. Accepted evidence records provider, query date, source date, source URL, URL-missing status, evidence text, match confidence, and policy-evidence status in `calendar_analysis[].source_evidence`. News rows without a provable source date must not affect classification; `query_date` is recorded but never treated as proof of source date.

## Follow-up

A separate task can add a dedicated `calendar_event_source_evidence.v1` capture layer with source URL, query date, source date, evidence excerpt, and replay cache behavior. That would allow broader title search / source-backed classification beyond the existing report input without breaking historical reproducibility.
