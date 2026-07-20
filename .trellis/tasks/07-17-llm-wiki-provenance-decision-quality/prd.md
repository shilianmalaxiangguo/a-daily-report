# LLM Wiki 引用轨迹与决定质量优化

状态：实现、提交前审计与当前 HEAD 隔离复验已完成，等待提交授权

## Goal

把现有 LLM Wiki 从“静态上下文数组 + 关键词命中表”升级为可编译、可追溯、可按交易日复核的知识引用框架。每次日报都要能回答：使用了哪一版知识、由哪些结构化事实触发、引用了哪个来源、知识最多影响哪个解释区，以及为什么它没有临时改写既定交易决定。

## User Story

- **角色**：依赖日报提前决定次日动作、同时持续积累交易经验的个人交易者。
- **场景**：生成 fresh 日报、历史 replay、盘中问股或复盘时，系统会从 Wiki 中命中交易原则并写入报告。
- **目标**：看到知识命中时，可以追到当时知识版本、来源内容和触发事实；知识缺失、过期或只属于后来复盘时，系统明确说明而不是静默套用。
- **成功标准**：改变 Wiki 内容或命中结果，只能改变知识解释与引用轨迹，不得改变同一份市场、账户和候选事实产生的最终对象、明日新仓比例、B1/B2 或退出动作。

### 用户旅程

1. 日报读取目标交易日事实，先完成既有候选、账户和动作判断。
2. Wiki 编译器生成稳定知识快照，检查来源是否存在并计算内容指纹。
3. 路由器只使用白名单结构化事实和受约束的文本触发，选出 1 至 3 条知识。
4. 系统保存 `knowledge_trace.v1`，说明命中版本、来源、触发事实、排序依据和影响边界。
5. fresh 日报在既定动作之后展示短引用；replay 优先使用目标日期已冻结的引用轨迹。
6. 缺少历史知识快照时，报告明确写知识依据不足，不拿今天的 Wiki 冒充当时知识。
7. 复盘只评价当时引用是否适用、是否漏掉反证，不把未来走势写回当时决定。

## What I Already Know

- `scripts/knowledge/llm_wiki_context.py` 当前有 271 条 `FIELD_MAPPINGS`，混合交易规则、输出纪律和流程说明。
- `scripts/knowledge/llm_wiki_router.py` 续跑时的混合工作区有 30 条结构化 `KNOWLEDGE_INDEX` 条目，其中 5 条来自并行业务改动；首版 manifest 必须覆盖提交时实际存在的全部条目，不把数量写死在实现或测试里。
- `build_llm_wiki_context()` 目前只静默过滤不存在的来源文件，没有来源内容指纹、缺失清单、目标日期或历史版本说明。
- `knowledge_hits` 目前只有知识 ID、标题、来源路径、触发词、影响和可信度，缺少 manifest 版本、事实摘要指纹、来源内容指纹和运行日期。
- 当前运行链没有发现 Wiki 命中反向修改 `selection_workflow`、`final_target_resolution`、仓位或 B1/B2，但这个边界主要靠代码位置维持，尚未形成逐字段验收与运行轨迹。
- Karpathy 原始方案强调不可变来源、持久知识编译、`index.md`、追加式 `log.md` 和定期质量检查；`nashsu/llm_wiki` 的来源身份、SHA 缓存和两阶段摄入可借鉴，但它的通用网页研究缺少本仓库要求的交易日隔离。
- 当前工作区有上一任务及研究任务的未提交改动；本任务必须只修改自己明确列出的 Wiki/knowledge/runtime/test 文件，不覆盖或清理其他改动。

## Requirements

- [x] R1: 建立 `knowledge_manifest.v1`。首版以当前全部 `KNOWLEDGE_INDEX` 为唯一结构化知识条目来源，为每条知识生成稳定 `knowledge_id`、`kind`、标题、主题、场景、触发条件、可信度、生命周期、报告位置、影响边界和来源引用；`FIELD_MAPPINGS` 中的全局纪律与流程说明不得自动变成可路由知识。
- [x] R2: manifest 编译必须验证知识 ID 唯一、必填字段完整和来源路径安全；为每个来源保存相对路径、本地路径、存在性、SHA-256 内容指纹和可用的来源日期字段。缺少日期或原文位置时必须显式标记资料不完整，不得伪造。
- [x] R3: `build_llm_wiki_context()` 必须接受目标日期和查询日期，输出 manifest 版本、稳定 manifest 指纹、预期来源、已找到来源、缺失来源、知识可用性和诊断说明，同时保留现有顶层字段，避免破坏旧消费者。
- [x] R4: 建立 `knowledge_trace.v1`。每次 fresh 正式日报路由至少保存目标日期、查询日期、场景、manifest 指纹、结构化事实指纹、命中顺序、得分、触发事实路径、来源引用、知识影响边界、知识引用用途和 trace 指纹；异常 hook 也保留诊断轨迹，replay 原样复用目标日冻结轨迹或生成缺失占位轨迹；不带 trace 的旧列表 helper 不得进入这些正式链路。
- [x] R5: 正式路由必须优先使用结构化字段条件；文本触发只负责召回候选知识。`knowledge_hit_facts` 旁路必须经过白名单和来源说明，不允许任意字典无说明地替换事实，也不得因为否定文本、字段名或无关说明出现关键词就形成命中。旧列表 helper 只读取已登记事实根和字符串 `question`，未知根不得参与文本命中。
- [x] R6: 日报运行产物必须同时保存兼容的 `knowledge_hits` 和完整 `knowledge_trace.v1`。Markdown/Bear HTML 继续只展示简短知识引用，完整轨迹留在结构化产物和诊断中；知识引用出现在明日执行结论、账户动作、执行条件和不执行条件之后。
- [x] R7: fresh 运行使用当次编译的 manifest；replay 优先使用与目标日期一致的已冻结知识轨迹。若历史快照不存在，不得把当前 Wiki 伪装成历史依据；允许以明确标注的“当前复盘视角”单独展示，但不得写入当时知识命中或改变当时决定。
- [x] R8: 缺少来源、manifest 内容变化、历史知识轨迹缺失或引用来源不完整时，hook/runtime 必须输出可追溯诊断并降低知识可用性；不得继续给 `confidence=1.0` 且空 warnings。
- [x] R9: 同一份市场、账户、候选和交易日期事实下，改变 manifest 版本、命中条目、知识正文或知识缺失情况，`selection_workflow`、`final_target_resolution`、明日执行对象、明日新仓比例、B1/B2、旧仓处理和退出动作必须逐字段一致。
- [x] R10: 新增 `wiki/index.md` 与 `wiki/log.md`。index 作为人的知识导航入口，至少覆盖现有 Wiki 分区和首版全部运行知识来源；log 使用可解析日期前缀追加记录 ingest/query/lint/contract 变化，不记录当天行情或可由代码重算的事实。
- [x] R11: 新增 Wiki lint/validation 检查，至少发现重复知识 ID、来源缺失、断链、manifest 必填字段缺失、生命周期非法、影响边界缺失和可路由知识没有来源指纹；检查只读 Wiki，不自动改写知识正文。
- [x] R12: 保留现有 `knowledge_hits`、`source_paths`、`field_mappings`、报告短表和公开调用签名的兼容行为；旧列表 helper 保留已登记事实根与自由文本 `question` 查询，忽略未知顶层根。本任务不要求一次性把 40 篇 Wiki 全部改成 frontmatter，也不删除现有 FIELD_MAPPINGS。

## Non-functional Requirements

### 可复现性

- 同一份 Wiki 文件字节、manifest 条目和目标日期必须生成相同 manifest 指纹、事实指纹和 trace 指纹。
- 指纹使用稳定 JSON 序列化，不包含当前时间、绝对工作区路径或非确定性排序。

### 日期隔离

- fresh/replay 引用必须保留 `target_date`、`query_date`、可用的 `source_date` / `capture_date`。
- 后来整理的知识不得被描述成目标日期已经存在的知识。

### 安全与可靠性

- manifest 中的来源必须位于仓库 `wiki/` 范围内，拒绝路径穿越。
- 缺失或损坏的知识来源不能静默通过。
- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。

### 性能

- 首版只处理本地 Markdown 和当前全部结构化知识，单次 manifest 编译不引入网络、向量模型或外部服务。
- 同一运行内复用已构建 manifest，避免对同一来源重复读取和重复计算指纹。

## Source Of Truth

- 交易事实、账户事实、候选与动作仍以现有日报结构化数据、`decision-ledger` 和目标日期快照为准。
- Wiki 正文与 `knowledge_manifest.v1` 只提供稳定交易原则、引用解释、反证和复盘校准，不替代实时事实。
- 首版结构化知识条目以运行时全部 `KNOWLEDGE_INDEX` 为准；本轮混合工作区基线为 30 条，选择性候选排除 5 条并行业务知识后按提交时的实际条目数编译。271 条 `FIELD_MAPPINGS` 继续作为兼容上下文，只有经过独立 ID、来源和影响边界登记后才能进入 manifest。
- 如来源正文、manifest 和运行代码冲突，停止生成该条知识命中并报告差异，不静默选择其中一份。

## Domain Contract

### `knowledge_manifest.v1`

最小字段：

- `schema_version`
- `wiki_version`
- `language`
- `manifest_hash`
- `entries[]`
- `expected_source_paths[]`
- `available_source_paths[]`
- `missing_source_paths[]`
- `availability`
- `warnings[]`

每个 `entries[]` 至少包含：

- `knowledge_id`
- `kind`
- `title`
- `prior`
- `topics[]`
- `applies_to[]`
- `trigger_terms[]`
- `fact_conditions[]`
- `confidence`
- `lifecycle`
- `report_slots[]`
- `decision_effect`
- `decision_scope`
- `source_ref.path`
- `source_ref.local_path`
- `source_ref.content_hash`
- `source_ref.availability`
- 可用时的 `source_ref.source_date`、`capture_date`、`anchor`

### `knowledge_trace.v1`

最小字段：

- `schema_version`
- `target_date`
- `query_date`
- `scenario`
- `manifest_hash`
- `facts_hash`
- `facts_source`
- `fact_sources{}`，每个事实叶子保存规范化的 `source` 与 `input_path`
- `trace_hash`
- `availability`
- `warnings[]`
- `hits[]`

每个 `hits[]` 保留旧 hit 字段，并增加：

- `rank`
- `score`
- `matched_fact_paths[]`
- `matched_fact_sources[]`，逐项对应 `matched_fact_paths[]`
- `source_ref`
- `decision_effect`
- `decision_scope`
- `used_for[]`
- `not_used_for[]`

## Error Handling Strategy

| 场景 | 处理方式 | 用户可见结果 |
|------|----------|--------------|
| manifest 条目非法 | 拒绝该 manifest，诊断列出知识 ID 与原因 | 关键知识资料不完整，停止生成知识命中 |
| 来源文件缺失 | 保留缺失路径，相关条目不可命中 | 经验库来源不完整，不展示对应引用 |
| 历史 replay 无冻结轨迹 | 不把当前命中写成当时依据 | 当时知识引用缺失；当前复盘视角单独说明 |
| 来源内容指纹变化 | 重新编译 fresh；replay 保留旧轨迹并说明差异 | 引用版本发生变化，需要按来源复核 |
| 文本触发与结构化事实冲突 | 结构化事实优先，文本候选不成立 | 不展示误命中 |
| 知识调用尝试改变既定决定字段 | 运行检查报告不一致并停止输出该次知识解释 | 知识引用与既定决定不一致，停止生成知识解释 |

## Acceptance Criteria

- [x] AC-R1-1: 给定当前 `KNOWLEDGE_INDEX`，编译后 manifest 条目数与其完全一致、`knowledge_id` 全部唯一，且每条 `kind=knowledge_rule`；混合工作区续跑时为 30 条，测试不固定提交后的最低数量。
- [x] AC-R1-2: 给定只属于输出纪律或流程说明的 `FIELD_MAPPINGS`，它们不会因字符串相似自动成为 manifest entry。
- [x] AC-R2-1: 给定存在的来源文件，manifest 保存稳定 SHA-256；修改临时来源文件一个字节后，来源指纹与 manifest 指纹同时变化。
- [x] AC-R2-2: 给定来源缺失或路径越过 `wiki/`，编译结果明确记录缺失/拒绝原因，不生成对应可用知识条目。
- [x] AC-R3-1: 连续两次以相同目标日期构建 context，manifest 指纹完全一致，且旧 `source_paths`、`field_mappings` 仍可读取。
- [x] AC-R4-1: 给定结构化市场事实，trace 包含稳定 `facts_hash`、manifest 指纹、命中得分、事实路径、来源指纹和 trace 指纹。
- [x] AC-R4-2: 相同事实与 manifest 重复路由，命中顺序和 trace 指纹一致；事实或 manifest 改变时对应指纹变化。
- [x] AC-R5-1: 给定含冲突文本的结构化事实，结构化条件优先，不因无关字段名、否定说明或弱触发词形成额外命中；旧列表 helper 中只有未知根的文本返回空列表，未知根也不能给已登记事实补出额外命中。
- [x] AC-R5-2: 给定 `knowledge_hit_facts`，只有白名单字段进入路由，trace 记录其来源为显式结构化输入；未知字段被拒绝并进入 warnings。
- [x] AC-R6-1: fresh 日报结构化产物同时含兼容 `knowledge_hits` 和 `knowledge_trace.v1`，报告短表中的每条引用都能在 trace 中找到同一 `knowledge_id`。
- [x] AC-R6-2: 完整版、摘要版和正式落盘的 Bear HTML 均先出现明日执行结论、账户动作、执行条件与不执行条件，再出现知识引用或研究证据。
- [x] AC-R7-1: replay 有目标日期冻结轨迹时原样使用其 manifest/trace 指纹；没有时不生成伪历史命中。
- [x] AC-R8-1: 删除一个临时 Wiki 来源后，hook/runtime 的 `availability`、warnings 和 confidence 同步降级，不再返回无 warning 的满置信说明。
- [x] AC-R9-1: 对同一输入分别注入两份不同 manifest，并真实修改临时 Wiki 来源字节后重新编译来源与 manifest，逐字段比较 `selection_workflow`、`final_target_resolution`、执行对象、新仓比例、B1/B2、旧仓处理和退出动作，结果完全一致。
- [x] AC-R9-2: `knowledge_trace` 明确 `decision_scope=explanation_only`，并列出不得影响的决定字段。
- [x] AC-R10-1: `wiki/index.md` 能导航到现有分区和首版运行知识来源；`wiki/log.md` 至少记录本任务的 contract/lint 操作，格式可由简单文本命令解析。
- [x] AC-R11-1: Wiki lint 对重复 ID、缺源、断链、非法 lifecycle、缺 decision_scope 分别有稳定测试。
- [x] AC-R12-1: 现有 context/router/report 测试除口径已变更的陈旧断言外保持通过；旧消费者无需迁移即可读取原字段。

## Definition Of Done

- [x] Requirements 实现全部完成
- [x] Acceptance Criteria 已通过补充修正后的全量重新验证
- [x] `design.md` / `implement.md` 已补齐并通过 review
- [x] 外部方案与当前实现审计已保存到 `research/`
- [x] `implement.jsonl` / `check.jsonl` 已配置真实 spec / research 清单
- [x] 本任务直接单测与 Wiki lint 已通过；三个全组的候选外异常已在纯当前 HEAD 逐项复现并记录
- [x] fresh/replay 的知识引用和决定隔离已有定向结构化证据
- [x] 本轮未执行回滚、清理或格式化动作，现有其他未提交修改全部保留
- [x] 混合工作区的选择性提交范围证据已保存到 `commit-scope.md`；当前 HEAD 候选已重建并隔离复验
- [ ] task metadata 保持 `in_progress`；获得提交授权并完成提交后再收尾

## Completion Evidence

2026-07-18 当前 HEAD 提交候选证据：

- `HEAD` 与 `origin/develop` 同为 `c0e7dddd085815da28ec8cd7cbe13fb0ecb1ebcc`。旧候选到当前 HEAD 的 5 个提交没有改变候选代码路径；本任务文档在历史中被误加后完整撤回，当前按范围重新加入。
- 最终候选为 39 条路径；补丁由第二套临时索引从当前 HEAD 重放为同一 tree，真实暂存区已精确替换为该候选，其余工作区修改未纳入。
- 隔离副本通过知识链 148、可用决定链 77、渲染 171、编排器 2、报告短引用 10，以及 5 个 Wiki replay 专用用例。
- runtime 全组 319 项有 1 项基线错误：`test_sector_capital_carrier_limit_down_without_reversal_plan_stays_zero`。
- Markdown/Bear/入口全组 83 项有 7 项基线错误：`test_bear_html_render_failure_stops_before_postgres_and_artifact_writes`、`test_chart_html_fact_missing_still_saves_bear_html`、`test_main_entry_uses_markdown_reader_html_not_structured_dashboard_html`、`test_main_saves_sector_capital_preflight_after_markdown`、`test_missing_chart_mainline_context_still_saves_bear_html_only`、`test_postgres_only_validates_bear_html_before_postgres_fact_sync`、`test_runtime_artifact_failure_does_not_prevent_markdown_save`。
- replay 全组 66 项有 2 项基线失败：`test_build_replay_snapshot_contract_restores_critical_tushare_facts_from_fact_db`、`test_build_replay_snapshot_contract_restores_wind_a_from_tushare`。
- 上述 10 项在纯当前 HEAD 副本以相同测试 ID 和错误内容逐项复现；它们分别属于候选外持仓载体、PostgreSQL 前日报计划与 Tushare/事实库修正，不扩大本候选处理。
- 候选 Wiki lint 为 25 entries、0 errors、37 条来源元数据提醒；Trellis validate、相关 Python 语法、JSON/JSONL 与候选补丁检查均通过。
- 2026-07-17 混合工作区的 924 项全绿与编排器 2 项结果已经被本轮当前 HEAD 隔离复验替代，不作为当前提交候选的通过依据。
- 短引用继续只展示词语召回结果；结构化确认单独保存在 `matched_conditions`、`matched_fact_paths`、`matched_fact_sources` 与 trace 中。
- 首轮提交前独立审计发现两项缺口：非空但非法的日期仍可能产生命中，legacy body 仍有提前/重复附加 Wiki 的路径。现已改为严格校验规范 `YYYY-MM-DD` 日历日期，并删除 legacy body 的三处刷新，只保留正式决定完成后的单次附加。
- 上述两项先由新增回归复现失败，修正后定向测试通过；随后六组回归与编排器测试全部重新运行并通过。
- 第二轮提交前独立审计发现冻结轨迹完整性检查只验证日期非空和目标日相等，自洽重算指纹后仍会接受不存在的日历日期。现已对调用参数、context 与 trace 的目标日和查询日再次执行规范日期校验，并要求 context/trace 日期逐字段一致；快照入口和 replay 回归均覆盖该缺口。
- 第二轮审计同时复核首屏引用：正式 runtime 按设计不把 Wiki 传入旧报告主体，只在正式动作完成后追加引用表；组件显式传入命中时的展示兼容行为不变。对应 runtime 测试已明确验证动作早于引用。
- 第三轮完成性审计发现：11 个 expected-only 来源缺少元数据状态与提醒，context 顶层未直接暴露已找到来源，fresh/runtime/replay 的数值置信度没有统一同步。现已为所有 `manifest.sources[]` 固定 `metadata_status/missing_metadata`，新增顶层 `available_source_paths`，并由公共 availability 映射同步 context、hook、runtime 与 replay 的 confidence。
- 最终提交前审计继续发现：entry 引用可与全局来源索引的元数据分叉，异常 hook 返回可留下满置信空提醒，来源变化后的 replay 外层无法再次作为冻结依据复用。现已增加逐字段来源一致性、异常 hook 降级、`frozen_confidence` 与重复 replay 回归。
- 本次续跑提交前审计又发现：非 Mapping 直接进入公共 validator/router、Mapping 清单的其他列表字段和 `kind` / `lifecycle` 类型异常仍可能中断校验，hook 外层提醒字段异常也会中断，清单自报 invalid 且未附原因时会留下空提醒。现已用 validator、router、hook 三层失败回归分别复现，并改为保留字段类型诊断、空命中、0.0 置信度和稳定原因提醒。
- 本轮六路提交前审计继续发现：context 直接展开畸形清单列表字段会异常，公共 trace 路由会读取非 Mapping facts 的 `.items()`，外部清单可用父路径放宽结构化条件，零命中 trace 缺少顶层解释边界。现已先用失败回归复现，再由 manifest/router 共用精确事实路径、context 安全列表读取和 trace 顶层边界完成最小修正；最终补丁复核进一步把同一精确路径检查覆盖到 `prefer_any`。冻结完整性同步拒绝缺边界的自洽轨迹。
- lint 对原始 legacy 条目缺少 `decision_scope` 的质疑经点验后保留兼容默认值，因为 R1 要求编译器为当前条目生成 `explanation_only`；另加回归证明编译后 manifest 真正丢失该字段时 lint 会稳定检出。
- 2026-07-17 混合工作区的六组 924 项与编排器 2 项曾使用 `.generated/venv-py314/bin/python3.14` 运行并全绿；该结果只保留为历史集成证据。
- `commit-scope.md` 已以当前 `HEAD=c0e7dddd085815da28ec8cd7cbe13fb0ecb1ebcc` 为基线，记录整文件候选、混合文件符号块、明确排除项、动态来源指纹影响和提交前重核步骤。
- 本轮范围审计进一步发现：专用 manifest 测试把混合工作区的 30 条写成最低数量，且另一个 Bear HTML 流程用例也需要 fresh Wiki fixture。现已改为逐条覆盖提交时实际 `KNOWLEDGE_INDEX`，并补齐该用例的选择块；排除 5 条并行业务知识后的 25 条候选定向编译为 25 条 manifest、0 errors，随后原定七组单测重新通过。
- 本轮提交前审计继续补齐四类证据：旧列表 helper 只读取登记事实根和字符串问题；异常 hook 仍保存完整稳定 trace；R9 用固定的非空正式决定样本真实改写临时 Wiki A/B 字节、拒绝清单与来源字节失配并逐字段比较，另由 legacy-body 隔离回归证明真实决定主体看不到 Wiki；正式 HTML 入口读取最终落盘文件验证动作早于经验引用。混合工作区 replay 64 项曾全绿；当前候选与纯 HEAD 的两个回补基线失败另行保留，不改动无关 replay 业务逻辑。
- 选择性候选现有 39 条路径；`candidate.patch`、`candidate-manifest.json` 和 `candidate-paths.txt` 保存在被 Git 忽略的 `.generated/commit-candidates/07-17-llm-wiki-provenance-decision-quality/`。构造过程使用临时索引与临时对象库，补丁再由第二套临时索引从 HEAD 重放，两次 tree 完全一致，真实暂存区哈希未变化。
- 候选隔离副本的本任务直接测试全部通过；runtime、Markdown/Bear/入口与 replay 全组保留上列 10 个纯 HEAD 同现异常。候选 Wiki lint 为 25 entries、0 errors、37 条来源元数据提醒；Trellis validate、Python 语法、JSON/JSONL 和候选 diff 检查通过。
- `tests/test_position_action_semantics.py` 按范围契约整体排除，因此隔离副本只运行同组内已提交的两个决定链模块，共 77 项全绿。
- 隔离副本链接原仓库被忽略的只读 ECharts vendor；本轮没有依赖缺失错误，软链接不改变候选 tree。
- 最终暂存审计发现 fresh Wiki 完整性检查仍可能晚于 PostgreSQL、运行期产物或报告写入；`test_incomplete_fresh_wiki_trace_stops_before_any_persistence` 先复现失败，修正后确认资料不完整时所有持久化动作均未发生。
- 同轮审计发现 replay 缺历史 Wiki 轨迹时的 `query_date` 取决于宿主本地日期；`test_missing_historical_wiki_trace_uses_shanghai_query_date` 先复现失败，修正后统一使用 `Asia/Shanghai` 日期。
- 提前完整性检查使原有 PostgreSQL 同步失败用例暴露陈旧夹具；该用例现提供目标日完整 Wiki 上下文，在工作区和隔离候选单例均通过。HTML/Bear/入口 81 项只保留 7 个纯 HEAD 同现错误，没有新增失败。
- 后续持久化复核又发现两项边界：冻结轨迹自洽并不足以证明 fresh 来源字节仍匹配，且入口抛错后的 `finally` 仍会写质量记录。现已增加 fresh 来源字节校验，正式日报资料不完整时质量记录也不写；`--no-report` 不生成 Wiki trace，继续按既有数据采集、PostgreSQL 同步和质量记录契约运行。更新后的入口/Bear 全组为 82 项，仍只保留同一 7 个纯 HEAD 异常。
- 本轮六路只读审计发现：Wiki 来源核对本身异常时质量记录仍可能写入，公共 replay helper 空查询日没有自行使用上海日期，sections facade 会绕过冻结轨迹读取当前 Wiki。三个失败回归先复现后完成最小修正；R9 审计同时把“固定正式决定样本 + 主体看不到 Wiki”的两段证据写清，不再描述成未执行的全链路 A/B。

2026-07-17 修正前历史证据（已被后续 924 项混合工作区验证和 2026-07-18 当前 HEAD 隔离复验替代，不作为当前提交依据）：

- 知识链、hook、快照入口与 lint 回归：137 tests OK。
- 日报 runtime：332 tests OK。
- 决定隔离：99 tests OK。
- 完整版/摘要版 front-page 与渲染：175 tests OK。
- Markdown、Bear HTML 与输出入口：95 tests OK。
- replay：64 tests OK，冻结轨迹完整性、目标日期一致性和缺失降级均有回归覆盖。
- Wiki lint：30 entries、0 errors；30 条来源元数据提醒保留，未伪造 `source_date`、`capture_date` 或 `anchor`。
- 提交前独立审计已完成一轮；公共 trace 入口事实路径绕过、事实来源伪造、列表事实父路径、缺失历史引用结构、fresh 快照完整性与目标日期、普通快照边界、研究证据前置、lint 影响边界与来源指纹覆盖均已修正并回归。
- 六组相关回归合计 902 tests OK；计数包含知识/快照 137、runtime 332、replay 64、决定隔离 99、front-page/render 175、Markdown/Bear/入口 95。另有编排器 2 tests OK，不重复计入六组总数。
- 当前工作区混有其他任务修改；上述计数来自 2026-07-17 当前工作区的独立 Python 3.14 命令，不把全局范围隔离写成已证明。

## Final Acceptance Matrix

| Requirement | 实现证据 | 验证证据 |
|-------------|----------|----------|
| R1 | `build_knowledge_manifest()` 只从 `KNOWLEDGE_INDEX` 编译运行条目，保留 `FIELD_MAPPINGS` 兼容层 | `test_compiles_every_current_structured_knowledge_entry`、`test_field_mappings_remain_compatibility_context_not_manifest_entries` |
| R2 | manifest 读取真实 Wiki 字节，校验路径范围、来源存在性、SHA-256 与声明一致性；所有来源含明确元数据状态，expected-only 来源缺少日期或原文位置时生成稳定提醒，entry 引用与全局来源索引逐字段一致 | `tests.test_llm_wiki_manifest` 的字节变化、元数据完整/缺失、expected-only 来源、entry/source 分叉、缺源、越界与伪造 hash 用例 |
| R3 | `build_llm_wiki_context()` 增加日期、manifest、预期/已找到/缺失来源、可用性、数值置信度和 warnings，畸形列表字段安全降级，旧字段不变 | `test_context_keeps_target_dates_and_stable_manifest_without_breaking_legacy_fields`、`test_context_reports_malformed_manifest_list_fields_without_raising` |
| R4 | trace 保存稳定 manifest/facts/trace 指纹、日期、全局事实来源、逐命中事实来源、排序和知识来源；日期缺失、格式非法或日历日期不存在时仅返回不可用诊断轨迹，冻结时再次核对 context/trace 日期；fresh/replay/hook/runtime 不调用旧列表 helper | `test_trace_is_stable_and_links_rank_score_fact_paths_and_source_hash`、`test_trace_requires_target_and_query_dates_before_hits_are_usable`、`test_fresh_trace_normalizes_list_fact_sources_and_remains_replay_safe`、`test_frozen_trace_completeness_rejects_noncanonical_dates_even_with_valid_hash`、`test_frozen_trace_completeness_rejects_context_trace_query_date_mismatch` |
| R5 | 全部运行知识声明非空 `must_any`，`must_any` / `prefer_any` 的条件路径都必须精确命中白名单叶子；trace 先按词语召回候选，再按结构化事实确认，非 Mapping facts 稳定返回空命中诊断，路由器重建规范来源映射；旧列表 helper 保留已登记根和 `question`，未知根不参与排序 | `test_manifest_rejects_routable_entry_without_structured_confirmation`、`test_manifest_rejects_structured_condition_outside_fact_path_allowlist`、`test_manifest_rejects_preferred_condition_outside_fact_path_allowlist`、`test_trace_reports_non_mapping_facts_without_raising`、`test_trace_rejects_manifest_condition_outside_fact_path_allowlist`、`test_trace_uses_text_only_for_recall_and_structured_path_for_confirmation`、`test_legacy_list_router_ignores_unregistered_fact_roots`、`test_trace_replaces_unverified_fact_source_with_canonical_origin` |
| R6 | runtime 同时保存兼容 hits 与完整 trace；full/summary 共用一次编译；sections 只消费显式上下文；Bear 按 Markdown 保序并区分动作/证据，正式写出的 HTML 直接复核同一顺序 | `test_build_report_outputs_reuses_one_wiki_compile_and_keeps_evidence_after_actions`、`test_generate_markdown_report_from_sections_keeps_expected_order`、`test_runtime_routes_account_knowledge_after_formal_action`、`test_render_marks_action_and_evidence_sections_for_bear_reader`、`test_saved_markdown_html_sync_overwrites_existing_reader_html` |
| R7 | 正式入口和快照编排入口均在 fresh 保存前检查完整轨迹与非空目标日期；检查异常也不写质量记录；普通快照不因其他知识对象改变结构；replay 只复用目标日完整冻结轨迹，公共 helper 自行使用上海查询日，sections 不读取当前 Wiki | `test_normal_path_freezes_rendered_wiki_trace_after_report_outputs_succeed`、`test_fresh_wiki_check_error_stops_before_quality_persistence`、`test_snapshot_persistence_hook_rejects_incomplete_llm_wiki_trace`、`test_snapshot_persistence_hook_rejects_self_hashed_impossible_query_date`、`test_snapshot_persistence_hook_rejects_llm_wiki_without_target_date`、`test_snapshot_persistence_hook_keeps_non_wiki_payload_unchanged`、`test_build_replay_snapshot_contract_reuses_target_date_frozen_wiki_trace`、`test_build_replay_snapshot_contract_rejects_frozen_wiki_trace_from_another_date`、`test_build_replay_snapshot_contract_marks_missing_historical_wiki_trace`、`test_missing_replay_trace_defaults_query_date_to_shanghai_calendar`、`test_generate_markdown_report_replay_sections_do_not_read_current_wiki` |
| R8 | context/hook/runtime 共享 trace 的真实来源诊断与数值置信度；缺日期/缺源/缺 manifest/清单内部类型异常/缺历史轨迹时同步降低；replay 当前来源变化时冻结 manifest/trace/hits 不变，以独立字段保留冻结可信度并允许重复 replay | `test_validation_reports_malformed_internal_field_types_without_raising`、`test_trace_reports_malformed_or_declared_invalid_manifest`、`test_hook_rejects_ready_snapshot_without_a_manifest`、`test_hook_rejects_malformed_context_warnings_without_raising`、`test_runtime_syncs_trace_diagnostics_and_confidence`、`test_replay_rejects_incomplete_self_hashed_trace`、`test_replay_keeps_frozen_trace_and_reports_current_source_change` |
| R9 | 旧报告主体在正式决定完成前看不到 Wiki；知识附加前后保存完整正式决定投影；版本、真实来源正文 A/B 字节、命中和知识缺失四类变化均逐字段比较；零命中 trace 仍保存顶层解释边界 | `test_real_runtime_keeps_formal_decision_identical_with_market_language_artifact`、`test_legacy_report_body_cannot_read_wiki_before_formal_decisions_finish`、`test_trace_keeps_decision_boundary_when_no_entries_match`、`test_fresh_trace_completeness_check_rejects_partial_context` |
| R10 | `wiki/index.md` 覆盖全部运行来源，`wiki/log.md` 使用可解析的追加记录格式 | `test_current_wiki_has_no_lint_errors_and_covers_all_runtime_entries`、`test_lint_is_deterministic_and_read_only`、`test_lint_rejects_impossible_log_date` |
| R11 | 只读 lint 检查 manifest、来源指纹、导航断链、生命周期、影响边界和日志格式 | `tests.test_llm_wiki_lint` 8 组用例及 CLI lint；包含 `test_lint_reports_decision_scope_removed_from_compiled_manifest` |
| R12 | 旧 context 字段、旧 route 返回值、已登记事实根与 `question` 查询、`knowledge_hits` 和报告短表继续可用；未知顶层根被忽略 | 知识链/hook/lint 回归及现有 runtime/render 测试集合 |

## Out Of Scope

- 不迁移到 `nashsu/llm_wiki` 桌面应用。
- 不引入向量数据库、embedding、外部搜索服务、MCP 服务或新依赖。
- 不批量重写全部 40 篇 Wiki，不强制一次性补齐所有 frontmatter。
- 不让 Wiki 命中直接生成候选、最终对象、仓位、B1/B2、买卖点或退出动作。
- 不修改候选池、评分、选股、市场语言研究公式或一分钟曲线结论。
- 不用当前实时数据或当前 Wiki 命中回补历史交易日事实。
- 不自动把 AI 推断、当天行情或无来源问答写成正式交易知识。
- 不删除、清理、格式化或提交当前工作区的其他未提交改动。

## Technical Notes

### 参考来源

- `wiki/运行契约/LLM Wiki维护与路由契约.md`
- `wiki/交易思想/日报术语契约.md`
- `docs/trellis/specs/2026-05-29-daily-report-knowledge-agent-design.md`
- `.trellis/spec/backend/daily-report-decision-loop.md`
- `.trellis/spec/backend/llm-wiki-provenance.md`
- `.trellis/tasks/07-12-market-language-daily-report-wiki/`
- `.trellis/tasks/07-13-daily-report-index-cross-validation/`
- `.trellis/tasks/07-14-daily-position-action-semantics/`
- `https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f`
- `https://github.com/nashsu/llm_wiki`

### 影响区域

- `scripts/knowledge/` — manifest、context、router、lint 与 trace。
- `scripts/hooks/knowledge/use_llm_wiki.py` — target date 与诊断。
- `scripts/report/runtime.py` — trace 接入、兼容 hits 和决定隔离。
- `scripts/hooks/report/use_report_sections.py` — 短引用与来源展示。
- `scripts/replay/report_replay.py` / snapshot 相关模块 — 冻结轨迹与历史隔离。
- `wiki/index.md` / `wiki/log.md` — 人类导航和知识操作记录。
- `tests/test_llm_wiki_*.py`、runtime/replay/report tests — 契约验收。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_manifest tests.test_llm_wiki_context tests.test_llm_wiki_router tests.test_llm_wiki_hook tests.test_llm_wiki_lint tests.test_use_snapshot_persistence`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_replay`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow tests.test_two_layer_decision_payload tests.test_position_action_semantics`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer tests.test_daily_report_render`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_html_output tests.test_daily_report_markdown_html`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_orchestrator`
- `.generated/venv-py314/bin/python3.14 scripts/knowledge/llm_wiki_lint.py`
- `.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py validate 07-17-llm-wiki-provenance-decision-quality`
- `git diff --check`
- 比较两份不同 Wiki manifest 下的正式决定字段指纹与逐字段 payload。
- 检查 `git diff --name-only`，确认本任务未改候选、研究公式或无关历史产物。

## 落地 commit

待提交。本轮未获得提交授权，代码与验证已完成后保持未提交状态。
