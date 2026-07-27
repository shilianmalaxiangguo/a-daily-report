# 问题定义优先原则

状态：🔨 实现、验证与审计已完成，等待提交授权

## Goal

把“定义问题的能力优先于提问与解决”落成日报和 LLM Wiki 都能执行、追溯与验证的长期原则，避免大模型在错误问题上快速生成看似完整的答案。

## User Story

- **角色**：使用 AI 工具维护 LLM Wiki、生成日报并持续复盘决定质量的个人交易者。
- **场景**：提出新任务、沉淀知识、修改日报规则或让 AI 解决复杂问题时。
- **目标**：先说清要改善的决定、事实边界、完成证据和不可改变项，再提问消除关键未知并完成最小可验证闭环。
- **成功标准**：仓库总规则、Wiki 正文和紧凑运行上下文表达同一原则，并由定向测试证明；交易决定逻辑保持不变。

### 用户旅程

1. 用户提出目标，执行者先定义需要改善的决定和完成证据。
2. 执行者只询问会实质改变判断或实现的未知，并完成最小可验证闭环。
3. 验证失败时，执行者先复核事实和问题定义，再决定是否修改方案或知识节点。

## What I Already Know

- `AGENTS.md` 已有 Goal、范围、非目标、完成定义和验证规则，但“问题定义优先”尚未作为统一上位原则集中表达。
- `wiki/交易思想/AI摩擦与知识复利.md` 已记录 AI 使用、反馈机制、知识复利和模仿学习原则，适合作为本原则的既有来源节点。
- `scripts/knowledge/llm_wiki_context.py` 通过 `FIELD_MAPPINGS` 向旧消费者暴露紧凑原则；该兼容层不自动成为可路由知识。
- 当前工作区已有等待提交授权的 LLM Wiki 候选；本任务只增加独立未暂存增量，不替换或清理既有修改。

## Requirements

- [x] R1: 在项目 `AGENTS.md` 增加“问题定义优先”的执行规则，明确决定、事实边界、完成证据、不可改变项、关键未知、最小闭环和失败复核顺序。
- [x] R2: 在 `AI摩擦与知识复利.md` 记录同一长期原则，并写清它不是无条件的能力排名，也不能用宏大问题、漂亮提问或快速答案代替真实反馈与验证。
- [x] R3: 在 LLM Wiki 紧凑上下文增加对应字段映射，不新增路由器、知识层或交易决定影响。
- [x] R4: 增加定向测试，证明 Wiki 原文与紧凑上下文都包含该原则及其边界。
- [x] R5: 在 Wiki 操作日志记录本次知识摄入和影响边界。

## Non-functional Requirements

### 兼容性

- 保留现有 `build_llm_wiki_context()` 返回结构和 `FIELD_MAPPINGS` 兼容行为。
- 不改变 `selection_workflow`、`final_target_resolution`、明日执行对象、仓位、B1/B2、旧仓处理或退出动作。

### 可靠性

- 所有 Python 验证使用 `.generated/venv-py314/bin/python3.14`。
- 改动只追加本任务内容，不覆盖当前工作区其他任务的暂存或未暂存修改。

## Acceptance Criteria

- [x] AC-R1-1: 阅读 `AGENTS.md` 时，可以直接找到“先定义需要改善的决定，再提问和解决”的可执行步骤，以及验证失败时回查事实和问题定义的要求。
- [x] AC-R2-1: `AI摩擦与知识复利.md` 同时包含问题定义优先公式、有效价值乘法关系和至少三条禁止误用边界。
- [x] AC-R3-1: `build_llm_wiki_context()["field_mappings"]` 包含问题定义优先、决定先于工具和验证失败复核三条紧凑表达，且不产生新的 manifest entry。
- [x] AC-R4-1: 定向单测使用 Python 3.14 通过，并验证项目规则、Wiki 正文、操作日志与字段映射的一致性。
- [x] AC-R5-1: `wiki/log.md` 以 `2026-07-20` 记录本次原则摄入，并明确只影响任务定义、知识整理与复盘，不直接改变交易动作。

## Definition Of Done

- [x] Requirements 全部完成
- [x] Acceptance Criteria 全部通过
- [x] 本任务为 PRD-only 轻量任务，不需要 `design.md` / `implement.md`
- [x] 无需新增 research；判断依据来自用户确认、现有 Wiki 和仓库契约
- [x] 不需要预加载上下文清单；主代理已读取适用规范
- [x] 定向测试和 Wiki 检查通过
- [x] 完成一轮独立提交前审计并修正发现
- [ ] PRD 状态更新为 `✅ 已完成`；提交仍需用户授权

## Out Of Scope

- 不新增 Wiki 页面、路由器、manifest 条目、知识子系统或外部依赖。
- 不修改候选池、评分、日报决定、仓位、B1/B2、买卖点、旧仓处理或退出动作。
- 不把“选择最大领域”“做给自己用”或“AI 必然创造更多就业”写成无条件真理。
- 不清理、格式化、暂存、提交或回滚当前工作区的其他修改。

## Technical Notes

### 参考来源

- `AGENTS.md`
- `wiki/交易思想/AI摩擦与知识复利.md`
- `.trellis/spec/backend/llm-wiki-provenance.md`
- `.trellis/tasks/07-17-llm-wiki-provenance-decision-quality/prd.md`

### 影响区域

- `AGENTS.md` — 项目级执行原则。
- `wiki/交易思想/AI摩擦与知识复利.md` — 长期知识正文。
- `scripts/knowledge/llm_wiki_context.py` — 兼容紧凑字段映射。
- `tests/test_llm_wiki_context.py` — 定向契约测试。
- `wiki/log.md` — 知识摄入记录。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context.LlmWikiContextTest.test_problem_definition_first_principle_enters_wiki_context`
- `.generated/venv-py314/bin/python3.14 scripts/knowledge/llm_wiki_lint.py`
- `.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py validate 07-20-problem-definition-first`
- `git diff --check`
- `git diff -- AGENTS.md wiki/交易思想/AI摩擦与知识复利.md scripts/knowledge/llm_wiki_context.py tests/test_llm_wiki_context.py wiki/log.md .trellis/tasks/07-20-problem-definition-first/`

## Completion Evidence

- 混合工作区：`tests.test_llm_wiki_context` 50 项通过。
- 混合工作区：Wiki 检查为 32 个运行条目、0 个错误、42 条既有来源元数据提醒。
- 隔离候选：以真实 39 路暂存候选为基线，只叠加本任务精确块后，`tests.test_llm_wiki_context` 48 项通过。
- 隔离候选：Wiki 检查为 25 个运行条目、0 个错误、37 条既有来源元数据提醒。
- `task.py validate 07-20-problem-definition-first` 通过，`git diff --check` 通过。
- 三名独立审计者分别检查内容边界、LLM Wiki 契约和提交范围；发现的交易语言问题已修正，混合文件提交隔离要求已写入 `commit-scope.md`。
- 当前真实暂存候选仍为 39 条路径，本任务没有执行暂存或提交。
- 本任务不更新 `.trellis/spec/`：没有新增或改变 API、数据结构、路由或跨层代码契约；既有 provenance spec 已明确 `FIELD_MAPPINGS` 只属于兼容上下文。本次长期原则已落在 `AGENTS.md` 与正式 Wiki 节点。

## 落地 commit

待提交；提交前需用户授权。
