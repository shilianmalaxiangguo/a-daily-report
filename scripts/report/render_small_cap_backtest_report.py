"""Render existing frozen comparison curves; this command does not rerun a backtest."""
import argparse
import html
import json
from math import isfinite
from pathlib import Path
from report.small_cap_report import ROOT, STYLE, write_new

NAMES = {'small_cap_plan': '小盘止盈10%（等权）', 'small_cap_plan_hold': '同名单不止盈（等权）',
         'small_cap_pool': '股票池（等权）', '399006.SZ': '创业板指', '932000.CSI': '中证2000',
         'index': '中证全指', 'alpha': '旧阿尔法', 'alpha_regime': '旧阿尔法阶段过滤',
         'beta': '旧高贝塔', 'beta_offense': '旧高贝塔阶段过滤', 'stance': '旧阿尔法／贝塔轮换',
         'live_rule': '旧阿尔法／贝塔综合规则'}
COLORS = ['#a53c31', '#8c64ac', '#b58027', '#2e729e', '#217e65', '#313a49', '#b96791', '#796379', '#358d96', '#779657', '#705ba2', '#a45f51']


def metric(curve):
    values = [float(v) for v in curve]
    if len(values) < 2 or any(not isfinite(v) or v <= 0 for v in values):
        raise ValueError('净值数据不完整，停止生成')
    peak, dd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1)
    return [(values[-1] / values[0] - 1) * 100,
            ((values[-1] / values[0]) ** (252 / (len(values) - 1)) - 1) * 100, dd * 100]


def chart(dates, curves):
    normalized = {k: [float(v) / float(c[0]) for v in c] for k, c in curves.items()}
    low = min(min(c) for c in normalized.values()) * .97
    high = max(max(c) for c in normalized.values()) * 1.03
    lines, labels = [], []
    for i, (key, values) in enumerate(normalized.items()):
        points = ' '.join(f'{60 + j / (len(dates)-1) * 1120:.2f},{430 - (v-low)/(high-low)*390:.2f}' for j, v in enumerate(values))
        lines.append(f'<polyline data-series="{key}" points="{points}" fill="none" stroke="{COLORS[i%len(COLORS)]}" stroke-width="2"/>')
        label = html.escape(NAMES.get(key, key))
        labels.append(f'<label style="color:{COLORS[i%len(COLORS)]}"><input type="checkbox" checked data-key="{key}"> {label}</label>')
    ticks = ''.join(f'<text x="4" y="{430-n*390/4:.1f}" font-size="14">{low+(high-low)*n/4:.2f}</text><line x1="55" x2="1185" y1="{430-n*390/4:.1f}" y2="{430-n*390/4:.1f}" stroke="#ddd"/>' for n in range(5))
    return '<div class="legend">'+' '.join(labels)+'</div><svg role="img" aria-label="同日期净值曲线，起点归一为1" viewBox="0 0 1240 480">'+ticks+''.join(lines)+f'<text x="60" y="465">{dates[0]}</text><text x="1080" y="465">{dates[-1]}</text></svg>'


def render(inputs):
    backtest = inputs['backtest']; dates = backtest['dates']
    curves = {k: backtest['curves'][k] for k in NAMES if k in backtest['curves']}
    if not dates or dates != sorted(set(dates)) or dates[0] != inputs['recent_start'] or dates[-1] != backtest['end']:
        raise ValueError('冻结比较日期不符')
    if len(dates) != backtest['sessions'] or any(len(c) != len(dates) for c in curves.values()):
        raise ValueError('冻结比较曲线长度不符')
    rows = []
    for key, c in curves.items():
        rows.append('<tr><td>'+html.escape(NAMES[key])+'</td>'+''.join(f'<td>{v:+.2f}%</td>' for v in metric(c))+'</tr>')
    account = inputs['account']
    account_rows = []
    for key, label in [('tp10','止盈10%'), ('base','不止盈')]:
        item = account[key]
        if item['span'] != dates or len(item['nav']) != len(dates):
            raise ValueError('账户曲线日期不符')
        account_rows.append('<tr><td>'+label+'</td>'+''.join(f'<td>{v:+.2f}%</td>' for v in metric(item['nav']))+'</tr>')
    heading = '<tr><th>模型</th><th>累计收益</th><th>年化</th><th>最大回撤</th></tr>'
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>小盘轮换 v0.3 冻结比较</title><style>'+STYLE+
            '.legend{display:flex;flex-wrap:wrap;gap:12px 20px;font-size:14px}svg{width:100%;display:block}label{cursor:pointer}</style><main>'+
            f'<h1>小盘轮换 v0.3：冻结回测比较</h1><p>{dates[0]} 至 {dates[-1]}，{len(dates)}个交易日。本页只重绘冻结结果，没有重新回测或优化。</p>'+
            '<p class="limit">等权模型沿用窗口前买价，每期来回成本0.2%，不是用户的佣金。整手账户使用万一免五，另计税费。收益不是实盘预期。</p>'+
            '<section><h2>同窗口比较</h2>'+chart(dates, curves)+'<table>'+heading+''.join(rows)+'</table></section>'+
            '<section><h2>独立连续整手账户</h2><table>'+heading+''.join(account_rows)+'</table>'+
            '<p>该冻结账户尚未限制3只备选，也未接入0.7底线卖出；日报仍是每期重置1万元的单期模拟。三者不可混称。</p></section>'+
            '<p>数据出处：docs/research/small-cap-v0.3/comparison-inputs.json。历史研究源码及摘要见 docs/archive/；原始快照与行情缓存保留。止盈规则是在看过结果后采纳，需继续前推检验。</p>'+
            '<script>document.querySelectorAll("input[data-key]").forEach(el=>el.addEventListener("change",()=>{document.querySelectorAll("[data-series]").forEach(line=>{if(line.dataset.series===el.dataset.key)line.style.display=el.checked?"":"none"})}));</script></main></html>')


def main(argv=None):
    parser = argparse.ArgumentParser(description='重绘小盘冻结比较，不重新回测')
    parser.add_argument('--input', type=Path, default=ROOT / 'docs/research/small-cap-v0.3/comparison-inputs.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/research/small_cap_v0.3_frozen_compare.html')
    args = parser.parse_args(argv)
    write_new(args.output, render(json.loads(args.input.read_text(encoding='utf-8'))))
    print(args.output)


if __name__ == '__main__':
    main()
