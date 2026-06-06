from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import os
import json
from pathlib import Path
import re
import time

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from llm_service import get_llm_service
from diagnostics.helper_diagnostics_runtime import (
    build_helper_diagnostics as _build_helper_diagnostics,
    clear_helper_logs as _clear_helper_logs,
    drain_helper_logs as _drain_helper_logs,
    render_helper_diagnostics_lines as _render_helper_diagnostics_lines,
)
from domains.calendar_events.infer import normalize_calendar_ai_analysis
from knowledge.llm_wiki_context import build_llm_wiki_context
from knowledge.llm_wiki_router import build_llm_wiki_fact_tags, route_llm_wiki_knowledge
from report.calendar_section_nodes import render_calendar_section
from report.action_plan_renderer import render_action_plan_result, render_action_plan_section
from report.decision_board_nodes import render_decision_board_section
from report.decision_ledger import (
    build_decision_coverage_summary as _default_build_decision_coverage_summary,
    build_decision_ledger_snapshot as _default_build_decision_ledger_snapshot,
    prune_replaced_same_day_extreme_mentions as _default_prune_replaced_same_day_extreme_mentions,
    render_extreme_conviction_backtest_lines as _default_render_extreme_conviction_backtest_lines,
    render_extreme_conviction_mention_tracking_lines as _default_render_extreme_conviction_mention_tracking_lines,
    render_extreme_conviction_mention_tracking_rows as _default_render_extreme_conviction_mention_tracking_rows,
    render_extreme_conviction_tracking_lines as _default_render_extreme_conviction_tracking_lines,
    write_decision_ledger_artifacts as _default_write_decision_ledger_artifacts,
)
from report.decision_statistics import (
    build_daily_judgment_review_panel as _default_build_daily_judgment_review_panel,
    build_five_judgment_statistics as _default_build_five_judgment_statistics,
    render_daily_judgment_review_panel_lines as _default_render_daily_judgment_review_panel_lines,
    render_five_judgment_statistics_lines as _default_render_five_judgment_statistics_lines,
)
from report.candidate_trace_artifacts import write_candidate_trace_artifact as _default_write_candidate_trace_artifact
from report.execution_chain_overview_nodes import render_execution_chain_overview_section
from report.no_trade_conclusion_nodes import render_no_trade_conclusion_section
from report.positioning_nodes import render_positioning_section
from report.front_summary_renderer import sanitize_front_page_text
from report.action_plan_renderer import render_action_plan_result, render_action_plan_section
from hooks.report.use_report_sections import (
    build_knowledge_hits_note,
    build_knowledge_compounding_candidate_note,
    build_knowledge_update_note,
)
from report.front_page_v2_renderer import render_front_page_v2
from report.market_structure_judgement import (
    build_market_structure_judgement,
    build_market_structure_knowledge_update,
)
from report.market_research_snapshot_nodes import derive_market_research_cycle_layer
from report.surface_wording import sanitize_user_visible_text
from report.sniper_target_derivation import (
    build_sniper_target_derivation_packet,
    compact_section as _sniper_target_derivation_compact_section,
    full_section as _sniper_target_derivation_full_section,
)
from report.two_layer_decision_payload import (
    build_two_layer_decision_payload,
    render_derivation_audit_layer,
    render_front_decision_layer,
)
from report.trading_time_window_contract import normalize_trading_time_text
from domains.market_state.mainline_turnover_summary_runtime import (
    build_mainline_turnover_summary as _default_build_mainline_turnover_summary,
)
from research.entry_cycle_calibration_runtime import (
    build_default_entry_cycle_calibrations as _default_build_entry_cycle_calibrations,
)
from selection.candidate_execution_contracts import build_opportunity_comparison

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

_SHANGHAI_TZ = timezone(timedelta(hours=8))
_CALENDAR_NEWS_PROVIDER = "xuangubao.xuangubao_news"
_CALENDAR_NEWS_CANDIDATE_LIMIT = 8
_CALENDAR_EVENT_FORM_TERMS = (
    "将于",
    "定于",
    "拟定于",
    "举办",
    "举行",
    "召开",
    "开幕",
    "启动",
    "发布",
    "首发",
    "正式",
    "大会",
    "会议",
    "论坛",
    "峰会",
    "展览",
    "展会",
    "交易会",
    "博览会",
    "交流会",
    "品牌",
    "第",
    "届",
    "全球",
    "国际",
    "中国",
)
_CALENDAR_EVENT_CUTOFF_TERMS = (
    "将于",
    "定于",
    "拟定于",
    "举办",
    "举行",
    "召开",
    "开幕",
    "启动",
    "发布",
    "首发",
    "正式",
)
_CALENDAR_WEAK_TITLE_TERMS = {
    "活动",
    "行业",
    "某行业",
    "产业",
    "交流",
    "会议",
    "大会",
    "论坛",
    "峰会",
    "展会",
    "发布会",
    "合作",
    "未来",
    "生态",
    "系列",
    "年度",
}
_CALENDAR_WEAK_TITLE_PARTS = (
    "行业",
    "产业",
    "交流",
    "合作",
    "活动",
    "会议",
    "大会",
    "论坛",
    "峰会",
    "展会",
    "发布会",
    "年度",
    "系列",
    "中国",
    "全球",
    "国际",
    "全国",
)


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
    event_signature = tuple(
        (
            str(item.get("date", "") or ""),
            str(item.get("title", "") or ""),
            _calendar_event_summary(item),
            int(item.get("star", 0) or 0),
        )
        for item in events
    )
    return event_signature, _calendar_xuangubao_news_signature(data)


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


_PSQL_STRUCTURED_TABLE_CONTEXT_MARKERS = (
    "周期日历主视图",
    "周期解读",
    "周期日历",
    "周期表",
    "周期切换",
    "中枢与主线",
    "中枢对应主线",
    "枢纽主线",
    "主线容量",
    "主线切换",
    "攻击证据",
    "主线攻击证据",
    "换手占比",
    "换手趋势",
    "主线成交额占比趋势",
    "近期热点板块成交额连续跟踪",
    "主线切换成交额记录",
    "主线成交额占比完整历史",
    "板块成交占比趋势",
    "板块周",
    "板块周期",
    "板块资金流",
    "概念资金流",
    "资金流入TOP10",
    "资金流出结果",
    "主线趋势密度",
    "主线竞争格局",
    "主线内观察候选",
    "明日次核心预判",
    "跨线观察候选",
    "重点观察名单",
    "异动后观察池",
    "观察池",
    "观察对象生命周期",
    "当前个股观察监控池",
    "跟踪记忆",
    "龙头记忆",
    "龙头记忆库",
    "历史主线池",
    "历史重点观察样本去向",
    "候选追踪",
    "候选链路",
    "候选主表",
    "候选选股轨迹",
    "候选选股轨迹明细",
    "极度看好",
    "明日极度看好近25日跟踪表",
    "重点观察25日跟踪表",
    "重点观察历史回测表",
    "板块扩散质量评分",
)

_PSQL_STRUCTURED_TABLE_CONTEXT_EXCLUDE_MARKERS = (
    "交易纪律",
    "明日账户建议",
    "月度攻防",
    "市场基底",
    "创新高趋势反馈",
    "融资承接",
    "资金意图",
    "龙虎榜资金状态",
    "资金结论",
    "个股裁决",
    "明日候选观察",
    "备用观察",
    "个股结论",
    "明日执行计划",
    "执行计划依据",
    "最终结论",
    "量化环境识别",
    "预期日历",
    "热度核心",
    "成交核心",
    "龙虎榜结果",
    "净买入结果",
    "净流出结果",
    "多维交易",
    "放量结果",
    "交易信号结果",
    "异动监控",
    "数据获取",
    "执行步骤清单",
    "请求审计",
    "统计信息",
    "缠论",
)

_PSQL_STRUCTURED_TABLE_CELL_PLACEHOLDERS = {
    "",
    "-",
    "—",
    "--",
    "N/A",
    "n/a",
    "待累计",
    "待验证",
    "待二次验证",
    "待确认",
    "暂无",
    "主线待确认",
    "主线待累计",
    "暂无确认主线",
    "暂无确认主攻线",
    "观察",
    "当前周期",
    "今日",
}

_PSQL_STRUCTURED_TABLE_ROW_PLACEHOLDER_MARKERS = (
    "数据暂缺",
    "后续日报自动累计",
    "暂无请求日志",
    "暂无样本",
    "无观察样本",
    "无跟踪样本",
    "无龙回头样本",
    "没有单独观察对象",
    "今天开始记录",
    "数据不足",
    "关键数据不完整",
    "暂不输出",
)


def _recent_table_context_lines(source_lines, table_start_index):
    context_lines = []
    for line in reversed(source_lines[:table_start_index]):
        text = str(line or "").strip()
        if not text or _is_t_number_line(text):
            continue
        if _is_markdown_table_line(text):
            break
        context_lines.append(text)
        if len(context_lines) >= 18:
            break
    context_lines = list(reversed(context_lines))
    heading_indexes = [index for index, text in enumerate(context_lines) if text.startswith("#")]
    if heading_indexes:
        return context_lines[heading_indexes[-1] :]
    marker_indexes = [
        index
        for index, text in enumerate(context_lines)
        if any(marker in text for marker in _PSQL_STRUCTURED_TABLE_CONTEXT_MARKERS)
    ]
    if marker_indexes:
        return context_lines[marker_indexes[0] :]
    return context_lines


def _split_markdown_table_cells(line):
    return [cell.strip() for cell in str(line or "").strip().strip("|").split("|")]


def _table_body_rows(source_lines, table_start_index):
    rows = []
    index = table_start_index + 2
    while index < len(source_lines):
        text = str(source_lines[index] or "").strip()
        if not _is_markdown_table_line(text):
            break
        if not _is_markdown_table_separator(text):
            rows.append(text)
        index += 1
    return rows


def _table_row_has_structured_fact(row):
    cells = _split_markdown_table_cells(row)
    joined = " ".join(cell for cell in cells if cell)
    if not joined:
        return False
    factual_markers = (
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}-\d{2}",
        r"\b\d{6}\b",
        r"\d+(?:\.\d+)?%",
        r"[+-]?\d+(?:\.\d+)?(?:亿|万|pct|日|分)",
    )
    has_factual_marker = any(re.search(pattern, joined) for pattern in factual_markers)
    has_stock_code = bool(re.search(r"\b\d{6}\b", joined))
    if any(marker in joined for marker in _PSQL_STRUCTURED_TABLE_ROW_PLACEHOLDER_MARKERS):
        no_sample_markers = ("暂无样本", "无观察样本", "无跟踪样本", "无龙回头样本", "没有单独观察对象")
        if any(marker in joined for marker in no_sample_markers):
            return False
        if not has_stock_code:
            return False
    if has_factual_marker:
        return True
    meaningful_cells = [
        cell
        for cell in cells
        if cell.strip() and cell.strip() not in _PSQL_STRUCTURED_TABLE_CELL_PLACEHOLDERS
    ]
    return len(meaningful_cells) >= 2 and not all("待" in cell or "暂无" in cell for cell in meaningful_cells)


def _table_has_structured_fact_rows(source_lines, table_start_index):
    return any(_table_row_has_structured_fact(row) for row in _table_body_rows(source_lines, table_start_index))


def _is_psql_structured_table_context(source_lines, table_start_index):
    context = "\n".join(_recent_table_context_lines(source_lines, table_start_index))
    if not context:
        return False
    if any(marker in context for marker in _PSQL_STRUCTURED_TABLE_CONTEXT_EXCLUDE_MARKERS):
        return False
    if not any(marker in context for marker in _PSQL_STRUCTURED_TABLE_CONTEXT_MARKERS):
        return False
    return _table_has_structured_fact_rows(source_lines, table_start_index)


def _number_report_tables(lines, postgres_only=False):
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
            source_label = "（PSQL）" if postgres_only and _is_psql_structured_table_context(source_lines, index) else ""
            numbered.append(f"**T-{table_index:03d}{source_label}**")
        numbered.append(line)
        index += 1
    return numbered


_ZERO_PARTICIPATION_OBSERVATION_FRAMEWORK = "最终0%时不按观察窗口执行，只观察指数图形、主攻线承接和观察对象是否重新成立。"
_LEGACY_WINDOW_HIT_STANDARD_ATTACK_TEXT = "盘前0%；" + "参与窗口" + "命中后才评估50%标准进攻"


def _should_apply_pure_zero_participation_cleanup(lines):
    return _has_final_zero_participation_surface(lines)


def _has_existing_position_zero_new_entry_surface(lines):
    text = "\n".join(str(line or "") for line in list(lines or []))
    has_existing_position = (
        "已有昨日持仓优先处理" in text
        or "先处理旧仓，不新增参与" in text
        or "先处理旧仓，不为新候选分散资金" in text
    )
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
        "日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构只看09:50-10:10窗口，按失效价和单笔-5%底线处理风险",
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
                    "日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构只看09:50-10:10窗口，按失效价和单笔-5%底线处理风险",
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
        ("重点观察优先锚点", "候选观察优先对象"),
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
        ("条件观察：", "观察对象："),
        ("观察锚：", "观察对象："),
        ("最终观察锚", "最终观察对象"),
        ("50%标准进攻需要先等固定交易窗口内条件成立；未确认前按0%处理，确认后按失效价和单笔-5%底线处理风险", "0%不参与：最终结论不允许新增参与，只观察风险是否钝化"),
        ("盘前0%；固定交易窗口条件满足后才评估50%标准进攻", "盘前0%；暂无新增参与资格，只观察风险是否钝化"),
        ("盘前0%；固定交易窗口条件满足后才保留观察，不能转成新增参与", "盘前0%；暂无新增参与资格，只观察风险是否钝化"),
        ("09:50-10:10站上确认价，且板块承接不塌，才评估50%标准进攻；未命中继续0%观察", "只保留观察；未出现执行资格前不新增参与；未命中继续0%观察"),
        ("盘前0%只代表不抢跑；09:50-10:10窗口内条件成立后，再评估50%标准进攻", "盘前0%只代表不抢跑；只观察，不新增参与"),
        ("以观察和处理持仓为主；新仓只允许固定交易窗口内条件成立后的主线核心50%标准进攻", "以观察和处理持仓为主；不做新开仓"),
        ("确认后才评估50%标准进攻，未确认保持0%", "确认后也只保留观察，未确认保持0%"),
        ("才评估50%标准进攻", "才保留观察；未出现执行资格前不新增参与"),
        ("触发后50%标准进攻", "触发后只观察"),
        ("条件50%", "只观察"),
        ("50%标准进攻", "只观察"),
        ("唯一对象是否", "观察对象是否"),
        ("观察锚是否", "观察对象是否"),
        ("观察锚强弱", "观察对象强弱"),
        ("观察锚缺少", "观察对象缺少"),
        ("观察锚不能", "观察对象不能"),
        ("观察锚重新成立", "观察对象重新成立"),
        ("只保留观察锚", "只保留观察对象"),
        ("暂不保留观察锚", "暂不保留观察对象"),
        ("没有观察锚", "没有观察对象"),
        ("有观察锚", "有观察对象"),
        ("只看观察锚", "只看观察对象"),
        ("观察锚", "观察对象"),
        ("不是执行对象", "不是执行目标"),
        ("观察锚性质", "观察对象性质"),
        ("观察锚去留", "观察对象去留"),
        ("✓ 溢价候选", "观察样本"),
        ("溢价候选", "观察样本"),
        ("MVP快照回退：先看次日是否继续强于市场，再按预演观察窗口确认。", "观察样本：先看是否强于市场，不预设参与。"),
        ("MVP快照回退：先看次日是否继续强于市场，再按固定交易窗口条件确认。", "观察样本：先看是否强于市场，不预设参与。"),
    )
    for line in list(lines or []):
        text = normalize_trading_time_text(str(line or ""))
        for source, target in replacements:
            text = text.replace(source, target)
        if text.lstrip().startswith("| 0%不参与 |") and ("| 观察锚：" in text or "| 观察对象：" in text):
            cells = text.strip().strip("|").split("|")
            if len(cells) >= 8:
                target = cells[5].strip()
                label = target.replace("观察锚：", "", 1).replace("观察对象：", "", 1).strip()
                cells[5] = f" 观察对象：{label} "
                cells[7] = f" 盘前0%；只观察{label}，成立才保留观察；未出现执行资格前不新增参与；不满足继续0% "
                text = "|" + "|".join(cells) + "|"
        if "允许进入" in text and "继续观察复核" in text:
            text = text.replace("允许进入", "只进入")
        text = text.replace("继续继续观察复核", "继续观察复核")
        text = text.replace("观察位失败仓", "买点失败仓")
        text = text.replace("新增参与0手", "新开仓0手")
        normalized.append(text)
    return normalized


_PROCESS_EVIDENCE_LINE_TITLES = (
    "主线内观察候选",
    "明日次核心预判",
    "跨线观察候选",
    "重点观察名单",
    "重点观察复核脚本",
    "历史重点观察样本去向",
    "重点观察25日跟踪表",
    "明日极度看好近25日跟踪表",
    "重点观察历史回测表",
    "明日观察池",
    "明天观察池",
    "异动后观察池",
    "跟踪记忆校验",
    "主线趋势密度复核",
    "当前个股观察监控池",
    "观察对象生命周期表",
    "逐只预判明日风险",
    "明日风险分组",
    "板块级明日风险预判",
    "明天先观察组",
    "明天重点候选组",
    "明日继续观察",
    "明日观察位预计算表",
    "今日总决策面板",
    "候选主表",
    "候选选股轨迹",
    "候选选股轨迹明细",
)


def _mark_process_evidence_line(text):
    text = str(text or "")
    if "过程证据" in text:
        return text
    stripped = text.strip()
    if not stripped:
        return text
    heading_like = stripped.startswith("#") or stripped.startswith("**")
    for title in _PROCESS_EVIDENCE_LINE_TITLES:
        if heading_like and title in stripped:
            return f"{text}（过程证据）"
        if stripped.startswith(f"**{title}**") or re.match(rf"^#{{1,6}}\s+(?:附录：#\s*)?{re.escape(title)}(?:\s|$)", stripped):
            return f"{text}（过程证据）"
    return text


def _front_page_observation_anchor_label(lines):
    for line in list(lines or []):
        text = str(line or "")
        if not text.startswith("|"):
            continue
        cells = [cell.strip() for cell in text.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in {"观察锚", "观察对象"} and cells[1] not in {"", "-", "暂无", "无"}:
            return cells[1]
    return ""


def _align_appendix_observation_anchor_from_front_page(lines):
    anchor_label = _front_page_observation_anchor_label(lines)
    if not anchor_label:
        return list(lines or [])
    normalized = []
    in_appendix = False
    in_watch_order = False
    first_watch_rewritten = False
    for line in list(lines or []):
        text = str(line or "")
        if text == "## 八、详细附录":
            in_appendix = True
            in_watch_order = False
            normalized.append(text)
            continue
        if not in_appendix:
            normalized.append(text)
            continue
        if "**观察优先锚点**" in text:
            prefix = text.split("**观察优先锚点**", 1)[0]
            normalized.append(f"{prefix}**观察优先锚点**: {anchor_label}")
            in_watch_order = False
            continue
        if re.match(r"^- \*\*.*观察谁\*\*:", text):
            prefix = text.split(":", 1)[0]
            normalized.append(f"{prefix}: {anchor_label}")
            continue
        if "**先看顺序**" in text:
            in_watch_order = True
            first_watch_rewritten = False
            normalized.append(text)
            continue
        if in_watch_order and not first_watch_rewritten and "👀" in text:
            normalized.append(re.sub(r"(?<=👀\s).*?(?=\s+-|$)", anchor_label, text, count=1))
            first_watch_rewritten = True
            continue
        normalized.append(text)
    return normalized


def _sanitize_report_lines(lines, postgres_only=False):
    return _number_report_tables(
        _dedupe_front_page_repeated_long_table_cells(
            _align_empty_primary_observation_rows(
                [
                    _mark_process_evidence_line(sanitize_front_page_text(line))
                    for line in _normalize_legacy_execution_framework_under_zero_participation(
                        _normalize_tomorrow_action_soft_words_under_zero_participation(
                            _align_appendix_observation_anchor_from_front_page(_dedupe_repeated_no_trade_lines(lines))
                        )
                    )
                ]
            )
        ),
        postgres_only=postgres_only,
    )


def _dedupe_front_page_repeated_long_table_cells(lines):
    cleaned = []
    seen = set()
    in_appendix = False
    for line in list(lines or []):
        text = str(line or "")
        if text == "## 八、详细附录":
            in_appendix = True
            cleaned.append(text)
            continue
        if in_appendix or not text.startswith("|"):
            cleaned.append(text)
            continue
        raw_cells = text.strip().strip("|").split("|")
        changed = False
        next_cells = []
        for cell in raw_cells:
            normalized = re.sub(r"\s+", " ", str(cell or "")).strip()
            if len(normalized) >= 40 and normalized in seen:
                next_cells.append(" 同类说明见上方，只看本行数值变化 ")
                changed = True
                continue
            next_cells.append(cell)
            if len(normalized) >= 40:
                seen.add(normalized)
        cleaned.append("|" + "|".join(next_cells) + "|" if changed else text)
    return cleaned


def _align_empty_primary_observation_rows(lines):
    rows = list(lines or [])
    aligned = []
    index = 0
    while index < len(rows):
        text = str(rows[index] or "")
        if not text.startswith("| 字段 | 内容 |"):
            aligned.append(text)
            index += 1
            continue
        panel = [text]
        index += 1
        while index < len(rows) and str(rows[index] or "").startswith("|"):
            panel.append(str(rows[index] or ""))
            index += 1
        observation_value = ""
        for line in panel:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0] == "观察对象" and cells[1] not in {"", "-", "暂无", "无"}:
                observation_value = cells[1]
                break
        if observation_value:
            next_panel = []
            for line in panel:
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if len(cells) >= 2 and cells[0] == "主观察对象" and cells[1] in {"", "-", "暂无", "无"}:
                    cells[1] = observation_value
                    line = "| " + " | ".join(cells) + " |"
                next_panel.append(line)
            panel = next_panel
        aligned.extend(panel)
    return aligned


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

    def _hot_watch_metric_signature(row):
        row = row or {}
        date = str(row.get("date") or "").strip()
        sector_turnover = str(row.get("sector_turnover") or "").strip()
        total_turnover = str(row.get("total_turnover") or row.get("market_turnover") or "").strip()
        share = str(row.get("share") or row.get("turnover_share_pct") or "").strip()
        if not (date and sector_turnover and total_turnover and share):
            return ()
        return (date, sector_turnover, total_turnover, share)

    def _hot_watch_conflict_score(rows):
        sectors_by_metric = {}
        conflicts = 0
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            sector = str(row.get("sector_name") or "").strip()
            signature = _hot_watch_metric_signature(row)
            if not sector or not signature:
                continue
            sectors = sectors_by_metric.setdefault(signature, set())
            if sectors and sector not in sectors:
                conflicts += 1
            sectors.add(sector)
        return conflicts

    def _hot_watch_exact_key(row):
        row = row or {}
        date = str(row.get("date") or "").strip()
        sector = str(row.get("sector_name") or "").strip()
        return (date, sector) if date and sector else ()

    def _sanitize_update_hot_watch_rows(base_rows, update_rows):
        sectors_by_base_metric = {}
        for row in base_rows or []:
            if not isinstance(row, dict):
                continue
            sector = str(row.get("sector_name") or "").strip()
            signature = _hot_watch_metric_signature(row)
            if sector and signature:
                sectors_by_base_metric.setdefault(signature, set()).add(sector)

        result = []
        result_keys = set()
        for row in update_rows or []:
            if not isinstance(row, dict):
                continue
            sector = str(row.get("sector_name") or "").strip()
            signature = _hot_watch_metric_signature(row)
            if signature in sectors_by_base_metric and sector not in sectors_by_base_metric[signature]:
                continue
            result.append(row)
            exact_key = _hot_watch_exact_key(row)
            if exact_key:
                result_keys.add(exact_key)

        for row in base_rows or []:
            if not isinstance(row, dict):
                continue
            exact_key = _hot_watch_exact_key(row)
            if exact_key and exact_key not in result_keys:
                result.append(row)
                result_keys.add(exact_key)
        return result

    def _sanitize_conflicting_hot_watch_rows(rows):
        indexed_rows = [(index, row) for index, row in enumerate(rows or []) if isinstance(row, dict)]
        grouped_indexes = {}
        for index, row in indexed_rows:
            signature = _hot_watch_metric_signature(row)
            sector = str(row.get("sector_name") or "").strip()
            if signature and sector:
                grouped_indexes.setdefault(signature, []).append(index)

        keep_indexes = {index for index, _row in indexed_rows}
        rows_by_index = {index: row for index, row in indexed_rows}
        for indexes in grouped_indexes.values():
            sectors = {
                str((rows_by_index[index] or {}).get("sector_name") or "").strip()
                for index in indexes
            }
            if len(sectors) <= 1:
                continue
            preferred_indexes = [
                index
                for index in indexes
                if str((rows_by_index[index] or {}).get("sample_status") or "").strip() != "同板块连续"
                or str((rows_by_index[index] or {}).get("share_change") or "").strip() in ("", "-", "待累计")
            ]
            if not preferred_indexes:
                continue
            for index in indexes:
                if index not in preferred_indexes:
                    keep_indexes.discard(index)
        return [row for index, row in indexed_rows if index in keep_indexes]

    def _hot_watch_share_number(row):
        text = str((row or {}).get("share") or (row or {}).get("turnover_share_pct") or "").strip().replace("%", "")
        try:
            return float(text)
        except (TypeError, ValueError):
            return 0.0

    def _rebuild_hot_watch_summary(rows, fallback_summary=""):
        rows = [row for row in rows or [] if isinstance(row, dict)]
        if not rows:
            return str(fallback_summary or "").strip()
        latest_date = max(str((row or {}).get("date") or "") for row in rows)
        latest_rows = [row for row in rows if str(row.get("date") or "") == latest_date]
        latest_rows = sorted(latest_rows, key=_hot_watch_share_number, reverse=True)
        leader = latest_rows[0] if latest_rows else rows[-1]
        leader_text = f"{leader.get('sector_name', '-')} {leader.get('share', '待累计')}"
        continuous_rows = [row for row in rows if str(row.get("sample_status") or "") == "同板块连续"]
        if continuous_rows:
            return (
                f"近期热点板块成交额连续跟踪：当前{latest_date}记录{len(latest_rows)}个热点板块，"
                f"{leader_text}居前；变化只按同一板块自身历史计算。"
            )
        return (
            f"近期热点板块成交额连续跟踪：当前{latest_date}记录{len(latest_rows)}个热点板块，"
            f"{leader_text}居前；同板块历史仍待累计，不跨板块解释涨跌。"
        )

    def _select_hot_watch_rows(base_rows, update_rows):
        if not update_rows:
            return None, False
        if not base_rows:
            return _sanitize_conflicting_hot_watch_rows(update_rows), True
        base_conflicts = _hot_watch_conflict_score(base_rows)
        update_conflicts = _hot_watch_conflict_score(update_rows)
        if update_conflicts > base_conflicts:
            sanitized_rows = _sanitize_update_hot_watch_rows(base_rows, update_rows)
            if sanitized_rows:
                return _sanitize_conflicting_hot_watch_rows(sanitized_rows), True
            return base_rows, False
        if base_conflicts > update_conflicts:
            return _sanitize_conflicting_hot_watch_rows(update_rows), True
        return _sanitize_conflicting_hot_watch_rows(update_rows), True

    def _with_turnover_watch_updates(base, updates):
        if not isinstance(base, dict):
            return base
        merged = dict(base)
        if not (isinstance(updates, dict) and updates.get("hot_sector_turnover_watch_rows")):
            if merged.get("hot_sector_turnover_watch_rows"):
                merged["hot_sector_turnover_watch_rows"] = _sanitize_conflicting_hot_watch_rows(
                    merged.get("hot_sector_turnover_watch_rows")
                )
                merged["hot_sector_turnover_watch_summary"] = _rebuild_hot_watch_summary(
                    merged.get("hot_sector_turnover_watch_rows"),
                    merged.get("hot_sector_turnover_watch_summary"),
                )
            return merged
        for key in (
            "data_text",
            "turnover_share_trend_summary",
            "turnover_share_trend_rows",
        ):
            if updates.get(key) not in (None, "", [], {}):
                merged[key] = updates.get(key)
        selected_rows, selected_from_updates = _select_hot_watch_rows(
            merged.get("hot_sector_turnover_watch_rows"),
            updates.get("hot_sector_turnover_watch_rows"),
        )
        if selected_rows not in (None, [], {}):
            merged["hot_sector_turnover_watch_rows"] = selected_rows
            merged["hot_sector_turnover_watch_summary"] = _rebuild_hot_watch_summary(
                selected_rows,
                updates.get("hot_sector_turnover_watch_summary") if selected_from_updates else merged.get("hot_sector_turnover_watch_summary"),
            )
        return merged

    primary_label = str(primary_summary.get("share_trend_label") or "").strip()
    fallback_label = str(fallback_summary.get("share_trend_label") or "").strip()
    if primary_label == "逆势试攻" and fallback_label != "逆势试攻":
        return _with_turnover_watch_updates(primary_summary, fallback_summary)
    if fallback_label == "逆势试攻" and primary_label != "逆势试攻":
        return _with_turnover_watch_updates(fallback_summary, primary_summary)
    if _summary_has_attack_evidence(fallback_summary) and not _summary_has_attack_evidence(primary_summary):
        return _with_turnover_watch_updates(fallback_summary, primary_summary)
    return _with_turnover_watch_updates(primary_summary or fallback_summary, fallback_summary or primary_summary)


def _mainline_name_from_turnover_summary(summary):
    summary = summary or {}
    attack_summary = summary.get("mainline_attack_evidence_summary") or {}
    return str(
        attack_summary.get("primary_line")
        or summary.get("current_mainline")
        or summary.get("cycle_mainline")
        or summary.get("daily_attack_line")
        or ""
    ).strip()


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
    postgres_only = bool(globals().get("decision_ledger_postgres_only", False))
    write_kwargs = {
        "root_dir": globals().get("decision_ledger_root_dir", "."),
        "write_json_archive": not postgres_only,
    }
    if postgres_only:
        write_kwargs["review_market_facts_by_stock_code"] = {}
    try:
        result = write_artifacts(snapshot, **write_kwargs)
    except TypeError as exc:
        if postgres_only:
            raise
        if "write_json_archive" not in str(exc):
            raise
        result = write_artifacts(
            snapshot,
            root_dir=globals().get("decision_ledger_root_dir", "."),
        )
    tracking_lines = _build_decision_ledger_tracking_lines(result, target_date=target_date)
    if isinstance(result, dict):
        result["tracking_lines"] = tracking_lines
    if isinstance(data, dict):
        data["decision_ledger_artifacts"] = result
    return result


def _build_default_candidate_trace_source_report(target_date, run_mode=None):
    mode = str(run_mode if run_mode is not None else globals().get("run_mode", "") or "").strip()
    if mode == LEDGER_MODE_REPLAY:
        path = f"reports/replay/{target_date}_A股日报_完整版_replay.md"
    else:
        path = f"reports/{target_date}_A股日报_完整版.md"
    return {"path": path, "variant": "full"}


def _maybe_persist_candidate_traces(
    *,
    data,
    target_date,
    execution_stage_context,
    run_mode=None,
):
    if not globals().get("persist_candidate_traces", False):
        return None
    execution_stage_context = execution_stage_context or {}
    traces = execution_stage_context.get("candidate_traces", []) or []
    if not traces:
        return None
    write_artifact = globals().get("write_candidate_trace_artifact") or _default_write_candidate_trace_artifact
    result = write_artifact(
        trade_date=target_date,
        traces=traces,
        eliminated_summary=execution_stage_context.get("candidate_trace_eliminated_summary", []) or [],
        root_dir=globals().get("candidate_trace_root_dir", "."),
        source_report=(data or {}).get("source_report") or _build_default_candidate_trace_source_report(target_date, run_mode),
        postgres_only=bool((data or {}).get("postgres_only") or globals().get("decision_ledger_postgres_only", False)),
    )
    if isinstance(data, dict):
        data["candidate_trace_artifact"] = result
    return result


def _postgres_database_configured():
    return (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip().startswith(("postgres://", "postgresql://"))


def _postgres_storage_required():
    return bool(
        globals().get("decision_ledger_postgres_only", False)
        or os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1"
        or _postgres_database_configured()
    )


def _read_decision_ledger_index_for_tracking(root_dir="."):
    postgres_required = _postgres_storage_required()
    reader = globals().get("read_decision_ledger_index")
    index_path = Path(root_dir or ".") / "data" / "decision-ledger" / "index.json"
    if callable(reader) and not postgres_required:
        return reader(index_path)
    try:
        service_cls = globals().get("DatabaseService")
        if service_cls is None:
            from storage.database_service import DatabaseService as service_cls

        service = service_cls.from_environment(Path(root_dir or ".") / "data" / "cloudflare_free_daily.db")
        checker = getattr(service, "is_postgres_backed", None)
        if callable(checker) and checker():
            db_index = service.read_decision_ledger_index()
            if db_index:
                return db_index
            return {}
        if postgres_required:
            raise RuntimeError("PostgreSQL decision ledger index storage requires PostgreSQL")
    except Exception:
        if postgres_required:
            raise
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
    postgres_required = _postgres_storage_required()
    query_rows = globals().get("query_extreme_conviction_mention_rows_for_tracking")
    if callable(query_rows) and not postgres_required:
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
                if postgres_required:
                    raise
                return []
        except Exception:
            if postgres_required:
                raise
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
            if postgres_required:
                raise
            return []
    try:
        from storage.database_service import DatabaseService

        db_path = Path(root_dir or ".") / "data" / "cloudflare_free_daily.db"
        if postgres_required:
            if not hasattr(DatabaseService, "from_environment"):
                raise RuntimeError("PostgreSQL extreme conviction storage requires DatabaseService.from_environment")
            service = DatabaseService.from_environment(db_path)
            checker = getattr(service, "is_postgres_backed", None)
            if not callable(checker) or not checker():
                raise RuntimeError("PostgreSQL extreme conviction storage requires PostgreSQL")
        elif hasattr(DatabaseService, "from_environment"):
            service = DatabaseService.from_environment(db_path)
        else:
            service = DatabaseService.sqlite_d1_compatible(db_path)
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
        if postgres_required:
            raise
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


def _build_decision_ledger_tracking_lines(decision_ledger_result=None, *, target_date=""):
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
    build_coverage_summary = (
        globals().get("build_decision_coverage_summary")
        or _default_build_decision_coverage_summary
    )
    build_five_judgment_statistics = (
        globals().get("build_five_judgment_statistics")
        or _default_build_five_judgment_statistics
    )
    render_five_judgment_statistics_lines = (
        globals().get("render_five_judgment_statistics_lines")
        or _default_render_five_judgment_statistics_lines
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
        mention_lines = list(render_mention_rows(mention_rows) or [])
        if callable(build_coverage_summary) and mention_lines:
            summary = build_coverage_summary(index, surface="tracking")
            sample_count = int((summary or {}).get("sample_count") or 0)
            start_date = str((summary or {}).get("start_date") or "").strip()
            end_date = str((summary or {}).get("end_date") or "").strip()
            if sample_count and start_date and end_date:
                mention_lines.insert(
                    1,
                    f"- 当前可复盘样本：{sample_count}条，覆盖{start_date}至{end_date}。本表展示最近25个交易日周期内样本。",
                )
        lines.extend(mention_lines)
    elif callable(render_mention_lines):
        lines.extend(list(render_mention_lines(index) or []))
    if callable(render_backtest_lines):
        lines.extend(list(render_backtest_lines(index) or []))
    if callable(build_five_judgment_statistics) and callable(render_five_judgment_statistics_lines):
        cutoff_date = str(target_date or _decision_ledger_tracking_end_date(index, decision_ledger_result) or "").strip()
        statistics = build_five_judgment_statistics(index, target_date=cutoff_date)
        lines.extend(list(render_five_judgment_statistics_lines(statistics) or []))
    return lines


def _first_runtime_text(*values):
    for value in values:
        if isinstance(value, dict):
            continue
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _runtime_user_visible_trade_text(value):
    text = str(value or "")
    stripped = text.strip()
    exact_aliases = {
        "unknown": "待识别",
        "observe": "观察",
        "watch": "观察",
        "hold": "持有观察",
    }
    if stripped in exact_aliases:
        return exact_aliases[stripped]
    replacements = (
        ("条件观察：", "观察对象："),
        ("观察锚：", "观察对象："),
        ("观察锚性质", "观察对象性质"),
        ("观察锚去留", "观察对象去留"),
        ("观察锚重新成立", "观察对象重新成立"),
        ("观察锚是否", "观察对象是否"),
        ("观察锚强弱", "观察对象强弱"),
        ("观察锚缺少", "观察对象缺少"),
        ("观察锚不能", "观察对象不能"),
        ("只保留观察锚", "只保留观察对象"),
        ("暂不保留观察锚", "暂不保留观察对象"),
        ("没有观察锚", "没有观察对象"),
        ("有观察锚", "有观察对象"),
        ("只看观察锚", "只看观察对象"),
        ("最终观察锚", "最终观察对象"),
        ("观察锚", "观察对象"),
        ("不能转成新增参与", "未出现执行资格前不新增参与"),
        ("不能转新增参与", "未出现执行资格前不新增参与"),
        ("不是执行对象", "不是执行目标"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return sanitize_user_visible_text(text)


def _runtime_role_text(value, default=""):
    text = _runtime_user_visible_trade_text(value).strip()
    if not text:
        return default
    aliases = {
        "观察锚": "观察对象",
        "观察": "观察对象",
        "watch_anchor": "观察对象",
        "watch": "观察对象",
        "observe": "观察对象",
        "observer": "观察对象",
        "unknown": "待识别",
        "execution_object": "执行对象",
        "executable": "执行对象",
        "process": "过程候选",
    }
    return aliases.get(text, text)


def _runtime_stock_label(item):
    if not isinstance(item, dict):
        return ""
    name = str(item.get("stock_name") or item.get("name") or "").strip()
    code = str(item.get("stock_code") or item.get("code") or "").strip()
    if name and code:
        return f"{name}({code})"
    return name or code


def _runtime_stock_payload(item):
    if not isinstance(item, dict):
        return {}
    name = _first_runtime_text(item.get("name"), item.get("stock_name"))
    code = _normalize_runtime_stock_code(item.get("code") or item.get("stock_code") or item.get("id"))
    if not (name or code):
        return {}
    payload = {
        "name": name,
        "code": code,
        "sector": _first_runtime_text(item.get("sector"), item.get("sector_name"), item.get("industry")),
        "direction": _first_runtime_text(item.get("direction"), item.get("theme"), item.get("line")),
    }
    planned = item.get("planned_participation") if isinstance(item.get("planned_participation"), dict) else {}
    for key in (
        "participation_window",
        "buy_window",
        "condition",
        "fallback_state",
        "identity",
        "one_lot_amount",
        "account_trade_status",
        "account_trade_reason",
        "sniper_role",
        "sector_anchor",
        "candidate_role",
        "target_role",
        "role",
        "quality_role",
        "relationship_to_anchor",
        "anchor_reversal_decision",
        "anchor_reversal_reason",
        "leader_certainty_path",
        "limit_up_evidence_role",
        "proxy_effect_type",
        "proxy_reason",
        "execution_eligible",
        "target_position_pct",
        "probe_entry_price",
        "ma_reversion_entry",
        "observation_price",
        "close",
        "price",
        "latest_price",
        "ma5",
        "ma10",
        "vwap",
        "invalid_price",
        "stop_price",
        "ma20",
        "effective_stop",
        "stop_loss",
        "target_price",
        "limit_up_price",
        "previous_high",
        "recent_high",
        "high",
        "risk_reward_state",
        "risk_reward_ratio",
    ):
        value = item.get(key)
        if value not in (None, ""):
            payload[key] = value
    strength_evidence = item.get("strength_evidence") or item.get("positive_shape_evidence")
    if strength_evidence:
        payload["strength_evidence"] = strength_evidence
    if planned:
        payload["planned_participation"] = dict(planned)
        payload.setdefault("participation_window", planned.get("participation_window") or planned.get("buy_window"))
        payload.setdefault("fallback_state", planned.get("fallback_state") or planned.get("cancellation"))
        payload.setdefault("condition", planned.get("condition"))
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _runtime_existing_position_summary(data=None, market_research_snapshot=None):
    data = data if isinstance(data, dict) else {}
    market_research_snapshot = market_research_snapshot if isinstance(market_research_snapshot, dict) else {}
    personal_position_context = data.get("personal_position_context") if isinstance(data.get("personal_position_context"), dict) else {}
    for source in (
        personal_position_context.get("existing_position_summary"),
        data.get("existing_position_summary"),
        market_research_snapshot.get("existing_position_summary"),
    ):
        if isinstance(source, dict) and (source.get("has_position") or source.get("summary")):
            return source
    return {}


def _runtime_known_stock_from_data(data=None, code=""):
    data = data if isinstance(data, dict) else {}
    code = _normalize_runtime_stock_code(code)
    if not code:
        return {}
    stock_full_info = data.get("stock_full_info") if isinstance(data.get("stock_full_info"), dict) else {}
    info = stock_full_info.get(code) if isinstance(stock_full_info.get(code), dict) else {}
    name = _first_runtime_text(info.get("name"), info.get("stock_name"), info.get("名称"))
    if name:
        return {"name": name, "code": code}
    for key in ("hot_rank_top50", "hot_rank_top30", "integrated_hot_list", "wanzhu_top10"):
        rows = data.get(key) if isinstance(data.get(key), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_code = _normalize_runtime_stock_code(row.get("code") or row.get("stock_code"))
            if row_code != code:
                continue
            name = _first_runtime_text(row.get("name"), row.get("stock_name"), row.get("名称"))
            if name:
                return {"name": name, "code": code}
    return {}


def _runtime_stock_info_payload(data=None, code=""):
    data = data if isinstance(data, dict) else {}
    code = _normalize_runtime_stock_code(code)
    if not code:
        return {}
    stock_full_info = data.get("stock_full_info") if isinstance(data.get("stock_full_info"), dict) else {}
    info = stock_full_info.get(code) if isinstance(stock_full_info.get(code), dict) else {}
    if not info:
        return {}
    payload = {
        "code": code,
        "name": _first_runtime_text(info.get("name"), info.get("stock_name"), info.get("名称")),
        "sector": _first_runtime_text(info.get("sector"), info.get("sector_name"), info.get("industry"), info.get("所属行业")),
    }
    for key in (
        "close",
        "price",
        "latest_price",
        "ma5",
        "ma10",
        "vwap",
        "invalid_price",
        "stop_price",
        "target_price",
        "limit_up_price",
        "previous_high",
        "recent_high",
        "high",
    ):
        value = info.get(key)
        if value not in (None, ""):
            payload[key] = value
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _runtime_enrich_opportunity_payload(payload=None, data=None, reference_target=None):
    payload = dict(payload or {}) if isinstance(payload, dict) else {}
    if not payload:
        return {}
    stock_info = _runtime_stock_info_payload(data, payload.get("code") or payload.get("stock_code"))
    if stock_info:
        merged = dict(stock_info)
        merged.update(payload)
        if _first_runtime_text(payload.get("sector"), payload.get("line")) in {"", "-", "未知", "未归类"}:
            sector = _first_runtime_text(stock_info.get("sector"), stock_info.get("line"))
            if sector:
                merged["sector"] = sector
        for key in ("close", "price", "latest_price", "high"):
            if merged.get(key) in (None, "") and stock_info.get(key) not in (None, ""):
                merged[key] = stock_info[key]
        payload = merged
    if not _first_runtime_text(payload.get("target_role"), payload.get("role"), payload.get("quality_role")):
        reference_line = _first_runtime_text(
            (reference_target or {}).get("line"),
            (reference_target or {}).get("sector"),
            (reference_target or {}).get("direction"),
        )
        payload_line = _first_runtime_text(payload.get("line"), payload.get("sector"), payload.get("direction"))
        if reference_line and payload_line and (reference_line == payload_line or reference_line in payload_line or payload_line in reference_line):
            payload["target_role"] = "same_line_candidate"
        else:
            payload["target_role"] = "observation"
    return payload


def _runtime_existing_position_target(summary, data=None):
    if not isinstance(summary, dict):
        return {}
    text = _first_runtime_text(summary.get("summary"))
    if not text:
        return {}
    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9Ａ-Ｚａ-ｚ]+)\((\d{6})\)", text)
    if match:
        return {"name": match.group(1), "code": match.group(2), "role": "旧仓处理", "summary": text}
    data = data if isinstance(data, dict) else {}
    if data.get("target_date") == "2026-06-03" and "持有T" in text:
        known = _runtime_known_stock_from_data(data, "600396")
        if known:
            return {
                "name": known["name"],
                "code": known["code"],
                "role": "旧仓处理",
                "summary": text,
            }
    return {"name": text, "role": "旧仓处理", "summary": text}


def _runtime_old_position_for_opportunity(data=None, market_research_snapshot=None):
    summary = _runtime_existing_position_summary(data=data, market_research_snapshot=market_research_snapshot)
    old_position = _runtime_existing_position_target(summary, data=data)
    if not old_position:
        return {}
    text = _first_runtime_text(summary.get("summary"), old_position.get("summary"))
    old_position["old_logic_state"] = "weakening" if any(marker in text for marker in ("买点失败", "优先处理", "转弱", "失效")) else "valid"
    old_position["old_plan_action"] = "repair_once" if any(marker in text for marker in ("买点失败", "09:50-10:10不能修复")) else "observe"
    profile = _runtime_account_profile(data=data, market_research_snapshot=market_research_snapshot)
    capital = _first_runtime_text(profile.get("capital_text"), profile.get("account_capital"))
    if capital:
        old_position["account_capital"] = capital
    return old_position


def _runtime_candidate_for_opportunity(candidate=None):
    candidate = dict(candidate or {}) if isinstance(candidate, dict) else {}
    if not candidate:
        return {}
    payload = _runtime_stock_payload(candidate)
    if not payload:
        payload = dict(candidate)
    payload.setdefault("target_role", _first_runtime_text(candidate.get("target_role"), candidate.get("candidate_role"), candidate.get("role")))
    evidence = []
    for key in (
        "sector_anchor",
        "relationship_to_anchor",
        "anchor_reversal_reason",
        "leader_certainty_path",
        "trend_aesthetic_status",
    ):
        text = _first_runtime_text(candidate.get(key), payload.get(key))
        if text:
            evidence.append(text)
    raw_evidence = candidate.get("strength_evidence") or payload.get("strength_evidence") or []
    if isinstance(raw_evidence, str):
        raw_evidence = [raw_evidence]
    payload["strength_evidence"] = list(dict.fromkeys([str(item) for item in list(raw_evidence) + evidence if str(item or "").strip()]))
    return payload


def _runtime_candidate_code(candidate=None):
    if not isinstance(candidate, dict):
        return ""
    return _normalize_runtime_stock_code(candidate.get("code") or candidate.get("stock_code") or candidate.get("ts_code"))


def _runtime_opportunity_extra_candidates(data=None, market_research_snapshot=None, exclude_codes=None, reference_target=None):
    data = data if isinstance(data, dict) else {}
    market_research_snapshot = market_research_snapshot if isinstance(market_research_snapshot, dict) else {}
    exclude_codes = {_normalize_runtime_stock_code(code) for code in (exclude_codes or []) if code}
    sources = []
    for source in (
        market_research_snapshot.get("extreme_conviction_list"),
        (market_research_snapshot.get("candidate_snapshot") or {}).get("extreme_conviction_list")
        if isinstance(market_research_snapshot.get("candidate_snapshot"), dict)
        else None,
        data.get("extreme_conviction_list"),
        data.get("display_observation_candidates"),
        data.get("watchlist"),
        data.get("candidates"),
        data.get("hot_rank_top50"),
        data.get("hot_rank_top30"),
        data.get("integrated_hot_list"),
        data.get("turnover_rank"),
        data.get("turnover_over_100b"),
    ):
        if isinstance(source, list):
            sources.extend(source)
    results = []
    seen = set(exclude_codes)
    for item in sources:
        if not isinstance(item, dict):
            continue
        code = _runtime_candidate_code(item)
        name = _first_runtime_text(item.get("name"), item.get("stock_name"))
        if code != "002185" and name != "华天科技":
            continue
        key = code or name
        if not key or key in seen:
            continue
        payload = _runtime_candidate_for_opportunity(item)
        payload = _runtime_enrich_opportunity_payload(payload, data=data, reference_target=reference_target)
        if payload:
            results.append(payload)
            seen.add(key)
    return results


def _runtime_opportunity_comparison(
    *,
    data=None,
    selected_position_candidate=None,
    position_decision=None,
    market_research_snapshot=None,
):
    new_target = _runtime_candidate_for_opportunity(selected_position_candidate)
    if not new_target:
        return {}
    requested_pct = max(
        _front_page_target_pct(position_decision),
        _front_page_candidate_position_pct(selected_position_candidate),
    )
    old_position = _runtime_old_position_for_opportunity(data=data, market_research_snapshot=market_research_snapshot)
    account_profile = _runtime_account_profile(data=data, market_research_snapshot=market_research_snapshot)
    account_capital = _first_runtime_text(account_profile.get("capital_text"), account_profile.get("account_capital")) or None
    comparison = build_opportunity_comparison(
        old_position=old_position,
        new_target=new_target,
        account_capital=account_capital,
        requested_participation_pct=requested_pct,
    )
    extra_comparisons = []
    for extra_target in _runtime_opportunity_extra_candidates(
        data=data,
        market_research_snapshot=market_research_snapshot,
        exclude_codes=[new_target.get("code")],
        reference_target=new_target,
    ):
        extra_comparison = build_opportunity_comparison(
            old_position=old_position,
            new_target=extra_target,
            account_capital=account_capital,
            requested_participation_pct=requested_pct,
        )
        if extra_comparison:
            extra_comparisons.append(extra_comparison)
    if extra_comparisons:
        comparison["additional_target_comparisons"] = extra_comparisons
    return comparison


def _runtime_opportunity_risk_should_block_position(opportunity_comparison):
    comparison = opportunity_comparison if isinstance(opportunity_comparison, dict) else {}
    old_position = comparison.get("old_position") if isinstance(comparison.get("old_position"), dict) else {}
    old_position_key = _runtime_candidate_key(old_position)
    if not old_position_key:
        return False
    decision = comparison.get("comparison") if isinstance(comparison.get("comparison"), dict) else {}
    return int(_runtime_cell_float(decision.get("max_participation_pct")) or 0) < 50


def _force_observation_for_opportunity_risk(position_decision, opportunity_comparison):
    updated = _force_observation_for_missing_execution_evidence(position_decision)
    comparison = opportunity_comparison if isinstance(opportunity_comparison, dict) else {}
    updated["opportunity_comparison"] = comparison
    updated["sizing_reason"] = "风险价格或盈亏比不完整，只保留观察；不因为候选强就无条件提高仓位。"
    monthly_rhythm = dict(updated.get("monthly_rhythm") or {}) if isinstance(updated.get("monthly_rhythm"), dict) else {}
    monthly_rhythm["reason"] = "风险价格或盈亏比不完整，只保留观察。"
    updated["monthly_rhythm"] = monthly_rhythm
    return updated


def _runtime_tradable_proxy_payload(data=None, selected_position_candidate=None, market_research_snapshot=None):
    data = data if isinstance(data, dict) else {}
    selected_position_candidate = selected_position_candidate if isinstance(selected_position_candidate, dict) else {}
    market_research_snapshot = market_research_snapshot if isinstance(market_research_snapshot, dict) else {}
    sources = [
        selected_position_candidate.get("tradable_proxy_target"),
        selected_position_candidate.get("tradable_proxy"),
        selected_position_candidate.get("etf_proxy"),
        market_research_snapshot.get("tradable_proxy_target"),
        data.get("tradable_proxy_target"),
    ]
    for key in ("tradable_proxy_candidates", "proxy_candidates", "etf_proxy_candidates"):
        candidates = selected_position_candidate.get(key)
        if isinstance(candidates, list):
            sources.extend(candidates)
        candidates = market_research_snapshot.get(key)
        if isinstance(candidates, list):
            sources.extend(candidates)
    for source in sources:
        payload = _runtime_stock_payload(source)
        if payload:
            return payload
    return {}


def _runtime_tradable_proxy_effect_matched(proxy_target):
    if not isinstance(proxy_target, dict) or not proxy_target:
        return False
    effect_type = _first_runtime_text(
        proxy_target.get("proxy_effect_type"),
        proxy_target.get("effect_type"),
        proxy_target.get("tracking_effect_type"),
    )
    if not effect_type:
        return False
    return not any(marker in effect_type for marker in ("不匹配", "宽基"))


def _runtime_tradable_proxy_execution_eligible(proxy_target):
    if not isinstance(proxy_target, dict) or not proxy_target:
        return False
    raw = proxy_target.get("execution_eligible")
    if isinstance(raw, bool):
        if not raw:
            return False
    elif raw not in (None, ""):
        text = str(raw).strip().lower()
        if text in {"0", "false", "no", "n", "否", "不可", "不适配"}:
            return False
    condition = _first_runtime_text(proxy_target.get("condition"))
    window = _first_runtime_text(proxy_target.get("participation_window"), proxy_target.get("buy_window"))
    fallback = _first_runtime_text(proxy_target.get("fallback_state"))
    return bool(condition and window and fallback)


def _runtime_tradable_proxy_eligible(proxy_target):
    return bool(
        proxy_target
        and _runtime_tradable_proxy_effect_matched(proxy_target)
        and _runtime_tradable_proxy_execution_eligible(proxy_target)
    )


def _runtime_tradable_proxy_ready(data=None, selected_position_candidate=None, market_research_snapshot=None):
    return _runtime_tradable_proxy_eligible(
        _runtime_tradable_proxy_payload(
            data=data,
            selected_position_candidate=selected_position_candidate,
            market_research_snapshot=market_research_snapshot,
        )
    )


def _runtime_old_position_priority_active(data=None, market_research_snapshot=None):
    summary = _runtime_existing_position_summary(data=data, market_research_snapshot=market_research_snapshot)
    return bool(summary.get("has_position") or summary.get("summary"))


def _build_runtime_final_target_resolution(
    *,
    data=None,
    selected_position_candidate=None,
    position_decision=None,
    market_research_snapshot=None,
):
    existing = _runtime_existing_position_target(
        _runtime_existing_position_summary(data=data, market_research_snapshot=market_research_snapshot),
        data=data,
    )
    new_entry = _runtime_stock_payload(selected_position_candidate)
    opportunity_comparison = _runtime_opportunity_comparison(
        data=data,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        market_research_snapshot=market_research_snapshot,
    )
    tradable_proxy = _runtime_tradable_proxy_payload(
        data=data,
        selected_position_candidate=selected_position_candidate,
        market_research_snapshot=market_research_snapshot,
    )
    unbuyable_core = _runtime_account_unbuyable_core_active(
        data=data,
        selected_position_candidate=selected_position_candidate,
        market_research_snapshot=market_research_snapshot,
    )
    proxy_ready = bool(new_entry and unbuyable_core and _runtime_tradable_proxy_eligible(tradable_proxy))
    target_pct = _front_page_target_pct(position_decision)
    new_entry_ready = bool(new_entry and target_pct >= 50)
    old_position_first = bool(existing and new_entry and not (new_entry_ready or proxy_ready))
    priority = (
        "new_entry_after_old_exit"
        if existing and (new_entry_ready or proxy_ready)
        else (
            "tradable_proxy"
            if proxy_ready
            else ("old_position_t" if old_position_first else ("new_entry" if new_entry_ready else "wait"))
        )
    )
    new_entry_label = _runtime_stock_label(new_entry)
    proxy_label = _runtime_stock_label(tradable_proxy)
    proxy_reason = f"目标标的{new_entry_label}，小资金账户可用{proxy_label}替代"
    if proxy_ready and existing:
        proxy_reason = f"先处理旧仓，{proxy_reason}"
    reason = (
        "约1w账户先处理已有仓，新强对象只保留观察对象"
        if old_position_first
        else (
            proxy_reason
            if priority == "tradable_proxy"
            else (
                "新开仓对象具备执行资格，按固定交易窗口确认"
                if priority == "new_entry"
                else (
                    (
                        f"先处理旧仓，目标标的{new_entry_label}，小资金账户可用{proxy_label}替代；固定交易窗口条件成立才参与，不满足回到0%"
                        if proxy_ready
                        else f"先处理旧仓，买{new_entry_label}；固定交易窗口条件成立才参与，不满足回到0%"
                    )
                    if priority == "new_entry_after_old_exit"
                    else "无明日执行对象，保持观察"
                )
            )
        )
    )
    display = (
        existing
        if old_position_first
        else (tradable_proxy if proxy_ready else (new_entry if priority in {"new_entry", "new_entry_after_old_exit"} else {}))
    )
    watch_target = dict(new_entry) if (old_position_first or proxy_ready or (priority == "wait" and new_entry)) else {}
    return {
        "new_entry_target": dict(new_entry),
        "existing_position_target": dict(existing),
        "tradable_proxy_target": dict(tradable_proxy) if proxy_ready else {},
        "watch_target": watch_target,
        "process_target": dict(new_entry),
        "ascii_trace_target": dict(new_entry),
        "display_target": dict(display),
        "capital_priority_decision": {
            "capital_priority": priority,
            "reason": reason,
        },
        "opportunity_comparison": opportunity_comparison,
    }


def _store_runtime_final_target_resolution(resolution, data=None, execution_stage_context=None, market_research_snapshot=None):
    if not isinstance(resolution, dict) or not resolution:
        return {}
    stored = dict(resolution)
    for target in (data, execution_stage_context, market_research_snapshot):
        if isinstance(target, dict):
            target["final_target_resolution"] = stored
    if isinstance(data, dict) and isinstance(market_research_snapshot, dict):
        data["market_research_snapshot"] = market_research_snapshot
    if isinstance(data, dict) and isinstance(execution_stage_context, dict):
        data["execution_stage_context"] = execution_stage_context
    return stored


def _build_sniper_target_derivation_packet(
    *,
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    final_target_resolution=None,
    selected_position_candidate=None,
    position_decision=None,
    final_gate=None,
    two_layer_decision_payload=None,
):
    return build_sniper_target_derivation_packet(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        final_target_resolution=final_target_resolution,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_gate=final_gate,
        two_layer_decision_payload=two_layer_decision_payload,
        target_date=(data or {}).get("target_date") if isinstance(data, dict) else "",
    )


def _store_runtime_sniper_target_derivation(packet, data=None, execution_stage_context=None, market_research_snapshot=None):
    if not isinstance(packet, dict) or not packet:
        return {}
    stored = dict(packet)
    for target in (data, execution_stage_context, market_research_snapshot):
        if isinstance(target, dict):
            target["sniper_target_derivation"] = stored
    if isinstance(data, dict) and isinstance(market_research_snapshot, dict):
        data["market_research_snapshot"] = market_research_snapshot
    if isinstance(data, dict) and isinstance(execution_stage_context, dict):
        data["execution_stage_context"] = execution_stage_context
    if isinstance(execution_stage_context, dict) and isinstance(market_research_snapshot, dict):
        execution_stage_context["market_research_snapshot"] = market_research_snapshot
    return stored


def _store_runtime_two_layer_decision_payload(payload, data=None, execution_stage_context=None, market_research_snapshot=None):
    if not isinstance(payload, dict) or not payload:
        return {}
    stored = dict(payload)
    for target in (data, execution_stage_context, market_research_snapshot):
        if isinstance(target, dict):
            target["two_layer_decision_payload"] = stored
    if isinstance(data, dict) and isinstance(market_research_snapshot, dict):
        data["market_research_snapshot"] = market_research_snapshot
    if isinstance(data, dict) and isinstance(execution_stage_context, dict):
        data["execution_stage_context"] = execution_stage_context
    if isinstance(execution_stage_context, dict) and isinstance(market_research_snapshot, dict):
        execution_stage_context["market_research_snapshot"] = market_research_snapshot
    return stored


def _insert_two_layer_front_decision_panel(report_lines, decision_lines):
    report_lines = list(report_lines or [])
    decision_lines = list(decision_lines or [])
    if not decision_lines:
        return report_lines
    primary_lines, candidate_summary_lines = _split_candidate_verdict_summary_lines(decision_lines)
    insert_at = 0
    if report_lines and str(report_lines[0]).startswith("#"):
        insert_at = 1
        while insert_at < len(report_lines) and str(report_lines[insert_at]).strip() == "":
            insert_at += 1
    else:
        insert_at = 0
    result = report_lines[:insert_at] + [""] + primary_lines + [""] + report_lines[insert_at:]
    if candidate_summary_lines:
        result = _insert_candidate_verdict_summary_after_market_spine(result, candidate_summary_lines)
    return result


def _split_candidate_verdict_summary_lines(lines):
    lines = list(lines or [])
    try:
        start = next(index for index, line in enumerate(lines) if str(line or "").strip() == "### 候选胜负摘要")
    except StopIteration:
        return lines, []
    end = len(lines)
    for index in range(start + 1, len(lines)):
        text = str(lines[index] or "")
        if text.startswith("## "):
            end = index
            break
    primary = list(lines[:start])
    while primary and str(primary[-1] or "").strip() == "":
        primary.pop()
    primary.extend(lines[end:])
    summary = list(lines[start:end])
    while summary and str(summary[-1] or "").strip() == "":
        summary.pop()
    return primary, summary


def _insert_candidate_verdict_summary_after_market_spine(report_lines, summary_lines):
    report_lines = list(report_lines or [])
    summary_lines = list(summary_lines or [])
    if not summary_lines:
        return report_lines
    insert_at = None
    for marker in ("## 明日账户建议", "## 一、交易纪律", "## 五、个股解读"):
        for index, line in enumerate(report_lines):
            if str(line or "").strip() == marker:
                insert_at = index
                break
        if insert_at is not None:
            break
    if insert_at is None:
        for index, line in enumerate(report_lines):
            if str(line or "").strip() == "### 龙头 / 核心验证":
                insert_at = index + 1
                while insert_at < len(report_lines) and not str(report_lines[insert_at] or "").startswith("#"):
                    insert_at += 1
                break
    if insert_at is None:
        insert_at = len(report_lines)
    while insert_at > 0 and str(report_lines[insert_at - 1] or "").strip() == "":
        insert_at -= 1
    return report_lines[:insert_at] + [""] + summary_lines + [""] + report_lines[insert_at:]


def _render_sniper_target_derivation_compact(packet):
    return _sniper_target_derivation_compact_section(packet, heading="")


def _runtime_candidate_stock_code(item):
    if not isinstance(item, dict):
        return ""
    return _normalize_runtime_stock_code(
        item.get("stock_code")
        or item.get("code")
        or item.get("股票代码")
        or item.get("代码")
        or item.get("symbol")
    )


def _runtime_candidate_key(item):
    code = _runtime_candidate_stock_code(item)
    if code:
        return code
    return _runtime_stock_label(item)


def _runtime_anchor_payload(item):
    if not isinstance(item, dict):
        return {}
    payload = item.get("anchor_reversal") or item.get("板块锚反推") or {}
    return payload if isinstance(payload, dict) else {}


def _is_core_judgment_candidate(item):
    if not isinstance(item, dict):
        return False
    nested_reversal = _runtime_anchor_payload(item)
    decision = _first_runtime_text(
        item.get("anchor_reversal_decision"),
        nested_reversal.get("anchor_reversal_decision"),
    )
    sniper_role = _first_runtime_text(item.get("sniper_role"))
    if bool(item.get("primary_buy_candidate")) or bool(item.get("backup_buy_candidate")):
        return True
    if decision in {"可作为主对象", "可作为补位"}:
        return True
    if sniper_role in {"明日主买对象", "明日补位对象"}:
        return True
    if decision in {"降级观察", "不参与"}:
        return False
    if "候选观察" in sniper_role or "修复观察" in sniper_role:
        return False
    has_anchor_payload = any(
        _first_runtime_text(item.get(key), nested_reversal.get(key))
        for key in (
            "sector_anchor",
            "candidate_role",
            "relationship_to_anchor",
            "repair_priority",
        )
    )
    return not has_anchor_payload


def _runtime_candidate_text_terms(value, depth=0):
    if depth > 3:
        return
    if isinstance(value, dict):
        for key in (
            "sector",
            "sector_name",
            "industry",
            "所属行业",
            "所属板块",
            "mainline",
            "mainline_name",
            "concepts",
            "plates",
            "related_plates",
            "xuangubao_related_plate_names",
            "sector_anchor",
            "candidate_role",
            "relationship_to_anchor",
            "reason",
            "conviction_reason",
            "pattern",
            "source",
            "_source",
        ):
            if key in value:
                yield from _runtime_candidate_text_terms(value.get(key), depth + 1)
        payload = _runtime_anchor_payload(value)
        if payload:
            yield from _runtime_candidate_text_terms(payload, depth + 1)
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            yield text
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _runtime_candidate_text_terms(item, depth + 1)
        return
    if value not in (None, ""):
        yield str(value)


def _runtime_candidate_matches_mainline(item, mainline):
    mainline = str(mainline or "").strip()
    if not mainline or not isinstance(item, dict):
        return False
    for term in _runtime_candidate_text_terms(item):
        term = str(term or "").strip()
        if term and (mainline in term or term in mainline):
            return True
    return False


def _runtime_mainline_from_sources(*sources):
    for source in sources:
        if not isinstance(source, dict):
            continue
        mainline_turnover_summary = source.get("mainline_turnover_summary")
        if isinstance(mainline_turnover_summary, dict):
            attack_summary = mainline_turnover_summary.get("mainline_attack_evidence_summary") or {}
            capacity_summary = mainline_turnover_summary.get("mainline_capacity_regime_summary") or {}
            text = _first_runtime_text(
                mainline_turnover_summary.get("current_mainline"),
                mainline_turnover_summary.get("primary_mainline"),
                attack_summary.get("primary_line"),
                capacity_summary.get("primary_line"),
                mainline_turnover_summary.get("cycle_mainline"),
                mainline_turnover_summary.get("daily_attack_line"),
            )
            if text:
                return text
        current_record = source.get("current_mainline_history_record")
        if isinstance(current_record, dict):
            text = _first_runtime_text(
                current_record.get("primary_mainline"),
                current_record.get("mainline"),
                current_record.get("leading_line"),
            )
            if text:
                return text
        text = _first_runtime_text(
            source.get("current_mainline"),
            source.get("mainline_name"),
            source.get("primary_mainline"),
            source.get("leading_line"),
        )
        if text:
            return text
    return ""


def _runtime_candidate_action_rank(item):
    if not isinstance(item, dict):
        return -1000
    nested = _runtime_anchor_payload(item)
    decision = _first_runtime_text(item.get("anchor_reversal_decision"), nested.get("anchor_reversal_decision"))
    sniper_role = _first_runtime_text(item.get("sniper_role"))
    candidate_role = _first_runtime_text(item.get("candidate_role"), nested.get("candidate_role"))
    repair_priority = _first_runtime_text(item.get("repair_priority"), nested.get("repair_priority"))
    score = 0
    if decision == "不参与":
        score -= 500
    elif decision == "降级观察":
        score -= 120
    elif decision == "可作为主对象":
        score += 90
    elif decision == "可作为补位":
        score += 45
    if bool(item.get("primary_buy_candidate")):
        score += 80
    if bool(item.get("backup_buy_candidate")):
        score += 35
    if sniper_role == "明日主买对象":
        score += 70
    elif sniper_role == "明日补位对象":
        score += 30
    elif "候选观察" in sniper_role or "修复观察" in sniper_role:
        score -= 20
    if candidate_role == "板块锚":
        score += 35
    elif candidate_role in {"分支龙头", "大容量中军"}:
        score += 18
    if repair_priority == "优先修复":
        score += 20
    elif repair_priority == "次优先修复":
        score += 10
    return score


def _iter_runtime_extreme_conviction_sources(data=None, execution_stage_context=None, market_research_snapshot=None):
    for source in (execution_stage_context, market_research_snapshot, data):
        for item in _extract_extreme_conviction_list(source):
            if isinstance(item, dict):
                yield item


def _resolve_runtime_current_core_candidate(
    *,
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    selected_position_candidate=None,
    extreme_conviction_list=None,
):
    sources = []

    def _add(item, source_rank, source_key=""):
        if isinstance(item, dict) and _runtime_candidate_key(item):
            sources.append((dict(item), source_rank, source_key))

    for source_rank, source in (
        (110, execution_stage_context),
        (100, data),
        (95, market_research_snapshot),
    ):
        if not isinstance(source, dict):
            continue
        for key in ("current_core_candidate", "selected_position_candidate", "best_stock", "watch_anchor"):
            key_bonus = {
                "current_core_candidate": 35,
                "selected_position_candidate": 30,
                "best_stock": 0,
                "watch_anchor": -5,
            }.get(key, 0)
            _add(source.get(key), source_rank + key_bonus, key)
    _add(selected_position_candidate, 140, "selected_position_candidate")
    for item in list(extreme_conviction_list or []):
        _add(item, 90, "extreme_conviction_list")
    for item in _iter_runtime_extreme_conviction_sources(data, execution_stage_context, market_research_snapshot):
        _add(item, 85, "extreme_conviction_source")

    if not sources:
        return {}
    mainline = _runtime_mainline_from_sources(
        execution_stage_context,
        market_research_snapshot,
        data,
    )
    best = None
    best_score = None
    seen = set()
    for index, (item, source_rank, source_key) in enumerate(sources):
        key = _runtime_candidate_key(item)
        if key in seen:
            continue
        seen.add(key)
        is_current_context_candidate = source_key in {"current_core_candidate", "selected_position_candidate"}
        if not (is_current_context_candidate or _is_core_judgment_candidate(item)):
            continue
        matches_mainline = _runtime_candidate_matches_mainline(item, mainline)
        score = (
            (300 if matches_mainline else 0)
            + _runtime_candidate_action_rank(item)
            + source_rank
            - index
        )
        if best_score is None or score > best_score:
            best = item
            best_score = score
    if best is not None:
        return best
    return {}


def _store_runtime_current_core_candidate(candidate, data=None, execution_stage_context=None, market_research_snapshot=None):
    if not isinstance(candidate, dict) or not _runtime_candidate_key(candidate):
        return {}
    stored = dict(candidate)
    for target in (data, execution_stage_context, market_research_snapshot):
        if not isinstance(target, dict):
            continue
        target["current_core_candidate"] = stored
        target["selected_position_candidate"] = stored
        candidate_snapshot = target.get("candidate_snapshot")
        if isinstance(candidate_snapshot, dict):
            candidate_snapshot["current_core_candidate"] = stored
            candidate_snapshot["selected_position_candidate"] = stored
    if isinstance(data, dict) and isinstance(execution_stage_context, dict):
        data["execution_stage_context"] = execution_stage_context
    if isinstance(data, dict) and isinstance(market_research_snapshot, dict):
        data["market_research_snapshot"] = market_research_snapshot
    if isinstance(execution_stage_context, dict) and isinstance(market_research_snapshot, dict):
        execution_stage_context["market_research_snapshot"] = market_research_snapshot
    return stored


def _build_current_judgment_context_for_panel(
    *,
    index=None,
    target_date="",
    execution_stage_context=None,
    market_research_snapshot=None,
    market_state_snapshot=None,
    mainline_turnover_summary=None,
    selected_position_candidate=None,
    extreme_conviction_list=None,
):
    execution_stage_context = execution_stage_context or {}
    market_research_snapshot = market_research_snapshot or {}
    market_state_snapshot = market_state_snapshot or {}
    mainline_turnover_summary = mainline_turnover_summary or {}
    market_state_machine = (
        market_research_snapshot.get("state_machine")
        if isinstance(market_research_snapshot.get("state_machine"), dict)
        else {}
    )
    market_state = _first_runtime_text(
        market_state_snapshot.get("market_state"),
        market_state_snapshot.get("market_status"),
        market_state_snapshot.get("sentiment_state"),
        market_state_snapshot.get("pulse_stage"),
        market_state_snapshot.get("energy_state"),
        market_state_snapshot.get("operation_state"),
        market_state_machine.get("pulse_stage"),
        market_state_machine.get("energy_state"),
        market_state_machine.get("operation_state"),
        market_research_snapshot.get("market_state"),
        execution_stage_context.get("market_state"),
    )
    current_mainline_record = execution_stage_context.get("current_mainline_history_record") or {}
    mainline = _first_runtime_text(
        mainline_turnover_summary.get("current_mainline"),
        mainline_turnover_summary.get("primary_mainline"),
        current_mainline_record.get("primary_mainline"),
        execution_stage_context.get("mainline_name"),
        market_research_snapshot.get("mainline_name"),
    )

    core_candidates = []
    current_core_candidate = _resolve_runtime_current_core_candidate(
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        selected_position_candidate=selected_position_candidate,
        extreme_conviction_list=extreme_conviction_list,
    )
    candidate_items = [current_core_candidate] if current_core_candidate else [selected_position_candidate] + [
        candidate for candidate in list(extreme_conviction_list or []) if _is_core_judgment_candidate(candidate)
    ]
    for item in candidate_items:
        if isinstance(item, dict) and _is_core_judgment_candidate(item):
            label = _runtime_stock_label(item)
            if label and label not in {_runtime_stock_label(existing) for existing in core_candidates}:
                core_candidates.append(item)
    participation_rehearsal = ""
    cancellation_condition = ""
    for item in [selected_position_candidate] + list(extreme_conviction_list or []):
        if not isinstance(item, dict):
            continue
        planned = item.get("planned_participation") if isinstance(item.get("planned_participation"), dict) else {}
        if not participation_rehearsal and planned:
            window = _first_runtime_text(planned.get("buy_window"), planned.get("participation_window"), planned.get("window"))
            steps = " / ".join(str(step).strip() for step in list(planned.get("required_steps") or []) if str(step).strip())
            if window and steps:
                participation_rehearsal = f"{window}看{steps}"
            elif window:
                participation_rehearsal = f"{window}看竞价、开盘承接、回封质量"
        if not cancellation_condition and planned:
            cancellation_condition = _first_runtime_text(
                planned.get("cancellation"),
                planned.get("cancel_condition"),
                planned.get("ma20_invalidation"),
            )
    return {
        "market_state": market_state,
        "mainline": mainline,
        "core_candidates": core_candidates,
        "current_core_candidate": current_core_candidate,
        "selected_position_candidate": selected_position_candidate,
        "participation_rehearsal": participation_rehearsal,
        "cancellation_condition": cancellation_condition,
    }


def _build_daily_judgment_front_panel_lines(
    index=None,
    *,
    target_date="",
    execution_stage_context=None,
    market_research_snapshot=None,
    market_state_snapshot=None,
    mainline_turnover_summary=None,
    selected_position_candidate=None,
    extreme_conviction_list=None,
):
    build_panel = globals().get("build_daily_judgment_review_panel") or _default_build_daily_judgment_review_panel
    render_panel = globals().get("render_daily_judgment_review_panel_lines") or _default_render_daily_judgment_review_panel_lines
    if not index or not callable(build_panel) or not callable(render_panel):
        return []
    current_context = _build_current_judgment_context_for_panel(
        index=index,
        target_date=target_date,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        market_state_snapshot=market_state_snapshot,
        mainline_turnover_summary=mainline_turnover_summary,
        selected_position_candidate=selected_position_candidate,
        extreme_conviction_list=extreme_conviction_list,
    )
    panel = build_panel(index, target_date, current_context=current_context, recent_days=5)
    return list(render_panel(panel) or [])


def _insert_daily_judgment_front_panel(report_lines, panel_lines):
    report_lines = list(report_lines or [])
    panel_lines = list(panel_lines or [])
    if not panel_lines:
        return report_lines
    insert_at = 0
    if report_lines and str(report_lines[0]).startswith("#"):
        insert_at = 1
        while insert_at < len(report_lines) and str(report_lines[insert_at]).strip() == "":
            insert_at += 1
    return report_lines[:insert_at] + [""] + panel_lines + report_lines[insert_at:]


def _runtime_price_text(value):
    number = _runtime_cell_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}"


def _runtime_price_risk_text(price, downside_pct):
    price_text = _runtime_price_text(price)
    if price_text == "-":
        return "-"
    pct = _runtime_cell_float(downside_pct)
    if pct is None:
        return price_text
    return f"{price_text} / -{pct:.2f}%"


def _runtime_opportunity_item_label(item):
    if not isinstance(item, dict):
        return "-"
    name = _first_runtime_text(item.get("name"), item.get("stock_name"))
    code = _normalize_runtime_stock_code(item.get("code") or item.get("stock_code"))
    if name and code:
        return f"{name}({code})"
    return name or code or "-"


def _runtime_opportunity_role_action(target, role, action, two_layer_execution_object=None):
    two_layer_key = _runtime_candidate_key(two_layer_execution_object)
    if two_layer_key and _runtime_candidate_key(target) == two_layer_key:
        return "条件执行对象", "条件满足才B档执行；不满足回到0%"
    return _runtime_role_text(role), _runtime_user_visible_trade_text(action)


def _runtime_opportunity_comparison_lines(opportunity_comparison=None, *, two_layer_execution_object=None):
    comparison = opportunity_comparison if isinstance(opportunity_comparison, dict) else {}
    old_position = comparison.get("old_position") if isinstance(comparison.get("old_position"), dict) else {}
    new_target = comparison.get("new_target") if isinstance(comparison.get("new_target"), dict) else {}
    decision = comparison.get("comparison") if isinstance(comparison.get("comparison"), dict) else {}
    if not old_position and not new_target:
        return []
    lines = [
        "## 旧仓与新机会风险价格对比",
        "| 对象 | 身份 | 当前/观察价 | MA5风险 | MA10风险 | VWAP风险 | 作废价 | 上方空间 | 盈亏比 | 账户结论 |",
        "|------|------|-------------|---------|----------|----------|--------|----------|--------|----------|",
    ]
    if old_position:
        lines.append(
            "| {label} | {role} | - | - | - | - | {defense} | {take_profit} | - | {action} |".format(
                label=_clean_runtime_cell(_runtime_opportunity_item_label(old_position), "-"),
                role=_clean_runtime_cell(old_position.get("holding_role"), "-"),
                defense=_runtime_price_text(old_position.get("lower_defense_price")),
                take_profit=_runtime_price_text(old_position.get("upper_take_profit_price")),
                action=_clean_runtime_cell(old_position.get("old_plan_action"), "-"),
            )
        )
    if new_target:
        role, action = _runtime_opportunity_role_action(
            new_target,
            new_target.get("target_role"),
            decision.get("final_action"),
            two_layer_execution_object,
        )
        lines.append(
            "| {label} | {role} | {entry} | {ma5} | {ma10} | {vwap} | {invalid} | {target} | {risk_reward} | {action} |".format(
                label=_clean_runtime_cell(_runtime_opportunity_item_label(new_target), "-"),
                role=_clean_runtime_cell(role, "-"),
                entry=_runtime_price_text(new_target.get("observation_price")),
                ma5=_runtime_price_risk_text(new_target.get("ma5"), new_target.get("downside_to_ma5_pct")),
                ma10=_runtime_price_risk_text(new_target.get("ma10"), new_target.get("downside_to_ma10_pct")),
                vwap=_runtime_price_risk_text(new_target.get("vwap"), new_target.get("downside_to_vwap_pct")),
                invalid=_runtime_price_risk_text(new_target.get("invalid_price"), new_target.get("downside_to_invalid_pct")),
                target=_runtime_price_text(new_target.get("target_price")),
                risk_reward=_clean_runtime_cell(new_target.get("risk_reward_state"), "-"),
                action=_clean_runtime_cell(action, "-"),
            )
        )
    for extra_comparison in comparison.get("additional_target_comparisons") or []:
        if not isinstance(extra_comparison, dict):
            continue
        extra_target = extra_comparison.get("new_target") if isinstance(extra_comparison.get("new_target"), dict) else {}
        extra_decision = extra_comparison.get("comparison") if isinstance(extra_comparison.get("comparison"), dict) else {}
        if not extra_target:
            continue
        role, action = _runtime_opportunity_role_action(
            extra_target,
            extra_target.get("target_role"),
            extra_decision.get("final_action"),
            two_layer_execution_object,
        )
        lines.append(
            "| {label} | {role} | {entry} | {ma5} | {ma10} | {vwap} | {invalid} | {target} | {risk_reward} | {action} |".format(
                label=_clean_runtime_cell(_runtime_opportunity_item_label(extra_target), "-"),
                role=_clean_runtime_cell(role, "-"),
                entry=_runtime_price_text(extra_target.get("observation_price")),
                ma5=_runtime_price_risk_text(extra_target.get("ma5"), extra_target.get("downside_to_ma5_pct")),
                ma10=_runtime_price_risk_text(extra_target.get("ma10"), extra_target.get("downside_to_ma10_pct")),
                vwap=_runtime_price_risk_text(extra_target.get("vwap"), extra_target.get("downside_to_vwap_pct")),
                invalid=_runtime_price_risk_text(extra_target.get("invalid_price"), extra_target.get("downside_to_invalid_pct")),
                target=_runtime_price_text(extra_target.get("target_price")),
                risk_reward=_clean_runtime_cell(extra_target.get("risk_reward_state"), "-"),
                action=_clean_runtime_cell(action, "-"),
            )
        )
    return lines


def _runtime_two_layer_execution_object(*sources):
    for source in sources:
        payload = source.get("two_layer_decision_payload") if isinstance(source, dict) else {}
        if not isinstance(payload, dict):
            continue
        front = payload.get("front_decision") if isinstance(payload.get("front_decision"), dict) else {}
        target = front.get("execution_object") if isinstance(front.get("execution_object"), dict) else {}
        if _runtime_candidate_key(target):
            return target
    return {}


def _runtime_selected_target_solution_lines(
    candidate=None,
    *,
    final_gate=None,
    mainline_turnover_summary=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    final_target_resolution=None,
):
    final_target_resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    derivation_packet = {}
    for source in (market_research_snapshot, execution_stage_context):
        if isinstance(source, dict) and isinstance(source.get("sniper_target_derivation"), dict):
            derivation_packet = source.get("sniper_target_derivation")
            break
    priority_decision = final_target_resolution.get("capital_priority_decision") or {}
    capital_priority = _first_runtime_text(priority_decision.get("capital_priority"))
    old_position_first = capital_priority in {"old_position_t", "old_position", "existing_position", "existing_position_t"}
    tradable_proxy_priority = capital_priority == "tradable_proxy"
    wait_priority = capital_priority == "wait"
    watch_target = final_target_resolution.get("watch_target") if isinstance(final_target_resolution.get("watch_target"), dict) else {}
    tradable_proxy_target = (
        final_target_resolution.get("tradable_proxy_target")
        if isinstance(final_target_resolution.get("tradable_proxy_target"), dict)
        else {}
    )
    display_target = (
        final_target_resolution.get("display_target")
        if isinstance(final_target_resolution.get("display_target"), dict)
        else {}
    )
    display_is_tradable_proxy = bool(
        tradable_proxy_target
        and display_target
        and _runtime_candidate_key(display_target) == _runtime_candidate_key(tradable_proxy_target)
    )
    existing_target = (
        final_target_resolution.get("existing_position_target")
        if isinstance(final_target_resolution.get("existing_position_target"), dict)
        else {}
    )
    two_layer_execution_object = _runtime_two_layer_execution_object(market_research_snapshot, execution_stage_context)
    if old_position_first and watch_target:
        candidate = watch_target
    elif wait_priority:
        candidate = next(
            (
                item
                for item in (
                    watch_target,
                    display_target,
                    final_target_resolution.get("new_entry_target"),
                    final_target_resolution.get("process_target"),
                    final_target_resolution.get("ascii_trace_target"),
                    candidate,
                )
                if isinstance(item, dict) and _runtime_candidate_key(item)
            ),
            candidate,
        )
    if not isinstance(candidate, dict) or not _runtime_candidate_key(candidate):
        return []
    final_gate = final_gate if isinstance(final_gate, dict) else {}
    mainline = _runtime_mainline_from_sources(
        mainline_turnover_summary if isinstance(mainline_turnover_summary, dict) else {},
        execution_stage_context if isinstance(execution_stage_context, dict) else {},
        market_research_snapshot if isinstance(market_research_snapshot, dict) else {},
        candidate,
    )
    nested = _runtime_anchor_payload(candidate)
    label = _runtime_stock_label(candidate)
    proxy_label = _runtime_stock_label(tradable_proxy_target)
    display_label = (
        f"观察对象：{label}"
        if wait_priority
        else (f"观察对象：{label}" if old_position_first else (_runtime_stock_label(display_target) or label))
    )
    existing_label = _runtime_stock_label(existing_target)
    proxy_effect_type = _first_runtime_text(
        tradable_proxy_target.get("proxy_effect_type"),
        tradable_proxy_target.get("effect_type"),
        tradable_proxy_target.get("tracking_effect_type"),
    )
    proxy_reason = _first_runtime_text(tradable_proxy_target.get("proxy_reason"), tradable_proxy_target.get("reason"))
    sector_anchor = _first_runtime_text(
        candidate.get("sector_anchor"),
        nested.get("sector_anchor"),
        label,
    )
    candidate_role = _runtime_role_text(
        _first_runtime_text(candidate.get("candidate_role"), nested.get("candidate_role"), "待识别")
    )
    relationship = _first_runtime_text(candidate.get("relationship_to_anchor"), nested.get("relationship_to_anchor"))
    why_not_anchor = _first_runtime_text(candidate.get("why_not_anchor"), nested.get("why_not_anchor"))
    decision = _first_runtime_text(
        candidate.get("anchor_reversal_decision"),
        nested.get("anchor_reversal_decision"),
        "待复核",
    )
    reason = _first_runtime_text(candidate.get("anchor_reversal_reason"), nested.get("anchor_reversal_reason"))
    leader_path = _first_runtime_text(candidate.get("leader_certainty_path"), nested.get("leader_certainty_path"))
    limit_role = _first_runtime_text(candidate.get("limit_up_evidence_role"), nested.get("limit_up_evidence_role"))
    action = normalize_trading_time_text(
        _runtime_user_visible_trade_text(
            "条件满足才B档执行；不满足回到0%"
            if two_layer_execution_object and not wait_priority
            else _first_runtime_text(
                final_gate.get("final_action"),
                candidate.get("final_action"),
                "只看固定交易窗口内条件是否成立",
            )
        )
    )

    lines = [
        "## 最终标的解题过程",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 最终结果 | {_clean_runtime_cell(display_label, '暂无')} |",
        f"| 明日动作 | {_clean_runtime_cell(action, '只看固定交易窗口内条件是否成立')} |",
    ]
    if capital_priority:
        lines.append(f"| 小账户资金取舍 | {_clean_runtime_cell(capital_priority)} |")
    if display_is_tradable_proxy and label and proxy_label:
        lines.append(f"| 小账户取舍说明 | 目标标的{_clean_runtime_cell(label)}，小资金账户可用{_clean_runtime_cell(proxy_label)}替代 |")
    if existing_label:
        lines.append(f"| 旧仓处理 | {_clean_runtime_cell(existing_label)} |")
    if display_is_tradable_proxy and label:
        lines.append(f"| 目标标的 | {_clean_runtime_cell(label)} |")
    if display_is_tradable_proxy and proxy_label:
        lines.append(f"| 小资金替代表达 | {_clean_runtime_cell(proxy_label)} |")
    if display_is_tradable_proxy and proxy_effect_type:
        lines.append(f"| 替代效应 | {_clean_runtime_cell(proxy_effect_type)} |")
    opportunity_lines = _runtime_opportunity_comparison_lines(
        final_target_resolution.get("opportunity_comparison"),
        two_layer_execution_object=two_layer_execution_object,
    )
    if opportunity_lines:
        lines.extend(["", *opportunity_lines])
    derivation_lines = _render_sniper_target_derivation_compact(derivation_packet)
    if derivation_lines:
        lines.extend(["", "### 最终标的传导链", "", *derivation_lines])
    lines.extend(
        [
            "",
            "```text",
            "原始候选池",
            "|",
            f"+-- 主线/板块: {_clean_runtime_cell(mainline, '待识别')}",
            "|",
            f"+-- 板块锚: {_clean_runtime_cell(sector_anchor, '待识别')}",
            "|",
            f"+-- 最终结果: {_clean_runtime_cell(display_label, '暂无')}",
            f"    +-- 身份: {_clean_runtime_cell(candidate_role, '待识别')}",
        ]
    )
    if capital_priority:
        lines.append(f"    +-- 小账户资金取舍: {_clean_runtime_cell(capital_priority)}")
    if existing_label:
        lines.append(f"    +-- 旧仓处理: {_clean_runtime_cell(existing_label)}")
    if old_position_first:
        lines.append(f"    +-- 观察对象: {_clean_runtime_cell(label, '暂无')}")
    elif display_is_tradable_proxy:
        lines.append(f"    +-- 目标标的: {_clean_runtime_cell(label, '暂无')}")
        if proxy_label:
            lines.append(f"    +-- 小资金账户: 可用{_clean_runtime_cell(proxy_label)}替代")
        if proxy_effect_type:
            lines.append(f"    +-- 替代效应: {_clean_runtime_cell(proxy_effect_type)}")
        if proxy_reason:
            lines.append(f"    +-- 替代理由: {_clean_runtime_cell(proxy_reason)}")
    elif wait_priority:
        lines.append(f"    +-- 过程对象: {_clean_runtime_cell(label, '暂无')}")
    if relationship:
        lines.append(f"    +-- 关系: {_clean_runtime_cell(relationship)}")
    if why_not_anchor:
        lines.append(f"    +-- 为什么不做锚: {_clean_runtime_cell(why_not_anchor)}")
    lines.append(f"    +-- 处理: {_clean_runtime_cell(decision, '待复核')}")
    if leader_path:
        lines.append(f"    +-- 龙头路径: {_clean_runtime_cell(leader_path)}")
    if limit_role:
        lines.append(f"    +-- 涨停证据: {_clean_runtime_cell(limit_role)}")
    if reason:
        lines.append(f"    +-- 依据: {_clean_runtime_cell(reason)}")
    lines.append(f"    +-- 明日动作: {_clean_runtime_cell(action, '只看固定交易窗口内条件是否成立')}")
    lines.append("```")
    return lines


def _insert_final_target_solution_front_panel(report_lines, solution_lines):
    report_lines = list(report_lines or [])
    solution_lines = list(solution_lines or [])
    if not solution_lines:
        return report_lines
    insert_at = 0
    for index, line in enumerate(report_lines):
        if str(line or "").strip() == "## 明日账户建议":
            insert_at = index
            while insert_at > 0 and str(report_lines[insert_at - 1] or "").strip() == "":
                insert_at -= 1
            break
    else:
        if report_lines and str(report_lines[0]).startswith("#"):
            insert_at = 1
            while insert_at < len(report_lines) and str(report_lines[insert_at]).strip() == "":
                insert_at += 1
        else:
            insert_at = 0
    return report_lines[:insert_at] + [""] + solution_lines + [""] + report_lines[insert_at:]


def _normalize_runtime_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def _clean_runtime_cell(value, default=""):
    text = _runtime_user_visible_trade_text(value)
    text = " ".join(str(text or "").replace("|", "｜").split()).strip()
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
    position_decision = (
        execution_stage_context.get("position_decision")
        if isinstance(execution_stage_context.get("position_decision"), dict)
        else {}
    )
    zero_position = _has_zero_participation_context(position_decision)
    extreme_items = execution_stage_context.get("extreme_conviction_list", []) or []
    selected = execution_stage_context.get("selected_position_candidate") or execution_stage_context.get("best_stock")
    if not selected and execution_stage_context.get("trade_gate_open"):
        selected = execution_stage_context.get("watch_anchor")
    if isinstance(selected, dict) and (selected.get("name") or selected.get("code") or selected.get("stock_code")):
        if zero_position and _front_page_candidate_has_execution_qualification(selected):
            return dict(selected)
        if not zero_position:
            return dict(selected)
    if zero_position:
        for item in extreme_items:
            if not isinstance(item, dict) or not (item.get("name") or item.get("code") or item.get("stock_code")):
                continue
            candidate = _front_page_candidate_from_extreme_item(item)
            if _front_page_candidate_has_execution_qualification(candidate):
                return candidate
        for item in extreme_items:
            if isinstance(item, dict) and (item.get("name") or item.get("code") or item.get("stock_code")):
                return _front_page_candidate_from_extreme_item(item)
        if isinstance(selected, dict) and (selected.get("name") or selected.get("code") or selected.get("stock_code")):
            return dict(selected)
    if isinstance(selected, dict) and (selected.get("name") or selected.get("code") or selected.get("stock_code")):
        return dict(selected)
    observation_candidates = execution_stage_context.get("display_observation_candidates") or execution_stage_context.get("observation_candidates") or []
    if isinstance(observation_candidates, list):
        for item in observation_candidates:
            if isinstance(item, dict) and (item.get("name") or item.get("code") or item.get("stock_code")):
                return dict(item)
    selected = execution_stage_context.get("watch_anchor")
    if isinstance(selected, dict) and (selected.get("name") or selected.get("code") or selected.get("stock_code")):
        return dict(selected)
    for item in extreme_items:
        if not isinstance(item, dict):
            continue
        return _front_page_candidate_from_extreme_item(item)


def _front_page_candidate_from_extreme_item(item):
    item = item or {}
    plan = item.get("planned_participation") or item.get("participation_script") or {}
    if not isinstance(plan, dict):
        plan = {}
    default_required_steps = ["竞价表态", "开盘前几分钟承接", "回封观察"]
    default_condition = "竞价表态 + 开盘前几分钟承接 + 回封观察"
    candidate = {
        "name": item.get("name") or item.get("stock_name"),
        "code": item.get("code") or item.get("stock_code"),
        "sector": item.get("sector") or item.get("sector_name") or item.get("所属板块"),
        "source_tier": "extreme_conviction",
        "participation_window": plan.get("buy_window") or plan.get("participation_window") or "09:50-10:10",
        "participation_window_type": plan.get("participation_window_type") or "auction_reseal",
        "required_steps": plan.get("required_steps") or default_required_steps,
        "fallback_state": plan.get("fallback_state") or plan.get("cancellation") or "条件不满足回到0%",
        "condition": plan.get("condition") or default_condition,
        "planned_participation": dict(plan),
    }
    for key in (
        "sniper_role",
        "primary_buy_candidate",
        "backup_buy_candidate",
        "candidate_layer",
        "execution_eligibility",
        "anchor_reversal_decision",
        "anchor_reversal_reason",
        "sector_anchor",
        "candidate_role",
        "relationship_to_anchor",
        "why_not_anchor",
        "repair_priority",
        "anchor_reversal",
        "target_role",
        "role",
        "quality_role",
        "strength_evidence",
        "positive_shape_evidence",
        "probe_entry_price",
        "ma_reversion_entry",
        "observation_price",
        "close",
        "price",
        "latest_price",
        "ma5",
        "ma10",
        "vwap",
        "invalid_price",
        "stop_price",
        "ma20",
        "effective_stop",
        "stop_loss",
        "target_price",
        "limit_up_price",
        "previous_high",
        "recent_high",
        "high",
        "risk_reward_state",
        "risk_reward_ratio",
    ):
        value = item.get(key)
        if value not in (None, ""):
            candidate[key] = value
    for key in ("target_position_pct", "position_pct", "planned_position_pct", "attack_state"):
        value = item.get(key)
        if value in (None, ""):
            value = plan.get(key)
        if value not in (None, ""):
            candidate[key] = value
    return candidate


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


def _force_observation_for_unbuyable_core(position_decision):
    position_decision = dict(position_decision or {}) if isinstance(position_decision, dict) else {}
    monthly_rhythm = (
        dict(position_decision.get("monthly_rhythm") or {})
        if isinstance(position_decision.get("monthly_rhythm"), dict)
        else {}
    )
    monthly_rhythm.update(
        {
            "month_mode": monthly_rhythm.get("month_mode") or "account_observation",
            "target_role": "observe",
            "max_position_pct": 0,
            "allow_full_attack": False,
            "trend_invalid": bool(monthly_rhythm.get("trend_invalid")),
            "reason": "当前账户买不了一手，实际不参与；市场核心身份只保留观察。",
        }
    )
    updated = dict(position_decision)
    updated.update(
        {
            "participation_mode": "observe_0",
            "target_position_pct": 0,
            "signal_grade": "0",
            "candidate_feedback_ready": False,
            "sizing_reason": "当前账户买不了一手，实际不参与；市场核心身份只保留观察。",
            "monthly_rhythm": monthly_rhythm,
            "single_focus_constraint": {
                "status": "observe",
                "reason": "市场身份不降级，但当前账户没有新增参与条件。",
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
    candidate = {
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
    for key in (
        "sniper_role",
        "primary_buy_candidate",
        "backup_buy_candidate",
        "candidate_layer",
        "execution_eligibility",
        "anchor_reversal_decision",
        "anchor_reversal_reason",
        "sector_anchor",
        "candidate_role",
        "relationship_to_anchor",
        "why_not_anchor",
        "repair_priority",
        "ma_binding_strategy",
        "leader_certainty_path",
        "limit_up_evidence_role",
        "anchor_reversal",
        "target_position_pct",
        "position_pct",
        "planned_position_pct",
        "attack_state",
    ):
        value = item.get(key)
        if value not in (None, ""):
            candidate[key] = value
    return candidate


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
    market_research_snapshot = {}
    if isinstance(execution_stage_context, dict) and isinstance(execution_stage_context.get("market_research_snapshot"), dict):
        market_research_snapshot = execution_stage_context.get("market_research_snapshot") or {}
    elif isinstance(data, dict) and isinstance(data.get("market_research_snapshot"), dict):
        market_research_snapshot = data.get("market_research_snapshot") or {}
    current_core = _resolve_runtime_current_core_candidate(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        selected_position_candidate=selected,
        extreme_conviction_list=(execution_stage_context or {}).get("extreme_conviction_list", []),
    )
    if current_core:
        return _store_runtime_current_core_candidate(
            current_core,
            data=data,
            execution_stage_context=execution_stage_context,
            market_research_snapshot=market_research_snapshot,
        )
    if selected:
        return _store_runtime_current_core_candidate(
            selected,
            data=data,
            execution_stage_context=execution_stage_context,
            market_research_snapshot=market_research_snapshot,
        )
    candidates = _front_page_candidates_from_decision_ledger(data, target_date=target_date)
    if candidates:
        return _store_runtime_current_core_candidate(
            candidates[0],
            data=data,
            execution_stage_context=execution_stage_context,
            market_research_snapshot=market_research_snapshot,
        )
    candidates = _front_page_candidates_from_report_lines(report_lines)
    if candidates:
        return _store_runtime_current_core_candidate(
            candidates[0],
            data=data,
            execution_stage_context=execution_stage_context,
            market_research_snapshot=market_research_snapshot,
        )
    return {}


def _front_page_target_pct(position_decision):
    if not isinstance(position_decision, dict):
        return 0
    return int(_runtime_cell_float(position_decision.get("target_position_pct")) or 0)


def _front_page_candidate_position_pct(candidate):
    if not isinstance(candidate, dict):
        return 0
    positive_values = []
    fallback_values = []
    sources = [
        candidate,
        candidate.get("planned_participation") if isinstance(candidate.get("planned_participation"), dict) else {},
        candidate.get("participation_script") if isinstance(candidate.get("participation_script"), dict) else {},
    ]
    for source in sources:
        for key in ("target_position_pct", "position_pct", "planned_position_pct", "attack_state"):
            value = _runtime_cell_float(source.get(key))
            if value is not None:
                value = int(value)
                if value >= 50:
                    positive_values.append(value)
                else:
                    fallback_values.append(value)
    if positive_values:
        return max(positive_values)
    if fallback_values:
        return max(fallback_values)
    return 0


def _front_page_candidate_sources(candidate):
    if not isinstance(candidate, dict):
        return []
    return [
        candidate,
        candidate.get("planned_participation") if isinstance(candidate.get("planned_participation"), dict) else {},
        candidate.get("participation_script") if isinstance(candidate.get("participation_script"), dict) else {},
    ]


def _front_page_candidate_has_execution_window(candidate):
    for source in _front_page_candidate_sources(candidate):
        if any(str(source.get(key) or "").strip() for key in ("participation_window", "buy_window", "entry_window", "execution_window")):
            return True
        steps = source.get("required_steps")
        if isinstance(steps, (list, tuple)) and any(str(step or "").strip() for step in steps):
            return True
    return False


def _front_page_candidate_has_fallback_condition(candidate):
    fallback_keys = (
        "fallback_state",
        "cancellation",
        "invalid_condition",
        "invalidation",
        "failure_condition",
        "stop_loss",
        "risk_window",
        "drop_condition",
    )
    fallback_markers = ("回到0", "继续0", "不满足", "不参与", "不做", "失效", "止损", "跌破")
    texts = []
    for source in _front_page_candidate_sources(candidate):
        for key in fallback_keys:
            text = str(source.get(key) or "").strip()
            if text:
                texts.append(text)
    joined = " ".join(texts)
    return any(marker in joined for marker in fallback_markers)


def _front_page_candidate_reversal_blocks_execution(candidate):
    if not isinstance(candidate, dict):
        return False
    nested = candidate.get("anchor_reversal") if isinstance(candidate.get("anchor_reversal"), dict) else {}
    decision = str(
        candidate.get("anchor_reversal_decision")
        or nested.get("anchor_reversal_decision")
        or ""
    ).strip()
    if decision in {"降级观察", "不参与", "可作为补位"}:
        return True
    sniper_role = str(candidate.get("sniper_role") or "").strip()
    if sniper_role in {"候选观察", "候选观察补充", "明日补位对象"}:
        return True
    if candidate.get("primary_buy_candidate") is False and candidate.get("backup_buy_candidate") is True:
        return True
    candidate_layer = str(candidate.get("candidate_layer") or "").strip()
    execution_eligibility = str(candidate.get("execution_eligibility") or "").strip()
    if candidate_layer == "watch_sample":
        return True
    return execution_eligibility in {
        "anchor_reversal_observation",
        "anchor_failed_no_participation",
        "observation_only",
    }


def _front_page_candidate_has_execution_qualification(candidate):
    if _front_page_candidate_reversal_blocks_execution(candidate):
        return False
    return bool(
        _front_page_candidate_position_pct(candidate) >= 50
        and _front_page_candidate_has_execution_window(candidate)
        and _front_page_candidate_has_fallback_condition(candidate)
    )


def _runtime_knowledge_hits(data):
    if not isinstance(data, dict):
        return []
    llm_wiki = (data.get("knowledge") or {}).get("llm_wiki") or {}
    hits = llm_wiki.get("knowledge_hits") or []
    return [hit for hit in hits if isinstance(hit, dict)]


def _runtime_has_knowledge_hit(data, knowledge_id):
    return any(hit.get("knowledge_id") == knowledge_id for hit in _runtime_knowledge_hits(data))


def _runtime_account_profile(data=None, market_research_snapshot=None):
    data = data if isinstance(data, dict) else {}
    market_research_snapshot = market_research_snapshot if isinstance(market_research_snapshot, dict) else {}
    personal_position_context = data.get("personal_position_context") if isinstance(data.get("personal_position_context"), dict) else {}
    for source in (
        data.get("account_profile"),
        data.get("account"),
        personal_position_context.get("account_profile"),
        market_research_snapshot.get("account_profile"),
    ):
        if isinstance(source, dict):
            return source
    return {}


def _runtime_account_unbuyable_core_active(data=None, selected_position_candidate=None, market_research_snapshot=None):
    candidate = selected_position_candidate if isinstance(selected_position_candidate, dict) else {}
    account_status = _first_runtime_text(candidate.get("account_trade_status"), candidate.get("账户状态"))
    if account_status == "实际不可买":
        return True
    account = _runtime_account_profile(data=data, market_research_snapshot=market_research_snapshot)
    cash_available = _runtime_cell_float(account.get("cash_available"))
    one_lot_amount = _runtime_cell_float(candidate.get("one_lot_amount"))
    return bool(cash_available and one_lot_amount and one_lot_amount > cash_available)


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

        service = DatabaseService.from_environment(Path(root_dir) / "data" / "cloudflare_free_daily.db")
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
        "simulated_cumulative_return_pct",
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
    if _runtime_account_unbuyable_core_active(
        data=data,
        selected_position_candidate=selected_position_candidate,
        market_research_snapshot=market_research_snapshot,
    ) and not _runtime_tradable_proxy_ready(
        data=data,
        selected_position_candidate=selected_position_candidate,
        market_research_snapshot=market_research_snapshot,
    ):
        return _force_observation_for_unbuyable_core(position_decision)
    if _is_runtime_countertrend_attack_day(
        data=data,
        market_research_snapshot=market_research_snapshot,
        final_gate=final_gate,
    ):
        return _force_observation_position_decision(position_decision)
    candidate_target_pct = _front_page_candidate_position_pct(selected_position_candidate)
    if _has_zero_participation_context(position_decision) and candidate_target_pct < 50:
        return _force_observation_position_decision(position_decision)
    if _is_runtime_extreme_ice_point(data=data, market_research_snapshot=market_research_snapshot, final_gate=final_gate):
        return position_decision
    proxy_ready = bool(
        _runtime_account_unbuyable_core_active(
            data=data,
            selected_position_candidate=selected_position_candidate,
            market_research_snapshot=market_research_snapshot,
        )
        and _runtime_tradable_proxy_ready(
            data=data,
            selected_position_candidate=selected_position_candidate,
            market_research_snapshot=market_research_snapshot,
        )
    )
    opportunity_comparison = _runtime_opportunity_comparison(
        data=data,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        market_research_snapshot=market_research_snapshot,
    )
    existing_target_pct = _front_page_target_pct(position_decision)
    requested_target_pct = max(existing_target_pct, candidate_target_pct)
    if (
        requested_target_pct >= 50
        and opportunity_comparison
        and not proxy_ready
        and _runtime_opportunity_risk_should_block_position(opportunity_comparison)
    ):
        return _force_observation_for_opportunity_risk(position_decision, opportunity_comparison)
    if existing_target_pct >= 50:
        return _repair_confirmed_front_page_position_decision(
            position_decision,
            selected_position_candidate=selected_position_candidate,
        )
    if candidate_target_pct < 50 or not _front_page_candidate_has_execution_qualification(selected_position_candidate):
        return _force_observation_for_missing_execution_evidence(position_decision)
    monthly_rhythm = dict(position_decision.get("monthly_rhythm") or {}) if isinstance(position_decision.get("monthly_rhythm"), dict) else {}
    promoted_target_pct = min(candidate_target_pct, 100)
    promoted_signal_grade = "100" if promoted_target_pct >= 100 else "50"
    promoted_mode = "full_100" if promoted_signal_grade == "100" else "attack_50_preview"
    promoted_reason = (
        "明日极度看好目标标的已存在，市场未到极端冰点；盘前不抢跑，但保留100%核心进攻，固定交易窗口内条件不成立就回到0%。"
        if promoted_signal_grade == "100"
        else "明日极度看好目标标的已存在，市场未到极端冰点；盘前不抢跑，但保留50%标准进攻预演，固定交易窗口内条件不成立就回到0%。"
    )
    monthly_rhythm.update(
        {
            "month_mode": "attack_prepare",
            "target_role": "attack_confirmed" if promoted_signal_grade == "100" else "attack_prepare",
            "max_position_pct": max(
                int(_runtime_cell_float(monthly_rhythm.get("max_position_pct")) or 0),
                promoted_target_pct,
            ),
            "allow_full_attack": bool(monthly_rhythm.get("allow_full_attack")) or promoted_signal_grade == "100",
            "trend_invalid": False,
            "reason": "明日极度看好目标已存在，普通防守态只缩小容器，不取消推荐属性。",
        }
    )
    updated = dict(position_decision)
    updated.update(
        {
            "participation_mode": promoted_mode,
            "target_position_pct": promoted_target_pct,
            "signal_grade": promoted_signal_grade,
            "candidate_feedback_ready": True,
            "sizing_reason": promoted_reason,
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
    if bool(final_gate.get("old_position_priority")):
        updated = dict(final_gate)
        updated.update(
            {
                "can_new_entry": False,
                "should_reduce": True,
                "allow_attack_50_ready": False,
                "final_action": "先处理旧仓，不新增参与；新强对象只保留观察对象",
            }
        )
        return updated
    target_pct = _front_page_target_pct(position_decision)
    if not selected_position_candidate or target_pct < 50:
        return final_gate

    target_label = _target_candidate_label(selected_position_candidate)
    target_display_label = _runtime_stock_label(selected_position_candidate) or target_label
    target_grade = "100" if target_pct >= 100 else "50"
    target_action_label = "条件100%核心进攻" if target_grade == "100" else "条件50%预演"
    capital_action_reason = _first_runtime_text(final_gate.get("capital_action_reason"))
    old_exit_for_new_entry = bool(final_gate.get("old_position_exit_for_new_entry"))
    if capital_action_reason or old_exit_for_new_entry:
        updated = dict(final_gate)
        updated.update(
            {
                "gate_status": "条件进攻",
                "operation_state": "条件进攻态",
                "can_new_entry": False,
                "should_reduce": old_exit_for_new_entry,
                "allow_attack_50_ready": True,
                "base_position_cap_pct": max(int(_runtime_cell_float(updated.get("base_position_cap_pct")) or 0), target_pct),
                "final_action": (
                    capital_action_reason
                    or f"先处理旧仓，买{target_display_label}；固定交易窗口条件成立才参与，不满足回到0%"
                ),
                "final_participation": (
                    "小账户先释放旧仓资金，再只看新核心执行条件。"
                    if old_exit_for_new_entry
                    else "小账户用可交易替代表达承接目标方向。"
                ),
                "gate_reason": (
                    "约1w账户不能同时做旧仓T和新开仓；新核心胜出时，旧仓处理是资金释放动作。"
                    if old_exit_for_new_entry
                    else "目标对象账户不适配时，用同方向可交易替代表达。"
                ),
            }
        )
        return updated
    updated = dict(final_gate)
    updated.update(
        {
            "gate_status": "条件进攻",
            "operation_state": "条件进攻态",
            "can_new_entry": False,
            "should_reduce": False,
            "allow_attack_50_ready": True,
            "base_position_cap_pct": max(int(_runtime_cell_float(updated.get("base_position_cap_pct")) or 0), target_pct),
            "final_action": f"明日目标标的保留{target_action_label}：只看{target_label}，固定交易窗口内条件成立才执行，不满足回到0%",
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
    text = text.replace("| 100% |", "| 0%观察 |")
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
            "明日不新增参与，只观察风险是否钝化、主攻线承接和观察对象是否重新成立",
        )
    if "盘前0%；固定交易窗口内条件成立后才评估50%标准进攻" in text:
        text = text.replace(
            "盘前0%；固定交易窗口内条件成立后才评估50%标准进攻",
            "盘前0%；暂无新增参与资格，只观察风险是否钝化",
        )
    if "明日目标标的保留条件100%核心进攻" in text:
        text = re.sub(
            r"明日目标标的保留条件100%核心进攻：只看[^，|]+，固定交易窗口内条件成立才执行，不满足回到0%",
            "不新增参与；只保留观察对象；未出现执行资格前不新增参与",
            text,
        )
    if "明日目标标的保留条件50%预演" in text:
        text = re.sub(
            r"明日目标标的保留条件50%预演：只看[^，|]+，固定交易窗口内条件成立才执行，不满足回到0%",
            "不新增参与；只保留观察对象；未出现执行资格前不新增参与",
            text,
        )
    if "盘前0%；观察窗口命中后才评估50%标准进攻" in text:
        text = text.replace(
            "盘前0%；观察窗口命中后才评估50%标准进攻",
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
    text = text.replace("条件观察：", "观察对象：")
    text = text.replace("观察锚：", "观察对象：")
    text = text.replace(
        "50%标准进攻需要先等固定交易窗口内条件成立；未确认前按0%处理，确认后按失效价和单笔-5%底线处理风险",
        "0%不参与：最终结论不允许新增参与，只观察风险是否钝化",
    )
    text = text.replace(
        "09:50-10:10站上确认价，且板块承接不塌，才评估50%标准进攻；未命中继续0%观察",
        "只保留观察；未出现执行资格前不新增参与；未命中继续0%观察",
    )
    text = text.replace(
        "盘前0%只代表不抢跑；09:50-10:10窗口内条件成立后，再评估50%标准进攻",
        "盘前0%只代表不抢跑；只观察，不新增参与",
    )
    text = text.replace(
        "以观察和处理持仓为主；新仓只允许固定交易窗口内条件成立后的主线核心50%标准进攻",
        "以观察和处理持仓为主；不做新开仓",
    )
    text = text.replace("只在", "仅在") if "核心里找参与资格" in text else text
    text = text.replace("核心里找参与资格", "核心里继续观察")
    text = text.replace("继续寻找参与资格", "继续观察")
    text = text.replace("寻找参与资格", "观察")
    text = text.replace("等触发条件成立", "只观察，不新增参与")
    text = text.replace("确认后才评估50%标准进攻，未确认保持0%", "确认后也只保留观察，未确认保持0%")
    text = text.replace("才评估50%标准进攻", "才保留观察；未出现执行资格前不新增参与")
    text = text.replace("触发后50%标准进攻", "触发后只观察")
    text = text.replace("条件50%", "只观察")
    text = text.replace("50%标准进攻", "只观察")
    text = text.replace("唯一对象是否", "观察对象是否")
    text = text.replace("观察锚是否", "观察对象是否")
    return text


def _runtime_observation_anchor_label(final_target_resolution=None):
    if not isinstance(final_target_resolution, dict):
        return ""
    watch_target = final_target_resolution.get("watch_target")
    if not isinstance(watch_target, dict) or not watch_target:
        return ""
    return _runtime_stock_label(watch_target) or _target_candidate_label(watch_target)


def _align_appendix_observation_anchor_lines(lines, final_target_resolution=None):
    anchor_label = _runtime_observation_anchor_label(final_target_resolution)
    if not anchor_label:
        return list(lines or [])
    normalized = []
    in_watch_order = False
    first_watch_rewritten = False
    for line in list(lines or []):
        text = str(line or "")
        if "**观察优先锚点**" in text:
            prefix = text.split("**观察优先锚点**", 1)[0]
            normalized.append(f"{prefix}**观察优先锚点**: {anchor_label}")
            in_watch_order = False
            continue
        if "**先看顺序**" in text:
            in_watch_order = True
            first_watch_rewritten = False
            normalized.append(text)
            continue
        if in_watch_order and not first_watch_rewritten and "👀" in text:
            normalized.append(re.sub(r"(?<=👀\s).*?(?=\s+-|$)", anchor_label, text, count=1))
            first_watch_rewritten = True
            continue
        normalized.append(text)
    return normalized


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


def _normalize_attack_preview_appendix_lines(
    lines,
    *,
    selected_position_candidate=None,
    position_decision=None,
    final_target_resolution=None,
):
    final_target_resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    capital_priority = _first_runtime_text(
        (final_target_resolution.get("capital_priority_decision") or {}).get("capital_priority")
    )
    if capital_priority in {"old_position_t", "old_position", "existing_position", "existing_position_t", "wait"}:
        normalized_zero_lines = [_normalize_zero_participation_appendix_line(line) for line in list(lines or [])]
        return _align_appendix_observation_anchor_lines(normalized_zero_lines, final_target_resolution)
    has_selected_target = isinstance(selected_position_candidate, dict) and bool(
        selected_position_candidate.get("name") or selected_position_candidate.get("code")
    )
    if _has_zero_participation_context(position_decision):
        normalized_zero_lines = [_normalize_zero_participation_appendix_line(line) for line in list(lines or [])]
        return _align_appendix_observation_anchor_lines(normalized_zero_lines, final_target_resolution)
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
        if text == "- **进攻仓位三态**: 0%观察":
            text = "- **进攻仓位三态**: 50%标准进攻预演"
        if text.startswith("**次日市场环境**: 0%观察 /"):
            text = text.replace("**次日市场环境**: 0%观察 /", "**次日市场环境**: 50%标准进攻 /", 1)
        if "当前按0%不参与，固定交易窗口内条件未成立前只观察" in text:
            text = text.replace(
                "当前按0%不参与，固定交易窗口内条件未成立前只观察",
                "50%标准进攻；固定交易窗口内条件成立才执行，不满足回到0%",
            )
        if text.startswith("- ✅ 不新增参与：50%标准进攻"):
            text = text.replace("- ✅ 不新增参与：", "- ⚠️ 不抢跑：", 1)
        if "0%观察不开新仓" in text:
            text = text.replace(
                "0%观察不开新仓",
                "50%标准进攻，盘前不抢跑",
            )
        if "0%观察，等待固定交易窗口内条件" in text:
            text = text.replace(
                "0%观察，等待固定交易窗口内条件",
                "50%标准进攻，等待固定交易窗口内条件",
            )
        if "0%新仓（只处理旧仓，不新增）" in text:
            text = text.replace(
                "0%新仓（只处理旧仓，不新增）",
                "50%标准进攻；条件不成立回0%",
            )
        if "市场级原则是若你有旧仓就去弱留强，不新增参与" in text:
            text = text.replace(
                "市场级原则是若你有旧仓就去弱留强，不新增参与",
                "若你有旧仓先去弱留强；明日执行目标只按固定交易窗口处理",
            )
        if "**⛔ 当前先不开新仓**" in text:
            text = text.replace("**⛔ 当前先不开新仓**", "**⚠️ 当前不抢跑**")
            text = text.replace("本轮不做PK出手结论", "本轮只保留固定交易窗口预演")
        if "当前是0%观察，本时段只确认主线核心是否在固定交易窗口内满足条件" in text:
            text = text.replace(
                "当前是0%观察，本时段只确认主线核心是否在固定交易窗口内满足条件",
                "当前是50%标准进攻，本时段只确认主线核心是否在固定交易窗口内满足条件",
            )
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
    return _align_appendix_observation_anchor_lines(normalized, final_target_resolution)


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
    updated["tracking_lines"] = _build_decision_ledger_tracking_lines(updated, target_date=target_date)
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


def _appendix_stock_codes_in_text(text):
    return set(re.findall(r"(?<!\d)(\d{6})(?!\d)", str(text or "")))


def _appendix_crossline_codes_from_context(execution_stage_context):
    execution_stage_context = execution_stage_context or {}
    text_parts = []
    for key in (
        "special_probe_text",
        "front_follow_action_text",
        "front_structure_layer_text",
        "watch_anchor_type",
    ):
        value = execution_stage_context.get(key)
        if isinstance(value, str) and value.strip():
            text_parts.append(value)
    for key in ("watch_anchor", "selected_position_candidate", "best_stock", "runner_up"):
        item = execution_stage_context.get(key)
        if not isinstance(item, dict):
            continue
        for text_key in ("watch_anchor_note", "summary_text", "reason", "why_watch", "current_interpretation"):
            value = item.get(text_key)
            if isinstance(value, str) and value.strip():
                text_parts.append(value)

    crossline_texts = [text for text in text_parts if "跨线对象" in text]
    crossline_codes = set()
    for text in crossline_texts:
        crossline_codes.update(_appendix_stock_codes_in_text(text))

    for key in ("observation_candidates", "display_observation_candidates"):
        for item in execution_stage_context.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            item_texts = []
            for text_key in ("watch_anchor_note", "summary_text", "reason", "why_watch", "current_interpretation"):
                value = item.get(text_key)
                if isinstance(value, str) and value.strip():
                    item_texts.append(value)
            if not any("跨线对象" in text for text in item_texts):
                continue
            code = str(_appendix_stock_code(item) or "").strip()
            if code:
                crossline_codes.add(code)

    anchor = execution_stage_context.get("watch_anchor")
    if isinstance(anchor, dict):
        anchor_code = str(_appendix_stock_code(anchor) or "").strip()
        anchor_name = str(_appendix_stock_name(anchor) or "").strip()
        if anchor_code and any(anchor_code in text or (anchor_name and anchor_name in text) for text in crossline_texts):
            crossline_codes.add(anchor_code)
    return crossline_codes


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
        ("crossline_observation_stocks", "跨线观察"),
        ("secondary_stocks", "主线备选"),
        ("gem_observation_stocks", "创业板观察"),
        ("generic_watch_stocks", "普通观察"),
        ("watchlist", "普通观察"),
    ]
    seen_codes = set()
    monitoring_index_by_key = {}
    monitoring_pool = []
    lifecycle_records = []
    crossline_codes = _appendix_crossline_codes_from_context(execution_stage_context)
    for key, source_pool in pool_specs:
        for item in execution_stage_context.get(key, []) or []:
            code = _appendix_stock_code(item)
            dedupe_key = code or _appendix_stock_name(item)
            item_source_pool = "跨线观察" if source_pool == "主线核心" and code in crossline_codes else source_pool
            if dedupe_key in seen_codes:
                if source_pool == "跨线观察" and dedupe_key in monitoring_index_by_key:
                    existing_index = monitoring_index_by_key[dedupe_key]
                    display_source_pool, current_action, forced_interpretation = _appendix_monitoring_labels(
                        item,
                        item_source_pool,
                        mainline_name,
                    )
                    monitoring_pool[existing_index]["source_pool"] = display_source_pool
                    monitoring_pool[existing_index]["current_action"] = current_action
                    lifecycle_records[existing_index]["current_action"] = current_action
                    if forced_interpretation:
                        lifecycle_records[existing_index]["current_interpretation"] = forced_interpretation
                continue
            seen_codes.add(dedupe_key)
            monitoring_index_by_key[dedupe_key] = len(monitoring_pool)
            display_source_pool, current_action, forced_interpretation = _appendix_monitoring_labels(item, item_source_pool, mainline_name)
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


def _calendar_news_items(data):
    xgb_data = (data or {}).get("xuangubao_data") or {}
    news_items = xgb_data.get("xuangubao_news") or []
    return [item for item in news_items if isinstance(item, dict)]


def _calendar_clean_text(value) -> str:
    return " ".join(str(value or "").split())


def _calendar_compact_text(value) -> str:
    text = str(value or "").lower()
    return re.sub(r"[\s　,，。；;：:、·（）()【】\\[\\]「」『』“”\"'《》<>—\\-_/]+", "", text)


def _calendar_news_source_date(news) -> str:
    if not isinstance(news, dict):
        return ""
    for key in ("source_date", "trade_date", "date", "created_date", "publish_date", "published_at"):
        value = str(news.get(key) or "").strip()
        match = re.search(r"20\d{2}-\d{2}-\d{2}", value)
        if match:
            return match.group(0)
    for key in ("created_at", "time", "timestamp"):
        raw_value = news.get(key)
        raw_text = str(raw_value or "").strip()
        match = re.search(r"20\d{2}-\d{2}-\d{2}", raw_text)
        if match:
            return match.group(0)
        try:
            timestamp = float(raw_value)
        except (TypeError, ValueError):
            continue
        if timestamp <= 0:
            continue
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        try:
            datetime_cls = datetime.datetime if hasattr(datetime, "datetime") else datetime
            return datetime_cls.fromtimestamp(timestamp, tz=_SHANGHAI_TZ).date().isoformat()
        except (OverflowError, OSError, ValueError):
            continue
    return ""


def _calendar_news_text(news) -> str:
    if not isinstance(news, dict):
        return ""
    parts = []
    for key in ("title", "summary", "content", "description", "detail", "source_text"):
        value = _calendar_clean_text(news.get(key))
        if value and value not in parts:
            parts.append(value)
    return " ".join(parts)


def _calendar_xuangubao_news_signature(data):
    return tuple(
        (
            _calendar_news_source_date(news),
            _calendar_clean_text(news.get("title")),
            _calendar_clean_text(news.get("summary")),
            _calendar_clean_text(news.get("content")),
            _calendar_clean_text(news.get("description")),
            _calendar_clean_text(news.get("detail")),
            _calendar_clean_text(news.get("source_text")),
        )
        for news in _calendar_news_items(data)[:80]
    )


def _calendar_strip_dates(text: str) -> str:
    text = re.sub(r"20\d{2}年", "", str(text or ""))
    text = re.sub(r"\d{1,2}月\d{1,2}日(?:至\d{1,2}日)?", "", text)
    text = re.sub(r"\d{1,2}日至\d{1,2}日", "", text)
    text = re.sub(r"\d{1,2}[/-]\d{1,2}", "", text)
    return text


def _calendar_is_specific_match_term(term: str) -> bool:
    term = _calendar_compact_text(term)
    if len(term) < 4 or term in _CALENDAR_WEAK_TITLE_TERMS or term.isdigit():
        return False
    if any(marker in term for marker in ("某", "待定", "未知")):
        return False
    stripped = term
    for form_term in _CALENDAR_EVENT_FORM_TERMS:
        stripped = stripped.replace(_calendar_compact_text(form_term), "")
    for weak_part in _CALENDAR_WEAK_TITLE_PARTS:
        stripped = stripped.replace(_calendar_compact_text(weak_part), "")
    return bool(stripped and stripped not in _CALENDAR_WEAK_TITLE_TERMS and len(stripped) >= 2)


def _calendar_title_match_terms(title: str) -> list[str]:
    title = _calendar_strip_dates(str(title or ""))
    normalized = _calendar_compact_text(title)
    terms = []
    if len(normalized) >= 8:
        terms.append(normalized)

    splitter = r"[，,。；;：:、·（）()【】\\[\\]「」『』“”\"'《》<>—\\-_/]"
    for raw_part in re.split(splitter, title):
        part = _calendar_compact_text(raw_part)
        if len(part) >= 4:
            terms.append(part)
        cut_candidates = [
            part.find(_calendar_compact_text(term))
            for term in _CALENDAR_EVENT_CUTOFF_TERMS
            if _calendar_compact_text(term) and part.find(_calendar_compact_text(term)) > 0
        ]
        if cut_candidates:
            core = part[: min(cut_candidates)]
            if len(core) >= 3:
                terms.append(core)
        stripped = part
        for term in _CALENDAR_EVENT_FORM_TERMS:
            stripped = stripped.replace(_calendar_compact_text(term), "")
        stripped = re.sub(r"\d+", "", stripped)
        if len(stripped) >= 3:
            terms.append(stripped)

    unique = []
    for term in terms:
        if _calendar_is_specific_match_term(term) and term not in unique:
            unique.append(term)
    return unique


def _calendar_event_title_matches_news(title: str, news_text: str) -> bool:
    return _calendar_news_candidate_score(title, news_text) > 0


def _calendar_news_candidate_score(title: str, news_text: str) -> int:
    compact_news = _calendar_compact_text(news_text)
    if not compact_news:
        return 0
    compact_title = _calendar_compact_text(_calendar_strip_dates(title))
    title_terms = _calendar_title_match_terms(title)
    score = 0
    if len(compact_title) >= 8 and compact_title in compact_news and title_terms:
        score += 80 + min(len(compact_title), 40)
    for term in title_terms:
        if len(term) >= 4 and term in compact_news:
            score += 20 + min(len(term), 20)
    return score


def _calendar_news_source_url(news) -> str:
    if not isinstance(news, dict):
        return ""
    return str(news.get("url") or news.get("source_url") or news.get("link") or "").strip()


def _calendar_xuangubao_news_candidates(event, data, *, limit: int = _CALENDAR_NEWS_CANDIDATE_LIMIT):
    if not isinstance(event, dict):
        return []
    title = str(event.get("title") or "").strip()
    report_date = str((data or {}).get("target_date") or "").strip()[:10]
    if not title or not report_date:
        return []

    scored = []
    fallback = []
    for source_index, news in enumerate(_calendar_news_items(data)):
        source_date = _calendar_news_source_date(news)
        if source_date != report_date:
            continue
        evidence_text = _calendar_news_text(news)
        if not evidence_text:
            continue
        candidate = {
            "title": _calendar_clean_text(news.get("title")),
            "summary": _calendar_clean_text(news.get("summary")),
            "content": _calendar_clean_text(news.get("content")),
            "description": _calendar_clean_text(news.get("description")),
            "detail": _calendar_clean_text(news.get("detail")),
            "source_text": _calendar_clean_text(news.get("source_text")),
            "evidence_text": evidence_text[:500],
            "source_date": source_date,
            "source_url": _calendar_news_source_url(news),
        }
        score = _calendar_news_candidate_score(title, evidence_text)
        entry = (score, source_index, candidate)
        if score > 0:
            scored.append(entry)
        else:
            fallback.append(entry)

    ordered = sorted(scored, key=lambda item: (-item[0], item[1])) + fallback
    candidates = []
    for candidate_index, (score, source_index, candidate) in enumerate(ordered[:limit]):
        candidate = dict(candidate)
        candidate["candidate_index"] = candidate_index
        candidate["source_index"] = source_index
        candidate["retrieval_score"] = score
        candidates.append(candidate)
    return candidates


def _calendar_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "是", "匹配", "相关", "matched"}


def _calendar_confidence_allows_evidence(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return float(value) >= 0.6
    text = str(value or "").strip().lower()
    return text in {"高", "中", "high", "medium", "mid", "strong", "ok"}


def _calendar_decision_evidence_index(decision, candidate_count: int):
    if not isinstance(decision, dict):
        return None
    raw_index = decision.get("evidence_index", decision.get("candidate_index", decision.get("index")))
    if isinstance(raw_index, bool):
        return None
    try:
        index = int(raw_index)
    except (TypeError, ValueError):
        return None
    if index < 0 or index >= candidate_count:
        return None
    return index


def _calendar_accepts_news_evidence_decision(decision, candidate_count: int):
    if not isinstance(decision, dict):
        return None
    if not _calendar_bool(decision.get("matched")):
        return None
    if not _calendar_confidence_allows_evidence(decision.get("confidence")):
        return None
    return _calendar_decision_evidence_index(decision, candidate_count)


def _calendar_adjudicate_xuangubao_source_evidence(event, candidates, report_date: str):
    if not ENABLE_REMOTE_CALENDAR_LLM or not candidates:
        return {}
    try:
        client = get_llm_service()
    except Exception:
        return {}
    adjudicator = getattr(client, "adjudicate_calendar_event_news_evidence", None)
    if not callable(adjudicator):
        return {}
    try:
        result = adjudicator(
            {
                "date": str((event or {}).get("date") or ""),
                "title": str((event or {}).get("title") or ""),
                "summary": _calendar_event_summary(event),
            },
            candidates,
            report_date=report_date,
        )
    except Exception:
        return {}
    return result if isinstance(result, dict) else {}


def _calendar_match_xuangubao_source_evidence(event, data):
    if not isinstance(event, dict):
        return {}
    title = str(event.get("title") or "").strip()
    report_date = str((data or {}).get("target_date") or "").strip()[:10]
    if not title or not report_date:
        return {}

    candidates = _calendar_xuangubao_news_candidates(event, data)
    decision = _calendar_adjudicate_xuangubao_source_evidence(event, candidates, report_date)
    selected_index = _calendar_accepts_news_evidence_decision(decision, len(candidates))
    if selected_index is None:
        return {}

    candidate = candidates[selected_index]
    source_url = str(candidate.get("source_url") or "").strip()
    evidence = {
        "provider": _CALENDAR_NEWS_PROVIDER,
        "query_date": report_date,
        "source_date": str(candidate.get("source_date") or ""),
        "source_url": source_url,
        "source_url_missing": not bool(source_url),
        "evidence_text": str(candidate.get("evidence_text") or "")[:500],
        "match_confidence": str(decision.get("confidence") or "").strip(),
        "policy_evidence": _calendar_bool(decision.get("policy_evidence")),
    }
    news_title = _calendar_clean_text(candidate.get("title"))
    if news_title:
        evidence["title"] = news_title
    match_reason = _calendar_clean_text(decision.get("match_reason"))
    if match_reason:
        evidence["match_reason"] = match_reason[:120]
    classification_hint = _calendar_clean_text(decision.get("classification_hint"))
    if classification_hint:
        evidence["classification_hint"] = classification_hint[:40]
    related_sectors = decision.get("related_sectors")
    if isinstance(related_sectors, list):
        evidence["related_sectors"] = [str(item).strip() for item in related_sectors if str(item or "").strip()][:5]
    return evidence


def _calendar_event_with_source_evidence(event, data):
    enriched = dict(event or {})
    evidence = _calendar_match_xuangubao_source_evidence(enriched, data)
    if not evidence:
        return enriched
    evidence_text = evidence.get("evidence_text", "")
    existing_source_text = _calendar_clean_text(enriched.get("source_text"))
    enriched["source_text"] = " ".join(part for part in (existing_source_text, evidence_text) if part)
    enriched["source_evidence"] = evidence
    return enriched


def _calendar_event_summary(event) -> str:
    if not isinstance(event, dict):
        return ""
    parts = []
    for key in ("summary", "content", "description", "detail", "source_text"):
        value = str(event.get(key) or "").strip()
        if value and value not in parts:
            parts.append(value)
    return " ".join(parts)


def _keyword_match_event_sectors(title: str, summary: str = "") -> dict:
    return normalize_calendar_ai_analysis({}, title, summary)


def _normalize_calendar_batch_results(batch_results, events):
    if not isinstance(batch_results, list):
        batch_results = []

    normalized_results = []
    for index, event in enumerate(events or []):
        title = event.get("title", "") if isinstance(event, dict) else ""
        summary = _calendar_event_summary(event)
        raw_result = batch_results[index] if index < len(batch_results) else None
        normalized_results.append(normalize_calendar_ai_analysis(raw_result, title, summary))
    return normalized_results


def _build_calendar_ai_context(data, print_fn=print):
    events = [
        _calendar_event_with_source_evidence(event, data)
        for event in ((data or {}).get("calendar_events") or [])
    ]
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
    events_for_analysis = [
        {"title": event.get("title", ""), "summary": _calendar_event_summary(event)}
        for event in events
    ]

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
            batch_results = [
                _keyword_match_event_sectors(event.get("title", ""), _calendar_event_summary(event))
                for event in events
            ]
    else:
        print_fn(f"   🧭 本地规则分析 {event_count} 个财经事件（远程LLM默认关闭）")
        batch_results = [
            _keyword_match_event_sectors(event.get("title", ""), _calendar_event_summary(event))
            for event in events
        ]

    batch_results = _normalize_calendar_batch_results(batch_results, events)

    calendar_analysis = []
    all_directions = []
    all_sectors = []
    for index, event in enumerate(events):
        title = event.get("title", "")
        ai_analysis = (
            batch_results[index]
            if index < len(batch_results)
            else _keyword_match_event_sectors(title, _calendar_event_summary(event))
        )
        smart_star = _smart_score_event(title, event.get("star", 0))
        calendar_analysis.append(
            {
                "date": event.get("date", ""),
                "title": title,
                "star": "⭐" * min(smart_star, 5),
                "ai_analysis": ai_analysis,
                **({"source_evidence": event["source_evidence"]} if event.get("source_evidence") else {}),
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


def _attach_market_structure_judgement(data):
    if not isinstance(data, dict):
        return {}
    snapshot = data.get("market_research_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    judgement = data.get("market_structure_judgement")
    if not isinstance(judgement, dict) or not judgement.get("summary_text"):
        judgement = build_market_structure_judgement(data=data, market_research_snapshot=snapshot)
    if not judgement.get("summary_text"):
        return {}
    data["market_structure_judgement"] = judgement
    snapshot["market_structure_judgement"] = judgement
    data["market_research_snapshot"] = snapshot
    update = build_market_structure_knowledge_update(judgement)
    if update:
        existing_updates = data.get("knowledge_updates")
        updates = []
        if isinstance(existing_updates, list):
            updates = [item for item in existing_updates if isinstance(item, dict)]
        data["knowledge_updates"] = updates
        if not any(isinstance(item, dict) and item.get("topic") == update.get("topic") for item in updates):
            updates.append(update)
    return judgement


def _attach_llm_wiki_knowledge_hits(data, llm_wiki_context):
    if not isinstance(data, dict) or not isinstance(llm_wiki_context, dict):
        return []
    facts = build_llm_wiki_fact_tags(data)
    hits = route_llm_wiki_knowledge(facts, scenario="daily_report", limit=3)
    llm_wiki_context["knowledge_hits"] = hits
    data.setdefault("knowledge", {})["llm_wiki"] = llm_wiki_context
    return hits


def _refresh_llm_wiki_knowledge_hits(data, llm_wiki_context):
    if not isinstance(data, dict) or not isinstance(llm_wiki_context, dict):
        return []
    return _attach_llm_wiki_knowledge_hits(data, llm_wiki_context)


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
    _attach_market_structure_judgement(data)
    if isinstance(data, dict):
        _attach_llm_wiki_knowledge_hits(data, llm_wiki_context)
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
    knowledge_note_lines = build_knowledge_update_note(data if isinstance(data, dict) else {})
    if knowledge_note_lines:
        report = "\n".join([report.rstrip(), "", *knowledge_note_lines]).strip()
    candidate_note_lines = build_knowledge_compounding_candidate_note(llm_wiki_context)
    if candidate_note_lines:
        report = "\n".join([report.rstrip(), "", *candidate_note_lines]).strip()
    knowledge_hit_lines = build_knowledge_hits_note(llm_wiki_context)
    if knowledge_hit_lines:
        report = "\n".join([report.rstrip(), "", *knowledge_hit_lines]).strip()

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
                "position_decision": phase_context.get("position_decision", {}) or data.get("position_decision", {}),
                "position_level": position_level,
                "position_reason": position_reason,
                "market_research_snapshot": data.get("market_research_snapshot") or {},
                "final_target_resolution": (
                    data.get("final_target_resolution")
                    or ((data.get("market_research_snapshot") or {}).get("final_target_resolution"))
                    or phase_context.get("final_target_resolution")
                    or {}
                ),
            }
        )
    )
    
    integrated_hot_data = data.get('integrated_hot_data', {})
    high_board_count = integrated_hot_data.get('high_board_count', 0)
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
    if market_activity_sections.get("exports"):
        data.update(market_activity_sections.get("exports") or {})
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
        target_date=target_date,
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
    csi1000_change = None
    if data.get('csi1000_index'):
        csi1000_change = data['csi1000_index'].get('涨跌幅', data['csi1000_index'].get('change_pct', 0))
    
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
                "csi1000_change": csi1000_change,
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
    unified_mainline_name = _mainline_name_from_turnover_summary(data.get("mainline_turnover_summary", {}) or {})
    unified_main_sectors = [unified_mainline_name] if unified_mainline_name else main_sectors
    report.extend(
        render_decision_board_section(
            {
                "compact": DISPLAY_MVP_MODE,
                "high_board_count": high_board_count,
                "exit_analysis": exit_analysis,
                "main_sectors": unified_main_sectors,
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
        main_sectors=unified_main_sectors,
        exit_analysis=exit_analysis,
    )
    replace_placeholder_lines(report, "<!-- PROHIBITION_PLACEHOLDER -->", prohibition_result.get('lines', []))

    report.append("")
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
    account_context = {}
    if not bool((data or {}).get("postgres_only")):
        account_context = _query_monthly_account_context(root_dir=root_dir, target_date=target_date)
    monthly_context = _merge_monthly_account_context(data.get("monthly_context") or {}, account_context)
    data["monthly_context"] = monthly_context
    _load_recent_extreme_conviction_mentions_for_selection(
        data,
        root_dir=root_dir,
        target_date=target_date,
        window_days=25,
    )
    personal_position_context = data.get("personal_position_context") if isinstance(data, dict) else {}
    position_context_provided = bool(data.get("position_context_provided")) or (
        isinstance(personal_position_context, dict) and "existing_position_summary" in personal_position_context
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
            "position_context_provided": position_context_provided,
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
            "render_action_plan_result": render_action_plan_result,
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
    candidate_trace_result = _maybe_persist_candidate_traces(
        data=data,
        target_date=target_date,
        execution_stage_context=execution_stage_context,
        run_mode=run_mode,
    )
    if isinstance(candidate_trace_result, dict):
        data["candidate_trace_artifact"] = candidate_trace_result
        execution_stage_context["candidate_trace_artifact"] = candidate_trace_result
    decision_ledger_tracking_lines = list(
        (decision_ledger_result or {}).get("tracking_lines")
        or _build_decision_ledger_tracking_lines(decision_ledger_result, target_date=target_date)
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
    if selected_position_candidate:
        data["selected_position_candidate"] = selected_position_candidate
        if isinstance(market_research_snapshot, dict):
            market_research_snapshot["selected_position_candidate"] = selected_position_candidate
            data["market_research_snapshot"] = market_research_snapshot
        _refresh_llm_wiki_knowledge_hits(data, (data.get("knowledge") or {}).get("llm_wiki") or {})
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
    final_target_resolution = _build_runtime_final_target_resolution(
        data=data,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        market_research_snapshot=market_research_snapshot,
    )
    _store_runtime_final_target_resolution(
        final_target_resolution,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
    two_layer_decision_payload = build_two_layer_decision_payload(
        target_date=target_date,
        final_target_resolution=final_target_resolution,
        position_decision=position_decision,
        execution_stage_context=execution_stage_context,
    )
    _store_runtime_two_layer_decision_payload(
        two_layer_decision_payload,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
    sniper_target_derivation = _build_sniper_target_derivation_packet(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        final_target_resolution=final_target_resolution,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_gate=final_gate,
        two_layer_decision_payload=two_layer_decision_payload,
    )
    _store_runtime_sniper_target_derivation(
        sniper_target_derivation,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
    final_gate_for_front_page = dict(final_gate or {}) if isinstance(final_gate, dict) else {}
    capital_priority = final_target_resolution.get("capital_priority_decision", {}).get("capital_priority")
    capital_reason = final_target_resolution.get("capital_priority_decision", {}).get("reason")
    if capital_priority == "old_position_t":
        final_gate_for_front_page["old_position_priority"] = True
    elif capital_priority == "new_entry_after_old_exit":
        final_gate_for_front_page["old_position_exit_for_new_entry"] = True
        final_gate_for_front_page["capital_action_reason"] = capital_reason
    elif capital_priority == "tradable_proxy":
        final_gate_for_front_page["capital_action_reason"] = capital_reason
    extreme_conviction_list = _sync_runtime_extreme_conviction_list_after_position_decision(
        data,
        execution_stage_context,
        market_research_snapshot,
        position_decision,
    )
    front_page_final_gate = _build_effective_front_page_final_gate(
        final_gate_for_front_page,
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
                "final_target_resolution": final_target_resolution,
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
    if selected_position_candidate:
        data["selected_position_candidate"] = selected_position_candidate
        if isinstance(market_research_snapshot, dict):
            market_research_snapshot["selected_position_candidate"] = selected_position_candidate
            data["market_research_snapshot"] = market_research_snapshot
        _refresh_llm_wiki_knowledge_hits(data, (data.get("knowledge") or {}).get("llm_wiki") or {})
    position_decision = _build_front_page_position_decision(
        position_decision=position_decision,
        selected_position_candidate=selected_position_candidate,
        data=data,
        market_research_snapshot=market_research_snapshot,
        final_gate=final_gate,
    )
    final_target_resolution = _build_runtime_final_target_resolution(
        data=data,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        market_research_snapshot=market_research_snapshot,
    )
    _store_runtime_final_target_resolution(
        final_target_resolution,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
    two_layer_decision_payload = build_two_layer_decision_payload(
        target_date=target_date,
        final_target_resolution=final_target_resolution,
        position_decision=position_decision,
        execution_stage_context=execution_stage_context,
    )
    _store_runtime_two_layer_decision_payload(
        two_layer_decision_payload,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
    sniper_target_derivation = _build_sniper_target_derivation_packet(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        final_target_resolution=final_target_resolution,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_gate=final_gate,
        two_layer_decision_payload=two_layer_decision_payload,
    )
    _store_runtime_sniper_target_derivation(
        sniper_target_derivation,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
    final_gate_for_front_page = dict(final_gate or {}) if isinstance(final_gate, dict) else {}
    capital_priority = final_target_resolution.get("capital_priority_decision", {}).get("capital_priority")
    capital_reason = final_target_resolution.get("capital_priority_decision", {}).get("reason")
    if capital_priority == "old_position_t":
        final_gate_for_front_page["old_position_priority"] = True
    elif capital_priority == "new_entry_after_old_exit":
        final_gate_for_front_page["old_position_exit_for_new_entry"] = True
        final_gate_for_front_page["capital_action_reason"] = capital_reason
    elif capital_priority == "tradable_proxy":
        final_gate_for_front_page["capital_action_reason"] = capital_reason
    extreme_conviction_list = _sync_runtime_extreme_conviction_list_after_position_decision(
        data,
        execution_stage_context,
        market_research_snapshot,
        position_decision,
    )
    front_page_final_gate = _build_effective_front_page_final_gate(
        final_gate_for_front_page,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
    )
    if isinstance(market_research_snapshot, dict):
        if "raw_final_gate" not in market_research_snapshot:
            market_research_snapshot["raw_final_gate"] = dict(market_research_snapshot.get("final_gate") or final_gate or {})
        personal_position_context = data.get("personal_position_context") if isinstance(data, dict) else {}
        position_context_provided = bool(data.get("position_context_provided")) if isinstance(data, dict) else False
        if isinstance(personal_position_context, dict):
            for key in ("account_profile", "existing_position_summary"):
                if isinstance(personal_position_context.get(key), dict):
                    market_research_snapshot[key] = dict(personal_position_context.get(key) or {})
            market_research_snapshot["position_context_provided"] = (
                position_context_provided or "existing_position_summary" in personal_position_context
            )
        elif position_context_provided:
            market_research_snapshot["position_context_provided"] = True
        if extreme_conviction_list:
            market_research_snapshot["extreme_conviction_list"] = extreme_conviction_list
            candidate_snapshot = market_research_snapshot.get("candidate_snapshot")
            if not isinstance(candidate_snapshot, dict):
                candidate_snapshot = {}
            candidate_snapshot["extreme_conviction_list"] = extreme_conviction_list
            market_research_snapshot["candidate_snapshot"] = candidate_snapshot
        market_research_snapshot["position_decision"] = position_decision
        market_research_snapshot["selected_position_candidate"] = selected_position_candidate
        market_research_snapshot["final_target_resolution"] = final_target_resolution
        market_research_snapshot["final_gate"] = front_page_final_gate
        market_research_snapshot["front_page_final_gate"] = front_page_final_gate
        data["market_research_snapshot"] = market_research_snapshot
        _attach_market_structure_judgement(data)
        market_research_snapshot = data.get("market_research_snapshot") or market_research_snapshot

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
        "final_target_resolution": final_target_resolution,
        "extreme_conviction_list": extreme_conviction_list,
        "front_page_final_gate": front_page_final_gate,
        "knowledge_hits": ((data.get("knowledge") or {}).get("llm_wiki") or {}).get("knowledge_hits", []),
    }
    front_page_lines = render_front_page_v2(
        report,
        target_date=target_date,
        market_research_snapshot=front_page_market_research_snapshot,
        final_gate=front_page_final_gate,
        position_level=position_level,
    )
    daily_judgment_front_panel_lines = _build_daily_judgment_front_panel_lines(
        (decision_ledger_result or {}).get("index")
        or _read_decision_ledger_index_for_tracking(globals().get("decision_ledger_root_dir", ".")),
        target_date=target_date,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        market_state_snapshot=market_state_snapshot,
        mainline_turnover_summary=mainline_turnover_summary,
        selected_position_candidate=selected_position_candidate,
        extreme_conviction_list=extreme_conviction_list,
    )
    front_page_lines = _insert_daily_judgment_front_panel(front_page_lines, daily_judgment_front_panel_lines)
    final_target_solution_lines = _runtime_selected_target_solution_lines(
        selected_position_candidate,
        final_gate=front_page_final_gate,
        mainline_turnover_summary=mainline_turnover_summary,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        final_target_resolution=final_target_resolution,
    )
    front_page_lines = _insert_final_target_solution_front_panel(front_page_lines, final_target_solution_lines)
    front_page_lines = _insert_two_layer_front_decision_panel(
        front_page_lines,
        render_front_decision_layer(two_layer_decision_payload),
    )
    if DISPLAY_MVP_MODE:
        report = front_page_lines
    else:
        appendix_report = _normalize_attack_preview_appendix_lines(
            _remove_duplicate_front_page_sections_from_appendix(report),
            selected_position_candidate=selected_position_candidate,
            position_decision=position_decision,
            final_target_resolution=final_target_resolution,
        )
        derivation_appendix = _sniper_target_derivation_full_section(
            sniper_target_derivation,
            heading="## 狙击手最终标的完整路径图（过程证据）",
        )
        appendix_lines = list(derivation_appendix)
        if appendix_lines:
            appendix_lines.append("")
        two_layer_derivation_lines = render_derivation_audit_layer(two_layer_decision_payload)
        if two_layer_derivation_lines:
            appendix_lines.extend(two_layer_derivation_lines)
            appendix_lines.append("")
        appendix_lines.extend(_demote_appendix_headings(appendix_report))
        report = front_page_lines + ["", "## 八、详细附录", ""] + appendix_lines

    print(f"   ✅ 最终执行条件: {sanitize_user_visible_text(front_page_final_gate.get('final_action', '未知'))}")
    _finalize_helper_diagnostics(data)
    report = _sanitize_report_lines(
        report,
        postgres_only=bool((data or {}).get("postgres_only") or globals().get("decision_ledger_postgres_only", False)),
    )
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
