# Report And Request Runtime Migration Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the remaining report-output orchestration out of `scripts/daily_report_entry_demo.py`, then continue shrinking the entry file by extracting `get_daily_data()` into request/input runtime modules.

**Architecture:** Keep the legacy function names in `scripts/daily_report_entry_demo.py` as thin compatibility wrappers, but move orchestration into dedicated runtime modules that accept explicit helper bundles. Reuse existing `scripts/report/*`, `scripts/hooks/report/*`, and future `scripts/input/*` patterns so the entry file only wires helpers, config, and persistence.

**Tech Stack:** Python 3, `unittest`, existing hook/runtime modules under `scripts/report`, `scripts/domains`, and `scripts/hooks`

---

### Task 1: Migrate `generate_markdown_report()` into report runtime

**Files:**
- Create: `scripts/report/runtime.py`
- Modify: `scripts/daily_report_entry_demo.py`
- Test: `tests/test_report_runtime.py`

- [x] **Step 1: Write the failing test**

```python
def test_legacy_generate_markdown_report_wrapper_delegates_to_report_runtime(self):
    payload = {"report": "# migrated"}
    with patch("daily_report_entry_demo.render_markdown_report_runtime", return_value=payload) as runtime_mock:
        rendered = daily_report_entry_demo.generate_markdown_report({"foo": "bar"}, "2026-04-22")

    runtime_mock.assert_called_once()
    self.assertEqual(rendered, "# migrated")
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_legacy_generate_markdown_report_wrapper_delegates_to_report_runtime -v`
Expected: FAIL because `render_markdown_report_runtime` does not exist and the wrapper still owns the full implementation.

- [x] **Step 3: Write minimal runtime implementation**

```python
def render_markdown_report_runtime(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    persist_strategy_tracking=True,
    *,
    helpers,
    config,
):
    ...
    return {
        "report": "\n".join(report_lines),
        "artifacts": {...},
    }
```

The runtime should own the old orchestration flow, while the entry wrapper should only build the `helpers` / `config` bundle and return `result["report"]`.

- [x] **Step 4: Run targeted tests to verify it passes**

Run: `python3 -m unittest tests.test_report_runtime tests.test_daily_report_render -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/report/runtime.py scripts/daily_report_entry_demo.py tests/test_report_runtime.py
git commit -m "refactor: move report orchestration into runtime"
```

### Task 2: Extend report runtime regression coverage

**Files:**
- Modify: `tests/test_report_runtime.py`
- Modify: `tests/test_daily_report_render.py`

- [x] **Step 1: Write the failing test**

```python
def test_render_markdown_report_runtime_can_build_report_from_helper_bundle(self):
    result = render_markdown_report_runtime(
        {"foo": "bar"},
        "2026-04-22",
        helpers=build_minimal_helper_bundle(),
        config=build_minimal_runtime_config(),
    )
    self.assertIn("# Runtime Report", result["report"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_render_markdown_report_runtime_can_build_report_from_helper_bundle -v`
Expected: FAIL until the runtime has a stable callable surface for tests.

- [x] **Step 3: Implement the helper-driven regression surface**

```python
def _resolve_runtime_callable(helpers, key):
    value = helpers.get(key)
    if value is None:
        raise KeyError(f"Missing report runtime helper: {key}")
    return value
```

Use the helper bundle instead of hidden imports so the runtime can be exercised in isolation.

- [x] **Step 4: Run targeted tests to verify it passes**

Run: `python3 -m unittest tests.test_report_runtime tests.test_daily_report_render tests.test_report_orchestrator -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_report_runtime.py tests/test_daily_report_render.py
git commit -m "test: cover report runtime helper delegation"
```

### Task 3: Start request/input runtime extraction for `get_daily_data()`

**Files:**
- Create: `scripts/input/runtime.py`
- Create: `scripts/input/request_registry.py`
- Modify: `scripts/daily_report_entry_demo.py`
- Test: `tests/test_input_runtime.py`

- [x] **Step 1: Write the failing test**

```python
def test_get_daily_data_wrapper_delegates_to_input_runtime(self):
    payload = {"target_date": "2026-04-22", "module_logs": []}
    with patch("daily_report_entry_demo.run_input_runtime", return_value=payload) as runtime_mock:
        result = daily_report_entry_demo.get_daily_data("2026-04-22")

    runtime_mock.assert_called_once()
    self.assertEqual(result["target_date"], "2026-04-22")
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_input_runtime.InputRuntimeTest.test_get_daily_data_wrapper_delegates_to_input_runtime -v`
Expected: FAIL because the request runtime wrapper does not exist yet.

- [x] **Step 3: Implement the first request runtime slice**

```python
def run_input_runtime(target_date=None, *, helpers, config):
    ...
    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": logs,
    }
```

Start with the first cohesive batch the roadmap already names: indices, turnover, calendar/date normalization, hot rank / leaderboard fetch units. Keep request functions registered by key so later overnight runs can keep peeling units off `get_daily_data()` without rewriting the wrapper again.

- [x] **Step 4: Run targeted tests to verify it passes**

Run: `python3 -m unittest tests.test_input_runtime -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/input/runtime.py scripts/input/request_registry.py scripts/daily_report_entry_demo.py tests/test_input_runtime.py
git commit -m "refactor: start input runtime extraction"
```

### Task 4: Full verification and roadmap sync

**Files:**
- Modify: `docs/trellis/plans/2026-04-22-entry-modularization-roadmap.md`

- [x] **Step 1: Update roadmap status**

Mark the report-runtime migration complete and note which request units have moved off the entry file.

- [x] **Step 2: Run full test suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS with the full suite green.

- [x] **Step 3: Run an entry-level smoke verification if imports allow**

Run: `python3 -m unittest tests.test_legacy_entry_import -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/trellis/plans/2026-04-22-entry-modularization-roadmap.md
git commit -m "docs: update entry modularization roadmap"
```

### Follow-up Progress

- [x] 将候选股历史补数从 `scripts/input/runtime.py` 迁移到 `scripts/domains/watch_candidates/request.py`
- [x] 将放量异常、龙虎榜深度分析、板块共振评分、交易信号从 `scripts/input/runtime.py` 迁移到 `scripts/domains/market_activity/infer.py`
- [x] 让 `scripts/input/runtime.py` 退回到候选池推导、候选历史请求、量化分析 bundle 的薄编排层
- [x] 将 MVP 报告裁剪规则从入口内联函数迁移到 `scripts/report/mvp_compactor.py`
- [x] 让 `build_legacy_final_conclusion_lines` 支持显式 `report_stages` 标题和顺序，减少对固定 Step 文案的依赖
- [x] 将策略账本尾部的 `build_strategy_factor_snapshot / build_strategy_plan_context / update_strategy_performance_book / append_strategy_performance_section / normalize_report_timer_steps` 迁移到 `scripts/report/strategy_tracking_runtime.py`
- [x] 将策略账本 store 的 `load_strategy_performance_ledger / save_strategy_performance_ledger / save_factor_snapshot` 迁移到 `scripts/report/strategy_tracking_store.py`
- [x] 将 recent target followup / reflection / compare 从入口迁移到 `scripts/report/strategy_tracking_followups.py`
- [x] 将策略记录与复盘准备 helper 从入口迁移到 `scripts/report/strategy_tracking_records.py`
- [x] 将策略复盘分析 helper 从入口迁移到 `scripts/report/strategy_tracking_review.py`
- [x] 将策略评估与链路 helper 从入口迁移到 `scripts/report/strategy_tracking_evaluation.py`
- [x] 将策略账本 support helper 从入口迁移到 `scripts/report/strategy_tracking_support.py`
- [x] 将策略 EV calibration helper 从入口迁移到 `scripts/report/strategy_tracking_ev.py`
- [x] 扩展 `scripts/report/strategy_tracking_support.py`，将候选反馈 support helper 从入口迁移过去，已覆盖 `candidate confirmation / probe role / probe candidate scan / history feedback / feedback clock`
- [x] 提取 `scripts/report/observation_plan_formatter.py`，将异动观察/冻结计划 formatter 从入口迁移过去，已覆盖 `follow rule / follow display / abnormal observation columns / frozen plan columns`
- [x] 提取 `scripts/report/observation_price_formatter.py`，将观察价位说明 formatter 从入口迁移过去，已覆盖 `zone badge / price focus text / note text / append note / compose observation focus`
- [x] 扩展 `scripts/report/strategy_tracking_support.py` 与 `scripts/report/strategy_tracking_store.py`，将 `pct formatter / run mode label / ledger path / factor snapshot path` 从入口迁移过去
- [x] 扩展 `scripts/diagnostics/single_stock_runtime.py`，将 `resolve_single_stock_snapshot / generate_single_stock_diagnostic_markdown` 从入口迁移过去
- [x] 收口入口里纯 report output wrapper cluster，直接导出 `daily_report_render` 的 `_get_report_output_path / _get_stock_diagnostic_output_path / _inject_report_variant_banner / _render_report_with_display_mode / build_report_outputs / save_report_output / save_report_outputs / save_stock_diagnostic_output`
- [x] 扩展 `scripts/portfolio/position_management_report.py`，将 `parse_position_string / analyze_position_management` 从入口迁移过去
- [x] 扩展 `scripts/replay/report_replay.py`，将 `replay_from_snapshot` 从入口迁移过去
- [x] 落地 `scripts/market_data/daily_price_runtime.py`，将 `daily bars / trading day / one-word limit / tradability` 相关 helper 从入口迁移过去
- [x] 提取 `scripts/report/strategy_contract_support.py`，将 `trading philosophy / strategy positioning / contract digest / alignment pool` 从入口迁移过去
- [x] 提取 `scripts/report/front_summary_support.py`，将 `front mainline label / style action / core mvp digest / mvp focus summary` 从入口迁移过去
- [x] 提取 `scripts/research/market_research_support.py`，将 `market research snapshot / step0 follow plan / market research renderers / context bundle` 从入口迁移过去
- [x] 扩展 `scripts/risk/risk_bundle_runtime.py`，将 `step3 risk bundle / limit-time parse / limit-up friction / risk reason formatter` 从入口迁移过去
- [x] 扩展 `scripts/research/market_research_support.py`，将 `dialectical decision snapshot / abnormal projection / observation snapshot / follow verdict / mainline competition snapshot` 从入口迁移过去
- [x] 扩展 `scripts/selection/candidate_bundle_runtime.py`，将 `step2 candidate bundle` 从入口迁移过去
- [x] 提取 `scripts/domains/market_state/support.py`，将 `market_state_machine_snapshot / mainline_pulse / environment_score / structure_score / mainline_score / memory_score / abnormal_score / flow normalization` 从入口迁移过去
- [x] 提取 `scripts/selection/watch_anchor_support.py`，将 `watch_anchor_bucket / crossline_second_confirmation / watch_anchor_type / pending_candidate_type / watch_anchor_note / append_watch_anchor_note` 从入口迁移过去
- [x] 提取 `scripts/report/strategy_tracking_snapshot_support.py`，将 `abnormal_setup_distribution / snapshot_candidate_brief` 从入口迁移过去
- [x] 提取 `scripts/selection/mainline_support.py`，将 `resolve_primary_mainline_name / split_candidates_by_mainline` 从入口迁移过去
- [x] 提取 `scripts/selection/candidate_context_support.py`，将 `build_washout_reclaim_context / build_trend_continuation_context` 从入口迁移过去
- [x] 修复旧入口直跑兼容链：补齐 `data_collector / xuangubao_intraday / ths_hot_stock / ths_hot_list / tencent_finance_data / limit_up_down_pool / strong_stock_pool / data_validator / quantitative_analyzer / hot_list_integrated / history_cache / llm_service` 本地 shim
- [x] 修复 report/runtime 与 strategy tracking 真实运行时漏口：已补齐 `today_predictions / nextday_predictions`、front-summary runtime wrapper helper 注入、`risk_sectors` 传递，以及 `no actionable` 窗口跳过 benchmark 抓取
