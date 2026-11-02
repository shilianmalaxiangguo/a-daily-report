# A 股日报：小盘轮换 v0.3

当前唯一主策略是[小盘轮换 v0.3](wiki/交易思想/小盘轮换策略.md)。每20个交易日换手，5只名单加3只备选，只买主板和创业板；收盘相对原买价上涨10%后，下一个可卖交易日开盘卖，现金留到下次换手。账户净值底线为初始本金的0.7。

佣金为万一免五：成交额0.01%，无最低收费；过户费和卖出印花税另计。日报整手表每期以1万元重新起算，未承接旧仓、现金和原买价，不是连续账户或实际成交。当前评价窗口为2025-02-28至2026-10-29。

## 当前功能

- 当前入口只生成桌面板块阅读页，并独立显示小盘计划和市场、板块事实。
- 板块资金扩散淘汰赛只保留历史观察身份，不参与小盘选股、择时或资金分配。
- 缺失事实保留为待确认，不转成空仓、买入或卖出结论。
- 已有正式报告与快照只读；历史修复写入 replay，不覆盖正式资料。
- 旧阿尔法/贝塔建议、六项买入检查、五日退出、旧个股漏斗和其他旧组合不再日更。
- 只维护桌面页面，不恢复手机适配或手机窗口验收。

## 快速开始

所有 Python 命令使用仓库固定解释器：`.generated/venv-py314/bin/python3.14`。

```bash
# 读取正式快照并生成当前板块阅读页
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-20

# 只读取正式快照，不联网
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-20 --replay

# 只读取重建快照
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-20 --replay --snapshot-source replay

# 无快照时按目标日来源整理，只写 replay
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-20 --historical-rebuild
```

已有正式快照默认不重新采集；历史日期缺少正式快照时必须显式选择 `--replay --snapshot-source replay` 或 `--historical-rebuild`。`full` 只定位已有旧完整版，`short` 已停用。

## 当前代码入口

| 文件 | 责任 |
|---|---|
| `scripts/daily_report_current.py` | 当前命令、来源选择、快照保护和桌面阅读页 |
| `scripts/report/sector_fact_loader.py` | 目标日市场与板块事实采集 |
| `scripts/report/sector_reading_sources.py` | 补充来源和历史比较，内存只保留当前需要的字段 |
| `scripts/report/small_cap_rotation.py` | 小盘名单、备选和单期整手模拟 |
| `scripts/report/small_cap_history.py` | 小盘当前所需的冻结行情矩阵适配 |
| `scripts/report/sector_daily_report.py` | 离线板块阅读页渲染 |
| `scripts/daily_report_entry_demo.py` | 旧兼容导入；直接执行会转入当前精简入口 |
| `wiki/交易思想/回测与检验证据.md` | 当前窗口、模型身份和证据限制 |
| `references/verification.md` | 当前验证命令和历史保护要求 |

历史维护记录已移到[归档文件](docs/archive/daily-report-framework/2026-11-02/README-release-history.md)，不再作为当前入口说明加载。旧源码和旧测试仍可能为历史复核保留，但不能恢复当前交易规则。

本轮入口分离与历史保留的证据见[清理记录](docs/plans/2026-11-02-current-runtime-cleanup.md)。

阿尔法／贝塔算法、数据与回测证据保留为显式研究，不进入当前小盘执行。旧交易链、旧手机要求与历史测试的进一步隔离见[隔离记录](docs/plans/2026-11-02-small-cap-isolation.md)；查证被冻结资料须显式使用 `rg --no-ignore` 和对应路径。

## 验证

定向测试使用 Python 3.14；测试通过只说明代码路径和资料边界，不说明未来收益。提交前必须检查当前策略范围、桌面页面、正式文件哈希和 `git diff --check`。
