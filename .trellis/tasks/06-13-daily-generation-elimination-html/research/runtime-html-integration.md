# Research: runtime HTML integration

- Query: 日报生成同步产出淘汰赛 HTML 的 runtime / 保存层 / 验收审计接入点。
- Scope: internal
- Date: 2026-06-13

## Findings

### Files Found

- `.trellis/tasks/06-13-daily-generation-elimination-html/prd.md`: 本子任务要求 replay 生成后同步出现 companion HTML，并给出建议路径与审计命令。
- `.trellis/tasks/06-13-sector-first-elimination-html/design.md`: 父设计明确数据流为 runtime 构建最终对象和淘汰赛 payload，再写出静态 companion HTML。
- `.trellis/tasks/06-13-sector-first-elimination-html/implement.md`: 父实现清单把日报接入和验收扩展列为 I6/I7/I8。
- `.trellis/tasks/06-13-elimination-evidence-contract/prd.md`: 上游子任务定义 payload 至少包含 `trade_date`、`variant`、`final_action`、`layers`。
- `.trellis/tasks/06-13-elimination-html-renderer/prd.md`: 渲染器子任务限定为静态 HTML 字符串，不接入日报生成命令。
- `.trellis/spec/backend/daily-report-decision-loop.md`: 约束最终动作来源、历史 replay 日期边界、`selection_workflow`、`sniper_target_derivation` 和验收审计一致性。
- `.trellis/spec/backend/database-guidelines.md`: 约束 runtime 计算事实需回写 `data` 后再进 PostgreSQL；渲染后的 markdown/html 属低价值输出，不应写入事实库。
- `scripts/daily_report_entry_demo.py`: 日报入口，串起 replay/live 数据、报告构建、PostgreSQL 同步、runtime 产物、Markdown 保存、缠论 HTML、Markdown 阅读器 HTML。
- `scripts/daily_report_render.py`: Markdown 变体命名、保存路径和 runtime 产物持久化入口。
- `scripts/report/runtime.py`: 构建并存储 `selection_workflow`、`final_target_resolution`、`two_layer_decision_payload`、`sniper_target_derivation`。
- `scripts/report/report_acceptance_audit.py`: Markdown 与 companion HTML 的一致性审计入口。
- `scripts/report/markdown_report_html.py`: 从已保存 Markdown 生成同名阅读器 HTML。
- `scripts/export/sh_index_chanlun_html.py`: 上证缠论 companion HTML 生成与保存路径。
- `tests/test_daily_report_entry_html_output.py`: 当前覆盖 Markdown 保存后再生成 HTML 的调用顺序，是日报接入回归最窄落点。
- `tests/test_report_acceptance_audit.py` / `tests/test_report_acceptance_audit_cli.py`: 当前覆盖 `sniper_target_derivation`、`selection_workflow` 与 `--companion-html` 失配场景。

### 1. Markdown / HTML / replay 产物保存位置与最小接入点

Markdown 主产物由 `daily_report_render._get_report_output_path()` 决定路径：official 写 `reports/<date>_A股日报_<variant>.md`，replay 写 `reports/replay/<date>_A股日报_<variant>_replay.md`，见 `scripts/daily_report_render.py:142`-`scripts/daily_report_render.py:149`。`save_report_output()` 在 official 已存在且未允许覆盖时会自动改写 replay 路径，见 `scripts/daily_report_render.py:1549`-`scripts/daily_report_render.py:1572`；`save_report_outputs()` 循环保存所有 Markdown 变体并返回 `saved_paths`，见 `scripts/daily_report_render.py:1575`-`scripts/daily_report_render.py:1614`。

日报入口的实际落盘顺序在 `main()`：先 `build_report_outputs()` 生成 Markdown 字符串，见 `scripts/daily_report_entry_demo.py:4358`-`scripts/daily_report_entry_demo.py:4366`；再用内存中的缠论 HTML 做审计，见 `scripts/daily_report_entry_demo.py:4367`-`scripts/daily_report_entry_demo.py:4376`；PostgreSQL 同步成功后才写 runtime 产物，见 `scripts/daily_report_entry_demo.py:4378`-`scripts/daily_report_entry_demo.py:4397`；随后 `save_report_outputs()` 保存 Markdown，见 `scripts/daily_report_entry_demo.py:4399`-`scripts/daily_report_entry_demo.py:4406`。

已保存 Markdown 的阅读器 HTML 不是结构化 dashboard，而是从 `saved_report_paths[REPORT_VARIANT_FULL]` 同名转 `.html`：`_try_save_daily_report_html_from_saved_markdown()` 读取完整版 Markdown 并调用 `render_markdown_report_file(full_report_path, full_report_path.with_suffix(".html"), ...)`，见 `scripts/daily_report_entry_demo.py:4109`-`scripts/daily_report_entry_demo.py:4125` 与 `scripts/report/markdown_report_html.py:1564`-`scripts/report/markdown_report_html.py:1582`。结构化 HTML renderer 也有路径规则：`reports/<date>_A股日报_完整版.html` 或 `reports/replay/<date>_A股日报_完整版_replay.html`，见 `scripts/report/html_report_renderer.py:269`-`scripts/report/html_report_renderer.py:281`，但入口测试明确当前主流程使用 Markdown 阅读器 HTML，不调用结构化 HTML 保存函数，见 `tests/test_daily_report_entry_html_output.py:115`-`tests/test_daily_report_entry_html_output.py:140`。

上证缠论 companion HTML 当前固定写 `reports/chanlun-html/<date>_上证指数缠论.html`，不随 replay 目录变化，见 `scripts/export/sh_index_chanlun_html.py:458`-`scripts/export/sh_index_chanlun_html.py:495`；入口在 Markdown 保存后调用它，见 `scripts/daily_report_entry_demo.py:4407`-`scripts/daily_report_entry_demo.py:4415`。

推荐最小接入方案：

1. payload 构建在 runtime 完成同源结构后进行，不要从 Markdown 反推。具体是在第二次 `front_page` 口径的 `two_layer_decision_payload` 与 `sniper_target_derivation` 已存入 `data` / `execution_stage_context` / `market_research_snapshot` 后，见 `scripts/report/runtime.py:8171`-`scripts/report/runtime.py:8198`；此时 `market_research_snapshot` 也被补入 `position_decision`、`selected_position_candidate`、`final_target_resolution`，见 `scripts/report/runtime.py:8254`-`scripts/report/runtime.py:8259`。
2. 文件写入放在入口保存 Markdown 之后，使用 `saved_report_paths[REPORT_VARIANT_FULL]` 的父目录派生 companion 路径。最小位置是 `save_report_outputs()` 返回后、耗时日志前，见 `scripts/daily_report_entry_demo.py:4399`-`scripts/daily_report_entry_demo.py:4449`。这样 replay、official、自定义 `output_dir` 都跟随 Markdown 的真实保存目录。
3. 不建议把淘汰赛 HTML 塞进 `save_report_outputs()` 的 Markdown 变体循环，因为该函数当前只接收字符串报告变体，不接收 runtime `data`，见 `scripts/daily_report_render.py:1575`-`scripts/daily_report_render.py:1585`。更小的改法是新增类似 `_try_save_daily_report_html_from_saved_markdown(...)` 的 helper，签名带 `data`、`target_date`、`run_mode`、`saved_report_paths`。

### 2. 四个结构从 runtime 到保存层的传递路径

`build_report_outputs()` 是保存层之前的共同入口。它先做事实完整性检查，再两次调用 `_render_report_with_display_mode()` 生成完整版和摘要，见 `scripts/daily_report_render.py:1355`-`scripts/daily_report_render.py:1413`。该 facade 会回到 `daily_report_entry_demo.generate_markdown_report()`，再进入 `render_markdown_report_runtime()`，见 `scripts/daily_report_entry_demo.py:3633`-`scripts/daily_report_entry_demo.py:3667` 与 `scripts/report/runtime.py:7034`-`scripts/report/runtime.py:7079`。

`selection_workflow` 的源头是 `scripts/report/selection_workflow.py:693`-`scripts/report/selection_workflow.py:845`，其中 `nodes` 固定 N0-N9，`candidate_pool` 和 `final` 一起返回；`store_selection_workflow()` 把同一份 dict 写入传入 targets，见 `scripts/report/selection_workflow.py:848`-`scripts/report/selection_workflow.py:855`。runtime 包装后还派生 candidate traces，并把 workflow 写入 `data`、`execution_stage_context`、`market_research_snapshot`，见 `scripts/report/runtime.py:2305`-`scripts/report/runtime.py:2318`。

runtime 有两轮最终对象收口。第一轮在尾部整理前：`selection_workflow` 构建/存储见 `scripts/report/runtime.py:7806`-`scripts/report/runtime.py:7819`，`final_target_resolution` 构建/存储见 `scripts/report/runtime.py:7820`-`scripts/report/runtime.py:7833`。第二轮在附录后、前台渲染前：`selection_workflow` 见 `scripts/report/runtime.py:8131`-`scripts/report/runtime.py:8144`，`final_target_resolution` 见 `scripts/report/runtime.py:8145`-`scripts/report/runtime.py:8158`。`_store_runtime_final_target_resolution()` 写入 `data`、`execution_stage_context`、`market_research_snapshot` 并记录前后身份，见 `scripts/report/runtime.py:2785`-`scripts/report/runtime.py:2829`。

`two_layer_decision_payload` 从 `execution_stage_context` 读取 `selection_workflow`，见 `scripts/report/two_layer_decision_payload.py:317`-`scripts/report/two_layer_decision_payload.py:327`；builder 以 `final_target_resolution`、`position_decision`、`execution_stage_context` 为入参，见 `scripts/report/two_layer_decision_payload.py:970`-`scripts/report/two_layer_decision_payload.py:988`。runtime 在第二轮最终对象后构建并存储该 payload，见 `scripts/report/runtime.py:8171`-`scripts/report/runtime.py:8182`；存储函数写入三个 runtime 容器，见 `scripts/report/runtime.py:2872`-`scripts/report/runtime.py:2885`。

`sniper_target_derivation` 读取 `data`、`execution_stage_context`、`market_research_snapshot` 中的 `selection_workflow`，并在可用时直接从 workflow 生成 packet；否则结合 `final_target_resolution` 与 `two_layer_decision_payload` 得到 canonical target，见 `scripts/report/sniper_target_derivation.py:524`-`scripts/report/sniper_target_derivation.py:556`。runtime 在 `two_layer_decision_payload` 后构建并存储，见 `scripts/report/runtime.py:8183`-`scripts/report/runtime.py:8198`；存储函数写入三个 runtime 容器，见 `scripts/report/runtime.py:2856`-`scripts/report/runtime.py:2869`。

保存层本身只拿到 `report_outputs` 字符串与 `saved_paths`，不主动接收这些 dict。它们能到保存层，是因为 `build_report_outputs()` 渲染期间原地更新了 `data`，然后入口在同一作用域继续持有 `data`。所以淘汰赛接入应读取 `data["selection_workflow"]` / `data["final_target_resolution"]` / `data["two_layer_decision_payload"]` / `data["sniper_target_derivation"]`，并对 `execution_stage_context`、`market_research_snapshot` 做 fallback，而不是从 Markdown 或 HTML 解析。

### 3. report_acceptance_audit.py 的现有 HTML / 缠论检查与扩展点

当前 CLI 只有一个 HTML 参数：`--companion-html`，读取文件文本后传给 `audit_report_markdown(..., companion_html=...)`，见 `scripts/report/report_acceptance_audit.py:2899`-`scripts/report/report_acceptance_audit.py:2922`。`audit_report_markdown()` 在最后统一追加 companion HTML 检查，见 `scripts/report/report_acceptance_audit.py:2860`-`scripts/report/report_acceptance_audit.py:2892`。

现有 companion HTML 检查只针对上证缠论的“明日抉择”表：`_extract_chanlun_tomorrow_decision_values()` 查找 `<h2>明日抉择</h2>` 后的第一张表，抽取“最终执行条件 / 明日最大仓位 / 新增参与”等键值，见 `scripts/report/report_acceptance_audit.py:454`-`scripts/report/report_acceptance_audit.py:471`。`_audit_chanlun_tomorrow_decision_consistency()` 只在 Markdown 前台最终为 `0%不参与` 且传入 companion HTML 时运行，见 `scripts/report/report_acceptance_audit.py:1864`-`scripts/report/report_acceptance_audit.py:1892`。

Markdown 本身已经有两条同源最终对象检查：`_audit_sniper_target_derivation_consistency()` 比较前台最终对象与传导链最终对象，见 `scripts/report/report_acceptance_audit.py:2440`-`scripts/report/report_acceptance_audit.py:2468`；`_audit_selection_workflow_consistency()` 比较前台对象与 `selection_workflow.final`，见 `scripts/report/report_acceptance_audit.py:2471`-`scripts/report/report_acceptance_audit.py:2577`。

推荐最小扩展点：

1. 保留 `--companion-html`，增加 HTML 类型分支。若 HTML 包含淘汰赛稳定标识（例如 `<meta name="artifact" content="elimination-tournament">` 或标题“明日标的选股淘汰赛”），走 `_audit_elimination_companion_consistency(lines, companion_html)`；否则继续走现有缠论检查。这样无需新增 CLI 参数，兼容 PRD 中的验收命令。
2. 新检查放在现有 companion 调用附近，即 `scripts/report/report_acceptance_audit.py:2889` 前后；先抽取淘汰赛最终层中的 `final_action.target` / `position_pct` / `label`，再与 Markdown 前台最终对象、`selection_workflow.final`、`sniper_target_derivation` 的最终对象做一致性比较。
3. 若上游 renderer 能把 payload JSON 安全内嵌到 `<script type="application/json" id="elimination-payload">`，审计应优先 JSON 解析，失败再做少量 HTML 文本检查。这样比用表格文案 regex 更稳，也符合“HTML 只解释 payload，不重新推导”的父设计。
4. Focused tests 放在 `tests/test_report_acceptance_audit.py` 新增匹配/失配样例；CLI 保留在 `tests/test_report_acceptance_audit_cli.py`，可复用现有 `--companion-html` 失败模式，见 `tests/test_report_acceptance_audit_cli.py:100`-`tests/test_report_acceptance_audit_cli.py:119`。

### 4. 2026-06-12 replay 后最合理的淘汰赛 HTML 路径

`2026-06-12 --replay` 的完整版 Markdown 路径应为：

```text
reports/replay/2026-06-12_A股日报_完整版_replay.md
```

依据是 replay 模式进入 `reports/replay/` 并添加 `_replay` suffix，见 `scripts/daily_report_render.py:142`-`scripts/daily_report_render.py:149`。Markdown 阅读器 HTML 会从该 Markdown 同名转 `.html`，因此是：

```text
reports/replay/2026-06-12_A股日报_完整版_replay.html
```

淘汰赛 companion 不应复用这个同名 HTML，也不应写入 `reports/chanlun-html/`，因为它需要和 replay Markdown 共同定位且避免 official/replay 同日覆盖。最合理路径是 PRD 已给出的稳定命名：

```text
reports/replay/2026-06-12_明日标的选股淘汰赛.html
```

实现上建议用 `Path(saved_report_paths[REPORT_VARIANT_FULL]).parent / f"{target_date}_明日标的选股淘汰赛.html"`。official 生成时自然落到：

```text
reports/2026-06-12_明日标的选股淘汰赛.html
```

若未来支持 `output_dir`，同一 parent 派生规则也能让 companion 跟随自定义输出目录。

### Recommended Minimal Integration Plan

1. 在主会话实现的 `scripts/report/elimination_tournament.py` 中提供两个纯函数：`build_elimination_tournament_payload(data, target_date, variant)` 和 renderer/save helper（具体函数名以主会话实现为准）。
2. 在 `scripts/report/runtime.py` 第二轮最终对象收口后把 payload 写回 `data["elimination_tournament_payload"]`、`execution_stage_context["elimination_tournament_payload"]`、`market_research_snapshot["elimination_tournament_payload"]`。推荐位置在 `sniper_target_derivation` 存储后，见 `scripts/report/runtime.py:8183`-`scripts/report/runtime.py:8198`。
3. 在 `scripts/daily_report_entry_demo.py` 中新增 `_try_save_elimination_tournament_html(...)`，调用点放在 `save_report_outputs()` 之后、耗时日志之前，见 `scripts/daily_report_entry_demo.py:4399`-`scripts/daily_report_entry_demo.py:4449`。
4. 路径由完整版 Markdown parent 派生：`reports/replay/<date>_明日标的选股淘汰赛.html` 或 `reports/<date>_明日标的选股淘汰赛.html`。
5. `report_acceptance_audit.py` 继续接收 `--companion-html`，根据 HTML 内稳定标识分支到淘汰赛一致性检查；不要让淘汰赛 HTML 重新挑最终对象。
6. 最小回归测试：
   - `tests/test_daily_report_entry_html_output.py`: 断言顺序变为 `sync -> runtime_artifacts -> markdown -> elimination_html -> chanlun -> html` 或团队确认的相邻顺序，并断言 replay 路径 parent 正确。
   - `tests/test_report_acceptance_audit.py`: companion final action 与 Markdown 最终对象匹配时通过，失配时返回新 finding code。
   - `tests/test_report_acceptance_audit_cli.py`: `--companion-html reports/replay/2026-06-12_明日标的选股淘汰赛.html` 可发现失配。
   - 生成验收：`.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay` 后检查上述 HTML 路径存在。

## Caveats / Not Found

- `.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py current --source` 在本研究会话返回 `Current task: (none)`；用户已明确目标写入路径，所以本文件仍写入 `.trellis/tasks/06-13-daily-generation-elimination-html/research/`。
- 只读检查未发现 `scripts/report/elimination_tournament.py` 或对应测试已落盘；主会话可能仍在并行实现中。因此本研究只引用现有 runtime / 保存 / 审计代码，未引用尚未出现的函数签名。
- 只读检查未在当前工作区发现 `reports/replay/2026-06-12...` 产物；本研究没有运行 replay 生成命令，避免和主会话并行实现互相影响。
- External references: none. 本问题只需要仓库内部代码、Trellis 任务文档与项目 spec。
