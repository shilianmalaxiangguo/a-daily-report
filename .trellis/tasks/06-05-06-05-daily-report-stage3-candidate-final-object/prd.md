# 日报 Stage 3：候选池到最终对象身份一致性

状态：✅ 代码与产物已完成，待提交

## Goal

重写日报候选池到最终对象的表达契约，让前台最终对象、T-006 今日判断、候选过程证据和附录推导都能说明同一条选择逻辑：谁是最终对象、谁只是过程候选、为什么这个对象胜出或保持观察。

## User Story

- **角色**：每日复盘和次日计划使用者。
- **场景**：用户阅读 A 股日报，看到多个候选同时出现，例如 `中船特气(688146)` 和 `双星新材(002585)`。
- **目标**：用户能一眼区分最终观察对象、明日执行对象、过程候选和待验证样本，并知道为什么未胜出的票不能替代最终对象。
- **成功标准**：报告前台不再出现“最终对象是 A，但 T-006 又把 B 写成核心候选”的冲突；附录仍保留 B 的过程证据和降级原因。

### 用户旅程

1. 用户打开日报前台 → 系统先展示最终对象和次日动作。
2. 用户查看 T-006 今日判断 → 系统只展示具备最终解析支持的核心候选；如果最终结果只是观察或等待，则显示 `待补事实`。
3. 用户查看候选推导和附录 → 系统展示未胜出候选的来源、五维差异、降级原因和过程身份。
4. 用户复盘具体争议票 → 系统能解释“为什么是中船特气观察、双星新材只保留过程观察”，而不是只说“未被最终解析选中”。

## What I Already Know

- 当前 Stage 3 任务原始 PRD 只描述了候选池 verdict 和五维对比，未按项目 PRD 新规范展开完整需求与验收。
- 项目 PRD 规范位于 `.trellis/spec/guides/prd-format.md`，要求 PRD 使用通用骨架、稳定需求 ID 和验收 ID。
- 现有 `sniper_target_derivation` 已经能存储 canonical target，但部分前台表格仍可能从 `best_stock`、候选池、同日记录或旧候选字段取对象。
- 2026-06-10 正式日报旧产物里，前台最终对象是 `中船特气(688146)`，但 T-006 今日判断把 `双星新材(002585)` 写成核心候选判断。
- `中船特气` 和 `双星新材` 都来自 `extreme_conviction_list`，但两者都被降级；双星可以出现在过程证据和候选观察样本里，不能冒充最终对象。
- 2026-06-10 已新增补丁 spec：`.trellis/tasks/06-05-06-05-daily-report-stage3-candidate-final-object/spec-2026-06-10-final-object-identity.md`。
- 2026-06-11 已把 Mermaid 页中的 P0/P1 全量关闭要求纳入补充 spec：`.trellis/tasks/06-05-06-05-daily-report-stage3-candidate-final-object/spec-2026-06-11-p0-p1-closure.md`。

## Requirements

- [x] R1: 建立候选池到最终对象的统一身份契约，区分最终观察对象、明日执行对象、过程候选、待验证样本。
- [x] R2: 候选池 verdict 必须用同一组五维标准比较胜出对象和重要未胜出对象：主线/板块、个股结构、资金确认、账户适配、风险/缺失。
- [x] R3: 前台最终对象、最终标的解题过程、T-006 今日判断和附录最终对象必须引用同一个最终解析结果。
- [x] R4: T-006 今日判断不得从 `best_stock`、候选池、同日记录回填已经不是最终对象的过程候选。
- [x] R5: 当最终结果为等待、旧仓优先或仅观察时，T-006 核心候选应显示 `待补事实`，过程候选保留在推导和附录中。
- [x] R6: 重要未胜出候选必须渲染具体差异原因，不能只写“未被最终解析选中”。
- [x] R7: 回归测试必须覆盖 2026-06-10 中船特气 / 双星新材场景，以及既有上海石化 / 豫能控股类错配场景。
- [x] R8: 生成或 replay 日报后，最终对象、T-006 和候选过程证据必须通过一致性检查。
- [x] R9: Mermaid 页列出的 P1 防回归项必须进入任务验收：正式入口、HTML 职责边界、全文术语检查、历史 replay 来源日期。

## Non-functional Requirements

### 性能

- 不新增实时外部查询来修正最终对象身份；只使用当前运行期已有数据、目标日期快照或 replay 数据。

### 安全

- 无额外安全要求，沿用项目默认标准。

### 兼容性

- 保留已有候选过程证据和附录信息，不删除候选池来源字段。
- 不能破坏已有 `sniper_target_derivation`、`two_layer_decision_payload`、`decision_statistics` 的公开输出结构。

### 用户可见文字

- 日报正文、测试名、PRD 和诊断输出必须遵守 `wiki/交易思想/日报术语契约.md`。

## Acceptance Criteria

- [x] AC-R1-1: 给定候选池同时包含最终对象和未胜出候选，当报告渲染前台结论时，则最终对象只显示最终解析出的对象。
- [x] AC-R1-2: 给定未胜出候选仍有强势形态，当报告渲染过程证据时，则该候选带有过程身份，而不是最终对象身份。
- [x] AC-R2-1: 给定至少两个候选进入同一候选池，当生成 verdict 时，则每个重要候选都有五维字段和最终差异说明。
- [x] AC-R3-1: 给定最终解析结果为观察对象，当渲染前台最终对象和附录最终对象时，则两处对象一致。
- [x] AC-R4-1: 给定 `best_stock` 为 `双星新材(002585)` 且最终解析为等待 / 仅观察，当渲染 T-006 今日判断时，则 T-006 不显示双星新材为核心候选。
- [x] AC-R5-1: 给定最终解析没有明日执行对象，当渲染 T-006 今日判断时，则核心候选显示 `待补事实`。
- [x] AC-R6-1: 给定 `双星新材(002585)` 未胜出，当渲染候选推导时，则说明其主线/板块、资金确认、账户适配或风险缺失中的具体弱点。
- [x] AC-R7-1: 给定回归测试运行，当覆盖 2026-06-10 形态时，则测试证明过程候选不能绕过最终解析进入 T-006。
- [x] AC-R8-1: 给定日报重新生成成功，当运行一致性检查时，则最终对象、T-006 和附录最终对象没有身份冲突。
- [x] AC-R9-1: 给定主入口生成日报，当一致性检查未通过时，则不保存 Markdown、Bear HTML 或事实同步结果。
- [x] AC-R9-2: 给定 Bear HTML 与结构化 HTML 同时存在，当主入口保存阅读版时，则 Bear HTML 由最终 Markdown 生成，结构化 HTML 不覆盖阅读版口径。
- [x] AC-R9-3: 给定整篇 Markdown 任意位置出现旧工程口径，当运行一致性检查时，则检查失败。
- [x] AC-R9-4: 给定 replay 历史行情无目标日期证明，当回补失败或日期不符时，则保留缺失并记录降级，不用当前数据填历史日期。

## Definition Of Done

- [x] Requirements 全部完成或明确拆到后续 child task。
- [x] Acceptance Criteria 全部通过。
- [x] 复杂剩余工作补齐 `design.md` / `implement.md`；2026-06-10 P0 补丁允许 PRD-only 记录，因为实现已落在 runtime 和回归测试。
- [x] 必要研究结论保存到 `research/` 或本 PRD 的 `What I Already Know`。
- [x] `implement.jsonl` / `check.jsonl` 包含相关 spec / research 清单。
- [x] 新增和既有相关测试通过。
- [x] 生成或 replay 目标日报，并运行一致性检查；若外部数据源不可用，必须说明未完成的整报验证风险。
- [ ] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 不重写市场、资金、板块、仓位阶段的排序逻辑；Stage 2 负责这些上游结论。
- 不重写候选数据采集、实时行情采集或 replay 回补系统。
- 不改 Bear HTML 和 Mermaid HTML 的视觉样式。
- 不迁移正式入口；本任务只把入口并存、HTML 职责、全文术语和历史来源日期纳入防回归验收。
- 不把观察对象包装成明日新增参与对象。

## Technical Notes

### 参考来源

- `.trellis/spec/guides/prd-format.md` — PRD 写作规范。
- `.trellis/spec/backend/daily-report-decision-loop.md` — 日报判断、预演、复盘和前台对象契约。
- `.trellis/spec/backend/quality-guidelines.md` — 日报候选、最终对象和用户可见文字质量要求。
- `.trellis/tasks/06-05-06-05-daily-report-stage3-candidate-final-object/research/explorer-stage3.md` — Stage 3 只读探索结论。
- `.trellis/tasks/06-05-06-05-daily-report-stage3-candidate-final-object/spec-2026-06-10-final-object-identity.md` — 2026-06-10 P0 补丁 spec。
- `.trellis/tasks/06-05-06-05-daily-report-stage3-candidate-final-object/spec-2026-06-11-p0-p1-closure.md` — Mermaid 页 P0/P1 全量关闭 spec。

### 影响区域

- `scripts/report/runtime.py` — 最终解析、T-006 当前上下文、前台对象存储。
- `scripts/report/decision_statistics.py` — 今日判断行的候选读取与过滤。
- `scripts/report/sniper_target_derivation.py` — canonical target 与推导链。
- `scripts/report/two_layer_decision_payload.py` — 前台决策层和候选过程层。
- `scripts/report/candidate_quality_renderer.py` — 候选过程证据渲染。
- `scripts/report/report_acceptance_audit.py` — 最终对象一致性检查。
- `tests/test_report_runtime.py` — runtime 回归测试。
- `tests/test_decision_statistics.py` — T-006 和判断统计回归测试。
- `tests/test_two_layer_decision_payload.py`、`tests/test_candidate_quality_renderer.py`、`tests/test_report_acceptance_audit.py` — 后续 Stage 3 扩展测试。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_decision_statistics`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_candidate_quality_renderer tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-10`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-10_A股日报_完整版.md`

## Root Cause

- **现象**：2026-06-10 日报前台最终对象为 `中船特气(688146)`，T-006 今日判断却显示 `双星新材(002585)` 为核心候选。
- **根因**：最终对象解析和 T-006 今日判断读取对象的来源不同。最终对象来自最终解析结果，T-006 可能从 `best_stock`、候选池或同日记录取到过程候选。
- **影响范围**：凡是最终结果为等待、旧仓优先、仅观察，且过程候选里仍有强势票的日报，都可能出现前台身份冲突。

## Reproduction

1. 使用 2026-06-10 的候选上下文：`中船特气(688146)` 和 `双星新材(002585)` 都来自 `extreme_conviction_list`。
2. 最终解析保留 `中船特气` 为观察对象，明日执行对象为空。
3. `best_stock` 或过程候选仍携带 `双星新材`。
4. 预期：T-006 核心候选为 `待补事实`，双星只出现在过程证据。
5. 实际旧产物：T-006 核心候选显示 `双星新材(002585)`。

## Fix Strategy

- **修改点**：`scripts/report/runtime.py` 的当前判断上下文构造。
- **修改方式**：T-006 当前核心候选先读取最终解析结果；最终解析为等待、旧仓优先或仅观察时，不再从 `best_stock`、候选池或同日记录回填核心候选。
- **风险评估**：中等。改动集中，但会影响所有前台 T-006 今日判断，因此必须保留既有主对象优先测试和观察样本过滤测试。

## Regression Guard

- 新增测试：`tests.test_report_runtime.ReportRuntimeTest.test_daily_judgment_front_panel_ignores_best_stock_when_final_result_waits`
- 已有测试继续覆盖：
  - `tests.test_report_runtime.ReportRuntimeTest.test_daily_judgment_front_panel_uses_anchor_primary_not_same_day_observation_records`
  - `tests.test_decision_statistics.DecisionStatisticsTest.test_daily_panel_keeps_observation_candidates_out_of_core_judgment`

## Delivery Slices

| Slice / Child Task | 交付物 | 是否可独立验收 | 对应 Requirement | 对应 Acceptance Criteria |
|--------------------|--------|----------------|------------------|--------------------------|
| 2026-06-10 P0 补丁 | T-006 不再把过程候选写成核心候选 | 是 | `R3`, `R4`, `R5`, `R7` | `AC-R3-1`, `AC-R4-1`, `AC-R5-1`, `AC-R7-1` |
| 候选池 verdict | 同池五维对比和胜出/未胜出理由 | 是 | `R1`, `R2`, `R6` | `AC-R1-1`, `AC-R1-2`, `AC-R2-1`, `AC-R6-1` |
| 前台/附录一致性 | 前台最终对象、附录最终对象和过程证据身份一致 | 是 | `R3`, `R8` | `AC-R3-1`, `AC-R8-1` |
| 一致性检查 | 报告检查能发现最终对象与 T-006 冲突 | 是 | `R8` | `AC-R8-1` |
| P1 防回归关闭 | 正式入口、HTML 职责、全文术语、历史日期来源进入验收 | 是 | `R9` | `AC-R9-1` 至 `AC-R9-4` |

## Dependency Flow

- 上游候选池事实 → 最终解析结果 → 当前判断上下文 → T-006 今日判断。
- 上游候选池事实 → 候选池 verdict → 前台解题过程和附录过程证据。
- 最终解析结果和 verdict 必须先完成，渲染和一致性检查再消费它们。

## 落地 commit

待用户确认后提交并回填 commit。

## 执行记录

- 2026-06-10：修复 T-006 当前判断对象来源，最终前台结论无明日执行对象时，核心候选显示 `待补事实`，不再从 `best_stock`、过程候选或同日记录回填。
- 2026-06-10：补充保存后审计，能够识别“最终对象 / T-006 当前核心候选 / 无明日执行对象”之间的身份冲突。
- 2026-06-10：补充 ETF 趋势批量请求整体等待上限，避免整报生成因单个慢请求长期停住。
- 2026-06-10：已重新生成 `reports/2026-06-10_A股日报_完整版.md` 与 `reports/2026-06-10_A股日报_完整版.html`；保存后 `report_acceptance_audit` 通过。
- 2026-06-11：将 Mermaid 页 P0/P1 全量关闭要求写入补充 spec，并补充正式入口、HTML 职责、全文术语和 replay 日期来源的防回归验收。
