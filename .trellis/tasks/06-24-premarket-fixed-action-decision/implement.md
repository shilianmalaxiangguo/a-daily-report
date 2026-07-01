# Implementation: 盘前买卖决定固定，盘中只执行或取消

## Prerequisites

- 使用 `.generated/venv-py314/bin/python3.14` 运行所有 Python 命令。
- 先读取 `prd.md`、`design.md`、本文件和相关 Trellis spec。
- 不修改无关 dirty 文件。

## Ordered Checklist

- [x] I1: 搜索旧临盘升级文案，确认渲染入口和测试断言。
- [x] I2: 更新运行时和 front-page 明日仓位表达：0% 写“不买新仓 / 只复盘”，50%/100% 写“已决定执行；不满足取消”。
- [x] I3: 更新 shell/action-plan 相关摘要，确保固定交易窗口不再被写成临盘创建买入决定。
- [x] I4: 扩展 `report_acceptance_audit.py`，把旧临盘升级文案作为验收错误。
- [x] I5: 更新交易思想文档和 Trellis spec，记录规则。
- [x] I6: 更新相关单测断言，新增旧文案失败 / 新文案通过样例。
- [x] I7: 运行窄测试，必要时运行 2026-06-24 报告验收审计。
- [x] I8: 提交前启用子代理做一轮审计，按审计结果修正。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-24_A股日报_完整版.md`

## Validation Results

- 2026-06-24 21:xx: `py_compile` for changed runtime helpers passed.
- 2026-06-24 21:xx: `tests.test_runtime_contracts tests.test_front_summary_support tests.test_llm_wiki_context tests.test_llm_wiki_router` — 64 tests OK.
- 2026-06-24 21:xx: `tests.test_action_plan_renderer tests.test_candidate_selection_stage tests.test_front_page_v2_renderer tests.test_two_layer_decision_payload tests.test_report_acceptance_audit` — 307 tests OK.
- 2026-06-24 21:xx: `tests.test_watch_anchor_support tests.test_pk_decision_stage tests.test_positioning_node_runtime tests.test_market_research_renderer` — 122 tests OK.
- 2026-06-24 21:xx: `tests.test_report_runtime` — 273 tests OK.
- 2026-06-24 21:xx: `scripts/report/report_acceptance_audit.py reports/2026-06-24_A股日报_完整版.md` — passed.
- 2026-06-24 23:xx: `py_compile scripts/report/runtime.py scripts/report/report_acceptance_audit.py` — passed.
- 2026-06-24 23:xx: `tests.test_report_runtime tests.test_report_acceptance_audit` — 417 tests OK.
- 2026-06-24 23:xx: `scripts/daily_report_entry_demo.py 2026-06-24 --overwrite-official` — official Markdown and HTML regenerated; report acceptance check passed; PostgreSQL facts synced with 42230 fields.
- 2026-06-24 23:xx: `scripts/report/report_acceptance_audit.py reports/2026-06-24_A股日报_完整版.md` — passed.
- 2026-06-24 23:xx: `rg` check confirmed `600584 长电科技` no longer appears as `候选观察`, `不作为新增参与依据`, `最终0%时只作观察样本`, or `明日买入决定：不买新仓` in the official full report.
- 2026-06-24 23:xx: `git diff --check` — passed.

## Subagent Audit Notes

- Turing found old wording in position strategy, runtime contracts, front summary, and llm wiki context; all listed real-source findings were patched and re-tested.
- Planck found the `front_summary_support.py` indentation failure, stale runtime-contract assertions, remaining “再决定/评估50%” wording in source, and stale task records; syntax, source wording, tests, and task records were corrected.
- Gibbs final read-only audit found positive-position wording that still read as “condition hit creates a new buy”; `front_page_v2_renderer.py`, `report_acceptance_audit.py`, and related tests were corrected so positive positions now read as already-decided execution plans and old wording is rejected.
- Aquinas/Banach final read-only audit requested after the 2026-06-24 official regeneration; awaiting final notes before commit.

## Risk And Rollback Points

- 风险：测试中大量旧断言依赖“条件成立才评估50%”表达。处理方式是只改和本契约直接相关的断言，不做大规模格式重排。
- 风险：多个渲染入口有相似文案。处理方式是先搜索旧字符串，再按入口逐个替换，并用验收审计兜住遗漏。
- 回滚点：如发现影响正式报告生成，可先保留审计规则和文档，回滚具体渲染变更，再重新定位入口。

## Review Checkpoints

- 0% 报告不再出现临盘升级买入口径。
- 正仓位报告清楚表达已决定的执行计划和取消条件。
- 观察对象只进入复盘或下一份日报，不在同日生成新增参与。
- 测试和审计覆盖旧口径失败、新口径通过。
