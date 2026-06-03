from __future__ import annotations

from pathlib import Path


LEDGER_MODE_REPLAY = "replay"


MARKET_SCENARIOS = [
    {
        "heading": "上证单边上升",
        "holding_action": "强于板块锚点的持仓继续持有；上升趋势：站上MA3并守MA7才允许持有或加仓；冲高后二次不过高、跌回均价线或先于指数翻绿时减仓。",
        "new_action": "只允许对大盘、板块、锚点、个股同时确认的极度看好目标按固定交易窗口条件试错。",
        "forbidden": "不因指数上涨扩大随机仓位，不把旧仓反弹当新机会买点。",
    },
    {
        "heading": "上证震荡",
        "holding_action": "旧仓不能主动走强就按弱处理；反抽优先降风险，避免在噪音里反复交易。",
        "new_action": "明日目标标的保留50%标准进攻预演，只等右侧放量突破并守住均价线。",
        "forbidden": "不把一分钟止跌当买点，不因候选池好看就临盘换仓。",
    },
    {
        "heading": "上证单边下跌",
        "holding_action": "只处理旧仓风险；下降趋势：MA20下方不主动开新仓；跌破计划防守线、反抽不过均价线或同步新低时执行卖出。",
        "new_action": "只保留明日目标标的的条件仓位，至少等下一次V反或W底确认后再评估50%标准进攻预演。",
        "forbidden": "不因跌得多就买，不用新机会抵消旧仓亏损。",
    },
    {
        "heading": "上证M顶",
        "holding_action": "把冲高二次不过高当卖点；M顶：跌破MA7先降风险，跌破MA10认错；跌回均价线或破日内平台时降低隔夜暴露。",
        "new_action": "只保留明日目标标的的条件仓位；只有重新放量突破日内高点并站稳才评估50%标准进攻预演。",
        "forbidden": "不把派发形态误判成进攻延续，不卖飞追回。",
    },
    {
        "heading": "上证W底",
        "holding_action": "W底：第二脚不破低点，站回MA3/MA7后才试；持仓先于指数修复时可继续观察，W失败则先降风险。",
        "new_action": "第二脚确认、站回MA3/MA7、板块锚点止跌后，才允许小仓试错。",
        "forbidden": "不在第一脚低点提前猜底，不为了摊低成本新增仓位。",
    },
    {
        "heading": "上证V反",
        "holding_action": "已降风险的旧仓先看能否强于锚点；V反：先站回MA3，再看MA7是否收复；V反失败时继续防守。",
        "new_action": "只做右侧确认后的买入预演，指数回0、板块止跌、目标承接同时成立才可做。",
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
    return "50%标准进攻预演"


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
            "昨日高惯性/重点观察样本，保留延续观察资格，但不是当前新买按钮；"
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
    pct = position.get("position", position.get("position_pct", None))
    if isinstance(pct, (int, float)):
        return f"{pct:.1f}%"
    if pct not in (None, ""):
        return _clean_text(pct, "-")
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
    if position.get("trade_action") == "做T":
        buy_text = _format_lots(position.get("buy_lots"))
        sell_text = _format_lots(position.get("sell_lots"))
        trade_parts = []
        if buy_text:
            trade_parts.append(f"买入{buy_text}")
        if sell_text:
            trade_parts.append(f"卖出{sell_text}")
        trade_text = f"今日做T{'、'.join(trade_parts)}" if trade_parts else "今日做T"
        return f"{base}，{trade_text}" if base else trade_text
    return base or "-"


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


def render_position_strategy_report(data, target_date, positions, source_report_markdown=""):
    candidates = _extract_extreme_conviction_list(data, source_report_markdown=source_report_markdown)
    tracking_items = _extract_tracking_memory_items(data)
    lines = [
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
