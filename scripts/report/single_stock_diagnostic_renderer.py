def render_single_stock_diagnostic_markdown(context):
    context = context or {}
    lines = [
        f"# {context.get('target_date', '-')} 单票诊断 - {context.get('name', '-') }({context.get('code', '-')})",
        "",
        "> **口径说明**：本诊断与日报共用同一套市场环境、主线、异常承接、可交易性与执行权限状态机，不走旁路判断。",
        "",
        "## 一、市场层",
        f"- **环境档位**: {context.get('position_level', '-')}",
        f"- **最终门控**: {context.get('final_action', '-')}",
        f"- **主攻线**: {context.get('mainline_name', '-')}",
        f"- **主线驱动**: {context.get('driver_type', '-')}",
        f"- **脉冲阶段**: {context.get('pulse_stage', '-')}",
        f"- **承接质量**: {context.get('acceptance_quality', '-')}",
        f"- **当前动作偏置**: {context.get('pulse_action_bias', '-')}",
        f"- **状态机**: {context.get('energy_state', '-')}",
        f"- **Step 0裁决**: {context.get('step0_prediction_cn', '-')}",
        "",
        "## 二、个股层",
        f"- **系统角色**: {context.get('system_role', '-')}",
        f"- **所属板块**: {context.get('sector', '未知')}",
        f"- **今日涨跌**: {float(context.get('change_pct', 0) or 0):+.2f}%",
        f"- **今日形态**: {context.get('pattern', '-')}",
        f"- **异动状态**: {context.get('abnormal_follow_state', '无明确异动跟踪')}",
        f"- **异动灯号**: {context.get('risk_light', '-')} / {context.get('risk_reason', '-')}",
        f"- **执行权限**: {context.get('permission_label', '-')}",
        f"- **权限说明**: {context.get('permission_reason', '-')}",
        f"- **Step 3分组**: {context.get('risk_level', '-')} / {context.get('risk_group', '-')}",
        f"- **Step 3理由**: {context.get('risk_reason_text', '-')}",
        f"- **风险归因**: 风险项{context.get('risk_penalty_count', 0)}条 / 修复项{context.get('repair_buffer_count', 0)}条 / 原始分{context.get('raw_risk_score', '-')} / 净分{context.get('risk_score', '-')}",
        "",
        "## 三、执行层",
        f"- **可交易性**: {context.get('tradability_status', '-')}",
        f"- **可交易性说明**: {context.get('tradability_reason', '-')}",
        f"- **量化信号**: {context.get('quant_signal_type', '-')}",
        f"- **量化判断**: {context.get('quant_reason', '暂无量化信号')}",
        f"- **60分钟确认点**: {context.get('confirm_text', '-')}",
        f"- **关键位/带**: {context.get('key_zone_display', '-')}",
        f"- **执行止损**: {context.get('execution_stop_display', '-')}",
        f"- **最晚硬止损**: {context.get('hard_stop_display', '-')}",
        f"- **价格怎么看**: {context.get('price_note_text', '-')}",
        f"- **决策栈**: 环境{(context.get('decision_stack', {}) or {}).get('environment_score', '-')} / "
        f"主线{(context.get('decision_stack', {}) or {}).get('mainline_score', '-')} / "
        f"记忆{(context.get('decision_stack', {}) or {}).get('memory_score', '-')} / "
        f"触发{(context.get('decision_stack', {}) or {}).get('trigger_score', '-')} / "
        f"可交易性{(context.get('decision_stack', {}) or {}).get('tradability_score', '-')} / EV{context.get('ev_stack_text', '-')}",
        "",
        "## 四、结论",
        f"- **最终裁决**: {context.get('final_verdict', '-')}",
        f"- **裁决理由**: {context.get('final_reason', '-') or '-'}",
    ]
    if context.get("risk_tomorrow_text") and context.get("risk_tomorrow_text") != "-":
        lines.append(f"- **明日预判**: {context.get('risk_tomorrow_text')}")
    elif context.get("tmr_forecast"):
        lines.append(f"- **明日预判**: {context.get('tmr_forecast')}")
    if context.get("source_tags"):
        lines.append(f"- **命中来源**: {' / '.join(context.get('source_tags', []))}")
    lines.append("")
    return "\n".join(lines)
