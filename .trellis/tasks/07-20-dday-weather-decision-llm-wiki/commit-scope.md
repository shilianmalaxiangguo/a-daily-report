# Commit Scope: 诺曼底气象决策知识接入 LLM Wiki

## 本任务新增文件

- `.trellis/tasks/07-20-dday-weather-decision-llm-wiki/`
- `wiki/交易思想/历史先验、实时结构与可用窗口.md`
- `wiki/资料库/诺曼底D日气象预报分歧与决策窗口样本.md`

## 与其他任务共享的文件

以下文件在本任务开始前已经有暂存或未暂存修改，不能按整文件直接归入本任务提交：

- `scripts/knowledge/llm_wiki_router.py`：只归属 `market.historical-prior-live-structure` 条目。
- `scripts/knowledge/llm_wiki_context.py`：只归属主节点 `SOURCE_PATHS` 项。
- `tests/test_llm_wiki_manifest.py`：只归属新条目的来源与事实路径断言。
- `tests/test_llm_wiki_context.py`：只归属主节点来源、来源卡不自动接入、章节结构和目标节点来源变化回放断言。
- `tests/test_llm_wiki_router.py`：只归属新节点正向、问题词、未知路径与否定事实用例。
- `tests/test_report_runtime.py`：只归属完整正式决定投影不变用例。
- `tests/test_report_replay.py`：只归属新节点冻结轨迹用例及其辅助函数、导入。
- `wiki/README.md`、`wiki/index.md`、`wiki/log.md`：只归属本节点的入口、链接和摄入记录。

## 提交限制

- 不直接执行 `git add` 上述共享文件的完整路径，否则会混入其他任务修改。
- 提交前应按本任务片段单独复核并选择性暂存；若无法可靠分离，由用户在现有工作批次中统一处理。
- 不修改、撤回或覆盖本任务开始前已经存在的暂存与未暂存内容。
