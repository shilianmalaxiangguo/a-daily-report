# Design: LLM Wiki 引用轨迹与决定质量优化

## Scope And Boundaries

本设计把 LLM Wiki 分成四个明确层次：

1. `wiki/` 正文：人可读的稳定交易知识、反证、来源和运行契约。
2. `knowledge_manifest.v1`：由现有结构化知识条目和 Wiki 文件编译出的运行清单。
3. `knowledge_trace.v1`：某个目标日期、某组事实和某版 manifest 的一次可复核命中记录。
4. 日报决定链：继续只由市场、板块、候选、账户、时间窗口和既有决策契约产生正式动作。

Wiki 只向报告解释区和复盘提供知识引用。它不作为候选、评分、最终对象、仓位、B1/B2 或退出动作的输入。若未来某条经验要改变正式动作，应先单独进入业务契约、确定性实现和回归测试，不在本任务中打通这种反向路径。

## Architecture

```text
wiki markdown + KNOWLEDGE_INDEX
  -> manifest compiler
     -> source validation + SHA-256
     -> knowledge_manifest.v1 + manifest_hash
        -> structured fact extraction
        -> explainable router
           -> knowledge_trace.v1 + trace_hash
              -> data.knowledge.llm_wiki
              -> artifacts.llm_wiki
              -> short report citation

formal report facts
  -> existing selection / account / action chain
  -> formal decision payload

knowledge_trace ── explanation only ──> report/review
```

## Contracts / Data Flow

### 1. Manifest Compiler

新增 `scripts/knowledge/llm_wiki_manifest.py`，职责只包括：

- 稳定 JSON 序列化和 SHA-256。
- 验证来源路径必须位于 `wiki/`。
- 读取来源字节并生成内容指纹。
- 把 `KNOWLEDGE_INDEX` 的旧字段规范化为 `knowledge_manifest.v1`。
- 检查唯一 ID、必填字段、生命周期、影响边界和来源可用性。
- 输出 warnings，不修改 Wiki 文件。

首版不搬迁当前全部结构化条目（混合工作区续跑时 30 条，提交时按实际条目数编译），避免在已有脏文件上做高风险机械移动。`KNOWLEDGE_INDEX` 仍是条目声明的唯一来源；manifest compiler 是唯一运行编译入口。`FIELD_MAPPINGS`、全局纪律和流程数组保持兼容，但不参与 manifest 条目生成。

稳定指纹不包含：

- 当前时间。
- 绝对仓库路径。
- 文件 mtime。
- 非确定性集合顺序。

### 2. Context Builder

`build_llm_wiki_context()` 扩展为关键字参数：

```python
build_llm_wiki_context(
    *,
    target_date: str = "",
    query_date: str = "",
    manifest: dict | None = None,
) -> dict
```

保留旧字段，并新增：

- `target_date`
- `query_date`
- `manifest`
- `manifest_hash`
- `expected_source_paths`
- `available_source_paths`
- `missing_source_paths`
- `availability`
- `confidence`
- `warnings`

来源缺失时不再静默消失。兼容 `source_paths` 仍只列出存在文件，但消费者可以通过 expected/missing 对比理解缺口。
`available_source_paths` 直接承接 manifest 的已找到来源；`confidence` 由同一套 availability 映射生成，供直接 context、hook、runtime 和 replay 共用。

### 3. Structured Fact Input

自动事实提取保持现有逻辑，但显式 `knowledge_hit_facts` 经过递归白名单：

- 顶层只允许 `market`、`account`、`candidate`、`position`、`decision`、`capital_priority`。
- 每个顶层对象只保留登记过的内层事实路径；公共 trace 入口也会再次执行同一套过滤，不能绕过显式输入入口注入未知路径。
- 只保留 JSON 基本类型、字典和列表。
- 未知顶层字段进入 trace warnings，不参与路由。
- trace 记录 `facts_source=explicit` 或 `derived`，并为每个事实叶子保存规范化的 `fact_sources[path].source/input_path`。
- 调用方传入的 `fact_sources` 只用于一致性核对；来源或输入路径不匹配时写 warning，并由路由器按事实类型重建规范来源，不能由调用方伪造。

首版不试图理解任意中文否定句。降低误命中的方法是：

- 每条可路由知识都必须声明非空 `fact_conditions.must_any`。
- trace 先用 `trigger_terms` 召回候选，再由 `must_any` 结构化条件确认最终命中；同一词出现在无关事实路径时不成立。
- `fact_conditions` 得分高于文本触发。
- `weak_trigger_terms` 没有结构化条件时不能单独成立。
- 路由只扁平化白名单事实，不扫描整份日报正文。
- 增加已知否定和无关字段测试。

### 4. Router And Trace

新增：

```python
route_llm_wiki_knowledge_trace(
    facts,
    *,
    manifest,
    scenario="daily_report",
    limit=3,
    target_date="",
    query_date="",
    facts_source="derived",
    fact_sources=None,
    warnings=None,
    source_root=None,
) -> dict
```

旧 `route_llm_wiki_knowledge()` 继续返回 hits 列表并保留原签名。它只读取六个已登记事实根和字符串 `question`，未知顶层根在排序前被忽略；这个 helper 只用于旧问答兼容，不生成 trace，也不得进入 fresh、replay、hook 或正式日报 runtime。fresh 与 hook 调用 `route_llm_wiki_knowledge_trace()`；replay 只复用目标日冻结 trace，缺失时由 replay builder 生成诊断占位，不重新路由当前 Wiki。

trace 的 `target_date` 和 `query_date` 都必须是规范的 `YYYY-MM-DD` 日历日期。任一缺失、格式非法或日期不存在时只返回 `availability=invalid` 的诊断轨迹和稳定 warnings，不返回可用命中；旧列表 helper 不增加日期参数，因此只能留在非正式兼容查询中。

排序沿用现有规则：结构化条件每项 2 分、文本触发每项 1 分、声明顺序作为稳定次序。trace 显式保存 score/rank、全局 `fact_sources`，以及每个 hit 与 `matched_fact_paths` 一一对应的 `matched_fact_sources`，避免只看到结果看不到为什么排在前面或事实来自哪里。

`trace_hash` 对移除自身 `trace_hash` 后的完整 trace 做稳定哈希。`hit_id` 仍按排序生成 `kh-001`，不作为跨运行永久身份；永久身份只认 `knowledge_id`。

### 5. Runtime Integration

`render_markdown_report_runtime()` 只构建一次 context/manifest，并把 `target_date` 传入。legacy body 运行期间不读取、不刷新 Wiki；wrapper 等正式决定全部落定后只附加一次。`_attach_llm_wiki_knowledge_hits()`：

1. 提取结构化事实。
2. 生成 trace。
3. 把 `trace["hits"]` 同时写到兼容 `knowledge_hits`。
4. 把完整 trace 写到 `knowledge_trace`。
5. 保存到 `data["knowledge"]["llm_wiki"]` 和返回 artifacts。

知识附加前后，对正式决定字段做稳定投影与指纹比较。首版投影包含存在的：

- `selection_workflow`
- `final_target_resolution`
- `front_decision`
- `two_layer_decision_payload`
- `position_decision`
- `planned_participation`
- `old_position_plan`

若投影变化，知识解释停止生成并写诊断；不尝试自动修复正式决定。

### 6. Hook Diagnostics

`use_llm_wiki.run(ctx)` 从 `ctx` 的 request/data 中提取目标日期；提取不到时保持空值但写 warning。confidence 由 availability 派生：

- `ready`：来源齐全。
- `partial`：来源元数据不完整但文件存在。
- `missing_sources`：至少一个必需来源缺失，不生成相关命中。
- `invalid`：日期或 manifest 不完整，不生成知识命中，confidence 为 0。

hook 的 warnings 与 context warnings 使用同一来源，不再硬编码空数组。
hook 和 report runtime 在 trace 完成后都以 trace 的 availability 与 warnings 回写顶层 context，并通过公共映射同步数值 confidence，避免顶层诊断与实际引用轨迹不一致。
若 hook 收到缺失、非 Mapping，或内部列表字段、`kind` / `lifecycle` 类型非法的 manifest，直接返回 invalid、0 confidence、空命中和明确提醒。manifest validator 与 trace 路由被直接传入非 Mapping 时也返回 `manifest_type_invalid`，不在 `.get()` 处中断。manifest 校验先记录字段类型问题，再使用安全空列表继续完成诊断；hook 外层 warnings 类型非法时也停止生成引用。上述情况都不得抛异常或保留无 trace 的满置信结果，自报 invalid 且没有原始提醒的 manifest 仍要补稳定原因。

### 7. Fresh And Replay

fresh：使用当前 manifest，trace 写明 query/target date。

fresh 快照保存前必须通过完整性校验：manifest、来源内容指纹、目标日期、manifest/facts/trace 指纹、全局 `fact_sources` 与逐命中 `matched_fact_sources` 都完整且互相一致。畸形或被重算 hash 后仍缺字段的 trace 不能进入正式快照。

replay：

- 如果快照已有与 target date 一致的 `knowledge_trace.v1`，优先保留该轨迹。
- 当前 Wiki 来源字节与冻结 manifest 不一致时，冻结 manifest、trace 和 hits 原样保留；只在 replay 外层保存 `frozen_availability`，把当前复核可用性标为 `source_changed` 并降低 `review_confidence`。
- 如果没有冻结轨迹，当前 manifest 可以作为明确标注的复盘参考，但不写成“当时命中”，也不进入 formal decision payload。
- 缺少或拒绝冻结轨迹时，外层 `confidence` 与 `review_confidence` 都明确为 `0.0`；来源变化时以 `frozen_confidence` 保留当时可信度，顶层两项 confidence 同步降为当前复核可信度。
- 来源变化后的 replay context 仍可再次复用同一冻结 manifest/trace/hits；外层 `source_changed` 不破坏冻结轨迹完整性判断。
- 首版若 snapshot 持久化接入范围过大，至少要在 runtime/replay 产物中保留这一差异，并以测试证明当前 Wiki 不改变当时决定；不能静默冒充历史版本。

### 8. Human Index And Log

`wiki/index.md` 是内容导航：分区、关键节点、运行知识来源和用途，不承载运行时触发条件。

`wiki/log.md` 是追加记录，格式：

```markdown
## [YYYY-MM-DD] contract | 简短标题
```

只记录 ingest/query/lint/contract 变化；不记录当天行情和可重算事实。

### 9. Wiki Lint

新增只读 CLI `scripts/knowledge/llm_wiki_lint.py`：

- 编译 manifest。
- 检查重复 ID、必填字段、生命周期、decision_scope、来源、断链。
- 输出确定性问题列表和退出码。
- 不自动写 index/log，不修改正文。

## Compatibility / Migration

- `source_paths`、`field_mappings`、`knowledge_hits`、旧 hit 字段全部保留。
- 新消费者优先读取 manifest/trace；旧消费者继续读取原字段。
- 首版编译当前全部结构化知识，271 条 FIELD_MAPPINGS 不批量迁移。
- manifest 编译失败不影响正式决定链；只停止知识命中与解释。
- 报告短表保持现有列，来源可以在不扩大版面的前提下增加版本短标识。

## Tradeoffs

### 选择运行时编译，而非提交大型 JSON

优点：不复制结构化条目；来源指纹永远对应当前字节；修改 Wiki 后测试能立即发现变化。

代价：运行时需读取少量 Markdown。当前只有几十条知识和几十个文件，成本可控；同一运行内缓存编译结果。

### 首版不移动 KNOWLEDGE_INDEX

优点：减少在已有大范围未提交改动上的冲突，保留所有测试与声明顺序。

代价：条目声明仍位于 router 文件。后续可在工作区干净后机械移动到独立 registry，但这不是本任务质量成立的必要条件。

### 不直接采用向量检索

当前主要问题是来源、版本和影响边界不可追溯，不是少量知识召回不足。先让每次命中可解释和可验收，再根据误召回/漏召回数据决定是否升级检索。

## Rollback / Roll-forward

- 新字段是追加式，回滚时可以停止调用 manifest/trace，旧 context/hits 仍可工作。
- 不删除 Wiki 正文或旧常量，因此不会丢失知识。
- 每个实现阶段先跑最窄单测；runtime/replay 接入前保留独立 checkpoint。
- 若 replay 冻结轨迹需要更广 snapshot 迁移，先保持“无历史轨迹则明确缺失”的正确降级，不用当前知识假装补齐。

## Open Decisions Resolved

- `knowledge_hits` 继续进入正式日报，但必须位于动作之后且仅作短引用。
- 首版 manifest 运行时编译，不新建需要人工双写的 JSON 清单。
- 不创建新的个人 skill；先把仓库运行契约和 trace 做实。
- 首版覆盖运行时全部结构化知识，不批量迁移 271 条 FIELD_MAPPINGS。
