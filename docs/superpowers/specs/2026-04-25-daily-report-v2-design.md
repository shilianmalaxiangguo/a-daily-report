# A Daily Report V2 Design

Date: 2026-04-25
Scope: `a-daily-report` daily markdown output redesign
Status: Proposed and user-aligned

## 1. Problem Statement

The current daily report is still too close to an internal research dump rather than a sniper-style trading brief.

Three structural problems remain:

1. The main reading path mixes conclusions, derivation process, rankings, and diagnostics, so the real decision signal is buried.
2. The report over-indexes on same-day interpretation and does not preserve enough continuity across cycles, mainline rotation, and watchlist lifecycle tracking.
3. The execution plan is too generic and does not reflect the user's real operating rhythm: default action windows around `10:00`, with tail-session exceptions only in quant-style fan-rotation environments.

The redesigned report must answer the user's actual decision questions first:

1. What needs attention tomorrow?
2. What is the market base color?
3. Which mainline matters over the current cycle?
4. Which stocks are worth watching or executing?
5. What is the expected action window and risk boundary?

Everything else must be pushed into appendices.

## 2. Goals

### Primary goals

1. Turn the daily report into a two-layer artifact:
   - Front page: sniper-style action brief
   - Appendices: evidence and continuity tracking
2. Preserve conclusion-first wording with compact, data-backed expression.
3. Replace abstract labels with readable Chinese business language.
4. Introduce continuity views for:
   - cycle/mainline evolution
   - historical mainline pool
   - stock monitoring lifecycle
5. Keep the node-based architecture and TDD migration path.

### Secondary goals

1. Make the report easier to scan in 2 minutes before market open.
2. Improve confidence by linking index structure, cycle stage, mainline rotation, and capital behavior.
3. Reduce repeated wording and draft-style concept explanation.

## 3. Non-Goals

1. Do not remove inference ability or diagnostics from the system.
2. Do not remove evidence tables entirely; move them to appendices.
3. Do not collapse business logic into a single monolithic renderer again.
4. Do not optimize runtime performance in this spec; this design only focuses on output structure and wording.

## 4. Core Design Principles

1. The front page serves tomorrow's action, not internal self-explanation.
2. Every front-page section must answer a trading question.
3. Tables are the default presentation form when they increase density and clarity.
4. Mainline judgments must distinguish between:
   - cycle mainline
   - same-day attacking line
5. Structural interpretation must be time-aware, so cycles are shown on a calendar-like view.
6. English trading jargon must not appear in the markdown output.
7. Continuity assets must be preserved in appendices, not lost each day.

## 5. Front Page Structure

The redesigned front page contains seven sections.

### 5.1 Action Discipline

Purpose:

- Tell the user the base action stance immediately.

Format:

- One compact table.

Required fields:

- `明日结论`
- `默认节奏`
- `尾盘例外`
- `最大风险`
- `核心纪律`

### 5.2 Market Base Layer

Purpose:

- Show the market's base color before discussing sectors or stocks.

Format:

- One index table
- One market-state summary table

Required fields in the index table:

- `上证指数`
- `深证成指`
- `创业板指`
- `中证全指`
- `两市成交额`
- `涨停 / 跌停`
- `涨跌比`

Required fields in the market-state table:

- `市场状态`
- `当前盈亏比`
- `当前结构位置`
- `明日总体含义`

### 5.3 Cycle and Mainline Layer

Purpose:

- Link index structure, cycle timing, and mainline replacement into one reading chain.

Format:

- `周期日历主视图`
- `周期解读`
- `中枢与主线解读`
- `双层主线结论`
- `主线成交额占比趋势`

#### 5.3.1 Cycle Calendar Main View

Purpose:

- Show cycle evolution by weekday and date.

Rendering rule:

- Use `markdown` calendar-style table.
- Mainline names must be written as `[板块] 状态`.

Examples:

- `[电力] 主导`
- `[电力] 强化`
- `[电力] 分化`
- `[电力] 退潮`
- `[半导体] 接力`
- `[半导体] 修复`
- `[半导体] 回流`
- `[电力] 反抽 / [半导体] 偏弱`

The bracketed format is mandatory because it visually separates the mainline subject from its state label.

#### 5.3.2 Cycle Interpretation Table

Required fields:

- `周期`
- `时间段`
- `交易日数`
- `主导主线`
- `市场状态`
- `周期解读`

This table must explicitly show:

- previous cycle date range and trading-day count
- current cycle date range and trading-day count
- which line replaced which line
- whether the current line is only repairing or has entered a real attack stage

#### 5.3.3 Structure and Mainline Interpretation Table

Required fields:

- `时间段`
- `中枢区间`
- `所在位置`
- `结构状态`
- `对应主线`
- `结构解读`

Important wording rule:

- The last column must be a readable Chinese interpretation sentence.
- It must state subject, change, and current meaning.

Good example:

- `[半导体] 开始接替 [电力]，但目前只是修复接力，还没有形成稳定攻击段`

Bad example:

- `修复`
- `观察`
- `等待`

#### 5.3.4 Double-Mainline Summary

Required fields:

- `周期主线`
- `当天主攻线`
- `两者关系`
- `明日动作`

Rule:

- Execution permission is granted only from the cycle mainline side, not from cross-line pulse candidates.

#### 5.3.5 Mainline Turnover Share Trend Table

Purpose:

- Show whether the cycle mainline is really strengthening in market-share terms.

Required fields:

- `日期`
- `周期主线`
- `当天主攻线`
- `主线成交额`
- `两市成交额`
- `占比`
- `占比变化`
- `解读`

## 6. Capital Intent Layer

Purpose:

- Explain not just who is on the leaderboard, but what capital is trying to do.

Format:

- `龙虎榜资金状态`
- `资金结论`

### 6.1 龙虎榜资金状态 Table

Required dimensions:

- `资金强弱`
- `资金力度`
- `资金方向`
- `资金意图`
- `风格转向`
- `事件属性`

Interpretation target:

- Is capital betting expectations?
- Is capital self-rescuing same-day positions?
- Is capital trading breaking news?
- Is capital continuing prior emotion/mainline relay?
- Is capital just rotating?

Rule:

- Do not dump raw news titles into the front page.
- Only keep the event-property judgment when it changes capital interpretation.

### 6.2 Capital Summary Table

Required fields:

- `当前资金状态`
- `对主线的态度`
- `对明日动作的含义`

## 7. Stock Interpretation Layer

Purpose:

- Narrow the execution field to as few names as possible.

Format:

- `主线内可执行候选`
- `跨线观察候选`
- `个股结论`

### 7.1 Mainline Execution Candidates

Required fields:

- `股票`
- `代码`
- `所属方向`
- `为什么看`
- `明天重点看什么`
- `执行权`

Rules:

1. Keep the list minimal.
2. Only include names that may really enter the execution window.
3. Do not include hidden comment-block tables.

### 7.2 Cross-Line Observation Candidates

Required fields:

- `股票`
- `代码`
- `所属方向`
- `观察意义`
- `明日原则`

Rules:

1. These names are only for energy migration observation.
2. They must not carry implicit buy instructions.

### 7.3 Stock Summary Table

Required fields:

- `主线内唯一重点`
- `跨线对象定位`
- `动作原则`

## 8. Execution Plan Layer

Purpose:

- Reflect the user's real execution rhythm.

Format:

- One time-plan table.

Required windows:

- `09:25-09:40`
- `09:50-10:10`
- `10:00左右` for sell handling
- `10:00左右` for buy permission
- `午后`
- `尾盘`

Business rule:

1. Default buy/sell rhythm is around `10:00`.
2. Tail-session new entries are exceptions, not standard behavior.
3. Tail-session entries are only opened for quant-style fast rotation markets.

## 9. Final Summary Table

Purpose:

- Compress the whole front page into one final checkpoint.

Required fields:

- `明日结论`
- `当前盈亏比`
- `周期主线`
- `当天主攻线`
- `当前市场底色`
- `唯一重点对象`
- `明日执行风格`
- `一句话动作`

## 10. Appendix Design

The appendices preserve continuity and evidence but must not crowd the front page.

### Appendix A: Market Evidence

Modules:

- `热度榜`
- `成交额榜`
- `情绪数据`
- `资金流`

### Appendix B: Mainline Tracking

#### B1. 历史主线池

Required fields:

- `主线`
- `周期`
- `当前状态`
- `最近变化`
- `当前处理`

#### B2. 主线切换记录

Required fields:

- `日期`
- `原主线`
- `新主线`
- `切换状态`
- `解读`

#### B3. 主线成交额占比完整历史

Required fields:

- `日期`
- `周期主线`
- `主线成交额`
- `两市成交额`
- `占比`
- `状态`

#### B4. 中枢对应主线记录

Required fields:

- `时间段`
- `中枢区间`
- `对应主线`
- `主线状态`
- `解读`

### Appendix C: Stock Tracking

#### C1. 当前个股观察监控池

Required fields:

- `股票`
- `所属方向`
- `之前定位`
- `当前状态`
- `最近变化`
- `当前处理`

#### C2. 观察对象生命周期表

Purpose:

- Solve the mismatch between observation cycle and entry cycle.

Required fields:

- `股票`
- `首次进入日报日期`
- `来自哪天日报`
- `已跟踪交易日数`
- `所属主线`
- `当前状态`
- `次日至今每日涨幅`
- `次日至今量能变化`
- `次日至今累计涨幅`
- `当前解读`
- `当前处理`

State examples:

- `新进入观察`
- `继续观察`
- `震荡整理`
- `整理后转强`
- `偏弱待定`
- `转弱降级`
- `A杀淘汰`
- `结束跟踪`

#### C3. A杀淘汰记录

Required fields:

- `股票`
- `淘汰日期`
- `淘汰原因`
- `淘汰前累计涨跌幅`

Rule:

- Once a stock is classified as `A杀淘汰`, it leaves the active lifecycle table and moves to the elimination log.

#### C4. 放量异常明细

#### C5. 龙虎榜个股明细

### Appendix D: System Logs

Modules:

- `node日志`
- `快照`
- `数据状态`
- `调试信息`

## 11. Wording Rules

1. No English trading jargon in the report.
2. No formula exposition in the front page.
3. No draft-style concept explanation.
4. Repeated no-trade conclusions must be deduplicated.
5. Front-page conclusions must be data-backed but not process-heavy.

Examples of forbidden front-page wording:

- `act right`
- `setup`
- `probe`
- `follow through`

Replace with Chinese business language such as:

- `走势符合强势标准`
- `形态条件`
- `优先观察对象`
- `延续承接`

## 12. Migration Strategy

The redesign should be implemented in nodeized increments.

Suggested implementation order:

1. Replace current front page shell with new section layout.
2. Add cycle calendar view and cycle interpretation contracts.
3. Replace old mainline section with double-mainline + turnover-share tables.
4. Replace LHB rendering with capital-intent tables.
5. Move ranking-heavy content to appendices.
6. Add historical mainline pool appendix.
7. Add stock lifecycle appendix and elimination log.
8. Keep old interfaces compatible during transition.

## 13. Acceptance Criteria

The redesign is considered complete when all of the following are true:

1. The front page can be read in roughly two minutes.
2. The user can answer from the front page:
   - whether tomorrow is tradable
   - what the market base color is
   - what the cycle mainline is
   - whether same-day attack agrees with the cycle mainline
   - which stock is the single most important watch/execution object
   - when default action windows occur
3. Mainline turnover share appears on the front page as a formal table.
4. Cycle timing is visible through a calendar-like view.
5. Historical mainline pool and stock lifecycle tracking exist in appendices.
6. No hidden comment-only execution tables remain.
7. No English trading jargon appears in the rendered daily report.

## 11. Final Front Page Sketch

This section is the canonical visual target. Implementation and tests must match this front-page shape before claiming the redesign is complete. Earlier sections define fields and rules; this sketch defines the reader-facing order and markdown effect.

```markdown
# YYYY-MM-DD a股市场分析

## 一、交易纪律
| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |
|----------|----------|----------|----------|----------|
| 空仓 / 轻仓观察 / 只做主线确认 | 09:50-10:10确认，10:00左右处理买卖 | 仅量化电风扇行情允许尾盘试错，次日高开兑现 | 单笔最晚-5%，不能大亏 | 先看市场底色，再看周期主线，只在主线个股上做小亏小赚偶尔大赚 |

## 二、市场基底
### 1. 指数与市场底色
| 指标 | 数值 | 涨跌幅 | 解读 |
|------|------|--------|------|
| 上证指数 | - | - | - |
| 深证成指 | - | - | - |
| 创业板指 | - | - | - |
| 中证全指 | - | - | - |
| 两市成交额 | - | - | 放量 / 缩量 / 量能不差但赚钱效应不足 |
| 涨停 / 跌停 | - / - | - | 情绪强弱 |
| 涨跌比 | - / - | - | 市场底色 |

### 2. 市场状态结论
| 项目 | 结论 |
|------|------|
| 市场状态 | 收缩防守 / 修复试探 / 主线攻击 / 电风扇轮动 |
| 当前盈亏比 | 不值得主动参与 / 只适合小仓试错 / 主线内有正盈亏比 |
| 当前结构位置 | 日线中枢内 / 中枢上沿 / 中枢突破 / 中枢跌破 / 修复段 |
| 市场贴合度 | 贴合 / 池子偏窄 / 主线偏差 / 数据不足 |
| 明日总体含义 | 先防守 / 等10点确认 / 只做主线核心 / 尾盘例外 |

## 三、周期与主线
### 1. 周期日历主视图
| 周次 | 一 | 二 | 三 | 四 | 五 |
|------|---|---|---|---|---|
| 上个周期 | [电力] 主导 | [电力] 强化 | [电力] 分化 | [电力] 退潮 | [电力] 退出中心 |
| 当前周期 | [半导体] 接力 | [半导体] 修复 | [半导体] 回流 | [半导体] 分歧 | [半导体] 待确认 |

### 2. 周期解读
| 周期 | 时间段 | 交易日数 | 主导主线 | 市场状态 | 周期解读 |
|------|--------|----------|----------|----------|----------|
| 上个周期 | YYYY-MM-DD ~ YYYY-MM-DD | N日 | 电力 | 强化后退潮 | [电力] 上个周期主导市场，但后半段退潮，主导能力减弱 |
| 当前周期 | YYYY-MM-DD ~ 今日 | N日 | 半导体 | 修复接力中 | [半导体] 开始接替 [电力]，但当前仍是修复接力，尚未形成稳定攻击段 |

### 3. 中枢与主线解读
| 时间段 | 中枢区间 | 所在位置 | 结构状态 | 对应主线 | 结构解读 |
|--------|----------|----------|----------|----------|----------|
| YYYY-MM-DD ~ YYYY-MM-DD | 3992-4114 | 中枢上沿 | 上沿承压 | 电力 | [电力] 在中枢上沿主导市场，但承压后开始分化 |
| YYYY-MM-DD ~ 今日 | 3992-4114 | 中枢内 | 中枢内修复 | 半导体 | [半导体] 在中枢内接替 [电力]，但需要放量和承接确认才能进入攻击段 |

### 4. 双层主线结论
| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |
|----------|------------|----------|----------|
| 半导体 | 半导体 / 电池 / 专用设备 | 当天主攻线是周期主线内部加强 / 当天主攻线偏离周期主线，先按轮动观察 | 资格只从周期主线里给，跨线只观察能量迁移 |

### 5. 主线成交额占比趋势
| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |
|------|----------|------------|------------|------------|------|----------|------|
| YYYY-MM-DD | 电力 | 电力 | - | - | - | - | 上个周期主线占比状态 |
| YYYY-MM-DD | 半导体 | 半导体 | - | - | - | - | 当前周期主线占比状态 |
| 今日 | 半导体 | 半导体 / 其他 | 数据暂缺也要显示 | - | 待累计 | 待累计 | 若数据暂缺，说明缺口；若数据可用，说明强化/分化/切换 |

## 四、资金意图
### 1. 龙虎榜资金状态
| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |
|----------|----------|----------|----------|----------|----------|
| 强 / 中 / 弱 | 净买入集中度、净卖出压力 | 主线内 / 支线 / 轮动方向 | 赌预期 / 自救 / 突发消息 / 情绪接力 / 轮动试探 | 游资 / 机构 / 量化 / 混合 | 新闻驱动 / 情绪承接 / 业绩预期 / 无明显事件 |

### 2. 资金结论
| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |
|--------------|--------------|------------------|
| 资金在主线内增强 / 资金外溢轮动 / 资金自救为主 | 确认主线 / 尚未确认 / 主线分化 | 只看主线核心承接 / 等资金回主线 / 不给买入指令 |

## 五、个股解读
### 1. 主线内可执行候选
| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |
|------|------|----------|--------------|-----------|------|----------|----------|
| 富瀚微 | 300613 | 半导体 | 放量涨停 / 大阳线 | 未完全爆发 / 已爆发 | 09:50-10:10承接、60分钟确认 | 主线资金主动进攻 / 链内跟随 | 可做 / 仅观察 / 不做 |

### 2. 跨线观察候选
| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |
|------|------|----------|----------|----------|
| 某股票 | 000000 | 电池 / 其他 | 用于确认资金外溢、切换或轮动 | 只看强弱，不直接给买入指令 |

### 3. 个股结论
| 主线内唯一重点 | 跨线对象定位 | 动作原则 |
|----------------|--------------|----------|
| 富瀚微只看承接，不提前幻想 | 跨线只用于判断资金是否外溢 | 10点附近确认，买点等60分钟，买后30分钟结构止损 |

## 六、明日执行计划
| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |
|--------------|------|------|--------------|
| 只看唯一对象 | 富瀚微(300613) / 暂无 | 主线确认 + 承接 + 60分钟确认 | 不做 |

| 时间窗口 | 要看什么 | 买入权限 | 卖出/风控 | 结论 |
|----------|----------|----------|-----------|------|
| 09:25-09:40 | 竞价强弱、主线核心是否被核、跌停扩散 | 默认无 | 有旧仓先看是否需要降风险 | 不抢 |
| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 仅主线核心可进入观察买点 | 10:00左右处理弱仓/错仓 | 核心确认窗口 |
| 10:00左右卖 | 弱仓、错仓、破结构仓位 | 无 | 该卖就卖，不做自救 | 防大亏 |
| 10:00左右买 | 只看周期主线核心，且必须有承接 | 满足60分钟确认才允许 | 买后用30分钟结构止损 | 小仓或不开 |
| 午后 | 看主线是否延续，不追轮动末端 | 默认谨慎 | 若走弱继续降风险 | 不扩大试错 |
| 尾盘 | 只判断是否量化电风扇行情 | 仅电风扇行情例外，次日高开兑现 | 非电风扇不尾盘开新仓 | 例外，不是常规 |

## 七、最终结论
| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |
|----------|------------|----------|------------|--------------|--------------|--------------|------------|
| C档0% / B档30% / A-档50% / A档80%-100% | 不值得 / 一般 / 正盈亏比 | 半导体 | 半导体 / 其他 | 收缩防守 / 修复试探 / 主线攻击 | 富瀚微 / 暂无 | 仅观察 / B档条件等待 / 唯一对象执行 / 买定离手 | 10点确认，不满足就不做；绝不为了不确定性承担大亏 |
```

### 11.1 Explicit Non-Compliance Examples

The following front-page shapes are not acceptable:

- A front page that still starts from `市场研究快照` rather than the seven-section sketch above.
- A front page that keeps `Step 0` as the main execution-plan section.
- A front page that hides candidate tables in comments or only renders them in the full report but not the summary report.
- A front page that places `龙虎榜资金状态` under `周期与主线`; it must be its own `资金意图` layer.
- A front page that only says `主线更替与成交额占比` in prose but does not render the turnover-share trend table.
- A front page that omits the cycle calendar, cycle interpretation, or structure-mainline interpretation tables.
```
