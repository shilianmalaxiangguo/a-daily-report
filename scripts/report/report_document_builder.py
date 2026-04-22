def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.report_document_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_report_shell_contract(
    target_date,
    run_mode="frozen",
    has_personal_positions=False,
    compact=False,
    *,
    use_report_preamble,
):
    report = []
    logs = []
    report.extend(
        use_report_preamble(
            target_date,
            run_mode=run_mode,
            has_personal_positions=has_personal_positions,
            compact=compact,
        )
    )
    report.append("## 🚫 次日操作纪律（第一眼看这里）")
    report.append("")
    report.append("次日早盘打开日报，第一眼看这里。不在允许清单里的，就是禁止的。")
    report.append("")
    report.append("<!-- PROHIBITION_PLACEHOLDER -->")
    report.append("")
    _append_log(logs, "build.report_shell", "success", "已构建日报文档骨架", line_count=len(report))
    return {
        "report": report,
        "module_logs": logs,
    }


def build_prohibition_section_contract(
    display_position_level,
    display_operation_state,
    environment_headline="",
    has_personal_positions=False,
    final_gate=None,
    main_sectors=None,
    exit_analysis=None,
):
    prohibition_content = []
    logs = []
    final_gate = final_gate or {}
    main_sectors = main_sectors or []
    exit_analysis = exit_analysis or {}

    if display_position_level == "一档（空仓档）":
        headline = environment_headline or "环境关闭，只做等待，不做新增参与"
        prohibition_content.append(f"**次日市场环境**: {display_position_level} / {display_operation_state} - {headline}")
        prohibition_content.append("")
        prohibition_content.append("**禁止事项**:")
        prohibition_content.append("- ✅ 禁止新开仓：当前不允许新增任何买入")
        if has_personal_positions:
            prohibition_content.append("- ✅ 禁止恋战：你的现有仓位只做退出，不做摊平和自救")
        else:
            prohibition_content.append("- ✅ 禁止恋战：若你有旧仓，只做退出，不做摊平和自救")
        prohibition_content.append("- ✅ 禁止买入任何方向：无论题材多热，都先等环境重新打开")
        prohibition_content.append("- ✅ 禁止追高：不追涨任何股票")
        prohibition_content.append("- ✅ 禁止做T：次日不做日内回转")
        prohibition_content.append("- ✅ 禁止模式外交易：不在主线里的票不碰")
    elif display_position_level == "二档（防守档）":
        headline = environment_headline or "先看特殊标的是否继续抗跌，只保留观察权/旧仓处理权"
        prohibition_content.append(f"**次日市场环境**: {display_position_level} / {display_operation_state} - {headline}")
        prohibition_content.append("")
        prohibition_content.append("**禁止事项**:")
        prohibition_content.append("- ✅ 禁止新开仓：二档不允许任何新增买入")
        if final_gate.get("should_reduce"):
            if has_personal_positions:
                prohibition_content.append("- ✅ 禁止抱弱留弱：你的旧仓里，不在最强趋势的票要优先处理")
            else:
                prohibition_content.append("- ✅ 禁止抱弱留弱：若你有旧仓，不在最强趋势里的票要优先处理")
        if main_sectors:
            primary_mainline = main_sectors[0]
            secondary_hint = main_sectors[1] if len(main_sectors) >= 2 else ""
            if secondary_hint and secondary_hint != primary_mainline:
                prohibition_content.append(
                    f"- ⚠️ 主攻线只盯{primary_mainline}；{secondary_hint}只作竞争观察，不当执行方向"
                )
            else:
                prohibition_content.append(f"- ⚠️ 只盯主攻线{primary_mainline}里最强的票：主线弱化时，杂毛先淘汰")
        prohibition_content.append("- ✅ 禁止追高：不买昨天或大前天的最高点个股")
        prohibition_content.append("- ✅ 禁止做T：次日只买一种，不做日内回转")
        prohibition_content.append("- ✅ 禁止模式外交易：不在主线板块里的票不碰")
        prohibition_content.append("")
        prohibition_content.append("**允许事项**:")
        if final_gate.get("should_reduce"):
            if has_personal_positions:
                prohibition_content.append("- ✅ 持有：你的旧仓里，只允许继续拿仍在主线、仍有承接、仍在趋势里的最强票")
                prohibition_content.append("- ✅ 卖出：你的旧仓一旦转弱、失承接、跌破结构就卖，不犹豫")
            else:
                prohibition_content.append("- ✅ 持有：若你有旧仓，只允许继续拿仍在主线、仍有承接、仍在趋势里的最强票")
                prohibition_content.append("- ✅ 卖出：若你有旧仓，一旦转弱、失承接、跌破结构就卖，不犹豫")
        else:
            if has_personal_positions:
                prohibition_content.append("- ✅ 持有：你的现有强仓在主线未走坏前可继续持有")
                prohibition_content.append("- ✅ 卖出：你的持仓在大阳线或触及止损线时卖出")
            else:
                prohibition_content.append("- ✅ 持有：若你有强仓，在主线未走坏前可继续持有")
                prohibition_content.append("- ✅ 卖出：若你有仓位，在大阳线或触及止损线时卖出")
    else:
        headline = environment_headline or "环境放行不等于立刻下单，先看特殊标的，再等市场缩到唯一对象"
        prohibition_content.append(f"**次日市场环境**: {display_position_level} / {display_operation_state} - {headline}")
        prohibition_content.append("")
        prohibition_content.append("**禁止事项**:")
        prohibition_content.append("- ✅ 禁止追高：不买昨天或大前天的最高点个股")
        prohibition_content.append("- ✅ 禁止做T：次日只买一种，不做日内回转")
        prohibition_content.append("- ✅ 禁止模式外交易：不在主线板块里的票不碰")
        prohibition_content.append("- ✅ 禁止一看到市场转强就直接下单：没有缩到一只可买股之前，一律不开仓")
        prohibition_content.append("")
        prohibition_content.append("**允许事项**:")
        prohibition_content.append("- ✅ 先看特殊标的：先判断它们是深跌还是抗跌，再决定这轮调整是继续收还是重新攻")
        prohibition_content.append("- ✅ 新开仓前提：只有缩到一只可买股时，才允许按计划买入")
        if has_personal_positions:
            prohibition_content.append("- ✅ 持有：你的现有仓位继续持有")
            prohibition_content.append("- ✅ 卖出：你的持仓在大阳线或触及止损线时卖出")
        else:
            prohibition_content.append("- ✅ 持有：若你有仓位，可继续持有")
            prohibition_content.append("- ✅ 卖出：若你有仓位，在大阳线或触及止损线时卖出")

    risk_sectors = exit_analysis.get("risk_sectors", [])
    if risk_sectors:
        prohibition_content.append("")
        prohibition_content.append(f"**风险板块（禁止碰）**: {'、'.join(risk_sectors[:5])}")

    _append_log(
        logs,
        "build.prohibition_section",
        "success",
        "已生成次日操作纪律块",
        position_level=display_position_level,
        operation_state=display_operation_state,
        risk_sector_count=len(risk_sectors),
    )
    return {
        "lines": prohibition_content,
        "module_logs": logs,
    }


def replace_placeholder_lines(report_lines, marker, replacement_lines):
    for idx, line in enumerate(report_lines):
        if line == marker:
            report_lines[idx : idx + 1] = list(replacement_lines or [])
            return True
    return False
