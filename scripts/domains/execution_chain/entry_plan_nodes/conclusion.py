from report.trading_time_window_contract import normalize_trading_time_text


def build_entry_plan_conclusion_node(context, node_meta=None, node_lookup=None):
    final_gate = context.get("final_gate", {}) or {}
    keep_group = context.get("keep_group", []) or []
    executable_stocks = context.get("executable_stocks", []) or []
    waiting_stocks = context.get("waiting_stocks", []) or []
    untradable_stocks = context.get("untradable_stocks", []) or []
    rejected_stocks = context.get("rejected_stocks", []) or []
    next_stage_label = str(context.get("next_stage_label", "") or "Step 5").strip() or "Step 5"
    step4_structure_layer_text = str(context.get("step4_structure_layer_text", "") or "").strip()

    lines = ["**结论**:"]
    lines.append(f"- **现在是什么情况**: {step4_structure_layer_text}")
    lines.append(
        f"- **传给下一步**: 可执行{len(executable_stocks)}只 / 等待{len(waiting_stocks)}只 / "
        f"不可交易{len(untradable_stocks)}只 / 拒绝{len(rejected_stocks)}只"
    )
    if final_gate.get("can_new_entry", False) and executable_stocks:
        lines.append(f"- **接着做什么**: 进入{next_stage_label}，只允许一只执行对象留下来")
    elif waiting_stocks:
        lines.append("- **接着做什么**: 当前还在等待层，先等买点自己长出来，不提前写成执行对象")
    elif keep_group or executable_stocks:
        lines.append(f"- **接着做什么**: 只把观察结论传给{next_stage_label}，不传执行对象")
    else:
        lines.append("- **明天先怎么观察**: 当前没有需要特别盯的执行记录，先看市场自己给答案")
    if untradable_stocks:
        lines.append(f"- **哪些票看着强但买不进去**: {len(untradable_stocks)}只（如一字/连续一字，只记观察不计执行收益）")
    lines.append(f"- **执行节奏**: {normalize_trading_time_text(context['get_execution_framework_text']())}")
    if final_gate.get("can_new_entry", False):
        lines.append(
            "- **⚠️ 重要**: 以上买点基于今日收盘数据预计算；明日按竞价表态、开盘前几分钟承接、打板/回封、09:50-10:10窗口分层处理，任一路径不满足固定交易窗口条件就回到0%，买后用失效价和单笔-5%底线处理风险"
        )
    elif final_gate.get("allow_attack_50_ready"):
        lines.append("- **进攻仓位**: 50%条件执行（待固定交易窗口内条件成立）；没有主线承接、竞价表态、开盘前几分钟承接或结构确认就自动转为0%不参与")
    else:
        lines.append("- **进攻仓位**: 0%不参与；无合格标的或取消条件已经出现")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
