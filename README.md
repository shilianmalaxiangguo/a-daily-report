# A 股日报：小盘轮换 v0.3

现在只执行小盘轮换。旧阿尔法／贝塔保留为独立备用研究；淘汰赛、旧仓位、买点和固定买卖日历已移出运行目录。

## 先看哪里

| 需要做什么 | 位置 |
|---|---|
| 看懂整个文件夹 | [目录地图](docs/structure.md) |
| 核对当前买卖规则 | [小盘轮换 v0.3](wiki/交易思想/小盘轮换策略.md) |
| 看净值1开始的五只模拟跟踪 | [连续模拟说明](docs/small-cap-tracking.md) |
| 核对回测数字和账户差异 | [回测证据](wiki/交易思想/回测与检验证据.md) |
| 查本次删了什么 | [清理记录](docs/cleanup-2026-11-02.md) |
| 查旧方法的精华和原代码 | [归档索引](docs/archive/README.md) |
| 以后研究阿尔法／贝塔 | [备用研究说明](docs/research/alpha-beta/README.md) |

## 常用命令

所有 Python 命令固定使用 `.generated/venv-py314/bin/python3.14`。依赖清单在 `requirements.txt`；数据和环境保留在本机，不随源码发布。

```bash
# 离线读取已核对具有v0.3计划的重建快照
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-30 --replay --snapshot-source replay

# 正式来源（必须已有当前版本计划，否则明确停止）
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py YYYY-MM-DD --replay

# 当日无正式快照时，采集行情、财报、日历与对照指数
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py YYYY-MM-DD

# 重绘已有冻结回测比较；不重新回测
PYTHONPATH=scripts .generated/venv-py314/bin/python3.14 -m report.render_small_cap_backtest_report

# 当前源码的全部测试
.generated/venv-py314/bin/python3.14 -m unittest discover -s tests -t .
```

日常只用 `scripts/daily_report_current.py`。旧命令 `daily_report_entry_demo.py` 仅剩跳转，不含旧策略。历史重新采集须显式用 `--historical-rebuild`；产物另存，读取时使用 `--replay --snapshot-source rebuilt`。不同来源的回放页面分别保存，不再互相覆盖。

## 实现边界

5只名单加3只备选、每20交易日换手、止盈10%、账户底线0.7。佣金为万一免五，税费另计。2026-11-02起按用户指定五只、各20%预算，以当天开盘买入前净值1建立连续碎股模拟；持仓、原买价、现金和待卖逐日延续，无需接入真实账户。起点前的单期整手演示只供历史阅读，当前跟踪不显示该演示或中途重新排名买入表。计算与费用见[说明](docs/small-cap-tracking.md)。

只维护桌面页面。历史日报、快照、原始行情和独立 UI 项目保留；它们不再决定当前日报内容。当前入口不加载板块图、数据库、旧执行流程、模型解读或阿尔法／贝塔研究。
