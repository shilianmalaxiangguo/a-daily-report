# 2026-06-10 日报 P0/P1 全量关闭规格

## Goal

把 Mermaid 逻辑页列出的 P0/P1 从页面说明升级为项目级生成契约，确保最终对象、T-006 今日判断、Bear HTML、结构化 HTML、用户可见术语和历史 replay 来源日期都有代码级保护。

## In Scope

- 关闭 P0：最终对象解析两段流程导致的前台对象错配。
- 关闭 P0：过程候选从候选池、`best_stock` 或同日记录误入 T-006 当前核心候选。
- 关闭 P1：入口并存时，正式日报入口仍以 `scripts/daily_report_entry_demo.py` 的保存前后一致性检查为准。
- 关闭 P1：Bear 阅读版 HTML 来自最终 Markdown；结构化 HTML 只作为事实看板，不覆盖阅读版口径。
- 关闭 P1：用户可见术语检查覆盖整篇 Markdown，而不是只看首页。
- 关闭 P1：replay 股票行情必须证明属于目标日期，不能使用无日期或错日期行情回补历史日报。

## Out of Scope

- 不重写候选池评分、排序、板块锚反推或最终对象算法。
- 不改 Mermaid 页视觉样式。
- 不覆盖无关历史正式日报。
- 不处理当前工作区里与本任务无关的 Trellis、wiki、导出、数据库或图表改动。

## Non-goals

- 不把观察对象包装成明日新增参与对象。
- 不隐藏双星新材、中船特气等过程证据；只要求它们保留正确身份。
- 不引入新的报告入口或新 HTML 渲染框架。

## Contracts

1. `final_target_resolution_audit` 必须记录 `pre_tail` 和 `front_page` 身份；若两次解析不同，前台以 `front_page` 为准，并记录 `resolution_policy=front_page_final_resolution`。
2. T-006 当前核心候选只接受最终解析允许的新参与对象或可用替代对象；最终结果为 0% 或仅观察时显示 `待补事实`。
3. `report_acceptance_audit.py` 必须扫描整篇 Markdown，发现最终对象、T-006、推导链、候选生命周期、观察顺序或 selection workflow 之间的身份冲突。
4. `report_acceptance_audit.py` 必须扫描整篇 Markdown 的旧工程口径；发现后停止生成。
5. 主入口保存日报时必须先通过 Markdown 一致性检查，再同步事实、保存 Markdown、生成 Bear HTML。
6. Bear HTML 必须由保存后的完整 Markdown 渲染；结构化 HTML 只能由 `html_report_view/html_report_renderer` 消费结构化事实并作为独立看板。
7. replay 股票行情只接受 `trade_date/source_date/query_date/date == target_date` 的报价。无日期、错日期或回补失败时清空旧行情字段并记录降级日志。
8. 历史观察样本只能写作观察/复核身份，不能写成当前已满足执行资格或正式新增参与身份。

## Acceptance Criteria

- AC-P0-1: 给定 `pre_tail` 和 `front_page` 解析对象不同，报告运行期记录两者，并以前台解析为最终可见对象。
- AC-P0-2: 给定 `best_stock=双星新材` 且最终对象只有观察身份，T-006 今日判断显示 `待补事实`。
- AC-P0-3: 给定 0%不参与报告中 T-006 写入具体候选，保存后审计失败。
- AC-P1-1: 给定正式入口成功生成日报，Bear HTML 从保存后的完整 Markdown 生成，结构化 HTML 不抢占同名阅读版。
- AC-P1-2: 给定结构化 HTML view 的 0%不参与且有具体观察对象，view 输出 `observation_target`，`primary_target` 为空。
- AC-P1-3: 给定整篇 Markdown 任意位置出现旧工程口径，日报一致性检查失败。
- AC-P1-4: 给定 replay 历史快照行情无日期、错日期或回补失败，对应股票行情字段被清空并记录降级。
- AC-P1-5: 给定历史观察复核样本，候选生命周期文字不包含正式新增参与身份。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_decision_statistics tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_replay tests.test_candidate_bundle_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_html_output tests.test_daily_report_html_view tests.test_daily_report_html_renderer tests.test_daily_report_markdown_html`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-10_A股日报_完整版.md --json`

## 2026-06-11 Execution Notes

- 当前最新 2026-06-10 日报前台对象为 `雅克科技(002409)` 观察对象，明日执行对象为空。
- `双星新材(002585)` 是候选观察补充和过程证据，不是当前执行对象。
- `中船特气(688146)` 是历史观察证据，不是当前前台最终对象。
- Mermaid 页里的 P1 不是新的对象错配；它们是此前尚未纳入 PRD 验收的防回归项，本规格将其正式纳入。
