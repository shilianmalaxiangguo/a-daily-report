# 日报板块先行选股链路

状态：✅ 已完成

## Goal

记录 2026-06-12 用户对“日报选股应从板块路径切入，再在板块内筛核心对象”的明确确认，并把实际实现归并到已有任务 `06-11-daily-report-market-sector-leader-derivation`，避免两套并行任务重复改造同一条日报主链路。

## User Story

- **角色**：使用日报制定次日计划的交易者。
- **场景**：当前日报仍偏“个股池先行，再做板块校验”，用户确认更合理的方向是“板块先行，再做板块内角色分层和对象收口”。
- **目标**：后续实现沿用同一份板块先行推导设计，不再拆出一条重复任务。
- **成功标准**：实际代码实现、测试和验证都归入 `06-11-daily-report-market-sector-leader-derivation`；本任务不单独启动实现。

### 用户旅程

1. 用户确认“更应该像板块先行模型” -> 系统记录确认。
2. 系统检查已有 Trellis 任务 -> 发现 `06-11-daily-report-market-sector-leader-derivation` 已覆盖同一目标且处于执行中。
3. 系统切回已有任务继续执行 -> 不在本任务里创建重复设计或重复改动。

## What I Already Know

- `06-11-daily-report-market-sector-leader-derivation` 已有完整 `prd.md`、`design.md`、`implement.md` 和 `research/current-selection-workflow-evidence.md`。
- 该旧任务目标已经是“市场 -> 板块 -> 龙头 -> 价格行为 -> 账户条件”的严格板块推导。
- 本任务由用户在读取旧会话后确认执行而创建，核心 intent 与旧任务重叠。
- 为降低当前交付风险，本任务不作为新的实现入口。

## Requirements

- [x] R1: 实际实现必须继续使用 `06-11-daily-report-market-sector-leader-derivation` 的 PRD、design 和 implement 作为依据。
- [x] R2: 本任务不得引入第二套候选入口、板块评分或最终对象收口设计。
- [x] R3: 后续执行总结必须说明本任务只是确认记录，代码改动归属旧任务。

## Acceptance Criteria

- [x] AC-R1-1: 给定后续进入实现阶段，当前 Trellis active task 应指向 `06-11-daily-report-market-sector-leader-derivation`。
- [x] AC-R2-1: 给定本任务存在，仓库中不新增与旧任务冲突的独立 `design.md` 或 `implement.md`。
- [x] AC-R3-1: 给定阶段性总结，必须说明用户确认的方向和实际执行任务归属。

## Definition Of Done

- [x] 本 PRD 记录清楚用户确认、已有任务归属和不重复实现的边界。
- [x] active task 已切回 `06-11-daily-report-market-sector-leader-derivation`。

## Out Of Scope

- 不在本任务内实现代码。
- 不新建第二套板块先行模型。
- 不覆盖旧任务已有 PRD、design、implement。

## Technical Notes

### 参考来源

- `codex://threads/019ebc49-1458-7812-ac3f-5dba04017d23`
- `.trellis/tasks/06-11-daily-report-market-sector-leader-derivation/prd.md`
- `.trellis/tasks/06-11-daily-report-market-sector-leader-derivation/design.md`
- `.trellis/tasks/06-11-daily-report-market-sector-leader-derivation/implement.md`

### 影响区域

- `.trellis/tasks/06-12-sector-first-daily-selection/prd.md` — 仅记录任务归属，不作为实现入口。

## Verification

- `.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py current --source`

## 落地 commit

待旧任务实现完成后在旧任务回填。

## Notes

- 本任务是执行确认记录，不需要单独 `design.md` / `implement.md`。
