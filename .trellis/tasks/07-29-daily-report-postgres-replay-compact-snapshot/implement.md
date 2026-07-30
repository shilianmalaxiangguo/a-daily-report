# Implementation: 日报 PostgreSQL replay 与紧凑快照迁移

## Prerequisites

- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 保留当前工作区已有日报修复与性能优化，不回滚、不格式化无关文件。
- 删除历史快照、修改数据库结构、改环境配置和提交代码前必须另行确认。
- 每个阶段先运行定向测试，再进入下一阶段。

## Ordered Checklist

- [x] I1: 在 `scripts/report/runtime.py` 持久化执行上下文前移除完整 `data` 和可调用对象，同时保留业务输出。
- [x] I2: 在 `scripts/daily_report_snapshot_io.py` 增加当前递归路径循环识别，并保留合法共享引用。
- [x] I3: 快照改为 64MiB 上限的原子写入；超限或异常不得覆盖目标或留下临时文件。
- [x] I4: 增加循环、共享引用、小文件、超限、新旧目标保护的单元测试。
- [x] I5: 主日报入口的快照成功与失败都记录目标路径、请求模式、实际模式、已写字节和尺寸限制结果，并补结构化观察测试。
- [ ] I6: 建立 PostgreSQL replay source adapter，并把目标日期数据库事实送入现有 replay 合同。
- [ ] I7: 持久化冻结知识引用、补充观察和必要来源日期；优先复用现有紧凑字段。
- [ ] I8: 禁止 PostgreSQL-only replay 实时刷新或从历史 Markdown 补事实；缺失时明确停止。
- [ ] I9: 迁移 replay 检查、判断复盘和前瞻复盘，不再默认读取完整 JSON。
- [ ] I10: 为 snap-ui 和发布器提供专用紧凑投影，并迁移现有整文件读取接口。
- [ ] I11: 对正式/旧 JSON replay/PostgreSQL replay 比较核心判断、来源日期、Markdown 与 Bear HTML。
- [ ] I12: 验收通过后停止新增完整 JSON，只保留旧 reader 和旧档案兼容能力。
- [ ] I13: 生成历史大文件清理预演；获得用户确认后才能执行删除、覆盖或批量压缩。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_snapshot_io`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_replay tests.test_daily_report_source_health tests.test_postgres_daily_fact_db`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-28 --replay`
- 对 2026-07-28 正式与 replay 产物运行日报一致性检查，并逐字段比较最终对象、仓位、执行性质、B1/B2 和退出动作。
- `git diff --check HEAD`

## Risk And Rollback Points

- `execution_stage_context` 有多个下游消费者；只能移除运行期依赖，不能移除阶段业务输出。
- 共享引用不是循环；循环识别必须使用当前递归路径集合，而不是全局已访问集合。
- 尺寸限制必须在临时文件上执行，不能先截断正式或 replay 目标。
- PostgreSQL replay 必须精确使用目标日期来源，不得因缺失回退到当前实时事实。
- snap-ui 和发布器需要面向用途的紧凑投影，不能直接依赖数据库内部宽字段布局。

## Review Checkpoints

- Checkpoint 1: 循环引用用例不再展开，合法共享引用仍完整。
- Checkpoint 2: 超限用例中已有文件哈希不变、临时文件为零。
- Checkpoint 3: S1 修改前后核心判断字段逐项一致。
- Checkpoint 4: PostgreSQL replay 在删除测试目录内官方 JSON 后仍可完成，且没有实时调用。
- Checkpoint 5: snap-ui 与发布器的所有旧完整 JSON 读取点都有明确替代来源。
- Checkpoint 6: 停止新增完整 JSON 前完成多日期双路径和数据库恢复演练。
- Checkpoint 7: 提交前审计最多两个窄主题，8 分钟返回阶段证据，10 分钟停止。

## Verification Evidence

- 2026-07-29: `tests.test_daily_report_snapshot_io` 4 项通过；覆盖循环引用、共享引用、有效 JSON、尺寸超限和已有文件保护。
- 2026-07-29: `tests.test_report_runtime` 349 项通过；执行上下文清理未改变完整报告运行回归。
- 2026-07-29: `tests.test_daily_report_entry_preflight` 61 项、`tests.test_daily_report_entry_html_output` 50 项通过。
- 2026-07-29: 快照 hook 与策略跟踪 25 项通过；相关总计 489 项。
- 2026-07-29: 修复独立审计发现的活跃执行上下文过早清理问题后，相关完整回归 495 项通过，耗时 120.056 秒。
- 2026-07-29: 快照成功观察覆盖 frozen 请求实际转存 replay、目标路径与文件字节数；失败观察覆盖 64MiB 受限停止、已写字节与尝试字节数。
- 2026-07-29: 两个窄主题独立审计并行运行，均在约 8 分钟返回阶段证据；代码审计发现 2 项、文档审计发现 5 项，相关问题均已修正或通过收窄本阶段表述处理。
- 2026-07-29: 16:48:36 启动最终两个窄主题审计；8 分钟节点均未主动返回，主线程立即停止。文档审计在停止节点交付 2 项有效发现，代码审计未返回可用结论；已修正 Spec 的旧原地清理断言，并把 R7 明确限定为本阶段实际覆盖的主日报入口观察。
- 2026-07-29: 8MiB 数据加直接自引用序列化为 8,388,681 字节，耗时 0.459 秒，并包含单个循环占位。
- 2026-07-29: 2026-07-28 两份旧快照只读核验为 1,401,954,582 与 1,403,989,568 字节；本轮未覆盖或删除。
