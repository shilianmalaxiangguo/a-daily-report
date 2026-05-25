# 你的理念必须是

The quality you have the fast you go, the only way to go fast is to go well.

# Python 运行版本硬约束

本仓库所有 Python 命令、测试、脚本、日报生成、数据源检查和临时诊断都必须使用 Python 3.14。

固定解释器路径：

```bash
.generated/venv-py314/bin/python3.14
```

禁止使用：

```bash
python
python3
venv/bin/python
venv/bin/python3
venv/bin/python3.11
```

如果需要运行单测，必须使用：

```bash
.generated/venv-py314/bin/python3.14 -m unittest ...
```

如果需要生成日报，必须使用：

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py ...
```

# 文件读取工具选择

## 规则

优先使用 Bash 的 cat/head 读取文件，避免使用 Read 工具。

## 原因

Read 工具在 Windows 环境下读取某些特定文件时会返回乱码（显示为二进制数据），而文件实际是正常的 UTF-8 编码。通过 `cat` 或 `head` 命令可以正常读取。

## 问题特征

- 不是所有文件都有问题，是特定文件会出现乱码
- `file` 命令显示文件是正常 UTF-8，但 Read 工具读取乱码
- Read 工具会缓存读取结果，同一个会话内再次读取会返回缓存

## 验证结果

| 方法 | 结果 |
|------|------|
| `file` 命令 | ✅ 显示 "Unicode text, UTF-8 text" |
| `head`/`cat` 命令 | ✅ 正常显示内容 |
| Read 工具 | ⚠️ 部分文件正常，部分文件乱码 |
| Write 工具 | ✅ 正常 |
| Edit 工具 | ⚠️ 需要先 Read，如果 Read 乱码则失败 |

## 替代方案

```bash
# 读取整个文件
cat <file>

# 读取前 N 行
head -n <lines> <file>

# 读取文件并显示行号
cat -n <file>
```

# 用户可见语言与禁止词

本仓库所有用户可见文字都必须遵守 `wiki/交易思想/日报术语契约.md`，范围包括：

- 助手回复、阶段性说明、计划、总结。
- 日报正文、执行摘要、诊断输出、运行日志。
- 新增或修改的测试名、文档、示例文案、错误提示。

禁止把工程状态机、抽象权限词、系统实现词搬到用户可见文字里。

明确禁用以下说法：

- `硬门禁`
- `门禁`
- `gate`
- `hard gate`
- `状态机`
- `状态机词汇`

需要表达检查、阻断或是否允许执行时，统一改写为交易语言：

- `条件`
- `资格`
- `买入资格`
- `执行资格`
- `可做`
- `不做`
- `参与`
- `不参与`
- `关键数据不完整，停止生成`
- `条件未满足，停止生成`

如果不得不引用用户原话或历史问题，也要用“你指出的禁用说法”“这个旧工程口径”等替代表达，不在新的用户可见输出里复述禁用词。

# Spec-Driven Scope Control

For implementation tasks, always define and follow:

- In Scope
- Out of Scope
- Non-goals
- Done Definition

If one of these is missing and the task has ambiguity, clarify before expanding architecture.

Default to the smallest vertical slice that satisfies the current goal.

Do not build for hypothetical future needs by default. Add abstraction only when there is present-time evidence.

Before introducing a new layer/subsystem, all of the following must be true:

- It is required by current In Scope or Done Definition.
- The current implementation has concrete, repeated complexity that the new layer actually removes now.
- The change can be explained as lower current delivery risk, not future preference.

If these conditions are not met, do not introduce the abstraction in the current PR.

If out-of-scope ideas are valuable, record them as follow-up proposals (RFC/ADR/todo) and keep the current PR minimal and mergeable.

During review, if a PR materially exceeds the current Done Definition, request a split: merge the minimal in-scope slice first, and move expansions to separate follow-up PRs.
