# Monitoring Pool Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为策略跟踪链路新增主监测池 / 副监测池、走势分类、日度监测行和尾部渲染，让用户可以持续复盘明日标的和观察池标的从选中日起到当前的走势质量。

**Architecture:** 基于现有 `strategy_tracking_*` 账本与 `daily_price_runtime.py` 扩展，不另起账本。新增一个 monitoring support 层负责池归集、日度 OHLC 评估、走势分类与状态迁移，再由 renderer 输出主池/副池摘要表和展开表。

**Tech Stack:** Python 3.11, unittest, existing report runtime/render pipeline

---

### Task 1: 设计监测池 support 运行时骨架

**Files:**
- Create: `scripts/report/monitoring_pool_support.py`
- Test: `tests/test_monitoring_pool_support.py`

- [ ] 写 failing test：`build_monitoring_row()` 生成日度 OHLC / 日涨幅 / 累计涨幅 / 收盘位置 / 量能 / K线形态
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_support`，确认失败
- [ ] 最小实现 `build_monitoring_row()` 与 candle/volume helpers
- [ ] 重跑 `venv/bin/python -m unittest tests.test_monitoring_pool_support`，确认通过

### Task 2: 监测池来源归集

**Files:**
- Modify: `scripts/report/monitoring_pool_support.py`
- Test: `tests/test_monitoring_pool_support.py`

- [ ] 写 failing test：主池只收执行候选/核心候选，副池收跨线观察/20cm侧翼/普通观察
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_support`，确认失败
- [ ] 最小实现 `collect_monitoring_pool_candidates()`
- [ ] 重跑 `venv/bin/python -m unittest tests.test_monitoring_pool_support`，确认通过

### Task 3: 走势分类与状态迁移

**Files:**
- Modify: `scripts/report/monitoring_pool_support.py`
- Test: `tests/test_monitoring_pool_support.py`

- [ ] 写 failing test：博杰/龙蟠归为 `trend_continuation`，中嘉/津药归为 `fast_in_fast_out`，石大归为 `range_consumption`
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_support`，确认失败
- [ ] 最小实现 `classify_monitoring_pattern()` 与 `assess_monitoring_status()`
- [ ] 重跑 `venv/bin/python -m unittest tests.test_monitoring_pool_support`，确认通过

### Task 4: 接入 strategy tracking evaluation

**Files:**
- Modify: `scripts/report/strategy_tracking_evaluation.py`
- Modify: `scripts/report/strategy_tracking_runtime.py`
- Test: `tests/test_strategy_tracking_evaluation.py`
- Test: `tests/test_strategy_tracking_runtime.py`

- [ ] 写 failing test：strategy tracking summary 中新增主池/副池 monitoring 结果
- [ ] 运行 `venv/bin/python -m unittest tests.test_strategy_tracking_evaluation tests.test_strategy_tracking_runtime`，确认失败
- [ ] 最小接入 monitoring support 到 tracking evaluation/runtime
- [ ] 重跑 `venv/bin/python -m unittest tests.test_strategy_tracking_evaluation tests.test_strategy_tracking_runtime`，确认通过

### Task 5: 扩展 tracking records 持久字段

**Files:**
- Modify: `scripts/report/strategy_tracking_records.py`
- Test: `tests/test_strategy_tracking_records.py`

- [ ] 写 failing test：record 支持 `source_pool / tracking_status / pattern_type / anchor_price / observation_band / failure_line / monitoring_rows`
- [ ] 运行 `venv/bin/python -m unittest tests.test_strategy_tracking_records`，确认失败
- [ ] 最小实现 records merge/upsert 对新增字段的保留与更新
- [ ] 重跑 `venv/bin/python -m unittest tests.test_strategy_tracking_records`，确认通过

### Task 6: 监测池 renderer 输出

**Files:**
- Create: `scripts/report/monitoring_pool_renderer.py`
- Modify: `scripts/report/strategy_performance_renderer.py`
- Test: `tests/test_monitoring_pool_renderer.py`
- Test: `tests/test_strategy_performance_renderer.py`

- [ ] 写 failing test：渲染主监测池/副监测池摘要表与展开表
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_renderer tests.test_strategy_performance_renderer`，确认失败
- [ ] 最小实现 renderer，并在 strategy performance tail 中接入
- [ ] 重跑 `venv/bin/python -m unittest tests.test_monitoring_pool_renderer tests.test_strategy_performance_renderer`，确认通过

### Task 7: 样本回归断言

**Files:**
- Modify: `tests/test_monitoring_pool_support.py`

- [ ] 加入博杰股份、龙蟠科技、石大胜华、中嘉博创、津药药业五个样本断言
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_support`，确认通过

### Task 8: 端到端报告回归

**Files:**
- Test: `tests/test_daily_report_render.py`
- Test: `tests/test_report_runtime.py`
- Test: `tests/test_use_strategy_performance_tail.py`

- [ ] 写 failing test：报告尾部包含主监测池/副监测池区块
- [ ] 运行 `venv/bin/python -m unittest tests.test_daily_report_render tests.test_report_runtime tests.test_use_strategy_performance_tail`，确认失败
- [ ] 最小修正接线
- [ ] 重跑 `venv/bin/python -m unittest tests.test_daily_report_render tests.test_report_runtime tests.test_use_strategy_performance_tail`，确认通过

### Task 9: 最终验收

**Files:**
- Test: `tests/test_monitoring_pool_support.py`
- Test: `tests/test_strategy_tracking_records.py`
- Test: `tests/test_strategy_tracking_evaluation.py`
- Test: `tests/test_strategy_tracking_runtime.py`
- Test: `tests/test_monitoring_pool_renderer.py`
- Test: `tests/test_strategy_performance_renderer.py`
- Test: `tests/test_use_strategy_performance_tail.py`
- Test: `tests/test_daily_report_render.py`
- Test: `tests/test_report_runtime.py`

- [ ] 运行整组 monitoring 相关测试并确认通过
- [ ] 如可行，再运行 `venv/bin/python scripts/daily_report_entry_demo.py 2026-04-23 --replay`
- [ ] 确认报告新增主监测池/副监测池且字段齐全
