# Research: 1x/2x仓位语义串位根因

## Question

为什么结构化 `position_pct=50` 最终显示为满仓，为什么默认1x旧仓被保存为100%，以及如何防止同类问题再次发生？

## Sources

- `scripts/report/runtime.py`
- `scripts/report/position_context.py`
- `scripts/report/report_acceptance_audit.py`
- `wiki/交易思想/实际账户情况.md`
- `.trellis/spec/backend/daily-report-decision-loop.md`
- `tests/test_report_runtime.py`
- `tests/test_position_action_semantics.py`
- commits `2f4815e3`、`fcc128a62`、`92cfe6f3`

## Findings

### 1. Root Cause Category

- **Category A - Missing Spec**：早期没有明确区分计划仓位档、x档和实际仓位。
- **Category B - Cross-Layer Contract**：结构化50%经过 runtime 文本归一后变成满仓，而持仓策略仍保留50%。
- **Category C - Change Propagation Failure**：后续 Wiki 已规定50%不升满仓，但没有传播到旧仓继承、暴露、渲染和验收。
- **Category D - Test Coverage Gap**：测试保护了错误输出，缺少同一50%输入贯穿 selection、Markdown、HTML和验收的字段一致性断言。
- **Category E - Implicit Assumption**：把旧的“满仓/空仓账户模式”错误泛化为“1x=满仓、2x=200%”，再用字符串替换掩盖结构冲突。

### 2. Proven Failure Path

```text
selection_workflow.final.position_pct=50
  -> position_decision.target_position_pct=50
  -> final_target_resolution保持50
  -> _normalize_full_or_empty_account_visible_lines()
  -> _full_or_empty_account_visible_text()
  -> 50%条件执行被替换成满仓条件执行
  -> Markdown/stdout错误
  -> Bear HTML忠实继承错误Markdown
  -> acceptance audit把错误满仓输出当成正确结果
```

默认旧仓的另一条错误路径：

```text
previous_report_target_default_1x
  -> normalize_inferred_previous_target_records()
  -> position/default_position_pct/holding.position_pct强写100
  -> full_or_empty_exposure.v1把单腿称为1x满仓
  -> 两腿称为2x/200%
```

### 3. Why Earlier Fixes Failed

1. 06-24 任务只要求盘前决定、盘中执行或取消，并明确保留50%/100%三档；满仓替换超出了需求。
2. 07-14 任务修旧仓动作时沿用了1x=100%的旧假设，且明确不改新仓仓位，因此没有审计旧文本归一器。
3. 后续通过增加字符串替换和验收断言消除表面文案冲突，实际把错误固化到了更多层。

### 4. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|----------|-----------|-----------------|--------|
| P0 | Architecture | 建立0/1x/2x与0/50/100的纯结构化换算契约 | DONE |
| P0 | Test Coverage | 增加50%跨 selection/runtime/Markdown/HTML/audit 一致性反例 | DONE |
| P0 | Runtime | 验收拒绝50%与满仓、1x与100%、2x与200%的同对象组合 | DONE |
| P1 | Documentation | 更新 backend spec、账户、做T和术语 Wiki | DONE |
| P1 | Compatibility | 历史默认1x来源修复为50%，显式真实100%保持不变 | DONE |

### 5. Systematic Expansion

- **Similar Issues**：前日报继承、同股T、不同股交叉持仓、账户日序表、持仓策略、LLM知识注入。
- **Design Improvement**：每腿和汇总都同时保存 `position_pct` 与 `position_x`，不再由布尔存在性推断比例。
- **Process Improvement**：涉及仓位语义时必须比较结构化决定、Markdown、HTML和验收四层，不接受只改文案测试。

## Recommendation

新增仓位契约和显式暴露 v2，删除50%→满仓字符串升档；按历史来源修复默认1x为50%；用跨层测试和验收冲突检查防止复发。

## Impact

- PRD: 明确唯一仓位字典、历史兼容和不改选股边界。
- Design: 引入纯换算契约与显式每腿/汇总暴露字段。
- Implementation: 必须测试先行，并同时修改继承、runtime、验收、Wiki与知识上下文。
