from report.legacy_stage_summary import build_legacy_report_stage_rows
from report.stage_registry import build_report_stages
from report.conclusion_support import (
    build_focus_recap_text as _build_focus_recap_text,
    build_market_outlook_text as _build_market_outlook_text,
    derive_risk_guard_text as _derive_risk_guard_text,
    derive_trade_style as _derive_trade_style,
    get_watch_anchor_note as _get_watch_anchor_note,
)


LAYERED_PARTICIPATION_TEXT = "竞价/开盘前几分钟/回封/60分钟分层参与窗口"


def _build_report_stages_from_context(context):
    report_stages = context.get("report_stages") or []
    if report_stages:
        return report_stages

    final_gate = context.get("final_gate") or {}
    generated_stages = build_report_stages(
        {
            "derived": {
                "market_phase": {"phase": str(context.get("step0_prediction", "") or "").lower()},
                "mainline": {"primary_line": context.get("mainline_name", "")},
                "strategy_contract": {"contract_label": final_gate.get("gate_status", "")},
            },
            "decision": {
                "execution_permission": {"label": "attack_50_ready" if context.get("trade_gate_open") else "watch_only"},
                "action_plan": {"trigger": context.get("front_follow_action_text", "")},
            },
        }
    )
    return [{**stage, "use_dynamic_title": False} for stage in generated_stages]

def _build_mvp_target_row(context):
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    trade_gate_open = bool(context.get("trade_gate_open"))
    watch_anchor_note = _get_watch_anchor_note(watch_anchor)

    if best_stock:
        entry_range = best_stock.get("entry_range") or ()
        if len(entry_range) >= 2:
            return (
                "| 如果要买只买谁 | "
                f"{best_stock.get('name')}({best_stock.get('code')})，"
                f"按{LAYERED_PARTICIPATION_TEXT}触发，价格预案{entry_range[0]:.2f}-{entry_range[1]:.2f} |"
            )
        return (
            "| 如果要买只买谁 | "
            f"{best_stock.get('name')}({best_stock.get('code')})，按{LAYERED_PARTICIPATION_TEXT}触发 |"
        )
    if watch_anchor:
        if trade_gate_open:
            return (
                "| 明天先盯哪只 | "
                f"{watch_anchor.get('name')}({watch_anchor.get('code')})，"
                f"先看{LAYERED_PARTICIPATION_TEXT}是否成立，只有走成明天唯一能买的那只才参与"
                f"{'；' + watch_anchor_note if watch_anchor_note else ''} |"
            )
        return (
            "| 重点观察谁 | "
            f"{watch_anchor.get('name')}({watch_anchor.get('code')})，"
            "只看强弱，不构成买入指令"
            f"{'；' + watch_anchor_note if watch_anchor_note else ''} |"
        )
    return "| 观察名单 | 当前没有可买对象，只保留观察名单 |"


def _build_full_mode_strategy_row(context):
    final_gate = context.get("final_gate") or {}
    step0_prediction = str(context.get("step0_prediction", "") or "").strip()
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    trade_gate_open = bool(context.get("trade_gate_open"))
    watch_anchor_note = _get_watch_anchor_note(watch_anchor)

    if not final_gate.get("can_new_entry"):
        if final_gate.get("should_reduce"):
            return ("明日策略", "只处理旧仓：继续研究市场，但不新增参与；若你有旧仓先去弱留强")
        return ("明日策略", "不开新仓，只观察：当前裁决不允许新增跟随，先看环境和主线是否继续强化")

    if step0_prediction == "DIFFICULT":
        return ("明日策略", "开盘再评估：环境仍需确认，只记录竞价表态和开盘承接，不满足预演情境就回到0%")

    if best_stock:
        if step0_prediction == "CLEAR":
            return ("明日策略", f"执行唯一标的：只操作{best_stock.get('name')}，按竞价表态/开盘前几分钟/回封/60分钟确认分层处理，买后用30分钟结构止损，其他标的禁止")
        return ("明日策略", f"唯一标的条件触发：只操作{best_stock.get('name')}，满足预演参与窗口才执行，其他标的无论多诱人都禁止")

    if watch_anchor:
        if trade_gate_open:
            guidance = (
                f"先盯重点盯盘股：只盯{watch_anchor.get('name')}，先看预演参与窗口，"
                "只有走成明天唯一能买的那只才参与"
            )
            if watch_anchor_note:
                guidance = f"{guidance}；{watch_anchor_note}"
            return ("明日策略", guidance)
        guidance = f"不开新仓，只观察：{watch_anchor.get('name')}作为重点观察谁，只看强弱，不下买单"
        if watch_anchor_note:
            guidance = f"{guidance}；{watch_anchor_note}"
        return ("明日策略", guidance)

    return ("明日策略", "空仓观望：无符合条件标的")

def build_final_conclusion_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["#### 最终结论", ""], "exports": {}, "module_logs": []}


def build_final_conclusion_table_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["| 项目 | 明日指引 |", "|------|----------|"], "exports": {}, "module_logs": []}


def build_final_conclusion_market_outlook_node(context, node_meta=None, node_lookup=None):
    if context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"| 明日大盘预期 | {_build_market_outlook_text(context)} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_market_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"| 明日大盘预期 | {_build_market_outlook_text(context)} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_focus_recap_node(context, node_meta=None, node_lookup=None):
    return {"lines": [f"| 今日关注标的 | {_build_focus_recap_text(context)} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_mainline_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"| 主看方向 | {context.get('mainline_label') or context.get('mainline_name') or '-'} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_focus_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    line = (
        f"| 观察池焦点 | {int(context.get('watchlist_count', 0) or 0)}只观察 / "
        f"{int(context.get('core_count', 0) or 0)}只主线核心 / "
        f"{int(context.get('crossline_count', 0) or 0)}只跨线观察 / "
        f"{int(context.get('abnormal_watch_count', 0) or 0)}只异常承接 |"
    )
    return {"lines": [line], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_gate_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"| 明天能不能开仓 | {context.get('front_structure_layer_text', '')} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_probe_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    abnormal_probe_parts = context.get("abnormal_probe_parts") or []
    if not abnormal_probe_parts:
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"| 异常探针 | {'；'.join(abnormal_probe_parts)} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_target_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [_build_mvp_target_row(context)], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_action_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"| 明日唯一动作 | {context.get('front_follow_action_text', '')} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_style_summary_node(context, node_meta=None, node_lookup=None):
    return {"lines": [f"| 操作风格 | {_derive_trade_style(context)} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_risk_guard_node(context, node_meta=None, node_lookup=None):
    return {"lines": [f"| 盈亏比约束 | {_derive_risk_guard_text(context)} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_mvp_discipline_node(context, node_meta=None, node_lookup=None):
    if not context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            "| 执行纪律 | 竞价表态/开盘前几分钟/回封/60分钟确认分层处理；不满足预演情境就回到0%；买后用30分钟结构止损，最晚单笔-5% |"
        ],
        "exports": {},
        "module_logs": [],
    }


def build_final_conclusion_full_stage_rows_node(context, node_meta=None, node_lookup=None):
    if context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    report_stages = _build_report_stages_from_context(context)
    stage_rows = build_legacy_report_stage_rows(
        {
            "report_stages": report_stages,
            "prefer_data_driven_stage_rows": not bool(context.get("report_stages")),
            "step0_prediction_cn": context.get("step0_prediction_cn", ""),
            "step0_action": context.get("step0_action", ""),
            "watchlist_count": context.get("watchlist_count", 0),
            "style_switch": context.get("style_switch", {}) or {},
            "market_style_label": context.get("market_style_label", ""),
            "tracking_memory_status": context.get("tracking_memory_status", {}) or {},
            "today_validated_items": context.get("today_validated_items"),
            "core_count": context.get("core_count", 0),
            "secondary_count": context.get("secondary_count", 0),
            "crossline_count": context.get("crossline_count", 0),
            "risk_summary": context.get("front_structure_layer_text", ""),
            "final_gate": context.get("final_gate", {}) or {},
            "trade_gate_open": context.get("trade_gate_open", False),
            "best_stock": context.get("best_stock"),
            "watch_anchor": context.get("watch_anchor"),
            "watch_anchor_type": context.get("watch_anchor_type", ""),
            "position_level": context.get("position_level", ""),
            "trade_style": context.get("trade_style", ""),
            "abnormal_probe_parts": context.get("abnormal_probe_parts") or [],
        }
    )
    return {
        "lines": [f"| {row.get('title', '-')} | {row.get('guidance', '-')} |" for row in stage_rows],
        "exports": {},
        "module_logs": [],
    }


def build_final_conclusion_full_strategy_node(context, node_meta=None, node_lookup=None):
    if context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    strategy_label, strategy_guidance = _build_full_mode_strategy_row(context)
    return {"lines": [f"| {strategy_label} | {strategy_guidance} |"], "exports": {}, "module_logs": []}


def build_final_conclusion_full_discipline_node(context, node_meta=None, node_lookup=None):
    if context.get("display_mvp_mode"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            "| 执行纪律 | 竞价表态/开盘前几分钟/回封/60分钟确认分层处理；不满足预演情境就回到0%；若直接高开离计划过远且无回封/承接方案则放弃 |"
        ],
        "exports": {},
        "module_logs": [],
    }


def build_final_conclusion_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": [""], "exports": {}, "module_logs": []}
