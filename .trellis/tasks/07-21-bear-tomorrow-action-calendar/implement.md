# Implementation: Bear 最近25条明日操作日历

## Prerequisites

- 用户已确认每格显示“当日涨幅”和“跑赢上证”，明日标的从数据库读取；每份标的连续参与两个交易日，每腿 `1x/50%`，个股与上证都按同日开收到收计算。
- 实现前读取 backend database / decision-loop、frontend quality、cross-layer 和术语契约。
- 工作区存在大量未提交改动；只增量修改本任务所需段落，不格式化或清理无关代码。
- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。

## Ordered Checklist

- [x] I1: 为最近 25 条台账、两交易日映射、两腿仓位、操作分类、开收收益、缺失状态和复利汇总增加失败测试。
- [x] I2: 在现有 PostgreSQL repository/service 边界增加最小历史查询能力，优先读取因子快照最终决定；不新增表，不扫描 Markdown/JSON，不为日历触发整本策略历史重写。
- [x] I3: 新增纯函数构建 `tomorrow_action_calendar.v1`，明确正式/replay 模式、数据来源、两日两腿、日期、缺失字段和复利累计跑赢上证。
- [x] I4: 在日报 HTML 入口构建载荷，并作为可选参数传给 Bear Markdown HTML 渲染器。
- [x] I5: 在顶部账户日序时间轴前渲染 5 列交易周日历与汇总；无账户时间轴时仍作为正文首块。
- [x] I6: 在现有模板增加紧凑、可访问、组件内滚动的样式；正负收益保留符号，不只靠颜色。
- [x] I7: 增加正式/replay 模式隔离、数据库缺失、未来执行日、短样本、周末、休市日、同股重叠和不新增继承第二日回归测试。
- [x] I8: 增加 HTML 顺序、双腿字段、转义、窄屏和页面无横向溢出的测试/视觉核验。
- [x] I9: 对接入前后决策字段做逐字段对比，并运行相关 Bear、入口、渲染和验收套件。
- [x] I10: 启用子代理完成提交前逻辑、数据、范围、文案与响应式审计；主代理定点复核并修复确认问题。

## 当前验证记录

- 审计修复后，日历、Bear HTML、PostgreSQL、入口、日报渲染和一致性检查 6 个模块共 502 项通过，1 项按条件跳过；日历与 Bear HTML 定向回归 75 项通过。
- Python 3.14 `py_compile` 与全工作区 `git diff --check` 通过；仓库未配置本任务专用 lint/type-check 命令。
- 真实 PostgreSQL 只读重算来源为 `strategy_factor_snapshot_fields`：25 条报告记录、24 个有效交易日、1 个待发生；明日标的计划 11 日、账户持仓 17 日、账户空仓 8 日、不新增计划 14 日，其中 6 日为仍持有第 2 日腿但本日不新增。
- 真实累计账户收益 `+14.17%`、累计上证收益 `-0.55%`、累计跑赢上证 `+14.72%`，跑赢 13/24 日；2026-06-18 双腿账户涨幅 `+8.45%`、跑赢上证 `+8.54%`。
- 账户与计划语义复核通过：无活跃腿显示 `空仓`；上一份标的仍有第 2 日腿时显示标的和 `1x/50% · 第2日`，并注明 `本日计划：不新增`；2026-06-19 显示 `端午休假 · 非交易日`，样本两端显示 `样本外`，这些说明格不进入 25 条记录或收益汇总。
- 真实 Markdown 重渲染前后 SHA-256 均为 `6fab5f3d24eb75e4256d7e01504e45527c1062e519b6f7900b9d5fbf5a62504b`；决策字段投影前后 SHA-256 均为 `b34d4c60efe9eb2bb276ad3c531a73fc7685ae6b1656de64899bba2a26fd324c`，`selection_workflow`、`final_target_resolution`、明日对象、仓位、执行性质、B1/B2 和退出动作未改变。
- 1440x900 浏览器核验：页面宽度 `1440/1440`，25 个记录格、8 个空仓格、6 个持仓但不新增格、5 个解释格，无文字裁切，日历位于账户日序时间轴之前。
- 390x844 浏览器核验：页面宽度 `390/390`，日历内部 `900→296` 横向滚动；滚动后最后一条真实记录 `2026-07-22` 完整可见，无文字裁切。
- 三名子代理分别审计核心计算、HTML/响应式、范围与文档。确认并修复 1 个渲染边界问题：外部载荷中的 `NaN/Infinity` 现在显示 `事实不足`，不会渲染为百分比，并已补回归测试。
- 审计提出的两个范围疑问经主代理复核后不改动：本组件按“最近 25 份日报对应的次日记录”展示，第 2 日腿在下一份日报对应的执行日格合并，不把 25 条扩成 50 条；下一交易日 14 天保护用于阻止数据库断档时把远期行情误配为次日，现有周末和法定休市反例均通过。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest <新增日历数据测试模块>`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m py_compile <本任务修改的Python文件>`
- `git diff --check`
- 本地 HTTP 预览 1440x900 与 390x844，检查日历在账户日序时间轴之前、组件内滚动、无文字重叠和页面级横向溢出。

## Risk And Rollback Points

- `scripts/daily_report_entry_demo.py`、`scripts/report/markdown_report_html.py`、模板和相关测试已有用户改动；编辑前必须完整阅读确切函数，补丁只改目标片段。
- 数据库字段里“无标的”不能自动等于“空仓”；分类错误会破坏账户语义。
- 股票涨幅字段缺省可能落成 `0`；必须读取目标日 `open/close` 并先确认行情行存在，不能把无行当平盘。
- 上证指数表没有本日历所需的开收涨幅列；只允许用目标日有效 `open/close` 计算。交易日行存在但价格事实缺失时保留日期、收益留缺。
- HTML 组件不得改变 Markdown 或 Mermaid 源文本；出现原甘特图、标题顺序或决策字段变化时回滚相应接入点。

## Review Checkpoints

- RP1: PostgreSQL 是明日操作和行情的主事实源，Markdown/JSON 不参与回填。
- RP2: 账户结果 `空仓/标的/事实不足` 与计划字段 `不新增/空仓/标的` 分层；无活跃腿显示空仓，有第二日腿则显示标的并保留不新增计划备注；已知休市和样本外注释不混入记录。
- RP3: 报告日只映射到下一实际交易日，周末与法定休市反例通过。
- RP4: 两日两腿、每腿 50% 的账户当日涨幅与上证开收涨幅公式、单位、舍入和汇总有效日集合一致；累计账户和累计上证分别复利后相减。
- RP5: 日历是只读展示，决策对象、仓位、B1/B2 与退出动作逐字段不变。
- RP6: 桌面与窄屏均可扫描，页面本身无横向溢出。
