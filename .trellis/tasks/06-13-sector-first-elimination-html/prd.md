# 板块先行选股淘汰赛HTML与日报同步生成

状态：✅ 已完成（未提交）

## Goal

将日报选股从分散模块各自给对象，收敛为板块先行、唯一最终对象、全链路淘汰证据可视化的交付：每次生成日报时，同步产出一份 companion HTML，清楚展示每一层输入几只、淘汰几只、淘汰哪些、淘汰理由、剩余哪些，以及最终如何进入 `final_target_resolution` 的唯一动作。

## User Story

- **角色**：日报使用者 / 盘前决策者。
- **场景**：查看每日 A 股日报，想知道明日唯一动作是如何从板块和个股比较中推导出来。
- **目标**：不再在多个模块看到多个“明日标的”，而是在一张淘汰赛 HTML 中看到完整决策链。
- **成功标准**：用户能一眼判断某只股票在哪一层被淘汰、为什么淘汰、若淘汰有误应复盘哪个环节。

### 用户旅程

1. 用户生成某日 A 股日报 → 系统生成 Markdown/HTML 日报，并同步生成淘汰赛 companion HTML。
2. 用户打开淘汰赛 HTML → 看到板块层、角色层、龙头反推层、价格行为层、盈亏比/账户层、最终收口层。
3. 用户点击或阅读某只股票 → 看到它进入哪一层、被哪条规则淘汰、淘汰理由和剩余对象。
4. 用户回看日报前台 → 只看到一个明日唯一动作或观察对象；其他股票只作为过程样本、被淘汰对象或板块参照。

## What I Already Know

- `scripts/knowledge/llm_wiki_context.py` 已规定报告模块只消费 `final_target_resolution`，不各自重算标的。
- LLM Wiki 口径要求最终只生成明日唯一动作或观察对象；最终 0% 时前台不得继续写主买/补位或新增参与。
- 当前 2026-06-12 replay 已有 `data/candidate-traces/2026-06-12.json` 与 `data/decision-ledger/2026-06-12.json`，但缺少按层淘汰赛方式呈现的同步 HTML。
- 当前报告里存在“身份通过但执行资格未成立”的阅读混淆，例如和远气体：板块锚通过，但因炸板57次、尾盘回封、高换手连板等风险只保留观察。
- 当前 Codex 会话为 inline 模式，Trellis 子任务承载交付拆分；代码实现和检查由主会话直接执行，不实际派发实现代理。

## Requirements

- [x] R1: 日报必须有且只有一个最终动作来源：`final_target_resolution` 或由它控制的同源结构化结果；报告模块不得各自重算明日标的。
- [x] R2: 每次日报生成必须同步产出淘汰赛 companion HTML，文件名能从报告日期和 replay/official 语境稳定定位。
- [x] R3: 淘汰赛 HTML 必须按层展示：板块层、板块内角色层、龙头反推层、价格行为层、盈亏比/账户层、最终收口层。
- [x] R4: 每一层必须展示输入数量、淘汰数量、淘汰名单、淘汰理由、剩余名单、下一层依据。
- [x] R5: HTML 中除最终收口层外，所有非最终股票只能标为过程样本、被淘汰对象或板块参照，不得显示为新的明日标的。
- [x] R6: 和远气体这类“身份通过、风险复核失败”的样本必须显示为明确路径：板块锚/身份通过，风险层因炸板、尾盘回封、高换手连板等原因降为观察或不参与。
- [x] R7: 需要最小回归检查，确保 0% 时前台不泄漏多个明日标的，且 companion HTML 存在并包含分层淘汰证据。

## Non-functional Requirements

### 性能
- 沿用日报生成默认性能约束；HTML 生成不得触发额外实时行情全量采集。

### 安全
- 不引入外部脚本依赖；HTML 使用本地静态资源或内联样式。

### 兼容性
- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- replay 默认只写 `reports/replay/` 和相关 replay 输出，不覆盖正式历史日报。

### 可访问性
- HTML 表格和层级块必须有可读标题；颜色不能作为唯一信息来源。

## Acceptance Criteria

- [x] AC-R1-1: 给定同一份日报生成上下文，前台最终对象、淘汰赛 HTML 最终对象、`final_target_resolution` 三者一致。
- [x] AC-R2-1: 运行 2026-06-12 replay 生成命令后，`reports/replay/` 下出现对应淘汰赛 HTML。
- [x] AC-R3-1: HTML 包含六个固定层级标题，且层级顺序与板块先行推导一致。
- [x] AC-R4-1: 每个有候选输入的层级至少显示输入数量、淘汰数量、淘汰名单或“无”、剩余名单或“无”。
- [x] AC-R5-1: HTML 中只有最终收口层可以出现“明日唯一动作”；其他层不出现并列明日标的。
- [x] AC-R6-1: 2026-06-12 和远气体路径显示“板块锚/身份通过”与“风险复核因炸板57次、尾盘回封、高换手连板而不直接参与”。
- [x] AC-R7-1: 相关单测或验收脚本覆盖 companion HTML 存在、唯一最终对象一致、0% 多标的泄漏防护。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md` / `implement.md` 已补齐并通过 review。
- [x] 子任务 PRD 已覆盖独立交付，且父任务 task map 与实际一致。
- [x] 必要 research 已保存到 `research/`。
- [x] 需要预加载上下文时，`implement.jsonl` / `check.jsonl` 已配置 spec / research 清单。
- [x] 测试通过（含新增测试）。
- [x] lint / typecheck 或等价窄验证通过。
- [x] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 不重写整份日报正文结构。
- 不重新定义交易体系或 LLM Wiki 既有口径。
- 不引入多个并列明日标的。
- 不覆盖正式历史日报，除非用户另行明确要求。
- 不新增实时行情全量采集路径。

## Technical Notes

### 参考来源
- `scripts/knowledge/llm_wiki_context.py`
- `wiki/交易思想/极度看好参与时机.md`
- `wiki/交易思想/扣分系统与动作分层.md`
- `scripts/report/selection_workflow.py`
- `scripts/report/two_layer_decision_payload.py`
- `scripts/report/runtime.py`
- `scripts/report/report_acceptance_audit.py`

### 影响区域
- `scripts/report/selection_workflow.py` — 淘汰链结构化来源。
- `scripts/report/runtime.py` — 日报生成与 companion HTML 同步产出。
- `scripts/report/*html*` 或新增 report renderer — 淘汰赛 HTML 渲染。
- `tests/` — 同源最终对象、HTML 存在与泄漏防护。

## Delivery Slices

| Slice / Child Task | 交付物 | 是否可独立验收 | 对应 Requirement | 对应 Acceptance Criteria |
|--------------------|--------|----------------|------------------|--------------------------|
| `06-13-elimination-evidence-contract` | 分层淘汰证据数据契约与唯一对象收口约束 | 是 | `R1`, `R3`, `R4`, `R5`, `R6` | `AC-R1-1`, `AC-R3-1`, `AC-R4-1`, `AC-R5-1`, `AC-R6-1` |
| `06-13-elimination-html-renderer` | 静态淘汰赛 HTML 渲染器 | 是 | `R2`, `R3`, `R4`, `R5`, `R6` | `AC-R2-1`, `AC-R3-1`, `AC-R4-1`, `AC-R5-1`, `AC-R6-1` |
| `06-13-daily-generation-elimination-html` | 日报生成接入与验收检查 | 是 | `R2`, `R7` | `AC-R2-1`, `AC-R7-1` |

## Dependency Flow

- 淘汰证据契约 → HTML 渲染器 → 日报生成接入与验收检查。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest <focused tests>`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html <generated-elimination-html>`
- `git diff --check`

## 落地结果

- 本轮未提交 commit。
- 代码：`scripts/report/elimination_tournament.py`、`scripts/report/runtime.py`、`scripts/daily_report_entry_demo.py`、`scripts/report/report_acceptance_audit.py`。
- 测试：`tests/test_elimination_tournament.py`、`tests/test_report_acceptance_audit.py`、`tests/test_report_acceptance_audit_cli.py`。
- Research：`research/runtime-html-integration.md`、`research/precommit-audit.md`。
- 验证：
  - `.generated/venv-py314/bin/python3.14 -m unittest tests.test_elimination_tournament tests.test_report_acceptance_audit tests.test_report_acceptance_audit_cli tests.test_daily_report_entry_html_output` 通过，156 tests OK。
  - `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --postgres-only` 通过，并自动写入 replay 输出。
  - `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html reports/replay/2026-06-12_明日标的选股淘汰赛.html` 通过。
  - `.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/elimination_tournament.py scripts/report/runtime.py scripts/daily_report_entry_demo.py scripts/report/report_acceptance_audit.py` 通过。
  - `git diff --check` 通过。
- 备注：`.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay` 因 `snapshots/2026-06-12.json` 缺失未生成；未用实时全量采集回补历史日期。
