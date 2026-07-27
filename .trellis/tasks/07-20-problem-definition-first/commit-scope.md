# 提交范围证据

本任务在已有大量暂存与未暂存修改的工作区中完成。提交时不得对混合文件整文件执行 `git add`。

## 可整文件纳入

- `AGENTS.md`：新增 `问题定义优先` 小节。
- `wiki/交易思想/AI摩擦与知识复利.md`：新增问题定义原则、有效价值关系和禁止误用边界。
- `.trellis/tasks/07-20-problem-definition-first/`：本任务文档与范围证据。

## 必须按块隔离

- `scripts/knowledge/llm_wiki_context.py`：只取以下版本与兼容映射块：
  - 顶层版本：`WIKI_VERSION = "2026-07-20"`
  - `FIELD_MAPPINGS` 中的四条新增映射：
    - `问题定义优先`
    - `决定先于工具`
    - `有效价值乘法`
    - `验证失败复核`
- `tests/test_llm_wiki_context.py`：只取版本断言 `2026-07-20` 和 `test_problem_definition_first_principle_enters_wiki_context`。
- `wiki/log.md`：只取 `## [2026-07-20] ingest | 问题定义优先` 这一段。

## 明确排除

- 上述混合文件中的仓位、明日空仓、创新高结构、冻结轨迹、其他 Wiki 摄入和其他任务测试改动。
- 当前暂存区已有的 07-17 LLM Wiki 引用轨迹候选及任何其他任务内容。

## 操作约束

- 当前轮次不暂存、不提交。
- 后续获得提交授权时，使用临时索引或等价的块级候选构造方法；不得使用 `git add <混合文件>`。
- 构造候选后必须比较候选补丁，确认只包含本文件列出的内容，并重新运行本任务验证命令。

## 当前隔离证据

- 审计时真实暂存补丁 SHA-256：`c32f8fec2c9befd48b75584a7853b99f88384829de5e86c2ed5df55f9e926f72`。
- 真实暂存候选路径数：`39`。
- 从该暂存候选导出隔离副本，只叠加本任务允许块后，`tests.test_llm_wiki_context` 为 `48 tests OK`。
- 同一隔离副本的 Wiki 检查为 `25 entries / 0 errors / 37 warnings`；提醒均为既有来源元数据不完整。
- 混合工作区另外通过 `50 tests` 与 `32 entries / 0 errors / 42 warnings`，但只把隔离副本结果作为本任务不依赖其他未暂存改动的证据。
