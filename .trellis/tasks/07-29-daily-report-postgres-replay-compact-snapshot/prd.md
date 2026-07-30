# 日报 PostgreSQL replay 与紧凑快照迁移

状态：🔨 进行中

## Goal

消除日报完整 JSON 的异常膨胀和历史读取成本，让 PostgreSQL 成为正式事实与 replay 的主要来源，并在迁移期间只保留有明确尺寸上限的紧凑灾备产物。

## User Story

- **角色**：日报生成与历史修复使用者
- **场景**：生成当日日报、重新渲染历史日报或修复历史日期
- **目标**：无需读取或写入 GB 级 JSON，也能从目标日期事实稳定生成 Markdown、Bear HTML 和 replay 结果
- **成功标准**：新快照不会超过约定上限；PostgreSQL-only replay 与旧基线的核心判断逐字段一致；完成迁移后停止新增完整 JSON

### 用户旅程

1. 用户生成当日日报，系统先写入 PostgreSQL 正式事实，再写入尺寸受控的过渡快照。
2. 用户修复历史日报，系统按目标日期从 PostgreSQL 构建 replay，不扫描完整历史 JSON。
3. 旧 JSON 仅用于一次性迁移或手工修复；迁移验收完成后，系统不再新增完整 JSON。

## What I Already Know

- `snapshots/2026-07-28.json` 为 `1,401,954,582` 字节，其中 `execution_stage_context` 占约 99.45%。
- `execution_stage_context` 保存完整 `data`，之后又被写回 `data`，形成自引用；序列化器只按 50 层停止，没有识别当前递归路径。
- 正式与 replay 两份 2026-07-28 快照合计约 2.806GB；`snapshots/` 现有约 30.944GB，11 个文件超过 1GB。
- PostgreSQL 已能支撑近期正式日报快速重渲染，2026-07-28 的生成前检查可通过。
- 当前 replay 仍以官方 JSON 为起点；冻结知识引用、补充观察及部分明细尚未完整进入 PostgreSQL。
- snap-ui、日报分层发布器、判断复盘和部分导出器仍直接消费完整 JSON。

## Requirements

- [x] R1: 运行期执行上下文不得把完整日报对象或函数引用写回持久化数据；通用序列化器必须识别当前递归路径中的循环引用。
- [x] R2: 过渡期快照必须原子写入并受 64MiB 上限保护；超限时不得留下新文件、截断文件或覆盖已有快照。
- [ ] R3: PostgreSQL 必须成为目标日期 replay 的首选基线；数据库事实缺失时明确停止或使用显式旧档案兼容路径，不得混入当前实时事实。
- [ ] R4: replay 所需但当前缺失的冻结知识引用、补充观察、来源日期与必要明细必须以紧凑事实形式持久化。
- [ ] R5: replay 检查、判断复盘、前瞻复盘、snap-ui、发布器和必要导出器必须迁移到 PostgreSQL 或专用紧凑投影，不再整文件解码完整 JSON。
- [ ] R6: 停止新增完整 JSON 前，必须完成同日期双路径验收，确认最终对象、仓位、执行性质、B1/B2、退出动作和来源日期逐字段一致。
- [x] R7: 主日报入口每次保存正式或 replay 快照时，必须记录目标路径、实际字节数、请求模式、实际模式和是否受限停止；日志不得包含完整业务载荷或数据库凭证。
- [ ] R8: 历史大文件只读保留，删除、覆盖或批量压缩必须另行获得用户确认，并先提供可回收空间预演。

## Non-functional Requirements

### 性能

- 新增过渡快照不得超过 64MiB；正常样本目标控制在 32MiB 左右。
- 循环引用必须在首次回到当前递归路径时停止，不得依赖 50 层展开后才停止。
- PostgreSQL replay 的目标日期基线加载不得扫描 `snapshots/*.json` 或 `snapshots/replay/*_replay.json`。
- 以 2026-07-28 为验收日期，完整 PostgreSQL-only replay 目标在 180 秒内完成；外部服务不计入该路径。

### 安全

- 原子写入失败、尺寸超限或 PostgreSQL 事实不完整时保留已有正式产物，不写半成品。
- 数据库错误与日志沿用现有脱敏规则。

### 兼容性

- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 旧官方 JSON reader 暂时保留为一次性导入和手工修复兼容入口。
- 不改变报告判断逻辑、候选池、明日对象、仓位、执行性质、B1/B2 或退出动作。

## Acceptance Criteria

- [x] AC-R1-1: 给定 `data -> execution_stage_context -> data` 的循环引用，序列化结果只出现一次循环占位，不重复展开 50 层。
- [x] AC-R1-2: 给定真实执行上下文，保存到 `data.execution_stage_context` 的结构不包含 `data` 键和可调用对象，同时保留候选、决策和执行输出。
- [x] AC-R2-1: 给定小于 64MiB 的快照，保存后可被现有 loader 读取，且目标文件通过完整 JSON 解析。
- [x] AC-R2-2: 给定超过上限的快照，保存抛出明确错误，目标文件不存在或保持原字节不变，临时文件被清理。
- [ ] AC-R3-1: 给定目标日期 PostgreSQL 事实完整且无官方 JSON，replay 能生成 Markdown 和 Bear HTML，不调用实时采集或完整 JSON loader。
- [ ] AC-R3-2: 给定 PostgreSQL 目标日期事实缺失，replay 明确列出缺失事实并停止，不从当前日期事实补历史日期。
- [ ] AC-R4-1: 冻结知识引用和补充观察经过 PostgreSQL 保存、读取后，目标日期、来源日期和正文内容保持一致。
- [ ] AC-R5-1: PostgreSQL-only replay 的消费链在测试中若调用完整 JSON loader 则失败；snap-ui 与发布器读取专用紧凑投影。
- [ ] AC-R6-1: 2026-07-28 双路径比较中，最终对象、仓位、执行性质、B1/B2、退出动作和来源日期逐字段一致。
- [x] AC-R7-1: 主日报入口的运行观察信息包含快照字节数、请求模式、实际模式和保存结果，但不包含完整载荷、连接串或凭证。
- [ ] AC-R8-1: 清理命令默认只输出候选文件、总字节数和预计可回收空间，不执行删除或覆盖。

## Definition Of Done

- [ ] Requirements 全部完成。
- [ ] Acceptance Criteria 全部通过。
- [x] `design.md`、`implement.md` 和根因研究已补齐。
- [x] `implement.jsonl`、`check.jsonl` 已配置必要 Spec 与研究摘要。
- [ ] 新增和相关既有测试使用 Python 3.14 通过。
- [ ] 提交前独立审计在 10 分钟总墙钟预算内完成，发现已处理或明确记录。
- [ ] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 本轮不删除、覆盖或就地压缩任何历史快照。
- 第一阶段不修改 PostgreSQL 表结构；缺失事实先验证能否复用现有结构化表或紧凑字段存储。
- 不为了迁移存储而改变交易判断、报告阅读结构或候选生成逻辑。
- 不把原始响应树、运行日志、缓存、分钟级大载荷整体写入 PostgreSQL。
- 不在同一改动中重写全部 snap-ui 接口或发布页面。

## Source Of Truth

当前 replay 基线仍是旧官方 JSON；这项现状在 R3-R5 验收前保持不变。R3-R5 完成后的目标态以目标日期 PostgreSQL 结构化事实、已验收的日报判断字段和明确带有 `trade_date/source_date/query_date` 的来源为准，旧 JSON 届时只作为迁移与兼容证据，不再承担日常查询主来源。

## Root Cause

- **现象**：单日正式快照达到约 1.3GB，生成与历史读取耗时显著增加，磁盘持续增长。
- **根因**：运行期执行上下文保存完整 `data`，随后上下文又写回 `data`；序列化器未识别循环引用，只在 50 层后停止。
- **影响范围**：正式与 replay 快照保存、历史 replay、snap-ui、发布器、磁盘占用和 Python 进程内存。

## Reproduction

1. 构造 `data = {}` 和 `context = {"data": data}`，再执行 `data["execution_stage_context"] = context`。
2. 调用现有 `_make_serializable(data)` 并写 JSON。
3. 预期：循环引用立即停止，产物保持紧凑；实际：结构重复展开至 50 层，真实日报膨胀到约 1.3GB。

## Fix Strategy

- **修改点**：执行上下文持久化边界、快照序列化与写入边界、replay 数据入口和下游消费者。
- **修改方式**：先切断循环并增加原子尺寸保护，再迁移 PostgreSQL replay 与紧凑投影，最后停止新增完整 JSON。
- **风险评估**：高。replay、历史保护、snap-ui 和发布器共享旧快照契约，必须分阶段验收。

## Regression Guard

- 新增循环引用、共享引用、超限写入、已有文件保护和临时文件清理测试。
- 新增 PostgreSQL-only replay 不读取 JSON 的反例测试。
- 新增正式与 replay 核心判断逐字段一致性测试。
- 新增 snap-ui、发布器紧凑投影契约测试。

## Metrics

| 指标 | 基线 | 目标 | 测量方式 |
|------|-----:|-----:|----------|
| 2026-07-28 正式快照 | 1,401,954,582 字节 | 过渡期不超过 64MiB | `stat` 与保存日志 |
| 正式 + replay 单日快照 | 约 2.806GB | 过渡期不超过 128MiB | 目标日期文件合计 |
| `snapshots/` 总量 | 约 30.944GB | 停止新增 GB 级文件 | 每日尺寸清单 |
| 历史读取峰值内存 | 约 12.3GB | 小于 1GB | `/usr/bin/time -l` |
| PostgreSQL-only replay | 当前不能独立完成 | 2026-07-28 在 180 秒内完成 | 固定日期 replay 演练 |

## Delivery Slices

| Slice | 交付物 | 可独立验收 | 对应 Requirement |
|-------|--------|------------|------------------|
| S1 | 循环引用修复、运行期引用清理、64MiB 原子写入保护 | 是 | `R1`, `R2`, `R7` |
| S2 | PostgreSQL replay 起点与缺失冻结事实持久化 | 是 | `R3`, `R4`, `R6` |
| S3 | replay、snap-ui、发布器与导出器迁移到紧凑来源 | 是 | `R5`, `R6` |
| S4 | 停止新增完整 JSON 与历史清理预演 | 是，且删除需另行确认 | `R6`, `R8` |

执行顺序：S1 → S2 → S3 → S4。S1 立即阻止继续产生异常文件；S2 与 S3 验收通过前不直接移除旧兼容入口。

## Technical Notes

### 参考来源

- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/spec/backend/error-handling.md`
- `.trellis/spec/guides/cross-layer-thinking-guide.md`
- `.trellis/tasks/07-28-daily-report-readiness-fast-render/research/20260728-runtime-performance.md`
- `research/snapshot-root-cause-and-postgres-coverage-summary.md`

### 影响区域

- `scripts/report/runtime.py`：运行期执行上下文持久化边界。
- `scripts/daily_report_snapshot_io.py`：循环识别、原子写入和尺寸限制。
- `scripts/replay/report_replay.py`：PostgreSQL replay 起点。
- `scripts/storage/postgres_daily_fact_db.py`：缺失冻结事实的紧凑持久化。
- `scripts/daily_report_source_health.py`：replay 来源完整性检查。
- `snap-ui/server/`：专用紧凑查询投影。
- `scripts/report_onion/publisher.py`：发布器紧凑输入。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_snapshot_io tests.test_report_runtime`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_replay tests.test_daily_report_source_health tests.test_postgres_daily_fact_db`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-28 --replay`
- 对正式与 replay 产物运行日报一致性检查并比较核心判断字段。
- `git diff --check HEAD`

## 落地 commit

本轮按用户要求不提交。
