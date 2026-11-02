# 当前产物契约

唯一日常入口为 scripts/daily_report_current.py。daily_report_entry_demo.py只是旧命令的跳转。旧 full/short、仓位参数与发布命令不再提供。

正式来源优先读取 snapshots/small-cap/<date>.json，若不存在则读取原 snapshots/<date>.json；两者都必须具有同日行情与v0.3计划。replay只读 snapshots/replay/<date>_replay.json；rebuilt只读 snapshots/small-cap/rebuilt/<date>.json。不同来源不混合。

新当日事实写 snapshots/small-cap/；显式历史重新采集写其 rebuilt/ 子目录。原正式、原replay快照不改写。文件先完整写好再发布；同名内容不一致停止覆盖。

当前日报为 reports/small-cap/<date>_小盘轮换.html；回放在 reports/replay/small-cap/，名称带来源。页面只显示冻结小盘计划、单期模拟及模型边界，不读取历史HTML，也不重建其他策略。

未有v0.3计划的旧快照不能靠旧买卖建议补齐。历史重新采集只接受显式 --historical-rebuild，股票资料按查询时版本留痕，不能声称历史资料完全还原。
