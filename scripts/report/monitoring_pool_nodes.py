from report.monitoring_pool_node_registry import build_monitoring_pool_node_specs
from report.monitoring_pool_node_runtime import run_monitoring_pool_nodes


def _format_stock_label(item):
    label = item.get('stock_name', '-')
    if item.get('stock_code'):
        label = f"{label}({item.get('stock_code')})"
    return label


def _format_pct(context, value):
    format_pct = (context.get('helpers') or {}).get('format_pct') or (lambda v: '-' if v is None else str(v))
    return format_pct(value)


def build_main_pool_header_node(context, node_meta=None, node_lookup=None):
    main_pool = ((context.get('performance_summary') or {}).get('monitoring_pool') or {}).get('main_pool', []) or []
    if not main_pool:
        return {'lines': [], 'exports': {}, 'module_logs': []}
    return {'lines': ['### 9. 主监测池', ''], 'exports': {}, 'module_logs': []}


def build_main_pool_summary_node(context, node_meta=None, node_lookup=None):
    main_pool = ((context.get('performance_summary') or {}).get('monitoring_pool') or {}).get('main_pool', []) or []
    if not main_pool:
        return {'lines': [], 'exports': {}, 'module_logs': []}
    lines = ['| 标的 | 交易日数 | 累计涨幅 | 走势类型 | 当前结论 |', '|------|----------|----------|----------|----------|']
    for item in main_pool:
        lines.append(f"| {_format_stock_label(item)} | {item.get('days_since_selected', '-')} | {_format_pct(context, item.get('cum_change_pct'))} | {item.get('pattern_type', '-')} | {item.get('current_assessment', '-')} |")
    lines.append('')
    return {'lines': lines, 'exports': {}, 'module_logs': []}


def build_main_pool_details_node(context, node_meta=None, node_lookup=None):
    main_pool = ((context.get('performance_summary') or {}).get('monitoring_pool') or {}).get('main_pool', []) or []
    lines = []
    for item in main_pool:
        rows = item.get('monitoring_rows', []) or []
        if not rows:
            continue
        stock_label = _format_stock_label(item)
        lines.extend([
            f'#### 主池明细 - {stock_label}',
            '',
            f"- **观察锚点**: {item.get('anchor_price', '-')}",
            f"- **容忍带**: {item.get('observation_band_low', '-')} ~ {item.get('observation_band_high', '-')}",
            f"- **失真线**: {item.get('failure_line', '-')}",
            f"- **当前原因**: {item.get('assessment_reason', '-')}",
            '',
            '| 日期 | 开盘 | 最高 | 最低 | 收盘 | 日涨幅 | 累计涨幅 | 量能 | K线 | 日标签 |',
            '|------|------|------|------|------|--------|----------|------|------|--------|',
        ])
        for row in rows:
            lines.append(f"| {row.get('date', '-')} | {row.get('open', '-')} | {row.get('high', '-')} | {row.get('low', '-')} | {row.get('close', '-')} | {_format_pct(context, row.get('daily_change_pct'))} | {_format_pct(context, row.get('cum_change_pct_from_next_day'))} | {row.get('volume_state', '-')} | {row.get('candle_shape', '-')} | {row.get('day_label', '-')} |")
        lines.append('')
    return {'lines': lines, 'exports': {}, 'module_logs': []}


def build_secondary_pool_header_node(context, node_meta=None, node_lookup=None):
    secondary_pool = ((context.get('performance_summary') or {}).get('monitoring_pool') or {}).get('secondary_pool', []) or []
    if not secondary_pool:
        return {'lines': [], 'exports': {}, 'module_logs': []}
    return {'lines': ['### 10. 副监测池', ''], 'exports': {}, 'module_logs': []}


def build_secondary_pool_summary_node(context, node_meta=None, node_lookup=None):
    secondary_pool = ((context.get('performance_summary') or {}).get('monitoring_pool') or {}).get('secondary_pool', []) or []
    if not secondary_pool:
        return {'lines': [], 'exports': {}, 'module_logs': []}
    lines = ['| 标的 | 交易日数 | 累计涨幅 | 走势类型 | 当前结论 |', '|------|----------|----------|----------|----------|']
    for item in secondary_pool:
        lines.append(f"| {_format_stock_label(item)} | {item.get('days_since_selected', '-')} | {_format_pct(context, item.get('cum_change_pct'))} | {item.get('pattern_type', '-')} | {item.get('current_assessment', '-')} |")
    lines.append('')
    return {'lines': lines, 'exports': {}, 'module_logs': []}


def build_secondary_pool_details_node(context, node_meta=None, node_lookup=None):
    secondary_pool = ((context.get('performance_summary') or {}).get('monitoring_pool') or {}).get('secondary_pool', []) or []
    lines = []
    for item in secondary_pool:
        rows = item.get('monitoring_rows', []) or []
        if not rows:
            continue
        stock_label = _format_stock_label(item)
        lines.extend([
            f'#### 副池明细 - {stock_label}',
            '',
            f"- **观察锚点**: {item.get('anchor_price', '-')}",
            f"- **容忍带**: {item.get('observation_band_low', '-')} ~ {item.get('observation_band_high', '-')}",
            f"- **失真线**: {item.get('failure_line', '-')}",
            f"- **当前原因**: {item.get('assessment_reason', '-')}",
            '',
            '| 日期 | 开盘 | 最高 | 最低 | 收盘 | 日涨幅 | 累计涨幅 | 量能 | K线 | 日标签 |',
            '|------|------|------|------|------|--------|----------|------|------|--------|',
        ])
        for row in rows:
            lines.append(f"| {row.get('date', '-')} | {row.get('open', '-')} | {row.get('high', '-')} | {row.get('low', '-')} | {row.get('close', '-')} | {_format_pct(context, row.get('daily_change_pct'))} | {_format_pct(context, row.get('cum_change_pct_from_next_day'))} | {row.get('volume_state', '-')} | {row.get('candle_shape', '-')} | {row.get('day_label', '-')} |")
        lines.append('')
    return {'lines': lines, 'exports': {}, 'module_logs': []}


MONITORING_POOL_NODE_BUILDERS = {
    'main_pool_header': build_main_pool_header_node,
    'main_pool_summary': build_main_pool_summary_node,
    'main_pool_details': build_main_pool_details_node,
    'secondary_pool_header': build_secondary_pool_header_node,
    'secondary_pool_summary': build_secondary_pool_summary_node,
    'secondary_pool_details': build_secondary_pool_details_node,
}


def render_monitoring_pool_nodes(context):
    context = context or {}
    node_specs = build_monitoring_pool_node_specs(MONITORING_POOL_NODE_BUILDERS, enabled_node_keys=context.get('enabled_node_keys'))
    return run_monitoring_pool_nodes(node_specs, context)
