---
name: task-mode
description: Use when 需要判断任务应直接言出法随执行、进入 Trellis、使用 grill-me，或处理 Trellis 遗留工作
---

# 统筹任务

## 核心原则

默认 Plan。小任务言出法随直接完成，复杂任务才升级到 Trellis；方案不稳、判断困难或业务口径需要压测时，再叠加 grill-me。不要因为工具存在就把简单请求变成重流程。

## 使用入口

- 不清楚任务大小：先用 `$task-mode`，输出推荐模式、理由、下一步动作。
- 已经清楚任务大小：可说“按 Plan 做”“这是轻量改动”“按 Trellis 做”“先 grill 我”，也可用 `/plan`、`/trellis`、`/grill`、`/legacy-trellis` 这类短口令表达自然语言意图。
- 一个请求包含多个目标、任务大小不明、影响范围不清，或用户问“应该怎么做”：自动先做任务统筹。
- 短口令代表执行模式，不等于真实系统命令，也不等于自动启动额外工具；是否进入 Trellis、使用 grill-me 或 subagent，仍按分流表判断。
- 如果短口令明显偏重或偏轻，先用中文说明原因，再采用更合适的模式。

## 本地流程覆写

### 任务分级

- Plan：单文件或小范围修改、明确 bug 修复、配置调整、文案修改、小测试补充。默认直接定位代码并实现；只在关键不确定点提问，首次最多 1 个问题。
- Trellis：中型任务。需要项目规范、任务记录、知识沉淀或质量检查时，使用 Trellis 的任务/spec/check 流程，在当前分支执行；需要 review 时优先 inline self-review。
- Trellis + Grill：大型任务、方案不稳任务、业务判断任务。先用 grill-me 压清楚目标、边界、反例和取舍，再用 Trellis 落任务、计划、执行和检查。

### 绕过重流程的自然语言意图

用户表达以下意思时，按轻量路径处理，除非实际风险明显更高：

- “这是轻量改动，不进入完整任务流程。”
- “已知上下文充分，不要重复问 AGENTS.md 或项目说明里已经回答过的问题。”
- “如果觉得需要 review，改用 inline self-review，不要派评审子代理。”

如果实际任务牵涉共享契约、数据源、存储、业务主链路、候选池、推理或生成链路，先用中文说明为什么升级，再按 Trellis 或 Trellis + Grill 处理。

### 头脑风暴

- 用户明确要求头脑风暴，或关键设计取舍会实质改变结果时，使用独立的 `brainstorming` skill。
- 不需要设计取舍的简单任务继续按 Plan 直接执行。
- 设计获确认后，回到本 skill 的 Plan / Trellis / Grill 分流继续执行。

## 复合任务拆分

遇到复合任务时，先拆成最少数量的可验证子任务，再给每个子任务单独标模式：

| 字段 | 写法 |
|---|---|
| 子任务 | 一句话说明要做什么 |
| 模式 | Plan / Trellis / Trellis + Grill / Grill / Legacy Trellis |
| 执行者 | 本地直接做，或在用户明确允许时交给 subagent |
| 上下文 | 该子任务自己的目标、范围、非目标、验证、限制、输出 |

执行规则：

- Plan 子任务直接做，不等待整体计划变重。
- Trellis 子任务先写中文小 checklist，再执行。
- Trellis + Grill 子任务先用 grill-me 拷问，再用 Trellis 执行。
- Grill 子任务只处理方案判断，不混入执行；需要执行时再回到 Plan 或 Trellis。
- Legacy Trellis 子任务只处理 `.trellis` 遗留内容。
- 如果子任务执行中发现影响范围变大，立即重新标模式，并用中文说明原因。

## Worktree、spec 与提交

- 非用户明确要求，不默认创建 worktree。
- 已经在原生隔离工作区内时，不再叠加 `git worktree add`。
- spec / plan 可以落盘；提交到 git 前必须问用户。
- 非用户明确要求，不修改 git 历史，不推送远程。

## Subagent 与 review

- subagent 只有用户明确允许代理、并行或 subagent 工作时才用。
- 如果平台不支持 subagent，回退到主线程串行执行，并用中文说明。
- 子代理基于具体 commit 工作时，必须用 `git switch -c <branch> <sha>` 或等价方式创建分支，不要裸切到提交。
- 子代理长时间没有回报时，主动打断并报告停滞原因。
- Plan 和 Trellis 的 review 优先 inline self-review；只有用户明确允许代理或并行，且任务天然独立时，才考虑评审子代理。
- 如果 review 异常慢，跳过子代理 review 或改用 inline self-review，并报告原因。

## 高风险操作

以下操作不受轻量覆写影响，必须先确认：

- 删除文件。
- 大规模重构。
- 修改 git 历史。
- 推送远程。
- 改环境配置。
- 改 CI。
- 数据库变更。

## 分流表

| 模式 | 适用任务 | 执行方式 |
|---|---|---|
| Plan | 单文件、小文案、清晰 bug、小配置、可直接验证的规则补丁 | 言出法随直接做，跑最窄验证；不创建 Trellis 任务，不写规格文档，不拆 subagent |
| Trellis | 多文件但边界清楚、局部逻辑、沿用现有模式的扩展，或需要规范/任务记录/知识沉淀/质量检查 | 先用中文写范围、风险、验证；按 Trellis 任务/spec/check 流程推进 |
| Trellis + Grill | 新功能、跨模块重构、共享契约、数据源、存储、业务主链路、候选池、推理或生成链路，或方案需要反例拷问 | 先用 grill-me 把目标、边界、反例和取舍问清楚，再用 Trellis 执行 |
| Grill | 用户要求“拷问我 / grill me / 这个方案对吗 / 判断方案”，或当前方案需要先判断是否成立 | 使用 grill-me 追问和压测决策；先把方案判断清楚，再决定是否进入 Plan 或 Trellis |
| Legacy Trellis | `.trellis` 旧任务、旧文档、迁移、兼容性维护 | 只在处理 Trellis 遗留内容时使用，不作为新任务的主流程 |

## 中文输出约束

- Goal、In Scope、Out of Scope、Non-goals、Done Definition、Verification 必须用中文写给用户看。
- 所有人可见 Todo、任务拆分、子任务说明、subagent 提示词、审计结论、复盘摘要必须中文。
- `docs/brainstorming/specs/` 或其他规格文档必须中文；如果模板是英文，保存前改成本仓库可读的中文。
- Trellis + Grill 里也不是自动拆 subagent；只有用户明确允许代理或并行代理，且任务天然独立时才拆。

## 中文任务上下文

进入 Trellis / Trellis + Grill，或用户明确允许 subagent 时，给后续执行者带入这份上下文：

- 模式：Plan / Trellis / Trellis + Grill / Grill / Legacy Trellis。
- 目标：这次要完成什么。
- 范围：只做哪些文件、模块或行为。
- 非目标：明确不做哪些扩展、重构或迁移。
- 验证：用什么命令、检查或人工审阅证明完成。
- 限制：中文输出、禁止扩大范围、不要覆盖他人改动。
- 输出：需要返回的结论、文件路径、风险和剩余问题。

## 常见例子

- “改一个标题”“补一条提示词规则”“补一条 AGENTS 小规则”：Plan。
- “修一个清晰 bug”：通常是 Trellis；如果只有单点改动且可直接验证，可以按 Plan。
- “新增业务规则”“调整推理或生成主链路”“重构数据源契约”：Trellis + Grill。
- “你拷问下这个方案”“这个架构方案对吗”：Grill。
- “清理 Trellis 旧任务”“迁移 .trellis 文档”：Legacy Trellis。
