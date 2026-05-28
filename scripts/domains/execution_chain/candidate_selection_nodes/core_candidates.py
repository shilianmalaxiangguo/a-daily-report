from selection.candlestick_signature import infer_signature_big_yangline
from report.trading_time_window_contract import normalize_trading_time_text


def build_candidate_selection_core_candidates_node(context, node_meta=None, node_lookup=None):
    core_stocks = context.get("core_stocks", []) or []
    primary_mainline = str(context.get("primary_mainline", "") or "").strip()
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    final_gate = context.get("final_gate", {}) or {}
    trade_gate_open = bool(final_gate.get("can_new_entry"))

    lines = ["**主线内可执行候选**:"]

    if core_stocks:
        lines.append("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |")
        lines.append("|------|------|----------|--------------|-----------|------|----------|----------|")
        core_preview = core_stocks[:2] if display_mvp_mode else core_stocks
        for stock in core_preview:
            signature_big_yangline = infer_signature_big_yangline(stock)
            five_day_burst_state = stock.get("five_day_burst_state") or "-"
            acceptance_state = (
                stock.get("acceptance_state")
                or stock.get("tomorrow_focus")
                or stock.get("tmr_forecast")
                or "09:50-10:10看是否抗跌、是否有承接回流"
            )
            capital_trace = (
                stock.get("capital_trace")
                or stock.get("core_level")
                or stock.get("reason")
                or stock.get("pattern")
                or "主线辨识度对象"
            )
            explicit_qualification = (
                stock.get("qualification_text")
                or stock.get("execution_right")
                or stock.get("permission_label")
            )
            if explicit_qualification:
                qualification_text = normalize_trading_time_text(explicit_qualification)
            elif trade_gate_open:
                qualification_text = "可做"
            else:
                qualification_text = "观察，等09:50-10:10窗口" if final_gate.get("allow_attack_50_ready") else "仅观察，条件未满足"
            if not trade_gate_open and "观察" not in str(qualification_text) and "无" not in str(qualification_text):
                qualification_text = "观察，等09:50-10:10窗口" if final_gate.get("allow_attack_50_ready") else "仅观察，条件未满足"
            elif not trade_gate_open and final_gate.get("allow_attack_50_ready") and str(qualification_text) in ("有条件执行", "资格", "可做"):
                qualification_text = "观察，等09:50-10:10窗口"
            elif not trade_gate_open and not final_gate.get("allow_attack_50_ready") and str(qualification_text) in ("有条件执行", "资格", "可做"):
                qualification_text = "仅观察，条件未满足"
            lines.append(
                f"| {stock.get('name', '-')} | {stock.get('code', '-')} | {stock.get('sector', primary_mainline or '-')} | "
                f"{signature_big_yangline} | {five_day_burst_state} | {normalize_trading_time_text(acceptance_state)} | {capital_trace} | {qualification_text} |"
            )
    else:
        lines.append("- 无明日核心股")

    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
