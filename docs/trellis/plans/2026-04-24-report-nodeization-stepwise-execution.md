# Report Nodeization Stepwise Execution Tasks

> **For agentic workers:** Execute strictly from Task 1 to Task 12. Do not mark a task complete until its file checks and targeted tests pass.

**Goal:** 按 `2026-04-24-report-nodeization-task-list.md` 的 Task 1–12 逐项复核并补齐 node 化，不用总体验收替代逐项执行。

**Architecture:** 每个任务先查 node registry/runtime/builder 接入，再跑对应 unittest。若发现普通 renderer 黑盒、手工 append 或不可裁剪入口残留，先写/调整测试观察失败，再修实现，最后重跑该任务测试。

**Tech Stack:** Python 3.11 venv, unittest, report runtime/render/replay pipeline

---

## Task 1: Step 0 市场研究快照 Node 化

**Files:**
- Check: `scripts/report/market_research_snapshot_node_registry.py`
- Check: `scripts/report/market_research_snapshot_node_runtime.py`
- Check: `scripts/report/market_research_snapshot_nodes.py`
- Check: `scripts/report/market_research_renderer.py`
- Test: `tests/test_market_research_renderer.py`

- [x] 核验快照 node 文件存在
- [x] 核验 `render_market_research_snapshot_section()` 走 node runtime 且支持 `enabled_node_keys`
- [x] 运行 `venv/bin/python -m unittest tests.test_market_research_renderer`

## Task 2: Step 0 跟随裁决 Node 化

**Files:**
- Check: `scripts/report/step0_follow_node_registry.py`
- Check: `scripts/report/step0_follow_node_runtime.py`
- Check: `scripts/report/step0_follow_nodes.py`
- Check: `scripts/report/market_research_renderer.py`
- Check: `scripts/domains/execution_chain/environment_follow_stage.py`
- Test: `tests/test_market_research_renderer.py`

- [x] 核验 step0 follow node 文件存在
- [x] 核验 `render_step0_follow_section()` 走 node runtime 且支持 `enabled_node_keys`
- [x] 核验 `environment_follow_stage` 不直接吞整段 renderer 细节
- [x] 运行 `venv/bin/python -m unittest tests.test_market_research_renderer`

## Task 3: 顶部纪律壳 Node 化

**Files:**
- Check: `scripts/report/report_shell_node_registry.py`
- Check: `scripts/report/report_shell_node_runtime.py`
- Check: `scripts/report/report_shell_nodes.py`
- Check: `scripts/report/report_document_builder.py`
- Test: `tests/test_report_document_builder.py`

- [x] 核验 report shell node 文件存在
- [x] 核验 `次日操作纪律` 通过 node specs/runtime 生成
- [x] 运行 `venv/bin/python -m unittest tests.test_report_document_builder`

## Task 4: 仓位与中枢块 Node 化

**Files:**
- Check: `scripts/report/positioning_node_registry.py`
- Check: `scripts/report/positioning_node_runtime.py`
- Check: `scripts/report/positioning_nodes.py`
- Check: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py`

- [x] 核验 positioning node 文件存在
- [x] 核验 `runtime.py` 不再手工 append 仓位与中枢大块
- [x] 运行 `venv/bin/python -m unittest tests.test_report_runtime`

## Task 5: 核心结论看板前半段 Node 化

**Files:**
- Check: `scripts/report/decision_board_node_registry.py`
- Check: `scripts/report/decision_board_node_runtime.py`
- Check: `scripts/report/decision_board_nodes.py`
- Check: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py`

- [x] 核验 decision board node 文件存在
- [x] 核验 `主线方向 / 仓位决策 / 明天要防什么` 由 node 输出
- [x] 运行 `venv/bin/python -m unittest tests.test_report_runtime`

## Task 6: 预期日历 Node 化

**Files:**
- Check: `scripts/report/calendar_section_node_registry.py`
- Check: `scripts/report/calendar_section_node_runtime.py`
- Check: `scripts/report/calendar_section_nodes.py`
- Check: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py`

- [x] 核验 calendar section node 文件存在
- [x] 核验日历块支持按节点裁剪
- [x] 运行 `venv/bin/python -m unittest tests.test_report_runtime`

## Task 7: Market Activity 章节 Node 化

**Files:**
- Check: `scripts/domains/market_activity/report_section_node_registry.py`
- Check: `scripts/domains/market_activity/report_section_node_runtime.py`
- Check: `scripts/domains/market_activity/report_section_nodes.py`
- Check: `scripts/domains/market_activity/report_sections.py`
- Test: `tests/test_market_activity_domain_report_sections.py`

- [x] 核验 Market Activity 顶层 node 文件存在
- [x] 核验 `hot_rank / turnover / sector_fund_flow / lhb` 子节点可裁剪
- [x] 运行 `venv/bin/python -m unittest tests.test_market_activity_domain_report_sections`

## Task 8: 三到十二章剩余 Builder Node 化

**Files:**
- Check: `scripts/report/market_overview_builder.py`
- Check: `scripts/report/market_analysis_builder.py`
- Check: `scripts/report/board_tag_analysis_builder.py`
- Check: `scripts/report/exchange_monitor_builder.py`
- Test: `tests/test_market_overview_builder.py`
- Test: `tests/test_market_analysis_builder.py`
- Test: `tests/test_board_tag_analysis_builder.py`
- Test: `tests/test_exchange_monitor_builder.py`
- Test: `tests/test_daily_report_render.py`
- Test: `tests/test_report_runtime.py`

- [x] 核验 market overview / analysis / board tag / exchange monitor 都接入 node runtime
- [x] 核验旧 contract 入口保留兼容且支持 `enabled_node_keys`
- [x] 运行对应 builder 与 runtime 测试

## Task 9: 尾部补充区 Node 化

**Files:**
- Check: `scripts/hooks/report/use_report_tail_summary.py`
- Check: `scripts/report/front_summary_renderer.py`
- Check: `scripts/report/context_sections_renderer.py`
- Test: `tests/test_front_summary_renderer.py`
- Test: `tests/test_context_sections_renderer.py`
- Test: `tests/test_use_report_tail_summary.py`

- [x] 核验 front summary / context sections 都接入 node runtime
- [x] 核验 tail hook 只做组装与透传
- [x] 运行尾部补充区测试

## Task 10: 策略账本与附录 Node 化

**Files:**
- Check: `scripts/hooks/report/use_strategy_performance_tail.py`
- Check: `scripts/report/strategy_performance_renderer.py`
- Check: `scripts/hooks/report/use_execution_appendix_tail.py`
- Check: `scripts/report/appendix_renderer.py`
- Test: `tests/test_strategy_performance_renderer.py`
- Test: `tests/test_use_strategy_performance_tail.py`
- Test: `tests/test_use_execution_appendix_tail.py`

- [x] 核验 strategy performance / appendix 都接入 node runtime
- [x] 核验 hook 只做尾部装配，不持有整段正文
- [x] 运行策略账本与附录测试

## Task 11: Runtime 总装配清理

**Files:**
- Check: `scripts/report/runtime.py`
- Check: `scripts/daily_report_render.py`
- Test: `tests/test_report_runtime.py`
- Test: `tests/test_daily_report_render.py`
- Test: `tests/test_report_document_builder.py`

- [x] 核验 `runtime.py` 只剩装配和上下文透传，不残留大块手工 append
- [x] 核验 `full / summary / replay` 入口兼容
- [x] 运行 runtime/render/document builder 测试

## Task 12: 执行链残留普通 Renderer 去黑盒化

**Files:**
- Check: `scripts/domains/execution_chain/candidate_selection_nodes/mainline_summary.py`
- Check: `scripts/domains/execution_chain/risk_review_nodes/gem_pool.py`
- Test: `tests/test_candidate_selection_stage.py`
- Test: `tests/test_risk_review_stage.py`

- [x] 核验 candidate selection 创业板观察不调用 legacy renderer fallback
- [x] 核验 risk review 创业板观察池不调用 legacy renderer fallback
- [x] 运行 candidate/risk 测试

## Final Acceptance

- [x] 运行 15 个清单相关测试模块合并回归
- [x] 运行 `venv/bin/python scripts/daily_report_entry_demo.py 2026-04-23 --replay`
- [x] 检查 replay 不含 `草稿|概念说明`
- [x] 检查 replay 不重复输出空仓结论
- [x] 将本文件所有任务打勾，并记录命令证据


## Execution Evidence

- Task 1: `market_research_snapshot_node_*` files exist; `render_market_research_snapshot_section()` uses node specs/runtime with `enabled_node_keys`; `venv/bin/python -m unittest tests.test_market_research_renderer` passed.
- Task 2: `step0_follow_node_*` files exist; `render_step0_follow_section()` uses node specs/runtime with `enabled_node_keys`; `environment_follow_stage` is stage-shell oriented; `tests.test_market_research_renderer` passed.
- Task 3: `report_shell_node_*` files exist; `report_document_builder.py` routes discipline/prohibition sections through node specs/runtime; `tests.test_report_document_builder` passed.
- Task 4: `positioning_node_*` files exist; `runtime.py` no longer contains positioning block append chains; `tests.test_report_runtime` passed.
- Task 5: `decision_board_node_*` files exist and output `主线方向 / 仓位决策 / 明天要防什么`; `tests.test_report_runtime` passed.
- Task 6: `calendar_section_node_*` files exist and support `enabled_node_keys`; `tests.test_report_runtime` passed.
- Task 7: `report_section_node_*` files exist; `hot_rank / turnover / sector_fund_flow / lhb` subnodes are independently selectable; `tests.test_market_activity_domain_report_sections` passed.
- Task 8: `market_overview / market_analysis / board_tag_analysis / exchange_monitor` builders route through node specs/runtime and preserve contract entry compatibility; related builder/runtime tests passed.
- Task 9: `front_summary_renderer.py` and `context_sections_renderer.py` route through node specs/runtime; tail summary hook remains assembly/pass-through; tail tests passed.
- Task 10: `strategy_performance_renderer.py` and `appendix_renderer.py` route through node specs/runtime; tail hooks remain assembly/pass-through; strategy/appendix tests passed.
- Task 11: `runtime.py` residual `report.append("")` is only blank-line assembly; runtime/render/document builder tests passed.
- Task 12: Removed legacy renderer fallback from candidate/risk GEM nodes; tests now fail if legacy renderer is called; `tests.test_candidate_selection_stage tests.test_risk_review_stage` passed.
- Final regression: `venv/bin/python -m unittest tests.test_market_research_renderer tests.test_market_activity_domain_report_sections tests.test_board_tag_analysis_builder tests.test_exchange_monitor_builder tests.test_front_summary_renderer tests.test_context_sections_renderer tests.test_use_report_tail_summary tests.test_strategy_performance_renderer tests.test_use_strategy_performance_tail tests.test_use_execution_appendix_tail tests.test_report_runtime tests.test_daily_report_render tests.test_report_document_builder tests.test_candidate_selection_stage tests.test_risk_review_stage` -> `Ran 71 tests ... OK`.
- Replay: `venv/bin/python scripts/daily_report_entry_demo.py 2026-04-23 --replay` regenerated `reports/replay/2026-04-23_A股日报_完整版_replay.md` and `reports/replay/2026-04-23_A股日报_执行摘要_replay.md`.
- Replay content: `rg -n "草稿|概念说明" reports/replay/2026-04-23_A股日报_*_replay.md` returned no matches; full replay counts: `空仓结论=0`, `极端困难模式=0`, `空仓等待，禁止参与=1`.
- Scope note: Full `unittest discover` was not claimed because broad discovery can be delayed by external行情/data tests; this execution used the checklist-specific acceptance set.
