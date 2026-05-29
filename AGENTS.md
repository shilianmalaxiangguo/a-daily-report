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

# 日报 bug 修复短口令

当用户说 `修日报bug`、`日报有bug`、`修 YYYY-MM-DD 日报`、`重新生成昨天日报和推论`，或同类短句时，默认进入“历史日报修复”流程。不要要求用户重复完整约束。

默认展开如下：

- Goal：修复指定交易日的日报问题，并重新生成该交易日的 replay 日报、推论和必要的 replay 快照。
- In Scope：报告逻辑、推理逻辑、渲染逻辑、replay 缺口回补、与该 bug 直接相关的最小测试。
- Out of Scope：重新按当前实时盘面全量采集历史日期、覆盖正式历史日报、顺手重构无关模块、扩展新功能。
- Non-goals：不把今天的热度、异动、盘中新闻、顽主杯、龙虎榜、资金流、涨跌家数、成交额排行等当前数据混入历史日报。
- Done Definition：目标日期 replay 产物重新生成，关键检查通过，并说明哪些事实来自官方快照、哪些事实按目标日期回补、哪些事实仍缺失。

执行规则：

1. 先解析目标日期；如果用户只说“昨天/前天”，按当前时区换算成明确日期；如果日期无法判断，只问日期。
2. 历史日期优先读取 `snapshots/<date>.json`，默认命令是：
   ```bash
   .generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <date> --replay
   ```
3. 如果官方快照不存在，不要直接改走实时全量采集；先说明缺少历史快照，并询问是否允许按目标日期重新采集。
4. 修数据源 bug 时，不能只修实时采集路径；如果坏数据已经冻结在历史快照里，还要检查 `scripts/replay/report_replay.py` 是否需要按目标日期回补。
5. replay 回补只能使用明确支持 `target_date=<date>` 的历史源、本地事实库、官方快照或 replay 快照；如果某个来源只能返回当前数据，不得用它补历史日期。
6. 对会随当天变化的数据，回补时必须保留 `query_date`、`source_date`、`trade_date` 或等价字段；无法证明属于目标日期时，宁可保留缺失并报告风险。
7. 默认只写 `reports/replay/` 和 `snapshots/replay/`；除非用户明确要求覆盖正式历史并允许 `--overwrite-official`，否则不覆盖 `reports/` 下的正式日报。
8. 验证优先级：相关单测；然后运行 `<date> --replay`；最后对 `reports/replay/<date>_A股日报_完整版_replay.md` 运行日报一致性检查。

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
