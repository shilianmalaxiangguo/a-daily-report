# 市场语言翻译接入日报与 LLM Wiki

状态：✅ 已完成

## Goal

把“价格曲线是市场语言的表象，资金合力阶段才是需要翻译的语义”整理成可复用的 LLM Wiki 知识，并为日报增加一层只读研究证据：识别向上与向下压力的启动、扩散、拥挤、衰减、踩踏与修复，帮助使用者在固定交易窗口内更早看懂环境，同时不让三个锚定案例、事后最佳公式或未来高低点直接改写正式交易决定。

## User Story

- **角色**：使用日报进行 T0 研究、T+1 条件参与和 T+2 处理复盘的个人交易者。
- **场景**：看到指数、板块或个股出现顺滑弧形、同步加速、放量不涨或修复失败，希望知道市场正在表达什么，而不是先猜卖方身份或追逐小作文。
- **目标**：在日报中同时看到合力范围、方向、阶段、证据、反证和下一窗口任务，并能用 replay 检查早盘参与区与尾部退出征兆是否真的有效。
- **成功标准**：日报先给原有明日动作，再给市场语言研究证据；研究证据缺失时明确写事实不足；无论研究判断为何，第一版的候选、仓位、B1/B2 和退出动作都与接入前一致。

### 用户旅程

1. 收盘后生成日报，先阅读原有“明日执行结论”和账户动作。
2. 在后续市场研究区查看市值加权指数、全市场宽度和板块同步是否说同一种话。
3. 查看当天合力处于启动、扩散、拥挤、衰减、踩踏、修复或不清楚中的哪一类，以及候选何时出现、何时确认、何时失效。
4. 下一交易日仍只在 `09:30-09:35`、`09:50-10:10`、`14:30-14:55` 三段处理买卖；事件时钟只决定每个窗口该验证什么。
5. 收盘后用未来已发生的价格区间、后续收益和失效记录验收判断，不把这些事后答案倒灌到当时结论。

## What I Already Know

- 上证指数的平滑弧形包含大量成分股聚合效果，但它是市值加权指数，不能单独等同于全市场合力；必须同时看等权宽度、中位数或上涨下跌家数，以及板块成分股同步。
- 三个一分钟锚定案例中，上证全日最接近平移椭圆弧，三例客观下降段都由单变化点分段模型第一，但换挡方向并不一致，因此不存在已经被三例证明的万能公式。
- 兆易创新在 `09:47` 出现候选、`09:49` 仅见重叠斜率连续、`09:54` 失效；`10:00` 再次出现，`10:01` 有价格同向延续，`10:02` 重叠斜率连续。上证到 `10:10` 没有越过噪声带的向下候选，第一轮向下候选是 `10:17`，持续到尾盘的一轮从 `13:50` 开始。候选、证据质量和失效比“长得像鸭蛋”更接近可用市场语言。
- `09:45-09:50` 可作为第二窗口的前哨观察，但不是新增买卖窗口；正式普通结构处理仍是 `09:50-10:10`。
- 当前 Tushare 账号不能取得三个锚定案例的历史一分钟数据；新鲜日报如果没有可追溯分钟事实，不能伪造事件时间，只能输出较粗的日终合力判断和 `evidence_status=partial/insufficient`。
- `market_research_snapshot` 同时被研究展示和正式对象解析消费。新研究产物若直接混入该共享快照，存在无意影响正式决定的风险。
- 现有公式、烧柴理论和案例节点已经保存详细推导；新总节点只负责统一语言、阶段、时间与日报边界，不复制长篇公式。

## Requirements

- [x] R1: 建立 `市场语言翻译与资金合力阶段` 总节点，明确表象、机制假说、合力范围、方向、阶段、反证、固定时间钟和事件时间钟的关系，并链接现有公式、烧柴和案例节点。
- [x] R2: 定义独立的 `market_language_translation.v1` 研究产物，至少包含来源引用、合力范围、价格压力方向、合法阶段组合、多轮候选/重叠斜率连续/价格同向延续/失效时间、证据质量、因果截止点、同步与扩散、价格冲击代理、反证、下一窗口任务和事后验收字段。
- [x] R3: 第一版只使用现有日报事实与可追溯分钟数据；缺少一分钟数据时按字段降级，不新增外部数据源，不把五分钟插值或当日实时数据冒充历史一分钟事实。
- [x] R4: 固定交易时间只保留 `09:30-09:35`、`09:50-10:10`、`14:30-14:55`；`09:45-09:50` 只作前哨观察；全天事件时钟记录候选、确认、失效和阶段切换，但不新增窗口外买卖动作。
- [x] R5: 日报命令入口、AgentRunner 或 replay 入口在完整版和摘要版渲染前从原始事实投影只准备一次研究产物，并保留在局部变量中，以显式只读参数传入；只在第二次最终对象解析完成后进入“明日执行结论”之后的最终前台证据区，不写入共享输入，不参与 `selection_workflow`、`final_target_resolution`、候选排序、仓位、B1/B2 或退出动作计算。
- [x] R6: replay 同时覆盖三个锚定案例与普通下跌、消息重估、单一大资金执行、快速修复、权重股独涨/独跌等反例，分别检验候选领先时间、重叠斜率连续、价格同向延续、失效次数和阶段解释稳定性。
- [x] R7: 事后低区/高区命中、未来 `5/10/20` 分钟表现、T+1/T+2 价格区间、主要行情完成比例、MFE/MAE 和资金重叠只进入 replay 验收，不进入当日判断字段。
- [x] R8: 更新 LLM Wiki 路由、公式工具箱和默认上下文的方式必须分阶段：本轮先完成人工知识路由；只有研究字段实现并通过保护测试后，才单独决定是否加入日报默认知识上下文。
- [x] R9: fresh 研究产物只在完整版、摘要版、正式决定不变对比、日报检查和整日事实同步都通过后独立保存；PostgreSQL 使用现有 `daily_report_fact_fields` 的专属 `source_policy` 与字段前缀并能跨后续整日同步保留，本地 fresh 与 replay 使用不同路径，replay 只按目标日期精确加载且不覆盖 fresh。

## Non-functional Requirements

### 可追溯性

- 每个分钟或日终字段保留 `target_date`、`source_date`、`query_date`、粒度和来源；无法证明日期归属时保持缺失。
- 公式拟合、阶段判断和事后结果分栏保存，禁止用未来事实补写当时结论。

### 兼容性

- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 报告保持现有动作优先顺序，Markdown 与 Bear HTML 同步展示；窄屏不出现横向溢出。

### 表达

- 用户可见文字遵守 `wiki/交易思想/日报术语契约.md`。
- 不输出“椭圆等于量化”“公式匹配度等于量化概率”“量化成交占比已测得”等越过证据的结论。

## Acceptance Criteria

- [x] AC-R1-1: 新总节点能独立回答“市场语言是什么、指数为何更平滑、怎样区分合力范围、两个时间钟怎样配合、哪些结论不能下”。
- [x] AC-R2-1: `market_language_translation.v1` 有稳定字段表、单位、时间语义、来源引用、合法方向/阶段组合和缺失语义；每一轮事件都包含候选、识别、确认基础、证据质量、价格同向延续、失效与因果截止字段。
- [x] AC-R2-2: 给定同一前缀事实，改变任一事件 `causal_cutoff` 之后的数据，不会修改该事件已经保存的候选、确认或失效时点。
- [x] AC-R3-1: 给定没有分钟事实但有目标日可追溯日终事实的 replay，产物标记 `reconstructed` 并降级为 `partial/insufficient`；给定目标日事实也不足的 replay，事件数组为空并列出缺失项。两种情况都不读取当前日期事实或虚构时刻。
- [x] AC-R4-1: 所有用户可见买卖动作仍只出现于三段正式窗口，`09:45-09:50`、`10:10-11:00`、`13:00-14:30` 只能写观察或研究任务。
- [x] AC-R5-1: 同一冻结输入的完整版和摘要版，在接入前后生成的 `selection_workflow`、`final_target_resolution`、明日执行对象、明日仓位、执行性质、B1/B2 和退出动作逐字段一致；两次渲染前后原 artifact 的 canonical JSON 哈希不变。
- [x] AC-R5-2: 二级标题“市场语言翻译（研究证据）”只在最终前台渲染，位于“明日执行结论”之后，并被 Bear HTML 归为证据区，不抢占首屏动作。
- [x] AC-R6-1: replay 报告逐例列出首次候选、确认、失效、主要阶段切换和反证，且三个锚定案例可以得到不同公式排名或阶段路径而不被强行归为同一机制。
- [x] AC-R6-2: 反例出现时允许输出“不清楚”或候选失效，不以提高命中率为由删除失败记录。
- [x] AC-R7-1: 所有未来高低点、未来收益和区间排名只存在于 `posthoc_validation` 或等价 replay 结果中，生产日报研究字段不包含未来事实。
- [x] AC-R8-1: Wiki 人工路由先完成；若未来加入默认上下文，必须有 `tests/test_llm_wiki_context.py` 的来源路径与字段映射测试。
- [x] AC-R9-1: PostgreSQL 专属 `source_policy` 和本地 fresh JSON 均可按目标日期做规范化结构 round-trip；写入当前产物不删除同日其他事实，随后再次保存整日事实也不删除 artifact，读取不到目标日时不回退到最近日期。
- [x] AC-R9-2: replay 重建与 `posthoc_validation` 只保存在内存或 `snapshots/replay/market-language/`，不覆盖 PostgreSQL fresh artifact 或 `data/market-language/fresh/`。
- [x] AC-R9-3: 当前 AgentRunner 的预保存检查或保存后最终检查任一失败时不写 replay artifact；两次检查和报告保存都成功时才写 replay 路径，且从不调用 fresh writer。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md`、`implement.md` 与 `research/market-language-integration.md` 已补齐。
- [x] `implement.jsonl`、`check.jsonl` 已配置必要上下文。
- [x] 日报实现相关单测、replay、Markdown/Bear HTML 顺序和正式决定不变对比通过。
- [x] 子代理完成数据因果、代码边界和 Wiki 表达三类提交前审计，问题已处理或明确记录。
- [x] PRD 状态改为 `✅ 已完成`，并在用户明确同意后提交。

## Out Of Scope

- 本轮只允许新增只读研究证据、独立保存和 replay 验收；不让研究产物修改正式日报的候选生成、对象解析、仓位、B1/B2 或退出动作。
- 不根据三个极端案例确定固定阈值、普遍命中率或“A 股量化占比约 40%”。
- 不确认龙虎榜席位、卖方账户身份、逐笔触发链、撤单率或真实盘口深度。
- 不把压力衰减直接翻译成抄底资格，不把完整鸭蛋形成后的事后识别包装成提前预警。
- 不新增第四个买卖窗口，不把全天事件候选改写成盘中临时下单理由。
- 不在本任务内新增或购买分钟数据源权限。
- 不新增数据库表或 DDL；持久化复用现有通用事实表的独立字段前缀。

## Delivery Slices

| 阶段 | 交付物 | 可独立验收 | 对应 Requirement |
|------|--------|------------|------------------|
| A. 知识统一 | Wiki 总节点、README 路由、公式工具箱校准 | 是 | `R1`, `R8` |
| B. 只读研究产物 | builder、字段契约、缺失处理、独立保存 | 是 | `R2`, `R3`, `R7`, `R9` |
| C. 日报证据展示 | Markdown/Bear HTML 小节、动作优先顺序 | 是 | `R4`, `R5` |
| D. replay 验收 | 锚定案例、反例、走前验证与正式决定对比 | 是 | `R5`, `R6`, `R7` |

执行顺序：A → B → D 的字段校准 → C 的影子展示 → 扩大 D 的样本外验收。任何阶段都不自动升级为正式交易决定输入。

## Technical Notes

### 参考来源

- `.trellis/tasks/07-11-07-11-quant-pressure-one-minute-window-review/research/findings.md`
- `reports/research/quant-pressure-replay-study-20260711.html`
- `wiki/资料库/量化跟踪日报公式工具箱.md`
- `wiki/资料库/异质临界值触发与流动性反馈模型.md`
- `wiki/资料库/烧柴理论-资金压力的峰值库存与半衰期.md`
- `wiki/资料库/2026-05-21上证指数级联下跌样本.md`
- `wiki/资料库/2026-07-10兆易创新极端资金样本.md`

### 预期影响区域

- `scripts/domains/market_state/` — 构建只读市场语言研究产物。
- `scripts/daily_report_entry_demo.py` — 命令入口准备局部 artifact，并在日报检查与整日事实同步成功后提交 fresh artifact。
- `scripts/daily_report_render.py` — 接收显式 artifact，为完整版和摘要版传入隔离副本，不负责提交。
- `scripts/agent_runner/daily_report_agent_runner.py` — 当前只支持 replay；在预保存检查、报告保存和保存后最终检查都通过时写 replay 副本，不提交 fresh。
- `scripts/report/runtime.py`、`scripts/report/front_page_v2_renderer.py` — 在第二次最终对象解析后渲染证据，不回写正式决定。
- `scripts/report/markdown_report_html.py` — 将二级标题归为 Bear HTML 证据区。
- `scripts/storage/postgres_daily_fact_db.py` — 专属字段前缀 writer/loader，不删除同日其他事实。
- `scripts/replay/report_replay.py` — 抽离目标日 artifact、按目标日重建并验收事后结果。
- `scripts/knowledge/llm_wiki_context.py` — 仅在后续明确批准默认注入时更新。
- `tests/` — 字段契约、窗口边界、未来事实隔离、顺序与正式决定不变测试。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_language_translation tests.test_postgres_daily_fact_db tests.test_tushare_input_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer tests.test_daily_report_render tests.test_daily_report_agent_runner tests.test_market_language_translation_lifecycle tests.test_report_replay tests.test_daily_report_markdown_html tests.test_report_acceptance_audit tests.test_llm_wiki_context`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <每个锚定/保护日期> --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/<日期>_A股日报_完整版_replay.md`
- 对完整版与摘要版的接入前后结构化产物比较 `selection_workflow`、`final_target_resolution`、明日执行对象、仓位、执行性质、B1/B2 与退出动作；检查 artifact 哈希不变。
- 检查 Markdown 与 Bear HTML 中“明日执行结论”早于“市场语言翻译（研究证据）”，并运行桌面与窄屏渲染检查。
- `git diff --check -- <本任务文件>`

最新证据（2026-07-12）：相关 12 模块共 766 项测试通过、1 项按环境条件跳过；单独开启后，真实 PostgreSQL 同库重存测试通过；真实 Runtime 与命令入口 5 项测试通过。Revision 4 研究模块 23 项测试、生成器逐字一致和 HTML 解析通过，SHA256 为 `b203af7a579eb16366da899baa7ac43b544fe9b96ba0ab76a26bdda866ca3f8d`。Playwright 在桌面和 `390px` 下均无页面级横向溢出，10/10 SVG 非空，新增宽表只在自身容器滚动，控制台零错误。

提交日复核（2026-07-13）：全量 `3353` 项测试通过、`1` 项按环境条件跳过；`2026-07-10` replay 日报一致性检查通过。提交前审计补齐了旧 replay 宽度事实的目标日期字段保留，以及 PostgreSQL-only 精确日期未命中时不读取本地 fresh 文件的隔离测试。

## 落地 commit

实现与提交前验证已完成，用户已确认提交；落地提交见 Git 历史。
