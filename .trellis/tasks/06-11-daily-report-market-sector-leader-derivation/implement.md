# Implementation: 日报市场板块龙头推导重构

## Prerequisites

- 使用 `.generated/venv-py314/bin/python3.14` 运行所有 Python 命令。
- 先读 `prd.md`、`design.md` 和 `research/current-selection-workflow-evidence.md`。
- 修改前确认当前工作树里相关文件是否已有用户改动，不能回退无关变更。

## Ordered Checklist

- [x] I1: 更新 `tests/test_selection_workflow.py`，加入严格板块推导样本：T字板/一字板不能作为新仓候选入口，板块先铺后筛出的核心可以进入对照。
- [x] I2: 扩展 `scripts/report/selection_workflow.py`，新增 `derivation_contract = "sector_first_strict.v1"`、市场/资金/板块/市场情绪线/龙头结构化字段和严格候选入口规则。
- [x] I3: 增加对象分层测试和逻辑：新仓候选、持仓风险处理对象、手动问股观察对象分开流转。
- [x] I4: 增加线路冲突测试和逻辑：市场情绪线与板块主线冲突时按环境切换优先级，未分胜负时不输出100%。
- [x] I5: 增加关键数据缺失测试和逻辑：市场、板块发酵、市场情绪线、龙头、价格行为或账户执行关键数据缺失时，停止生成日报并列出缺失项。
- [x] I6: 更新 Mermaid 输出，确保节点展示市场、资金、板块、市场情绪线、龙头、价格行为、执行资格和最终结论。
- [x] I7: 更新 `tests/test_two_layer_decision_payload.py` 和 `scripts/report/two_layer_decision_payload.py`，让日报正文推导层展示新版链路和严格候选生命周期。
- [x] I8: 更新 `tests/test_front_page_v2_renderer.py` 和 `scripts/report/front_page_v2_renderer.py`，确保首页只消费 `selection_workflow.final`，旧对象不能残留。
- [x] I9: 更新 `tests/test_daily_report_markdown_html.py` 和 Bear HTML 相关模板/渲染，确保最终 Markdown 中的新推导链在 Bear 版 HTML 中可读。
- [x] I10: 运行窄测试，修正不符合 PRD 的旧断言。
- [x] I11: 选择一个 replay 日期生成日报，检查正文和 Bear HTML 的推导链是否同源。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_daily_report_markdown_html`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <target-date> --replay`

## Risk And Rollback Points

- `selection_workflow` 字段会影响多个消费者，优先新增字段并保留旧字段。
- 日报正文和 Bear HTML 由 Markdown 串联，正文若没有新版推导，HTML 也不会有；不要在 HTML 里另写一套判断。
- 若历史 replay 缺少板块发酵数据，必须停止生成并列出缺失项，不回退到涨停入口，也不输出观察版日报。

## Review Checkpoints

- [x] 新旧样本都通过：旧错误样本不能成为新仓候选，板块先铺样本可以进入对照。
- [x] 缺失关键数据样本必须停止生成，并提示优先修复缺失数据。
- [x] Mermaid、日报正文、首页和 Bear HTML 最终对象一致。
- [x] 用户可见文字符合 `wiki/交易思想/日报术语契约.md`。

## Verification Evidence

- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow` passed, 16 tests.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight` passed, 32 tests.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_daily_report_markdown_html` passed, 130 tests.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router` passed, 38 tests.
- 2026-06-12: `scripts/daily_report_entry_demo.py 2026-06-12 --replay` could not verify because `snapshots/2026-06-12.json` is missing.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay` generated replay markdown and HTML successfully.
- 2026-06-12: `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-05_A股日报_完整版_replay.md` passed.
- 2026-06-12: lint/typecheck commands were not available: `.generated/venv-py314/bin/python3.14 -m ruff --version` and `.generated/venv-py314/bin/python3.14 -m mypy --version` both reported missing modules.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_candidate_traces_can_be_built_from_selection_workflow tests.test_report_runtime.ReportRuntimeTest.test_runtime_inserts_single_final_target_solution_before_account_advice tests.test_report_runtime.ReportRuntimeTest.test_selection_workflow_zero_blocks_surface_candidate_even_with_front_observation tests.test_report_runtime.ReportRuntimeTest.test_selection_workflow_can_feed_two_layer_and_sniper_packets tests.test_report_runtime.ReportRuntimeTest.test_daily_judgment_front_panel_uses_anchor_primary_not_same_day_observation_records` passed, 5 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow` passed, 16 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_front_page_v2_renderer tests.test_daily_report_markdown_html` passed, 130 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router` passed, 38 tests.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay` generated replay markdown and HTML successfully; report consistency check passed; output table now renders `入口处理` and old legacy tomorrow-action wording is absent.
- 2026-06-13: `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-05_A股日报_完整版_replay.md` passed after replay regeneration.
- 2026-06-13: lint/typecheck commands were still unavailable: `.generated/venv-py314/bin/python3.14 -m ruff --version` and `.generated/venv-py314/bin/python3.14 -m mypy --version` both reported missing modules.
