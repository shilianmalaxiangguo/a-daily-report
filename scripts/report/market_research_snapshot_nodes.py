def _full_row(label, current_evidence, derived_judgement, action_effect):
    return f"| {label} | {current_evidence} | {derived_judgement} | {action_effect} |"


def _observation(context):
    return context.get("observation") or {}


def _benchmark_change(context):
    return float(context.get("benchmark_change", 0) or 0)


def _turnover(context):
    return float(context.get("turnover", 0) or 0)


def build_market_research_snapshot_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["### 🔬 市场研究快照"], "exports": {}, "module_logs": []}


def build_market_research_snapshot_table_header_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            "| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |",
            "|----------|----------|----------|--------------|",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_risk_preference_node(context, node_meta=None, node_lookup=None):
    observation = _observation(context)
    benchmark_change = _benchmark_change(context)
    turnover = _turnover(context)
    if context.get("compact"):
        lines = [
            (
                f"- **盘面风险偏好**: 上证{benchmark_change:+.2f}% / 涨停{observation.get('zt_count', 0)} / "
                f"跌停{observation.get('dt_count', 0)} / 涨跌比{observation.get('rise_fall_ratio_text', '暂无')} / 成交额{turnover:.0f}亿"
            )
        ]
    else:
        lines = [
            _full_row(
                "盘面风险偏好",
                "热点/趋势/异常",
                (
                    f"上证{benchmark_change:+.2f}% / 涨停{observation.get('zt_count', 0)} / "
                    f"跌停{observation.get('dt_count', 0)} / 涨跌比{observation.get('rise_fall_ratio_text', '暂无')} / 成交额{turnover:.0f}亿"
                ),
                "先看风险偏好，再决定能否继续往下判断",
            )
        ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_mainline_focus_node(context, node_meta=None, node_lookup=None):
    competition_result = context.get("competition_result", "主线待定")
    competition_evidence = context.get("competition_evidence", "先看趋势密度、异常承接和资金聚焦谁先胜出")
    if context.get("compact"):
        lines = [f"- **主线焦点**: {competition_result}；{competition_evidence}"]
    else:
        lines = [_full_row("主线焦点", competition_result, competition_evidence, "优先聚焦主线对象")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_rotation_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            _full_row(
                "主线内部轮动",
                context.get("rotation_label", "-"),
                context.get("rotation_summary_text", "-") or context.get("rotation_reason", "-"),
                context.get("rotation_action", "-"),
            )
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_narrative_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            _full_row(
                "叙事节点",
                context.get("narrative_label", "-"),
                context.get("narrative_reason", "-"),
                context.get("narrative_action", "-"),
            )
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_style_background_node(context, node_meta=None, node_lookup=None):
    style_label = context.get("style_label", "-")
    style_reason = context.get("style_reason", "-")
    style_evidence_text = context.get("style_evidence_text", "-") or style_reason
    if context.get("compact"):
        lines = [f"- **风格背景**: {style_label}；{style_reason}"]
    else:
        lines = [_full_row("风格背景", style_label, style_evidence_text, "背景参考，不直接触发动作")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_abnormal_projection_node(context, node_meta=None, node_lookup=None):
    abnormal_label = context.get("abnormal_projection_label", "-")
    abnormal_reason = context.get("abnormal_projection_reason", "-")
    if context.get("compact"):
        lines = [f"- **异常承接证据**: {abnormal_label}；{abnormal_reason}"]
    else:
        lines = [_full_row("异常承接证据", abnormal_label, abnormal_reason, "允许继续进入下一步判断")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_follow_verdict_node(context, node_meta=None, node_lookup=None):
    follow_label = context.get("follow_verdict_label", "-")
    follow_reason = context.get("follow_verdict_reason", "-")
    if context.get("compact"):
        lines = [f"- **明天能不能开仓**: {follow_label}；{follow_reason}"]
    else:
        lines = [_full_row("明天能不能开仓", follow_label, follow_reason, "动作锚定到“明天能不能开仓”")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_state_summary_node(context, node_meta=None, node_lookup=None):
    lines = []
    if not context.get("compact"):
        lines.append("")
    lines.append(
        f"- **统一状态判断**: {context.get('state_energy', '-')}；{context.get('state_reason', '-')}；{context.get('state_flow_direction', '-')}"
    )
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_leader_memory_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    observation = _observation(context)
    return {
        "lines": [
            f"- **龙头记忆**: 已保留{observation.get('leader_memory_count', 0)}只记忆资产，其中可信记忆{observation.get('trusted_tracking_count', 0)}只"
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_trend_density_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    observation = _observation(context)
    if not observation.get("densest_sector"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            f"- **最强趋势密度**: {observation.get('densest_sector')} 当前有{observation.get('densest_sector_trend_count', 0)}只活跃趋势股"
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_style_note_node(context, node_meta=None, node_lookup=None):
    if context.get("compact") or not context.get("style_reason"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"- **风格说明**: {context.get('style_reason')}"], "exports": {}, "module_logs": []}


def build_market_research_snapshot_dialectical_decision_node(context, node_meta=None, node_lookup=None):
    dialectical_decision = context.get("dialectical_decision") or {}
    if context.get("compact") or not dialectical_decision:
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = [
        "### 🧠 辩证决策补充",
        f"- **现在更像什么阶段**: {dialectical_decision.get('stage_label', '-')}；{dialectical_decision.get('stage_reason', '-')}",
        f"- **指数和赚钱效应是否背离**: {dialectical_decision.get('index_profit_relation', '-')}；{dialectical_decision.get('index_profit_reason', '-')}",
        f"- **赚钱效应现在往哪聚**: {dialectical_decision.get('focus_label', '-')}；{dialectical_decision.get('focus_action', '-')}",
        f"- **明天优先看哪类对象**: {dialectical_decision.get('candidate_focus', '-')}；{dialectical_decision.get('candidate_action', '-')}",
        f"- **什么情况下先不认这轮修复**: {' / '.join(dialectical_decision.get('falsification_conditions', []) or ['暂无'])}",
    ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": [""], "exports": {}, "module_logs": []}
