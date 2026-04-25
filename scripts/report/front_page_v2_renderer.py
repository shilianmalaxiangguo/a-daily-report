from __future__ import annotations

from report.reasoning_decision_renderer import render_reasoning_decision_lines
from report.reasoning_decision_support import derive_unique_action_target_from_reasoning_decision
from report.market_research_snapshot_nodes import (
    build_market_research_snapshot_cycle_calendar_node,
    build_market_research_snapshot_cycle_interpretation_node,
    build_market_research_snapshot_lhb_capital_intent_node,
    build_market_research_snapshot_pivot_mainline_interpretation_node,
    derive_market_research_cycle_layer,
)
from report.front_summary_renderer import sanitize_front_page_text
from report.mainline_turnover_summary_support import (
    resolve_double_mainline_summary,
    resolve_turnover_share_trend_rows,
)


FORBIDDEN_FRONT_PAGE_MARKERS = ("### 🔬 市场研究快照", "Step 0")


def _section_between(lines, start_marker, end_marker=None):
    lines = list(lines or [])
    try:
        start = lines.index(start_marker)
    except ValueError:
        return []
    if end_marker is None:
        end = len(lines)
    else:
        try:
            end = lines.index(end_marker, start + 1)
        except ValueError:
            end = len(lines)
    return list(lines[start:end])


def _extract_table(lines, header_line):
    lines = list(lines or [])
    try:
        start = lines.index(header_line)
    except ValueError:
        return []
    table = []
    for line in lines[start:]:
        if not str(line).startswith("|"):
            if table:
                break
            continue
        table.append(line)
    return table


def _strip_heading(lines, heading):
    return [line for line in list(lines or []) if line != heading]


def _append_nonempty(target, lines):
    for line in lines or []:
        if any(marker in str(line) for marker in FORBIDDEN_FRONT_PAGE_MARKERS):
            continue
        target.append(line)


def _market_fit_calibration(snapshot):
    calibration = (snapshot or {}).get("market_fit_calibration") or {}
    return calibration if isinstance(calibration, dict) else {}


def _append_sentence(text, addition):
    text = str(text or "").strip()
    addition = str(addition or "").strip()
    if not addition or addition in text:
        return text
    if text and not text.endswith("。"):
        text = f"{text}。"
    if addition and not addition.endswith("。"):
        addition = f"{addition}。"
    return f"{text}{addition}" if text else addition


def _with_derived_cycle_layer(snapshot):
    snapshot = dict(snapshot or {})
    if (
        snapshot.get("cycle_calendar_rows")
        and snapshot.get("cycle_interpretation_rows")
        and snapshot.get("pivot_mainline_rows")
    ):
        return snapshot
    cycle_layer = derive_market_research_cycle_layer(snapshot, snapshot.get("state_machine") or {})
    for key, value in cycle_layer.items():
        if value and not snapshot.get(key):
            snapshot[key] = value
    return snapshot


def _market_base_lines(report_lines, snapshot=None):
    lines = _section_between(report_lines, "## 二、市场基底", "## 三、周期与主线")
    calibration = _market_fit_calibration(snapshot)
    fit_label = str(calibration.get("fit_label") or "").strip()
    if not lines or not fit_label:
        return lines
    if any("| 市场贴合度 |" in str(line) for line in lines):
        return lines

    injected = []
    inserted = False
    for line in lines:
        injected.append(line)
        if not inserted and str(line).startswith("| 市场状态 |"):
            injected.append(f"| 市场贴合度 | {fit_label} |")
            inserted = True
    if inserted:
        return injected

    try:
        index = injected.index("### 2. 市场状态结论")
    except ValueError:
        injected.extend([
            "### 2. 市场状态结论",
            "| 项目 | 结论 |",
            "|------|------|",
            f"| 市场贴合度 | {fit_label} |",
        ])
        return injected

    insert_at = index + 1
    while insert_at < len(injected) and str(injected[insert_at]).startswith("|"):
        insert_at += 1
    injected.insert(insert_at, f"| 市场贴合度 | {fit_label} |")
    return injected


def _discipline_table(final_gate=None, position_level=""):
    final_gate = final_gate or {}
    final_action = str(final_gate.get("final_action") or "先观察，等10点确认")
    if final_gate.get("can_new_entry"):
        conclusion = "主线内小仓试错"
    elif "空仓" in final_action or "禁止" in final_action:
        conclusion = "空仓等待"
    else:
        conclusion = "轻仓观察"
    return [
        "## 一、交易纪律",
        "| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |",
        "|----------|----------|----------|----------|----------|",
        f"| {conclusion} | 09:50-10:10确认，10:00左右处理买卖 | 仅量化电风扇行情允许尾盘试错，次日高开兑现 | 单笔最晚-5%，不能大亏 | {position_level or '先看市场底色'}；先看周期主线，只在主线个股上做小亏小赚偶尔大赚 |",
        "",
    ]


def _double_mainline_lines(snapshot):
    summary = resolve_double_mainline_summary(snapshot.get("mainline_turnover_summary") or {})
    if not summary:
        summary = resolve_double_mainline_summary(snapshot)
    if not summary:
        summary = {"cycle_mainline": "-", "daily_attack_line": "-", "relationship": "主线待确认", "tomorrow_action": "10点确认，不满足空仓"}
    return [
        "### 4. 双层主线结论",
        "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |",
        "|----------|------------|----------|----------|",
        "| {cycle_mainline} | {daily_attack_line} | {relationship} | {tomorrow_action} |".format(**summary),
        "",
    ]


def _turnover_share_lines(snapshot):
    rows = resolve_turnover_share_trend_rows(snapshot)
    lines = [
        "### 5. 主线成交额占比趋势",
        "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |",
        "|------|----------|------------|------------|------------|------|----------|------|",
    ]
    if rows:
        for row in rows:
            lines.append(
                "| {date} | {cycle_mainline} | {daily_attack_line} | {mainline_turnover} | {market_turnover} | {share} | {share_change} | {interpretation} |".format(**row)
            )
    else:
        lines.append("| 今日 | - | - | 数据暂缺 | - | 待累计 | 待累计 | 今天开始记录，后续日报自动累计 |")
    lines.append("")
    return lines


def _cycle_calendar_lines(snapshot):
    lines = build_market_research_snapshot_cycle_calendar_node(snapshot).get("lines", [])
    if lines:
        return lines
    return [
        "### 1. 周期日历主视图",
        "| 周次 | 一 | 二 | 三 | 四 | 五 |",
        "|------|------|------|------|------|------|",
        "| 当前周期 | 主线待累计 | 主线待累计 | 主线待累计 | 主线待累计 | 主线待累计 |",
    ]


def _cycle_interpretation_lines(snapshot):
    calibration = _market_fit_calibration(snapshot)
    cycle_note = calibration.get("cycle_note") or ""
    if cycle_note and snapshot.get("cycle_interpretation_rows"):
        snapshot = dict(snapshot)
        rows = []
        for row in snapshot.get("cycle_interpretation_rows") or []:
            if isinstance(row, dict):
                row = dict(row)
                row["interpretation"] = _append_sentence(row.get("interpretation"), cycle_note)
            rows.append(row)
        snapshot["cycle_interpretation_rows"] = rows
    lines = build_market_research_snapshot_cycle_interpretation_node(snapshot).get("lines", [])
    if lines:
        return lines
    summary = resolve_double_mainline_summary(snapshot.get("mainline_turnover_summary") or {}) or resolve_double_mainline_summary(snapshot) or {}
    mainline = summary.get("cycle_mainline") or (snapshot.get("state_machine") or {}).get("leading_line") or "主线待确认"
    return [
        "### 2. 周期解读",
        "| 周期 | 时间段 | 交易日数 | 主导主线 | 市场状态 | 周期解读 |",
        "|------|------|------|------|------|------|",
        f"| 当前周期 | 待累计 | 待累计 | {mainline} | 待确认 | {_append_sentence('周期数据不足，先记录当前主线，后续日报继续补齐趋势。', cycle_note)} |",
    ]


def _pivot_mainline_lines(snapshot):
    lines = build_market_research_snapshot_pivot_mainline_interpretation_node(snapshot).get("lines", [])
    if lines:
        return lines
    summary = resolve_double_mainline_summary(snapshot.get("mainline_turnover_summary") or {}) or resolve_double_mainline_summary(snapshot) or {}
    mainline = summary.get("cycle_mainline") or (snapshot.get("state_machine") or {}).get("leading_line") or "主线待确认"
    return [
        "### 3. 中枢与主线解读",
        "| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 结构解读 |",
        "|------|------|------|------|------|------|------|------|------|",
        f"| 待累计 | 日线中枢 | 待累计 | 待确认 | {mainline} | 待确认 | 待确认 | 待确认 | 中枢与主线映射数据不足，先不放大结论，只保留观察。 |",
    ]


def _capital_intent_lines(snapshot):
    lines = ["## 四、资金意图"]
    snapshot = _normalize_capital_intent_snapshot(snapshot)
    capital_lines = build_market_research_snapshot_lhb_capital_intent_node(snapshot).get("lines", [])
    if capital_lines:
        for line in capital_lines:
            if line == "#### 龙虎榜资金状态":
                lines.append("### 1. 龙虎榜资金状态")
            elif line == "#### 资金结论":
                lines.append("### 2. 资金结论")
            else:
                lines.append(line)
    else:
        lines.extend([
            "### 1. 龙虎榜资金状态",
            "| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |",
            "|----------|----------|----------|----------|----------|----------|",
            "| - | - | - | - | - | - |",
            "### 2. 资金结论",
            "| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |",
            "|--------------|--------------|------------------|",
            "| - | - | - |",
        ])
    lines.append("")
    return lines


def _normalize_capital_intent_snapshot(snapshot):
    snapshot = dict(snapshot or {})
    status = snapshot.get("lhb_capital_status")
    if isinstance(status, list):
        first = next((item for item in status if isinstance(item, dict)), {})
        snapshot["lhb_capital_status"] = {
            "capital_strength": first.get("capital_strength") or first.get("strength") or "-",
            "capital_intensity": first.get("capital_intensity") or first.get("state") or "-",
            "capital_direction": first.get("capital_direction") or first.get("direction") or "-",
            "capital_intent": first.get("capital_intent") or first.get("intent") or "-",
            "style_shift": first.get("style_shift") or first.get("style") or "-",
            "event_attribute": first.get("event_attribute") or first.get("event") or "龙虎榜资金行为",
        }
    conclusion = snapshot.get("capital_conclusion")
    if isinstance(conclusion, list):
        first = next((item for item in conclusion if isinstance(item, dict)), {})
        snapshot["capital_conclusion"] = {
            "current_capital_state": first.get("current_capital_state") or first.get("conclusion") or "-",
            "mainline_attitude": first.get("mainline_attitude") or first.get("evidence") or "-",
            "tomorrow_action_meaning": first.get("tomorrow_action_meaning") or first.get("action") or "-",
        }
    return snapshot


def _split_md_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _convert_legacy_core_table(table):
    if not table:
        return []
    converted = [
        "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
        "|------|------|----------|--------------|-----------|------|----------|----------|",
    ]
    for row in table[2:]:
        cells = _split_md_row(row)
        if len(cells) < 6:
            continue
        name, code, sector, reason, focus, qualification = cells[:6]
        converted.append(f"| {name} | {code} | {sector} | - | - | {focus} | {reason} | {qualification} |")
    return converted


def _effective_unique_action_target(snapshot):
    snapshot = snapshot or {}
    target = snapshot.get("unique_action_target") or {}
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        return target
    return derive_unique_action_target_from_reasoning_decision(snapshot)


def _has_unique_action_target(snapshot):
    target = _effective_unique_action_target(snapshot)
    return isinstance(target, dict) and bool(target.get("name") or target.get("code"))


def _candidate_lines(report_lines, snapshot=None):
    core_header = "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |"
    legacy_core_header = "| 股票 | 代码 | 所属方向 | 为什么看 | 明天重点看什么 | 执行权 |"
    cross_header = "| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |"
    core_title = "### 1. 主线内可执行候选" if _has_unique_action_target(snapshot) else "### 1. 主线内观察候选"
    lines = ["## 五、个股解读", core_title]
    core_table = _extract_table(report_lines, core_header)
    if not core_table:
        core_table = _convert_legacy_core_table(_extract_table(report_lines, legacy_core_header))
    lines.extend(core_table or [core_header, "|------|------|----------|--------------|-----------|------|----------|----------|", "| 暂无 | - | - | - | - | 10点确认市场是否重新打开 | 暂无主线资格 | 不做 |"])
    lines.extend(["", "### 2. 跨线观察候选"])
    cross_table = _extract_table(report_lines, cross_header)
    lines.extend(cross_table or [cross_header, "|------|------|----------|----------|----------|", "| 暂无 | - | - | 只看资金是否外溢 | 不给买入指令 |"])
    lines.extend([
        "",
        "### 3. 个股结论",
        "| 主线内唯一重点 | 跨线对象定位 | 动作原则 |",
        "|----------------|--------------|----------|",
        "| 只看主线核心承接 | 跨线只用于判断资金是否外溢 | 10点附近确认，买点等60分钟，买后30分钟结构止损 |",
        "",
    ])
    return lines


def _unique_action_target_lines(snapshot):
    target = _effective_unique_action_target(snapshot)
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        name = str(target.get("name") or "唯一对象").strip()
        code = str(target.get("code") or "-").strip()
        label = f"{name}({code})" if code and code != "-" else name
        condition = str(target.get("condition") or "主线确认 + 承接 + 60分钟确认").strip()
    else:
        label = "暂无"
        condition = "主线确认 + 承接 + 60分钟确认未同时满足"
    return [
        "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
        "|--------------|------|------|--------------|",
        f"| 只看唯一对象 | {label} | {condition} | 不做 |",
        "",
    ]


def _execution_plan_lines(snapshot=None):
    decision_lines = render_reasoning_decision_lines((snapshot or {}).get("reasoning_decision"))
    return [
        "## 六、明日执行计划",
        *decision_lines,
        *_unique_action_target_lines(snapshot),
        "| 时间窗口 | 要看什么 | 买入权限 | 卖出/风控 | 结论 |",
        "|----------|----------|----------|-----------|------|",
        "| 09:25-09:40 | 竞价强弱、主线核心是否被核、跌停扩散 | 默认无 | 有旧仓先看是否需要降风险 | 不抢 |",
        "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 仅主线核心可进入观察买点 | 10:00左右处理弱仓/错仓 | 核心确认窗口 |",
        "| 10:00左右卖 | 弱仓、错仓、破结构仓位 | 无 | 该卖就卖，不做自救 | 防大亏 |",
        "| 10:00左右买 | 只看周期主线核心，且必须有承接 | 满足60分钟确认才允许 | 买后用30分钟结构止损 | 小仓或不开 |",
        "| 午后 | 看主线是否延续，不追轮动末端 | 默认谨慎 | 若走弱继续降风险 | 不扩大试错 |",
        "| 尾盘 | 只判断是否量化电风扇行情 | 仅电风扇行情例外，次日高开兑现 | 非电风扇不尾盘开新仓 | 例外，不是常规 |",
        "",
    ]


def _final_summary_lines(report_lines, snapshot, final_gate=None):
    final_gate = final_gate or {}
    cycle = (snapshot.get("mainline_turnover_summary") or {}).get("current_mainline") or (snapshot.get("state_machine") or {}).get("leading_line") or "-"
    daily = (snapshot.get("mainline_turnover_summary") or {}).get("current_mainline") or cycle
    action = str(final_gate.get("final_action") or "10点确认，不满足就空仓")
    target = _effective_unique_action_target(snapshot)
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        target_name = str(target.get("name") or "唯一对象").strip()
        target_code = str(target.get("code") or "").strip()
        unique_target = f"{target_name}({target_code})" if target_code else target_name
        one_line_action = f"只看{unique_target}，条件不满足就不做；绝不为了不确定性承担大亏"
    else:
        unique_target = "暂无"
        one_line_action = "没有唯一对象就不做；绝不为了不确定性承担大亏"
    return [
        "## 七、最终结论",
        "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
        "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
        f"| {action} | 不确定时不值得主动参与 | {cycle} | {daily} | 先看市场基底 | {unique_target} | 空仓 / 短线确认 | {one_line_action} |",
    ]


def render_front_page_v2(report_lines, *, target_date="", market_research_snapshot=None, final_gate=None, position_level=""):
    report_lines = list(report_lines or [])
    snapshot = _with_derived_cycle_layer(market_research_snapshot or {})
    lines = [f"# {target_date} a股市场分析" if target_date else "# a股市场分析", ""]
    lines.extend(_discipline_table(final_gate=final_gate, position_level=position_level))
    market_base = _market_base_lines(report_lines, snapshot)
    lines.extend(market_base or ["## 二、市场基底", "| 项目 | 结论 |", "|------|------|", "| 市场状态 | 待确认 |", ""])
    if lines and lines[-1] != "":
        lines.append("")

    lines.append("## 三、周期与主线")
    _append_nonempty(lines, _cycle_calendar_lines(snapshot))
    _append_nonempty(lines, _cycle_interpretation_lines(snapshot))
    _append_nonempty(lines, _pivot_mainline_lines(snapshot))
    lines.extend(_double_mainline_lines(snapshot))
    lines.extend(_turnover_share_lines(snapshot))

    lines.extend(_capital_intent_lines(snapshot))
    lines.extend(_candidate_lines(report_lines, snapshot))
    lines.extend(_execution_plan_lines(snapshot))
    lines.extend(_final_summary_lines(report_lines, snapshot, final_gate=final_gate))
    lines = [line for line in lines if not any(marker in str(line) for marker in FORBIDDEN_FRONT_PAGE_MARKERS)]
    return sanitize_front_page_text(lines)
