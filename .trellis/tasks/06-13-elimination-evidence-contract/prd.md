# 淘汰赛证据契约与唯一对象收口

状态：✅ 已完成（未提交）

## Goal

建立日报选股淘汰赛的结构化证据契约，让每一层候选进入、淘汰、保留和最终收口都能被 HTML 与审计逻辑复用，同时确保明日动作仍只来自唯一最终对象。

## User Story

- **角色**：日报使用者 / 后续 HTML 渲染器。
- **场景**：日报已有多个候选来源和模块输出，需要知道每只股票在哪层被淘汰。
- **目标**：输出一份结构化 payload，明确每层输入、淘汰、剩余、理由和最终动作。
- **成功标准**：同一份 payload 可以解释 2026-06-12 和远气体为什么身份通过但风险层不直接参与。

### 用户旅程

1. 日报 runtime 汇总候选、决策台账和最终对象。
2. 淘汰赛 payload builder 生成固定层级数据。
3. 后续 HTML 渲染器只消费该 payload，不重新推导明日标的。

## What I Already Know

- `selection_workflow` 已有 N0-N9 推导链。
- `candidate-traces` 已有 per-candidate `workflow_path`、`checks`、`missing_data`、`final_action`。
- `decision-ledger` 已有 `anchor_reversal_decision`、`candidate_role`、`market_participation_qualification`、`position_plan_pct`、`planned_participation`。
- LLM Wiki 要求最终前台只消费 `final_target_resolution`。

## Requirements

- [x] R1: 定义并实现淘汰赛 payload builder，至少包含 trade_date、variant、final_action、layers。
- [x] R2: payload 固定包含板块层、板块内角色层、龙头反推层、价格行为层、盈亏比/账户层、最终收口层。
- [x] R3: 每层提供 input_count、eliminated_count、survivor_count、entries。
- [x] R4: 每个 entry 提供股票身份、层内状态、理由、下一层依据或淘汰依据。
- [x] R5: final_action 必须来自 `final_target_resolution` 或当前同源最终结构，不允许从普通候选重新挑明日标的。
- [x] R6: 对证据不足的层级输出明确缺失说明，不编造淘汰理由。

## Non-functional Requirements

### 性能
- 只使用已有 runtime/context/artifact 数据，不触发额外实时行情全量采集。

### 安全
- 无额外安全约束，沿用项目默认标准。

### 兼容性
- 兼容 replay 和 official 生成上下文。

### 可访问性
- 不适用；本子任务只产出结构化数据。

## Acceptance Criteria

- [x] AC-R1-1: builder 返回 dict payload，字段稳定且可 JSON 序列化。
- [x] AC-R2-1: payload 固定包含六层，顺序与需求一致。
- [x] AC-R3-1: 每层数量与 entries 状态可互相校验。
- [x] AC-R4-1: 2026-06-12 和远气体 entry 能显示板块锚/身份通过，并在风险或执行层说明不直接参与原因。
- [x] AC-R5-1: 当 final_target_resolution 为空或 0% 时，payload final_action 不从过程候选补出明日标的。
- [x] AC-R6-1: 缺少 evidence 时 entry reason 或 layer note 明确显示数据不足。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] Focused tests 覆盖 payload shape、唯一最终对象、2026-06-12 和远气体路径。
- [x] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 不实现 HTML 渲染。
- 不接入日报生成命令。
- 不改变现有交易判断规则。

## Technical Notes

### 参考来源
- `.trellis/tasks/06-13-sector-first-elimination-html/prd.md`
- `.trellis/tasks/06-13-sector-first-elimination-html/design.md`
- `scripts/report/selection_workflow.py`
- `scripts/report/two_layer_decision_payload.py`
- `scripts/report/runtime.py`
- `data/candidate-traces/2026-06-12.json`
- `data/decision-ledger/2026-06-12.json`

### 影响区域
- `scripts/report/` 下新增或扩展淘汰赛 payload builder。
- `tests/` 下新增 focused tests。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest <focused elimination payload tests>`
- `git diff --check`

## 落地结果

- 本轮未提交 commit。
- 代码：`scripts/report/elimination_tournament.py`。
- 测试：`tests/test_elimination_tournament.py`。
- 验证：`.generated/venv-py314/bin/python3.14 -m unittest tests.test_elimination_tournament` 通过，8 tests OK。
