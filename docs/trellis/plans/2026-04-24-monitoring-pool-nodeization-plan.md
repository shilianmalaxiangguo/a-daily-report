# Monitoring Pool Nodeization Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前监测池系统从 `strategy_performance_renderer.py` 直出重构成独立 node 输出链，同时保持现有策略账本渲染入口兼容。

**Architecture:** 新增 monitoring pool 的 node registry/runtime/nodes 三文件，把主池/副池摘要和明细拆成 6 个顶层节点。旧 `render_strategy_performance_section()` 继续存在，但监测池部分改为通过 node runtime 生成。

**Tech Stack:** Python 3.11, unittest, existing report nodeization pattern

---

### Task 1: 新增 monitoring pool node runtime 骨架

**Files:**
- Create: `scripts/report/monitoring_pool_node_registry.py`
- Create: `scripts/report/monitoring_pool_node_runtime.py`
- Create: `scripts/report/monitoring_pool_nodes.py`
- Test: `tests/test_monitoring_pool_node_runtime.py`

- [ ] 写 failing test：node runtime 可按 `enabled_node_keys` 裁剪主池/副池节点
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_node_runtime`，确认失败
- [ ] 最小实现 registry/runtime/nodes 骨架
- [ ] 重跑 `venv/bin/python -m unittest tests.test_monitoring_pool_node_runtime`，确认通过

### Task 2: 主池节点化

**Files:**
- Modify: `scripts/report/monitoring_pool_nodes.py`
- Test: `tests/test_monitoring_pool_node_runtime.py`

- [ ] 写 failing test：`main_pool_header / main_pool_summary / main_pool_details` 分别可单独输出
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_node_runtime`，确认失败
- [ ] 最小实现主池 3 个节点
- [ ] 重跑 `venv/bin/python -m unittest tests.test_monitoring_pool_node_runtime`，确认通过

### Task 3: 副池节点化

**Files:**
- Modify: `scripts/report/monitoring_pool_nodes.py`
- Test: `tests/test_monitoring_pool_node_runtime.py`

- [ ] 写 failing test：`secondary_pool_header / secondary_pool_summary / secondary_pool_details` 分别可单独输出
- [ ] 运行 `venv/bin/python -m unittest tests.test_monitoring_pool_node_runtime`，确认失败
- [ ] 最小实现副池 3 个节点
- [ ] 重跑 `venv/bin/python -m unittest tests.test_monitoring_pool_node_runtime`，确认通过

### Task 4: renderer 兼容接线

**Files:**
- Modify: `scripts/report/strategy_performance_renderer.py`
- Test: `tests/test_strategy_performance_renderer.py`

- [ ] 写 failing test：renderer 不再直接拼监测池大块，而是通过 monitoring node runtime 输出
- [ ] 运行 `venv/bin/python -m unittest tests.test_strategy_performance_renderer`，确认失败
- [ ] 最小改造兼容入口
- [ ] 重跑 `venv/bin/python -m unittest tests.test_strategy_performance_renderer`，确认通过

### Task 5: 策略尾部与报告回归

**Files:**
- Test: `tests/test_use_strategy_performance_tail.py`
- Test: `tests/test_daily_report_render.py`
- Test: `tests/test_report_runtime.py`

- [ ] 运行尾部和报告测试，确认监测池区块仍能出现在策略账本里
- [ ] 如失败，最小修正接线
- [ ] 重跑测试确认通过

### Task 6: 最终验收

**Files:**
- Test: `tests/test_monitoring_pool_support.py`
- Test: `tests/test_monitoring_pool_node_runtime.py`
- Test: `tests/test_strategy_tracking_runtime.py`
- Test: `tests/test_strategy_performance_renderer.py`
- Test: `tests/test_use_strategy_performance_tail.py`
- Test: `tests/test_daily_report_render.py`
- Test: `tests/test_report_runtime.py`

- [ ] 运行整组 monitoring + renderer + report 测试
- [ ] 如可行，再跑一次 replay 检查监测池段落
