from report.surface_wording import sanitize_user_visible_text
from report.trading_time_window_contract import normalize_trading_time_text


def _format_closed_gate_buy_limit_text(position_level, final_gate):
    final_gate = final_gate or {}
    if final_gate.get("allow_attack_50_ready"):
        return "等固定交易窗口内条件成立；未确认按0%不参与"
    return "保持空仓，不新增参与"


def _format_position_display(position_level):
    text = str(position_level or "").strip()
    if "一档" in text or "空仓" in text:
        return "0%不参与"
    if "二档" in text or "防守" in text:
        return "0%观察"
    if "进攻" in text:
        return "50%标准进攻"
    return text or "0%观察"


def _is_ten_confirm_upgrade_candidate(candidate):
    candidate = candidate or {}
    text = " ".join(
        str(candidate.get(key, "") or "")
        for key in (
            "permission_label",
            "watch_anchor_type",
            "conviction_reason",
            "reason",
            "core_level",
            "watch_anchor_note",
        )
    )
    minute_plan = candidate.get("minute_plan") or {}
    return bool(
        minute_plan.get("confirm_price_60m")
        and (
            any(marker in text for marker in ("重点观察名单", "重点观察权", "重点观察确认"))
            or "极看" in text
            or "极度看好" in text
            or "板块锚定龙" in text
            or "首波先锋" in text
            or "主线核心" in text
        )
    )


def _candidate_key(candidate):
    candidate = candidate or {}
    return str(candidate.get("code") or candidate.get("代码") or candidate.get("name") or candidate.get("名称") or "").strip()


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _dedupe_candidates(candidates):
    deduped = []
    index_by_key = {}
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        key = _candidate_key(candidate)
        if key and key in seen:
            existing = deduped[index_by_key[key]]
            for field, value in candidate.items():
                if value in (None, "", [], {}):
                    continue
                if field == "entry_cost_state" and value == "高成本":
                    existing[field] = value
                    continue
                if field in ("risk_flags", "cost_flags"):
                    existing[field] = _merge_unique_values(existing.get(field), value)
                    continue
                if existing.get(field) in (None, "", [], {}):
                    existing[field] = value
            continue
        if key:
            seen.add(key)
            index_by_key[key] = len(deduped)
        deduped.append(candidate)
    return deduped


def _merge_unique_values(existing_value, incoming_value):
    merged = []
    for value in _as_list(existing_value) + _as_list(incoming_value):
        if value not in (None, "") and value not in merged:
            merged.append(value)
    return merged


def _quality_candidate(candidate, *, quality_role="", selection_quality="", entry_cost_state="", is_core=None):
    if not candidate:
        return None
    enriched = dict(candidate)
    if selection_quality and not enriched.get("selection_quality"):
        enriched["selection_quality"] = selection_quality
    if entry_cost_state and not enriched.get("entry_cost_state"):
        enriched["entry_cost_state"] = entry_cost_state
    if is_core is not None and "is_core" not in enriched:
        enriched["is_core"] = is_core
    if quality_role and not enriched.get("quality_role"):
        enriched["quality_role"] = quality_role
    return enriched


def _build_candidate_quality_panel_fields(
    *,
    step0_prediction_cn,
    has_personal_positions,
    daily_new_entry_limit,
    best_stock,
    watch_anchor,
):
    backup_candidate = watch_anchor
    if _candidate_key(best_stock) and _candidate_key(best_stock) == _candidate_key(watch_anchor):
        backup_candidate = None
    return {
        "market_emotion_label": step0_prediction_cn,
        "account_attention_load": "有持仓需先处理" if has_personal_positions else "无持仓负担",
        "holding_priority_action": "先处理旧仓，再看新增" if has_personal_positions else "无旧仓时只等固定交易窗口内条件",
        "daily_new_entry_limit": daily_new_entry_limit,
        "primary_buy_candidate": best_stock,
        "backup_candidate": backup_candidate,
        "forbidden_actions": ["亏损后补仓", "计划外追高"],
        "ignored_noise_items": ["外盘大涨但A股未确认", "论坛情绪"],
    }


def build_pk_decision_action_plan_context_node(context, node_meta=None, node_lookup=None):
    trade_gate_open = context.get("trade_gate_open", False)
    best_stock = context.get("best_stock")
    watch_anchor = context.get("watch_anchor")
    watch_anchor_type = context.get("watch_anchor_type", "")
    position_level = str(context.get("position_level", "") or "").strip()
    step0_prediction = str(context.get("step0_prediction", "") or "").strip()
    step0_prediction_cn = str(context.get("step0_prediction_cn", "") or "").strip()
    final_gate = context.get("final_gate", {}) or {}
    has_personal_positions = bool(context.get("has_personal_positions", False))
    display_observation_candidates = context.get("display_observation_candidates", context.get("observation_candidates", [])) or []
    waiting_stocks = context.get("waiting_stocks", []) or []
    today_predictions = context.get("today_predictions", []) or []
    nextday_predictions = context.get("nextday_predictions", []) or []

    build_trade_price_focus = context.get("build_trade_price_focus", lambda minute_plan, stop_plan: {})
    build_observation_price_focus_text = context.get("build_observation_price_focus_text", lambda price_focus: "-")
    append_watch_anchor_note = context.get("append_watch_anchor_note", lambda report_lines, candidate, prefix="  ": None)
    append_observation_price_focus_note = context.get(
        "append_observation_price_focus_note",
        lambda report_lines, price_focus, prefix="  ": None,
    )
    compose_observation_focus_text = context.get(
        "compose_observation_focus_text",
        lambda confirm_text, observation_price_focus_text: f"{confirm_text} / {observation_price_focus_text}",
    )
    build_stop_execution_plan = context.get("build_stop_execution_plan", lambda *args, **kwargs: {})
    build_candidate_exit_rules = context.get("build_candidate_exit_rules", lambda candidate, stop_plan=None: {})
    format_holding_window_text = context.get("format_holding_window_text", lambda min_days, max_days: "")
    get_execution_framework_text = context.get("get_execution_framework_text", lambda: "")
    ten_confirm_upgrade_candidate = next(
        (candidate for candidate in display_observation_candidates if _is_ten_confirm_upgrade_candidate(candidate)),
        None,
    )
    can_ten_confirm_upgrade = bool(final_gate.get("allow_attack_50_ready") or ten_confirm_upgrade_candidate)
    daily_new_entry_limit = 1 if final_gate.get("can_new_entry") or trade_gate_open else 0

    action_rows = []
    if best_stock:
        if "signal" in best_stock:
            signal = best_stock["signal"]
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            stop_plan = best_stock.get("stop_plan") or build_stop_execution_plan(
                signal.entry_price,
                best_stock.get("stop_loss", signal.stop_loss),
                structure_label="日线预估结构止损",
            )
            exit_rules = build_candidate_exit_rules(best_stock, stop_plan)
            stop_summary_text = (stop_plan or {}).get("summary")
            if not stop_summary_text:
                stop_summary_text = f"预估{best_stock.get('stop_loss', signal.stop_loss):.2f}"
            action_rows.append(
                {
                    "action": "🔥 唯一买入",
                    "name": best_stock.get("name"),
                    "code": best_stock.get("code"),
                    "trigger": f"明日09:50-10:10站上{confirm_price:.2f}" if confirm_price else "明日09:50-10:10窗口内满足条件后触发",
                    "risk_window": f"{stop_summary_text} / {format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
                }
            )
        else:
            stop_plan = best_stock.get("stop_plan")
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            exit_rules = build_candidate_exit_rules(best_stock, stop_plan)
            action_rows.append(
                {
                    "action": "🔥 唯一买入",
                    "name": best_stock.get("name"),
                    "code": best_stock.get("code"),
                    "trigger": (
                        f"明日09:50-10:10站上{confirm_price:.2f}后按{best_stock.get('trigger', '条件')}执行"
                        if confirm_price
                        else f"明日09:50-10:10窗口内满足条件后按{best_stock.get('trigger', '条件')}执行"
                    ),
                    "risk_window": f"{(stop_plan or {}).get('summary', '先看失效价 / 最晚-5%')} / "
                    f"{format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
                }
            )
    elif trade_gate_open and watch_anchor:
        minute_plan = watch_anchor.get("minute_plan") or {}
        stop_plan = watch_anchor.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        exit_rules = build_candidate_exit_rules(watch_anchor, stop_plan)
        action_rows.append(
            {
                "action": "👀 明天先盯哪只",
                "name": watch_anchor.get("name"),
                "code": watch_anchor.get("code"),
                "trigger": (
                    f"09:50-10:10站上{confirm_price:.2f}后，再看是否走成明天唯一能买的那只"
                    if confirm_price
                    else "先看09:50-10:10窗口，再看是否走成明天唯一能买的那只"
                ),
                "risk_window": f"{(price_focus or {}).get('key_zone_display', '-')} / "
                f"{format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
            }
        )
    elif can_ten_confirm_upgrade and display_observation_candidates:
        candidate = ten_confirm_upgrade_candidate or display_observation_candidates[0] or {}
        minute_plan = candidate.get("minute_plan") or {}
        stop_plan = candidate.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        confirm_text = f"09:50-10:10站上{confirm_price:.2f}" if confirm_price else "09:50-10:10窗口内条件成立"
        action_rows.append(
            {
                "action": "⏳ 确认后执行预案",
                "name": candidate.get("name"),
                "code": candidate.get("code"),
                "trigger": f"{confirm_text}，且板块承接不塌，固定交易窗口内条件成立后才评估50%标准进攻",
                "risk_window": (price_focus or {}).get("key_zone_display", "-"),
            }
        )
    else:
        action_rows.append(
            {
                "action": "❌ 明天没有可买对象",
                "name": "-",
                "code": "-",
                "trigger": _format_closed_gate_buy_limit_text(position_level, final_gate) if not trade_gate_open else "无符合条件标的",
                "risk_window": "-",
            }
        )

    observation_priority_lines = []
    if not trade_gate_open and display_observation_candidates:
        for candidate in display_observation_candidates[:3]:
            minute_plan = candidate.get("minute_plan") or {}
            stop_plan = candidate.get("stop_plan")
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
            observation_price_focus_text = build_observation_price_focus_text(price_focus)
            observation_priority_lines.append(
                f"- 👀 {candidate.get('name')}({candidate.get('code')}) - "
                f"{candidate.get('watch_anchor_type', candidate.get('permission_label', '观察权'))}，"
                f"{normalize_trading_time_text(compose_observation_focus_text(confirm_text, observation_price_focus_text))}"
            )
            append_watch_anchor_note(observation_priority_lines, candidate, prefix="  ")
            append_observation_price_focus_note(observation_priority_lines, price_focus, prefix="  ")

    backup_observation_lines = []
    for candidate in waiting_stocks[:3]:
        minute_plan = candidate.get("minute_plan") or {}
        stop_plan = candidate.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
        observation_price_focus_text = build_observation_price_focus_text(price_focus)
        backup_observation_lines.append(
            f"- ⏳ {candidate.get('name')}({candidate.get('code')}) - 等买点出现，"
            f"{normalize_trading_time_text(compose_observation_focus_text(confirm_text, observation_price_focus_text))}"
        )
        append_observation_price_focus_note(backup_observation_lines, price_focus, prefix="  ")

    position_section_lines = [
        f"- **进攻仓位三态**: {_format_position_display(position_level)}",
        f"- **明日裁决**: {step0_prediction_cn}",
        f"- **怎么执行**: {normalize_trading_time_text(get_execution_framework_text())}",
    ]
    if position_level == "一档（空仓档）":
        if can_ten_confirm_upgrade and display_observation_candidates:
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 0%观察，禁止抢跑，但保留重点观察名单的盘中确认路径",
                    "- **明天仓位放多少**: 盘前0%；固定交易窗口内条件成立后才评估50%标准进攻",
                    "- **明天具体怎么做**: 09:50-10:10只看重点观察/主线核心是否主动证明自己，命中后才评估50%标准进攻，未命中继续0%",
                ]
            )
        else:
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 空仓",
                    "- **明天仓位放多少**: 0%（保持空仓）",
                    "- **明天具体怎么做**: 不新增参与；若有旧仓只处理旧仓，否则保持空仓",
                ]
            )
    elif position_level == "二档（防守档）":
        position_section_lines.append("- **现在到底是什么状态**: 0%观察，等待固定交易窗口内条件")
        if final_gate.get("should_reduce"):
            position_section_lines.append("- **明天仓位放多少**: 0%新仓（只处理旧仓，不新增）")
            position_section_lines.append(
                "- **明天具体怎么做**: 只处理你的旧仓，去弱留强，不新增参与"
                if has_personal_positions
                else "- **明天具体怎么做**: 市场级原则是若你有旧仓就去弱留强，不新增参与"
            )
        else:
            position_section_lines.append("- **明天仓位放多少**: 0%观察；固定交易窗口内条件成立后才评估50%标准进攻")
            position_section_lines.append(
                "- **明天具体怎么做**: 旧强仓可持有；新仓只看主线核心是否在固定交易窗口内满足条件，强核心走竞价表态、开盘前几分钟或回封，普通结构只看09:50-10:10窗口"
                if has_personal_positions
                else "- **明天具体怎么做**: 只观察主线核心是否在固定交易窗口内满足条件；未满足0%，满足后才评估50%标准进攻"
            )
    else:
        if not best_stock:
            if watch_anchor:
                position_section_lines.extend(
                    [
                        "- **现在到底是什么状态**: 还没有缩到一只可买股",
                        "- **明天仓位放多少**: 0%（市场允许出手，但还没有可买股前不开仓）",
                        "- **明天具体怎么做**: 只观察明天先盯哪只，等它走成明天唯一能买的那只后再买",
                    ]
                )
            else:
                position_section_lines.extend(
                    [
                        "- **现在到底是什么状态**: 市场允许出手但还没有对象",
                        "- **明天仓位放多少**: 0%（没有标的可买）",
                        "- **明天具体怎么做**: 保持空仓，不做试错参与",
                    ]
                )
        elif step0_prediction == "DIFFICULT":
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 等开盘再确认",
                    "- **明天仓位放多少**: 开盘前重新评估后再定",
                    "- **明天具体怎么做**: 观望为主，不急于开仓",
                ]
            )
        elif step0_prediction == "NEUTRAL":
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 已经缩到一只可买股",
                    "- **明天仓位放多少**: 50%标准进攻（只在固定交易窗口内条件成立后）",
                    "- **明天具体怎么做**: 严格按买点触发，不追涨；固定交易窗口内条件不满足就转为0%",
                ]
            )
        else:
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 已经缩到一只可买股",
                    "- **明天仓位放多少**: 最多50%（正常参与）",
                    "- **明天具体怎么做**: 积极执行买点计划",
                ]
            )

    pre_market_lines = []
    if best_stock:
        if "signal" in best_stock:
            signal = best_stock["signal"]
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            structure_stop_30m = minute_plan.get("structure_stop_30m")
            if confirm_price:
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 09:50-10:10站上{confirm_price:.2f}提醒")
            else:
                entry_range = best_stock.get("entry_range", (signal.entry_price, signal.entry_price))
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 触及{entry_range[0]:.2f}-{entry_range[1]:.2f}提醒")
            if structure_stop_30m:
                pre_market_lines.append(f"- **风险预埋**: 若买入，先盯失效价{structure_stop_30m:.2f}")
        else:
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            pre_market_lines.append(
                f"- **关注标的**: {best_stock.get('name')}({best_stock.get('code')}) - "
                f"{'09:50-10:10站上' + format(confirm_price, '.2f') + '后按条件触发' if confirm_price else '按条件触发'}"
            )
    elif watch_anchor:
        minute_plan = watch_anchor.get("minute_plan") or {}
        stop_plan = watch_anchor.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
        observation_price_focus_text = build_observation_price_focus_text(price_focus)
        pre_market_lines.append(
            f"- **{watch_anchor_type}**: {watch_anchor.get('name')}({watch_anchor.get('code')}) - "
            f"{normalize_trading_time_text(compose_observation_focus_text(confirm_text, observation_price_focus_text))}"
        )
        append_watch_anchor_note(pre_market_lines, watch_anchor)
        append_observation_price_focus_note(pre_market_lines, price_focus)
    else:
        pre_market_lines.append("- **空仓准备**: 无操作标的，准备观望")
    pre_market_lines.extend(["- 查看隔夜消息、外围市场、期货走势", "- 确认A杀冷却池无变化"])

    opening_lines = [
        "- 观察涨跌比、昨日涨停溢价率",
        "- 重新评估Step 0裁决是否仍然成立",
        "- 观察唯一对象的竞价表态、匹配金额、委托稳定和板块同步",
        "- 若竞价表态和开盘前几分钟承接同时成立，按09:30-09:35窗口处理；不成立回到0%",
    ]
    if trade_gate_open and best_stock:
        first_hour_lines = [
            "- 竞价/开盘前几分钟未触发时，只等09:50-10:10窗口内条件成立",
            "- 直接高开离计划过远且没有回封/承接方案 → 放弃，等新的买点",
        ]
        intraday_lines = [
            "- 竞价表态、开盘承接、打板/回封或09:50-10:10窗口任一路径命中，且大盘不崩 → 按预设仓位执行",
            "- 买入后按失效价和单笔-5%底线处理风险；若失效价过深，则直接用单笔-5%底线",
            "- 跌破执行止损线 → 无条件止损",
        ]
    elif trade_gate_open and watch_anchor:
        first_hour_lines = [
            "- 市场允许出手，但当前还不是明天唯一能买的那只，本时段先看重点盯盘股能否在固定交易窗口内满足条件",
            "- 只有它继续抗跌并走成明天唯一能买的那只，才允许进入参与流程",
        ]
        intraday_lines = [
            "- 继续只盯明天先盯哪只，不做多票分散",
            "- 它如果始终走不成明天唯一能买的那只 → 当天继续等待，不抢跑",
            "- 若候选盘中直接走坏或失守关键位/带 → 取消它的执行资格",
        ]
    else:
        if can_ten_confirm_upgrade:
            first_hour_lines = [
                "- 当前是0%观察，本时段只确认主线核心是否在固定交易窗口内满足条件",
                "- 重点观察优先锚点是否继续走强；确认后才评估50%标准进攻，未确认保持0%",
            ]
            intraday_lines = [
                "- 以观察和处理持仓为主；新仓只允许固定交易窗口内条件成立后的主线核心50%标准进攻",
                "- 若你有仓位，失效价失守或日内明显转弱 → 执行减仓/止损",
                "- 若观察标的全天未形成更强确认 → 继续等待",
            ]
        else:
            first_hour_lines = [
                "- 当前条件不允许新开仓，本时段只确认环境是否继续支持持仓/观察",
                "- 重点观察优先锚点是否继续走强；若你有旧仓，只处理旧仓，不做新增",
            ]
            intraday_lines = [
                "- 以观察和处理持仓为主，不做新开仓",
                "- 若你有仓位，失效价失守或日内明显转弱 → 执行减仓/止损",
                "- 若观察标的全天未形成更强确认 → 继续等待",
            ]

    closing_lines = ["- 未买入的保持观望"]
    if trade_gate_open and best_stock:
        closing_lines.append("- 已买入的确认风险线是否需要上移")
    else:
        closing_lines.append("- 若你有旧仓，确认风险线是否需要上移")

    alert_rows = []
    for pred in today_predictions[:3]:
        actual_change = pred.get("actual_change_pct")
        if actual_change is not None:
            actual_change_str = f"{actual_change:+.2f}%"
            if pred.get("is_triggered") is True:
                trigger_status = "✅已触发"
            elif pred.get("is_triggered") is False:
                trigger_status = "⏳未触发"
            else:
                trigger_status = "❓未知"
        else:
            actual_change_str = "-"
            trigger_status = "待观察"
        alert_rows.append(
            {
                "name": pred.get("name", "?"),
                "code": pred.get("code", "?"),
                "deviation_days": pred.get("deviation_days", 0),
                "trigger_info": f"{pred.get('trigger_pct', 0):+.2f}%",
                "actual_change_str": actual_change_str,
                "trigger_status": trigger_status,
            }
        )
    for pred in nextday_predictions[:2]:
        alert_rows.append(
            {
                "name": pred.get("name", "?"),
                "code": pred.get("code", "?"),
                "deviation_days": pred.get("deviation_days", 0),
                "trigger_info": f"次日{pred.get('trigger_pct', 0):+.2f}%",
                "actual_change_str": "-",
                "trigger_status": "次日观察",
            }
        )

    return {
        "lines": [],
        "exports": {
            "action_rows": sanitize_user_visible_text(action_rows),
            "observation_priority_lines": sanitize_user_visible_text(observation_priority_lines),
            "backup_observation_lines": sanitize_user_visible_text(backup_observation_lines),
            "position_section_lines": sanitize_user_visible_text(position_section_lines),
            "pre_market_lines": sanitize_user_visible_text(pre_market_lines),
            "opening_lines": sanitize_user_visible_text(opening_lines),
            "first_hour_lines": sanitize_user_visible_text(first_hour_lines),
            "intraday_lines": sanitize_user_visible_text(intraday_lines),
            "closing_lines": sanitize_user_visible_text(closing_lines),
            "alert_rows": alert_rows,
            "candidate_quality_panel_fields": sanitize_user_visible_text(
                _build_candidate_quality_panel_fields(
                    step0_prediction_cn=step0_prediction_cn,
                    has_personal_positions=has_personal_positions,
                    daily_new_entry_limit=daily_new_entry_limit,
                    best_stock=best_stock,
                    watch_anchor=watch_anchor,
                )
            ),
            "candidate_quality_samples": sanitize_user_visible_text(
                _dedupe_candidates(
                    [
                        _quality_candidate(
                            best_stock,
                            quality_role="主买对象" if daily_new_entry_limit > 0 else "核心观察",
                            selection_quality="高",
                            entry_cost_state="确认中",
                            is_core=True,
                        ),
                        _quality_candidate(
                            watch_anchor,
                            quality_role="补位对象",
                            selection_quality="中",
                            entry_cost_state="确认中",
                        ),
                    ]
                    + list(display_observation_candidates)
                    + list(waiting_stocks)
                )
            ),
        },
        "module_logs": [],
    }
