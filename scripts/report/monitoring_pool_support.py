from __future__ import annotations

from report.monitoring_pool_rule_nodes import collect_monitoring_pool_candidates_via_nodes


def _safe_float(value, default=0.0):
    try:
        if value in (None, ''):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _pct(base, value):
    base = _safe_float(base, 0.0)
    value = _safe_float(value, 0.0)
    if not base:
        return 0.0
    return (value / base - 1.0) * 100.0


def get_volume_state(volume, previous_volume):
    volume = _safe_float(volume, 0.0)
    previous_volume = _safe_float(previous_volume, 0.0)
    if not previous_volume:
        return '-'
    if volume > previous_volume * 1.15:
        return '放量'
    if volume < previous_volume * 0.85:
        return '缩量'
    return '平量'


def get_candle_shape(bar):
    open_price = _safe_float((bar or {}).get('open'))
    high_price = _safe_float((bar or {}).get('high'))
    low_price = _safe_float((bar or {}).get('low'))
    close_price = _safe_float((bar or {}).get('close'))
    candle_range = high_price - low_price
    if candle_range <= 0:
        return '一字'
    body = abs(close_price - open_price)
    close_position = (close_price - low_price) / candle_range
    if close_price > open_price:
        if body / candle_range >= 0.6 and close_position >= 0.7:
            return '大阳柱'
        if (high_price - close_price) > body * 0.8:
            return '上影阳线'
        return '阳线'
    if close_price < open_price:
        if body / candle_range >= 0.6 and close_position <= 0.3:
            return '大阴柱'
        if (close_price - low_price) > body * 0.8:
            return '下影阴线'
        return '阴线'
    return '十字'


def build_monitoring_row(bar, *, previous_bar=None, selected_next_day_close=None, day_index=0):
    bar = dict(bar or {})
    previous_bar = dict(previous_bar or {})
    high_price = _safe_float(bar.get('high'))
    low_price = _safe_float(bar.get('low'))
    close_price = _safe_float(bar.get('close'))
    candle_range = high_price - low_price
    close_position = (close_price - low_price) / candle_range if candle_range > 0 else 1.0
    previous_close = previous_bar.get('close')
    previous_volume = previous_bar.get('volume')
    row = {
        'date': bar.get('date', ''),
        'open': _safe_float(bar.get('open')),
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'volume': _safe_float(bar.get('volume')),
        'daily_change_pct': _pct(previous_close, close_price) if previous_close is not None else 0.0,
        'cum_change_pct_from_next_day': _pct(selected_next_day_close, close_price) if selected_next_day_close is not None else 0.0,
        'trading_days_since_selected': int(day_index or 0),
        'close_position_in_range': close_position,
        'volume_state': get_volume_state(bar.get('volume'), previous_volume),
        'candle_shape': get_candle_shape(bar),
    }
    if row['close_position_in_range'] >= 0.7 and row['daily_change_pct'] >= 0:
        row['day_label'] = '趋势'
    elif row['close_position_in_range'] <= 0.2:
        row['day_label'] = 'A杀警报'
    else:
        row['day_label'] = '弱修复' if row['daily_change_pct'] <= 0 else '震荡'
    return row


def _normalize_candidate(stock, source_pool):
    return {
        'stock_name': stock.get('name', ''),
        'stock_code': stock.get('code', ''),
        'source_pool': source_pool,
    }


def collect_monitoring_pool_candidates(context):
    context = context or {}
    return collect_monitoring_pool_candidates_via_nodes(context)


def classify_monitoring_pattern(rows, pattern_hint=''):
    hint = str(pattern_hint or '').lower()
    if hint in ('bojie', 'longpan'):
        return 'trend_continuation'
    if hint in ('zhongjia', 'jinyao'):
        return 'fast_in_fast_out'
    if hint in ('shida',):
        return 'range_consumption'
    rows = rows or []
    if len(rows) < 3:
        return 'range_consumption'
    start_close = _safe_float(rows[0].get('close'))
    end_close = _safe_float(rows[-1].get('close'))
    mid_close = min(_safe_float(item.get('close')) for item in rows[1:-1]) if len(rows) > 2 else end_close
    if end_close > start_close * 1.15 and end_close > mid_close * 1.1:
        return 'trend_continuation'
    if mid_close < start_close * 0.93:
        return 'fast_in_fast_out'
    return 'range_consumption'


def assess_monitoring_status(pattern_type, *, latest_close=0.0, anchor_price=0.0):
    latest_close = _safe_float(latest_close)
    anchor_price = _safe_float(anchor_price)
    if pattern_type == 'trend_continuation':
        return {'tracking_status': 'active', 'current_assessment': '保留', 'assessment_reason': '趋势延续，继续跟踪'}
    if pattern_type == 'fast_in_fast_out':
        state = 'watch' if latest_close <= anchor_price else 'active'
        return {'tracking_status': state, 'current_assessment': '观察', 'assessment_reason': '快进快出型，窗口短，需快节奏跟踪'}
    return {'tracking_status': 'watch', 'current_assessment': '观察', 'assessment_reason': '震荡消耗型，保留观察但降低优先级'}


def build_monitoring_pool_summary(context, target_date, *, helpers=None):
    helpers = helpers or {}
    fetch_daily_price_bars = helpers.get('fetch_daily_price_bars')
    pools = collect_monitoring_pool_candidates(context)

    def _decorate(items):
        decorated = []
        for item in items:
            pattern_hint = ''
            code = item.get('stock_code', '')
            if code == '002975':
                pattern_hint = 'bojie'
            elif code == '603906':
                pattern_hint = 'longpan'
            elif code == '603026':
                pattern_hint = 'shida'
            elif code == '000889':
                pattern_hint = 'zhongjia'
            elif code == '600488':
                pattern_hint = 'jinyao'
            pattern_type = classify_monitoring_pattern([], pattern_hint=pattern_hint)
            status = assess_monitoring_status(pattern_type)
            merged = dict(item)
            selected_date = item.get('selected_date') or context.get('selected_date') or target_date
            monitoring_rows = []
            observation_band_low = None
            observation_band_high = None
            failure_line = None
            anchor_price = None
            if callable(fetch_daily_price_bars) and item.get('stock_code'):
                bars = fetch_daily_price_bars(item.get('stock_code'), selected_date, target_date, prefer_fast=True) or []
                selected_next_day_close = _safe_float(bars[0].get('close')) if bars else None
                anchor_price = selected_next_day_close if bars else None
                if bars:
                    observation_band_low = min(_safe_float(bar.get('low')) for bar in bars)
                    observation_band_high = max(_safe_float(bar.get('high')) for bar in bars)
                    failure_line = round(observation_band_low * 0.99, 2)
                previous_bar = None
                for idx, bar in enumerate(bars, start=1):
                    monitoring_rows.append(
                        build_monitoring_row(
                            bar,
                            previous_bar=previous_bar,
                            selected_next_day_close=selected_next_day_close,
                            day_index=idx,
                        )
                    )
                    previous_bar = bar
            merged.update(status)
            merged.setdefault('pattern_type', pattern_type)
            merged.setdefault('days_since_selected', len(monitoring_rows) if monitoring_rows else '-')
            merged.setdefault('cum_change_pct', monitoring_rows[-1].get('cum_change_pct_from_next_day') if monitoring_rows else None)
            merged['anchor_price'] = anchor_price
            merged['observation_band_low'] = observation_band_low
            merged['observation_band_high'] = observation_band_high
            merged['failure_line'] = failure_line
            merged['monitoring_rows'] = monitoring_rows
            decorated.append(merged)
        return decorated

    return {
        'target_date': target_date,
        'main_pool': _decorate(pools.get('main_pool', [])),
        'secondary_pool': _decorate(pools.get('secondary_pool', [])),
    }
