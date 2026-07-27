# Implementation: Bear 日报最近25日 T0市场底色图

## Prerequisites

- PostgreSQL 同步成功后才构建图表历史事实。
- 使用固定 Python 3.14 运行全部检查。

## Ordered Checklist

- [x] I1: 确认现有数据库服务查询的返回字段和日期约束，构建最多 25 个交易日的 Bear 市场底色载荷。
- [x] I2: 将可选载荷从日报入口传入 Bear 渲染器，保持保存后 HTML 重建链路一致。
- [x] I3: 在 Bear 渲染器将图卡插到“指数与市场底色”标题后，并把载荷写入 `bear-chart-payload`。
- [x] I4: 在 Markdown 阅读页模板增加 ECharts 渲染分支与窄屏样式复用，并为下跌家数设置微信绿和 `4000+下跌` 阈值标线。
- [x] I5: 添加最小单元与保存链路测试，覆盖 25 日窗口、未来日期过滤、空值和决策字段不变。
- [ ] I6: 运行目标测试、replay 生成与桌面/窄屏浏览器检查。

I6 当前状态：目标测试与 replay 生成已完成，中断续跑后的核心回归与最终载荷解析也已再次通过；桌面/窄屏浏览器检查因内置浏览器不允许访问本地 `file://` 页面而未完成。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render tests.test_report_replay`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <date> --replay`

## Risk And Rollback Points

- 历史序列必须按目标日裁剪，不能把目标日之后的事实带入回放。
- 全A涨跌幅首项依赖前收；查询窗口少一根会造成首项缺失。
- 既有工作区在 Bear 渲染、模板与日报入口上有未提交改动；只做局部补丁，不回退或格式化相邻代码。

## Review Checkpoints

- 数据载荷与前向回测图的四组数据语义一致。
- 图卡属于证据区，位于动作结论之后。
- 正式决策投影前后逐字段一致。
