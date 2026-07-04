# 回测 HTML 样式锚点

这份说明用于防止板块资金扩散前向回测 HTML 在后续修改中偏离当前日报阅读样式。

## 样式来源

- 回测 HTML 必须复用 `scripts/templates/daily_report_markdown_reader.html` 的 reader 样式。
- 回测只允许在 `scripts/replay/sector_forward_replay.py` 中追加少量回测专用覆盖样式。
- 页面结构保持 `bear-shell`、`outline-sidebar`、`reader-document`、`markdown-body`、`bear-chart-card`。

## 必须保留的视觉特征

- `区间说明` 使用 `bear-section-map`。
- `回测摘要` 使用 `bear-section-action`。
- 图表卡片使用日报当前的暖色阅读风格，不恢复旧 dashboard 风格。
- `买入 / 卖出时间矩阵` 使用浅底热力图：数值越大颜色越深，较高组合用描边和星号强调，不把整张图染成单一黄色。
- `区间收益与月度折算参考` 的图例必须是标题区 HTML 图例，不使用 ECharts 内置图例。
- 正收益图例使用日报主题红；负收益图例和负值柱使用微信绿 `#07C160`。
- 图 2 柱体保持直角，不加圆角。
- 图 2 内不能出现旧蓝色系列图例。

## 自动检查

修改回测 HTML 样式后至少运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_sector_forward_replay tests.test_daily_report_markdown_html
```

当前测试会检查：

- 回测 HTML 复用日报 reader 样式变量。
- 图 2 的 HTML 图例限定在 `replay-window-metrics` 图卡内。
- 图 2 的 ECharts 内置图例保持隐藏。
- 负收益色块保留 `#07C160`。
- 图 2 不恢复旧蓝色图例配置。
- 矩阵热力图保留当前正负色阶和较高组合描边。

## 目测预览

需要人工对照时，生成固定样本预览：

```bash
.generated/venv-py314/bin/python3.14 scripts/replay/sector_forward_replay_style_preview.py
```

默认输出：

```text
reports/replay/_style_anchor_sector_forward_replay.html
```

这个文件是临时预览产物，不需要提交。目测时重点看：

- 整体是否仍像当前日报 reader，而不是旧后台报表。
- 图 2 图例是否显示为 `正收益 / 负收益`。
- 负收益色块和负值柱是否为微信绿。
- 图 2 柱体是否是直角。
- 矩阵是否像热点图，深浅随数值变化。
- 图表卡片、表格、标题层级是否与日报阅读样式一致。
