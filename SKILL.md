---
name: a-daily-report
description: Use when handling natural-language A-share daily-report requests, report-output review, report defect fixes, trade-case reviews, workflow-memory extraction, or skill optimization in this repo.
---

# A Daily Report

This skill is a compact onboarding router for the daily-report repo. Treat the user request as natural-language intent; users do not need to remember commands.

## Trading Rhythm Base

Trading soul: 没有永远是好的股，好的只有好的周期。Before judging a stock as strong, first judge whether its current market cycle is still favorable. Once the cycle fades, stop defending the stock as "good" and switch the frame to exit, reduce, or avoid.

LLM Wiki base: stable trading knowledge lives in `wiki/` as Chinese nodes. Load `wiki/README.md` first when the request involves durable trading ideas, Chanlun, knowledge-base updates, or preventing report drift. For Chanlun, start from `wiki/交易思想/缠论体系.md`; keep raw source out of the report main chain and use `wiki/资料库/缠论原文索引.md` only for source tracing.

Energy exhaustion soul: 能量学只作为底层交易思想，必须字段化后进入系统。震荡=能量聚集，行情=能量释放；真正可执行的观察字段是上涨角度、下跌角度、上涨幅度、调整幅度、速度变化。等速运动最省力，若走势从等速变成加速冲顶或上涨速度放慢，按加速后衰竭/动能减少处理。T+1避亏要求在亏损日前一日收盘后识别风险，例如津药药业若在2026-04-08已经出现角度转弱、幅度扩散、速度失衡，就必须给出不介入/退出纪律，避免2026-04-09的确定性亏损。

Newton iteration decision discipline: this is a decision method, not a math display. Start with a coarse 1.0 judgment, test it against option sample feedback, and revise the next judgment instead of waiting for a perfect answer. For T+1, the skill must translate 强量转弱, 缩量冲高, 放量下杀, and 上涨斜率放缓 into fieldized decision fields and next-day action before the loss day confirms the risk.

Default monthly frame: 财报/季报密集期以防守为主；4/8/10 月这类财报/季报日历月即使没有显式月度上下文，也先按防守处理。核心目标是守住 0% and avoid earnings landmines; non-earnings months are the attack window, where the skill may look for 10%-20% opportunity months only after market fit, mainline strength, and stock structure confirm. Daily decisions inherit this monthly rhythm before judging individual setups.

Monthly target standard: 月10cm is not a low bar; treat it as the attack-month acceptance line, not a monthly KPI. In attack months, +10% is qualified, 15% is excellent, and 20% is market-gift territory. The skill should not raise targets by forcing trades; the real challenge is A-grade courage when the market gives a true A setup and C-grade patience when the market gives nothing.

Signal grades: C means observe only, B means 30% trial, A- means 50% standard attack, and A means 80%-100% buy-and-hold attack. Profit is not a downgrade trigger: a profit cushion can support holding or adding while the trend acts right; only trend invalidation, mainline fading, or a broken invalidation price downgrades the position.

B档 is not absolute empty-position: 一档（空仓档） means true C/0% no-trade, while 二档（防守档） can still keep 10点确认后的30%条件试错. Do not render B as C; the report must say whether the user is waiting because there is no setup, waiting as `B档条件等待`, or waiting for a specific 30% trial condition.

## Intent Routes

| Internal intent | When to choose it | First reference |
|-----------------|-------------------|-----------------|
| `generate_report` | User asks for a daily report, replay, summary, or fresh report artifact. | `references/report-contract.md`, then `references/reasoning-mode-contract.md`, then `references/verification.md` |
| `review_report_output` | User asks whether a report reads correctly, is useful, or matches prior wording preferences. | `references/report-contract.md`, then `references/reasoning-mode-contract.md` |
| `fix_report_defect` | User points to a concrete report bug, duplicated line, fake zero, missing action contract, broken replay, or a delta spec for report behavior. | `references/report-contract.md`, then `references/reasoning-mode-contract.md`, then `references/verification.md` |
| `review_trade_case` | User asks whether to buy, wait, cut, or review a specific stock or setup. | `references/report-contract.md` |
| `extract_workflow_memory` | User asks to preserve repeated workflow lessons, preferences, or report-quality defects for future agents. | `references/memory-governance.md` |
| `optimize_skill` | User asks to improve this skill, routing, references, the report contract, or the report workflow. | `references/report-contract.md`, then `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md`, then `references/reasoning-mode-contract.md`, then `references/memory-governance.md`, then `references/verification.md` |

## Priority Order

When the user gives broad optimization direction, preserve this order unless the latest user instruction narrows scope:

1. report acceptance audit
2. structured history
3. only-focus audit
4. entry-cycle calibration
5. workflow memory
6. skill refactor

## Operating Rules

- Prefer report usefulness over process ceremony: first make the output auditable, actionable, and honest.
- Treat future report-change requests as a delta spec: default inherit `references/report-contract.md` unless the latest user instruction explicitly overrides it.
- Treat reasoning as bounded decision support: future report changes inherit both report contract and reasoning contract unless the latest user instruction explicitly overrides them.
- Treat external simulations and free-form predictions as anti-noise boundary risks: they do not enter the report main chain unless a later approved spec turns them into auditable fields. Trading experience can be absorbed only after being translated into price-action fields such as `上涨斜率`, `回撤比例`, `突破后承接`, and `加速后衰竭`.
- Keep command details out of this file. Load `references/verification.md` only when concrete checks are needed.
- For defects, write or update a focused test first, then verify against replay markdown when the output surface matters.
- For memory extraction, create reviewable artifacts only. Do not auto-apply memory or build a memory platform.
- Latest user instruction overrides older memory, older plans, and this router.

## References

- `references/report-contract.md` - report acceptance, user-facing wording, trade-case boundaries.
- `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md` - anti-noise boundary for simulation tools and price-action fieldization.
- `references/reasoning-mode-contract.md` - no-API first reasoning decision JSON, boundaries, and no chain-of-thought output.
- `references/memory-governance.md` - review-artifact memory rules and safety boundaries.
- `references/verification.md` - practical replay, audit, unittest, and diff checks.
