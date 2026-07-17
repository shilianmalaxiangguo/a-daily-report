# Design: 受控 Agent Memory Vault 试点

## Scope And Boundaries

本设计建立三套物理隔离、职责单一的目录：

1. `/Users/chaixixi/Projects/agent-memory-vault`：可维护源码 clone，只保存程序、模板、测试和公开文档。
2. `/Users/chaixixi/.local/share/agent-memory-vault`：私人 Markdown 正式记忆，不保存派生数据库和模型。
3. `/Users/chaixixi/.config/agent-memory`：本机 runtime、TOML、策略 JSON、SQLite、日志和报告，不提交到项目 Git。

当前日报仓库只修改 `.trellis/tasks/07-17-controlled-agent-memory-vault-pilot/`。现有 `vault/`、Wiki、Trellis、日报代码、报告和快照均不接入私有 runtime。

## Contracts / Data Flow

### 1. 事实归属

```text
日报项目事实
  ├─ Trellis：任务、规格、开发记录
  ├─ wiki：稳定交易知识
  ├─ project vault：日报项目工作记忆索引
  └─ reports/snapshots：目标日证据与产物

私有 Agent Memory Vault
  ├─ 用户长期偏好
  ├─ 跨项目短指针
  ├─ 通用工作流与架构决定
  └─ Agent 案例
```

私有 Vault 可以链接到项目正式来源，但不能复制正文。项目生成链不反向读取私有 Vault。

### 2. 安全 CLI 默认值

- `search` 默认最多返回 3 条。
- `search` 默认不写搜索日志；只有显式参数才记录脱敏日志。
- `memoryctl closeout` 无参数时追加 `--dry-run`，不再追加 `--commit`。
- 显式 `--commit` 保持可用，但本次试点不执行。
- `prewrite` 继续只做写入前对账，不修改 Markdown。

### 3. 受控内容策略

新增机器可读策略文件，最小字段包括：

- 允许的 `memory_type` 与 `status`。
- 正式记忆必填 frontmatter。
- 默认排除的非当前状态。
- 需要 `source_paths` 的跨项目指针类型。
- 复核日期与复核周期要求。
- 单文件大小上限与敏感内容处理。

策略校验复用现有轻量 frontmatter 语法，只接受简单标量和列表。策略文件保存在 runtime config；公开仓库提供无私人信息的示例。

### 4. 检索资格

默认检索需要同时满足：

- `status=active`。
- 记忆类型和 Agent 范围符合查询。
- 原文仍存在。
- `verified_at + review_after_days` 尚未到复核日期。
- 结构化过滤完成后才进行结果截断。

到复核日期的内容可以通过显式参数查询，但不能默认进入当前上下文。

### 5. 写入与敏感内容

- 写入前先运行 `prewrite`。
- 敏感模式命中时仍使用 `ASK_USER` 这一兼容动作，但命令返回失败并标记不可继续。
- 正式 Markdown 在索引或 closeout 前通过策略与秘密扫描。
- 新旧内容冲突只报告人工合并，不自动覆盖或生成第二份当前事实。

### 6. 本机配置

TOML 使用绝对路径，并把 runtime Python 与语义 Python 都绑定到：

`/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/.generated/venv-py314/bin/python3.14`

默认配置：

- `commit_scoped_memory_files = false`
- `semantic_retrieval.enabled = false`
- `run_vector_index_after_closeout = false`
- 不安装 Hook，不创建周期任务，不下载 embedding 模型。

### 7. 初始私有内容

bootstrap 只创建空白模板。首批额外内容只包括：

- 一个跨项目指针，指向日报项目 `vault/README.md`、Wiki 入口和 Trellis 任务目录。
- 一份“为什么首版不启用向量、Hook 和自动提交”的架构决定。

不迁移历史聊天、日报、账户、Wiki 正文或 Trellis 任务正文。

## Compatibility / Migration

- 无策略配置时，公开仓库原有基础行为保持兼容；受控策略由本机配置显式启用。
- 新增 CLI 参数为追加式；已有显式 `--limit`、`--commit` 和日志迁移行为保持有效。
- runtime 安装使用来源内容指纹；源码修改后需要显式重新安装并验证，不自动覆盖本机配置。
- 现有项目 `vault/` 不迁移、不重命名、不加入私有索引。

## Tradeoffs

### 选择独立 clone，而不是 vendoring

避免外部源码、许可证和运行依赖进入日报大工作区；代价是需要维护一次显式 runtime 更新。

### 选择关键词检索，而不是向量检索

首版优先保证来源、复核和范围准确；代价是同义表达召回较弱，但可以通过稳定关键词补足。

### 选择默认无日志

减少无意写状态和查询元数据积累；代价是暂时缺少检索使用统计，后续可在明确需要时显式开启。

### 选择过期默认排除

降低旧记忆污染当前判断；代价是需要定期复核，否则有价值内容会暂时不参与默认检索。

## Rollout

1. 在独立 clone 上先写失败测试并完成安全改造。
2. 运行全部基础测试与新增测试。
3. 创建私有 Vault 与 runtime 配置，初始化 SQLite。
4. 写入两条受控初始记忆并重建索引。
5. 运行固定检索验收、策略检查、Doctor 与安装指纹验证。
6. 运行日报 Wiki 与 replay 的最窄验证，证明没有接入运行链。

## Rollback / Roll-forward

- 停用只需要停止调用独立 runtime；日报项目不依赖它。
- 私有 Markdown 是唯一需要保留的数据，SQLite、日志和 runtime 均可重建。
- 不自动删除任何目录。若用户未来决定清理，应先备份 Markdown，再分别处理源码、私有数据和 runtime。
- 后续向量检索、Hook 或自动化必须作为独立任务重新评估，不能在本试点中顺带启用。
