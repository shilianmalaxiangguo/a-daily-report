from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path


LEDGER_MODE_REPLAY = "replay"


MARKET_SCENARIOS = [
    {
        "heading": "上证单边上升",
        "holding_action": "强于板块锚点的持仓继续持有；上升趋势：站上MA3并守MA7才允许持有或加仓；冲高后二次不过高、跌回均价线或先于指数翻绿时减仓。",
        "new_action": "只允许对大盘、板块、锚点、个股同时确认的极度看好目标按固定交易窗口条件执行。",
        "forbidden": "不因指数上涨扩大随机仓位，不把旧仓反弹当新机会买点。",
    },
    {
        "heading": "上证震荡",
        "holding_action": "旧仓不能主动走强就按弱处理；反抽优先降风险，避免在噪音里反复交易。",
        "new_action": "明日目标标的保留50%条件执行，只等右侧放量突破并守住均价线。",
        "forbidden": "不把一分钟止跌当买点，不因候选池好看就临盘换仓。",
    },
    {
        "heading": "上证单边下跌",
        "holding_action": "持仓按防守线独立评估；下降趋势：MA20下方不主动开新仓；跌破计划防守线、反抽不过均价线或同步新低时执行卖出。",
        "new_action": "只保留明日目标标的的条件仓位；若昨晚已决定50%条件执行，下一次V反或W底确认只用于检查执行资格，不满足回到0%。",
        "forbidden": "不因跌得多就买，不用新机会抵消旧仓亏损。",
    },
    {
        "heading": "上证M顶",
        "holding_action": "把冲高二次不过高当卖点；M顶：跌破MA7先降风险，跌破MA10认错；跌回均价线或破日内平台时降低隔夜暴露。",
        "new_action": "只保留明日目标标的的条件仓位；只有重新放量突破日内高点并站稳才按昨晚预案检查执行资格。",
        "forbidden": "不把派发形态误判成进攻延续，不卖飞追回。",
    },
    {
        "heading": "上证W底",
        "holding_action": "W底：第二脚不破低点，站回MA3/MA7后才试；持仓先于指数修复时可继续观察，W失败则先降风险。",
        "new_action": "若昨晚已决定50%条件执行，第二脚确认、站回MA3/MA7、板块锚点止跌后只检查执行资格；不满足回到0%。",
        "forbidden": "不在第一脚低点提前猜底，不为了摊低成本新增仓位。",
    },
    {
        "heading": "上证V反",
        "holding_action": "已降风险的旧仓先看能否强于锚点；V反：先站回MA3，再看MA7是否收复；V反失败时继续防守。",
        "new_action": "只做右侧确认后的买入预演；昨晚已决定的对象在指数回0、板块止跌、目标承接同时成立时才执行，否则取消。",
        "forbidden": "不在第一脚急跌中补仓，不用可能V反取消防守线。",
    },
    {
        "heading": "上证A杀",
        "holding_action": "A杀：放量大跌超7%或同破MA7/MA10，先处理可卖风险仓位；执行条件单或防守线，取消幻想。",
        "new_action": "极端冰点只保留观察，等止跌后的二次确认；不是用新名单救旧仓。",
        "forbidden": "不抄底，不把高波动当机会，不把新名单当救命动作。",
    },
]

MA_EXECUTION_ANCHOR_TEXT = "MA3攻击线 / MA7分歧线 / MA10认错线 / MA20环境线"
MA_CONFIRMATION_TEXT = "成交量确认优先于均线形态"


def _clean_text(value, default="-"):
    text = str(value or "").strip()
    return text if text else default


def _normalize_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def _parse_candidates_from_markdown(markdown_text):
    text = str(markdown_text or "").strip()
    if not text:
        return []
    try:
        from report.decision_ledger import parse_extreme_conviction_list_from_markdown
    except (ImportError, ModuleNotFoundError):
        return []
    return list(parse_extreme_conviction_list_from_markdown(text) or [])


def _source_report_allows_new_position(markdown_text):
    text = str(markdown_text or "")
    if not text.strip():
        return True
    no_new_markers = (
        "新开仓上限 | 0",
        "新开仓0手",
        "明日不新增参与",
        "不构成明日新增参与",
        "最终0%时只作观察样本",
        "先处理旧仓，不新增参与",
    )
    return not any(marker in text for marker in no_new_markers)


def _extract_extreme_conviction_list(data, source_report_markdown=""):
    if source_report_markdown and not _source_report_allows_new_position(source_report_markdown):
        return []
    markdown_candidates = _parse_candidates_from_markdown(source_report_markdown)
    if markdown_candidates:
        return markdown_candidates
    data = data or {}
    contexts = [
        data.get("execution_stage_context") or {},
        data.get("step2_bundle") or {},
    ]
    for context in contexts:
        rows = context.get("extreme_conviction_list") if isinstance(context, dict) else None
        if rows:
            return list(rows)
    artifacts = data.get("decision_ledger_artifacts") or {}
    snapshot = artifacts.get("snapshot") if isinstance(artifacts, dict) else {}
    cases = snapshot.get("cases") if isinstance(snapshot, dict) else None
    if cases:
        return [
            {
                "code": item.get("stock_code"),
                "name": item.get("stock_name"),
                "sector": (item.get("hypothesis") or {}).get("sector_candidate"),
                "conviction_reason": (item.get("hypothesis") or {}).get("stock_setup"),
                "planned_participation": item.get("planned_participation") or {},
            }
            for item in cases
        ]
    return []


def _candidate_name(item):
    return _clean_text(item.get("name") or item.get("stock_name") or item.get("股票"), "-")


def _candidate_code(item):
    return _normalize_code(item.get("code") or item.get("stock_code") or item.get("代码"))


def _candidate_plan(item):
    return item.get("planned_participation") or item.get("participation_script") or {}


def _as_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_extreme_ice_point(data):
    data = data or {}
    for context in (
        data,
        data.get("market_research_snapshot") or {},
        (data.get("market_research_snapshot") or {}).get("state_machine") or {},
    ):
        if isinstance(context, dict) and context.get("market_ice_point") is True:
            return True

    evidence = (
        ((data.get("market_research_snapshot") or {}).get("state_machine") or {}).get("market_performance_evidence")
        or ((data.get("execution_stage_context") or {}).get("market_research_snapshot") or {}).get("market_performance_evidence")
        or {}
    )
    funding = evidence.get("funding_activity") or {}
    new_high = evidence.get("new_high_attack") or {}
    top50_share = _as_float(funding.get("top50_share_pct"))
    new_high_pct = _as_float(new_high.get("all_a_share_pct"))
    return bool(top50_share is not None and top50_share < 18 and new_high_pct is not None and new_high_pct < 1)


def _format_recommended_position(plan):
    attack_state = _clean_text(plan.get("attack_state"), "50%").replace("％", "%")
    if "100" in attack_state:
        return "100%核心进攻候选"
    return "50%条件执行"


def _render_tomorrow_target_lines(candidates, data):
    lines = ["## 明日目标标的", ""]
    if not candidates:
        lines.extend(["- 当前没有明日极度看好候选，明日不设目标标的。", ""])
        return lines
    if _is_extreme_ice_point(data):
        lines.extend(["- 当前属于极端冰点，明日极度看好全部降为观察，不设新买目标标的。", ""])
        return lines

    target = candidates[0]
    plan = _candidate_plan(target)
    name = _candidate_name(target)
    code = _candidate_code(target) or "-"
    sector = _clean_text(target.get("sector") or target.get("所属板块"), "-")
    window = _clean_text(plan.get("buy_window") or plan.get("participation_window"), "09:50-10:10")
    position = _format_recommended_position(plan)
    execution_path = _format_candidate_execution_path(plan)
    fail_action = _format_candidate_fail_action(plan).replace("按0%不参与", "条件不满足回到0%")
    lines.extend(
        [
            "| 目标 | 代码 | 板块 | 推荐仓位 | 参与窗口 | 执行条件 | 失败动作 |",
            "|------|------|------|----------|----------|----------|----------|",
            f"| {name} | {code} | {sector} | {position} | {window} | {execution_path} | {fail_action} |",
            "",
            "- 大盘表现决定用桶、盆还是碗，不取消明日极度看好本身的推荐属性；条件不满足回到0%。",
            "",
        ]
    )
    return lines


def _active_tomorrow_target(candidates, data):
    if candidates and not _is_extreme_ice_point(data):
        return candidates[0]
    target = _extract_current_report_target(data)
    if target and not _is_extreme_ice_point(data):
        return target
    return None


def _position_label(position):
    name = _clean_text(position.get("name") or position.get("stock_name"), "")
    code = _normalize_code(position.get("code") or position.get("stock_code") or position.get("代码"))
    return f"{name}({code})" if name and code else name


def _position_names(positions):
    names = []
    for position in positions or []:
        name = _position_label(position)
        if name:
            names.append(name)
    return names


def _target_label(item):
    if not item:
        return "无"
    name = _candidate_name(item)
    code = _candidate_code(item)
    return f"{name}({code})" if code else name


_STOCK_REF_PATTERN = re.compile(r"([^，,\n|：:]+?)\((\d{6})\)")

_TARGET_PATTERNS = (
    re.compile(r"明日执行对象[：:| ]+([^|\n：:]+?)\((\d{6})\)"),
    re.compile(r"最终对象[：:| ]+明日执行对象[：: ]*([^|\n：:]+?)\((\d{6})\)"),
    re.compile(r"最终对象=([^，,\n|：:]+?)\((\d{6})\)"),
    re.compile(r"最终执行对象[：: ]+([^，,\n|：:]+?)\((\d{6})\)"),
)


def _stock_like_from_value(value):
    if not isinstance(value, dict):
        return {}
    source = value
    if isinstance(value.get("execution_object"), dict):
        source = value.get("execution_object") or {}
    stock = value.get("stock") if isinstance(value.get("stock"), dict) else {}
    name = _clean_text(
        source.get("name")
        or source.get("stock_name")
        or source.get("股票")
        or stock.get("name")
        or stock.get("stock_name"),
        "",
    )
    code = _candidate_code(source) or _candidate_code(stock)
    if not name and not code:
        return {}
    item = dict(source)
    item["name"] = name or code
    item["code"] = code
    sector = _clean_text(source.get("sector") or source.get("所属板块") or source.get("industry") or stock.get("sector"), "")
    if sector:
        item["sector"] = sector
    plan = source.get("planned_participation") if isinstance(source.get("planned_participation"), dict) else {}
    if not plan:
        plan = {
            key: source.get(key)
            for key in ("buy_window", "participation_window", "condition", "fallback_state", "target_position_pct")
            if source.get(key) not in (None, "")
        }
    if plan:
        item["planned_participation"] = plan
    return item


def _selection_workflow_final_target(workflow):
    if not isinstance(workflow, dict):
        return {}
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    target = _stock_like_from_value(final.get("execution_object") if isinstance(final.get("execution_object"), dict) else final)
    if not target:
        return {}
    position_pct = _as_float(final.get("position_pct"))
    if position_pct is not None and position_pct <= 0:
        return {}
    plan = target.get("planned_participation") if isinstance(target.get("planned_participation"), dict) else {}
    plan = dict(plan)
    if final.get("action_text") and not plan.get("attack_state"):
        plan["attack_state"] = str(final.get("action_text"))
    if final.get("fail_action") and not plan.get("fallback_state"):
        plan["fallback_state"] = str(final.get("fail_action"))
    if position_pct is not None and not plan.get("target_position_pct"):
        plan["target_position_pct"] = position_pct
    if plan:
        target["planned_participation"] = plan
    return target


def _extract_current_report_target(data):
    data = data or {}
    containers = [
        data,
        data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {},
        data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {},
    ]
    for context in containers:
        resolution = context.get("final_target_resolution") if isinstance(context, dict) else {}
        if isinstance(resolution, dict):
            for key in ("new_entry_target", "display_target", "ascii_trace_target", "process_target"):
                target = _stock_like_from_value(resolution.get(key))
                if target:
                    return target
        workflow_target = _selection_workflow_final_target(context.get("selection_workflow") if isinstance(context, dict) else {})
        if workflow_target:
            return workflow_target
        for key in ("selected_position_candidate", "current_core_candidate"):
            target = _stock_like_from_value(context.get(key) if isinstance(context, dict) else {})
            if target:
                return target
    return {}


def _extract_report_target_from_markdown(markdown_text):
    text = str(markdown_text or "")
    for pattern in _TARGET_PATTERNS:
        match = pattern.search(text)
        if match:
            return {"name": match.group(1).strip(), "code": match.group(2).strip()}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        label = cells[0]
        value = " | ".join(cells[1:])
        if label in {"最终对象", "明日执行对象", "最终结果"} or "明日执行对象" in label:
            match = _STOCK_REF_PATTERN.search(value)
            if match:
                return {"name": match.group(1).strip(), "code": match.group(2).strip()}
    return {}


def _previous_trade_day(value):
    try:
        current = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    current = current - _dt.timedelta(days=1)
    while current.weekday() >= 5:
        current = current - _dt.timedelta(days=1)
    return current.isoformat()


def _read_previous_report_target(target_date, output_root=None):
    previous = _previous_trade_day(target_date)
    if not previous:
        return {}
    root = Path(output_root) if output_root else Path(__file__).resolve().parents[2] / "reports"
    for suffix in ("_A股日报_执行摘要.md", "_A股日报_完整版.md"):
        path = root / f"{previous}{suffix}"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        target = _extract_report_target_from_markdown(text)
        if target:
            target["source_report_date"] = previous
            return target
    return {}


def _weekday_cn(value):
    try:
        day = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    return ("周一", "周二", "周三", "周四", "周五", "周六", "周日")[day.weekday()]


def _add_trade_days(value, days):
    try:
        current = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    remaining = max(0, int(days))
    while remaining > 0:
        current = current + _dt.timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current.isoformat()


def _add_calendar_days(value, days):
    try:
        current = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    current = current + _dt.timedelta(days=int(days))
    return current.isoformat()


def _date_weekday_label(value):
    text = str(value or "").strip()
    weekday = _weekday_cn(text)
    return f"{text}（{weekday}）" if weekday else text


def _render_day_order_timeline_lines(candidates, data, positions, target_date, previous_report_target=None):
    target = _active_tomorrow_target(candidates, data)
    if not target and isinstance(data, dict):
        target = _extract_report_target_from_markdown(data.get("source_report_markdown", ""))
    holding_names = _position_names(positions)
    previous_report_target = previous_report_target or {}
    if not holding_names and previous_report_target:
        holding_names = [_target_label(previous_report_target)]
    report_day = str(target_date or "").strip()
    has_previous_source = bool((previous_report_target or {}).get("source_report_date"))
    first_day = _add_calendar_days(report_day, -1) if has_previous_source else report_day
    second_day = report_day if has_previous_source else _add_trade_days(report_day, 1)
    third_day = _add_trade_days(report_day, 1) if has_previous_source else _add_trade_days(report_day, 2)
    fourth_day = _add_trade_days(report_day, 2) if has_previous_source else _add_trade_days(report_day, 3)
    first_day_label = _date_weekday_label(first_day)
    second_day_label = _date_weekday_label(second_day)
    third_day_label = _date_weekday_label(third_day)
    fourth_day_label = _date_weekday_label(fourth_day)
    position_context_unknown = (
        isinstance(data, dict)
        and data.get("position_context_provided") is False
        and not holding_names
        and not has_previous_source
    )
    ta_label = "、".join(holding_names) if holding_names else ("待确认旧仓" if position_context_unknown else "空仓")
    tb_label = _target_label(target) if target else "空仓"
    if has_previous_source and holding_names:
        ta_first_text = "上一份日报目标，进入旧仓/旧路径复核"
    elif holding_names:
        ta_first_text = "Ta+0 旧仓占用"
    else:
        ta_first_text = "先确认旧仓" if position_context_unknown else "Ta+0 空仓"
    if holding_names:
        ta_second_text = "Ta+1 继续处理旧仓或取消路径" if has_previous_source else "Ta+1 继续处理旧仓"
    else:
        ta_second_text = "确认后再处理" if position_context_unknown else "空仓"
    tb_second_text = "报告日确认明日目标" if has_previous_source and target else ("Tb+0 明日目标" if target else "没有Tb+0，空仓")
    tb_third_text = "Tb+0 条件买入，不是无条件买入" if has_previous_source and target else ("Tb+1 只按昨晚预案执行或取消" if target else "没有Tb+1，空仓")
    tb_fourth_text = "Tb+1 只按昨晚预案执行或取消" if has_previous_source and target else ("Tb+2 未执行则回到空仓" if target else "空仓")
    tc_third_text = "没有Tc+0，不提前占用"
    tc_fourth_text = "下一份日报再复核" if has_previous_source else "空仓"
    if holding_names and target:
        ta_third_text = "Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理"
        ta_note = "- Ta 表示旧仓占用；有Tb明日目标时，Ta+2 默认按昨晚预案尾盘卖出；只有旧仓失去持有资格、跌破计划线或持续弱于指数时，才提前处理。"
    elif holding_names:
        ta_third_text = "Ta+2 优先处理旧仓，空仓时间尽可能接近全天空仓"
        ta_note = "- Ta 表示旧仓占用；没有Tb+0/没有Tc+0且只剩Ta+2旧仓时，优先处理旧仓，让账户尽可能接近全天空仓；仍有承接的正常持仓按预案尾盘处理。"
    elif position_context_unknown:
        ta_third_text = "持仓确认后再决定"
        ta_note = "- Ta 表示旧仓占用；持仓未输入时，Ta轨道只表示待确认，执行前先确认旧仓情况。"
    else:
        ta_third_text = "空仓"
        ta_note = "- Ta 表示旧仓占用；无旧仓时，Ta轨道保持空仓。"
    timeline_note = (
        "- 顶部长时间轴按日报视角展示：第一列是上一份日报路径在本轮报告前的占用日，报告日确认明日目标，下一交易日是执行日；轨道内继续展示 Ta/Tb/Tc 后续路径。"
        if has_previous_source
        else "- 顶部长时间轴按日报视角展示：第一列是报告日，下一交易日是执行日；轨道内继续展示 Ta/Tb/Tc 后续路径。"
    )

    return [
        "| 轨道 | 标的 | " + " | ".join([first_day_label, second_day_label, third_day_label, fourth_day_label]) + " |",
        "|------|------|" + "|".join(["------"] * 4) + "|",
        (
            f"| Ta旧仓 | {ta_label} | "
            f"{ta_first_text} | "
            f"{ta_second_text} | "
            f"{ta_third_text} | "
            "空仓 |"
        ),
        (
            f"| Tb明日目标 | {tb_label} | 空仓 | "
            f"{tb_second_text} | "
            f"{tb_third_text} | "
            f"{tb_fourth_text} |"
        ),
        (
            "| Tc复核位 | 无 | 空仓 | 空仓 | "
            f"{tc_third_text} | {tc_fourth_text} |"
        ),
        "",
        timeline_note,
        ta_note,
        "- Tb 表示明日目标；Tb+0 是条件买入，不是无条件买入；Tb+1 要继续按昨晚预案处理持有或取消路径；没有明日目标时，必须写明没有Tb+0 / 没有Tb+1。",
        "- Tc 表示下一份日报的复核位；默认不提前占用，必须写明没有Tc+0。",
        "",
    ]


def _item_name(item):
    return _clean_text(item.get("name") or item.get("stock_name") or item.get("股票"), "")


def _item_code(item):
    return _normalize_code(item.get("code") or item.get("stock_code") or item.get("代码"))


def _matches_position(position, item):
    name = _clean_text(position.get("name"), "")
    code = _normalize_code(position.get("code") or position.get("stock_code"))
    if name and name == _item_name(item):
        return True
    if code and code == _item_code(item):
        return True
    return False


def _holding_membership(position, candidates):
    for candidate in candidates:
        if _matches_position(position, candidate):
            return True
    return False


def _get_nested(data, path):
    current = data or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_tracking_memory_items(data):
    status_paths = [
        ("tracking_memory_status",),
        ("execution_stage_context", "tracking_memory_status"),
        ("market_research_snapshot", "tracking_memory_status"),
        ("market_research_snapshot", "observation", "tracking_memory_status"),
        ("report_context", "tracking_memory_status"),
        ("strategy_tracking_context", "tracking_memory_status"),
    ]
    item_keys = [
        "today_validated_items",
        "validated_items",
        "promoted_items",
        "today_tentative_items",
        "tentative_items",
        "new_items",
        "total_items",
    ]
    items = []
    seen = set()
    for path in status_paths:
        status = _get_nested(data, path)
        if not isinstance(status, dict):
            continue
        for key in item_keys:
            for item in status.get(key) or []:
                if not isinstance(item, dict):
                    continue
                marker = (_item_code(item), _item_name(item), str(item.get("last_seen_date") or ""))
                if marker in seen:
                    continue
                seen.add(marker)
                items.append(item)
    return items


def _parse_int(value, default=999):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _is_prior_high_inertia_item(item):
    days_since_seen = _parse_int(item.get("days_since_seen"), default=999)
    if days_since_seen > 1:
        return False
    combined = " ".join(
        str(value or "")
        for value in [
            item.get("status"),
            item.get("follow_state"),
            item.get("last_reason"),
            " ".join(item.get("sources") or []),
        ]
    )
    high_inertia_markers = (
        "高惯性",
        "T字板",
        "涨停",
        "连板",
        "分歧转一致",
        "强异动",
        "板块前排",
        "明日可能加速",
        "观察竞价",
        "回封",
        "打板",
        "leader_memory",
    )
    return any(marker in combined for marker in high_inertia_markers)


def _holding_identity(position, candidates, tracking_items):
    if _holding_membership(position, candidates):
        return "是", "current_extreme"
    for item in tracking_items or []:
        if _matches_position(position, item) and _is_prior_high_inertia_item(item):
            return "昨日高惯性回看", "prior_high_inertia"
    return "否", "ordinary"


def _holding_identity_action(identity_kind):
    if identity_kind == "current_extreme":
        return "当前仍在明日极度看好；先按原参与脚本验证强弱，强于锚点才持有，走弱仍按旧仓风控处理。"
    if identity_kind == "prior_high_inertia":
        return (
            "昨日高惯性/过程观察样本，保留延续观察资格，但不是当前新买按钮；"
            "开盘强攻路径只看急拉、几千万级大单净流入和封板/回封质量，"
            "10点路径看09:50-10:10筹码交换后不再下杀，并站回分时黄线/0轴；"
            "确认失败就降为普通旧仓风控，不为摊低成本加仓。"
        )
    return "不享受极度看好身份；只按旧仓失效、防守线和大盘剧本处理。"


def _format_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:.3f}".rstrip("0").rstrip(".")


def _format_lots(value):
    text = _format_number(value)
    return f"{text}手" if text else ""


def _format_holding_position_text(position):
    def _join_trade_context(base):
        parts = [base] if base else []
        if position.get("trade_action") == "做T":
            buy_text = _format_lots(position.get("buy_lots"))
            sell_text = _format_lots(position.get("sell_lots"))
            trade_parts = []
            if buy_text:
                trade_parts.append(f"买入{buy_text}")
            if sell_text:
                trade_parts.append(f"卖出{sell_text}")
            parts.append(f"今日做T{'、'.join(trade_parts)}" if trade_parts else "今日做T")
        note = _clean_text(position.get("holding_note"), "")
        if note:
            parts.append(note)
        return "，".join(parts) if parts else "-"

    pct = position.get("position", position.get("position_pct", None))
    if isinstance(pct, (int, float)):
        return _join_trade_context(f"{pct:.1f}%")
    if pct not in (None, ""):
        return _join_trade_context(_clean_text(pct, "-"))
    shares = position.get("shares")
    if not shares and position.get("lots") not in (None, ""):
        shares = int(float(position.get("lots")) * 100)
    lots_text = _format_lots(position.get("lots"))
    parts = []
    if lots_text:
        parts.append(lots_text)
    if shares:
        parts.append(f"{shares}股")
    base = "/".join(parts)
    return _join_trade_context(base)


def _render_holding_rows(positions, candidates, tracking_items, scenario):
    rows = []
    for position in positions or []:
        name = _clean_text(position.get("name") or position.get("stock_name"), "-")
        pct_text = _format_holding_position_text(position)
        identity, identity_kind = _holding_identity(position, candidates, tracking_items)
        action = _holding_identity_action(identity_kind)
        rows.append(f"| {name} | {pct_text} | {identity} | {scenario['holding_action']} | {action} |")
    if rows:
        return rows
    return ["| - | - | - | 当前无持仓输入 | 无旧仓处理 |"]


def _format_candidate_execution_path(plan):
    entry_timing = _clean_text(plan.get("entry_timing"), "")
    parts = []
    if entry_timing == "open_core" or str(plan.get("buy_window") or "").startswith("09:30"):
        parts.append("09:30-09:35 开盘强攻/打板入口")
    parts.append("09:50-10:10 筹码交换/分时黄线或0轴确认入口")
    intraday_cross = _clean_text(
        plan.get("intraday_average_line_cross_probe"),
        "09:50-10:10价格与分时黄色均价线交叉并形成金叉，且上穿后不快速跌回黄线下方",
    )
    zero_axis = _clean_text(
        plan.get("zero_axis_reclaim_probe"),
        "水下强势修复到0轴，0轴附近不再放量回落，才算资金重新表态",
    )
    daily_ma = _clean_text(
        plan.get("daily_ma_entry_probe"),
        "逻辑确认后再看MA3/MA7/MA10/MA20：MA3=攻击线，MA7=分歧线，MA10=认错线，MA20=环境线；MA不是买入理由，只是执行锚点和失效参考，仍要叠加分时承接",
    )
    parts.append(intraday_cross)
    parts.append(zero_axis)
    parts.append(daily_ma)
    parts.append("可分两笔：09:50-10:10窗口内先试，站回黄线/0轴或关键日K均线角色确认后再加")
    return "；".join(parts)


def _format_candidate_fail_action(plan):
    fail_action = _clean_text(
        plan.get("cancellation") or plan.get("fallback_state") or "任一确认失败按0%不参与",
        "任一确认失败按0%不参与",
    )
    guard = "不把价格更低本身当买点；10点仍走弱或承接继续扩散，按0%不参与"
    if guard in fail_action:
        return fail_action
    return f"{fail_action}；{guard}"


def _append_execution_path(action_text, execution_path):
    base = _clean_text(action_text, "").rstrip("。；; ")
    if not base:
        return f"执行路径：{execution_path}"
    return f"{base}；执行路径：{execution_path}"


def _render_candidate_rows(candidates, scenario):
    rows = []
    for item in candidates or []:
        plan = _candidate_plan(item)
        name = _candidate_name(item)
        code = _candidate_code(item) or "-"
        sector = _clean_text(item.get("sector") or item.get("所属板块"), "-")
        window = _clean_text(plan.get("buy_window") or plan.get("participation_window"), "按日报参与窗口")
        attack_state = _clean_text(plan.get("attack_state"), "按日报仓位三态")
        reason = _clean_text(item.get("conviction_reason") or item.get("reason"), "-")
        execution_path = _format_candidate_execution_path(plan)
        new_action = _append_execution_path(scenario["new_action"], execution_path)
        fail_action = _format_candidate_fail_action(plan)
        rows.append(
            f"| {name} | {code} | {sector} | {window} | {attack_state} | {new_action} | {fail_action} | {reason} |"
        )
    if rows:
        return rows
    return ["| - | - | - | - | - | 当前无明日极度看好候选 | 不参与 | - |"]


def render_position_strategy_report(data, target_date, positions, source_report_markdown="", output_root=None):
    data = dict(data or {})
    if source_report_markdown:
        data.setdefault("source_report_markdown", source_report_markdown)
    candidates = _extract_extreme_conviction_list(data, source_report_markdown=source_report_markdown)
    tracking_items = _extract_tracking_memory_items(data)
    previous_report_target = _read_previous_report_target(target_date, output_root=output_root)
    lines = [
        *_render_day_order_timeline_lines(candidates, data, positions, target_date, previous_report_target=previous_report_target),
        f"# {target_date} 持仓策略",
        "",
        "## 核心原则",
        "",
        "- 卖出处理和买入处理分开判断。",
        "- 不因新机会而处理旧仓，也不因旧仓处理结果强行开启新仓。",
        "- 明日极度看好是推荐面，不是无条件买入按钮；先选明日目标标的，再用大盘、板块、锚点、个股确认决定容器大小。",
        f"- 买卖点执行锚点：{MA_EXECUTION_ANCHOR_TEXT}；{MA_CONFIRMATION_TEXT}。",
        "- 先有板块/资金/承接资格，再看均线执行锚点。",
        "- 上午做超短主动性，下午做短线确认。",
        "- 0%不参与不是没有策略；不开新仓时也按MA3/MA7/MA10/MA20管理旧仓和观察对象。",
        "",
    ]
    lines.extend(_render_tomorrow_target_lines(candidates, data))
    for scenario in MARKET_SCENARIOS:
        lines.extend(
            [
                f"# {scenario['heading']}",
                "",
                "## 持仓处理",
                "",
                "| 持仓 | 仓位 | 是否在明日极度看好 | 剧本下卖出/持有动作 | 个股身份处理 |",
                "|------|------|--------------------|----------------------|--------------|",
                *_render_holding_rows(positions, candidates, tracking_items, scenario),
                "",
                "## 新机会处理",
                "",
                "| 候选 | 代码 | 板块 | 参与窗口 | 仓位三态 | 剧本下买入动作 | 不满足怎么办 | 理由 |",
                "|------|------|------|----------|----------|----------------|--------------|------|",
                *_render_candidate_rows(candidates, scenario),
                "",
                "## 禁止动作",
                "",
                f"- {scenario['forbidden']}",
                "- 旧仓处理和新机会处理必须分开记录，不能合并成换仓指令。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def get_position_strategy_output_path(target_date, mode="frozen", output_root=None):
    root = Path(output_root) if output_root else Path(__file__).resolve().parents[2] / "reports"
    if mode == LEDGER_MODE_REPLAY:
        root = root / "replay"
    root.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    return str(root / f"{target_date}_持仓策略{suffix}.md")


def save_position_strategy_report(report_text, target_date, mode="frozen", output_root=None):
    path = Path(get_position_strategy_output_path(target_date, mode=mode, output_root=output_root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
    print(f"✅ 持仓策略已保存: {path}")
    return str(path)


__all__ = [
    "MARKET_SCENARIOS",
    "get_position_strategy_output_path",
    "render_position_strategy_report",
    "save_position_strategy_report",
]
