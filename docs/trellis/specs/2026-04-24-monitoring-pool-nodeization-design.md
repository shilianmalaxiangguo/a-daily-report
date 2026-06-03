# Monitoring Pool Nodeization Design

> Scope: 把当前已落地的监测池系统从 `strategy_performance_renderer.py` 直出，收口成独立的 node 输出链，做到可裁剪、可替换、可与现有 report nodeization 体系保持一致。

## Goal

为监测池新增完整 node 化结构：
- 独立 registry / runtime / nodes
- 保持现有 `strategy_performance_renderer.py` 兼容入口
- 支持按 node key 单独裁剪主池/副池摘要与明细

## Why Now

当前监测池已经具备：
- 主监测池 / 副监测池
- 进池规则
- 升降级 / 淘汰语义
- 摘要表 + 日度展开表
- 观察锚点 / 容忍带 / 失真线 / 日标签

功能已成独立子系统，继续挂在 renderer 里会阻碍：
- 摘要/明细单独裁剪
- 后续增加节点日志追踪
- 与整份日报的 nodeization 结构统一

## Target Architecture

新增三文件：
- `scripts/report/monitoring_pool_node_registry.py`
- `scripts/report/monitoring_pool_node_runtime.py`
- `scripts/report/monitoring_pool_nodes.py`

### Node Split

建议先拆成 6 个顶层节点：
- `main_pool_header`
- `main_pool_summary`
- `main_pool_details`
- `secondary_pool_header`
- `secondary_pool_summary`
- `secondary_pool_details`

不再继续细拆到单票级 node，先保证摘要/明细可以分开裁剪。

## Compatibility

保留现有入口：
- `render_strategy_performance_section()` 仍可调用，但监测池部分改为委托 node runtime
- 旧测试和调用链无需整体重写

## Context Contract

node context 继续使用：
- `performance_summary.monitoring_pool.main_pool`
- `performance_summary.monitoring_pool.secondary_pool`
- 每个 item 内的：
  - `anchor_price`
  - `observation_band_low/high`
  - `failure_line`
  - `assessment_reason`
  - `monitoring_rows`

## Rendering Rules

### Main Pool
- `main_pool_header`: 标题与说明
- `main_pool_summary`: 摘要表
- `main_pool_details`: 每只票的锚点/容忍带/失真线/原因 + 日度明细表

### Secondary Pool
- `secondary_pool_header`: 标题与说明
- `secondary_pool_summary`: 摘要表
- `secondary_pool_details`: 每只票的锚点/容忍带/失真线/原因 + 日度明细表

## Acceptance

- 监测池部分不再在 `strategy_performance_renderer.py` 里直接拼接大块文本
- 监测池支持 `enabled_node_keys` 裁剪
- 旧入口兼容
- replay/report 相关测试继续通过
