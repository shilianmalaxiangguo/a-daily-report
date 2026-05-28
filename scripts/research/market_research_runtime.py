from report.market_fit_calibration import build_market_fit_calibration
import daily_report_analysis_utils as analysis_utils


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


_NON_DIRECTIONAL_LHB_SECTORS = {
    "HS",
    "GEM",
    "STAR",
    "BJ",
    "SH",
    "SZ",
    "沪深",
    "创业板",
    "科创板",
    "北交所",
    "未知",
    "未归类",
    "-",
}


def _is_directional_lhb_sector(value):
    sector = str(value or "").strip()
    return bool(sector and sector not in _NON_DIRECTIONAL_LHB_SECTORS)


def _has_resolved_mainline_turnover_summary(summary):
    if not isinstance(summary, dict):
        return False
    if not str(summary.get("current_mainline") or "").strip():
        return False
    for row in summary.get("turnover_share_trend_rows") or []:
        if not isinstance(row, dict):
            continue
        has_mainline_turnover = str(row.get("mainline_turnover") or "").strip() not in {"", "-", "数据暂缺"}
        missing_market_turnover = str(row.get("market_turnover") or "").strip() in {"", "-", "数据暂缺"}
        if has_mainline_turnover and missing_market_turnover:
            return False
    return True


def _confirmed_attack_line(mainline_turnover_summary):
    if not isinstance(mainline_turnover_summary, dict):
        return ""
    attack_summary = mainline_turnover_summary.get("mainline_attack_evidence_summary") or {}
    if not isinstance(attack_summary, dict):
        return ""
    if str(attack_summary.get("attack_state") or "").strip() != "confirmed_attack":
        return ""
    return str(attack_summary.get("primary_line") or "").strip()


def _align_current_mainline_history_record_with_attack(current_record, mainline_turnover_summary, target_date):
    primary_line = _confirmed_attack_line(mainline_turnover_summary)
    if not primary_line:
        return current_record or {}

    current_record = dict(current_record or {})
    old_mainline = str(
        current_record.get("primary_mainline")
        or current_record.get("leading_line")
        or ""
    ).strip()
    if old_mainline == primary_line:
        return current_record

    attack_summary = mainline_turnover_summary.get("mainline_attack_evidence_summary") or {}
    evidence = str(
        attack_summary.get("confirmation_evidence")
        or mainline_turnover_summary.get("conclusion")
        or f"{primary_line}攻击证据成立"
    ).strip()
    existing_rotation_label = str(current_record.get("rotation_label") or "").strip()
    existing_rotation_summary = str(current_record.get("rotation_summary") or "").strip()
    current_record["date"] = str(current_record.get("date") or target_date or "").strip()
    current_record["primary_mainline"] = primary_line
    current_record["leading_line"] = primary_line
    current_record["secondary_mainline"] = ""
    current_record["competition_mainline"] = ""
    if existing_rotation_label == "逆势攻击" and existing_rotation_summary:
        current_record["rotation_summary"] = (
            existing_rotation_summary
            if evidence and evidence in existing_rotation_summary
            else "；".join([part for part in (existing_rotation_summary, evidence) if part])
        )
    else:
        current_record["rotation_summary"] = evidence
    current_record["source"] = "market_research_snapshot.confirmed_attack"
    return current_record


def _refresh_current_mainline_record_from_rotation(current_record, rotation_snapshot, target_date):
    current_record = dict(current_record or {})
    rotation_snapshot = rotation_snapshot or {}
    rotation_label = str(rotation_snapshot.get("rotation_label") or "").strip()
    rotation_summary = str(
        rotation_snapshot.get("summary_text")
        or rotation_snapshot.get("rotation_reason")
        or ""
    ).strip()
    if not rotation_label and not rotation_summary:
        return current_record

    current_record["date"] = str(current_record.get("date") or target_date or "").strip()
    if rotation_label:
        current_record["rotation_label"] = rotation_label
    if rotation_summary:
        current_record["rotation_summary"] = rotation_summary
    return current_record


def _mainline_turnover_summary_conflicts_with_current_record(summary, current_record):
    if not isinstance(summary, dict):
        return True
    current_record = current_record or {}
    record_text = " ".join(
        str(current_record.get(key) or "")
        for key in ("rotation_label", "market_state", "state", "rotation_summary")
    )
    conclusion_text = " ".join(
        str(summary.get(key) or "")
        for key in ("share_trend_label", "conclusion", "data_text", "action_text")
    )
    if ("逆势攻击" in record_text or "放量杀跌" in record_text) and "主线切换" in conclusion_text:
        return True
    return False


def _resolve_effective_total_turnover(
    data,
    observation_snapshot,
    target_date,
    *,
    get_market_total_turnover_from_fact_db=None,
):
    data = data or {}
    observation_snapshot = observation_snapshot or {}
    for value in (
        data.get("total_turnover"),
        observation_snapshot.get("turnover"),
        observation_snapshot.get("total_turnover"),
    ):
        total_turnover = _safe_float(value)
        if total_turnover > 0:
            return total_turnover

    if callable(get_market_total_turnover_from_fact_db):
        total_turnover = _safe_float(get_market_total_turnover_from_fact_db(target_date))
        if total_turnover > 0:
            return total_turnover

    return 0.0


def _fill_sector_snapshot_total_turnover(snapshot, total_turnover):
    if not isinstance(snapshot, dict):
        return snapshot or {}
    if not snapshot:
        return {}
    total_turnover = round(_safe_float(total_turnover), 2)
    if total_turnover <= 0 or _safe_float(snapshot.get("total_turnover")) > 0:
        return snapshot
    snapshot = dict(snapshot)
    sector_turnover = _safe_float(snapshot.get("sector_turnover"))
    snapshot["total_turnover"] = total_turnover
    if sector_turnover > 0:
        snapshot["turnover_share_pct"] = round(sector_turnover / total_turnover * 100, 2)
    return snapshot


def _derive_lhb_capital_intent(data, mainline_name=""):
    data = data or {}
    buy_rows = list(data.get("lhb_net_buy_top10") or [])
    sell_rows = list(data.get("lhb_net_sell_top10") or [])
    if not buy_rows and not sell_rows:
        return {}, {}

    sector_totals = {}
    total_buy_amount = 0.0
    for item in buy_rows:
        amount = _safe_float((item or {}).get("net_buy_amount_yi"))
        total_buy_amount += amount
        sector = str((item or {}).get("sector") or "").strip()
        if not _is_directional_lhb_sector(sector):
            continue
        sector_totals[sector] = sector_totals.get(sector, 0.0) + amount
    if sector_totals:
        top_sector, top_amount = max(sector_totals.items(), key=lambda pair: pair[1])
        intensity_text = f"龙虎榜净买入集中在{top_sector}，约{top_amount:.2f}亿"
    else:
        top_sector, top_amount = "未归类", total_buy_amount
        intensity_text = f"龙虎榜净买入行业方向未归类，约{top_amount:.2f}亿"
    sell_amount = abs(sum(_safe_float((item or {}).get("net_buy_amount_yi")) for item in sell_rows))
    strength = "强" if top_amount >= 5 else "中" if top_amount >= 2 else "弱"
    style_shift = "资金向主线集中" if mainline_name and top_sector == mainline_name else "资金偏轮动试探"
    current_state = f"龙虎榜资金{strength}，方向未归类" if top_sector == "未归类" else f"龙虎榜资金{strength}，方向在{top_sector}"
    status = {
        "capital_strength": strength,
        "capital_intensity": f"{intensity_text}；净卖出端约{sell_amount:.2f}亿",
        "capital_direction": top_sector,
        "capital_intent": "承接主线核心" if mainline_name and top_sector == mainline_name else "尝试外溢或轮动",
        "style_shift": style_shift,
        "event_attribute": "龙虎榜资金行为",
    }
    lhb_validates_mainline = bool(mainline_name and top_sector == mainline_name)
    conclusion = {
        "current_capital_state": current_state,
        "mainline_attitude": "资金仍在主线内确认" if lhb_validates_mainline else f"龙虎榜未验证{mainline_name or '主线'}",
        "tomorrow_action_meaning": "只看主线核心承接，不追非主线热票" if lhb_validates_mainline else "先看板块攻击证据，龙虎榜只作为验证层",
    }
    return status, conclusion


def _format_signed_amount(value, unit="亿"):
    amount = _safe_float(value)
    sign = "+" if amount > 0 else ""
    return f"{sign}{amount:.2f}{unit}"


def _format_share_change(value):
    change = _safe_float(value)
    if not change:
        return ""
    sign = "+" if change > 0 else ""
    return f"成交占比{sign}{change:.1f}pct"


def _find_sector_evidence_row(rows, sector_name):
    for row in rows or []:
        if isinstance(row, dict) and _sector_names_match(row.get("sector_name"), sector_name):
            return row
    return {}


def _derive_capital_intent_breakdown(
    mainline_turnover_summary,
    sector_attack_evidence_rows,
    lhb_capital_status,
    capital_conclusion,
):
    attack_summary = (mainline_turnover_summary or {}).get("mainline_attack_evidence_summary") or {}
    primary_line = str(
        attack_summary.get("primary_line")
        or (mainline_turnover_summary or {}).get("current_mainline")
        or ""
    ).strip()
    if not primary_line:
        return {}, capital_conclusion or {}

    attack_state = str(attack_summary.get("attack_state") or "").strip()
    confirmed_attack = attack_state == "confirmed_attack"
    evidence_row = _find_sector_evidence_row(sector_attack_evidence_rows, primary_line)
    if not confirmed_attack or not evidence_row:
        return {}, capital_conclusion or {}

    rank = evidence_row.get("net_inflow_rank")
    amount = evidence_row.get("net_inflow_amount")
    if rank and amount not in (None, ""):
        sector_fund_attitude = f"{primary_line}板块攻击资金确认：净流入第{rank}，{_format_signed_amount(amount)}"
    else:
        sector_fund_attitude = f"{primary_line}板块攻击资金确认"

    strength_parts = []
    if evidence_row.get("limit_up_count") not in (None, ""):
        strength_parts.append(f"涨停{int(_safe_float(evidence_row.get('limit_up_count')))}")
    if evidence_row.get("high_anchor_height") not in (None, ""):
        strength_parts.append(f"高标{int(_safe_float(evidence_row.get('high_anchor_height')))}")
    share_change_text = _format_share_change(evidence_row.get("turnover_share_change"))
    if share_change_text:
        strength_parts.append(share_change_text)
    strength_feedback = "，".join(strength_parts) if strength_parts else attack_summary.get("confirmation_evidence", "-")

    lhb_direction = str((lhb_capital_status or {}).get("capital_direction") or "").strip()
    if lhb_direction and _sector_names_match(lhb_direction, primary_line):
        lhb_validation = "龙虎榜验证主线"
        capital_consistency = "板块攻击成立，龙虎榜同步验证"
        tomorrow_meaning = "先按板块攻击线观察，龙虎榜作为加分确认"
    elif lhb_direction:
        lhb_validation = f"龙虎榜方向在{lhb_direction}，未验证主线"
        capital_consistency = "板块攻击成立，龙虎榜未验证"
        tomorrow_meaning = "先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决"
    else:
        lhb_validation = "龙虎榜未验证主线"
        capital_consistency = "板块攻击成立，龙虎榜未验证"
        tomorrow_meaning = "先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决"

    capital_conclusion = dict(capital_conclusion or {})
    capital_conclusion["mainline_attitude"] = capital_consistency
    capital_conclusion["tomorrow_action_meaning"] = tomorrow_meaning
    if not capital_conclusion.get("current_capital_state"):
        capital_conclusion["current_capital_state"] = sector_fund_attitude

    return {
        "sector_fund_attitude": sector_fund_attitude,
        "strength_feedback": strength_feedback,
        "lhb_validation": lhb_validation,
        "capital_consistency": capital_consistency,
        "tomorrow_meaning": tomorrow_meaning,
    }, capital_conclusion


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "research.market_research_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _collect_market_fit_observation_pool(data, observation_snapshot):
    pool = []
    for source in (
        (observation_snapshot or {}).get("abnormal_watch_pool"),
        (observation_snapshot or {}).get("leader_memory_bank"),
        (data or {}).get("watchlist"),
        (data or {}).get("candidates"),
    ):
        if isinstance(source, list):
            pool.extend(item for item in source if isinstance(item, dict))
    return pool


def _collect_market_fit_strong_samples(data):
    data = data or {}
    if isinstance(data.get("strong_samples"), list):
        return data.get("strong_samples") or []
    return data.get("zt_pool") or []


def _load_recent_mainline_history_for_cycle_calendar(loader, target_date):
    try:
        return loader(target_date, lookback_days=25, max_scan_days=60)
    except TypeError as exc:
        if "max_scan_days" not in str(exc):
            raise
        return loader(target_date, lookback_days=25)


def _mainline_name_from_history_record(record):
    record = record or {}
    return str(record.get("primary_mainline") or record.get("leading_line") or "").strip()


def _history_date(record):
    return str((record or {}).get("date") or (record or {}).get("trade_date") or "").strip()


def _load_recent_turnover_by_daily_mainline(loader, recent_mainline_history, target_date):
    records_by_sector = {}
    record_by_date = {}
    for record in recent_mainline_history or []:
        record_date = _history_date(record)
        mainline = _mainline_name_from_history_record(record)
        if not record_date or not mainline:
            continue
        records_by_sector.setdefault(mainline, set()).add(record_date)
        record_by_date[record_date] = record

    rows_by_date = {}
    for mainline, expected_dates in records_by_sector.items():
        try:
            rows = loader(target_date, mainline, lookback_days=25) or []
        except TypeError:
            rows = loader(target_date, mainline) or []
        except Exception:
            rows = []
        for row in rows or []:
            row = dict(row or {})
            row_date = _history_date(row)
            if row_date not in expected_dates:
                continue
            record = record_by_date.get(row_date) or {}
            row["date"] = row_date
            row.setdefault("cycle_mainline", mainline)
            row.setdefault("daily_attack_line", str((record or {}).get("daily_attack_line") or mainline).strip())
            rows_by_date[row_date] = row
    return [rows_by_date[date] for date in sorted(rows_by_date)]


def _fill_turnover_placeholders_for_mainline_history(recent_sector_turnover_history, recent_mainline_history):
    rows_by_date = {
        _history_date(row): dict(row or {})
        for row in recent_sector_turnover_history or []
        if _history_date(row)
    }
    completed = []
    for record in recent_mainline_history or []:
        record_date = _history_date(record)
        mainline = _mainline_name_from_history_record(record)
        if not record_date or not mainline:
            continue
        row = rows_by_date.get(record_date)
        if row:
            row.setdefault("date", record_date)
            row.setdefault("cycle_mainline", mainline)
            row.setdefault("daily_attack_line", str((record or {}).get("daily_attack_line") or mainline).strip())
            completed.append(row)
            continue
        completed.append(
            {
                "date": record_date,
                "sector_name": mainline,
                "cycle_mainline": mainline,
                "daily_attack_line": str((record or {}).get("daily_attack_line") or mainline).strip(),
                "sector_turnover": 0.0,
                "total_turnover": 0.0,
                "turnover_share_pct": 0.0,
                "source_status": "history_missing",
            }
        )
    return completed[-25:]


def _sector_name_from_row(row):
    row = row or {}
    return str(row.get("sector_name") or row.get("name") or row.get("sector") or row.get("行业") or "").strip()


def _sector_names_match(left, right):
    left = str(left or "").strip()
    right = str(right or "").strip()
    if not left or not right:
        return False
    return analysis_utils.sector_name_matches(left, right)


def _pick_first_number(row, *keys):
    row = row or {}
    for key in keys:
        if row.get(key) not in (None, ""):
            return _safe_float(row.get(key))
    return None


def _flow_turnover_yi(row):
    turnover = _pick_first_number(row, "turnover_yi", "sector_turnover")
    if turnover is not None:
        return turnover
    cje = _pick_first_number(row, "cje", "成交额")
    if cje is None:
        return None
    return cje / 1e4


def _flow_row_key(row):
    row = row or {}
    code = str(row.get("code") or row.get("ts_code") or "").strip()
    name = _sector_name_from_row(row)
    return code or name


def _sector_flow_entries(sector_fund_flow):
    if isinstance(sector_fund_flow, dict):
        inflow_rows = sector_fund_flow.get("inflow") or []
        outflow_rows = sector_fund_flow.get("outflow") or []
    else:
        inflow_rows = sector_fund_flow or []
        outflow_rows = []

    entries = []
    seen = set()
    for rank, row in enumerate(inflow_rows, 1):
        if not isinstance(row, dict) or not _sector_name_from_row(row):
            continue
        key = _flow_row_key(row)
        if key:
            seen.add(key)
        entries.append((rank, row))

    for row in outflow_rows:
        if not isinstance(row, dict) or not _sector_name_from_row(row):
            continue
        key = _flow_row_key(row)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        entries.append((None, row))
    return entries


def _append_unique_sector_name(target, sector_name):
    sector_name = str(sector_name or "").strip()
    if sector_name and not any(_sector_names_match(existing, sector_name) for existing in target):
        target.append(sector_name)


def _merge_flow_rows_for_sector(sector_name, flow_entries):
    matches = [
        (rank, row)
        for rank, row in flow_entries or []
        if _sector_names_match(_sector_name_from_row(row), sector_name)
    ]
    if not matches:
        return None, {}

    rank_values = [rank for rank, _ in matches if rank]
    net_total = 0.0
    has_net = False
    turnover_total = 0.0
    has_turnover = False
    matched_names = []
    for _, row in matches:
        row_name = _sector_name_from_row(row)
        if row_name and row_name not in matched_names:
            matched_names.append(row_name)
        net_inflow = _pick_first_number(
            row,
            "net_inflow_amount",
            "net_inflow_yi",
            "zljlr",
            "inflow",
            "fund_flow",
        )
        if net_inflow is not None:
            net_total += net_inflow
            has_net = True
        turnover = _flow_turnover_yi(row)
        if turnover is not None and turnover > 0:
            turnover_total += turnover
            has_turnover = True

    merged = {"name": sector_name, "matched_flow_names": matched_names}
    if has_net:
        merged["zljlr"] = round(net_total, 2)
    if has_turnover:
        merged["turnover_yi"] = round(turnover_total, 2)
    return min(rank_values) if rank_values else None, merged


def _extract_board_height(stock):
    stock = stock or {}
    direct = _pick_first_number(stock, "连板数", "lianban", "board_count", "height")
    if direct is not None:
        return int(direct)
    text = str(stock.get("涨停统计") or stock.get("zt_type") or stock.get("limit_up_type") or "").strip()
    if "首板" in text:
        return 1
    if "/" in text:
        parts = [part.strip() for part in text.split("/") if part.strip()]
        if len(parts) >= 2:
            digits = "".join(char for char in parts[1] if char.isdigit())
            if digits:
                return int(digits)
        if parts:
            digits = "".join(char for char in parts[0] if char.isdigit())
            if digits:
                return int(digits)
    if "天" in text and "板" in text:
        after_tian = text.split("天", 1)[1]
        digits = "".join(char for char in after_tian if char.isdigit())
        if digits:
            return int(digits)
    digits = "".join(char for char in text if char.isdigit())
    return int(digits) if digits else 0


def _stock_display_name(stock):
    stock = stock or {}
    for key in ("名称", "name", "stock_name", "股票简称", "code", "代码"):
        value = str(stock.get(key) or "").strip()
        if value:
            return value
    return ""


def _truthy_evidence(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    text = str(value or "").strip().lower()
    return text in {
        "1",
        "true",
        "yes",
        "y",
        "是",
        "有",
        "确认",
        "已确认",
        "成立",
        "顶住",
        "顶住压力",
        "二次确认",
        "第二波确认",
    }


def _leader_pressure_hold_confirmed(stock):
    stock = stock or {}
    return any(
        _truthy_evidence(stock.get(key))
        for key in ("pressure_hold_confirmed", "second_wave_confirmed", "held_pressure", "顶住压力")
    )


def _sector_zt_stocks(zt_pool_by_sector, sector_name):
    if not isinstance(zt_pool_by_sector, dict):
        return None
    for key, stocks in zt_pool_by_sector.items():
        if _sector_names_match(key, sector_name):
            return list(stocks or [])
    return []


def _derive_dragon_pullback_review(data, mainline_name):
    mainline_name = str(mainline_name or "").strip()
    if not mainline_name:
        return {}
    stocks = _sector_zt_stocks((data or {}).get("zt_pool_by_sector"), mainline_name)
    if not stocks:
        return {}

    leader = max(stocks, key=_extract_board_height)
    leader_height = _extract_board_height(leader)
    leader_name = _stock_display_name(leader)
    if not leader_name or leader_height <= 2 or not _leader_pressure_hold_confirmed(leader):
        return {}

    laggard_feedback = []
    for stock in stocks:
        if stock is leader:
            continue
        height = _extract_board_height(stock)
        name = _stock_display_name(stock)
        if 0 < height <= 2 and name:
            laggard_feedback.append(name)
    if not laggard_feedback:
        return {}

    return {
        "sector": mainline_name,
        "leader": leader_name,
        "leader_height": leader_height,
        "second_confirmation": True,
        "laggard_feedback": laggard_feedback,
        "pullback": "第一波后回撤观察，当前用低位反馈复核",
    }


def _sector_previous_share(recent_sector_turnover_history, sector_name):
    for item in reversed(list(recent_sector_turnover_history or [])):
        if not _sector_names_match(_sector_name_from_row(item), sector_name):
            continue
        share = _safe_float((item or {}).get("turnover_share_pct"))
        if share > 0:
            return share
    return 0.0


def _sector_current_share(sector_name, flow_row, current_sector_turnover_snapshot, total_turnover):
    snapshot = current_sector_turnover_snapshot or {}
    if _sector_names_match(_sector_name_from_row(snapshot), sector_name):
        snapshot_share = _safe_float(snapshot.get("turnover_share_pct"))
        if snapshot_share > 0:
            return round(snapshot_share, 2)
    row_share = _pick_first_number(flow_row, "turnover_share_pct")
    if row_share is not None and row_share > 0:
        return round(row_share, 2)
    turnover_yi = _flow_turnover_yi(flow_row)
    total_turnover = _safe_float(total_turnover)
    if turnover_yi is not None and turnover_yi > 0 and total_turnover > 0:
        return round(turnover_yi / total_turnover * 100, 2)
    return None


def _build_sector_attack_evidence_rows(
    data,
    current_sector_turnover_snapshot,
    recent_sector_turnover_history,
    total_turnover,
):
    data = data or {}
    sector_fund_flow = data.get("sector_fund_flow") or {}
    flow_entries = _sector_flow_entries(sector_fund_flow)
    zt_pool_by_sector = data.get("zt_pool_by_sector")
    has_zt_pool = isinstance(zt_pool_by_sector, dict)

    ordered_sectors = []
    if has_zt_pool:
        for sector_name in zt_pool_by_sector.keys():
            _append_unique_sector_name(ordered_sectors, sector_name)

    for _, row in flow_entries:
        _append_unique_sector_name(ordered_sectors, _sector_name_from_row(row))

    if not ordered_sectors:
        return None

    evidence_rows = []
    for sector_name in ordered_sectors:
        rank, flow_row = _merge_flow_rows_for_sector(sector_name, flow_entries)
        evidence_row = {"sector_name": sector_name}
        net_inflow = _pick_first_number(
            flow_row,
            "net_inflow_amount",
            "net_inflow_yi",
            "zljlr",
            "inflow",
            "fund_flow",
        )
        if net_inflow is not None:
            evidence_row["net_inflow_amount"] = round(net_inflow, 2)
            if rank is not None:
                evidence_row["net_inflow_rank"] = rank

        zt_stocks = _sector_zt_stocks(zt_pool_by_sector, sector_name)
        if zt_stocks is not None:
            evidence_row["limit_up_count"] = len(zt_stocks)
            if zt_stocks:
                anchor_stock = max(zt_stocks, key=_extract_board_height)
                evidence_row["high_anchor_height"] = _extract_board_height(anchor_stock)
                evidence_row["high_anchor_name"] = str(anchor_stock.get("名称") or anchor_stock.get("name") or "").strip()
            else:
                evidence_row["high_anchor_height"] = 0

        current_share = _sector_current_share(sector_name, flow_row, current_sector_turnover_snapshot, total_turnover)
        if current_share is not None:
            evidence_row["turnover_share_pct"] = current_share
            sector_turnover = _flow_turnover_yi(flow_row)
            if sector_turnover is not None and sector_turnover > 0:
                evidence_row["sector_turnover"] = round(sector_turnover, 2)
            previous_share = _sector_previous_share(recent_sector_turnover_history, sector_name)
            if previous_share > 0:
                evidence_row["turnover_share_change"] = round(current_share - previous_share, 2)

        evidence_rows.append(evidence_row)

    return evidence_rows


def build_market_research_snapshot_contract(
    data,
    final_gate,
    position_level,
    exit_analysis,
    observation_snapshot=None,
    target_date="",
    *,
    build_abnormal_projection_summary,
    build_market_style_switch_snapshot,
    build_market_state_machine_snapshot,
    build_mainline_rotation_snapshot,
    build_abnormal_probe_group,
    build_special_probe_verdict,
    build_follow_verdict,
    build_dialectical_decision_snapshot,
    build_mainline_turnover_summary=None,
    build_mainline_history_record=None,
    load_recent_mainline_history=None,
    get_market_total_turnover_from_fact_db=None,
    get_sector_turnover_snapshot_from_tencent_fund_flow=None,
    get_sector_turnover_snapshot_from_ths=None,
    load_recent_sector_turnover_history=None,
):
    observation_snapshot = observation_snapshot or {}
    sector_ai_analysis = data.get("sector_ai_analysis", {}) or {}
    mainline_turnover_summary = data.get("mainline_turnover_summary") or observation_snapshot.get("mainline_turnover_summary") or {}
    logs = []

    abnormal_projection = build_abnormal_projection_summary(observation_snapshot.get("abnormal_watch_pool", []))
    _append_log(logs, "abnormal_projection", "success", "已构建异常投影摘要")

    style_switch_snapshot = build_market_style_switch_snapshot(
        target_date,
        data,
        observation_snapshot=observation_snapshot,
        abnormal_projection=abnormal_projection,
    )
    _append_log(logs, "style_switch", "success", "已构建风格切换快照")

    state_machine_snapshot = build_market_state_machine_snapshot(
        data,
        final_gate,
        position_level,
        exit_analysis,
        main_sectors_info=observation_snapshot.get("main_sectors_info", []),
        secondary_sectors_info=observation_snapshot.get("secondary_sectors_info", []),
        sector_trend_snapshot=observation_snapshot.get("sector_trend_snapshot", []),
        abnormal_watch_pool=observation_snapshot.get("abnormal_watch_pool", []),
    )
    _append_log(logs, "market_state", "success", "已构建市场状态快照", state_code=state_machine_snapshot.get("state_code", ""))

    mainline_rotation_snapshot = build_mainline_rotation_snapshot(
        observation=observation_snapshot,
        state_machine=state_machine_snapshot,
        style_switch=style_switch_snapshot,
        sector_ai_analysis=sector_ai_analysis,
    )
    special_probe_group = build_abnormal_probe_group(
        style_switch_snapshot=style_switch_snapshot,
        abnormal_watch_pool=observation_snapshot.get("abnormal_watch_pool", []),
        mainline_name=state_machine_snapshot.get("leading_line", ""),
        watch_anchor={},
    )
    special_probe_verdict = build_special_probe_verdict(
        abnormal_probe_group=special_probe_group,
        watch_anchor={},
        watch_anchor_type="",
        mainline_name=state_machine_snapshot.get("leading_line", ""),
        target_date=target_date,
    )
    follow_verdict = build_follow_verdict(
        final_gate,
        position_level,
        state_machine_snapshot,
        special_probe_verdict=special_probe_verdict,
    )
    _append_log(logs, "follow_verdict", "success", "已构建跟随裁决", follow_label=follow_verdict.get("label", ""))

    dialectical_decision = build_dialectical_decision_snapshot(
        observation=observation_snapshot,
        style_switch=style_switch_snapshot,
        state_machine=state_machine_snapshot,
        follow_verdict=follow_verdict,
        final_gate=final_gate,
    )
    current_mainline_history_record = data.get("current_mainline_history_record") or {}
    recent_mainline_history = data.get("recent_mainline_history") or []
    current_sector_turnover_snapshot = data.get("current_sector_turnover_snapshot") or {}
    recent_sector_turnover_history = data.get("recent_sector_turnover_history") or []

    if not current_mainline_history_record and callable(build_mainline_history_record):
        current_mainline_history_record = build_mainline_history_record(
            target_date,
            {
                "observation": observation_snapshot,
                "state_machine": state_machine_snapshot,
                "mainline_rotation_snapshot": mainline_rotation_snapshot,
            },
        )

    current_mainline_history_record = _refresh_current_mainline_record_from_rotation(
        current_mainline_history_record,
        mainline_rotation_snapshot,
        target_date,
    )

    current_mainline_name = str(
        (current_mainline_history_record or {}).get("primary_mainline")
        or (current_mainline_history_record or {}).get("leading_line")
        or state_machine_snapshot.get("leading_line", "")
        or ""
    ).strip()

    if not recent_mainline_history and callable(load_recent_mainline_history):
        recent_mainline_history = _load_recent_mainline_history_for_cycle_calendar(
            load_recent_mainline_history,
            target_date,
        )

    total_turnover = _resolve_effective_total_turnover(
        data,
        observation_snapshot,
        target_date,
        get_market_total_turnover_from_fact_db=get_market_total_turnover_from_fact_db,
    )
    current_sector_turnover_snapshot = _fill_sector_snapshot_total_turnover(
        current_sector_turnover_snapshot,
        total_turnover,
    )

    if not current_sector_turnover_snapshot and current_mainline_name and callable(get_sector_turnover_snapshot_from_tencent_fund_flow):
        current_sector_turnover_snapshot = get_sector_turnover_snapshot_from_tencent_fund_flow(
            current_mainline_name,
            data.get("sector_fund_flow", {}),
            target_date=target_date,
            total_turnover=total_turnover,
        )

    has_sector_turnover = _safe_float((current_sector_turnover_snapshot or {}).get("sector_turnover")) > 0
    if not has_sector_turnover and current_mainline_name and callable(get_sector_turnover_snapshot_from_ths):
        current_sector_turnover_snapshot = get_sector_turnover_snapshot_from_ths(
            current_mainline_name,
            target_date=target_date,
            total_turnover=total_turnover,
        )

    if not recent_sector_turnover_history and current_mainline_name and callable(load_recent_sector_turnover_history):
        recent_sector_turnover_history = _load_recent_turnover_by_daily_mainline(
            load_recent_sector_turnover_history,
            recent_mainline_history,
            target_date,
        )
    if not recent_sector_turnover_history and current_mainline_name and callable(load_recent_sector_turnover_history):
        recent_sector_turnover_history = load_recent_sector_turnover_history(
            target_date,
            current_mainline_name,
            lookback_days=25,
        )
    if recent_mainline_history:
        recent_sector_turnover_history = _fill_turnover_placeholders_for_mainline_history(
            recent_sector_turnover_history,
            recent_mainline_history,
        )

    sector_attack_evidence_rows = _build_sector_attack_evidence_rows(
        data,
        current_sector_turnover_snapshot,
        recent_sector_turnover_history,
        total_turnover,
    )
    realtime_tag_evidence_snapshot = data.get("realtime_tag_evidence_snapshot") or {}
    should_rebuild_for_attack_evidence = bool(
        sector_attack_evidence_rows
        and not (mainline_turnover_summary or {}).get("mainline_attack_evidence_summary")
    )

    if (
        should_rebuild_for_attack_evidence
        or _mainline_turnover_summary_conflicts_with_current_record(
            mainline_turnover_summary,
            current_mainline_history_record,
        )
        or not _has_resolved_mainline_turnover_summary(mainline_turnover_summary)
    ) and callable(build_mainline_turnover_summary):
        mainline_turnover_summary = build_mainline_turnover_summary(
            target_date=target_date,
            current_mainline_history_record=current_mainline_history_record,
            recent_mainline_history=recent_mainline_history,
            current_sector_turnover_snapshot=current_sector_turnover_snapshot,
            recent_sector_turnover_history=recent_sector_turnover_history,
            sector_attack_evidence_rows=sector_attack_evidence_rows,
            realtime_tag_evidence_snapshot=realtime_tag_evidence_snapshot,
        )

    current_mainline_history_record = _align_current_mainline_history_record_with_attack(
        current_mainline_history_record,
        mainline_turnover_summary,
        target_date,
    )
    current_mainline_name = str(
        (current_mainline_history_record or {}).get("primary_mainline")
        or (current_mainline_history_record or {}).get("leading_line")
        or current_mainline_name
        or ""
    ).strip()

    market_fit_calibration = build_market_fit_calibration(
        strong_samples=_collect_market_fit_strong_samples(data),
        current_mainline=current_mainline_name,
        observation_pool=_collect_market_fit_observation_pool(data, observation_snapshot),
    )
    _append_log(
        logs,
        "market_fit_calibration",
        "success",
        "已构建市场贴合度校准",
        fit_label=market_fit_calibration.get("fit_label", ""),
    )

    lhb_capital_status, capital_conclusion = _derive_lhb_capital_intent(data, current_mainline_name)
    capital_intent_breakdown, capital_conclusion = _derive_capital_intent_breakdown(
        mainline_turnover_summary,
        sector_attack_evidence_rows,
        lhb_capital_status,
        capital_conclusion,
    )
    dragon_pullback_review = _derive_dragon_pullback_review(data, current_mainline_name)

    return {
        "observation": observation_snapshot,
        "style_switch": style_switch_snapshot,
        "state_machine": state_machine_snapshot,
        "abnormal_projection": abnormal_projection,
        "follow_verdict": follow_verdict,
        "special_probe_verdict": special_probe_verdict,
        "dialectical_decision": dialectical_decision,
        "mainline_rotation_snapshot": mainline_rotation_snapshot,
        "current_mainline_history_record": current_mainline_history_record,
        "recent_mainline_history": recent_mainline_history,
        "current_sector_turnover_snapshot": current_sector_turnover_snapshot,
        "recent_sector_turnover_history": recent_sector_turnover_history,
        "mainline_turnover_summary": mainline_turnover_summary,
        "realtime_tag_evidence_snapshot": realtime_tag_evidence_snapshot,
        "market_fit_calibration": market_fit_calibration,
        "capital_intent_breakdown": capital_intent_breakdown,
        "lhb_capital_status": lhb_capital_status,
        "capital_conclusion": capital_conclusion,
        "dragon_pullback_review": dragon_pullback_review,
        "sector_ai_analysis": sector_ai_analysis,
        "final_gate": final_gate,
        "module_logs": logs,
    }


def derive_step0_follow_plan_contract(market_research_snapshot, final_gate, position_level):
    market_research_snapshot = market_research_snapshot or {}
    state_machine_snapshot = market_research_snapshot.get("state_machine", {}) or {}
    follow_verdict = market_research_snapshot.get("follow_verdict", {}) or {}
    style_switch = market_research_snapshot.get("style_switch", {}) or {}
    special_probe_verdict = market_research_snapshot.get("special_probe_verdict", {}) or {}
    logs = []

    step0_prediction = "NEUTRAL"
    if not final_gate.get("can_new_entry"):
        step0_prediction = "BLOCKED"
    elif state_machine_snapshot.get("state_code") == "expand":
        step0_prediction = "CLEAR"
    elif state_machine_snapshot.get("state_code") == "contract":
        step0_prediction = "DIFFICULT"

    prediction_map = {
        "BLOCKED": follow_verdict.get("label", "🚫 暂不跟随"),
        "DIFFICULT": "⚠️ 先看环境",
        "NEUTRAL": follow_verdict.get("label", "🟡 条件跟随"),
        "CLEAR": follow_verdict.get("label", "🟢 跟随主线"),
    }
    step0_reason = follow_verdict.get("reason") or state_machine_snapshot.get("state_reason", "")
    step0_action = follow_verdict.get("action") or state_machine_snapshot.get("reflection_focus", "")
    style_action = style_switch.get("primary_action", "")
    probe_action = str(special_probe_verdict.get("action", "") or "").strip()
    probe_summary = str(special_probe_verdict.get("summary_text", "") or "").strip()
    if probe_action and probe_action not in step0_action:
        step0_action = f"先看特殊标的：{probe_action}" if not step0_action else f"先看特殊标的：{probe_action}；{step0_action}"
    style_label = str(style_switch.get("style_label", "") or "").strip()
    if style_action and style_action not in step0_action:
        if step0_action:
            style_note_prefix = f"市场层面的{style_label}只作背景参考" if style_label else "市场层面的风格分歧只作背景参考"
            style_action_text = f"{style_note_prefix}：{style_action}"
        else:
            style_action_text = style_action
        step0_action = f"{step0_action}；{style_action_text}" if step0_action else style_action_text
    if probe_summary and probe_summary not in step0_reason:
        step0_reason = f"{step0_reason}；{probe_summary}" if step0_reason else probe_summary

    if step0_prediction == "DIFFICULT" and not step0_reason:
        step0_reason = f"当前处于{state_machine_snapshot.get('energy_state', '未知状态')}，先确认环境，再决定是否继续跟随。"

    _append_log(logs, "step0_plan", "success", "已生成 Step0 跟随计划", prediction=step0_prediction)

    return {
        "step0_prediction": step0_prediction,
        "step0_prediction_cn": prediction_map.get(step0_prediction, step0_prediction),
        "step0_reason": step0_reason,
        "step0_action": step0_action,
        "position_level": position_level,
        "module_logs": logs,
    }
