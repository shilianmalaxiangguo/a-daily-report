# New Stock Narrative Research Pool Design

## Goal

Add a separate new-stock research channel to the daily report so newly listed A-share stocks can be evaluated before they are allowed into the normal tomorrow-candidate flow.

This channel must support the user's N Liqi Intelligent calibration case: the system should notice an official listing-date window, map the new stock to the current or potential mainline, evaluate narrative association and market emotion, and only then decide whether the stock deserves a candidate upgrade.

The channel must be early enough to be tradable. If a high-quality new stock lists on T day, the system should start warning on T-2, sharpen the plan on T-1, and only evaluate live opening confirmation on T. The purpose is to let the user clear or reduce other positions in time when the opportunity is strong enough, not to discover the stock after the opening move has already happened.

## 1.0 Assumption

The old decision chain mainly sees stocks after they appear in hot lists, turnover ranks, limit-up pools, LHB, or abnormal watch pools. That chain can explain why N Liqi Intelligent worked after the fact, but it cannot reliably answer this question before the session:

> Is there an officially listing new stock near tomorrow that has enough mainline, narrative, emotion, and resonance evidence to deserve a research upgrade?

The 1.1 rule is not "buy new stocks". The rule is:

> New stocks are a separate research pool. They can be upgraded into tomorrow candidates only when official listing timing, narrative association, market emotion, board resonance, and price/value-for-trade all pass the threshold.

## Scope

In scope:

- Add a structured new-stock calendar request based on Sina's new-stock calendar page.
- Preserve official listing date as the primary timing field.
- Build a `new_stock_research_pool` beside the existing candidate path.
- Add a narrative scoring runtime that produces auditable factor fields.
- Allow threshold-passing records to be appended to the normal watch candidate pool with an explicit source and upgrade reason.
- Keep non-upgraded new stocks visible only as research records.

Out of scope:

- No direct buy signal from new-stock data.
- No direct PK-layer participation in the first version.
- No automatic execution permission.
- No valuation-investing model.
- No dependence on AkShare for the first version.
- No parsing of rendered markdown as a data source.

## Data Source

Primary source:

- Sina new-stock calendar: `https://vip.stock.finance.sina.com.cn/corp/go.php/vRPD_NewStockIssue/page/1.phtml`

The page is GB2312/GB18030 encoded, table-based, and includes `上市日期`. Pagination is visible in the page text, for example `当前页面是第1页,共6页`. The implementation should fetch one or more pages and parse table rows into normalized records.

Required normalized fields:

| Field | Meaning |
| --- | --- |
| `code` | Six-digit or market-prefixed stock code normalized to local code style |
| `name` | Security short name |
| `net_issue_date` | Online issue date, kept for context only |
| `listing_date` | Official first trading/listing date; this is the decisive date |
| `issue_amount_10k` | Issue amount in ten-thousand shares |
| `online_issue_amount_10k` | Online issue amount in ten-thousand shares |
| `issue_price` | Issue price |
| `pe_ratio` | Issue PE |
| `fundraising_yi` | Fundraising amount in RMB 100 million |
| `market` | `sh` / `sz` / `bj` inferred from code |
| `days_to_listing` | Calendar days from target date to listing date |
| `days_since_listing` | Calendar days from listing date to target date |
| `listing_window` | `pre_alert_t2`, `tomorrow_listing`, `today_listing`, `recently_listed`, `upcoming_soon`, or `outside_window` |
| `pre_listing_action` | `prepare_clear_cash`, `focus_tomorrow_battle`, `live_open_confirm`, `post_listing_track`, or `none` |
| `source` | `sina_new_stock_calendar` |
| `source_status` | `success`, `degraded`, or `error` |

Important date rule:

- `listing_date` means official first trading/listing date.
- `net_issue_date`, subscription date, lottery date, and payment date must not be used as listing-date substitutes.

## Architecture

### 1. Request Layer

Create a new request module:

- `scripts/domains/new_stock_calendar/request.py`

Responsibilities:

- Fetch Sina new-stock calendar pages.
- Decode GB18030 safely.
- Parse table rows.
- Normalize records.
- Filter or annotate records by target date window.
- Return `results`, `data_status`, `step_status`, and `module_logs` in the same style as existing request modules.

Suggested public functions:

- `parse_sina_new_stock_calendar_html(html, target_date="", source_url="")`
- `fetch_sina_new_stock_calendar_pages(page_count=2, opener=None)`
- `collect_new_stock_calendar_request_bundle(target_date, fetch_pages, timer, emit, page_count=2)`

The fetcher should allow injected page content in tests.

### 2. Research Scoring Layer

Create a new scoring runtime:

- `scripts/selection/new_stock_narrative_runtime.py`

Responsibilities:

- Score each new-stock record against current daily context.
- Output factor fields, not only one number.
- Produce `new_stock_research_pool`.
- Produce `new_stock_candidate_upgrades` only for records passing the threshold.

Suggested public functions:

- `build_new_stock_research_pool(new_stock_calendar=None, target_date="", context=None)`
- `score_new_stock_narrative(record, context=None, target_date="")`
- `should_upgrade_new_stock_candidate(scored_record)`

The scoring model is short-term A-share narrative logic, not value investing.

Factor fields:

| Factor | Field | Expected meaning |
| --- | --- | --- |
| Official listing timing | `listing_window_score` | High when listing is tomorrow, today, or within the recent new-stock window |
| Mainline match | `mainline_match_score` | Current or potential mainline overlap |
| Narrative association | `narrative_association_score` | Customer anchor, supply-chain role, domestic manufacturing advantage, big-company anchor |
| Market emotion | `market_emotion_score` | Recent new-stock money-making effect and market risk appetite |
| Board resonance | `board_resonance_score` | Sector flow, sector change, mainline turnover share, or hot-plate support |
| Trade value-for-risk | `trade_value_score` | Issue price, fundraising size, market, and tradability sanity |
| Final score | `new_stock_narrative_score` | Explainable weighted score |

Timing action contract:

| Timing | `listing_window` | Action |
| --- | --- | --- |
| T-2 | `pre_alert_t2` | If score is strong enough, warn the user to prepare cash and avoid filling the account with lower-quality trades. The wording should be "prepare to clear/reduce if tomorrow still qualifies", not "buy now". |
| T-1 | `tomorrow_listing` | If score still qualifies, upgrade to tomorrow candidate and explicitly say "tomorrow can battle the new stock, keep cash ready". |
| T | `today_listing` | Do not pre-commit. Only evaluate live opening emotion, VWAP/auction/turnover, and whether the mainline is still resonating. |
| T+1 to T+5 | `recently_listed` | Track only if the new-stock money-making effect and stock-level承接 remain valid. |

Upgrade contract:

- Upgrade threshold: `new_stock_narrative_score >= 72`
- Hard requirements:
  - `listing_window` is one of `pre_alert_t2`, `tomorrow_listing`, `today_listing`, `recently_listed`, `upcoming_soon`
  - `mainline_match_score >= 20`
  - `narrative_association_score >= 18`
  - at least one of `market_emotion_score` or `board_resonance_score` is positive enough to explain current-market support
- Upgraded candidate label: `新股预期差候选`
- Upgraded source: `新股研究池`
- Upgrade does not grant execution permission.

### 3. Candidate Integration

Modify the watch-candidate inference boundary, not the PK layer:

- `scripts/domains/watch_candidates/infer.py`

The existing `build_watch_candidate_pool_bundle` should continue to gather normal sources. It may append `new_stock_candidate_upgrades` from `all_data` only after the scoring layer has explicitly produced them.

Upgraded candidate fields:

| Field | Value |
| --- | --- |
| `_source` | `新股研究池` |
| `watch_source` | `new_stock_research_pool` |
| `core_level` | `新股预期差候选` |
| `candidate_upgrade_reason` | Human-readable factor summary |
| `new_stock_narrative_score` | Final score |
| `new_stock_factors` | Factor score dictionary |
| `listing_date` | Official first trading date |
| `listing_window` | Derived timing bucket |
| `pre_listing_action` | Timing action derived from listing window and score |

Non-upgraded research records remain in `new_stock_research_pool` and must not be appended to `candidates`.

### 4. Input Runtime Integration

Modify:

- `scripts/input/runtime.py`

Add the new request after general market and sector context is available, or before candidate pool assembly if the research scoring only needs raw market context. The final `results` payload should expose:

- `new_stock_calendar`
- `new_stock_research_pool`
- `new_stock_candidate_upgrades`

The module logs should show whether Sina data was fetched and how many records were parsed/upgraded.

## Data Flow

```text
Sina new-stock calendar
  -> domains.new_stock_calendar.request
  -> new_stock_calendar
  -> selection.new_stock_narrative_runtime
  -> new_stock_research_pool
  -> new_stock_candidate_upgrades
  -> domains.watch_candidates.infer
  -> normal candidates only when threshold passes
```

## Calibration Examples

### Must Change: N Liqi Intelligent Style Success

Input:

- `target_date`: `2026-04-29`
- New stock: Liqi Intelligent, official `listing_date`: `2026-04-30`
- Current/potential mainline: `电池`
- Narrative anchors: CATL, BYD, lithium battery equipment/material-chain role, domestic manufacturing advantage
- Market emotion: recent new-stock money-making effect is strong
- Board resonance: battery or technology line has positive market support

Expected:

- The stock appears in `new_stock_research_pool`.
- `listing_window` is `tomorrow_listing`.
- `pre_listing_action` is `focus_tomorrow_battle`.
- `new_stock_narrative_score >= 72`.
- The stock appears in `new_stock_candidate_upgrades`.
- The upgraded candidate source is `新股研究池`.
- The candidate is not marked as direct execution permission.

### Must Change: T-2 Early Cash Preparation

Input:

- `target_date`: two calendar days before a high-quality official listing date.
- Mainline, narrative association, market emotion, board resonance, and trade value score all qualify.

Expected:

- The stock appears in `new_stock_research_pool`.
- `listing_window` is `pre_alert_t2`.
- `pre_listing_action` is `prepare_clear_cash`.
- The report or structured output warns that tomorrow should re-check qualification and prepare cash if it still qualifies.
- It does not say to buy before listing.

### Must Preserve: Ordinary Weak New Stock

Input:

- Official listing date is near target date.
- Mainline does not match.
- Narrative association is weak or generic.
- No market emotion or board resonance support.

Expected:

- The stock appears in `new_stock_research_pool`.
- The stock does not appear in `new_stock_candidate_upgrades`.
- The normal watch candidate pool does not include it.

### Must Preserve: Existing Normal Candidate Flow

Input:

- Existing zt/turnover/hot/LHB candidates.
- Empty or failed Sina new-stock data.

Expected:

- Existing candidate collection behavior stays unchanged.
- New-stock request failure is degraded, not fatal.
- No existing candidate loses fields or rank because of missing new-stock data.

## Report Behavior

The first version does not need a large new report section. It should make the structured data available for later rendering and debugging.

If rendered, use a compact appendix-style block:

```text
新股研究池：3 只，升级 1 只
升级：理奇智能(301608) / 明日上市 / 电池主线 / 宁德时代+比亚迪关联 / 新股情绪强
未升级：某某新股 / 主线不匹配 / 只保留观察
```

Do not use user-visible words such as `条件`, `可做`, or `资格` in this new section.

## Error Handling

- Sina request failure returns empty `new_stock_calendar` and a module log with `status: error`.
- HTML parse failure returns empty records and `source_status: degraded`.
- Missing `listing_date` records are skipped or marked degraded; they must not be upgraded.
- Missing narrative context should lower the score instead of inventing associations.
- Duplicate records by code should keep the nearest listing-date row.

## Testing

Add focused tests before implementation:

- `tests/test_new_stock_calendar_request.py`
  - Parses Sina GB18030/HTML table rows and extracts `listing_date`.
  - Distinguishes `net_issue_date` from `listing_date`.
  - Calculates `listing_window` and `pre_listing_action`, including T-2 `pre_alert_t2`.
  - Handles empty/error pages as degraded data.

- `tests/test_new_stock_narrative_runtime.py`
  - Liqi-style sample upgrades.
  - T-2 strong sample warns to prepare cash but does not say to buy before listing.
  - Weak non-mainline sample stays research-only.
  - Factor fields are present and explain score.

- `tests/test_watch_candidates_infer.py`
  - Existing multi-source candidate collection is preserved.
  - Only `new_stock_candidate_upgrades` are appended.
  - `new_stock_research_pool` alone does not pollute normal candidates.

- `tests/test_input_runtime.py`
  - Runtime exposes `new_stock_calendar`, `new_stock_research_pool`, and `new_stock_candidate_upgrades` when injected helpers return data.
  - Sina/new-stock failure is non-fatal.

## Acceptance

- A structured new-stock calendar source exists and preserves official listing dates.
- New-stock records are evaluated in a separate research pool.
- T-2 records can warn the user to prepare cash when score qualifies.
- Only threshold-passing records enter normal watch candidates.
- Upgraded records carry explicit factor evidence and source tags.
- No new-stock record receives direct execution permission.
- Existing candidate flow passes its current focused tests.
- The implementation has at least one success calibration and one protected non-upgrade sample.

## Open Follow-Up

After this version, a future iteration can add a richer knowledge graph for customers, suppliers, and business descriptions. The first implementation should accept simple structured anchors from context and avoid overfitting one sample.
