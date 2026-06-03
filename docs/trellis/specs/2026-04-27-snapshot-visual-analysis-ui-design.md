# Daily Snapshot Visual Analysis UI Design

> Scope: 为 `a-daily-report` 新增一个本地可视化分析界面。新的根目标不是普通复盘 dashboard，而是把 **日线中枢结构、结构区间、大小主线、主线成交额、观察池个股** 放到同一张分析台里。

## Revision

This spec supersedes the earlier "mainline funding first" version and also supersedes the current implementation plan at `docs/trellis/plans/2026-04-27-snapshot-visual-analysis-ui-implementation-plan.md`.

The required first screen is now:

1. **中枢 K 线图**
2. **中枢范围矩形框**
3. **中枢周期 / ZG / ZD**
4. **这段中枢的大主线 / 小主线**

`主线成交额占比` and `观察池 K 线` remain important, but they are supporting layers under the central zhongshu view.

Non-negotiable product rule: if the first screen cannot answer **“指数现在处在哪个日线中枢、这个中枢的 ZG/ZD 是什么、这段结构的大主线和小主线是谁”**, the UI is considered incomplete even if all other charts render.

## Decision

采用 **Nuxt 4 + Nuxt UI + ECharts**。不使用 Next。

- Nuxt 4 负责页面、路由和本地 `server/api` 数据适配。
- Nuxt UI 负责基础控件，但主题、密度、图表容器和状态色全部定制。
- Reka UI 只在 Nuxt UI 默认交互不够贴合时补充 headless primitive。
- ECharts 负责中枢 K 线、矩形框、成交额 smooth line、个股 K 线和成交量图。
- 中枢矩形框优先使用 ECharts `markArea` 或 `custom series`，必须能按日期区间和价格区间精确落位。

## Repository Placement

The UI project lives inside this skill checkout, but it is not tracked by the `a-daily-report` git repository.

Planned local folder:

- `snap-ui/`

This folder is ignored from the root `.gitignore` so the UI can later become its own independent git repository. The daily-report repository should only track design/spec documents and any data contract helpers that belong to the skill itself.

## Product Narrative

这个界面是一张 **中枢结构复盘台**。

- Setting: 白色桌面上的交易研究面板，像一张干净的结构图纸。
- Protagonist: 每天用“日线中枢定环境、60 分钟定买点、30 分钟定止损”的交易者。
- Conflict: 当前日报能说出中枢和主线，但读者不能一眼在 K 线上看到“价格在哪个中枢里、这个中枢承载哪条大主线和小主线”。
- Resolution: 第一屏直接画出指数 K 线和中枢矩形框；每个框上标注时间段、ZG/ZD、大主线、小主线，再用成交额和观察池做侧证。

The decision chain is fixed:

1. `日线中枢` determines environment.
2. `大主线 / 小主线` explains who is carrying that environment.
3. `主线成交额占比` validates whether the line has real market energy.
4. `观察池 K 线` turns the environment into executable objects.

## Visual Direction

采用清爽的 **微信绿 + 白色 + 灰色** 主题。

Core palette:

- Page background: `#F7F8F7`
- Panel background: `#FFFFFF`
- Border / grid: `#E6E8E6`
- Primary text: `#1F2A24`
- Secondary text: `#6B756E`
- WeChat green: `#07C160`
- Deep green: `#128C45`
- Risk red: `#D64545`
- Warning amber: `#B98218`

Rules:

- 微信绿用于选中态、当前中枢、主线确认、可继续观察。
- A 股涨跌色仍按习惯处理：红涨、绿跌。
- 中枢矩形框用浅绿透明填充，边框用深绿；历史中枢用浅灰框。
- 跌破、失效、A 杀相关状态用风险红，不用微信绿表达风险。
- 不做暗色大屏、霓虹科技风、紫色 SaaS、厚重卡片堆砌。

## Primary Layout

采用新的 **Z 方案：中枢结构优先的分析台**。

### Top Toolbar

一条薄白色工具栏，固定在页面顶部。

Controls:

- Date picker: 当前快照日期。
- Snapshot mode: 官方快照 / replay 快照。
- Index selector: 上证指数 / 深证成指 / 创业板指 / 自定义指数，MVP 默认上证指数。
- Range switch: 近 60 日 / 近 120 日 / 全部可用结构。
- Layer toggles:
  - 中枢框
  - 主线标签
  - 成交额占比
  - 观察池
- Refresh button: 重新读取本地快照索引。

### Zhongshu Structure Panel

第一屏最大区域，约占视口高度 60%-70%。这是页面根模块。

This panel is P0. It must be built before any secondary chart work continues.

Required chart:

- Title: `日线中枢结构`
- ECharts candlestick chart.
- Below K-line: volume bar.
- Shared tooltip and axis pointer.
- Data zoom enabled.
- 中枢区间用矩形框覆盖在 K 线上：
  - X range: `start_date` to `end_date`
  - Y range: `zd` to `zg`
  - label: `中枢周期 + ZG/ZD + 大主线 + 小主线`
- 今日收盘价必须显示为 marker 或 horizontal reference.
- 当前中枢高亮；历史中枢弱化；尾部过渡结构用虚线框或虚线连接段。

Required label contents per zhongshu rectangle:

- `中枢周期`: `start_date ~ end_date`
- `中枢高`: `ZG`
- `中枢低`: `ZD`
- `大主线`: big mainline for this structure
- `小主线`: small mainline / daily attack line for this structure
- `结构状态`: 中枢内 / 上沿承压 / 突破中枢 / 跌破中枢 / 过渡结构

The label should be visible without requiring hover for the current zhongshu. Historical labels may collapse and expand on hover.

The current zhongshu label must not be replaced by a generic tooltip-only interaction. The trader should be able to take a screenshot of the first screen and still see the current structure range, ZG/ZD, and big/small mainline.

### Zhongshu Detail Strip

放在中枢 K 线图下方，解释当前结构，不重复长篇日报。

Fields:

- 当前结构状态
- 中枢周期
- ZG / ZD
- 今日收盘
- 相对 ZG
- 相对 ZD
- 大主线
- 小主线
- 明日结构含义

This strip answers: **价格在哪个结构里、谁是这段结构的主线、明天结构上先看什么。**

### Mainline Funding Panel

作为第二层侧证，而不是第一屏主轴。

Required chart:

- Title: `主线成交额占比`
- ECharts smooth line, all line series use `smooth: true`.
- Left axis:
  - `主线成交额`
  - `两市成交额`
- Right axis:
  - `主线成交额占比`

Purpose:

- Validate whether the mainline attached to the zhongshu is supported by turnover share.
- Show whether big/small mainline alignment is strengthening or diverging.

### Observation Pool Workspace

作为第三层：结构给环境，观察池给执行对象。

Left side: pool list

- 主线核心
- 主线备选
- 跨线观察
- 普通观察

Right side: selected stock chart

- ECharts candlestick chart.
- Volume bar below K-line.
- Header fields:
  - 观察锚点
  - 容忍带
  - 失真线
  - 当前处理

Observation pool must be visually linked back to zhongshu:

- If a stock belongs to the big mainline or small mainline shown on the current zhongshu, mark it with a green rail.
- If it is crossline only, mark it grey and do not visually imply same priority.

## Data Contracts

### Snapshot Files

The UI reads local snapshot data through Nuxt server APIs, not directly in the browser.

Primary directories:

- `snapshots/*.json`
- `snapshots/replay/*_replay.json`
- `reports/replay/*.md` only for optional provenance links, not chart parsing in MVP.

### Zhongshu Structure Contract

The UI needs a normalized zhongshu structure payload.

Preferred source:

- `market_zhongshu` from report runtime / phase context when present.

Known upstream fields:

- `market_zhongshu.success`
- `market_zhongshu.zhongshu_list[]`
- `market_zhongshu.current_zhongshu`
- `market_zhongshu.structure_segments[]`
- `market_zhongshu.latest_structure_segment`
- `market_zhongshu.today_price`
- `market_zhongshu.today_date`
- `market_zhongshu.signal.status`
- `market_zhongshu.signal.signal_type`
- `market_zhongshu.signal.comparison_state`
- `market_zhongshu.signal.zg`
- `market_zhongshu.signal.zd`
- `market_zhongshu.signal.dist_to_zg`
- `market_zhongshu.signal.dist_to_zd`

Each normalized zhongshu zone must expose:

- `id`
- `startDate`
- `endDate`
- `zg`
- `zd`
- `klineCount`
- `segmentType`: `zhongshu` / `connector`
- `connectorRole`: `leading` / `between` / `trailing` / empty
- `isCurrent`
- `isLatest`
- `structureState`
- `bigMainline`
- `smallMainline`
- `mainlineDegree`
- `evolution`
- `replacement`
- `interpretation`
- `sourceStatus`

The K-line chart also needs index K-line rows:

- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`

If existing snapshots do not contain these rows, the implementation must add a parent-repo data helper that exports zhongshu visual data from existing Python logic. It must not fabricate K-line rows.

Suggested parent helper:

- `scripts/export/zhongshu_visual_snapshot.py`

Suggested helper behavior:

- call or reuse `scripts/decision/zhongshu_runtime.py`
- output normalized JSON with K-line rows, zhongshu zones, signal, and source diagnostics
- support `--date YYYY-MM-DD`
- support `--index-code sh000001` or equivalent default

### Mainline Mapping Contract

The zhongshu rectangles must carry big/small mainline labels.

Preferred sources:

- `market_research_snapshot.pivot_mainline_rows`
- `market_research_snapshot.pivot_mainline_history`
- `appendix_b.structure_mainline_records`
- `current_mainline_history_record`
- `mainline_turnover_summary.double_mainline_summary`

Known row fields:

- `date_range`
- `pivot_level`
- `pivot_range`
- `position`
- `mainline`
- `mainline_degree`
- `evolution`
- `replacement`
- `interpretation`

Mapping rules:

- `bigMainline` comes from rows whose `mainline_degree` contains `大主线`, or whose `pivot_level` is a daily / large / cycle zhongshu. If no explicit row exists, use `current_mainline_history_record.primary_mainline`.
- `smallMainline` comes from rows whose `mainline_degree` contains `小主线`, or from `mainline_turnover_summary.double_mainline_summary.daily_attack_line`.
- If only one line is known, show `大主线: <name>` and `小主线: 待确认`; do not copy the big line into the small line unless the source explicitly says they are the same.
- If a zhongshu range lacks a mapped mainline, show a missing-data badge on that rectangle.

### Mainline Series Contract

The adapter scans available snapshots and builds a normalized daily series.

Preferred fields:

- `data.current_sector_turnover_snapshot.date`
- `data.current_sector_turnover_snapshot.sector_name`
- `data.current_sector_turnover_snapshot.sector_turnover`
- `data.current_sector_turnover_snapshot.total_turnover`
- `data.current_sector_turnover_snapshot.turnover_share_pct`
- `data.current_mainline_history_record.primary_mainline`
- `data.mainline_turnover_summary.turnover_share_trend_rows`

### Observation Pool Contract

The first version uses:

- `data.appendix_c.current_stock_monitoring_pool`
- `data.appendix_c.stock_lifecycle_records`
- `data.appendix_c.a_kill_elimination_records`

For deeper monitoring-pool data, the adapter should also recognize:

- `performance_summary.monitoring_pool.main_pool`
- `performance_summary.monitoring_pool.secondary_pool`
- `core_stocks`
- `secondary_stocks`
- `crossline_observation_stocks`
- `gem_observation_stocks`
- `generic_watch_stocks`

## API Shape

Suggested Nuxt server endpoints:

- `GET /api/snapshots`
  - Lists available snapshot dates and modes.
- `GET /api/zhongshu-structure?date=&mode=&index=`
  - Returns K-line rows, zhongshu rectangles, signal, and big/small mainline mapping.
- `GET /api/mainline-series?from=&to=&mode=auto`
  - Returns the smooth-line chart series.
- `GET /api/observation-pool?date=&mode=`
  - Returns grouped pool rows and lifecycle summaries.
- `GET /api/observation-pool/:code/kline?date=&mode=`
  - Returns K-line and volume rows for selected stock.

All endpoints return structured JSON and explicit source status. Do not return markdown blobs to the UI.

## Component Model

Top-level page:

- `pages/index.vue`

Layout components:

- `SnapshotToolbar.vue`
- `ZhongshuStructurePanel.vue`
- `ZhongshuDetailStrip.vue`
- `MainlineFundingPanel.vue`
- `ObservationPoolWorkspace.vue`

Chart components:

- `ZhongshuKlineChart.vue`
- `SmoothLineChart.vue`
- `StockKlineVolumeChart.vue`

Data components:

- `ZhongshuZoneLegend.vue`
- `ZhongshuMainlineBadge.vue`
- `PoolGroupList.vue`
- `PoolStockRow.vue`
- `MetricPill.vue`
- `DataStatusBadge.vue`

Pure builders:

- `buildZhongshuKlineOptions(rows, zones, options)`
- `buildMainlineOptions(rows)`
- `buildStockKlineOptions(rows)`

## Interaction Rules

- Changing date updates zhongshu structure, mainline series, and observation pool together.
- Selecting a zhongshu rectangle highlights its time range and updates detail strip.
- Hovering a rectangle shows `周期 / ZG / ZD / 大主线 / 小主线 / 状态`.
- Layer toggles can hide/show zhongshu boxes, labels, and turnover share.
- Selecting a pool row updates the stock K-line panel without navigating away.
- Empty data states are explicit:
  - `暂无中枢 K 线数据`
  - `快照缺少 market_zhongshu`
  - `中枢缺少主线映射`
  - `暂无 K 线数据`
- Missing data must never render fake zeroes or fake rectangles.

## Motion

Motion should clarify state changes and stay restrained.

- Switching date fades the chart content and preserves panel geometry.
- Selecting a zhongshu rectangle uses a subtle border-strength transition.
- Pool row selection uses a subtle green left rail.
- Respect `prefers-reduced-motion`.
- Avoid layout-shifting animation; animate only `transform` and `opacity`.

## Error Handling

Required states:

- Snapshot directory unavailable.
- Date exists but requested mode is missing.
- Zhongshu analysis is missing or failed.
- K-line rows unavailable for index.
- Zhongshu range exists but lacks `zg` or `zd`.
- Mainline mapping missing for a zhongshu range.
- Observation pool empty.
- Selected stock K-line unavailable.

Each error state should include the exact missing source field where practical.

## Security

- Server API only reads from allowed local directories under this project.
- Validate date strings as `YYYY-MM-DD`.
- Validate index and stock codes.
- If a Nuxt endpoint calls a Python helper, pass arguments as an argv array, never by shell interpolation.
- No `innerHTML`, `dangerouslySetInnerHTML`, `eval`, or `new Function`.
- Markdown reports are not rendered as HTML in MVP.

## Testing

Unit tests:

- Snapshot scanner lists frozen and replay dates.
- Zhongshu adapter normalizes `market_zhongshu` into K-line rows, zones, and signal.
- Zhongshu adapter rejects missing `zg/zd` with a clear source status.
- Mainline mapper resolves big/small mainline separately and does not duplicate big into small unless explicitly sourced.
- ECharts option builder creates rectangle overlays whose X/Y ranges match zhongshu `startDate/endDate/zd/zg`.
- Mainline adapter keeps all line series `smooth: true`.
- Observation pool adapter groups and dedupes rows.

Component tests:

- Zhongshu chart receives K-line rows and zone overlays.
- Current zhongshu label is visible without hover.
- Layer toggles hide/show labels and boxes.
- Selecting a zhongshu zone updates the detail strip.
- Selecting a stock changes the K-line request key.

Visual verification:

- Desktop viewport: first screen shows toolbar, zhongshu K-line chart, current zhongshu rectangle, and detail strip.
- Mobile viewport: zhongshu chart remains first; labels collapse cleanly.
- Text does not overflow chart labels, badges, or toolbar controls.

## Acceptance

- The app can run locally as a Nuxt app inside `snap-ui/`.
- No Next dependency or scaffold is introduced.
- First screen prioritizes `日线中枢结构`, not the mainline turnover chart.
- Zhongshu K-line chart renders actual K-line rows.
- Current zhongshu rectangle spans the correct date range and price range.
- Current zhongshu label shows `中枢周期`, `ZG`, `ZD`, `大主线`, and `小主线`.
- Historical zhongshu boxes are visible but visually secondary.
- Mainline turnover chart remains available with smooth line series.
- Observation pool remains available and links priority to the current big/small mainline.
- White / grey / WeChat-green visual theme is applied consistently.
- Missing data is shown as clear state, not fake zeroes.

## Out Of Scope For MVP

- User login.
- Remote deployment.
- Live intraday streaming.
- Editing snapshots from the UI.
- Rendering full markdown reports inside the UI.
- AI interpretation generation inside the browser.
- Manual drag-editing of zhongshu rectangles.
