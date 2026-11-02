# 备用阿尔法／贝塔

这是旧方法的可运行研究副本，不是第二条日常策略。核心模型和回测参数保留，入口与小盘执行分开。

- `scripts/research/alpha_beta/market_alpha_beta.py`：市场共振、收缩贝塔、独立上涨等统计投影。
- `decision_board.py`：旧六项检查、旧贝塔篮子、五日比较与旧阶段规则。
- `strategy_backtest.py`：上述阿尔法／贝塔变体、指数及随机对照；提供长历史 `load_history`、`run_backtest`。
- `scripts/alpha_beta_research.py`：显式读取一份冻结快照，另存研究JSON。可选回测仅使用快照内至多61日，不称20个月回测。

```bash
.generated/venv-py314/bin/python3.14 scripts/alpha_beta_research.py snapshots/replay/2026-10-30_replay.json --backtest
```

这里保留的五日退出、失效价与来回0.2%成本属于旧研究，不能覆盖小盘止盈规则或用户万一免五佣金。`live_rule` 是历史字段名，不表示当前使用。

长历史输入仍在 `data/market-returns/` 和 `data/market-history/`（日历、基准、股票资料、历史名称）。独立复算的结果JSON保留在本目录，原始脚本、README及完整研究过程保存在 [研究压缩包](../../archive/README.md)。旧脚本需要原版本导入路径，不能未经恢复就称可直接复现；新备用模型以当前测试为准。

没有重新排名这些方法，也没有把旧统计结论当作今天应该执行的建议。

当前备用入口验证范围为研究JSON和快照窗口回测。旧HTML辅助渲染器需要宿主提供图表库，不作为当前可独立运行的页面入口；本轮未为旧展示恢复全局ECharts资产。
