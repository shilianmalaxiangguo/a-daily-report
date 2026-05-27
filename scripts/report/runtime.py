from __future__ import annotations

from collections import Counter
import os
import json
from pathlib import Path
import time

from daily_report_snapshot_io import LEDGER_MODE_FROZEN
from diagnostics.helper_diagnostics_runtime import (
    build_helper_diagnostics as _build_helper_diagnostics,
    clear_helper_logs as _clear_helper_logs,
    drain_helper_logs as _drain_helper_logs,
    render_helper_diagnostics_lines as _render_helper_diagnostics_lines,
)
from domains.calendar_events.infer import normalize_calendar_ai_analysis
from knowledge.llm_wiki_context import build_llm_wiki_context
from report.calendar_section_nodes import render_calendar_section
from report.decision_board_nodes import render_decision_board_section
from report.decision_ledger import (
    build_decision_ledger_snapshot as _default_build_decision_ledger_snapshot,
    prune_replaced_same_day_extreme_mentions as _default_prune_replaced_same_day_extreme_mentions,
    render_extreme_conviction_backtest_lines as _default_render_extreme_conviction_backtest_lines,
    render_extreme_conviction_mention_tracking_lines as _default_render_extreme_conviction_mention_tracking_lines,
    render_extreme_conviction_mention_tracking_rows as _default_render_extreme_conviction_mention_tracking_rows,
    render_extreme_conviction_tracking_lines as _default_render_extreme_conviction_tracking_lines,
    write_decision_ledger_artifacts as _default_write_decision_ledger_artifacts,
)
from report.execution_chain_overview_nodes import render_execution_chain_overview_section
from report.no_trade_conclusion_nodes import render_no_trade_conclusion_section
from report.positioning_nodes import render_positioning_section
from report.front_summary_renderer import sanitize_front_page_text
from hooks.report.use_report_sections import (
    build_ai_friction_knowledge_note,
    build_knowledge_compounding_candidate_note,
)
from report.front_page_v2_renderer import render_front_page_v2
from report.market_research_snapshot_nodes import derive_market_research_cycle_layer
from report.surface_wording import sanitize_user_visible_text
from report.trading_time_window_contract import normalize_trading_time_text
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
ENABLE_REMOTE_CALENDAR_LLM = str(os.getenv("A_DAILY_REPORT_ENABLE_REMOTE_CALENDAR_LLM", "")).lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_DEFAULT_LLM_CALL_STATS = {
    "total_calls": 0,
    "total_time": 0.0,
    "event_analysis_calls": 0,
    "event_analysis_time": 0.0,
    "sector_analysis_calls": 0,
    "sector_analysis_time": 0.0,
}

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


def _ensure_llm_call_stats():
    stats = globals().get("_llm_call_stats")
    if not isinstance(stats, dict):
        stats = dict(_DEFAULT_LLM_CALL_STATS)
        globals()["_llm_call_stats"] = stats
    for key, value in _DEFAULT_LLM_CALL_STATS.items():
        stats.setdefault(key, value)
    return stats


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


def _is_markdown_table_line(line):
    text = str(line or "").strip()
    return text.startswith("|") and text.endswith("|") and text.count("|") >= 2


def _is_markdown_table_separator(line):
    if not _is_markdown_table_line(line):
        return False
    inner = str(line or "").strip().strip("|")
    cells = [cell.strip() for cell in inner.split("|")]
    if not cells:
        return False
    return all(cell and set(cell) <= {"-", ":"} and "-" in cell for cell in cells)


def _is_t_number_line(line):
    text = str(line or "").strip()
    return text.startswith("**T-") and text.endswith("**")


def _number_report_tables(lines):
    numbered = []
    table_index = 0
    source_lines = list(lines or [])
    index = 0
    while index < len(source_lines):
        line = str(source_lines[index])
        next_line = str(source_lines[index + 1]) if index + 1 < len(source_lines) else ""
        previous_line = str(numbered[-1]).strip() if numbered else ""
        if _is_markdown_table_line(line) and _is_markdown_table_separator(next_line):
            if _is_t_number_line(previous_line):
                numbered.pop()
            table_index += 1
            numbered.append(f"**T-{table_index:03d}**")
        numbered.append(line)
        index += 1
    return numbered


_ZERO_PARTICIPATION_OBSERVATION_FRAMEWORK = "最终0%时不按观察窗口执行，只观察指数图形、主攻线承接和唯一对象是否重新成立。"
_LEGACY_WINDOW_HIT_STANDARD_ATTACK_TEXT = "盘前0%；" + "参与窗口" + "命中后才评估50%标准进攻"


def _has_conditional_observation_target_surface(lines):
    text = "\n".join(str(line or "") for line in list(lines or []))
    if "条件观察：" not in text:
        return False
    return "0%：条件不满足" in text or "不满足继续0%" in text or "条件50%" in text


def _should_apply_pure_zero_participation_cleanup(lines):
    return _has_final_zero_participation_surface(lines) and not _has_conditional_observation_target_surface(lines)


def _has_existing_position_zero_new_entry_surface(lines):
    text = "\n".join(str(line or "") for line in list(lines or []))
    has_existing_position = "已有昨日持仓优先处理" in text or "先处理旧仓，不为新候选分散资金" in text
    has_zero_new_entry = (
        "| 新开仓上限 | 0 |" in text
        or "| 新增参与上限 | 0 |" in text
        or "新开仓0手" in text
        or "新开仓0" in text
    )
    return has_existing_position and has_zero_new_entry


def _should_apply_zero_style_language_cleanup(lines):
    return _should_apply_pure_zero_participation_cleanup(lines) or _has_existing_position_zero_new_entry_surface(lines)


def _has_final_zero_participation_surface(lines):
    lines = list(lines or [])
    for line in lines:
        text = str(line or "").strip()
        if text.startswith("| 0%不参与 |") and ("| 0% / 不参与 |" in text or "0%：" in text):
            return True
    text = "\n".join(str(line or "") for line in lines)
    if "0%不参与" not in text:
        return False
    if "唯一重点对象 | 暂无" in text:
        return True
    if "0%：没有合格标的就不参与" in text:
        return True
    return False


def _normalize_legacy_execution_framework_under_zero_participation(lines):
    if not _should_apply_zero_style_language_cleanup(lines):
        return list(lines or [])

    normalized = []
    legacy_markers = (
        "强核心走竞价表态",
        "普通结构只看09:50-10:10窗口",
        "日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构只看09:50-10:10窗口，30分钟定止损",
    )
    for line in list(lines or []):
        text = str(line or "")
        if any(marker in text for marker in legacy_markers):
            if text.startswith("- **怎么执行**:"):
                text = f"- **怎么执行**: {_ZERO_PARTICIPATION_OBSERVATION_FRAMEWORK}"
            elif text.startswith("- **执行节奏**:"):
                text = f"- **执行节奏**: {_ZERO_PARTICIPATION_OBSERVATION_FRAMEWORK}"
            elif text.startswith("> **怎么执行**："):
                text = f"> **怎么执行**：{_ZERO_PARTICIPATION_OBSERVATION_FRAMEWORK}"
            else:
                text = text.replace(
                    "日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构只看09:50-10:10窗口，30分钟定止损",
                    _ZERO_PARTICIPATION_OBSERVATION_FRAMEWORK,
                )
        normalized.append(text)
    return normalized


def _normalize_tomorrow_action_soft_words_under_zero_participation(lines):
    if not _should_apply_zero_style_language_cleanup(lines):
        return list(lines or [])

    normalized = []
    replacements = (
        ("买点线", "观察线"),
        ("卖点线", "失效线"),
        ("买入窗口", "观察位窗口"),
        ("明日买点预计算", "明日观察位预计算"),
        ("预计算买点", "预计算观察位"),
        ("筛到可买股", "继续观察复核"),
        ("可买标的", "合格参与对象"),
        ("可买对象", "合格参与对象"),
        ("一只可买股", "唯一合格对象"),
        ("可买股", "合格参与对象"),
        ("真正能不能买", "真正是否参与"),
        ("明天能不能开仓", "明天是否参与"),
        ("能不能开仓", "是否参与"),
        ("买入动作", "新增参与动作"),
        ("未买入的保持观望", "未参与的保持观望"),
        ("单独买入", "单独参与"),
        ("低吸理由", "观察理由"),
        ("不把局部强势当成可执行爆发", "不把局部强势当成参与资格"),
        ("只展示真正可执行对象", "只展示真正具备参与资格的对象"),
        ("禁止买入任何方向", "不参与任何方向"),
        ("提前硬上", "提前参与"),
        ("无新仓止损", "无新增参与止损"),
        ("新仓止损", "新增参与止损"),
        ("非电风扇不" + "尾盘" + "新增参与", "非电风扇不在14:30-14:55新增参与"),
        ("非电风扇不" + "尾盘" + "开新仓", "非电风扇不在14:30-14:55新增参与"),
        ("不开新仓", "不新增参与"),
        ("开新仓", "新增参与"),
        ("新开仓", "新增参与"),
        ("不开仓", "不新增参与"),
        ("PK出手结论", "PK参与结论"),
        ("允许出手", "允许参与"),
        ("出手条件", "参与条件"),
        ("主动出手预期", "主动参与预期"),
        ("出手指令", "参与指令"),
        ("筛出明天唯一能买的那只", "筛出明天唯一观察对象"),
        ("明天唯一能买的那只", "明天唯一观察对象"),
        ("核心可买 > 龙头回看 > 主线盯盘 > 普通观察", "核心观察 > 龙头回看 > 主线盯盘 > 普通观察"),
        ("只保留重点观察谁", "只保留候选观察样本"),
        ("重点观察优先锚点", "候选观察锚点"),
        ("重点观察优先", "候选观察样本"),
        ("重点观察名单全天都不给确认", "候选观察样本全天都不给确认"),
        ("首波先锋，优先做重点观察谁", "首波先锋，仅作承接观察"),
        ("没有买入资格，买点到了也只能看", "没有观察资格，价格到了也只能看"),
        ("买入资格", "观察资格"),
        ("怎么买", "怎么观察"),
        ("买点到了", "价格到了"),
        ("买点", "观察位"),
        ("给买入资格", "给观察资格"),
        ("新增买入资格", "新增观察资格"),
        ("溢价预期", "承接观察"),
        ("明日可能加速+板块龙一", "只观察承接，不预设参与"),
        ("大阳线封板，明日有溢价+板块龙一", "大阳线封板，仅作承接观察"),
        ("明日有溢价", "只观察承接"),
        ("明日可能高开溢价", "只观察承接"),
        ("形态正常，明日看竞价", "条件未满足，只观察"),
        ("可按计划", "条件未满足，只观察"),
        ("按计划买入", "按计划参与"),
        ("主买对象", "主观察对象"),
        ("补位", "观察"),
        ("实际可买", "仅观察"),
        ("动作上限", "观察上限"),
        ("✓ 溢价候选", "观察样本"),
        ("溢价候选", "观察样本"),
        ("MVP快照回退：先看次日是否继续强于市场，再按预演观察窗口确认。", "观察样本：先看是否强于市场，不预设参与。"),
        ("MVP快照回退：先看次日是否继续强于市场，再按固定交易窗口条件确认。", "观察样本：先看是否强于市场，不预设参与。"),
    )
    for line in list(lines or []):
        text = normalize_trading_time_text(str(line or ""))
        for source, target in replacements:
            text = text.replace(source, target)
        if "允许进入" in text and "继续观察复核" in text:
            text = text.replace("允许进入", "只进入")
        text = text.replace("继续继续观察复核", "继续观察复核")
        text = text.replace("新增参与0手", "新开仓0手")
        normalized.append(text)
    return normalized


def _sanitize_report_lines(lines):
    return _number_report_tables(
        [
            sanitize_front_page_text(line)
            for line in _normalize_legacy_execution_framework_under_zero_participation(
                _normalize_tomorrow_action_soft_words_under_zero_participation(_dedupe_repeated_no_trade_lines(lines))
            )
        ]
    )


def _strip_report_table_numbers(lines):
    return [line for line in list(lines or []) if not _is_t_number_line(line)]


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


def _resolve_decision_ledger_market_branch(market_research_snapshot, execution_stage_context):
    market_research_snapshot = market_research_snapshot or {}
    execution_stage_context = execution_stage_context or {}
    return (
        market_research_snapshot.get("market_branch")
        or market_research_snapshot.get("cycle_note")
        or execution_stage_context.get("step0_reason")
        or "待验证市场演变"
    )


def _summary_has_attack_evidence(summary):
    if not isinstance(summary, dict):
        return False
    attack_summary = summary.get("mainline_attack_evidence_summary")
    return isinstance(attack_summary, dict) and bool(str(attack_summary.get("attack_state") or "").strip())


def _confirmed_attack_primary_line(summary):
    if not isinstance(summary, dict):
        return ""
    attack_summary = summary.get("mainline_attack_evidence_summary") or {}
    if not isinstance(attack_summary, dict):
        return ""
    if str(attack_summary.get("attack_state") or "").strip() != "confirmed_attack":
        return ""
    return str(attack_summary.get("primary_line") or "").strip()


def _history_record_mainline(record):
    if not isinstance(record, dict):
        return ""
    return str(
        record.get("primary_mainline")
        or record.get("leading_line")
        or record.get("mainline")
        or ""
    ).strip()


def _prefer_confirmed_attack_mainline_history_record(
    execution_record=None,
    snapshot_record=None,
    mainline_turnover_summary=None,
    target_date=None,
):
    primary_line = _confirmed_attack_primary_line(mainline_turnover_summary)
    if not primary_line:
        return execution_record or snapshot_record or {}

    source_record = {}
    if _history_record_mainline(snapshot_record) == primary_line:
        source_record = dict(snapshot_record or {})
    elif _history_record_mainline(execution_record) == primary_line:
        source_record = dict(execution_record or {})
    else:
        source_record = dict(snapshot_record or execution_record or {})

    attack_summary = (mainline_turnover_summary or {}).get("mainline_attack_evidence_summary") or {}
    source_record["date"] = str(source_record.get("date") or target_date or "").strip()
    source_record["primary_mainline"] = primary_line
    source_record["leading_line"] = primary_line
    if _history_record_mainline(execution_record) != primary_line:
        source_record["secondary_mainline"] = ""
        source_record["competition_mainline"] = ""
    if "主攻线半导体" in str(source_record.get("rotation_summary") or ""):
        source_record["rotation_summary"] = ""
    if str(source_record.get("rotation_label") or "").strip() == "逆势攻击" and str(source_record.get("rotation_summary") or "").strip():
        existing_summary = str(source_record.get("rotation_summary") or "").strip()
        evidence = str(
            attack_summary.get("confirmation_evidence")
            or (mainline_turnover_summary or {}).get("conclusion")
            or f"{primary_line}攻击证据成立"
        ).strip()
        source_record["rotation_summary"] = (
            existing_summary
            if evidence and evidence in existing_summary
            else "；".join([part for part in (existing_summary, evidence) if part])
        )
    if not str(source_record.get("rotation_summary") or "").strip():
        source_record["rotation_summary"] = str(
            attack_summary.get("confirmation_evidence")
            or (mainline_turnover_summary or {}).get("conclusion")
            or f"{primary_line}攻击证据成立"
        ).strip()
    source_record["source"] = source_record.get("source") or "market_research_snapshot.confirmed_attack"
    return source_record


def _prefer_structured_mainline_turnover_summary(primary_summary, fallback_summary):
    primary_summary = primary_summary or {}
    fallback_summary = fallback_summary or {}
    primary_label = str(primary_summary.get("share_trend_label") or "").strip()
    fallback_label = str(fallback_summary.get("share_trend_label") or "").strip()
    if primary_label == "逆势试攻" and fallback_label != "逆势试攻":
        return primary_summary
    if fallback_label == "逆势试攻" and primary_label != "逆势试攻":
        return fallback_summary
    if _summary_has_attack_evidence(fallback_summary) and not _summary_has_attack_evidence(primary_summary):
        return fallback_summary
    return primary_summary or fallback_summary


def _resolve_decision_ledger_sector_relationship(execution_stage_context):
    execution_stage_context = execution_stage_context or {}
    summary = execution_stage_context.get("mainline_turnover_summary") or {}
    return (
        summary.get("relationship")
        or summary.get("relationship_label")
        or execution_stage_context.get("mainline_relationship_state")
        or "暂未分出"
    )


def _extract_extreme_conviction_list(source):
    if not isinstance(source, dict):
        return []
    direct = source.get("extreme_conviction_list")
    if isinstance(direct, list) and direct:
        return list(direct)
    candidate_snapshot = source.get("candidate_snapshot")
    if isinstance(candidate_snapshot, dict):
        nested = candidate_snapshot.get("extreme_conviction_list")
        if isinstance(nested, list) and nested:
            return list(nested)
    for key in ("candidate_selection", "step2_bundle", "execution_stage_context"):
        nested_source = source.get(key)
        nested = _extract_extreme_conviction_list(nested_source)
        if nested:
            return nested
    return []


def _sync_runtime_extreme_conviction_list(data, execution_stage_context, market_research_snapshot):
    data = data if isinstance(data, dict) else {}
    execution_stage_context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    market_research_snapshot = market_research_snapshot if isinstance(market_research_snapshot, dict) else {}

    extreme_conviction_list = (
        _extract_extreme_conviction_list(execution_stage_context)
        or _extract_extreme_conviction_list(market_research_snapshot)
        or _extract_extreme_conviction_list(data)
    )
    if not extreme_conviction_list:
        return []

    execution_stage_context["extreme_conviction_list"] = extreme_conviction_list
    data["extreme_conviction_list"] = extreme_conviction_list
    data["execution_stage_context"] = execution_stage_context

    market_research_snapshot["extreme_conviction_list"] = extreme_conviction_list
    candidate_snapshot = market_research_snapshot.get("candidate_snapshot")
    if not isinstance(candidate_snapshot, dict):
        candidate_snapshot = {}
    candidate_snapshot["extreme_conviction_list"] = extreme_conviction_list
    market_research_snapshot["candidate_snapshot"] = candidate_snapshot
    execution_stage_context["market_research_snapshot"] = market_research_snapshot
    data["market_research_snapshot"] = market_research_snapshot
    return extreme_conviction_list


def _downgrade_extreme_conviction_list_to_observation(extreme_conviction_list):
    downgraded = []
    for idx, item in enumerate(list(extreme_conviction_list or [])):
        if not isinstance(item, dict):
            continue
        updated = dict(item)
        original_role = str(updated.get("sniper_role") or "").strip()
        if original_role:
            updated.setdefault("zero_position_role_original", original_role)
        _normalize_extreme_observation_text_fields(updated)
        updated["sniper_role"] = "候选观察" if idx == 0 else "候选观察补充"
        updated["primary_buy_candidate"] = False
        updated["backup_buy_candidate"] = False
        updated["candidate_layer"] = "watch_sample"
        updated["execution_eligibility"] = "observation_only"
        updated["source_tier"] = "extreme_conviction"
        updated["attack_state"] = "0%观察"
        updated["participation_window"] = str(updated.get("participation_window") or "09:50-10:10").replace("参与", "观察")
        updated["conviction_rule"] = "最终0%时只作观察样本，不构成明日新增参与"
        for plan_key in ("planned_participation", "participation_script"):
            plan = updated.get(plan_key)
            if isinstance(plan, dict):
                plan = dict(plan)
                plan["source_tier"] = "extreme_conviction"
                plan["attack_state"] = "0%观察"
                updated[plan_key] = plan
        downgraded.append(updated)
    return downgraded


def _normalize_extreme_observation_text_fields(value, *, parent_key=""):
    if isinstance(value, dict):
        for key, nested in list(value.items()):
            if key == "zero_position_role_original":
                continue
            value[key] = _normalize_extreme_observation_text_fields(nested, parent_key=str(key or ""))
        return value
    if isinstance(value, list):
        return [_normalize_extreme_observation_text_fields(item, parent_key=parent_key) for item in value]
    if not isinstance(value, str):
        return value
    text = value.replace("明日主买对象", "候选观察").replace("明日补位对象", "候选观察补充")
    if parent_key in {"reason", "stock_setup", "market_branch", "final_action", "decision_action"}:
        text = text.replace("空仓等待，禁止参与；若你有仓位，只做退出不做幻想", "明日不新增参与，只观察风险是否钝化、主攻线承接和唯一对象是否重新成立")
    return text


def _downgrade_nested_extreme_conviction_lists_to_observation(value, visited=None):
    if visited is None:
        visited = set()
    if not isinstance(value, (dict, list)):
        return
    marker = id(value)
    if marker in visited:
        return
    visited.add(marker)
    if isinstance(value, list):
        for item in value:
            _downgrade_nested_extreme_conviction_lists_to_observation(item, visited)
        return

    direct = value.get("extreme_conviction_list")
    if isinstance(direct, list) and direct:
        value["extreme_conviction_list"] = _downgrade_extreme_conviction_list_to_observation(direct)

    for key, nested in list(value.items()):
        key_text = str(key or "")
        if (
            key_text in {
                "data",
                "execution_stage_context",
                "market_research_snapshot",
                "candidate_snapshot",
                "candidate_selection",
                "step2_bundle",
                "report_outputs",
                "decision_ledger",
            }
            or "conviction" in key_text
            or "candidate" in key_text
        ):
            _downgrade_nested_extreme_conviction_lists_to_observation(nested, visited)


def _sync_runtime_extreme_conviction_list_after_position_decision(data, execution_stage_context, market_research_snapshot, position_decision):
    if not _has_zero_participation_context(position_decision):
        return execution_stage_context.get("extreme_conviction_list", []) or []
    original = (
        execution_stage_context.get("extreme_conviction_list")
        or _extract_extreme_conviction_list(market_research_snapshot)
        or _extract_extreme_conviction_list(data)
    )
    if not original:
        return []
    downgraded = _downgrade_extreme_conviction_list_to_observation(original)
    execution_stage_context["extreme_conviction_list"] = downgraded
    data["extreme_conviction_list"] = downgraded
    data["execution_stage_context"] = execution_stage_context
    if isinstance(market_research_snapshot, dict):
        market_research_snapshot["extreme_conviction_list"] = downgraded
        candidate_snapshot = market_research_snapshot.get("candidate_snapshot")
        if not isinstance(candidate_snapshot, dict):
            candidate_snapshot = {}
        candidate_snapshot["extreme_conviction_list"] = downgraded
        market_research_snapshot["candidate_snapshot"] = candidate_snapshot
        execution_stage_context["market_research_snapshot"] = market_research_snapshot
        data["market_research_snapshot"] = market_research_snapshot
    _downgrade_nested_extreme_conviction_lists_to_observation(data)
    _downgrade_nested_extreme_conviction_lists_to_observation(execution_stage_context)
    _downgrade_nested_extreme_conviction_lists_to_observation(market_research_snapshot)
    return downgraded


def _maybe_persist_decision_ledger(
    *,
    data,
    target_date,
    execution_stage_context,
    market_research_snapshot=None,
):
    if not globals().get("persist_decision_ledger", False):
        return None
    execution_stage_context = execution_stage_context or {}
    extreme_conviction_list = execution_stage_context.get("extreme_conviction_list", []) or []
    build_snapshot = globals().get("build_decision_ledger_snapshot") or _default_build_decision_ledger_snapshot
    write_artifacts = globals().get("write_decision_ledger_artifacts") or _default_write_decision_ledger_artifacts
    snapshot = build_snapshot(
        trade_date=target_date,
        extreme_conviction_list=extreme_conviction_list,
        market_branch=_resolve_decision_ledger_market_branch(market_research_snapshot, execution_stage_context),
        sector_relationship_state=_resolve_decision_ledger_sector_relationship(execution_stage_context),
        source_report=(data or {}).get("source_report") or {},
    )
    result = write_artifacts(
        snapshot,
        root_dir=globals().get("decision_ledger_root_dir", "."),
    )
    tracking_lines = _build_decision_ledger_tracking_lines(result)
    if isinstance(result, dict):
        result["tracking_lines"] = tracking_lines
    if isinstance(data, dict):
        data["decision_ledger_artifacts"] = result
    return result


def _read_decision_ledger_index_for_tracking(root_dir="."):
    reader = globals().get("read_decision_ledger_index")
    index_path = Path(root_dir or ".") / "data" / "decision-ledger" / "index.json"
    if callable(reader):
        return reader(index_path)
    if not index_path.exists():
        return {}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _query_extreme_conviction_mention_rows_for_tracking(root_dir=".", end_date="", window_days=25, include_a_kill=False):
    end_date = str(end_date or "").strip()
    globals()["_last_extreme_conviction_a_kill_mark_result"] = {"updated_count": 0, "updated_records": []}
    if not end_date:
        return []
    query_rows = globals().get("query_extreme_conviction_mention_rows_for_tracking")
    if callable(query_rows):
        try:
            result = query_rows(
                root_dir=root_dir,
                end_date=end_date,
                window_days=window_days,
                include_a_kill=include_a_kill,
            ) or []
        except TypeError:
            try:
                result = query_rows(root_dir=root_dir, end_date=end_date, window_days=window_days) or []
            except Exception:
                return []
        try:
            if isinstance(result, dict):
                mark_result = {
                    "updated_count": int(result.get("updated_count") or 0),
                    "updated_records": list(result.get("updated_records") or []),
                }
                globals()["_last_extreme_conviction_a_kill_mark_result"] = mark_result
                return list(result.get("rows") or [])
            return list(result or [])
        except Exception:
            return []
    try:
        from storage.database_service import DatabaseService

        service = DatabaseService.sqlite_d1_compatible(Path(root_dir or ".") / "data" / "cloudflare_free_daily.db")
        mark_result = service.mark_a_kill_shape_extreme_conviction_mentions(
            end_date,
            window_days=window_days,
            return_details=True,
        )
        if isinstance(mark_result, dict):
            globals()["_last_extreme_conviction_a_kill_mark_result"] = {
                "updated_count": int(mark_result.get("updated_count") or 0),
                "updated_records": list(mark_result.get("updated_records") or []),
            }
        return list(
            service.query_extreme_conviction_mentions(
                end_date,
                window_days=window_days,
                include_a_kill=include_a_kill,
            )
            or []
        )
    except Exception:
        return []


def _load_recent_extreme_conviction_mentions_for_selection(data, *, root_dir=".", target_date="", window_days=25):
    if not isinstance(data, dict):
        return []
    existing = data.get("recent_extreme_conviction_mentions")
    existing_review = data.get("recent_extreme_conviction_mentions_for_review")
    if isinstance(existing, list) and existing and isinstance(existing_review, list) and existing_review:
        return existing
    review_rows = _query_extreme_conviction_mention_rows_for_tracking(
        root_dir=root_dir,
        end_date=target_date,
        window_days=window_days,
        include_a_kill=True,
    )
    if not review_rows and isinstance(existing, list):
        data["recent_extreme_conviction_mentions_for_review"] = list(existing)
        return existing
    active_rows = [
        row
        for row in list(review_rows or [])
        if not bool((row or {}).get("is_a_kill_eliminated"))
    ]
    data["recent_extreme_conviction_mentions"] = active_rows
    data["recent_extreme_conviction_mentions_for_review"] = list(review_rows or active_rows or [])
    return data["recent_extreme_conviction_mentions"]


def _decision_ledger_tracking_end_date(index, decision_ledger_result=None):
    candidates = []
    if isinstance(index, dict):
        candidates.append(index.get("latest_trade_date"))
    if isinstance(decision_ledger_result, dict):
        candidates.append(decision_ledger_result.get("trade_date"))
    candidates.append(globals().get("target_date"))
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def _build_decision_ledger_tracking_lines(decision_ledger_result=None):
    render_tracking_lines = (
        globals().get("render_extreme_conviction_tracking_lines")
        or _default_render_extreme_conviction_tracking_lines
    )
    render_mention_lines = (
        globals().get("render_extreme_conviction_mention_tracking_lines")
        or _default_render_extreme_conviction_mention_tracking_lines
    )
    render_mention_rows = (
        globals().get("render_extreme_conviction_mention_tracking_rows")
        or _default_render_extreme_conviction_mention_tracking_rows
    )
    render_backtest_lines = (
        globals().get("render_extreme_conviction_backtest_lines")
        or _default_render_extreme_conviction_backtest_lines
    )
    if not callable(render_tracking_lines):
        return []
    index = (decision_ledger_result or {}).get("index") or _read_decision_ledger_index_for_tracking(
        globals().get("decision_ledger_root_dir", ".")
    )
    if not index:
        return []
    lines = list(render_tracking_lines(index) or [])
    mention_rows = _query_extreme_conviction_mention_rows_for_tracking(
        globals().get("decision_ledger_root_dir", "."),
        _decision_ledger_tracking_end_date(index, decision_ledger_result),
        window_days=25,
    )
    if mention_rows and callable(render_mention_rows):
        lines.extend(list(render_mention_rows(mention_rows) or []))
    elif callable(render_mention_lines):
        lines.extend(list(render_mention_lines(index) or []))
    if callable(render_backtest_lines):
        lines.extend(list(render_backtest_lines(index) or []))
    return lines


def _normalize_runtime_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def _clean_runtime_cell(value, default=""):
    text = " ".join(str(value or "").replace("|", "｜").split()).strip()
    return text if text else default


def _runtime_cell_float(value):
    try:
        if value in (None, ""):
            return None
        return float(str(value).strip().replace("%", "").replace("+", ""))
    except (TypeError, ValueError):
        return None


def _split_runtime_markdown_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _is_runtime_markdown_separator(cells):
    return bool(cells) and all(set(str(cell).replace(" ", "")) <= {"-", ":"} for cell in cells)


def _runtime_header_index(headers, *names):
    for name in names:
        if name in headers:
            return headers.index(name)
    return -1


def _current_extreme_conviction_codes(execution_stage_context=None):
    codes = set()
    for item in (execution_stage_context or {}).get("extreme_conviction_list", []) or []:
        code = _normalize_runtime_stock_code(
            (item or {}).get("code")
            or (item or {}).get("stock_code")
            or (item or {}).get("股票代码")
        )
        if code:
            codes.add(code)
    return codes


def _build_front_page_selected_position_candidate(execution_stage_context=None):
    execution_stage_context = execution_stage_context or {}
    selected = execution_stage_context.get("selected_position_candidate") or execution_stage_context.get("best_stock") or execution_stage_context.get("watch_anchor")
    if isinstance(selected, dict) and (selected.get("name") or selected.get("code") or selected.get("stock_code")):
        return dict(selected)
    for item in execution_stage_context.get("extreme_conviction_list", []) or []:
        if not isinstance(item, dict):
            continue
        plan = item.get("planned_participation") or item.get("participation_script") or {}
        return {
            "name": item.get("name") or item.get("stock_name"),
            "code": item.get("code") or item.get("stock_code"),
            "sector": item.get("sector") or item.get("sector_name") or item.get("所属板块"),
            "source_tier": "extreme_conviction",
            "participation_window": plan.get("buy_window") or plan.get("participation_window") or "09:50-10:10",
            "participation_window_type": plan.get("participation_window_type") or "auction_reseal",
            "required_steps": plan.get("required_steps") or ["竞价表态", "开盘前几分钟承接", "回封/打板"],
            "fallback_state": plan.get("fallback_state") or plan.get("cancellation") or "条件不满足回到0%",
            "condition": plan.get("condition") or "竞价表态 + 开盘前几分钟 + 回封/打板",
        }
    return {}


def _is_runtime_extreme_ice_point(data=None, market_research_snapshot=None, final_gate=None):
    data = data or {}
    market_research_snapshot = market_research_snapshot or {}
    final_gate = final_gate or {}
    state_machine = market_research_snapshot.get("state_machine") if isinstance(market_research_snapshot, dict) else {}
    for source in (data, market_research_snapshot, state_machine or {}, final_gate):
        if isinstance(source, dict) and source.get("market_ice_point") is True:
            return True
    evidence = {}
    if isinstance(state_machine, dict):
        evidence = state_machine.get("market_performance_evidence") or {}
    if not evidence and isinstance(market_research_snapshot, dict):
        evidence = market_research_snapshot.get("market_performance_evidence") or {}
    funding = evidence.get("funding_activity") if isinstance(evidence, dict) else {}
    new_high = evidence.get("new_high_attack") if isinstance(evidence, dict) else {}
    top50_share = _runtime_cell_float((funding or {}).get("top50_share_pct"))
    new_high_pct = _runtime_cell_float((new_high or {}).get("all_a_share_pct"))
    return bool(top50_share is not None and top50_share < 18 and new_high_pct is not None and new_high_pct < 1)


def _iter_runtime_text_values(value, depth=0):
    if depth > 3:
        return
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_runtime_text_values(nested, depth + 1)
        return
    if isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _iter_runtime_text_values(nested, depth + 1)


def _is_runtime_countertrend_attack_day(data=None, market_research_snapshot=None, final_gate=None):
    data = data or {}
    market_research_snapshot = market_research_snapshot or {}
    final_gate = final_gate or {}
    state_machine = market_research_snapshot.get("state_machine") if isinstance(market_research_snapshot, dict) else {}
    sources = [
        data.get("mainline_turnover_summary") if isinstance(data, dict) else {},
        data.get("current_mainline_history_record") if isinstance(data, dict) else {},
        market_research_snapshot,
        market_research_snapshot.get("mainline_turnover_summary") if isinstance(market_research_snapshot, dict) else {},
        market_research_snapshot.get("current_mainline_history_record") if isinstance(market_research_snapshot, dict) else {},
        state_machine or {},
        final_gate,
    ]
    text = " ".join(part for source in sources for part in _iter_runtime_text_values(source))
    return any(marker in text for marker in ("逆势试攻", "逆势攻击", "放量杀跌", "先防踩踏", "踩踏"))


def _force_observation_position_decision(position_decision):
    position_decision = dict(position_decision or {}) if isinstance(position_decision, dict) else {}
    monthly_rhythm = (
        dict(position_decision.get("monthly_rhythm") or {})
        if isinstance(position_decision.get("monthly_rhythm"), dict)
        else {}
    )
    monthly_rhythm.update(
        {
            "month_mode": monthly_rhythm.get("month_mode") or "weak_market_defense",
            "target_role": "observe",
            "max_position_pct": 0,
            "allow_full_attack": False,
            "trend_invalid": True,
            "reason": "当天是放量杀跌里的局部逆势活跃，先防踩踏，等指数图形与主攻线承接同时修复后再给参与资格。",
        }
    )
    updated = dict(position_decision)
    updated.update(
        {
            "participation_mode": "observe_0",
            "target_position_pct": 0,
            "signal_grade": "0",
            "candidate_feedback_ready": False,
            "sizing_reason": "当天是放量杀跌里的局部逆势活跃，不把局部强势当成参与资格；先防踩踏，等指数图形与主攻线承接同时修复后再给参与资格。",
            "monthly_rhythm": monthly_rhythm,
            "single_focus_constraint": {
                "status": "observe",
                "reason": "市场整体承接未修复，唯一对象只保留观察，不给新增参与资格。",
            },
        }
    )
    return updated


def _force_observation_for_missing_execution_evidence(position_decision):
    position_decision = dict(position_decision or {}) if isinstance(position_decision, dict) else {}
    monthly_rhythm = (
        dict(position_decision.get("monthly_rhythm") or {})
        if isinstance(position_decision.get("monthly_rhythm"), dict)
        else {}
    )
    monthly_rhythm.update(
        {
            "month_mode": monthly_rhythm.get("month_mode") or "observation",
            "target_role": "observe",
            "max_position_pct": 0,
            "allow_full_attack": False,
            "trend_invalid": bool(monthly_rhythm.get("trend_invalid")),
            "reason": "重点观察对象只说明偏好集中，缺少独立参与证据时不自动生成仓位结论。",
        }
    )
    updated = dict(position_decision)
    updated.update(
        {
            "participation_mode": "observe_0",
            "target_position_pct": 0,
            "signal_grade": "0",
            "candidate_feedback_ready": False,
            "sizing_reason": "重点观察对象只保留固定交易窗口预案；缺少独立参与证据，不把偏好名单自动抬成仓位结论。",
            "monthly_rhythm": monthly_rhythm,
            "single_focus_constraint": {
                "status": "observe",
                "reason": "已有观察对象，但仓位结论仍需来自独立参与证据。",
            },
        }
    )
    return updated


def _candidate_from_extreme_item(item):
    if not isinstance(item, dict):
        return {}
    plan = item.get("planned_participation") or item.get("participation_script") or {}
    if not isinstance(plan, dict):
        plan = {}
    return {
        "name": item.get("name") or item.get("stock_name"),
        "code": _normalize_runtime_stock_code(item.get("code") or item.get("stock_code")),
        "sector": item.get("sector") or item.get("sector_name") or item.get("所属板块"),
        "source_tier": "extreme_conviction",
        "source_section": item.get("source_section") or "极度看好名单",
        "rank": item.get("rank"),
        "participation_window": plan.get("buy_window") or plan.get("participation_window") or "09:50-10:10",
        "participation_window_type": plan.get("participation_window_type") or "auction_reseal",
        "required_steps": plan.get("required_steps") or ["竞价表态", "开盘前几分钟承接", "回封/打板"],
        "fallback_state": plan.get("fallback_state") or plan.get("cancellation") or "条件不满足回到0%",
        "condition": plan.get("condition") or plan.get("participation_window") or "竞价表态 + 开盘前几分钟 + 回封/打板",
        "planned_participation": dict(plan),
    }


def _sort_front_page_candidates(items):
    def _rank(item):
        rank = _runtime_cell_float((item or {}).get("rank"))
        return int(rank) if rank is not None else 999

    return sorted(
        [item for item in list(items or []) if isinstance(item, dict) and (item.get("name") or item.get("code") or item.get("stock_code"))],
        key=lambda item: (_rank(item), str(item.get("code") or item.get("stock_code") or ""), str(item.get("name") or item.get("stock_name") or "")),
    )


def _front_page_candidates_from_decision_ledger(data=None, target_date=""):
    data = data or {}
    artifacts = data.get("decision_ledger_artifacts") or {}
    index = artifacts.get("index") if isinstance(artifacts, dict) else {}
    records = []
    trade_date = str(target_date or data.get("target_date") or "").strip()
    if isinstance(index, dict):
        for group in (index.get("by_stock_code") or {}).values():
            for record in list(group or []):
                if str(record.get("latest_trade_date") or "").strip() != trade_date:
                    continue
                mentions = record.get("mentions") or []
                latest = mentions[-1] if mentions else {}
                if str(latest.get("mention_trade_date") or "").strip() != trade_date:
                    continue
                planned = record.get("planned_participation") or latest.get("planned_participation") or {}
                records.append(
                    {
                        "rank": latest.get("rank") or record.get("rank"),
                        "name": record.get("stock_name"),
                        "code": record.get("stock_code"),
                        "sector": (record.get("hypothesis") or {}).get("sector_candidate"),
                        "source_section": latest.get("source_section") or "极度看好名单",
                        "planned_participation": planned,
                    }
                )
        if records:
            return [_candidate_from_extreme_item(item) for item in _sort_front_page_candidates(records)]

    rows = index.get("extreme_conviction_backtest_rows") if isinstance(index, dict) else []
    for row in list(rows or []):
        if str(row.get("mention_trade_date") or "").strip() != trade_date:
            continue
        records.append(
            {
                "rank": row.get("rank"),
                "name": row.get("stock_name"),
                "code": row.get("stock_code"),
                "sector": row.get("sector_candidate"),
                "source_section": row.get("source_section") or "极度看好名单",
                "planned_participation": {
                    "buy_window": row.get("buy_window"),
                    "attack_state": "50%",
                    "source_tier": "extreme_conviction",
                    "fallback_state": "条件不满足回到0%",
                },
            }
        )
    return [_candidate_from_extreme_item(item) for item in _sort_front_page_candidates(records)]


def _front_page_candidates_from_report_lines(report_lines):
    candidates = []
    lines = list(report_lines or [])
    for idx, line in enumerate(lines):
        if "极度看好名单" not in str(line) and "重点观察名单" not in str(line) and "主线内可执行候选" not in str(line):
            continue
        header = []
        for next_line in lines[idx + 1:]:
            cells = _split_runtime_markdown_row(next_line)
            if not cells:
                if header:
                    break
                continue
            if not header:
                header = cells
                continue
            if _is_runtime_markdown_separator(cells):
                continue

            def _cell(*names):
                cell_idx = _runtime_header_index(header, *names)
                return cells[cell_idx].strip() if 0 <= cell_idx < len(cells) else ""

            name = _clean_runtime_cell(_cell("股票", "名称", "目标"))
            code = _normalize_runtime_stock_code(_cell("代码", "股票代码"))
            if not name and not code:
                continue
            candidates.append(
                {
                    "rank": _cell("优先级", "排名"),
                    "name": name,
                    "code": code,
                    "sector": _clean_runtime_cell(_cell("所属板块", "板块", "所属方向")),
                    "source_section": "极度看好名单",
                    "planned_participation": {
                        "buy_window": "09:50-10:10",
                        "participation_window": "09:50-10:10",
                        "source_tier": "extreme_conviction",
                        "fallback_state": "条件不满足回到0%",
                    },
                }
            )
        if candidates:
            break
    return [_candidate_from_extreme_item(item) for item in _sort_front_page_candidates(candidates)]


def _resolve_front_page_target_candidate(data=None, execution_stage_context=None, report_lines=None, target_date=""):
    selected = _build_front_page_selected_position_candidate(execution_stage_context)
    if selected:
        return selected
    candidates = _front_page_candidates_from_decision_ledger(data, target_date=target_date)
    if candidates:
        return candidates[0]
    candidates = _front_page_candidates_from_report_lines(report_lines)
    if candidates:
        return candidates[0]
    return {}


def _front_page_target_pct(position_decision):
    if not isinstance(position_decision, dict):
        return 0
    return int(_runtime_cell_float(position_decision.get("target_position_pct")) or 0)


def _front_page_candidate_position_pct(candidate):
    if not isinstance(candidate, dict):
        return 0
    for key in ("target_position_pct", "position_pct", "planned_position_pct"):
        value = _runtime_cell_float(candidate.get(key))
        if value is not None:
            return int(value)
    return 0


def _repair_confirmed_front_page_position_decision(position_decision, *, selected_position_candidate=None):
    updated = dict(position_decision or {})
    target_pct = _front_page_target_pct(updated)
    if target_pct < 50:
        return updated
    monthly_rhythm = (
        dict(updated.get("monthly_rhythm") or {})
        if isinstance(updated.get("monthly_rhythm"), dict)
        else {}
    )
    monthly_rhythm["max_position_pct"] = max(
        int(_runtime_cell_float(monthly_rhythm.get("max_position_pct")) or 0),
        target_pct,
    )
    updated["monthly_rhythm"] = monthly_rhythm
    updated.setdefault("participation_mode", "attack_50_preview")
    updated.setdefault("signal_grade", "100" if target_pct >= 100 else "50")
    if selected_position_candidate:
        updated.setdefault("single_focus_constraint", {
            "status": "clear",
            "reason": "仓位结论已给出唯一对象，等待固定交易窗口内条件成立。",
        })
    return _repair_extreme_candidate_full_attack_check(updated)


def _query_monthly_account_context(root_dir=".", target_date="", account_id="main"):
    query_fn = globals().get("query_monthly_account_context")
    if callable(query_fn):
        return dict(query_fn(root_dir=root_dir, target_date=target_date, account_id=account_id) or {})
    try:
        from storage.database_service import DatabaseService

        service = DatabaseService.sqlite_d1_compatible(Path(root_dir) / "data" / "cloudflare_free_daily.db")
        row = service.query_monthly_account_ledger(target_date, account_id=account_id)
    except Exception:
        return {}
    if not row:
        return {}
    context = {
        "month_return_source": row.get("source_policy") or "monthly_account_ledger",
        "monthly_ledger_trade_date": row.get("trade_date", ""),
        "monthly_ledger_month_key": row.get("month_key", ""),
    }
    for key in (
        "month_return_pct",
        "equity",
        "cash",
        "position_market_value",
        "realized_pnl",
        "unrealized_pnl",
        "max_drawdown_pct",
        "planned_trade_count",
        "unplanned_trade_count",
    ):
        if row.get(key) not in (None, ""):
            context[key] = row.get(key)
    return context


def _merge_monthly_account_context(base_context=None, account_context=None):
    merged = dict(base_context or {})
    account_context = dict(account_context or {})
    if not account_context:
        merged.setdefault("month_return_source", "missing")
        return merged
    for key, value in account_context.items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def _repair_extreme_candidate_full_attack_check(position_decision):
    position_decision = dict(position_decision or {})
    full_attack_check = position_decision.get("full_attack_check")
    if not isinstance(full_attack_check, dict):
        return position_decision
    repaired_check = dict(full_attack_check)
    missing = [
        item
        for item in list(repaired_check.get("missing", []) or [])
        if str(item or "").strip() not in {"唯一对象", "参与窗口"}
    ]
    repaired_check["missing"] = missing
    if repaired_check.get("status") == "incomplete" and not missing:
        repaired_check["status"] = "ready"
    position_decision["full_attack_check"] = repaired_check
    return position_decision


def _build_front_page_position_decision(
    *,
    position_decision=None,
    selected_position_candidate=None,
    data=None,
    market_research_snapshot=None,
    final_gate=None,
):
    position_decision = dict(position_decision or {}) if isinstance(position_decision, dict) else {}
    selected_position_candidate = selected_position_candidate or {}
    if not selected_position_candidate:
        return position_decision
    if _is_runtime_countertrend_attack_day(
        data=data,
        market_research_snapshot=market_research_snapshot,
        final_gate=final_gate,
    ):
        return _force_observation_position_decision(position_decision)
    if _has_zero_participation_context(position_decision):
        return _force_observation_position_decision(position_decision)
    if _is_runtime_extreme_ice_point(data=data, market_research_snapshot=market_research_snapshot, final_gate=final_gate):
        return position_decision
    existing_target_pct = _front_page_target_pct(position_decision)
    if existing_target_pct >= 50:
        return _repair_confirmed_front_page_position_decision(
            position_decision,
            selected_position_candidate=selected_position_candidate,
        )
    candidate_target_pct = _front_page_candidate_position_pct(selected_position_candidate)
    if candidate_target_pct < 50:
        return _force_observation_for_missing_execution_evidence(position_decision)
    monthly_rhythm = dict(position_decision.get("monthly_rhythm") or {}) if isinstance(position_decision.get("monthly_rhythm"), dict) else {}
    monthly_rhythm.update(
        {
            "month_mode": "attack_prepare",
            "target_role": "attack_prepare",
            "max_position_pct": max(int(_runtime_cell_float(monthly_rhythm.get("max_position_pct")) or 0), 50),
            "allow_full_attack": bool(monthly_rhythm.get("allow_full_attack")),
            "trend_invalid": False,
            "reason": "明日极度看好目标已存在，普通防守态只缩小容器，不取消推荐属性。",
        }
    )
    updated = dict(position_decision)
    updated.update(
        {
            "participation_mode": "attack_50_preview",
            "target_position_pct": min(candidate_target_pct, 100),
            "signal_grade": "50",
            "candidate_feedback_ready": True,
            "sizing_reason": "明日极度看好目标标的已存在，市场未到极端冰点；盘前不抢跑，但保留50%标准进攻预演，固定交易窗口内条件不成立就回到0%。",
            "monthly_rhythm": monthly_rhythm,
            "single_focus_constraint": {
                "status": "clear",
                "reason": "已缩到明日极度看好目标，等待固定交易窗口内条件成立。",
            },
        }
    )
    return _repair_extreme_candidate_full_attack_check(updated)


def _target_candidate_label(candidate):
    if not isinstance(candidate, dict):
        return "明日目标标的"
    code = _normalize_runtime_stock_code(candidate.get("code") or candidate.get("stock_code"))
    name = _clean_runtime_cell(candidate.get("name") or candidate.get("stock_name"), default="")
    if code and name:
        return f"{code} {name}"
    return code or name or "明日目标标的"


def _build_effective_front_page_final_gate(final_gate=None, *, selected_position_candidate=None, position_decision=None):
    final_gate = dict(final_gate or {}) if isinstance(final_gate, dict) else {}
    target_pct = _front_page_target_pct(position_decision)
    if not selected_position_candidate or target_pct < 50:
        return final_gate

    target_label = _target_candidate_label(selected_position_candidate)
    updated = dict(final_gate)
    updated.update(
        {
            "gate_status": "条件进攻",
            "operation_state": "条件进攻态",
            "can_new_entry": False,
            "should_reduce": False,
            "allow_attack_50_ready": True,
            "base_position_cap_pct": max(int(_runtime_cell_float(updated.get("base_position_cap_pct")) or 0), 50),
            "final_action": f"明日目标标的保留条件50%预演：只看{target_label}，固定交易窗口内条件成立才执行，不满足回到0%",
            "final_participation": "有明日极度看好目标时，防守态只缩小容器，不取消推荐属性。",
            "gate_reason": "普通防守态不等于每天推荐空仓；先定明日目标标的，再用大盘、板块和分时确认决定是否接雨。",
        }
    )
    return updated


def _has_zero_participation_context(position_decision=None):
    if not isinstance(position_decision, dict) or not position_decision:
        return False
    signal_grade = str(position_decision.get("signal_grade") or "").strip()
    participation_mode = str(position_decision.get("participation_mode") or "").strip()
    target_pct = _front_page_target_pct(position_decision)
    monthly_rhythm = (
        dict(position_decision.get("monthly_rhythm") or {})
        if isinstance(position_decision.get("monthly_rhythm"), dict)
        else {}
    )
    monthly_max_pct = _runtime_cell_float(monthly_rhythm.get("max_position_pct"))
    if signal_grade == "0":
        return True
    if target_pct <= 0 and participation_mode in {"observe_0", "observation_only", "zero_participation"}:
        return True
    if target_pct <= 0 and monthly_max_pct == 0:
        return True
    return False


def _normalize_zero_participation_appendix_line(line):
    text = str(line or "")
    had_sniper_role = "明日主买对象" in text or "明日补位对象" in text
    if "重点观察名单" in text and "绑定参与窗口" in text:
        text = "**候选观察名单**（最终0%时只作观察样本，不构成明日新增参与）:"
    text = text.replace("重点观察参与脚本", "重点观察复核脚本")
    text = text.replace("明日主买对象", "候选观察")
    text = text.replace("明日补位对象", "候选观察补充")
    text = text.replace("主线内可执行候选", "主线内观察候选")
    text = text.replace("可执行候选", "观察候选")
    text = text.replace("执行分层", "观察分层")
    text = text.replace("最终复核", "观察复核")
    text = text.replace("参与窗口", "观察窗口")
    text = text.replace("参与窗", "观察窗")
    text = text.replace("回封参与", "回封观察")
    text = text.replace("| 50% |", "| 0%观察 |")
    text = text.replace("买入资格后", "观察资格成立后")
    text = text.replace("给出买入资格", "给出观察资格")
    text = text.replace("优化买点", "优化观察点")
    text = text.replace("均线回归试错", "均线回归观察")
    text = text.replace("回封/打板", "回封/封板观察")
    text = text.replace("打板策略", "封板观察")
    text = text.replace("才算试错条件", "才算复核条件")
    if "| 仓位三态 |" in text:
        text = text.replace("仓位三态", "观察状态")
    text = text.replace("允许小仓试错", "只观察，不试错")
    text = text.replace("才允许小仓试错", "只观察，不试错")
    text = text.replace("时参与", "时只观察")
    if had_sniper_role:
        text = text.replace("| 通过 |", "| 仅观察 |")
    if "空仓等待，禁止参与；若你有仓位，只做退出不做幻想" in text:
        text = text.replace(
            "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
            "明日不新增参与，只观察风险是否钝化、主攻线承接和唯一对象是否重新成立",
        )
    if "盘前0%；固定交易窗口内条件成立后才评估50%标准进攻" in text:
        text = text.replace(
            "盘前0%；固定交易窗口内条件成立后才评估50%标准进攻",
            "盘前0%；暂无新增参与资格，只观察风险是否钝化",
        )
    if _LEGACY_WINDOW_HIT_STANDARD_ATTACK_TEXT in text:
        text = text.replace(
            _LEGACY_WINDOW_HIT_STANDARD_ATTACK_TEXT,
            "盘前0%；暂无新增参与资格，只观察风险是否钝化",
        )
    if "0%观察，禁止抢跑，但保留重点观察名单的盘中确认路径" in text:
        text = text.replace(
            "0%观察，禁止抢跑，但保留重点观察名单的盘中确认路径",
            "0%观察，不抢跑，只保留候选观察的盘中复核路径",
        )
    return text


def _should_keep_zero_appendix_for_selected_target(position_decision=None):
    if not _has_zero_participation_context(position_decision):
        return False
    if not isinstance(position_decision, dict):
        return False
    if position_decision.get("candidate_feedback_ready") is False:
        return True
    single_focus = position_decision.get("single_focus_constraint") or {}
    if isinstance(single_focus, dict) and single_focus.get("status") == "observe":
        reason = str(single_focus.get("reason") or "")
        if "不给新增参与资格" in reason or "缺少独立参与证据" in reason:
            return True
    sizing_reason = str(position_decision.get("sizing_reason") or "")
    return "不把局部强势当成参与资格" in sizing_reason or "缺少独立参与证据" in sizing_reason


def _normalize_attack_preview_appendix_lines(lines, *, selected_position_candidate=None, position_decision=None):
    has_selected_target = isinstance(selected_position_candidate, dict) and bool(
        selected_position_candidate.get("name") or selected_position_candidate.get("code")
    )
    if has_selected_target and _should_keep_zero_appendix_for_selected_target(position_decision):
        return [_normalize_zero_participation_appendix_line(line) for line in list(lines or [])]
    if _has_zero_participation_context(position_decision) and not has_selected_target:
        return [_normalize_zero_participation_appendix_line(line) for line in list(lines or [])]
    if not has_selected_target and _front_page_target_pct(position_decision) < 50:
        return list(lines or [])

    target_label = _target_candidate_label(selected_position_candidate)
    target_pct = _front_page_target_pct(position_decision)
    normalized = []
    for line in list(lines or []):
        text = str(line or "")
        if "空仓等待，禁止参与；若你有仓位，只做退出不做幻想" in text:
            text = text.replace(
                "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
                f"明日目标标的保留条件50%预演：只看{target_label}，固定交易窗口内条件成立才执行，不满足回到0%",
            )
        if text == "- **进攻仓位三态**: 0%不参与":
            text = "- **进攻仓位三态**: 50%标准进攻预演"
        if "盘前0%；固定交易窗口内条件成立后才评估50%标准进攻" in text:
            text = text.replace(
                "盘前0%；固定交易窗口内条件成立后才评估50%标准进攻",
                "条件50%；盘前不抢跑，固定交易窗口内条件成立后执行，不满足回到0%",
            )
        if _LEGACY_WINDOW_HIT_STANDARD_ATTACK_TEXT in text:
            text = text.replace(
                _LEGACY_WINDOW_HIT_STANDARD_ATTACK_TEXT,
                "条件50%；盘前不抢跑，固定交易窗口内条件成立后执行，不满足回到0%",
            )
        if "0%观察，禁止抢跑，但保留重点观察名单的盘中确认路径" in text:
            text = text.replace(
                "0%观察，禁止抢跑，但保留重点观察名单的盘中确认路径",
                "条件50%预演，盘前不抢跑，只等明日目标标的盘中确认路径",
            )
        text = normalize_trading_time_text(text)
        text = text.replace("重点观察参与脚本", "重点观察复核脚本")
        text = text.replace("参与窗口", "固定交易窗口")
        text = text.replace("回封参与", "回封观察")
        normalized.append(text)
    return normalized


def _prune_decision_ledger_result_for_current_extreme_list(decision_ledger_result=None, *, target_date="", execution_stage_context=None):
    current_codes = _current_extreme_conviction_codes(execution_stage_context)
    if not current_codes:
        return decision_ledger_result
    if not isinstance(decision_ledger_result, dict):
        index = _read_decision_ledger_index_for_tracking(globals().get("decision_ledger_root_dir", "."))
        if not index:
            return decision_ledger_result
        decision_ledger_result = {"index": index}
    else:
        decision_ledger_result = dict(decision_ledger_result)
    if not isinstance(decision_ledger_result, dict):
        return decision_ledger_result
    index = decision_ledger_result.get("index")
    if not isinstance(index, dict):
        return decision_ledger_result
    prune_mentions = (
        globals().get("prune_replaced_same_day_extreme_mentions")
        or _default_prune_replaced_same_day_extreme_mentions
    )
    if not callable(prune_mentions):
        return decision_ledger_result
    pruned_index = prune_mentions(index, trade_date=target_date, current_codes=current_codes)
    updated = dict(decision_ledger_result)
    updated["index"] = pruned_index
    updated["tracking_lines"] = _build_decision_ledger_tracking_lines(updated)
    return updated


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


def _format_appendix_price(value):
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or "-"


def _appendix_daily_structure_ratio(daily_structure):
    count = daily_structure.get("kline_count")
    required = daily_structure.get("required_kline_count")
    if count is None and required is None:
        return "-"
    if required is None:
        return str(count)
    return f"{count or 0}/{required}"


def _appendix_market_zhongshu_pivot_row(market_zhongshu, *, current_mainline_history_record=None, data=None):
    market_zhongshu = market_zhongshu or {}
    daily_structure = market_zhongshu.get("daily_structure_current") or {}
    if not daily_structure:
        return None
    data = data or {}
    current_mainline_history_record = current_mainline_history_record or {}
    confirmation = market_zhongshu.get("chanlun_confirmation") or {}
    ratio = _appendix_daily_structure_ratio(daily_structure)
    start_date = daily_structure.get("start_date") or "-"
    end_date = daily_structure.get("end_date") or "-"
    structure_state = confirmation.get("confirmation_status") or daily_structure.get("candidate_status") or "待确认"
    mainline = (
        current_mainline_history_record.get("primary_mainline")
        or current_mainline_history_record.get("mainline")
        or current_mainline_history_record.get("leading_line")
        or "-"
    )
    pivot_range = (
        f"{_format_appendix_price(daily_structure.get('zd_candidate'))}"
        f"-{_format_appendix_price(daily_structure.get('zg_candidate'))}"
    )
    return {
        "date": data.get("target_date") or current_mainline_history_record.get("date") or end_date,
        "date_range": f"{start_date} ~ {end_date}",
        "pivot_level": f"日K结构候选（{ratio}）",
        "pivot_range": pivot_range,
        "position": "日K候选区间内",
        "structure_state": structure_state,
        "mainline": mainline,
        "mainline_degree": current_mainline_history_record.get("mainline_degree") or "观察主线",
        "evolution": structure_state,
        "replacement": "待确认",
        "interpretation": f"日K结构候选尚未确认为日线中枢；结构证据：{structure_state}。",
    }


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


def _normalize_appendix_a_kill_item(item):
    if isinstance(item, dict):
        return item
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        candidate, record = item[0], item[1]
        merged = {}
        if isinstance(candidate, dict):
            merged.update(candidate)
        if isinstance(record, dict):
            merged.update(record)
        if merged:
            return merged
    return {}


def _build_appendix_b_continuity_payload(
    *,
    current_mainline_history_record=None,
    recent_mainline_history=None,
    current_sector_turnover_snapshot=None,
    recent_sector_turnover_history=None,
    pivot_mainline_history=None,
    mainline_turnover_summary=None,
    target_date=None,
):
    from report.mainline_turnover_summary_support import resolve_mainline_attack_evidence_summary

    attack_summary = resolve_mainline_attack_evidence_summary({"mainline_turnover_summary": mainline_turnover_summary or {}})
    has_unconfirmed_attack = bool(attack_summary) and attack_summary.get("attack_state") != "confirmed_attack"
    target_date_text = str(target_date or "").strip()

    def _is_current_item(item):
        item_date = str((item or {}).get("date") or (item or {}).get("date_range") or "").strip()
        if not target_date_text or not item_date:
            return False
        return item_date[:10] == target_date_text[:10] or item_date == target_date_text[5:10]

    def _structure_record_from_item(item):
        record = {
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
        if has_unconfirmed_attack and _is_current_item(record):
            evidence = attack_summary.get("confirmation_evidence") or "板块攻击证据不足"
            record["mainline"] = "暂无确认主线"
            record["mainline_degree"] = "待确认"
            record["replacement"] = "待确认"
            record["interpretation"] = f"中枢只记录候选方向，不把单日热度升级为周期主线；{evidence}。"
            record["note"] = record["interpretation"]
        return record

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
    summary_turnover_items = []
    for row in (mainline_turnover_summary or {}).get("turnover_share_trend_rows") or []:
        if not isinstance(row, dict):
            continue
        row_date = str(row.get("date") or "").strip()
        if not row_date:
            continue
        summary_turnover_items.append(
            {
                "date": row_date,
                "mainline": row.get("cycle_mainline") or row.get("daily_attack_line") or "-",
                "turnover_share_pct": row.get("share") or "待累计",
                "source": "mainline_turnover_summary",
            }
        )
    if summary_turnover_items:
        turnover_share_history = _merge_turnover_share_history(turnover_share_history, summary_turnover_items)

    structure_mainline_records = [_structure_record_from_item(item) for item in list(pivot_mainline_history or [])]

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

    market_zhongshu = (
        execution_stage_context.get("market_zhongshu")
        or data.get("market_zhongshu")
        or market_research_snapshot.get("market_zhongshu")
        or {}
    )
    market_zhongshu_row = _appendix_market_zhongshu_pivot_row(
        market_zhongshu,
        current_mainline_history_record=current_mainline_history_record,
        data=data,
    )
    if market_zhongshu_row:
        return [market_zhongshu_row]

    snapshot = dict(market_research_snapshot)
    if current_mainline_history_record and not snapshot.get("current_mainline_history_record"):
        snapshot["current_mainline_history_record"] = current_mainline_history_record
    if recent_mainline_history and not snapshot.get("recent_mainline_history"):
        snapshot["recent_mainline_history"] = recent_mainline_history
    cycle_layer = derive_market_research_cycle_layer(snapshot, snapshot.get("state_machine") or {})
    return list(cycle_layer.get("pivot_mainline_rows") or [])


def _appendix_share_number(value):
    if value in (None, ""):
        return 0.0
    text = str(value).strip().replace("%", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _should_replace_appendix_turnover_share(existing_item, derived_item):
    if str((derived_item or {}).get("source") or "").strip() == "mainline_turnover_summary":
        existing_mainline = str((existing_item or {}).get("mainline") or "").strip()
        derived_mainline = str((derived_item or {}).get("mainline") or "").strip()
        if existing_mainline and derived_mainline and existing_mainline != derived_mainline:
            return True
        existing_share = _appendix_share_number((existing_item or {}).get("turnover_share_pct"))
        return existing_share <= 0
    existing_share = _appendix_share_number((existing_item or {}).get("turnover_share_pct"))
    derived_share = _appendix_share_number((derived_item or {}).get("turnover_share_pct"))
    if derived_share <= 0:
        return False
    return existing_share <= 0


def _merge_turnover_share_history(existing_items, derived_items):
    merged = list(existing_items or [])
    index_by_date = {
        str((item or {}).get("date") or "").strip(): idx
        for idx, item in enumerate(merged)
        if isinstance(item, dict) and str((item or {}).get("date") or "").strip()
    }
    for item in derived_items or []:
        if not isinstance(item, dict):
            continue
        item_date = str(item.get("date") or "").strip()
        if item_date and item_date in index_by_date:
            existing_idx = index_by_date[item_date]
            if _should_replace_appendix_turnover_share(merged[existing_idx], item):
                merged[existing_idx] = dict(item)
            continue
        merged.append(item)
        if item_date:
            index_by_date[item_date] = len(merged) - 1
    return merged


def _structure_record_key(item):
    return str((item or {}).get("date") or (item or {}).get("date_range") or "").strip()


def _merge_structure_mainline_records(existing_items, derived_items):
    merged = list(existing_items or [])
    index_by_key = {
        _structure_record_key(item): idx
        for idx, item in enumerate(merged)
        if isinstance(item, dict) and _structure_record_key(item)
    }
    for item in derived_items or []:
        if not isinstance(item, dict):
            continue
        item_key = _structure_record_key(item)
        if item_key and item_key in index_by_key:
            merged[index_by_key[item_key]] = dict(item)
            continue
        merged.append(item)
        if item_key:
            index_by_key[item_key] = len(merged) - 1
    return merged


def _appendix_date_key(item):
    return str((item or {}).get("date") or "").strip()


def _merge_appendix_items_by_date(existing_items, derived_items):
    merged = list(existing_items or [])
    index_by_date = {
        _appendix_date_key(item): idx
        for idx, item in enumerate(merged)
        if isinstance(item, dict) and _appendix_date_key(item)
    }
    for item in derived_items or []:
        if not isinstance(item, dict):
            continue
        item_date = _appendix_date_key(item)
        if item_date and item_date in index_by_date:
            merged[index_by_date[item_date]] = dict(item)
            continue
        merged.append(item)
        if item_date:
            index_by_date[item_date] = len(merged) - 1
    return merged


def _merge_appendix_b_payload(existing_appendix_b, derived_appendix_b):
    if not existing_appendix_b:
        return derived_appendix_b or {}
    if not isinstance(existing_appendix_b, dict):
        return derived_appendix_b or {}
    merged = dict(existing_appendix_b)
    if (derived_appendix_b or {}).get("turnover_share_history"):
        merged["turnover_share_history"] = _merge_turnover_share_history(
            merged.get("turnover_share_history") or [],
            (derived_appendix_b or {}).get("turnover_share_history") or [],
        )
    if (derived_appendix_b or {}).get("structure_mainline_records"):
        merged["structure_mainline_records"] = _merge_structure_mainline_records(
            merged.get("structure_mainline_records") or [],
            (derived_appendix_b or {}).get("structure_mainline_records") or [],
        )
    for key in (
        "historical_mainline_pool",
        "mainline_switch_log",
    ):
        if (derived_appendix_b or {}).get(key):
            merged[key] = _merge_appendix_items_by_date(
                merged.get(key) or [],
                (derived_appendix_b or {}).get(key) or [],
            )
    return merged


def _safe_float_or_none(value):
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace("%", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _appendix_item_change_pct(item):
    for key in ("change_pct", "change", "pct_chg", "涨跌幅"):
        value = _safe_float_or_none((item or {}).get(key))
        if value is not None:
            return value
    return None


def _appendix_item_is_limit_down(item):
    item = item or {}
    change_pct = _appendix_item_change_pct(item)
    if item.get("is_limit_down") or (change_pct is not None and change_pct <= -9.5):
        return True
    status_text = " / ".join(
        str(item.get(key) or "")
        for key in ("limit_status", "zt_status", "涨停状态", "status", "tag", "pattern")
    )
    return "跌停" in status_text


def _appendix_item_is_flat_heat_only(item):
    item = item or {}
    change_pct = _appendix_item_change_pct(item)
    pattern = str(item.get("pattern") or "")
    lianban = int(_safe_float_or_none(item.get("连板数", item.get("lianban", 0))) or 0)
    if change_pct is None:
        return False
    if lianban > 0 or change_pct >= 5:
        return False
    return -2 <= change_pct <= 2 or "震荡整理" in pattern or "普通形态" in pattern


def _appendix_monitoring_labels(item, source_pool, mainline_name):
    if _appendix_item_is_limit_down(item):
        return "风险回避", "跌停/接近跌停，取消明日参与", "跌停/接近跌停，不是明日核心"
    if source_pool == "主线核心" and not str(mainline_name or "").strip():
        if _appendix_item_is_flat_heat_only(item):
            return "候选观察", "仅观察，等待重新转强", "热度高但价格未转强，只能观察"
        return "候选观察", item.get("tmr_forecast") or "仅观察，等待主线确认", "无确认主攻线，不标主线核心"
    return source_pool, item.get("current_action") or item.get("tomorrow_action") or item.get("tmr_forecast") or "继续跟踪", None


def _build_appendix_c_continuity_payload(*, target_date="", execution_stage_context=None):
    execution_stage_context = execution_stage_context or {}
    current_turnover = execution_stage_context.get("current_sector_turnover_snapshot") or {}
    mainline_name = (
        execution_stage_context.get("mainline_name")
        or execution_stage_context.get("primary_mainline")
        or (current_turnover.get("sector_name") if isinstance(current_turnover, dict) else "")
        or ""
    )
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
            display_source_pool, current_action, forced_interpretation = _appendix_monitoring_labels(item, source_pool, mainline_name)
            interpretation = (
                forced_interpretation
                or item.get("current_interpretation")
                or item.get("abnormal_summary")
                or item.get("why_watch")
                or item.get("reason")
                or "进入观察池，等待后续交易日累计"
            )
            monitoring_pool.append(
                {
                    "stock_name": _appendix_stock_name(item),
                    "stock_code": code,
                    "source_pool": display_source_pool,
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
    a_kill_items = [_normalize_appendix_a_kill_item(item) for item in a_kill_items]
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


def _keyword_match_event_sectors(title: str) -> dict:
    return normalize_calendar_ai_analysis({}, title, "")


def _normalize_calendar_batch_results(batch_results, events):
    if not isinstance(batch_results, list):
        batch_results = []

    normalized_results = []
    for index, event in enumerate(events or []):
        title = event.get("title", "") if isinstance(event, dict) else ""
        summary = event.get("summary", "") if isinstance(event, dict) else ""
        raw_result = batch_results[index] if index < len(batch_results) else None
        normalized_results.append(normalize_calendar_ai_analysis(raw_result, title, summary))
    return normalized_results


def _build_calendar_ai_context(data, print_fn=print):
    events = (data or {}).get("calendar_events") or []
    if not events:
        return {
            "calendar_analysis": [],
            "top_directions": [],
            "unique_sectors": [],
            "bullish_events": [],
            "analysis_source": "local_rules",
            "remote_llm_error": "",
        }

    event_count = len(events)
    estimated_time = max(15, event_count * 1.5)
    batch_size = 8
    total_batches = (event_count + batch_size - 1) // batch_size

    batch_start = time.time()
    events_for_analysis = [{"title": event.get("title", ""), "summary": ""} for event in events]

    analysis_source = "local_rules"
    remote_llm_error = ""
    if ENABLE_REMOTE_CALENDAR_LLM:
        print_fn(f"   🤖 远程LLM增强分析 {event_count} 个财经事件...")
        print_fn(f"      ⏱  预计耗时 {estimated_time:.0f}-{estimated_time*1.5:.0f} 秒（分{total_batches}批处理，每批约10-15秒）")
        print_fn("      💡 分析内容包括：产业链方向识别、细分板块归类、炒作逻辑生成...")
        try:
            client = get_llm_service()
            batch_results = client.analyze_events_batch(events_for_analysis, batch_size=batch_size)
            batch_elapsed = time.time() - batch_start
            print_fn(f"   ✅ 远程LLM增强完成 [⏱ {batch_elapsed:.2f}s]")

            llm_call_stats = _ensure_llm_call_stats()
            llm_call_stats["total_calls"] += 1
            llm_call_stats["total_time"] += batch_elapsed
            llm_call_stats["event_analysis_calls"] += len(events_for_analysis)
            llm_call_stats["event_analysis_time"] += batch_elapsed
            analysis_source = "remote_llm"
        except Exception as error:
            remote_llm_error = str(error)
            print_fn(f"   ⚠️ 远程LLM失败: {error}，使用本地规则")
            batch_results = [_keyword_match_event_sectors(event.get("title", "")) for event in events]
    else:
        print_fn(f"   🧭 本地规则分析 {event_count} 个财经事件（远程LLM默认关闭）")
        batch_results = [_keyword_match_event_sectors(event.get("title", "")) for event in events]

    batch_results = _normalize_calendar_batch_results(batch_results, events)

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
        filtered_sectors = [sector for sector in related_sectors if sector and sector not in ["需盘面确认", "相关产业链标的"]]
        all_sectors.extend(filtered_sectors)

    direction_counts = Counter(all_directions)
    top_directions = [(direction, count) for direction, count in direction_counts.most_common(10)][:5]
    unique_sectors = list(dict.fromkeys(all_sectors))[:10]
    bullish_events = [item for item in calendar_analysis if (item.get("ai_analysis") or {}).get("expectation") == "利好"]

    return {
        "calendar_analysis": calendar_analysis,
        "top_directions": top_directions,
        "unique_sectors": unique_sectors,
        "bullish_events": bullish_events,
        "analysis_source": analysis_source,
        "remote_llm_error": remote_llm_error,
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
    llm_wiki_context = build_llm_wiki_context()
    if isinstance(data, dict):
        data.setdefault("knowledge", {})["llm_wiki"] = llm_wiki_context
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
    knowledge_note_lines = build_ai_friction_knowledge_note(data if isinstance(data, dict) else {})
    if knowledge_note_lines:
        report = "\n".join([report.rstrip(), "", *knowledge_note_lines]).strip()
    candidate_note_lines = build_knowledge_compounding_candidate_note(llm_wiki_context)
    if candidate_note_lines:
        report = "\n".join([report.rstrip(), "", *candidate_note_lines]).strip()

    return {
        "report": report,
        "artifacts": {"llm_wiki": llm_wiki_context},
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
    if isinstance(market_analysis, dict):
        for risk_key in ("systemic_risk_warnings", "risk_theme_impacts", "risk_sectors"):
            if risk_key in market_analysis:
                data[risk_key] = list(market_analysis.get(risk_key) or [])
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
                "final_gate": final_gate,
                "position_level": position_level,
                "position_reason": position_reason,
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
                "mainline_turnover_summary": data.get("mainline_turnover_summary", {}) or {},
                "data": data,
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
        sectors_for_analysis = [direction for direction, _ in top_directions]
        if sectors_for_analysis:
            chain_analysis = ai_analyze_sector_relationships(
                sectors_for_analysis,
                "日历事件产业链分析",
                tag_evidence_snapshot=data.get("realtime_tag_evidence_snapshot") or {},
            )
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
    
    # 主线退出分析和最终执行条件已在前面构建，最终前台口径会在执行候选确定后统一。
    print(f"   ✅ 龙头股票: {len(dragon_stocks)} 只")
    print(f"   ✅ 主线退出分析完成: {exit_analysis.get('sector_name', '未知')}")

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
                "mainline_turnover_summary": data.get("mainline_turnover_summary", {}) or {},
                "realtime_tag_evidence_snapshot": data.get("realtime_tag_evidence_snapshot") or {},
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
    bundle_mainline_turnover_summary = (
        market_research_bundle.get("mainline_turnover_summary")
        or (market_research_bundle.get("market_research_snapshot", {}) or {}).get("mainline_turnover_summary", {})
        or {}
    )
    if bundle_mainline_turnover_summary:
        data["mainline_turnover_summary"] = _prefer_structured_mainline_turnover_summary(
            data.get("mainline_turnover_summary", {}) or {},
            bundle_mainline_turnover_summary,
        )
        market_research_bundle["mainline_turnover_summary"] = data["mainline_turnover_summary"]
        if isinstance(market_research_bundle.get("market_research_snapshot"), dict):
            market_research_bundle["market_research_snapshot"]["mainline_turnover_summary"] = data["mainline_turnover_summary"]
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
    root_dir = globals().get("decision_ledger_root_dir") or str(Path(__file__).resolve().parents[1])
    monthly_context = _merge_monthly_account_context(
        data.get("monthly_context") or {},
        _query_monthly_account_context(root_dir=root_dir, target_date=target_date),
    )
    data["monthly_context"] = monthly_context
    _load_recent_extreme_conviction_mentions_for_selection(
        data,
        root_dir=root_dir,
        target_date=target_date,
        window_days=25,
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
            "mainline_turnover_summary": data.get("mainline_turnover_summary", {}) or {},
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
            "monthly_context": monthly_context,
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
    _sync_runtime_extreme_conviction_list(data, execution_stage_context, market_research_snapshot)
    _sync_runtime_extreme_conviction_list_after_position_decision(
        data,
        execution_stage_context,
        market_research_snapshot,
        execution_stage_context.get("position_decision", {}) or {},
    )
    snapshot_mainline_turnover_summary = (
        market_research_snapshot.get("mainline_turnover_summary", {})
        if isinstance(market_research_snapshot, dict)
        else {}
    ) or {}
    mainline_turnover_summary = _prefer_structured_mainline_turnover_summary(
        execution_stage_context.get("mainline_turnover_summary", {}) or {},
        snapshot_mainline_turnover_summary,
    )
    mainline_turnover_summary = _prefer_structured_mainline_turnover_summary(
        mainline_turnover_summary,
        data.get("mainline_turnover_summary", {}) or {},
    )
    if mainline_turnover_summary:
        execution_stage_context["mainline_turnover_summary"] = mainline_turnover_summary
    decision_ledger_result = _maybe_persist_decision_ledger(
        data=data,
        target_date=target_date,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
    decision_ledger_result = _prune_decision_ledger_result_for_current_extreme_list(
        decision_ledger_result,
        target_date=target_date,
        execution_stage_context=execution_stage_context,
    )
    if isinstance(decision_ledger_result, dict):
        data["decision_ledger_artifacts"] = decision_ledger_result
    decision_ledger_tracking_lines = list(
        (decision_ledger_result or {}).get("tracking_lines")
        or _build_decision_ledger_tracking_lines(decision_ledger_result)
    )
    if market_research_snapshot:
        data["market_research_snapshot"] = market_research_snapshot
    else:
        market_research_snapshot = data.get("market_research_snapshot", {}) or {}
    snapshot_mainline_turnover_summary = (
        market_research_snapshot.get("mainline_turnover_summary", {})
        if isinstance(market_research_snapshot, dict)
        else {}
    ) or {}
    mainline_turnover_summary = _prefer_structured_mainline_turnover_summary(
        mainline_turnover_summary,
        snapshot_mainline_turnover_summary,
    )
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
    mainline_turnover_summary = _prefer_structured_mainline_turnover_summary(
        mainline_turnover_summary,
        data.get("mainline_turnover_summary", {}) or {},
    )
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
        if isinstance(market_research_snapshot, dict):
            market_research_snapshot["mainline_turnover_summary"] = _prefer_structured_mainline_turnover_summary(
                market_research_snapshot.get("mainline_turnover_summary", {}) or {},
                mainline_turnover_summary,
            )
            data["market_research_snapshot"] = market_research_snapshot
    else:
        mainline_turnover_summary = data.get("mainline_turnover_summary", {}) or {}
    build_mainline_turnover_summary_fn = globals().get("build_mainline_turnover_summary") or _default_build_mainline_turnover_summary
    if (
        current_mainline_history_record
        and not str((mainline_turnover_summary or {}).get("current_mainline") or "").strip()
        and not _summary_has_attack_evidence(mainline_turnover_summary)
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
        if isinstance(market_research_snapshot, dict):
            market_research_snapshot["mainline_turnover_summary"] = mainline_turnover_summary
            data["market_research_snapshot"] = market_research_snapshot
    snapshot_current_mainline_history_record = (
        market_research_snapshot.get("current_mainline_history_record", {})
        if isinstance(market_research_snapshot, dict)
        else {}
    ) or {}
    current_mainline_history_record = _prefer_confirmed_attack_mainline_history_record(
        execution_record=current_mainline_history_record,
        snapshot_record=snapshot_current_mainline_history_record,
        mainline_turnover_summary=mainline_turnover_summary,
        target_date=target_date,
    )
    if current_mainline_history_record:
        data["current_mainline_history_record"] = current_mainline_history_record
        if isinstance(market_research_snapshot, dict):
            market_research_snapshot["current_mainline_history_record"] = current_mainline_history_record
            data["market_research_snapshot"] = market_research_snapshot
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
    selected_position_candidate = _resolve_front_page_target_candidate(
        data=data,
        execution_stage_context=execution_stage_context,
        report_lines=report,
        target_date=target_date,
    )
    abnormal_probe_group = execution_stage_context.get('abnormal_probe_group', {}) or {}
    special_probe_verdict = execution_stage_context.get('special_probe_verdict', {}) or {}
    position_decision = execution_stage_context.get('position_decision', {}) or {}
    position_decision = _build_front_page_position_decision(
        position_decision=position_decision,
        selected_position_candidate=selected_position_candidate,
        data=data,
        market_research_snapshot=market_research_snapshot,
        final_gate=final_gate,
    )
    extreme_conviction_list = _sync_runtime_extreme_conviction_list_after_position_decision(
        data,
        execution_stage_context,
        market_research_snapshot,
        position_decision,
    )
    front_page_final_gate = _build_effective_front_page_final_gate(
        final_gate,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
    )
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
                "final_gate": front_page_final_gate,
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
                "selected_position_candidate": selected_position_candidate,
                "position_decision": position_decision,
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
    if decision_ledger_tracking_lines:
        report.extend(decision_ledger_tracking_lines)

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
        mainline_turnover_summary=mainline_turnover_summary,
        target_date=target_date,
    )
    appendix_b = _merge_appendix_b_payload(existing_appendix_b, derived_appendix_b)
    derived_appendix_c = _build_appendix_c_continuity_payload(
        target_date=target_date,
        execution_stage_context=execution_stage_context,
    )
    appendix_c = derived_appendix_c or data.get("appendix_c") or (market_research_snapshot.get("appendix_c") if isinstance(market_research_snapshot, dict) else {})
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
                "request_diagnostics": data.get("request_diagnostics", {}),
                "target_date": target_date,
                "generated_at": _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "report_version": "v2.5.0",
                "appendix_b": appendix_b,
                "appendix_c": appendix_c,
                "entry_cycle_calibration": entry_cycle_calibration,
                "new_stock_research_pool": data.get("new_stock_research_pool", []) or [],
                "new_stock_candidate_upgrades": data.get("new_stock_candidate_upgrades", []) or [],
                "margin_pressure": data.get("margin_pressure", {}) or {},
                "etf_turnover_series": data.get("etf_turnover_series", {}) or {},
                "extreme_conviction_list": extreme_conviction_list,
                "dragon_rebound_watch_pool": execution_stage_context.get("dragon_rebound_watch_pool", []) or [],
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

    selected_position_candidate = _resolve_front_page_target_candidate(
        data=data,
        execution_stage_context=execution_stage_context,
        report_lines=report,
        target_date=target_date,
    )
    position_decision = _build_front_page_position_decision(
        position_decision=position_decision,
        selected_position_candidate=selected_position_candidate,
        data=data,
        market_research_snapshot=market_research_snapshot,
        final_gate=final_gate,
    )
    extreme_conviction_list = _sync_runtime_extreme_conviction_list_after_position_decision(
        data,
        execution_stage_context,
        market_research_snapshot,
        position_decision,
    )
    front_page_final_gate = _build_effective_front_page_final_gate(
        final_gate,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
    )
    if isinstance(market_research_snapshot, dict):
        if "raw_final_gate" not in market_research_snapshot:
            market_research_snapshot["raw_final_gate"] = dict(market_research_snapshot.get("final_gate") or final_gate or {})
        personal_position_context = data.get("personal_position_context") if isinstance(data, dict) else {}
        if isinstance(personal_position_context, dict):
            for key in ("account_profile", "existing_position_summary"):
                if isinstance(personal_position_context.get(key), dict):
                    market_research_snapshot[key] = dict(personal_position_context.get(key) or {})
        if extreme_conviction_list:
            market_research_snapshot["extreme_conviction_list"] = extreme_conviction_list
            candidate_snapshot = market_research_snapshot.get("candidate_snapshot")
            if not isinstance(candidate_snapshot, dict):
                candidate_snapshot = {}
            candidate_snapshot["extreme_conviction_list"] = extreme_conviction_list
            market_research_snapshot["candidate_snapshot"] = candidate_snapshot
        market_research_snapshot["position_decision"] = position_decision
        market_research_snapshot["selected_position_candidate"] = selected_position_candidate
        market_research_snapshot["final_gate"] = front_page_final_gate
        market_research_snapshot["front_page_final_gate"] = front_page_final_gate
        data["market_research_snapshot"] = market_research_snapshot

    front_page_market_research_snapshot = {
        **(market_research_snapshot or {}),
        "current_mainline_history_record": current_mainline_history_record,
        "recent_mainline_history": recent_mainline_history,
        "current_sector_turnover_snapshot": current_sector_turnover_snapshot,
        "recent_sector_turnover_history": recent_sector_turnover_history,
        "mainline_turnover_summary": mainline_turnover_summary,
        "pivot_mainline_history": appendix_pivot_mainline_history,
        "position_decision": position_decision,
        "selected_position_candidate": selected_position_candidate,
        "extreme_conviction_list": extreme_conviction_list,
        "front_page_final_gate": front_page_final_gate,
    }
    front_page_lines = render_front_page_v2(
        report,
        target_date=target_date,
        market_research_snapshot=front_page_market_research_snapshot,
        final_gate=front_page_final_gate,
        position_level=position_level,
    )
    if DISPLAY_MVP_MODE:
        report = front_page_lines
    else:
        appendix_report = _normalize_attack_preview_appendix_lines(
            _remove_duplicate_front_page_sections_from_appendix(report),
            selected_position_candidate=selected_position_candidate,
            position_decision=position_decision,
        )
        report = front_page_lines + ["", "## 八、详细附录", ""] + _demote_appendix_headings(appendix_report)

    print(f"   ✅ 最终执行条件: {sanitize_user_visible_text(front_page_final_gate.get('final_action', '未知'))}")
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
