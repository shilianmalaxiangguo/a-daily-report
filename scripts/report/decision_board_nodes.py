from report.decision_board_node_registry import build_decision_board_node_specs
from report.decision_board_node_runtime import run_decision_board_nodes
from report.mainline_turnover_summary_support import resolve_mainline_attack_evidence_summary


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_decision_board_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 一、核心结论（决策看板）", ""], "exports": {}, "module_logs": []}


def build_decision_board_market_snapshot_placeholder_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->", ""], "exports": {}, "module_logs": []}


def build_decision_board_mvp_digest_placeholder_node(context, node_meta=None, node_lookup=None):
    if not context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": ["<!-- CORE_MVP_DIGEST_PLACEHOLDER -->", ""], "exports": {}, "module_logs": []}


def build_decision_board_mainline_section_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    exit_analysis = context.get("exit_analysis", {}) or {}
    main_sectors = context.get("main_sectors", []) or []
    primary_mainline = exit_analysis.get("sector_name", "") or (main_sectors[0] if main_sectors else "")
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    has_unconfirmed_attack_evidence = bool(attack_summary) and attack_summary.get("attack_state") != "confirmed_attack"
    high_board_count = int(context.get("high_board_count", 0) or 0)
    lines = ["### 🎯 主线方向"]
    if has_unconfirmed_attack_evidence:
        lines.append("- **核心主攻线**: 暂无确认主攻线")
        lines.append(f"- **主线确认**: {attack_summary.get('confirmation_evidence') or '攻击证据不足'}")
    elif primary_mainline:
        lines.append(f"- **核心主攻线**: {primary_mainline}")
    else:
        lines.append("- **核心主攻线**: 暂无明确主线")
    if high_board_count > 3:
        lines.append(f"- **资金偏好**: 高位连板股（资金追高意愿强，{high_board_count}只高位连板）")
    else:
        lines.append(f"- **资金偏好**: 低位启动股（资金谨慎，高位连板仅{high_board_count}只）")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_decision_board_positioning_section_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    exit_analysis = context.get("exit_analysis", {}) or {}
    final_gate = context.get("final_gate", {}) or {}
    price_info = context.get("price_info")
    lines = [
        "### 💰 仓位决策",
        f"- **市场环境档位**: {context.get('position_level', '')}",
        f"- **主线状态**: {context.get('overall_level', '红灯')}（{exit_analysis.get('overall_action', '未知')}）",
    ]
    if exit_analysis.get("overall_score") is not None and exit_analysis.get("mainline_score_pct") is not None:
        lines.append(
            f"- **主线连续评分**: 主线{exit_analysis.get('mainline_score_pct'):.1f}分 / 总体{exit_analysis.get('overall_score'):.1f}分"
        )
    score_detail = exit_analysis.get("score_detail", {}) or {}
    if score_detail:
        score_parts = [f"{name}{_safe_float(score):.1f}" for name, score in score_detail.items()]
        if score_parts:
            lines.append(f"- **六维拆解**: {' / '.join(score_parts)}")
        strongest = max(score_detail.items(), key=lambda x: _safe_float(x[1]))
        weakest = min(score_detail.items(), key=lambda x: _safe_float(x[1]))
        lines.append(f"- **当前强项**: {strongest[0]} {_safe_float(strongest[1]):.1f}分")
        lines.append(f"- **当前短板**: {weakest[0]} {_safe_float(weakest[1]):.1f}分")
    mainline_components = exit_analysis.get("mainline_component_scores", {}) or {}
    if mainline_components:
        component_parts = [f"{name}{_safe_float(score):.1f}" for name, score in mainline_components.items()]
        lines.append(f"- **主线内部分项**: {' / '.join(component_parts)}")
    if exit_analysis.get("mainline_trend_label"):
        lines.append(f"- **主线连续性**: {exit_analysis.get('mainline_trend_label')}")
    lines.append(f"- **最终操作状态**: {final_gate.get('operation_state', context.get('position_level', ''))}")
    lines.append(f"- **明天具体怎么做**: {final_gate.get('final_action', '')}")
    lines.append(f"- **环境推导**: {context.get('display_position_reason', '')}")
    if final_gate.get("gate_reason"):
        lines.append(f"- **主线修正**: {final_gate.get('gate_reason')}")
    get_execution_framework_text = context.get("get_execution_framework_text")
    framework_text = get_execution_framework_text() if callable(get_execution_framework_text) else "-"
    lines.append(f"- **怎么执行**: {framework_text}")
    if price_info and final_gate.get("can_new_entry"):
        lines.append(f"- **日线预估买入区间**: {price_info.get('buy_range')}元")
        lines.append(f"- **硬止损底线**: {price_info.get('stop_loss')}元")
        lines.append(f"- **止盈观察位**: {price_info.get('take_profit')}元")
        lines.append(f"- **执行说明**: {price_info.get('stop_rule', '盘中以30分钟结构止损为准')}")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_decision_board_risk_section_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    dt_count = int(context.get("dt_count", 0) or 0)
    turnover = _safe_float(context.get("turnover", 0))
    rise_fall_ratio = _safe_float(context.get("rise_fall_ratio", 0))
    up_count = int(context.get("up_count", 0) or 0)
    down_count = int(context.get("down_count", 0) or 0)
    high_board_count = int(context.get("high_board_count", 0) or 0)
    abnormal_risk = context.get("abnormal_risk", []) or []
    lines = ["### ⚠️ 明天要防什么"]
    risk_count = 0
    if high_board_count > 5:
        lines.append(f"- 🔴 高位连板股占比过高（{high_board_count}只），需警惕分歧风险")
        risk_count += 1
    if dt_count > 5:
        lines.append(f"- 🔴 跌停数较多（{dt_count}只），市场风险偏好下降")
        risk_count += 1
    if turnover < 7000:
        lines.append(f"- 🟡 成交额不足（{turnover:.0f}亿），市场参与度低")
        risk_count += 1
    if rise_fall_ratio < 0.5:
        lines.append(f"- 🔴 涨跌比过低（{up_count}:{down_count}），市场情绪低迷")
        risk_count += 1
    if abnormal_risk:
        lines.append(f"- 🟡 异动监控显示{len(abnormal_risk)}只股票存在潜在风险")
        risk_count += 1
    if risk_count == 0:
        lines.append("- ✅ 暂无明显风险信号")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_decision_board_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": [""], "exports": {}, "module_logs": []}


DECISION_BOARD_NODE_BUILDERS = {
    "header": build_decision_board_header_node,
    "market_snapshot_placeholder": build_decision_board_market_snapshot_placeholder_node,
    "mvp_digest_placeholder": build_decision_board_mvp_digest_placeholder_node,
    "mainline_section": build_decision_board_mainline_section_node,
    "positioning_section": build_decision_board_positioning_section_node,
    "risk_section": build_decision_board_risk_section_node,
    "footer": build_decision_board_footer_node,
}


def render_decision_board_section(context):
    context = context or {}
    node_specs = build_decision_board_node_specs(
        DECISION_BOARD_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    result = run_decision_board_nodes(node_specs, context)
    return result["lines"]
