# Daily Snapshot Visual Analysis UI Design

> Scope: 为 `a-daily-report` 新增一个本地可视化分析界面，用来查看每日快照、主线成交额占比趋势，以及观察池标的的每日 K 线和成交量。

## Decision

采用 **Nuxt 4 + Nuxt UI + ECharts**。不使用 Next。

- Nuxt 4 负责页面、路由和本地 `server/api` 数据适配。
- Nuxt UI 负责基础控件，但主题、密度、图表容器和状态色全部定制。
- Reka UI 只在 Nuxt UI 默认交互不够贴合时补充 headless primitive。
- ECharts 负责主线 smooth line、K 线和成交量图。

## Repository Placement

The UI project should live inside this skill checkout, but it should not be tracked by the `a-daily-report` git repository.

Planned local folder:

- `snapshot-visual-analysis-ui/`

This folder is ignored from the root `.gitignore` so the UI can later become its own independent git repository. The daily-report repository should only track the design/spec documents and any data contract helpers that belong to the skill itself.

When implementation starts:

- Scaffold the Nuxt app inside `snapshot-visual-analysis-ui/`.
- Keep its `package.json`, lockfile, source files, and build outputs inside that folder.
- Initialize a separate git repository there when the UI project is ready to be versioned independently.
- Do not add the folder as a submodule unless explicitly requested later.

## Product Narrative

这个界面不是营销页，也不是暗色大屏，而是一张清爽的每日复盘工作台。

- Setting: 白色桌面上的交易研究面板，信息密集但不压迫。
- Protagonist: 每天打开快照复盘的人，先判断主线，再看个股。
- Conflict: 日报文本长、快照字段分散、主线资金与观察池标的之间缺少直观连接。
- Resolution: 第一屏先显示主线成交额与占比是否继续成立，再让用户点击观察池标的查看 K 线和成交量。

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

- 微信绿只用于选中态、主线有效、筛选激活、可继续观察等 UI 状态。
- A 股涨跌色仍按市场习惯处理：红涨、绿跌。
- 避免紫色 SaaS、霓虹科技大屏、重阴影卡片堆砌。
- 页面分区使用细线、浅灰底、紧凑留白；卡片圆角不超过 8px。

## Primary Layout

采用用户已确认的 **A 方案：主线资金优先的分析台**。

### Top Toolbar

一条薄白色工具栏，固定在页面顶部。

Controls:

- Date picker: 当前快照日期。
- Snapshot mode: 官方快照 / replay 快照。
- Range switch: 近 5 日 / 近 10 日 / 全部可用快照。
- Pool filter: 全部 / 主线核心 / 主线备选 / 跨线观察 / 普通观察。
- Refresh button: 重新读取本地快照索引。

### Mainline Funding Panel

第一屏最大区域，约占视口高度 55%-60%。

Required chart:

- Title: `主线成交额占比`
- ECharts smooth line, all line series use `smooth: true`.
- Left axis:
  - `主线成交额`
  - `两市成交额`
- Right axis:
  - `主线成交额占比`

Series styling:

- 主线成交额: WeChat green.
- 两市成交额: neutral grey-blue.
- 主线成交额占比: deep green, visually strongest.
- Optional soft area under share line, low opacity only.

Compact metrics above chart:

- 当前主线
- 次强线 / 竞争线
- 当前占比
- 占比变化
- 主线状态

### Mainline State Strip

放在主图下方，用一行紧凑指标解释图形。

Fields:

- 周期主线
- 当天主攻线
- 两者关系
- 明日动作
- 数据状态

The strip should be scannable. It must not repeat long report prose.

### Observation Pool Workspace

放在第一屏下半段或主图下方，初版不做抽屉优先。

Left side: pool list

- Group by source pool.
- First-class groups:
  - 主线核心
  - 主线备选
  - 跨线观察
  - 普通观察
- Each row shows:
  - Stock name and code
  - Source pool
  - Current action
  - Lightweight status marker

Right side: selected stock chart

- ECharts candlestick chart.
- Volume bar chart below K line.
- Shared tooltip and axis pointer.
- Data zoom enabled.
- Header fields:
  - 观察锚点
  - 容忍带
  - 失真线
  - 当前处理

## Data Sources

### Snapshot Files

The UI reads local snapshot data through Nuxt server APIs, not directly in the browser.

Primary directories:

- `snapshots/*.json`
- `snapshots/replay/*_replay.json`
- `reports/replay/*.md` only for optional links or source provenance, not for chart parsing in the first version.

### Mainline Series Contract

The adapter scans available snapshots and builds a normalized daily series.

Preferred fields:

- `data.current_sector_turnover_snapshot.date`
- `data.current_sector_turnover_snapshot.sector_name`
- `data.current_sector_turnover_snapshot.sector_turnover`
- `data.current_sector_turnover_snapshot.total_turnover`
- `data.current_sector_turnover_snapshot.turnover_share_pct`
- `data.current_sector_turnover_snapshot.source_status`
- `data.current_mainline_history_record.primary_mainline`
- `data.current_mainline_history_record.secondary_mainline`
- `data.current_mainline_history_record.competition_mainline`
- `data.current_mainline_history_record.state_code`
- `data.mainline_turnover_summary.turnover_share_trend_rows`

If a snapshot only has `mainline_turnover_summary.turnover_share_trend_rows`, the adapter can parse the row values as fallback. The normalized API should expose numeric values whenever possible.

### Observation Pool Contract

The first version uses the snapshot appendix as the user-facing observation pool:

- `data.appendix_c.current_stock_monitoring_pool`
- `data.appendix_c.stock_lifecycle_records`
- `data.appendix_c.a_kill_elimination_records`

For deeper monitoring-pool data, the adapter should also recognize:

- `performance_summary.monitoring_pool.main_pool`
- `performance_summary.monitoring_pool.secondary_pool`
- Upstream pool source fields:
  - `core_stocks`
  - `secondary_stocks`
  - `crossline_observation_stocks`
  - `gem_observation_stocks`
  - `generic_watch_stocks`

Pool source resolution:

- `主线核心` and `主线备选` map to main pool.
- `跨线观察`, `20cm 侧翼观察`, and `普通观察` map to secondary pool.
- Dedupe by normalized stock code.

### K Line Data

Initial implementation can use existing Python-generated rows when available:

- `entry_cycle_calibration.cases[].day_rows`
- `monitoring_pool.*[].monitoring_rows`
- `appendix_c.stock_lifecycle_records` for summary fields

If no rows are present for the selected stock, the API should return an empty chart state with a clear data-status message. The UI must not fabricate K-line data.

Future enhancement:

- Add a server-side bridge that calls existing Python helpers such as `market_data.daily_price_runtime.fetch_daily_price_bars`.

## API Shape

Suggested Nuxt server endpoints:

- `GET /api/snapshots`
  - Lists available snapshot dates and modes.
- `GET /api/snapshots/:date/overview?mode=frozen|replay`
  - Returns mainline state, current sector turnover snapshot, and normalized status.
- `GET /api/mainline-series?from=&to=&mode=auto`
  - Returns the smooth-line chart series.
- `GET /api/observation-pool?date=&mode=`
  - Returns grouped pool rows and lifecycle summaries.
- `GET /api/observation-pool/:code/kline?date=&mode=`
  - Returns K-line and volume rows for the selected stock.

All endpoints should return structured JSON and explicit source status. Do not return markdown blobs to the UI.

## Component Model

Top-level page:

- `pages/index.vue`

Layout components:

- `SnapshotToolbar.vue`
- `MainlineFundingPanel.vue`
- `MainlineStateStrip.vue`
- `ObservationPoolWorkspace.vue`

Chart components:

- `SmoothLineChart.vue`
- `StockKlineVolumeChart.vue`

Data components:

- `PoolGroupList.vue`
- `PoolStockRow.vue`
- `MetricPill.vue`
- `DataStatusBadge.vue`

Nuxt UI usage:

- Button, Select, Tabs, Popover, Tooltip, Badge, Skeleton, Modal/Drawer if needed.

Reka usage:

- Only for custom segmented controls or focus-heavy interactions that Nuxt UI cannot style cleanly.

## Interaction Rules

- Changing date updates mainline overview and observation pool together.
- Changing date range updates only the mainline funding chart.
- Selecting a pool row updates the K-line panel without navigating away.
- Pool filter changes the visible row set but preserves selected stock when possible.
- Empty data states are explicit: `暂无 K 线数据`, `快照缺少成交额字段`, or `该日期无观察池`.
- Loading states use skeletons; no spinner-only blocking screen.

## Motion

Motion should clarify state changes and stay restrained.

- Toolbar controls use quick press scale only.
- Chart swaps fade and translate slightly; no bouncing.
- Pool row selection uses a subtle green left rail.
- Respect `prefers-reduced-motion`.
- Avoid layout-shifting animations; animate `transform` and `opacity`.

## Error Handling

Required states:

- Snapshot directory unavailable.
- Date exists but requested mode is missing.
- Mainline turnover fields missing.
- Observation pool empty.
- K-line rows unavailable for selected stock.
- Invalid stock code in URL or request.

Each error state should include the exact missing source field where practical.

## Security

- Server API only reads from allowed local directories under this project.
- Validate date strings as `YYYY-MM-DD`.
- Validate stock code as 6-digit A-share code.
- No `innerHTML`, `dangerouslySetInnerHTML`, `eval`, or `new Function`.
- Markdown reports are not rendered as HTML in the MVP.

## Testing

Unit tests:

- Snapshot scanner lists frozen and replay dates.
- Mainline adapter normalizes numeric turnover and share fields.
- Observation pool adapter groups and dedupes rows.
- K-line adapter returns rows when `day_rows` exist and clear empty state otherwise.

Component tests:

- Mainline chart receives all line series with `smooth: true`.
- Pool filter hides and restores groups correctly.
- Selecting a stock changes the K-line request key.

Visual verification:

- Desktop viewport: first screen shows toolbar, mainline chart, and top of observation workspace.
- Mobile viewport: toolbar wraps cleanly; observation pool becomes tabs or stacked sections.
- Check text does not overflow controls or chart headers.

## Acceptance

- The app can run locally as a Nuxt app.
- No Next dependency or scaffold is introduced.
- First screen prioritizes the mainline funding chart.
- Mainline chart includes 主线成交额, 两市成交额, 主线成交额占比, with all line series smooth.
- Observation pool reads the existing snapshot pool and groups by source pool.
- Selected pool stock shows daily K-line and volume when rows are available.
- White / grey / WeChat-green visual theme is applied consistently.
- Missing data is shown as a clear state, not as fake zeroes.

## Out Of Scope For MVP

- User login.
- Remote deployment.
- Live intraday streaming.
- Editing snapshots from the UI.
- Rendering full markdown reports inside the UI.
- AI interpretation generation inside the browser.
