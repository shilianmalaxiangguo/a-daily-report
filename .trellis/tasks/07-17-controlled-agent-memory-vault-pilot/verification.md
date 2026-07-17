# Verification: 受控 Agent Memory Vault 试点

验证日期：2026-07-17

固定解释器：

`/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/.generated/venv-py314/bin/python3.14`

## 范围结论

- 独立源码位于 `/Users/chaixixi/Projects/agent-memory-vault`，分支为 `codex/controlled-memory-pilot`，上游基线为 `3097fe40c76d3901b8520c3c0208555202f40342`。
- 私有 Markdown 位于 `/Users/chaixixi/.local/share/agent-memory-vault`；runtime、配置和 SQLite 位于 `/Users/chaixixi/.config/agent-memory`。
- 日报仓库只新增本任务目录。对 `scripts/`、`tests/`、`wiki/`、`reports/`、`snapshots/` 和项目 `vault/` 检索私有 Vault/runtime 路径，无匹配。
- 未安装 Memory Vault Hook 或周期任务；向量检索和自动提交保持关闭。

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

提交前审计补充了 4 项回归覆盖：配置或策略不可用时，closeout 在读取 Git 或写入状态前停止；内容检查失败时不再继续对账、索引、向量、Agent 统计或 audit；直接索引入口在打开 SQLite 前停止；Stop Hook 使用配置的 Python，并在自动提交关闭时让到期 audit 只做预览。

外部源码已在用户确认后提交为 `a397da16e1112a059a1c90a014c783eb7c3d6688`。随后使用固定 Python 3.14 重新安装 runtime；manifest 记录该提交、`source_dirty=false`，18/18 个文件匹配，外部源码工作区保持干净。

## 私有 Vault 与 runtime 验证

- 内容与结构检查通过：25 份 Markdown 全部满足受控策略，SQLite schema 正常。
- Doctor：11 项通过、4 项提示、1 项失败。
- 唯一失败为私有 Vault 尚无 Git 基线；按任务约束未自行执行 `git init`。
- 4 项提示分别是：向量索引未初始化、尚无 audit 历史、尚无 closeout 历史、尚无远端备份。前三项符合首版设置；远端备份需要在是否建立私有 Git 基线后再决定。
- Markdown、SQLite、FTS 与 INDEX 一致：25/25；搜索日志没有遗留原始查询正文。
- 固定查询：日报项目范围返回 1 条正式来源指针；错误项目范围返回 0 条；宽查询严格返回 3 条。
- 默认 closeout 以预览方式运行。由于当前会话没有认领文件且私有 Vault 无 Git 基线，命令退出码为 2；运行前后 SQLite SHA-256 均为 `869701e2fa6ce2d6beafb8365265c673ee7945a3d9d96b85f3698d671e937900`，没有写入状态库。

## 日报仓库独立性验证

| 检查 | 结果 |
|------|------|
| `scripts/knowledge/llm_wiki_lint.py` | 0 errors；30 个既有来源元数据提示 |
| `-m unittest tests.test_llm_wiki_manifest tests.test_llm_wiki_router -v` | 通过，79 项（当前日报工作区） |
| 私有 Vault/runtime 路径检索 | 无匹配，`rg` 退出码 1 |
| 本任务目录 `git diff --check` | 通过；新增文件另做空白字符检查 |

原定日报回归命令：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_report_runtime tests.test_report_replay -v
```

最终结果为 396/396 通过。首次运行时，另一个未提交的 LLM Wiki/replay 任务曾缺少 `fact_sources` 字段；该任务在本轮审计期间由其所有者修正。本试点没有修改对应日报代码，修正后使用同一测试范围重新验证通过。

## 提交前审计

- 三个只读子代理分别检查外部源码、runtime 隔离和日报提交范围。
- 审计发现的 closeout 后续步骤、Stop Hook audit 预览和固定解释器示例问题均已修复，并由新增测试及全量测试复核。
- 日报任务目录没有私有 Markdown 正文或凭证；私有路径只用于说明独立落点。
- 日报仓库提交范围必须精确限定为 `.trellis/tasks/07-17-controlled-agent-memory-vault-pilot/`。

## 剩余事项

1. 是否为私有 Vault 建立仅本地 Git 基线需要用户单独决定；在此之前 Doctor 会保留 1 项失败。
2. 向量检索、Hook、周期任务和自动提交继续保持关闭，待人工试用后另行评估。
