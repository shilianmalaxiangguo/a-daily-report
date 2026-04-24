# Entry Modularization Roadmap

> 当前目标不是继续给 `daily_report_entry_demo.py` 叠逻辑，而是持续把它压缩成“函数入口 + 模块装配 + 调用编排”。

## 最终架构方向

- `入口层`: 只负责参数接收、路由、编排、结果持久化。
- `请求层`: 只负责外部数据获取、标准化和回退策略。
- `分析层`: 只负责推导、筛选、评分、决策。
- `输出层`: 只负责日报、单票、复盘文档的结构化渲染。
- `追踪层`: 统一模块日志、错误追踪、执行耗时和关键输入输出摘要。

## 新拆分原则

- 不再按章节号暴力切文件。
- 改为 `业务域 × 功能域` 的混合矩阵拆分。
- 先问“它属于哪个业务域”，再问“它在这个域里是 request / infer / report / persist / trace 哪一类”。

### 当前业务域规划

- `market_state`
- `market_activity`
- `calendar_events`
- `watch_candidates`
- `execution_chain`
- `snapshot_replay`
- `single_stock_diagnostic`
- `report_shell`
- `monitoring`

## 当前 Todo

- [x] 修复旧入口直跑阻塞问题：已补齐本地兼容 shim（`data_collector / xuangubao_intraday / ths_hot_stock / ths_hot_list / tencent_finance_data / limit_up_down_pool / strong_stock_pool / data_validator / quantitative_analyzer / hot_list_integrated / history_cache / llm_service`），`daily_report_entry_demo.py 2026-04-22 --replay` 已可真实跑通
- [x] 提取复盘回放模块：`scripts/replay/report_replay.py`
- [x] 提取单票诊断模块：`scripts/diagnostics/single_stock_runtime.py`
- [x] 提取市场研究上下文模块：`scripts/research/market_research_context_bundle.py`
- [x] 提取前台摘要 builder：`scripts/report/front_summary_builder.py`
- [x] 落地执行链动态 stage runtime：`scripts/domains/execution_chain/stage_runtime.py`
- [x] 落地执行链 stage registry：`scripts/domains/execution_chain/stage_registry.py`
- [x] 提取执行链环境跟随 stage：`scripts/domains/execution_chain/environment_follow_stage.py`
- [x] 提取执行链观察池 stage：`scripts/domains/execution_chain/watch_pool_stage.py`
- [x] 提取执行链核心候选 stage：`scripts/domains/execution_chain/candidate_selection_stage.py`
- [x] 让入口通过 registry 挂载 `environment_follow / watch_pool / candidate_selection`
- [ ] 提取输出文档骨架 builder：日报开头、纪律块、占位替换等基础文档装配逻辑
- [ ] 落地第一个业务域：`market_activity`，把热榜/成交额/龙虎榜/连板/量化活跃度收敛到同一域
- [x] 落地 `market_state` 首域 graph：`scripts/domains/market_state/graph.py`
- [x] 把 `build_mainline_exit_analysis()` 迁移成 graph wrapper：`scripts/domains/market_state/runtime.py`
- [ ] 继续细化 `market_state` node：把连续性、风险、替代主线判断从粗节点升级成更细粒度 node
- [ ] 提取请求层第一批模块：从 `get_daily_data()` 拆出指数、热榜、日历、龙虎榜等请求单元
- [ ] 统一 trace/log 契约：请求层、分析层、输出层都产出一致的 `module_logs`
- [x] 把 `risk_review` 从入口移入独立 stage：`scripts/domains/execution_chain/risk_review_stage.py`
- [x] 把 `entry_plan` 从入口移入独立 stage：`scripts/domains/execution_chain/entry_plan_stage.py`
- [x] 把 `pk_decision` 从入口移入独立 stage：`scripts/domains/execution_chain/pk_decision_stage.py`
- [x] 把“最终结论 + 洞察尾部”从入口移入独立 hook：`scripts/hooks/report/use_report_tail_summary.py`
- [x] 把“策略账本尾部”从入口移入独立 hook：`scripts/hooks/report/use_strategy_performance_tail.py`
- [x] 把“执行附录尾部”从入口移入独立 hook：`scripts/hooks/report/use_execution_appendix_tail.py`
- [x] 把 `generate_markdown_report()` 迁移成 report runtime wrapper：`scripts/report/runtime.py`
- [x] 把 `get_daily_data()` 迁移成 input runtime wrapper：`scripts/input/runtime.py`
- [x] 建立请求层首批 registry：`scripts/input/request_registry.py` 先托管 `total_turnover / major_indices / wind_a`
- [x] 把首批市场环境请求落到业务域模块：`scripts/domains/market_state/request.py`
- [x] 把首批市场活跃度请求落到业务域模块：`scripts/domains/market_activity/request.py`
- [x] 扩展 `market_activity/request`：已覆盖涨停跌停池、热榜、整合热榜、板块热榜、行业资金流向、板块涨跌幅、成交额排名、连板梯队、龙虎榜
- [x] 把首批市场活跃度分析落到业务域模块：`scripts/domains/market_activity/infer.py`
- [x] 扩展 `scripts/domains/market_activity/infer.py`：已覆盖 `market status / main-secondary sectors / risk sectors / hot concept aggregation`
- [x] 扩展 `scripts/domains/market_activity/infer.py`：已覆盖 `mainline context / dragon stock extraction`
- [x] 提取市场活跃度蜡烛图形态判断：`scripts/domains/market_activity/candlestick.py`
- [x] 提取市场活跃度板块归链 runtime：`scripts/domains/market_activity/sector_chain_runtime.py`
- [x] 把首批候选池推导落到业务域模块：`scripts/domains/watch_candidates/infer.py`
- [x] 把候选股历史补数请求落到业务域模块：`scripts/domains/watch_candidates/request.py`
- [x] 扩展 `market_activity/infer`：已覆盖放量异常、龙虎榜深度分析、板块共振评分、交易信号
- [x] 把预期日历请求落到业务域模块：`scripts/domains/calendar_events/request.py`
- [x] 把监控类请求落到业务域模块：`scripts/domains/monitoring/request.py`
- [x] 把 `build_legacy_final_conclusion_lines` 接入动态 stage metadata：支持显式 `report_stages` 顺序和标题映射
- [x] 把 `_compact_report_for_mvp()` 的截取规则迁移到 `scripts/report/mvp_compactor.py`，改成 stage heading / registry 驱动
- [x] 把策略账本尾部 helper 迁移到 `scripts/report/strategy_tracking_runtime.py`，已覆盖 `factor_snapshot / plan_context / ledger_update / appendix timer normalize`
- [x] 把策略账本持久化 store 迁移到 `scripts/report/strategy_tracking_store.py`，已覆盖 `load/save ledger` 与 `save_factor_snapshot`
- [x] 把 recent target followup / reflection / compare 迁移到 `scripts/report/strategy_tracking_followups.py`，已覆盖 `followups / review_matrix / reflection / gem_horizontal_compare_cards`
- [x] 把策略记录与复盘准备 helper 迁移到 `scripts/report/strategy_tracking_records.py`，已覆盖 `find / format / signature / upsert / merge / window_summary / review_prepare`
- [x] 把策略复盘分析 helper 迁移到 `scripts/report/strategy_tracking_review.py`，已覆盖 `attribution / setup review / gem week review / self calibration / structure cycles / graduation dashboard`
- [x] 把策略评估与链路 helper 迁移到 `scripts/report/strategy_tracking_evaluation.py`，已覆盖 `simulate_exit / benchmark / watch outcome / single record evaluation / market path / yizi chain / display metrics`
- [x] 把策略账本 support helper 迁移到 `scripts/report/strategy_tracking_support.py`，已覆盖 `compound / status label / action label / signal label / record backfill / trade stats / ev review`
- [x] 把策略 EV calibration helper 迁移到 `scripts/report/strategy_tracking_ev.py`，已覆盖 `ev calibration / posterior estimate / execution ev scoring`
- [x] 扩展 `scripts/report/strategy_tracking_support.py`：已覆盖 `candidate confirmation / probe role / probe candidate scan / history feedback / feedback clock`
- [x] 提取异动观察/冻结计划 formatter：`scripts/report/observation_plan_formatter.py`，已覆盖 `follow rule / follow display / abnormal observation columns / frozen plan columns`
- [x] 提取观察价位说明 formatter：`scripts/report/observation_price_formatter.py`，已覆盖 `zone badge / price focus text / note text / append note / compose observation focus`
- [x] 扩展 `scripts/report/strategy_tracking_support.py` 与 `scripts/report/strategy_tracking_store.py`：已覆盖 `pct formatter / run mode label / ledger path / factor snapshot path`
- [x] 扩展 `scripts/diagnostics/single_stock_runtime.py`：已覆盖 `resolve_single_stock_snapshot / generate_single_stock_diagnostic_markdown` wrapper 下沉
- [x] 收口纯 report output wrapper cluster：入口已直接导出 `daily_report_render` 的 `_get_report_output_path / _get_stock_diagnostic_output_path / _inject_report_variant_banner / _render_report_with_display_mode / build_report_outputs / save_report_output / save_report_outputs / save_stock_diagnostic_output`
- [x] 扩展 `scripts/portfolio/position_management_report.py`：已覆盖 `parse_position_string / analyze_position_management` wrapper 下沉
- [x] 扩展 `scripts/replay/report_replay.py`：已覆盖 `replay_from_snapshot` wrapper 下沉
- [x] 提取 `scripts/execution/intraday_execution_runtime.py`：已覆盖 `intraday pivot / avg volume / build intraday execution plan`
- [x] 扩展 `scripts/execution/intraday_execution_runtime.py`：已覆盖 `fetch intraday bars / waiting stock plan`
- [x] 落地 market-data runtime 首段：`scripts/market_data/daily_price_runtime.py`，已覆盖 `bs code / quicktiny / daily bars / trading day count / one-word limit / bar change / live tradability`
- [x] 扩展 `scripts/market_data/daily_price_runtime.py`：已覆盖 `recent price bars / stop-loss anchor / breakout confluence anchor / stop-plan reference enrich`
- [x] 提取策略契约/前摘要 support helper：`scripts/report/strategy_contract_support.py`，已覆盖 `trading philosophy / strategy positioning / contract digest / alignment pool`
- [x] 提取前摘要 support helper：`scripts/report/front_summary_support.py`，已覆盖 `front mainline label / style action / core mvp digest / mvp focus summary`
- [x] 提取市场研究 support helper：`scripts/research/market_research_support.py`，已覆盖 `market research snapshot / step0 follow plan / dialectical decision / abnormal projection / observation snapshot / follow verdict / mainline competition / market research renderers / context bundle`
- [x] 扩展 `scripts/risk/risk_bundle_runtime.py`：已覆盖 `step3 risk bundle / limit-time parse / limit-up friction / risk reason formatter` wrapper 下沉
- [x] 扩展 `scripts/research/market_research_support.py`：已覆盖 `dialectical decision snapshot / abnormal projection / observation snapshot / follow verdict / mainline competition` 下沉
- [x] 扩展 `scripts/selection/candidate_bundle_runtime.py`：已覆盖 `step2 candidate bundle` wrapper 下沉
- [x] 提取 `scripts/domains/market_state/support.py`：已覆盖 `market state machine snapshot / mainline pulse / environment score / structure score / mainline score / memory score / abnormal score / flow normalization`
- [x] 扩展 `scripts/domains/market_state/support.py`：已覆盖 `breadth snapshot / keyword item counter / mainline star level / sector hotlist weight / sector bucket / quadrant snapshot`
- [x] 扩展 `scripts/domains/market_state/support.py`：已覆盖 `sector flow history / market turnover history / exit price lines / core hot stock / sector leader`
- [x] 提取 `scripts/selection/watch_anchor_support.py`：已覆盖 `watch anchor bucket / crossline second confirmation / watch anchor type / pending candidate type / watch anchor note / append watch anchor note`
- [x] 提取 `scripts/report/strategy_tracking_snapshot_support.py`：已覆盖 `abnormal setup distribution / candidate brief snapshot`
- [x] 提取 `scripts/selection/mainline_support.py`：已覆盖 `resolve primary mainline / split candidates by mainline`
- [x] 提取 `scripts/selection/candidate_context_support.py`：已覆盖 `washout reclaim context / trend continuation context`
- [x] 提取 `scripts/selection/candidate_execution_contracts.py`：已覆盖 `GEM textbook / weak-to-strong / philosophy constraint / setup contract / holding window / candidate exit rules`
- [x] 扩展 `scripts/selection/watch_anchor_support.py`：已覆盖 `sort_watch_anchor_candidates / weak-to-strong note merge / watch priority scoring`
- [x] 扩展 `scripts/selection/watch_anchor_support.py`：已覆盖 `execute anchor active-window text / cycle triplet text`
- [x] 扩展 `scripts/selection/watch_anchor_support.py`：已覆盖 `priority watch anchor selector / gem fallback selection`
- [x] 扩展 `scripts/report/front_summary_support.py`：已覆盖 `bridge prep context / front guard label / candidate preview formatter`
- [x] 扩展 `scripts/report/front_summary_support.py` 与 `scripts/selection/position_sizing_runtime.py`：已覆盖 `runtime default dependencies for front follow/structure action and position sizing`
- [x] 扩展 `scripts/report/strategy_tracking_support.py`：已覆盖 `runtime default dependencies for strategy support / candidate feedback clock`，入口 strategy helper wrapper 已退成纯转发
- [x] 扩展 `scripts/selection/special_probe_runtime.py`：已覆盖 `abnormal watch anchor candidate assembly`
- [x] 扩展 `scripts/selection/special_probe_runtime.py`：已覆盖 `decision stack scoring / candidate ordering`
- [x] 扩展 `scripts/selection/special_probe_runtime.py`：已覆盖 `abnormal follow risk signal mapping`
- [x] 扩展 `scripts/selection/special_probe_runtime.py`：已覆盖 `runtime default dependencies for watch-anchor assembly / probe group / special probe verdict`
- [x] 提取 `scripts/selection/gem_breathing_runtime.py`：已覆盖 `is_20cm_stock / evaluate_gem_breathing_window / build_gem_breathing_prep_context`
- [x] 扩展 `scripts/selection/gem_breathing_runtime.py`：已覆盖 `discover gem candidates / textbook profile / gem observation pool`
- [x] 扩展 `scripts/selection/gem_breathing_runtime.py`：已覆盖 `gem breathing contract / watch anchor builder`
- [x] 扩展 `scripts/selection/gem_breathing_runtime.py`：已覆盖 `20cm elasticity context / entry-range exposure / contract prices / branch classify`
- [ ] 把入口收敛成少量 `run_*` 入口函数，最终让主入口文件小于 `1000` 行

## 最新进展

- `input.runtime` 已从 `887` 行继续压到 `590` 行，说明候选历史补数和量化分析胶水已经从编排层拆回业务域模块。
- 当前已形成 `watch_candidates: infer + request`，以及 `market_activity: request + infer` 的成对域结构，后续可以继续把残留的分析胶水按同一规范推进。
- 输出层里对固定 `Step 1 / Step 2` 锚点的依赖也已经开始收口；`final_conclusion` 和 `MVP compactor` 现在都能吃动态 stage 元数据，不再把执行链编号写死在规则里。
- 策略账本尾部的 `factor_snapshot / plan_context / ledger_update / appendix timer normalize` 已脱离入口；持久化 store、recent target followup / reflection / compare、策略记录与复盘准备 helper、整组策略复盘分析 helper、策略评估与链路 helper、策略账本 support helper、策略 EV calibration helper、候选反馈 support helper、异动观察/冻结计划 formatter、观察价位说明 formatter、support/store 的路径与格式化 helper、单票诊断 wrapper、纯 report output wrapper cluster、`portfolio` 域的持仓解析/持仓管理 wrapper、`snapshot_replay` 域的 replay wrapper、market-data runtime 首段，以及策略契约/前摘要 support helper、front-summary support helper、market-research support helper、step3 risk helper cluster、step2 candidate bundle、`market_state` support helper、`watch_anchor` support helper、`strategy_tracking snapshot` support helper、`selection mainline` support helper、`selection candidate context` support helper 也都开始脱离入口；同时这轮还补齐了旧入口直跑兼容层，并修掉了 `report/runtime` 与 `strategy_tracking_records` 的真实运行时漏口，`daily_report_entry_demo.py` 又从 `10289` 行降到了 `10197` 行，完整入口命令 `python3 scripts/daily_report_entry_demo.py 2026-04-22 --replay` 已真实跑通并成功落盘到 `reports/replay/`。

## 当前执行顺序

1. 先按业务域落地 `market_activity`
2. 再按业务域落地 `market_state`
3. 再拆 `请求层`
4. 再拆 `分析层`
5. 最后压缩 `入口层`
