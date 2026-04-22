# Entry Modularization Roadmap

> 当前目标不是继续给 `daily_report_entry_demo.py` 叠逻辑，而是持续把它压缩成“函数入口 + 模块装配 + 调用编排”。

## 最终架构方向

- `入口层`: 只负责参数接收、路由、编排、结果持久化。
- `请求层`: 只负责外部数据获取、标准化和回退策略。
- `分析层`: 只负责推导、筛选、评分、决策。
- `输出层`: 只负责日报、单票、复盘文档的结构化渲染。
- `追踪层`: 统一模块日志、错误追踪、执行耗时和关键输入输出摘要。

## 当前 Todo

- [x] 提取复盘回放模块：`scripts/replay/report_replay.py`
- [x] 提取单票诊断模块：`scripts/diagnostics/single_stock_runtime.py`
- [x] 提取市场研究上下文模块：`scripts/research/market_research_context_bundle.py`
- [x] 提取前台摘要 builder：`scripts/report/front_summary_builder.py`
- [ ] 提取输出文档骨架 builder：日报开头、纪律块、占位替换等基础文档装配逻辑
- [ ] 提取输出文档分段 builder：把 `generate_markdown_report()` 按章节切成独立 builder
- [ ] 提取请求层第一批模块：从 `get_daily_data()` 拆出指数、热榜、日历、龙虎榜等请求单元
- [ ] 提取分析层第一批模块：从 `build_mainline_exit_analysis()` 拆出连续性、风险、主线判定子模块
- [ ] 统一 trace/log 契约：请求层、分析层、输出层都产出一致的 `module_logs`
- [ ] 把入口收敛成少量 `run_*` 入口函数，最终让主入口文件小于 `1000` 行

## 当前执行顺序

1. 先继续拆 `输出层`
2. 再拆 `请求层`
3. 再拆 `分析层`
4. 最后压缩 `入口层`
