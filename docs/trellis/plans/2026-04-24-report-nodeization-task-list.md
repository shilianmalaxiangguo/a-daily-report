# Report Nodeization Task List

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis test-first execution for each task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把成品日报从上到下继续收口成 node 化输出链，做到可裁剪、可替换、可局部维护、可日志追踪，同时保持旧接口兼容。

**Architecture:** 以“成品日报真实装配顺序”为主线，不再按旧 Step 编号整块迁移。优先把当前仍在 `runtime.py` 里手工 `append` 的大块，以及仍在 hook 中挂普通 renderer 的出口，逐步改成 `node_registry + node_runtime + node builders`。

**Tech Stack:** Python, unittest, existing report runtime/render pipeline

---

## 执行看板

### 已完成

- [x] Task 1: Step 0 市场研究快照 Node 化
- [x] Task 2: Step 0 跟随裁决 Node 化
  - [x] `environment_follow_stage` 继续瘦身，只保留 stage 壳
- [x] Task 3: 顶部纪律壳 Node 化
- [x] Task 4: 仓位与中枢块 Node 化
- [x] Task 5: 核心结论看板前半段 Node 化
- [x] Task 6: 预期日历 Node 化

### 待完成

- [x] Task 7: Market Activity 章节 Node 化
- [x] Task 8: 三到十二章剩余 Builder Node 化
- [x] Task 9: 尾部补充区 Node 化
- [x] Task 10: 策略账本与附录 Node 化
- [x] Task 11: Runtime 总装配清理

### 剩余收尾执行清单

1. [x] Task 7.1: `hot_rank` 内部拆成 `hot_rank_header / hot_rank_table`
2. [x] Task 7.2: `turnover` 内部拆成 `turnover_header / turnover_table`
3. [x] Task 7.3: `sector_fund_flow` 内部拆成 `sector_fund_header / sector_fund_inflow / sector_fund_outflow`
4. [x] Task 7.4: `lhb` 内部拆成 `lhb_header / lhb_buy / lhb_sell`
5. [x] Task 11.1: `runtime.py` 只保留装配与上下文透传的验收测试
6. [x] Task 11.2: `full / summary / replay` 三出口兼容回归
7. [x] Task 12.1: `candidate_selection` 创业板观察从普通 renderer 改为 node builder
8. [x] Task 12.2: `risk_review` 创业板观察池从普通 renderer 改为 node builder
9. [x] Task 12.3: replay 产物验收：日报不重复空仓结论、不输出草稿概念说明

### 执行顺序

1. 先收尾 Task 2
2. 再做 Task 7
3. 然后做 Task 8
4. 再做 Task 9
5. 再做 Task 10
6. 最后做 Task 11

## 当前从上到下 Node 化验收状态

1. 三到十二章业务 builder
   - `scripts/report/market_overview_builder.py`
   - `scripts/domains/market_activity/report_sections.py`
   - `scripts/report/market_analysis_builder.py`
   - `scripts/report/board_tag_analysis_builder.py`
   - `scripts/report/exchange_monitor_builder.py`
   - 状态：已收成 `node_registry + node_runtime + node builders` 兼容壳，并保留旧 contract 入口

2. 十三章开头 `总-市场整体判断`
   - 当前位置：`scripts/report/execution_chain_overview_nodes.py`
   - 状态：已从 `runtime.py` 手工 append 收成 execution-chain overview node

3. 原统一执行链普通 renderer 残留
   - `scripts/domains/execution_chain/candidate_selection_nodes/mainline_summary.py`
   - `scripts/domains/execution_chain/risk_review_nodes/gem_pool.py`
   - 状态：候选筛选 / 风险复核的创业板观察块已改为节点 builder 独立输出，`market_research_renderer.py` 仅保留兼容入口

4. 原统一执行链前台摘要 renderer 残留
   - `scripts/report/front_summary_renderer.py`
   - 状态：`core_mvp_digest / mvp_focus_summary` 已收成 `front_digest / mvp_focus` node 壳

5. 尾部补充区
   - `scripts/hooks/report/use_report_tail_summary.py`
   - `scripts/report/context_sections_renderer.py`
   - 状态：`主线纪律 / 补充观察 / 市场快照` 已收成 context section node，hook 只做组装和透传

6. 策略计划账本尾部
   - `scripts/hooks/report/use_strategy_performance_tail.py`
   - `scripts/report/strategy_performance_renderer.py`
   - 状态：正文已收成 strategy performance node，hook 保留日志与统计透传

7. 执行附录尾部
   - `scripts/hooks/report/use_execution_appendix_tail.py`
   - `scripts/report/appendix_renderer.py`
   - 状态：正文已收成 appendix node，hook 只负责尾部装配

### Task 1: Step 0 市场研究快照 Node 化

**Files:**
- Create: `scripts/report/market_research_snapshot_node_registry.py`
- Create: `scripts/report/market_research_snapshot_node_runtime.py`
- Create: `scripts/report/market_research_snapshot_nodes.py`
- Modify: `scripts/report/market_research_renderer.py`
- Test: `tests/test_market_research_renderer.py`

- [x] 把 `render_market_research_snapshot_section()` 改成走 node runtime，但保留旧函数名和旧调用方式
- [x] 支持 `enabled_node_keys`，先做到快照行可动态裁剪
- [x] 保持 full / compact 两种模式输出兼容

### Task 2: Step 0 跟随裁决 Node 化

**Files:**
- Create: `scripts/report/step0_follow_node_registry.py`
- Create: `scripts/report/step0_follow_node_runtime.py`
- Create: `scripts/report/step0_follow_nodes.py`
- Modify: `scripts/report/market_research_renderer.py`
- Modify: `scripts/domains/execution_chain/environment_follow_stage.py`
- Test: `tests/test_market_research_renderer.py`

- [x] 把 `render_step0_follow_section()` 拆成裁决、风险偏好、主线焦点、异常承接、最终状态几个 node
- [x] 让 `environment_follow_stage` 只负责 stage 壳，不再吞整段 renderer 细节

### Task 3: 顶部纪律壳 Node 化

**Files:**
- Create: `scripts/report/report_shell_node_registry.py`
- Create: `scripts/report/report_shell_node_runtime.py`
- Create: `scripts/report/report_shell_nodes.py`
- Modify: `scripts/report/report_document_builder.py`
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_report_document_builder.py`

- [x] 把 `次日操作纪律` 从整块 contract 改成 node 链
- [x] 让禁止事项、允许事项、风险板块提示都能单独替换

### Task 4: 仓位与中枢块 Node 化

**Files:**
- Create: `scripts/report/positioning_node_registry.py`
- Create: `scripts/report/positioning_node_runtime.py`
- Create: `scripts/report/positioning_nodes.py`
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py`

- [x] 拆出 `环境标题 / 核心状态 / 结构区间 / 图示 / 中枢表 / 过渡结构 / 空态` 等节点
- [x] 去掉 `runtime.py` 中这段长串 `report.append(...)`

### Task 5: 核心结论看板前半段 Node 化

**Files:**
- Create: `scripts/report/decision_board_node_registry.py`
- Create: `scripts/report/decision_board_node_runtime.py`
- Create: `scripts/report/decision_board_nodes.py`
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py`

- [x] 把 `主线方向 / 仓位决策 / 明天要防什么` 迁成 node
- [x] 保持数据驱动和结论优先，不回退成解释味

### Task 6: 预期日历 Node 化

**Files:**
- Create: `scripts/report/calendar_section_node_registry.py`
- Create: `scripts/report/calendar_section_node_runtime.py`
- Create: `scripts/report/calendar_section_nodes.py`
- Modify: `scripts/report/runtime.py`
- Test: `tests/test_report_runtime.py`

- [x] 拆出 `热点分布 / 重点事件 / 利好方向 / 产业链洞察 / 空态`
- [x] 让日历块可以在 full / summary 下动态裁剪

### Task 7: Market Activity 章节 Node 化

**Files:**
- Create: `scripts/domains/market_activity/report_section_node_registry.py`
- Create: `scripts/domains/market_activity/report_section_node_runtime.py`
- Create: `scripts/domains/market_activity/report_section_nodes.py`
- Modify: `scripts/domains/market_activity/report_sections.py`
- Test: `tests/test_market_activity_domain_report_sections.py`

- [x] 把 `热度 / 成交 / 资金 / 龙虎榜 / 连板 / 多维交易结果` 各自拆成顶层 node
- [x] 让基础活跃度与高阶活跃度入口都支持 `enabled_node_keys`
- [x] 高阶 `多维交易结果` 已拆出 `advanced_header`，可独立裁剪总标题和子业务块
- [x] 基础业务块内部继续允许按子 node 裁剪

### Task 8: 三到十二章剩余 Builder Node 化

**Files:**
- Modify: `scripts/report/market_overview_builder.py`
- Modify: `scripts/report/market_analysis_builder.py`
- Modify: `scripts/report/board_tag_analysis_builder.py`
- Modify: `scripts/report/exchange_monitor_builder.py`
- Add supporting node runtime/registry files as needed
- Test: `tests/test_daily_report_render.py`, `tests/test_report_runtime.py`

- [x] 继续清掉普通 contract/builder 整段输出
- [x] `market_overview_builder.py` 已收成顶层 node 壳，并支持 `enabled_node_keys`
- [x] `market_analysis_builder.py` 已收成顶层 node 壳，并支持 `enabled_node_keys`
- [x] `board_tag_analysis_builder.py` 收成顶层 node 壳，并支持 `enabled_node_keys`
- [x] `exchange_monitor_builder.py` 收成顶层 node 壳，并支持 `enabled_node_keys`
- [x] 统一到可裁剪、可追踪的 node 输出模型

### Task 8.1: 板块标签分析 Node 化

**Files:**
- Create: `scripts/report/board_tag_analysis_node_registry.py`
- Create: `scripts/report/board_tag_analysis_node_runtime.py`
- Create: `scripts/report/board_tag_analysis_nodes.py`
- Modify: `scripts/report/board_tag_analysis_builder.py`
- Test: `tests/test_board_tag_analysis_builder.py`

- [x] 拆出 `header / source_note / analysis / footer` 顶层 node
- [x] 保持旧 `build_board_tag_analysis_sections_contract()` 入口兼容
- [x] 支持 `enabled_node_keys` 动态裁剪

### Task 8.2: 异动监控 Node 化

**Files:**
- Create: `scripts/report/exchange_monitor_node_registry.py`
- Create: `scripts/report/exchange_monitor_node_runtime.py`
- Create: `scripts/report/exchange_monitor_nodes.py`
- Modify: `scripts/report/exchange_monitor_builder.py`
- Test: `tests/test_exchange_monitor_builder.py`

- [x] 拆出 `header / today_alerts / nextday_alerts / footer` 顶层 node
- [x] 保持旧 `build_exchange_monitor_sections_contract()` 入口兼容
- [x] 支持 `enabled_node_keys` 动态裁剪

### Task 9: 尾部补充区 Node 化

**Files:**
- Modify: `scripts/hooks/report/use_report_tail_summary.py`
- Modify: `scripts/report/front_summary_renderer.py`
- Modify: `scripts/report/context_sections_renderer.py`
- Add supporting node runtime/registry files as needed
- Test: `tests/test_front_summary_renderer.py`, `tests/test_context_sections_renderer.py`, `tests/test_use_report_tail_summary.py`

- [x] 把 `front summary / supplementary perspective / market snapshot` 从普通 renderer 收成 node
- [x] `front_summary_renderer.py` 已收成 `front_digest / mvp_focus` node 壳
- [x] `context_sections_renderer.py` 已收成 `mainline_discipline / supplementary_perspective / market_insight` node 壳
- [x] 尾部 hook 只做组装和透传，不持有整段文案
- [x] `use_report_tail_summary.py` 已优先走统一 `render_context_tail_sections` 出口，旧 helper 仅作 fallback

### Task 10: 策略账本与附录 Node 化

**Files:**
- Modify: `scripts/hooks/report/use_strategy_performance_tail.py`
- Modify: `scripts/report/strategy_performance_renderer.py`
- Modify: `scripts/hooks/report/use_execution_appendix_tail.py`
- Modify: `scripts/report/appendix_renderer.py`
- Test: `tests/test_strategy_performance_renderer.py`, `tests/test_use_strategy_performance_tail.py`, `tests/test_use_execution_appendix_tail.py`

- [x] 把 `策略计划账本` 和 `附录` 从大 renderer 收成 node
- [x] 保留日志与统计能力，但正文结构可替换
- [x] `use_strategy_performance_tail.py` 已优先走统一 `render_strategy_performance_nodes` 出口，旧 append helper 仅作 fallback

### Task 11: Runtime 总装配清理

**Files:**
- Modify: `scripts/report/runtime.py`
- Modify: `scripts/daily_report_render.py`
- Test: `tests/test_report_runtime.py`, `tests/test_daily_report_render.py`, `tests/test_report_document_builder.py`

- [x] 清掉剩余手工 `append` 大块
- [x] `runtime.py` 统一执行链开头 `总-市场整体判断` 已收成 node
- [x] `runtime.py` 极端困难空仓分支已收成 node
- [x] 让 runtime 只负责装配节点和透传上下文
- [x] 确保 full / summary / replay 三条出口都兼容

### Task 12: 执行链残留普通 Renderer 去黑盒化

**Files:**
- Modify: `scripts/domains/execution_chain/candidate_selection_nodes/mainline_summary.py`
- Modify: `scripts/domains/execution_chain/risk_review_nodes/gem_pool.py`
- Modify: `scripts/report/market_research_renderer.py` as compatibility wrapper only if needed
- Test: `tests/test_candidate_selection_stage.py`, `tests/test_risk_review_stage.py`, replay smoke tests

- [x] `candidate_selection` 的创业板观察块不再依赖普通 renderer 黑盒，可由节点 builder 独立输出
- [x] `risk_review` 的创业板观察池不再依赖普通 renderer 黑盒，可由节点 builder 独立输出
- [x] replay 产物验证：不重复空仓结论，不写草稿概念说明
