#!/usr/bin/env python3.14
"""The only daily entry: small-cap rotation; Alpha/Beta is explicit research."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import time
from zoneinfo import ZoneInfo
from report.fact_utils import _target_date
from report.small_cap_report import ROOT, collect, render, save_snapshot, selected_snapshot, write_new
from report.small_cap_tracking import prepare, save as save_tracking


def main(argv=None, *, root=ROOT):
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description='小盘轮换 v0.3 桌面日报')
    parser.add_argument('date', nargs='?', help='目标交易日 YYYY-MM-DD')
    parser.add_argument('--replay', action='store_true', help='只读选定快照，完全离线')
    parser.add_argument('--snapshot-source', choices=['official', 'replay', 'rebuilt'], default='official',
                        help='正式、旧重建或独立小盘重建快照，不混合来源')
    parser.add_argument('--historical-rebuild', action='store_true', help='按目标日采集，另存独立小盘重建资料')
    parser.add_argument('--no-report', action='store_true', help='只校验资料，不保存页面或快照')
    args = parser.parse_args(argv)
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date()
    day = _target_date(args.date or (today - timedelta(days=1)).isoformat())
    if args.snapshot_source != 'official' and not args.replay:
        parser.error('指定历史来源须同时使用 --replay')
    if args.replay and args.historical_rebuild:
        parser.error('离线读取与重新采集只能选一种')
    try:
        if args.replay or not args.historical_rebuild:
            try:
                data, source = selected_snapshot(root, day, args.snapshot_source)
            except ValueError:
                exists = any(p.is_file() for p in [root / 'snapshots/small-cap' / f'{day}.json',
                                                  root / 'snapshots' / f'{day}.json'])
                if args.replay or exists or day != today.isoformat():
                    raise
                data, source = collect(day, root=root), '目标日采集'
        else:
            data = collect(day, root=root, historical=True)
            source = '按目标日重新采集；股票资料以查询时版本为准'
        if root == ROOT and not (root / 'config/small-cap-tracking.json').is_file():
            raise ValueError('连续模拟起始配置缺失，停止生成；不退回单期演示')
        tracking = prepare(data, day, root=root,
                           allow_collect=not args.replay and (day == today.isoformat() or args.historical_rebuild),
                           snapshot_source='rebuilt' if args.historical_rebuild else args.snapshot_source)
        if args.no_report:
            print(f'{day} 小盘事实与计划校验通过；未保存产物')
            return 0
        if isinstance(source, Path):
            source = str(source.relative_to(root))
        else:
            save_snapshot(data, day, root=root, historical=args.historical_rebuild)
        if tracking:
            save_tracking(tracking, root)
        replay = args.replay or args.historical_rebuild or day != today.isoformat()
        directory = root / ('reports/replay/small-cap' if replay else 'reports/small-cap')
        suffix = f'_{args.snapshot_source}_replay' if args.replay else '_rebuilt' if args.historical_rebuild else ''
        path = directory / f'{day}_小盘轮换{suffix}.html'
        write_new(path, render(data, day, source=source, tracking=tracking))
        print(f'小盘日报：{path}')
        return 0
    finally:
        print(f'本次运行耗时：{time.perf_counter() - started:.2f}秒')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f'停止生成：{error}')
        raise SystemExit(1) from None
