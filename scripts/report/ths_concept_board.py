"""概念指数榜：把同花顺概念指数(ths_index type='N')当日序列冻结成事实。

只读数据源、只写自己的 JSON 产物，不改报告决定。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_data.tushare_market_activity_service import (  # noqa: E402
    THS_CONCEPT_INDEX_TYPE,
    fetch_tushare_ths_concept_board,
    fetch_tushare_ths_daily,
    fetch_tushare_ths_index_history,
    fetch_tushare_ths_index_map,
    is_a_share_concept_index,
)
from report.hypothesis_revision import _canonical_date, _hash  # noqa: E402

SCHEMA = 'ths_concept_board.v1'
DEFAULT_OUTPUT_DIR = '.generated/ths-concept-board'


def build_board(
    target_date,
    *,
    index_map,
    daily_rows,
    history_fetcher=None,
    history_days=0,
    top=20,
    index_type=THS_CONCEPT_INDEX_TYPE,
    retrieved_at=None,
    today=None,
):
    if not _canonical_date(target_date):
        raise ValueError('目标日期必须是 YYYY-MM-DD')
    today = today or datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    if target_date > today:
        raise ValueError('目标日期晚于今天，停止生成')
    board = fetch_tushare_ths_concept_board(
        target_date, index_type=index_type, index_map=index_map, daily_rows=daily_rows,
    )
    if not board:
        raise ValueError('当日没有同花顺概念指数记录，停止生成')
    selected = board[:top]
    if history_days and history_fetcher:
        start = (date.fromisoformat(target_date) - timedelta(days=history_days)).isoformat()
        for item in selected:
            rows = history_fetcher(item['ts_code'], start, target_date) or []
            series = []
            for row in rows:
                try:
                    series.append({
                        'trade_date': str(row.get('trade_date') or '').strip(),
                        'pct_change': round(float(row.get('pct_change')), 4),
                        'close': None if row.get('close') in (None, '') else float(row.get('close')),
                    })
                except (TypeError, ValueError):
                    continue
            series.sort(key=lambda row: row['trade_date'])
            item['history'] = [row for row in series if row['trade_date'] and row['trade_date'] <= target_date.replace('-', '')]
    a_share_registered = sum(
        1 for meta in index_map.values() if is_a_share_concept_index(meta, index_type=index_type)
    )
    payload = {
        'schema_version': SCHEMA,
        'target_date': target_date,
        'retrieved_at': retrieved_at or datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        'index_type': index_type,
        'sources': [
            {'endpoint': 'ths_index', 'type': index_type, 'rows': len(index_map)},
            {'endpoint': 'ths_daily', 'trade_date': target_date, 'rows': len(daily_rows)},
            {'endpoint': 'ths_daily.history', 'days': history_days, 'per_concept': bool(history_days)},
        ],
        'universe': {
            'registered_total': len(index_map),
            'a_share_concepts': a_share_registered,
            'with_rows': len(board),
        },
        'board_size': len(board),
        'shown': len(selected),
        'board': selected,
        'boundary': [
            '概念指数只提供当日涨跌与指数序列，不等于资金净流入。',
            '指数分类以同花顺 ths_index(type="N") 为准，只取 exchange=A 且 885/886 代码族；'
            '875xxx 港股概念、865xxx 美股概念与 883xxx 样本股指数一律不入选。',
            '登记概念数与当日有行数不相等：目标日没有行的概念按事实不足处理，不补 0。',
            '本产物只作研究证据，不产生候选、仓位或执行资格。',
        ],
    }
    payload['artifact_hash'] = _hash(payload)
    return payload


def save_board(payload, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description='冻结同花顺概念指数当日榜')
    parser.add_argument('date', help='目标交易日 YYYY-MM-DD')
    parser.add_argument('--top', type=int, default=20, help='输出前多少个概念')
    parser.add_argument('--history-days', type=int, default=0, help='为前 N 个概念附带多少自然日的历史序列')
    parser.add_argument('--output', default='', help='输出路径，默认 .generated/ths-concept-board/<date>.json')
    args = parser.parse_args(argv)
    index_map = fetch_tushare_ths_index_map(index_type=THS_CONCEPT_INDEX_TYPE)
    daily_rows = fetch_tushare_ths_daily(args.date)
    payload = build_board(
        args.date, index_map=index_map, daily_rows=daily_rows,
        history_fetcher=fetch_tushare_ths_index_history,
        history_days=args.history_days, top=args.top,
    )
    output = args.output or f'{DEFAULT_OUTPUT_DIR}/{args.date}-concept-index-board.json'
    path = save_board(payload, output)
    print(f'概念指数榜: {path}')
    for row in payload['board'][:10]:
        print(f"{row['rank']:>2} {row['name']:<16} {row['pct_change']:>7.2f}%  {row['ts_code']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
