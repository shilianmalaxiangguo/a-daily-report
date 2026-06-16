from __future__ import annotations


SCHEMA_VERSION = "sector_capital_carrier_paper_strategy.v1"
DATE_KEYS = ("trade_date", "source_date", "query_date", "date", "day")


def _clean(value, default=""):
    text = str(value if value is not None else "").strip()
    return text or default


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rows(value):
    return value if isinstance(value, list) else []


def _normalize_date_text(value):
    text = _clean(value)
    if not text:
        return ""
    text = text.replace("/", "-")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _row_source_date(row):
    if not isinstance(row, dict):
        return ""
    for key in DATE_KEYS:
        date_text = _normalize_date_text(row.get(key))
        if date_text:
            return date_text
    return ""


def _row_display_label(row):
    if not isinstance(row, dict):
        return "未知"
    name = _name_from_row(row) or _clean(row.get("name"))
    code = _code_from_row(row)
    if name and code:
        return f"{name}({code})"
    return name or code or _clean(row.get("name"), "未知")


def _filter_same_day_rows(rows, expected_date, mismatches, source_name):
    rows = _rows(rows)
    if not expected_date:
        return rows
    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            filtered.append(row)
            continue
        source_date = _row_source_date(row)
        if source_date and source_date != expected_date:
            mismatches.append(
                {
                    "source": source_name,
                    "expected_trade_date": expected_date,
                    "source_date": source_date,
                    "label": _row_display_label(row),
                    "reason": "输入行日期不是T0，不参与板块资金载体生成",
                }
            )
            continue
        filtered.append(row)
    return filtered


def _same_day_filtered_data(data, trade_date):
    data = data if isinstance(data, dict) else {}
    expected_date = _normalize_date_text(trade_date)
    mismatches = []
    if not expected_date:
        return data, mismatches
    filtered = dict(data)
    for key in (
        "hot_plates",
        "sector_change_up",
        "hot_rank_top50",
        "hot_rank_top30",
        "integrated_hot_list",
        "turnover_rank",
        "zt_pool",
        "lianban_data",
    ):
        filtered[key] = _filter_same_day_rows(data.get(key), expected_date, mismatches, key)
    sector_fund_flow = data.get("sector_fund_flow") if isinstance(data.get("sector_fund_flow"), dict) else {}
    if sector_fund_flow:
        fund_flow = dict(sector_fund_flow)
        for key in ("inflow", "outflow"):
            fund_flow[key] = _filter_same_day_rows(
                sector_fund_flow.get(key),
                expected_date,
                mismatches,
                f"sector_fund_flow.{key}",
            )
        filtered["sector_fund_flow"] = fund_flow
    zt_pool_by_sector = data.get("zt_pool_by_sector") if isinstance(data.get("zt_pool_by_sector"), dict) else {}
    if zt_pool_by_sector:
        filtered["zt_pool_by_sector"] = {
            sector: _filter_same_day_rows(
                rows,
                expected_date,
                mismatches,
                f"zt_pool_by_sector.{sector}",
            )
            for sector, rows in zt_pool_by_sector.items()
        }
    summary = data.get("mainline_turnover_summary")
    if isinstance(summary, dict):
        source_date = _row_source_date(summary)
        if source_date and source_date != expected_date:
            mismatches.append(
                {
                    "source": "mainline_turnover_summary",
                    "expected_trade_date": expected_date,
                    "source_date": source_date,
                    "label": _clean(summary.get("current_mainline"), "主线记录"),
                    "reason": "主线记录日期不是T0，不参与板块资金载体生成",
                }
            )
            filtered["mainline_turnover_summary"] = {}
    return filtered, mismatches[:80]


def _stock_code(value):
    text = _clean(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return digits[-6:]
    return text


def _code_from_row(row):
    if not isinstance(row, dict):
        return ""
    return _stock_code(row.get("code") or row.get("代码") or row.get("stock_code"))


def _name_from_row(row):
    if not isinstance(row, dict):
        return ""
    return _clean(row.get("name") or row.get("名称") or row.get("stock_name"))


def _stock_label(stock):
    stock = stock if isinstance(stock, dict) else {}
    name = _clean(stock.get("name"), "未知")
    code = _stock_code(stock.get("code"))
    return f"{name}({code})" if code else name


def _sector_aliases(*values):
    names = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            names.update(_sector_aliases(*value))
            continue
        text = _clean(value)
        if not text:
            continue
        names.add(text)
        if "电力" in text or "发电" in text:
            names.update({"电力", "新型电力", "火力发电", "绿色电力"})
        if "煤炭" in text:
            names.update({"煤炭", "煤炭开采", "煤炭开采加工"})
        if "半导体" in text or "芯片" in text:
            names.update({"半导体", "国产芯片替代", "存储芯片", "汽车芯片"})
        if "化学纤维" in text or text == "化纤":
            names.update({"化学纤维", "化纤"})
        if "轨交" in text:
            names.update({"轨交设备"})
        if "元件" in text or "元器件" in text or "被动元件" in text or "PCB" in text:
            names.update({"元件", "元器件", "被动元件", "PCB", "消费电子"})
        if "通信" in text or "CPO" in text or "光通信" in text or "共封装光学" in text:
            names.update({"通信设备", "光通信/CPO", "CPO", "共封装光学", "高速连接器"})
        if "小金属" in text or "锗" in text or "稀土" in text:
            names.update({"小金属", "稀土永磁", "金属新材料"})
        if "化学制品" in text or "化工" in text or "氟" in text:
            names.update({"化学制品", "化工原料", "氟化工"})
    return names


def _names_match(left, right):
    left = _clean(left)
    right = _clean(right)
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 2 and len(right) >= 2 and (left in right or right in left):
        return True
    return False


def _terms_match_aliases(terms, aliases):
    expanded = set()
    for term in terms:
        expanded.update(_sector_aliases(term))
    aliases = set(aliases or set())
    if expanded & aliases:
        return True
    for term in expanded:
        for alias in aliases:
            if _names_match(term, alias):
                return True
    return False


def _row_text_terms(row):
    if not isinstance(row, dict):
        return set()
    terms = set()
    scalar_keys = (
        "sector",
        "所属行业",
        "industry",
        "concept",
        "popularity_tag",
        "zt_type",
        "涨停统计",
        "reason",
        "xuangubao_stock_reason",
    )
    list_keys = (
        "concepts",
        "tags",
        "sector_tags",
        "all_tags",
        "status_tags",
        "xuangubao_related_plate_names",
    )
    for key in scalar_keys:
        text = _clean(row.get(key))
        if text:
            terms.add(text)
    for key in list_keys:
        value = row.get(key)
        if isinstance(value, (list, tuple, set)):
            for item in value:
                text = _clean(item)
                if text:
                    terms.add(text)
    for item in row.get("xuangubao_related_plates") or []:
        if isinstance(item, dict):
            text = _clean(item.get("plate_name"))
            if text:
                terms.add(text)
    return terms


def _add_sector_profile(profiles, name, *, source_type, evidence, order=999):
    name = _clean(name)
    if not name:
        return
    aliases = _sector_aliases(name) or {name}
    existing_key = None
    for key, profile in profiles.items():
        if profile["aliases"] & aliases:
            existing_key = key
            break
    key = existing_key or name
    profile = profiles.setdefault(
        key,
        {
            "name": name,
            "aliases": set(aliases),
            "source_types": set(),
            "non_limit_source_types": set(),
            "evidence": [],
            "best_order": 999,
        },
    )
    profile["aliases"].update(aliases)
    profile["source_types"].add(source_type)
    if source_type != "limit_width":
        profile["non_limit_source_types"].add(source_type)
    if evidence and evidence not in profile["evidence"]:
        profile["evidence"].append(evidence)
    profile["best_order"] = min(profile["best_order"], _safe_int(order, 999))


def _name_suffix(row):
    name = _clean(row.get("name")) if isinstance(row, dict) else ""
    change = _safe_float(
        (row or {}).get("change_pct")
        if isinstance(row, dict) and "change_pct" in row
        else (row or {}).get("zdf")
        if isinstance(row, dict)
        else None
    )
    net = _safe_float(
        (row or {}).get("net_inflow_yi")
        if isinstance(row, dict) and "net_inflow_yi" in row
        else (row or {}).get("zljlr")
        if isinstance(row, dict)
        else None
    )
    parts = []
    if name:
        parts.append(name)
    if change is not None:
        parts.append(f"涨幅{change:.2f}%")
    if net is not None:
        parts.append(f"净额{net:g}亿")
    return "（" + "，".join(parts) + "）" if parts else ""


def _sector_profile_public(profile):
    return {
        "name": profile["name"],
        "aliases": sorted(profile["aliases"]),
        "source_types": sorted(profile["source_types"]),
        "non_limit_source_types": sorted(profile["non_limit_source_types"]),
        "evidence": list(profile["evidence"][:6]),
        "best_order": profile["best_order"],
    }


def _build_sector_profiles(data):
    data = data if isinstance(data, dict) else {}
    profiles = {}
    for row in _rows(data.get("hot_plates"))[:8]:
        if not isinstance(row, dict):
            continue
        order = _safe_int(row.get("order") or row.get("rank"), 999)
        evidence = "热度板块第" + _clean(order) + (f"，{_clean(row.get('tag'))}" if _clean(row.get("tag")) else "")
        _add_sector_profile(profiles, row.get("name"), source_type="hot_plate", evidence=evidence, order=order)

    sector_fund_flow = data.get("sector_fund_flow") if isinstance(data.get("sector_fund_flow"), dict) else {}
    for row in _rows(sector_fund_flow.get("inflow"))[:10]:
        if not isinstance(row, dict):
            continue
        net = _safe_float(row.get("net_inflow_yi") if "net_inflow_yi" in row else row.get("zljlr"), 0)
        change = _safe_float(row.get("change_pct") if "change_pct" in row else row.get("zdf"), 0)
        if (net or 0) <= 0 and (change or 0) <= 0:
            continue
        evidence = f"资金流入{_name_suffix(row)}"
        _add_sector_profile(profiles, row.get("name"), source_type="fund_flow", evidence=evidence)

    for row in _rows(data.get("sector_change_up"))[:8]:
        if not isinstance(row, dict):
            continue
        change = _safe_float(row.get("change_pct") if "change_pct" in row else row.get("zdf"), 0)
        if (change or 0) <= 0:
            continue
        rank = _safe_int(row.get("rank"), 999)
        evidence = "板块涨幅" + (f"第{rank}" if rank != 999 else "") + (f"，涨幅{change:.2f}%" if change is not None else "")
        _add_sector_profile(profiles, row.get("name"), source_type="sector_change", evidence=evidence, order=rank)

    summary = data.get("mainline_turnover_summary") if isinstance(data.get("mainline_turnover_summary"), dict) else {}
    mainline_names = [
        summary.get("current_mainline"),
        (summary.get("double_mainline_summary") or {}).get("cycle_mainline") if isinstance(summary.get("double_mainline_summary"), dict) else "",
        (summary.get("double_mainline_summary") or {}).get("daily_attack_line") if isinstance(summary.get("double_mainline_summary"), dict) else "",
    ]
    for name in mainline_names:
        text = _clean(name)
        if not text or text in {"暂无", "无", "多方向"}:
            continue
        _add_sector_profile(
            profiles,
            text,
            source_type="mainline",
            evidence="主线成交/主攻线记录：" + text,
            order=1,
        )

    zt_pool_by_sector = data.get("zt_pool_by_sector") if isinstance(data.get("zt_pool_by_sector"), dict) else {}
    for sector, rows in zt_pool_by_sector.items():
        count = len(_rows(rows))
        if count >= 2:
            _add_sector_profile(
                profiles,
                sector,
                source_type="limit_width",
                evidence=f"同板块涨停宽度{count}只，只作为板块热度证据",
            )

    selected = []
    eliminated = []
    for profile in profiles.values():
        non_limit_count = len(profile["non_limit_source_types"])
        source_count = len(profile["source_types"])
        strong_top_hot = "hot_plate" in profile["source_types"] and profile["best_order"] <= 3
        selected_by = []
        if "mainline" in profile["non_limit_source_types"]:
            selected_by.append("主线记录")
        if non_limit_count >= 2:
            selected_by.append("至少两类非涨停板块证据")
        if strong_top_hot and non_limit_count >= 1:
            selected_by.append("热度板块前三且不是涨停池单点起步")
        if "fund_flow" in profile["source_types"] and "sector_change" in profile["source_types"]:
            selected_by.append("资金流入与板块涨幅同向")
        row = _sector_profile_public(profile)
        if selected_by:
            row["status"] = "survived"
            row["reason"] = "；".join(selected_by)
            selected.append(row)
        else:
            row["status"] = "eliminated"
            row["reason"] = (
                "只有涨停宽度或单一板块线索，不能证明资金已经选择该方向"
                if source_count
                else "板块线索不足"
            )
            eliminated.append(row)

    selected.sort(key=lambda item: (item.get("best_order", 999), -len(item.get("source_types", [])), item.get("name", "")))
    eliminated.sort(key=lambda item: (item.get("best_order", 999), item.get("name", "")))
    return {
        "input_count": len(profiles),
        "selected": selected[:8],
        "eliminated": eliminated[:40],
    }


def _add_stock_profile(profiles, row, *, source_type, source_label, fallback_sector="", order=999):
    if not isinstance(row, dict):
        return
    code = _code_from_row(row)
    name = _name_from_row(row)
    if not code and not name:
        return
    key = code or f"name:{name}"
    sector = _clean(row.get("sector") or row.get("所属行业") or fallback_sector)
    profile = profiles.setdefault(
        key,
        {
            "code": code,
            "name": name,
            "sector": sector,
            "terms": set(),
            "source_types": set(),
            "source_labels": [],
            "source_orders": {},
            "change_pct": None,
            "turnover": None,
            "hot_rank": None,
            "turnover_rank": None,
        },
    )
    if code and not profile.get("code"):
        profile["code"] = code
    if name and not profile.get("name"):
        profile["name"] = name
    if sector and not profile.get("sector"):
        profile["sector"] = sector
    profile["terms"].update(_row_text_terms(row))
    if fallback_sector:
        profile["terms"].add(fallback_sector)
    profile["source_types"].add(source_type)
    if source_label and source_label not in profile["source_labels"]:
        profile["source_labels"].append(source_label)
    profile["source_orders"][source_type] = min(_safe_int(order, 999), profile["source_orders"].get(source_type, 999))
    change = _safe_float(row.get("change_pct") if "change_pct" in row else row.get("zdf") if "zdf" in row else row.get("涨跌幅"))
    if change is not None:
        profile["change_pct"] = change
    turnover = _safe_float(row.get("turnover") if "turnover" in row else row.get("成交额"))
    if turnover is not None:
        profile["turnover"] = turnover
    rank = _safe_int(row.get("rank") if "rank" in row else row.get("hot_rank"), 999)
    if source_type in {"hot_rank", "integrated_hot"} and rank != 999:
        profile["hot_rank"] = min(rank, profile["hot_rank"] or 999)
    if source_type == "turnover" and rank != 999:
        profile["turnover_rank"] = min(rank, profile["turnover_rank"] or 999)


def _build_stock_profiles(data):
    data = data if isinstance(data, dict) else {}
    profiles = {}
    hot_rank_rows = _rows(data.get("hot_rank_top50")) or _rows(data.get("hot_rank_top30"))
    for row in hot_rank_rows:
        rank = _safe_int(row.get("rank") if isinstance(row, dict) else None, 999)
        _add_stock_profile(
            profiles,
            row,
            source_type="hot_rank",
            source_label="热榜第" + _clean(rank),
            order=rank,
        )
    for row in _rows(data.get("integrated_hot_list")):
        rank = _safe_int((row or {}).get("rank") or (row or {}).get("hot_rank"), 999) if isinstance(row, dict) else 999
        _add_stock_profile(
            profiles,
            row,
            source_type="integrated_hot",
            source_label="整合热榜" + (f"第{rank}" if rank != 999 else ""),
            order=rank,
        )
    for row in _rows(data.get("turnover_rank")):
        rank = _safe_int(row.get("rank") if isinstance(row, dict) else None, 999)
        turnover = _safe_float(row.get("turnover") if isinstance(row, dict) else None)
        label = "成交额榜" + (f"第{rank}" if rank != 999 else "") + (f"，成交{turnover:g}亿" if turnover is not None else "")
        _add_stock_profile(profiles, row, source_type="turnover", source_label=label, order=rank)
    for row in _rows(data.get("zt_pool")):
        _add_stock_profile(
            profiles,
            row,
            source_type="limit_up",
            source_label="涨停/封板证据：" + _clean(row.get("涨停统计") or row.get("zt_type"), "涨停"),
            fallback_sector=_clean(row.get("所属行业")),
        )
    for row in _rows(data.get("lianban_data")):
        days = _clean(row.get("lianban_days") if isinstance(row, dict) else "")
        _add_stock_profile(
            profiles,
            row,
            source_type="limit_up",
            source_label="连板/高度证据" + (f"：{days}板" if days else ""),
            fallback_sector=_clean(row.get("sector") if isinstance(row, dict) else ""),
        )
    zt_pool_by_sector = data.get("zt_pool_by_sector") if isinstance(data.get("zt_pool_by_sector"), dict) else {}
    for sector, rows in zt_pool_by_sector.items():
        for row in _rows(rows):
            _add_stock_profile(
                profiles,
                row,
                source_type="limit_up",
                source_label="同板块涨停证据：" + _clean(row.get("zt_type") if isinstance(row, dict) else "", "涨停"),
                fallback_sector=sector,
            )
    sector_fund_flow = data.get("sector_fund_flow") if isinstance(data.get("sector_fund_flow"), dict) else {}
    for row in _rows(sector_fund_flow.get("inflow")) if isinstance(sector_fund_flow, dict) else []:
        leader_name = _clean(row.get("lzg_name")) if isinstance(row, dict) else ""
        if not leader_name:
            continue
        for profile in profiles.values():
            if _names_match(profile.get("name"), leader_name):
                profile["source_types"].add("sector_leader")
                label = f"板块资金表领涨股：{leader_name}"
                if label not in profile["source_labels"]:
                    profile["source_labels"].append(label)
                profile["terms"].add(_clean(row.get("name")))
    return list(profiles.values())


def _candidate_role(profile):
    source_types = profile.get("source_types") or set()
    hot_rank = profile.get("hot_rank") or 999
    turnover_rank = profile.get("turnover_rank") or 999
    turnover = profile.get("turnover")
    change = profile.get("change_pct")
    roles = []
    if turnover_rank <= 10 or (turnover is not None and turnover >= 50):
        roles.append("趋势容量核心")
    if hot_rank <= 10 or "sector_leader" in source_types:
        roles.append("板块锚/资金表领涨")
    if change is not None and change >= 5:
        roles.append("量化弹性")
    if "limit_up" in source_types:
        roles.append("涨停/连板证据")
    return roles or ["过程观察"]


def _evidence_families(profile):
    source_types = profile.get("source_types") or set()
    families = []
    if "hot_rank" in source_types or "integrated_hot" in source_types:
        families.append("热榜关注")
    if "turnover" in source_types:
        families.append("容量成交")
    if "sector_leader" in source_types:
        families.append("板块资金表领涨")
    if "limit_up" in source_types:
        families.append("涨停/连板证据")
    return families


def _profile_matches_sector(profile, sector_profile):
    terms = set(profile.get("terms") or set())
    if profile.get("sector"):
        terms.add(profile.get("sector"))
    return _terms_match_aliases(terms, sector_profile.get("aliases") or [])


def build_sector_capital_carrier_strategy(trade_date, data):
    data = data if isinstance(data, dict) else {}
    data, source_date_mismatches = _same_day_filtered_data(data, trade_date)
    sectors = _build_sector_profiles(data)
    selected_sectors = sectors["selected"]
    stock_profiles = _build_stock_profiles(data)
    candidate_rows = []
    eliminated_rows = []
    for profile in stock_profiles:
        matched_sector = next((sector for sector in selected_sectors if _profile_matches_sector(profile, sector)), None)
        label = _stock_label(profile)
        if not matched_sector:
            eliminated_rows.append(
                {
                    "stock_label": label,
                    "reason": "没有落在当日已被资金选择的板块内",
                }
            )
            continue
        families = _evidence_families(profile)
        non_limit_families = [item for item in families if item != "涨停/连板证据"]
        if not non_limit_families:
            eliminated_rows.append(
                {
                    "stock_label": label,
                    "reason": "只有涨停/连板证据，不能作为板块资金载体起点",
                }
            )
            continue
        roles = _candidate_role(profile)
        reason = (
            f"{matched_sector['name']}进入板块候选；"
            f"个股证据：{'、'.join(families)}；"
            f"角色：{'、'.join(roles)}"
        )
        candidate_rows.append(
            {
                "stock": {
                    "name": profile.get("name"),
                    "code": profile.get("code"),
                    "sector": profile.get("sector") or matched_sector["name"],
                },
                "stock_label": label,
                "sector": matched_sector["name"],
                "sector_evidence": matched_sector.get("evidence") or [],
                "source_pools": sorted(profile.get("source_types") or []),
                "source_labels": profile.get("source_labels") or [],
                "evidence_families": families,
                "roles": roles,
                "reason": reason,
                "status": "纸面候选",
                "candidate_origin": "sector_capital_carrier_v1",
                "priority": {
                    "sector_order": matched_sector.get("best_order", 999),
                    "family_count": len(families),
                    "hot_rank": profile.get("hot_rank") or 999,
                    "turnover_rank": profile.get("turnover_rank") or 999,
                },
            }
        )
    candidate_rows.sort(
        key=lambda item: (
            item["priority"]["sector_order"],
            -item["priority"]["family_count"],
            item["priority"]["hot_rank"],
            item["priority"]["turnover_rank"],
            item["stock_label"],
        )
    )
    primary = candidate_rows[0] if candidate_rows else {}
    if primary and len(primary.get("evidence_families") or []) >= 2:
        action = "paper_participate"
        action_label = "板块资金载体主样本"
        action_reason = "板块被资金选择，且主样本同时具备至少两类资金载体证据"
    elif primary:
        action = "paper_watch"
        action_label = "纸面观察"
        action_reason = "板块成立，但资金载体证据仍偏单薄"
    else:
        action = "paper_skip"
        action_label = "纸面不参与"
        action_reason = "没有从已选板块中恢复出资金载体"
    return {
        "schema_version": SCHEMA_VERSION,
        "trade_date": _clean(trade_date),
        "action": action,
        "action_label": action_label,
        "action_reason": action_reason,
        "selected_sectors": selected_sectors,
        "eliminated_sectors": sectors["eliminated"],
        "source_date_mismatches": source_date_mismatches,
        "paper_candidates": candidate_rows[:8],
        "primary_candidate": primary,
        "eliminated_candidates": eliminated_rows[:60],
        "stages": [
            {
                "title": "板块线索恢复",
                "input_count": sectors["input_count"],
                "eliminated_count": len(sectors["eliminated"]),
                "survivor_count": len(selected_sectors),
                "survivors": [{"label": item["name"], "reason": item["reason"]} for item in selected_sectors],
                "eliminated": [{"label": item["name"], "reason": item["reason"]} for item in sectors["eliminated"]],
            },
            {
                "title": "板块内资金载体",
                "input_count": len(stock_profiles),
                "eliminated_count": len(eliminated_rows),
                "survivor_count": len(candidate_rows),
                "survivors": [{"label": item["stock_label"], "reason": item["reason"]} for item in candidate_rows[:20]],
                "eliminated": [{"label": item["stock_label"], "reason": item["reason"]} for item in eliminated_rows[:30]],
            },
            {
                "title": "纸面动作",
                "input_count": len(candidate_rows),
                "eliminated_count": max(len(candidate_rows) - 1, 0),
                "survivor_count": 1 if primary else 0,
                "survivors": [{"label": primary.get("stock_label", ""), "reason": action_reason}] if primary else [],
                "eliminated": [
                    {"label": item["stock_label"], "reason": "作为备选样本保留，不抢主样本位置"}
                    for item in candidate_rows[1:8]
                ],
            },
        ],
    }
