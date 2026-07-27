# Implementation: 创新高扩散收缩与核心补跌

## Prerequisites

- 已阅读 `prd.md`、`design.md` 和 `research/2026-07-new-high-breadth-calibration.md`。
- 保留工作区中他人已完成的 staged/unstaged 改动，不覆盖不相关文件。

## Ordered Checklist

- [x] I1: 新增纯函数结构投影，对个位数、快速下降、板块碎片化、低位修复、目标日不匹配、来源不足和重复/覆盖异常建立测试。
- [x] I2: 在《创新高趋势反馈》插入四行结构文案，保持现有表格和旧三档解释。
- [x] I3: 把结构字段投影到 LLM Wiki 的 `market.breadth` 派生事实，注册知识 ID、来源和清单字段，保持 `explanation_only`。
- [x] I4: 补充 Markdown 和 Bear HTML 渲染测试，检查文案顺序、固定标题和窄屏不溢出。
- [x] I5: 运行日报相关单测、LLM Wiki lint、日报一致性检查和目标日 replay；目标日 replay 已完成快照读取、渲染和一致性检查，但在 PostgreSQL-only 事实同步处因现场无数据库停止，未写入新的完整 replay 快照。
- [x] I6: 用子代理做提交前审计，只修复本任务导致的问题；不触碰其他未提交改动。
- [x] I7: 回填 PRD 状态、验收结果和剩余风险，不自动创建 commit。
- [x] I8: 先补 `5 / 2 / 1 / 0.2` 精确边界、个位数优先、`2.3 -> 0.8` 收缩和 `0.4 -> 0.8` 修复的失败测试。
- [x] I9: 在 `new_high_structure.py` 建立唯一五档阈值、分类函数和方向字段，趋势表与当前解读只读取共享分类。
- [x] I10: 将阈值写入 Bear chart payload，ECharts 从 payload 生成四条参考线并显示新高数、绝对水位。
- [x] I11: 更新 LLM Wiki、字段映射和路由词，保留 `explanation_only` 与正式决定隔离。
- [x] I12: 重新生成 2026-07-17 正式 Markdown/Bear HTML，执行定向测试、Wiki lint、acceptance audit、决策字段对比和提交前子代理审计。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_new_high_structure_signal tests.test_market_overview_builder tests.test_llm_wiki_router tests.test_llm_wiki_manifest tests.test_llm_wiki_lint`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py <target-report.md>`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <target-date> --replay`

## Risk And Rollback Points

- 高风险文件：`market_overview_nodes.py`、`llm_wiki_router.py`、`llm_wiki_context.py`。
- 回滚点：结构投影调用、Wiki 新路由条目、日报四行文案。
- 不进行的操作：不重新采集所有历史日、不覆盖正式历史日报、不改决策字段。

## Review Checkpoints

- 结构字段和文案是否只来自快照已有字段。
- 日报的明日对象、仓位、执行性质、B1/B2 和退出动作是否与接入前一致。
- 来源不足、板块归属不足或目标日不匹配时，是否显示事实不足。
- Bear HTML 是否仅渲染 Markdown 文字，没有另外生成一套会改变决策的解释。

## 本轮质量结果

- 创新高结构 `10` 项、受影响的市场总览 `3` 项、Bear HTML 与入口 `100` 项、LLM Wiki `155` 项通过。
- 市场总览全量 `44` 项中 `43` 项通过；唯一失败是既有的 `3600.0 / 1600.0` 与断言 `3600 / 1600` 的格式差异，与新高结构接入无关，本轮未扩大修复范围。
- LLM Wiki lint：`32 entries / 0 errors / 42` 个既有元数据警告。
- 正式 `reports/2026-07-17_A股日报_完整版.md` acceptance audit 通过；replay 文件的唯一失败是既有 `Tb` 历史路径缺失，不由本任务引入。
- `git diff --check`、Python 3.14 编译检查通过。
- 提交前审计确认阈值、方向、来源质量、正式动作隔离和 Wiki 路由；审计发现的重复板块覆盖与“事实不足”口径已由聚合/覆盖反例和用户可见文案回归覆盖。

## 剩余风险

- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-17 --replay` 已从官方快照完成读取和报告一致性检查，但 PostgreSQL-only 同步因现场无可用 PostgreSQL 事实库停止；因此没有生成新的 `snapshots/replay/2026-07-17_replay.json`。
- 目标日报当前可见序列确认 `2026-07-13=6/0.12%`、`2026-07-17=9/0.18%`；历史来源混用时仍只输出结构观察，不把半导体写成主导板块。
