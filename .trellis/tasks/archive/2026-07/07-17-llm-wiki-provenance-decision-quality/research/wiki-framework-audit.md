# Research: LLM Wiki 调用、引用与决定质量审计

## Question

现有 Wiki 框架与 Karpathy 原始构想、`nashsu/llm_wiki` 相比，哪些能力直接影响日报调用、引用与决定质量；首版怎样在不扩大到通用知识应用的前提下修正？

## Sources

- `https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f`
- `https://github.com/nashsu/llm_wiki`，审计 commit `969e7e8d9e2903af0e3ed0be85c97639511e845c`
- `wiki/README.md`
- `wiki/运行契约/LLM Wiki维护与路由契约.md`
- `docs/trellis/specs/2026-05-29-daily-report-knowledge-agent-design.md`
- `scripts/knowledge/llm_wiki_context.py`
- `scripts/knowledge/llm_wiki_router.py`
- `scripts/hooks/knowledge/use_llm_wiki.py`
- `scripts/report/runtime.py`
- `.trellis/spec/backend/daily-report-decision-loop.md`
- `.trellis/tasks/07-12-market-language-daily-report-wiki/`
- `.trellis/tasks/07-13-daily-report-index-cross-validation/`
- `.trellis/tasks/07-14-daily-position-action-semantics/`

## Findings

### 1. 当前系统已守住决定边界，但缺少可验证证据

- `runtime.py` 从正式数据提取事实，再路由 `knowledge_hits` 并写入知识区；`selection_workflow`、最终对象和 two-layer payload 没有读取命中结果。
- 这是正确边界，但当前只能通过代码阅读得出。运行产物没有保存“知识只用于解释”的影响范围，也没有正式决定字段的前后指纹。
- 因此，后续维护者仍可能把 `impact` 文字误当成正式动作输入，而测试不一定及时发现。

### 2. 静态上下文和运行知识存在明显双写

- `llm_wiki_context.py` 有 271 条 `FIELD_MAPPINGS`，其中约 217 条像交易/判断规则，约 54 条明显属于输出、运行或流程纪律。
- 初次审计时 `llm_wiki_router.py` 有 26 条结构化 `KNOWLEDGE_INDEX`；续跑混合工作区已增加到 30 条，其中 5 条属于并行业务改动。manifest 编译和测试应覆盖提交时实际存在的全部条目，不固定最低数量。
- 直接把 271 条全部迁移会把流程说明误当成可路由知识。首版应以运行时全部结构化条目为 manifest 基础，明确 `knowledge_rule` 与 policy/process 的边界。

### 3. 来源保真契约没有进入运行数据

- Wiki 运行契约要求 URL/local path、标题、作者或发布方、发布时间、采集日期以及 `source_date`/`capture_date`。
- 当前 context 只返回存在的相对路径；缺失路径被静默过滤。
- 当前 hit 只带 `source_path`，没有来源内容指纹、知识版本、原文位置或日期。
- 这使 fresh 结果难以复核，也无法证明历史 replay 用的是当时知识。

### 4. 当前路由解释性有限

- 结构化条件与文本触发都有使用，但所有事实最终也会被扁平化为字符串做子串匹配。
- `knowledge_hit_facts` 可以用任意字典替换自动事实，没有白名单或来源说明。
- 现有测试有少量否定场景，但没有系统覆盖字段名误命中、历史知识版本、缺源和显式旁路。

### 5. Karpathy 方案最值得补的是维护结构，不是更复杂搜索

- 原始方案的核心是不可变来源、持续编译 Wiki、`index.md`、追加式 `log.md` 和 lint；搜索是规模增长后的可选工具。
- 当前 Wiki 有 40 个 Markdown 节点和手写 README 路由，但没有统一 `index.md`、`log.md` 与机器可读知识版本。
- 确定性扫描无法把当前目录识别为完整 Karpathy-pattern Wiki，缺口正是 index/log/raw/schema 的机器入口。

### 6. `nashsu/llm_wiki` 可借鉴但不应整体接入

可借鉴：

- 来源稳定身份与 SHA-256 摄入缓存。
- 两阶段“先分析矛盾与连接，再生成页面”。
- 人工复核、index/log、可选混合检索和图关系。

不应直接采用：

- 当前网页搜索结果作为历史交易事实。
- LLM 自动合并冲突知识并直接覆盖原页。
- 字符预算替代真实 token 预算。
- 把 JSON 解析失败当作“没有重复/没有问题”。
- 非原子多文件写入和只在单进程内有效的锁作为交易事实保障。

### 7. 历史任务已经给出必须继承的日期与决定契约

- 所有来源必须保留 target/source/query date 和内容指纹。
- `source_date != target_date` 的时变事实不得进入目标日报派生。
- T+1/T+2 未来事实只进入 replay/review，不得改变 T0 候选和动作。
- 市场语言与研究证据必须后置，不能参与最终对象、仓位、B1/B2 或退出动作。
- Wiki 新仓/旧仓规则必须与正文、静态上下文和路由一致。

## Recommendation

先实现 `knowledge_manifest.v1 + knowledge_trace.v1 + 决定隔离测试`，再讨论召回升级。首版：

1. 以运行时全部结构化知识为唯一运行条目来源，不把条目数量写死。
2. 编译来源指纹和 manifest 指纹，缺源显式诊断。
3. 路由保存事实指纹、得分、事实路径、来源引用和影响边界。
4. fresh 保存当次 trace；replay 优先冻结 trace，无历史 trace 时明确缺失。
5. 同一输入切换两份 manifest，逐字段证明正式决定完全不变。
6. 增加 `wiki/index.md`、`wiki/log.md` 和只读 lint。

不在首版引入向量库、桌面应用、自动网页研究、全库 frontmatter 改写或知识自动回写。

## Impact

- PRD: 新增 manifest、trace、日期隔离、缺源诊断、index/log/lint 和正式决定不变量要求。
- Design: 采用追加式兼容字段与运行时编译，避免大型 JSON 双写。
- Implementation: 先完成 manifest/context，再做 router/trace，最后接 runtime/replay 与跨层测试。
