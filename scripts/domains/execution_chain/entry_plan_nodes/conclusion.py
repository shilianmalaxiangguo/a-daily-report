def build_entry_plan_conclusion_node(context, node_meta=None, node_lookup=None):
    final_gate = context.get("final_gate", {}) or {}
    keep_group = context.get("keep_group", []) or []
    position_level = str(context.get("position_level", "") or "").strip()
    executable_stocks = context.get("executable_stocks", []) or []
    waiting_stocks = context.get("waiting_stocks", []) or []
    untradable_stocks = context.get("untradable_stocks", []) or []
    next_stage_label = str(context.get("next_stage_label", "") or "Step 5").strip() or "Step 5"
    step4_structure_layer_text = str(context.get("step4_structure_layer_text", "") or "").strip()

    lines = ["**结论**:"]
    lines.append(f"- **现在是什么情况**: {step4_structure_layer_text}")
    if final_gate.get("can_new_entry", False) and executable_stocks:
        lines.append(f"- **接着做什么**: 继续进入{next_stage_label}筛选，只允许一只可买股留下来")
    elif waiting_stocks:
        lines.append("- **接着做什么**: 当前还在等待层，先等买点自己长出来")
    elif keep_group or executable_stocks:
        lines.append("- **接着做什么**: 当前只保留观察权，不做任何新买入")
    else:
        lines.append("- **明天先怎么观察**: 当前没有需要特别盯的执行记录，先看市场自己给答案")
    if untradable_stocks:
        lines.append(f"- **哪些票看着强但买不进去**: {len(untradable_stocks)}只（如一字/连续一字，只记观察不计执行收益）")
    lines.append(f"- **执行节奏**: {context['get_execution_framework_text']()}")
    if final_gate.get("can_new_entry", False):
        lines.append("- **⚠️ 重要**: 以上买点基于今日收盘数据预计算，明日若直接高开离买点>5%，则放弃；即便满足价格条件，也要等60分钟确认后再买")
    elif final_gate.get("allow_conditional_30"):
        lines.append(f"- **🟡 档位限制**: {position_level}，只保留10点确认后的30%条件试错；没有主线承接就不开新仓")
    else:
        lines.append(f"- **⛔ 档位限制**: {position_level}，禁止任何买入操作")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
