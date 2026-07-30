# Design: 日报目标日就绪检查、17:30 数据日期契约与快速重渲染

## Scope And Boundaries

本设计在既有日报入口选路基础上，补齐 ETF 成交额与融资压力的目标日期契约。修改范围限于 ETF 数据生产、输入汇总、正式生成前检查和入口选路，以及融资日期规则的回归确认；不改变报告判断链路、保存策略或数据库结构。

自动选择仅适用于“普通完整日报”：没有显式 `--postgres-only`、`--replay`、`--no-report`、`--source-health-only`、`--stock` 或 `--force-live`。其他命令保持原含义。

正式运行前提是目标交易日 17:30（Asia/Shanghai）之后启动。该时间用于定义业务场景，不新增调度器，也不在数据函数中读取系统时钟决定事实日期；所有判断仍以显式 `target_date`、`trade_date`、`source_date` 和交易日历为准。

## Contracts / Data Flow

### 路径选择结果

入口内部返回普通字典：

```python
{
    "eligible": True,
    "selected_path": "postgres_only" | "live",
    "target_date": "YYYY-MM-DD",
    "reason": "脱敏后的可读原因",
    "data": {},
    "preflight": {},
}
```

`data` 只在快速路径可用时保存，供后续生成直接复用。

### 数据流

```text
解析命令参数
  -> 判断是否属于普通完整日报
  -> 是：只读加载目标日 PostgreSQL 候选数据
       -> 现有目标事实判断失败：选择 live
       -> 现有关键数据检查失败：选择 live
       -> 两者通过：选择 postgres_only，并缓存候选数据
  -> 否：保持用户显式路径
  -> 按最终路径运行现有 source health
  -> postgres_only：使用缓存数据或现有 PostgreSQL loader
  -> live：调用现有 get_daily_data
  -> 后续报告构建、检查、保存保持原链路
```

### 目标日期事实契约

- 候选必须由 `load_daily_report_snapshot(target_date)` 按目标日期读取。
- 必须通过 `_postgres_loaded_data_has_target_facts()`；不能以其他日期的历史结构行、市场总量行或宽表外壳取得资格。
- 必须继续通过 `build_report_preflight(data, target_date)`。
- 候选检查阶段不调用实时补取；需要实时补取才完整的数据应选择 live。

### 17:30 分数据日期契约

| 数据 | 目标日为 D 时允许的最后事实日 | 17:30 正常来源 | 不满足时 |
|------|-------------------------------|----------------|----------|
| ETF 成交额 | 必须等于 D | 上一交易日已验收 PostgreSQL 历史窗口 + D 日新浪当前列表；Tushare `fund_daily(D)` 作为备用 | 继续尝试目标日备用来源；仍无 D 日事实则不可用并停止生成 |
| 融资压力 | D 或 D 的上一交易日 | 交易所/Tushare 汇总；必要时采用日期更近且来源明确的市场级备用事实 | 超过一个交易日或交易日历无法证明可用时判为不可用 |

ETF 的“目标日存在”和“覆盖正常”是两个独立条件，必须同时成立。覆盖检查不得在找不到目标日时自动把最后一行当作目标日。融资的滞后按交易日历计算，不按自然日计算。

### ETF payload 契约

ETF payload 继续保留现有字段，并明确输出：

```python
{
    "available": True,
    "requested_trade_date": "YYYY-MM-DD",
    "latest_data_date": "YYYY-MM-DD",
    "is_stale_for_target": False,
    "coverage_anomaly": False,
    "rows": [],
}
```

- `latest_data_date` 取过滤到目标日后的最后一行日期；无行时为空。
- `is_stale_for_target` 仅表示最后事实日早于请求日。
- `available` 只有在有有效行且最后事实日等于请求日时才为真；覆盖不足继续由现有 `coverage_anomaly` 独立表达，以保留诊断信息和兼容性。
- 目标日缺失不是覆盖率异常，不通过伪造 `coverage_anomaly` 表达；下游同时检查日期与覆盖两个条件。

### ETF 实时来源流

```text
加载上一交易日已验收 ETF 窗口
  -> 校验连续性和历史覆盖
  -> 尝试获取 D 日新浪历史/当前列表
       -> D 日当前列表覆盖 >= 95%：追加 D 日并重算窗口
       -> 否：尝试 Tushare fund_daily(D)
            -> D 日覆盖正常：使用 Tushare 目标日结果
            -> 否：返回不可用，关键数据不完整，停止生成
  -> 数据生产端写入请求日与最后事实日
  -> 输入汇总复核日期 + 覆盖
  -> 正式生成前检查复核日期 + 覆盖
  -> PostgreSQL 快速重渲染复核日期 + 覆盖
```

整个 ETF 分支复用现有 120 秒总预算。目标日缺失会触发已有备用来源，但不会启动无限轮询，也不会从入口重复运行整份日报。

### 最近运行契约

- 每次运行仍写 `latest_run.json`。
- 失败仍写 `latest_failure.json` 和独立的 `logs/errors/<run-key>.json`。
- 成功时移除旧 `latest_failure.json`；历史错误 JSON 和运行日志不删除。

## Compatibility / Migration

- 新增 `--force-live`，用于明确要求重新采集。
- 显式 `--postgres-only` 仍按原方式检查并读取 PostgreSQL。
- replay、no-report、source-health-only、单票诊断保持原路径。
- 正式历史存在时的实验稿切换、`--overwrite-official` 语义和报告保存位置不变。
- 不需要数据迁移。
- 旧 PostgreSQL payload 可能没有 `latest_data_date`；读取时可由 `rows` 的最后有效日期确定，但不能因字段缺失跳过日期检查。
- 当前 2026-07-27 payload 已包含目标日 ETF 行和上一交易日融资事实，按新契约仍可通过。

## Tradeoffs

- 使用现有严格 loader 与关键数据检查，可能把部分“看起来已有数据但尚不足以生成”的快照判为 live；这是有意选择，避免错误快速路径。
- 自动路径改变普通完整日报的默认数据来源，因此必须提供 `--force-live`，并在终端和运行观察信息中明确最终路径。
- 本设计不拆分 `run_input_runtime()`。当 PostgreSQL 不可用时，实时采集仍可能较慢；逐来源恢复应单独立项。
- ETF 成交额选择目标日严格一致，会让数据提供方尚未更新时更早停止生成；这是有意选择，避免把上一交易日成交额写入当日日报。
- 融资允许上一交易日，避免 17:30 运行被次日约 8:30 的正常发布时间误伤；代价是报告必须清楚保留“截至日期”和滞后交易日数。

## Rollback / Roll-forward

- 回退入口路径选择和 `--force-live` 后，普通命令恢复当前实时行为；PostgreSQL-only 显式路径仍可用。
- 回退最近运行收口后只影响排查摘要，不影响历史运行日志。
- 后续可独立设计逐来源检查点和恢复能力，不应并入本次修改。
- 回退 ETF 日期检查会重新暴露旧成交额被误收的问题，因此只允许前滚修复来源兼容性，不以放宽日期要求作为恢复手段。

## 2026-07-29 运行性能增量设计

### 历史快照读取契约

`daily_metric_history_index.py` 公开现有紧凑读取能力：

```python
load_compact_metric_history_snapshot(target_date) -> tuple[dict | None, str | None]
```

- 返回形状与 `load_data_snapshot()` 保持兼容，但只包含历史比较需要的顶层字段。
- 大于 32MB 的快照不执行整棵 `json.load()`；沿用现有头尾定位和顺序扫描逻辑。
- 紧凑字段集同时保留主线记录的单数/复数形状、板块成交快照的单数/复数形状，以及 `market_amount_yi`、`total_amount_yi`、`turnover_data` 成交额别名。
- 主线历史、板块成交历史和板块资金历史在默认生产 loader 未被替换时调用该公开函数。
- 测试或调用方通过 `helpers` 替换 `load_data_snapshot` 时，继续调用注入 loader；该行为是现有测试和 replay 夹具的兼容边界。
- PostgreSQL-only 路径保持现有行为；数据库历史不足时也不读取主线 series replay 或其他 JSON。

### 阶段耗时契约

入口维护一组非重叠阶段记录，每次完成一个阶段就保存阶段名和秒数：

```python
[
    {"phase": "参数解析与目标日事实判断", "elapsed_seconds": 0.12},
    {"phase": "数据源检查", "elapsed_seconds": 1.23},
]
```

成功运行的耗时表至少区分：

1. 参数解析与目标日事实判断。
2. 数据源检查。
3. 数据读取与生成前检查。
4. 日报构建与首次检查。
5. 事实同步与 Bear 复核。
6. 产物保存与附属页面。
7. Bear 落盘与快照保存。
8. 其他收尾。

`其他收尾 = 总耗时 - 已记录阶段合计`，用于吸收计时调用、日志拼装等微小差额。运行日志显示秒数和占比；运行观察信息保存同一份紧凑列表。阶段统计只观察既有顺序，不改变任何报告数据或判断。

数据读取返回空字典或非字典载荷时，入口在补充默认日期字段前认定关键数据不完整，记录失败并停止生成；这种运行不能以成功状态返回，也不伪造阶段耗时。

### 性能边界与取舍

- 固定验收对象是约 1.2GB 的 `snapshots/2026-07-22.json`：低于 30 秒、峰值物理内存低于 1GB。
- 不并发外部请求。当前最大单源为选股通 63.14 秒，但直接并发会引入限流、失败传播和结果顺序风险，不属于本轮最小修复。
- 不承诺实时全流程固定时长；网络数据源仍会波动。阶段表提供后续优化所需的事实基线。
- 紧凑读取失败时沿用“缺失该日历史事实”的既有处理，不退回完整 1GB 快照解码，以免重新引入本次根因。
