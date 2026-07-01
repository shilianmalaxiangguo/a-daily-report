from __future__ import annotations

__all__ = [
    "build_gem_horizontal_compare_cards",
    "build_recent_target_followups",
    "build_recent_target_reflection",
    "build_recent_target_review_matrix",
]

_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def build_recent_target_followups(records, as_of_date, limit=3, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_recent_target_followups_legacy_body(records, as_of_date, limit=limit)
    finally:
        _restore_runtime_bindings(previous)


def build_recent_target_reflection(review_matrix, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_recent_target_reflection_legacy_body(review_matrix)
    finally:
        _restore_runtime_bindings(previous)


def build_recent_target_review_matrix(current_plan, recent_followups, limit=4, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_recent_target_review_matrix_legacy_body(current_plan, recent_followups, limit=limit)
    finally:
        _restore_runtime_bindings(previous)


def build_gem_horizontal_compare_cards(gem_cycle_cards=None, review_matrix=None, limit=4, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_horizontal_compare_cards_legacy_body(
            gem_cycle_cards=gem_cycle_cards,
            review_matrix=review_matrix,
            limit=limit,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_recent_target_followup_item(record, as_of_date):
    record = record or {}
    code = normalize_stock_code(record.get('stock_code', ''))
    report_date = _normalize_kline_date_str(record.get('report_date'))
    as_of_date = _normalize_kline_date_str(as_of_date)
    stock_name = str(record.get('stock_name') or '').strip()
    if not code or not report_date or not as_of_date or not stock_name:
        return {}

    tracking_days = _count_trading_days_between(report_date, as_of_date)
    if tracking_days <= 1 or tracking_days > 6:
        return {}

    bars = fetch_daily_price_bars(code, report_date, as_of_date, is_index=False)
    bars = [
        bar for bar in (bars or [])
        if report_date <= _normalize_kline_date_str(bar.get('date')) <= as_of_date
    ]
    if not bars:
        return {}

    latest_bar = _get_last_bar_on_or_before(bars, as_of_date) or bars[-1]
    latest_close = _safe_float(latest_bar.get('close'))
    latest_high = _safe_float(latest_bar.get('high'))
    latest_low = _safe_float(latest_bar.get('low'))
    if latest_close <= 0:
        return {}

    confirm_price = _round_or_none(record.get('confirm_price_60m') or record.get('entry_price_anchor'))
    support_price = _round_or_none(
        record.get('confirm_support_60m')
        or record.get('execution_stop')
        or record.get('effective_stop')
        or record.get('display_anchor_price')
    )
    contract_kind = str(record.get('contract_kind', '') or '').strip()
    contract_window_days = max(int(_safe_float(record.get('contract_active_window_days', 0))), 0)
    contract_trigger_price = _round_or_none(record.get('contract_right_side_trigger_price') or confirm_price)
    contract_void_price = _round_or_none(record.get('contract_void_price') or support_price)
    contract_reset_breakout_price = _round_or_none(record.get('contract_reset_breakout_price'))
    attribution_label = str((record.get('attribution', {}) or {}).get('label', '') or '').strip()
    path_metrics = _collect_record_market_path(record, as_of_date) or {}
    observed_return = path_metrics.get('observed_return')
    max_runup = path_metrics.get('max_runup')

    support_broken = bool(
        support_price is not None
        and support_price > 0
        and (latest_close < support_price or latest_low < support_price)
    )
    confirm_reclaimed = bool(confirm_price is not None and confirm_price > 0 and latest_close >= confirm_price)
    confirm_tested = bool(confirm_price is not None and confirm_price > 0 and latest_high >= confirm_price)

    current_position = f'收于{latest_close:.2f}'
    timeline_text = '从选出日到今天，价格还在继续演化。'
    if support_broken and support_price is not None:
        path_label = '已失守观察边界'
        current_position = f'收于{latest_close:.2f}，已跌破{support_price:.2f}观察边界'
        focus_text = (
            f'未来1-3天先按作废处理；只有重新站回{support_price:.2f}'
            f"{'并再次站上' + format(confirm_price, '.2f') if confirm_price is not None else ''}后，才重新评估。"
        )
        timeline_text = f'选出后价格一度反复，但到今天已经失守{support_price:.2f}观察边界。'
        review_hint = '这说明观察权已经失效，后续复盘不要把失守对象继续误当成可执行候选。'
    elif contract_kind == 'gem_breathing_20cm' and contract_reset_breakout_price is not None and latest_close >= contract_reset_breakout_price and (contract_void_price is None or latest_close >= contract_void_price):
        path_label = '右侧确认/再突破已出现'
        current_position = f'收于{latest_close:.2f}，已重新站上{contract_reset_breakout_price:.2f}再突破位'
        trigger_ref = contract_trigger_price if contract_trigger_price is not None else confirm_price
        if trigger_ref is not None and contract_void_price is not None:
            focus_text = f'未来1-3天重点看{contract_void_price:.2f}不能破，并继续站稳{trigger_ref:.2f}之上；当前已重新站上{contract_reset_breakout_price:.2f}再突破位，后续只在固定交易窗口内条件成立时考虑50%条件执行'
            timeline_text = f'预启动观察后价格一直没失守{contract_void_price:.2f}，到今天已重新站上{contract_reset_breakout_price:.2f}再突破位。'
        else:
            focus_text = '未来1-3天重点看再突破后能否继续横住，不满足继续只观察。'
            timeline_text = f'预启动观察后价格到今天已重新站上{contract_reset_breakout_price:.2f}再突破位。'
        review_hint = f'这说明创业板20cm预启动合同仍在{contract_window_days or 5}日窗口内，后续重点看它会不会从观察权升级到50%条件执行。'
    elif attribution_label == '个股对了但环境条件未满足':
        path_label = '个股先走出来了'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，明显站在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = f'选出当天已经完成{confirm_price:.2f}确认，之后连续几天都站在确认位之上。'
        else:
            focus_text = '未来1-3天重点看是否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = '选出后价格持续走强，明显快于最初的观察口径。'
        review_hint = '这说明对象先强于环境，后续要反查环境过滤/桥接层是不是拦得过严。'
    elif attribution_label == '弱转强识别偏慢':
        path_label = '假弱后超预期转强'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，已经沿着{confirm_price:.2f}确认位上方继续走强'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续 act right；若继续强势，下次要更早把这类假弱样本纳入升级评估'
            timeline_text = f'前面假弱承接住后，价格又重新站稳{confirm_price:.2f}并继续走强。'
        else:
            focus_text = '未来1-3天重点看是否继续 act right；若继续强势，下次要更早把这类假弱样本纳入升级评估'
            timeline_text = '前面假弱承接住后，价格又给出超预期转强。'
        review_hint = '这说明它本来就是强基底上的假弱，后续又走成超预期转强；以后不能等它完全走出来才承认弱转强。'
    elif attribution_label == '介入周期偏慢':
        path_label = '已走成 act right'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，仍在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续横住并给利润缓冲'
            timeline_text = f'选出后很快完成{confirm_price:.2f}确认，随后一直没有失去确认位。'
        else:
            focus_text = '未来1-3天重点看是否继续横住并给利润缓冲'
            timeline_text = '选出后价格很快按强股方式替判断作证。'
        review_hint = '这说明票本身没看错，慢在介入权给慢了。'
    elif confirm_reclaimed and observed_return is not None and observed_return >= 0.03:
        path_label = '已走成 act right'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，仍在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续横住并给利润缓冲'
            timeline_text = f'价格已经重新站稳{confirm_price:.2f}，并且到今天还维持在确认位上方。'
        else:
            focus_text = '未来1-3天重点看是否继续横住并给利润缓冲'
            timeline_text = '价格已经明显转强，今天仍保持强势结构。'
        review_hint = '这说明价格已经替判断作证，后续复盘不能再把它和普通观察对象混在一起。'
    elif confirm_reclaimed and max_runup is not None and max_runup >= 0.08:
        path_label = '个股先走出来了'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，明显站在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = f'价格已经越过{confirm_price:.2f}并明显展开，但系统当时没有给买入资格。'
        else:
            focus_text = '未来1-3天重点看是否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = '价格已经明显展开，但系统当时没有给买入资格。'
        review_hint = '这说明对象先强于环境，后续要反查环境过滤/桥接层是不是拦得过严。'
    elif confirm_tested and support_price is not None and latest_close >= support_price:
        path_label = '先强后回，进入二次确认'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，未破{support_price:.2f}，但还没重新站稳{confirm_price:.2f}'
            focus_text = f'未来1-3天重点看{support_price:.2f}不能破，重新站回{confirm_price:.2f}才算重新亮起介入权'
            timeline_text = f'选出后先摸到{confirm_price:.2f}，但后面没有继续强扩张；到今天仍未重新站稳确认位。'
        else:
            current_position = f'收于{latest_close:.2f}，仍在观察边界{support_price:.2f}之上'
            focus_text = f'未来1-3天重点看{support_price:.2f}不能破，再看是否重新转强'
            timeline_text = f'价格曾经有过转强尝试，但到今天更像二次确认阶段。'
        review_hint = '这说明防守不一定错，但后续要继续跟踪它会不会从观察对象重新走回唯一动作。'
    elif support_price is not None and latest_close >= support_price:
        path_label = '仍在观察周期'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，未破{support_price:.2f}观察边界，但还没重新站回{confirm_price:.2f}'
            focus_text = f'未来1-3天先看{support_price:.2f}不破，再看能否重新站上{confirm_price:.2f}'
            timeline_text = f'到今天还没失守{support_price:.2f}，但也还没重新完成{confirm_price:.2f}确认。'
        else:
            current_position = f'收于{latest_close:.2f}，仍在观察边界{support_price:.2f}之上'
            focus_text = f'未来1-3天先看{support_price:.2f}不破，再看有没有继续转强'
            timeline_text = f'到今天仍在观察边界之上，但还没有形成明确升级信号。'
        review_hint = '这说明它还没彻底走坏，但也不能把观察资格误写成买入资格。'
    else:
        path_label = '继续跟踪'
        focus_text = '未来1-3天继续看是否重新转强，不急着提前下结论。'
        timeline_text = '这段时间价格既没有彻底走坏，也没有给出足够强的升级证据。'
        review_hint = '这说明样本还没给出足够清晰的后验信号，先继续跟踪。'

    return {
        'report_date': report_date,
        'stock_label': f'{stock_name}({code})',
        'sample_label': f'{stock_name}({code})',
        'tracking_days': tracking_days,
        'phase_label': f'第{tracking_days}个交易日',
        'path_label': path_label,
        'current_position': current_position,
        'today_view': current_position,
        'timeline_text': timeline_text,
        'focus_text': focus_text,
        'next_focus': focus_text,
        'review_hint': review_hint,
        'attribution_label': attribution_label or '-',
    }


def _build_recent_target_followups_legacy_body(records, as_of_date, limit=3):
    items = []
    for record in sorted(
        records or [],
        key=lambda x: _normalize_kline_date_str(x.get('report_date')),
        reverse=True,
    ):
        item = _build_recent_target_followup_item(record, as_of_date)
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def _build_current_target_review_item(current_plan):
    current_plan = current_plan or {}
    code = normalize_stock_code(current_plan.get('stock_code', ''))
    report_date = _normalize_kline_date_str(current_plan.get('report_date'))
    stock_name = str(current_plan.get('stock_name') or '').strip()
    if not code or not report_date or not stock_name:
        return {}

    bars = fetch_daily_price_bars(code, report_date, report_date, is_index=False)
    bars = [bar for bar in (bars or []) if _normalize_kline_date_str(bar.get('date')) == report_date]
    if not bars:
        return {}

    bar = bars[-1]
    close_price = _safe_float(bar.get('close'))
    high_price = _safe_float(bar.get('high'))
    low_price = _safe_float(bar.get('low'))
    if close_price <= 0:
        return {}

    confirm_price = _round_or_none(current_plan.get('confirm_price_60m') or current_plan.get('entry_price_anchor'))
    support_price = _round_or_none(
        current_plan.get('confirm_support_60m')
        or current_plan.get('execution_stop')
        or current_plan.get('effective_stop')
        or current_plan.get('display_anchor_price')
    )
    trigger_text = str(current_plan.get('trigger_text', '') or '').strip()

    if confirm_price is not None and support_price is not None and high_price >= confirm_price and low_price < support_price:
        path_label = '确认不干净，继续观察'
        timeline_text = f'今天打到{confirm_price:.2f}，但盘中低点{low_price:.2f}先破{support_price:.2f}。'
        today_view = '收盘打到确认位，不代表确认链完整。'
        next_focus = f'未来1-3天先看{support_price:.2f}能否重新站稳，再看有没有更干净的确认。'
        review_hint = '不能因为今天收得高，就提前把它当成航天工程。'
    elif confirm_price is not None and support_price is not None and high_price >= confirm_price and low_price >= support_price:
        path_label = '日内确认相对干净'
        timeline_text = f'今天已经打到{confirm_price:.2f}，且日内没有破{support_price:.2f}。'
        today_view = f'收于{close_price:.2f}，确认链相对干净，但还缺后续连续 act right。'
        next_focus = f'未来1-3天重点看{confirm_price:.2f}之上能否继续 act right。'
        review_hint = '这时可以继续跟踪，但还不能只凭一天就认定它已经完成升级。'
    elif support_price is not None and low_price < support_price:
        path_label = '先破观察边界，暂不升级'
        timeline_text = f'今天盘中最低{low_price:.2f}，已经先破{support_price:.2f}观察边界。'
        today_view = f'收于{close_price:.2f}，但链路已经被日内破坏。'
        next_focus = f'未来1-3天先看能否重新站回{support_price:.2f}，否则按作废处理。'
        review_hint = '这说明今天更多只是探针，不该提前抬成执行对象。'
    else:
        path_label = '还在等待确认'
        if confirm_price is not None:
            timeline_text = f'今天还没有把{confirm_price:.2f}这道确认链走完整。'
            next_focus = f'未来1-3天继续看能否站上{confirm_price:.2f}并保持不破。'
        else:
            timeline_text = '今天还没把确认链走完整。'
            next_focus = '未来1-3天继续看能否给出更清楚的确认。'
        today_view = f'收于{close_price:.2f}，当前仍以观察为主。'
        review_hint = '这说明现在更适合继续观察，不适合抢着给买入资格。'

    return {
        'sample_label': f'{stock_name}({code})',
        'report_date': report_date,
        'phase_label': '报告日当天',
        'path_label': path_label,
        'timeline_text': timeline_text,
        'today_view': today_view,
        'next_focus': next_focus,
        'review_hint': review_hint,
        'trigger_text': trigger_text,
    }


def _derive_target_review_system_fix(item):
    item = item or {}
    sample_label = str(item.get('sample_label', '') or '')
    path_label = str(item.get('path_label', '') or '')
    review_hint = str(item.get('review_hint', '') or '')

    if '彩虹股份' in sample_label or '观察链不要偷写成执行链' in review_hint or '提前把它当成航天工程' in review_hint:
        return '观察链不要偷写成执行链：先继续观察，不提前升级成航天工程那种已证明样本。'
    if '弱转强识别偏慢' in review_hint or '假弱后超预期转强' in path_label or ('假弱' in review_hint and '弱转强' in review_hint):
        return '弱转强识别偏慢：对强基底+假弱非真弱、且主线共振未坏的对象，要更早从观察权升级到执行评估。'
    if '介入权给慢了' in review_hint or '已走成 act right' in path_label:
        return '介入周期偏慢：对已经确认成功且继续 act right 的唯一对象，要更快给到执行评估。'
    if '环境过滤' in review_hint or '个股先走出来了' in path_label:
        return '环境过滤过严：跨线对象若已连续 act right，不能一直停在纯观察层。'
    if '二次确认' in path_label:
        return '二次确认样本单独管理：先盯 guard 不破，再看能否重新站回 confirm，不要和已成功样本混为一类。'
    if '失守' in path_label:
        return '作废样本及时出清：失守 guard 后不要继续在观察池里占位置。'
    return '继续积累样本：暂不改大规则，先把后续1-3天路径继续跟清楚。'


def _build_recent_target_reflection_legacy_body(review_matrix):
    review_matrix = review_matrix or []
    if not review_matrix:
        return {}

    fixes = [str(item.get('system_fix', '') or '') for item in review_matrix]
    mistakes = []
    adjustments = []

    if any('介入周期偏慢' in fix for fix in fixes):
        mistakes.append('- 龙蟠科技这类样本说明我对唯一对象的介入周期仍然偏慢。')
        adjustments.append('- 下次再遇到唯一对象次日确认成功且继续 act right，要更快给执行评估。')
    if any('环境过滤过严' in fix for fix in fixes):
        mistakes.append('- 航天工程这类样本说明我对跨线连续 act right 样本的环境过滤仍然偏严。')
        adjustments.append('- 下次再遇到跨线对象连续 act right，不能一直停在纯观察层。')
    if any('弱转强识别偏慢' in fix for fix in fixes):
        mistakes.append('- 弱转强样本说明我对强基底假弱对象的识别仍然偏慢，容易等它彻底走出来后才承认。')
        adjustments.append('- 下次再遇到强基底+假弱非真弱+主线共振未坏的对象，要更早从观察权升级到执行评估。')
    if any('二次确认' in fix for fix in fixes):
        mistakes.append('- 石大胜华这类样本说明我过去容易把“先强后回”样本压成一句防守正确，没有单独拆出二次确认。')
        adjustments.append('- 下次再遇到先强后回样本，要单独按 guard/confirm 的二次确认链路管理。')
    if any('观察链不要偷写成执行链' in fix for fix in fixes):
        mistakes.append('- 彩虹股份这类样本说明我容易因为当天收盘强，就提前把观察对象脑补成成功样本。')
        adjustments.append('- 观察链不要偷写成执行链：下次再遇到确认不干净的当日探针，先继续观察，不提前升格。')

    headline = '这批样本已经告诉我，错不在同一个地方，必须分层修正。'
    if not mistakes:
        mistakes.append('- 当前后验样本还不够多，暂时先继续积累。')
    if not adjustments:
        adjustments.append('- 先继续跟踪样本，不急着改大规则。')

    return {
        'headline': headline,
        'mistakes': mistakes,
        'adjustments': adjustments,
    }


def _build_recent_target_review_matrix_legacy_body(current_plan, recent_followups, limit=4):
    items = []
    for item in (recent_followups or [])[:max(limit - 1, 0)]:
        items.append({
            'sample_label': item.get('sample_label') or item.get('stock_label') or '-',
            'report_date': item.get('report_date', '-'),
            'phase_label': item.get('phase_label') or f"第{item.get('tracking_days', 0)}个交易日",
            'path_label': item.get('path_label', '-'),
            'timeline_text': item.get('timeline_text', item.get('current_position', '-')),
            'today_view': item.get('today_view', item.get('current_position', '-')),
            'next_focus': item.get('next_focus', item.get('focus_text', '-')),
            'review_hint': item.get('review_hint', '-'),
        })
    current_item = _build_current_target_review_item(current_plan)
    if current_item:
        items.append(current_item)
    final_items = items[:limit]
    for item in final_items:
        item['system_fix'] = _derive_target_review_system_fix(item)
    return final_items


def _build_gem_horizontal_compare_cards_legacy_body(gem_cycle_cards=None, review_matrix=None, limit=4):
    gem_cycle_cards = gem_cycle_cards or []
    review_matrix = review_matrix or []
    if not gem_cycle_cards or not review_matrix:
        return []

    def _pick_reference(latest_status_label=''):
        latest_status_label = str(latest_status_label or '').strip()
        if latest_status_label in ('再突破成功但升级偏慢', '已升级到条件执行预演', '已升级到50%条件执行', '已走成再突破'):
            preferred = ('已走成 act right', '个股先走出来了')
        elif latest_status_label in ('仍在观察窗口', '已触发右侧确认'):
            preferred = ('先强后回，进入二次确认', '还在等待确认', '日内确认相对干净', '仍在观察周期')
        else:
            preferred = ('已失守观察边界', '先破观察边界，暂不升级', '确认不干净，继续观察')

        for label in preferred:
            for item in review_matrix:
                if str(item.get('path_label', '') or '').strip() == label:
                    return item
        return review_matrix[0] if review_matrix else {}

    cards = []
    for gem_card in gem_cycle_cards[:limit]:
        latest_status_label = str(gem_card.get('latest_status_label', '') or '').strip()
        reference = _pick_reference(latest_status_label)
        if not reference:
            continue

        if latest_status_label in ('再突破成功但升级偏慢', '已升级到条件执行预演', '已升级到50%条件执行', '已走成再突破'):
            same_point = '两者都属于价格上先证明自己的样本，都是市场先替判断作证。'
            key_difference = '区别是20cm弹性和波动都更大，不能直接按10cm唯一动作给50%，必须先过右侧确认、void、reset这条合同链。'
            system_translation = '系统里要先核对void/trigger/reset三价；固定交易窗口内条件不成立就保持0%不参与，确认结果只进入复盘和下一份日报判断，不能把20cm再突破直接翻译成10cm唯一执行。'
        elif latest_status_label in ('仍在观察窗口', '已触发右侧确认'):
            same_point = '两者都还停在“有观察资格、没买入资格”的阶段，本质都还没走成唯一动作。'
            key_difference = '区别是20cm多了一层呼吸感合同窗口；窗口过期或失守void，就要比10cm更快降权。'
            system_translation = '把20cm先当成二次确认/等待确认样本，除非后续再突破并09:50-10:10窗口满足条件，否则继续观察，不提前抬仓位。'
        else:
            same_point = '两者都说明观察链已经被破坏，继续脑补升级都容易犯错。'
            key_difference = '区别是20cm失守后伤害放大更快，所以破void或窗口到期时必须更果断降权。'
            system_translation = '一旦20cm合同失守或过期，直接从高优先级观察里拿掉，不再把它留成“也许还有戏”的对象。'

        cards.append({
            'cycle_label': gem_card.get('cycle_label', '-'),
            'sample_label': gem_card.get('sample_label', '-'),
            'gem_path_label': latest_status_label or '-',
            'reference_sample_label': reference.get('sample_label', '-'),
            'reference_path_label': reference.get('path_label', '-'),
            'same_point': same_point,
            'key_difference': key_difference,
            'system_translation': system_translation,
        })
    return cards
