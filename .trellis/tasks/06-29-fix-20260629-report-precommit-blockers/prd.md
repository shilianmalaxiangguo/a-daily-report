# 修复 2026-06-29 日报提交前阻断项

状态：✅ 已验证，待提交

## Goal

修复 2026-06-29 正式日报在提交前巡查中暴露的可见不一致和数据缺口，让 Markdown、Bear HTML、生成链路和验收检查对同一份执行事实保持一致。

## User Story

- **角色**：每日使用 A 股日报做次日执行复盘的用户。
- **场景**：用户打开 2026-06-29 日报 Markdown 和 Bear HTML，确认 2026-06-30 应该如何处理太极实业旧仓与深科技明日目标。
- **目标**：一眼看到 Ta/Tb/Tc 时间占用、旧仓/新目标来源、关键资金数据和复盘事实是否完整。
- **成功标准**：报告不再同时说“太极实业旧仓”和“持仓未输入”，资金流表不再全 0，正式日报不外露成片待补事实，验收检查能拦住同类问题。

### 用户旅程

1. 用户打开 Bear HTML → 顶部看到 Ta/Tb/Tc 甘特图，时间轴按 2026-06-28、2026-06-29、2026-06-30 展示关键执行日。
2. 用户打开 Markdown → 同样能看到可读的 Ta/Tb/Tc 表格，不依赖 HTML 专属样式才能理解旧仓和明日目标。
3. 用户查看资金流表 → 行业净流入/涨跌幅使用真实字段，不显示整表 0。
4. 用户查看判断纠偏区 → 已结算事实和未完成结算分区清楚，正式日报不把成片待补事实当作结论输出。
5. 用户或提交者运行验收命令 → 同类可见质量问题会被检查拦住。

## What I Already Know

- 用户指出 2026-06-29 日报中，上一日/旧仓应为太极实业，明日目标应为深科技，时间轴应覆盖 2026-06-28、2026-06-29、2026-06-30。
- 当前 Bear HTML 已包含 Ta/Tb/Tc 时间轴，Ta=太极实业，Tb=深科技，但 Markdown 没有同等表格。
- 当前报告正文仍写“持仓未输入”，与 HTML 的旧仓太极实业冲突。
- 当前资金流入/流出表存在整表 `0.00亿 / +0.00%`，请求层和渲染层字段名不一致是主要线索。
- 当前判断纠偏区仍显示多项待补事实，现有 `report_acceptance_audit` 未拦截。
- 工作区已有大量未提交变更，本任务只修与上述阻断项直接相关的最小文件和产物。

## Requirements

- [x] R1: 2026-06-29 Markdown 和 Bear HTML 都必须展示 Ta/Tb/Tc 日序表，且 Ta=太极实业、Tb=深科技、Tc=无提前占用。
- [x] R2: 日报正文中账户/持仓文案必须与 Ta/Tb/Tc 表一致，不能在存在太极实业旧仓时继续显示“持仓未输入”。
- [x] R3: 行业资金流入/流出表必须使用真实净流入和涨跌幅字段，不得在有有效行业资金行时整表显示 0。
- [x] R4: 正式日报的判断纠偏区必须把未完成结算与今日判断分开，不能把成片待补事实作为已结算结论外露。
- [x] R5: 验收检查必须覆盖 R1-R4 的核心失败形态，避免当前产物能通过但可见面错误。
- [x] R6: 重新生成 2026-06-29 正式 Markdown 和 HTML，并确认 Bear HTML 中保留 Ta/Tb/Tc 图。

## Non-functional Requirements

### 性能

- 沿用现有日报生成性能标准；本任务不引入新外部数据源或长耗时批量回测。

### 安全

- 不修改密钥、环境配置、数据库结构或远端数据。

### 兼容性

- 所有 Python 命令必须使用 `.generated/venv-py314/bin/python3.14`。
- 保持现有报告生成入口和文件命名不变。

### 可访问性

- Bear HTML 时间轴保留现有 `role` / `aria-label` 可读结构。

## Acceptance Criteria

- [x] AC-R1-1: 给定 `reports/2026-06-29_A股日报_完整版.md`，当搜索 Ta/Tb/Tc 相关文案时，可找到包含 2026-06-28、2026-06-29、2026-06-30、太极实业、深科技、没有Tc+0 的可读表格。
- [x] AC-R1-2: 给定 `reports/2026-06-29_A股日报_完整版.html`，当搜索 `position-timeline` 时，可找到同一组日期、Ta/Tb/Tc 和标的信息。
- [x] AC-R2-1: 给定 2026-06-29 正式日报，全文不再出现与旧仓太极实业冲突的“持仓未输入”账户执行文案。
- [x] AC-R3-1: 给定行业资金流入/流出表有有效行，生成报告不得出现流入 TOP10 和流出 TOP10 同时全为 `0.00亿 / +0.00%`。
- [x] AC-R4-1: 给定正式日报的判断纠偏区，已结算表不包含待补事实行；未完成结算如仍存在，必须作为未完成区呈现且验收检查能识别其风险。
- [x] AC-R5-1: 新增或更新的单测能在当前坏样本上失败，并在修复后通过。
- [x] AC-R6-1: 运行 2026-06-29 正式日报生成命令后，Markdown、HTML、执行摘要、证据附录等必要产物更新成功。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md` / `implement.md` 已补齐并按计划执行。
- [x] 必要 research 已保存到 `research/`。
- [x] `implement.jsonl` / `check.jsonl` 只包含 spec / research 清单。
- [x] 相关单测通过。
- [x] 2026-06-29 日报和 HTML 已重新生成。
- [x] 验收检查通过，并人工抽查关键字符串。
- [x] PRD 状态改为 `✅ 已验证，待提交`；本轮未提交，等待用户确认。

## Out Of Scope

- 不清理当前工作区中与本任务无关的 90+ 个既有改动。
- 不重构整个日报生成架构。
- 不新增外部数据源。
- 不覆盖其他日期正式日报，除非验证命令自然读取历史输入。
- 不提交、推送或改远端分支，除非用户另行要求。

## Root Cause

- **现象**：2026-06-29 报告 HTML 有 Ta/Tb/Tc 图但 Markdown 缺图；正文持仓文案与图不一致；行业资金流表整表 0；判断纠偏区外露大量待补事实。
- **根因**：同一执行事实在 Markdown、HTML、前页账户文案和验收检查之间没有统一校验；行业资金流字段在请求层与渲染层之间没有统一别名；判断复盘缺口未被正式日报验收覆盖。
- **影响范围**：2026-06-29 正式日报、Bear HTML、提交前验收检查；同类字段契约也可能影响后续日报。

## Reproduction

1. 打开 `reports/2026-06-29_A股日报_完整版.html`，可见 Ta/Tb/Tc 图中 Ta=太极实业、Tb=深科技。
2. 打开 `reports/2026-06-29_A股日报_完整版.md`，Ta/Tb/Tc 表缺失，正文仍写“持仓未输入”。
3. 查看资金流入/流出表，可见全 0 行。
4. 运行当前验收检查，报告仍能通过。

## Fix Strategy

- **修改点**：报告运行时字段归一、Markdown 前页/HTML 读者渲染、验收检查、相关单测、2026-06-29 产物。
- **修改方式**：沿用现有数据结构，在现有边界上补字段别名和可见表格，不新增大抽象。
- **风险评估**：中等；涉及正式产物与验收检查，但可用小范围单测和正式生成命令验证。

## Regression Guard

- 新增或更新资金流字段归一测试。
- 新增或更新 Ta/Tb/Tc Markdown/HTML 输出测试。
- 新增或更新报告验收测试，覆盖整表 0 和旧仓冲突。
- 必要时新增当前日期产物检查命令，作为提交前人工核验。

## Technical Notes

### 参考来源

- 当前 2026-06-29 Markdown / HTML 产物。
- 子代理提交前审计结果。
- `.trellis/spec/backend/daily-report-decision-loop.md`。
- `wiki/交易思想/日报术语契约.md`。

### 影响区域

- `scripts/domains/market_activity/request.py` — 行业资金流字段归一。
- `scripts/domains/market_activity/report_section_nodes.py` — 行业资金流渲染。
- `scripts/report/runtime.py` / `scripts/report/markdown_report_html.py` / `scripts/templates/daily_report_markdown_reader.html` — Ta/Tb/Tc 表与前页文案。
- `scripts/report/report_acceptance_audit.py` — 提交前可见质量检查。
- `tests/` 相关测试 — 回归覆盖。
- `reports/2026-06-29_*` — 重新生成的正式产物。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_request tests.test_market_activity_domain_report_sections tests.test_daily_report_markdown_html tests.test_report_acceptance_audit tests.test_front_page_v2_renderer`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-29`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-29_A股日报_完整版.md --companion-html reports/2026-06-29_A股日报_完整版.html`
- `rg -n "position-timeline|2026-06-28|2026-06-30|太极实业|深科技|0.00亿 \\| \\+0.00%|持仓未输入|待补事实" reports/2026-06-29_A股日报_完整版.md reports/2026-06-29_A股日报_完整版.html`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_activity_request tests.test_market_activity_domain_report_sections tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output tests.test_report_acceptance_audit tests.test_front_page_v2_renderer tests.test_position_strategy_report tests.test_pk_decision_stage tests.test_decision_statistics tests.test_report_runtime.ReportRuntimeTest.test_runtime_keeps_inferred_previous_report_path_from_blocking_tomorrow_target` — 456 tests passed.
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-29 --overwrite-official` — official Markdown, HTML, execution summary, light report, evidence appendix, runtime log, tournament HTML, sector precheck HTML, chanlun HTML, and position strategy regenerated.
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-29_A股日报_完整版.md --companion-html reports/2026-06-29_A股日报_完整版.html` — passed.
- `rg -n "无持仓负担|无旧仓|持仓未输入" reports/2026-06-29_A股日报_完整版.md reports/2026-06-29_A股日报_完整版.html; true` — no matches.
- `rg -n "\\*\\*T-015\\*\\*|\\*\\*T-017\\*\\*|\\*\\*T-018\\*\\*|\\*\\*T-025\\*\\*|账户后台任务负担|持仓优先动作" reports/2026-06-29_A股日报_完整版.md` — target tables and old-path account panel present.
- `visible_report_assertions` Python one-shot check — passed.
- `git diff --check` — passed.

## 落地 commit

未提交；等待用户确认提交范围。
