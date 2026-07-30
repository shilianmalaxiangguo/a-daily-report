# Research: 超大快照根因与 PostgreSQL 覆盖摘要

## Question

每日约 1.3GB JSON 是否必要，它是否是日报变慢的主要原因，以及 PostgreSQL 现在能否完全替代它？

## Sources

- `scripts/report/runtime.py:11263`
- `scripts/report/runtime.py:12283`
- `scripts/daily_report_snapshot_io.py:85`
- `scripts/daily_report_snapshot_io.py:288`
- `scripts/daily_report_entry_demo.py:1943`
- `scripts/replay/report_replay.py:2801`
- `scripts/storage/postgres_daily_fact_db.py:1391`
- `snap-ui/server/utils/snapshot/loadSnapshot.ts:7`
- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/tasks/07-28-daily-report-readiness-fast-render/research/20260728-runtime-performance.md`

## Findings

- `2026-07-28.json` 为 `1,401,954,582` 字节；`execution_stage_context` 约占 99.45%，其中内嵌 `data` 约占 98%。
- 修复前运行期上下文保存完整 `data`，随后上下文又写回 `data`，形成直接自引用；当前代码在最终持久化边界生成不含 `data` 和可调用对象的副本。
- 修复前 `_make_serializable()` 没有当前递归路径识别，只按 50 层停止，因此相同大对象被重复展开；当前代码已增加当前递归路径识别。
- 切断该引用后，按现有字段估算快照约为 28MB 量级；1.3GB 不是业务事实的必要体积。
- 2026-07-28 正式与 replay 快照合计约 2.806GB；`snapshots/` 共约 30.944GB，11 个文件超过 1GB。
- 运行时对旧 1.2GB JSON 完整解码时峰值内存约 12.3GB；紧凑字段读取复测低于 30 秒且峰值低于 1GB。超大 JSON 是已确认的主要程序瓶颈之一。
- 2026-07-28 PostgreSQL 有约 30,310 个日报字段，纯数据库载荷的生成前检查可以通过，足以支持近期正式日报快速重渲染。
- PostgreSQL 当前不能完全替代 replay：入口仍强制官方 JSON 基线，冻结知识引用、补充观察和部分必要明细尚未完整入库。
- snap-ui、发布器、判断复盘、前瞻复盘和部分导出器仍直接读取完整 JSON。
- 完整 JSON 在 PostgreSQL 同步成功后才写，因此它不是数据库当场不可用时的生成保障，只是后续恢复副本和旧消费入口。

## Recommendation

采用分阶段迁移：立即切断循环并限制新快照为 64MiB；随后让 PostgreSQL 成为 replay 起点、补齐冻结事实并迁移下游消费者；逐字段验收通过后停止新增完整 JSON。旧档案不在本任务中直接删除，先输出清理预演并获得用户确认。

## Impact

- PRD: 增加 64MiB 过渡上限、PostgreSQL replay、消费者迁移和删除确认要求。
- Design: 保留旧 reader 作为兼容 adapter，不直接删除 `_save_data_snapshot()`。
- Implementation: 先完成循环与原子写入保护，再推进 replay 和消费者迁移。
