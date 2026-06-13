# PRD 撰写格式指南

> **目的**：为 Trellis 任务 PRD 提供结构化模板。核心思路是「通用骨架 + 按任务类型增量」——写全骨架则需求不漏，只加相关增量则 PRD 不臃肿。

---

## 使用方式

1. **所有任务**先写 Part 1（通用骨架）——这些章节无论什么任务都要有
2. **根据任务类型**从 Part 2 选取对应的增量章节——一个任务可能同时匹配多种类型（如「新建功能 + UI」），把相关增量都加上
3. **实现完成后**回填「落地 commit」

## 与 Trellis 工作流对齐

- `task.py create` 只生成最小 PRD seed（`Goal` / `Requirements` / `Acceptance Criteria` / `Notes`）；新建任务后必须按本指南扩展成完整 PRD。
- `prd.md` 只写需求、约束、验收标准和必要背景；不要把技术设计、架构取舍或执行 checklist 放进 PRD。
- 复杂任务必须补 `design.md` 和 `implement.md`：`design.md` 写边界、契约、数据流、兼容/回滚；`implement.md` 写有序执行步骤、验证命令和回滚点。
- 如果一个任务包含 3 个以上可独立验收的交付物，或交付物可以独立实现/检查/归档，优先拆成 parent + child tasks。
- Parent PRD 负责源需求、任务地图、跨子任务验收和最终集成检查；child PRD 负责可独立验收的具体交付。
- PRD 状态行使用人类可读状态：`⏳ 待开工`、`🔨 进行中`、`✅ 已完成`。不要把 `task.json.status` 的 `planning/in_progress/completed` 原样写进 PRD。
- Requirements 和 Acceptance Criteria 必须使用稳定 ID（如 `R1`、`AC-R1-1`），便于实现、检查和完成后勾选。

## 任务目录产物契约

| 文件 / 目录 | 什么时候需要 | 职责 | 禁止 |
|-------------|--------------|------|------|
| `task.json` | `task.py create` 自动生成 | 任务元数据、状态、父子关系、提交信息 | 手写替代脚本能维护的字段 |
| `prd.md` | 所有任务必须 | 目标、背景、需求、约束、验收、验证方式 | 技术设计、执行 checklist、临时聊天结论 |
| `research/*.md` | 有技术不确定性、外部 API/库、历史任务/源码考证时 | 保存研究问题、来源、发现、结论和对需求/设计的影响 | 只把研究结果留在聊天里 |
| `design.md` | 复杂任务必须 | 技术边界、数据流、契约、兼容/迁移、取舍、回滚形态 | 逐步执行 checklist |
| `implement.md` | 复杂任务必须 | 有序实现步骤、验证命令、风险文件、回滚点、review checkpoint | 需求原文、未决产品问题 |
| `implement.jsonl` | 子代理模式或需要预加载上下文时 | 实现阶段要先读的 spec / research 清单 | 代码文件路径、将要修改的文件 |
| `check.jsonl` | 子代理模式或需要预加载检查上下文时 | 检查阶段要先读的 spec / research 清单 | 代码文件路径、将要修改的文件 |

`research/`、`design.md`、`implement.md` 可以在需求探索中反复更新。进入实现前，复杂任务必须已经具备完整 `prd.md`、`design.md`、`implement.md`；轻量任务可以注明 PRD-only。

## 配套产物最小模板

### Research Artifact

每个研究主题一个文件，例如 `research/auth-library-comparison.md`：

```markdown
# Research: <主题>

## Question

<要回答的具体问题>

## Sources

- <源码/文档/历史任务/外部资料路径或链接>

## Findings

- <可验证发现 1>
- <可验证发现 2>

## Recommendation

<推荐结论，以及为什么>

## Impact

- PRD: <是否改变需求/验收>
- Design: <是否影响技术方案>
- Implementation: <是否影响执行顺序/验证命令>
```

### Design Artifact

复杂任务的 `design.md` 至少覆盖：

```markdown
# Design: <任务名>

## Scope And Boundaries

## Contracts / Data Flow

## Compatibility / Migration

## Tradeoffs

## Rollback / Roll-forward
```

### Implementation Artifact

复杂任务的 `implement.md` 至少覆盖：

```markdown
# Implementation: <任务名>

## Prerequisites

## Ordered Checklist

- [ ] I1: <实现步骤>
- [ ] I2: <实现步骤>

## Validation Commands

- `<命令>`

## Risk And Rollback Points

## Review Checkpoints
```

### JSONL Context Manifests

`implement.jsonl` / `check.jsonl` 是上下文清单，不是计划文档。每行一个 JSON 对象：

```jsonl
{"file": ".trellis/spec/frontend/index.md", "reason": "Frontend conventions for this task"}
{"file": ".trellis/tasks/<task>/research/<topic>.md", "reason": "Research decision used by implementation"}
```

规则：
- 只放 spec / research 文件或目录。
- 不放将要修改的代码文件；实现/检查阶段自己按任务读取源码。
- `implement.jsonl` 面向实现所需上下文；`check.jsonl` 面向质量检查所需上下文。
- `task.py create` 生成的 `_example` seed 不是有效条目；有真实条目后可以删除。

---

# Part 1：通用骨架（所有任务必须）

## 1. Title + 状态

```markdown
# <任务名称>

状态：⏳ 待开工 | 🔨 进行中 | ✅ 已完成
```

新建 PRD 默认写 `状态：⏳ 待开工`。任务启动后可改为 `🔨 进行中`，实现、验证、提交完成后改为 `✅ 已完成`。

## 2. Goal

一段话说清目标。不写实现细节，只写「要达成什么、为什么」。

```markdown
## Goal

<一句话描述要达成什么，以及为什么现在做>
```

- 对齐类：「将 X 对齐 Y 的字段契约」
- 新建类：「为 Z 角色提供 W 能力，解决当前的 V 痛点」
- Bug 类：「修复 X 场景下 Y 的异常，根因是 Z」
- 性能类：「将 X 操作的 P99 从 A 降到 B」

## 3. User Story / User Journey

谁是用户，在什么场景下，要完成什么，成功的标准是什么。

```markdown
## User Story

- **角色**：<谁>
- **场景**：<在什么情况下>
- **目标**：<要达成什么>
- **成功标准**：<怎样算做完>

### 用户旅程

1. 用户 <动作> → 系统 <响应>
2. 用户 <动作> → 系统 <响应>
3. ...
```

> 即使纯后端/基础设施任务，也写清「谁」——可能是前端开发者、其他服务、运维。

## 4. What I Already Know

前置知识，格式：`关键事实`，每项一行。目的是让接手者快速建立上下文，避免反复查证。

```markdown
## What I Already Know

- <当前系统的相关模块现状>
- <上游/外部依赖的已知行为>
- <已知的约束或坑>
- <本任务不涉及的边界>
```

## 5. Requirements

Checklist 形式，每项具体可验证。使用稳定 ID，禁止「完善 X」「优化 Y」等模糊词。

```markdown
## Requirements

- [ ] R1: <具体要做的事 1>
- [ ] R2: <具体要做的事 2>
```

复杂需求可使用 `R1.1`、`R1.2` 做子项，但顶层 `R1` 仍应代表一个可验收的交付面。

好的写法：「R1: 用户提交表单后 3 秒内看到结果」vs 坏的写法：「优化用户体验」

## 6. Non-functional Requirements

```markdown
## Non-functional Requirements

### 性能
- <关键路径的延迟/吞吐量约束>

### 安全
- <权限、数据脱敏、注入防护>

### 兼容性
- <浏览器/Node 版本、依赖版本范围>

### 可访问性（前端）
- <键盘导航、屏幕阅读器、色彩对比度>
```

如果没有特殊要求，至少写一句「无额外约束，沿用项目默认标准」。

## 7. Acceptance Criteria

Checklist，与 Requirements 建立 ID 映射但更可度量。每个 Requirement 至少有一个 Acceptance Criterion；不要出现无法追溯到 Requirement 的孤立验收项。

```markdown
## Acceptance Criteria

- [ ] AC-R1-1: 给定 <X 条件>，当 <Y 操作>，则 <Z 结果>
- [ ] AC-R2-1: 给定 <X 条件>，当 <Y 操作>，则 <Z 结果>
```

## 8. Definition Of Done

```markdown
## Definition Of Done

- [ ] Requirements 全部完成
- [ ] Acceptance Criteria 全部通过
- [ ] 复杂任务的 `design.md` / `implement.md` 已补齐并通过 review（轻量任务注明 PRD-only）
- [ ] 必要 research 已保存到 `research/`，不是只留在聊天中
- [ ] 需要预加载上下文时，`implement.jsonl` / `check.jsonl` 已配置 spec / research 清单
- [ ] 测试通过（含新增测试）
- [ ] lint / typecheck 通过
- [ ] PRD 状态改为 `✅ 已完成` 并补充落地 commit
```

## 9. Out Of Scope

明确不做什么。每项一行。

```markdown
## Out Of Scope

- 不 <做什么>
- 不 <做什么>
```

## 10. Technical Notes

参考来源和影响区域：

```markdown
## Technical Notes

### 参考来源
- <文档/源码/协议/设计稿>

### 影响区域
- `path/to/file.ts` — <简述影响>
```

## 11. Verification

```markdown
## Verification

- <typecheck 命令>
- <lint 命令>
- <测试命令>
- <额外验证命令>
```

## 12. 落地 commit

实现完成后回填：

```markdown
## 落地 commit

<commit-hash>
```

---

# Part 2：按任务类型增量

> 一个任务可能匹配多种类型——把相关增量的章节全部加进 PRD，不相关的跳过。

---

## 类型 A：Schema / 字段对齐 / 数据迁移

数据库 schema 变更、字段重命名、上游对齐、破坏性迁移。

### A1. Source Of Truth

```markdown
## Source Of Truth

只以 <上游源码 / 协议文档 / 设计规范> 和当前系统源码为依据。
如果后续发现冲突，以 <优先级最高的来源> 为准。
```

### A2. Destructive Naming Policy

```markdown
## Destructive Naming Policy

本任务不保留旧表/字段/API 的向后兼容，直接按 <参考来源> 重建。

命名规则：
- 业务契约名以 <参考来源> 的命名风格为准
- API / 前端字段使用契约名的直接映射
- 数据库列名使用 <命名风格> 派生
- 数据库表名使用 <模块名> 派生命名

旧字段不兼容、不保留、不 alias。
```

### A3. Domain Model / Field Contract

```markdown
## <Domain> Field Contract

### 公共字段

所有实体均包含：
- `<CommonField>`：中文说明

本系统额外保留技术列：`id`、`<parent_id>`、`created_at`、`updated_at`。

### EntityName / 中文名

字段来源：`<SourceFile>` + `<MetaFile>`。

业务可写字段：
- `<Field>`：中文说明 | 类型 | 约束

系统分配字段（不应由外部输入）：
- `<SystemField>`：说明

计算属性（不落库）：
- `<ComputedField>`：派生自 `<SourceField>`

旧字段映射：
| 旧名 | 新名 | 动作 |
|------|------|------|
| `old_field` | `new_field` | 重命名 |
| `dead_field` | — | 移除 |
```

### A4. Enumerations And Validation

```markdown
## Enumerations And Validation

- `<EnumField>` 只能是：`值1`、`值2`、`值3`
- `<NumericField>` 必须为正整数
- `<DependentField>` 由 `<ParentField>` 决定候选范围
```

### A5. Dependency / Generation Flow

```markdown
## Dependency And Generation Flow

- EntityA 依赖 Dep1 + Dep2
- EntityB 依赖 Dep1 + Dep2 + EntityA

链路约束：
- 每层保存时记录上游版本快照
- 生成顺序：Dep1 → Dep2 → EntityA → EntityB
```

---

## 类型 B：新建功能（前后端通用）

从零实现一个功能模块。

### B1. API / Service Contract

```markdown
## API Contract

### `METHOD /api/<path>`

请求：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `<field>` | `<type>` | 是/否 | `<说明>` |

响应：
| 字段 | 类型 | 说明 |
|------|------|------|
| `<field>` | `<type>` | `<说明>` |

错误码：
| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | <条件> |
| 404 | <条件> |
| 500 | 服务端异常 |
```

### B2. Error Handling Strategy

```markdown
## Error Handling Strategy

| 层级 | 策略 |
|------|------|
| API | 统一错误码，敏感信息不泄露到响应体 |
| Service | 业务异常抛自定义 Error，带错误码和可安全展示的 message |
| UI | 网络异常→toast+重试按钮；业务异常→内联提示；未知异常→全局兜底 |
| 日志 | 服务端 error 级日志含 stack trace；客户端异常上报到 <平台> |
```

---

## 类型 C：UI / 交互

前端页面、组件、交互流程。

### C1. Interaction States Matrix

```markdown
## Interaction States

| 状态 | 展示 | 用户可操作 |
|------|------|-----------|
| Loading | <骨架屏/spinner/说明> | <取消？> |
| Empty（无数据） | <空状态插图和文案> | <引导操作> |
| Normal | <正常展示> | <全部操作> |
| Error | <错误信息和重试> | <重试/返回> |
| Disabled | <置灰+说明> | 无 |
| Optimistic Update | <即时反馈> | <撤销？> |
```

### C2. Accessibility

```markdown
## Accessibility

- 键盘导航：Tab 序、Enter/Space 激活、Escape 关闭
- 屏幕阅读器：关键元素有 aria-label / role
- 色彩对比度：≥ 4.5:1（正文）
- 焦点管理：弹窗打开时焦点移入，关闭时焦点还原
```

### C3. Responsive / Breakpoints（如适用）

```markdown
## Responsive Breakpoints

| 断点 | 宽度 | 布局 |
|------|------|------|
| Mobile | < 768px | <描述> |
| Tablet | 768–1024px | <描述> |
| Desktop | > 1024px | <描述> |
```

---

## 类型 D：性能优化

### D1. Baseline & Target Metrics

```markdown
## Metrics

| 指标 | 基线（当前） | 目标 | 测量方式 |
|------|------------|------|----------|
| P50 | <值> | <值> | <工具> |
| P99 | <值> | <值> | <工具> |
| TTFB | <值> | <值> | <工具> |
| Bundle Size | <值> | <值> | <工具> |
```

### D2. Load / Stress Test Plan

```markdown
## Test Plan

- 场景：<并发数> 并发，持续 <时长>
- 预期：错误率 < X%，P99 < Yms
- 工具：<k6 / artillery / wrk / lighthouse>
```

---

## 类型 E：API 集成（第三方/外部服务）

### E1. Integration Contract

```markdown
## Integration Contract

| 项目 | 值 |
|------|----|
| Provider | <服务名> |
| Base URL | <url> |
| Auth | <API Key / OAuth2 / mTLS> |
| Rate Limit | <N req/s> |
| Timeout | <ms> |
| Retry | <次数> 次，退避策略 <fixed/exponential> |
| Idempotency | <幂等键 / 不需要> |
```

### E2. Failure Modes

```markdown
## Failure Modes

| 场景 | 降级策略 | 用户可见 |
|------|----------|----------|
| 超时 | <兜底值 / 跳过后台重试> | <提示/无感知> |
| 限流 | <排队 / 拒绝并提示稍后重试> | <提示> |
| 服务不可用 | <熔断 + 兜底> | <提示> |
```

---

## 类型 F：Bug 修复

### F1. Root Cause

```markdown
## Root Cause

- **现象**：<用户看到什么>
- **根因**：<代码/数据/时序层面出了什么问题>
- **影响范围**：<哪些用户/场景>
```

### F2. Reproduction

```markdown
## Reproduction

1. <步骤 1>
2. <步骤 2>
3. 预期：<X>，实际：<Y>
```

### F3. Fix Strategy

```markdown
## Fix Strategy

- **修改点**：<文件/函数>
- **修改方式**：<简述>
- **风险评估**：<低/中/高，说明理由>
```

### F4. Regression Guard

```markdown
## Regression Guard

- 新增测试：`<测试文件/用例名>`
- 覆盖场景：<正常/边界/异常>
```

---

## 类型 G：运维 / 部署

### G1. Environment Variables

```markdown
## Environment Variables

| Key | 环境 | 必填 | 说明 |
|-----|------|------|------|
| `<KEY>` | 全环境 | 是 | <说明> |
| `<KEY>` | 仅生产 | 否 | <说明，默认值> |
```

### G2. Rollback / Roll-forward

```markdown
## Rollback Plan

- **回滚方式**：<git revert / 重新部署旧版 / 特性开关关闭>
- **回滚影响**：<数据兼容？/ 用户可见？>
- **前置条件**：<数据库迁移已做向下兼容？>

## Roll-forward Plan（如不回滚）

- <修 forward 的步骤>
```

### G3. Monitoring

```markdown
## Monitoring

| 信号 | 告警条件 | 通知方式 |
|------|----------|----------|
| 错误率 | > X% | <渠道> |
| 延迟 | P99 > Yms | <渠道> |
```

---

## 类型 H：复杂多交付任务

当任务涉及 3 个以上独立模块、多个可独立验收交付物，或需要 parent / child task 管理时使用。

### H1. Delivery Slices / Task Breakdown

```markdown
## Delivery Slices

| Slice / Child Task | 交付物 | 是否可独立验收 | 对应 Requirement | 对应 Acceptance Criteria |
|--------------------|--------|----------------|------------------|--------------------------|
| `<slice-or-task>` | <具体交付> | 是/否 | `R1` | `AC-R1-1`, `AC-R1-2` |

拆分规则：
- 可独立实现、检查、回滚或归档的交付物，优先拆 child task。
- Parent PRD 只保留源需求、任务地图、跨子任务验收和最终集成检查。
- Child PRD 写自己的 Requirements / Acceptance Criteria / Verification。
- 执行顺序、实现 checklist、验证命令和回滚点写入 `implement.md`，不要写在 PRD。
```

### H2. Dependency Flow（如适用）

```markdown
## Dependency Flow

- ModuleA 依赖 Dep1 + Dep2
- ModuleB 依赖 Dep1 + ModuleA

执行顺序：Dep1 → Dep2 → ModuleA → ModuleB
```

---

# 任务类型速查

| 我的任务 | 通用骨架 | 加这些增量类型 |
|----------|----------|--------------|
| 从零加一个 CRUD 模块 | ✅ | B（新建功能） |
| 对齐上游字段契约 | ✅ | A（字段对齐） |
| 写一个新页面 | ✅ | B + C（新建功能 + UI） |
| 优化列表页加载速度 | ✅ | D（性能） |
| 接入微信支付 | ✅ | B + E（新建功能 + API 集成） |
| 修一个数据不一致 bug | ✅ | F（Bug 修复） |
| 数据库迁移 + API 重写 | ✅ | A + B（字段对齐 + 新建功能） |
| 上线新服务 | ✅ | G（部署） |
| 重构跨多模块业务链路 | ✅ | A + H（字段对齐 + 复杂多交付） |

---

# 通用质量检查

PRD 写完之前确认：

- [ ] Goal 一句话说清目标了吗？
- [ ] User Story 写清了谁在什么场景下做什么吗？
- [ ] Requirements 具体可验证吗（不是「完善 X」）？
- [ ] Requirements 是否有稳定 ID（`R1`、`R2`）？
- [ ] Non-functional 写了吗（至少一句「沿用默认标准」）？
- [ ] Acceptance Criteria 可以交给别人独立验收吗？
- [ ] 每条 Acceptance Criteria 是否映射到 Requirement（如 `AC-R1-1`）？
- [ ] Out Of Scope 足够窄吗（防止范围蔓延）？
- [ ] Technical Notes 列出了参考来源和影响区域吗？
- [ ] 复杂任务是否已把设计放入 `design.md`、执行计划放入 `implement.md`？
- [ ] 多交付物任务是否考虑 parent / child task 拆分？
- [ ] 按任务类型取的增量章节都加了吗？不相关的跳了吗？

---

## 相关

- [Trellis 工作流](../../workflow.md) — Phase 1.1 需求探索流程
