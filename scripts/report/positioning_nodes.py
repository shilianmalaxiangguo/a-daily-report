from report.positioning_node_registry import build_positioning_node_specs
from report.positioning_node_runtime import run_positioning_nodes
from report.trading_time_window_contract import normalize_trading_time_text


def _compact(context):
    return bool(context.get("compact"))


def _signal(context):
    return ((context.get("market_zhongshu") or {}).get("signal") or {})


def _success(context):
    return bool(((context.get("market_zhongshu") or {}).get("success")))


def _has_current_signal(context):
    market_zhongshu = context.get("market_zhongshu") or {}
    has_structure = bool(market_zhongshu.get("current_zhongshu")) or bool(market_zhongshu.get("daily_structure_current"))
    return has_structure and bool(market_zhongshu.get("signal"))


def _format_price(value):
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _daily_structure_ratio(daily_structure):
    count = daily_structure.get("kline_count")
    required = daily_structure.get("required_kline_count")
    if count is None and required is None:
        return "-"
    if required is None:
        return str(count)
    return f"{count or 0}/{required}"


def _daily_structure_range_text(daily_structure):
    start_date = daily_structure.get("start_date") or "-"
    end_date = daily_structure.get("end_date") or "-"
    return f"{start_date}~{end_date}"


def _daily_candidate_range_text(daily_structure):
    zd = daily_structure.get("zd_candidate")
    zg = daily_structure.get("zg_candidate")
    return f"[{_format_price(zd)}, {_format_price(zg)}]"


def _chanlun_confirmation_text(confirmation):
    status = confirmation.get("confirmation_status") or "待确认"
    explanation = str(confirmation.get("explanation") or "").strip()
    return f"{status}；{explanation}" if explanation else status


def _environment_emoji(display_position_level):
    if "进攻" in str(display_position_level or ""):
        return "🟢"
    if "空仓" in str(display_position_level or ""):
        return "🔴"
    return "🟡"


def _zero_or_empty_text(value):
    text = str(value or "").strip()
    return text in {"", "-", "暂无", "不做", "无", "无合格标的"}


def _numeric_zero(value):
    text = str(value if value is not None else "").strip().replace("%", "")
    if text == "":
        return False
    try:
        return float(text) <= 0
    except ValueError:
        return False


def _final_target_resolution(context):
    context = context or {}
    resolution = context.get("final_target_resolution")
    if isinstance(resolution, dict) and resolution:
        return resolution
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict):
        resolution = snapshot.get("final_target_resolution")
        if isinstance(resolution, dict) and resolution:
            return resolution
    return {}


def _capital_priority(context):
    decision = (_final_target_resolution(context).get("capital_priority_decision") or {})
    if not isinstance(decision, dict):
        return ""
    return str(decision.get("capital_priority") or "").strip()


def _has_zero_participation_result(context):
    context = context or {}
    capital_priority = _capital_priority(context)
    if capital_priority in {"new_entry", "new_entry_after_old_exit", "tradable_proxy"}:
        return False
    if capital_priority in {"old_position_t", "old_position", "existing_position", "existing_position_t", "wait"}:
        return True
    position_decision = context.get("position_decision") or {}
    if isinstance(position_decision, dict):
        grade = str(position_decision.get("signal_grade") or "").strip()
        if grade.startswith("0"):
            return True
        if "target_position_pct" in position_decision and _numeric_zero(position_decision.get("target_position_pct")):
            return True

    final_gate = context.get("final_gate") or {}
    if isinstance(final_gate, dict):
        for key in ("final_action", "action", "summary", "reason"):
            text = str(final_gate.get(key) or "")
            if "0%不参与" in text or "不新增参与" in text or "禁止新开仓" in text:
                return True
        if final_gate.get("can_new_entry") is False and str(final_gate.get("operation_state") or "") in {"撤退态", "观察态"}:
            return True

    display_text = " ".join(
        str(context.get(key) or "")
        for key in ("display_position_level", "display_operation_state", "position_level", "position_reason")
    )
    return "空仓" in display_text or "0%不参与" in display_text


def _has_explicit_empty_unique_object(context):
    context = context or {}
    candidate_snapshot = context.get("candidate_snapshot") or {}
    front_page = candidate_snapshot.get("front_page") if isinstance(candidate_snapshot, dict) else {}
    if isinstance(front_page, dict) and "unique_object" in front_page:
        return _zero_or_empty_text(front_page.get("unique_object"))

    if "unique_action_target" in context:
        target = context.get("unique_action_target") or {}
        if not isinstance(target, dict):
            return True
        return not (target.get("name") or target.get("code") or target.get("stock_code"))
    return False


def _intraday_note_text(context):
    if _has_zero_participation_result(context) or _has_explicit_empty_unique_object(context):
        return "> **真到盘中怎么做**：日报这里只做盘前预案。明日不新增参与，只观察指数图形、主攻线承接和观察锚是否重新成立；未同时满足前继续0%。"
    return "> **真到盘中怎么做**：日报这里只做盘前预案。明日只按09:30-09:35、09:50-10:10、14:30-14:55三段窗口处理；不满足预演情境就回到0%。"


def build_positioning_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 📈 明天仓位怎么放（基于日线结构中枢）", ""], "exports": {}, "module_logs": []}


def build_positioning_execution_framework_node(context, node_meta=None, node_lookup=None):
    if _has_zero_participation_result(context) or _has_explicit_empty_unique_object(context):
        framework_text = "最终0%时不按固定交易窗口执行，只观察指数图形、主攻线承接和观察锚是否重新成立。"
    else:
        get_execution_framework_text = context.get("get_execution_framework_text")
        framework_text = get_execution_framework_text() if callable(get_execution_framework_text) else "-"
    return {"lines": [f"**怎么执行**：{normalize_trading_time_text(framework_text)}"], "exports": {}, "module_logs": []}


def build_positioning_structure_note_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": ["> **说明**：这里的“结构中枢”是缠论启发版的日线价格结构工具，不是严格笔/线段缠论。它只负责环境过滤、仓位判断和能不能开仓。"],
        "exports": {},
        "module_logs": [],
    }


def build_positioning_intraday_note_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            _intraday_note_text(context),
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_positioning_environment_status_node(context, node_meta=None, node_lookup=None):
    if not _success(context) or not _has_current_signal(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    signal = _signal(context)
    lines = [
        f"### {_environment_emoji(context.get('display_position_level'))} 明日市场环境：{context.get('display_position_level', '')} / {context.get('display_operation_state', '')}",
        "",
        f"**大盘状态**：{signal.get('status', '未知')}",
        f"**信号类型**：{signal.get('signal_type', '未知')}",
    ]
    if signal.get("comparison_result"):
        lines.append(f"**结构对比结果**：{signal['comparison_result']}")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_positioning_structure_range_node(context, node_meta=None, node_lookup=None):
    if not _success(context) or not _has_current_signal(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    market_zhongshu = context.get("market_zhongshu") or {}
    signal = market_zhongshu.get("signal") or {}
    daily_structure = market_zhongshu.get("daily_structure_current") or {}
    if daily_structure:
        confirmation = market_zhongshu.get("chanlun_confirmation") or {}
        lines = [
            f"- **日K结构箱体**：{_daily_structure_range_text(daily_structure)}（{_daily_structure_ratio(daily_structure)}）",
            f"- **日K候选区间**：{_daily_candidate_range_text(daily_structure)}",
            f"- **日K结构证据**：{_chanlun_confirmation_text(confirmation)}",
            f"- **今日收盘**：{signal.get('today_price', 0):.2f}",
            f"- **相对ZG**：{float(signal.get('dist_to_zg', 0) or 0) * 100:+.2f}%",
            "",
        ]
        return {"lines": lines, "exports": {}, "module_logs": []}
    current = market_zhongshu.get("current_zhongshu") or {}
    latest_structure_segment = market_zhongshu.get("latest_structure_segment") or {}
    zone_label = "最近确认结构区间" if latest_structure_segment.get("segment_type") == "connector" else "当前结构区间"
    lines = [
        f"- **{zone_label}**：[{signal.get('zd', 0):.2f}, {signal.get('zg', 0):.2f}]",
        f"- **今日收盘**：{signal.get('today_price', 0):.2f}",
        f"- **相对ZG**：{float(signal.get('dist_to_zg', 0) or 0) * 100:+.2f}%",
    ]
    if current:
        lines.append(f"- **最近确认中枢**：{current.get('start_date', '-')}~{current.get('end_date', '-')}")
    if latest_structure_segment.get("segment_type") == "connector":
        lines.append(
            f"- **最新历史结构**：{latest_structure_segment.get('start_date', '-')}~{latest_structure_segment.get('end_date', '-')} 为过渡结构（{latest_structure_segment.get('kline_count', 0)}根K线）"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_positioning_ascii_diagram_node(context, node_meta=None, node_lookup=None):
    if _compact(context) or not context.get("ascii_diagram"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": ["**ASCII结构图**：", "```text", str(context.get("ascii_diagram", "")), "```", ""],
        "exports": {},
        "module_logs": [],
    }


def build_positioning_state_basis_node(context, node_meta=None, node_lookup=None):
    if not _success(context) or not _has_current_signal(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            f"**状态依据**：{context.get('display_position_reason', '')}",
            "**执行说明**：这里的档位只代表环境条件是否满足，不代表已经有可买标的；真正能不能买，要看后文有没有缩到一只可买股。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_positioning_structure_overview_node(context, node_meta=None, node_lookup=None):
    if not (_success(context) and _has_current_signal(context) and _compact(context)):
        return {"lines": [], "exports": {}, "module_logs": []}
    zhongshu_list = (context.get("market_zhongshu") or {}).get("zhongshu_list") or []
    return {
        "lines": [f"- **结构识别概览**：历史共识别 {len(zhongshu_list)} 个结构中枢；当前只跟踪最近确认中枢与尾部过渡。", ""],
        "exports": {},
        "module_logs": [],
    }


def build_positioning_zhongshu_table_node(context, node_meta=None, node_lookup=None):
    if not (_success(context) and _has_current_signal(context) and not _compact(context)):
        return {"lines": [], "exports": {}, "module_logs": []}
    market_zhongshu = context.get("market_zhongshu") or {}
    daily_structure = market_zhongshu.get("daily_structure_current") or {}
    if daily_structure:
        confirmation = market_zhongshu.get("chanlun_confirmation") or {}
        lines = [
            "**日K结构候选与缠论确认**：",
            "| 项目 | 时间/区间 | ZG | ZD | 状态 |",
            "|------|----------|-----|-----|------|",
            (
                f"| 日K结构箱体 | {_daily_structure_range_text(daily_structure)}（{_daily_structure_ratio(daily_structure)}） | "
                f"{_format_price(daily_structure.get('zg_candidate'))} | {_format_price(daily_structure.get('zd_candidate'))} | "
                f"{daily_structure.get('candidate_status') or '候选形成中'} |"
            ),
            f"| 日K结构证据 | - | - | - | {_chanlun_confirmation_text(confirmation)} |",
            "",
        ]
        return {"lines": lines, "exports": {}, "module_logs": []}
    zhongshu_list = market_zhongshu.get("zhongshu_list") or []
    if not zhongshu_list:
        return {"lines": [], "exports": {}, "module_logs": []}
    signal = market_zhongshu.get("signal") or {}
    latest_structure_segment = market_zhongshu.get("latest_structure_segment") or {}
    lines = [
        f"**识别出 {len(zhongshu_list)} 个结构中枢**：",
        "| 结构中枢 | 时间区间 | ZG | ZD | 性质 |",
        "|------|----------|-----|-----|------|",
    ]
    for i, zs in enumerate(zhongshu_list):
        is_current = i == len(zhongshu_list) - 1
        if is_current:
            status = signal.get("status", "")
            if latest_structure_segment.get("segment_type") == "connector":
                nature = f"**最近确认结构中枢**（后续过渡结构延伸至{latest_structure_segment.get('end_date', '-')}）"
            elif "突破中枢" in status:
                nature = "**当前结构中枢**（🔥今日突破）"
            elif "跌破并落入下中枢区间" in status:
                nature = "**当前结构中枢**（🚨今日暴跌·已落入下一中枢）"
            elif "跌破中枢" in status:
                nature = "**当前结构中枢**（⚠️今日跌破·空仓观望）"
            else:
                nature = "**当前结构中枢**"
        else:
            nature = "已完成"
        lines.append(f"| 第{i+1}结构中枢 | {zs.get('start_date', '-')}~{zs.get('end_date', '-')} | {float(zs.get('zg', 0) or 0):.2f} | {float(zs.get('zd', 0) or 0):.2f} | {nature} |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_positioning_connector_segments_node(context, node_meta=None, node_lookup=None):
    if not (_success(context) and _has_current_signal(context) and not _compact(context)):
        return {"lines": [], "exports": {}, "module_logs": []}
    structure_segments = (context.get("market_zhongshu") or {}).get("structure_segments") or []
    connector_segments = [segment for segment in structure_segments if segment.get("segment_type") == "connector"]
    if not connector_segments:
        return {"lines": [], "exports": {}, "module_logs": []}
    role_map = {
        "leading": "前置过渡",
        "between": "中枢间过渡",
        "trailing": "尾部过渡",
    }
    lines = ["**过渡结构保留**：", "| 过渡结构 | 时间区间 | K线数 | 角色 |", "|--------|----------|-------|------|"]
    for idx, seg in enumerate(connector_segments[-3:], 1):
        lines.append(
            f"| 第{idx}过渡结构 | {seg.get('start_date', '-')}~{seg.get('end_date', '-')} | {seg.get('kline_count', 0)} | {role_map.get(seg.get('connector_role', ''), '过渡结构')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_positioning_error_state_node(context, node_meta=None, node_lookup=None):
    if _success(context) and _has_current_signal(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    if _success(context):
        lines = ["> **⚠️ 大盘中枢分析**：数据异常，请查看详细分析", ""]
    else:
        lines = ["> **⚠️ 大盘中枢分析**：数据获取失败，基于情绪指标判断仓位", ""]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_positioning_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["---", ""], "exports": {}, "module_logs": []}


POSITIONING_NODE_BUILDERS = {
    "header": build_positioning_header_node,
    "execution_framework": build_positioning_execution_framework_node,
    "structure_note": build_positioning_structure_note_node,
    "intraday_note": build_positioning_intraday_note_node,
    "environment_status": build_positioning_environment_status_node,
    "structure_range": build_positioning_structure_range_node,
    "ascii_diagram": build_positioning_ascii_diagram_node,
    "state_basis": build_positioning_state_basis_node,
    "structure_overview": build_positioning_structure_overview_node,
    "zhongshu_table": build_positioning_zhongshu_table_node,
    "connector_segments": build_positioning_connector_segments_node,
    "error_state": build_positioning_error_state_node,
    "footer": build_positioning_footer_node,
}


def render_positioning_section(context):
    context = context or {}
    node_specs = build_positioning_node_specs(
        POSITIONING_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    result = run_positioning_nodes(node_specs, context)
    return result["lines"]
