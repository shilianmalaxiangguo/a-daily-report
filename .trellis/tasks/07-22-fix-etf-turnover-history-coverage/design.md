# Design: 修复ETF成交额历史覆盖并生成20260722日报

## Scope And Boundaries

本次只调整 ETF 两市成交额 25 日趋势的事实来源组合与 Tushare 备用分页参数。完整性判断仍由现有 `_annotate_etf_turnover_coverage_quality()` 负责，日报渲染、选股、仓位和执行动作不变。

数据流：

```text
上一交易日 PostgreSQL 已验收 ETF 窗口
  -> 校验精确上一交易日、连续日期、正常覆盖
  -> 取最近 24 日
目标日新浪 ETF 当前列表
  -> 校验正成交样本覆盖 >= 95%
  -> 汇总目标日成交额
两者合并
  -> 补充逐行来源日期
  -> 重算日变化
  -> 重新执行 70%/95% 完整性检查
  -> 输入运行 / 日报生成前检查 / PostgreSQL 保存 / Markdown / Bear HTML
```

## Contracts / Data Flow

### 历史窗口输入

- 来源必须是精确上一交易日的 PostgreSQL 日报事实。
- payload 必须 `coverage_anomaly=False`，且 `coverage_status` 不是 `partial/empty`。
- 行日期必须覆盖交易日历要求的最近 `window_days - 1` 日，最后一行等于上一交易日。
- 每行成交额和有成交 ETF 数必须为正。

### 目标日输入

- 仅当 `target_date` 等于当前日期时使用新浪 ETF 当前列表。
- 正成交数 / 当前样本池总数必须不低于 95%。
- 目标日成交额、正成交数、样本池总数和来源日期必须保留。

### 合并输出

- 固定返回最多 `window_days` 行，按交易日升序。
- 历史行：`source=上一窗口上游来源`、`source_date=trade_date`、`query_date=上一交易日`。
- 目标行：`source=sina.etf.category_current_amount`、`source_date=target_date`、`query_date=当前日期`。
- 顶层来源标记 PostgreSQL 历史事实与新浪目标日列表的组合，并记录上一事实日期。
- 合并后重新运行现有完整性检查；不能直接继承上一日的成功状态。

### Tushare 备用来源

- 首次分页不传 `offset=0`；只有第二页开始才传正 offset。
- 区间请求为空时可以逐日尝试，但只有完整覆盖全部目标交易日才可用。
- Tushare 备用不影响 PostgreSQL + 新浪当前列表的优先路径。

## Compatibility / Migration

- 保留现有字段：`available`、`source`、`requested_trade_date`、`usable_etf_count`、`empty_etf_count`、覆盖质量字段和 `rows`。
- 新增字段仅补充来源和历史事实日期，旧消费者可忽略。
- 不迁移旧快照、不改数据库结构；新字段继续由通用日报事实字段表保存。

## Tradeoffs

- 选择上一交易日已验收窗口而非逐只查询 1607 只 ETF：生成更快，且沿用已有正式事实；代价是首次启用或历史断档时仍会停止生成。
- 不移除历史序列完整性检查：避免用看似平滑但漏掉大量 ETF 的总额作机构容量判断。
- 不把当前 1607 只样本池直接当作每个历史日期的唯一真值；本次窗口本身已在上一交易日通过检查，合并后仍会用当前池重新验证最近 24 日不低于 95%。

## Rollback / Roll-forward

- 回滚：移除本次 ETF 历史续接 helper 和对应调用，恢复原新浪历史 -> Tushare 备用顺序；不涉及数据库回滚。
- 前滚：若未来需要脱离日报快照，可新增专门的 ETF 逐日聚合事实表；不在本次范围内。
