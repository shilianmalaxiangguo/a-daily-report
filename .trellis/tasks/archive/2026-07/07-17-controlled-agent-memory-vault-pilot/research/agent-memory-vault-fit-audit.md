# Research: Agent Memory Vault 受控试点适配审计

## Question

如何在不复制日报项目事实、不进入日报运行链、不过度自动化的前提下，把 `mcncarl/agent-memory-vault` 改造成 Codex 与 Claude 可共用的长期记忆试点？

## Sources

- `https://github.com/mcncarl/agent-memory-vault`
- 外部源码临时审计目录：`/tmp/agent-memory-vault-019f6dd7`
- 外部审计 commit：`3097fe4`
- 当前项目 `vault/README.md`
- 当前项目 `.trellis/tasks/07-17-llm-wiki-provenance-decision-quality/prd.md`
- 当前项目 `.trellis/tasks/07-17-llm-wiki-provenance-decision-quality/design.md`

## Findings

### 可直接复用

- Markdown 作为正式事实源，SQLite/FTS 作为可重建索引。
- `memory_type`、`track`、`project_id`、`agent_scope`、`status`、`verified_at` 和 `review_after_days` 等正交检索字段。
- Codex/Claude 共用 runtime、会话认领、写入前对账、closeout、audit 和 Doctor 的基础结构。
- 搜索结果回读 Markdown 原文、向量层只作候选召回的原则。
- runtime 安装清单与内容指纹，可区分源码和本机配置。

### 必须收紧的默认行为

- 搜索默认返回 5 条且无条件写 SQLite 搜索日志；试点需要默认最多 3 条且默认不写日志。
- `memoryctl closeout` 在没有显式参数时自动追加 `--commit`；试点需要默认 `--dry-run`，提交只能显式请求。
- 示例配置允许 closeout 自动提交，Python 使用未固定的 `python3`；本机配置需要关闭自动提交并绑定 Python 3.14。
- 向量检索虽默认关闭，但模型、依赖和 Hook 文档完整存在；试点不安装、不配置、不调用这些入口。

### 内容质量缺口

- 当前没有受控试点的允许记忆类型、必填元数据和值域策略。
- `review_after_days` 只用于审计，默认搜索不会排除已经到复核日期的内容。
- 写入前敏感文本只返回 `ASK_USER` 建议，未形成不可忽略的失败结果。
- 项目记忆模板没有要求 `source_paths`，无法保证跨项目记忆只保存正式来源引用。
- frontmatter 使用轻量解析器，策略应限制在明确支持的简单字段与列表，不引入复杂 YAML。

### 当前项目既有边界

- 日报仓库已经有 `vault/`，它是项目内工作记忆索引，受 Git 管理，不能被新的私有 Vault 替代。
- 项目 Wiki、Trellis、项目 `vault/`、报告与快照各自已有明确事实归属。
- 新的私有 Vault 只能保存跨 Agent、跨项目内容；涉及日报项目时只保存短摘要和正式来源路径。
- 日报 runtime、Wiki manifest/trace、正式决定和 replay 不得读取新的私有 Vault。

### 运行与兼容

- 外部仓库基础测试使用本项目 Python 3.14 运行，40 项通过；测试过程中出现 SQLite 连接未关闭的 ResourceWarning。
- 外部公开 CI 只覆盖 Python 3.11/3.12，因此本试点必须把 Python 3.14 作为独立验收项。
- 外部实现使用 `fcntl` 和 macOS/Unix 自动化方式；本次只在 macOS 上运行，不承诺 Windows 兼容。
- 外部许可证为 MIT，但版权行仍是占位文字；本次保留独立 clone 和原始许可证，不把源码复制到日报仓库。

## Recommendation

采用三目录布局：独立源码 clone、独立私有 Markdown、独立 runtime/config/state。对本地 clone 做小范围安全改造：默认 Top 3、搜索日志显式开启、closeout 默认预览、配置化内容策略、到期内容默认排除、敏感写入失败。日报仓库只保存本任务规划与验证证据。

私有 Vault 首批只允许用户偏好、跨项目指针、通用工作流、架构决定和 Agent 案例。日报项目只建立一个短项目指针，指向当前项目 `vault/README.md`、Wiki 和 Trellis，不复制正文。

## Impact

- PRD: 增加项目内 `vault/` 的唯一事实归属，并确认三目录落点。
- Design: 采用单向引用和安全默认值，不接入日报 runtime。
- Implementation: 先用测试固定 CLI 与策略行为，再安装私有 runtime 和空白 Vault；最后运行跨仓库验证。
