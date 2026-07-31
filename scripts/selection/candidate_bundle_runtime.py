__all__ = [
    "build_candidate_bundle_contract",
    "build_step2_candidate_bundle",
]

_NON_SECTOR_LABELS = {
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
    "待补充板块",
    "待补充",
    "其他",
    "其它",
    "-",
}


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "selection.candidate_bundle_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _build_code_map(items, normalize_stock_code, code_keys):
    mapped = {}
    if isinstance(items, dict):
        for code, item in items.items():
            if isinstance(item, dict):
                normalized = normalize_stock_code(item.get("code") or code)
                if normalized:
                    mapped[normalized] = item
        return mapped
    for item in items or []:
        if not isinstance(item, dict):
            continue
        code = ""
        for key in code_keys:
            code = item.get(key)
            if code:
                break
        normalized = normalize_stock_code(code)
        if normalized:
            mapped[normalized] = item
    return mapped


def _related_plate_names(related_plates):
    names = []
    for plate in related_plates or []:
        if not isinstance(plate, dict):
            continue
        name = str(plate.get("plate_name") or plate.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _build_xueqiu_argument_map(rows, normalize_stock_code):
    mapped = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        code = normalize_stock_code(row.get("code") or row.get("stock_code") or row.get("symbol") or row.get("full_code"))
        if code:
            mapped[code] = row
    return mapped


def _first_valid_text(values):
    for value in values or []:
        if _is_valid_sector_label(value):
            return str(value).strip()
    return ""


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(str(value).replace("%", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return float(default)


def _first_number(item, *keys):
    for key in keys:
        if key not in (item or {}):
            continue
        value = (item or {}).get(key)
        if value not in (None, ""):
            return _safe_float(value, 0.0)
    return 0.0


def _candidate_selection_priority_sort_key(item):
    item = item or {}
    priority = item.get("selection_priority")
    if isinstance(priority, dict):
        return tuple(priority.get(key, 0) for key in ("source", "board", "base", "acceptance", "order"))
    return (
        _safe_float(item.get("tomorrow_strength", 0), 0),
        _safe_float(item.get("base_strength_score", item.get("score", 0)), 0),
        0,
        0,
        0,
    )


def _base_condition_tier(base_strength):
    base_strength = _safe_float(base_strength, 0)
    if base_strength >= 85:
        return 3, "高辨识度来源"
    if base_strength >= 70:
        return 2, "中高辨识度来源"
    if base_strength >= 50:
        return 1, "普通候选来源"
    return 0, "低辨识度来源"


def _board_condition_tier(lb_count, base_strength):
    base_tier, _ = _base_condition_tier(base_strength)
    if lb_count >= 3:
        return 4, "三板以上高标"
    if lb_count == 2:
        return 3, "二板连板"
    if lb_count == 1 and base_tier >= 2:
        return 2, "首板且来源辨识度较高"
    if base_tier >= 1:
        return 1, "非连板普通候选"
    return 0, "仅观察候选"


def _abnormal_condition_tier(abnormal_item, abnormal_adjustment):
    follow_state = str((abnormal_item or {}).get("follow_state") or "").strip()
    if follow_state == "跌不下去":
        return 3, "异动后承接强"
    if follow_state == "缩量消化":
        return 2, "异动后缩量消化"
    if follow_state == "新异动待观察":
        return 1, "新异动待确认"
    if follow_state == "已经转弱":
        return -1, "异动后承接转弱"
    adjustment = _safe_float(abnormal_adjustment, 0)
    if adjustment > 0:
        return 1, "异动证据待确认"
    if adjustment < 0:
        return -1, "异动证据转弱"
    return 0, "无异动承接证据"


def _source_condition_tier(item):
    source_tier = str((item or {}).get("source_tier") or "").strip()
    source = str((item or {}).get("source") or "").strip()
    candidate_role = str((item or {}).get("candidate_role") or "").strip()
    if candidate_role in {"板块锚", "大容量中军", "分支龙头", "主线核心"}:
        return 3, candidate_role
    if source == "recent_extreme_conviction_mention":
        return 0, source
    if source_tier == "extreme_conviction":
        return 3, source_tier
    if source_tier == "anchor_reversal_source":
        return 2, source_tier
    if source:
        return 1, source
    return 0, "普通来源"


def _selection_priority_label(priority):
    if not isinstance(priority, dict):
        return "待补证据"
    board = priority.get("board", 0)
    acceptance = priority.get("acceptance", 0)
    source = priority.get("source", 0)
    if board >= 4 or (board >= 3 and acceptance >= 2):
        return "高标强承接"
    if source >= 3 and acceptance >= 2:
        return "板块核心承接"
    if board >= 2 or acceptance >= 2 or source >= 2:
        return "候选观察"
    if acceptance < 0:
        return "转弱观察"
    return "低优先观察"


def _build_candidate_selection_priority(item, *, lb_count, abnormal_item, abnormal_adjustment, source_order):
    base_tier, base_reason = _base_condition_tier(item.get("score", 0))
    board_tier, board_reason = _board_condition_tier(lb_count, item.get("score", 0))
    acceptance_tier, acceptance_reason = _abnormal_condition_tier(abnormal_item, abnormal_adjustment)
    source_tier, source_reason = _source_condition_tier(item)
    priority = {
        "board": board_tier,
        "acceptance": acceptance_tier,
        "source": source_tier,
        "base": base_tier,
        "order": -int(source_order),
    }
    reasons = [board_reason, acceptance_reason, source_reason, base_reason]
    return priority, "；".join(reason for reason in reasons if reason)


def _infer_sector_from_reason(text):
    text = str(text or "")
    if "长鑫" in text or "国产芯片" in text:
        return "国产芯片"
    keyword_groups = [
        ("半导体", ("长鑫", "存储", "芯片", "光刻", "晶圆", "半导体")),
        ("算力", ("Token工厂", "昇腾", "算力", "服务器", "数据中心", "液冷")),
        ("机器人", ("机器人", "减速器", "智能体", "机器视觉")),
        ("商业航天", ("商业航天", "卫星", "航天", "火箭")),
        ("低空经济", ("低空", "无人机", "eVTOL")),
        ("家用电器", ("小家电", "家用电器", "空调")),
        ("消费电子", ("MiniLED", "车载背光", "VR背光", "背光显示", "消费电子", "无线耳机", "苹果产业链")),
        ("食品饮料", ("葡萄酒", "白兰地", "保健酒", "食品", "饮料")),
        ("天然气", ("天然气", "页岩气", "燃气")),
        ("股权转让", ("股权转让", "资产重组", "并购重组", "控制权")),
    ]
    for sector, markers in keyword_groups:
        if any(marker in text for marker in markers):
            return sector
    return ""


def _first_valid_stock_plate(item):
    return _first_valid_text(
        list(item.get("xuangubao_related_plate_names") or [])
        + list(item.get("concepts") or [])
        + list(item.get("plates") or [])
        + list(item.get("related_plates") or [])
        + [
            _infer_sector_from_reason(
                " / ".join(
                    str(item.get(key) or "")
                    for key in ("reason", "涨停统计", "xuangubao_stock_reason", "abnormal_summary", "volume_summary")
                )
            ),
            item.get("industry"),
            item.get("所属行业"),
            item.get("sector_name"),
        ]
    )


def _enrich_candidate_item(item, code, stock_info_map, volume_anomaly_map):
    stock_info = stock_info_map.get(code, {}) or {}
    for key in ("open", "high", "low", "close", "price", "yclose", "change_pct"):
        if key in stock_info and item.get(key) in (None, ""):
            item[key] = stock_info.get(key)
    for source_key, target_key in (("industry", "industry"), ("所属行业", "所属行业"), ("sector_name", "sector_name")):
        if stock_info.get(source_key) and item.get(target_key) in (None, ""):
            item[target_key] = stock_info.get(source_key)

    volume_anomaly = volume_anomaly_map.get(code, {}) or {}
    reason = volume_anomaly.get("reason")
    if reason and not item.get("volume_summary"):
        item["volume_summary"] = reason


def _enrich_candidate_with_xuangubao_reason(item, code, xuangubao_reason_map):
    reason = xuangubao_reason_map.get(code, {}) or {}
    if not reason:
        return
    related_plates = reason.get("related_plates", []) or []
    item["xuangubao_stock_reason"] = reason.get("stock_reason", "")
    item["xuangubao_related_plates"] = related_plates
    item["xuangubao_related_plate_names"] = _related_plate_names(related_plates)
    item["xuangubao_limit_up_days"] = reason.get("limit_up_days", 0)


def _enrich_candidate_with_xueqiu_argument(item, code, xueqiu_argument_map):
    argument = xueqiu_argument_map.get(code, {}) or {}
    if not argument:
        return
    text = str(argument.get("argument") or argument.get("reason") or argument.get("content") or "").strip()
    if text:
        item["xueqiu_hot_stock_argument"] = text
        item.setdefault("xueqiu_hot_stock_reason", text)
    provider = str(argument.get("provider") or "").strip()
    if provider:
        item["xueqiu_hot_stock_argument_provider"] = provider


def _enrich_candidate_with_stock_risk(item, code, stock_risk_map):
    risk = (stock_risk_map or {}).get(code, {}) or {}
    if not risk:
        return
    item["stock_risk"] = risk
    risk_flags = risk.get("risk_flags") or []
    if risk_flags:
        item["news_risk_flags"] = list(dict.fromkeys(list(item.get("news_risk_flags") or []) + list(risk_flags)))
    risk_summary = str(risk.get("risk_summary") or "").strip()
    if risk_summary and not item.get("news_risk_summary"):
        item["news_risk_summary"] = risk_summary
    risk_events = list(risk.get("risk_events") or [])
    if risk_events:
        item["risk_events"] = list(item.get("risk_events") or []) + risk_events


def _enrich_candidate_with_recent_bars(item, code, target_date, fetch_recent_price_bars=None, fast_fail=False):
    if item.get("recent_bars") or item.get("stock_klines"):
        return
    if not code or not target_date:
        return
    if not callable(fetch_recent_price_bars):
        return
    try:
        bars = fetch_recent_price_bars(code, target_date, lookback_days=120, fast_fail=fast_fail)
    except TypeError:
        if fast_fail:
            return
        bars = fetch_recent_price_bars(code, target_date, lookback_days=120)
    except Exception:
        bars = []
    if bars:
        item["recent_bars"] = list(bars)[-120:]


def _normalize_candidate_sector(item):
    sector = str(item.get("sector") or "").strip()
    if _is_valid_sector_label(sector):
        return
    replacement = _first_valid_stock_plate(item)
    if replacement:
        item["sector"] = replacement


_TRADE_NARRATIVE_RULES = (
    (
        "脑机接口",
        (
            "脑机接口",
            "脑科学",
        ),
    ),
    (
        "AI算力基础设施",
        (
            "英伟达",
            "NVIDIA",
            "AI平台",
            "AI服务器",
            "AIDC",
            "数据中心",
            "智算",
            "液冷服务器",
        ),
    ),
)


def _trade_narrative_text(item):
    parts = []
    for key in (
        "xueqiu_hot_stock_argument",
        "xueqiu_hot_stock_reason",
        "reason",
        "conviction_reason",
        "xuangubao_stock_reason",
        "hot_reason",
        "rank_reason",
        "popularity_tag",
    ):
        value = (item or {}).get(key)
        if value not in (None, ""):
            parts.append(str(value))
    for key in (
        "concepts",
        "concept_list",
        "sector_tags",
        "tags",
        "plates",
        "related_plates",
        "xuangubao_related_plate_names",
    ):
        value = (item or {}).get(key)
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            parts.extend(str(nested) for nested in value.values() if nested not in (None, ""))
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                if isinstance(nested, dict):
                    text = str(nested.get("plate_name") or nested.get("name") or "").strip()
                    if text:
                        parts.append(text)
                elif nested not in (None, ""):
                    parts.append(str(nested))
        else:
            parts.append(str(value))
    return " / ".join(part for part in parts if part)


def _infer_trade_narrative_sector(item):
    text = _trade_narrative_text(item)
    if not text:
        return "", ""
    for sector, markers in _TRADE_NARRATIVE_RULES:
        for marker in markers:
            if marker and marker in text:
                return sector, marker
    return "", ""


def _apply_trade_narrative_sector(item):
    narrative_sector, evidence = _infer_trade_narrative_sector(item)
    if not narrative_sector:
        return
    raw_sector = str(item.get("sector") or item.get("sector_name") or item.get("industry") or item.get("所属行业") or "").strip()
    if raw_sector and not item.get("raw_sector"):
        item["raw_sector"] = raw_sector
    item["trade_narrative_sector"] = narrative_sector
    source_reason = str(item.get("xueqiu_hot_stock_argument") or item.get("xueqiu_hot_stock_reason") or "").strip()
    item["trade_narrative_reason"] = f"当日叙事命中：{source_reason if source_reason and evidence in source_reason else evidence}"
    item["sector"] = narrative_sector


def _candidate_code(item, normalize_stock_code):
    if not isinstance(item, dict):
        return ""
    for key in ("code", "stock_code", "代码", "ts_code", "symbol"):
        value = item.get(key)
        if value:
            return normalize_stock_code(value)
    return ""


def _candidate_identity_text(item):
    item = item or {}
    parts = []
    for key in (
        "candidate_role",
        "候选身份",
        "reason",
        "conviction_reason",
        "pattern",
        "capacity_profile",
        "turnover_capacity",
        "volume_capacity",
        "ma_binding_strategy",
        "holding_strategy",
        "position_strategy",
    ):
        value = item.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " / ".join(parts)


def _iter_candidate_terms(item, *extra_values):
    item = item or {}
    for value in extra_values:
        if value not in (None, ""):
            yield str(value)
    for key in (
        "sector",
        "industry",
        "所属行业",
        "sector_name",
        "concepts",
        "tags",
        "plates",
        "related_plates",
        "xuangubao_related_plate_names",
        "xueqiu_hot_stock_argument",
        "xueqiu_hot_stock_reason",
        "reason",
        "popularity_tag",
        "rank_reason",
        "hot_reason",
    ):
        value = item.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            for nested in value.values():
                yield str(nested)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                if isinstance(nested, dict):
                    yield str(nested.get("plate_name") or nested.get("name") or nested)
                else:
                    yield str(nested)
        else:
            yield str(value)


def _candidate_matches_mainline(item, mainline_name):
    mainline_name = str(mainline_name or "").strip()
    if not mainline_name:
        return False
    for term in _iter_candidate_terms(item):
        term = str(term or "").strip()
        if term and (mainline_name in term or term in mainline_name):
            return True
    return False


def _hot_capacity_rank(item, *keys):
    for key in keys:
        try:
            value = int(float(str((item or {}).get(key) or "").strip()))
        except ValueError:
            continue
        if value > 0:
            return value
    return 9999


def _merge_candidate_context(base, *sources):
    merged = dict(base or {})
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if value in (None, ""):
                continue
            if key not in merged or merged.get(key) in (None, "", [], {}):
                merged[key] = value
    return merged


def _is_anchor_source_candidate(item, *, source_name=""):
    if not isinstance(item, dict):
        return False
    role = str(item.get("candidate_role") or item.get("候选身份") or "").strip()
    if role in {"板块锚", "分支龙头", "大容量中军"}:
        return True
    lianban = _first_number(item, "连板数", "lianban", "lianban_days")
    turnover = _first_number(item, "turnover", "成交额", "amount", "成交金额")
    if turnover > 10000:
        turnover = turnover / 1e8
    hot_rank = _hot_capacity_rank(item, "hot_rank", "rank", "popularity_rank")
    turnover_rank = _hot_capacity_rank(item, "turnover_rank")
    if source_name == "dragon_stocks" and (lianban >= 2 or turnover >= 50 or hot_rank <= 30 or turnover_rank <= 20):
        return True
    text = _candidate_identity_text(item)
    return any(
        marker in text
        for marker in (
            "板块锚",
            "锚定龙",
            "趋势比价链",
            "大容量",
            "中军",
            "反复做",
            "热门股",
            "MA5入/MA7清/MA5T",
            "MA5B",
            "MA7清",
            "MA5T",
        )
    )


def _build_anchor_source_candidates(
    *,
    candidates,
    dragon_stocks,
    normalize_stock_code,
    existing_codes,
):
    result = []
    seen = {code for code in existing_codes if code}
    for source_name, items in (("dragon_stocks", dragon_stocks), ("candidates", candidates)):
        for item in items or []:
            if not _is_anchor_source_candidate(item, source_name=source_name):
                continue
            code = _candidate_code(item, normalize_stock_code)
            if not code or code in seen:
                continue
            copied = dict(item)
            copied["code"] = code
            copied.setdefault("source", source_name)
            copied.setdefault("source_tier", "anchor_reversal_source")
            result.append(copied)
            seen.add(code)
    return result


def _build_hot_capacity_anchor_candidates(
    *,
    data,
    candidates,
    stock_info_map,
    normalize_stock_code,
    existing_codes,
    mainline_name,
):
    if not str(mainline_name or "").strip():
        return []

    seen = {code for code in existing_codes if code}
    candidate_map = _build_code_map(candidates or [], normalize_stock_code, ("code", "stock_code", "代码", "symbol"))
    turnover_map = _build_code_map((data or {}).get("turnover_rank", []), normalize_stock_code, ("code", "stock_code", "代码", "symbol"))
    hot_rows = []
    for key in ("hot_rank_top30", "hot_rank_top50", "integrated_hot_list"):
        hot_rows.extend((data or {}).get(key) or [])
    hot_map = _build_code_map(hot_rows, normalize_stock_code, ("code", "stock_code", "代码", "symbol"))

    ordered_codes = []
    for source in (turnover_map, hot_map, candidate_map):
        for code in source:
            if code and code not in ordered_codes:
                ordered_codes.append(code)

    result = []
    for code in ordered_codes:
        if not code or code in seen:
            continue
        base = candidate_map.get(code, {})
        turnover_row = turnover_map.get(code, {})
        hot_row = hot_map.get(code, {})
        stock_info = stock_info_map.get(code, {})
        item = _merge_candidate_context(base, turnover_row, hot_row, stock_info)
        item["code"] = code
        item.setdefault("name", base.get("name") or turnover_row.get("name") or hot_row.get("name") or stock_info.get("name") or "")
        item.setdefault("sector", base.get("sector") or turnover_row.get("sector") or stock_info.get("industry") or stock_info.get("所属行业") or "")
        if stock_info.get("industry") and item.get("industry") in (None, ""):
            item["industry"] = stock_info.get("industry")
        if stock_info.get("所属行业") and item.get("所属行业") in (None, ""):
            item["所属行业"] = stock_info.get("所属行业")
        _normalize_candidate_sector(item)
        if not _candidate_matches_mainline(item, mainline_name):
            continue

        turnover_rank = _hot_capacity_rank(turnover_row, "rank", "turnover_rank")
        hot_rank = _hot_capacity_rank(hot_row, "rank", "hot_rank", "popularity_rank")
        turnover = _first_number(item, "turnover", "成交额", "amount")
        if turnover > 10000:
            turnover = turnover / 1e8
        source_text = " / ".join(
            str(value or "")
            for value in (
                base.get("_source"),
                base.get("source"),
                turnover_row.get("data_source"),
                hot_row.get("data_source"),
                hot_row.get("source"),
            )
            if str(value or "").strip()
        )
        is_capacity = turnover_rank <= 20 or turnover >= 50
        is_hot = hot_rank <= 30
        is_candidate_capacity = any(marker in source_text for marker in ("成交额", "热榜"))
        if not (is_capacity or is_hot or is_candidate_capacity):
            continue

        if turnover_rank <= 3 or hot_rank <= 5 or turnover >= 100:
            item["capacity_tier"] = "一线容量锚"
        elif turnover_rank <= 10 or hot_rank <= 15 or turnover >= 50:
            item["capacity_tier"] = "容量核心"
        else:
            item["capacity_tier"] = "容量观察"
        item.setdefault("score", item.get("legacy_score", 0))
        item["source"] = "hot_capacity_anchor_source"
        item["source_tier"] = "anchor_reversal_source"
        item["candidate_role"] = "大容量中军"
        item["capacity_profile"] = item.get("capacity_profile") or "大容量趋势资金"
        if turnover:
            item["turnover_capacity"] = item.get("turnover_capacity") or f"成交额{turnover:.1f}亿"
            item["turnover"] = turnover
        if turnover_rank != 9999:
            item["turnover_rank"] = turnover_rank
        if hot_rank != 9999:
            item["hot_rank"] = hot_rank
        item["reason"] = item.get("reason") or f"{mainline_name}热门股 / 大容量趋势资金 / 反复做对象 / 承接好"
        item["pattern"] = item.get("pattern") or "大容量强趋势"
        item["trend_aesthetic_status"] = item.get("trend_aesthetic_status") or "通过"
        result.append(item)
        seen.add(code)
    result.sort(
        key=lambda item: (
            -_hot_capacity_rank(item, "hot_rank"),
            -_hot_capacity_rank(item, "turnover_rank"),
            _safe_float(item.get("turnover", 0), 0),
            _safe_float(item.get("score", 0), 0),
        ),
        reverse=True,
    )
    return result[:5]


def _build_recent_extreme_mention_candidates(data, normalize_stock_code):
    result_by_code = {}
    code_order = []
    for row in (data or {}).get("recent_extreme_conviction_mentions") or []:
        if not isinstance(row, dict):
            continue
        code = _candidate_code(row, normalize_stock_code)
        if not code:
            continue
        name = str(row.get("name") or row.get("stock_name") or "").strip()
        sector = str(row.get("sector") or row.get("sector_candidate") or "").strip()
        reason = str(row.get("reason") or row.get("next_action") or "").strip()
        planned_window = str(row.get("planned_window") or row.get("buy_window") or "").strip()
        candidate = {
            "name": name,
            "code": code,
            "sector": sector,
            "score": row.get("score", 50),
            "source": "recent_extreme_conviction_mention",
            "source_tier": "extreme_conviction",
            "reason": reason or "历史过程观察样本待复核",
            "pattern": str(row.get("pattern") or reason or "历史好形态").strip(),
            "conviction_reason": reason,
            "participation_window": planned_window,
            "recent_extreme_mention": dict(row),
        }
        if code not in result_by_code:
            code_order.append(code)
            result_by_code[code] = candidate
            continue
        current_date = str((result_by_code[code].get("recent_extreme_mention") or {}).get("mention_trade_date") or "")
        next_date = str(row.get("mention_trade_date") or "")
        if next_date >= current_date:
            result_by_code[code] = candidate
    return [result_by_code[code] for code in code_order if code in result_by_code]


def _historical_review_text(item):
    if not isinstance(item, dict):
        return str(item or "")
    parts = []
    for key in (
        "review_status",
        "next_action",
        "invalidation",
        "reason",
        "source_section",
        "payload",
    ):
        value = item.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " / ".join(parts)


def _is_eliminated_historical_extreme(row):
    if not isinstance(row, dict):
        return False
    if bool(row.get("is_a_kill_eliminated")):
        return True
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if bool(payload.get("is_a_kill_eliminated") or payload.get("a_kill_eliminated")):
        return True
    texts = [
        row.get("review_status"),
        row.get("next_action"),
        payload.get("review_status"),
        payload.get("next_action"),
    ]
    elimination_markers = ("A杀淘汰", "A杀冷却", "A杀出清", "取关淘汰", "禁买")
    return any(
        any(marker in str(text or "") for marker in elimination_markers)
        or str(text or "").strip().lower() in {"a_kill", "a-kill"}
        for text in texts
    )


def _historical_extreme_rank(row):
    for key in ("rank_no", "rank"):
        try:
            value = int(float(str((row or {}).get(key) or "").strip()))
        except ValueError:
            continue
        if value > 0:
            return value
    payload = row.get("payload") if isinstance((row or {}).get("payload"), dict) else {}
    for key in ("rank_no", "rank"):
        try:
            value = int(float(str(payload.get(key) or "").strip()))
        except ValueError:
            continue
        if value > 0:
            return value
    return 9999


def _is_dragon_rebound_historical_extreme(row):
    if not isinstance(row, dict):
        return False
    if not _is_eliminated_historical_extreme(row):
        return False
    rank = _historical_extreme_rank(row)
    if rank > 2:
        return False
    text = _historical_review_text(row)
    return any(marker in text for marker in ("板块锚定龙", "首板", "龙头", "龙一", "核心传导"))


def _review_reasons_from_stock(stock):
    review = (stock or {}).get("trend_aesthetic_review") or {}
    if not isinstance(review, dict):
        return ""
    reasons = [str(reason).strip() for reason in review.get("reasons") or [] if str(reason).strip()]
    return " / ".join(reasons)


def _build_historical_extreme_review(
    data,
    evaluated_stocks,
    extreme_conviction_list,
    shape_repair_pool,
    normalize_stock_code,
    dragon_rebound_watch_pool=None,
):
    review_rows = (
        (data or {}).get("recent_extreme_conviction_mentions_for_review")
        or (data or {}).get("recent_extreme_conviction_mentions")
        or []
    )
    if not review_rows:
        return []
    formal_by_code = {
        normalize_stock_code(item.get("code") or item.get("stock_code")): item
        for item in extreme_conviction_list or []
        if isinstance(item, dict)
    }
    repair_by_code = {
        normalize_stock_code(item.get("code") or item.get("stock_code")): item
        for item in shape_repair_pool or []
        if isinstance(item, dict)
    }
    dragon_rebound_by_code = {
        normalize_stock_code(item.get("code") or item.get("stock_code")): item
        for item in dragon_rebound_watch_pool or []
        if isinstance(item, dict)
    }
    evaluated_by_code = {
        normalize_stock_code(item.get("code") or item.get("stock_code")): item
        for item in evaluated_stocks or []
        if isinstance(item, dict)
    }
    result = []
    for row in review_rows:
        if not isinstance(row, dict):
            continue
        code = _candidate_code(row, normalize_stock_code)
        if not code:
            continue
        enriched = evaluated_by_code.get(code, {})
        name = str(row.get("name") or row.get("stock_name") or enriched.get("name") or "").strip()
        sector = str(row.get("sector") or row.get("sector_candidate") or enriched.get("sector") or "").strip()
        source_section = str(row.get("source_section") or "极度看好名单").strip()
        mention_date = str(row.get("mention_trade_date") or row.get("trade_date") or "").strip()
        if code in formal_by_code:
            destination = "过程观察样本"
            review_status = "当前观察样本"
            review_basis = "进入过程观察样本池"
            next_action = "按最终仓位结论统一收口；不作为明日新增参与依据"
        elif code in repair_by_code:
            repair = repair_by_code[code]
            destination = "形态待修复池"
            review_status = str(repair.get("repair_status") or "待修复").strip()
            review_basis = _review_reasons_from_stock(repair) or "历史好形态但当前承接转弱"
            next_action = str(
                repair.get("next_action")
                or "保留跟踪，重新站回短中线承接后再评估；继续走坏再取关淘汰"
            ).strip()
        elif code in dragon_rebound_by_code:
            rebound = dragon_rebound_by_code[code]
            destination = "龙回头观察池"
            review_status = str(rebound.get("repair_status") or "龙回头观察").strip()
            review_basis = _review_reasons_from_stock(rebound) or "龙回头样本，A杀未修复"
            next_action = str(
                rebound.get("next_action")
                or "单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰"
            ).strip()
        elif _is_dragon_rebound_historical_extreme(row):
            destination = "龙回头观察池"
            review_status = "龙回头观察"
            review_basis = str(row.get("reason") or "排名靠前锚定龙，A杀未修复").strip()
            next_action = "单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰"
        elif _is_eliminated_historical_extreme(row):
            destination = "取关淘汰"
            review_status = "A杀/结构破坏"
            review_basis = "A杀或继续走坏"
            next_action = "不进明日比较，后续重新站回短中线承接后再重建样本"
        else:
            destination = "历史观察"
            review_status = str(row.get("review_status") or "历史复核").strip()
            review_basis = str(row.get("reason") or row.get("next_action") or row.get("invalidation") or "未进入正式名单或形态待修复池").strip()
            next_action = "继续按历史复盘观察，不写成明日新增参与"
        result.append(
            {
                "mention_trade_date": mention_date,
                "name": name,
                "code": code,
                "sector": sector,
                "source_section": source_section,
                "destination": destination,
                "review_status": review_status,
                "review_basis": review_basis,
                "next_action": next_action,
            }
        )
    return result


def _has_anchor_reversal_contract(item):
    if not isinstance(item, dict):
        return False
    return any(
        str(item.get(key) or "").strip()
        for key in (
            "anchor_reversal_decision",
            "sector_anchor",
            "candidate_role",
            "relationship_to_anchor",
            "why_not_anchor",
        )
    )


def _is_primary_conviction(item):
    return bool((item or {}).get("primary_buy_candidate")) or str((item or {}).get("sniper_role") or "").strip() == "明日主买对象"


def _is_backup_conviction(item):
    return bool((item or {}).get("backup_buy_candidate")) or str((item or {}).get("sniper_role") or "").strip() == "明日补位对象"


def _apply_anchor_reversal_visible_groups(
    *,
    core_stocks,
    secondary_stocks,
    ignored_stocks,
    extreme_conviction_list,
    mainline_evaluated_stocks,
    normalize_stock_code,
):
    if not any(_has_anchor_reversal_contract(item) for item in extreme_conviction_list or []):
        return core_stocks, secondary_stocks, ignored_stocks

    primary = [dict(item) for item in extreme_conviction_list or [] if _is_primary_conviction(item)]
    backup = [dict(item) for item in extreme_conviction_list or [] if _is_backup_conviction(item)]
    visible_codes = {
        _candidate_code(item, normalize_stock_code)
        for item in primary + backup
        if _candidate_code(item, normalize_stock_code)
    }
    observation = [
        dict(item)
        for item in extreme_conviction_list or []
        if _candidate_code(item, normalize_stock_code) not in visible_codes
    ]
    evaluated_by_code = {
        _candidate_code(item, normalize_stock_code): item
        for item in mainline_evaluated_stocks or []
        if _candidate_code(item, normalize_stock_code)
    }
    extra_ignored = [
        item
        for code, item in evaluated_by_code.items()
        if code and code not in visible_codes and code not in {_candidate_code(row, normalize_stock_code) for row in observation}
    ]
    return primary[:1], backup[:1], observation + extra_ignored


def build_candidate_bundle_contract(
    data,
    exit_analysis,
    candidates,
    watchlist,
    abnormal_watch_map,
    dragon_stocks,
    zt_pool_by_sector=None,
    gem_breathing_candidates=None,
    target_date="",
    *,
    normalize_stock_code,
    get_abnormal_rank_adjustment,
    split_candidates_by_mainline,
    build_gem_observation_pool,
    build_sector_trend_snapshot,
    build_extreme_conviction_list=None,
    build_extreme_conviction_groups=None,
    fetch_recent_price_bars=None,
):
    zt_pool_by_sector = zt_pool_by_sector or {}
    gem_breathing_candidates = gem_breathing_candidates or []
    replay_mode = bool(data.get("replay_mode"))
    logs = []
    stock_info_map = _build_code_map(data.get("stock_full_info", {}), normalize_stock_code, ("code", "代码", "stock_code"))
    volume_anomaly_map = _build_code_map(data.get("volume_anomalies", []), normalize_stock_code, ("stock_code", "code", "代码"))
    stock_risk_map = _build_code_map(data.get("stock_risk_map", {}), normalize_stock_code, ("code", "stock_code", "ts_code", "代码"))
    xuangubao_reason_map = _build_code_map(
        (data.get("xuangubao_data") or {}).get("xuangubao_limit_up_reasons", []),
        normalize_stock_code,
        ("symbol", "code", "stock_code"),
    )
    xueqiu_argument_map = _build_xueqiu_argument_map(data.get("xueqiu_hot_stock_arguments", []), normalize_stock_code)

    lianban_data = data.get("lianban_data", {})
    lb_stocks_map = {}
    if isinstance(lianban_data, dict) and "stocks" in lianban_data:
        lianban_stocks = lianban_data["stocks"]
    elif isinstance(lianban_data, list):
        lianban_stocks = lianban_data
    else:
        lianban_stocks = []
    for lb_stock in lianban_stocks:
        if isinstance(lb_stock, dict):
            code = normalize_stock_code(lb_stock.get("code", ""))
            lb_stocks_map[code] = {
                "连板数": lb_stock.get("连板数", lb_stock.get("lianban_days", 0)),
                "昨日涨停价": lb_stock.get("昨日涨停价", 0),
                "涨停原因": lb_stock.get("涨停原因", lb_stock.get("reason", "")),
                "sector": lb_stock.get("sector") or lb_stock.get("所属行业") or "",
                "plates": list(lb_stock.get("plates") or []),
            }

    primary_mainline = str(exit_analysis.get("sector_name", "") or "").strip()
    watchlist_codes = {_candidate_code(stock, normalize_stock_code) for stock in watchlist or []}
    mention_candidates = [
        item
        for item in _build_recent_extreme_mention_candidates(data, normalize_stock_code)
        if item.get("code") not in watchlist_codes
    ]
    source_codes = set(watchlist_codes)
    source_codes.update(_candidate_code(item, normalize_stock_code) for item in mention_candidates)
    anchor_source_candidates = _build_anchor_source_candidates(
        candidates=candidates,
        dragon_stocks=dragon_stocks,
        normalize_stock_code=normalize_stock_code,
        existing_codes=source_codes,
    )
    source_codes.update(_candidate_code(item, normalize_stock_code) for item in anchor_source_candidates)
    hot_capacity_anchor_candidates = _build_hot_capacity_anchor_candidates(
        data=data,
        candidates=candidates,
        stock_info_map=stock_info_map,
        normalize_stock_code=normalize_stock_code,
        existing_codes=source_codes,
        mainline_name=primary_mainline,
    )
    evaluation_source_stocks = (
        list(watchlist or [])
        + mention_candidates
        + anchor_source_candidates
        + hot_capacity_anchor_candidates
    )

    evaluated_stocks = []
    for source_order, stock in enumerate(evaluation_source_stocks):
        item = dict(stock)
        code = item.get("code", "")
        normalized_code = normalize_stock_code(code)
        _enrich_candidate_item(item, normalized_code, stock_info_map, volume_anomaly_map)
        _enrich_candidate_with_xuangubao_reason(item, normalized_code, xuangubao_reason_map)
        _enrich_candidate_with_xueqiu_argument(item, normalized_code, xueqiu_argument_map)
        _enrich_candidate_with_stock_risk(item, normalized_code, stock_risk_map)
        _enrich_candidate_with_recent_bars(
            item,
            normalized_code,
            target_date,
            fetch_recent_price_bars=fetch_recent_price_bars,
            fast_fail=replay_mode,
        )
        _normalize_candidate_sector(item)
        _apply_trade_narrative_sector(item)
        base_score = item.get("score", 0)
        abnormal_item = abnormal_watch_map.get(code, {}) or abnormal_watch_map.get(normalized_code, {})
        abnormal_adjustment, abnormal_summary, abnormal_rule = get_abnormal_rank_adjustment(abnormal_item)
        lb_info = lb_stocks_map.get(code, {})
        if item.get("reason") in (None, "") and lb_info.get("涨停原因"):
            item["reason"] = lb_info.get("涨停原因")
        if lb_info.get("sector") and item.get("sector") in (None, ""):
            item["sector"] = lb_info.get("sector")
        if lb_info.get("plates") and not item.get("plates"):
            item["plates"] = lb_info.get("plates")
        _normalize_candidate_sector(item)
        _apply_trade_narrative_sector(item)
        lb_count = lb_info.get("连板数", 0)
        if lb_count >= 3:
            core_level = "🔥🔥 高标核心"
            tmr_forecast = f"{lb_count}进{lb_count+1}，若竞价高开可能继续"
        elif lb_count == 2:
            core_level = "🔥 连板核心"
            tmr_forecast = "2进3，观察竞价是否超预期"
        elif lb_count == 1 and base_score >= 70:
            core_level = "⭐ 首板强芯"
            tmr_forecast = "首板形态好，明日有连板预期"
        elif base_score >= 50:
            core_level = "✓ 溢价候选"
            tmr_forecast = "明日可能高开溢价"
        else:
            core_level = "○ 观察备选"
            tmr_forecast = "需看明日竞价强弱"

        if abnormal_adjustment >= 18 and "高标核心" not in core_level and "连板核心" not in core_level:
            core_level = "🔥 异动抗跌核心"
        elif abnormal_adjustment >= 10 and core_level in ["✓ 溢价候选", "○ 观察备选"]:
            core_level = "⭐ 抗跌观察芯"
        elif abnormal_adjustment < 0:
            core_level = "○ 转弱观察"

        if abnormal_item:
            if abnormal_item.get("follow_state") == "跌不下去":
                tmr_forecast = f"{tmr_forecast}；异动后承接强，优先看竞价表态、开盘承接和结构确认"
            elif abnormal_item.get("follow_state") == "缩量消化":
                tmr_forecast = f"{tmr_forecast}；异动后缩量消化，可继续跟"
            elif abnormal_item.get("follow_state") == "已经转弱":
                tmr_forecast = f"{tmr_forecast}；但异动后承接差，只能降级观察"
            elif abnormal_item.get("follow_state") == "新异动待观察":
                tmr_forecast = f"{tmr_forecast}；异动刚出现，先看次日承接"

        selection_priority, selection_priority_reason = _build_candidate_selection_priority(
            item,
            lb_count=lb_count,
            abnormal_item=abnormal_item,
            abnormal_adjustment=abnormal_adjustment,
            source_order=source_order,
        )
        item["selection_priority"] = selection_priority
        item["selection_priority_tier"] = _selection_priority_label(selection_priority)
        item["selection_priority_reason"] = selection_priority_reason
        item["tomorrow_strength"] = base_score
        item["base_strength_score"] = base_score
        item["core_level"] = core_level
        item["tmr_forecast"] = tmr_forecast
        item["连板数"] = lb_count
        item["abnormal_bonus"] = abnormal_adjustment
        item["abnormal_summary"] = abnormal_summary
        item["abnormal_rule"] = abnormal_rule
        item["abnormal_follow_state"] = abnormal_item.get("follow_state", "")
        item["abnormal_type"] = abnormal_item.get("abnormal_type", "")
        item["abnormal_setup_signal_id"] = abnormal_item.get("setup_signal_id", "")
        item["abnormal_setup_signal_label"] = abnormal_item.get("setup_signal_label", "")
        item["abnormal_setup_signal_phase"] = abnormal_item.get("setup_signal_phase", "")
        item["abnormal_is_degraded_snapshot"] = bool(abnormal_item.get("is_degraded_snapshot", False))
        evaluated_stocks.append(item)

    evaluated_stocks.sort(
        key=_candidate_selection_priority_sort_key,
        reverse=True,
    )
    _append_log(logs, "candidate_condition_sorting", "success", "已完成候选条件链排序", evaluated_count=len(evaluated_stocks))

    if primary_mainline:
        mainline_evaluated_stocks, crossline_evaluated_stocks = split_candidates_by_mainline(
            evaluated_stocks,
            primary_mainline,
        )
        if not mainline_evaluated_stocks:
            mainline_evaluated_stocks = list(evaluated_stocks)
            crossline_evaluated_stocks = []
    else:
        mainline_evaluated_stocks = list(evaluated_stocks)
        crossline_evaluated_stocks = []

    crossline_observation_stocks = crossline_evaluated_stocks[:4]
    gem_observation_stocks = build_gem_observation_pool(gem_breathing_candidates, target_date=target_date)

    core_stocks = mainline_evaluated_stocks[:3] if len(mainline_evaluated_stocks) >= 3 else mainline_evaluated_stocks
    secondary_stocks = mainline_evaluated_stocks[3:6] if len(mainline_evaluated_stocks) >= 6 else mainline_evaluated_stocks[3:]
    ignored_stocks = mainline_evaluated_stocks[6:]
    crossline_core_stocks = crossline_observation_stocks[:2] if len(crossline_observation_stocks) >= 2 else crossline_observation_stocks
    crossline_secondary_stocks = crossline_observation_stocks[2:4] if len(crossline_observation_stocks) >= 4 else crossline_observation_stocks[2:]
    crossline_ignored_stocks = crossline_evaluated_stocks[4:]
    sector_trend_snapshot = build_sector_trend_snapshot(
        candidates,
        watchlist,
        evaluated_stocks,
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        top_n=5,
    )
    risk_context = {
        "systemic_risk_warnings": list(data.get("systemic_risk_warnings") or []),
        "risk_theme_impacts": list(data.get("risk_theme_impacts") or []),
        "risk_sectors": list(data.get("risk_sectors") or []),
    }
    shape_repair_pool = []
    dragon_rebound_watch_pool = []
    if build_extreme_conviction_groups:
        try:
            conviction_groups = build_extreme_conviction_groups(
                evaluated_stocks,
                exit_analysis.get("sector_name", ""),
                sector_snapshot=sector_trend_snapshot,
                top_n=3,
                risk_context=risk_context,
            )
        except TypeError as error:
            if "risk_context" not in str(error):
                raise
            conviction_groups = build_extreme_conviction_groups(
                evaluated_stocks,
                exit_analysis.get("sector_name", ""),
                sector_snapshot=sector_trend_snapshot,
                top_n=3,
            )
        extreme_conviction_list = list((conviction_groups or {}).get("extreme_conviction_list") or [])
        shape_repair_pool = list((conviction_groups or {}).get("shape_repair_pool") or [])
        dragon_rebound_watch_pool = list((conviction_groups or {}).get("dragon_rebound_watch_pool") or [])
    elif callable(build_extreme_conviction_list):
        try:
            extreme_conviction_list = build_extreme_conviction_list(
                evaluated_stocks,
                exit_analysis.get("sector_name", ""),
                sector_snapshot=sector_trend_snapshot,
                top_n=3,
                risk_context=risk_context,
            )
        except TypeError as error:
            if "risk_context" not in str(error):
                raise
            extreme_conviction_list = build_extreme_conviction_list(
                evaluated_stocks,
                exit_analysis.get("sector_name", ""),
                sector_snapshot=sector_trend_snapshot,
                top_n=3,
            )
    else:
        extreme_conviction_list = []
    historical_extreme_review = _build_historical_extreme_review(
        data,
        evaluated_stocks,
        extreme_conviction_list,
        shape_repair_pool,
        normalize_stock_code,
        dragon_rebound_watch_pool,
    )
    core_stocks, secondary_stocks, ignored_stocks = _apply_anchor_reversal_visible_groups(
        core_stocks=core_stocks,
        secondary_stocks=secondary_stocks,
        ignored_stocks=ignored_stocks,
        extreme_conviction_list=extreme_conviction_list,
        mainline_evaluated_stocks=mainline_evaluated_stocks,
        normalize_stock_code=normalize_stock_code,
    )
    _append_log(logs, "candidate_grouping", "success", "已完成主线/跨线/创业板分组", mainline_name=primary_mainline)

    return {
        "evaluated_stocks": evaluated_stocks,
        "mainline_name": primary_mainline,
        "mainline_evaluated_stocks": mainline_evaluated_stocks,
        "core_stocks": core_stocks,
        "secondary_stocks": secondary_stocks,
        "ignored_stocks": ignored_stocks,
        "crossline_evaluated_stocks": crossline_evaluated_stocks,
        "crossline_observation_stocks": crossline_observation_stocks,
        "gem_observation_stocks": gem_observation_stocks,
        "crossline_core_stocks": crossline_core_stocks,
        "crossline_secondary_stocks": crossline_secondary_stocks,
        "crossline_ignored_stocks": crossline_ignored_stocks,
        "sector_trend_snapshot": sector_trend_snapshot,
        "extreme_conviction_list": extreme_conviction_list,
        "shape_repair_pool": shape_repair_pool,
        "dragon_rebound_watch_pool": dragon_rebound_watch_pool,
        "historical_extreme_review": historical_extreme_review,
        "module_logs": logs,
    }


def build_step2_candidate_bundle(
    data,
    exit_analysis,
    candidates,
    watchlist,
    abnormal_watch_map,
    dragon_stocks,
    zt_pool_by_sector=None,
    gem_breathing_candidates=None,
    target_date="",
    *,
    helpers=None,
):
    helpers = helpers or {}
    return build_candidate_bundle_contract(
        data,
        exit_analysis,
        candidates,
        watchlist,
        abnormal_watch_map,
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        gem_breathing_candidates=gem_breathing_candidates,
        target_date=target_date,
        normalize_stock_code=helpers["normalize_stock_code"],
        get_abnormal_rank_adjustment=helpers["get_abnormal_rank_adjustment"],
        split_candidates_by_mainline=helpers["split_candidates_by_mainline"],
        build_gem_observation_pool=helpers["build_gem_observation_pool"],
        build_sector_trend_snapshot=helpers["build_sector_trend_snapshot"],
        build_extreme_conviction_list=helpers["build_extreme_conviction_list"],
        build_extreme_conviction_groups=helpers.get("build_extreme_conviction_groups"),
        fetch_recent_price_bars=helpers.get("fetch_recent_price_bars"),
    )
