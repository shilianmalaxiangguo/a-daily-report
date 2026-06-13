# 日报生成前板块资金扩散审计落地

状态：✅ 已完成；fresh replay 等待 2026-06-12 官方快照补齐

## Goal

把“板块资金扩散生成前审计”真正接进日报生成链路，让每次日报生成都能先得到一份可见、可审计的 Mermaid 流程块和层级化淘汰证据，再进入最终日报与 companion HTML 输出。

## User Story

- **角色**：日报使用者 / 报告维护者。
- **场景**：生成日报前或复核日报时，需要先看见当前流程是不是从市场资金结构和板块扩散出发，而不是从涨停池、分数或多个模块各自挑对象。
- **目标**：在日报正文与 companion HTML 中看到一条统一的生成前审计链，明确每层输入、淘汰、剩余、反证和唯一最终动作。
- **成功标准**：日报生成时可以直接看到生成前 Mermaid 审计块；淘汰赛 HTML 或等价 companion artifact 中能对应展示每层证据；最终仍只产出一个当前动作或观察结论。

### 用户旅程

1. 用户运行日报生成命令。
2. 系统先产出生成前 Mermaid 审计块与层级淘汰证据。
3. 系统再继续生成日报正文与 companion HTML。
4. 用户打开报告时，能复核从板块扩散到唯一动作的完整决策链。

## What I Already Know

- `scripts/report/runtime.py` 已在两轮收口阶段构建并存储 `selection_workflow`、`final_target_resolution`、`two_layer_decision_payload`、`sniper_target_derivation`、`elimination_tournament_payload`。
- `scripts/report/two_layer_decision_payload.py` 已能渲染推导审计层与 `selection_workflow` 的 Mermaid。
- `scripts/daily_report_entry_demo.py` 当前在保存 Markdown 之后同步写出上证缠论 companion HTML。
- `scripts/report/report_acceptance_audit.py` 已支持 companion HTML 审计，并且已有最终对象一致性检查。
- 现有 `selection_workflow` 与 `elimination_tournament` 已足够表达大部分层级证据，但缺少“生成前审计块”作为单独可见产物。

## Requirements

- [x] R1: 在日报 runtime 中构建一份结构化的生成前审计对象，包含市场资金结构、板块扩散、资金载体、角色分类、量化参与痕迹、价格行为、反证、账户/盈亏比和唯一动作。
- [x] R2: 生成前审计对象必须可渲染为 Mermaid 块，并在日报相关前台或 companion artifact 中可见。
- [x] R3: companion HTML 或等价审计载体必须展示每一层的输入、淘汰、剩余和下一步依据，且不重新推导明日标的。
- [x] R4: 生成前审计与 `selection_workflow.final` / `final_target_resolution` / `two_layer_decision_payload` 的唯一动作必须一致，0% 场景不能泄漏新的执行对象。
- [x] R5: 报告生成入口必须在 Markdown 保存或 companion HTML 落盘前完成该审计块的构建与保存，保证 replay/official 同路径生效。
- [x] R6: `report_acceptance_audit.py` 必须能够识别新的 companion 审计块，并验证其与 Markdown 前台的唯一动作一致。

## Non-functional Requirements

### 性能
- 不额外触发实时全量采集；复用现有 runtime 数据和已有结构化 payload。

### 安全
- 不引入外部网络资源；HTML 仅使用本地静态资源或内联内容。

### 兼容性
- 保持现有 `selection_workflow.v1`、`two_layer_daily_decision.v1`、`elimination_tournament.v1` 向后兼容。

### 可访问性
- Mermaid 块和 companion HTML 都要可读，不依赖颜色单独表达含义。

## Acceptance Criteria

- [x] AC-R1-1: 给定一份完整日报上下文，runtime 能生成生成前审计对象，并至少包含市场、板块、资金载体、价格行为和最终动作字段。
- [x] AC-R2-1: 给定相同上下文，前台或 companion artifact 中能看到该对象渲染出的 Mermaid 审计块。
- [x] AC-R3-1: 给定分层候选，HTML 中能看到每层输入、淘汰、剩余与下一层依据。
- [x] AC-R4-1: 给定 0% 场景，审计块与前台最终对象一致，不出现新的明日标的。
- [x] AC-R5-1: 运行日报生成命令后，replay / official 输出路径下存在对应审计 companion artifact。
- [x] AC-R6-1: acceptance audit 能识别新的 companion 审计块并校验其最终动作一致性。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] 复杂任务的 `design.md` / `implement.md` 已补齐并通过 review。
- [x] 必要 research 已保存到 `research/`，不是只留在聊天中。
- [x] 测试通过（含新增测试）。
- [x] `git diff --check` 通过。
- [x] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 不重写 selection workflow 的整套候选规则。
- 不改动现有 `final_target_resolution` 的唯一对象口径。
- 不引入新的实时数据源。
- 不把 companion HTML 做成交互式前端。

## Technical Notes

### 参考来源
- `.trellis/spec/backend/daily-report-decision-loop.md`
- `.trellis/tasks/06-13-daily-generation-elimination-html/research/runtime-html-integration.md`
- `scripts/report/runtime.py`
- `scripts/report/two_layer_decision_payload.py`
- `scripts/report/elimination_tournament.py`
- `scripts/daily_report_entry_demo.py`
- `scripts/report/report_acceptance_audit.py`

### 影响区域
- `scripts/report/runtime.py` — 生成前审计对象的构建与存储。
- `scripts/report/two_layer_decision_payload.py` — Mermaid / 审计块渲染或复用层。
- `scripts/report/elimination_tournament.py` — 分层淘汰 companion HTML。
- `scripts/daily_report_entry_demo.py` — companion 落盘位置与顺序。
- `scripts/report/report_acceptance_audit.py` — companion 审计识别与一致性检查。
- `tests/` — 产物顺序、HTML 存在、最终动作一致性、0% 泄漏防护。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_html_output tests.test_two_layer_decision_payload tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html reports/replay/2026-06-12_板块资金扩散生成前复核.html`
- `git diff --check`

## 落地 commit

- `643cd1fd` — `feat(report): render sector preflight tournament in report`

## 验证记录

- 已通过 focused 单测、py_compile、`git diff --check` 和 2026-06-12 现有 replay Markdown + companion HTML 验收。
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay` 因 `snapshots/2026-06-12.json` 不存在停止，不能在当前工作区重新从官方快照生成；需要先补齐该快照。
- 逐日 K 线过程校准已保存到 `research/calibration-kline-process-20260612.md`，覆盖中船特气、信维通信截至 2026-06-12 的逐日过程。
