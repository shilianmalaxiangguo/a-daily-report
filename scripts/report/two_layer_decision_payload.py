from __future__ import annotations

from report.sniper_target_derivation import clean_text, normalize_stock_code


SCHEMA_VERSION = "two_layer_daily_decision.v1"
EMPTY_STOCK_TEXTS = {"", "-", "无", "暂无", "不做", "无明日执行对象", "无执行对象", "无执行目标"}


def _safe_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").replace("亿", "").strip())
    except (TypeError, ValueError):
        return default


def _stock_payload(value):
    if not isinstance(value, dict):
        return {}
    name = clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    code = normalize_stock_code(
        value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol")
    )
    if not code and name in EMPTY_STOCK_TEXTS:
        return {}
    if not (name or code):
        return {}
    payload = {"name": name, "code": code}
    sector = clean_text(
        value.get("sector")
        or value.get("sector_name")
        or value.get("industry")
        or value.get("板块")
        or value.get("所属行业")
    )
    if sector:
        payload["sector"] = sector
    for numeric_key in ("market_value", "turnover_amount", "amount"):
        if numeric_key in value:
            payload[numeric_key] = value.get(numeric_key)
    return payload


def _stock_label(value):
    payload = _stock_payload(value)
    name = payload.get("name", "")
    code = payload.get("code", "")
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def _first_stock(*values):
    for value in values:
        payload = _stock_payload(value)
        if payload:
            return payload
    return {}


def _first_context_stock(execution_stage_context, key):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    for item in _context_list(context, key):
        payload = _stock_payload(item)
        if payload:
            return payload
    return {}


def _capital_priority(final_target_resolution):
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    decision = resolution.get("capital_priority_decision")
    if not isinstance(decision, dict):
        return ""
    return clean_text(decision.get("capital_priority"))


def _execution_priority_allows_b_level(priority, position_decision):
    priority = clean_text(priority)
    if priority in {"wait", "old_position_t", "old_position", "existing_position", "existing_position_t"}:
        return False
    if priority in {"new_entry", "new_entry_after_old_exit", "tradable_proxy"}:
        return True
    return _position_pct(position_decision) >= 50


def _position_pct(position_decision):
    position_decision = position_decision if isinstance(position_decision, dict) else {}
    for key in ("target_position_pct", "position_pct", "position_plan_pct"):
        if key not in position_decision:
            continue
        try:
            return int(float(str(position_decision.get(key)).replace("%", "").strip()))
        except (TypeError, ValueError):
            continue
    return 0


def _money_bucket(target):
    target = target if isinstance(target, dict) else {}
    market_value = _safe_float(target.get("market_value"))
    turnover_amount = _safe_float(target.get("turnover_amount") or target.get("amount"))
    if market_value >= 300_000_000_000 or turnover_amount >= 10_000_000_000:
        return {
            "money_bucket": "大市值或高成交核心",
            "money_confirmation": "分时大单净流入1亿+，并保持VWAP上方",
        }
    return {
        "money_bucket": "小中盘活跃股",
        "money_confirmation": "分时大单净流入3000w-5000w，并保持VWAP上方",
    }


def _build_b_level_conditions(target):
    active_attack = _money_bucket(target)
    active_attack["money_threshold_policy"] = "小中盘活跃股3000w-5000w；大市值或高成交核心1亿+"
    active_attack["money_confirmation"] = (
        "分时大单净流入3000w-5000w（小中盘活跃股）；"
        "大市值或高成交核心需1亿+，并保持VWAP上方"
    )
    active_attack.update(
        {
            "trigger": "主动进攻型",
            "window": "09:30-09:35或09:50-10:10",
            "price_action": "开盘直线进攻，不快速冲高回落",
            "intraday_hold": "VWAP上方保持，短暂震荡后要快速收回",
            "action": "B档执行",
        }
    )
    return {
        "low_open_acceptance": {
            "trigger": "低开承接型",
            "window": "09:50-10:10",
            "daily_structure": "靠近MA5、不有效跌破MA5，或跌破后快速收回MA5",
            "intraday_reclaim": "收回VWAP或0轴并能站住",
            "action": "B档执行",
        },
        "active_attack": active_attack,
        "invalidations": [
            "MA5未收回",
            "VWAP/0轴未收回",
            "资金确认不足",
            "市场或相关方向明显走弱",
        ],
    }


def _context_list(context, key):
    value = context.get(key) if isinstance(context, dict) else None
    return value if isinstance(value, list) else []


def _process_candidates_from_context(execution_stage_context):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    bundle = context.get("step2_bundle") if isinstance(context.get("step2_bundle"), dict) else {}
    candidates = []
    for key in (
        "core_stocks",
        "secondary_stocks",
        "crossline_observation_stocks",
        "gem_observation_stocks",
    ):
        for item in _context_list(bundle, key):
            payload = _stock_payload(item)
            if payload:
                candidates.append(payload)
    for key in ("executable_stocks", "waiting_stocks", "rejected_stocks"):
        for item in _context_list(context, key):
            payload = _stock_payload(item)
            if payload:
                candidates.append(payload)
    return candidates


def _dedupe_labels(items):
    labels = []
    seen = set()
    for item in items:
        label = _stock_label(item)
        if label == "暂无" or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def _stock_key(value):
    payload = _stock_payload(value)
    return payload.get("code") or payload.get("name") or ""


def _same_stock(left, right):
    left_payload = _stock_payload(left)
    right_payload = _stock_payload(right)
    left_code = left_payload.get("code")
    right_code = right_payload.get("code")
    if left_code and right_code:
        return left_code == right_code
    left_name = left_payload.get("name")
    right_name = right_payload.get("name")
    return bool(left_name and right_name and left_name == right_name)


def _candidate_text(value, *keys):
    if not isinstance(value, dict):
        return ""
    for key in keys:
        text = clean_text(value.get(key))
        if text:
            return text
    return ""


def _candidate_payload(value, source):
    stock = _stock_payload(value)
    if not stock:
        return {}
    value = value if isinstance(value, dict) else {}
    pool_source = clean_text(source, "候选池")
    payload = {"stock": stock, "pool_source": pool_source, "pool_sources": [pool_source]}
    for key in (
        "reason",
        "conviction_reason",
        "stock_structure",
        "structure",
        "pattern",
        "funds_confirmation",
        "fund_confirmation",
        "money_confirmation",
        "account_fit",
        "risk_missing_data",
        "risk",
        "mainline_sector",
    ):
        if key in value:
            payload[key] = value.get(key)
    missing_data = value.get("missing_data") or value.get("missing_fields")
    if isinstance(missing_data, list):
        payload["missing_data"] = [clean_text(item) for item in missing_data if clean_text(item)]
    elif clean_text(missing_data):
        payload["missing_data"] = [clean_text(missing_data)]
    return payload


def _merge_pool_sources(existing, payload):
    sources = []
    for source in list(existing.get("pool_sources") or []) + [existing.get("pool_source")]:
        source = clean_text(source)
        if source and source not in sources:
            sources.append(source)
    for source in list(payload.get("pool_sources") or []) + [payload.get("pool_source")]:
        source = clean_text(source)
        if source and source not in sources:
            sources.append(source)
    if not sources:
        sources = ["候选池"]
    existing["pool_sources"] = sources
    existing["pool_source"] = "、".join(sources)


def _append_candidate(entries, seen, candidate, source):
    payload = _candidate_payload(candidate, source)
    if not payload:
        return
    key = _stock_key(payload.get("stock"))
    if key and key in seen:
        existing = entries[seen[key]]
        _merge_pool_sources(existing, payload)
        existing_stock = existing.get("stock") if isinstance(existing.get("stock"), dict) else {}
        payload_stock = payload.get("stock") if isinstance(payload.get("stock"), dict) else {}
        for field, value in payload_stock.items():
            if value and not existing_stock.get(field):
                existing_stock[field] = value
        existing["stock"] = existing_stock
        for field in (
            "reason",
            "conviction_reason",
            "stock_structure",
            "structure",
            "pattern",
            "funds_confirmation",
            "fund_confirmation",
            "money_confirmation",
            "account_fit",
            "risk_missing_data",
            "risk",
            "mainline_sector",
        ):
            if field in payload and not clean_text(existing.get(field)):
                existing[field] = payload[field]
        if payload.get("missing_data"):
            missing_data = list(existing.get("missing_data") or [])
            for item in payload.get("missing_data") or []:
                if item not in missing_data:
                    missing_data.append(item)
            existing["missing_data"] = missing_data
        return
    if key:
        seen[key] = len(entries)
    entries.append(payload)


def _candidate_pool_entries(final_target_resolution, execution_stage_context):
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    entries = []
    seen = {}
    for key, source in (
        ("display_target", "最终对象"),
        ("tradable_proxy_target", "可执行替代对象"),
        ("new_entry_target", "新机会对象"),
        ("watch_target", "观察对象"),
        ("process_target", "过程候选"),
    ):
        _append_candidate(entries, seen, resolution.get(key), source)
    bundle = context.get("step2_bundle") if isinstance(context.get("step2_bundle"), dict) else {}
    for key, source in (
        ("core_stocks", "核心候选池"),
        ("secondary_stocks", "次级候选池"),
        ("crossline_observation_stocks", "跨线观察池"),
        ("gem_observation_stocks", "创业板观察池"),
    ):
        for item in _context_list(bundle, key):
            _append_candidate(entries, seen, item, source)
    step3_bundle = context.get("step3_bundle") if isinstance(context.get("step3_bundle"), dict) else {}
    for key, source in (
        ("focus_group", "收缩保留组"),
        ("keep_group", "继续观察组"),
        ("delete_group", "淘汰组"),
    ):
        for item in _context_list(step3_bundle, key):
            _append_candidate(entries, seen, item, source)
    for key, source in (
        ("executable_stocks", "可执行池"),
        ("waiting_stocks", "等待池"),
        ("rejected_stocks", "淘汰池"),
    ):
        for item in _context_list(context, key):
            _append_candidate(entries, seen, item, source)
    return entries


def _position_stance_payload(target, observation_target, priority, position_decision, execution_stage_context):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    market_state = context.get("market_state_snapshot") if isinstance(context.get("market_state_snapshot"), dict) else {}
    mainline = clean_text(
        context.get("mainline_name")
        or (context.get("mainline_turnover_summary") or {}).get("current_mainline")
        or "待补事实"
    )
    final_action = clean_text(
        position_decision.get("final_action")
        or position_decision.get("sizing_reason")
        or (position_decision.get("capital_priority_decision") or {}).get("reason")
    )
    if target:
        return {
            "stance": "50%标准进攻",
            "reason_from_market": f"市场状态：{clean_text(market_state.get('market_state'), '待补事实')}",
            "reason_from_funds": "资金确认需在明日盘中继续校验",
            "reason_from_sector_window": f"主方向：{mainline}",
            "reason_from_leader_validation": "最终对象进入B档条件校验",
            "not_participate_reason": "",
            "passes_forward": "允许B档执行，条件不满足回到0%不参与",
        }
    return {
        "stance": "0%不参与",
        "reason_from_market": f"市场状态：{clean_text(market_state.get('market_state'), '待补事实')}",
        "reason_from_funds": "资金确认不足或待补事实",
        "reason_from_sector_window": f"主方向：{mainline}",
        "reason_from_leader_validation": "观察对象只跟踪确认" if observation_target else "缺少最终对象",
        "not_participate_reason": final_action or _priority_reason(priority) or "缺少明日执行对象",
        "passes_forward": "只保留观察，不生成B档执行条件" if observation_target else "无对象，0%不参与",
    }


def _priority_reason(priority):
    priority = clean_text(priority)
    if priority in {"wait"}:
        return "等待条件确认"
    if priority in {"old_position_t", "old_position", "existing_position", "existing_position_t"}:
        return "旧仓优先"
    return ""


def _dimension_labels(candidate, winner_stock, *, is_winner, position_plan, priority, execution_stage_context):
    stock = candidate.get("stock") if isinstance(candidate, dict) else {}
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    mainline = clean_text(
        context.get("mainline_name")
        or (context.get("mainline_turnover_summary") or {}).get("current_mainline")
    )
    sector = clean_text(stock.get("sector"))
    winner_sector = clean_text((winner_stock or {}).get("sector"))
    mainline_sector = _candidate_text(candidate, "mainline_sector")
    if not mainline_sector:
        if sector and (sector == winner_sector or sector == mainline):
            mainline_sector = "主线贴合"
        elif sector:
            mainline_sector = "支线"
        else:
            mainline_sector = "主线缺失"
    structure = _candidate_text(candidate, "stock_structure", "structure", "pattern")
    if not structure:
        structure = "承接" if is_winner else "结构缺失"
    funds = _candidate_text(candidate, "funds_confirmation", "fund_confirmation", "money_confirmation")
    if not funds:
        funds = "可用" if is_winner else "资金缺失"
    account_fit = _candidate_text(candidate, "account_fit")
    if not account_fit:
        if position_plan == "B档执行" and is_winner:
            account_fit = "可执行"
        elif clean_text(priority) in {"old_position_t", "old_position", "existing_position", "existing_position_t"}:
            account_fit = "旧仓优先"
        elif is_winner:
            account_fit = "等条件"
        else:
            account_fit = "不适合"
    risk = _candidate_text(candidate, "risk_missing_data", "risk")
    if not risk:
        risk = "可控" if is_winner else "关键缺失"
    return {
        "mainline_sector": mainline_sector,
        "stock_structure": structure,
        "funds_confirmation": funds,
        "account_fit": account_fit,
        "risk_missing_data": risk,
    }


def _missing_data_from_dimensions(candidate, dimensions):
    missing = list((candidate or {}).get("missing_data") or [])
    missing_map = {
        "mainline_sector": "主线证据缺失",
        "stock_structure": "结构确认缺失",
        "funds_confirmation": "资金确认缺失",
        "risk_missing_data": "风险边界缺失",
    }
    for key, label in missing_map.items():
        value = clean_text((dimensions or {}).get(key))
        if "缺失" in value and label not in missing:
            missing.append(label)
    return missing


def _non_circular_reason(candidate):
    reason = _candidate_text(candidate, "reason", "conviction_reason")
    circular_markers = ("最终解析", "未选中", "未选为", "没有被选", "未成为最终", "未进入最终")
    if any(marker in reason for marker in circular_markers):
        return ""
    return reason


def _loss_reason(candidate, dimensions, missing_data):
    reason = _non_circular_reason(candidate)
    if reason:
        return reason
    labels = [
        clean_text(dimensions.get("mainline_sector")),
        clean_text(dimensions.get("stock_structure")),
        clean_text(dimensions.get("funds_confirmation")),
        clean_text(dimensions.get("account_fit")),
        clean_text(dimensions.get("risk_missing_data")),
    ]
    labels = [label for label in labels if label]
    if labels:
        suffix = "；关键数据缺失：" + "、".join(missing_data) if missing_data else ""
        return "、".join(labels) + "，条件弱于保留对象" + suffix
    if missing_data:
        return "关键数据缺失：" + "、".join(missing_data)
    return "候选维度证据缺失，暂不进入最终对象"


def _candidate_verdict_row(candidate, winner_stock, *, is_winner, position_plan, priority, execution_stage_context):
    dimensions = _dimension_labels(
        candidate,
        winner_stock,
        is_winner=is_winner,
        position_plan=position_plan,
        priority=priority,
        execution_stage_context=execution_stage_context,
    )
    missing_data = _missing_data_from_dimensions(candidate, dimensions)
    row = {
        "stock": dict(candidate.get("stock") or {}),
        "pool_source": clean_text(candidate.get("pool_source"), "候选池"),
        "pool_sources": list(candidate.get("pool_sources") or [clean_text(candidate.get("pool_source"), "候选池")]),
        "dimension_labels": dimensions,
        "dimension_results": dict(dimensions),
        "loss_reason": "",
        "missing_data": missing_data,
    }
    if not is_winner:
        row["loss_reason"] = _loss_reason(candidate, dimensions, missing_data)
    return row


def _candidate_pool_verdict(
    *,
    final_target_resolution,
    execution_stage_context,
    final_stock,
    final_identity,
    position_plan,
    priority,
):
    entries = _candidate_pool_entries(final_target_resolution, execution_stage_context)
    winner_entry = {}
    for entry in entries:
        if _same_stock(entry.get("stock"), final_stock):
            winner_entry = entry
            break
    if final_stock and not winner_entry:
        winner_entry = {"stock": dict(final_stock), "pool_source": "最终对象"}
    winner = {}
    if winner_entry:
        winner = _candidate_verdict_row(
            winner_entry,
            final_stock,
            is_winner=True,
            position_plan=position_plan,
            priority=priority,
            execution_stage_context=execution_stage_context,
        )
        winner["identity"] = final_identity
    losers = []
    for entry in entries:
        if final_stock and _same_stock(entry.get("stock"), final_stock):
            continue
        losers.append(
            _candidate_verdict_row(
                entry,
                final_stock,
                is_winner=False,
                position_plan=position_plan,
                priority=priority,
                execution_stage_context=execution_stage_context,
            )
        )
        if len(losers) >= 3:
            break
    rows = ([winner] if winner else []) + losers
    dimension_results = {
        _stock_label(row.get("stock")): row.get("dimension_labels", {})
        for row in rows
        if _stock_label(row.get("stock")) != "暂无"
    }
    return {
        "pool_source": [
            {
                "stock": dict(entry.get("stock") or {}),
                "source": clean_text(entry.get("pool_source"), "候选池"),
                "sources": list(entry.get("pool_sources") or [clean_text(entry.get("pool_source"), "候选池")]),
            }
            for entry in entries
        ],
        "winner": winner,
        "important_losers": losers,
        "downgraded_or_rejected_top3": losers,
        "dimension_results": dimension_results,
        "missing_data": sorted({item for row in rows for item in row.get("missing_data", [])}),
        "passes_forward": _stock_label(final_stock) if final_stock else "无明日执行对象",
    }


def _execution_condition_lines(b_level_conditions):
    conditions = b_level_conditions if isinstance(b_level_conditions, dict) else {}
    low_open = conditions.get("low_open_acceptance") if isinstance(conditions.get("low_open_acceptance"), dict) else {}
    active = conditions.get("active_attack") if isinstance(conditions.get("active_attack"), dict) else {}
    lines = []
    if low_open:
        lines.append(
            "低开承接型：{daily}；{intraday}；{window}".format(
                daily=clean_text(low_open.get("daily_structure"), "靠近MA5或快速收回MA5"),
                intraday=clean_text(low_open.get("intraday_reclaim"), "收回VWAP或0轴"),
                window=clean_text(low_open.get("window"), "09:50-10:10"),
            )
        )
    if active:
        lines.append(
            "主动进攻型：{price}；{money}；{hold}；{window}".format(
                price=clean_text(active.get("price_action"), "开盘直线进攻"),
                money=clean_text(active.get("money_confirmation"), "分时资金确认达标"),
                hold=clean_text(active.get("intraday_hold"), "VWAP上方保持"),
                window=clean_text(active.get("window"), "09:30-09:35或09:50-10:10"),
            )
        )
    return lines


def _failure_conditions(target, observation_target, b_level_conditions, position_stance):
    conditions = b_level_conditions if isinstance(b_level_conditions, dict) else {}
    invalidations = [clean_text(item) for item in conditions.get("invalidations", []) or [] if clean_text(item)]
    if target:
        return invalidations + ["固定交易窗口内条件未满足"]
    reason = clean_text((position_stance or {}).get("not_participate_reason"))
    if observation_target:
        result = [reason] if reason else []
        result.append("未出现回踩确认或资金确认前不参与")
        return result
    return [reason or "缺少明日执行对象", "关键数据不完整时不参与"]


def _observation_conditions(observation_target, target):
    if observation_target:
        label = _stock_label(observation_target)
        return [f"只观察{label}，不新增参与", "等待市场、板块与资金重新满足参与条件"]
    if target:
        return ["条件未出现前只观察，不抢跑"]
    return []


def _why_this_not_others(final_stock, final_identity, candidate_pool_verdict, observation_target):
    if not final_stock:
        return "没有可用明日执行对象，也没有观察对象"
    label = _stock_label(final_stock)
    losers = candidate_pool_verdict.get("important_losers", []) if isinstance(candidate_pool_verdict, dict) else []
    if losers:
        loser = losers[0]
        dims = loser.get("dimension_results") if isinstance(loser.get("dimension_results"), dict) else {}
        dimension_text = "、".join(
            text
            for text in (
                f"主线/板块={clean_text(dims.get('mainline_sector'))}",
                f"个股结构={clean_text(dims.get('stock_structure'))}",
                f"资金确认={clean_text(dims.get('funds_confirmation'))}",
                f"账户匹配={clean_text(dims.get('account_fit'))}",
                f"风险/缺失={clean_text(dims.get('risk_missing_data'))}",
            )
            if not text.endswith("=")
        )
        reason = clean_text(loser.get("loss_reason"), "关键数据缺失")
        return (
            f"{label}保留为{final_identity}；{_stock_label(loser.get('stock'))}未胜出："
            f"{reason}；维度差异：{dimension_text}"
        )
    if observation_target:
        return f"仓位不允许B档，{label}只保留为观察对象"
    return f"{label}是当前唯一保留对象，明日只按条件校验"


def _final_object_payload(target, observation_target, position_stance, b_level_conditions, candidate_pool_verdict):
    final_stock = target or observation_target
    if target:
        identity = "明日执行对象"
        execution_type = "B档执行，条件满足才参与"
    elif observation_target:
        identity = "观察对象"
        execution_type = "只观察，不新增参与"
    else:
        identity = "无"
        execution_type = "无明日执行对象"
    execution_conditions = _execution_condition_lines(b_level_conditions) if target else []
    observation_conditions = _observation_conditions(observation_target, target)
    failure_conditions = _failure_conditions(target, observation_target, b_level_conditions, position_stance)
    return {
        "identity": identity,
        "stock": dict(final_stock or {}),
        "position_stance": clean_text((position_stance or {}).get("stance"), "0%不参与"),
        "execution_type": execution_type,
        "execution_conditions": execution_conditions,
        "observation_conditions": observation_conditions,
        "failure_conditions": failure_conditions,
        "why_this_not_others": _why_this_not_others(
            final_stock,
            identity,
            candidate_pool_verdict,
            observation_target,
        ),
    }


def _next_day_action_payload(final_object, b_level_conditions):
    final_object = final_object if isinstance(final_object, dict) else {}
    stock = final_object.get("stock") if isinstance(final_object.get("stock"), dict) else {}
    label = _stock_label(stock)
    execution_conditions = list(final_object.get("execution_conditions") or [])
    failure_conditions = list(final_object.get("failure_conditions") or [])
    if final_object.get("identity") == "明日执行对象":
        checklist = [f"确认{label}仍满足最终对象条件"]
        checklist.extend(f"执行条件：{condition}" for condition in execution_conditions)
        checklist.extend(f"不参与条件：{condition}" for condition in failure_conditions)
    elif final_object.get("identity") == "观察对象":
        checklist = [
            f"只观察{label}，不新增参与",
            "记录回踩、资金和板块确认是否改善",
            "条件未重新满足前继续0%不参与",
        ]
    else:
        checklist = ["无明日执行对象，0%不参与", "关键数据不完整时不生成新增参与计划"]
    return {
        "stock": dict(stock),
        "final_object_identity": clean_text(final_object.get("identity"), "无"),
        "position_stance": clean_text(final_object.get("position_stance"), "0%不参与"),
        "checklist": checklist,
        "time_windows": ["09:30-09:35", "09:50-10:10"] if execution_conditions else [],
        "buy_conditions": execution_conditions,
        "no_buy_conditions": failure_conditions,
        "old_position_handling": "旧仓优先时，新机会只观察，不新增参与",
        "review_points": ["收盘后复核条件是否命中", "记录失败条件是否触发"],
    }


def _opening_verdict_payload(position_stance, candidate_pool_verdict, final_object, next_day_action):
    return {
        "position_stance": clean_text((position_stance or {}).get("stance"), "0%不参与"),
        "final_object_identity": clean_text((final_object or {}).get("identity"), "无"),
        "stock": dict((final_object or {}).get("stock") or {}),
        "execution_type": clean_text((final_object or {}).get("execution_type"), "无明日执行对象"),
        "winner": (candidate_pool_verdict or {}).get("winner", {}),
        "important_losers": (candidate_pool_verdict or {}).get("important_losers", []),
        "next_day_checklist": (next_day_action or {}).get("checklist", []),
        "summary": clean_text((final_object or {}).get("why_this_not_others"), "无明日执行对象"),
    }


def _step_payloads(target, execution_stage_context, final_object=None):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    final_object = final_object if isinstance(final_object, dict) else {}
    observation_stock = (
        final_object.get("stock")
        if final_object.get("identity") == "观察对象" and isinstance(final_object.get("stock"), dict)
        else {}
    )
    observation_label = _stock_label(observation_stock) if observation_stock else ""
    market_state = context.get("market_state_snapshot") if isinstance(context.get("market_state_snapshot"), dict) else {}
    mainline = clean_text(
        context.get("mainline_name")
        or (context.get("mainline_turnover_summary") or {}).get("current_mainline")
        or market_state.get("market_state")
        or "待确认"
    )
    target_label = _stock_label(target)
    candidate_labels = _dedupe_labels(_process_candidates_from_context(execution_stage_context))
    kept_label = target_label if target_label != "暂无" else observation_label
    rejected = [label for label in candidate_labels if label != kept_label]
    target_list = [target_label] if target_label != "暂无" else []
    candidate_input = "、".join(candidate_labels) if candidate_labels else "无可用候选"
    rejected_input = "、".join(rejected) if rejected else "无"
    steps = [
        {
            "step": "Step 0",
            "title": "市场底色",
            "input_summary": [
                f"市场状态：{clean_text(market_state.get('market_state'), '待确认')}",
                f"主方向：{mainline}",
                "指数涨跌、涨跌家数、成交额趋势、涨停跌停扩散",
            ],
            "judgement": "判断明日是否允许考虑B档执行",
            "kept": [],
            "rejected": [],
            "passes_forward": "可等待B档条件",
            "cannot_conclude": "本步不能选出执行对象",
        },
        {
            "step": "Step 1",
            "title": "候选池",
            "input_summary": [
                f"候选池：{candidate_input}",
                "热榜、涨停池、盘中异动、板块与tag证据、近期龙头记忆",
            ],
            "judgement": "形成过程候选，不生成最终身份",
            "kept": candidate_labels,
            "rejected": [],
            "passes_forward": "过程候选进入主方向收缩",
            "cannot_conclude": "本步不能把候选直接升级为明日执行对象",
        },
    ]
    if not target_list:
        kept_observation = [observation_label] if observation_label and observation_label != "暂无" else []
        step2_judgement = "本步判断：当前无明日执行对象"
        step2_passes_forward = "传给下一步：无明日执行对象，保持0%不参与"
        if kept_observation:
            step2_judgement = f"本步判断：当前无明日执行对象；保留观察对象：{observation_label}"
            step2_passes_forward = f"观察对象：{observation_label}；无明日执行对象，保持0%不参与"
        steps.extend(
            [
                {
                    "step": "Step 2",
                    "title": "主方向与候选收缩",
                    "input_summary": [
                        f"主方向：{mainline}",
                        f"进入收缩的候选：{candidate_input}",
                    ],
                    "judgement": step2_judgement,
                    "kept": kept_observation,
                    "rejected": rejected,
                    "passes_forward": step2_passes_forward,
                    "cannot_conclude": "不能推出无条件买入，也不能生成B档执行对象",
                },
                {
                    "step": "Step 3",
                    "title": "风险复核",
                    "input_summary": [
                        f"保留对象：观察对象{observation_label}" if kept_observation else "保留对象：无明日执行对象",
                        f"淘汰对象：{rejected_input}",
                        "烂板/炸板、板块走弱、A杀或结构破坏、跌停扩散、关键数据缺失",
                    ],
                    "judgement": (
                        f"{observation_label}只保留观察身份，风险复核结论保持0%不参与"
                        if kept_observation
                        else "当前无明日执行对象，风险复核结论保持0%不参与"
                    ),
                    "kept": kept_observation,
                    "rejected": [],
                    "passes_forward": "无明日执行对象，不进入B档执行计划",
                    "cannot_conclude": "本步不能引入新的执行对象",
                },
                {
                    "step": "Step 4",
                    "title": "B档执行计划",
                    "input_summary": [
                        "MA5位置、VWAP/0轴、市场和方向确认",
                        "资金确认：小中盘活跃股3000w-5000w；大市值或高成交核心1亿+",
                    ],
                    "judgement": "未生成B档执行条件",
                    "kept": [],
                    "rejected": [],
                    "passes_forward": "前台同步0%不参与",
                    "cannot_conclude": "没有明日执行对象时不能执行",
                },
                {
                    "step": "Step 5",
                    "title": "最终一致性",
                    "input_summary": ["最终对象、B档条件、账户约束、旧仓处理"],
                    "judgement": (
                        f"同步前台0%不参与结论，并保留观察对象：{observation_label}"
                        if kept_observation
                        else "同步前台0%不参与结论"
                    ),
                    "kept": kept_observation,
                    "rejected": [],
                    "passes_forward": "生成最终前台决策：0%不参与",
                    "cannot_conclude": "不能重新打开候选选择",
                },
            ]
        )
        return steps
    steps.extend(
        [
            {
                "step": "Step 2",
                "title": "主方向与候选收缩",
                "input_summary": [
                    f"主方向：{mainline}",
                    f"进入收缩的候选：{candidate_input}",
                ],
                "judgement": f"{target_label}作为条件执行对象继续准备B档条件",
                "kept": target_list,
                "rejected": rejected,
                "passes_forward": f"条件执行对象：{target_label}",
                "cannot_conclude": "不能推出无条件买入",
            },
            {
                "step": "Step 3",
                "title": "风险复核",
                "input_summary": [
                    f"保留对象：{target_label}",
                    f"淘汰对象：{rejected_input}",
                    "烂板/炸板、板块走弱、A杀或结构破坏、跌停扩散、关键数据缺失",
                ],
                "judgement": f"{target_label}继续保留为条件执行对象",
                "kept": target_list,
                "rejected": [],
                "passes_forward": f"{target_label}进入B档执行计划",
                "cannot_conclude": "本步不能引入新的执行对象",
            },
            {
                "step": "Step 4",
                "title": "B档执行计划",
                "input_summary": [
                    "MA5位置、VWAP/0轴、市场和方向确认",
                    "资金确认：小中盘活跃股3000w-5000w；大市值或高成交核心1亿+",
                ],
                "judgement": "生成低开承接型和主动进攻型两条触发路径",
                "kept": target_list,
                "rejected": [],
                "passes_forward": "B档执行条件同步到前台",
                "cannot_conclude": "条件未出现前不能执行",
            },
            {
                "step": "Step 5",
                "title": "最终一致性",
                "input_summary": ["最终对象、B档条件、账户约束、旧仓处理"],
                "judgement": "同步前台、行动计划、候选质量和附录路径",
                "kept": target_list,
                "rejected": [],
                "passes_forward": "生成最终前台决策",
                "cannot_conclude": "不能重新打开候选选择",
            },
        ]
    )
    return steps


def build_two_layer_decision_payload(
    *,
    target_date="",
    final_target_resolution=None,
    position_decision=None,
    execution_stage_context=None,
):
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    position_decision = position_decision if isinstance(position_decision, dict) else {}
    priority = _capital_priority(resolution)
    target = {}
    if _execution_priority_allows_b_level(priority, position_decision):
        if priority == "tradable_proxy":
            target = _first_stock(
                resolution.get("display_target"),
                resolution.get("tradable_proxy_target"),
            )
        elif priority in {"new_entry", "new_entry_after_old_exit"}:
            target = _first_stock(
                resolution.get("display_target"),
                resolution.get("new_entry_target"),
                resolution.get("tradable_proxy_target"),
                resolution.get("watch_target"),
            )
        else:
            target = _first_stock(
                resolution.get("display_target"),
                resolution.get("new_entry_target"),
                resolution.get("tradable_proxy_target"),
            )
    position_plan = "B档执行" if target else "0%不参与"
    observation_target = {}
    if not target:
        observation_target = _first_stock(resolution.get("watch_target"))
    b_level_conditions = _build_b_level_conditions(target) if target else {}
    position_stance = _position_stance_payload(
        target,
        observation_target,
        priority,
        position_decision,
        execution_stage_context,
    )
    final_stock = target or observation_target
    final_identity = "明日执行对象" if target else ("观察对象" if observation_target else "无")
    candidate_pool_verdict = _candidate_pool_verdict(
        final_target_resolution=resolution,
        execution_stage_context=execution_stage_context,
        final_stock=final_stock,
        final_identity=final_identity,
        position_plan=position_plan,
        priority=priority,
    )
    final_object = _final_object_payload(
        target,
        observation_target,
        position_stance,
        b_level_conditions,
        candidate_pool_verdict,
    )
    next_day_action = _next_day_action_payload(final_object, b_level_conditions)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "target_date": clean_text(target_date),
        "opening_verdict": _opening_verdict_payload(
            position_stance,
            candidate_pool_verdict,
            final_object,
            next_day_action,
        ),
        "position_stance": position_stance,
        "candidate_pool_verdict": candidate_pool_verdict,
        "final_object": final_object,
        "next_day_action": next_day_action,
        "front_decision": {
            "position_plan": position_plan,
            "position_pct": 50 if position_plan == "B档执行" else 0,
            "execution_object": target,
            "execution_identity": "明日执行对象" if target else "无明日执行对象",
            "if_fail": "不参与",
        },
        "b_level_conditions": b_level_conditions,
    }
    payload["derivation_steps"] = _step_payloads(target, execution_stage_context, final_object)
    return payload


def _render_opening_verdict_lines(payload):
    payload = payload if isinstance(payload, dict) else {}
    opening = payload.get("opening_verdict") if isinstance(payload.get("opening_verdict"), dict) else {}
    if not opening:
        return []
    stock = opening.get("stock") if isinstance(opening.get("stock"), dict) else {}
    stock_label = _stock_label(stock)
    object_text = opening.get("final_object_identity", "无")
    if stock_label != "暂无":
        object_text = f"{object_text}：{stock_label}"
    lines = [
        "## 日报裁决总览",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 仓位姿态 | {clean_text(opening.get('position_stance'), '0%不参与')} |",
        f"| 最终对象 | {clean_text(object_text, '无')} |",
        f"| 对象性质 | {clean_text(opening.get('execution_type'), '无明日执行对象')} |",
        f"| 推导摘要 | {clean_text(opening.get('summary'), '无明日执行对象')} |",
    ]
    losers = opening.get("important_losers") if isinstance(opening.get("important_losers"), list) else []
    if losers:
        lines.extend(
            [
                "",
                "### 候选胜负摘要",
                "| 候选 | 主线/板块 | 个股结构 | 资金确认 | 账户匹配 | 风险/缺失 | 结论 |",
                "|------|-----------|----------|----------|----------|-----------|------|",
            ]
        )
        for loser in losers[:3]:
            if not isinstance(loser, dict):
                continue
            dims = loser.get("dimension_labels") if isinstance(loser.get("dimension_labels"), dict) else {}
            lines.append(
                "| {stock} | {mainline} | {structure} | {funds} | {account} | {risk} | {reason} |".format(
                    stock=_stock_label(loser.get("stock")),
                    mainline=clean_text(dims.get("mainline_sector"), "-"),
                    structure=clean_text(dims.get("stock_structure"), "-"),
                    funds=clean_text(dims.get("funds_confirmation"), "-"),
                    account=clean_text(dims.get("account_fit"), "-"),
                    risk=clean_text(dims.get("risk_missing_data"), "-"),
                    reason=clean_text(loser.get("loss_reason"), "关键数据缺失"),
                )
            )
    return lines


def render_front_decision_layer(payload):
    payload = payload if isinstance(payload, dict) else {}
    front = payload.get("front_decision") if isinstance(payload.get("front_decision"), dict) else {}
    target = front.get("execution_object") if isinstance(front.get("execution_object"), dict) else {}
    target_label = _stock_label(target)
    conditions = payload.get("b_level_conditions") if isinstance(payload.get("b_level_conditions"), dict) else {}
    low_open = conditions.get("low_open_acceptance") if isinstance(conditions.get("low_open_acceptance"), dict) else {}
    active = conditions.get("active_attack") if isinstance(conditions.get("active_attack"), dict) else {}
    position_plan = clean_text(front.get("position_plan"), "B档执行")
    opening_lines = _render_opening_verdict_lines(payload)
    if not target:
        lines = [
            "## 明日执行结论",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 明日仓位 | 0%不参与 |",
            "| 明日执行对象 | 无 |",
            "| 执行性质 | 无明日执行对象 |",
            f"| 不满足条件 | {clean_text(front.get('if_fail'), '不参与')} |",
        ]
        return opening_lines + ([""] if opening_lines else []) + lines
    lines = [
        "## 明日执行结论",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 明日仓位 | 条件满足才{position_plan}；不满足回到0% |",
        f"| 明日执行对象 | {target_label} |",
        "| 执行性质 | B档执行，约50%仓位 |",
        f"| 不满足条件 | {clean_text(front.get('if_fail'), '不参与')} |",
        "",
        "## B档执行条件",
        "| 触发类型 | 必须满足 | 窗口 | 动作 |",
        "|----------|----------|------|------|",
        "| 低开承接型 | {daily}；{intraday} | {window} | {action} |".format(
            daily=clean_text(low_open.get("daily_structure"), "靠近MA5或快速收回MA5"),
            intraday=clean_text(low_open.get("intraday_reclaim"), "收回VWAP或0轴"),
            window=clean_text(low_open.get("window"), "09:50-10:10"),
            action=clean_text(low_open.get("action"), "B档执行"),
        ),
        "| 主动进攻型 | {price}；{money}；{hold} | {window} | {action} |".format(
            price=clean_text(active.get("price_action"), "开盘直线进攻"),
            money=clean_text(active.get("money_confirmation"), "分时大单净流入达标"),
            hold=clean_text(active.get("intraday_hold"), "VWAP上方保持"),
            window=clean_text(active.get("window"), "09:30-09:35或09:50-10:10"),
            action=clean_text(active.get("action"), "B档执行"),
        ),
        "",
        "## 不执行条件",
    ]
    for item in conditions.get("invalidations", []) or []:
        lines.append(f"- {clean_text(item)}")
    return opening_lines + ([""] if opening_lines else []) + lines


def render_derivation_audit_layer(payload):
    payload = payload if isinstance(payload, dict) else {}
    lines = ["## 推导审计层"]
    for step in payload.get("derivation_steps", []) or []:
        if not isinstance(step, dict):
            continue
        lines.extend(
            [
                "",
                f"### {clean_text(step.get('step'))}：{clean_text(step.get('title'))}",
                "#### 输入数据",
            ]
        )
        for item in step.get("input_summary", []) or []:
            lines.append(f"- {clean_text(item)}")
        lines.extend(
            [
                "#### 本步判断",
                f"- {clean_text(step.get('judgement'), '-')}",
                "#### 保留与淘汰",
            ]
        )
        kept = "、".join(clean_text(item) for item in step.get("kept", []) or [] if clean_text(item)) or "无"
        rejected = "、".join(clean_text(item) for item in step.get("rejected", []) or [] if clean_text(item)) or "无"
        lines.append(f"- 保留：{kept}")
        lines.append(f"- 淘汰：{rejected}")
        lines.extend(["#### 传给下一步", f"- {clean_text(step.get('passes_forward'), '无')}"])
        lines.extend(["#### 本步不能推出什么", f"- {clean_text(step.get('cannot_conclude'), '-')}"])
    return lines
