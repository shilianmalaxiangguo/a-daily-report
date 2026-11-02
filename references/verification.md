# 当前验证

固定解释器：`.generated/venv-py314/bin/python3.14`。

```bash
.generated/venv-py314/bin/python3.14 -m unittest discover -s tests -t .
.generated/venv-py314/bin/python3.14 scripts/daily_report_current.py 2026-10-30 --replay --snapshot-source replay
```

保留功能的全部测试覆盖小盘选股与止盈、费用、纯小盘采集、快照来源隔离、旧HTML无关、原件保护、数据指纹、备用阿尔法／贝塔和归档逐文件摘要。

页面变化按1440px桌面实际查看连续持仓、买价、止盈线、净值、现金、选股依据与备选；当前跟踪页不能显示旧单期表或中途入场表。新连续记录必须独立复算当日净值和费用；同日重跑、完全离线重读、缺日停止、延迟卖出和换手延续见 tests.test_small_cap_tracking。冻结回测重绘需核对日期、指标和图例交互。正式报告、快照和冻结研究产物在修改前后核对SHA-256。

提交前独立审计当前运行依赖、删除范围、文档、备用研究与保护副本，并运行 git diff --check。只报告实际执行的验证；测试不证明未来盈利，也不能补齐真实账户记录。实时数据源若未联网验证应明确说明。
