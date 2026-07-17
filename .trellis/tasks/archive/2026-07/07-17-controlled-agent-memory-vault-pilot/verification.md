# Verification: 受控 Agent Memory Vault 试点

验证日期：2026-07-18

固定解释器：

`/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/.generated/venv-py314/bin/python3.14`

## 范围结论

- 独立源码位于 `/Users/chaixixi/Projects/agent-memory-vault`，分支为 `codex/controlled-memory-pilot`，上游基线为 `3097fe40c76d3901b8520c3c0208555202f40342`。
- 私有 Markdown 位于 `/Users/chaixixi/.local/share/agent-memory-vault`；runtime、配置和 SQLite 位于 `/Users/chaixixi/.config/agent-memory`。
- 日报任务文档的既有落地提交、受控源码和私有 Markdown 已分别同步到 `shilianmalaxiangguo/a-daily-report`、private `shilianmalaxiangguo/agent-memory-vault` 和 private `shilianmalaxiangguo/agent-memory-private`；本轮 I14 与验证记录在收尾检查后单独提交。
- 日报仓库只新增本任务目录。对 `scripts/`、`tests/`、`wiki/`、`reports/`、`snapshots/` 和项目 `vault/` 检索私有 Vault/runtime 路径，无匹配。
- 未安装 Memory Vault Hook 或周期任务；向量检索、自动写入、自动提交和自动推送保持关闭。

## 独立源码验证

| 检查 | 结果 |
|------|------|
| `-m unittest discover -s tests -v` | 通过，70 项 |
| `scripts/agent_memory_check.py --skip-state-db` | 通过，公开模板、frontmatter、运行文件和隐私路径检查均正常 |
| `-m compileall -q scripts tests` | 通过 |
| `-m json.tool config/content-policy.example.json` | 通过 |
| `scripts/install_runtime.py --config-root /Users/chaixixi/.config/agent-memory --verify --json` | 通过，18/18 文件匹配 |
| `git diff --check` | 通过 |

测试仍会输出上游既有 SQLite `ResourceWarning`，但 unittest 退出码为 0。本任务未顺带修改该资源释放问题。

固定验收由同一 70 项测试覆盖，关键测试包括：

- `test_default_search_is_top_three_log_free_and_excludes_review_due`：默认 Top 3、到期内容排除、显式包含、范围过滤和默认无日志。
- `test_prewrite_conflict_is_reported_without_creating_another_fact`、`test_conflicting_candidate_requires_manual_merge`：冲突只报告人工合并，不生成第二份当前事实。
- `test_type_status_required_fields_and_project_sources_are_enforced`、`test_sensitive_and_forbidden_body_content_are_rejected`：缺少元数据、非当前状态、缺少来源路径和敏感内容不能进入受控记忆。

提交前审计补充了 4 项回归覆盖：配置或策略不可用时，closeout 在读取 Git 或写入状态前停止；内容检查失败时不再继续对账、索引、向量、Agent 统计或 audit；直接索引入口在打开 SQLite 前停止；Stop Hook 使用配置的 Python，并在自动提交关闭时让到期 audit 只做预览。

外部源码已在用户确认后提交为 `a397da16e1112a059a1c90a014c783eb7c3d6688`，并推送到私有 `origin/codex/controlled-memory-pilot`；公开原仓库保留为 `upstream`。随后使用固定 Python 3.14 重新安装 runtime；manifest 记录该提交、`source_dirty=false`，18/18 个文件匹配，外部源码工作区保持干净。

## 私有 Vault 与 runtime 验证

- 内容与结构检查通过：25 份 Markdown 全部满足受控策略，SQLite schema 正常。
- 私有 Markdown 初始提交为 `1457d35`，只包含 25 份 Markdown 与 `.gitignore`，已推送并跟踪 private `origin/main`。
- Doctor：13 项通过、3 项提示、0 项失败；Git 基线干净，远端备份与 `origin/main` 同步。
- 3 项提示分别是：可选向量索引未初始化、尚无成功 audit 历史、尚无成功 closeout 历史，均符合首版设置。
- 当前配置保持 `commit_scoped_memory_files=false`、`semantic_retrieval.enabled=false`、`run_vector_index_after_closeout=false`，runtime Python 固定为项目 Python 3.14。
- Markdown、SQLite、FTS 与 INDEX 一致：25/25；`memory_search_log` 为 0 行，最近记录时间为空。
- 固定查询：日报项目范围返回 1 条正式来源指针；错误项目范围返回 0 条；宽查询严格返回 3 条。
- 人工试用完成 10/10 次只读检索、5/5 个独立真实任务会话，其中 Codex 8 次、Claude Code 2 次；所有检索退出码为 0、`warnings` 为空，命中后均回读原文。
- S01 使用当前 Codex 任务 ID，S02-S04 使用当前任务的独立子代理会话标识，S05 使用 Claude Code 会话 ID；搜索日志保持关闭，因此试用证据以会话标识、原文回读记录和固定测试为准，不能从日志库复演查询正文。
- Claude Code 会话 `4a6ed7e3-c9ea-4067-b679-c0c463c580f3` 完成少量取回与停用独立性两次检索；人工样本没有实际出现过期条目或一组真实冲突内容，这两项仍由固定验收测试证明。
- 默认 closeout 以预览方式运行。当前会话没有认领文件，命令退出码为 2，后续索引、向量、Agent 统计、audit 与提交均跳过；运行前后 SQLite SHA-256 均为 `44b68a2661e8b140ac42a4bae193a937cfbf804107f3dd570645d072fc421584`，没有写入状态库，也没有生成 closeout 日志文件。

## 日报仓库独立性验证

| 检查 | 结果 |
|------|------|
| `scripts/knowledge/llm_wiki_lint.py` | 30 个条目，0 errors；41 个当前工作区来源元数据提示 |
| `-m unittest tests.test_llm_wiki_manifest tests.test_llm_wiki_router -v` | 通过，88 项（当前日报工作区） |
| 私有 Vault/runtime 路径检索 | 无匹配，`rg` 退出码 1 |
| 本任务目录 `git diff --check` | 通过 |

当前 `git status --short -- .trellis/tasks/07-17-controlled-agent-memory-vault-pilot` 只列出 `prd.md`、`implement.md`、`trial-log.md`、`verification.md` 四份未暂存文档；日报工作区的其他既有修改保持原状。私有 Markdown、SQLite、日志、模型和 runtime 均未进入日报仓库变更列表。

原定日报回归命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_report_runtime tests.test_report_replay -v
```

最终复验结果为 397/397 通过，墙钟 270.813 秒。首次运行时，另一个未提交的 LLM Wiki/replay 任务曾缺少 `fact_sources` 字段；该任务在本轮审计期间由其所有者修正。本试点没有修改对应日报代码，修正后使用同一测试范围持续验证通过。

日报仓库从未安装 Hook、导入私有 runtime 或增加调用入口；停止使用即不再执行独立 runtime，不需要删除日报项目文件。上述 Wiki lint、88 项 Wiki 测试和 397 项日报回归均在不调用 Memory Vault 的情况下通过，证明 Trellis、Wiki、日报生成和历史 replay 保持独立。

## Spec 更新判断

本轮只完成独立 Memory Vault 试点的任务文档、人工检索记录和验证收口，没有新增或改变日报命令、API、数据库、运行依赖、跨层数据字段或项目编码约定，因此不修改 `.trellis/spec/`。

## 提交前审计

- 六个只读子代理分两轮检查外部源码、runtime 隔离、验收覆盖和日报提交范围。
- 审计发现的 closeout 后续步骤、Stop Hook audit 预览和固定解释器示例问题均已修复，并由新增测试及全量测试复核。
- I14 人工试用记录明确区分真实观察与固定测试：实际样本没有出现过期条目或一组真实冲突内容，不扩大检索结论。
- 最终审计要求补充 T01 退出码、固定验收测试名、停用独立性和本轮远端同步边界；上述文档问题已修正。
- 日报任务目录没有私有 Markdown 正文或凭证；私有路径只用于说明独立落点。
- 日报仓库提交范围必须精确限定为 `.trellis/tasks/07-17-controlled-agent-memory-vault-pilot/`。

## 剩余事项

1. 人工试用后继续使用关键词检索；向量检索、Hook、周期任务、自动写入、自动提交和自动推送继续保持关闭。只有真实使用持续漏召回或每周维护明显超过 10 分钟时，才另开任务评估。
2. audit 与 closeout 历史提示将在未来首次显式成功运行后自然消失，本次不为消除提示而制造运行记录。
