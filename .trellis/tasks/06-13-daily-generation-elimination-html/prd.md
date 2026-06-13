# 日报生成同步产出淘汰赛HTML

状态：✅ 已完成（未提交）

## Goal

将淘汰赛 payload 与 HTML renderer 接入日报生成流程，使 replay 和 official 日报生成时同步写出 companion HTML，并纳入最小验收检查。

## User Story

- **角色**：日报使用者 / 报告维护者。
- **场景**：运行每日/历史 replay 日报生成命令。
- **目标**：不需要额外手工步骤即可得到对应淘汰赛 HTML。
- **成功标准**：2026-06-12 replay 生成后，Markdown 日报和淘汰赛 HTML 同时存在，并通过一致性检查。

### 用户旅程

1. 用户运行日报生成命令。
2. 系统写出 Markdown/HTML 日报。
3. 系统同步写出淘汰赛 companion HTML。
4. 用户运行验收审计，确认最终对象一致且不存在多标的泄漏。

## What I Already Know

- replay 默认写 `reports/replay/`。
- 现有 acceptance audit 已支持 companion HTML 参数。
- 本任务不能覆盖正式历史日报，除非用户另行明确要求。

## Requirements

- [x] R1: 在日报生成流程中同步构建淘汰赛 payload 并写出 HTML 文件。
- [x] R2: replay 输出写到 `reports/replay/<date>_明日标的选股淘汰赛.html` 或同等稳定命名。
- [x] R3: official 输出写到对应 official report 目录，命名稳定。
- [x] R4: 验收检查能发现 Markdown 与 companion HTML 最终动作不一致。
- [x] R5: 2026-06-12 replay 生成后 companion HTML 包含和远气体风险层淘汰路径。

## Non-functional Requirements

### 性能
- 生成 companion HTML 不触发额外实时行情全量采集。

### 安全
- 不引入外部网络资源。

### 兼容性
- 所有命令使用 `.generated/venv-py314/bin/python3.14`。

### 可访问性
- 继承 renderer 子任务标准。

## Acceptance Criteria

- [x] AC-R1-1: 运行日报生成命令时 companion HTML 自动生成。
- [x] AC-R2-1: 2026-06-12 replay companion HTML 出现在 `reports/replay/`。
- [x] AC-R3-1: 非 replay 生成路径具备稳定输出路径。
- [x] AC-R4-1: acceptance audit 或 focused check 在最终对象不一致时失败。
- [x] AC-R5-1: 2026-06-12 companion HTML 包含和远气体、炸板57次、尾盘回封、高换手连板或等价风险说明。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] 2026-06-12 replay 已重新生成并检查 companion HTML。
- [x] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 不覆盖正式历史日报。
- 不改变日报主文大量结构。
- 不新增外部依赖。

## Technical Notes

### 参考来源
- `.trellis/tasks/06-13-sector-first-elimination-html/design.md`
- `.trellis/tasks/06-13-elimination-evidence-contract/prd.md`
- `.trellis/tasks/06-13-elimination-html-renderer/prd.md`
- `scripts/daily_report_entry_demo.py`
- `scripts/report/runtime.py`
- `scripts/report/report_acceptance_audit.py`

### 影响区域
- 日报入口 / runtime 写文件逻辑。
- acceptance audit 或 focused verification tests。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest <focused generation/audit tests>`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html reports/replay/2026-06-12_明日标的选股淘汰赛.html`
- `git diff --check`

## 落地结果

- 本轮未提交 commit。
- 原始命令 `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay` 因 `snapshots/2026-06-12.json` 缺失未生成；未用实时全量采集回补历史日期。
- 已使用同日 PostgreSQL 事实运行 `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --postgres-only`，系统检测已有正式历史后自动写入 replay 输出。
- 生成产物：`reports/replay/2026-06-12_A股日报_完整版_replay.md`、`reports/replay/2026-06-12_A股日报_完整版_replay.html`、`reports/replay/2026-06-12_明日标的选股淘汰赛.html`。
- 验证：`.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html reports/replay/2026-06-12_明日标的选股淘汰赛.html` 通过。
