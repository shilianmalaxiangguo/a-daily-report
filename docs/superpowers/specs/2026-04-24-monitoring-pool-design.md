# Monitoring Pool Design

> Scope: 为 `a-daily-report` 的策略跟踪链路新增“主监测池 / 副监测池”视图与评估逻辑，用于复盘明日标的、跨线观察与侧翼观察标的从选中日起到当前的走势质量。

## Goal

把原本只记录策略账本的结果，扩展成可持续复盘的监测池系统：
- 主监测池：只放明日标的 / 执行候选 / 核心候选
- 副监测池：放跨线观察 / 20cm 侧翼观察 / 普通观察池
- 每只票支持日度 OHLC、日涨幅、累计涨幅、交易日数、K线形态、量能、走势类型、当前状态
- 不再只给单一“关键价”，而是给观察锚点、震荡容忍带、结构失真线

## Why

现有账本更偏“建议与绩效结果”，缺少对“选出来之后走势质量”的持续复盘。用户现在需要的是：
- 明确知道某票是趋势延续、快进快出，还是震荡消耗
- 明确知道它为什么被保留、降级或淘汰
- 避免再用“跌破关键价”这种模糊句式替代真实可执行的观察框架

## Classification Model

### 1. Pattern Types

每只监测标的必须归入以下一种走势类型：

- `trend_continuation`
  - 启动后允许震荡
  - 允许盘中刺穿观察线
  - 但需要收盘修复，且后续能再突破
  - 典型：博杰股份、龙蟠科技

- `fast_in_fast_out`
  - 情绪驱动强
  - 加速快、回撤也快
  - 一旦加速断裂或放量弱收盘，要快速降级/淘汰
  - 典型：中嘉博创、津药药业

- `range_consumption`
  - 看起来没暴毙，但迟迟不能脱离震荡箱体
  - 主要问题是机会成本与注意力消耗
  - 典型：石大胜华

### 2. Price-Level Model

不再输出单一止损关键价，统一改为三层价位：

- `anchor_price`
  - 观察锚点
  - 可来自：关键涨停收盘、首次突破价、平台上沿
  - 用于看强弱变化，不等于机械止损

- `observation_band_low/high`
  - 震荡容忍带
  - 票仍在带内且可修复时，不能简单淘汰

- `failure_line`
  - 结构失真线
  - 一般需要结合收盘、量能、次日修复情况综合判断
  - 不是“盘中碰到就出局”

### 3. Day-Level Evaluation

每个交易日都需要生成一行评估，至少包含：
- `date`
- `open/high/low/close`
- `daily_change_pct`
- `cum_change_pct_from_next_day`
- `trading_days_since_selected`
- `close_position_in_range`
- `volume_state`：放量 / 缩量 / 平量
- `candle_shape`：大阳柱 / 大阴柱 / 上影阳线 / 下影阴线 / 阴线 / 阳线 / 十字 / 一字
- `day_label`：趋势 / 震荡 / 弱修复 / A杀警报

当日判断不看“盘中破没破”本身，而看：
- 最低价刺穿后收盘是否收回
- 收盘离最低价有多远
- 收盘离最高价有多远
- 是否放量
- 后续 1-2 天是否修复

## Pool Model

### 1. Main Pool

来源：
- `candidate_selection` 中真正进入执行候选 / 明日标的 / 核心候选的标的

用途：
- 用户最核心的复盘池
- 必须每天输出状态

### 2. Secondary Pool

来源：
- 跨线观察
- 20cm 侧翼观察
- 普通观察池

用途：
- 作为补充机会池
- 不与主池同权重展示

### 3. State Transitions

- `secondary -> main`
  - 持续强于主池同主题对象
  - 或出现有效再突破 / 强收盘确认

- `main -> secondary`
  - 未完全走坏，但已经不是最强
  - 或进入震荡消耗

- `main|secondary -> eliminated`
  - 结构失真
  - 或快进快出型票的最佳窗口结束

## Data Model

在现有 `strategy_tracking` 记录基础上扩展：

- `source_pool`: `main` / `secondary`
- `tracking_status`: `active` / `watch` / `eliminated`
- `pattern_type`: `trend_continuation` / `fast_in_fast_out` / `range_consumption`
- `anchor_price`
- `observation_band_low`
- `observation_band_high`
- `failure_line`
- `selected_date`
- `days_since_selected`
- `monitoring_rows`: 日度评估列表
- `current_assessment`
- `assessment_reason`

## Rendering

在策略账本尾部追加两组内容：

1. `主监测池`
- 摘要表：标的、选中日、交易日数、累计涨幅、走势类型、当前结论
- 展开表：每只票的每日 OHLC / 形态 / 量能 / 日涨幅 / 累计涨幅

2. `副监测池`
- 结构与主池一致，但默认置后展示

## Integration Points

优先复用现有模块：
- `scripts/report/strategy_tracking_records.py`
- `scripts/report/strategy_tracking_runtime.py`
- `scripts/report/strategy_tracking_evaluation.py`
- `scripts/report/strategy_performance_renderer.py`
- `scripts/market_data/daily_price_runtime.py`

新增模块建议：
- `scripts/report/monitoring_pool_support.py`
- `scripts/report/monitoring_pool_renderer.py`

## Testing

新增/补充测试要覆盖：
- 主池 / 副池来源划分
- 趋势延续 / 快进快出 / 震荡消耗 分类
- 日度 monitoring row 计算
- 博杰股份 / 龙蟠科技 / 石大胜华 / 中嘉博创 / 津药药业 五个样本的回归断言
- renderer 输出列和顺序

## Acceptance

验收以以下结果为准：
- 博杰股份、龙蟠科技更偏 `trend_continuation`
- 中嘉博创、津药药业更偏 `fast_in_fast_out`
- 石大胜华更偏 `range_consumption`
- 主监测池与副监测池都能在报告中渲染
- 输出包含每天的 OHLC、形态、量能、日涨幅、累计涨幅、状态与原因
