# Daily Report Appendix Output Consistency Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the daily report appendix/output defects reported by the user: sector turnover trend duplicates and zeroes, quant-environment pending output, volume wording that ignores shrinkage, repeated `no_trade` review-script placeholders, and final observation-target mismatch.

**Architecture:** Keep the fixes at the smallest contract boundaries: normalize data before trend calculation, reuse the existing two-market turnover comparison helper, render the existing quant detector shape correctly, and make process evidence consume the already-resolved current target. Do not create a new report subsystem.

**Tech Stack:** Python 3.14, `unittest`, existing report runtime modules under `scripts/`, Trellis task PRDs under `.trellis/tasks/`.

---

## File Ownership

Task 1 owns:
- Modify: `scripts/domains/market_state/sector_turnover_trend_tracker.py`
- Test: `tests/test_market_activity_domain_report_sections.py`
- Optional test: `tests/test_sector_fund_flow_enhancer.py`

Task 2 owns:
- Modify: `scripts/domains/market_state/sector_fund_flow_enhancer.py`
- Modify: `scripts/report/market_analysis_nodes.py`
- Modify: `scripts/report/market_analysis_builder.py` only if target date needs to pass into node context
- Test: `tests/test_market_analysis_builder.py`
- Test: `tests/test_market_activity_domain_report_sections.py`
- Regression: `tests/test_market_overview_builder.py`

Task 3 owns:
- Modify after inspection only: `scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py`
- Modify after inspection only: `scripts/domains/execution_chain/pk_decision_nodes/candidate_quality_scorecard.py`
- Modify after inspection only: `scripts/selection/candidate_quality_contracts.py`
- Modify after inspection only: `scripts/report/front_page_v2_renderer.py`
- Modify after inspection only: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py`
- Test: `tests/test_front_page_v2_renderer.py`
- Test: `tests/test_candidate_quality_renderer.py`

Shared constraints:
- Preserve unrelated dirty changes.
- Use `.generated/venv-py314/bin/python3.14` for every Python command.
- Do not edit generated reports as a fix.

---

### Task 1: Sector Turnover Trend Normalization

**Child PRD:** `.trellis/tasks/06-04-fix-sector-turnover-share-trend/prd.md`

- [ ] **Step 1: Write the failing user-visible test**

Add a test near the existing sector-internal-analysis tests in `tests/test_market_activity_domain_report_sections.py`.

The test should call `build_market_activity_report_sections()` with `recent_sector_turnover_history` only, using flat rows such as:

```python
"recent_sector_turnover_history": [
    {"date": "2026-05-27", "sector_name": "电网设备", "turnover_share_pct": 3.2},
    {"date": "2026-05-28", "sector_name": "电网设备", "turnover_share_pct": 4.0},
    {"date": "2026-05-29", "sector_name": "电网设备", "turnover_share_pct": 4.6},
    {"date": "2026-05-28", "sector_name": "电力", "turnover_share_pct": 2.8},
    {"date": "2026-05-29", "sector_name": "电力", "turnover_share_pct": 3.5},
    {"date": "2026-05-28", "sector_name": "半导体", "turnover_share_pct": 5.8},
    {"date": "2026-05-29", "sector_name": "半导体", "turnover_share_pct": 5.0},
]
```

Assert the rendered `板块成交占比趋势 (近5日)` section includes one row for each sector, includes `4.6%` for `电网设备`, and does not include duplicate `| 电力 | 0.0% | 待累计 |`.

- [ ] **Step 2: Run the failing test**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_domain_report_sections
```

Expected before implementation: the new assertion fails because flat rows are treated as grouped sectors without `history`.

- [ ] **Step 3: Implement the normalizer**

In `scripts/domains/market_state/sector_turnover_trend_tracker.py`, add a helper that converts mixed input into grouped rows:

```python
def _normalize_sector_turnover_history_rows(rows):
    grouped = {}
    normalized = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        sector_name = str(item.get("sector_name") or item.get("name") or "").strip()
        if not sector_name:
            continue
        if isinstance(item.get("history"), list):
            normalized.append({"sector_name": sector_name, "history": list(item.get("history") or [])})
            continue
        grouped.setdefault(sector_name, []).append(dict(item))
    for sector_name, history in grouped.items():
        history.sort(key=lambda row: str(row.get("date") or row.get("trade_date") or ""))
        normalized.append({"sector_name": sector_name, "history": history})
    return normalized
```

Use it at the start of `build_top5_sector_turnover_summary()` before the `top_n` slicing. Keep the existing positive-share filtering inside `build_sector_turnover_trend()`.

- [ ] **Step 4: Run focused verification**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_domain_report_sections
.generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_fund_flow_enhancer
```

Expected: all tests pass.

---

### Task 2: Volume Regime And Quant Environment Wording

**Child PRD:** `.trellis/tasks/06-04-fix-volume-regime-and-quant-env/prd.md`

- [ ] **Step 1: Write the quant-environment rendering test**

In `tests/test_market_activity_domain_report_sections.py`, add or update a test that passes market data sufficient for `detect_quant_environment()` to return top-level output. Assert:

```python
self.assertNotIn("当前环境: 待识别", rendered)
self.assertIn("动作建议", rendered)
```

For a no-mode case, assert the rendered line includes `未检测到明显的量化横行特征`.

- [ ] **Step 2: Write the market-analysis shrinkage test**

In `tests/test_market_analysis_builder.py`, add a test for `build_market_and_sector_analysis_contract()` with:

```python
data={
    "total_turnover": 27791.64,
    "market_turnover_history": [
        {"date": "2026-06-02", "turnover": 35072.80},
        {"date": "2026-06-03", "turnover": 32643.59},
    ],
    "market_stats": {"up_count": 1800, "down_count": 3600},
    "dt_pool": [{"code": "000001"}] * 5,
}
```

Assert the `量能水平` line includes a relative shrink/pullback label such as `成交额连续回落` or `成交额冲高后回落`, and does not only render `量能充沛，但赚钱效应不足`.

Also add a second case without `market_turnover_history`, using `top50_turnover_share_series.rows` with:

```python
"top50_turnover_share_series": {
    "rows": [
        {"trade_date": "2026-06-03", "market_amount_yi": 31531.25, "share_pct": 20.0},
        {"trade_date": "2026-06-04", "market_amount_yi": 27791.64, "share_pct": 19.0},
    ]
}
```

Assert this existing series also prevents absolute-only `量能充沛` wording.

- [ ] **Step 3: Run the failing tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_domain_report_sections tests.test_market_analysis_builder
```

Expected before implementation: at least one new assertion fails.

- [ ] **Step 4: Fix quant-environment rendering**

In `scripts/domains/market_state/sector_fund_flow_enhancer.py`, update `_build_markdown_sections()` so it supports both shapes:

```python
env = quant_environment.get("environment") if isinstance(quant_environment.get("environment"), dict) else quant_environment
```

Then read `summary`, `modes`, and `action` from `env`.

- [ ] **Step 5: Reuse turnover comparison in market analysis**

In `scripts/report/market_analysis_nodes.py`, import the existing `build_turnover_comparison` helper and, inside `build_market_analysis_market_state_node()`, compute comparison with `target_date` from context if available. Build the volume text as:

```python
condition = describe_market_turnover_condition(data)
comparison = build_turnover_comparison(data, context.get("target_date", ""))
label = comparison.get("label")
volume_text = f"{label}；{condition}" if label and label != "量能历史不足" else condition
```

If `build_market_and_sector_analysis_contract()` does not pass `target_date`, add an optional keyword argument and include it in node context without breaking existing callers.

- [ ] **Step 6: Run focused verification**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_analysis_builder
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_domain_report_sections
.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_overview_builder
```

Expected: all tests pass.

---

### Task 3: Review Script And Final Observer Consistency

**Child PRD:** `.trellis/tasks/06-04-fix-review-script-final-observer-mismatch/prd.md`

- [ ] **Step 1: Inspect current target-resolution flow**

Read these files with `cat`/`sed`, preserving dirty work:

```bash
sed -n '360,430p' scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py
sed -n '230,310p' scripts/domains/execution_chain/pk_decision_nodes/candidate_quality_scorecard.py
sed -n '280,330p' scripts/selection/candidate_quality_contracts.py
sed -n '6600,6720p' tests/test_report_runtime.py
sed -n '1300,1425p' tests/test_front_page_v2_renderer.py
```

Record which field currently wins for the final observation object.

- [ ] **Step 2: Write a failing target-priority test**

Add a test in `tests/test_report_runtime.py` or `tests/test_front_page_v2_renderer.py` where current runtime/final target resolves `豫能控股(001896)`, while stale fallback data contains `上海石化(600688)`. Assert the process-evidence decision panel and appendix observation anchor render `豫能控股`, not `上海石化`.

- [ ] **Step 3: Write a failing no-trade placeholder test**

Add a focused test around `重点观察复核脚本` in `tests/test_candidate_selection_stage.py` with several candidate rows that have `participation_window_type == "no_trade"` and identical placeholder scripts. Assert the rendered script does not produce multiple generic `no_trade` rows. A single real observation row for the resolved target may remain.

- [ ] **Step 4: Run the failing tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_front_page_v2_renderer tests.test_candidate_quality_renderer
```

Expected before implementation: new target-priority or no-trade placeholder assertions fail.

- [ ] **Step 5: Implement current-target priority**

Prefer current runtime/final target fields before stale fallback records:

1. `final_target_resolution.watch_target`
2. `market_research_snapshot.selected_position_candidate`
3. runtime `selected_position_candidate` / `current_core_candidate`
4. ledger fallback only if no current candidate rows exist

Make the smallest change at the builder that feeds T-116 and the appendix anchor. Do not alter unrelated candidate scoring.

- [ ] **Step 6: Compact or filter generic no-trade script rows**

At the review-script rendering boundary, skip duplicate placeholder rows when all of these are true:

* `participation_window` or `participation_window_type` is `no_trade`;
* the row has no real stock identity, or repeats the same observation-only scripts already rendered;
* the row would add no new price/window/invalidation fact.

Keep one observation row for the resolved target if it has a stock identity.

- [ ] **Step 7: Run focused verification**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_renderer
```

Expected: all tests pass.

---

### Task 4: Combined Review

- [ ] **Step 1: Run combined focused tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_market_activity_domain_report_sections \
  tests.test_sector_fund_flow_enhancer \
  tests.test_market_analysis_builder \
  tests.test_market_overview_builder \
  tests.test_report_runtime \
  tests.test_front_page_v2_renderer \
  tests.test_candidate_quality_renderer
```

- [ ] **Step 2: Run diff hygiene**

Run:

```bash
git diff --check
```

- [ ] **Step 3: Dispatch final review subagent**

Ask a `trellis-check` subagent to review the combined diff against:

* parent PRD `.trellis/tasks/06-04-daily-report-appendix-output-audit/prd.md`
* all three child PRDs
* `.trellis/spec/backend/quality-guidelines.md`
* `.trellis/spec/backend/daily-report-decision-loop.md`

The reviewer must report findings first and may fix narrow issues directly.

---

## Self-Review

Spec coverage:
- T-068 is covered by Task 1.
- Quant environment and relative volume wording are covered by Task 2.
- T-109 and T-116 are covered by Task 3.
- Final verification and review are covered by Task 4.

Placeholder scan:
- The plan contains no deferred implementation placeholders. Each task has concrete files, tests, and commands.

Type consistency:
- The plan uses existing field names observed in code: `recent_sector_turnover_history`, `sector_turnover_history`, `turnover_share_pct`, `market_turnover_history`, `final_target_resolution.watch_target`, and `selected_position_candidate`.
