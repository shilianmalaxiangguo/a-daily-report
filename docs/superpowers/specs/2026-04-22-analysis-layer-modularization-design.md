# Analysis Layer Modularization Design

## 背景

当前仓库已经完成了部分尾部 hook 化和执行链 stage 化，但 [`scripts/daily_report_entry_demo.py`](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/daily_report_entry_demo.py) 仍然承担过多“分析层大脑”职责，主要体现在：

- `get_daily_data()` 仍是单体型请求总控
- `build_mainline_exit_analysis()` 仍是单体型分析推导函数
- `generate_markdown_report()` 仍掌握较多中间态和装配职责

这会带来 4 个直接问题：

- 替换某段逻辑时容易牵一发动全身
- AI 或人工排错时需要回到入口文件阅读大量上下文
- 日志和错误定位停留在“大段逻辑”，难以落到最小单元
- 模块升级无法形成稳定规范，每次都要重新约定边界

本 spec 的目标，就是把“分析层”沉淀成一套之后可以反复复用的模块化规范。

## 目标

- 把分析层从“入口内联大函数”重构成“业务域 runtime + 可替换 infer 节点”
- 让最小可替换单元收敛到 `infer_*.py`
- 让每个模块通过统一 `contracts + module_logs` 暴露稳定插口
- 让入口层最终只保留少量 `run_*` 级装配调用
- 让 AI 和人工都可以在“不读完整入口文件”的情况下完成定位、替换和升级

## 非目标

- 本 spec 不覆盖 UI、前端或视觉表现设计
- 本 spec 不要求一次性重写所有旧逻辑
- 本 spec 不要求第一阶段就上完整插件化 registry
- 本 spec 不改变现有产出日报格式作为首要目标，兼容旧输出优先

## 设计原则

### 1. 外层按业务域，内层按推导节点

分析层采用混合式组织：

- 外层按业务域分目录
- 内层按推导职责拆成多个节点

推荐业务域：

- `market_state`
- `watch_candidates`
- `execution_chain`
- `report_shell`

### 2. 最小可替换单元是 infer 节点

后续替换、升级、修复应优先发生在 `infer_*.py`，而不是直接修改入口或 runtime。

### 3. runtime 负责装配，不负责大推理

每个业务域的 `runtime.py` 只负责：

- 收上下文
- 调用各 infer 节点
- 合并 exports
- 汇总 module logs
- 产出本域中间态

runtime 不应重新内联复杂业务判断。

### 4. contracts 是稳定边界

后续所有替换和升级，都以 `contracts.py` 为准，而不是以函数内部局部变量为准。

### 5. trace 不是附属品，而是标准层

每个域必须有明确日志契约，保证后续快速排错。

## 推荐目录规范

```text
scripts/domains/
  market_state/
    contracts.py
    runtime.py
    infer_environment_signal.py
    infer_mainline_candidates.py
    infer_mainline_continuity.py
    infer_risk_pressure.py
    infer_sector_competition.py
    assemble_exit_analysis.py
    trace.py

  watch_candidates/
    contracts.py
    runtime.py
    infer_candidate_pool.py
    infer_candidate_score.py
    infer_candidate_filter.py
    assemble_watchlist.py
    trace.py

  execution_chain/
    contracts.py
    runtime.py
    infer_permission.py
    infer_position_sizing.py
    infer_action_plan.py
    assemble_execution_context.py
    trace.py
```

补充约束：

- `contracts.py` 只定义输入输出契约、常量 key、结构说明
- `infer_*.py` 保持无状态，尽量只依赖参数
- `assemble_*.py` 只拼装，不新增复杂推理
- `trace.py` 负责本域日志构造器

## 统一上下文契约

每个 runtime 或 infer 节点统一接收如下上下文：

```python
{
  "inputs": {...},
  "state": {...},
  "helpers": {...},
  "config": {...},
}
```

定义如下：

- `inputs`
  当前节点真正需要的外部输入
- `state`
  由前置节点或上游域传来的中间态
- `helpers`
  工具函数、兼容旧 wrapper、格式化器、转换器
- `config`
  阈值、开关、策略参数、试运行模式

约束如下：

- 节点不能隐式依赖入口全局变量
- 节点不能通过副作用偷偷修改别的域数据
- 所有跨节点依赖必须显式出现在 `inputs` 或 `state`

## 统一返回契约

每个 runtime 或 infer 节点统一返回：

```python
{
  "value": {...},
  "exports": {...},
  "module_logs": [...],
  "errors": [...],
}
```

定义如下：

- `value`
  当前节点原始结果
- `exports`
  允许被下游稳定依赖的输出
- `module_logs`
  本节点日志
- `errors`
  非致命错误或降级信息

约束如下：

- `exports` 必须显式定义，不能默认把所有中间变量都向外暴露
- 下游优先依赖 `exports`，避免耦合 `value` 的内部细节
- `errors` 不等于抛异常；可恢复问题优先用结构化错误记录

## 统一日志契约

每个节点至少产出如下结构：

```python
{
  "module": "domains.market_state.infer_risk_pressure",
  "step": "infer.risk_pressure",
  "status": "success",
  "message": "已完成风险压力推导",
  "details": {
    "input_keys": ["dt_pool", "a_kill_records"],
    "output_keys": ["risk_snapshot"],
    "decision": "高位抱团风险升高"
  }
}
```

日志约束：

- `module` 必须指向具体模块
- `step` 必须是稳定标识，不能用 `step0/step1.1` 这种固定章节号
- `status` 统一使用 `success / degraded / error / skipped`
- `details` 至少包含关键输入、关键输出、关键决策摘要

## 推荐运行模型

每个业务域采用“runtime 驱动节点”的模式：

```python
def run_market_state_analysis(ctx):
    environment = infer_environment_signal.run(ctx)
    mainline = infer_mainline_candidates.run(...)
    continuity = infer_mainline_continuity.run(...)
    risk = infer_risk_pressure.run(...)
    competition = infer_sector_competition.run(...)
    exit_analysis = assemble_exit_analysis.run(...)
    return {...}
```

第一阶段不强制上 registry，但 runtime 必须具备未来升级到 registry 的条件：

- 节点顺序清晰
- 节点输入输出显式
- 节点之间无隐式共享状态

## `build_mainline_exit_analysis()` 的目标拆分

当前单体函数应被兼容式重构为：

```python
def build_mainline_exit_analysis(...):
    result = run_market_state_analysis(ctx)
    return result["exports"]["exit_analysis"]
```

`domains/market_state/` 内部推荐拆成以下节点：

### `infer_environment_signal.py`

职责：

- 判断环境开关、强弱、防守/进攻状态

输出：

- `environment_signal`

### `infer_mainline_candidates.py`

职责：

- 从热榜、板块、资金、连板、异动中找主线候选

输出：

- `mainline_candidates`

### `infer_mainline_continuity.py`

职责：

- 判断主线是否具备连续性和延续条件

输出：

- `continuity_snapshot`

### `infer_risk_pressure.py`

职责：

- 汇总跌停、A杀、高位失败样本、结构风险

输出：

- `risk_snapshot`

### `infer_sector_competition.py`

职责：

- 归纳主攻线、次强线、竞争线

输出：

- `competition_snapshot`

### `assemble_exit_analysis.py`

职责：

- 只做最终结构拼装
- 兼容旧入口和旧渲染逻辑所需格式

输出：

- `exit_analysis`

## 市场分析域的稳定 exports

```python
{
  "environment_signal": {...},
  "mainline_candidates": [...],
  "continuity_snapshot": {...},
  "risk_snapshot": {...},
  "competition_snapshot": {...},
  "exit_analysis": {...},
}
```

后续要求：

- 下游尽量消费这些稳定 exports
- 旧逻辑迁移期允许 wrapper 消费旧格式，但新模块不得继续扩大旧格式依赖

## 迁移策略

### 第一阶段：兼容式迁移

- 保留旧入口函数名
- 内部改调 domain runtime
- 对外仍返回旧数据结构

### 第二阶段：压缩入口

- 让入口只保留 `run_*` 级装配调用
- 把大多数中间态搬入 domain runtime

### 第三阶段：准 registry 化

- 把 runtime 内固定顺序节点逐步升级为可配置顺序
- 但仍保持同一 exports 契约

## 推荐实施顺序

1. 先重构 `build_mainline_exit_analysis()` 所属的 `market_state` 域
2. 再重构 `watch_candidates`
3. 再重构 `execution_chain` 中仍残留在入口内的判断逻辑
4. 最后继续压缩 `generate_markdown_report()` 和 `get_daily_data()`

## 验证要求

每拆一个业务域，至少满足以下验证：

- 该域新增单元测试覆盖核心 infer 节点
- 旧入口 wrapper 行为保持兼容
- `module_logs` 可定位到具体节点
- 旧输出结构不因域内重构而破坏

## 成功标准

满足以下条件可视为分析层规范落地成功：

- 新增分析逻辑优先写入某个域的 `infer_*.py`
- 入口文件不再继续膨胀承载新推导逻辑
- 任意一个分析问题都能定位到“哪个域、哪个节点、哪条 exports”
- 替换某个判断逻辑时，不需要同步重写整个入口文件
- AI 可以仅基于该域 contracts 和 tests 完成局部修改

## 决策结论

本仓库分析层后续统一采用：

- 外层按业务域
- 内层按推导节点
- runtime 负责装配
- infer 节点负责最小推理单元
- contracts 负责稳定边界
- trace 负责结构化日志

这份 spec 作为后续拆解 `daily_report_entry_demo.py`、迁移分析逻辑、统一日志和契约的正式规范。
