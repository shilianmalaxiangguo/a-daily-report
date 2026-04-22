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
- [ ] 落地 `market_state`，把环境判断相关的请求/推导/输出收敛到同一域
- [ ] 提取请求层第一批模块：从 `get_daily_data()` 拆出指数、热榜、日历、龙虎榜等请求单元
- [ ] 提取分析层第一批模块：从 `build_mainline_exit_analysis()` 拆出连续性、风险、主线判定子模块
- [ ] 统一 trace/log 契约：请求层、分析层、输出层都产出一致的 `module_logs`
- [x] 把 `risk_review` 从入口移入独立 stage：`scripts/domains/execution_chain/risk_review_stage.py`
- [ ] 把 `entry_plan` 从入口移入独立 stage：`scripts/domains/execution_chain/entry_plan_stage.py`
- [ ] 把 `pk_decision` 从入口移入独立 stage：`scripts/domains/execution_chain/pk_decision_stage.py`
- [ ] 把 `build_legacy_final_conclusion_lines` 接入动态 stage label，不再依赖固定 Step 文案
- [ ] 把 `_compact_report_for_mvp()` 的截取规则改成 registry/key 驱动，移除固定 `Step x.y` 锚点
- [ ] 把入口收敛成少量 `run_*` 入口函数，最终让主入口文件小于 `1000` 行

## 当前执行顺序

1. 先按业务域落地 `market_activity`
2. 再按业务域落地 `market_state`
3. 再拆 `请求层`
4. 再拆 `分析层`
5. 最后压缩 `入口层`
