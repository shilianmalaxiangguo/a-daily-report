# Report Contract

This reference is for report quality judgment. It is not a command manual.

## User-Facing Contract

- Say the conclusion first, then explain why.
- Keep the front page usable within two minutes.
- Make the action contract explicit: what to do, what confirms it, and what to do when conditions fail.
- Treat data and news are raw material as the first principle: the report edge is the processing layer that converts common facts into trend-chain position, relative-price feedback, angle/amplitude/speed change, participation windows, missed-entry plans, and cancellation rules.
- The daily report is tomorrow's rehearsal. Every high-conviction path should be a designed scenario, not an after-the-fact explanation.
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

## Mainline Capacity And Regime

- The front page must render `主线容量与格局判断` before the turnover-share trend evidence table.
- `主线容量` answers how many lines current liquidity can support. It uses today's turnover, yesterday's turnover, daily change, and the recent 25-trading-day turnover median; do not publish fixed turnover experience anchors as public rules.
- `主线确认` must come from fund attack evidence: net inflow, high-position strength, batch limit-ups, broad sector gains, strong gain clusters, or turnover-share expansion. A news topic, hot phrase, or isolated stock move is not enough.
- `主线格局` must allow `无主线`, `单主线聚焦`, `双主线竞争`, `主线+背景线`, `混沌接力`, and `多主线牛市`. Outside bull or super-bull markets, three or more active directions usually means chaotic relay, rolling rotation, or no stable mainline.
- `主线进程` is post-confirmation stage language such as 启动, 推进, 加速, 分歧承接, 斜率放缓, or 衰竭. It must not replace the initial fund-attack confirmation.
- Keep `主线成交额占比趋势` as evidence, but do not treat today's line label as proof of tomorrow's continuation.

## Monthly Trading Rhythm

- Before daily stock selection, classify the month as 财报/季报高筛选月, ordinary attack month, or weak-market defense month.
- 财报/季报密集月 raises evidence requirements but no longer automatically caps position. Calendar earnings months such as 4/8/10 require earnings-landmine checks, stricter cancellation conditions, and clear invalidation prices; if a qualified target exists and the market is not at ice point, the position still follows the 50% / 100% attack states.
- Non-earnings months default to attack: use market fit, mainline strength, and individual stock structure to decide whether a 10%-20% opportunity month is realistic.
- Weak market structure overrides the calendar: even outside earnings months, use 0% when market fit and mainline strength are absent.
- Treat 10%-20% as an attack-window target, not a promised report outcome. The report should state the current month mode and maximum allowed position before naming trades.
- 月10cm is not a low bar. It is the attack-month acceptance line, not a monthly KPI; forcing every month to hit +10% will push the report toward bad trades.
- In attack months, +10% is qualified, 15% is excellent, and 20% is market-gift territory. The report may identify market-gift conditions, but must not imply the user can command them.
- A profit cushion is not a reason to downgrade. If price, mainline, and invalidation rules still act right, the report may hold or add; if the trend invalidates, the report downgrades.
- Surface the monthly attack/defense position as `进攻仓位三态` with fixed slabs: `0%`, `50%`, or `100%`.

## Attack Position States

- 0% = no participation. Use only when there is no qualified target, the market is at ice point, the trend chain is broken, or the invalidation condition has already appeared.
- 50% = standard attack. Use when market fit, trend chain, participation window, and stock structure support a valid target, even if the target has not earned full-core status.
- 100% = full attack. Use when the candidate is the clear core target, the trend chain is active, the participation window is explicit, acceptance has acted right, and the invalidation price is clear.
- 100% must pass six checks before it appears in the decision payload: unique core target, active trend chain, explicit participation window, acceptance acting right, clear invalidation price, and non-ice-point market.
- Final summary execution style must use the explicit state labels: `0% / 不参与`, `50% / 标准进攻`, or `100% / 核心进攻`.
- Final summary conclusion must also use the state-machine action label, not raw legacy `空仓等待 / 短线确认` language from upstream gates.
- Legacy conservative sizing is removed: 0/50/100 only. Do not answer uncertainty by shrinking every opportunity.
- Risk control happens through scenario cancellation, invalidation price, market ice-point detection, and the 0% state; it should not quietly downgrade every valid opportunity into a small trial.
- Profit is not a downgrade trigger. Do not cap a correct trend just because the month reached 10%; downgrade only when the trend, mainline, or invalidation price breaks.
- The hard part is not raising the target. It is 100% courage when a true core setup appears, 50% commitment when a valid opportunity appears, and 0% patience when the market gives nothing.

## Extreme-Conviction Participation Script

- `明日极度看好` is a pre-rehearsal list, not an observation list.
- Each item must include a participation script covering auction, first minutes, board, reseal, missed-entry, and cancellation.
- The script must express risk control through cancellation, invalidation, and 0%, not by quietly shrinking every valid opportunity.
- For fast limit-up cases, the script must distinguish auction participation, first-minutes attack, board participation, reseal participation, and missed-entry handling. If the core target is unavailable, either shift down the same trend-chain relative-price candidate or skip the phase.
- The participation script must be persisted to the local **本地判断账本** as machine-readable `planned_participation`, not only displayed in Markdown.
- `planned_participation` must include participation window, position state, auction, first-minutes, board, reseal, missed-entry, and cancellation.
- `planned_participation` must also include `source_tier`, `entry_timing`, and `buy_window`. Controlled `entry_timing` values are `open_core`, `ten_confirm`, `tail_exception`, and `no_trade`.
- `planned_participation` must include the extreme-conviction-only reversion probe fields: `ma_reversion_probe_allowed`, `ma_reversion_window`, `ma_reversion_probe`, `intraday_yellow_line_probe`, `ma20_invalidation`, and `tracking_window_trade_days`.
- `planned_participation` must include the limit-up inertia fields: `limit_up_inertia_level`, `limit_up_inertia_score`, `next_day_limit_probability_band`, and `limit_up_inertia_reason`. Yesterday's limit-up, multi-board, T-board, sector anchor, and mainline core samples cannot be collapsed into the same "observe" bucket as +1%, +3%, or +5% ordinary rises.
- `planned_participation` must include the risk-reward fields: `risk_reward_min_ratio`, `risk_reward_ratio`, `risk_reward_state`, and `risk_reward_plan`. MA5/MA10 or intraday yellow-line reversion is actionable only when the plan can explain the expected upside versus MA20 or other invalidation risk; default minimum is `2:1`.
- The visible participation script must show `跟踪周期` as `25个交易日` by default, so the report reader can see that each extreme-conviction sample enters a finite review cycle instead of disappearing into a hidden data field.
- Strong core cases such as T-board, limit-up relay, mainline core, sector anchor, trend-chain anchor, or divergence-to-consensus must not hide behind ordinary 60-minute confirmation; they use `open_core` unless the plan explicitly says no trade.
- MA5/MA10 or intraday yellow-line reversion is not a general low-buy rule. It is only a small-probe path for the prior day's `明日极度看好` list, and it requires 09:50-10:10 support confirmation; MA20 failure cancels the thesis as A-kill risk.
- Ordinary extreme-conviction cases use `ten_confirm`; tail participation is only `tail_exception`; crossline or ordinary watch samples use `no_trade` and cannot be counted as extreme-conviction execution wins.
- Store `planned_participation` at case-level and mention-level: case-level records the current designed plan; mention-level preserves what the original report said, so replay can compare tomorrow's behavior against the designed scenario.
- After next-day facts exist, store the replay result as `participation_review`. This is the **参与预演复盘** field, not a free-form commentary field.
- `participation_review` must be derived from explicit facts: `auction_matched`, `first_minutes_accepted`, `board_sealed`, `reseal_success`, `sector_supported`, `cancellation_triggered`, `primary_unavailable`, and `missed_action_worked`.
- `participation_review` labels are controlled: `预演命中`, `预演作废`, `错过后方案命中`, `预演过早`, or waiting for more facts.
- The decision-ledger index must expose `participation_review_status` plus a compact `participation_review` summary for snap-ui list consumption.
- The report tail must render both `极度看好25日跟踪表` and `极度看好历史回测表`. The backtest table must separate selection quality, buy-point quality, risk-reward, execution review, and standard action; it must not collapse "stock picked right" into "trade executed right".
- snap-ui must consume `planned_participation` from the decision-ledger artifact. It must not implement a separate buy/sell timing algorithm for the same case.

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
