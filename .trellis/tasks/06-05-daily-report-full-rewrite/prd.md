# brainstorm: daily report full rewrite

## Goal

Rewrite the daily report on top of the existing two-layer rewrite spec so the report is readable as a decision product: the reader first sees the final next-day conclusion, then sees a traceable derivation from data, candidate pool, scoring, candidate contraction, account constraints, and final single target. The rewrite should remove the current feeling that STEP sections are noisy, fragmented, and disconnected.

## What I already know

* The user now wants the full rewrite, not another local patch.
* The main pain is daily report composition and readability: the report is too long, too mixed, and the STEP output does not read like a coherent chain.
* The user wants the report to center on mainline decomposition, sector analysis, and market analysis before stock selection. The report must explain what happened in the market, whether the market is near ice point or climax, where funds are flowing, and what approximate position stance follows.
* The user wants to include their unique `超车 / 失速 / 窗口` module: identify which sectors are stronger than expected, which sectors are weaker than expected, and which sectors are better than expected and more worth doing.
* The previous spec `docs/superpowers/specs/2026-06-05-daily-report-two-layer-rewrite-design.md` is the base document and should be modified rather than replaced from scratch.
* That previous spec already defines a useful two-layer shape: front decision layer plus derivation audit layer.
* The 2026-06-04 replay still shows the readability problem: front-page conclusion, five-judgment review, final target process, account advice, discipline tables, derivation chain, STEP audit, and appendix evidence all compete early in the report.
* The same replay now aligns the final identity better: `明日执行对象：无`, `最终结果：观察对象：豫能控股(001896)`.
* The current derivation still does not explain enough: `上海石化(600688)` is shown as a process candidate replaced by final resolution, but the replacement reason does not clearly say which scoring or qualification item it lost on.
* Existing code already has partial contracts for final target resolution, sniper target derivation, two-layer decision payload, candidate quality, front-page rendering, and report acceptance audit.
* The durable rewrite likely needs a unified candidate verdict packet upstream of rendering, not only renderer alignment.

## Assumptions (temporary)

* The report should optimize for one mental path: `数据与候选 -> 推导裁决 -> 最终对象 -> 怎么执行或不执行 -> 风险与复盘`.
* Better revised mental path: `市场阶段 -> 资金结构 -> 板块关系 -> 板块周期/超车失速窗口 -> 龙头验证 -> 仓位姿态 -> 候选裁决 -> 最终对象 -> 明日行动`.
* The mainline decomposition should include expectation-relative analysis, not only absolute strength ranking.
* Individual stocks are downstream evidence. The report should not start from stocks; it should first analyze market, funds, sectors, and sector relationships, then use leader/core stocks to validate the sector conclusion.
* The report should not expose every internal module as a top-level section.
* Long market/background/review content can stay, but must move behind the decision and derivation spine.
* STEP sections should stop being generic blocks and become a compact decision ledger: each step says input, judgment, passed forward, rejected, and reason.
* The final daily report should normally select one primary final object: either one execution object or one observation object. Other candidates are process evidence.

## Open Questions

* Should the unified verdict packet use the proposed "pipeline spine plus candidate review dimensions" structure, or should any section be allowed to produce an independent final object?

## Requirements (evolving)

* Build on the previous two-layer rewrite spec.
* Make the report readable before it is exhaustive.
* User selected a full-derivation-first opening: the report should first show how data, candidate pool, scoring, contraction, account constraints, and final conclusion connect before moving into the next-day action details.
* User selected a pyramid / total-detail-total report shape: start with a full conclusion and proof spine, expand into detailed derivation, then close with the final action recap.
* User is concerned that a full main-flow rewrite may delete or ignore existing useful data conclusions. The rewrite must protect and relocate useful current outputs instead of dropping them.
* User selected protected implementation depth option 2: build the unified verdict packet and pyramid report structure first, then migrate existing useful data conclusions into the new structure instead of deleting them.
* The opening layer must first show the derivation spine, then immediately answer the next-day action before entering long market background or appendix evidence.
* The report must have one visible final conclusion packet shared by front page, final target process, action plan, final conclusion, candidate quality, and appendix.
* Candidate selection must read as one pool judged by multiple dimensions, then narrowed by a sequential contraction process.
* Each rejected or downgraded candidate needs a human-readable reason from the same scoring/qualification dimensions, not a circular reason like "not selected by final resolution".
* STEP output must be reorganized into a consistent compact template.
* Process evidence must remain available, but it should be visually and structurally secondary.
* Existing useful conclusions and data sections must be inventoried before deletion or relocation.
* Removing a current section is allowed only after mapping its useful content to the new report structure or explicitly marking it out of scope with user approval.
* The first implementation slice should introduce the unified verdict packet and a migration map, not hand-delete old report sections.
* Main body must retain these data conclusions:
  * market background and position reason,
  * mainline / sector strength,
  * candidate pool win/loss table,
  * final object execution or observation conditions,
  * risk review and no-participation reason,
  * historical judgment correction.
* Historical judgment correction should appear immediately after the opening derivation overview.
* Opening derivation overview should be one verdict summary table, not prose-first.
* Verdict summary table must show the top 3 rejected/downgraded candidates and their reasons.
* Rejected/downgraded candidate reasons use fixed five dimensions: mainline/sector, stock structure, funds confirmation, account fit, and risk/missing data.
* Five-dimension results in the opening table use short labels, not numeric scores or long prose.
* The closing summary should be a next-day action checklist.
* Report emphasis: mainline decomposition, sector strength, market stage, and fund direction are first-class analysis layers. Candidate selection must be downstream of those layers, not a standalone stock-ranking exercise.
* Sector relationships are a first-class analysis layer. The report must explain relationships such as mainline, rival line, replacement, inheritance, rotation, resonance, siphoning, and slowdown before producing the final candidate verdict.
* `超车 / 失速 / 窗口` is a first-class main-body module, not appendix-only:
  * `超车`: which sector or line is becoming stronger than expected versus rivals.
  * `失速`: which expected line is weakening, stalling, or failing to confirm.
  * `窗口`: topic window, not trading time window; whether the stronger-than-expected line is in first confirmation, early diffusion, or still has expectation gap before overheating.
* `超车 / 失速 / 窗口` should appear after sector relationships and before leader/core stock validation.
* Opening verdict summary table should include one compact `超车 / 失速 / 窗口` summary sentence.
* Trading time windows such as `09:30-09:35` and `09:50-10:10` belong in the final next-day action checklist, not in the `超车 / 失速 / 窗口` market-analysis module.
* Topic-window labels must use the user's cycle-theory language: `启动`, `发酵`, `高潮`, `退潮`, `冰点`.
* Cycle labels must be assigned at both levels: whole-market stage and each mainline/sector stage.
* The report must support divergence such as "whole market in retreat while one sector is starting or fermenting"; this divergence should directly affect position stance and candidate verdict.
* Confirmed top-level report order:
  1. Market-wide stage.
  2. Fund structure.
  3. Sector relationships.
  4. Overtake / slowdown / topic window.
  5. Leader/core stock validation.
  6. Position stance.
  7. Candidate pool verdict.
  8. Final object.
  9. Next-day action checklist.
* Fund structure has two layers:
  * market-level risk appetite: increment/shrinkage, rising/falling breadth, limit-up/limit-down spread, and turnover concentration;
  * sector-level migration: which sectors attract funds, which sectors are drained, and which sectors are only rotation pulses.
* Sector relationship table should compare the top 3 core directions by default: mainline, rival line, and potential overtake line.
* Leader/core validation should check one core anchor and one elastic vehicle for each core direction by default.
* Position stance has only three allowed levels: `100%核心进攻`, `50%标准进攻`, and `0%不参与`. No small-position tier should be introduced.
* Position stance should be decided mainly by market stage, market-level fund risk appetite, and sector topic window. Candidate quality can validate the decision but must not override the upstream market/fund/sector conclusion alone.
* `100%核心进攻` requires market/mainline/funds/object resonance, and should primarily capture startup or fermentation confirmation rather than blindly chasing climax:
  * whole market is not in ice point and market-level risk appetite supports attack;
  * the strongest executable mainline is in `启动` or `发酵`, with topic window still present and not already overheated;
  * funds concentrate into that mainline, not only scattered one-day pulses;
  * both the core anchor and elastic vehicle confirm, proving the direction has both stability and attack elasticity.
* `高潮` should not automatically mean `100%核心进攻`; the report must check whether it is still an executable climax or already close to slowdown/retreat.
* `50%标准进攻` applies when participation is allowed but the setup is not strong enough for full core attack:
  * whole market is not in ice point, and the strongest executable mainline is not in ice point;
  * at least one executable sector/mainline is in `启动` or `发酵`, or a topic window is opening but not yet fully confirmed;
  * funds show usable confirmation, but concentration, continuity, or breadth is not strong enough for `100%核心进攻`;
  * core anchor or elastic vehicle confirms the direction, but not both at full strength;
  * final object can only be executed after the next-day price/fund conditions appear.
* `0%不参与` should be reserved for true ice-point conditions, not ordinary candidate weakness or local disagreement:
  * whole-market ice point: broad market risk appetite collapses, such as index-level heavy decline, weak breadth, many limit-down/deep-water names, and no clear fund participation across the market;
  * strongest-mainline ice point: the current strongest mainline itself collapses, such as power-related high targets all limit-down/deep-water, sector breadth broadly weak, and the mainline loses execution qualification.
* Market ice point is broader than one hot line failing. It means the whole street is empty, not only the central shopping mall: the whole market has no participation, not just the current mainline.
* If the market is not in ice point and the strongest mainline is not in ice point, the report should usually choose between `100%核心进攻` and `50%标准进攻`, while downgrading or rejecting individual candidates inside the candidate verdict rather than turning the whole report into `0%不参与`.
* `50%标准进攻` is the default conditional-participation stance for non-ice-point markets when the report can identify a usable direction but still needs next-day confirmation.
* User-visible wording must use trading language such as conditions, qualification, executable, observation object, participate, not participate.
* The unified verdict packet should be a pipeline spine, not a set of parallel independent opinions:
  * market-wide stage decides whether the day has participation qualification and what cycle label applies;
  * fund structure decides whether risk appetite and sector migration support attack;
  * sector relationships decide which direction is mainline, rival line, replacement line, or overtake line;
  * `超车 / 失速 / 窗口` decides which direction is stronger/weaker than expected and whether the topic window is still usable;
  * leader/core validation checks whether each important direction has core-anchor and elastic-vehicle confirmation;
  * position stance converts upstream conclusions into `100%核心进攻` / `50%标准进攻` / `0%不参与`;
  * candidate pool verdict compares stocks only after the above conclusions, using the same five dimensions for winner and rejected/downgraded candidates;
  * final object selects one execution object or one observation object from the candidate verdict and carries its execution/observation conditions;
  * next-day action checklist restates the final object, position stance, execution conditions, failure conditions, and old-position handling.
* Candidate verdict can use "multiple reviewer dimensions" only inside the same candidate pool:
  * mainline/sector fit;
  * stock structure;
  * funds confirmation;
  * account fit;
  * risk/missing data.
* No report section should be allowed to independently name a different final object after the final object packet is built. Later sections may only explain, reject, downgrade, or add conditions to the packet object.

## Unified Verdict Packet Field Contract (evolving)

The first implementation should extend the existing two-layer decision payload toward a single daily verdict packet. The packet can still be assembled from current modules, but all action-facing renderers must read from this packet.

### Top-level fields

| Field | Meaning | Must answer |
|---|---|---|
| `target_date` | Report date | Which trading day is being judged |
| `schema_version` | Payload contract version | Which renderer/audit contract applies |
| `opening_verdict` | First-screen summary table source | What is the final answer and proof spine |
| `market_stage` | Whole-market cycle and participation background | Is the market in `启动 / 发酵 / 高潮 / 退潮 / 冰点` |
| `fund_structure` | Market-level and sector-level funds | Are funds adding risk, leaving, concentrating, or rotating |
| `sector_relationships` | Mainline/rival/overtake/replacement map | Which sector relationship explains today |
| `overtake_slowdown_window` | Expectation-relative module | What is stronger than expected, weaker than expected, and still worth doing |
| `leader_core_validation` | Core anchor and elastic vehicle check | Does the chosen direction have stability and attack elasticity |
| `position_stance` | 100% / 50% / 0% conclusion | How much can participate and why |
| `candidate_pool_verdict` | Same-pool stock comparison | Which stock wins, which lose, and on what dimensions |
| `final_object` | Single object identity | One execution object, one observation object, or no object |
| `next_day_action` | Closing checklist source | What to do, what not to do, and when old positions come first |
| `historical_correction` | Historical judgment correction | Which prior judgment was corrected and how it affects tomorrow |
| `section_migration_map` | Preservation map | Where each old useful section moved, merged, or stayed |

### Layer field requirements

#### `market_stage`

Required fields:

| Field | Meaning |
|---|---|
| `cycle_label` | One of `启动 / 发酵 / 高潮 / 退潮 / 冰点` |
| `participation_qualification` | `可参与 / 条件参与 / 不参与` |
| `breadth_evidence` | Rising/falling breadth, limit-up/limit-down spread, deep-water spread |
| `index_pressure` | Index-level pressure such as heavy decline or stability |
| `turnover_evidence` | Turnover expansion/shrinkage and concentration |
| `conclusion` | One short sentence explaining the market background |
| `passes_forward` | Whether the report may continue to funds/sector analysis |

This layer cannot select an individual stock.

#### `fund_structure`

Required fields:

| Field | Meaning |
|---|---|
| `market_risk_appetite` | Increment, shrinkage, defensive, or mixed |
| `sector_migration` | Which sectors attract funds, lose funds, or only rotate |
| `concentration` | Whether funds are concentrated enough to support attack |
| `continuity` | Whether the fund direction is one-day pulse or continuous |
| `conclusion` | What fund behavior means for tomorrow |
| `passes_forward` | Which directions remain worth sector comparison |

#### `sector_relationships`

Required fields:

| Field | Meaning |
|---|---|
| `directions` | Top 3 directions by default |
| `relationship_role` | Mainline, rival line, replacement, inheritance, rotation, resonance, siphoning, slowdown, or overtake |
| `cycle_label` | Sector-level `启动 / 发酵 / 高潮 / 退潮 / 冰点` |
| `strength_evidence` | Turnover share,涨停扩散, core stock behavior, breadth |
| `risk_evidence` | Failed continuation, high-target damage, drain, divergence |
| `conclusion` | Which direction is the current executable focus |
| `passes_forward` | Directions sent to topic-window and leader/core validation |

#### `overtake_slowdown_window`

Required fields:

| Field | Meaning |
|---|---|
| `overtake_line` | Stronger-than-expected direction |
| `slowdown_line` | Weaker-than-expected direction |
| `topic_window_label` | `启动 / 发酵 / 高潮 / 退潮 / 冰点` for the opportunity itself |
| `expectation_gap` | Why the direction is better or worse than expected |
| `failure_condition` | What would prove the window failed |
| `tomorrow_verification` | What next day must verify |
| `passes_forward` | Direction(s) still worth leader/core validation |

This module is about topic opportunity, not trading time window.

#### `leader_core_validation`

Required fields:

| Field | Meaning |
|---|---|
| `direction` | Direction being validated |
| `core_anchor` | Stable core stock proving the line exists |
| `elastic_vehicle` | Higher-elasticity stock proving attack opportunity |
| `anchor_confirmation` | Confirmed / weak / missing |
| `elastic_confirmation` | Confirmed / weak / missing |
| `conclusion` | Whether the direction has stability, attack elasticity, both, or neither |
| `passes_forward` | Direction quality sent to position stance and candidate verdict |

#### `position_stance`

Required fields:

| Field | Meaning |
|---|---|
| `stance` | `100%核心进攻 / 50%标准进攻 / 0%不参与` |
| `reason_from_market` | Market-stage contribution |
| `reason_from_funds` | Fund-structure contribution |
| `reason_from_sector_window` | Sector/topic-window contribution |
| `reason_from_leader_validation` | Core-anchor/elastic-vehicle contribution |
| `not_participate_reason` | Only filled when stance is 0% |
| `passes_forward` | Maximum participation allowed for final object |

Candidate quality can validate this stance, but cannot independently turn a true ice-point 0% into 50% or 100%.

#### `candidate_pool_verdict`

Required fields:

| Field | Meaning |
|---|---|
| `pool_source` | Why each candidate entered the same pool |
| `winner` | Candidate passed to final object, if any |
| `downgraded_or_rejected_top3` | Up to 3 important losers shown in the opening table |
| `dimension_results` | Same five dimensions for every shown candidate |
| `loss_reason` | Specific reason, never circular wording |
| `missing_data` | Missing data that caused downgrade or lower confidence |
| `passes_forward` | Winner identity plus execution/observation nature |

Five fixed dimensions:

| Dimension | Compact labels examples |
|---|---|
| mainline_sector | 主线贴合 / 支线 / 背离 / 主线冰点 |
| stock_structure | 突破 / 承接 / 失速 / 破位 |
| funds_confirmation | 强确认 / 可用 / 脉冲 / 缺失 |
| account_fit | 可执行 / 等条件 / 旧仓优先 / 不适合 |
| risk_missing_data | 可控 / 偏高 / 关键缺失 / 不做 |

#### `final_object`

Required fields:

| Field | Meaning |
|---|---|
| `identity` | `明日执行对象 / 条件执行对象 / 观察对象 / 无` |
| `stock` | Code/name/sector if present |
| `position_stance` | Copied from `position_stance.stance` |
| `execution_type` | Direct core attack, conditional standard attack, observation only, or no participation |
| `execution_conditions` | Price/fund conditions for execution |
| `observation_conditions` | Conditions that keep or cancel observation |
| `failure_conditions` | Conditions that force no participation |
| `why_this_not_others` | One compact explanation comparing winner to key losers |

Only this object may be rendered as the final object.

#### `next_day_action`

Required fields:

| Field | Meaning |
|---|---|
| `checklist` | Action checklist at the report end |
| `time_windows` | Trading time windows such as `09:30-09:35` and `09:50-10:10` |
| `buy_conditions` | What allows execution |
| `no_buy_conditions` | What blocks execution |
| `old_position_handling` | What to do if old positions exist |
| `review_points` | What must be checked after the next session |

## Current Section Migration Map (evolving)

Migration actions:

| Action | Meaning |
|---|---|
| Keep | Keep useful conclusion in the main body with clearer placement |
| Move | Move the section to the matching new pipeline layer |
| Merge | Merge repeated sections into one packet-driven section |
| Rewrite | Keep the underlying data, but rewrite the visible conclusion and table shape |
| Appendix | Keep as supporting evidence after the main decision flow |
| Remove duplicate | Remove only when the same content is already represented by a named new location |

### Main body sections from the current replay

| Current section | Current value | Action | New location | Preservation rule |
|---|---|---|---|---|
| `明日执行结论` | First visible answer, but currently can conflict with later object sections | Rewrite | `opening_verdict` and `final_object` | Must read the unified final object identity only |
| `判断纠偏与今日五项结论` | Historical judgment correction and recent correctness table | Keep + Move | Immediately after opening derivation overview as `historical_correction` | Keep in main body, not appendix-only |
| `最终标的解题过程` | Shows final object and process chain, but replacement reasons are too circular | Rewrite | `candidate_pool_verdict` + `final_object.why_this_not_others` | Keep process candidates, but every replaced object needs a concrete loss reason |
| `旧仓与新机会风险价格对比` | Account/risk price comparison, often with missing prices | Move + Rewrite | `next_day_action.old_position_handling` + candidate `account_fit` and `risk_missing_data` | Missing price must be visible as missing data, not turned into vague observation |
| `明日账户建议` | Account constraint, position, observation object, action conditions | Merge | `position_stance` + `next_day_action` | Remove duplicate object identity; keep account-size and old-position constraint |
| `一、交易纪律` | Useful discipline matrix, but too early and too large | Move + Compress | Closing `next_day_action` plus discipline appendix | Main body keeps only tomorrow-relevant rules |
| `月度攻防与进攻仓位` | Position background and monthly rhythm | Move | `position_stance` evidence or appendix | Keep if it changes tomorrow stance; otherwise appendix |
| `二、市场基底` | Index, breadth, turnover, concentration, ETF, financing, price-band style | Keep + Move | `market_stage` and `fund_structure.market_risk_appetite` | Must feed participation qualification before any stock appears |
| `指数与市场底色` | Index pressure, turnover, breadth, limit-up/limit-down | Keep | `market_stage` | Core evidence for whole-market `启动/发酵/高潮/退潮/冰点` |
| `市场状态结论` | Current market conclusion and participation meaning | Rewrite | `market_stage.conclusion` + `position_stance.reason_from_market` | Must use cycle labels and participation qualification |
| `价格带风格` | High-price vs low-price style background | Appendix + optional summary | `market_stage` support or market appendix | Only main-body if it changes risk appetite |
| `创新高趋势反馈` | Trend diffusion / new-high feedback | Move | `fund_structure.market_risk_appetite` | Keep as risk appetite evidence |
| `融资承接与成交量` | Financing pressure and turnover support | Move | `fund_structure.market_risk_appetite` | Keep source-date lag note |
| `市场结构判断` | Market structure conclusion | Merge | `market_stage` + `position_stance` | Avoid creating a separate competing market verdict |
| `三、周期与主线` | Cycle calendar, mainline, pivot, turnover share | Keep + Move | `sector_relationships` | This becomes one of the most important main-body sections |
| `周期日历主视图` | Historical sector cycle memory | Move + Compress | `sector_relationships` summary, details in appendix | Keep current-cycle and recent-cycle signal; long calendar goes appendix |
| `周期解读` | Current and recent cycle meaning | Rewrite | `market_stage.cycle_label` + sector `cycle_label` | Convert old labels into `启动/发酵/高潮/退潮/冰点` where possible |
| `中枢与主线解读` | Mainline confirmation and pivot relation | Keep | `sector_relationships` | Must explain no-mainline, mainline, rival, replacement, rotation |
| `主线容量与格局判断` | Mainline capacity, attack evidence, relationship state | Keep + Rewrite | `sector_relationships` + `fund_structure.sector_migration` | Must compare top 3 directions rather than one isolated line |
| `主线成交额占比趋势` | Hot-sector turnover continuity | Move | `fund_structure.sector_migration` and appendix | Main body shows only top 3 comparison; full history appendix |
| `四、资金意图` | LHB and fund intent | Move + Merge | `fund_structure` | LHB becomes validation, not the only fund conclusion |
| `龙虎榜资金状态` | LHB direction and strength | Appendix + summary | `fund_structure.continuity` support | Main body keeps the conclusion if it validates or contradicts sector migration |
| `资金结论` | Fund attitude to mainline and action meaning | Rewrite | `fund_structure.conclusion` | Must say add-risk, rotate, drain, or pulse |
| `五、个股解读` | Object verdict, candidate observation, backups | Rewrite | `candidate_pool_verdict` + `final_object` | Individual stocks appear only after market/funds/sector/position stance |
| `个股裁决` | Current candidate decision but mixes final object and no-action reason | Rewrite | `candidate_pool_verdict` | Must compare winner and top rejected/downgraded candidates with the same five dimensions |
| `明日候选观察` | Candidate observation table | Move | `candidate_pool_verdict` | Keep as same-pool evidence, not separate object source |
| `备用观察` | Backup objects | Move | `candidate_pool_verdict.downgraded_or_rejected_top3` or appendix | Only visible if it helps explain final choice |
| `个股结论` | Summary of front display and full candidates | Merge | `final_object` + `next_day_action` | Remove duplicate identity wording |
| `六、明日执行计划` | Time windows and conditions | Keep + Rewrite | Closing `next_day_action` | This becomes final checklist, after final object is known |
| `七、最终结论` | One-line final answer, duplicates opening | Merge | Opening `opening_verdict` and closing `next_day_action` | Keep the answer, not the duplicate section |
| `八、详细附录` | Raw evidence and generated sections | Appendix | Evidence appendix after main flow | Details stay available, but cannot compete with the final answer |
| `狙击手最终标的完整路径图` | Process chain visualization | Rewrite | `candidate_pool_verdict` + generated flowchart | Must explain why candidates lost, not just show replacement |
| `推导审计层 Step 0-5` | Current step ledger, but too disconnected | Rewrite | New nine-layer derivation ledger matching the pipeline order | Each layer shows input, conclusion, passed-forward result, rejected/downgraded objects |

### Appendix and evidence sections from the current replay

| Current appendix group | Action | New location | Preservation rule |
|---|---|---|---|
| Market research snapshot / mainline capacity / market capacity evolution | Merge + Appendix | `market_stage`, `sector_relationships`, `fund_structure` | Main body keeps conclusions; full tables remain appendix |
| Dialectical decision supplement | Move + Rewrite | `overtake_slowdown_window` and `position_stance` | Keep only if it explains expectation gap, risk, or position stance |
| Expected calendar / industry hot event distribution | Move | `overtake_slowdown_window` support | Use to explain topic window, not stock selection by itself |
| Hotness core results | Move | `sector_relationships` support | Use as sector strength evidence |
| Turnover core results | Move | `fund_structure.sector_migration` | Use for capital migration and concentration |
| Sector fund flow | Keep + Move | `fund_structure` and `leader_core_validation` | Keep inflow/outflow, diffusion quality, and top fund directions |
| LHB results | Appendix + summary | `fund_structure` support | Summarize only when it validates or contradicts mainline |
| Market and sector analysis | Merge | `market_stage` + `sector_relationships` | Remove duplicate prose after conclusion is represented |
| Limit-up results | Move | `sector_relationships.strength_evidence` | Use high-target and spread evidence |
| Multi-dimensional trading results | Appendix | Candidate/fund evidence appendix | Keep as data evidence, not main conclusion |
| Sector tag analysis | Move | `sector_relationships` and `overtake_slowdown_window` | Use tags to explain direction relationship and topic window |
| Intraday/next-day mutation monitoring | Move | `next_day_action.review_points` | Only tomorrow-relevant checks stay in main body |
| Unified execution chain / core conclusion dashboard | Remove duplicate + Rewrite | `opening_verdict` + nine-layer derivation ledger | Old duplicate dashboards should not create a second conclusion |
| Current stock observation pool / lifecycle / A-kill removal / stop-loss calibration | Move | `candidate_pool_verdict`, `final_object.failure_conditions`, risk appendix | Keep as candidate risk and lifecycle evidence |
| Financing full table / ETF full table / Top50 full table | Appendix | Market/fund evidence appendix | Main body keeps only current value, trend, and meaning |
| Data acquisition checklist / execution steps / statistics / source request audit / runtime | Appendix or separate diagnostics file | End-of-report technical appendix in full report only | Must never appear before final action or market/sector proof |
| Knowledge compound candidates / experience hits | Appendix + historical correction support | `historical_correction` support | Main body only if it changes today's correction or tomorrow rule |

### Non-removal commitments

* Market background, position reason, mainline/sector strength, candidate win/loss table, final object conditions, risk review, no-participation reason, and historical correction must all remain visible.
* Full evidence tables may move to appendix, but their conclusions must be represented in the matching main-body layer.
* A current section can be removed only if its useful conclusion has a named replacement location above.
* Duplicate final-answer sections must be merged because duplicates are the main source of conflicting object identity.

## Acceptance Criteria (evolving)

* [ ] The updated spec states the final report table of contents in exact order.
* [ ] The updated spec defines a full-derivation-first opening section.
* [ ] The updated spec defines a unified candidate verdict packet with winner, loser, score dimensions, reasons, passed-forward fields, and missing data.
* [ ] STEP sections have a fixed readable contract and each step can be understood without reading code.
* [ ] A 2026-06-04 replay example shows why `豫能控股(001896)` is the observation object and why `上海石化(600688)` is not the final object.
* [ ] Final/action-facing sections can only read the unified conclusion packet.
* [ ] Process evidence and appendix tables cannot override or visually compete with the final conclusion.
* [ ] The implementation plan includes a section-inventory migration map: keep, move, merge, rewrite, appendix, or remove with reason.
* [ ] No useful current data conclusion is removed without a named replacement location.
* [ ] Historical judgment correction remains in the main body and is not reduced to appendix evidence only.
* [ ] Historical judgment correction appears immediately after the opening derivation overview.
* [ ] Opening derivation overview renders one verdict summary table.
* [ ] The opening verdict summary table includes up to 3 rejected/downgraded candidates with reason dimensions.
* [ ] Winner and top rejected/downgraded candidates are compared using the same five dimensions.
* [ ] Five-dimension cells use compact labels so the opening table remains readable.
* [ ] The report closes with a next-day action checklist that restates position, primary object, execution/observation conditions, no-participation conditions, and old-position handling.
* [ ] The report explicitly states market stage, fund direction, mainline/sector conclusion, and resulting position stance before final candidate selection.
* [ ] Individual candidates appear only after market, funds, sector relationship, and sector-cycle conclusions are rendered.
* [ ] The report includes a sector-relationship map/table before leader/core stock validation.
* [ ] The report includes a main-body `超车 / 失速 / 窗口` section that compares expectation-relative sector strength and feeds the candidate verdict.
* [ ] The table of contents places `超车 / 失速 / 窗口` after sector relationships and before leader/core stock validation.
* [ ] The opening verdict summary table includes one `超车 / 失速 / 窗口` summary sentence.
* [ ] `窗口` in this module is defined as topic/window-of-opportunity, and trading time windows are separated into the next-day action section.
* [ ] Topic-window conclusion uses `启动 / 发酵 / 高潮 / 退潮 / 冰点` cycle labels.
* [ ] Both market-wide and sector/mainline cycle labels are rendered.
* [ ] The report can represent market/sector divergence and explain the resulting position stance.
* [ ] The updated spec uses the confirmed top-level order from market stage through next-day action checklist.
* [ ] Fund structure section renders both market-level risk appetite and sector-level fund migration.
* [ ] Sector relationship section compares the top 3 core directions by default.
* [ ] Leader/core validation renders one core anchor and one elastic vehicle per core direction by default.
* [ ] Position stance uses only 100% / 50% / 0%, with no extra small-position tier.
* [ ] Position stance is derived from market stage, market-level fund risk appetite, and sector topic window before candidate quality.
* [ ] 100% position requires whole market not in ice point, strongest executable mainline in startup/fermentation, funds concentrating into that mainline, and core-anchor plus elastic-vehicle confirmation.
* [ ] Climax does not automatically trigger 100%; the report must distinguish executable climax from overheating or near-retreat risk.
* [ ] 50% position covers non-ice-point markets where a usable startup/fermentation direction exists, but fund concentration or core/elastic validation is not strong enough for 100%.
* [ ] 50% position is rendered as conditional participation: the object is executable only when next-day price/fund conditions appear.
* [ ] 0% position is triggered only by whole-market ice point or strongest-mainline ice point, not by ordinary candidate-level weakness.
* [ ] The report distinguishes "one mainline failing" from "whole market ice point" with market breadth, index pressure, limit-down/deep-water spread, and fund participation evidence.
* [ ] If the current strongest mainline is in ice point, the report can choose 0% even if the broader index is not in full collapse, because the executable mainline has lost participation qualification.
* [ ] The spec names focused tests and replay checks needed before implementation can be called complete.
* [ ] The unified verdict packet is defined as a market-to-action pipeline with one passed-forward conclusion per layer.
* [ ] Candidate review dimensions are applied only after market, funds, sector relationships, topic window, leader/core validation, and position stance are known.
* [ ] No downstream section can introduce an independent final object that was not passed forward by the final object packet.
* [ ] The spec defines required fields for market_stage, fund_structure, sector_relationships, overtake_slowdown_window, leader_core_validation, position_stance, candidate_pool_verdict, final_object, and next_day_action.
* [ ] Opening verdict, final object, candidate verdict, and next-day action all read the same final_object identity.
* [ ] Candidate_pool_verdict renders the same five dimensions for the winner and the top rejected/downgraded candidates.
* [ ] Position_stance renders source reasons from market, funds, sector window, and leader/core validation.
* [ ] Final_object includes `why_this_not_others`, so the report explicitly explains why the winner beat important alternatives.

## Definition of Done (team quality bar)

* The existing two-layer rewrite spec is updated, not discarded.
* The PRD records the agreed scope, approach, and out-of-scope boundaries.
* Implementation plan can be split into small PRs.
* Tests, replay generation, and report acceptance audit are listed as verification.
* Python commands use `.generated/venv-py314/bin/python3.14`.

## Trellis Phase Tasks

The full rewrite is split into four child tasks. They should execute mostly sequentially because later stages depend on the shared verdict packet from stage 1.

| Stage | Task | Status | Purpose | Execution note |
|---|---|---|---|---|
| 1 | `.trellis/tasks/06-05-06-05-daily-report-stage1-verdict-packet` | completed | Build unified verdict packet and opening derivation summary | Landed first shared packet slice and opening verdict rendering |
| 2 | `.trellis/tasks/06-05-06-05-daily-report-stage2-market-sector-spine` | planning | Render market, funds, sector relationships, overtake/slowdown/window, leader/core validation | Can be explored in parallel, implemented after stage 1 packet shape is stable |
| 3 | `.trellis/tasks/06-05-06-05-daily-report-stage3-candidate-final-object` | planning | Rewrite candidate pool verdict and single final object explanation | Depends on stage 1 final_object fields and stage 2 upstream conclusions |
| 4 | `.trellis/tasks/06-05-06-05-daily-report-stage4-action-appendix-audit-flowchart` | planning | Close with next-day action, migrate appendix, strengthen audit, regenerate replay/flowchart | Runs after stages 1-3 settle the report body |

Each child task has its own `prd.md`, `implement.jsonl`, and `check.jsonl`. The context files include the parent PRD, daily report decision loop spec, backend quality contracts, and cross-layer/reuse guides.

Subagent use:

* Explorer subagents may inspect stages 1-4 in parallel and return implementation recommendations.
* Worker subagents should only edit their assigned stage files and must not revert unrelated existing work.
* Stage 1 worker owns the first code-writing slice; stages 2-4 workers should wait until the stage 1 packet contract is stable.

## Out of Scope (explicit)

* Rebuilding every data collector in the first rewrite slice.
* Replacing all market data sources.
* Turning the report into a fully automated trading system.
* Hiding useful process candidates; they should be placed in the right layer with reasons.
* Editing generated replay markdown by hand as the fix.

## Technical Notes

* Existing base spec: `docs/superpowers/specs/2026-06-05-daily-report-two-layer-rewrite-design.md`.
* Key current report sample: `reports/replay/2026-06-04_A股日报_完整版_replay.md`.
* Key current modules found by inspection:
  * `scripts/report/runtime.py`
  * `scripts/report/front_page_v2_renderer.py`
  * `scripts/report/two_layer_decision_payload.py`
  * `scripts/report/sniper_target_derivation.py`
  * `scripts/report/candidate_quality_renderer.py`
  * `scripts/report/final_conclusion_renderer.py`
  * `scripts/report/report_acceptance_audit.py`
  * `scripts/domains/execution_chain/candidate_selection_stage.py`
  * `scripts/domains/execution_chain/pk_decision_stage.py`
  * `scripts/domains/execution_chain/pk_decision_nodes/candidate_quality_scorecard.py`
  * `scripts/domains/execution_chain/pk_decision_nodes/probe_position.py`
  * `scripts/selection/candidate_quality_contracts.py`
* Current likely rewrite axis:
  * report information architecture,
  * unified conclusion packet,
  * candidate verdict packet,
  * readable STEP contract,
  * renderer consumption rules,
  * acceptance audit rules.
* Existing code already has an appendix-like `超车窗口判断` table in `scripts/report/market_research_snapshot_nodes.py`, with fields for rival line, rival slowdown, own line, own stability, overtake logic, arena boundary, speed gap, failure condition, and tomorrow verification.
* Existing wiki references for topic window:
  * `wiki/板块补充/实时Tag池维护与使用.md` defines `新题材窗口` as first concentrated discussion, historical speculation memory, old-mainline relabel risk, independent core/diffusion, and early trend stage.
  * `wiki/板块补充/板块中枢与主线延续.md` separates topic window from trading time windows.

## Decision (ADR-lite)

**Context**: The previous two-layer rewrite spec starts with the front decision layer, but the user now prefers a report that first shows how the conclusion was derived. This is a readability and report-composition decision, not yet a decision about implementation depth.

**Decision**: Use a pyramid / total-detail-total report architecture. The report starts with the whole derivation conclusion, expands into the detailed candidate and STEP proof, then closes with the final action recap.

**Consequences**: The spec must define the exact report order, the unified conclusion packet, the candidate verdict packet, and the STEP contract before implementation.

## Decision (ADR-lite): implementation depth

**Context**: Renderer-only changes can improve readability, but they cannot reliably explain candidate wins and losses if the main report flow still produces fragmented local conclusions. However, an unconstrained full rewrite risks deleting existing useful market, sector, candidate, review, and risk conclusions that the user still needs.

**Decision**: Revisit implementation depth with a data-preservation constraint. Any main-flow rewrite must first inventory current report sections and classify each as keep, move, merge, rewrite, appendix, or remove. Removal requires a reason and a replacement location for useful conclusions.

**Consequences**: The next decision is not simply "how aggressive"; it must choose how much orchestration to rewrite while preserving existing information value. The implementation plan must include a migration map before code changes.

## Decision (ADR-lite): protected rewrite depth

**Context**: The report needs a stronger unified verdict, but the existing report also contains useful market, sector, candidate, risk, account, and review conclusions. A safe rewrite must improve readability without losing those conclusions.

**Decision**: Use "verdict packet first, old data migrated" as the implementation depth. Build the unified candidate/conclusion verdict packet and pyramid report structure, then migrate old sections into new locations: derivation body, compressed summary, or appendix evidence.

**Consequences**: The rewrite is deeper than a renderer reshuffle but less risky than deleting and rebuilding everything. Every old section must have a named destination before implementation removes or suppresses it.

## Expansion Sweep

### Future evolution

* The same unified packet can later feed replay review, decision ledger rows, and visual flowcharts.
* The report can later support a compact "daily brief" and a full "audit report" view without changing the underlying decision packet.

### Related scenarios

* Front page, action plan, final conclusion, candidate quality, appendix, and historical replay should all consume the same conclusion identity.
* Daily report,盘中问股, and later review should use the same object identity and participation windows.

### Failure and edge cases

* No qualified execution object: report must still explain the primary observation object or state no object clearly.
* Conflicting local sources: the report should show the conflict as process evidence and identify the packet that owns the final conclusion.
* Missing key data: the candidate should be downgraded with missing-data reason instead of silently promoted or erased.
* Historical replay: no current-day live facts should be inserted into an old report.
