"""Independent factual inputs for the sector product, with no account workflow."""
from collections import defaultdict
from datetime import date, timedelta
import json
from pathlib import Path


def _compact_history_snapshot(value, expected_date, notes):
    """Keep current facts after validating the prior comparison on its full source."""
    if value.get('date') != expected_date or not isinstance(value.get('data'), dict):
        raise ValueError('历史快照文件名与事实日期不符')
    facts = value['data']
    compact = {key: facts[key] for key in (
        'market_stats', 'wind_a_alternative', 'turnover_data',
        'new_high_feedback', 'top50_turnover_share_series',
        'recent_mainline_history', 'current_mainline_history_record',
        'reading_history_conflicts', 'reading_small_cap_plan',
    ) if key in facts}
    prior = facts.get('reading_choice')
    if prior:
        from report.sector_choice import validate_sector_choice
        try:
            compact['reading_choice'] = validate_sector_choice(prior, facts, expected_date)
        except (ValueError, TypeError, KeyError, AttributeError):
            notes.append('历史板块比较' + expected_date + '未通过原始事实核对，保留独立市场事实。')
    return {'date': expected_date, 'data': compact}


def build_index_view(rows, metadata, market_bars, target_date, *, trade_dates=None, index_type='I'):
    from report.sector_fact_loader import (
        _date, _normalize_nonfinite, _number, _row_date, is_reading_concept,
    )
    from report.sector_trend_tracking import price_temperature
    metadata = _normalize_nonfinite(metadata or {})
    market = {}
    for row in market_bars:
        day = _row_date(row)
        if not day or day > target_date:
            raise ValueError('全A路径来源日期缺失、矛盾或超出目标日')
        value = _number(row.get('close'))
        if day and day <= target_date and value is not None and value > 0:
            if day in market and market[day] != value:
                raise ValueError('全A同日指数存在冲突')
            market[day] = value
    observed_days = set(market)
    for row in rows:
        meta = metadata.get(row.get('ts_code')) or {}
        if (meta.get('exchange') == 'A' and meta.get('type') == index_type
                and (index_type != 'N' or is_reading_concept(meta))):
            day = _row_date(row)
            if not day or day > target_date:
                raise ValueError('板块路径来源日期超出目标日')
            observed_days.add(day)
    if trade_dates is not None:
        calendar = sorted(set(_date(day) for day in trade_dates))
        if any(not day or day > target_date for day in calendar):
            raise ValueError('板块交易日历日期不符')
        ranking_dates = calendar[-60:]
    else:
        ranking_dates = sorted(observed_days)[-60:]
    dates = ranking_dates[-30:]
    if not dates or dates[-1] != target_date:
        return None
    indexed = defaultdict(dict)
    for row in rows:
        day = _row_date(row)
        code = row.get('ts_code')
        meta = metadata.get(code) or {}
        if not day or day > target_date:
            raise ValueError('板块路径来源日期超出目标日')
        if day not in ranking_dates or meta.get('exchange') != 'A' or meta.get('type') != index_type:
            continue
        if index_type == 'N' and not is_reading_concept(meta):
            continue
        close, change = _number(row.get('close')), _number(row.get('pct_change'))
        if close is not None and close <= 0 or change is not None and change <= -100:
            raise ValueError('板块指数价格或收益无效')
        value = (close, change)
        if code in indexed and day in indexed[code] and indexed[code][day] != value:
            raise ValueError('板块路径同日行情冲突')
        indexed[code][day] = value
    tracks, heat_rows, ranking_rows = [], [], []
    for code, values in sorted(indexed.items()):
        name = str(metadata[code].get('name') or code)
        identity = 'index:' + code
        initial = values.get(dates[0], (None, None))[0]
        peak, path = None, []
        for i, day in enumerate(dates):
            close, change = values.get(day, (None, None))
            level = close / initial * 100 if close and initial else None
            benchmark = market[day] / market[dates[0]] * 100 if market.get(day) and market.get(dates[0]) else None
            if close:
                peak = max(close, peak or close)
            prior = values.get(dates[i - 5], (None, None))[0] if i >= 5 else None
            complete = i >= 5 and all(values.get(d, (None, None))[0] for d in dates[i - 5:i + 1])
            five = (close / prior - 1) * 100 if complete and close and prior else None
            market_five = (market[day] / market[dates[i - 5]] - 1) * 100 if i >= 5 and market.get(day) and market.get(dates[i - 5]) else None
            path.append({'date': day, 'background': day < target_date, 'change_pct': change,
                         'level': level, 'market_level': benchmark,
                         'cumulative_pct': level - 100 if level is not None else None,
                         'excess_pp': level - benchmark if level is not None and benchmark is not None else None,
                         'drawdown_pct': (close / peak - 1) * 100 if close and peak else None,
                         'five_day_pct': five, 'five_day_excess_pp': five - market_five if five is not None and market_five is not None else None,
                         'breadth': None, 'five_day_breadth': None})
        tracks.append({'track_id': identity, 'name': name, 'code': code, 'index_type': index_type,
                       'identity': f'tushare.ths_index:{index_type}:{code}', 'started_date': target_date,
                       'method': '同代码板块指数', 'path': path})
        pct = [values.get(day, (None, None))[1] for day in dates]
        heat_rows.append({'name': name, 'track_id': identity, 'pct': pct,
                          'temp': [price_temperature(value) for value in pct], 'selected': [False] * len(dates)})
        ranking_rows.append({'name': name, 'track_id': identity,
                             'pct': [values.get(day, (None, None))[1] for day in ranking_dates]})
    if not tracks:
        return None
    view = {'target_date': target_date, 'index_type': index_type,
            'calendar_verified': trade_dates is not None, 'trade_dates': dates, 'tracks': tracks, 'focus_track': None,
            'selected_track_id': tracks[0]['track_id'], 'selected_date': target_date,
            'focus_note': ('本次可用概念指数样本' if index_type == 'N' else '本次可用行业指数样本') +
                          '；没有自动指定主攻，历史路径为本次查询的比较背景。',
            'reading_terms': [], 'heat': {'dates': dates, 'rows': heat_rows},
            'ranking_returns': {'dates': ranking_dates, 'rows': ranking_rows}, 'display_context': {}}
    if index_type == 'N':
        view['price_inputs'] = {
            'index_type': index_type, 'metadata': metadata, 'trade_dates': ranking_dates,
            'rows': [{'ts_code': code, 'trade_date': day, 'close': values[0], 'pct_change': values[1]}
                     for code, days in sorted(indexed.items()) for day, values in sorted(days.items())],
            'market_bars': [{'date': day, 'close': value} for day, value in sorted(market.items())
                            if day in ranking_dates],
        }
    return view


def collect_index_view(pro, metadata, target_date, *, index_type='I', price_supplement=None):
    from market_data.tushare_service import fetch_daily_price_bars
    from market_data.tushare_market_activity_service import fetch_tushare_open_trade_dates
    from report.sector_fact_loader import _date

    start = (date.fromisoformat(target_date) - timedelta(days=140)).isoformat()
    market = fetch_daily_price_bars('000985', start, target_date, is_index=True, pro=pro)
    calendar = fetch_tushare_open_trade_dates(start, target_date, pro=pro) if callable(getattr(pro, 'trade_cal', None)) else None
    days = calendar[-60:] if calendar is not None else sorted({_date(row.get('date') or row.get('trade_date')) for row in market
                   if _date(row.get('date') or row.get('trade_date'))
                   and _date(row.get('date') or row.get('trade_date')) <= target_date})[-60:]
    if not days or days[-1] != target_date:
        return None
    rows = []
    # Bound each date range: the provider rejects offsets beyond 100,000.
    # ths_daily also caps each response at 3,000 rows.
    page_size = 3000
    for index in range(0, len(days), 20):
        window = days[index:index + 20]
        offset = 0
        while True:
            page = pro.ths_daily(start_date=window[0].replace('-', ''), end_date=window[-1].replace('-', ''),
                                 limit=page_size, offset=offset).to_dict('records')
            if any(not (day := _date(row.get('trade_date'))) or not window[0] <= day <= window[-1]
                   for row in page):
                raise ValueError('板块历史来源日期超出查询分段')
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += len(page)
            if offset > 100000:
                raise ValueError('板块历史单段返回数量超出来源分页范围')
    if price_supplement is not None and index_type == 'N':
        from market_data.iwencai_concept_prices import merge_price_rows
        rows = merge_price_rows(rows, price_supplement, target_date)
    return build_index_view(rows, metadata, market, target_date, trade_dates=calendar, index_type=index_type)


def collect_reading_supplements(data, target_date, *, pro, metadata, snapshot_root=None, service=None):
    from market_data.tushare_market_activity_service import fetch_tushare_sector_flow, fetch_tushare_top_list
    from market_data.tushare_service import fetch_daily_price_bars
    from report.sector_fact_loader import _date, _number
    from report.sector_reading_history import evidence_hash
    from report.hypothesis_revision import _observation_flow
    from report.sector_snapshot_charts import snapshot_chart_payload

    # An injected non-client used by offline callers must not trigger network.
    if not callable(getattr(pro, 'query', None)):
        return
    query = data['query_date']
    stamp = data['reading_collected_at']
    chart_payload = data.setdefault('reading_chart_payload', {})
    notes = data['reading_source_notes']

    def optional(label, task):
        try:
            return task()
        except Exception as error:
            notes.append(f'{label}未能取得（{type(error).__name__}）；保留缺口，不用当前数据补历史。')
            return None

    def fact(items, source):
        return {'target_date': target_date, 'source_date': target_date, 'query_date': query,
                'retrieved_at': stamp, 'data_source': source, 'items': items}

    def exact(rows):
        if any(_date(r.get('trade_date')) != target_date for r in rows):
            raise ValueError('补充事实日期不符')
        return rows

    flows = optional('行业资金', lambda: exact(fetch_tushare_sector_flow(target_date, pro=pro)))
    if flows:
        rows = [{**r, 'name': r.get('industry'), 'code': r.get('ts_code'), 'change_pct': r.get('pct_change'),
                 'stock_count': int(count) if (count := _number(r.get('company_num'))) is not None
                 and count >= 0 and count.is_integer() else None,
                 'trade_date': target_date, 'source_date': target_date, 'query_date': query,
                 'retrieved_at': stamp, 'data_source': 'tushare.moneyflow_ind_ths'} for r in flows]
        data['sector_fund_flow'] = {'inflow': [r for r in rows if (_number(r.get('net_amount')) or 0) >= 0],
                                    'outflow': [r for r in rows if (_number(r.get('net_amount')) or 0) < 0]}

    seals = optional('收盘封单', lambda: exact(pro.limit_list_d(
        trade_date=target_date.replace('-', ''), fields='trade_date,ts_code,name,close,pct_chg,fd_amount,limit'
    ).to_dict('records')))
    if seals is not None:
        seals = [{**row, **{key: _number(row.get(key))
                           for key in ('close', 'pct_chg', 'fd_amount')}} for row in seals]
        data['limit_list_d'] = seals
    seal_status = {r['ts_code']: '涨停' if r.get('limit') == 'U' else '跌停'
                   for r in seals or [] if r.get('limit') in ('U', 'D')}
    disclosures = optional('龙虎榜', lambda: exact(fetch_tushare_top_list(target_date, pro=pro)))
    if disclosures:
        unique = {}
        for r in disclosures:
            code, amount = r.get('ts_code'), _number(r.get('net_amount'))
            if not code or amount is None:
                continue
            # Different disclosures are not summed into a fictitious stock flow.
            unique[(code, amount, r.get('reason'))] = {'code': code.split('.')[0],
                'name': r.get('name') or code, 'amount': amount / 1e8, 'abs_amount': abs(amount) / 1e8,
                'change_pct': r.get('pct_change'), 'status': seal_status.get(code, ''),
                'reason': r.get('reason'), 'trade_date': target_date, 'source_date': target_date, 'query_date': query}
        items = []
        for side, values in (('buy', sorted((r for r in unique.values() if r['amount'] > 0), key=lambda r: -r['amount'])),
                             ('sell', sorted((r for r in unique.values() if r['amount'] < 0), key=lambda r: r['amount']))):
            items.extend({**r, 'rank': i, 'side': side} for i, r in enumerate(values[:10], 1))
        if items:
            chart_payload['lhb_net_flow'] = fact(items, 'tushare.top_list（逐项披露，不合并不同原因）')

    root = Path(snapshot_root) if snapshot_root else Path(__file__).resolve().parents[2] / 'snapshots'
    snapshots = []
    paths = [p for p in sorted(root.glob('????-??-??.json')) if p.stem < target_date][-24:]
    for path in paths:
        def read(path=path):
            value = json.loads(path.read_text(encoding='utf-8'))
            return _compact_history_snapshot(value, path.stem, notes)
        value = optional('本地历史' + path.stem, read)
        if value:
            snapshots.append(value)
    history = [*snapshots[-24:], {'date': target_date, 'data': data}]
    breadth, turnover, highs = [], [], []
    mainline_versions = defaultdict(list)
    from report.sector_reading_content import recorded_fact
    for snapshot in history:
        day, facts = snapshot['date'], snapshot['data']
        stats = recorded_fact(facts.get('market_stats'), day)
        index = recorded_fact(facts.get('wind_a_alternative'), day)
        amount = recorded_fact(facts.get('turnover_data'), day)
        high = recorded_fact(facts.get('new_high_feedback'), day)
        if stats:
            breadth.append({**stats, 'date': day, 'all_a_change_pct': index.get('change_pct'),
                            'new_high_share_pct': high.get('all_a_share_pct')})
        if amount:
            share_series = facts.get('top50_turnover_share_series') or {}
            share = next((r for r in share_series.get('rows', []) if _date(r.get('trade_date')) == day), {})
            provenance_fields = ('source', 'data_source', 'source_date', 'query_date', 'retrieved_at', 'available_at')
            # Validate the actual inherited dates, not only the original row.
            inherited = {key: share.get(key) or share_series.get(key) for key in provenance_fields
                         if share.get(key) or share_series.get(key)}
            share = recorded_fact({**share, **inherited}, day) if share else {}
            share_provenance = {key: share[key] for key in provenance_fields if share.get(key)}
            turnover.append({**amount, 'date': day, 'total_turnover': amount.get('total_turnover_yi'),
                             'top50_share_pct': share.get('share_pct'), 'top50_turnover': share.get('top_amount_yi'),
                             'top50_sample_label': share.get('sample_label') or str(share_series.get('query_window') or '历史口径未完整记录'),
                             'top50_scope': ('hs_a' if (share_series.get('query_window') or {}).get('rank_scope') == 'hs_a'
                                             else 'unknown'),
                             'top50_market_amount_yi': share.get('market_amount_yi'),
                             'share_provenance': share_provenance})
        if high:
            highs.append({**high, 'date': day, 'new_high_share_pct': high.get('all_a_share_pct')})
        records = [(row, [day]) for row in [*(facts.get('recent_mainline_history') or []),
            *([facts['current_mainline_history_record']] if facts.get('current_mainline_history_record') else [])]]
        for conflict in facts.get('reading_history_conflicts') or []:
            for version in conflict['versions']:
                row, origins = version['record'], version['snapshot_dates']
                if (row.get('date') != conflict['date'] or not isinstance(origins, list)
                        or any(_date(origin) != origin or not row['date'] <= origin <= day for origin in origins)):
                    raise ValueError('历史接力版本的日期与所在快照不符')
                records.append((row, [*origins, day]))
        for row, origins in records:
            if _date(row.get('date')) and row['date'] < target_date:
                record_day = row['date']
                versions = mainline_versions[record_day]
                version = next((item for item in versions if item['record'] == row), None)
                if version is None:
                    version = {'record': row, 'snapshot_dates': []}
                    versions.append(version)
                for origin in origins:
                    if origin not in version['snapshot_dates']:
                        version['snapshot_dates'].append(origin)
    # Conflicting optional history is a dated gap, not a choice of one version
    # and not a reason to discard independently valid current market facts.
    data['recent_mainline_history'] = [mainline_versions[day][0]['record']
        for day in sorted(mainline_versions) if len(mainline_versions[day]) == 1]
    conflicts = [{'date': day, 'versions': mainline_versions[day]}
                 for day in sorted(mainline_versions) if len(mainline_versions[day]) > 1]
    if conflicts:
        data['reading_history_conflicts'] = conflicts
        notes.append('历史接力记录存在版本差异：' + '、'.join(item['date'] for item in conflicts)
                     + '。这些日期不选定版本、不生成接力节点；原始版本与所在快照日期保留在本次快照中。')
    if breadth and breadth[-1]['date'] == target_date:
        chart_payload['t0_market_breadth'] = fact(breadth, '目标日事实与本地冻结快照；原查询字段按行保留')
    if turnover and turnover[-1]['date'] == target_date:
        start = turnover[0]['date']
        bars = optional('创业板历史', lambda: fetch_daily_price_bars('399006', start, target_date, is_index=True, pro=pro)) or []
        closes = {_date(r.get('date') or r.get('trade_date')): r.get('close') for r in bars}
        for row in turnover:
            row['chinext_close'] = closes.get(row['date'])
            if row['chinext_close'] is not None:
                row['chinext_provenance'] = {'data_source': 'tushare.index_daily', 'source_date': row['date'],
                                             'query_date': query, 'retrieved_at': stamp}
        chart_payload['market_turnover_top50_trend'] = fact(turnover, '目标日事实与本地冻结快照；创业板tushare.index_daily')

    from report.sector_top50 import collect_top50_series
    concentration = optional('同口径Top50历史', lambda: collect_top50_series(pro, target_date,
        provider_hosts=(data.get('reading_collection') or {}).get('configured_provider_hosts', [])))
    if concentration:
        data['reading_top50'] = concentration
        chart_payload['market_turnover_top50_trend'] = {k: v for k, v in concentration.items() if k != 'inputs'}

    from report.market_returns import collect_market_returns
    market_returns = optional('全市场个股与大盘关系', lambda: collect_market_returns(pro, target_date,
        provider_hosts=(data.get('reading_collection') or {}).get('configured_provider_hosts', [])))
    if market_returns:
        data['reading_market_returns'] = market_returns

    if service is None:
        from storage.database_service import DatabaseService
        service = optional('本地事实库', DatabaseService.from_environment)
    from report.sector_new_high import collect_new_high_series
    new_high = optional('创新高交易日统计', lambda: collect_new_high_series(pro, target_date))
    if new_high:
        data['reading_new_high'] = new_high
        gaps = [r for r in new_high['items'] if r.get('missing_reason')]
        if gaps:
            notes.append('创新高缺失：' + '；'.join(r['date'] + ' ' + r['missing_reason'] for r in gaps))
    from report.cffex_index_futures_position_evidence import load_cffex_index_futures_position_evidence
    evidence = optional('期货持仓', lambda: load_cffex_index_futures_position_evidence(
        target_date, service=service, replay=False, query_date=query, allow_fresh_write=False))
    if evidence:
        data['cffex_index_futures_position_evidence'] = evidence
        if evidence.get('availability') != 'complete' or evidence.get('missing_reasons'):
            notes.append('股指期货持仓事实不足：' + '；'.join(evidence.get('missing_reasons') or ['来源未返回完整资料']))
    if not new_high and highs:
        highs = [row for row in highs if row['date'] < target_date]
        highs.append({'date': target_date, 'new_high_count': None, 'new_high_share_pct': None,
                      'missing_reason': '目标日独立统计未取得，未用旧值代替'})
        chart_payload['new_high_share_trend'] = fact(sorted(highs, key=lambda r: r['date']),
            '本地冻结创新高事实；统计来源与分母可能不同，不作同口径连续比较')

    index_type = 'N' if data.get('sector_universe') == 'concept' else 'I'
    view = optional('板块跨日价格', lambda: collect_index_view(pro, metadata, target_date, index_type=index_type,
        price_supplement=data.get('reading_concept_prices')))
    if view:
        if evidence and view.get('calendar_verified') is True:
            from report.cffex_index_futures_position_evidence import align_cffex_history_calendar
            evidence = optional('期货真实交易日历对照', lambda: align_cffex_history_calendar(
                evidence, (view.get('price_inputs') or {}).get('trade_dates') or view['trade_dates'],
                calendar_source='tushare.trade_cal:SSE')) or evidence
            data['cffex_index_futures_position_evidence'] = evidence
        from report.sector_member_comparison import collect_member_comparison
        members = optional('精选板块成分股', lambda: collect_member_comparison(pro, view))
        if members:
            view['member_comparison'] = members
            from report.sector_market_relation import collect_member_history
            member_history = optional('成员20日大盘关系', lambda: collect_member_history(pro, view,
                provider_hosts=(data.get('reading_collection') or {}).get('configured_provider_hosts', [])))
            if member_history:
                data['reading_member_history'] = member_history
        assets = {'target_date': target_date, 'record_hash': None, 'trend': view,
                  'trend_provenance': {'retrieved_at': stamp, 'source': 'tushare.ths_daily+index_daily',
                      'configured_provider_hosts': (data.get('reading_collection') or {}).get('configured_provider_hosts', [])},
                  'flow': _observation_flow({'target_date': target_date, 'history': data['recent_mainline_history'],
                                            'trade_dates': view['trade_dates']}, target_date)}
        if data.get('reading_concept_prices'):
            supplement = data['reading_concept_prices']
            assets['trend_provenance']['price_supplement'] = {key: supplement[key] for key in
                ('source', 'target_date', 'query_date', 'retrieved_at', 'endpoint', 'sample_count', 'artifact_hash')}
        if index_type == 'N':
            from report.sector_concept_flow import collect_concept_flow
            flow = optional('概念逐日净额', lambda: collect_concept_flow(
                pro, target_date, view['trade_dates'], metadata,
                calendar_verified=view['calendar_verified'],
                directory_provenance={key: value for key, value in (data.get('concept_directory') or {}).items()
                                      if key in ('source', 'query_date', 'retrieved_at', 'basis')}
                                     if (data.get('concept_directory') or {}).get('retrieved_at') else None,
                provider_hosts=(data.get('reading_collection') or {}).get('configured_provider_hosts', [])))
            if flow:
                assets['concept_flow'] = flow
            else:
                assets['concept_flow_missing'] = '概念净额事实未取得，不以旧接力或行业资金替代。'
        assets['source_sha256'] = evidence_hash(assets)
        data['reading_sector_history'] = assets
        if index_type == 'N':
            from report.sector_choice import build_sector_choice
            def compare():
                previous = None
                for saved in reversed(snapshots):
                    prior = saved['data'].get('reading_choice')
                    if prior:
                        previous = prior  # validated against its full snapshot before pruning
                        break
                return build_sector_choice(data, target_date, previous=previous)
            choice = optional('板块机会比较', compare)
            if choice:
                data['reading_choice'] = choice
    if data.get('reading_market_returns'):
        from report.daily_extras import collect_extras, refresh_comparison_history
        from report.small_cap_rotation import refresh_plan_inputs
        optional('小盘轮换对照指数', lambda: refresh_comparison_history(pro, target_date))
        optional('执行计划的交易日历与财报指标', lambda: refresh_plan_inputs(pro, target_date))
        optional('小盘轮换名单与单期模拟', lambda: collect_extras(data, target_date, snapshots=snapshots))
    data['reading_chart_payload'].update({k: v for k, v in snapshot_chart_payload(data, target_date).items()
                                         if k not in chart_payload})
