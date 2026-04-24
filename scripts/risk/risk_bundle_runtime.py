__all__ = [
    "build_risk_bundle_contract",
    "build_step3_risk_bundle",
    "evaluate_limit_up_friction",
    "format_step3_risk_reason",
    "parse_limit_time_to_minutes",
]


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "risk.risk_bundle_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _append_unique_text(container, text):
    text = str(text or "").strip()
    if text and text not in container:
        container.append(text)


def _parse_limit_time_to_minutes(time_text):
    digits = "".join(ch for ch in str(time_text or "") if ch.isdigit())
    if len(digits) >= 6:
        digits = digits[:6]
        return int(digits[:2]) * 60 + int(digits[2:4])
    if len(digits) == 4:
        return int(digits[:2]) * 60 + int(digits[2:4])
    return None


def parse_limit_time_to_minutes(time_text):
    return _parse_limit_time_to_minutes(time_text)


def _evaluate_limit_up_friction(zhaban, last_limit_time="", turnover=0.0, board_count=1, *, safe_float, clamp):
    zhaban = int(safe_float(zhaban) or 0)
    turnover = safe_float(turnover)
    board_count = int(safe_float(board_count) or 1)

    if zhaban <= 0:
        return {"penalty": 0, "reason": ""}

    if zhaban == 1:
        penalty = 8
    elif zhaban == 2:
        penalty = 16
    elif zhaban == 3:
        penalty = 24
    else:
        penalty = 36 + min((zhaban - 4) * 2, 6)

    last_limit_minutes = _parse_limit_time_to_minutes(last_limit_time)
    if last_limit_minutes is not None:
        if last_limit_minutes <= 9 * 60 + 40:
            penalty -= 8
        elif last_limit_minutes <= 10 * 60 + 30:
            penalty -= 4
        elif last_limit_minutes >= 14 * 60 + 30:
            penalty += 8
        elif last_limit_minutes >= 13 * 60 + 30:
            penalty += 4

    if turnover >= 15:
        penalty += 4
    elif turnover >= 10:
        penalty += 2
    elif turnover <= 5:
        penalty -= 4
    elif turnover <= 8:
        penalty -= 2

    if board_count >= 3 and last_limit_minutes is not None and last_limit_minutes <= 10 * 60:
        penalty -= 2

    penalty = int(clamp(penalty, 0, 48))

    if zhaban >= 4 and last_limit_minutes is not None:
        if last_limit_minutes >= 14 * 60 + 30:
            reason = f"炸板{zhaban}次且尾盘才回封"
        elif last_limit_minutes <= 10 * 60 + 30:
            reason = f"炸板{zhaban}次但上午回封"
        else:
            reason = f"炸板{zhaban}次且回封不算早"
    elif zhaban == 3 and last_limit_minutes is not None and last_limit_minutes <= 10 * 60:
        reason = "炸板3次但快速回封"
    else:
        reason = f"炸板{zhaban}次"
    return {"penalty": penalty, "reason": reason}


def evaluate_limit_up_friction(zhaban, last_limit_time="", turnover=0.0, board_count=1, *, helpers=None):
    helpers = helpers or {}
    safe_float = helpers["safe_float"]
    clamp = helpers["clamp"]
    return _evaluate_limit_up_friction(
        zhaban,
        last_limit_time=last_limit_time,
        turnover=turnover,
        board_count=board_count,
        safe_float=safe_float,
        clamp=clamp,
    )


def format_step3_risk_reason(risk_penalties=None, repair_buffers=None, risk_level="", *, helpers=None):
    risk_penalties = [str(item).strip() for item in (risk_penalties or []) if str(item or "").strip()]
    repair_buffers = [str(item).strip() for item in (repair_buffers or []) if str(item or "").strip()]

    if risk_penalties and repair_buffers:
        if risk_level == "🟢 低风险":
            return f"虽有{'、'.join(risk_penalties)}，但{'、'.join(repair_buffers)}，净风险可控"
        if risk_level == "🟡 中风险":
            return f"风险项：{'、'.join(risk_penalties)}；缓冲项：{'、'.join(repair_buffers)}；仍需观察"
        return f"风险项：{'、'.join(risk_penalties)}；虽有{'、'.join(repair_buffers)}，但不足以对冲"

    if risk_penalties:
        prefix = "风险项：" if len(risk_penalties) >= 2 else ""
        return f"{prefix}{'、'.join(risk_penalties)}"

    if repair_buffers:
        return f"修复项：{'、'.join(repair_buffers)}，净风险可控"

    return "风险可控"


def build_step3_risk_bundle(
    data,
    target_date,
    mainline_name,
    core_stocks,
    secondary_stocks,
    gem_observation_stocks=None,
    zt_pool_by_sector=None,
    dt_pool_by_sector=None,
    persist_a_kill=False,
    *,
    helpers=None,
):
    helpers = helpers or {}
    return build_risk_bundle_contract(
        data,
        target_date,
        mainline_name,
        core_stocks,
        secondary_stocks,
        gem_observation_stocks=gem_observation_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        dt_pool_by_sector=dt_pool_by_sector,
        persist_a_kill=persist_a_kill,
        normalize_stock_code=helpers["normalize_stock_code"],
        safe_float=helpers["safe_float"],
        clamp=helpers["clamp"],
        get_abnormal_follow_risk_signal=helpers["get_abnormal_follow_risk_signal"],
        format_risk_reason=helpers.get("format_risk_reason", format_step3_risk_reason),
        update_a_kill_blacklist=helpers["update_a_kill_blacklist"],
    )


def build_risk_bundle_contract(
    data,
    target_date,
    mainline_name,
    core_stocks,
    secondary_stocks,
    gem_observation_stocks=None,
    zt_pool_by_sector=None,
    dt_pool_by_sector=None,
    persist_a_kill=False,
    *,
    normalize_stock_code,
    safe_float,
    clamp,
    get_abnormal_follow_risk_signal,
    format_risk_reason,
    update_a_kill_blacklist,
):
    zt_pool_by_sector = zt_pool_by_sector or data.get("zt_pool_by_sector", {}) or {}
    dt_pool_by_sector = dt_pool_by_sector or data.get("dt_pool_by_sector", {}) or {}
    gem_observation_stocks = gem_observation_stocks or []
    logs = []

    all_check_stocks = []
    seen_codes = set()
    for stock in list(core_stocks or []) + list(secondary_stocks or []) + list(gem_observation_stocks or []):
        code = normalize_stock_code((stock or {}).get("code", ""))
        if code and code in seen_codes:
            continue
        if code:
            seen_codes.add(code)
        all_check_stocks.append(dict(stock or {}))

    delete_group = []
    keep_group = []
    focus_group = []
    stock_rows = []
    stock_info_map = {}
    for stock in data.get("zt_pool", []) or []:
        code = normalize_stock_code(stock.get("代码", stock.get("code", "")))
        if code:
            stock_info_map[code] = {
                "close": stock.get("最新价", stock.get("close", 0)),
                "volume": stock.get("成交额", stock.get("volume", 0)),
                "open": stock.get("开盘价", stock.get("open", 0)),
                "high": stock.get("最高价", stock.get("high", 0)),
                "low": stock.get("最低价", stock.get("low", 0)),
                "封单额": stock.get("封单额", stock.get("封单资金", 0)),
                "换手": stock.get("换手率", stock.get("换手", 0)),
                "炸板次数": stock.get("炸板次数", 0),
                "首次封板时间": stock.get("首次封板时间", stock.get("first_limit_time", "")),
                "最后封板时间": stock.get("最后封板时间", stock.get("last_limit_time", "")),
            }

    abnormal_green_count = 0
    abnormal_red_count = 0
    by_code = {}

    for original in all_check_stocks:
        stock = dict(original or {})
        code = stock.get("code", "")
        name = stock.get("name", "")
        pattern = stock.get("pattern", "未知")

        info = stock_info_map.get(code, {})
        stock["close"] = stock.get("close", 0) or info.get("close", 0)
        stock["volume"] = stock.get("volume", 0) or info.get("volume", 0)
        stock["high"] = info.get("high", 0)
        stock["low"] = info.get("low", 0)
        stock["open"] = info.get("open", 0)

        fengdan = info.get("封单额", 0)
        huanshou = info.get("换手", 0)
        zhaban = info.get("炸板次数", 0)
        last_limit_time = info.get("最后封板时间", "")
        change = stock.get("change", stock.get("change_pct", 0))
        abnormal_signal = get_abnormal_follow_risk_signal(stock)
        abnormal_light = abnormal_signal.get("light", "🟡 黄灯")
        abnormal_delta = int(abnormal_signal.get("delta", 0) or 0)
        abnormal_reason = abnormal_signal.get("reason", "")
        abnormal_forecast = abnormal_signal.get("forecast", "")

        risk_score = 0
        raw_risk_score = 0
        risk_penalties = []
        repair_buffers = []
        tomorrow_risk = ""

        friction_snapshot = _evaluate_limit_up_friction(
            zhaban,
            last_limit_time=last_limit_time,
            turnover=huanshou,
            board_count=stock.get("连板数", 1),
            safe_float=safe_float,
            clamp=clamp,
        )
        friction_penalty = int(friction_snapshot.get("penalty", 0) or 0)
        friction_reason = friction_snapshot.get("reason", "")
        if friction_penalty > 0:
            risk_score += friction_penalty
            raw_risk_score += friction_penalty
            _append_unique_text(risk_penalties, friction_reason)
            if friction_penalty >= 34:
                tomorrow_risk = "明日低开风险大"
            elif friction_penalty >= 22:
                tomorrow_risk = "明日分歧可能继续放大"
            elif friction_penalty >= 10:
                tomorrow_risk = "明日可能低开"

        if pattern == "一字板" and fengdan < 100000000:
            risk_score += 25
            raw_risk_score += 25
            _append_unique_text(risk_penalties, "一字板封单弱")
            tomorrow_risk = "明日可能开板即炸"

        if stock.get("连板数", 1) >= 3 and huanshou > 30:
            risk_score += 20
            raw_risk_score += 20
            _append_unique_text(risk_penalties, "高换手连板")
            tomorrow_risk = "明日分歧可能加大"

        sector = stock.get("sector", "")
        sector_rank = 0
        for idx, sector_stock in enumerate(zt_pool_by_sector.get(sector, []) or []):
            if sector_stock.get("代码", sector_stock.get("code", "")) == code:
                sector_rank = idx + 1
                break
        if sector_rank > 3:
            risk_score += 15
            raw_risk_score += 15
            _append_unique_text(risk_penalties, f"板块后排第{sector_rank}")
            if not tomorrow_risk:
                tomorrow_risk = "明日可能断板"

        if 0 < change < 5:
            risk_score += 10
            raw_risk_score += 10
            _append_unique_text(risk_penalties, "涨幅不足")
            if not tomorrow_risk:
                tomorrow_risk = "明日可能走弱"

        risk_score += abnormal_delta
        if abnormal_reason and abnormal_reason != "无异动承接信息":
            if abnormal_delta < 0:
                _append_unique_text(repair_buffers, abnormal_reason)
            else:
                raw_risk_score += abnormal_delta
                _append_unique_text(risk_penalties, abnormal_reason)
        if abnormal_light == "🟢 绿灯":
            abnormal_green_count += 1
        elif abnormal_light == "🔴 红灯":
            abnormal_red_count += 1

        if abnormal_light == "🔴 红灯":
            tomorrow_risk = abnormal_forecast or tomorrow_risk or "异动后承接转弱，明日易低开或继续下杀"
        elif abnormal_light == "🟠 橙灯" and not tomorrow_risk:
            tomorrow_risk = abnormal_forecast or "异动刚出现，明日先看承接"
        elif abnormal_light in ["🟢 绿灯", "🟡 黄灯"] and abnormal_forecast and not tomorrow_risk:
            tomorrow_risk = abnormal_forecast

        if not tomorrow_risk:
            tomorrow_risk = "形态正常，明日看竞价"

        risk_score = max(risk_score, 0)
        if abnormal_light == "🟢 绿灯" and risk_score < 20:
            tomorrow_risk = "异动后承接强，明日即使低开也先看60分钟确认"
        elif abnormal_light == "🟡 黄灯" and risk_score < 20 and "低开风险" in tomorrow_risk:
            tomorrow_risk = "异动后仍在消化，明日先看竞价与承接是否继续稳定"
        elif abnormal_light == "🟠 橙灯" and risk_score < 40 and "低开风险" in tomorrow_risk:
            tomorrow_risk = "异动刚出现且承接未验证，明日先看是否跌得下去"

        if abnormal_light == "🟢 绿灯" and raw_risk_score >= 30:
            tomorrow_risk = "盘中分歧不小，但承接仍在；明日只看竞价和60分钟确认，不宜直接乐观"
        elif abnormal_light == "🟢 绿灯" and raw_risk_score >= 12 and risk_score < 20:
            tomorrow_risk = "分歧已出现但承接尚可，明日只看回踩后的60分钟确认"
        elif abnormal_light == "🟡 黄灯" and raw_risk_score >= 20:
            tomorrow_risk = abnormal_forecast or "仍在消化分歧，明日先看竞价与承接"

        enriched = {
            **stock,
            "reason": "风险可控",
            "tomorrow_risk": tomorrow_risk,
            "risk_score": risk_score,
            "raw_risk_score": raw_risk_score,
            "abnormal_light": abnormal_light,
            "risk_penalties": risk_penalties,
            "repair_buffers": repair_buffers,
        }

        if risk_score >= 40:
            risk_level = "🔴 高风险"
            dest = "明天先回避谁"
            delete_group.append(enriched)
        elif risk_score >= 20:
            risk_level = "🟡 中风险"
            dest = "观察竞价"
            keep_group.append(enriched)
        else:
            risk_level = "🟢 低风险"
            dest = "可按计划"
            focus_group.append(enriched)

        enriched["reason"] = format_risk_reason(
            risk_penalties=risk_penalties,
            repair_buffers=repair_buffers,
            risk_level=risk_level,
        )
        enriched["risk_level"] = risk_level
        enriched["dest"] = dest

        row = {
            **enriched,
            "risk_level": risk_level,
            "dest": dest,
            "pattern": pattern,
            "name": name,
            "code": code,
        }
        stock_rows.append(row)
        if code:
            by_code[normalize_stock_code(code)] = row

    _append_log(logs, "risk_scoring", "success", "已完成个股风险评分", stock_count=len(stock_rows))

    risk_sectors_from_dt = []
    for sector_name, stocks in dt_pool_by_sector.items():
        if len(stocks or []) >= 3:
            risk_sectors_from_dt.append(
                {
                    "sector": sector_name,
                    "count": len(stocks),
                    "stocks": [item.get("name", item.get("名称", "")) for item in stocks[:3]],
                }
            )

    mainline_a_kill = False
    mainline_dt_stocks = []
    for sector_name, stocks in dt_pool_by_sector.items():
        if mainline_name and (mainline_name in sector_name or sector_name in mainline_name):
            mainline_dt_stocks = stocks
            break

    mainline_zt_count = 0
    for sector_name, stocks in zt_pool_by_sector.items():
        if mainline_name and (mainline_name in sector_name or sector_name in mainline_name):
            mainline_zt_count = len(stocks)
            break

    mainline_change = 0
    sector_fund_flow = data.get("sector_fund_flow", {}) or {}
    if sector_fund_flow:
        for sector in sector_fund_flow.get("inflow", []) or []:
            sector_name = sector.get("name", "")
            if mainline_name and (mainline_name in sector_name or sector_name in mainline_name):
                mainline_change = sector.get("zdf", 0)
                break
        if mainline_change == 0:
            for sector in sector_fund_flow.get("outflow", []) or []:
                sector_name = sector.get("name", "")
                if mainline_name and (mainline_name in sector_name or sector_name in mainline_name):
                    mainline_change = sector.get("zdf", 0)
                    break

    structural_a_kill = False
    structural_reason = ""
    if mainline_change <= -5:
        structural_a_kill = True
        structural_reason = f"主线当日跌幅{mainline_change:+.2f}%过深，已接近结构破坏"
    elif mainline_change <= -3 and mainline_zt_count == 0 and len(mainline_dt_stocks) >= 1:
        structural_a_kill = True
        structural_reason = "主线转弱且板块内已出现跌停，缺乏修复承接"

    if len(mainline_dt_stocks) >= 3:
        mainline_a_kill = True
    elif structural_a_kill:
        mainline_a_kill = True

    a_kill_blacklist_updates = []
    if persist_a_kill and mainline_a_kill:
        a_kill_blacklist_updates = update_a_kill_blacklist(target_date, mainline_dt_stocks, mainline_name)

    _append_log(logs, "risk_grouping", "success", "已完成风险分组与A杀判断", mainline_a_kill=mainline_a_kill)

    return {
        "all_check_stocks": all_check_stocks,
        "stock_rows": stock_rows,
        "by_code": by_code,
        "delete_group": delete_group,
        "keep_group": keep_group,
        "focus_group": focus_group,
        "abnormal_green_count": abnormal_green_count,
        "abnormal_red_count": abnormal_red_count,
        "risk_sectors_from_dt": risk_sectors_from_dt,
        "mainline_a_kill": mainline_a_kill,
        "mainline_dt_stocks": mainline_dt_stocks,
        "mainline_zt_count": mainline_zt_count,
        "mainline_change": mainline_change,
        "structural_a_kill": structural_a_kill,
        "structural_reason": structural_reason,
        "a_kill_blacklist_updates": a_kill_blacklist_updates,
        "module_logs": logs,
    }
