# 超短节奏复位与边际主线反推

状态：✅ 已完成

## Goal

把本次关于太极实业、空仓、节奏复位和边际主线反推的讨论沉淀为可复用的 Wiki 口径，并在日报选股链路中新增 `rhythm_reset_review.v1` 解释层，使最终 0% 仍能批改候选与次日复核路径，但不改写既有最终动作。

## User Story

- **角色**：超短日报使用者
- **场景**：日报最终给出 0% 时，用户怀疑不是防守正确，而是节奏踏错、新主线延后确认或旧目标尾端处理错误。
- **目标**：在不事后倒灌涨跌、不把观察对象升级为明日目标的前提下，解释为什么当日不能做、次日需要什么条件才恢复执行资格。
- **成功标准**：报告前台能看到“超短边际节奏复核”，并且 `Tb明日目标` / `明日执行对象` 仍只来自原最终动作。

### 用户旅程

1. 用户看到最终 0% → 系统展示 0% 分类：防守空仓、节奏复位空仓、延后确认空仓或错失待批改。
2. 用户查看复核行 → 系统说明复核对象为什么需要批改、为什么 T0 不能做、T+1 需要什么条件才恢复执行资格。
3. 用户复盘次日 → 系统只把事实用于批改与下一份日报，不回写 T0 结论。

## What I Already Know

- 本任务只修选股解释和复核，不改 B1/B2、同股T、临时2x、仓位买法或旧仓卖出规则。
- 当前报告已有 `sector_capital_preflight.v1` 和 T0/T+1/T+2 推演，适合作为解释层载体。
- `selection_workflow.final` 和 `final_target_resolution` 已经是最终动作来源；新结构只能解释和批改，不能覆盖它们。
- 外盘默认是噪音；只有同链事件、海外定价、亚洲确认、A股映射、标的暴露度同时成立，才进入 T+1 复核。
- 2026-07-06 默认应解释为“空仓复位 + 明日市场强者复核”；太极实业只能作为旧目标尾端和旧节奏占用批改，不能被倒推成 T0 答案。
- 若周一最终为空仓且复核对象来自周五旧信号，必须批改周五选股、买点、持仓预期和退出纪律；周二再强只算重新取得比较资格，不能替周五或周一结论正名。

## Requirements

- [x] R1: 更新 LLM Wiki，把“公共合理 vs 超短边际”“节奏复位空仓”“合理不是超额收益来源”和外盘主线传导复核写入稳定口径。
- [x] R2: 更新 LLM Wiki context/router，使“节奏踏错、同手同脚、合理空仓、边际主线、外盘拉升、存储大涨、旧目标强弩之末”等表达能命中相关知识。
- [x] R3: 新增 `rhythm_reset_review.v1`，支持 `防守空仓`、`节奏复位空仓`、`延后确认空仓`、`错失待批改` 四类结论。
- [x] R4: 报告前台新增“超短边际节奏复核”表，展示候选可能性、T0 不做原因、T+1 恢复执行资格条件。
- [x] R5: 最终 0% 时，复核候选不得写成 `Tb明日目标`、`明日执行对象` 或覆盖 `selection_workflow.final`。
- [x] R6: 太极实业这类周五旧信号不能只做周一复核；最终 0% 时必须追溯周五信号源是否已经尾端化，并把周二再强限定为重新比较。

## Non-functional Requirements

### 兼容性
- 沿用既有 Markdown 报告、runtime payload 和 unittest 模式。

### 可审计性
- 新 payload 必须能从已有运行时事实派生；缺少事实时保守记录为复核，不编造 T0 资格。

### 用户可见语言
- 遵守 `wiki/交易思想/日报术语契约.md`，用户可见文字使用条件、资格、可做、参与、不参与等交易语言。

## Acceptance Criteria

- [x] AC-R1-1: Wiki 文档包含公共合理、超短边际、节奏复位空仓和外盘完整传导链进入 T+1 复核的说明。
- [x] AC-R2-1: `tests.test_llm_wiki_router` 能验证“节奏踏错/外盘存储/合理空仓/同手同脚”命中新路由。
- [x] AC-R2-2: `tests.test_llm_wiki_context` 能验证新增短句进入 compact context，且不引入用户可见禁用词。
- [x] AC-R3-1: 2026-07-06 最终 0% 的构造样本生成 `节奏复位空仓` 且附带 `延后确认空仓`，首行是空仓复位，太极实业只作为旧信号源批改。
- [x] AC-R4-1: 宜宾纸业强势但主线未确认时，只进入延后确认复核，不成为明日执行对象。
- [x] AC-R4-2: 外盘存储强但 A 股未确认时，只进入 T+1 复核路径，不新增参与。
- [x] AC-R5-1: 最终 0% 时，报告前台仍保留 `Tb明日目标 | 空仓` 和 `明日执行对象 | 无`。
- [x] AC-R6-1: 2026-07-06 太极实业复核行渲染为旧信号源批改，说明周五买点、周一继续做旧目标不能由周二再强倒推正名。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] 本任务为 PRD-only 任务记录；不补 design/implement，因实现沿用既有解释 payload 和 renderer 模式。
- [x] 新增或更新测试通过。
- [x] 指定 Python 3.14 验证命令已运行并记录结果。
- [x] PRD 状态改为 `✅ 已完成` 并补充落地 commit；若用户未要求提交，则落地 commit 写“未提交”。

## Out Of Scope

- 不修改 B1/B2、同股T、临时2x 或任何仓位买法规则。
- 不把外盘从噪音升级为直接买入理由。
- 不用事后涨跌倒灌 T0 结论。
- 不指定太极实业、宜宾纸业或任何单票为“正确答案”。
- 不重构日报主链路、候选池排序或最终动作生成。

## Technical Notes

### 参考来源
- 用户 2026-07-06 关于太极实业、空仓、节奏踏错和边际主线反推的讨论。
- `wiki/交易思想/价格行为与能量框架.md`
- `wiki/板块补充/板块中枢与主线延续.md`
- `.trellis/spec/backend/daily-report-decision-loop.md`

### 影响区域
- `wiki/交易思想/价格行为与能量框架.md` — 交易思想沉淀。
- `wiki/板块补充/板块中枢与主线延续.md` — 外盘与主线传导复核口径。
- `wiki/README.md` — Wiki 路由说明。
- `scripts/knowledge/llm_wiki_context.py` — compact context 短句。
- `scripts/knowledge/llm_wiki_router.py` — 知识路由项。
- `scripts/report/runtime.py` — `rhythm_reset_review.v1` 构建、存储和前台渲染。
- `tests/` — Wiki 与报告复核回归。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_router tests.test_llm_wiki_context`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-07-06_A股日报_完整版.md`

## 落地 commit

未提交
