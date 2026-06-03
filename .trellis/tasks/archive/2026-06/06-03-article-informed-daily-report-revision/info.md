# Technical Design: Opportunity-Cost Daily Report Revision

## Boundary

Goal: make the daily report compare old-position handling and new-entry promotion through risk price, risk-reward, and account fit before rendering 50% or 100%.

In scope: current task files, report decision payload, report rendering, acceptance audit, and focused tests.

Out of scope: new data vendors, broad backtesting, broker execution, and a full account optimizer.

Done: the 2026-06-03 replay cannot render unconditional `100%核心进攻` when risk-reward or planned participation is missing, and the report shows a clear opportunity-cost table.

## Design

Create one comparison record, then consume it everywhere.

```text
old position context
  + selected candidate
  + existing target-date price facts
  + LLM Wiki trading doctrine
        |
        v
opportunity_comparison.v1
        |
        +--> participation percentage cap
        +--> final action wording
        +--> opportunity-cost table
        +--> acceptance audit checks
```

The comparison record must answer three questions before a switch is allowed:

1. Is the old position actually weakening or a capital/risk burden?
2. Is the new target materially stronger than the old position?
3. Can the account carry the risk price if the target reverts to MA5/MA10/VWAP or invalidation?

If any answer is incomplete, the report may still display the candidate, but only as observation.

## Data Contract

Use `opportunity_comparison.v1` from `prd.md`. Keep the contract small and local to the report decision path. Do not introduce a new subsystem for this slice.

Required derived fields:

- downside to MA5/MA10/VWAP/invalidation,
- risk-reward state from the existing risk-reward helper,
- risk price comfort,
- stronger-opportunity result,
- capital-efficiency result,
- max participation percentage.

## Rendering Contract

The opportunity-cost table should appear before the final action section, so the participation percentage is backed by visible price risk. A suggested table:

| 对象 | 身份 | 当前/观察价 | MA5风险 | MA10风险 | VWAP风险 | 作废价 | 上方空间 | 盈亏比 | 账户结论 |
|------|------|-------------|---------|----------|----------|--------|----------|--------|----------|

Final wording rules:

- If missing risk prices: `只保留观察，等风险价格补齐`.
- If new target is stronger but buy point is stretched: `强度保留，执行等待回踩/收回窗口`.
- If old position weakens and new target is stronger with controllable risk: `先释放旧仓资金，只在固定交易窗口参与新核心`.
- If old position remains valid and new target does not win: `旧仓按原计划处理，新目标观察`.

## Implementation Slices

1. Add comparison helper and unit tests for missing price, valid ratio, invalid ratio, and stretched MA distance.
2. Wire comparison into final target / position decision repair so missing or unacceptable risk prevents 50%/100% rendering.
3. Render the comparison table and align final target process, account advice, execution plan, and final conclusion.
4. Extend acceptance audit to flag 50%/100% without calculable risk-reward or planned participation.
5. Regenerate `2026-06-03 --replay` and run focused report checks.

## Verification Plan

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_position_management_report`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context`
- Focused new/updated render and audit tests for the opportunity comparison.
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-03 --replay`
- Report acceptance audit for `reports/replay/2026-06-03_A股日报_完整版_replay.md`
- `git diff --check` for touched files.

## Risks

- Some price fields may not exist in the frozen replay snapshot. That is acceptable only if the report visibly downgrades to observation instead of inventing values.
- Existing renderers may duplicate final-action wording. The implementation should consume one comparison result rather than patching each sentence independently.
- Existing dirty worktree files are extensive; implementation must stage only files touched for this task.
