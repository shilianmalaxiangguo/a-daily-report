# Bayesian 路径诊断接入说明

## 这次改动解决什么

这次接入的目标不是让 Bayesian 重新替日报选股，而是把最终动作背后的“市场、主线、资金、个股、反证”路径整理出来，让人和 AI 都能复盘：

- 最终动作仍以 `selection_workflow.final` 为准。
- Bayesian 只负责解释、复盘和暴露反证。
- 首页保留先看最终结论的阅读顺序，再补一段“路径诊断复盘”。
- 附录展示完整路径，作为过程证据。
- 来源日期缺失时保留“来源日期缺失”，不静默当作目标日期事实。

## 主要文件

| 文件 | 作用 |
|---|---|
| `scripts/report/bayesian_diagnosis.py` | 新增路径诊断包，生成 `bayesian_diagnosis.v1`。 |
| `scripts/report/runtime.py` | 在日报生成期构建并保存路径诊断包，传给首页和附录。 |
| `scripts/report/front_page_v2_renderer.py` | 在最终结论之后渲染简版“路径诊断复盘”。 |
| `scripts/report/sniper_target_derivation.py` | 在狙击目标推导附录加入完整路径，但不覆盖原最终对象。 |
| `scripts/report/report_acceptance_audit.py` | 增加来源日期、粗糙概率表达、对象不一致等专项检查。 |
| `tests/test_bayesian_diagnosis.py` | 覆盖路径诊断包的核心契约。 |
| `tests/test_sniper_target_derivation.py` | 覆盖 Bayesian 不能覆盖原最终对象。 |
| `tests/test_front_page_v2_renderer.py` | 覆盖首页展示顺序和简版路径解释。 |
| `tests/test_report_acceptance_audit.py` | 覆盖新增检查规则。 |
| `tests/test_report_runtime.py` | 覆盖运行期保存和传递。 |

## 接入后的阅读效果

日报首页的阅读顺序变成：

1. 先看“最终结论”：明天做不做、做谁、几成。
2. 再看“路径诊断复盘”：这个动作经过哪些层确认。
3. 再看“关键反证”：哪些条件会让动作降级或取消。
4. 到附录看完整路径和每层来源日期。

这样整理后，日报更适合人工复盘，也更适合 AI 继续理解：最终动作、路径解释、反证、证据日期各自分层，不再混成一段散乱文字。

## 与原有逻辑的关系

| 原有逻辑 | 本次处理 |
|---|---|
| `selection_workflow.final` 决定最终动作 | 保留，不被 Bayesian 覆盖。 |
| `final_target_resolution` 统一展示对象 | 保留，Bayesian 只读取结果做解释。 |
| 首页先给最终动作 | 保留，路径诊断放在最终结论之后。 |
| replay 必须尊重目标日期事实 | 保留，缺失来源日期时显式暴露。 |
| 原有一致性检查 | 保留，只新增 Bayesian 专项检查。 |

## 当前仍需谨慎的点

- 这次是解释层接入，不代表 Bayesian 已经能独立决定交易动作。
- 2026-07-03 已用 PostgreSQL-only 已冻结事实生成 replay 样例，未覆盖正式历史。
- 旧正式日报仍可作为对照；它本身存在旧持仓口径问题，所以本次成功样例以 `reports/replay/` 为准。
- 合并前建议人工打开成功样例页面，重点确认“路径诊断复盘”位置、篇幅和“条件执行 / 满仓条件执行”的表达颗粒度是否舒服。

## 2026-07-03 成功样例

| 产物 | 路径 | 说明 |
|---|---|---|
| 完整 Markdown | `reports/replay/2026-07-03_A股日报_完整版_replay.md` | PostgreSQL-only replay 样例，独立接受检查通过。 |
| Bear HTML | `reports/replay/2026-07-03_A股日报_完整版_replay.html` | 由新版 Markdown 渲染。 |
| 运行日志 | `reports/replay/2026-07-03_A股日报_运行日志_replay.md` | 记录关键数据检查、数据路径和耗时。 |
| 对比说明 | `docs/bayesian-diagnosis-migration/2026-07-03_regeneration_comparison.html` | 展示接入前后结构差异和流程对比。 |

样例结果：

- 雪球热榜与热榜解释在登录态可用后恢复。
- 实时路径仍受中证全指数据源影响；PostgreSQL-only 已冻结事实读取成功。
- “路径诊断复盘”出现在最终结论之后，执行对象仍是太极实业(600667)。
- 独立接受检查通过，顶部 Ta/Tb/Tc 时间轴不再把未输入持仓写成无持仓结论。
