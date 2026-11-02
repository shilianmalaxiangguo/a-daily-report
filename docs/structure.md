# 文件夹地图

```text
a-daily-report/
├── README.md / AGENTS.md / SKILL.md / CONTEXT.md  当前入口和约定
├── requirements.txt                             Python 3.14依赖
├── scripts/
│   ├── daily_report_current.py                  唯一日常入口
│   ├── daily_report_entry_demo.py               旧命令的短跳转
│   ├── alpha_beta_research.py                   显式备用研究入口
│   ├── report/
│   │   ├── small_cap_rotation.py                选股、卖出、单期模拟
│   │   ├── small_cap_report.py                  必需采集、快照、桌面页面
│   │   ├── market_returns.py                    按日期采集与验证全市场行情
│   │   ├── small_cap_history.py                 行情转计算矩阵
│   │   ├── fact_utils.py                        日期、数值、指纹等共用工具
│   │   └── render_small_cap_backtest_report.py   重绘冻结比较结果
│   ├── market_data/                            数据源连接与日期工具
│   └── research/alpha_beta/                     备用模型、旧规则和回测
├── tests/                                      只测试保留的功能
├── wiki/                                       当前策略、证据和表达约定
├── references/                                 产物契约、验证命令
├── docs/
│   ├── structure.md / cleanup-2026-11-02.md      本地图与实际清理记录
│   ├── research/                               小盘冻结比较、阿尔法／贝塔证据
│   └── archive/                                精华说明、压缩源码、逐文件摘要
├── reports/                                    历史产物与新小盘页面
├── snapshots/                                  不可覆盖的冻结事实
└── .generated/                                 环境、行情缓存、本地保护副本和验证日志
```

## 每次生成实际经过什么

`daily_report_current → small_cap_report → market_returns / small_cap_rotation → 小盘HTML`。

联网只需交易日历、个股日线、股票基础资料、目标日ST、季度财报、中证全指及两条对照指数。离线只读所选JSON，不读旧HTML，不运行旧策略。阿尔法／贝塔在独立命令中显式调用，共用行情校验，不反向进入小盘。

## 产物放在哪里

| 文件夹 | 内容 |
|---|---|
| `reports/small-cap/` | 新的小盘桌面日报 |
| `reports/replay/small-cap/` | 按来源分别命名的离线阅读页 |
| `snapshots/small-cap/` | 新小盘快照；只含当前行情和计划 |
| `snapshots/small-cap/rebuilt/` | 显式历史采集产生的独立快照 |
| `reports/research/` | 冻结回测比较和备用研究结果 |
| 旧 `reports/`、`snapshots/` | 原件继续保留，不覆盖 |
| `.generated/backtest-history/`、`.generated/market-returns-v2/` | 日历、财报和原始行情缓存 |

## 为什么仍有大文件夹

主要体积来自冻结事实、历史报告、Python环境和其他Git工作树。它们不是当前运行代码，清理策略源码不会让历史数据凭空变小。

`data/`、`logs/`、`output/`、`.worktrees/`、`venv/`、`snap-ui/`及独立UI副本没有用于新入口。数据、Git工作树和独立项目保留；旧环境尚未核清所有外部启动引用，本次未删除。根目录散落的旧截图、临时HTML和旧Wiki压缩包另存本地历史产物目录。

查旧方法先看 `docs/archive/README.md`，需要原文才按清单取出压缩包中的单个文件；不要重新解压到 `scripts/` 或根指令目录。
