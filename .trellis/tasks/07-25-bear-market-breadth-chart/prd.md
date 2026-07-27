# Bear 日报加入最近25日 T0市场底色图

状态：🔨 进行中

## Goal

让每份每日完整版 Bear 日报在“指数与市场底色”中展示截至报告日的最近 25 个交易日市场底色，方便读者同时观察上涨与下跌家数、全A涨跌幅和创新高占比的共同变化。

## User Story

- **角色**：复盘每日 A 股日报的交易者。
- **场景**：在 Bear HTML 阅读市场底色和明日执行结论的依据时。
- **目标**：无需切换到前向回测页面，即可查看最近 25 个交易日的市场宽度变化。
- **成功标准**：在报告日对应的 Bear HTML 中能看到数据日期不晚于报告日、按交易日升序排列的图表。

### 用户旅程

1. 用户打开某日完整版日报的 Bear HTML。
2. 用户进入“指数与市场底色”。
3. 系统在该段落开头展示最近 25 个交易日的市场底色图。
4. 用户可从图中比较上涨家数、下跌家数、全A涨跌幅和创新高占比；窄屏时页面本身不发生横向溢出。

## What I Already Know

- 最终 Bear 日报由 `markdown_report_html.py` 和 `daily_report_markdown_reader.html` 生成，不走独立驾驶舱模板。
- 回测页已有同名图的四组数据语义：上涨家数、下跌家数、全A涨跌幅、创新高占比。
- 历史 PostgreSQL 已提供全A指数日线、逐日涨跌家数、创新高反馈序列查询；全A涨跌幅需要用前一交易日收盘价计算。
- Bear HTML 现有统一图卡、载荷和 ECharts 分发机制。
- 报告候选、最终对象、仓位、执行性质、B1/B2 与退出动作不属于本次修改范围。

## Requirements

- [x] R1: 在完整版 Bear 日报的“指数与市场底色”标题后、该段落原始事实表前插入一张 `T0市场底色` 图。
- [x] R2: 图表展示截至目标报告日的最近 25 个交易日，日期升序；不得读取目标日之后的数据。
- [x] R3: 图表包含上涨家数、下跌家数、全A涨跌幅、创新高全A占比四组数据，沿用现有前向回测图的正负柱与双线表达；下跌家数使用微信绿，并在 4000 家阈值显示 `4000+下跌` 标线。
- [x] R4: 图表事实只来自带有目标日期依据的历史事实；缺失值保持为空，不得伪造为 0 或以当前数据补历史数据。
- [ ] R5: 图表在桌面和窄屏 Bear 阅读页中可见，页面本身不得因图表产生横向溢出。
- [x] R6: 接入图表不能改变日报正式决策字段或 Markdown 正文的既有结论。

## Non-functional Requirements

### 性能

- 只查询构建最近 25 个交易日图表所需的最小历史事实；不引入实时全量采集。

### 兼容性

- 沿用本地 ECharts 资源和 Bear 图卡机制；无图表载荷时保留现有 Bear HTML 行为。

### 可访问性

- 图表容器保留准确的 `role="img"` 和中文 `aria-label`。

## Interaction States

| 状态 | 展示 | 用户可操作 |
|------|------|-----------|
| 正常 | 最近 25 个交易日的四组市场底色数据 | 查看图例与悬浮提示 |
| 部分事实不足 | 已知日期与数值正常绘制，缺失数值不绘制 | 查看其余事实 |
| 无可用历史事实 | 不插入图卡，保留原有市场底色内容 | 正常阅读报告 |

## Acceptance Criteria

- [x] AC-R1-1: 给定包含“指数与市场底色”段落的日报，生成 Bear HTML 后，`data-bear-chart="t0_market_breadth"` 恰好出现一次，且位于该标题后、原始事实表前。
- [x] AC-R2-1: 给定 26 个及以上历史交易日和一个目标日之后的未来行，生成的载荷恰好保留目标日及以前最近 25 个交易日，并按日期升序排列。
- [x] AC-R3-1: 给定完整历史事实，Bear 图表载荷包含四组指定序列；上涨家数为正柱、下跌家数为微信绿负柱，全A涨跌幅和创新高占比为独立折线；下跌家数系列包含 `yAxis: -4000` 且标注为 `4000+下跌`，即使最近 25 日没有达到该阈值，家数轴也必须保留足够范围让标线可见。
- [x] AC-R4-1: 给定缺失涨跌家数或创新高事实的日期，生成载荷保留日期且对应数值为 `null`，不以 0 或无日期当前数据替代。
- [ ] AC-R5-1: 使用一份 replay 日报在桌面和窄屏浏览器验证图表 canvas 非空、图例可读且文档无横向溢出。
- [x] AC-R6-1: 图表接入前后，同一份日报数据的 `selection_workflow`、`final_target_resolution`、明日执行对象、仓位、执行性质、B1/B2 和退出动作逐字段一致。

## Definition Of Done

- [ ] Requirements 与 Acceptance Criteria 全部满足。
- [x] 本任务按 Trellis 复杂跨层任务保存 PRD、设计和实现计划。
- [x] 针对数据窗口、Bear 载荷/位置、保存链路和正式决策不变性添加或更新最小测试。
- [ ] 相关测试、replay 生成和浏览器检查通过。
- [ ] PRD 状态改为 `✅ 已完成` 并回填落地 commit。

## Out Of Scope

- 不改变候选生成、最终对象、仓位、B1/B2、退出动作或执行窗口。
- 不改变 Markdown 正文的现有市场底色表。
- 不向独立驾驶舱 `daily_report_reader.html` 增加重复图表。
- 不修改前向回测图的既有视觉语义或历史数据。
- 不补录、覆盖或重写已有 PostgreSQL 历史事实。

## Technical Notes

### 参考来源

- `reports/replay/2026-06-17_2026-06-30_板块资金扩散前向回测.html` — 已确认的 T0 市场底色图表达。
- `scripts/replay/sector_forward_replay.py` — 现有四组数据和 ECharts 表达。
- `scripts/report/html_report_view.py` — 25 日窗口与按日期补齐涨跌家数的已有事实读取逻辑。

### 影响区域

- `scripts/daily_report_entry_demo.py` — 在 PostgreSQL 同步后构建 Bear 图表历史事实并传入 Bear 渲染器。
- `scripts/report/markdown_report_html.py` — 合并载荷并在市场底色段落插入图卡。
- `scripts/templates/daily_report_markdown_reader.html` — 渲染 ECharts 图表。
- `tests/test_daily_report_markdown_html.py` — 图表载荷、位置和前端表达测试。
- `tests/test_daily_report_entry_html_output.py` — 保存后 Bear HTML 主链测试。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render tests.test_report_replay`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <date> --replay`
- 使用本地浏览器在桌面与窄屏查看生成的 Bear HTML。

## 落地 commit

待完成。

## 2026-07-25 验证记录

- `2026-07-22 --replay` 完整退出并生成 replay Markdown、Bear HTML 和 replay 快照。
- 最终 Bear 载荷为 25 个交易日，日期从 `2026-06-17` 到 `2026-07-22`，升序且无未来日期；图卡和图表容器各 1 个。
- 目标日图表事实与日报正文保持同一创新高口径：上涨 1530 家、下跌 3876 家、全A涨跌幅 -0.74%、创新高全A占比 0.10%。
- Bear 渲染 60 项、日报入口 50 项、正式决策 80 项、replay 日期保护 2 项通过；Python 3.14 语法检查和 `git diff --check` 通过。
- 独立提交前审计未发现高、中严重度问题；相似标题插入位置和数据库后备正向测试已补齐。
- 未完成：内置浏览器拒绝访问本地 `file://` 页面，不能继续执行实际 canvas、窄屏和侧栏收起后的尺寸变化检查。
- 额外说明：完整 `tests.test_report_replay` 在既有 `test_legacy_replay_wrapper_delegates_to_runtime` 子进程处不退出；本任务直接相关的两项 replay 日期保护测试已单独通过。
- 中断续跑后确认没有残留的日报生成、相关单测或 replay 进程，目标文件和最终 HTML 均完整存在。
- 最终核心回归再次通过：Bear 渲染与日报入口共 110 项、正式决策 80 项、replay 日期保护 2 项；Bear 渲染模块在补强相似标题、重复标题和下跌家数空值断言后 60 项通过。
- 最终 HTML 再次解析为 25 条，日期从 `2026-06-17` 到 `2026-07-22`，图卡与容器各 1 个，且顺序为正式标题、图卡、原始事实表；目标日事实为上涨 1530 家、下跌 3876 家、全A涨跌幅 -0.74%、创新高全A占比 0.10%。
- 中断续跑时再次尝试内置浏览器，仍因本地 `file://` 地址被浏览器策略拒绝；因此 R5、AC-R5 和 I6 继续保持未完成，不据静态检查替代实际 canvas 验收。
