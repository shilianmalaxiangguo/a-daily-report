# 修复仓位档与1x/2x语义串位

状态：✅ 实现与验证完成，待用户确认提交

## Goal

修复日报把 `1x/50%/B1` 错写为满仓、把 `2x` 错写为 200% 暴露的问题，确保结构化决定、账户暴露、Markdown、日志、Bear HTML、持仓策略和知识规则始终使用同一仓位字典。

## User Story

- **角色**：使用 0、1x、2x 三档仓位并按 B1/B2 分笔执行的 A 股短线交易者。
- **场景**：日报在弱环境或条件执行场景选出唯一对象，并给出次日仓位与 B1/B2 计划。
- **目标**：一眼确认 1x 就是半仓、2x 才是满仓，不因账户暴露、旧仓继承或渲染后处理被错误升档。
- **成功标准**：同一对象在所有产物中保持 `0=0%`、`1x=50%`、`2x=100%`；B1 为 1x，B2 确认后总仓位才到 2x。

### 用户旅程

1. T0 日报决定 1x 条件执行 → 次日只先执行 B1，报告始终显示 `1x/50%`。
2. T0 日报决定 2x 满仓计划 → 次日先执行 B1，只有确认成立才执行 B2，总仓位达到 `2x/100%`。
3. 旧仓已有 1x → 同股 T 时把旧仓视为 B1；B2 未确认不增加，确认失败仍回到 1x 或更低。
4. 旧仓 1x 与不同股票的新仓 1x 同时存在 → 账户合计为 2x/100%，不得写成 200%。

## What I Already Know

- 用户已明确唯一正确契约：`0=不参与`、`1x=50%半仓/B1`、`2x=100%满仓/B1+B2`。
- `selection_workflow`、`position_decision` 和 `final_target_resolution` 原本都能保持 `position_pct=50`；错误发生在账户继承、暴露解释、渲染归一和验收测试。
- `runtime._full_or_empty_account_visible_text()` 会主动把 `50%条件执行` 替换为满仓，并删除结构化 50% 痕迹；这不是跨测试数据泄漏。
- 前日报默认目标当前被归一为 `100%/1x`，与用户契约相反。
- 当前工作区有大量并行修改；07-17 选择性暂存明确排除了仓位、旧仓和候选语义，本任务不得混入其提交范围。

## Source Of Truth

只以用户本轮明确确认的仓位定义和本 PRD 为最高优先级来源：

| x档 | 计划仓位档 | 分笔含义 | 用户可见含义 |
|-----|------------|----------|----------------|
| `0` | `0%` | 无 B1/B2 | 不参与，只观察或处理旧仓 |
| `1x` | `50%` | B1 参与权 | 半仓条件执行 |
| `2x` | `100%` | B1 + B2 | 满仓计划；B2 仅在确认后执行 |

历史文档、测试或快照与本表冲突时，以本表为准。`previous_report_target_default_1x` 作为历史来源标识保留，但不再代表 100%。

## Requirements

- [x] R1: 建立并复用唯一仓位换算契约，稳定映射 `0/1x/2x` 与 `0/50/100`，不得由字符串或账户模式另行解释。
- [x] R2: `selection_workflow.final.position_pct`、`position_decision.target_position_pct` 和最终对象解析出的仓位档必须原样传播；下游不得把 50% 升为 100%。
- [x] R3: 前日报默认目标在次交易日继承为已确认 `1x/50%/B1` 旧仓；历史坏数据即使在该来源下写成 100，也必须修正为 50。显式真实 100% 或明确 2x 事实不降级。
- [x] R4: 账户暴露必须按腿的仓位档汇总：单腿 1x=50%，两腿各 1x 合计 2x=100%；同股 B2 也只把 1x 提升到 2x。总计划暴露不得超过 2x/100%。
- [x] R5: Markdown、stdout、Bear HTML、首页、持仓策略和执行摘要必须同时保留 x档与百分比含义；50%只写 1x/B1/半仓，100%才写 2x/B1+B2/满仓。
- [x] R6: 验收检查必须拒绝同一新仓对象上的 `position_pct=50` 与满仓文案、`1x` 与 100%、`2x` 与 200% 等组合，并接受正确的 0/1x/2x 三档输出。
- [x] R7: Wiki、LLM 静态上下文、知识路由和 backend spec 必须同步新契约，清除会再次生成旧语义的正文，同时保留旧关键词的检索兼容。
- [x] R8: 不改变候选池、评分、最终对象、板块判断、交易窗口和 T0 已决定/T+1只执行或取消的纪律。
- [x] R9: 兼容读取历史 `full_or_empty_exposure.v1` 与旧来源标识，但新产物必须写清每腿 `position_pct`、`position_x` 和汇总暴露，不再依赖含糊布尔值推断比例。

## Non-functional Requirements

### 兼容性

- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 不修改历史 source id、数据库 schema 或正式日报文件名。
- 不覆盖正式历史日报；只通过测试和隔离产物验证。

### 可追溯性

- 每个可见仓位必须能回溯到结构化 `position_pct` 和对应 x档。
- 旧快照修复必须保留原始来源，不把推定旧仓伪装成显式成交事实。

## Acceptance Criteria

- [x] AC-R1-1: 给定 0、50、100 三个计划仓位档，换算结果分别严格为 0、1x、2x，反向换算分别为 0%、50%、100%。
- [x] AC-R2-1: 给定最终对象 `position_pct=50`，经过 runtime、最终结论、Markdown、stdout 和 Bear HTML 后仍为 `1x/50%条件执行`，任何层都不出现满仓或 100%。
- [x] AC-R2-2: 给定最终对象 `position_pct=100`，报告显示 `2x/100%` 满仓计划，并明确 B1 先参与、B2 确认后补。
- [x] AC-R3-1: 给定来源为 `previous_report_target_default_1x` 且历史数值为 0、缺失或错误的 100，归一后均为已确认 `1x/50%` 旧仓。
- [x] AC-R3-2: 给定显式真实持仓 100% 且不属于默认1x来源，归一后保持 `2x/100%`。
- [x] AC-R4-1: 给定旧仓 1x 与新仓 1x，账户汇总为 2x/100%；不存在 200% 或两个满仓账户的文字。
- [x] AC-R4-2: 给定同股旧仓 1x，B2 未确认时保持 1x/50%；B2 确认后上限为 2x/100%，失败时回到 1x 或更低。
- [x] AC-R5-1: 完整版、摘要、首页、持仓策略和 Bear HTML 对同一输入逐字段一致。
- [x] AC-R6-1: 验收检查分别拒绝 `50%+满仓`、`1x+100%`、`2x+200%` 三类矛盾，并通过正确三档样本。
- [x] AC-R7-1: 以“1x/2x仓位”为问题调用知识路由时，返回 `1x=50%/B1`、`2x=100%/B1+B2`，不返回旧满仓/200%解释。
- [x] AC-R8-1: 修复前后同一 fixture 的 `selection_workflow.final.execution_object`、`final_target_resolution.new_entry_target`、交易窗口和取消条件逐字段一致，仅仓位解释被纠正。
- [x] AC-R9-1: 旧 v1 暴露数据可读取；新产物包含显式的旧仓、新仓和汇总 `position_pct/position_x` 字段，不通过存在性布尔值猜仓位。

## Definition Of Done

- [x] Requirements 全部完成
- [x] Acceptance Criteria 全部通过
- [x] `design.md` / `implement.md` 已补齐并通过 review
- [x] 根因研究已保存到 `research/`
- [x] `implement.jsonl` / `check.jsonl` 已配置
- [x] 相关定向、跨层和完整模块测试通过
- [x] `git diff --check` 通过
- [x] 修复后的独立子代理提交前复核（确认三种 v2 流程无越界；审计发现的同源仓位边界缺陷已修复并复核）
- [ ] PRD 状态改为 `✅ 已完成` 并补充落地 commit

## Out Of Scope

- 不修改选股算法、候选排序、板块资金选择、市场环境结论或执行对象。
- 不引入券商下单、自动交易、融资或超过 2x/100% 的账户模型。
- 不重写正式历史日报或数据库历史事实。
- 不清理当前工作区其他任务的修改，不改动 07-17 选择性暂存范围。

## Root Cause

- **现象**：结构化 `position_pct=50` 的对象在日报和日志中显示为满仓；默认 1x 旧仓被保存为 100%，2x 被解释为 200%。
- **根因**：早期把“账户满仓/空仓模式”与“计划仓位档”合并为同一语义；运行时用字符串替换修补表面冲突，后续测试把错误输出固化。后来的半仓规则只更新了文档和局部代码，没有传播到继承、暴露、渲染和验收层。
- **影响范围**：前日报旧仓继承、同股 T、不同股交叉持仓、完整/摘要日报、日志、Bear HTML、持仓策略、验收检查和 LLM Wiki。

## Reproduction

1. 构造最终对象与 `position_decision.target_position_pct=50`。
2. 运行日报 runtime。
3. 预期：`1x/50%条件执行`；实际：`满仓条件执行`，结构化 50% 文案被删除。
4. 构造 `previous_report_target_default_1x`；预期继承 50%，实际被归一为 100%。

## Fix Strategy

- **修改点**：仓位换算契约、前日报继承、账户暴露、runtime 可见归一、首页/策略、验收检查、Wiki/LLM 上下文及相关测试。
- **修改方式**：用结构化仓位字段取代字符串推断；移除 50%→满仓改写；历史默认1x按来源修复为50%；为新暴露产物写显式每腿与汇总字段。
- **风险评估**：高。该问题跨越账户事实、最终动作和多个用户可见产物，必须用测试先行和跨层逐字段对比控制风险。

## Regression Guard

- 新增三档换算单测、历史坏数据修复、同股/不同股汇总、Markdown/stdout/Bear 一致性和验收冲突测试。
- 保留一个弱环境 `position_pct=50` 的端到端反例，证明观察/环境文案不能把 B1 升为满仓。
- 提交前比较修复前后最终对象、交易窗口和取消条件，确保没有越界改变选股。

## Technical Notes

### 参考来源

- 用户 2026-07-18 明确确认的 0/1x/2x 仓位定义
- `.trellis/spec/backend/daily-report-decision-loop.md`
- `wiki/交易思想/实际账户情况.md`
- `wiki/交易思想/日报术语契约.md`
- `research/root-cause.md`

### 影响区域

- `scripts/report/position_context.py` — 默认1x旧仓归一
- `scripts/report/runtime.py` — 暴露结构与可见仓位传播
- `scripts/report/front_page_v2_renderer.py` — 账户暴露展示
- `scripts/report/report_acceptance_audit.py` — 跨层一致性检查
- `scripts/knowledge/llm_wiki_context.py` / `llm_wiki_router.py` — 知识契约
- `wiki/交易思想/*.md` / `.trellis/spec/backend/daily-report-decision-loop.md` — 业务与工程规格

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_position_tier_contract tests.test_position_action_semantics`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_front_page_v2_renderer tests.test_position_strategy_report tests.test_two_layer_decision_payload tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output tests.test_llm_wiki_context tests.test_llm_wiki_router`
- `git diff --check`

2026-07-19 实际结果：上述 3 组命令共 1029 项测试通过（32 + 776 + 221）；`tests.test_elimination_tournament` 与 `tests.test_two_layer_decision_payload` 完整模块各 45 项通过；Python 3.14 `py_compile`、工作区与暂存区 diff 检查通过。三个 v2 场景逐字段保留最终对象、原定窗口、执行条件和取消条件；非法中间比例、旧仓小数越档、显式缓存档绕过、盘前复核宽松消费和两层缺仓位默认半仓均有回归保护。

## 落地 commit

待实现后回填。
