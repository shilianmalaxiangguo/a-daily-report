# 2026-06-10 前台观察对象资格根因规格

状态：✅ 已执行

## Goal

修复“过程候选被抬成前台最终观察对象”的底层问题。候选池必须在生成时写清每只股票是否具备前台观察资格，运行时只能消费这个资格，不能再仅凭 `降级观察`、`观察对象`、候选排序或旧字段把过程样本放到前台。

## In Scope

- `selection_workflow.v1` 候选池新增前台观察资格字段。
- `final_target_resolution.watch_target` 只从具备前台观察资格的候选中产生。
- 保留雅克科技式主线容量观察样本作为前台观察对象的能力。
- 阻断双星新材式板块锚缺失、仅过程观察样本被放到前台。
- 补充失败样本和保留样本测试。

## Out of Scope

- 不重写上游行情、评分、板块锚识别或涨跌归因。
- 不把 2026-06-11 的走势反向写进 2026-06-10 当时的判断。
- 不新增自动回测、外部实时数据抓取或交易执行逻辑。
- 不调整 Bear HTML 和 Mermaid HTML 的视觉样式。

## Non-goals

- 不证明某只个股必然正确。
- 不用单日涨跌替代候选资格判断。
- 不删除过程候选、历史观察或失败样本。

## Root Cause

旧链路只定义了“最终执行对象”的严格资格：`可作为主对象` + 执行窗口 + 回到 0% 条件。当前报告为 0% 时，最终执行对象为空。

但另一路 `final_target_resolution.watch_target` 会从候选池里寻找观察对象。旧逻辑把 `status == 降级观察` 或 `reversal_decision == 降级观察` 当成足够条件，导致“只是过程观察样本”的股票也有机会因为排序靠前进入前台。

这就是 `雅克科技 / 双星新材 / 中船特气 / 金安国纪` 混乱感的根因：不是 HTML 名称错，而是候选身份和前台观察资格之间缺少机器字段。

## Contract: `selection_workflow_candidate.front_observation`

候选池每行必须新增：

```python
{
    "front_observation_qualified": True | False,
    "front_observation_reason": "str",
    "observation_layer": "front_observation | process_observation | execution_object",
}
```

### 资格规则

- `final.execution_object` 仍是唯一明日执行对象来源。
- `front_observation_qualified == True` 只能表示“可放到前台观察”，不能表示可新增参与。
- `anchor_reversal_decision == "可作为主对象"` 且角色是板块锚/主线核心，可保留前台观察资格，即使仓位结论是 0%。
- `anchor_reversal_decision == "降级观察"` 时，只有主线核心、大容量中军、分支龙头等可解释为“仍值得前台跟踪”的候选，才可保留前台观察资格。
- `candidate_role in {"观察样本", "跟风样本", "过程候选", "低位补涨", "套利工具"}` 默认只能作为过程观察样本。
- 缺少板块锚、不能解释为什么不做本板块锚、仅涨停/连板/高分的样本，只能进入过程证据。
- `runtime` 消费 `selection_workflow.candidate_pool` 时，优先读取 `front_observation_qualified`；没有这个字段的旧数据只允许用“可作为主对象 + 核心角色”的保守兼容路径。

## Acceptance Criteria

- AC-1: 给定候选池里双星新材是 `降级观察 + 观察样本 + 本板块锚未识别`，运行时不得把它写入 `watch_target`。
- AC-2: 给定候选池里雅克科技是 `降级观察 + 大容量中军 + 主线内核`，运行时可以把它写入 `watch_target`，但仓位仍为 0%。
- AC-3: 给定候选池里豫能控股是 `可作为主对象 + 板块锚`，即使最终仓位为 0%，仍可作为前台观察对象。
- AC-4: 给定报告无明日执行对象，任何 `watch_target` 都不得生成 `new_entry_target` 或执行命中。
- AC-5: Mermaid / 审计说明必须能看到“过程候选”和“前台观察对象”的区别。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow tests.test_report_runtime.ReportRuntimeTest.test_final_target_resolution_skips_process_observation_and_keeps_front_observation tests.test_report_runtime.ReportRuntimeTest.test_runtime_final_resolution_keeps_workflow_core_as_watch_target_when_position_is_zero tests.test_report_runtime.ReportRuntimeTest.test_zero_participation_downgraded_anchor_sample_does_not_become_final_watch_target`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-10_A股日报_完整版.md --json`

## Verification Result

- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/selection_workflow.py scripts/report/runtime.py tests/test_selection_workflow.py tests/test_report_runtime.py`：通过。
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow tests.test_report_runtime tests.test_report_acceptance_audit tests.test_next_day_attribution`：351 tests OK。
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-10_A股日报_完整版.md --json`：`passed=true`。
- `reports/2026-06-10_日报选股推导逻辑_mermaid.html` 静态结构校验：6 个 Mermaid 块，包含 `front_observation_qualified` / `process_observation` / 雅克科技 / 双星新材过程样本说明，旧的“按第一个候选”口径已移除。
- `reports/2026-06-10_次日归因闭环_mermaid.html` 静态结构校验：3 个 Mermaid 块，包含 `front_observation_qualified` / `observation_layer` / 雅克科技 / 双星新材过程样本说明；系统 Chromium 自动截图在当前环境挂起，已停止残留进程。

## Spec Sync

- 已同步到 `.trellis/spec/backend/quality-guidelines.md` 的 `Daily Report Front Observation Qualification Contract`。
