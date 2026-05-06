# Report Contract

This reference is for report quality judgment. It is not a command manual.

## User-Facing Contract

- Say the conclusion first, then explain why.
- Keep the front page usable within two minutes.
- Make the action contract explicit: what to do, what confirms it, and what to do when conditions fail.
- Treat `没有永远是好的股，好的只有好的周期` as the trade-case soul: a stock can only be called good while its current cycle is good; when cycle evidence fades, the report must stop holding the "good stock" label and move to reduce, exit, or avoid.
- Treat replay markdown as the acceptance surface for report-output defects.
- Do not hide missing data behind fake precision such as `0.00%`.
- Do not repeat empty-position or no-trade conclusions.

## Anti-Noise And Price-Action Boundary

- Do not add external simulation, multi-agent, or free-form prediction language to the report front page.
- Do not use theory words such as `能量学`, `能量释放`, or `群体行为共振` as the reason for buy, add, or upgrade actions.
- Experience is allowed only after fieldization: prefer `上涨斜率`, `回撤比例`, `突破后承接`, `加速后衰竭`, `波动收敛`, and `板块内扩散强度`.
- Price-action fields may support candidate qualification, failure conditions, and unique action wording, but they must not bypass mainline confirmation, entry permission, 60分钟 confirmation, or 30分钟 stop rules.
- The energy model may guide research only after fieldization: 震荡=能量聚集, 行情=能量释放, but report decisions must use 上涨角度, 下跌角度, 上涨幅度, 调整幅度, 速度变化, and 加速后衰竭 instead of free theory prose.
- T+1避亏 is mandatory for trade-case review: if a stock already shows angle weakening, amplitude expansion, or speed imbalance at the report-date close, the report must say 不介入, reduce, or exit before the next trading day. 津药药业 is the regression sample: 2026-04-08 should flag no-entry/exit risk before the 2026-04-09 loss.
- Newton iteration decision discipline is allowed only as an operating method: begin with a coarse 1.0 judgment, use option sample feedback to revise it, and do not wait for a perfect answer. User-facing decisions must still use fieldized decision fields such as 强量转弱, 缩量冲高, 放量下杀, 上涨斜率放缓, 回撤比例, 收盘位置, and T+1 next-day action; do not turn Newton iteration into explanatory theory prose.

## Monthly Trading Rhythm

- Before daily stock selection, classify the month as 财报/季报防守月, ordinary attack month, or weak-market defense month.
- 财报/季报密集月 defaults to defense: calendar earnings months such as 4/8/10 are defensive by default even when no explicit monthly context is provided. Prioritize holding the account near 0% drawdown, reduce exposure, avoid earnings landmines, and only allow small trial entries for unusually strong setups.
- Non-earnings months default to attack: use market fit, mainline strength, and individual stock structure to decide whether a 10%-20% opportunity month is realistic.
- Weak market structure overrides the calendar: even outside earnings months, downgrade to defense when market fit and mainline strength are absent.
- Treat 10%-20% as an attack-window target, not a promised report outcome. The report should state the current month mode and maximum allowed position before naming trades.
- 月10cm is not a low bar. It is the attack-month acceptance line, not a monthly KPI; forcing every month to hit +10% will push the report toward bad trades.
- In attack months, +10% is qualified, 15% is excellent, and 20% is market-gift territory. The report may identify market-gift conditions, but must not imply the user can command them.
- A profit cushion is not a reason to downgrade. If price, mainline, and invalidation rules still act right, the report may hold or add; if the trend invalidates, the report downgrades.
- Surface the monthly attack/defense position as `仓位攻击等级` with fixed slabs: `C档0%`, `B档30%`, `A-档50%`, or `A档80%-100%`.

## Signal Grades And Position

- C = 0% observe only. Use when the setup is visible but not executable.
- B = 30% trial. Use for defense-month exceptions or attack-month probes that have not earned full commitment.
- A- = 50% standard attack. Use when non-earnings rhythm, market fit, mainline, and stock structure support participation but the candidate has not earned full commitment.
- A = 80%-100% buy-and-hold attack. Use only when A- conditions are already present, the month still allows attack, the candidate is the single clear core, the confirmation chain has acted right, and the invalidation price is clear.
- Final summary execution style must use the explicit state labels: `C档0% / 仅观察`, `B档30% / 10点确认后条件试错`, `A-档50% / 唯一对象执行`, or `A档80%-100% / 买定离手`.
- Final summary conclusion must also use the state-machine action label, not raw legacy `空仓等待 / 短线确认` language from upstream gates.
- B档 is not absolute empty-position: 一档（空仓档） is true C/0% no-trade; 二档（防守档） may still allow 10点确认后的30%条件试错. Do not render B as C, and do not make conditional defense read like permanent empty-position waiting.
- When B has no unique object yet, render it as `B档条件等待`; use `B档有条件试错对象` only after a concrete object exists.
- Profit is not a downgrade trigger. Do not cap a correct trend just because the month reached 10%; downgrade only when the trend, mainline, or invalidation price breaks.
- The hard part is not raising the target. It is A-grade courage when a true A setup appears, and C-grade patience when no setup appears.

## Future Change Inheritance

- Future daily-report requests use a delta spec by default: describe only the new or changed behavior.
- New requests default inherit this report contract unless the latest user instruction explicitly overrides it.
- Future report changes inherit both report contract and reasoning contract unless the latest user instruction explicitly overrides them.
- Future report changes also inherit `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md`: simulation tools stay out of the main chain, and trading experience enters only after becoming price-action fields.
- In practice, new report requests do not need to restate existing guardrails.

## Optimization Order

Use this order for broad report optimization:

1. report acceptance audit
2. structured history
3. only-focus audit
4. entry-cycle calibration
5. workflow memory
6. skill refactor

Workflow memory belongs after report acceptance, structured continuity, only-focus reasoning, and entry-cycle calibration are working well enough to preserve.

## Intent Notes

- `generate_report`: produce or replay the report artifact, then inspect whether the result reads like a trading decision surface.
- `review_report_output`: audit the generated markdown before trusting unit tests alone.
- `fix_report_defect`: isolate the visible defect, add a narrow test, patch the smallest responsible surface, and rerun replay/audit checks.
- `review_trade_case`: honor current position details, cost basis, account size, and the user's chosen trading frame. Do not convert workflow memory into stock observation continuity.
