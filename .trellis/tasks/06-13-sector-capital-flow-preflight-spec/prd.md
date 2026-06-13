# 板块资金扩散选股生成前审计

状态：✅ 已完成

## Goal

把“第一性原理 + 板块资金扩散 + 量化参与痕迹 + 唯一最终动作”固化为日报生成前审计 Spec，防止日报重新退回涨停池、分数排序或多个模块各自选标的。

## User Story

- **角色**：日报使用者 / 日报生成维护者。
- **场景**：生成日报或调试选股逻辑前，需要先确认当前流程是不是从板块资金扩散找资金载体，而不是从涨停池或单票分数倒推明日标的。
- **目标**：在正式生成前看到一张 Mermaid 流程图和一套可执行 Spec，明确市场、板块、资金载体、价格行为、账户条件如何逐层收口。
- **成功标准**：未来生成日报前，模型先用同一条流程梳理当前决策链；Spec 明确“好股不一定涨停，但必须能证明每天有资金参与和承接”。

### 用户旅程

1. 用户准备生成日报或复盘日报逻辑。
2. 系统先展示板块资金扩散选股 Mermaid 流程。
3. 系统按 Spec 检查：板块资金是否扩散、资金载体是谁、量化参与痕迹是否可见、价格行为是否确认、最终动作是否唯一。
4. 系统再进入日报生成或淘汰赛 HTML 输出。

## What I Already Know

- `selection_workflow.v1` 已有 `sector_first_strict.v1` 合同，并且已有 Mermaid 渲染函数 `render_selection_workflow_mermaid(...)`。
- 已有淘汰赛 companion HTML，可展示每一层输入、淘汰、晋级和最终收口。
- 已有 `wiki/交易思想/反伪精确第一性原理.md`，核心是事实数值保留，主观判断不写成精确分。
- 用户明确要求：日报不是从涨停里找股票，而是从板块资金扩散里找被资金反复参与的股票。
- 用户给出的典型目标是中船特气、信维通信这类资金载体：可能涨停，也可能不涨停，但每天都有资金参与和承接。

## Requirements

- [x] R1: 在 backend Spec 中新增“板块资金扩散生成前审计”合同，明确日报生成前必须先从第一性原理和板块扩散视角梳理流程。
- [x] R2: Spec 必须包含 Mermaid 审计模板，顺序为：市场资金结构 → 板块扩散 → 资金载体 → 角色分类 → 量化参与痕迹 → 价格行为 → 反证 → 账户/盈亏比 → 唯一动作。
- [x] R3: Spec 必须明确涨停、连板、热榜、龙虎榜、分数只能作为资金参与证据，不能作为自动买入资格。
- [x] R4: Spec 必须明确资金载体不一定涨停；趋势容量核心、板块锚、中军、分支龙头都可以成为观察对象，但必须证明资金反复参与。
- [x] R5: LLM Wiki 必须同步写入这条原则，防止未来生成和问股时漂回单票形态或分数排序。
- [x] R6: 不改变现有日报生成代码的最终动作逻辑；本任务只固化生成前审计合同和知识入口。

## Non-functional Requirements

### 性能
- 无运行时性能要求；本轮以 Spec / Wiki 为主。

### 安全
- 无额外安全约束，沿用项目默认标准。

### 兼容性
- 不改变既有 `selection_workflow.v1`、`elimination_tournament.v1` payload 结构。

### 可访问性
- 不适用；本轮不新增前端 UI。

## Acceptance Criteria

- [x] AC-R1-1: `daily-report-decision-loop.md` 中存在可测试、可执行的生成前审计合同。
- [x] AC-R2-1: Spec 中包含可直接复制到报告/审计文档的 Mermaid 流程图。
- [x] AC-R3-1: Spec 明确涨停和分数不是入口本身，必须先证明板块扩散和资金载体身份。
- [x] AC-R4-1: Spec 明确“不涨停但每天有人买”的资金载体也可以进入观察链。
- [x] AC-R5-1: `llm_wiki_context.py` 或 Wiki 文件可检索到“板块资金扩散找资金载体”的原则。
- [x] AC-R6-1: 本轮不会改出新的日报明日标的或多目标输出。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md` / `implement.md` 已补齐。
- [x] Spec 与 Wiki 更新完成。
- [x] 必要测试或文档检查通过。
- [x] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 不在本轮重写完整选股引擎。
- 不在本轮新增实时数据源。
- 不在本轮重新生成正式日报。
- 不在本轮清理 PK 决策、新股叙事、策略复盘等旧评分债务。
- 不把涨停池删除；只重新定义它在流程中的身份：资金参与证据，不是自动入口。

## Technical Notes

### 参考来源
- `.trellis/spec/backend/daily-report-decision-loop.md`
- `wiki/交易思想/反伪精确第一性原理.md`
- `scripts/report/selection_workflow.py`
- `scripts/report/elimination_tournament.py`

### 影响区域
- `.trellis/spec/backend/daily-report-decision-loop.md` — 固化生成前审计合同。
- `wiki/交易思想/反伪精确第一性原理.md` — 同步交易原则。
- `scripts/knowledge/llm_wiki_context.py` — 让运行时知识入口能取到这条原则。
- `scripts/knowledge/llm_wiki_router.py` — 让板块扩散相关词汇召回同一个第一性原理节点。
- `tests/test_llm_wiki_context.py` — 防止知识入口回退。
- `tests/test_llm_wiki_router.py` — 防止路由回退到单票/分数入口。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router`
- `git diff --check`

## Notes

- 本任务是防漂移任务。先定合同，再让后续日报生成实现跟合同对齐。

## 落地 commit

本任务随当前分支提交，具体提交以 `git log --oneline -1` 为准。
