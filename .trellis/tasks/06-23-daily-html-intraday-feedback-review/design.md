# Design: 日报HTML盘面反馈复盘模块

## Scope And Boundaries

本次先实现 Bear/readable HTML 图卡能力：Markdown 中出现标准“盘面反馈复盘”表格时，HTML 自动生成 ECharts 复盘图。日报自动拉取分钟线和自动写入 Markdown 表格是后续接入点，不放进 HTML 渲染器里直接做。

## Contracts / Data Flow

Markdown 约定两个可选表格：

1. `盘面反馈分时点`
   - 字段：`时间`、`对象`、`代码`、`角色`、`涨跌幅`、`相对上证`
   - `角色` 可为 `上证指数`、`当前持仓`、`昨日目标`、`今日买入`、`观察对象`
   - `涨跌幅` 和 `相对上证` 支持百分号文本。

2. `盘面反馈事件`
   - 字段：`时间`、`对象`、`事件`、`价格`、`说明`
   - 用于 markLine / markPoint 标注。

同一 Markdown 段落附近可出现账户结论文本，例如：

```text
账户结论：1x满仓二选一；旧仓弱于指数，优先释放资金。
```

渲染 payload：

```python
{
    "intraday_feedback_review": {
        "items": [
            {
                "time": "09:31",
                "name": "太极实业",
                "code": "600667",
                "role": "当前持仓",
                "change_pct": -4.52,
                "relative_pct": -4.21
            }
        ],
        "events": [
            {"time": "09:48", "name": "太极实业", "event": "跌破昨低", "price": "21.40", "note": "旧仓失效"}
        ],
        "account_conclusion": "1x满仓二选一；旧仓弱于指数，优先释放资金。"
    }
}
```

## Compatibility / Migration

- 没有标准表格时，不生成图卡，不影响现有 HTML。
- 现有 Bear 图表 payload 保持原字段不变。
- 所有文本继续使用 `_html()` 和 `_json_for_html_script()` 转义。

## Tradeoffs

- 先解析 Markdown 表格而不是在 HTML 渲染阶段拉行情：优点是 replay 可复现、HTML 稳定；代价是日报生成链路仍需要后续负责产出标准表格。
- 图表先使用折线和事件标注，不做复杂 K 线或逐笔成交：优点是可读、可维护；代价是微观成交细节需要后续扩展。

## Rollback / Roll-forward

- 回滚：删除新增 payload 解析、图卡插入和模板渲染函数，现有 HTML 表格仍可正常展示。
- 继续推进：在日报生成阶段自动写入 `盘面反馈分时点` / `盘面反馈事件` 表格，并接入分钟线缓存。
