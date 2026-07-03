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
- 已跑通相关单测，但历史 replay 样例受现有快照缺口影响，尚未生成一份完整样例日报。
- 合并前建议人工再看一份成功生成的日报页面，重点确认“路径诊断复盘”位置和篇幅是否舒服。
