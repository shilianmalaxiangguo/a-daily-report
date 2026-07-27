# 诺曼底气象决策知识接入 LLM Wiki

状态：🔨 进行中（实现、验证与提交前审计完成；待用户确认提交）

## Goal

把诺曼底登陆气象预报中“历史先验、实时观测、模型分歧与边际可用窗口”的可复用方法接入 LLM Wiki，帮助日报和复盘解释高不确定市场，同时防止历史类比被误写成实时证据或交易动作。

## User Story

- **角色**：日报阅读者、市场复盘者和维护 LLM Wiki 的模型。
- **场景**：历史杀跌样本与当前指数、宽度、成交和主线结构同时出现，但两者给出的解释并不完全一致。
- **目标**：区分历史先验与当前结构，列出竞争解释、区分证据、主要反证和下一观察窗口。
- **成功标准**：相关事实出现时能召回同一方法节点；没有结构化市场事实、只有类比词或否定表达时不命中；知识接入不改变任何正式交易决定。

### 用户旅程

1. 当日报已经形成市场结构事实与正式决定，LLM Wiki 根据登记事实决定是否引用该方法节点。
2. 报告只追加“历史先验如何使用、当前证据支持什么、还缺什么、下一窗口核对什么”的解释。
3. 历史回放只复用目标日冻结的知识轨迹，不用当前 Wiki 重写过去判断。

## What I Already Know

- 本轮研究材料暂将 James Stagg 概括为 SHAEF 首席气象官，将 Irving P. Krick 概括为美方 USAAF 预报思路的重要代表；具体职责和会议身份仍待一手材料逐项核验。
- 本轮研究材料把分歧概括为“当前观测与天气系统物理演变”对“历史类比和周期模式”，不是简单的“暴雨对晴空万里”；具体方法权重仍待一手材料核验。
- 本轮研究材料把 1944 年 6 月 6 日概括为边际可用的短暂改善窗口，实际仍有风、云和恶劣海况；不能写成精准预测了完美天气。
- 高空观测参与了分析，但现有证据不足以把现代意义的高空急流写成唯一决定因素。
- 当前 LLM Wiki 的运行入口是 `KNOWLEDGE_INDEX` 与显式 `SOURCE_PATHS`，生产命中必须同时满足触发词和已登记叶子事实条件。
- 当前唯一允许的知识用途是 `explanation_only`，正式决定隔离与 replay 冻结合同已经存在。

## Requirements

- [x] R1: 新增一份 D 日气象预报来源卡，分开记录待逐项复核的史实概述、整理判断、电影化简化和待核实缺口。
- [x] R2: 新增一份稳定方法节点，明确历史先验、实时结构、竞争解释、共同事实、区分证据、事实缺口、下一观察窗口和类比失效处。
- [x] R3: 只注册一个可路由方法节点，并复用现有 `market.market_form`、`market.breadth`、`market.turnover_distribution` 等结构化事实，不新增“市场急流”专用事实或单指标。
- [x] R4: 知识命中只用于引用、解释和复盘，不改变候选、最终对象、仓位、B1/B2、旧仓动作或退出动作。
- [x] R5: 更新 Wiki 导航、使用入口、操作日志与来源指纹，使新节点可发现、可查证、可复核。
- [x] R6: 覆盖结构化事实正向命中、仅有类比词不命中、否定事实不命中、决定隔离和历史回放冻结。

## Non-functional Requirements

### 可追溯性

- 每个外部来源保留发布方、标题、URL、采集日期和访问缺口；不使用未经点验的逐字引文。
- 2021 至 2022 年杀跌与修复数字保留为带样本窗口和来源日期的研究证据，不写入永久实时判断。

### 兼容性

- 沿用现有 `knowledge_manifest.v1`、`knowledge_trace.v1` 与事实路径清单。
- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。

### 用户可见语言

- 遵守《日报术语契约》；“下一观察窗口”只说明下一次核对什么，不新增窗口外动作。

## Acceptance Criteria

- [x] AC-R1-1: 来源卡以限定表述整理 Stagg、Krick、两类方法、6 月 6 日边际窗口和高空资料边界，并明确尚未取得一手逐字材料、页码或档案定位。
- [x] AC-R2-1: 方法节点包含维护契约要求的定位、适用、不适用、路由提示、核心判断、判断规则、反证、来源和待核实章节。
- [x] AC-R2-2: 方法节点明确“历史限定可能范围，来源明确的实时结构决定当前判断；短促反弹不等于稳定修复”。
- [x] AC-R3-1: manifest 中只有一个新增运行条目，`fact_conditions.must_any` 全部使用当前允许的精确叶子事实路径。
- [x] AC-R3-2: 给定含“历史类比/实时结构/修复质量”等触发词且同一叶子有相应市场事实时命中；只有问题文字、未知路径、无关事实或被否定的描述时不命中。
- [x] AC-R4-1: 新命中及 trace 均保持 `decision_scope="explanation_only"` 和完整 `not_used_for`。
- [x] AC-R4-2: 接入前后正式决定投影逐字段一致，包括候选、最终对象、仓位、B1/B2、旧仓动作和退出动作。
- [x] AC-R5-1: manifest 能读取新来源内容指纹，Wiki lint 对导航、日志、来源与用途检查无错误。
- [x] AC-R6-1: 目标日冻结轨迹在当前来源内容变化后仍原样用于 replay，只增加来源变化复核信息，不重新命中当前节点。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md`、`implement.md` 与必要 research 已保存并完成审查。
- [x] 相关单测、LLM Wiki lint、Python 编译检查和 `git diff --check` 通过。
- [x] 子代理完成一轮提交前独立审计，发现的问题已修复或明确记录。
- [ ] PRD 状态改为 `✅ 已完成`；提交动作按用户确认执行。

## Out Of Scope

- 不把“高空急流”固化为量化资金的同义词或独立交易指标。
- 不新增市场事实路径、分钟级数据源、预测模型或历史行情采集器。
- 不重新计算或覆盖 2021 至 2022 年历史研究数字。
- 不修改候选生成、最终对象、仓位、B1/B2、旧仓处理、退出动作或正式三段交易窗口。
- 不覆盖正式历史日报或使用当前 Wiki 回补旧快照。
- 不把 D 日军事决策的损失与证券交易盈亏作价值等同。

## Technical Notes

### 参考来源

- `wiki/运行契约/LLM Wiki维护与路由契约.md`
- `.trellis/spec/backend/llm-wiki-provenance.md`
- Met Office、Imperial War Museums、Eisenhower Library 的 D 日历史资料入口。
- James Stagg, *Forecast for Overlord*（1971），作为后续一手材料核验入口。

### 影响区域

- `wiki/资料库/`：D 日史实与来源卡。
- `wiki/交易思想/`：稳定判断方法。
- `scripts/knowledge/llm_wiki_router.py`：一个解释性知识条目。
- `scripts/knowledge/llm_wiki_context.py`：运行来源清单。
- `wiki/index.md`、`wiki/README.md`、`wiki/log.md`：导航、使用入口和变更记录。
- `tests/test_llm_wiki_*.py`、相关 runtime/replay 测试：来源、命中与隔离验证。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_manifest tests.test_llm_wiki_context tests.test_llm_wiki_router tests.test_llm_wiki_lint`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_report_replay`
- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/knowledge/llm_wiki_router.py scripts/knowledge/llm_wiki_context.py`
- `.generated/venv-py314/bin/python3.14 scripts/knowledge/llm_wiki_lint.py`
- `git diff --check`

## 本轮验证记录

- LLM Wiki manifest/context/router/lint：`160` 项通过。
- hook、快照保存与日报渲染：`95` 项通过。
- `tests.test_report_runtime` 与 `tests.test_report_replay`：`410` 项通过，修正前后各完整运行一次。
- LLM Wiki lint：`33 entries / 0 errors / 42` 条既有来源元数据提醒；新增条目没有提醒。
- Python 3.14 编译检查、Trellis context manifest 验证与 `git diff --check` 通过。
- 三名独立子代理完成提交前审计；来源证据强度和缺失 `判断规则` 标题两项发现已经修正。
- 本任务未新增事实路径、行情数据源或正式决策行为；`.trellis/spec/backend/llm-wiki-provenance.md` 已覆盖本次全部工程合同，无需重复修改 spec。

## 剩余事项

- 外部网页正文、会议记录和 Stagg 回忆录页码未能在本轮稳定取得；来源卡已降为待一手材料逐项复核的史实概述，不使用未经点验的直接引文。
- 工作区有大量其他未提交修改，共享文件只能按 `commit-scope.md` 的本任务片段选择性暂存。
- 未经用户明确确认，不创建 commit；因此任务保持进行中。

## 落地 commit

待用户确认。
