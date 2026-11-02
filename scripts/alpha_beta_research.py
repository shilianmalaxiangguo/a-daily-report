#!/usr/bin/env python3.14
"""Explicit Alpha/Beta research, isolated from daily execution."""
import argparse
import json
from pathlib import Path
from report.market_returns import validate_market_returns
from report.small_cap_report import ROOT, write_new
from research.alpha_beta.market_alpha_beta import build_alpha_beta
from research.alpha_beta.decision_board import build_decision_board
from research.alpha_beta.strategy_backtest import history_from_artifact, run_backtest


def main(argv=None):
    parser = argparse.ArgumentParser(description='备用阿尔法／贝塔研究；不会修改小盘名单')
    parser.add_argument('snapshot', type=Path, help='显式指定冻结JSON')
    parser.add_argument('--backtest', action='store_true', help='只在该快照行情窗口内回测旧规则')
    parser.add_argument('--output', type=Path, help='另存JSON，默认 reports/research/alpha-beta/')
    args = parser.parse_args(argv)
    value = json.loads(args.snapshot.read_text(encoding='utf-8'))
    day = value['date']
    market = validate_market_returns(value['data']['reading_market_returns'], day)
    projection = build_alpha_beta(market, day)
    if projection is None:
        raise ValueError('阿尔法／贝塔计算所需完整行情不足')
    result = {'identity': '备用研究，不是当前执行建议', 'date': day,
              'source': str(args.snapshot), 'projection': projection,
              'historical_board': build_decision_board(market, day, projection)}
    if args.backtest:
        result['backtest'] = run_backtest(history_from_artifact(market))[0]
        result['backtest_note'] = '只使用所选快照的至多61个交易日；旧五日模型和旧成本，不是小盘账户。长历史复算使用保留的load_history函数及原始缓存。'
    out = args.output or ROOT / 'reports/research/alpha-beta' / f'{day}_研究.json'
    write_new(out, json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    print(f'备用研究结果：{out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
