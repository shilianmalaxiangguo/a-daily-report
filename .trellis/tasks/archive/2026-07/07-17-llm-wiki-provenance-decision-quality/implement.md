# Implementation: LLM Wiki 引用轨迹与决定质量优化

## Prerequisites

- 当前工作区包含其他任务的未提交改动；每一步只编辑本任务明确文件，并在完成后按 path 审核 diff。
- 所有 Python 命令固定使用 `.generated/venv-py314/bin/python3.14`。
- 实现前读取 `.trellis/spec/backend/daily-report-decision-loop.md`、Wiki 运行契约、术语契约和本任务 research。
- 先修正/确认现有 `tests/test_llm_wiki_context.py` 的陈旧 1x/2x 断言，再把它作为基线；不能把旧失败误归因于本任务。

## Ordered Checklist

- [x] I1: 新增 `scripts/knowledge/llm_wiki_manifest.py`，完成稳定 JSON/hash、来源路径验证、来源内容指纹、manifest 规范化和 validation。
- [x] I2: 新增 `tests/test_llm_wiki_manifest.py`，覆盖当前全部唯一知识、稳定指纹、字节变化、缺源、越界路径、重复 ID、非法 lifecycle 和缺 decision_scope。
- [x] I3: 扩展 `build_llm_wiki_context()` 的 target/query date、manifest、expected/missing sources、availability 和 warnings，同时保持旧字段兼容。
- [x] I4: 规范化显式 `knowledge_hit_facts` 白名单，并让事实提取返回 `facts_source` 与 warnings 所需信息。
- [x] I5: 新增 `route_llm_wiki_knowledge_trace()`，复用现有排序，记录 score/rank/fact paths/source refs/manifest hash/facts hash/trace hash；旧 route API 继续返回 hits。
- [x] I6: 更新 Wiki hook，从 ctx 提取目标日期，使用真实 availability/confidence/warnings。
- [x] I7: 更新 report runtime，只构建一次 manifest，写入兼容 hits 与完整 trace，并在知识附加前后比较正式决定投影。
- [x] I8: 更新报告短引用，确保每条显示内容能映射到 trace，且动作与条件始终早于知识/研究证据。
- [x] I9: 接入 fresh/replay 结构化产物；有冻结 trace 时优先复用，没有时明确区分当前复盘参考与当时知识。
- [x] I10: 新增 `wiki/index.md`、`wiki/log.md` 和只读 `scripts/knowledge/llm_wiki_lint.py`。
- [x] I11: 补齐 context/router/runtime/replay/decision isolation 测试，并逐字段比较正式决定不变量。
- [x] I12: 重新运行 Trellis check、Wiki lint、相关单测和改动范围审计；按补充审计后的验收矩阵回填 PRD。

## Supplemental Completion Audit Fixes

- [x] A1: R1/R2 增加 FIELD_MAPPINGS 隔离、来源元数据完整/缺失和仓库相对 `local_path` 的直接回归。
- [x] A2: R4 缺 target/query date 时返回不可用空轨迹，并由 hook 同步降为 0 confidence。
- [x] A3: R5 为全部运行知识补非空结构化确认条件，trace 实施“词语召回候选 + 结构事实确认”，旧 list API 保持兼容。
- [x] A4: R8 当前来源字节变化时保留冻结 manifest/trace/hits，replay 外层降低复核可用性。
- [x] A5: R9 增加 version-only、content-hash-only、hit-change、knowledge-missing 四类 manifest 变体的完整正式决定投影比较。
- [x] A6: 重跑原定六组回归、Wiki lint、Trellis validate、语法、diff，并完成首轮提交前独立审计；审计发现的非法日期与提前附加问题已增加回归并修正。
- [x] A7: 对审计修正做独立复核，重跑最终机械检查并回填完成状态。
- [x] A8: 第二轮提交前独立审计发现冻结轨迹只校验日期非空；已增加规范日历日期、context/trace 日期一致性和快照拒绝回归，并重新运行原定验证。
- [x] A9: 完成性审计补齐 expected-only 来源元数据提醒、context 顶层已找到来源，以及 context/hook/runtime/replay 的统一数值置信度；新增失败回归后完成最小修正，并重跑原定验证。
- [x] A10: 最终提交前审计补齐 entry/source 元数据一致性、异常 hook 降级和来源变化 replay 的重复复用；修正证据计数后再次运行全部验证。
- [x] A11: 续跑提交前审计补齐非 Mapping 公共入口、畸形 manifest 内部字段、hook 外层提醒字段和无原因 invalid 清单的非异常诊断；新增分层失败回归后完成最小修正。
- [x] A12: 本轮六路提交前审计及最终补丁复核补齐 context 畸形列表字段、非 Mapping facts、`must_any` / `prefer_any` 过宽条件父路径、零命中 trace 顶层解释边界和冻结完整性；lint 对编译后影响边界缺失增加直接回归，并重新运行原定验证。
- [x] A13: 在混合工作区逐路径审计选择性提交范围，补齐 `commit-scope.md`；实际选择性暂存、隔离副本验证和提交等待明确授权。
- [x] A14: 独立范围审计发现 manifest 测试固定最低 30 条、另一个 Bear HTML 用例遗漏 fresh Wiki fixture；已改为按提交时实际条目核对，补齐对应选择块，并以排除 5 条并行业务知识后的 25 条候选完成定向编译，再重跑原定七组单测。
- [x] A15: 本轮提交前审计补齐旧列表 helper 对未知顶层根的隔离、异常 hook 的完整 trace、R9 的真实 A/B 来源字节与失配拒绝、非空 B1/B2/旧仓/退出投影，以及正式落盘 HTML 顺序；恢复后重新运行原定七组回归和机械检查。
- [x] A16: 基于旧候选基线构造 38 路径选择性候选；补齐内部事实 helper 改名依赖，并让正式动作后路由测试显式提供白名单事实。候选补丁已由第二套临时索引重放为同一 tree，隔离验证区分本任务结果、候选外 replay 异常和被范围契约排除的测试模块。
- [x] A17: 六个只读代理完成提交前范围、混合块、决定隔离、文档与验证审计；以 `c0e7dddd085815da28ec8cd7cbe13fb0ecb1ebcc` 重建同一 38 路径候选并重新隔离验证。runtime 1 项、Markdown/Bear/入口 7 项、replay 2 项异常均在纯当前 HEAD 逐项复现，未扩大候选去修并行业务基线。
- [x] A18: 四路最终暂存审计发现 fresh Wiki 完整性检查仍晚于部分持久化动作，且 replay 缺历史轨迹时按宿主本地日期填写查询日；两条失败回归先复现再完成最小修正。完整性检查现位于 PostgreSQL、运行期产物、Markdown/HTML 和快照写入之前，缺历史轨迹统一使用上海日期；同步失败用例补齐完整 Wiki 夹具。最终候选重建后，HTML/Bear/入口为 81 项、replay 为 65 项、Wiki replay 专用为 5 项。
- [x] A19: 续查持久化边界后，fresh 完整性改为同时核对当前 Wiki 来源字节，入口失败时不再写质量记录，snapshot hook 同步使用 fresh 校验；保留 `--no-report` 的数据采集、PostgreSQL 同步和质量记录契约。新增来源伪造、非 Mapping replay、质量记录与 `--no-report` 回归后，38 路径候选重新构造并通过隔离验证。
- [x] A20: 六路提交前审计后补齐三个边界：Wiki 检查异常时先暂停质量记录、公共 replay helper 自行使用上海日期、sections facade 不再编译当前 Wiki且 replay 只消费冻结上下文；同步修正专用用例数量与 R9 证据表述。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_manifest tests.test_llm_wiki_context tests.test_llm_wiki_router tests.test_llm_wiki_hook tests.test_llm_wiki_lint tests.test_use_snapshot_persistence`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_replay`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow tests.test_two_layer_decision_payload`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer tests.test_daily_report_render`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_html_output tests.test_daily_report_markdown_html`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_orchestrator`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_use_report_sections`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_replay.ReportReplayTest.test_build_replay_snapshot_contract_reuses_target_date_frozen_wiki_trace tests.test_report_replay.ReportReplayTest.test_build_replay_snapshot_contract_rejects_frozen_wiki_trace_from_another_date tests.test_report_replay.ReportReplayTest.test_build_replay_snapshot_contract_marks_missing_historical_wiki_trace tests.test_report_replay.ReportReplayTest.test_missing_historical_wiki_trace_uses_shanghai_query_date tests.test_report_replay.ReportReplayTest.test_build_replay_snapshot_contract_marks_non_mapping_nested_wiki_missing`；这 5 个 Wiki 专用用例覆盖目标日冻结复用、日期错配、历史引用缺失、上海查询日和非 Mapping Wiki；`tests.test_position_action_semantics` 按范围契约整体排除。
- `.generated/venv-py314/bin/python3.14 scripts/knowledge/llm_wiki_lint.py`
- `.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py validate 07-17-llm-wiki-provenance-decision-quality`
- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/knowledge/llm_wiki_manifest.py scripts/knowledge/llm_wiki_context.py scripts/knowledge/llm_wiki_router.py scripts/knowledge/llm_wiki_lint.py scripts/hooks/knowledge/use_llm_wiki.py scripts/hooks/persist/use_snapshot_persistence.py scripts/hooks/report/use_report_sections.py scripts/replay/report_replay.py scripts/report/runtime.py scripts/daily_report_render.py`
- `git diff --check`
- `git diff --name-only`

## Risk And Rollback Points

- **R1: import cycle**：manifest compiler 不反向 import context/runtime；router 条目作为参数传入。I1-I5 后先跑 knowledge 单测。
- **R2: 大型旧测试脆弱**：保留旧字段和 API；新增字段不改变报告短表的既有列。每阶段跑最窄兼容测试。
- **R3: replay 污染**：没有冻结 trace 时宁可明确缺失，不从当前 Wiki 伪造历史命中。
- **R4: 工作区混合**：不执行 reset/checkout，不格式化无关文件；最终只按本任务 path 审核。
- **R5: 决定意外变化**：任何正式决定逐字段不一致都视为本任务失败，立即回滚 runtime 反向读取知识的路径。

## Review Checkpoints

1. I1-I3 完成：检查 manifest/context 契约、稳定哈希和兼容字段。
2. I4-I7 完成：检查结构化事实、trace、hook/runtime 和决定投影。
3. I8-I10 完成：检查报告顺序、replay 隔离、index/log/lint。
4. I11-I12 完成：subagents 做提交前独立审计，主线程点验关键出处与全部验收证据。

## Roll-forward Notes

- 后续若结构化知识规模明显增长，再评估把声明机械移动到独立 registry 或由 Wiki frontmatter 编译。
- 只有在历史误召回/漏召回数据证明关键词不足后，才单独规划 BM25/向量/图扩展。
- source_date/anchor 缺失的旧节点逐次维护补齐，不在本任务批量伪造。
