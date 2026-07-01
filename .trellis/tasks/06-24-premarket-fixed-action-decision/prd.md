# 盘前买卖决定固定，盘中只执行或取消

状态：✅ 实现与验证完成，待提交

## Goal

把日报里的“明天买什么 / 卖什么”固定为当晚已经完成的交易决定，杜绝“明天如果满足某些情况再买某个观察对象”的表达和逻辑；盘中只能执行、取消、降风险或把观察结果留给下一份日报复盘。

## User Story

- **角色**：每日收盘后读取 A 股日报并据此准备次日操作的人。
- **场景**：日报给出明日仓位、目标、执行窗口、取消条件和观察对象。
- **目标**：在开盘前已经知道明天买不买、买谁、卖不卖、卖什么；盘中只按昨晚预案执行或取消，不把观察对象临时升级成买入对象。
- **成功标准**：日报和 HTML 中不再出现“盘前 0%，盘中条件满足再评估 50%”这类临盘再决定买的口径；所有正仓位动作都必须在日报里已经点名对象和动作。

### 用户旅程

1. 用户生成当日正式日报 → 系统给出明日买入决定、卖出决定、执行对象和取消条件。
2. 次日盘中 → 用户只检查预案是否仍有执行资格；若不满足则取消或降风险。
3. 次日收盘后 → 系统把观察对象表现写入复盘和下一份日报依据，而不是回头说盘中本该临时买入。

## What I Already Know

- `wiki/交易思想/交易错题本.md` 已经写有“盘前没有预案，盘中就没有买入资格”的旧规则。
- `wiki/交易思想/扣分系统与动作分层.md` 仍存在盘中观察升级的旧口径，需要收紧。
- 多个渲染入口仍输出“条件成立才评估50%条件执行”等表达，会让 0% 观察对象看起来可以临盘变成买入对象。
- `report_acceptance_audit.py` 已有 0% 明日动作一致性检查，可以扩展为本次规则的回归保护。
- 本仓库必须使用 `.generated/venv-py314/bin/python3.14` 运行测试和脚本。

## Requirements

- [x] R1: 0% / 空仓 / 仅观察的日报不得渲染任何“盘中条件满足后再买、再评估 50%、再参与”的文字或数据含义。
- [x] R2: 50% / 100% 正仓位日报必须表示为当晚已决定的执行计划，包含执行对象、仓位、执行窗口、取消条件；盘中条件只用于确认执行资格或取消。
- [x] R3: 观察对象、过程候选、复盘锚点即使次日走强，也只能进入复盘和下一份日报依据，不能在同一交易日被渲染为新增买入对象。
- [x] R4: Markdown、HTML/front-page、运行时摘要、验收审计和相关测试必须使用同一口径。
- [x] R5: 交易思想文档和 Trellis 规范要记录本次规则，避免后续生成链路再次滑回旧口径。

## Non-functional Requirements

### 性能
- 无额外性能要求；只做文案、结构字段和验收检查层面的最小改动。

### 兼容性
- 不改变日报生成入口、HTML 输出路径、正式日报和 replay 的命令形态。
- 保留既有 `0%不参与`、`50%条件执行`、`100%核心进攻` 标签，但重写其解释含义。

### 可维护性
- 新规则必须集中体现为可搜索的常量、测试断言或文档契约，不能只靠单处文案替换。

## Acceptance Criteria

- [x] AC-R1-1: 给定最终仓位为 0% 且存在观察对象，生成的 Markdown/HTML 不包含“条件成立才评估50%条件执行”“参与窗口命中后才评估50%条件执行”等临盘升级文案。
- [x] AC-R1-2: 给定最终仓位为 0% 且存在观察对象，验收审计会把旧临盘升级文案判为错误。
- [x] AC-R2-1: 给定最终仓位为 50% 或 100%，明日仓位文案表达为“已决定执行；条件不满足则取消/回到0%”，而不是“明天满足条件才决定买”。
- [x] AC-R2-2: 正仓位输出仍保留执行窗口和取消条件，用于盘中检查执行资格。
- [x] AC-R3-1: 观察对象文案明确“只复盘 / 下一份日报依据 / 不新增参与”，不出现同日买入升级。
- [x] AC-R4-1: `tests.test_report_acceptance_audit` 覆盖旧文案失败和新文案通过。
- [x] AC-R4-2: `tests.test_front_page_v2_renderer`、`tests.test_report_runtime` 或相关窄测试覆盖 0% 与 50%/100% 的新表达。
- [x] AC-R5-1: `wiki/交易思想/交易错题本.md`、`wiki/交易思想/扣分系统与动作分层.md` 或等价知识面记录本次规则。
- [x] AC-R5-2: `.trellis/spec/backend/daily-report-decision-loop.md` 记录“盘前决定、盘中只执行或取消”的日报契约。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md` 和 `implement.md` 已补齐。
- [x] 新增或更新的测试通过。
- [x] 窄验证命令已运行并记录结果。
- [x] 提交前已启用子代理做一轮审计。
- [ ] 提交完成后补充落地 commit。

## Out Of Scope

- 不重写整套选股、仓位评分或数据源采集逻辑。
- 不覆盖或重新生成历史正式日报，除非验证必须生成临时产物。
- 不引入券商执行、自动交易或实时盘中决策系统。
- 不把明日所有可能观察路径都展开成复杂分支；本任务只固定最终买卖决定和取消口径。

## Technical Notes

### 参考来源
- `wiki/交易思想/交易错题本.md` — 盘前预案和盘中买入资格规则。
- `.trellis/spec/backend/daily-report-decision-loop.md` — 日报决策链路契约。
- `scripts/report/report_acceptance_audit.py` — 验收审计入口。

### 影响区域
- `scripts/report/report_shell_nodes.py` — 明日仓位 / 固定交易窗口摘要。
- `scripts/report/front_page_v2_renderer.py` — HTML/front-page 明日仓位和观察对象表达。
- `scripts/report/runtime.py` — 运行时日报正文和摘要文案。
- `scripts/report/report_acceptance_audit.py` — 旧临盘升级文案拦截。
- `tests/` — 对应文案和审计测试。

## Verification

- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/front_summary_support.py scripts/selection/special_probe_runtime.py scripts/selection/watch_anchor_support.py scripts/report/strategy_tracking_followups.py` — passed。
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_runtime_contracts tests.test_front_summary_support tests.test_llm_wiki_context tests.test_llm_wiki_router` — 64 tests OK。
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_action_plan_renderer tests.test_candidate_selection_stage tests.test_front_page_v2_renderer tests.test_two_layer_decision_payload tests.test_report_acceptance_audit` — 307 tests OK。
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_watch_anchor_support tests.test_pk_decision_stage tests.test_positioning_node_runtime tests.test_market_research_renderer` — 122 tests OK。
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime` — 273 tests OK。
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-24_A股日报_完整版.md` — passed。
- `rg -n "升级为唯一执行候选|再决定是否进入50%|评估50%条件执行|再评估是否进入50%|升级参与|盘中新增参与|观察类.*上调|后才动手" scripts tests wiki .trellis/spec .trellis/tasks/06-24-premarket-fixed-action-decision` — remaining hits are legacy replacement/audit fixtures, negative assertions, or task text documenting old wording.
- `rg -n "命中才新开|条件满足才新开|买入区间命中|买入区间：" scripts tests wiki .trellis/spec .trellis/tasks/06-24-premarket-fixed-action-decision` — remaining hits are audit-block constants, negative assertions, or bad-case fixtures.
- `git diff --check` — passed。

## Notes

- 用户明确要求：不能写“如果明天怎样就买”，明天买什么 / 卖什么必须在今天日报里已经决定。

## 落地 commit

待提交；当前完成 commit 前审计与验证，尚未按用户确认创建 commit。
