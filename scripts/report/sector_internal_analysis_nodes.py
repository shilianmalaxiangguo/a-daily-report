from domains.market_state.sector_analysis_trigger import evaluate_sector_analysis_trigger
from report.surface_wording import sanitize_user_visible_text


_PCT_SUFFIXES = ("%", "pct")


DIMENSION_CORE_ANCHOR = "中军识别与跟踪"
DIMENSION_RELATIVE_POSITION = "板块内相对位置"
DIMENSION_ELASTIC_CARRIER = "弹性载体识别"
DIMENSION_FOLLOWER_SUPPORT = "后排承接质量"
DIMENSION_SECOND_WAVE = "二波创新高群"
DIMENSION_FUND_FLOW = "板块间资金流动"


def build_market_research_snapshot_sector_internal_analysis_node(context, node_meta=None, node_lookup=None):
    context = context or {}
    analysis_data = _sector_internal_analysis_data(context)
    explicit_trigger = _explicit_sector_analysis_trigger(context)

    if explicit_trigger is None and not _has_analysis_data(analysis_data):
        return _empty_node()

    trigger = explicit_trigger if explicit_trigger is not None else _evaluate_sector_analysis_trigger(context)
    if not trigger:
        return _empty_node()

    lines = [
        "### 板块内部分析",
        f"- **当前阶段**: {_text(trigger.get('phase'))}",
        f"- **判断原因**: {_text(trigger.get('reason'))}",
    ]

    if not _truthy(trigger.get("should_analyze")):
        return {"lines": lines, "exports": {}, "module_logs": []}

    selected_sector = _select_sector(_list_of_dicts(analysis_data.get("sectors")), _resolve_primary_line(context))
    if not selected_sector:
        return {
            "lines": lines + ["- **关键数据不完整，停止生成**"],
            "exports": {},
            "module_logs": [],
        }

    lines.insert(2, f"- **分析板块**: {_text(_sector_name(selected_sector))}")
    if selected_sector:
        lines.append(
            "- **核心字段**: "
            f"样本{_text(selected_sector.get('total_stocks'), '0')}只；"
            f"成交占比变化{_format_signed_pct(selected_sector.get('turnover_share_change'))}"
        )

    dimensions = list(_list_or_empty(trigger.get("dimensions")))
    if selected_sector:
        if DIMENSION_CORE_ANCHOR in dimensions:
            lines.extend(_core_anchor_lines(selected_sector))
        if DIMENSION_RELATIVE_POSITION in dimensions:
            lines.extend(_relative_position_lines(selected_sector))
        if DIMENSION_ELASTIC_CARRIER in dimensions:
            lines.extend(_elastic_carrier_lines(selected_sector))
        if DIMENSION_FOLLOWER_SUPPORT in dimensions:
            lines.extend(_follower_support_lines(selected_sector))
        if DIMENSION_SECOND_WAVE in dimensions:
            lines.extend(_second_wave_lines(selected_sector))

    if DIMENSION_FUND_FLOW in dimensions:
        lines.extend(_fund_flow_lines(_dict_or_empty(analysis_data.get("sector_fund_flow"))))

    return {"lines": lines, "exports": {}, "module_logs": []}


def _empty_node():
    return {"lines": [], "exports": {}, "module_logs": []}


def _sector_internal_analysis_data(context):
    data = context.get("sector_internal_analysis") or context.get("sector_internal_analysis_data") or {}
    return _dict_or_empty(data)


def _explicit_sector_analysis_trigger(context):
    if "sector_analysis_trigger" not in context or context.get("sector_analysis_trigger") is None:
        return None
    trigger = context.get("sector_analysis_trigger")
    return dict(trigger) if isinstance(trigger, dict) else {}


def _has_analysis_data(data):
    data = _dict_or_empty(data)
    sectors = _list_of_dicts(data.get("sectors"))
    fund_flow = _dict_or_empty(data.get("sector_fund_flow"))
    return bool(sectors) or bool(_list_of_dicts(fund_flow.get("flows"))) or bool(fund_flow.get("description"))


def _evaluate_sector_analysis_trigger(context):
    summary = _capacity_summary(context)
    overtake_summary = _overtake_summary(context)
    signal = {
        "window_state": _first_value(context.get("window_state"), overtake_summary.get("window_state")),
        "mainline_regime": _first_value(context.get("mainline_regime"), summary.get("mainline_regime")),
        "sector_relationship_state": _first_value(
            context.get("sector_relationship_state"),
            summary.get("sector_relationship_state"),
        ),
        "primary_line": _first_value(context.get("primary_line"), summary.get("primary_line")),
        "turnover_quality": context.get("turnover_quality"),
        "mainline_days": context.get("mainline_days"),
    }
    return evaluate_sector_analysis_trigger(signal)


def _capacity_summary(context):
    top_summary = context.get("mainline_capacity_regime_summary")
    if isinstance(top_summary, dict):
        return top_summary
    nested_summary = _dict_or_empty(context.get("mainline_turnover_summary")).get("mainline_capacity_regime_summary")
    return _dict_or_empty(nested_summary)


def _overtake_summary(context):
    top_summary = context.get("overtake_window_summary")
    if isinstance(top_summary, dict):
        return top_summary
    nested_summary = _dict_or_empty(context.get("mainline_turnover_summary")).get("overtake_window_summary")
    return _dict_or_empty(nested_summary)


def _resolve_primary_line(context):
    summary = _capacity_summary(context)
    return _first_value(context.get("primary_line"), summary.get("primary_line"))


def _select_sector(sectors, primary_line):
    sectors = _list_of_dicts(sectors)
    if not sectors:
        return {}
    primary_line = str(primary_line or "").strip()
    if primary_line:
        for sector in sectors:
            if _sector_name(sector) == primary_line:
                return sector
        for sector in sectors:
            sector_name = _sector_name(sector)
            if primary_line in sector_name or sector_name in primary_line:
                return sector
    return sectors[0]


def _sector_name(sector):
    sector = _dict_or_empty(sector)
    return _text(
        _first_value(
            sector.get("sector_name"),
            sector.get("name"),
            sector.get("sector"),
            sector.get("板块"),
        )
    )


def _core_anchor_lines(sector):
    sector = _dict_or_empty(sector)
    anchor = _dict_or_empty(sector.get("core_anchor"))
    return [
        "#### 中军状态",
        (
            "- **核心中军**: "
            f"{_stock_label(anchor)}；状态{_text(anchor.get('status'))}；"
            f"成交额{_format_amount(anchor.get('volume'))}；"
            f"板块内占比{_format_ratio_pct(anchor.get('volume_ratio_in_sector'))}；"
            f"涨跌幅{_format_signed_pct(anchor.get('change_pct'))}"
        ),
    ]


def _relative_position_lines(sector):
    sector = _dict_or_empty(sector)
    relative = _dict_or_empty(sector.get("relative_position"))
    lines = [
        "#### 板块内相对位置",
        "| 层级 | 代表对象 | 平均涨幅 | 成交占比 | 结论 |",
        "|------|----------|----------|----------|------|",
    ]
    rows = [
        ("领涨层", relative.get("leaders"), relative.get("leader_avg_change"), relative.get("leader_volume_ratio")),
        ("中军层", relative.get("core_anchors"), relative.get("core_avg_change"), relative.get("core_volume_ratio")),
        ("后排层", relative.get("followers"), relative.get("follower_avg_change"), relative.get("follower_volume_ratio")),
    ]
    for label, stocks, avg_change, volume_ratio in rows:
        lines.append(
            f"| {label} | {_stock_list(stocks)} | {_format_signed_pct(avg_change)} | "
            f"{_format_ratio_pct(volume_ratio)} | {_text(relative.get('conclusion'))} |"
        )
    return lines


def _elastic_carrier_lines(sector):
    sector = _dict_or_empty(sector)
    elastic = _dict_or_empty(sector.get("elastic_carrier"))
    return [
        "#### 弹性载体",
        (
            "- **弹性载体**: "
            f"{_text(elastic.get('count'), '0')}只；新高{_text(elastic.get('new_high_count'), '0')}只；"
            f"日内承接{_text(elastic.get('intraday_support'))}；代表{_stock_list(elastic.get('stocks'))}"
        ),
    ]


def _follower_support_lines(sector):
    sector = _dict_or_empty(sector)
    support = _dict_or_empty(sector.get("follower_support") or sector.get("follower_support_quality"))
    return [
        "#### 后排承接质量",
        (
            "- **后排承接**: "
            f"{_text(support.get('grade'))}级；"
            f"涨幅>5% {_text(support.get('gain_5pct_count'), '0')}只；"
            f"涨幅>3% {_text(support.get('gain_3pct_count'), '0')}只；"
            f"成交占比{_format_ratio_pct(support.get('volume_ratio'))}；"
            f"{_text(support.get('description'))}"
        ),
    ]


def _second_wave_lines(sector):
    sector = _dict_or_empty(sector)
    second_wave = _dict_or_empty(sector.get("second_wave_new_highs") or sector.get("second_wave_new_high_group"))
    return [
        "#### 二波创新高群",
        (
            "- **二波新高**: "
            f"{_text(second_wave.get('count'), '0')}只；占比{_format_ratio_pct(second_wave.get('ratio'))}；"
            f"代表{_stock_list(second_wave.get('stocks'))}；{_text(second_wave.get('description'))}"
        ),
    ]


def _fund_flow_lines(fund_flow):
    fund_flow = _dict_or_empty(fund_flow)
    flows = _list_of_dicts(fund_flow.get("flows"))
    lines = ["#### 板块间资金流动", f"- **流向说明**: {_text(fund_flow.get('description'), '板块间成交占比变化暂不明显')}"]
    if not flows:
        return lines
    lines.extend(
        [
            "| 流出板块 | 流入板块 | 类型 | 估算变化 |",
            "|----------|----------|------|----------|",
        ]
    )
    for flow in flows[:5]:
        lines.append(
            f"| {_text(flow.get('from_sector'))} | {_text(flow.get('to_sector'))} | "
            f"{_text(flow.get('type'))} | {_format_amount(flow.get('volume_change'))} |"
        )
    return lines


def _stock_list(stocks, limit=3):
    labels = [_stock_label(stock) for stock in _list_of_dicts(stocks)[:limit]]
    labels = [label for label in labels if label != "-"]
    return " / ".join(labels) if labels else "-"


def _stock_label(stock):
    stock = _dict_or_empty(stock)
    name = _text(stock.get("name") or stock.get("stock_name") or stock.get("名称"), "")
    code = _text(stock.get("code") or stock.get("stock_code") or stock.get("代码"), "")
    if name and code:
        return f"{name}({code})"
    return name or code or "-"


def _first_value(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def _text(value, default="-"):
    if value in (None, ""):
        return default
    return str(sanitize_user_visible_text(value)).strip() or default


def _truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "是"}
    return bool(value)


def _dict_or_empty(value):
    return value if isinstance(value, dict) else {}


def _list_or_empty(value):
    return value if isinstance(value, list) else []


def _list_of_dicts(value):
    return [item for item in _list_or_empty(value) if isinstance(item, dict)]


def _safe_float(value, default=None):
    if isinstance(value, str):
        value = _normalize_number_text(value)
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_number_text(value):
    text = str(value or "").strip().replace(",", "")
    if not text:
        return ""
    lower_text = text.lower()
    for suffix in ("亿", "万元", "万", "元", "%", "pct"):
        if lower_text.endswith(suffix):
            return text[: -len(suffix)].strip()
    return text


def _has_pct_suffix(value):
    if not isinstance(value, str):
        return False
    return value.strip().lower().endswith(_PCT_SUFFIXES)


def _format_amount(value):
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}亿"


def _format_signed_pct(value):
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number:+.2f}%"


def _format_ratio_pct(value):
    number = _safe_float(value)
    if number is None:
        return "-"
    if abs(number) <= 1 and not _has_pct_suffix(value):
        number *= 100
    return f"{number:.1f}%"
