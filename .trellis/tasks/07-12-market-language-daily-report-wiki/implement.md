# Implementation: 市场语言翻译接入日报与 LLM Wiki

## Prerequisites

- 用户确认从规划与 Wiki 阶段进入日报代码实现。
- 保留当前工作区已有修改，不清理、不格式化无关文件。
- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 先冻结至少一组普通日和反例 replay 输入；没有可追溯分钟数据时只验证日终降级路径。
- 实现前保存完整版与摘要版的正式决定基线投影。

## Ordered Checklist

- [x] I1: 汇总三例一分钟结论、公式职责、指数聚合边界和两个时间钟，保存研究记录。
- [x] I2: 新增 LLM Wiki 总节点，更新人工路由、公式工具箱和相邻案例的一分钟主口径。
- [x] I3: 先写 `market_language_translation.v1` 契约测试，覆盖完整分钟、只有日终事实、来源日期不明、空输入、多轮失效和非法方向/阶段组合。
- [x] I4: 实现 source projection 与纯函数 builder；每条派生证据引用来源编号，记录单位、`as_of_time` 和 `causal_cutoff`，不新增数据源。
- [x] I5: 实现多轮事件序列，保留候选、识别、重叠斜率连续、价格同向延续、证据质量、失效、再候选和阶段切换；证明追加截止点之后的数据不会改写历史事件。
- [x] I6: 日报命令入口、AgentRunner 和 replay 入口各自在局部变量中只准备一次 artifact，再显式传给 `build_report_outputs`；完整版与摘要版各接收深拷贝，不把 artifact 写入 `data`、`market_research_snapshot` 或 `execution_stage_context`。
- [x] I7: 将 artifact 作为显式可选参数传到第二次最终对象解析之后的 `render_front_page_v2`，新增二级标题“市场语言翻译（研究证据）”；数据不足时列出缺失，不渲染伪精确时刻。
- [x] I8: 把新二级标题加入 Bear HTML 证据区分类；增加动作优先顺序、空态、完整版/摘要版和窄屏测试。
- [x] I9: 实现独立 artifact writer/loader。PostgreSQL 行使用专属 `source_policy`，删除与批量写入处于同一事务；整日事实保存必须保留该 `source_policy`。本地 fresh 写 `data/market-language/fresh/<date>.json`，不得调用会先删除同日全部事实的整日保存函数。
- [x] I10: 正式命令入口只在日报检查与整日事实同步成功后提交 fresh；replay 在正式决定前抽离 artifact，缺失时只用目标日可追溯事实重建，事实不足时输出 `insufficient`，不回退到当前日期或最近日期。
- [x] I11: replay 在独立副本中增加 `posthoc_validation`，计算未来 `5/10/20` 分钟、低区/高区、MFE/MAE、T+1/T+2 与资金重叠，生产 artifact 保持 `null`；replay 仅写 `snapshots/replay/market-language/`，不覆盖 fresh。
- [x] I12: 用三个锚定案例和全部保护类别运行走前验证，记录不同公式/阶段路径、失效样本和起点敏感性。
- [x] I13: 对完整版与摘要版分别比较接入前后 `selection_workflow`、`final_target_resolution`、执行对象、仓位、执行性质、B1/B2 和退出动作；比较两次渲染前后 artifact 哈希。
- [x] I14: 已单独评估默认上下文；本轮继续只保留人工 Wiki 路由，不把总节点加入 `llm_wiki_context`。
- [x] I15: 将一分钟研究 HTML 生成器升级到 Revision 3，区分前哨与正式窗口、重叠斜率连续与价格同向延续，并用逐字一致测试保证正式 HTML 可复现。
- [x] I16: 处理第二轮提交前审计：数值化跨板块同步、交易所身份、显式 T+ 交易日历、fresh 未来事实隔离、完整 240 分钟、查询日期校验、正式/论文曲率复用、活动事件方向优先、跨方向时刻不回退、项目根目录 replay 保存及两层动作载荷不变对比均已补回归。
- [x] I17: 处理最终提交前审计：真实百分数字符串、严格查询日期、事件顺序与分钟网格、跨板块方向一致、双兼容键清理、主分钟内容哈希一致，以及任务/结构文档同步均已补回归或记录。
- [x] I18: 处理提交前跨层审计：固定窗口同步校验方向/阶段与反证引用；Tushare 和 PostgreSQL 的市场宽度生产结果写入自身目标交易日，并用真实生产形状证明宽度事实可以进入三层对照。
- [x] I19: 记录 `13:45-14:10` 午后风险观察假说，按三例分开复算“期间曾捕获”与 `14:00/14:05/14:10/14:20` 截止截面，补跨午持续事件和因果截止回归；区分防守式卖出、高位止盈和持续上涨，不修改正式三段窗口。
- [x] I20: 处理本轮三类提交前审计：撤回用截止截面选择 `14:10` 的错误推论，保留跨午持续事件，补完整结构化减风险条件，统一合力范围表达并收紧早盘能力表述。

## Proposed File Map

- `scripts/domains/market_state/market_language_translation.py`：新增 source projection、纯函数 builder、字段规范化和方向/阶段组合校验。
- `scripts/report/market_language_translation_artifacts.py`：新增 artifact 准备、canonical 数值规范化、独立 writer/loader、本地 fresh/replay 路径与 PostgreSQL service 路由。
- `scripts/daily_report_render.py`：接收显式 artifact，为完整版/摘要版传入隔离副本；不在该层持久化。
- `scripts/daily_report_entry_demo.py`：命令入口在局部变量中准备 artifact，传给报告构建，并在日报检查与整日事实同步成功后提交 fresh。
- `scripts/agent_runner/daily_report_agent_runner.py`：当前只支持 replay；使用显式 artifact，并在预保存检查、报告保存和保存后的最终检查都通过时写 replay 副本，不调用 fresh writer。
- `scripts/report/runtime.py`：把显式参数直传至第二次最终对象解析后的最终前台渲染调用。
- `scripts/report/front_page_v2_renderer.py`：新增二级证据区渲染函数；缺省参数保持旧行为。
- `scripts/report/markdown_report_html.py`：把“市场语言翻译（研究证据）”加入 `_EVIDENCE_H2_TITLES`；现有模板样式继续复用。
- `scripts/storage/postgres_daily_fact_db.py`：新增专属 `source_policy` 的事务写入与精确日期读取；整日保存保留该策略的行，不新增 DDL，不删除同日其他事实。
- `scripts/replay/report_replay.py`：在正式决定前抽离/重建目标日 artifact，分开保存当时字段与 `posthoc_validation`，只写 replay 路径。
- `tests/test_market_language_translation.py`：新增字段、来源、事件时间、因果截止、缺失和 round-trip 单测。
- `tests/test_postgres_daily_fact_db.py`：补专属 `source_policy` 事务覆盖、整日再次保存仍保留、相似字段不误删、数值规范化和精确日期读取测试。
- `tests/test_front_page_v2_renderer.py`：补最终插入点、动作优先、空态和正式决定只读测试。
- `tests/test_daily_report_render.py`：补显式参数、两种版本隔离副本和原 artifact canonical 哈希不变测试。
- `tests/test_market_language_translation_lifecycle.py`：补命令入口的日报检查/整日同步/提交顺序，以及任一步失败都不提交测试。
- `tests/test_daily_report_agent_runner.py`：补预保存检查或保存后最终检查失败都不提交 replay，以及全部通过才写 replay 副本的测试。
- `tests/test_report_replay.py`：补加载、重建、事实不足、事后验收和不回填测试。
- `tests/test_daily_report_markdown_html.py`：补 Bear HTML 证据区分类与标题顺序测试。
- `tests/test_report_acceptance_audit.py`：只在现有检查无法覆盖动作优先或未来事实泄漏时补最小规则。
- `tests/test_llm_wiki_context.py`：只在后续批准加入默认上下文时修改。
- `scripts/research/quant_pressure_one_minute_study.py`：维护三例一分钟公式、窗口和事件证据的可复现论文生成器。
- `tests/test_quant_pressure_one_minute_study.py`：覆盖噪声带后的锚定时点、确认质量、两分钟中性缓冲、前哨/正式窗口图示和生成器逐字一致。
- `reports/research/quant-pressure-replay-study-20260711.html`：Revision 4 论文式汇总，由上述生成器重建，不手工维护另一套正文。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_market_language_translation tests.test_postgres_daily_fact_db`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer tests.test_daily_report_render tests.test_daily_report_agent_runner tests.test_market_language_translation_lifecycle tests.test_report_replay tests.test_daily_report_markdown_html tests.test_report_acceptance_audit tests.test_llm_wiki_context`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <每个锚定/保护日期> --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/<日期>_A股日报_完整版_replay.md`
- `.generated/venv-py314/bin/python3.14 -m html.parser reports/replay/<日期>_A股日报_完整版_replay.html`
- `git diff --check -- <本任务实际修改文件>`

## Risk And Rollback Points

- **最终插入点错误**：若新小节从早期市场研究节点渲染，移除该路径，只保留第二次最终对象解析后的 `render_front_page_v2` 显式参数。
- **二次渲染污染**：若完整版生成后 artifact 出现在共享 `data`，停止持久化并改回局部变量；两种版本必须各接收深拷贝。
- **同日事实误删**：writer 只按精确 `trade_date + source_policy` 删除，并与批量写入共用事务；整日保存必须保留该策略。任何 `LIKE` 前缀删除或整日误删都停止实现。
- **保存过早**：`build_report_outputs` 不提交 artifact；日报检查或整日事实同步失败时不写 fresh。
- **replay 覆盖 fresh**：replay 不调用 fresh writer，只写 `snapshots/replay/market-language/`。
- **未来事实倒灌**：生产 artifact 出现未来高低点、未来收益或主要行情完成比例时，停止生成该小节并修正数据分层。
- **分钟来源缺失**：不切换为实时数据补历史，不用插值，不读取最近日期；输出事实不足。
- **窗口扩张**：观察时刻若被渲染成新增买卖动作，改回“观察/下一窗口任务”，并补文本检查。
- **案例过拟合**：保护样本误判较多时，保留 artifact 与 replay，但不进入日报展示。

## Review Checkpoints

- **Checkpoint A：字段因果** — 每条派生证据有来源引用、单位、时点和因果截止；未来数据不改写历史事件。
- **Checkpoint B：正式决定隔离** — artifact 只走显式参数，正式决定消费者不可读取。
- **Checkpoint C：双版本隔离** — 完整版与摘要版使用同一个源 artifact 的隔离副本，原哈希不变。
- **Checkpoint D：存储与 replay** — 精确目标日规范化结构 round-trip，整日再次保存仍保留 artifact，不删除相似字段，不用当前或最近日期替代，不用 replay 覆盖 fresh。
- **Checkpoint E：窗口纪律** — 三段正式窗口不变，前哨与事件时间只作观察。
- **Checkpoint F：反例** — 普通下跌、消息重估、单一权重和快速修复可以得到“不清楚”或候选失效。
- **Checkpoint G：展示** — 动作在前、证据在后，Markdown/Bear HTML 和窄屏一致。
- **Checkpoint H：提交前审计** — 数据因果、代码边界、Wiki 表达三类子代理审计完成。

## Latest Verification

- 相关 12 模块：766 项测试通过，1 项按环境条件跳过；被跳过的真实 PostgreSQL 用例已单独开启并通过。
- 真实 PostgreSQL：同一数据库内写入 artifact、再次保存整日事实、再读取 artifact 的测试通过。
- 真实 Runtime 与命令入口：正式决定不变、动作早于研究证据、fresh/replay 保存时点及磁盘正文不一致时停止写入，共 5 项通过。
- Revision 3：生成器逐字一致、HTML parser 通过；桌面与 `390px` 无页面级横向溢出或元素重叠，10/10 SVG 非空，公式与四类窗口底色可见，控制台零错误。
- Revision 4：研究模块 23 项测试、生成器逐字一致和 HTML parser 通过，SHA256 为 `b203af7a579eb16366da899baa7ac43b544fe9b96ba0ab76a26bdda866ca3f8d`；桌面 `1440px` 与窄屏 `390px` 均无页面级横向溢出，新增事件与分支表只在自身容器滚动，10/10 SVG 非空，控制台零错误。
