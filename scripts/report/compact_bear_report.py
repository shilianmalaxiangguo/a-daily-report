"""Render the confirmed compact selection without recomputing report decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report.sector_reading_primitives import (
    _finite_number, _fact_date, _frozen_sector_facts, seal_rows, _text, _seal_section, _SEAL_SCRIPT,
)
from report.hypothesis_revision import (
    HYPOTHESIS_STYLE, build_hypothesis_revision,
    render_hypothesis_revision_fragment, validate_hypothesis_record,
)
from report.surface_wording import sanitize_user_visible_text

# User-confirmed order. Each item has a visible place even if its facts are missing.
SELECTION = (
    ('execution', '明日执行结论'),
    ('sector_hypotheses', '板块假设与确认'),
    ('t0_market_breadth', 'T0市场底色'),
    ('market_turnover_trend', '两市成交额趋势'),
    ('top50_share_trend', 'Top50成交占比与创业板指趋势'),
    ('cycle_calendar', '周期日历主视图'),
    ('t2', '板块资金扩散淘汰赛'),
    ('turnover_top30', '成交额Top30'),
    ('seal_amount', '当日封板金额排行（排除 ST、*ST）'),
    ('cffex_position_trend', '股指期货净空结构趋势'),
    ('new_high_share_trend', '创新高全A占比'),
    ('lhb_net_flow', '龙虎榜净额表态'),
)
SECTION_IDS = {'execution', 'cycle_calendar', 't2'}








def _sector_hypothesis_section(soup, snapshot, target_date, previous_snapshot=None, previous_record=None,
                               *, origin='historical_rebuild', hypothesis_record=None, tracked_evidence=(), trend_evidence=None,
                               chart_facts=None, leader_board=None):
    rows, axis = _frozen_sector_facts(snapshot, target_date, include_nonpositive=True)
    previous_rows, previous_date, previous_market = [], '', None
    if previous_snapshot is not None:
        if not isinstance(previous_snapshot, dict) or not previous_snapshot.get('date'):
            raise ValueError('前次板块快照日期缺失，停止生成')
        previous_date = str(previous_snapshot['date'])
        previous_rows, _ = _frozen_sector_facts(previous_snapshot, previous_date, include_nonpositive=True)
        previous_market = _market_change(previous_snapshot, previous_date)
    raw_data = (snapshot.get('data') or {}) if isinstance(snapshot, dict) else {}
    accepted = {(row['data_source'], row['code'], row['name']) for row in rows}
    source_rows = []
    for key in ('sector_change_up', 'sector_change_down'):
        for row in raw_data.get(key) or []:
            if not isinstance(row, dict):
                continue
            source = str(row.get('data_source') or '').strip()
            identity = (source, str(row.get('code') or '').strip(),
                        sanitize_user_visible_text(str(row.get('name') or '').strip()))
            dates = [str(row[key]).replace('-', '') for key in ('trade_date', 'source_date', 'query_date') if row.get(key)]
            if (identity not in accepted or not row.get('trade_date')
                    or any(value != target_date.replace('-', '') for value in dates)
                    or (source == 'tushare.daily.industry_aggregate'
                        and any(not row.get(key) for key in ('source_date', 'query_date')))):
                continue
            source_rows.append({key: row.get(key) for key in ('name', 'code', 'data_source', 'trade_date', 'source_date', 'query_date')})
    market = raw_data.get('wind_a_alternative')
    market = market if isinstance(market, dict) and _market_change(snapshot, target_date) is not None else {}
    provenance = {
        'snapshot_date': target_date,
        'source_input_hash': hashlib.sha256(json.dumps(
            {key: raw_data.get(key) for key in ('sector_change_up', 'sector_change_down', 'wind_a_alternative')},
            ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest(),
        'rows': source_rows,
        'market': {key: market.get(key)
                   for key in ('code', 'data_source', 'trade_date', 'source_date', 'query_date')},
    }
    payload = build_hypothesis_revision(
        rows, target_date=target_date, market_change=_market_change(snapshot, target_date),
        previous_record=previous_record, previous_rows=previous_rows,
        previous_date=previous_date, previous_market_change=previous_market, origin=origin,
        source_provenance=provenance,
    )
    if hypothesis_record is not None:
        if (not validate_hypothesis_record(hypothesis_record)
                or hypothesis_record.get('target_date') != target_date
                or hypothesis_record.get('input_hash') != payload['input_hash']
                or hypothesis_record.get('source_hash') != payload['source_hash']):
            raise ValueError('当日事实与已保存板块记录不同，拒绝覆盖')
        payload = hypothesis_record
    from report.sector_chart_facts import build_sector_display_context, validate_sector_chart_facts
    display_trend = trend_evidence
    if chart_facts is not None:
        if trend_evidence is None or not validate_sector_chart_facts(chart_facts, payload, trend_evidence):
            raise ValueError('图表补查与原日期事实不符')
        display_trend = chart_facts['trend']
    display_context = build_sector_display_context(snapshot, target_date, display_trend, chart_facts)
    section = BeautifulSoup(render_hypothesis_revision_fragment(payload, tracked_evidence=tracked_evidence,
                                                               trend_evidence=display_trend,
                                                               display_context=display_context,
                                                               leader_board=leader_board), 'html.parser').section
    section['aria-label'] = '板块假设与修正'
    if axis:
        section['data-sector-source-hash'] = axis['artifact_hash']
        detail = soup.new_tag('details', attrs={'class': 'hypothesis-rules'})
        detail.append(_text(soup, 'summary', '展开原研究方向'))
        detail.append(_text(soup, 'p', sanitize_user_visible_text(
            f"原研究方向：{axis.get('direction') or '待确认'}；"
            f"{axis.get('time_axis', {}).get('stage') or '事实不足'}；"
            + '；'.join(axis.get('counter_evidence') or [])
            + '。与当日上涨榜分开核对。')))
        section.append(detail)
    script = soup.new_tag('script', attrs={'id': 'sector-hypothesis-record', 'type': 'application/json'})
    script.string = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    section.append(script)
    if tracked_evidence:
        script = soup.new_tag('script', attrs={'id': 'tracked-sector-evidence', 'type': 'application/json'})
        script.string = json.dumps(tracked_evidence, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        section.append(script)
    section['data-hypothesis-hash'] = payload['artifact_hash']
    if trend_evidence is not None:
        script = soup.new_tag('script', attrs={'id': 'sector-trend-evidence', 'type': 'application/json'})
        from report.sector_trend_tracking import public_trend_evidence
        script.string = json.dumps(public_trend_evidence(trend_evidence), ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        section.append(script)
        section['data-trend-hash'] = trend_evidence['artifact_hash']
    if chart_facts is not None:
        note = _text(soup, 'p',
            f'图表补查取得于{chart_facts["retrieved_at"]}；只补同源、同日期的价格缺口。'
            '矩阵与滚动走势按补查事实复核，原日期判断、原趋势凭据和正式决定保留不变；仍缺的事实不补零。')
        note['class'] = 'hypothesis-origin'
        section.append(note)
        script = soup.new_tag('script', attrs={'id': 'sector-chart-facts', 'type': 'application/json'})
        script.string = json.dumps({key: chart_facts[key] for key in (
            'schema_version', 'target_date', 'record_hash', 'base_trend_hash', 'retrieved_at', 'artifact_hash', 'issues')},
            ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        section.append(script)
    return section


def _market_change(snapshot, target_date):
    data = snapshot.get('data', {}) if isinstance(snapshot, dict) else {}
    index = data.get('wind_a_alternative')
    if not isinstance(index, dict) or str(index.get('trade_date') or '').replace('-', '') != target_date.replace('-', ''):
        return None
    dates = [str(index[k]).replace('-', '') for k in ('source_date', 'query_date') if index.get(k)]
    if any(value != target_date.replace('-', '') for value in dates):
        return None
    return _finite_number(index.get('change_pct'))






def _section(soup, marker):
    heading = next((h for h in soup.select('h2,h3') if marker in h.get_text()), None)
    if heading is None:
        return None
    section = soup.new_tag('section', attrs={'class': 'compact-evidence'})
    level = int(heading.name[1])
    node = heading
    while node:
        if node is not heading and node.name in ('h1', 'h2', 'h3') and int(node.name[1]) <= level:
            break
        following = node.next_sibling
        section.append(node.extract())
        node = following
    return section


def _execution_diagnostic(soup, snapshot, target_date):
    """Explain an empty execution result from frozen decision evidence."""
    data = snapshot.get('data', {}) if isinstance(snapshot, dict) else {}
    workflow = data.get('selection_workflow') if isinstance(data.get('selection_workflow'), dict) else {}
    final = workflow.get('final') if isinstance(workflow.get('final'), dict) else {}
    expected_date = str(target_date or '').replace('-', '')
    snapshot_date = str(snapshot.get('date') or '').replace('-', '') if isinstance(snapshot, dict) else ''
    workflow_date = str(
        workflow.get('target_date') or data.get('target_date') or ''
    ).replace('-', '')
    action = str(final.get('action_text') or final.get('final_action') or '').strip()
    execution_object = final.get('execution_object') if isinstance(final.get('execution_object'), dict) else {}
    position_pct = _finite_number(final.get('position_pct'))
    if execution_object and position_pct is not None and position_pct > 0 and '不参与' not in action:
        return None
    proof = workflow.get('local_trend_sector_proof') if isinstance(workflow.get('local_trend_sector_proof'), dict) else {}
    section = soup.new_tag('section', attrs={
        'class': 'reader-diagnostic reader-evidence',
        'data-compact-item': 'execution_diagnostic',
        'aria-label': '执行结论依据',
    })
    heading = _text(soup, 'h2', '为什么今天没有标的')
    heading['class'] = ['reader-diagnostic-title']
    section.append(heading)
    if expected_date != snapshot_date or expected_date != workflow_date:
        p = _text(
            soup, 'p',
            f'{target_date} 的冻结诊断事实不足：快照日期或选股链日期不一致，暂不展示候选数量和缺口解释。',
        )
        p['class'] = ['reader-wavy-red']
        section.append(p)
        return section
    pool = [item for item in workflow.get('candidate_pool') or [] if isinstance(item, dict)]
    statuses = {}
    for item in pool:
        status = str(item.get('status') or '未标注').strip()
        statuses[status] = statuses.get(status, 0) + 1
    trace_artifact = data.get('candidate_trace_artifact') if isinstance(data.get('candidate_trace_artifact'), dict) else {}
    trace_payload = trace_artifact.get('payload') if isinstance(trace_artifact.get('payload'), dict) else {}
    traces = [item for item in trace_payload.get('traces') or [] if isinstance(item, dict)]
    mainline_pass = 0
    mainline_missing = 0
    account_missing = 0
    for trace in traces:
        checks = {str(item.get('label')): str(item.get('result')) for item in trace.get('checks') or [] if isinstance(item, dict)}
        if 'mainline' in (trace.get('missing_data') or []):
            mainline_missing += 1
        elif checks.get('主线条件') == '满足':
            mainline_pass += 1
        if 'account_context' in (trace.get('missing_data') or []):
            account_missing += 1
    position_decision = data.get('position_decision') if isinstance(data.get('position_decision'), dict) else {}
    comparison = position_decision.get('opportunity_comparison') if isinstance(position_decision.get('opportunity_comparison'), dict) else {}
    target = comparison.get('new_target') if isinstance(comparison.get('new_target'), dict) else {}
    missing_risk = [str(item) for item in target.get('missing_fields') or [] if str(item).strip()]
    if pool:
        summary = f'{target_date} 不是“没有候选”：候选池有 {len(pool)} 只。'
        if mainline_pass:
            summary += f' 其中 {mainline_pass} 只的主线条件记录为满足，但个股结构仍未完整。'
        section.append(_text(soup, 'p', summary))
    else:
        section.append(_text(soup, 'p', f'{target_date} 候选池为空，暂时没有进入板块与个股对照。'))
    gaps = [str(item) for item in proof.get('evidence_gaps') or [] if str(item).strip()]
    if gaps:
        p = _text(soup, 'p', '当前阻塞：' + '、'.join(gaps) + '。')
        p['class'] = ['reader-wavy-red']
        section.append(p)
    if statuses:
        status_text = '；'.join(f'{key} {value} 只' for key, value in statuses.items())
        section.append(_text(soup, 'p', '候选去向：' + status_text + '。'))
    if mainline_missing or account_missing or missing_risk:
        details = []
        if mainline_missing:
            details.append(f'{mainline_missing} 份候选记录缺少可消费的主线字段')
        if account_missing:
            details.append(f'{account_missing} 份候选记录缺少账户事实')
        if missing_risk:
            details.append('主样本仍缺少' + '、'.join(missing_risk))
        p = _text(soup, 'p', '数据缺口：' + '；'.join(details) + '。')
        p['class'] = ['reader-wavy-amber']
        section.append(p)
    action = action or '0%不参与'
    note = _text(soup, 'p', f'当前动作：{action}。这表示条件未齐，不表示市场没有上涨方向。')
    note['class'] = ['reader-highlight']
    section.append(note)
    return section


def _fold_tournament(soup, section):
    # Keep the leading summary table intact; the remaining original evidence is
    # available on demand without changing its words, order, or table cells.
    first_table = section.select_one('table')
    if first_table is None:
        return
    anchor = first_table
    while anchor.parent is not section:
        anchor = anchor.parent
    rest = list(anchor.next_siblings)
    if not any(str(node).strip() for node in rest):
        return
    details = soup.new_tag('details', attrs={'class': 'compact-evidence-detail'})
    details.append(_text(soup, 'summary', '展开完整板块证据与反证'))
    for node in rest:
        details.append(node.extract())
    section.append(details)


def _refresh_chart_renderers(soup):
    """Reuse current chart rendering code while retaining frozen HTML and payloads."""
    start = 'const escapeText ='
    end = 'const setupTimelineTooltips ='
    template = (Path(__file__).resolve().parents[1] / 'templates' / 'daily_report_markdown_reader.html').read_text(encoding='utf-8')
    current = template[template.index(start):template.index(end)]
    for script in soup.find_all('script'):
        if script.get('src') or script.get('type') == 'application/json':
            continue
        source = script.string or script.get_text()
        if start in source and end in source:
            script.string = source[:source.index(start)] + current + source[source.index(end):]


def _normalize_cffex_position_window(soup):
    """Make extracted historical futures cards open at the available 60-day view."""
    card = soup.select_one('[data-bear-chart-card="cffex_position_trend"]')
    if card is None:
        return
    footnote = card.select_one('.bear-chart-footnote')
    if footnote is not None:
        footnote.string = footnote.get_text().replace(
            '默认显示最近20日，可切换到最多60日；',
            '默认显示最近60个交易日，可切换20日；不足60日按已有样本展示；',
        )
    control = card.select_one('[data-bear-chart-window-control="cffex_position_trend"]')
    if control is None:
        control = soup.new_tag('div', attrs={
            'class': 'bear-chart-window-control',
            'data-bear-chart-window-control': 'cffex_position_trend',
            'role': 'group', 'aria-label': '股指期货净空结构趋势时间范围',
        })
        for size in (20, 60):
            button = _text(soup, 'button', f'{size}日')
            button['type'] = 'button'
            button['data-window-size'] = str(size)
            control.append(button)
        toolbar = soup.new_tag('div', attrs={'class': 'bear-chart-toolbar'})
        toolbar.append(control)
        frame = card.select_one('.bear-chart-frame')
        if frame is not None:
            frame.insert_before(toolbar)
        else:
            card.append(toolbar)
    for button in card.select('button[data-window-size]'):
        button['aria-pressed'] = str(button.get('data-window-size') == '60').lower()






def render_compact(source_html, rows, target_date, *, snapshot=None, previous_snapshot=None,
                   previous_record=None, origin='historical_rebuild', hypothesis_record=None, tracked_evidence=(),
                   trend_evidence=None, chart_facts=None, leader_board=None):
    soup = BeautifulSoup(source_html, 'html.parser')
    _refresh_chart_renderers(soup)
    _normalize_cffex_position_window(soup)
    if soup.title is None or target_date not in soup.title.get_text():
        raise ValueError('日报日期与目标日期不一致')
    clean = seal_rows(rows, target_date)
    main = soup.new_tag('main', attrs={'class': 'compact-main reader-flow'})
    main.append(_text(soup, 'h1', target_date + ' 日报 · 图表精简版'))
    main.append(_text(soup, 'p',
        f'按确认清单保留 {len(SELECTION)} 项。目标日缺失事实保留说明，长证据可展开。'
        '封板金额只反映收盘截面，不单独产生买入资格。'))
    for key, label in SELECTION:
        if key == 'execution':
            card = _section(soup, label)
            if card is not None:
                card['class'] = [*card.get('class', []), 'reader-action']
        elif key == 'seal_amount':
            card = _seal_section(soup, clean, target_date)
        elif key == 'sector_hypotheses':
            card = _sector_hypothesis_section(
                soup, snapshot, target_date, previous_snapshot, previous_record,
                origin=origin, hypothesis_record=hypothesis_record, tracked_evidence=tracked_evidence,
                trend_evidence=trend_evidence, chart_facts=chart_facts, leader_board=leader_board,
            )
        elif key in SECTION_IDS:
            card = _section(soup, label)
            if key == 't2' and card is not None:
                _fold_tournament(soup, card)
        else:
            card = soup.select_one(f'[data-bear-chart-card="{key}"]')
            if card is not None:
                card.extract()
                if key == 'market_turnover_trend':
                    note = _text(soup, 'p',
                        '柱色：低于1.5万亿为紫色；1.5万亿至不足2万亿为绿色；2万亿及以上为红色。'
                        '红绿柱与T0市场底色一致，2万亿为绿色虚线；'
                        '仅当图中有低于1.5万亿的数据时，显示1.5万亿紫色虚线。')
                    note['class'] = 'bear-chart-footnote'
                    card.append(note)
                if key == 'cffex_position_trend':
                    footnote = card.select_one('.bear-chart-footnote')
                    if footnote is not None:
                        footnote.string = footnote.get_text().replace(
                            '目标日精确值与名义金额复核见下表',
                            '目标日精确值与名义金额复核见完整版持仓表',
                        )
        if card is None:
            card = soup.new_tag('section', attrs={'class': 'bear-chart-card'})
            card.append(_text(soup, 'h2', label))
            card.append(_text(soup, 'p', '目标日事实不足，暂无图表。'))
        card['data-compact-item'] = key
        main.append(card)
        if key == 'execution':
            diagnostic = _execution_diagnostic(soup, snapshot, target_date)
            if diagnostic is not None:
                main.append(diagnostic)
    scripts = [script.extract() for script in soup.find_all('script')]
    soup.body.clear()
    soup.body.append(main)
    for script in scripts:
        soup.body.append(script)
    style = soup.new_tag('style')
    style.string = '''
.compact-main{max-width:1180px;margin:auto;padding:24px;min-width:0}
.reader-flow{max-width:760px;padding:40px 28px 80px;color:#3e3732;font-family:"Noto Serif SC","Songti SC","STSong","PingFang SC",serif;font-size:16px;line-height:2.05;background:#fffdf8}
.reader-flow>h1{font-size:30px;line-height:1.35;font-weight:700;letter-spacing:0;margin:0 0 12px}
.reader-flow>p{margin:0 0 28px;color:#746960;font-size:14px;line-height:1.8}
.reader-flow .compact-evidence,.reader-flow .bear-chart-card,.reader-flow .reader-diagnostic,.reader-flow .sector-daily-section{background:transparent;border:0;border-radius:0;box-shadow:none;padding:0;margin:42px 0}
.reader-flow .reader-action{margin-top:20px;padding:0 0 28px;border-bottom:1px solid #ded4c8}
.reader-flow h2,.reader-flow h3,.reader-flow h4{font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;color:#2c2521;line-height:1.45}
.reader-flow h2{font-size:22px;margin:0 0 18px;padding-left:14px;border-left:3px solid #6f6258}
.reader-flow h3{font-size:18px;margin:26px 0 12px}
.reader-flow strong,.reader-flow b{font-weight:700;background:linear-gradient(transparent 58%,rgba(255,222,93,.62) 58%,rgba(255,222,93,.62) 92%,transparent 92%);box-decoration-break:clone;-webkit-box-decoration-break:clone}
.reader-flow mark,.reader-highlight{background:linear-gradient(transparent 48%,rgba(255,222,93,.72) 48%,rgba(255,222,93,.72) 94%,transparent 94%);color:inherit}
.reader-flow .reader-wavy-red{text-decoration-line:underline;text-decoration-style:wavy;text-decoration-color:#b74a43;text-decoration-thickness:1.5px;text-underline-offset:4px}
.reader-flow .reader-wavy-amber{text-decoration-line:underline;text-decoration-style:wavy;text-decoration-color:#b27a2c;text-decoration-thickness:1.5px;text-underline-offset:4px}
.reader-flow .reader-diagnostic{padding:18px 0 4px;border-bottom:1px solid #ded4c8}
.reader-flow .reader-diagnostic-title{font-size:19px;border-left-color:#a55248}
.reader-flow .reader-diagnostic p{margin:8px 0}
.reader-flow .bear-chart-copy p,.reader-flow .bear-chart-footnote,.reader-flow small{color:#746960}
.reader-flow .compact-evidence-detail,.reader-flow .sector-daily-archive{border-top:1px solid #ded4c8}
.reader-flow .compact-evidence-detail>summary,.reader-flow .sector-daily-archive>summary{padding:12px 0;color:#655950;font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.compact-main .bear-chart-card{margin:22px 0}
.compact-evidence{background:#fff;border-radius:16px;padding:20px;margin:22px 0;overflow:auto}
.compact-main table{max-width:100%}.compact-main p{overflow-wrap:anywhere}
.compact-sector-facts{max-width:100%;overflow:auto;margin:12px 0}
.compact-sector-facts table{min-width:560px;border-collapse:collapse}
.compact-hypothesis-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0}
.compact-hypothesis-card{min-width:0;border:1px solid var(--reader-line);border-radius:12px;padding:14px}
.compact-hypothesis-card h4{margin:0 0 10px}.compact-hypothesis-card strong{display:block;margin-top:8px}
.compact-hypothesis-card p{margin:3px 0}.compact-hypothesis-card small{display:block;margin-top:10px;color:var(--reader-muted)}
.compact-observation-checks{display:grid;grid-template-columns:minmax(130px,.4fr) minmax(0,1.6fr);gap:0;margin:14px 0}
.compact-observation-checks dt,.compact-observation-checks dd{margin:0;padding:8px 10px;border-top:1px solid var(--reader-line)}
.compact-observation-checks dt{font-weight:650}.compact-observation-checks dd{overflow-wrap:anywhere}
.compact-evidence-detail{margin-top:16px}.compact-evidence-detail>summary{cursor:pointer;padding:12px;font-weight:600}
.seal-controls{display:flex;gap:8px;margin:12px 0}
.seal-controls button{font:inherit;padding:8px 14px;border:1px solid var(--reader-line);border-radius:8px;background:white;color:var(--reader-text);cursor:pointer}
.seal-controls button[aria-pressed=true]{background:var(--reader-text);color:white}
body{display:block!important;overflow-x:hidden}
@media(max-width:600px){.compact-main{padding:12px}.reader-flow{padding:28px 18px 56px;font-size:15px}.reader-flow h1{font-size:25px}.reader-flow h2{font-size:20px}.compact-evidence{padding:12px}}
@media(max-width:800px){.compact-hypothesis-cards{grid-template-columns:1fr}}
'''
    style.string += HYPOTHESIS_STYLE
    soup.head.append(style)
    script = soup.new_tag('script')
    script.string = _SEAL_SCRIPT.replace('ROWS', json.dumps(clean, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c'))
    soup.body.append(script)
    soup.title.string = target_date + ' 日报 · 图表精简版'
    return str(soup)


def main():
    parser = argparse.ArgumentParser(description='旧图表精简版生成已停用')
    parser.error(
        '旧精简版会带入已废除的操作文字，已停止生成；'
        '请使用 scripts/daily_report_entry_demo.py 的板块日报入口，或直接查阅历史原件'
    )


if __name__ == '__main__':
    main()
