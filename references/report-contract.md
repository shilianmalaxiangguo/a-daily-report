# 当前产物契约

唯一日常入口为 scripts/daily_report_current.py。daily_report_entry_demo.py只是旧命令的跳转。旧 full/short、仓位参数与发布命令不再提供。

正式来源优先读取 snapshots/small-cap/<date>.json，若不存在则读取原 snapshots/<date>.json；两者都必须具有同日行情与v0.3计划。replay只读 snapshots/replay/<date>_replay.json；rebuilt只读 snapshots/small-cap/rebuilt/<date>.json。不同来源不混合。

新当日事实写 snapshots/small-cap/；显式历史重新采集写其 rebuilt/ 子目录。原正式、原replay快照不改写。文件先完整写好再发布；同名内容不一致停止覆盖。

当前连续跟踪日报为 reports/small-cap/<date>_小盘轮换_净值报告.html；回放在 reports/replay/small-cap/，名称带来源，例如 <date>_小盘轮换_净值报告_official_replay.html。新命名保留此前同日报告原件；起点前继续使用 <date>_小盘轮换.html 及其来源后缀。2026-11-02起首屏显示费用后净值、累计收益、成分股和下一调仓日，曲线使用全部连续记录；不显示旧单期整手或中途入场表。不读取历史HTML，也不重建其他策略。

连续模拟起点与五只配置在 config/small-cap-tracking.json；同日成交条件与连续记录单独保存在 snapshots/small-cap/tracking/。与所选行情、计划及前日记录逐项关联，不跨来源混用。缺少前一交易日记录停止，不重置净值；同名不同内容不覆盖。离线不能补采涨跌停或停牌事实。详见 docs/small-cap-tracking.md。

未有v0.3计划的旧快照不能靠旧买卖建议补齐。历史重新采集只接受显式 --historical-rebuild，股票资料按查询时版本留痕，不能声称历史资料完全还原。
