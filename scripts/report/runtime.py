from __future__ import annotations

from collections import Counter
import time

from daily_report_snapshot_io import LEDGER_MODE_FROZEN
from diagnostics.helper_diagnostics_runtime import (
    build_helper_diagnostics as _build_helper_diagnostics,
    clear_helper_logs as _clear_helper_logs,
    drain_helper_logs as _drain_helper_logs,
    render_helper_diagnostics_lines as _render_helper_diagnostics_lines,
)
from report.calendar_section_nodes import render_calendar_section
from report.decision_board_nodes import render_decision_board_section
from report.execution_chain_overview_nodes import render_execution_chain_overview_section
from report.no_trade_conclusion_nodes import render_no_trade_conclusion_section
from report.positioning_nodes import render_positioning_section
from report.front_summary_renderer import sanitize_front_page_text
from report.front_page_v2_renderer import render_front_page_v2
from report.market_research_snapshot_nodes import derive_market_research_cycle_layer
from domains.market_state.mainline_turnover_summary_runtime import (
    build_mainline_turnover_summary as _default_build_mainline_turnover_summary,
)
from research.entry_cycle_calibration_runtime import (
    build_default_entry_cycle_calibrations as _default_build_entry_cycle_calibrations,
)

__all__ = ["render_markdown_report_runtime"]

_MISSING = object()
EMIT_HELPER_DIAGNOSTICS = True
REPORT_RUNTIME_CACHE = None

_APPENDIX_FRONT_PAGE_HEADING_RENAMES = {
    "## 一、交易纪律": "## 交易纪律细则",
    "## 三、周期与主线": "## 周期与主线依据",
    "## 四、资金意图": "## 资金意图依据",
    "## 五、个股解读": "## 个股观察依据",
    "## 六、明日执行计划": "## 执行计划依据",
    "## 七、最终结论": "## 结论依据",
}


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


def _get_or_build_market_phase_context(data, target_date):
    shared_cache = globals().get("REPORT_RUNTIME_CACHE")
    cache_key = ("market_phase_context", id(data), str(target_date or ""))
    if isinstance(shared_cache, dict) and cache_key in shared_cache:
        return shared_cache[cache_key]

    phase_context = build_market_phase_context(data, target_date, emit_logs=True)
    if isinstance(shared_cache, dict):
        shared_cache[cache_key] = phase_context
    return phase_context


def _calendar_event_signature(data):
    events = (data or {}).get("calendar_events") or []
    return tuple(
        (
            str(item.get("date", "") or ""),
            str(item.get("title", "") or ""),
            int(item.get("star", 0) or 0),
        )
        for item in events
    )


def _build_display_safe_get_stock_sector(get_stock_sector):
    def _wrapped_get_stock_sector(*args, **kwargs):
        kwargs["skip_api_call"] = True
        return get_stock_sector(*args, **kwargs)

    return _wrapped_get_stock_sector


def _build_display_safe_analyze_buy_signal():
    return lambda *args, **kwargs: None


def _replace_all_placeholder_lines(report_lines, marker, replacement_lines):
    replaced = 0
    while replace_placeholder_lines(report_lines, marker, replacement_lines if replaced == 0 else []) is True:
        replaced += 1
    return replaced


def _strip_duplicate_market_base_header(lines):
    return [line for line in list(lines or []) if line != "## 二、市场基底"]


def _sanitize_report_lines(lines):
    return sanitize_front_page_text(_dedupe_repeated_no_trade_lines(lines))


def _dedupe_repeated_no_trade_lines(lines):
    cleaned = []
    seen = set()
    markers = ("不开新仓", "不做", "空仓等待")
    for line in list(lines or []):
        text = str(line or "")
        is_dedupe_target = (
            text.strip()
            and not text.lstrip().startswith("|")
            and any(marker in text for marker in markers)
        )
        if is_dedupe_target:
            key = text.strip()
            if key in seen:
                continue
            seen.add(key)
        cleaned.append(text)
    return cleaned


def _format_appendix_heading_content(content):
    text = str(content or "")
    return text if text.strip().startswith("附录") else "附录：" + text


def _demote_appendix_headings(lines):
    demoted = []
    for line in list(lines or []):
        text = str(line or "")
        if text.startswith("####"):
            demoted.append("##### " + _format_appendix_heading_content(text[5:]))
        elif text.startswith("###"):
            demoted.append("#### " + _format_appendix_heading_content(text[4:]))
        elif text.startswith("##"):
            demoted.append("### " + _format_appendix_heading_content(text[3:]))
        elif text.startswith("# "):
            demoted.append("### " + _format_appendix_heading_content(text[2:]))
        else:
            demoted.append(text)
    return demoted


def _remove_duplicate_front_page_sections_from_appendix(lines):
    cleaned = []
    skipping_market_base = False
    for line in list(lines or []):
        text = str(line or "")
        if text == "## 二、市场基底":
            skipping_market_base = True
            continue
        if skipping_market_base and text.startswith("## "):
            skipping_market_base = False
        if skipping_market_base:
            continue
        if text in _APPENDIX_FRONT_PAGE_HEADING_RENAMES:
            cleaned.append(_APPENDIX_FRONT_PAGE_HEADING_RENAMES[text])
            continue
        cleaned.append(text)
    return cleaned


def _format_appendix_pct(value):
    if value in (None, ""):
        return "待累计"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        text = str(value)
        return text if text else "待累计"


def _format_appendix_turnover_share(item):
    item = item or {}
    source_status = str(item.get("source_status") or "").strip()
    value = item.get("turnover_share_pct")
    try:
        numeric_value = float(value or 0)
    except (TypeError, ValueError):
        numeric_value = 0
    if source_status and source_status not in ("success", "ok") and numeric_value == 0:
        return "待累计"
    return _format_appendix_pct(value)


def _appendix_turnover_source(item):
    item = item or {}
    return item.get("source_status") or item.get("source") or "记录"


def _derive_structure_mainline_replacement(item):
    item = item or {}
    explicit = str(item.get("replacement") or item.get("replacement_relation") or "").strip()
    if explicit:
        return explicit
    text = " ".join(
        str(item.get(key) or "")
        for key in ("interpretation", "note", "evolution", "structure_state")
    )
    if "接替" in text:
        return "接替前主线"
    if "震荡" in text:
        return "中枢震荡"
    return "待确认"


def _resolve_structure_mainline_replacement(item, mainline_switch_log):
    replacement = _derive_structure_mainline_replacement(item)
    if replacement != "待确认":
        return replacement
    mainline = str((item or {}).get("mainline") or (item or {}).get("primary_mainline") or "").strip()
    if not mainline:
        return replacement
    for switch_item in reversed(list(mainline_switch_log or [])):
        if str(switch_item.get("to_mainline") or "").strip() == mainline:
            previous = str(switch_item.get("from_mainline") or "").strip()
            return f"接替{previous}" if previous else "接替前主线"
    return replacement


def _appendix_stock_name(item):
    return (item or {}).get("stock_name") or (item or {}).get("name") or "-"


def _appendix_stock_code(item):
    return (item or {}).get("stock_code") or (item or {}).get("code") or ""


def _build_appendix_b_continuity_payload(
    *,
    current_mainline_history_record=None,
    recent_mainline_history=None,
    current_sector_turnover_snapshot=None,
    recent_sector_turnover_history=None,
    pivot_mainline_history=None,
):
    mainline_records = list(recent_mainline_history or [])
    if current_mainline_history_record:
        mainline_records.append(current_mainline_history_record)

    historical_mainline_pool = []
    for item in mainline_records:
        mainline = item.get("primary_mainline") or item.get("mainline") or item.get("leading_line") or "-"
        historical_mainline_pool.append(
            {
                "date": item.get("date"),
                "mainline": mainline,
                "status": item.get("market_state") or item.get("rotation_label") or item.get("state_code") or item.get("status") or "记录",
                "note": item.get("rotation_summary") or item.get("note") or item.get("summary") or "",
            }
        )

    mainline_switch_log = []
    previous_mainline = ""
    for item in mainline_records:
        current_mainline = item.get("primary_mainline") or item.get("mainline") or item.get("leading_line") or ""
        if previous_mainline and current_mainline and previous_mainline != current_mainline:
            mainline_switch_log.append(
                {
                    "date": item.get("date"),
                    "from_mainline": previous_mainline,
                    "to_mainline": current_mainline,
                    "reason": item.get("rotation_summary") or item.get("note") or "周期主线发生切换",
                }
            )
        if current_mainline:
            previous_mainline = current_mainline

    turnover_items = list(recent_sector_turnover_history or [])
    if current_sector_turnover_snapshot:
        turnover_items.append(current_sector_turnover_snapshot)
    turnover_share_history = [
        {
            "date": item.get("date"),
            "mainline": item.get("mainline") or item.get("sector_name") or "-",
            "turnover_share_pct": _format_appendix_turnover_share(item),
            "source": _appendix_turnover_source(item),
        }
        for item in turnover_items
    ]

    structure_mainline_records = [
        {
            "date": item.get("date") or item.get("date_range"),
            "date_range": item.get("date_range") or item.get("date"),
            "structure": item.get("structure") or item.get("pivot_range") or item.get("position") or "-",
            "pivot_level": item.get("pivot_level") or item.get("structure_level") or item.get("cycle_level") or "日线中枢",
            "pivot_range": item.get("pivot_range") or item.get("structure") or "-",
            "position": item.get("position") or "-",
            "mainline": item.get("mainline") or item.get("primary_mainline") or "-",
            "mainline_degree": item.get("mainline_degree") or item.get("degree") or item.get("mainline_strength") or item.get("structure_state") or "待确认",
            "evolution": item.get("evolution") or item.get("market_state") or item.get("structure_state") or "待确认",
            "replacement": _resolve_structure_mainline_replacement(item, mainline_switch_log),
            "interpretation": item.get("interpretation") or item.get("note") or item.get("structure_state") or "",
            "note": item.get("interpretation") or item.get("note") or item.get("structure_state") or "",
        }
        for item in list(pivot_mainline_history or [])
    ]

    return {
        "historical_mainline_pool": historical_mainline_pool,
        "mainline_switch_log": mainline_switch_log,
        "turnover_share_history": turnover_share_history,
        "structure_mainline_records": structure_mainline_records,
    }


def _derive_appendix_pivot_mainline_history(
    *,
    market_research_snapshot=None,
    current_mainline_history_record=None,
    recent_mainline_history=None,
    execution_stage_context=None,
    data=None,
):
    execution_stage_context = execution_stage_context or {}
    data = data or {}
    market_research_snapshot = market_research_snapshot or {}
    explicit_rows = (
        execution_stage_context.get("pivot_mainline_history", [])
        or data.get("pivot_mainline_history", [])
        or (market_research_snapshot.get("pivot_mainline_history", []) if isinstance(market_research_snapshot, dict) else [])
        or (market_research_snapshot.get("pivot_mainline_rows", []) if isinstance(market_research_snapshot, dict) else [])
    )
    if explicit_rows:
        return list(explicit_rows)
    if not isinstance(market_research_snapshot, dict):
        return []

    snapshot = dict(market_research_snapshot)
    if current_mainline_history_record and not snapshot.get("current_mainline_history_record"):
        snapshot["current_mainline_history_record"] = current_mainline_history_record
    if recent_mainline_history and not snapshot.get("recent_mainline_history"):
        snapshot["recent_mainline_history"] = recent_mainline_history
    cycle_layer = derive_market_research_cycle_layer(snapshot, snapshot.get("state_machine") or {})
    return list(cycle_layer.get("pivot_mainline_rows") or [])


def _merge_appendix_b_payload(existing_appendix_b, derived_appendix_b):
    if not existing_appendix_b:
        return derived_appendix_b or {}
    if not isinstance(existing_appendix_b, dict):
        return derived_appendix_b or {}
    merged = dict(existing_appendix_b)
    for key in (
        "historical_mainline_pool",
        "mainline_switch_log",
        "turnover_share_history",
        "structure_mainline_records",
    ):
        if not merged.get(key) and (derived_appendix_b or {}).get(key):
            merged[key] = list((derived_appendix_b or {}).get(key) or [])
    return merged


def _build_appendix_c_continuity_payload(*, target_date="", execution_stage_context=None):
    execution_stage_context = execution_stage_context or {}
    pool_specs = [
        ("core_stocks", "主线核心"),
        ("secondary_stocks", "主线备选"),
        ("crossline_observation_stocks", "跨线观察"),
        ("gem_observation_stocks", "创业板观察"),
        ("generic_watch_stocks", "普通观察"),
        ("watchlist", "普通观察"),
    ]
    seen_codes = set()
    monitoring_pool = []
    lifecycle_records = []
    for key, source_pool in pool_specs:
        for item in execution_stage_context.get(key, []) or []:
            code = _appendix_stock_code(item)
            dedupe_key = code or _appendix_stock_name(item)
            if dedupe_key in seen_codes:
                continue
            seen_codes.add(dedupe_key)
            current_action = item.get("current_action") or item.get("tomorrow_action") or item.get("tmr_forecast") or "继续跟踪"
            interpretation = (
                item.get("current_interpretation")
                or item.get("abnormal_summary")
                or item.get("why_watch")
                or item.get("reason")
                or "进入观察池，等待后续交易日累计"
            )
            monitoring_pool.append(
                {
                    "stock_name": _appendix_stock_name(item),
                    "stock_code": code,
                    "source_pool": source_pool,
                    "current_action": current_action,
                }
            )
            lifecycle_records.append(
                {
                    "stock_name": _appendix_stock_name(item),
                    "stock_code": code,
                    "first_report_date": item.get("first_report_date") or item.get("source_report_date") or target_date,
                    "source_report_date": item.get("source_report_date") or target_date,
                    "tracked_trading_days": item.get("tracked_trading_days") or 1,
                    "daily_change_series": item.get("daily_change_series") or item.get("daily_changes") or [],
                    "volume_change_summary": item.get("volume_change_summary") or item.get("volume_state") or "-",
                    "cumulative_change_pct": item.get("cumulative_change_pct") or item.get("cumulative_change") or "-",
                    "current_interpretation": interpretation,
                    "current_action": current_action,
                }
            )

    a_kill_items = []
    for key in ("active_a_kill_records", "filtered_by_a_kill", "a_kill_blacklist_updates"):
        a_kill_items.extend(execution_stage_context.get(key, []) or [])
    a_kill_records = [
        {
            "stock_name": _appendix_stock_name(item),
            "stock_code": _appendix_stock_code(item),
            "a_kill_date": item.get("a_kill_date") or item.get("date") or target_date,
            "reason": item.get("reason") or item.get("sector_name") or item.get("note") or "A杀淘汰",
        }
        for item in a_kill_items
    ]

    return {
        "current_stock_monitoring_pool": monitoring_pool,
        "stock_lifecycle_records": lifecycle_records,
        "a_kill_elimination_records": a_kill_records,
    }


def _build_entry_cycle_calibration_payload(data=None, target_date=""):
    data = data or {}
    existing = data.get("entry_cycle_calibration")
    if isinstance(existing, dict) and existing.get("cases"):
        return existing

    builder = globals().get("_default_build_entry_cycle_calibrations")
    if not callable(builder):
        return {}
    try:
        return builder(as_of_date=target_date)
    except Exception as exc:
        return {
            "as_of_date": target_date,
            "cases": [],
            "source_status": "failed",
            "source_error": str(exc),
        }


def _clear_front_page_placeholders(report_lines):
    for marker in (
        "<!-- FRONT_PAGE_CYCLE_CALENDAR_PLACEHOLDER -->",
        "<!-- FRONT_PAGE_CYCLE_INTERPRETATION_PLACEHOLDER -->",
        "<!-- FRONT_PAGE_PIVOT_MAINLINE_PLACEHOLDER -->",
        "<!-- FRONT_PAGE_CAPITAL_INTENT_PLACEHOLDER -->",
        "<!-- FRONT_PAGE_STOCK_INTERPRETATION_PLACEHOLDER -->",
    ):
        _replace_all_placeholder_lines(report_lines, marker, [])


def _smart_score_event(title: str, original_star: int) -> int:
    high_impact_keywords = ["证监会", "美联储", "央行", "政策", "监管", "重磅", "突发", "危机"]
    medium_impact_keywords = ["大会", "博览会", "展览", "峰会", "论坛", "发布会", "新品", "调价", "涨价"]

    if original_star <= 3:
        return original_star

    title_lower = title.lower()
    if any(keyword in title_lower for keyword in high_impact_keywords):
        return 5
    if any(keyword in title_lower for keyword in ["开启", "上市", "预售", "推出", "发布"]):
        return 4
    if any(keyword in title_lower for keyword in medium_impact_keywords):
        return 3
    return 2


def _build_calendar_ai_context(data, print_fn=print):
    events = (data or {}).get("calendar_events") or []
    if not events:
        return {
            "calendar_analysis": [],
            "top_directions": [],
            "unique_sectors": [],
            "bullish_events": [],
        }

    event_count = len(events)
    estimated_time = max(15, event_count * 1.5)
    batch_size = 8
    total_batches = (event_count + batch_size - 1) // batch_size

    print_fn(f"   🤖 LLM智能分析 {event_count} 个财经事件...")
    print_fn(f"      ⏱  预计耗时 {estimated_time:.0f}-{estimated_time*1.5:.0f} 秒（分{total_batches}批处理，每批约10-15秒）")
    print_fn("      💡 分析内容包括：产业链方向识别、细分板块归类、炒作逻辑生成...")
    batch_start = time.time()

    events_for_analysis = [{"title": event.get("title", ""), "summary": ""} for event in events]
    try:
        client = get_llm_service()
        batch_results = client.analyze_events_batch(events_for_analysis, batch_size=batch_size)
        batch_elapsed = time.time() - batch_start
        print_fn(f"   ✅ 批量分析完成 [⏱ {batch_elapsed:.2f}s]")

        global _llm_call_stats
        _llm_call_stats["total_calls"] += 1
        _llm_call_stats["total_time"] += batch_elapsed
        _llm_call_stats["event_analysis_calls"] += len(events_for_analysis)
        _llm_call_stats["event_analysis_time"] += batch_elapsed
    except Exception as error:
        print_fn(f"   ⚠️ 批量分析失败: {error}，回退到关键词匹配")
        batch_results = [_keyword_match_event_sectors(event.get("title", "")) for event in events]

    calendar_analysis = []
    all_directions = []
    all_sectors = []
    for index, event in enumerate(events):
        title = event.get("title", "")
        ai_analysis = batch_results[index] if index < len(batch_results) else _keyword_match_event_sectors(title)
        smart_star = _smart_score_event(title, event.get("star", 0))
        calendar_analysis.append(
            {
                "date": event.get("date", ""),
                "title": title,
                "star": "⭐" * min(smart_star, 5),
                "ai_analysis": ai_analysis,
            }
        )
        all_directions.append(ai_analysis.get("main_direction", ""))
        related_sectors = ai_analysis.get("related_sectors", []) or []
        filtered_sectors = [sector for sector in related_sectors if sector and sector not in ["需盘面确认", "相关产业链标的", "其他"]]
        all_sectors.extend(filtered_sectors)

    direction_counts = Counter(all_directions)
    top_directions = [(direction, count) for direction, count in direction_counts.most_common(10) if direction != "其他"][:5]
    unique_sectors = list(dict.fromkeys(all_sectors))[:10]
    bullish_events = [item for item in calendar_analysis if (item.get("ai_analysis") or {}).get("expectation") == "利好"]

    return {
        "calendar_analysis": calendar_analysis,
        "top_directions": top_directions,
        "unique_sectors": unique_sectors,
        "bullish_events": bullish_events,
    }


def _get_or_build_calendar_ai_context(data):
    shared_cache = globals().get("REPORT_RUNTIME_CACHE")
    cache_key = ("calendar_ai_context", id(data), _calendar_event_signature(data))
    if isinstance(shared_cache, dict) and cache_key in shared_cache:
        return shared_cache[cache_key]

    context = _build_calendar_ai_context(data)
    if isinstance(shared_cache, dict):
        shared_cache[cache_key] = context
    return context


def _item_signature(items):
    signature = []
    for item in items or []:
        if isinstance(item, dict):
            signature.append(
                (
                    str(item.get("code", "") or ""),
                    str(item.get("name", "") or ""),
                    str(item.get("sector", "") or ""),
                )
            )
        else:
            signature.append(str(item or ""))
    return tuple(signature)


def _get_or_build_market_research_bundle(
    data,
    target_date,
    exit_analysis,
    final_gate,
    position_level,
    main_sectors_info=None,
    secondary_sectors_info=None,
    main_sectors=None,
    secondary_sectors=None,
    dragon_stocks=None,
):
    shared_cache = globals().get("REPORT_RUNTIME_CACHE")
    cache_key = (
        "market_research_bundle",
        id(data),
        str(target_date or ""),
        str(position_level or ""),
        str((exit_analysis or {}).get("sector_name", "") or ""),
        bool((final_gate or {}).get("can_new_entry")),
        str((final_gate or {}).get("final_action", "") or ""),
        _item_signature(main_sectors_info),
        _item_signature(secondary_sectors_info),
        _item_signature(main_sectors),
        _item_signature(secondary_sectors),
        _item_signature(dragon_stocks),
    )
    if isinstance(shared_cache, dict) and cache_key in shared_cache:
        return shared_cache[cache_key]

    bundle = build_market_research_context_bundle(
        data,
        target_date,
        exit_analysis=exit_analysis,
        final_gate=final_gate,
        position_level=position_level,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        main_sectors=main_sectors,
        secondary_sectors=secondary_sectors,
        dragon_stocks=dragon_stocks,
        decision_strict_mode=False,
        allow_display_degraded_abnormal_snapshot=True,
    )
    if isinstance(shared_cache, dict):
        shared_cache[cache_key] = bundle
    return bundle


def render_markdown_report_runtime(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    persist_strategy_tracking=True,
    *,
    helpers=None,
    config=None,
):
    bindings = {}
    bindings.update(helpers or {})
    bindings.update(config or {})
    previous = _install_runtime_bindings(bindings)
    try:
        report = _render_markdown_report_legacy_body(
            data,
            target_date,
            supplementary_perspective=supplementary_perspective,
            has_personal_positions=has_personal_positions,
            run_mode=run_mode,
            persist_strategy_tracking=persist_strategy_tracking,
        )
    finally:
        _restore_runtime_bindings(previous)

    return {
        "report": report,
        "artifacts": {},
    }


def _render_markdown_report_legacy_body(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    persist_strategy_tracking=True,
):
    """生成Markdown格式的A股日报报告
    
    严格遵循SKILL.md中的9步格式要求，增强AI分析能力
    
    Args:
        data: 所有数据源的结果字典
        target_date: 数据日期，格式 YYYY-MM-DD
        supplementary_perspective: 补充视角文字（复盘时使用），默认为空
    """
    print("\n" + "=" * 60)
    print("📄 生成A股日报报告...", flush=True)
    print("=" * 60)
    _clear_helper_logs()
    data['target_date'] = target_date
    
    report_shell = build_report_shell_contract(
        target_date,
        run_mode=run_mode,
        has_personal_positions=has_personal_positions,
        compact=DISPLAY_MVP_MODE,
        use_report_preamble=markdown_hooks.use_report_preamble,
    )
    report = report_shell.get('report', [])
    
    # ========== 提前计算最终档位（v2.3.51重构）==========
    # 目的：确保报告开头显示的档位和Step 4一致
    phase_context = _get_or_build_market_phase_context(data, target_date)
    market_zhongshu = phase_context.get('market_zhongshu', {})
    market_analysis = phase_context.get('market_analysis', {})
    market_trend = phase_context.get('market_trend', '震荡整理')
    mainline_context = phase_context.get('mainline_context', {}) or {}
    main_sectors_info = phase_context.get('main_sectors_info', [])
    secondary_sectors_info = phase_context.get('secondary_sectors_info', [])
    main_sectors = phase_context.get('main_sectors', [])
    secondary_sectors = phase_context.get('secondary_sectors', [])
    dragon_stocks = phase_context.get('dragon_stocks', [])
    exit_analysis = phase_context.get('exit_analysis', {}) or {}
    turnover = phase_context.get('turnover', 0)
    zt_count = phase_context.get('zt_count', 0)
    dt_count = phase_context.get('dt_count', 0)
    indices = phase_context.get('indices', {}) or {}
    sh_change = phase_context.get('sh_change', 0)
    market_stats = phase_context.get('market_stats', {}) or {}
    up_count = phase_context.get('up_count', 0)
    down_count = phase_context.get('down_count', 0)
    rise_fall_ratio = phase_context.get('rise_fall_ratio', 0)
    zs_signal_type = phase_context.get('zs_signal_type')
    zs_signal_status = phase_context.get('zs_signal_status')
    is_dt_panic = phase_context.get('is_dt_panic', False)
    base_position_level = phase_context.get('base_position_level', '')
    base_position_reason = phase_context.get('base_position_reason', '')
    position_level = phase_context.get('position_level', '')
    position_reason = phase_context.get('position_reason', '')
    final_gate = phase_context.get('final_gate', {}) or {}
    environment_display = phase_context.get('environment_display', {}) or {}
    display_position_level = str(environment_display.get('position_level', '') or position_level).strip()
    display_operation_state = str(environment_display.get('operation_state', '') or final_gate.get('operation_state', '观察态')).strip()
    environment_headline = str(environment_display.get('headline', '') or '').strip()
    display_position_reason = _resolve_environment_reason_contract(
        position_reason=position_reason,
        environment_display=environment_display,
        state_machine_snapshot=phase_context.get('preliminary_state_machine', {}) or {},
    )
    overall_level = phase_context.get('overall_level', '红灯')
    price_info = phase_context.get('price_info')
    
    positioning_ascii_diagram = None
    if market_zhongshu and market_zhongshu.get('success'):
        positioning_ascii_diagram = _build_zhongshu_ascii_diagram(
            market_zhongshu.get('structure_segments', []),
            market_zhongshu.get('today_date', ''),
            market_zhongshu.get('today_price', 0.0),
            market_zhongshu.get('signal', {}) or {},
        )
    report.extend(
        render_positioning_section(
            {
                "compact": DISPLAY_MVP_MODE,
                "display_position_level": display_position_level,
                "display_operation_state": display_operation_state,
                "display_position_reason": display_position_reason,
                "market_zhongshu": market_zhongshu,
                "ascii_diagram": positioning_ascii_diagram,
                "get_execution_framework_text": get_execution_framework_text,
            }
        )
    )
    
    integrated_hot_data = data.get('integrated_hot_data', {})
    high_board_count = integrated_hot_data.get('high_board_count', 0)
    report.extend(
        render_decision_board_section(
            {
                "compact": DISPLAY_MVP_MODE,
                "high_board_count": high_board_count,
                "exit_analysis": exit_analysis,
                "main_sectors": main_sectors,
                "position_level": position_level,
                "overall_level": overall_level,
                "final_gate": final_gate,
                "price_info": price_info,
                "display_position_reason": display_position_reason,
                "get_execution_framework_text": get_execution_framework_text,
                "dt_count": dt_count,
                "turnover": turnover,
                "rise_fall_ratio": rise_fall_ratio,
                "up_count": up_count,
                "down_count": down_count,
                "abnormal_risk": data.get('abnormal_risk', []),
            }
        )
    )
    
    prohibition_position_level = display_position_level or position_level
    prohibition_operation_state = display_operation_state or final_gate.get('operation_state', '观察态')
    prohibition_result = build_prohibition_section_contract(
        prohibition_position_level,
        prohibition_operation_state,
        environment_headline=environment_headline,
        has_personal_positions=has_personal_positions,
        final_gate=final_gate,
        main_sectors=main_sectors,
        exit_analysis=exit_analysis,
    )
    replace_placeholder_lines(report, "<!-- PROHIBITION_PLACEHOLDER -->", prohibition_result.get('lines', []))
    
    report.append("")

    calendar_ai_context = _get_or_build_calendar_ai_context(data) if data.get('calendar_events') else {}
    top_directions = calendar_ai_context.get("top_directions", []) or []
    chain_analysis_insights = ""
    if len(top_directions) >= 2 and not DISPLAY_MVP_MODE:
        sectors_for_analysis = [direction for direction, _ in top_directions if direction != '其他']
        if sectors_for_analysis:
            chain_analysis = ai_analyze_sector_relationships(sectors_for_analysis, "日历事件产业链分析")
            chain_analysis_insights = str(chain_analysis.get("insights", "") or "").strip()
    report.extend(
        render_calendar_section(
            {
                "calendar_events_present": bool(data.get("calendar_events")),
                "calendar_analysis": calendar_ai_context.get("calendar_analysis", []) or [],
                "top_directions": top_directions,
                "unique_sectors": calendar_ai_context.get("unique_sectors", []) or [],
                "bullish_events": calendar_ai_context.get("bullish_events", []) or [],
                "chain_analysis_insights": chain_analysis_insights,
            }
        )
    )
    
    market_trend_section = build_market_trend_sections_contract(data, target_date)
    replace_placeholder_lines(
        report,
        "<!-- FRONT_PAGE_MARKET_BASE_PLACEHOLDER -->",
        _strip_duplicate_market_base_header(market_trend_section.get('lines', [])),
    )
    
    stock_full_info = data.get('stock_full_info', {})
    display_safe_get_stock_sector = _build_display_safe_get_stock_sector(get_stock_sector)
    market_activity_sections = build_market_activity_report_sections(
        data,
        target_date,
        stock_full_info,
        get_stock_status=get_stock_status,
        get_stock_sector=display_safe_get_stock_sector,
        analyze_candlestick_pattern=analyze_candlestick_pattern,
    )
    report.extend(market_activity_sections.get('lines', []))
    data.setdefault("module_logs", []).extend(market_activity_sections.get("module_logs", []))
    
    market_and_sector_analysis = build_market_and_sector_analysis_contract(
        data,
        market_analysis,
        sh_change,
        indices,
        exit_analysis,
        main_sectors_info,
        secondary_sectors_info,
        ai_group_concepts_into_chains=ai_group_concepts_into_chains,
    )
    report.extend(market_and_sector_analysis.get('lines', []))
    
    advanced_activity_sections = build_advanced_activity_report_sections(
        data,
        stock_full_info,
        get_stock_sector=display_safe_get_stock_sector,
        analyze_candlestick_pattern=analyze_candlestick_pattern,
    )
    report.extend(advanced_activity_sections.get('lines', []))
    data.setdefault("module_logs", []).extend(advanced_activity_sections.get("module_logs", []))
    
    board_tag_analysis_sections = build_board_tag_analysis_sections_contract(
        data,
        analyze_sector_distribution=analyze_sector_distribution,
    )
    report.extend(board_tag_analysis_sections.get('lines', []))
    
    exchange_monitor_sections = build_exchange_monitor_sections_contract(data)
    report.extend(exchange_monitor_sections.get('lines', []))
    today_predictions = data.get("exchange_monitor_today", []) or []
    nextday_predictions = data.get("exchange_monitor_nextday", []) or []

    execution_stage_lookup = build_execution_stage_lookup(DEFAULT_EXECUTION_STAGE_SPECS)
    candidate_stage_label = get_execution_stage_label(execution_stage_lookup, "candidate_selection")

    # 辅助函数：当Step 0预判为DIFFICULT且环境极端恶劣时，输出空仓结论
    def _build_no_trade_conclusion(report, target_date, prediction, reason, dt_count, up_down_ratio):
        report.extend(
            render_no_trade_conclusion_section(
                {
                    "reason": reason,
                    "candidate_stage_label": candidate_stage_label,
                }
            )
        )
        return "\n".join(report)

    # 获取中证全指数据
    csci_change = 0
    if data.get('wind_a_alternative'):
        csci_change = data['wind_a_alternative'].get('涨跌幅', data['wind_a_alternative'].get('change_pct', 0))
    
    # 主线退出分析和最终门控已在前面构建，此处直接使用
    print(f"   ✅ 龙头股票: {len(dragon_stocks)} 只")
    print(f"   ✅ 主线退出分析完成: {exit_analysis.get('sector_name', '未知')}")
    print(f"   ✅ 最终执行门控: {final_gate.get('final_action', '未知')}")

    # 更新市场特征描述，基于智能分析
    primary_mainline = exit_analysis.get('sector_name', '') or (main_sectors[0] if main_sectors else '')
    if '暂无明确主线' in str(primary_mainline):
        primary_mainline = ''
    report.extend(
        render_execution_chain_overview_section(
            {
                "csci_change": csci_change,
                "market_trend": market_trend,
                "primary_mainline": primary_mainline,
            }
        )
    )
    
    
    # 狙击手视角主骨架（v3.0隔日预判模式重构）
    # ========================================
    # 核心交易哲学：在热点纷呈的中国一二级资本市场，如果没有定力，不能保持智力上的独立与诚实，很难不随波逐流。
    # 任何事件、题材、预期日历都只能作为辅助偏向性因子，不能凌驾于价格、趋势、抗性和转折确认之上。
    # 
    # v3.0重大改进：从"当日分析"改为"隔日预判"
    # 基于今日收盘数据 → 预判明日开盘环境 → 给出明日操作指引
    # ========================================
    
    market_research_bundle = _get_or_build_market_research_bundle(
        data,
        target_date,
        exit_analysis=exit_analysis,
        final_gate=final_gate,
        position_level=position_level,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        main_sectors=main_sectors,
        secondary_sectors=secondary_sectors,
        dragon_stocks=dragon_stocks,
    )
    front_market_research_lines = _render_market_research_snapshot_section(
        market_research_bundle.get("market_research_snapshot", {}) or {},
        compact=DISPLAY_MVP_MODE,
    )
    _replace_all_placeholder_lines(
        report,
        "<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->",
        front_market_research_lines,
    )
    replace_placeholder_lines(
        report,
        "<!-- STEP0_FOLLOW_PLACEHOLDER -->",
        _render_step0_follow_section(
            market_research_bundle.get("step0_plan", {}) or {},
            market_research_bundle.get("market_research_snapshot", {}) or {},
            compact=DISPLAY_MVP_MODE,
        ),
    )
    _clear_front_page_placeholders(report)

    def _render_core_mvp_digest_runtime(*args, **kwargs):
        return _render_core_mvp_digest(
            *args,
            **kwargs,
            build_gem_textbook_next_step_text=_build_gem_textbook_next_step_text,
            build_alignment_pool_text=_build_alignment_pool_text,
            build_mainline_rotation_snapshot=_build_mainline_rotation_snapshot,
            resolve_primary_mainline_name=_resolve_primary_mainline_name,
            build_weak_to_strong_context=_build_weak_to_strong_context,
            get_contract_logic_digest_text=_get_contract_logic_digest_text,
            render_front_digest=render_front_digest,
            safe_float=_safe_float,
        )

    def _render_mvp_focus_summary_runtime(*args, **kwargs):
        return _render_mvp_focus_summary(
            *args,
            **kwargs,
            resolve_primary_mainline_name=_resolve_primary_mainline_name,
            split_abnormal_watch_pool=_split_abnormal_watch_pool,
            build_bridge_prep_context=_build_bridge_prep_context,
            build_front_structure_layer_text=_build_front_structure_layer_text,
            build_special_probe_verdict=_build_special_probe_verdict,
            build_special_probe_focus_text=_build_special_probe_focus_text,
            build_mainline_rotation_snapshot=_build_mainline_rotation_snapshot,
            split_candidates_by_mainline=_split_candidates_by_mainline,
            format_candidate_preview=_format_candidate_preview,
            candidate_matches_mainline=_candidate_matches_mainline,
            build_position_sizing_decision=_build_position_sizing_decision,
            build_cycle_triplet_texts=_build_cycle_triplet_texts,
            build_execute_anchor_window_text=_build_execute_anchor_window_text,
            format_abnormal_probe_text=_format_abnormal_probe_text,
            build_front_follow_action_text=_build_front_follow_action_text,
            render_mvp_focus_summary=render_mvp_focus_summary,
        )

    def _render_environment_follow_stage_body_runtime(bundle, compact=False):
        bundle = bundle or {}
        lines = []
        lines.extend(
            _render_market_research_snapshot_section(
                bundle.get("market_research_snapshot", {}) or {},
                compact=compact,
            )
        )
        lines.extend(
            _render_step0_follow_section(
                bundle.get("step0_plan", {}) or {},
                bundle.get("market_research_snapshot", {}) or {},
                compact=compact,
            )
        )
        return lines

    execution_stage_specs = build_execution_stage_specs(
        {
            "environment_follow": build_environment_follow_stage,
            "watch_pool": build_watch_pool_stage,
            "candidate_selection": build_candidate_selection_stage,
            "risk_review": build_risk_review_stage,
            "entry_plan": build_entry_plan_stage,
            "pk_decision": build_pk_decision_stage,
        },
        enabled_stage_keys=["environment_follow", "watch_pool", "candidate_selection", "risk_review", "entry_plan", "pk_decision"],
    )
    execution_stage_result = run_registered_execution_stages(
        execution_stage_specs,
        stage_context={
            "data": data,
            "target_date": target_date,
            "exit_analysis": exit_analysis,
            "dragon_stocks": dragon_stocks,
            "main_sectors": main_sectors,
            "position_level": position_level,
            "display_mvp_mode": DISPLAY_MVP_MODE,
            "market_research_bundle": market_research_bundle,
            "final_gate": final_gate,
            "render_environment_follow_stage_body": _render_environment_follow_stage_body_runtime,
            "render_market_research_snapshot_section": _render_market_research_snapshot_section,
            "render_step0_follow_section": _render_step0_follow_section,
            "is_degraded_abnormal_snapshot": _is_degraded_abnormal_snapshot,
            "format_abnormal_observation_columns": _format_abnormal_observation_columns,
            "build_step2_candidate_bundle": build_step2_candidate_bundle,
            "render_gem_breathing_step2_section": _render_gem_breathing_step2_section,
            "build_step3_risk_bundle": build_step3_risk_bundle,
            "render_gem_breathing_pool_section": _render_gem_breathing_pool_section,
            "quant_system_available": QUANT_SYSTEM_AVAILABLE,
            "stop_prior_low_trading_days": STOP_PRIOR_LOW_TRADING_DAYS,
            "run_mode": run_mode,
            "position_reason": position_reason,
            "step0_prediction": step0_prediction if 'step0_prediction' in locals() else '',
            "step0_prediction_cn": step0_prediction_cn if 'step0_prediction_cn' in locals() else '',
            "step0_action": step0_action if 'step0_action' in locals() else '',
            "high_board_count": high_board_count,
            "has_personal_positions": has_personal_positions,
            "normalize_stock_code": normalize_stock_code,
            "get_execution_framework_text": get_execution_framework_text,
            "get_trade_permission": get_trade_permission,
            "fetch_recent_price_bars": fetch_recent_price_bars,
            "evaluate_live_tradability": evaluate_live_tradability,
            "build_intraday_execution_plan": build_intraday_execution_plan,
            "build_stop_execution_plan": build_stop_execution_plan,
            "enrich_stop_plan_with_reference_anchors": _enrich_stop_plan_with_reference_anchors,
            "build_waiting_stock_plan": build_waiting_stock_plan,
            "finalize_waiting_candidate": _finalize_waiting_candidate,
            "build_trade_price_focus": _build_trade_price_focus,
            "build_observation_price_focus_text": _build_observation_price_focus_text,
            "append_price_focus_note": _append_price_focus_note,
            "append_observation_price_focus_note": _append_observation_price_focus_note,
            "compose_observation_focus_text": _compose_observation_focus_text,
            "build_front_structure_layer_text": _build_front_structure_layer_text,
            "analyze_buy_signal": _build_display_safe_analyze_buy_signal(),
            "safe_float": _safe_float,
            "ai_analyze_sector_relationships": ai_analyze_sector_relationships,
            "score_execution_candidate": score_execution_candidate,
            "score_candidate_decision_stack": score_candidate_decision_stack,
            "sort_decision_stack_candidates": sort_decision_stack_candidates,
            "sort_watch_anchor_candidates": sort_watch_anchor_candidates,
            "build_strategy_ev_calibration": build_strategy_ev_calibration,
            "build_abnormal_watch_anchor_candidates": _build_abnormal_watch_anchor_candidates,
            "select_priority_watch_anchor": _select_priority_watch_anchor,
            "derive_watch_anchor_type": _derive_watch_anchor_type,
            "derive_watch_anchor_note": _derive_watch_anchor_note,
            "build_abnormal_probe_group": _build_abnormal_probe_group,
            "build_special_probe_verdict": _build_special_probe_verdict,
            "build_position_sizing_decision": _build_position_sizing_decision,
            "build_front_follow_action_text": _build_front_follow_action_text,
            "build_special_probe_focus_text": _build_special_probe_focus_text,
            "build_philosophy_constraint_text": _build_philosophy_constraint_text,
            "render_core_mvp_digest": _render_core_mvp_digest_runtime,
            "render_mvp_focus_summary": _render_mvp_focus_summary_runtime,
            "should_surface_price_note": _should_surface_price_note,
            "build_observation_price_note_text": _build_observation_price_note_text,
            "append_watch_anchor_note": _append_watch_anchor_note,
            "build_candidate_exit_rules": _build_candidate_exit_rules,
            "format_holding_window_text": _format_holding_window_text,
            "render_pk_decision_section": render_pk_decision_section,
            "render_action_plan_section": render_action_plan_section,
            "decision_stack_order_text": DECISION_STACK_ORDER_TEXT,
            "today_predictions": today_predictions,
            "nextday_predictions": nextday_predictions,
        },
        stage_lookup=execution_stage_lookup,
    )
    report.extend(execution_stage_result.get("lines", []))
    data.setdefault("module_logs", []).extend(execution_stage_result.get("module_logs", []))

    execution_stage_context = execution_stage_result.get("context", {}) or {}
    zt_pool_by_sector = execution_stage_context.get('zt_pool_by_sector', {}) or {}
    dt_pool_by_sector = execution_stage_context.get('dt_pool_by_sector', {}) or {}
    zt_pool = execution_stage_context.get('zt_pool', []) or []
    hot_stocks = execution_stage_context.get('hot_stocks', []) or []
    active_a_kill_records = execution_stage_context.get('active_a_kill_records', []) or []
    candidates = execution_stage_context.get('candidates', []) or []
    watchlist = execution_stage_context.get('watchlist', []) or []
    filtered_by_a_kill = execution_stage_context.get('filtered_by_a_kill', []) or []
    mainline_name = execution_stage_context.get('mainline_name', '')
    stock_meta_map = execution_stage_context.get('stock_meta_map', {}) or {}
    abnormal_watch_pool_all = execution_stage_context.get('abnormal_watch_pool_all', []) or []
    abnormal_watch_pool = execution_stage_context.get('abnormal_watch_pool', []) or []
    abnormal_watch_map = execution_stage_context.get('abnormal_watch_map', {}) or {}
    sector_trend_snapshot_step1 = execution_stage_context.get('sector_trend_snapshot_step1', []) or []
    leader_memory_bank = execution_stage_context.get('leader_memory_bank', []) or []
    tracking_memory_status = execution_stage_context.get('tracking_memory_status', {}) or {}
    mainline_competition_snapshot = execution_stage_context.get('mainline_competition_snapshot', []) or []
    observation_snapshot = execution_stage_context.get('observation_snapshot', {}) or {}
    market_research_snapshot = execution_stage_context.get('market_research_snapshot', {}) or {}
    market_state_snapshot = execution_stage_context.get('market_state_snapshot', {}) or {}
    current_mainline_history_record = execution_stage_context.get('current_mainline_history_record', {}) or {}
    recent_mainline_history = execution_stage_context.get('recent_mainline_history', []) or []
    current_sector_turnover_snapshot = execution_stage_context.get('current_sector_turnover_snapshot', {}) or {}
    recent_sector_turnover_history = execution_stage_context.get('recent_sector_turnover_history', []) or []
    mainline_turnover_summary = execution_stage_context.get(
        'mainline_turnover_summary',
        market_research_snapshot.get('mainline_turnover_summary', {}) or {},
    ) or {}
    if market_research_snapshot:
        data["market_research_snapshot"] = market_research_snapshot
    else:
        market_research_snapshot = data.get("market_research_snapshot", {}) or {}
    if not current_mainline_history_record:
        current_mainline_history_record = market_research_snapshot.get("current_mainline_history_record", {}) or {}
    if not recent_mainline_history:
        recent_mainline_history = market_research_snapshot.get("recent_mainline_history", []) or []
    if not current_sector_turnover_snapshot:
        current_sector_turnover_snapshot = market_research_snapshot.get("current_sector_turnover_snapshot", {}) or {}
    if not recent_sector_turnover_history:
        recent_sector_turnover_history = market_research_snapshot.get("recent_sector_turnover_history", []) or []
    if not mainline_turnover_summary:
        mainline_turnover_summary = market_research_snapshot.get("mainline_turnover_summary", {}) or {}
    if current_mainline_history_record:
        data["current_mainline_history_record"] = current_mainline_history_record
    else:
        current_mainline_history_record = data.get("current_mainline_history_record", {}) or {}
    if recent_mainline_history:
        data["recent_mainline_history"] = recent_mainline_history
    else:
        recent_mainline_history = data.get("recent_mainline_history", []) or []
    if current_sector_turnover_snapshot:
        data["current_sector_turnover_snapshot"] = current_sector_turnover_snapshot
    else:
        current_sector_turnover_snapshot = data.get("current_sector_turnover_snapshot", {}) or {}
    if recent_sector_turnover_history:
        data["recent_sector_turnover_history"] = recent_sector_turnover_history
    else:
        recent_sector_turnover_history = data.get("recent_sector_turnover_history", []) or []
    if mainline_turnover_summary:
        data["mainline_turnover_summary"] = mainline_turnover_summary
    else:
        mainline_turnover_summary = data.get("mainline_turnover_summary", {}) or {}
    build_mainline_turnover_summary_fn = globals().get("build_mainline_turnover_summary") or _default_build_mainline_turnover_summary
    if (
        current_mainline_history_record
        and not str((mainline_turnover_summary or {}).get("current_mainline") or "").strip()
        and callable(build_mainline_turnover_summary_fn)
    ):
        mainline_turnover_summary = build_mainline_turnover_summary_fn(
            target_date=target_date,
            current_mainline_history_record=current_mainline_history_record,
            recent_mainline_history=recent_mainline_history,
            current_sector_turnover_snapshot=current_sector_turnover_snapshot,
            recent_sector_turnover_history=recent_sector_turnover_history,
        )
        data["mainline_turnover_summary"] = mainline_turnover_summary
    abnormal_projection_summary = execution_stage_context.get('abnormal_projection_summary', {}) or {}
    step0_plan = execution_stage_context.get('step0_plan', {}) or {}
    step0_prediction = execution_stage_context.get('step0_prediction', 'NEUTRAL')
    step0_prediction_cn = execution_stage_context.get('step0_prediction_cn', step0_prediction)
    step0_reason = execution_stage_context.get('step0_reason', '')
    step0_action = execution_stage_context.get('step0_action', '')
    step2_bundle = execution_stage_context.get('step2_bundle', {}) or {}
    evaluated_stocks = execution_stage_context.get('evaluated_stocks', []) or []
    core_stocks = execution_stage_context.get('core_stocks', []) or []
    secondary_stocks = execution_stage_context.get('secondary_stocks', []) or []
    ignored_stocks = execution_stage_context.get('ignored_stocks', []) or []
    crossline_observation_stocks = execution_stage_context.get('crossline_observation_stocks', []) or []
    gem_observation_stocks = execution_stage_context.get('gem_observation_stocks', []) or []
    sector_trend_snapshot = execution_stage_context.get('sector_trend_snapshot', []) or []
    extreme_conviction_list = execution_stage_context.get('extreme_conviction_list', []) or []
    mainline_in_quadrant = execution_stage_context.get('mainline_in_quadrant')
    mainline_score = execution_stage_context.get('mainline_score', 0)
    step3_bundle = execution_stage_context.get('step3_bundle', {}) or {}
    delete_group = execution_stage_context.get('delete_group', []) or []
    keep_group = execution_stage_context.get('keep_group', []) or []
    focus_group = execution_stage_context.get('focus_group', []) or []
    abnormal_green_count = execution_stage_context.get('abnormal_green_count', 0)
    abnormal_red_count = execution_stage_context.get('abnormal_red_count', 0)
    risk_sectors_from_dt = execution_stage_context.get('risk_sectors_from_dt', []) or []
    risk_sectors = exit_analysis.get("risk_sectors", []) or market_analysis.get("risk_sectors", []) or []
    mainline_a_kill = execution_stage_context.get('mainline_a_kill', False)
    mainline_dt_stocks = execution_stage_context.get('mainline_dt_stocks', []) or []
    structural_a_kill = execution_stage_context.get('structural_a_kill', False)
    structural_reason = execution_stage_context.get('structural_reason', '')
    a_kill_blacklist_updates = execution_stage_context.get('a_kill_blacklist_updates', []) or []
    conviction_codes = execution_stage_context.get('conviction_codes', set()) or set()
    leader_memory_codes = execution_stage_context.get('leader_memory_codes', set()) or set()
    executable_stocks = execution_stage_context.get('executable_stocks', []) or []
    waiting_stocks = execution_stage_context.get('waiting_stocks', []) or []
    untradable_stocks = execution_stage_context.get('untradable_stocks', []) or []
    rejected_stocks = execution_stage_context.get('rejected_stocks', []) or []
    trade_gate_open = execution_stage_context.get('trade_gate_open', False)
    best_stock = execution_stage_context.get('best_stock')
    runner_up = execution_stage_context.get('runner_up')
    watch_anchor = execution_stage_context.get('watch_anchor')
    watch_anchor_type = execution_stage_context.get('watch_anchor_type', '')
    abnormal_probe_group = execution_stage_context.get('abnormal_probe_group', {}) or {}
    special_probe_verdict = execution_stage_context.get('special_probe_verdict', {}) or {}
    position_decision = execution_stage_context.get('position_decision', {}) or {}
    front_structure_layer_text = execution_stage_context.get('front_structure_layer_text', '')
    front_follow_action_text = execution_stage_context.get('front_follow_action_text', '')
    special_probe_text = execution_stage_context.get('special_probe_text', '')
    philosophy_constraint_text = execution_stage_context.get('philosophy_constraint_text', '')
    scored_executable_stocks = execution_stage_context.get('scored_executable_stocks', []) or []
    replace_placeholder_lines(
        report,
        "<!-- CORE_MVP_DIGEST_PLACEHOLDER -->",
        execution_stage_context.get("core_mvp_digest_lines", []),
    )
    replace_placeholder_lines(
        report,
        "<!-- MVP_FOCUS_SUMMARY_PLACEHOLDER -->",
        execution_stage_context.get("mvp_focus_summary_lines", []),
    )
    tail_summary_result = run_report_tail_summary(
        {
            "inputs": {
                "display_mvp_mode": DISPLAY_MVP_MODE,
                "step0_prediction": step0_prediction,
                "step0_prediction_cn": step0_prediction_cn,
                "step0_action": step0_action,
                "final_gate": final_gate,
                "mainline_name": mainline_name,
                "market_research_snapshot": market_research_snapshot,
                "watchlist": watchlist,
                "core_stocks": core_stocks,
                "secondary_stocks": secondary_stocks,
                "step2_bundle": step2_bundle,
                "abnormal_watch_pool": abnormal_watch_pool,
                "front_structure_layer_text": front_structure_layer_text,
                "trade_gate_open": trade_gate_open,
                "best_stock": best_stock,
                "watch_anchor": watch_anchor,
                "watch_anchor_type": watch_anchor_type,
                "tracking_memory_status": tracking_memory_status,
                "position_level": position_level,
                "front_follow_action_text": front_follow_action_text,
                "abnormal_probe_group": abnormal_probe_group,
                "report_stages": execution_stage_result.get("stages", []),
                "exit_analysis": exit_analysis,
                "main_sectors_info": main_sectors_info,
                "main_sectors": main_sectors,
                "risk_sectors": risk_sectors,
                "market_trend": market_trend,
                "zt_count": zt_count,
                "dt_count": dt_count,
                "market_state_snapshot": market_state_snapshot,
                "current_mainline_history_record": current_mainline_history_record,
                "recent_mainline_history": recent_mainline_history,
                "current_sector_turnover_snapshot": current_sector_turnover_snapshot,
                "recent_sector_turnover_history": recent_sector_turnover_history,
                "mainline_turnover_summary": mainline_turnover_summary,
                "supplementary_perspective": supplementary_perspective,
            },
            "helpers": {
                "format_abnormal_probe_text": _format_abnormal_probe_text,
                "build_front_mainline_label": _build_front_mainline_label,
                "build_legacy_final_conclusion_lines": build_legacy_final_conclusion_lines,
                "render_context_tail_sections": globals().get("render_context_tail_sections"),
                "render_supplementary_perspective_section": render_supplementary_perspective_section,
                "render_ai_market_insight_section": render_ai_market_insight_section,
            },
        }
    )
    tail_summary_value = tail_summary_result.get("value", {}) or {}
    tail_summary_exports = tail_summary_value.get("exports", {}) or {}
    if not replace_placeholder_lines(report, "<!-- FRONT_PAGE_FINAL_SUMMARY_PLACEHOLDER -->", tail_summary_value.get("lines", [])):
        report.extend(tail_summary_value.get("lines", []))
    data.setdefault("module_logs", []).extend(tail_summary_value.get("module_logs", []))
    abnormal_probe_parts = tail_summary_exports.get("abnormal_probe_parts", [])

    strategy_tail_result = run_strategy_performance_tail(
        {
            "inputs": {
                "target_date": target_date,
                "data": data,
                "market_zhongshu": market_zhongshu,
                "final_gate": final_gate,
                "exit_analysis": exit_analysis,
                "position_level": position_level,
                "position_reason": position_reason,
                "best_stock": best_stock,
                "watch_anchor": watch_anchor,
                "watch_anchor_type": watch_anchor_type,
                "persist_strategy_tracking": persist_strategy_tracking,
                "run_mode": run_mode,
                "factor_context": {
                    'best_stock': best_stock,
                    'runner_up': runner_up,
                    'watch_anchor': watch_anchor,
                    'watch_anchor_type': watch_anchor_type,
                    'core_stocks': core_stocks,
                    'secondary_stocks': secondary_stocks,
                    'crossline_observation_stocks': crossline_observation_stocks,
                    'gem_observation_stocks': gem_observation_stocks,
                    'generic_watch_stocks': watchlist,
                    'abnormal_probe_group': abnormal_probe_group,
                    'market_research_snapshot': market_research_snapshot,
                    'abnormal_watch_pool': abnormal_watch_pool,
                    'leader_memory_bank': leader_memory_bank,
                    'tracking_memory_status': tracking_memory_status,
                    'sector_trend_snapshot': sector_trend_snapshot,
                    'main_sectors_info': main_sectors_info or [{'name': name} for name in main_sectors[:2]],
                    'secondary_sectors_info': secondary_sectors_info or [{'name': name} for name in secondary_sectors[:2]],
                    'mainline_in_quadrant': mainline_in_quadrant,
                    'mainline_score': mainline_score,
                    'scored_executable_stocks': scored_executable_stocks,
                    'position_decision': position_decision,
                },
            },
            "helpers": {
                "build_strategy_factor_snapshot": _build_strategy_factor_snapshot,
                "build_strategy_plan_context": _build_strategy_plan_context,
                "update_strategy_performance_book": update_strategy_performance_book,
                "render_strategy_performance_nodes": globals().get("render_strategy_performance_nodes"),
                "strategy_performance_helpers": {
                    "ledger_mode_frozen": globals().get("LEDGER_MODE_FROZEN"),
                    "ledger_mode_replay": globals().get("LEDGER_MODE_REPLAY"),
                    "defensive_exit_rule_text": globals().get("DEFENSIVE_EXIT_RULE_TEXT"),
                    "format_strategy_record_brief": globals().get("format_strategy_record_brief"),
                    "format_frozen_plan_columns": globals().get("format_frozen_plan_columns"),
                    "get_plan_action_label": globals().get("get_plan_action_label"),
                    "get_recent_record_display_metrics": globals().get("get_recent_record_display_metrics"),
                    "format_pct_range": globals().get("format_pct_range"),
                    "format_pct": globals().get("format_pct"),
                    "safe_float": globals().get("safe_float"),
                },
            },
        }
    )
    strategy_tail_value = strategy_tail_result.get("value", {}) or {}
    report.extend(strategy_tail_value.get("lines", []))
    data.setdefault("module_logs", []).extend(strategy_tail_value.get("module_logs", []))
    
    # 【已删除v2.3.34】十五、隔日操作计划（功能与狙击手视角重复，用户要求移除）
    

    import datetime as _dt

    appendix_pivot_mainline_history = _derive_appendix_pivot_mainline_history(
        market_research_snapshot=market_research_snapshot,
        current_mainline_history_record=current_mainline_history_record,
        recent_mainline_history=recent_mainline_history,
        execution_stage_context=execution_stage_context,
        data=data,
    )
    existing_appendix_b = data.get("appendix_b") or (market_research_snapshot.get("appendix_b") if isinstance(market_research_snapshot, dict) else {})
    derived_appendix_b = _build_appendix_b_continuity_payload(
        current_mainline_history_record=current_mainline_history_record,
        recent_mainline_history=recent_mainline_history,
        current_sector_turnover_snapshot=current_sector_turnover_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        pivot_mainline_history=appendix_pivot_mainline_history,
    )
    appendix_b = _merge_appendix_b_payload(existing_appendix_b, derived_appendix_b)
    appendix_c = data.get("appendix_c") or (market_research_snapshot.get("appendix_c") if isinstance(market_research_snapshot, dict) else {}) or _build_appendix_c_continuity_payload(
        target_date=target_date,
        execution_stage_context=execution_stage_context,
    )
    entry_cycle_calibration = _build_entry_cycle_calibration_payload(data, target_date)
    data["appendix_b"] = appendix_b
    data["appendix_c"] = appendix_c
    data["entry_cycle_calibration"] = entry_cycle_calibration

    execution_appendix_result = run_execution_appendix_tail(
        {
            "inputs": {
                "data_status": data.get('data_status', {}),
                "step_status": data.get('step_status', {}),
                "timer_summary": data.get('timer_summary', {}),
                "target_date": target_date,
                "generated_at": _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "report_version": "v2.5.0",
                "appendix_b": appendix_b,
                "appendix_c": appendix_c,
                "entry_cycle_calibration": entry_cycle_calibration,
            },
            "helpers": {
                "normalize_report_timer_steps": _normalize_report_timer_steps,
                "render_execution_appendix": render_execution_appendix,
            },
        }
    )
    execution_appendix_value = execution_appendix_result.get("value", {}) or {}
    data["execution_appendix_lines"] = list(execution_appendix_value.get("lines", []) or [])
    report.extend(data["execution_appendix_lines"])
    data.setdefault("module_logs", []).extend(execution_appendix_value.get("module_logs", []))

    front_page_market_research_snapshot = {
        **(market_research_snapshot or {}),
        "current_mainline_history_record": current_mainline_history_record,
        "recent_mainline_history": recent_mainline_history,
        "current_sector_turnover_snapshot": current_sector_turnover_snapshot,
        "recent_sector_turnover_history": recent_sector_turnover_history,
        "mainline_turnover_summary": mainline_turnover_summary,
        "pivot_mainline_history": appendix_pivot_mainline_history,
    }
    front_page_lines = render_front_page_v2(
        report,
        target_date=target_date,
        market_research_snapshot=front_page_market_research_snapshot,
        final_gate=final_gate,
        position_level=position_level,
    )
    if DISPLAY_MVP_MODE:
        report = front_page_lines
    else:
        appendix_report = _remove_duplicate_front_page_sections_from_appendix(report)
        report = front_page_lines + ["", "## 八、详细附录", ""] + _demote_appendix_headings(appendix_report)

    _finalize_helper_diagnostics(data)
    report = _sanitize_report_lines(report)
    return "\n".join(report)


def _finalize_helper_diagnostics(data, print_fn=print):
    helper_logs = _drain_helper_logs()
    data.setdefault("module_logs", []).extend(helper_logs)
    diagnostics = _build_helper_diagnostics(helper_logs)
    data["helper_diagnostics"] = diagnostics
    if bool(globals().get("EMIT_HELPER_DIAGNOSTICS", True)):
        for line in _render_helper_diagnostics_lines(diagnostics):
            print_fn(line)
    return diagnostics
