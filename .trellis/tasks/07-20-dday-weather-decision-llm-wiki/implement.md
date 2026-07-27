# Implementation: 诺曼底气象决策知识接入 LLM Wiki

## Prerequisites

- 已阅读 `prd.md`、`design.md`、`research/dday-weather-decision-evidence.md`。
- 已阅读 LLM Wiki 来源追踪与决定隔离规范、Wiki 维护契约和日报术语契约。
- 保留当前工作区全部已有修改，只追加本任务所需内容。

## Ordered Checklist

- [x] I1: 新增 D 日来源卡，区分待逐项复核的史实概述、整理判断、影视化压缩、类比失效和待核实材料。
- [x] I2: 新增稳定方法节点，提供字段化判断、使用顺序、反证、日报边界和来源链接。
- [x] I3: 在 `KNOWLEDGE_INDEX` 注册一个解释性条目，在 `SOURCE_PATHS` 登记主节点，并更新 Wiki 导航、入口和日志。
- [x] I4: 补齐正向命中、仅有类比词不命中、未知路径不命中、否定事实不命中与完整用途边界测试。
- [x] I5: 补 manifest/source 指纹测试，以及正式决定不变和 replay 冻结测试；复用现有测试工具和断言。
- [x] I6: 运行 LLM Wiki 定向测试、runtime/replay 隔离测试、lint、Python 编译检查和 `git diff --check`。
- [x] I7: 启用子代理做提交前独立审计，只修复本任务引入的问题；回填 PRD 和实施结果，不自动提交。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_manifest tests.test_llm_wiki_context tests.test_llm_wiki_router tests.test_llm_wiki_lint`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_report_replay`
- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/knowledge/llm_wiki_router.py scripts/knowledge/llm_wiki_context.py`
- `.generated/venv-py314/bin/python3.14 scripts/knowledge/llm_wiki_lint.py`
- `git diff --check`

## Risk And Rollback Points

- 高风险文件已有其他未提交工作：`scripts/knowledge/llm_wiki_router.py`、`scripts/knowledge/llm_wiki_context.py` 及对应测试。
- 每次编辑只在当前工作副本中追加条目或断言，不重写周边代码、不格式化整文件。
- 若全量 runtime/replay 测试暴露与当前工作区其他任务有关的失败，先用定向用例确认本任务边界，再如实记录剩余风险。

## Review Checkpoints

- 史实是否避免“暴雨对晴天”“急流单因果”“Stagg 决定登陆”等电影化简化。
- 结构化确认是否只使用已登记的精确事实路径。
- 单独出现“高空急流”或“诺曼底”是否无法生成生产命中。
- 报告正式决定和历史回放冻结轨迹是否保持不变。

## 本轮质量结果

- LLM Wiki manifest/context/router/lint：`160` 项通过。
- hook、快照保存与日报渲染：`95` 项通过。
- runtime/replay 全模块：`410` 项通过，最终运行耗时 `235.129s`。
- LLM Wiki lint：`33 entries / 0 errors / 42 warnings`；提醒均来自其他既有条目的来源元数据缺口。
- Python 3.14 `py_compile`、Trellis context manifest 和 `git diff --check` 通过。
- 三路提交前审计完成；史实概述的证据标签已降级，主节点已补 `## 判断规则`，未跟踪文件格式检查和共享文件提交范围已记录。

## 规范沉淀判断

现有 `.trellis/spec/backend/llm-wiki-provenance.md` 已完整规定精确事实路径、`explanation_only`、正式决定隔离和 replay 冻结。本任务没有建立新的签名、事实模型或跨层合同，因此不重复修改 `.trellis/spec/`。

## 剩余事项

- 一手史料逐页或逐档案定位仍待后续外部查证，不影响当前方法节点的边界使用。
- 当前工作区包含其他任务的暂存与未暂存修改；提交前必须按 `commit-scope.md` 选择本任务片段。
- 本轮不自动创建 commit，等待用户明确确认。
