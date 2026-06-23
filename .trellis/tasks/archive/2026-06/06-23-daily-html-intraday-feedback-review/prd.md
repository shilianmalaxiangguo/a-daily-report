# 日报HTML盘面反馈复盘模块

状态：✅ 已完成（本次未提交）

## Goal

在 Bear/readable 日报 HTML 中加入“盘面反馈复盘”图表模块，把当日上证指数、当前持仓、昨日目标/今日买入对象放到同一张分时相对涨跌图里，形成可回看的盘面记录。

## User Story

- **角色**：交易复盘用户。
- **场景**：收盘后查看当日正式日报或 replay HTML。
- **目标**：直观看到市场、旧仓和新机会的分时反馈，判断旧仓是否仍有满仓资格，以及新仓是否值得切换或并行。
- **成功标准**：HTML 中出现可交互图卡，明确标注曲线、相对强弱、关键事件和账户结论；没有数据时不生成假图。

### 用户旅程

1. 用户生成或打开某日 A 股日报 HTML。
2. 系统在正文对应位置展示“盘面反馈复盘”图卡。
3. 用户查看上证、旧仓、昨日目标/今日买入对象的归一化分时曲线。
4. 用户查看相对上证强弱差和关键事件标注。
5. 用户得到 1x/2x 账户口径下的旧仓/新仓结论。

## What I Already Know

- 正式阅读 HTML 使用 `scripts/report/markdown_report_html.py` 的 Bear/readable 渲染器，不使用结构化 dashboard HTML 作为主输出。
- Bear HTML 已有 ECharts 图卡机制：`_collect_bear_chart_payload()` 解析 Markdown 表格，模板 `scripts/templates/daily_report_markdown_reader.html` 读取 `bear-chart-payload` 并渲染图卡。
- 项目已有 `scripts/market_data/minute_price_runtime.py` 和 `scripts/market_data/tushare_minute_service.py`，但 Bear 渲染器目前只消费已保存 Markdown，不应直接依赖实时数据源。
- 用户明确要求 1x/2x 不能误解成两个标的各 50%；默认是满仓/空仓模型。
- 2026-06-23 太极实业复盘图证明“分时长期弱于指数、反抽高点下移、跌破昨低/支撑”需要进入旧仓处理。

## Requirements

- [x] R1: Bear HTML 能从标准 Markdown 表格解析盘面反馈数据，并生成 ECharts 图卡。
- [x] R2: 图卡必须同时展示归一化分时涨跌曲线和相对上证强弱差。
- [x] R3: 图卡必须支持三类对象：上证指数、当前持仓、昨日目标/今日买入对象；重复代码要去重。
- [x] R4: 图卡必须支持关键事件标注，例如开盘、第一次反抽、跌破昨低、跌破支撑、尾盘。
- [x] R5: 图卡必须展示账户复盘结论，且 1x/2x 按满仓/空仓口径表达，不默认拆成两个 50%。
- [x] R6: 数据缺失时不生成假图；缺失只作为正文说明或普通表格保留。

## Non-functional Requirements

### 性能

- 图表只使用已嵌入 HTML 的 JSON payload，不在浏览器运行时请求外部数据。

### 安全

- Markdown 表格内容必须继续走现有 HTML 转义和 JSON script 转义，不能引入原始脚本注入。

### 兼容性

- 沿用现有 ECharts 加载策略：优先本地 `.generated/vendor/echarts/echarts.min.js`，缺失时使用现有 fallback。

### 可访问性

- 图卡保留 `role="img"` 和 `aria-label`，说明图表含义。

## Acceptance Criteria

- [x] AC-R1-1: 给定 Markdown 包含“盘面反馈复盘”标准表格，当渲染 Bear HTML，则 `bear-chart-payload` 包含 `intraday_feedback_review`。
- [x] AC-R2-1: 给定至少上证和一个标的的分钟点，当打开 HTML，则脚本包含 `renderIntradayFeedbackReviewChart`，并配置两段图：涨跌幅与相对上证。
- [x] AC-R3-1: 给定同一标的同时出现在持仓和今日买入对象中，payload 只保留一条曲线。
- [x] AC-R4-1: 给定事件表包含“跌破昨低”，HTML 图表配置包含 markLine 或 markPoint 标注。
- [x] AC-R5-1: 给定账户结论写明 `1x满仓二选一` 或 `2x满仓并行`，HTML 图卡脚注展示原文，不改写为 50%。
- [x] AC-R6-1: 给定 Markdown 没有有效盘面反馈表，HTML 不出现空白 ECharts 容器。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md` / `implement.md` 已补齐。
- [x] 必要测试通过。
- [x] 用户可见语言不含禁用旧工程口径。
- [x] PRD 状态改为 `✅ 已完成`；本次未提交，等待用户确认后再落 commit。

## Out Of Scope

- 不在本次第一步中重写日报生成主链路。
- 不让 Bear HTML 渲染器直接调用实时行情接口。
- 不做券商交易接入或真实下单。
- 不把 1x/2x 改写成半仓模型。

## Technical Notes

### 参考来源

- `scripts/report/markdown_report_html.py` — Bear/readable HTML Markdown 渲染与图表 payload 解析。
- `scripts/templates/daily_report_markdown_reader.html` — ECharts 图表渲染脚本和样式。
- `wiki/交易思想/实际账户情况.md` — 1x/2x 满仓/空仓账户口径。
- `wiki/交易思想/做T与风险控制.md` — 旧仓盈亏比优先规则。

### 影响区域

- `scripts/report/markdown_report_html.py` — 解析盘面反馈表并插入图卡。
- `scripts/templates/daily_report_markdown_reader.html` — 新增图表渲染函数和样式复用。
- `tests/test_daily_report_markdown_html.py` — 增加解析和渲染测试。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html`
- `git diff --check -- scripts/report/markdown_report_html.py scripts/templates/daily_report_markdown_reader.html tests/test_daily_report_markdown_html.py`
- 对改动文件和任务文档运行用户可见术语检查，确认没有旧工程口径。

## 落地 commit

本次未提交。用户未要求提交，先保留工作区改动等待确认。
