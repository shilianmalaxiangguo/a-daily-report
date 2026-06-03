# Snap UI Public Data Node Design

## Goal

把 `snap-ui` 线上依赖的数据生产纳入日报生成流程，使用 Tushare 作为主数据源，并在任何线上发布动作前完成数据完整性检查、manifest 记录和任务清单打勾。

## In Scope

- 在日报生成链路中新增 `publish.snap_ui_public_data` 节点，位置在快照保存之后、线上发布之前。
- 节点优先使用 Tushare 生成 `snap-ui` 所需数据，不自动切到东财、iwencai 或 akshare。
- 节点产出 `snap-ui_publish_manifest.json`，记录目标日期、数据源、行数、artifact 路径、hash、检查结果和同步结果。
- 节点产出 `snap-ui_publish_tasks.md`，每一步使用 checkbox 记录，完成一步打勾一步。
- 节点执行本地数据完整性检查；检查失败时停止线上发布步骤。
- 日报 CLI 继续可以生成本地报告和快照，但 `snap-ui` 发布状态必须明确标记为未完成。

## Out of Scope

- 不重构整个日报生成系统。
- 不把前端仓库变成数据生产入口。
- 不新增自动 Cloudflare Pages 部署动作。
- 不改变已有日报正文生成逻辑。

## Non-goals

- 不追求一次性覆盖所有未来 UI 数据形态。
- 不引入新的调度系统。
- 不替代现有 D1/R2 同步脚本，只把它们纳入可检查的节点产物。

## Architecture

新增一个小而明确的发布数据节点：

```text
daily_report_entry_demo.py
  -> _save_data_snapshot(...)
  -> publish.snap_ui_public_data
      -> Tushare turnover pipeline
      -> snap-ui static export
      -> local data contract check
      -> manifest + task checklist
```

节点本身只做编排和证据记录。Tushare 拉取、D1-compatible 写入、R2 artifact 生成继续由已有 pipeline/storage/export 服务负责；`snap-ui` 静态数据导出继续调用前端仓库已有的 `npm run export:static-data`。

## Data Flow

1. 输入目标日期和运行模式。
2. 运行 Tushare turnover pipeline，刷新目标日期相关行情、成交额排行和 Top50 占比 artifact。
3. 调用 `snap-ui` 静态导出，把日报、主线成交额排行、观察池和 Top50 静态 JSON 写到 `snap-ui/public/data`。
4. 执行本地 contract check，验证 `snap-ui` 线上所需关键数据存在且日期正确。
5. 写入 manifest 和 task checklist 到 `.generated/snap-ui-public-data/<date>/`。
6. 任一关键步骤失败时，manifest 标记 `failed`，task list 停在失败步骤，节点抛错阻止线上发布步骤继续。

## Failure Policy

- Tushare 返回空数据、Top50 artifact 缺行、静态导出失败、contract check 失败都算发布数据不完整。
- 数据不完整时不允许推送 `snap-ui/develop` 作为发布完成。
- 节点错误信息必须指向失败步骤和 artifact 路径，方便重跑。

## Task Checklist Format

`snap-ui_publish_tasks.md` 示例：

```markdown
# Snap UI Public Data Tasks - 2026-05-12

- [x] Resolve target date
- [x] Fetch Tushare turnover data
- [x] Build D1-compatible records
- [x] Export R2/D1 artifacts
- [x] Export snap-ui static data
- [x] Run local data contract check
- [x] Write publish manifest
```

失败时最后一步保持未完成，并追加 `Failure:` 行。

## Testing

- Python 单测覆盖节点成功路径：用 fake Tushare / fake command runner / 临时目录，断言 manifest、task list 和 artifact 摘要。
- Python 单测覆盖失败路径：contract check 失败时节点抛错，manifest 标记 failed，task list 保留未完成项。
- 现有 Tushare turnover pipeline 测试继续覆盖数据拉取与 artifact 生成。
- `snap-ui` 自身的 public static data contract test 继续作为发布前检查命令。

## Done Definition

- 日报流程能调用 `publish.snap_ui_public_data` 节点。
- 节点能生成 `snap-ui_publish_manifest.json` 和 `snap-ui_publish_tasks.md`。
- 本地 contract check 失败会阻止线上发布步骤。
- 所有新增 Python 单测通过。
- 现有 turnover pipeline 相关单测通过。
