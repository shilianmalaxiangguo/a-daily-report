def _format_closed_gate_buy_limit_text(position_level, final_gate):
    final_gate = final_gate or {}
    if final_gate.get("allow_conditional_30"):
        return "等10点确认，未确认不开"
    return f"⛔{position_level}禁止新开仓"


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
                    "trigger": f"明日首个60分钟站上{confirm_price:.2f}" if confirm_price else "明日60分钟确认后触发",
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
                        f"明日首个60分钟站上{confirm_price:.2f}后按{best_stock.get('trigger', '条件')}执行"
                        if confirm_price
                        else f"明日60分钟确认后按{best_stock.get('trigger', '条件')}执行"
                    ),
                    "risk_window": f"{(stop_plan or {}).get('summary', '先看30分钟结构 / 最晚-5%')} / "
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
                    f"首个60分钟站上{confirm_price:.2f}后，再看是否走成明天唯一能买的那只"
                    if confirm_price
                    else "先看60分钟确认，再看是否走成明天唯一能买的那只"
                ),
                "risk_window": f"{(price_focus or {}).get('key_zone_display', '-')} / "
                f"{format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
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
                f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
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
            f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
        )
        append_observation_price_focus_note(backup_observation_lines, price_focus, prefix="  ")

    position_section_lines = [
        f"- **市场环境档位**: {position_level}",
        f"- **明日裁决**: {step0_prediction_cn}",
        f"- **怎么执行**: {get_execution_framework_text()}",
    ]
    if position_level == "一档（空仓档）":
        position_section_lines.extend(
            [
                "- **现在到底是什么状态**: 空仓",
                "- **明天仓位放多少**: 0%（必须空仓）",
                "- **明天具体怎么做**: 清仓或保持空仓，禁止任何买入",
            ]
        )
    elif position_level == "二档（防守档）":
        position_section_lines.append("- **现在到底是什么状态**: 防守观察")
        if final_gate.get("should_reduce"):
            position_section_lines.append("- **明天仓位放多少**: 最多30%（只留强者，不做新增）")
            position_section_lines.append(
                "- **明天具体怎么做**: 只处理你的旧仓，去弱留强，禁止新开仓"
                if has_personal_positions
                else "- **明天具体怎么做**: 市场级原则是若你有旧仓就去弱留强，禁止新开仓"
            )
        else:
            position_section_lines.append("- **明天仓位放多少**: 最多30%（只在10点确认后条件试错）")
            position_section_lines.append(
                "- **明天具体怎么做**: 旧强仓可持有；新仓只允许主线核心完成10点确认后小仓试错"
                if has_personal_positions
                else "- **明天具体怎么做**: 只观察主线核心是否完成10点确认，确认前不开，确认后最多30%条件试错"
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
                        "- **明天具体怎么做**: 空仓等待，不做任何试错买入",
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
                    "- **明天仓位放多少**: 最多30%（轻仓试错）",
                    "- **明天具体怎么做**: 严格按买点触发，不追涨",
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
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 首个60分钟站上{confirm_price:.2f}提醒")
            else:
                entry_range = best_stock.get("entry_range", (signal.entry_price, signal.entry_price))
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 触及{entry_range[0]:.2f}-{entry_range[1]:.2f}提醒")
            if structure_stop_30m:
                pre_market_lines.append(f"- **止损预埋**: 若买入，30分钟结构止损先盯{structure_stop_30m:.2f}")
        else:
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            pre_market_lines.append(
                f"- **关注标的**: {best_stock.get('name')}({best_stock.get('code')}) - "
                f"{'首个60分钟站上' + format(confirm_price, '.2f') + '后按条件触发' if confirm_price else '按条件触发'}"
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
            f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
        )
        append_watch_anchor_note(pre_market_lines, watch_anchor)
        append_observation_price_focus_note(pre_market_lines, price_focus)
    else:
        pre_market_lines.append("- **空仓准备**: 无操作标的，准备观望")
    pre_market_lines.extend(["- 查看隔夜消息、外围市场、期货走势", "- 确认A杀冷却池无变化"])

    opening_lines = [
        "- 观察涨跌比、昨日涨停溢价率",
        "- 重新评估Step 0裁决是否仍然成立",
        "- 观察观察池个股的竞价情况",
        "- 这30分钟只确认环境，不抢买点",
    ]
    if trade_gate_open and best_stock:
        first_hour_lines = [
            "- 日线环境未被破坏 + 60分钟结构确认 → 才允许执行买点",
            "- 直接高开离买点>5% 或 60分钟走弱 → 放弃，等新的买点",
        ]
        intraday_lines = [
            "- 60分钟确认后，触及买点区间且大盘不崩 → 按预设仓位买入",
            "- 买入后用30分钟结构设置止损；若结构止损过深，则直接用单笔-5%硬止损",
            "- 跌破执行止损线 → 无条件止损",
        ]
    elif trade_gate_open and watch_anchor:
        first_hour_lines = [
            "- 市场允许出手，但当前还不是明天唯一能买的那只，本时段先看重点盯盘股能否完成60分钟确认",
            "- 只有它继续抗跌并走成明天唯一能买的那只，才允许进入买入流程",
        ]
        intraday_lines = [
            "- 继续只盯明天先盯哪只，不做多票分散",
            "- 它如果始终走不成明天唯一能买的那只 → 当天继续等待，不抢跑",
            "- 若候选盘中直接走坏或失守关键位/带 → 取消它的执行资格",
        ]
    else:
        if final_gate.get("allow_conditional_30"):
            first_hour_lines = [
                "- 当前仍是防守观察，本时段只确认主线核心是否完成10点确认",
                "- 重点观察优先锚点是否继续走强；确认后最多30%条件试错，未确认不开",
            ]
            intraday_lines = [
                "- 以观察和处理持仓为主；新仓只允许10点确认后的主线核心小仓试错",
                "- 若你有仓位，30分钟结构失守或日内明显转弱 → 执行减仓/止损",
                "- 若观察标的全天未形成更强确认 → 继续等待",
            ]
        else:
            first_hour_lines = [
                "- 当前门控不允许新开仓，本时段只确认环境是否继续支持持仓/观察",
                "- 重点观察优先锚点是否继续走强；若你有旧仓，只处理旧仓，不做新增",
            ]
            intraday_lines = [
                "- 以观察和处理持仓为主，不做新开仓",
                "- 若你有仓位，30分钟结构失守或日内明显转弱 → 执行减仓/止损",
                "- 若观察标的全天未形成更强确认 → 继续等待",
            ]

    closing_lines = ["- 未买入的保持观望"]
    if trade_gate_open and best_stock:
        closing_lines.append("- 已买入的确认30分钟止损线是否需要上移")
    else:
        closing_lines.append("- 若你有旧仓，确认30分钟结构止损线是否需要上移")

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
            "action_rows": action_rows,
            "observation_priority_lines": observation_priority_lines,
            "backup_observation_lines": backup_observation_lines,
            "position_section_lines": position_section_lines,
            "pre_market_lines": pre_market_lines,
            "opening_lines": opening_lines,
            "first_hour_lines": first_hour_lines,
            "intraday_lines": intraday_lines,
            "closing_lines": closing_lines,
            "alert_rows": alert_rows,
        },
        "module_logs": [],
    }
