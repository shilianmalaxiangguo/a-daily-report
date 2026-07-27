# Design: Bear 日报最近25日 T0市场底色图

## Scope And Boundaries

本任务只在最终 Bear / Markdown 阅读页接入图表。图表作为市场环境证据，位置在“指数与市场底色”段落内；它不参与候选、最终对象、仓位或任何盘中动作计算。

## Contracts / Data Flow

```text
PostgreSQL 历史事实
  -> Bear 市场底色载荷（最多25个交易日）
  -> render_markdown_report_html(..., t0_market_breadth=...)
  -> bear-chart-payload + 图卡
  -> daily_report_markdown_reader.html ECharts
```

载荷使用 `t0_market_breadth.v1`：

```python
{
    "items": [
        {
            "date": "YYYY-MM-DD",
            "up_count": int | None,
            "down_count": int | None,
            "all_a_change_pct": float | None,
            "new_high_share_pct": float | None,
        },
    ],
    "title": "T0市场底色",
    "subtitle": "上涨和下跌家数看宽度，双线看全A涨跌幅与创新高扩散。",
}
```

- 查询 26 根全A指数日线，计算后 25 个交易日的涨跌幅；这样首个展示日也能获得前收。
- 以目标日为上界过滤全部事实，按日期升序取最后 25 个交易日。
- 每项历史事实保留其日期约束；无法匹配目标日期的值不进入载荷。
- 缺失值为 `None`，由 ECharts 断点显示，绝不转换为 0。
- 图形复用前向回测的语义：上涨家数正向柱、下跌家数微信绿负向柱、全A涨跌幅与创新高占比双折线；下跌家数以 `-4000` 表示 4000 家阈值，并显示 `4000+下跌` 标线。家数轴至少保留至 `-4200`，真实数据更低时继续随数据扩展，保证阈值线不会因温和窗口的自动缩放而消失或贴住底边。

## Compatibility / Migration

- `render_markdown_report_html()` 和文件渲染函数的新增参数可选；调用方未提供数据时 HTML 保持原样。
- 现有 Markdown 正文与图表解析载荷保持兼容，新增图表不依赖向 Markdown 写入新的事实表。
- 不变更数据库表、快照格式或正式日报的决策字段。

## Tradeoffs

- 不从现有 Markdown 表格反推 25 日宽度：该表没有完整历史涨跌家数与全A涨跌幅，会导致事实缺失或误补。
- 不改独立驾驶舱：该产物不在最终 Bear 日报的生成路径。
- 不抽取新的共享模块：当前只增加一个 Bear 消费者，使用现有数据库服务接口完成最小闭环。

## Rollback / Roll-forward

- 回滚仅移除可选载荷、图卡和模板分支；报告正文与数据库事实均未变更。
- 若历史事实读取异常，保持原有 Bear 页面，不用实时数据替代历史数据。
