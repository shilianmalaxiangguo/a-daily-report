# brainstorm: 重写选股逻辑

## Goal

重写当前日报选股逻辑，让候选结果从“多来源并集后按分数排很多对象”收敛为“先反推当前板块锚，再判断候选股相对板块锚的身份与参与理由”。目标是减少号池噪音，优先输出少量真正值得反复做、能代表主线承接的对象。

## What I already know

* 用户复盘认为，京能电力这类对象可能只是资金阶段性套利载体；更应该反推电力方向真正有辨识度、资金可能反复回流的龙头，如华电辽能或大唐发电。
* 用户进一步指出，晶方科技式样本在华天科技、长电科技等板块锚走弱后不是便宜替代品，而是后排风险放大器；龙头失效时后排套利/跟风应直接不参与。
* 用户认同“买龙头、买反复做的、买热门股，慢即是快”的经验，核心不是追热闹，而是在市场最有共识、资金最愿意反复回来的地方练手。
* 用户进一步明确：涨停板只能证明弹性和次日惯性概率，也同时证明它能承受单日大回撤；题材周期里更偏向确定性，优先绑定板块锚/大容量龙头、承接和 `MA5入/MA7清/MA5T` 路径。
* 新选股逻辑应先问：当前板块龙头是谁；候选股是低位补涨、套利、跟风，还是分支龙头；它和龙头是什么关系；做它为什么不做龙头。
* 当前代码里候选池来源是多路并集：`涨停池`、`成交额排名`、`连板`、`热榜`、`龙虎榜`、`新股研究池`，位置在 `scripts/domains/watch_candidates/infer.py::build_watch_candidate_pool_bundle`。
* 当前候选评分在 `scripts/selection/candidate_bundle_runtime.py::build_candidate_bundle_contract`，主要使用基础分、连板数、异动承接加分排序，然后主线内取前 3 个核心、后 3 个次级。
* 当前已有“明日主买对象 / 明日补位对象 / 龙头速度分层”等字段，位置在 `scripts/selection/trend_snapshot_runtime.py`，可以承接新的板块锚反推逻辑。
* 当前候选轨迹在 `scripts/selection/candidate_trace_contracts.py`，但只有市场条件、主线条件、个股结构、账户适配；缺少“相对板块锚身份”和“为什么不做板块锚”的显式检查。
* 当前报告行动计划在 `scripts/report/action_plan_nodes.py` 已强调“明天只执行唯一动作，或者只观察”，与减少号池的目标一致。
* LLM Wiki 已经有“统一来源”“前台收口”“强票账户不适配”“换仓先证明旧仓失效、新仓更强、风险能承受”等口径，但当前 `knowledge.llm_wiki` 只把这些内容作为知识上下文和摘要注入报告链路，不会强制各个渲染模块共用同一个最终对象。
* 因此本次不是 Wiki 完全没生效，而是 Wiki 还没有升级成“最终对象身份”的可执行来源；只改 Wiki 文案仍不能阻止核心候选、账户旧仓、ASCII 路径图和最终结论各自取不同标的。
* 用户进一步补充：如果板块锚/强龙头是中际旭创这类高价对象，或 688 科创板对象，而小账户买不到一手或没有科创板权限，不能退而求其次去买弱跟风个股；应评估通信 ETF、科创芯片 ETF 等 ETF/指数化替代表达，并判断替代对象表达的是行业板块效应、科创板效应，还是更窄的分支效应。

## Assumptions (temporary)

* 原始数据采集和多来源候选入口暂时保留，用作证据来源；真正要收紧的是“进入可见候选、主买、补位、观察”的分层逻辑。
* 新逻辑应优先减少最终可见对象数量，而不是粗暴删除数据源，否则会丢失热度、成交、涨停和龙虎榜证据。
* 龙头反推不是单票崇拜；如果量化环境下单一龙头牵引力下降，仍要允许“板块锚 + 中军 + 分支核心”的组合锚，但每个候选都必须说明相对锚的角色。
* ETF 替代表达只能在强对象市场身份成立但账户不可买时触发；它不是弱个股替代，也不能绕过市场、板块、成交和固定交易窗口条件。

## Open Questions

* 重新确认 MVP 范围：最终结果是否只约束“明日新开仓/唯一对象”，还是同时把旧仓 T0 处理对象、观察锚、候选过程证据和复盘统计都纳入同一张结果身份图。
* 与 `.trellis/tasks/06-03-small-account-opportunity-cost` 的关系如何收口：板块锚反推选出的强对象，是否必须先经过小账户资金取舍，才能成为报告里的明日动作对象。

## Requirements (evolving)

* 建立“板块锚反推”字段：板块锚、候选身份、与板块锚关系、为什么不做板块锚、分歧时资金优先修复对象。
* 候选身份至少区分：板块锚、分支龙头、大容量中军、低位补涨、套利工具、跟风样本、修复观察。
* 候选进入主买或补位前，必须有“做它为什么不做板块锚”的明确理由；没有理由时默认降为观察或不参与。
* 原始候选池可以继续保留多来源证据，但报告前台只展示少量通过反推的对象。
* 输出必须能解释被剔除对象的原因，例如“低位补涨只能反馈板块，不替代龙头”“套利工具不承担板块回流锚”“跟风对象没有资金优先修复资格”。
* 报告过程证据必须展示“狙击手最终标的路径图”，用 ASCII 图把原始候选池、主线/板块、板块锚、主买对象、补位对象、观察/不参与对象和偏差/卡点串起来。
* 电力样本应作为验收样本：京能电力不能只因分数或热度进入主买；需要说明它相对华电辽能/大唐发电的角色，无法说明时降级。
* 龙头失效样本应作为否定验收样本：当华天科技、长电科技等板块锚走弱时，晶方科技这类套利/跟风样本不能作为补位，必须明确不参与。
* 涨停、连板、T 字板和次日涨停概率只能作为证据加分；它们必须在板块锚身份有效之后才影响排序，不能让低位补涨、套利、跟风样本压过板块锚。
* 已识别板块锚若具备承接、容量或 `MA5入/MA7清/MA5T` 路径，即使当日实际涨幅较小，也应进入明日主买/补位比较；技术线只作为执行锚点，不单独生成买入理由。
* 旧的候选层 Approach A 不再单独构成完整 MVP；新的 MVP 必须同时包含最终对象身份合同和小账户资金取舍，否则仍会把强对象、旧仓处理对象、观察对象混成一个结果。
* 新增耦合要求：板块锚反推只解决“哪个对象更值得盯”，不能直接等同于“1w 账户明天的钱给谁”。如果存在旧仓/T0 修复和新开仓冲突，最终对象必须经过小账户资金取舍后才能渲染为明日动作。
* 最终解题过程需要展示三段链路：`板块锚反推 -> 小账户资金取舍 -> 明日唯一动作`。只展示第一段会继续造成“强对象”和“能执行对象”混成一件事。
* LLM Wiki 统一输出口径需要同步更新：新增“板块锚反推 -> 小账户资金取舍 -> 明日唯一动作”的稳定口径，并明确 Wiki 负责沉淀口径，运行代码负责生成唯一 `final_target_resolution`，报告模块只消费该结果。
* Wiki 口径不能再只写“主买/补位/观察收口”，还必须区分 `new_entry_target`、`existing_position_target`、`watch_target`、`process_target` 和最终动作对象，避免用户把旧仓处理对象误读成新开仓唯一对象。
* 强对象账户不可买时，新增 `tradable_proxy_target` 角色：先保留原强对象为 `watch_target` / `process_target`，再评估可交易 ETF/指数化替代表达；最终动作必须说明“原强对象不可买 -> 选择/不选择替代表达 -> 替代表达的效应类型”。
* ETF 替代表达必须做成分/跟踪对象分类：行业板块效应（如通信设备链）、科创板效应、芯片/半导体分支效应、宽基或不匹配；不匹配时只观察，不作为新开仓对象。
* ETF 替代表达不得因为可买就自动参与；必须同时满足板块锚有效、ETF 自身成交/流动性可接受、跟踪效应匹配、固定交易窗口条件成立。

## Acceptance Criteria (evolving)

* [x] 给定同一板块内的龙头、低位补涨、套利、跟风样本，系统能输出每个候选的相对板块锚身份。
* [x] 没有“为什么不做板块锚”理由的候选，不会进入明日主买对象。
* [x] 报告前台的最终对象数量明显收敛：优先唯一对象，其次一个补位对象；其余只作为观察或剔除原因统计。
* [x] 被剔除或降级的对象有可读理由，不再只表现为分数低或排序靠后。
* [x] 板块锚已经失效时，后排套利/跟风样本直接不参与，不被当作便宜替代。
* [x] 保留既有市场条件、主线条件、个股结构、账户适配检查，不让新规则绕过参与资格。
* [x] 相关单测覆盖京能电力式“后排套利误入核心”的回归样本，以及大唐发电/华电辽能式“板块锚优先”的保留样本。
* [x] 同一板块内，后排涨停套利分数更高时，板块锚/大容量龙头仍优先成为主对象；套利样本只作为观察。
* [x] 低涨幅但具备承接和 `MA5入/MA7清/MA5T` 路径的板块锚，能进入明日比较，不被涨停后排挤出。
* [x] 报告前台能展示 `ma_binding_strategy`、`leader_certainty_path`、`limit_up_evidence_role`，解释“涨停只是证据，不是主买来源”。
* [x] 跨线自身锚不能替代当前主攻线锚；例如通信设备主线有工业富联时，大有能源只能对比工业富联后降级观察。
* [x] 主攻线龙头来自 `dragon_stocks` 或 anchor-like `candidates` 时，必须先进入评估，不能因为不在 watchlist / 涨停池而缺席。
* [x] 2026-06-02 replay 的 `核心候选判断` 只展示当前板块锚反推后的工业富联，不把同日账本里的亨通光电、中天科技等观察样本补回核心行。
* [x] 候选过程证据能渲染 ASCII 路径图，用户可以直接看到最终对象如何从候选池收敛出来，以及降级对象卡在哪里。
* [x] `build_llm_wiki_context()` 的统一口径、流程图或摘要能覆盖 `板块锚反推 -> 小账户资金取舍 -> 明日唯一动作`，并说明 Wiki 是口径来源，不是最终对象计算器。
* [x] LLM Wiki 相关测试覆盖统一口径文本，防止后续改动又退回“多个模块各自输出标的”的老问题。
* [x] 中际旭创式高价板块锚在小账户买不到一手时，最终结果不退到弱个股；报告保留中际旭创为观察锚/过程对象，并给出可交易 ETF 替代表达或明确无合格替代表达。
* [ ] 688 科创板强对象在账户没有科创板权限时，最终结果不退到弱个股；报告评估科创板/科创芯片/行业 ETF 的匹配度，并说明不匹配时只观察。
* [x] ETF 替代表达需要展示效应类型：行业板块效应、科创板效应、芯片/半导体分支效应、宽基不匹配；用户能从 ASCII 图看到为什么是这个 ETF，而不是后排个股。
* [x] `final_target_resolution` 支持 `tradable_proxy_target`，且前台、最终解题过程、账户建议对原强对象和 ETF 替代表达的角色不冲突。

## Definition of Done (team quality bar)

* Tests added/updated with `.generated/venv-py314/bin/python3.14 -m unittest ...`.
* Narrow implementation verification passes.
* 日报 replay 或最小报告渲染样本能展示新分层字段与收敛后的最终对象。
* 用户可见文字遵守 `wiki/交易思想/日报术语契约.md`。
* 不覆盖正式历史日报，除非用户另行明确要求。

## Out of Scope (explicit)

* 不重写全部数据采集源。
* 不新增实时全量采集。
* 不把当前盘面数据混入历史 replay。
* 不改仓位系统、做 T 规则、账户资金适配规则，除非新分层必须传递字段。
* 不做大规模报告版式重构。
* 不删除既有原始候选来源；除非确认 MVP 就是源头收窄。

## Technical Notes

* Likely source pool builder: `scripts/domains/watch_candidates/infer.py::build_watch_candidate_pool_bundle`.
* Likely scoring/grouping entry: `scripts/selection/candidate_bundle_runtime.py::build_candidate_bundle_contract`.
* Existing mainline helper: `scripts/selection/mainline_support.py`.
* Existing extreme-conviction/leader fields: `scripts/selection/trend_snapshot_runtime.py`.
* Existing trace artifact: `scripts/selection/candidate_trace_contracts.py`.
* Existing report rendering: `scripts/report/action_plan_nodes.py`, `scripts/report/candidate_quality_renderer.py`, `scripts/report/front_page_v2_renderer.py`.
* Existing tests likely impacted: `tests/test_candidate_bundle_runtime.py`, `tests/test_candidate_trace_contracts.py`, `tests/test_front_page_v2_renderer.py`.
* 2026-06-02 regression: the old report selected from the limit-up pool while
  the runtime mainline was 通信设备. The fixed path first resolves 工业富联 as the
  current mainline anchor, keeps 意华股份 / 亨通光电 / 中天科技 as observation or
  process evidence when they cannot explain why not the anchor, downgrades
  大有能源 / 中京电子 as crossline observation, and keeps limit-up evidence as
  support only.
* 2026-06-03 re-brainstorm finding: the remaining instability is no longer only a candidate-ranking problem. The report has multiple target identity outlets with partially independent sources:
  * `scripts/report/runtime.py::_resolve_runtime_current_core_candidate` chooses `current_core_candidate` from execution context, snapshot, `best_stock`, `watch_anchor`, selected candidate, and extreme conviction sources.
  * `scripts/report/runtime.py::_resolve_front_page_target_candidate` can fall back to selected candidate, decision ledger records, or parsed report lines, then stores the result into `current_core_candidate` and `selected_position_candidate`.
  * `scripts/report/front_page_v2_renderer.py::_account_status_lines` renders `T0主对象` from account/position context and may legitimately point at an old-position handling object rather than the new-entry final object.
  * `scripts/report/front_page_v2_renderer.py::_candidate_lines`, `_unique_action_target_lines`, and `_final_summary_lines` render execution target, unique object, unique action, and final conclusion from `selected_position_candidate` / derived unique target.
  * `scripts/report/decision_statistics.py::_current_core_candidates` renders `核心候选判断` from current context first, then falls back to historical ledger records.
  * `scripts/report/candidate_quality_renderer.py::_render_sniper_selection_graph` renders process evidence from candidate quality contracts/traces.
  * `scripts/report/conclusion_support.py` and `scripts/report/final_conclusion_nodes.py` still have full-mode tail rows that can mention `selected_position_candidate`, `best_stock`, `watch_anchor`, or core stocks separately.
* Concrete inconsistency sample:
  * Formal 2026-06-02 report uses `中际旭创(300308)` across front-page core candidate, account T0 row, execution target, unique action, final conclusion, and ASCII process graph.
  * Replay 2026-06-02 report uses `工业富联(601138)` for `核心候选判断`, execution target, unique action, final conclusion, and ASCII process graph, while account advice `T0主对象` prints `华电辽能(600396)` because it is an existing-position handling summary with new-entry count 0.
  * This means the product issue is not just "which stock wins"; old-position action target, new-entry target, observation target, and process target need explicit roles, or users will read them as contradictions.
* LLM Wiki gap finding:
  * `scripts/knowledge/llm_wiki_context.py` line 41 already says daily reports write a unified source and snap-ui only consumes it, and line 44 already says front-page sections must only write observation when there is no participation.
  * `scripts/hooks/knowledge/use_llm_wiki.py` only materializes compact Wiki context into `knowledge.llm_wiki`; its own derivation says it is compact knowledge context, not report prose.
  * `scripts/orchestrator/report_orchestrator.py` runs `knowledge.llm_wiki` before action-plan and report hooks, but no downstream renderer is required to select targets from Wiki.
  * Current result: Wiki provided language and principles, while target identity still came from `selected_position_candidate`, `best_stock`, `watch_anchor`, old-position account rows, candidate traces and decision statistics. This is why the unified口径 did not fully land in output.
* Coupled task finding from `06-03-small-account-opportunity-cost` / thread `019e8b17-5441-7330-978e-8a860fbdee2f`:
  * User has roughly a 1w account; buying a new large target such as 工业富联 can require selling all current holdings such as 华电辽能.
  * Therefore "final target" cannot be decided only by sector strength or leader identity. It must also answer whether the account should spend limited capital on old-position T, new-entry target, or waiting.
  * Current front-page account card already separates existing position and selected candidate, but it does not yet force a cross-decision comparison before rendering final action.
  * `scripts/domains/execution_chain/pk_decision_nodes/probe_position.py` picks `selected_position_candidate` from `best_stock` / `watch_anchor` before the account opportunity-cost comparison exists.
  * `scripts/report/front_page_v2_renderer.py::_account_status_lines` can say "先处理旧仓，不为新候选分散资金" while later sections still show a unique new-entry target. This is only acceptable if the report explicitly says old-position priority wins and the new target is observation-only.
* 2026-06-03 ETF proxy finding:
  * Existing account checks already detect 688 permission mismatch in `scripts/selection/candidate_trace_contracts.py::_resolve_account_status` and one-lot cash mismatch in `scripts/report/runtime.py::_runtime_account_unbuyable_core_active`.
  * Existing ETF data plumbing covers ETF universe / ETF turnover in `scripts/input/tushare_runtime.py::get_etf_turnover_series_from_sina_first` and market overview ETF capacity sections, but it is not yet wired into final target resolution as a tradable proxy.
  * Required new role: `tradable_proxy_target`, distinct from `new_entry_target`, `watch_target`, `process_target`, and `display_target`.
  * The proxy selector needs to compare candidate anchor effect against ETF effect: industry board, STAR-market board, semiconductor/chip branch, or broad/unmatched.

## Scope Boundary

### In Scope

* 重写选股分层的需求与技术方案。
* 明确候选从原始池到最终动作对象的收敛路径。
* 定义板块锚反推字段和验收样本。
* 实现板块锚确定性路径和涨停证据角色的最小代码接入。

### Out of Scope

* 不删除原始候选来源。
* 不扩大仓位系统或做 T 规则。
* 不覆盖正式历史日报产物。

### Non-goals

* 不追求更多候选。
* 不用单日热度替代板块锚判断。
* 不把低位补涨直接升级成主线核心。

### Done Definition

* 板块锚反推字段进入候选分层、质量合同、候选轨迹和报告前台。
* 最终可见候选从旧的“前 3 + 次 3”收敛为主对象、补位对象、观察或不参与。
* 报告最终结论有唯一目标时，直接展示“板块锚反推已收敛”，不再把旧数量统计挂到唯一目标前面。
* 候选过程证据展示“狙击手最终标的路径图”，解释最终主买/补位/观察路径。
* `2026-05-29 --replay` 能通过日报一致性检查，并展示板块锚反推后的收敛结果。

## Recommended Root-Fix Direction

推荐的根治不是先删除原始候选来源，而是先重写最终决策层：

1. 原始池继续收集涨停、成交额、连板、热榜、龙虎榜、新股等证据，作为事实入口。
2. 废弃“多来源并集后按分数取前 3 + 次 3”的最终选择方式。
3. 新增“板块锚反推”评估，给每个候选补充身份与相对锚理由。
4. 最终可见候选从“前 3 + 次 3”改为“唯一主对象 + 一个补位对象 + 观察/剔除原因统计”。
5. 报告只把具备明确参与理由的对象放进明日动作；低位补涨、套利、跟风默认只做观察或反馈。

这样才是当前问题的根因修复：保留证据入口，重写动作对象的生成规则。源头收窄可以作为第二阶段，但不能替代决策层重写；否则只是让输入变少，仍可能在剩余输入里选出套利或跟风对象。

## Feasible Approaches

### Approach A: Decision-Layer Root Fix (Recommended)

* How it works: 保留原始候选池作为事实入口，废弃“按分数取前 3 + 次 3”的最终选择方式；新增板块锚反推评估，把候选分为板块锚、分支龙头、大容量中军、低位补涨、套利工具、跟风样本、修复观察，再输出唯一主对象、一个补位对象、观察/剔除原因。
* Pros: 直接修复当前误选根因；不丢涨停、成交、热榜、龙虎榜等证据；风险最可控。
* Cons: 原始池数量仍然会多，但它只作为后台证据，不直接污染最终动作。

### Approach B: Source + Decision Root Fix

* How it works: 同时收窄原始候选池入口和最终决策层，例如减少成交额、热榜、龙虎榜的进入数量，再做板块锚反推。
* Pros: 后台候选数量也会减少，运行和阅读都更干净。
* Cons: 容易过早删掉有用证据；一旦板块锚识别需要热榜或成交额证据，源头收窄可能误伤。

### Approach C: Report-Only Fix

* How it works: 筛选逻辑暂不改，只在报告里增加“板块锚反推检查”和降级说明。
* Pros: 最快落地。
* Cons: 只改表达，不改最终对象生成，不能根治号池过多和套利票误入核心。

## Decision Needed

Previous decision is reopened. Approach A fixed part of the candidate-ranking problem, but it did not fully answer the user's newer concern: all visible result outlets must either share one authoritative new-entry identity or clearly state that they are a different role, such as existing-position handling or watch-only review.

The next decision is whether MVP should introduce one authoritative `final_target_resolution` payload and require all report surfaces to render from it, or only add a post-render consistency audit around the current fields.

## Technical Approach (previous, incomplete)

1. 在候选分层路径中增加板块锚反推评估，生成结构化字段：
   * `sector_anchor`
   * `candidate_role`
   * `relationship_to_anchor`
   * `why_not_anchor`
   * `repair_priority`
   * `anchor_reversal_decision`
   * `ma_binding_strategy`
   * `leader_certainty_path`
   * `limit_up_evidence_role`
2. 替换最终可见候选收口方式：不再直接使用“主线内前 3 + 次 3”作为核心候选，而是先按板块锚反推结果确定唯一主对象和一个补位对象。
3. 将低位补涨、套利工具、跟风样本默认降到观察或剔除原因统计，除非它能提供明确的相对板块锚参与理由；如果板块锚已经失效，后排套利/跟风直接不参与。
4. 板块锚识别优先看已知龙头身份、容量、趋势资金、反复承接和 `MA5入/MA7清/MA5T` 路径，再看涨停、连板和当日分数；涨停证据不能把低位补涨/套利样本推到锚点前面。
5. 已识别板块锚若有承接和 MA 绑定路径，即使当日涨幅较小，也允许进入明日比较；最终参与仍受固定窗口、板块同步、承接和风险复核约束。
6. 在候选轨迹和报告渲染中展示反推结论，让用户能看到每个对象为什么进入或离开最终动作。
7. 保留既有市场条件、主线条件、个股结构、账户适配检查，新反推规则只增加资格判断，不绕过原有风险约束。
8. 今日判断面板优先使用运行时已经收敛出的主对象/补位对象；同日判断账本只在当前上下文没有候选时兜底，不能把观察样本重新补成核心候选。

## Reopened Technical Approach Options

### Approach A2: Final Target Resolution Payload (Recommended)

* How it works: build one structured payload after execution-chain exports and before front-page rendering. It contains role-separated identities: `new_entry_target`, `existing_position_target`, `tradable_proxy_target`, `watch_target`, `process_target`, `display_target`, `ascii_trace_target`, and `capital_priority_decision`. Every front-page section and candidate-process graph must read from this payload or declare a non-new-entry role. If `capital_priority_decision` says old-position handling wins, the new-entry target can stay as a high-priority watch target but cannot be rendered as the action object. If the strong object is account-unbuyable, the ETF/index proxy may become the action object only when effect matching and execution conditions are satisfied.
* Pros: fixes the real root of repeated inconsistent reports; makes the ASCII graph the visible explanation of the same final result; distinguishes "old position first" from "new target"; gives tests one stable object to assert.
* Cons: needs careful wiring across runtime, front page renderer, conclusion support, decision statistics, and candidate quality evidence.

### Approach B2: Render-Time Consistency Audit

* How it works: keep the current fields, but add an acceptance check that extracts identities from core candidate, account advice, execution plan, final conclusion, and ASCII graph. If they differ without an explicit role label, report generation stops.
* Pros: smaller implementation; catches contradictions quickly.
* Cons: still leaves multiple sources generating identities; it prevents bad output but does not make generation deterministic by itself.

### Approach C2: Front-Page Only Rewrite

* How it works: change only the front page to use a single target label, while leaving appendix process evidence and statistics as-is.
* Pros: fastest visual improvement.
* Cons: likely repeats the same problem later because appendices and statistics can still disagree with the front page.

## Decision (ADR-lite, previous, incomplete)

**Context**: 当前选股逻辑把涨停、成交额、连板、热榜、龙虎榜、新股等来源合并后，主要按分数、连板和异动承接排序，容易把低位补涨、套利或跟风样本推到核心候选。新增复盘结论是：涨停代表弹性和惯性，但不等于更高确定性；题材周期里应优先选择资金愿意反复回看的板块锚和大容量龙头。

**Decision**: 采用 Approach A：保留原始候选池作为事实入口，重写最终决策层为板块锚反推。最终动作只允许唯一主对象和一个补位对象；其余对象进入观察或剔除原因统计。涨停、连板、T 字板只在板块锚身份有效后作为证据，不作为主买来源。

**Consequences**: 原始池仍可能较大，但不会直接污染最终动作；实现风险较低；后续可以用新决策层的样本表现再判断是否需要第二阶段源头收窄。

## Implementation Plan

* PR1: Define final target resolution payload and tests for role separation: new-entry target, old-position handling target, watch-only target, process graph target, and capital priority decision.
* PR2: Connect small-account opportunity-cost comparison before front-page rendering. The comparison decides whether old-position T, new entry, or waiting owns capital priority.
* PR3: Route front-page current judgment, account advice, stock verdict, execution plan, final conclusion, conclusion support, and candidate process graph through the resolution payload.
* PR4: Update LLM Wiki compact context and tests so the stable口径 records the same three-step chain and role split.
* PR5: Add report consistency checks that compare rendered identities and allow differences only when the role is explicitly old-position handling or watch-only review with a capital-priority explanation.
* PR6: Re-run 2026-06-02 formal/replay samples and a 华电辽能/工业富联 conflict sample, verifying that the rendered final result, process graph, account advice, and statistics explain the same decision chain rather than competing identities.
