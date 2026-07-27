# 验证说明

## 已执行

- LLM Wiki manifest/context/router/lint：`160` 项通过。
- 新节点正式决定隔离与冻结 replay 定向用例：`2` 项通过。
- `tests.test_report_runtime` 与 `tests.test_report_replay`：`410` 项通过。
- LLM Wiki lint：`33 entries / 0 errors / 42 warnings`。
- Python 3.14 `py_compile`：通过。
- Trellis context manifest：`implement.jsonl 3 entries / check.jsonl 3 entries`，验证通过。
- `git diff --check`：通过。

## 42 条提醒

42 条均为当前工作区既有知识来源缺少 `source_date/capture_date/anchor` 的提醒；新增的 `market.historical-prior-live-structure` 不在提醒中。本任务不扩大范围修复其他知识条目的历史元数据。

## 未跟踪文件格式检查

对两份新增 Wiki 文档和任务产物执行 `git diff --no-index --check /dev/null <file>`；命令无空白错误输出。该命令因文件内容与 `/dev/null` 不同返回 `1`，返回值表示存在差异，不表示格式检查失败。

## 人工复核

- 来源卡必须保留 `source_index_not_line_verified` 和一手材料未逐项定位的说明。
- 主节点必须保留 `## 判断规则`、反证、日报边界和 replay 冻结说明。
- 共享脏工作区提交前按 `commit-scope.md` 选择本任务片段，不能整文件暂存。
