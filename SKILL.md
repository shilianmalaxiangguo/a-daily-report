---
name: a-daily-report
description: Use when handling natural-language A-share daily-report requests, report-output review, report defect fixes, trade-case reviews, workflow-memory extraction, or skill optimization in this repo.
---

# A Daily Report

This skill is a compact onboarding router for the daily-report repo. Treat the user request as natural-language intent; users do not need to remember commands.

## Trading Rhythm Base

Trading soul: 没有永远是好的股，好的只有好的周期。Before judging a stock as strong, first judge whether its current market cycle is still favorable. Once the cycle fades, stop defending the stock as "good" and switch the frame to exit, reduce, or avoid.

LLM Wiki base: stable trading knowledge lives in `wiki/` as Chinese nodes. Load `wiki/README.md` first when the request involves durable trading ideas, Chanlun, knowledge-base updates, or preventing report drift. For Chanlun, start from `wiki/交易思想/缠论体系.md`; keep raw source out of the report main chain and use `wiki/资料库/缠论原文索引.md` only for source tracing.

Data source base: fresh daily generation is Tushare-first for speed, stability, and snap-ui public data completeness. AkShare and iwencai are fallback only; do not begin the daily report run by calling them for base market facts when a Tushare path exists. Current market-activity service exits include `stock_hot_rank` via `ths_hot(market="热股")`, `limit_pool_snapshot` via `limit_list_ths` / `limit_list_d`, `sector_hot_plates` via `ths_hot(market="概念板块"/"行业板块")`, `sector_change_rank` via `ths_index` + `ths_daily`, `sector_fund_flow` via `moneyflow_ind_ths`, `lhb_snapshot` via `top_list`, and `new_stock_calendar` via `new_share`, with old THS/AkShare/iWenCai/Tencent/finshare/Sina paths as degraded fallback. This repo uses a Tushare gateway, not the default public endpoint: keep `scripts/market_data/tushare_client.py::create_tushare_pro_api` and `TUSHARE_HTTP_URL` (`http://118.89.66.41:8010/`) in the path. Official basic usage reference: `https://tushare.pro/document/2?doc_id=14`. Durable contract: `wiki/运行契约/日报数据源契约.md`.

Runtime base: Python 3.14-first for local checks and report work when dependencies are available; do not silently fall back to 3.11. If the 3.14 environment lacks required packages, say that explicitly and either use the current populated venv for that run or create/install a 3.14 venv as a separate, intentional setup step.

Decision-processing base: data and news are raw material, not the edge. The skill must turn raw facts into a processing layer: trend-chain position, relative-price feedback, angle/amplitude/speed change, participation window, missed-entry plan, and invalidation. A report is useful only when it converts today's facts into tomorrow's designed scenarios instead of repeating information everyone can see.

Energy exhaustion soul: 能量学只作为底层交易思想，必须字段化后进入系统。震荡=能量聚集，行情=能量释放；真正可执行的观察字段是上涨角度、下跌角度、上涨幅度、调整幅度、速度变化。等速运动最省力，若走势从等速变成加速冲顶或上涨速度放慢，按加速后衰竭/动能减少处理。T+1避亏要求在亏损日前一日收盘后识别风险，例如津药药业若在2026-04-08已经出现角度转弱、幅度扩散、速度失衡，就必须给出不介入/退出纪律，避免2026-04-09的确定性亏损。

Newton iteration decision discipline: this is a decision method, not a math display. Start with a coarse 1.0 judgment, test it against option sample feedback, and revise the next judgment instead of waiting for a perfect answer. For T+1, the skill must translate 强量转弱, 缩量冲高, 放量下杀, and 上涨斜率放缓 into fieldized decision fields and next-day action before the loss day confirms the risk.

Default monthly frame: 财报/季报密集期提高证据要求，但不再自动压成小仓或空仓。4/8/10 月这类财报/季报日历月仍要识别财报地雷、提高取消条件、尊重失效价；但只要存在合格标的且大盘不是冰点，仓位仍按 50% / 100% 进攻仓位三态处理。Daily decisions inherit this monthly rhythm before judging individual setups.

Monthly target standard: 月10cm is not a low bar; treat it as an acceptance line for an opportunity month, not a monthly KPI. +10% is qualified, 15% is excellent, and 20% is market-gift territory. The skill should not raise targets by forcing trades; the real challenge is 100% courage when the market gives a true core setup, 50% commitment when a valid setup appears, and 0% patience when the market gives nothing.

Attack position states: the current strategy uses only 0%, 50%, and 100%. 0% means no qualified target, market ice point, broken trend chain, or invalidation already present. 50% means a valid attack target with market fit, trend chain, participation window, and stock structure. 100% means the clear core target with active trend chain, explicit participation window, acceptance that acts right, and a clear invalidation price. The 100% state must pass six checks: unique core target, active trend chain, explicit participation window, acceptance acting right, clear invalidation price, and non-ice-point market. Profit is not a downgrade trigger: a profit cushion can support holding or adding while the trend acts right; only trend invalidation, mainline fading, or a broken invalidation price downgrades the position.

Extreme-conviction participation script: `明日极度看好` is a pre-rehearsal list, not an observation list. Each item must carry a participation script covering auction, first minutes, board, reseal, missed-entry, and cancellation. If a stock is too fast to buy, the script must say whether to shift down the trend-chain relative-price candidate or skip the phase; it must not invent a late chase.

Decision ledger persistence: the participation script must enter the local decision ledger as machine-readable `planned_participation`, at both case-level and mention-level, so later replay can compare tomorrow's behavior against the designed scenario.

Participation replay: after next-day facts exist, write `participation_review` as the 参与预演复盘 field. It must use explicit fact inputs (`auction_matched`, `first_minutes_accepted`, `board_sealed`, `reseal_success`, `sector_supported`, `cancellation_triggered`, `primary_unavailable`, `missed_action_worked`) and controlled labels: `预演命中`, `预演作废`, `错过后方案命中`, `预演过早`, or waiting for more facts. The decision-ledger index also carries `participation_review_status` so snap-ui can surface review quality in lists.

Legacy conservative sizing is removed: 0/50/100 only. Do not answer uncertainty by shrinking every opportunity; risk control is expressed through 0%, cancellation conditions, invalidation price, and missed-entry handling.

## Intent Routes

| Internal intent | When to choose it | First reference |
|-----------------|-------------------|-----------------|
| `generate_report` | User asks for a daily report, replay, summary, or fresh report artifact. | `wiki/运行契约/日报数据源契约.md`, then `references/report-contract.md`, then `references/reasoning-mode-contract.md`, then `references/verification.md` |
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
