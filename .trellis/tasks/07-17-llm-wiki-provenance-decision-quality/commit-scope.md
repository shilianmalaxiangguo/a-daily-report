# LLM Wiki 选择性提交范围证据

状态：范围审计与候选隔离完成；真实暂存与提交等待明确授权。

## 现场基线

- 审计日期：2026-07-17。
- 分支：`develop`。
- 基线提交：`4c18ce2583bff9300b397863b04f95d252ed7a1d`。
- `HEAD` 与 `origin/develop` 的左右差异均为 0。
- 写入本文件后有 90 个已跟踪差异路径、18 个未跟踪文件（包含本文件）、0 个暂存路径；写入前未跟踪文件为 17 个。
- 候选构造前，另一个任务新增 Agent Memory 记录提交 `4c18ce2583bff9300b397863b04f95d252ed7a1d`；该提交只改对应任务下 2 个文件，没有触及本任务文件或混合文件选择块。
- 没有发现相关单测、lint、日报生成或语法检查进程残留，也没有发现 `.git/*.lock`。

以上数量只描述本次审计时点。授权暂存前若 `HEAD`、工作区路径数或本表列出的块发生变化，必须重新核对，不能沿用旧行号直接暂存。

## 选择规则

- 默认排除；只有下列整文件或明确符号块可以进入本任务提交。
- 禁止使用 `git add -A`、`git add .` 或把混合文件整文件加入暂存区。
- 混合文件按函数、常量或测试方法核对；行号只是本次审计定位，不是长期依据。
- Wiki 来源内容指纹在运行时按实际文件字节重新编译，不提交静态 hash。其他任务尚未提交的 Wiki 正文不因本任务 manifest 而自动进入提交。
- 本文件与 `.generated/commit-candidates/07-17-llm-wiki-provenance-decision-quality/` 共同记录候选范围和隔离证据；真实索引仍未执行选择性暂存。

## 整文件纳入候选

### 任务、规格与知识导航

- `.trellis/tasks/07-17-llm-wiki-provenance-decision-quality/**`
- `.trellis/spec/backend/llm-wiki-provenance.md`
- `scripts/knowledge/llm_wiki_manifest.py`
- `scripts/knowledge/llm_wiki_lint.py`
- `wiki/index.md`
- `wiki/log.md`

### Hook、编排与报告短引用

- `scripts/hooks/knowledge/use_llm_wiki.py`
- `scripts/hooks/persist/use_snapshot_persistence.py`
- `scripts/hooks/report/use_report_sections.py`
- `scripts/orchestrator/report_orchestrator.py`

### 专用测试

- `tests/test_llm_wiki_manifest.py`
- `tests/test_llm_wiki_lint.py`
- `tests/test_llm_wiki_hook.py`
- `tests/test_use_snapshot_persistence.py`
- `tests/test_use_report_sections.py`
- `tests/test_report_orchestrator.py`

## 只纳入指定块的混合文件

| 路径 | 纳入候选 | 明确排除 |
|------|----------|----------|
| `.trellis/spec/backend/index.md` | `LLM Wiki Provenance And Decision Isolation` 唯一索引行 | 其他 spec 修改 |
| `wiki/README.md` | 文件开头的 `知识导航`、`操作日志` 两个链接 | 账户语义、术语改写和市场二阶导入口 |
| `scripts/knowledge/llm_wiki_context.py` | manifest/hash 导入、可用性映射、扩展后的 `build_llm_wiki_context()`、冻结完整性与 replay helper | `FIELD_MAPPINGS`、`DAILY_DISCIPLINE_LINES` 的账户和交易语义改动 |
| `scripts/knowledge/llm_wiki_router.py` | trace 常量、日期与事实路径校验；HEAD 已有知识条目的 `fact_conditions`；旧事实入口改名为内部 helper；`_STRICT_FACT_SEPARATOR` 起的结构化事实、来源、排序、trace 与兼容 API 实现 | 新增业务知识 ID；已有条目的标题、触发词、正文影响或账户语义改写 |
| `scripts/report/runtime.py` | `deepcopy` 与 Wiki imports；`_llm_wiki_formal_decision_projection()`、`_attach_llm_wiki_knowledge_hits()`、context detach/cache；wrapper 中 fresh/replay 接入；删除 legacy body 内两处提前刷新 | `_attach_topic_lifecycle_snapshot()` 及其他持仓、空仓、旧仓、候选和尾部摘要改动 |
| `scripts/daily_report_entry_demo.py` | `is_complete_frozen_llm_wiki_context` import、`_assert_fresh_llm_wiki_trace_complete()`、正式快照写入前的调用 | 前日报标的继承、PostgreSQL 持仓、明日空仓及 CLI 改动 |
| `scripts/replay/report_replay.py` | `build_replay_llm_wiki_context` import、`_attach_replay_llm_wiki_context()`、非 Mapping 快照诊断、加载后接入与返回 artifact | `Path` import 和持仓时间线、其他历史回补改动 |
| `scripts/report/markdown_report_html.py` | `_EVIDENCE_H2_TITLES` 中 `知识模块`、`知识复利提示`、`知识复利候选`、`交易原则`、`经验库命中` | `明日新仓` 单元格和全部持仓时间线改动 |
| `tests/test_llm_wiki_context.py` | manifest/context/frozen/replay 专用 helper、`test_context_keeps_target_dates...` 起的 provenance 回归及对应兼容断言 | `test_explicit_tomorrow_empty...`、`test_huatian_unplanned_trade...` 和其他新增账户业务语义测试 |
| `tests/test_llm_wiki_router.py` | provenance imports 与 `test_trace_*`、事实白名单、来源、hash、日期、负向匹配、旧 helper 未知根和解释边界回归 | 账户候选回退、明日空仓、计划外交易、龙虎榜等知识扩展测试 |
| `tests/test_report_runtime.py` | `test_render_markdown_report_runtime_builds_wiki_manifest_once` 至 `test_runtime_routes_account_knowledge_after_formal_action` 中的 Wiki 专用回归；R9 用临时 Wiki A/B 字节重新编译且不跳过来源校验；正式动作后路由测试显式提供白名单事实 | 其余账户、旧仓、空仓、外部成交待核实和 topic lifecycle 测试 |
| `tests/test_report_replay.py` | Wiki imports、`_frozen_llm_wiki_context()`、4 个 `test_build_replay_snapshot_contract_*wiki*` / 非 Mapping 快照回归 | 市场数据回补和模拟持仓时间线测试 |
| `tests/test_daily_report_render.py` | `test_build_report_outputs_reuses_one_wiki_compile_and_keeps_evidence_after_actions` | 同一大块中的市场语言测试及其余旧仓/预检改动 |
| `tests/test_daily_report_entry_html_output.py` | `_complete_wiki_context()`、正常路径冻结 trace 与不完整 trace 拒绝测试；`test_bear_html_runs_after_report_runtime_data_exports` 中完整 Wiki fixture、快照 mock 和 `snapshot` 顺序断言；`test_saved_markdown_html_sync_overwrites_existing_reader_html` 中正式写出文件的动作/知识顺序断言 | 该方法其余 Bear HTML 逻辑及其他模拟旧仓、空仓、PostgreSQL 和 HTML 流程改动 |
| `tests/test_daily_report_markdown_html.py` | 现有 Bear 分类测试中的 Wiki 标题样例、分类断言和动作早于 Wiki 证据断言 | 市场语言、资金淘汰赛样例与断言，以及持仓时间线改动 |

### Router 业务知识排除清单

以下 5 个 ID 在当前工作区新增，但不属于 provenance 基础设施；本任务提交不得顺带加入：

- `discipline.tomorrow-empty-position-semantics`
- `discipline.unplanned-profit-qualification`
- `position.failed-position-loss-aversion`
- `evidence.dragon-tiger-list-sample-boundary`
- `discipline.long-thesis-short-failure-separation`

HEAD 已有的 `selection.rhythm-reset-margin-review`、`discipline.tplus-slot-timeline`、`intraday.do-t-risk-control`、`intraday.same-stock-t-failure-control` 只纳入 provenance 所需 `fact_conditions`；其他语义改写仍排除。

排除这 5 条后，基于当前 HEAD 的候选 `KNOWLEDGE_INDEX` 为 25 条。`tests/test_llm_wiki_manifest.py` 只断言 manifest 与提交时实际的 `KNOWLEDGE_INDEX` 逐条一致，不再把混合工作区的 30 条写成最低数量。

## 整体排除

- `tests/test_position_action_semantics.py`：只作为决定隔离回归输入，不是本任务实现产物。
- `wiki/交易思想/市场二阶导：基本面、价格与预期的边界.md`：标记为未接入日报，不属于运行知识来源。
- `scripts/daily_report_render.py`、`scripts/hooks/report/use_report_tail_summary.py`：当前差异与 Wiki provenance 无关。
- 其他已修改 Trellis spec、07-14 任务文件、研究 HTML、候选/持仓/市场语言/研究模块与测试。
- 其他 Wiki 正文修改，包括账户、价格行为、做 T、市场语言、术语、缠论和板块正文。

## 依赖闭环

本任务候选链路为：

`manifest -> context/router -> Wiki hook/runtime -> fresh snapshot/replay -> short citation/Bear classification -> dedicated tests/spec/index/log`

来源正文不保存静态 manifest。干净提交会按该提交实际包含的 `KNOWLEDGE_INDEX` 和已提交 Wiki 字节生成自洽 hash。审计期间基于未提交 Wiki 正文字节冻结的 fresh 产物，在正文未同步提交后可能出现来源内容变化诊断；这些本地产物不能作为提交后来源字节的固定依据。

## 本轮审计后验证

- 从当前 `KNOWLEDGE_INDEX` 排除上列 5 个 ID 后，定向编译得到 25 条候选 manifest entry，公共 manifest/source validation 为 0 errors。
- 当前混合工作区重新通过知识链 158、runtime 333、replay 64、决定隔离 99、渲染 175、Markdown/Bear/入口 95，共 924 项；编排器另 2 项。
- 上述全量结果证明当前工作区集成行为；它仍不能替代授权暂存后只应用候选补丁的隔离验证。
- 候选现有 38 条路径；补丁、manifest 和路径白名单保存在被忽略的 `.generated/commit-candidates/07-17-llm-wiki-provenance-decision-quality/`。第二套临时索引从补丁重放得到同一 tree，真实 `.git/index` 哈希前后一致。
- 候选隔离副本通过知识链 146、runtime 319、可用决定链 77、渲染 170、Markdown/Bear/入口 80、编排器 2，以及 4 个 Wiki replay 专用用例；候选 lint 为 25 entries、0 errors、37 warnings，Trellis、语法和 JSON/JSONL 检查通过。
- replay 全组的 2 个失败在纯 HEAD 副本完全复现，属于候选外 Tushare/事实库回补基线；`tests/test_position_action_semantics.py` 按第 88 行整体排除。隔离 HTML 需要链接被忽略的只读 ECharts vendor，补齐环境依赖后全组通过。

## 授权后的提交前重核

1. 确认 `HEAD`、上游关系和工作区状态；若基线变化，重新审计受影响块。
2. 按本文件构造选择性暂存，保持其他任务修改在工作区中不动。
3. 检查 `git diff --cached --name-status`、`git diff --cached --stat` 和完整 `git diff --cached`；混合文件必须逐块点验。
4. 运行 `git diff --cached --check`，确认没有冲突标记或行尾空白。
5. 在隔离副本中只应用候选补丁后，重新运行 `implement.md` 的原定验证，证明候选提交本身闭合；当前混合工作区测试不能替代这一步。
6. 只有上述结果全部通过且用户明确授权，才创建提交；任务在此之前保持 `in_progress`。
