# 修复ETF成交额历史覆盖并生成20260722日报

状态：✅ 实现与验收完成（未提交）

## Goal

修复 ETF 两市成交额 25 日趋势因历史来源覆盖不足而停止生成的问题，在不降低完整性标准的前提下生成并验收 2026-07-22 日报、快照和 Bear HTML。

## User Story

- **角色**：日报使用者
- **场景**：生成 2026-07-22 当日正式日报时，目标日 ETF 成交额完整，但历史趋势被不完整来源污染
- **目标**：使用来源日期明确、连续且已经验收的历史事实续接目标日事实
- **成功标准**：ETF 趋势通过现有完整性检查，正式 Markdown 与 Bear HTML 生成并通过一致性检查

### 用户旅程

1. 用户运行 2026-07-22 正式日报生成入口。
2. 系统读取上一交易日已经验收的 ETF 25 日趋势，并获取目标日完整 ETF 成交额。
3. 系统重建截至目标日的 25 日窗口，重新检查日期、样本覆盖和来源日期。
4. 检查通过后，系统生成正式日报、快照和 Bear HTML；任一关键事实不完整时仍停止生成。

## What I Already Know

- 2026-07-22 新浪 ETF 当前列表有 1607 只，1606 只有正成交额，目标日覆盖率为 99.94%。
- 新浪逐证券历史接口全量请求中 1606/1607 返回非空响应，没有整体反爬证据；但聚合后的历史覆盖会降至约 1000 只，单次重跑甚至更低，不能作为稳定 25 日来源。
- PostgreSQL 中 2026-07-21 已验收的 `etf_turnover_series` 有连续 25 个交易日，覆盖数量从 1561 只逐步增加到 1603 只。
- Tushare `fund_daily` 单日查询可返回约 2000 行，但当前代理在显式传入 `offset=0` 或使用日期区间查询时返回空；按证券查询区间可用但全量约需 35 分钟。
- 东方财富 ETF 接口当前出现连接中断，不能作为本次稳定来源。
- 新雪球 Cookie 已保存到 `.env`，热榜 100 条和理由 8 条的窄检查均通过。

## Requirements

- [x] R1: ETF 趋势在目标日历史抓取不完整时，只能使用上一交易日 PostgreSQL 中已经验收、日期连续、覆盖正常的 ETF 窗口作为历史底座。
- [x] R2: 新窗口必须保留最近 24 个历史交易日并追加目标日，逐行保留 `trade_date`、`source_date`、`query_date` 和来源标识，再执行现有 70%/95% 完整性检查。
- [x] R3: 上一交易日事实缺失、日期不连续、历史窗口曾被标记为不完整，或目标日 ETF 当前列表覆盖低于 95% 时，继续停止生成，不得用残缺序列替代。
- [x] R4: 修复 Tushare `fund_daily` 首次分页显式传 `offset=0` 导致空结果的问题，并保留后续页能力；Tushare 仍只作备用来源。
- [x] R5: 生成 2026-07-22 正式完整版、执行摘要、运行日志、快照和 Bear HTML，并通过日报一致性检查。

## Non-functional Requirements

### 性能

- 优先读取上一交易日 PostgreSQL 事实和单次目标日 ETF 当前列表，不在正常生成路径逐只查询 1607 只基金。

### 安全

- 雪球 Cookie 只保存在被 Git 忽略的 `.env`，测试、日志和用户可见输出不得包含凭据值。

### 兼容性

- 保持现有 ETF payload 字段和 70%/95% 判断兼容；新增来源字段只能补充证据，不得改变报告决策链路。

## Acceptance Criteria

- [x] AC-R1-1: 给定上一交易日有完整 25 日 ETF 事实、当前历史接口不完整，当生成目标日报时，结果使用上一事实的最近 24 日并追加目标日。
- [x] AC-R1-2: 给定上一交易日事实缺失或曾标记为不完整，当生成目标日报时，ETF 结果仍为不完整并停止日报生成。
- [x] AC-R2-1: 组合后的 25 行日期与交易日历一致，每行有明确 `trade_date/source_date/query_date/source`。
- [x] AC-R2-2: 组合后的 payload 继续输出并通过 `coverage_ratio`、`overall_coverage_ratio`、`coverage_reference_count`、`latest_covered_etf_count` 和 `total_etf_universe_count` 检查。
- [x] AC-R3-1: 目标日当前列表覆盖低于 95% 的测试仍失败，不得被 PostgreSQL 历史事实掩盖。
- [x] AC-R4-1: Tushare 首次单日请求不传 `offset=0`，当首批达到页大小时后续请求使用正 offset。
- [x] AC-R5-1: `reports/2026-07-22_A股日报_完整版.md`、对应 `.html`、摘要、运行日志和 `snapshots/2026-07-22.json` 均存在且非空。
- [x] AC-R5-2: 正式生成输出“日报一致性检查通过”，完整版通过 `report_acceptance_audit.py`。

## Definition Of Done

- [x] Requirements 全部完成
- [x] Acceptance Criteria 全部通过
- [x] `design.md` / `implement.md` 已补齐并通过 review
- [x] 研究证据已保存到 `research/`
- [x] `implement.jsonl` / `check.jsonl` 已配置
- [x] 相关单测通过
- [x] 2026-07-22 正式生成和验收通过
- [x] 提交前子代理审计完成并由主代理复核
- [x] PRD 状态已改为实现与验收完成，并明确记录未提交

## Out Of Scope

- 不降低 ETF 目标日或历史趋势的 70%/95% 完整性标准。
- 不把不完整的新浪历史聚合或 Tushare 空日期伪装为完整事实。
- 不修改候选池、最终对象、仓位、B1/B2、退出动作或 Bear 展示结构。
- 不重构其他数据源，不处理同文件中已有的创新高和涨跌停未提交改动。
- 不覆盖其他日期正式日报，不修改数据库结构或历史记录。

## Root Cause

- **现象**：ETF 趋势有 25 行，但历史日覆盖只有约 1000 只，导致关键数据检查停止生成。
- **根因**：新浪逐证券历史聚合在不同运行中的历史覆盖不稳定；Tushare 备用链路又因首次请求显式传 `offset=0`、区间查询兼容性和部分日期空结果而无法接替。系统没有复用上一交易日已经验收的连续 ETF 窗口。
- **影响范围**：依赖实时采集生成、且前一交易日已有正式事实的当日日报。

## Reproduction

1. 运行 `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-22`。
2. 预期：ETF 25 日趋势完整并继续生成；实际：目标日 1606/1607，但历史最低约 1000/1607，程序停止生成。
3. 直接查询 PostgreSQL 2026-07-21 事实，可见完整 25 日窗口及 1561-1603 只覆盖。

## Fix Strategy

- **修改点**：`scripts/input/tushare_runtime.py` 的 ETF 历史窗口构建和 Tushare 单日分页参数。
- **修改方式**：复用模块已有事实库注入方式；严格验证上一交易日窗口后续接目标日；首次 Tushare 分页省略零 offset。
- **风险评估**：中。变更影响关键数据来源选择，但不改变完整性阈值或报告决策；通过来源缺失、日期缺口、覆盖不足和正常续接测试控制风险。

## Regression Guard

- 新增测试：上一交易日完整窗口续接成功、历史事实不完整时拒绝、目标日覆盖不足时拒绝、Tushare 首次分页参数。
- 保留测试：ETF 最新覆盖坍塌、总体样本覆盖不足、输入运行拒绝不完整 payload、报告生成前检查拒绝不完整趋势。

## Technical Notes

### 参考来源

- `.trellis/spec/backend/quality-guidelines.md` — ETF Turnover Coverage Contract
- `wiki/运行契约/日报数据源契约.md` — PostgreSQL 主线窗口与历史事实口径
- `research/etf-source-diagnosis.md` — 本次实测证据

### 影响区域

- `scripts/input/tushare_runtime.py` — ETF 趋势采集、历史续接、Tushare 备用请求
- `tests/test_tushare_input_runtime.py` — 数据源和完整性回归测试
- `reports/2026-07-22_*`、`snapshots/2026-07-22.json` — 本次生成产物

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_tushare_input_runtime tests.test_input_runtime tests.test_daily_report_render tests.test_market_overview_nodes`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-22`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-07-22_A股日报_完整版.md`
- 检查正式 Markdown、HTML、摘要、运行日志和快照均存在且非空。

## 落地 commit

未提交；提交前需用户明确确认。

## 验收结果

- ETF 正式来源：`postgresql.daily_report_facts+sina.etf.category_current_amount`。
- 25 日窗口：2026-06-17 至 2026-07-22，最低覆盖 1562 只，目标日覆盖 1606/1607 只。
- 目标日 ETF 两市成交额：5791.75 亿元。
- `tests.test_tushare_input_runtime`：123 项通过。
- 输入、日报预检和市场概览跨层回归：106 项通过。
- 正式生成退出码为 0，生成内置一致性检查通过，独立 `report_acceptance_audit.py` 通过。
- 三名独立子代理完成提交前逻辑、测试、范围与凭据审计；无阻断发现，分页第三页和成功续接不访问新浪历史的断言已补强。
