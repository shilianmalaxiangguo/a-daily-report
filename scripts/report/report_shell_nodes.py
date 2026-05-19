from knowledge.trading_philosophy import PARTICIPATION_WINDOW_LAYER_TEXT


def build_report_shell_preamble_node(context, node_meta=None, node_lookup=None):
    use_report_preamble = context["use_report_preamble"]
    return {
        "lines": list(
            use_report_preamble(
                context.get("target_date"),
                run_mode=context.get("run_mode", "frozen"),
                has_personal_positions=bool(context.get("has_personal_positions", False)),
                compact=bool(context.get("compact", False)),
            )
            or []
        ),
        "exports": {},
        "module_logs": [],
    }


def build_report_shell_discipline_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 一、交易纪律"], "exports": {}, "module_logs": []}


def build_report_shell_blank_node(context, node_meta=None, node_lookup=None):
    return {"lines": [""], "exports": {}, "module_logs": []}


def build_report_shell_discipline_placeholder_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["<!-- PROHIBITION_PLACEHOLDER -->"], "exports": {}, "module_logs": []}


def build_report_shell_market_base_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", "## 二、市场基底"], "exports": {}, "module_logs": []}


def build_report_shell_market_base_placeholder_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["<!-- FRONT_PAGE_MARKET_BASE_PLACEHOLDER -->"], "exports": {}, "module_logs": []}


def build_report_shell_cycle_mainline_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", "## 三、周期与主线", "<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->"], "exports": {}, "module_logs": []}


def build_report_shell_cycle_calendar_placeholder_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": ["", "### 1. 周期日历主视图", "<!-- FRONT_PAGE_CYCLE_CALENDAR_PLACEHOLDER -->"],
        "exports": {},
        "module_logs": [],
    }


def build_report_shell_cycle_interpretation_placeholder_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": ["", "### 2. 周期解读", "<!-- FRONT_PAGE_CYCLE_INTERPRETATION_PLACEHOLDER -->"],
        "exports": {},
        "module_logs": [],
    }


def build_report_shell_pivot_mainline_placeholder_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": ["", "### 3. 中枢与主线解读", "<!-- FRONT_PAGE_PIVOT_MAINLINE_PLACEHOLDER -->"],
        "exports": {},
        "module_logs": [],
    }


def build_report_shell_capital_intent_placeholder_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", "<!-- FRONT_PAGE_CAPITAL_INTENT_PLACEHOLDER -->"], "exports": {}, "module_logs": []}


def build_report_shell_stock_interpretation_placeholder_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", "<!-- FRONT_PAGE_STOCK_INTERPRETATION_PLACEHOLDER -->"], "exports": {}, "module_logs": []}


def build_report_shell_execution_plan_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", "## 六、明日执行计划", "<!-- STEP0_FOLLOW_PLACEHOLDER -->"], "exports": {}, "module_logs": []}


def build_report_shell_final_summary_placeholder_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", "<!-- FRONT_PAGE_FINAL_SUMMARY_PLACEHOLDER -->"], "exports": {}, "module_logs": []}


def _build_prohibition_payload(
    display_position_level,
    display_operation_state,
    environment_headline="",
    has_personal_positions=False,
    final_gate=None,
    main_sectors=None,
    exit_analysis=None,
):
    final_gate = final_gate or {}
    main_sectors = main_sectors or []
    exit_analysis = exit_analysis or {}

    payload = {
        "environment_line": "",
        "prohibition_items": [],
        "allowed_items": [],
        "risk_line": "",
    }

    if display_position_level == "一档（空仓档）":
        headline = environment_headline or "环境关闭，只做等待，不做新增参与"
        payload["environment_line"] = f"**次日市场环境**: {display_position_level} / {display_operation_state} - {headline}"
        payload["prohibition_items"].append("- ✅ 禁止新开仓：当前不允许新增任何买入")
        if has_personal_positions:
            payload["prohibition_items"].append("- ✅ 禁止恋战：你的现有仓位只做退出，不做摊平和自救")
        else:
            payload["prohibition_items"].append("- ✅ 禁止恋战：若你有旧仓，只做退出，不做摊平和自救")
        payload["prohibition_items"].append("- ✅ 禁止买入任何方向：无论题材多热，都先等环境重新打开")
        payload["prohibition_items"].append("- ✅ 禁止追高：不追涨任何股票")
        payload["prohibition_items"].append("- ✅ 禁止做T：次日不做日内回转")
        payload["prohibition_items"].append("- ✅ 禁止模式外交易：不在主线里的票不碰")
    elif display_position_level == "二档（防守档）":
        headline = environment_headline or "先看特殊标的是否继续抗跌，只保留观察与参与窗口预演"
        payload["environment_line"] = f"**次日市场环境**: 0%观察 / {display_operation_state} - {headline}"
        if final_gate.get("allow_attack_50_ready") and not final_gate.get("should_reduce"):
            payload["prohibition_items"].append(f"- ⚠️ 不抢跑：确认前按0%观察；{PARTICIPATION_WINDOW_LAYER_TEXT}，命中预演情境才评估50%标准进攻")
        else:
            payload["prohibition_items"].append("- ✅ 禁止新开仓：当前按0%不参与，未形成参与窗口前不新增")
        if final_gate.get("should_reduce"):
            if has_personal_positions:
                payload["prohibition_items"].append("- ✅ 禁止抱弱留弱：你的旧仓里，不在最强趋势的票要优先处理")
            else:
                payload["prohibition_items"].append("- ✅ 禁止抱弱留弱：若你有旧仓，不在最强趋势里的票要优先处理")
        if main_sectors:
            primary_mainline = main_sectors[0]
            secondary_hint = main_sectors[1] if len(main_sectors) >= 2 else ""
            if secondary_hint and secondary_hint != primary_mainline:
                payload["prohibition_items"].append(f"- ⚠️ 主攻线只盯{primary_mainline}；{secondary_hint}只作竞争观察，不当执行方向")
            else:
                payload["prohibition_items"].append(f"- ⚠️ 只盯主攻线{primary_mainline}里最强的票：主线弱化时，杂毛先淘汰")
        payload["prohibition_items"].append("- ✅ 禁止追高：不买昨天或大前天的最高点个股")
        payload["prohibition_items"].append("- ✅ 禁止做T：次日只买一种，不做日内回转")
        payload["prohibition_items"].append("- ✅ 禁止模式外交易：不在主线板块里的票不碰")
        if final_gate.get("should_reduce"):
            if has_personal_positions:
                payload["allowed_items"].append("- ✅ 持有：你的旧仓里，只允许继续拿仍在主线、仍有承接、仍在趋势里的最强票")
                payload["allowed_items"].append("- ✅ 卖出：你的旧仓一旦转弱、失承接、跌破结构就卖，不犹豫")
            else:
                payload["allowed_items"].append("- ✅ 持有：若你有旧仓，只允许继续拿仍在主线、仍有承接、仍在趋势里的最强票")
                payload["allowed_items"].append("- ✅ 卖出：若你有旧仓，一旦转弱、失承接、跌破结构就卖，不犹豫")
        else:
            if has_personal_positions:
                payload["allowed_items"].append("- ✅ 持有：你的现有强仓在主线未走坏前可继续持有")
                payload["allowed_items"].append("- ✅ 卖出：你的持仓在大阳线或触及止损线时卖出")
                if final_gate.get("allow_attack_50_ready"):
                    payload["allowed_items"].append(f"- 🟡 参与窗口：{PARTICIPATION_WINDOW_LAYER_TEXT}，命中预演情境才评估50%标准进攻")
            else:
                payload["allowed_items"].append("- ✅ 持有：若你有强仓，在主线未走坏前可继续持有")
                payload["allowed_items"].append("- ✅ 卖出：若你有仓位，在大阳线或触及止损线时卖出")
                if final_gate.get("allow_attack_50_ready"):
                    payload["allowed_items"].append(f"- 🟡 参与窗口：{PARTICIPATION_WINDOW_LAYER_TEXT}，命中预演情境才评估50%标准进攻")
    else:
        headline = environment_headline or "环境条件满足不等于立刻下单，先看特殊标的，再等市场缩到唯一对象"
        payload["environment_line"] = f"**次日市场环境**: {display_position_level} / {display_operation_state} - {headline}"
        payload["prohibition_items"].append("- ✅ 禁止追高：不买昨天或大前天的最高点个股")
        payload["prohibition_items"].append("- ✅ 禁止做T：次日只买一种，不做日内回转")
        payload["prohibition_items"].append("- ✅ 禁止模式外交易：不在主线板块里的票不碰")
        payload["prohibition_items"].append("- ✅ 禁止一看到市场转强就直接下单：没有缩到一只可买股之前，一律不开仓")
        payload["allowed_items"].append("- ✅ 先看特殊标的：先判断它们是深跌还是抗跌，再决定这轮调整是继续收还是重新攻")
        payload["allowed_items"].append("- ✅ 新开仓前提：只有缩到一只可买股时，才允许按计划买入")
        if has_personal_positions:
            payload["allowed_items"].append("- ✅ 持有：你的现有仓位继续持有")
            payload["allowed_items"].append("- ✅ 卖出：你的持仓在大阳线或触及止损线时卖出")
        else:
            payload["allowed_items"].append("- ✅ 持有：若你有仓位，可继续持有")
            payload["allowed_items"].append("- ✅ 卖出：若你有仓位，在大阳线或触及止损线时卖出")

    risk_sectors = exit_analysis.get("risk_sectors", [])
    if risk_sectors:
        payload["risk_line"] = f"**风险板块（禁止碰）**: {'、'.join(risk_sectors[:5])}"
    return payload


def build_prohibition_environment_node(context, node_meta=None, node_lookup=None):
    payload = context["prohibition_payload"]
    lines = [payload["environment_line"]] if payload.get("environment_line") else []
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_prohibition_header_node(context, node_meta=None, node_lookup=None):
    payload = context["prohibition_payload"]
    return {"lines": ["**禁止事项**:"] if payload.get("prohibition_items") else [], "exports": {}, "module_logs": []}


def build_prohibition_items_node(context, node_meta=None, node_lookup=None):
    return {"lines": list(context["prohibition_payload"].get("prohibition_items") or []), "exports": {}, "module_logs": []}


def build_allowed_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["**允许事项**:"] if context["prohibition_payload"].get("allowed_items") else [], "exports": {}, "module_logs": []}


def build_allowed_items_node(context, node_meta=None, node_lookup=None):
    return {"lines": list(context["prohibition_payload"].get("allowed_items") or []), "exports": {}, "module_logs": []}


def build_risk_section_node(context, node_meta=None, node_lookup=None):
    risk_line = context["prohibition_payload"].get("risk_line")
    return {"lines": [risk_line] if risk_line else [], "exports": {}, "module_logs": []}
