# 文件夹地图

当前只运行小盘轮换 v0.3，阿尔法／贝塔是显式备用研究。先读本页，再读当前Wiki；旧报告与压缩归档不构成现行要求。

```text
a-daily-report/
├── README.md / AGENTS.md / SKILL.md / CONTEXT.md  当前入口和约定
├── requirements.txt                             Python 3.14依赖
├── config/small-cap-tracking.json                指定五只与2026-11-02起点
├── scripts/
│   ├── daily_report_current.py                  唯一日常入口
│   ├── daily_report_entry_demo.py               旧命令的短跳转
│   ├── alpha_beta_research.py                   显式备用研究入口
│   ├── report/
│   │   ├── small_cap_rotation.py                当前名单与日历；旧快照只读展示
│   │   ├── small_cap_tracking.py                唯一连续模拟账户、现金与原买价
│   │   ├── small_cap_report.py                  必需采集、快照、桌面页面
│   │   ├── market_returns.py                    按日期采集与验证全市场行情
│   │   ├── small_cap_history.py                 行情转计算矩阵
│   │   ├── fact_utils.py                        日期、数值、指纹等共用工具
│   │   └── render_small_cap_backtest_report.py   只重绘冻结比较
│   ├── market_data/                            本项目数据源连接与日期工具
│   └── research/alpha_beta/                     备用模型、历史规则和回测
├── tests/                                      保留功能及历史只读兼容测试
├── wiki/                                       当前策略、证据和表达约定
├── references/                                 产物契约、验证命令
├── docs/
│   ├── structure.md / cleanup-2026-11-02.md      本地图与实际清理记录
│   ├── small-cap-tracking.md                    当前净值计算与延续
│   ├── research/                               小盘冻结比较、备用研究证据
│   └── archive/                                精华说明与经核验的压缩源码
├── data/
│   ├── market-history/                         日历、财报、指数及备用研究基础事实
│   └── market-returns/                         按日期保存的原始行情
├── reports/                                    新小盘页面与不可覆盖的历史原件
├── snapshots/                                  不可覆盖的冻结事实和连续记录
└── .generated/venv-py314/                       固定Python环境，必须保留
```

## 当前调用路径

`daily_report_current → small_cap_report / small_cap_tracking → market_returns / small_cap_rotation → 小盘HTML`。

新计划只生成本期五只、三只备选与换手日历，不计算一万元单期账户、中途新排名或旧期收益。连续持仓、现金与净值只由 small_cap_tracking 生成。旧v7快照保留原指纹读取，不裁剪、不重新计算；计划存储版本升级不改变v0.3选股和买卖参数。

联网只需行情、日历、股票资料、目标日ST、季度财报、指数与同日涨跌停及停牌事实。行情配置只读取本项目根目录的.env及明确传入的配置，不搜索启动目录。当前入口不依赖WorkBuddy、旧UI、数据库或外部项目。

阿尔法／贝塔由独立命令显式运行；共用行情校验，可调用保留的小盘研究对照，不反向进入小盘执行。

## 数据和产物

- data/market-history、data/market-returns、config与snapshots是运行及查证资料，不能当临时缓存整体删除。连续跟踪还必须承接此前每个交易日的record和facts。
- snapshots/small-cap/tracking保存正式连续记录；replay、rebuilt在独立子目录累计，不混用。
- 新日报放在reports/small-cap；回放放在reports/replay/small-cap。文件名包含内容摘要，同日同内容复用，修正文案另存，历史原件不覆盖。以生成命令输出的路径为准。
- 当前回测比较入口是reports/research/small_cap_v0.3_frozen_compare_current.html；冻结输入仍是docs/research/small-cap-v0.3/comparison-inputs.json。

## 旧东西去了哪里

项目内旧.worktrees、三个独立UI工作副本、旧venv、旧data/logs/output、浏览器产物及.generated中的旧源码和指令已退出项目目录。先按逐文件摘要核验封存，再移除展开副本，未提交内容和独有快照一并保存。

78份历史报告附带的旧AGENTS.md与旧Obsidian插件配置也已封存；报告正文和事实快照保留，旧指令不在报告目录继续生效。

本机隔离归档在 `~/.hermes/archives/a-daily-report/hygiene-20261102-223943/`，不参与运行。可随源码发布的历史精华和压缩包仍在docs/archive。查证时只取需要的成员到临时目录，不把旧项目整体解压回当前目录。具体范围和验证见[清理记录](cleanup-2026-11-02.md)。
