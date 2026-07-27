# Design: 创新高扩散收缩与核心补跌预警

## Scope And Boundaries

- 新增一个使用现有 `new_high_feedback` 快照计算结构字段的纯函数。
- 在《创新高趋势反馈》当前解读后插入结构判断、风险含义、反证和下一窗口。
- LLM Wiki 只记录和路由这个解释框架，路由不参与候选和明日动作。
- Bear HTML 沿用 Markdown 的四行文本，不新建第二套解释。

## Contracts / Data Flow

### 输入合同

`build_new_high_structure_signal(snapshot, target_date="")` 只读消费：

- `available`、`new_high_count`、`all_a_share_pct`、`trend_rows`、`sector_distribution`、`source`。
- 当前行优先按 `target_date` 匹配；未匹配时用最新趋势行，并返回目标日不匹配提示。
- 不读取未出现在快照中的未来行情、盘中价格或华天科技特定数据。

### 输出字段

- `current_count` / `current_pct`：当日新高数和全 A 占比。
- `previous_count` / `change_count` / `change_ratio_pct`：较前一行的数量和速度变化。
- `window_peak_count` / `peak_retention_pct`：可见趋势窗口峰值保留率。
- `single_digit` / `first_single_digit_in_window`：是否进入个位数，以及是否是可见窗口内首次。
- `sector_count` / `top_sector` / `top_sector_share_pct` / `sector_fragmented`：新高是否形成板块集群，或只是碎片化。
- `state` / `severity`：`扩散断层预警`、`扩散收缩`、`低位修复`、`扩散震荡` 或 `待累计`；只表示结构观察级别。
- `breadth_level` / `breadth_level_label`：绝对水位代码与用户可见五档。
- `previous_breadth_level` / `breadth_level_change_steps` / `breadth_direction`：把当前水位与变化方向分开，区分高位下滑和低位修复。
- `breadth_thresholds`：Markdown、Bear payload 和 ECharts 共用的阈值、档位与参考线定义。
- `summary` / `risk_note` / `counterevidence` / `next_window`：用于日报和 Bear HTML 的四行输出。

### 主要规则

- 个位数阈值为 `<10`；只有当前行可用且数据大于等于 0 时才计入。
- 绝对水位精确分层：`>=5%` 极致扩散、`>=2%且<5%` 有效扩散、`>=1%且<2%` 扩散偏冷、`>=0.2%且<1%` 极低扩散、`<0.2%` 或新高数 `<10只` 扩散断层；恰好处于阈值时归入上档。
- 百分比档位与个位数冲突时，个位数优先归为扩散断层；这只修正绝对水位标签，不直接生成交易动作。
- 变化方向独立计算：高水位下滑到低水位写扩散收缩；低水位之间数量和占比同步回升、但仍低于窗口峰值时写低位修复。
- 快速收缩使用前一行为正数且当前数量不超过前一行的 50%；该字段只作强度提示，不作交易条件。
- 板块行先按板块名称聚合再计算覆盖；板块碎片化需同时满足：有效板块至少 3 个，头部板块占比不超过 50%，且当前新高数不超过 10 只。“待补充板块”不作成群证据。
- 聚合后的板块覆盖数超过当前新高总数时，视为板块事实不一致，板块数据降为事实不足，不输出成群、碎片化或主导板块结论。
- 长期低值后当前数量回升、但仍未达到窗口峰值时，只写低位修复观察，不写周期继续收缩。
- 历史行没有逐日 `source` / `source_date` 时，跨日变化标为“来源日期不足，只作结构观察”。

## 日报数据流

```text
new_high_feedback snapshot
        |
        v
new_high_structure_signal (pure projection)
        |                         |
        v                         v
Markdown 《创新高趋势反馈》       LLM Wiki fact tag / hit
        |
        v
Bear HTML 只读最终 Markdown
```

`selection_workflow`、`final_target_resolution` 和正式仓位字段不经过这个投影。

## Compatibility / Migration

- 删除 Markdown 与 ECharts 各自保存的旧三档解释，改为 `new_high_structure.py` 输出唯一五档阈值；保留原趋势表字段名和四行结构位置。
- 无创新高快照或目标日不匹配时，继续使用原有“待累计”提示，不写虚构结构判断。
- 新增 LLM Wiki 来源路径、知识 ID 和日志不会改变旧的决策字段。

## Tradeoffs

- 将解释放在既有新高节点内，可保持首屏数据结构不变，但四行文案会增加日报高度。
- 共享纯函数会多一个模块，但可以保证 Markdown 和 Wiki 不分别定义一套结构规则。
- 不强行回填跨日同源数据，会让部分日报只能输出方向性警示，但能避免错把冲突数据当成精确结论。

## Rollback / Roll-forward

- 回滚：删除结构投影模块的调用，保留原有创新高三档解释；LLM Wiki 节点可保留为复盘知识但临时取消路由条件。
- 向前：同源历史快照齐全后，再把来源日期、板块内部宽度和核心-板块背离提升为更完整的回放字段。
