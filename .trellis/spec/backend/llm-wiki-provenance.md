# LLM Wiki Provenance And Decision Isolation

> Executable contracts for compiling local Wiki knowledge, tracing fact-based routing, freezing fresh traces, and replaying historical references without changing formal trading decisions.

## Scenario: Source-Linked Knowledge Routing

### 1. Scope / Trigger

Use this contract when changing any of these paths:

- `scripts/knowledge/llm_wiki_manifest.py`
- `scripts/knowledge/llm_wiki_context.py`
- `scripts/knowledge/llm_wiki_router.py`
- `scripts/hooks/knowledge/use_llm_wiki.py`
- LLM Wiki integration in report runtime, fresh snapshots, replay, Markdown, or Bear HTML

Wiki knowledge may explain a completed trading decision and support later review. It must not create or modify candidates, final objects, position sizing, B1/B2, old-position actions, or exit actions.

### 2. Signatures

```python
build_knowledge_manifest(
    entries,
    *,
    root,
    wiki_version,
    language="zh-CN",
    expected_source_paths=None,
) -> dict

build_llm_wiki_context(
    *,
    target_date="",
    query_date="",
    manifest=None,
    source_root=None,
) -> dict

build_llm_wiki_fact_bundle(data) -> dict

route_llm_wiki_knowledge_trace(
    facts,
    *,
    manifest,
    scenario="daily_report",
    limit=3,
    target_date="",
    query_date="",
    facts_source="derived",
    fact_sources=None,
    warnings=None,
    source_root=None,
) -> dict

is_complete_frozen_llm_wiki_context(
    frozen_context,
    *,
    target_date,
) -> bool

is_complete_fresh_llm_wiki_context(
    fresh_context,
    *,
    target_date,
    source_root=None,
) -> bool

build_replay_llm_wiki_context(
    frozen_context,
    *,
    target_date,
    query_date="",
    source_root=None,
) -> dict
```

Stable schemas are `knowledge_manifest.v1`, `knowledge_trace.v1`, and `knowledge_decision_isolation.v1`.

### 3. Contracts

- A manifest source path must resolve inside `wiki/`. Read the actual source bytes and store their SHA-256; do not trust a caller-supplied hash or file metadata.
- Every `manifest.sources[]` item carries `metadata_status` and `missing_metadata`. Sources listed only through `expected_source_paths` receive the same explicit metadata shape and a stable warning when source date, capture date, or anchor is absent; never infer those fields from file metadata.
- An entry `source_ref` and its matching global `manifest.sources[]` item must agree on identity, hash, availability, dates, anchor, URL/publisher, metadata status, and missing metadata.
- `manifest_hash`, `facts_hash`, and `trace_hash` use stable JSON serialization. Exclude absolute workspace paths, timestamps, mtimes, and nondeterministic ordering.
- `KNOWLEDGE_INDEX` remains the routable entry source. `FIELD_MAPPINGS` remains a compatibility context and must not become routable merely through string similarity.
- Every routable `knowledge_rule` declares a non-empty `fact_conditions.must_any`, and every condition path must be an exact leaf in the shared fact-path allowlist. A parent path such as `market` cannot widen a condition over all nested facts. Trace routing first recalls a candidate through `trigger_terms`, then requires one declared structured condition to match; a term found in an unrelated allowed fact path cannot become a final hit. The legacy list-returning helper preserves its signature plus registered fact-root and string `question` behavior, but ignores every unregistered top-level root before ranking.
- Explicit facts and the public trace entry both use the same recursive path allowlist. Unknown roots or nested paths are rejected with warnings before ranking. A non-mapping `facts` value returns an invalid diagnostic trace with no hits instead of raising while reading `.items()`.
- A trace whose target date or query date is missing or is not a canonical `YYYY-MM-DD` calendar date is diagnostic-only: it has `availability=invalid`, stable warnings, and no hits.
- Frozen-trace completeness revalidates the requested target date plus the context and trace target/query dates as canonical calendar dates. Context and trace dates must match exactly; a self-consistent `trace_hash` cannot make an invalid or mismatched date replay-safe.
- Fresh routed traces use `facts_source` equal to `derived` or `explicit`. A replay placeholder for a missing historical trace uses `historical_snapshot`, with empty `fact_sources` and empty `hits`; it is a diagnostic placeholder, not a complete frozen trace.
- List-valued facts use their declared parent path in provenance. For example, values read from `market.rebound_roles[0]` and `[1]` are recorded once as `market.rebound_roles`; list indexes never expand the public fact-path allowlist.
- The router rebuilds every `fact_sources[path]` as `{source, input_path}`; a caller cannot assign a different provenance label or arbitrary input path.
- Each hit stores `matched_fact_paths` and an exactly corresponding `matched_fact_sources` list, plus the manifest entry's complete `source_ref`.
- `build_llm_wiki_context()` exposes manifest `available_source_paths` at the top level while preserving legacy `source_paths`. Its numeric `confidence` comes from the shared availability mapping. Injected manifest list fields are read only when they are actual lists; malformed list fields produce validation diagnostics, zero confidence, and no exception.
- For short-citation compatibility, `triggered_by` keeps matched recall terms when any exist; only a pure-condition legacy hit falls back to condition labels. Structured confirmation remains available in `matched_conditions`, `matched_fact_paths`, and `matched_fact_sources`.
- Every trace, including a zero-hit or missing-history trace, has top-level `decision_scope == "explanation_only"` and `not_used_for` listing all formal decision fields excluded from knowledge influence. Each hit repeats the same boundary for local inspection.
- Report runtime removes any frozen Wiki context before the legacy decision body runs. The legacy body never refreshes Wiki context; the outer runtime attaches Wiki hits exactly once after the formal decision projection exists, then compares the projection before and after attachment.
- Hook and fresh report runtime copy the completed trace's `availability` and `warnings` back to the top-level Wiki context, then derive top-level numeric `confidence` through the same public mapping. An invalid trace cannot leave a stale partial or full-confidence context.
- A hook result with a missing or non-mapping manifest, malformed top-level or entry list fields, non-string entry `kind` / `lifecycle`, or malformed context warnings is invalid, has zero confidence and no hits, and carries a stable diagnostic `knowledge_trace.v1`. Validation records the original field-type errors while using safe empty list views for further checks; malformed fields must not raise before diagnostics are returned. A manifest that declares `availability=invalid` still receives a stable reason when its own warnings and errors are empty.
- Public manifest validation, source validation, and trace routing also treat a directly supplied non-mapping manifest as `manifest_type_invalid`; they return diagnostics instead of reading `.get()` from the invalid value.
- Full and summary Markdown reuse one compiled manifest within a report run. Knowledge citations and market-language research evidence appear after the final action, account action, execution conditions, and non-execution conditions. Bear HTML preserves Markdown order.
- The public sections renderer never compiles the current Wiki. It may render discipline text only from an explicitly supplied `llm_wiki` context; in replay mode the facade accepts only a context marked `artifact_origin=frozen_trace`. Missing or untrusted replay context leaves the section absent instead of reading current Wiki bytes.
- The official report entry validates a complete manifest and trace against current Wiki source bytes after in-memory report acceptance but before PostgreSQL sync, quality-ledger persistence, runtime-artifact persistence, Markdown/HTML or companion writes, and snapshot persistence. The orchestrator snapshot hook repeats the same fresh-source check before its own fresh snapshot write. Both checks require a matching target date, valid hashes, source references, availability, rank sequence, global fact sources, and per-hit matched sources.
- The official entry marks Wiki-dependent persistence unavailable before invoking the fresh check and restores it only after success. A source-read or other check exception must not fall through to quality-ledger persistence.
- `--no-report` remains a data-only entry: it does not build a Wiki trace and therefore skips the fresh report-trace check while preserving its existing data preflight, PostgreSQL sync, and quality-ledger behavior.
- The orchestrator snapshot hook requires a non-empty normalized target date when `knowledge.llm_wiki` is present. A snapshot without `knowledge.llm_wiki` keeps its prior payload shape and is not widened to persist unrelated knowledge objects.
- Replay reuses only a complete frozen trace whose target date matches the requested date. Current Wiki source changes keep the frozen manifest, trace, and hits byte-for-byte unchanged, record `frozen_availability` and `frozen_confidence`, and set top-level `availability`, `confidence`, and `review_confidence` to the current `source_changed` review state. Such a replay wrapper remains reusable on a later replay. Missing or malformed historical traces produce no historical hits, explicitly set both current confidence fields to `0.0`, and record the replay query date using the `Asia/Shanghai` calendar date rather than the host machine's local date. This default belongs to `build_replay_llm_wiki_context()` itself, not only to its current caller.
- Preserve legacy `source_paths`, `field_mappings`, `knowledge_hits`, old hit fields, and the list-returning `route_llm_wiki_knowledge()` API. The list helper is compatibility-only: fresh and hooks call the trace API and persist `knowledge_trace.v1`; replay reuses the target-date frozen trace or creates a missing-history diagnostic placeholder without routing the current Wiki.

### 4. Validation & Error Matrix

| Condition | Required handling |
|-----------|-------------------|
| Source path escapes `wiki/` | Reject the source without reading it |
| Source is absent | Mark it missing, make dependent entries unavailable, and lower knowledge availability |
| Expected-only source lacks date or anchor metadata | Keep it available by content, mark metadata partial, and emit a stable incomplete-source warning |
| Entry source metadata differs from the global source index | Reject the manifest even when its self-hash is valid |
| Stored source hash differs from current bytes | Reject fresh routing; keep a valid replay trace frozen and add a review diagnostic |
| Manifest hash is self-consistent but source hash is forged | Reject it through byte-level source validation |
| Explicit fact root or nested path is unknown | Remove it before ranking and add a stable warning |
| Legacy list helper receives only unregistered top-level roots | Return an empty list; unregistered text must not create a hit |
| A routable knowledge entry has no `fact_conditions.must_any` | Reject the manifest entry; do not allow term-only trace hits |
| A manifest condition uses a parent or unregistered fact path | Reject the manifest; do not broaden the condition over nested facts |
| Public trace routing receives non-mapping facts | Return an invalid diagnostic trace with empty hits and `knowledge_facts_type_invalid` |
| Injected context manifest has malformed list fields | Preserve type diagnostics, return invalid context with zero confidence, and do not iterate the malformed value |
| Target date or query date is empty or not a canonical `YYYY-MM-DD` calendar date | Return an invalid diagnostic trace with no hits |
| Runtime trace availability differs from the pre-route context | Replace top-level availability, warnings, and numeric confidence with the trace-derived values |
| Hook context has no mapping manifest, has malformed context warnings, or its manifest has malformed list/kind/lifecycle fields | Mark it invalid with zero confidence, no hits, a stable warning, and a hashed diagnostic trace; preserve field-type diagnostics and do not raise while reading them |
| Public validator or trace route receives a non-mapping manifest | Return `manifest_type_invalid`; trace routing returns invalid with no hits and a stable warning |
| A self-hashed frozen trace contains an invalid or context-mismatched date | Reject snapshot persistence and return a missing historical reference during replay |
| Caller supplies a false fact source | Replace it with the canonical source/input path and add a warning |
| A list fact produces indexed leaf paths | Normalize every provenance and matched path to the declared parent path |
| Fresh trace omits global or per-hit fact sources | Stop snapshot persistence |
| Fresh trace omits its top-level decision boundary | Stop snapshot persistence even when its self-hash is valid |
| Fresh trace is incomplete after in-memory rendering | Stop before PostgreSQL sync or any runtime, Markdown, HTML, companion, or snapshot write |
| Fresh source validation raises while reading Wiki bytes | Stop quality-ledger persistence as well as every report persistence surface |
| `--no-report` collects valid data without a Wiki trace | Keep the data-only flow; do not require a report trace or suppress PostgreSQL and quality persistence |
| A Wiki-bearing snapshot has no target date | Stop before persistence; do not create an empty or `None`-named snapshot |
| A snapshot has unrelated knowledge but no `llm_wiki` | Preserve the ordinary snapshot payload shape |
| Replay has no complete historical trace | Return a `historical_snapshot` placeholder with empty fact sources and hits; do not accept it as frozen |
| Replay creates a missing-history placeholder near a host-timezone date boundary | Use the current `Asia/Shanghai` date for `query_date` |
| Sections rendering receives no explicit Wiki context, or replay receives a non-frozen context | Render no injected discipline text and do not compile the current Wiki |
| Replay source bytes differ from the frozen manifest | Preserve the frozen manifest/trace/hits, but mark the outer replay review as `source_changed` with reduced confidence |
| A source-changed replay context is replayed again | Resolve completeness through its frozen availability and reuse the same frozen manifest/trace/hits |
| Frozen trace date differs from replay target | Return historical-reference missing; do not compile current Wiki as the old trace |
| Knowledge attachment changes a formal decision projection | Remove the knowledge explanation and record the mismatch |
| Report evidence appears before the formal action | Fix Markdown ordering; Bear must inherit the corrected order |

### 5. Good / Base / Bad Cases

- Good: same Wiki bytes, entries, dates, and facts produce identical manifest and trace hashes.
- Good: explicit facts retain `source=explicit` and `input_path=knowledge_hit_facts.<path>` through the trace and each matched hit.
- Good: a list-valued explicit fact records one declared parent path and remains valid for fresh freezing and replay.
- Good: replay keeps the target-date frozen trace while reporting that the current source bytes differ.
- Base: an old snapshot has no complete trace, so replay renders no historical knowledge hits and returns an empty-source `historical_snapshot` placeholder explaining the missing reference.
- Bad: a caller injects `market.forged` or labels a fact as an official source and the router accepts it.
- Bad: current Wiki content is routed during replay and described as knowledge available on the historical date.
- Bad: a Wiki hit changes `selection_workflow`, `final_target_resolution`, position sizing, B1/B2, or an exit action.

### 6. Tests Required

- `tests.test_llm_wiki_manifest`: entry coverage, required structured confirmations and exact fact paths, stable hashes, byte changes, entry-linked and expected-only source metadata, missing/escaping sources, forged hashes, lifecycle, decision scope, and non-raising validation of malformed internal field types.
- `tests.test_llm_wiki_context`: legacy compatibility including top-level available sources, malformed manifest list fields, shared confidence mapping, frozen completeness including the top-level decision boundary, canonical context/trace dates, target/query-date equality, source-reference equality, fact-source completeness, and current-source diagnostics.
- `tests.test_llm_wiki_router`: recursive fact filtering, non-mapping fact diagnostics, canonical fact sources, required and canonical dates, exact condition paths, two-stage recall/confirmation, stable ranking/hashes, zero-hit decision boundaries, negation handling, legacy unknown-root rejection, and non-mapping, malformed, or declared-invalid manifest rejection.
- `tests.test_llm_wiki_hook`: target/query dates, availability-derived confidence/warnings, and hashed diagnostic traces for missing, non-mapping, internally malformed manifests or context warnings.
- `tests.test_report_runtime`: one compile and one post-decision attachment per run, legacy-body isolation, trace diagnostic/confidence synchronization, trace attachment, and formal decision projection equality across version-only, real source-byte A/B recompilation, hit-change, and knowledge-missing manifests without bypassing source validation.
- `tests.test_report_replay`, `tests.test_llm_wiki_context`, entry tests, and `tests.test_use_snapshot_persistence`: frozen reuse, missing/date-mismatched trace behavior, Shanghai query dates at both the public context helper and replay caller, fresh validation before every report persistence surface including source-read exceptions, data-only `--no-report` compatibility, list-fact replay safety, and incomplete-trace rejection at every snapshot entry.
- `tests.test_daily_report_render` and Bear tests: sections consume only explicit Wiki context, replay sections never compile current Wiki, full/summary action-before-evidence order, Bear action/evidence classification, and the same ordering in the final HTML file written by the official entry.
- `tests.test_llm_wiki_lint`: read-only behavior, navigation, log format, missing sources, fingerprints, lifecycle, and decision scope.

### 7. Wrong vs Correct

#### Wrong

```python
trace = route_llm_wiki_knowledge_trace(
    arbitrary_report_dict,
    manifest=current_manifest,
)
snapshot["knowledge_trace"] = trace  # Saved without provenance or date checks.
```

This lets unregistered facts influence routing and can present current knowledge as historical evidence.

#### Correct

```python
bundle = build_llm_wiki_fact_bundle(report_data)
trace = route_llm_wiki_knowledge_trace(
    bundle["facts"],
    manifest=context["manifest"],
    target_date=target_date,
    query_date=query_date,
    facts_source=bundle["facts_source"],
    fact_sources=bundle["fact_sources"],
    warnings=bundle["warnings"],
)
context["knowledge_trace"] = trace
assert is_complete_frozen_llm_wiki_context(context, target_date=target_date)
```

The fact surface, provenance, date boundary, and snapshot completeness are explicit and testable.
