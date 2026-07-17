# 受控 Agent Memory Vault 试点

状态：✅ 验证完成，待归档

## Goal

为 Codex 与 Claude 建立一个受控、可复核、可停止使用的长期记忆试点，解决跨会话遗忘、重复解释和通用经验无法复用的问题，同时保证长期记忆不会成为日报事实、交易知识或正式动作的第二来源。

## User Story

- **角色**：同时使用 Codex、Claude、Trellis 和项目 LLM Wiki 的个人交易系统维护者。
- **场景**：开始一个新会话时，需要快速找回用户偏好、跨项目决定和可复用工作流；结束重要任务时，需要把少量稳定结论留给后续会话。
- **目标**：只读取少量相关原文，明确记忆来源、复核日期和适用范围；过期、重复、冲突或未经复核的内容不进入当前判断。
- **成功标准**：试点能找回有用的跨会话信息，同时不复制项目事实、不进入日报生成、不改变选股、仓位、B1/B2 或退出动作。

## What I Already Know

- 当前项目已经由 Trellis 管理任务、规格与实现记录，由项目 Wiki 管理交易知识，由 `knowledge_manifest.v1` 和 `knowledge_trace.v1` 管理日报的目标日引用。
- 当前项目已有受 Git 管理的 `vault/`，它只保存日报项目内的跨会话工作记忆索引，并明确不替代 Wiki、Trellis、报告或快照；新的私有 Vault 不得复制这一层正文。
- `agent-memory-vault` 以 Markdown 为正式事实源，以 SQLite/FTS 为检索层，可选使用向量检索，并提供写入前对账、会话认领、closeout、audit 和 Doctor。
- 外部仓库的 40 个基础测试已使用本项目固定 Python 3.14 解释器通过，但出现 SQLite 连接未关闭提醒；其公开 CI 只覆盖 Python 3.11/3.12。
- 普通搜索会写入脱敏查询日志；closeout 可修改 SQLite、刷新派生索引并可选择执行 Git 提交，因此不能默认视为只读工具。
- 当前日报工作区包含大量未提交修改；本任务不得把外部代码直接混入日报运行链，也不得覆盖既有改动。
- 已共同确认的方向是先做独立、受控试点，不启用向量检索、自动 Hook、自动写入或自动提交。

## Requirements

- [x] R1: 建立唯一的跨 Agent、跨项目长期记忆事实目录；Markdown 是正式事实，SQLite/FTS 只是可重建索引，派生数据不得进入日报仓库的正式历史产物。
- [x] R2: 明确事实归属：Trellis 保存项目任务与实现决定，项目 Wiki 保存交易知识，项目 `vault/` 保存日报项目工作记忆索引，日报快照保存目标日事实，私有 Vault 只保存跨 Agent 用户偏好、跨项目决定、通用工作流和 Agent 案例。
- [x] R3: Vault 不保存当天行情、账户仓位、日报正文、聊天全文、Trellis 任务进度或项目 Wiki 正文副本；项目相关记忆只允许保存短摘要和正式来源路径。
- [x] R4: 会话开始检索默认使用结构化字段和关键词，最多返回 3 个候选；任何候选在使用前必须回读 Markdown 原文，不能仅凭摘要或相似度成为当前事实。
- [x] R5: 正式写入必须先对账，结果只能是新增、更新、跳过、标记过时、需要人工合并或询问用户；冲突内容不得自动合并，模型输出不得自动写回正式记忆。
- [x] R6: 每份正式记忆至少记录类型、范围、项目、状态、敏感级别、最近复核日期、复核周期、来源与更新者；过期或已归档内容默认不参与当前检索。
- [x] R7: 首版禁用向量检索、自动 Stop Hook、周期自动化、自动 Git 提交和日报运行时调用；所有写入、索引刷新和 closeout 必须由用户或 Agent 显式发起。
- [x] R8: 所有试点 Python 命令和测试使用 `.generated/venv-py314/bin/python3.14` 或独立安装后明确绑定的 Python 3.14，不能依赖未固定的 `python3`。
- [x] R9: 私有 Markdown、SQLite、查询日志、模型文件和其他派生数据不得提交到当前日报 Git 仓库；敏感内容和凭证必须在写入前被拒绝。
- [x] R10: 建立最小检索验收集，至少覆盖正确召回、过期内容排除、项目范围隔离、冲突内容说明、Top 3 上限和日报决定字段不受影响。
- [x] R11: 试点提供明确的停用与清理说明；停用后不影响 Trellis、项目 Wiki、日报生成或历史 replay。
- [x] R12: 日报任务文档、受控源码和私有 Markdown 分别使用独立 Git 归属；私有 Vault 仓库只跟踪 Markdown 与仓库规则，不纳入 runtime、SQLite、日志或模型文件。

## Non-functional Requirements

### 准确性

- 精确字段和关键词检索优先于语义召回。
- 每条使用中的记忆都能追到 Markdown 原文和复核日期。
- 重复文件不能因为出现次数更多而获得更高可信度。

### 隐私

- 正式记忆和派生索引默认保存在本机私有目录。
- 搜索日志不保存查询原文；日志与索引不得进入项目 Git。
- API key、token、cookie、密码、私密聊天全文和未脱敏账户数据不得写入 Vault。

### 可维护性

- 首版不引入向量模型、外部服务或新的日报运行依赖。
- 每周维护目标不超过 10 分钟；超出时应缩小记忆范围，而不是继续增加自动化。

### 兼容性

- 基础功能必须在 Python 3.14 下通过测试。
- 当前试点以 macOS 为运行环境；不得假定外部仓库的所有 Hook 和跨平台行为已经适配。

## Source Of Truth

| 内容 | 唯一事实来源 |
|------|--------------|
| 当前任务、实现计划、项目规格 | 当前项目 Trellis 与项目文档 |
| 交易原则、反证、适用范围 | 当前项目 Wiki 与运行知识清单 |
| 日报项目跨会话工作记忆索引 | 当前项目 `vault/` |
| 目标日行情、账户与日报引用 | 快照、正式日报产物、manifest 与 trace |
| 跨 Agent 用户偏好、跨项目决定、通用经验 | Agent Memory Vault |
| 临时讨论、猜测、原始聊天 | 不进入长期事实层 |

如 Vault 与项目正式来源冲突，以项目正式来源为准，同时把 Vault 条目标记为需要复核，不静默覆盖任一来源。

## Error Handling Strategy

| 场景 | 处理方式 | 用户可见结果 |
|------|----------|--------------|
| 记忆缺少来源或复核日期 | 不作为当前事实使用 | 说明资料不完整，需要复核 |
| 检索命中过期或归档内容 | 从默认结果排除 | 不注入当前上下文 |
| 新旧记忆冲突 | 保留两者并停止自动写入 | 提示需要人工选择当前有效结论 |
| 搜索或索引不可用 | 回退为显式路径读取 | 不影响日报和 Trellis |
| 发现敏感内容 | 拒绝写入正式记忆 | 说明具体敏感类型，不回显秘密 |
| closeout 发现无关脏文件 | 排除并停止自动提交 | 保留工作区，要求人工处理 |

## Acceptance Criteria

- [x] AC-R1-1: 删除 SQLite/FTS 派生数据后，可以仅凭 Markdown 重建同等基础索引。
- [x] AC-R2-1: 用一组代表性文件证明 Trellis、项目 Wiki、日报快照与 Vault 之间没有同一正文的重复事实副本。
- [x] AC-R3-1: 对当天行情、账户仓位、聊天全文和项目 Wiki 正文样本，写入检查均拒绝或要求改为正式来源路径。
- [x] AC-R4-1: 默认检索最多返回 3 条，并为每条返回原文路径、类型、状态和复核日期。
- [x] AC-R4-2: 检索结果使用前会重新读取原文；只有摘要而原文缺失时不得继续使用。
- [x] AC-R5-1: 重复或冲突写入分别产生跳过、更新或人工合并说明，不自动生成第二份有效事实。
- [x] AC-R6-1: 缺少必填元数据、已过期或已归档的样本不能进入默认当前检索。
- [x] AC-R7-1: 默认配置中向量检索、Hook、周期自动化和 Git 提交均处于关闭状态。
- [x] AC-R8-1: Python 3.14 下基础检查和试点新增测试全部通过，且不会使用其他解释器。
- [x] AC-R9-1: `git status` 证明私有记忆、SQLite、日志和派生数据未进入日报仓库变更列表。
- [x] AC-R10-1: 固定验收查询覆盖正确召回、过期排除、范围隔离和冲突说明，并输出可重复结果。
- [x] AC-R10-2: 启用和停用试点前后，日报正式决定字段及 replay 行为保持一致。
- [x] AC-R11-1: 按停用说明移除入口后，Trellis、Wiki lint、日报相关测试仍能独立运行。
- [x] AC-R12-1: 三个仓库均与各自私有远端同步；受控源码保留公开上游用于同步，私有 Vault 的已跟踪文件仅为 Markdown 与 `.gitignore`。

## Definition Of Done

- [x] PRD、技术设计和实现清单已完成并与用户确认
- [x] 代码与私有数据落点已经明确，不存在两套正式事实
- [x] 最小试点已实现，默认配置保持受控范围
- [x] Python 3.14 相关测试、检索验收和隐私检查通过
- [x] 已证明试点不进入日报运行链，不改变正式决定与 replay
- [x] 修改文件与现有大工作区改动已明确区分
- [x] 已完成 5 个独立真实任务会话、10 次只读检索，并决定继续关键词检索，不启用向量、Hook 或自动化
- [x] 试点落地 commit 已回填并同步；提交前已按用户确认执行
- [x] 日报任务的既有落地提交、受控源码和私有 Markdown 已分别同步到对应私有远端；本轮 I14 与验证记录按收尾流程单独提交

## Out Of Scope

- 不把 `agent-memory-vault` 整套代码直接复制进日报生成模块。
- 不修改候选池、评分、最终对象、仓位、B1/B2、退出动作或历史 replay 逻辑。
- 不引入向量数据库、embedding 模型、外部搜索服务或 MCP 服务。
- 不自动迁移现有 Trellis、AGENTS、Wiki、日报或聊天历史。
- 不扫描 `reports/`、`snapshots/`、账户原始数据或其他敏感历史产物。
- 不启用由 closeout、Hook 或周期任务触发的自动 Git 提交或自动推送。
- 不在本任务中解决外部仓库全部跨平台、许可证归属或向量依赖问题。

## Resolved Decisions

- RD1: 可维护源码使用 `/Users/chaixixi/Projects/agent-memory-vault` 独立本地 clone，并在独立分支上修改。
- RD2: 私人 Markdown 使用 `/Users/chaixixi/.local/share/agent-memory-vault`；runtime、SQLite、配置和日志使用 `/Users/chaixixi/.config/agent-memory`。
- RD3: 日报仓库只保留本 Trellis 任务文档，不添加 Memory Vault 运行依赖，不修改现有项目 `vault/`。
- RD4: 日报任务文档推送到 `shilianmalaxiangguo/a-daily-report`；受控源码推送到私有 `shilianmalaxiangguo/agent-memory-vault`，并保留 `mcncarl/agent-memory-vault` 为 `upstream`。
- RD5: 私有 Markdown 使用独立 private 仓库 `shilianmalaxiangguo/agent-memory-private`；只人工提交 Markdown，不提交或自动推送派生数据。

## Verification

- 使用固定 Python 3.14 运行外部基础测试与试点新增测试。
- 对默认配置执行检索、写入对账、过期排除、冲突说明和敏感内容拒绝测试。
- 检查私有目录、派生索引和搜索日志没有进入日报 Git。
- 运行当前项目 Wiki lint 和正式决定相关最窄测试，证明试点没有改变日报行为。
- 检查三个仓库的上游跟踪状态，并运行 Doctor 验证私有 Markdown 的 Git 基线与远端备份。
- 执行 `git diff --check`，并按本任务文件清单检查范围。

## Notes

- 外部参考：`https://github.com/mcncarl/agent-memory-vault`
- 相关任务：`.trellis/tasks/07-17-llm-wiki-provenance-decision-quality/`
- 实现前需要 `design.md` 与 `implement.md`；正式落点已由用户确认。

## 落地 commit

- 外部源码：`a397da16e1112a059a1c90a014c783eb7c3d6688`（`Add controlled Agent Memory safeguards`），已推送到私有 `origin/codex/controlled-memory-pilot`。
- 私有 Markdown：`1457d35`（`Initialize controlled Agent Memory vault`），已推送到 `origin/main`；仅跟踪 25 份 Markdown 与 `.gitignore`。
- 日报任务文档首个落地提交：`675bae7c`（`docs(task): record controlled agent memory pilot`），已推送到 `origin/develop`。
- runtime 已从外部源码提交 `a397da16e1112a059a1c90a014c783eb7c3d6688` 重新安装；安装清单记录 `source_dirty=false`，18/18 个文件匹配。
- 日报仓库后续仍只提交本 Trellis 任务目录；本次远端补充记录的提交 hash 在完成后的交付说明中记录。
