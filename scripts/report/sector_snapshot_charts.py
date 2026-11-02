"""Project frozen numerical facts without rendering or running the full report."""
from copy import deepcopy


def snapshot_chart_payload(data, target_date):
    from report.sector_reading_content import recorded_fact, _strict_number
    payload = deepcopy(data.get('reading_chart_payload') or {})

    def provenance(value):
        return {key: value[key] for key in ('data_source', 'source', 'source_date', 'query_date',
                                           'retrieved_at', 'available_at') if value.get(key)}

    def series_provenance(value, rows):
        result = provenance(value)
        target = [row for row in rows if (row.get('trade_date') or row.get('date')) == target_date]
        for key in ('source_date', 'query_date', 'retrieved_at', 'data_source'):
            values = {row.get(key) for row in target}
            if key not in result and len(values) == 1 and None not in values:
                result[key] = values.pop()
        return result

    ranks = data.get('turnover_rank') or []
    if 'turnover_top30' not in payload and ranks:
        rows = [row for row in ranks if recorded_fact(row, target_date)]
        rows = sorted(rows, key=lambda r: _strict_number(r.get('turnover')) or 0, reverse=True)[:30]
        if rows:
            payload['turnover_top30'] = {'trade_date': target_date, 'source': 'turnover_rank',
                'complete': len(rows) >= 30, 'items': [{**row, 'rank': i} for i, row in enumerate(rows, 1)]}
            for key in ('data_source', 'source_date', 'query_date', 'retrieved_at'):
                values = {row.get(key) for row in rows}
                if len(values) == 1 and None not in values:
                    payload['turnover_top30'][key] = values.pop()

    top50 = data.get('top50_turnover_share_series') or {}
    if 'market_turnover_top50_trend' not in payload and top50.get('rows'):
        items = []
        for row in top50['rows']:
            items.append({**row, 'date': row.get('trade_date'),
                          'total_turnover': row.get('market_amount_yi'), 'top50_turnover': row.get('top_amount_yi'),
                          'top50_share_pct': row.get('share_pct'), 'chinext_close': row.get('chinext_close'),
                          'top50_market_amount_yi': row.get('market_amount_yi'),
                          'top50_scope': 'hs_a' if (top50.get('query_window') or {}).get('rank_scope') == 'hs_a' else 'unknown'})
        payload['market_turnover_top50_trend'] = {**series_provenance(top50, top50['rows']),
                                                'target_date': target_date, 'items': items}

    if data.get('reading_top50') is not None:
        from report.sector_top50 import validate_top50_series
        revised = validate_top50_series(data['reading_top50'], target_date)
        payload['market_turnover_top50_trend'] = deepcopy({k: v for k, v in revised.items() if k != 'inputs'})

    high = data.get('new_high_feedback') or {}
    if not (payload.get('new_high_share_trend') or {}).get('items') and high.get('trend_rows'):
        payload['new_high_share_trend'] = {**series_provenance(high, high['trend_rows']), 'target_date': target_date,
            'items': [{**r, 'date': r.get('trade_date') or r.get('date'),
                       'new_high_share_pct': r.get('all_a_share_pct')} for r in high['trend_rows']]}

    if data.get('reading_new_high') is not None:
        from report.sector_new_high import validate_new_high_series
        payload['new_high_share_trend'] = deepcopy(validate_new_high_series(data['reading_new_high'], target_date))

    evidence = data.get('cffex_index_futures_position_evidence')
    if evidence and ('cffex_position_trend' not in payload or (evidence.get('history') or {}).get('calendar')):
        from report.cffex_index_futures_position_evidence import (
            normalize_cffex_position_trend_payload,
            validate_cffex_evidence,
        )
        valid, _ = validate_cffex_evidence(evidence, target_date=target_date)
        if not valid:
            raise ValueError('期货冻结事实日期或指纹不符')
        payload.pop('cffex_position_trend', None)
        fact = normalize_cffex_position_trend_payload(evidence, target_date)
        if fact:
            history = evidence.get('history') or {}
            if history.get('calendar'):
                fact.update(calendar=deepcopy(history['calendar']), complete_day_count=history['sample_count'])
            payload['cffex_position_trend'] = {**fact, **provenance(evidence),
                                              'data_source': evidence['source_policy']}
    return payload
