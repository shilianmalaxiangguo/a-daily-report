# 创新高扩散收缩与核心补跌预警接入日报

状态：🔨 进行中（实现与质量检查完成；目标日 replay 持久化受现场 PostgreSQL 事实库缺失影响）

## Goal

把创新高从“当日热度数字”升级为可复核的市场结构证据：为日报说明趋势生成率是扩散、收缩、碎片化还是修复，并明确核心相对强与板块生态转弱只是待复核的风险结构，不直接生成交易动作。

## User Story

- **角色**：日报阅读者和复盘者。
- **场景**：指数或核心股还强，但创新高数量快速下降，需判断是周期收缩还是下跌后衰竭。
- **目标**：在《创新高趋势反馈》内同时看到当日生成率、跨日变化、板块成群度、主要反证和下一窗口任务。
- **成功标准**：完整版和 Bear HTML 显示相同的结构评语，且日报的明日对象、仓位、执行性质、B1/B2 和退出动作与接入前逐字段一致。

## What I Already Know

- `scripts/domains/market_activity/new_high_runtime.py` 已产出 `new_high_count`、`all_a_share_pct`、`trend_rows`、`sector_distribution` 和 `leading_sectors` 。
- `scripts/report/market_overview_nodes.py` 是《创新高趋势反馈》的 Markdown 单一输出入口；旧版 `<2% / 2%-5% / >5%` 与 ECharts 的 `5% / 2% / 1%` 口径存在边界和语义不一致。
- Bear HTML 从最终 Markdown 读取，无需重新推断日报动作。
- LLM Wiki 的运行来源、路由和日志契约已存在，新节点必须保持 `explanation_only` 边界。
- `2026-07-13` 现有可见窗口稳定显示创新高 `6 只 / 0.12%`；周边日志存在来源混用和多次运行差异，不把冲突序列当作唯一事实。

## Requirements

- [x] R1: LLM Wiki 保留并路由“创新高扩散、核心独强与补跌”知识节点，包含适用场景、不适用场景、反证、来源与数据缺口。
- [x] R2: 从快照已有字段计算可审计的结构字段：当日新高数、较前日变化、窗口峰值保留率、是否首次个位数、板块分散/成群、头部板块占比。
- [x] R3: 在《创新高趋势反馈》现有用途和读法之后、趋势表之前加入四行结构输出：结构判断、风险含义、主要反证、下一窗口。
- [x] R4: 当历史行缺少逐日来源、目标日不匹配或板块归属不足时，日报明示事实不足，不输出精确跨日速度或“半导体主导”结论；板块覆盖异常也降为事实不足。
- [x] R5: 结构评语只进入解释、复盘和日报证据，不改候选生成、明日唯一对象、仓位、执行性质、B1/B2 或退出动作。
- [x] R6: 完整版、摘要版和 Bear HTML 均保留该结构评语，且页面不横向溢出。
- [ ] R7: 对个位数首次、跨日快速下降、板块碎片化、数据不足、低值后修复以及决策字段不变各类情况补齐验收；测试与既有 replay 产物已通过，目标日 replay 持久化因 PostgreSQL 事实库缺失尚未完成。
- [x] R8: 建立唯一的创新高绝对水位五档：`>=5%` 极致扩散、`2%-5%` 有效扩散、`1%-2%` 扩散偏冷、`0.2%-1%` 极低扩散、`<0.2%` 或新高数 `<10只` 扩散断层；日报、趋势表、Bear ECharts 和 LLM Wiki 使用同一阈值，并把绝对水位与变化方向分开表达。

## Non-functional Requirements

### 兼容性

- 沿用 Python 3.14 和现有日报 Markdown/Bear 渲染器，不新增外部数据源。

### 可追溯性

- 结构字段只使用当日快照和其中的历史行；最终输出保留目标日和来源不足提示。

### 用户可见语言

- 遵守《日报术语契约》，使用“证据、条件、观察、不参与、下一窗口”，不把解释词写成执行指令。

## Acceptance Criteria

- [x] AC-R1-1: LLM Wiki manifest/lint 能识别新节点的来源、路由条件和 `explanation_only`，新节点可通过中文触发词命中。
- [x] AC-R2-1: 给定 `new_high_count=6` 、前一行为大于等于 10 且板块分属较分散，结构函数返回“扩散收缩/断层”和首次个位数字段。
- [x] AC-R2-2: 给定长期低值后持续修复的序列，结构函数不固定输出周期收缩。
- [x] AC-R3-1: 结构评语位于《创新高趋势反馈》的读法之后、趋势表之前，包含四行固定标题。
- [x] AC-R4-1: 没有历史行、目标日不匹配、板块均为待补充时，输出明确事实不足，不输出半导体主导、核心必然补跌等超出证据的语句；重复/覆盖异常同样降级。
- [x] AC-R5-1: 路由命中的 knowledge hit 的 `decision_scope` 为 `explanation_only`，`not_used_for` 包含候选、最终对象、仓位、B1/B2 和退出动作。
- [x] AC-R6-1: 对包含《创新高趋势反馈》的 Markdown 进行 Bear 渲染，保留“结构判断”、“主要反证”和“下一窗口”，不出现横向溢出。
- [ ] AC-R7-1: 相关单测、日报一致性检查和 replay 对比已通过；目标日 replay 在 PostgreSQL-only 同步处停止，未生成新的完整 replay 快照，因此保留未完成标记。
- [x] AC-R8-1: 精确边界 `5 / 2 / 1 / 0.2` 向上归档一致，个位数优先覆盖百分比档位；`2.3% -> 0.8%` 输出扩散收缩，`0.4% -> 0.8%` 输出低位修复。
- [x] AC-R8-2: Bear 图表的四条参考线从 Python payload 读取，标签分别为“5% 极致扩散线 / 2% 有效扩散分界 / 1% 极低扩散分界 / 0.2% 断层观察线”，JavaScript 不再保存第二套硬编码阈值。
- [x] AC-R8-3: LLM Wiki 记录五档、方向差异和“绝对水位不是买卖动作”，并可由“极致扩散 / 有效扩散 / 扩散偏冷 / 极低扩散 / 扩散断层”命中。

## Definition Of Done

- [ ] Requirements 全部完成。
- [ ] Acceptance Criteria 全部通过。
- [x] `design.md` 和 `implement.md` 已完成并经过审查。
- [x] 校准证据已保存到 `research/`，不只留在对话中。
- [x] 单测、日报渲染检查和日报一致性对比通过。
- [x] 提交前子代理审计已完成。
- [ ] PRD 状态改为 `✅ 已完成`；落地 commit 由用户决定。

## Out Of Scope

- 不重新按当前实时盘面采集 2026-07-01 至07-17 的全部历史数据。
- 不用未经同源回补的历史数字生成买卖动作。
- 不改选股候选池、最终对象、仓位、B1/B2、旧仓处理或退出动作。
- 不新增数据源，不修复本任务无关的历史日报、仓位或 LLM Wiki 改动。
- 不把“半导体创新高主导”作为没有板块成群证据时的固定文案。

## Technical Notes

### 参考来源

- `wiki/交易思想/创新高扩散、核心独强与补跌.md`
- `wiki/板块补充/板块中枢与主线延续.md`
- `scripts/domains/market_activity/new_high_runtime.py`
- `scripts/report/market_overview_nodes.py`
- `.generated/report-quality/2026-07-15_default.json`
- `snapshots/2026-07-17.json`

### 影响区域

- 市场派生证据：创新高快照的结构解释。
- 报告渲染：《创新高趋势反馈》和从 Markdown 读取的 Bear HTML。
- LLM Wiki：知识清单、变化路由和来源指纹。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_new_high_structure_signal tests.test_market_overview_builder tests.test_llm_wiki_context tests.test_llm_wiki_router tests.test_llm_wiki_manifest tests.test_llm_wiki_lint`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py <target-report.md>`
- replay 后逐字段对比决策产物，确认结构解释没有回写明日动作。

## 本轮验证记录

- 创新高结构 `10` 项通过；受影响的市场总览定向回归 `3` 项通过；Bear HTML 与入口 `100` 项通过；LLM Wiki 路由/上下文/清单/lint `155` 项通过。
- 市场总览全量定向运行 `44` 项中 `43` 项通过；唯一失败是既有涨跌比浮点格式断言（`3600.0 / 1600.0` 对 `3600 / 1600`），与本任务无关。
- 正式日报 acceptance audit 通过；replay 现有产物审计仅报既有账户日序 `Tb` 历史路径缺失。
- 目标日 replay 已从 `snapshots/2026-07-17.json` 完成读取、关键数据检查、结构输出和日报一致性检查；随后因 PostgreSQL-only 事实库不可用停止，没有覆盖正式历史日报，也没有写入新 replay 快照。
- 目标日输出已同步 `事实不足` 用户口径；趋势表列名改为“板块分布前列”，未把 2026-07-13 的 6 只或 2026-07-17 的 9 只写成半导体主导。
- LLM Wiki lint 为 `32 entries / 0 errors / 42` 个既有元数据提醒；Python 3.14 编译检查、`git diff --check` 和 Trellis 上下文校验通过。

## 落地 commit

待用户决定；当前不创建 commit。
