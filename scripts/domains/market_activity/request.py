import datetime as _dt


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_activity.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


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

HOT_RANK_SAMPLE_TARGET = 50
HOT_RANK_STATUS_LABEL = f"热度前{HOT_RANK_SAMPLE_TARGET}个股"
HOT_RANK_STEP_LABEL = f"{HOT_RANK_STATUS_LABEL}获取"
_REPORT_STOCK_LIST_KEYS = {
    "hot_rank_top30",
    "hot_rank_top50",
    "integrated_hot_list",
    "turnover_rank",
    "turnover_over_100b",
    "lhb_net_buy_top10",
    "lhb_net_sell_top10",
    "lianban_data",
    "zt_pool",
    "dt_pool",
    "volume_anomalies",
    "trade_signals",
    "watchlist",
    "candidates",
    "dragon_stocks",
    "extreme_conviction_list",
    "display_observation_candidates",
    "observation_candidates",
    "abnormal_watch_pool",
    "high_lianban_stocks",
    "waiting_stocks",
    "scored_executable_stocks",
    "recent_extreme_conviction_mentions",
    "recent_extreme_conviction_mentions_for_review",
    "gem_breathing_candidates",
    "filtered_out_gem_breathing_candidates",
    "knowledge_compounding_candidates",
    "core_candidates",
    "backup_candidates",
}
_REPORT_STOCK_OBJECT_KEYS = {
    "selected_position_candidate",
    "current_core_candidate",
    "best_stock",
    "runner_up",
    "watch_target",
    "watch_anchor",
    "new_entry_target",
    "display_target",
    "canonical_target",
    "old_position",
    "new_target",
    "front_page_selected_position_candidate",
    "primary_buy_candidate",
    "backup_candidate",
    "target",
    "candidate",
}
_REPORT_STOCK_CONTAINER_KEYS = {
    "execution_stage_context",
    "market_research_snapshot",
    "candidate_snapshot",
    "candidate_quality_panel_fields",
    "candidate_quality_samples",
    "step2_bundle",
    "final_target_resolution",
    "sniper_target_derivation",
    "opportunity_comparison",
    "additional_target_comparisons",
}


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _infer_sector_from_reason(text):
    text = str(text or "")
    if "长鑫" in text or "国产芯片" in text:
        return "国产芯片"
    keyword_groups = [
        ("算力", ("Token工厂", "昇腾", "算力", "服务器", "数据中心", "液冷", "东数西算")),
        ("机器人", ("机器人", "减速器", "智能体", "机器视觉", "智能制造", "智能物流")),
        ("商业航天", ("商业航天", "卫星", "航天", "火箭")),
        ("低空经济", ("低空", "无人机", "eVTOL")),
        ("家用电器", ("小家电", "家用电器", "空调")),
        ("消费电子", ("MiniLED", "车载背光", "VR背光", "背光显示", "消费电子", "无线耳机", "苹果产业链")),
        ("食品饮料", ("葡萄酒", "白兰地", "保健酒", "食品", "饮料")),
        ("天然气", ("天然气", "页岩气", "燃气")),
        ("资产重组", ("股权转让", "资产重组", "并购重组", "控制权", "重整", "实控人变更", "国资入主", "资产置换")),
        ("环保", ("环保", "水务")),
        ("汽车产业链", ("汽车拆解", "汽车", "新能源汽车")),
    ]
    for sector, markers in keyword_groups:
        if any(marker in text for marker in markers):
            return sector
    return ""


def _stock_code_keys(item):
    raw_values = [
        item.get("代码", ""),
        item.get("code", ""),
        item.get("ts_code", ""),
    ]
    keys = []
    for raw in raw_values:
        code = str(raw or "").strip()
        if not code:
            continue
        keys.append(code)
        keys.append(code.upper())
        keys.append(code.replace(".SZ", "").replace(".SH", "").replace(".SS", "").replace(".BJ", ""))
    return keys


def _pick_sector_label(item, code_to_sector=None):
    for key in ("所属行业", "industry", "行业", "sector", "板块", "概念", "所属板块"):
        sector = item.get(key, "")
        if _is_valid_sector_label(sector):
            return str(sector).strip()

    code_to_sector = code_to_sector or {}
    for code in _stock_code_keys(item):
        sector = code_to_sector.get(code)
        if _is_valid_sector_label(sector):
            return str(sector).strip()

    reason_text = " ".join(
        str(item.get(key, "") or "")
        for key in ("涨停原因", "涨停统计", "原因", "reason", "limit_reason", "涨停解析", "涨停分析", "上榜原因")
    )
    inferred = _infer_sector_from_reason(reason_text)
    if _is_valid_sector_label(inferred):
        return inferred

    return "未知"


def _build_sector_bucket(records, *, include_zt_type=False, code_to_sector=None):
    buckets = {}
    for item in records or []:
        sector = _pick_sector_label(item, code_to_sector=code_to_sector)
        if sector not in buckets:
            buckets[sector] = []
        row = {
            "code": item.get("代码", ""),
            "name": item.get("名称", ""),
        }
        if include_zt_type:
            row["zt_type"] = item.get("涨停统计", "")
        buckets[sector].append(row)
    return buckets


class _RecordFrame:
    def __init__(self, rows):
        self._rows = list(rows or [])

    @property
    def empty(self):
        return not self._rows

    def to_dict(self, orient):
        if orient != "records":
            return {}
        return list(self._rows)

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, row

    def __len__(self):
        return len(self._rows)


def _normalize_market_stats_value(value):
    try:
        if isinstance(value, str):
            raw = value.replace("%", "").strip()
            if raw == "":
                return 0
            value = float(raw)
        if value != value:
            return 0
        return int(value)
    except Exception:
        return 0


def _hot_rank_sample_count(rows):
    return len(rows or [])


def _hot_rank_sample_complete(rows, target=HOT_RANK_SAMPLE_TARGET):
    return _hot_rank_sample_count(rows) >= int(target or HOT_RANK_SAMPLE_TARGET)


def _store_hot_rank_results(results, rows, *, target=HOT_RANK_SAMPLE_TARGET):
    rows = list(rows or [])
    results["hot_rank_top30"] = rows
    results["hot_rank_top50"] = rows
    results["hot_rank_sample_size"] = len(rows)
    results["hot_rank_sample_target"] = int(target or HOT_RANK_SAMPLE_TARGET)


def _store_best_hot_rank_results(results, rows, *, target=HOT_RANK_SAMPLE_TARGET):
    rows = list(rows or [])
    if len(rows) >= len(results.get("hot_rank_top30") or []):
        _store_hot_rank_results(results, rows, target=target)


def _market_breadth_counts_complete(market_stats):
    market_stats = market_stats or {}
    return (
        _normalize_market_stats_value(market_stats.get("up_count")) > 0
        and _normalize_market_stats_value(market_stats.get("down_count")) > 0
    )


def _market_stats_with_fallback_counts(primary, fallback, fallback_stats):
    market_stats = dict(primary or {})
    if not _market_breadth_counts_complete(fallback):
        return market_stats
    fallback = dict(fallback or {})
    if not _market_breadth_counts_complete(market_stats):
        market_stats.update(fallback)
    market_stats["zt_count"] = fallback_stats["zt_count"]
    market_stats["dt_count"] = fallback_stats["dt_count"]
    return market_stats


def _market_stats_fallback_source(market_stats, default_provider):
    if not isinstance(market_stats, dict):
        return default_provider
    return market_stats.get("source") or market_stats.get("data_source") or default_provider


def _load_market_breadth_from_fact_db(target_date, request_registry=None):
    service_cls = (request_registry or {}).get("database_service_cls")
    if service_cls is None:
        return {}
    try:
        factory = getattr(service_cls, "fact_store_from_environment", None)
        service = factory() if callable(factory) else service_cls.from_environment()
        row = service.query_market_breadth_counts(target_date)
    except Exception:
        return {}
    return dict(row or {}) if isinstance(row, dict) else {}


def _market_activity_row_value(row, key, position, default=None):
    missing = object()
    if hasattr(row, "get"):
        value = row.get(key, missing)
        if value is not missing:
            return value
    try:
        return row[position]
    except (KeyError, IndexError, TypeError):
        return default


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_sector_fund_flow_rows(rows):
    normalized = []
    for row in rows or []:
        item = dict(row or {})
        name = item.get("name") or item.get("sector") or item.get("sector_name") or item.get("industry")
        if name not in (None, ""):
            item["name"] = str(name).strip()
        if item.get("zljlr") in (None, ""):
            net_amount = item.get("net_amount", item.get("net_inflow_yi", item.get("net_inflow")))
            if net_amount not in (None, ""):
                item["zljlr"] = round(_safe_float(net_amount), 2)
        if item.get("zdf") in (None, ""):
            change_pct = item.get("change_pct", item.get("pct_change"))
            if change_pct not in (None, ""):
                item["zdf"] = round(_safe_float(change_pct), 2)
        turnover_yi = item.get("turnover_yi")
        if turnover_yi in (None, "") and item.get("cje") not in (None, ""):
            turnover_yi = _safe_float(item.get("cje")) / 1e4
        if turnover_yi not in (None, ""):
            item["turnover_yi"] = round(_safe_float(turnover_yi), 2)
        normalized.append(item)
    return normalized


def _derive_sector_change_rank_from_fund_flow(sector_fund_flow, *, rank_type="up", limit=10):
    seen = {}
    for row in list((sector_fund_flow or {}).get("inflow") or []) + list((sector_fund_flow or {}).get("outflow") or []):
        item = dict(row or {})
        name = str(item.get("name") or item.get("sector_name") or item.get("industry") or "").strip()
        if not name:
            continue
        change_pct = _safe_float(item.get("change_pct", item.get("zdf", item.get("pct_change", 0.0))))
        existing = seen.get(name)
        if existing is None or abs(change_pct) > abs(_safe_float(existing.get("change_pct"))):
            seen[name] = {
                "name": name,
                "change_pct": change_pct,
                "zdf": change_pct,
                "data_source": f"{item.get('data_source') or (sector_fund_flow or {}).get('provider') or 'sector_fund_flow'}.derived_change",
            }
    rows = list(seen.values())
    rows.sort(key=lambda item: (_safe_float(item.get("change_pct")), item.get("name") or ""), reverse=(rank_type != "down"))
    rows = rows[: max(int(limit or 10), 1)]
    for rank, item in enumerate(rows, start=1):
        item["rank"] = rank
    return rows


def _is_historical_target_date(target_date, current_dates=None):
    if not current_dates:
        return False
    current = {str(date or "").strip() for date in current_dates if str(date or "").strip()}
    return str(target_date or "").strip() not in current


def _historical_sector_flow_payload(target_date, *, provider="tushare.moneyflow_ind_ths"):
    return {
        "inflow": [],
        "outflow": [],
        "is_historical": True,
        "target_date": target_date,
        "provider": provider,
    }


_PROVIDER_ALIASES = {
    "tencent.fundflow.getHyRank": "tencent.sector_change_rank",
    "eastmoney.push2.clist": "eastmoney.turnover_rank",
}


def _provider_from_rows(rows, default_provider):
    sources = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        source = row.get("data_source")
        if source:
            sources.append(_PROVIDER_ALIASES.get(source, source))
    unique_sources = sorted(set(sources))
    if not unique_sources:
        return default_provider
    if len(unique_sources) == 1:
        return unique_sources[0]
    return ",".join(unique_sources)


def _build_integrated_hot_list_from_primary_hot_rank(hot_stocks):
    integrated = []
    tag_distribution = {}
    status_distribution = {}
    high_lianban_stocks = []

    for index, stock in enumerate(hot_stocks or [], start=1):
        if not isinstance(stock, dict):
            continue
        code = stock.get("code") or stock.get("代码") or stock.get("ts_code") or ""
        name = stock.get("name") or stock.get("名称") or stock.get("股票简称") or ""
        if not code and not name:
            continue

        concepts = stock.get("concepts") or []
        if isinstance(concepts, str):
            concepts = [concepts] if concepts else []
        tags = [str(item).strip() for item in concepts if str(item).strip()]
        sector = stock.get("sector") or stock.get("所属行业") or ""
        if sector and sector not in tags:
            tags.append(str(sector))
        for tag in tags:
            tag_distribution[tag] = tag_distribution.get(tag, 0) + 1

        integrated.append(
            {
                "rank": stock.get("rank") or index,
                "code": code,
                "name": name,
                "price": stock.get("price"),
                "change_pct": stock.get("change_pct"),
                "rate": stock.get("rate"),
                "sector": sector,
                "tags": tags,
                "status_tags": [],
                "data_source": stock.get("data_source") or "tushare.ths_hot",
                "source": "primary_hot_rank",
            }
        )

    return integrated, tag_distribution, status_distribution, high_lianban_stocks


def _normalize_integrated_hot_list_payload(payload):
    if isinstance(payload, tuple) and len(payload) == 4:
        return payload
    if isinstance(payload, list):
        return payload, {}, {}, []
    if isinstance(payload, dict):
        integrated = payload.get("integrated_hot_list") or payload.get("hot_list") or payload.get("items") or []
        tag_distribution = payload.get("tag_distribution") or {}
        status_distribution = payload.get("status_distribution") or {}
        high_lianban_stocks = payload.get("high_lianban_stocks") or []
        return integrated, tag_distribution, status_distribution, high_lianban_stocks
    return [], {}, {}, []


def _build_code_to_sector_map(existing_results=None):
    existing_results = existing_results or {}
    code_to_sector = {}

    for stock in existing_results.get("zt_pool", []) or []:
        code = stock.get("代码", "")
        sector = stock.get("所属行业", "")
        if code and _is_valid_sector_label(sector):
            code_to_sector[code] = sector

    for key in ("lhb_net_buy_top10", "lhb_net_sell_top10"):
        for stock in existing_results.get(key, []) or []:
            code = str(stock.get("code", "") or "").replace(".SZ", "").replace(".SS", "")
            sector = stock.get("sector", "")
            if code and _is_valid_sector_label(sector):
                code_to_sector[code] = sector

    return code_to_sector


def _has_limit_pool_snapshot_payload(snapshot):
    snapshot = snapshot or {}
    return bool(snapshot.get("zt_pool") or snapshot.get("dt_pool") or snapshot.get("market_stats"))


def _has_limit_pool_rows(snapshot):
    snapshot = snapshot or {}
    if snapshot.get("source_status") == "partial":
        return False
    return bool(snapshot.get("zt_pool") or snapshot.get("dt_pool"))


def _apply_limit_pool_snapshot(results, data_status, artifacts, snapshot, emit):
    snapshot = snapshot or {}
    zt_pool_records = list(snapshot.get("zt_pool") or [])
    dt_pool_records = list(snapshot.get("dt_pool") or [])
    market_stats = dict(snapshot.get("market_stats") or {})

    results["zt_pool"] = zt_pool_records
    results["limit_up_codes"] = set(snapshot.get("limit_up_codes") or [row.get("代码") for row in zt_pool_records if row.get("代码")])
    artifacts["limit_up_df"] = snapshot.get("limit_up_df") or _RecordFrame(zt_pool_records)
    artifacts["limit_up_provider"] = snapshot.get("provider", "tushare.limit_list_ths")
    data_status["涨停池"] = bool(zt_pool_records)
    if zt_pool_records:
        emit(f"   ✅ 涨停池: {len(zt_pool_records)} 只")
        results["zt_pool_by_sector"] = _build_sector_bucket(zt_pool_records, include_zt_type=True)
        data_status["涨停股板块分布"] = True
        emit(f"   ✅ 涨停股板块分布: {len(results['zt_pool_by_sector'])} 个板块")
    else:
        results["zt_pool_by_sector"] = {}
        data_status["涨停股板块分布"] = False
        emit("   ❌ 涨停池为空")

    results["dt_pool"] = dt_pool_records
    results["limit_down_codes"] = set(snapshot.get("limit_down_codes") or [row.get("代码") for row in dt_pool_records if row.get("代码")])
    artifacts["limit_down_df"] = snapshot.get("limit_down_df") or _RecordFrame(dt_pool_records)
    data_status["跌停池"] = bool(dt_pool_records)
    if dt_pool_records:
        emit(f"   ✅ 跌停池: {len(dt_pool_records)} 只")
        results["dt_pool_by_sector"] = _build_sector_bucket(dt_pool_records)
        data_status["跌停股板块分布"] = True
        emit(f"   ✅ 跌停股板块分布: {len(results['dt_pool_by_sector'])} 个板块")
    else:
        results["dt_pool_by_sector"] = {}
        data_status["跌停股板块分布"] = False
        emit("   ❌ 跌停池为空")

    results["market_stats"] = market_stats
    data_status["大盘涨跌统计"] = _market_breadth_counts_complete(market_stats)
    if data_status["大盘涨跌统计"]:
        emit(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
    else:
        emit("   ⚠️ 大盘涨跌统计数据不完整")


def collect_market_activity_pool_request_bundle(
    target_date,
    *,
    get_limit_up_pool,
    get_limit_down_pool,
    fetch_market_activity_df,
    request_registry=None,
    current_date=None,
    allow_realtime_market_activity=None,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {"涨停跌停数据获取": False}
    module_logs = []
    artifacts = {"limit_up_df": None, "limit_down_df": None}

    emit("  4️⃣ 获取涨停跌停数据（Tushare 优先）...")
    try:
        snapshot = {}
        snapshot_market_stats = {}
        limit_pool_fetcher = (request_registry or {}).get("limit_pool_snapshot")
        if callable(limit_pool_fetcher):
            snapshot = limit_pool_fetcher(target_date=target_date) or {}
            snapshot_market_stats = dict(snapshot.get("market_stats") or {})
            if _has_limit_pool_rows(snapshot):
                _apply_limit_pool_snapshot(results, data_status, artifacts, snapshot, emit)
                step_status["涨停跌停数据获取"] = True
                elapsed, _ = timer.record("涨停跌停数据获取", 4)
                emit(f"   ✅ 涨停跌停数据完成 [⏱ {elapsed:.2f}s]")
                _append_log(
                    module_logs,
                    "request.pool_snapshot",
                    "success" if data_status.get("涨停池") or data_status.get("跌停池") else "degraded",
                    "已获取涨停跌停池与市场活跃度快照",
                    provider=snapshot.get("provider", "tushare.limit_list_ths"),
                    target_keys=["zt_pool", "dt_pool", "zt_pool_by_sector", "dt_pool_by_sector", "market_stats"],
                    zt_count=len(results.get("zt_pool", [])),
                    dt_count=len(results.get("dt_pool", [])),
                    fallback_used=bool(snapshot.get("fallback_used")),
                )
                return {
                    "results": results,
                    "data_status": data_status,
                    "step_status": step_status,
                    "module_logs": module_logs,
                    "artifacts": artifacts,
                }

            _append_log(
                module_logs,
                "request.pool_snapshot",
                "degraded",
                "Tushare-first 涨跌停池返回空",
                provider=snapshot.get("provider", "tushare.limit_list_ths"),
                target_keys=["zt_pool", "dt_pool", "zt_pool_by_sector", "dt_pool_by_sector", "market_stats"],
                fallback_used=bool(snapshot.get("fallback_used")),
                error=snapshot.get("source_error", "empty_result"),
            )

        date_str = str(target_date or "").replace("-", "")

        limit_up_df, limit_up_codes = get_limit_up_pool(date_str)
        artifacts["limit_up_df"] = limit_up_df
        artifacts["limit_up_provider"] = "akshare.limit_up_pool"
        if not limit_up_df.empty:
            zt_pool_records = limit_up_df.to_dict("records")
            results["zt_pool"] = zt_pool_records
            results["limit_up_codes"] = limit_up_codes
            data_status["涨停池"] = True
            emit(f"   ✅ 涨停池: {len(limit_up_df)} 只")
            results["zt_pool_by_sector"] = _build_sector_bucket(zt_pool_records, include_zt_type=True)
            data_status["涨停股板块分布"] = True
            emit(f"   ✅ 涨停股板块分布: {len(results['zt_pool_by_sector'])} 个板块")
        else:
            results["zt_pool"] = []
            results["limit_up_codes"] = set()
            data_status["涨停池"] = False
            emit("   ❌ 涨停池为空")

        limit_down_df, limit_down_codes = get_limit_down_pool(date_str)
        artifacts["limit_down_df"] = limit_down_df
        if not limit_down_df.empty:
            dt_pool_records = limit_down_df.to_dict("records")
            results["dt_pool"] = dt_pool_records
            results["limit_down_codes"] = limit_down_codes
            data_status["跌停池"] = True
            emit(f"   ✅ 跌停池: {len(limit_down_df)} 只")
            results["dt_pool_by_sector"] = _build_sector_bucket(dt_pool_records)
            data_status["跌停股板块分布"] = True
            emit(f"   ✅ 跌停股板块分布: {len(results['dt_pool_by_sector'])} 个板块")
        else:
            results["dt_pool"] = []
            results["limit_down_codes"] = set()
            data_status["跌停池"] = False
            emit("   ❌ 跌停池为空")

        fallback_stats = {
            "up_count": 0,
            "down_count": 0,
            "zt_count": len(results.get("zt_pool", []) or []),
            "dt_count": len(results.get("dt_pool", []) or []),
        }
        realtime_market_activity_allowed = True
        if current_date is not None or allow_realtime_market_activity is not None:
            realtime_market_activity_allowed = _realtime_quote_fallback_allowed(
                target_date,
                current_date=current_date,
                allow_realtime_quote_fallback=allow_realtime_market_activity,
            )
        fact_db_market_stats = _load_market_breadth_from_fact_db(target_date, request_registry=request_registry)
        if not realtime_market_activity_allowed and _market_breadth_counts_complete(fact_db_market_stats):
            market_stats = dict(fact_db_market_stats)
            market_stats["zt_count"] = fallback_stats["zt_count"]
            market_stats["dt_count"] = fallback_stats["dt_count"]
            results["market_stats"] = market_stats
            data_status["大盘涨跌统计"] = True
            emit(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
            _append_log(
                module_logs,
                "request.market_stats",
                "success",
                "历史日期使用PostgreSQL行情快照回补大盘涨跌统计",
                provider=market_stats.get("source") or market_stats.get("data_source") or "storage.stock_daily_quotes_recent",
                target_keys=["market_stats"],
                up_count=market_stats.get("up_count", 0),
                down_count=market_stats.get("down_count", 0),
                zt_count=market_stats.get("zt_count", fallback_stats["zt_count"]),
                dt_count=market_stats.get("dt_count", fallback_stats["dt_count"]),
                realtime_market_activity_allowed=False,
            )
        elif not realtime_market_activity_allowed and _market_breadth_counts_complete(snapshot_market_stats):
            market_stats = dict(snapshot_market_stats)
            market_stats["zt_count"] = fallback_stats["zt_count"]
            market_stats["dt_count"] = fallback_stats["dt_count"]
            results["market_stats"] = market_stats
            data_status["大盘涨跌统计"] = True
            emit(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
            _append_log(
                module_logs,
                "request.market_stats",
                "success",
                "历史日期使用涨跌停池快照回补大盘涨跌统计",
                provider=snapshot.get("provider", "tushare.limit_list_ths"),
                target_keys=["market_stats"],
                up_count=market_stats.get("up_count", 0),
                down_count=market_stats.get("down_count", 0),
                zt_count=market_stats.get("zt_count", fallback_stats["zt_count"]),
                dt_count=market_stats.get("dt_count", fallback_stats["dt_count"]),
                realtime_market_activity_allowed=False,
            )
        elif not realtime_market_activity_allowed:
            results["market_stats"] = fallback_stats
            data_status["大盘涨跌统计"] = False
            emit("   ⚠️ 历史日期不使用实时大盘涨跌统计，保留涨跌家数缺口")
            _append_log(
                module_logs,
                "request.market_stats",
                "degraded",
                "历史日期缺少可验证的大盘涨跌统计",
                provider="storage.stock_daily_quotes_recent",
                target_keys=["market_stats"],
                up_count=0,
                down_count=0,
                zt_count=fallback_stats["zt_count"],
                dt_count=fallback_stats["dt_count"],
                realtime_market_activity_allowed=False,
            )
        else:
            try:
                market_activity_df = fetch_market_activity_df()
                emit(f"   📊 大盘涨跌统计原始数据: {len(market_activity_df)} 行")
                if not market_activity_df.empty:
                    market_stats = {}
                    for _, row in market_activity_df.iterrows():
                        item = _market_activity_row_value(row, "item", 0, "")
                        value = _market_activity_row_value(row, "value", 1, 0)
                        numeric_value = _normalize_market_stats_value(value)
                        if item == "上涨":
                            market_stats["up_count"] = numeric_value
                        elif item == "下跌":
                            market_stats["down_count"] = numeric_value
                        elif item == "涨停":
                            market_stats["zt_count"] = numeric_value
                        elif item == "跌停":
                            market_stats["dt_count"] = numeric_value
                    fallback_source = ""
                    fallback_message = ""
                    if not _market_breadth_counts_complete(market_stats):
                        if _market_breadth_counts_complete(fact_db_market_stats):
                            fallback_source = _market_stats_fallback_source(
                                fact_db_market_stats,
                                "storage.stock_daily_quotes_recent",
                            )
                            fallback_message = "大盘涨跌统计接口返回不完整，使用PostgreSQL行情快照回补"
                            market_stats = _market_stats_with_fallback_counts(
                                market_stats,
                                fact_db_market_stats,
                                fallback_stats,
                            )
                        elif _market_breadth_counts_complete(snapshot_market_stats):
                            fallback_source = _market_stats_fallback_source(
                                snapshot_market_stats,
                                snapshot.get("provider", "akshare.stock_market_activity_legu"),
                            )
                            fallback_message = "大盘涨跌统计接口返回不完整，使用涨跌停池快照回补"
                            market_stats = _market_stats_with_fallback_counts(
                                market_stats,
                                snapshot_market_stats,
                                fallback_stats,
                            )
                    results["market_stats"] = market_stats
                    data_status["大盘涨跌统计"] = _market_breadth_counts_complete(market_stats)
                    if data_status["大盘涨跌统计"]:
                        emit(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
                        if fallback_message:
                            _append_log(
                                module_logs,
                                "request.market_stats",
                                "success",
                                fallback_message,
                                provider=fallback_source,
                                target_keys=["market_stats"],
                                up_count=market_stats.get("up_count", 0),
                                down_count=market_stats.get("down_count", 0),
                                zt_count=market_stats.get("zt_count", fallback_stats["zt_count"]),
                                dt_count=market_stats.get("dt_count", fallback_stats["dt_count"]),
                            )
                    else:
                        emit("   ⚠️ 大盘涨跌统计缺少上涨/下跌家数")
                else:
                    results["market_stats"] = {}
                    data_status["大盘涨跌统计"] = False
                    emit("   ⚠️ 大盘涨跌统计数据为空")
            except Exception as stats_error:
                stats_provider = "akshare.stock_market_activity_legu"
                stats_message = "大盘涨跌统计接口异常，使用涨跌停池数量补足"
                if _market_breadth_counts_complete(fact_db_market_stats):
                    market_stats = dict(fact_db_market_stats)
                    market_stats["zt_count"] = fallback_stats["zt_count"]
                    market_stats["dt_count"] = fallback_stats["dt_count"]
                    results["market_stats"] = market_stats
                    data_status["大盘涨跌统计"] = True
                    stats_provider = market_stats.get("source") or market_stats.get("data_source") or "storage.stock_daily_quotes_recent"
                    stats_message = "大盘涨跌统计接口异常，使用PostgreSQL行情快照回补"
                    emit(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
                elif _market_breadth_counts_complete(snapshot_market_stats):
                    market_stats = dict(snapshot_market_stats)
                    market_stats["zt_count"] = fallback_stats["zt_count"]
                    market_stats["dt_count"] = fallback_stats["dt_count"]
                    results["market_stats"] = market_stats
                    data_status["大盘涨跌统计"] = True
                    stats_provider = snapshot.get("provider", "akshare.stock_market_activity_legu")
                    stats_message = "大盘涨跌统计接口异常，使用涨跌停池快照回补"
                    emit(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
                else:
                    results["market_stats"] = fallback_stats
                    data_status["大盘涨跌统计"] = False
                    emit(f"   ⚠️ 大盘涨跌统计使用涨跌停池数量补足: 涨停{fallback_stats['zt_count']}只 vs 跌停{fallback_stats['dt_count']}只")
                _append_log(
                    module_logs,
                    "request.market_stats",
                    "success" if data_status.get("大盘涨跌统计") else "degraded",
                    stats_message,
                    provider=stats_provider,
                    target_keys=["market_stats"],
                    up_count=(results.get("market_stats") or {}).get("up_count", 0),
                    down_count=(results.get("market_stats") or {}).get("down_count", 0),
                    zt_count=(results.get("market_stats") or {}).get("zt_count", fallback_stats["zt_count"]),
                    dt_count=(results.get("market_stats") or {}).get("dt_count", fallback_stats["dt_count"]),
                    error=str(stats_error),
                )

        step_status["涨停跌停数据获取"] = True
        elapsed, _ = timer.record("涨停跌停数据获取", 4)
        emit(f"   ✅ 涨停跌停数据完成 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.pool_snapshot",
            "success",
            "已获取涨停跌停池与市场活跃度快照",
            provider=(
                "akshare.limit_up_down+"
                + (
                    ((results.get("market_stats") or {}).get("source") or (results.get("market_stats") or {}).get("data_source") or "storage.stock_daily_quotes_recent")
                    if not realtime_market_activity_allowed
                    else "akshare.stock_market_activity_legu"
                )
            ),
            target_keys=["zt_pool", "dt_pool", "zt_pool_by_sector", "dt_pool_by_sector", "market_stats"],
            zt_count=len(results.get("zt_pool", [])),
            dt_count=len(results.get("dt_pool", [])),
        )
    except Exception as error:
        elapsed, _ = timer.record("涨停跌停数据获取(失败)", 4)
        emit(f"   ❌ 涨停跌停数据失败: {error} [⏱ {elapsed:.2f}s]")
        results["zt_pool"] = []
        results["dt_pool"] = []
        results["limit_up_codes"] = set()
        results["limit_down_codes"] = set()
        results["market_stats"] = {}
        data_status["涨停池"] = False
        data_status["跌停池"] = False
        data_status["大盘涨跌统计"] = False
        _append_log(
            module_logs,
            "request.pool_snapshot",
            "error",
            "涨停跌停池请求失败",
            provider="akshare.limit_up_down+akshare.stock_market_activity_legu",
            target_keys=["zt_pool", "dt_pool", "zt_pool_by_sector", "dt_pool_by_sector", "market_stats"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
        "artifacts": artifacts,
    }


def collect_market_activity_hot_rank_request_bundle(
    target_date,
    *,
    existing_results,
    fetch_ths_hot_stock,
    get_integrated_hot_list,
    tencent,
    request_registry=None,
    xueqiu_hot_rank_fetcher=None,
    xueqiu_argument_fetcher=None,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {
        HOT_RANK_STEP_LABEL: False,
        "整合热榜获取": False,
    }
    module_logs = []

    emit(f"  5️⃣ 获取{target_date}{HOT_RANK_STATUS_LABEL}（Tushare 优先）...")
    primary_error = ""
    hot_stocks = []
    registry_attempted = False
    hot_rank_fetcher = (request_registry or {}).get("stock_hot_rank")
    if callable(hot_rank_fetcher):
        registry_attempted = True
        try:
            hot_stocks = hot_rank_fetcher(target_date=target_date, limit=HOT_RANK_SAMPLE_TARGET)
        except Exception as error:
            primary_error = str(error)
            emit(f"   ⚠️ Tushare 热榜失败: {error}，尝试腾讯备用...")
            _append_log(
                module_logs,
                "request.hot_rank.primary",
                "error",
                "Tushare 热榜请求失败",
                provider="tushare.ths_hot",
                target_keys=["hot_rank_top30"],
                error=str(error),
            )
        else:
            if not hot_stocks:
                primary_error = "empty_result"
                emit("   ⚠️ Tushare 热榜返回空，尝试腾讯备用...")
                _append_log(
                    module_logs,
                    "request.hot_rank.primary",
                    "degraded",
                    "Tushare 热榜返回空",
                    provider="tushare.ths_hot",
                    target_keys=["hot_rank_top30"],
                    error="empty_result",
                )

    if hot_stocks:
        code_to_sector = _build_code_to_sector_map(existing_results)
        results["code_to_sector"] = code_to_sector
        for stock in hot_stocks:
            if stock.get("code") in code_to_sector:
                stock["sector"] = code_to_sector[stock.get("code")]
        _store_hot_rank_results(results, hot_stocks)
        sample_complete = _hot_rank_sample_complete(hot_stocks)
        data_status[HOT_RANK_STATUS_LABEL] = sample_complete
        step_status[HOT_RANK_STEP_LABEL] = sample_complete
        elapsed, _ = timer.record(HOT_RANK_STEP_LABEL, 5)
        provider = _provider_from_rows(hot_stocks, "tushare.ths_hot")
        if sample_complete:
            emit(f"   ✅ 热榜成功: {len(hot_stocks)} 只 [⏱ {elapsed:.2f}s]")
        else:
            emit(f"   ⚠️ 热榜样本不足: {len(hot_stocks)}/{HOT_RANK_SAMPLE_TARGET} 只 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.hot_rank.primary",
            "success" if sample_complete else "degraded",
            "热榜成功" if sample_complete else "热榜样本不足",
            provider=provider,
            target_keys=["hot_rank_top30"],
            hot_rank_count=len(hot_stocks),
            required_count=HOT_RANK_SAMPLE_TARGET,
        )

    if not _hot_rank_sample_complete(results.get("hot_rank_top30")):
        try:
            hot_stocks = fetch_ths_hot_stock(num=HOT_RANK_SAMPLE_TARGET)
        except Exception as error:
            primary_error = str(error)
            emit(f"   ⚠️ 同花顺热榜失败: {error}，尝试腾讯备用...")
            _append_log(
                module_logs,
                "request.hot_rank.primary",
                "error",
                "同花顺热榜请求失败",
                provider="ths_hot_stock",
                target_keys=["hot_rank_top30"],
                error=str(error),
            )
        else:
            if not hot_stocks:
                primary_error = "empty_result"
                emit("   ⚠️ 同花顺返回空，尝试腾讯备用...")
                _append_log(
                    module_logs,
                    "request.hot_rank.primary",
                    "degraded",
                    "同花顺热榜返回空",
                    provider="ths_hot_stock",
                    target_keys=["hot_rank_top30"],
                    error="empty_result",
                )

        if hot_stocks:
            code_to_sector = _build_code_to_sector_map(existing_results)
            results["code_to_sector"] = code_to_sector
            for stock in hot_stocks:
                if stock.get("code") in code_to_sector:
                    stock["sector"] = code_to_sector[stock.get("code")]
            _store_best_hot_rank_results(results, hot_stocks)
            sample_complete = _hot_rank_sample_complete(hot_stocks)
            data_status[HOT_RANK_STATUS_LABEL] = sample_complete
            step_status[HOT_RANK_STEP_LABEL] = sample_complete
            elapsed, _ = timer.record(HOT_RANK_STEP_LABEL, 5)
            if sample_complete:
                emit(f"   ✅ 同花顺热榜成功: {len(hot_stocks)} 只 [⏱ {elapsed:.2f}s]")
            else:
                emit(f"   ⚠️ 同花顺热榜样本不足: {len(hot_stocks)}/{HOT_RANK_SAMPLE_TARGET} 只 [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                "request.hot_rank.primary",
                "success" if sample_complete else "degraded",
                "同花顺热榜成功" if sample_complete else "同花顺热榜样本不足",
                provider="ths_hot_stock",
                target_keys=["hot_rank_top30"],
                hot_rank_count=len(hot_stocks),
                required_count=HOT_RANK_SAMPLE_TARGET,
            )

    if not _hot_rank_sample_complete(results.get("hot_rank_top30")):
        try:
            hot_stocks = tencent.get_hot_stocks(num=HOT_RANK_SAMPLE_TARGET)
            if hot_stocks:
                _store_best_hot_rank_results(results, hot_stocks)
                sample_complete = _hot_rank_sample_complete(hot_stocks)
                data_status[HOT_RANK_STATUS_LABEL] = sample_complete
                step_status[HOT_RANK_STEP_LABEL] = sample_complete
                elapsed, _ = timer.record(HOT_RANK_STEP_LABEL, 5)
                if sample_complete:
                    emit(f"   ✅ 腾讯热榜成功: {len(hot_stocks)} 只 [⏱ {elapsed:.2f}s]")
                else:
                    emit(f"   ⚠️ 腾讯热榜样本不足: {len(hot_stocks)}/{HOT_RANK_SAMPLE_TARGET} 只 [⏱ {elapsed:.2f}s]")
                _append_log(
                    module_logs,
                    "request.hot_rank.fallback",
                    "success" if sample_complete else "degraded",
                    "腾讯热榜兜底成功" if sample_complete else "腾讯热榜兜底样本不足",
                    provider="tencent.get_hot_stocks",
                    target_keys=["hot_rank_top30"],
                    hot_rank_count=len(hot_stocks),
                    required_count=HOT_RANK_SAMPLE_TARGET,
                    fallback_used=True,
                    upstream_error=primary_error,
                )
            else:
                results.setdefault("hot_rank_sample_target", HOT_RANK_SAMPLE_TARGET)
                results.setdefault("hot_rank_sample_size", len(results.get("hot_rank_top30") or []))
                data_status[HOT_RANK_STATUS_LABEL] = False
                emit("   ❌ 所有热榜数据源失败")
                _append_log(
                    module_logs,
                    "request.hot_rank.fallback",
                    "degraded",
                    "腾讯热榜兜底返回空",
                    provider="tencent.get_hot_stocks",
                    target_keys=["hot_rank_top30"],
                    fallback_used=True,
                    upstream_error=primary_error,
                    required_count=HOT_RANK_SAMPLE_TARGET,
                )
        except Exception as error:
            results.setdefault("hot_rank_sample_target", HOT_RANK_SAMPLE_TARGET)
            results.setdefault("hot_rank_sample_size", len(results.get("hot_rank_top30") or []))
            data_status[HOT_RANK_STATUS_LABEL] = False
            emit(f"   ❌ 腾讯热榜兜底失败: {error}")
            _append_log(
                module_logs,
                "request.hot_rank.fallback",
                "error",
                "腾讯热榜兜底失败",
                provider="tencent.get_hot_stocks",
                target_keys=["hot_rank_top30"],
                error=str(error),
                fallback_used=True,
                upstream_error=primary_error,
                required_count=HOT_RANK_SAMPLE_TARGET,
            )

    _collect_xueqiu_hot_rank_factors(
        results,
        data_status,
        step_status,
        module_logs,
        xueqiu_hot_rank_fetcher=xueqiu_hot_rank_fetcher,
        xueqiu_argument_fetcher=xueqiu_argument_fetcher,
        emit=emit,
    )

    emit("  5️⃣.5️⃣ 构建整合热榜数据（Tushare 热榜优先）...")
    try:
        hot_rank_provider = _provider_from_rows(results.get("hot_rank_top30", []), "")
        integrated_hot_list, tag_distribution, status_distribution, high_lianban_stocks = _normalize_integrated_hot_list_payload(
            get_integrated_hot_list(limit=100)
        )
        integrated_provider = "hot_list_integrated.get_integrated_hot_list"
        fallback_used = False
        sample_target = 100
        if not integrated_hot_list and results.get("hot_rank_top30"):
            integrated_hot_list, tag_distribution, status_distribution, high_lianban_stocks = (
                _build_integrated_hot_list_from_primary_hot_rank(results.get("hot_rank_top30", []))
            )
            integrated_provider = (
                "tushare.ths_hot.primary_hot_rank" if hot_rank_provider.startswith("tushare.") else "primary_hot_rank.fallback"
            )
            fallback_used = True
            sample_target = int(results.get("hot_rank_sample_target") or HOT_RANK_SAMPLE_TARGET)
        if integrated_hot_list:
            results["integrated_hot_list"] = integrated_hot_list
            results["integrated_hot_list_sample_size"] = len(integrated_hot_list)
            results["integrated_hot_list_sample_target"] = sample_target
            results["tag_distribution"] = tag_distribution
            results["status_distribution"] = status_distribution
            results["high_lianban_stocks"] = high_lianban_stocks
            data_status["整合热榜"] = True
            step_status["整合热榜获取"] = True
            emit(f"   ✅ 整合热榜成功: {len(integrated_hot_list)} 只")
            emit(f"   ✅ 板块标签分布: {len(tag_distribution)} 个板块，{len(status_distribution)} 个状态标签")
            if high_lianban_stocks:
                emit(f"   ✅ 高位连板股: {len(high_lianban_stocks)} 只（非ST股，10天以上）")
        else:
            results["integrated_hot_list"] = []
            results["tag_distribution"] = {}
            results["status_distribution"] = {}
            data_status["整合热榜"] = False
            emit("   ⚠️ 整合热榜返回空")
        _append_log(
            module_logs,
            "request.integrated_hot_rank",
            "success" if data_status.get("整合热榜") else "degraded",
            "已处理整合热榜请求",
            integrated_count=len(results.get("integrated_hot_list", [])),
            required_count=results.get("integrated_hot_list_sample_target"),
            provider=integrated_provider,
            target_keys=["integrated_hot_list", "tag_distribution", "status_distribution", "high_lianban_stocks"],
            fallback_used=fallback_used,
        )
    except Exception as error:
        results["integrated_hot_list"] = []
        results["tag_distribution"] = {}
        results["status_distribution"] = {}
        data_status["整合热榜"] = False
        emit(f"   ⚠️ 整合热榜失败: {error}")
        _append_log(
            module_logs,
            "request.integrated_hot_rank",
            "error",
            "整合热榜请求失败",
            provider="hot_list_integrated.get_integrated_hot_list",
            target_keys=["integrated_hot_list", "tag_distribution", "status_distribution", "high_lianban_stocks"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }


def _collect_xueqiu_hot_rank_factors(
    results,
    data_status,
    step_status,
    module_logs,
    *,
    xueqiu_hot_rank_fetcher=None,
    xueqiu_argument_fetcher=None,
    emit,
):
    if not callable(xueqiu_hot_rank_fetcher) or not callable(xueqiu_argument_fetcher):
        return

    emit("  5️⃣.1️⃣ 获取雪球A股24小时热榜和AI解释...")
    hot_rank_result = xueqiu_hot_rank_fetcher() or {}
    hot_rank_rows = list(hot_rank_result.get("rows") or [])
    hot_rank_ok = bool(hot_rank_rows) and hot_rank_result.get("can_continue_report") is not False
    results["xueqiu_hot_rank_top100"] = hot_rank_rows
    data_status["雪球A股24小时热榜"] = hot_rank_ok
    step_status["雪球A股24小时热榜获取"] = hot_rank_ok
    if hot_rank_ok:
        emit(f"   ✅ 雪球A股24小时热榜成功: {len(hot_rank_rows)} 只")
    else:
        emit(f"   ❌ 雪球A股24小时热榜失败: {hot_rank_result.get('diagnostic_note', '')}")
    _append_log(
        module_logs,
        "request.xueqiu_hot_rank",
        "success" if hot_rank_ok else "error",
        "已处理雪球A股24小时热榜请求",
        provider=hot_rank_result.get("provider", "xueqiu.hot_stock.type22"),
        target_keys=["xueqiu_hot_rank_top100"],
        row_count=len(hot_rank_rows),
        error=hot_rank_result.get("diagnostic_note", ""),
    )

    symbols = _xueqiu_argument_symbols(hot_rank_rows, results.get("hot_rank_top30", []))
    argument_result = xueqiu_argument_fetcher(symbols) if symbols else {
        "provider": "xueqiu.hot_stock.argument",
        "status": "error",
        "rows": [],
        "can_continue_report": False,
        "diagnostic_note": "雪球接口返回空，关键数据不完整，停止生成",
    }
    argument_rows = list((argument_result or {}).get("rows") or [])
    argument_ok = bool(argument_rows) and (argument_result or {}).get("can_continue_report") is not False
    results["xueqiu_hot_stock_arguments"] = argument_rows
    data_status["雪球热榜AI解释"] = argument_ok
    step_status["雪球热榜AI解释获取"] = argument_ok
    if argument_ok:
        emit(f"   ✅ 雪球热榜AI解释成功: {len(argument_rows)} 条")
    else:
        emit(f"   ❌ 雪球热榜AI解释失败: {(argument_result or {}).get('diagnostic_note', '')}")
    _append_log(
        module_logs,
        "request.xueqiu_hot_stock_arguments",
        "success" if argument_ok else "error",
        "已处理雪球热榜AI解释请求",
        provider=(argument_result or {}).get("provider", "xueqiu.hot_stock.argument"),
        target_keys=["xueqiu_hot_stock_arguments"],
        row_count=len(argument_rows),
        symbol_count=len(symbols),
        error=(argument_result or {}).get("diagnostic_note", ""),
    )


def _xueqiu_argument_symbols(*row_groups):
    symbols = []
    seen = set()
    for rows in row_groups:
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("full_code") or "").strip().upper()
            if not symbol:
                code = "".join(ch for ch in str(row.get("code") or "") if ch.isdigit())
                if len(code) == 6:
                    symbol = ("SH" if code.startswith("6") else "SZ") + code
            if symbol and symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)
            if len(symbols) >= 30:
                return symbols
    return symbols


def collect_market_activity_sector_snapshot_request_bundle(
    target_date,
    *,
    fetch_hot_plate,
    tencent,
    get_sector_change_from_iwencai,
    get_turnover_rank_from_iwencai,
    request_registry=None,
    timer,
    emit,
    current_dates=None,
):
    results = {}
    data_status = {}
    step_status = {
        "板块热榜获取": False,
        "行业资金流向获取": False,
        "板块涨跌幅排行获取": False,
        "成交额排名获取": False,
    }
    module_logs = []

    emit("  6️⃣ 获取板块热榜（Tushare 优先）...")
    try:
        hot_plates_fetcher = (request_registry or {}).get("sector_hot_plates")
        if callable(hot_plates_fetcher):
            hot_plates = hot_plates_fetcher(target_date=target_date, limit=20)
        else:
            hot_plates = fetch_hot_plate()
        if hot_plates:
            results["hot_plates"] = hot_plates
            data_status["板块热榜"] = True
            step_status["板块热榜获取"] = True
            elapsed, _ = timer.record("板块热榜获取", 6)
            emit(f"   ✅ 板块热榜成功: {len(hot_plates)} 条 [⏱ {elapsed:.2f}s]")
        else:
            results["hot_plates"] = []
            data_status["板块热榜"] = False
            emit("   ❌ 板块热榜返回空")
        _append_log(
            module_logs,
            "request.hot_plates",
            "success" if data_status.get("板块热榜") else "degraded",
            "已处理板块热榜请求",
            provider=_provider_from_rows(results.get("hot_plates", []), "tushare.ths_hot"),
            target_keys=["hot_plates"],
            plate_count=len(results.get("hot_plates", [])),
        )
    except Exception as error:
        results["hot_plates"] = []
        data_status["板块热榜"] = False
        emit(f"   ❌ 板块热榜失败: {error}")
        _append_log(
            module_logs,
            "request.hot_plates",
            "error",
            "板块热榜请求失败",
            provider="tushare.ths_hot",
            target_keys=["hot_plates"],
            error=str(error),
        )

    emit("  7️⃣ 获取行业资金流向（Tushare 优先）...")
    try:
        today, yesterday = current_dates or (None, None)
        historical_target = _is_historical_target_date(target_date, current_dates)
        sector_flow_fetcher = (request_registry or {}).get("sector_fund_flow")
        provider = ""
        if callable(sector_flow_fetcher):
            sector_flow = sector_flow_fetcher(target_date=target_date, limit=50) or {}
            inflow = _normalize_sector_fund_flow_rows(sector_flow.get("inflow", []))
            outflow = _normalize_sector_fund_flow_rows(sector_flow.get("outflow", []))
            provider = (sector_flow or {}).get("provider", "tushare.moneyflow_ind_ths")
            if not (inflow or outflow) and (target_date == today or target_date == yesterday):
                inflow = _normalize_sector_fund_flow_rows(tencent.get_sector_fund_flow(flow_type="in", limit=50))
                outflow = _normalize_sector_fund_flow_rows(tencent.get_sector_fund_flow(flow_type="out", limit=50))
                if inflow or outflow:
                    provider = "tencent.get_sector_fund_flow"
            results["sector_fund_flow"] = {
                "inflow": inflow,
                "outflow": outflow,
                "provider": provider,
                "fallback_used": bool((sector_flow or {}).get("fallback_used")),
            }
            for date_key in ("trade_date", "source_date", "query_date"):
                if (sector_flow or {}).get(date_key):
                    results["sector_fund_flow"][date_key] = (sector_flow or {}).get(date_key)
            if inflow or outflow:
                data_status["行业资金流向"] = True
                step_status["行业资金流向获取"] = True
                elapsed, _ = timer.record("行业资金流向获取", 7)
                emit(f"   ✅ 行业资金流成功: 净流入{len(inflow)}条, 净流出{len(outflow)}条 [⏱ {elapsed:.2f}s]")
            else:
                results["sector_fund_flow"].update({"inflow": [], "outflow": []})
                data_status["行业资金流向"] = False
                step_status["行业资金流向获取"] = False
                timer.record("行业资金流向获取(失败)", 7)
                emit("   ❌ 行业资金流向返回空，关键数据不完整，停止生成")
        elif target_date == today or target_date == yesterday:
            inflow = _normalize_sector_fund_flow_rows(tencent.get_sector_fund_flow(flow_type="in", limit=50))
            outflow = _normalize_sector_fund_flow_rows(tencent.get_sector_fund_flow(flow_type="out", limit=50))
            results["sector_fund_flow"] = {
                "inflow": inflow,
                "outflow": outflow,
                "provider": "tencent.get_sector_fund_flow",
                "fallback_used": True,
            }
            if inflow or outflow:
                data_status["行业资金流向"] = True
                step_status["行业资金流向获取"] = True
                elapsed, _ = timer.record("行业资金流向获取", 7)
                emit(f"   ✅ 腾讯财经成功: 净流入{len(inflow)}条, 净流出{len(outflow)}条 [⏱ {elapsed:.2f}s]")
            else:
                results["sector_fund_flow"].update({"inflow": [], "outflow": []})
                data_status["行业资金流向"] = False
                step_status["行业资金流向获取"] = False
                timer.record("行业资金流向获取(失败)", 7)
                emit("   ❌ 行业资金流向返回空，关键数据不完整，停止生成")
        else:
            results["sector_fund_flow"] = {"inflow": [], "outflow": [], "provider": "tencent.get_sector_fund_flow", "fallback_used": True}
            data_status["行业资金流向"] = False
            step_status["行业资金流向获取"] = False
            timer.record("行业资金流向获取(失败)", 7)
            emit("   ❌ 历史板块资金流向未取得，关键数据不完整，停止生成")
        _append_log(
            module_logs,
            "request.sector_fund_flow",
            "success" if data_status.get("行业资金流向") else "degraded",
            "已处理行业资金流向请求" if data_status.get("行业资金流向") else "行业资金流向缺失，关键数据不完整，停止生成",
            provider=provider or ((sector_flow or {}).get("provider", "tushare.moneyflow_ind_ths") if "sector_flow" in locals() else "tencent.get_sector_fund_flow"),
            target_keys=["sector_fund_flow"],
            historical=bool(results.get("sector_fund_flow", {}).get("is_historical")),
            error="" if data_status.get("行业资金流向") else "关键数据不完整，停止生成",
        )
    except Exception as error:
        results["sector_fund_flow"] = {"inflow": [], "outflow": []}
        data_status["行业资金流向"] = False
        step_status["行业资金流向获取"] = False
        emit(f"   ❌ 行业资金流向失败: {error}")
        _append_log(
            module_logs,
            "request.sector_fund_flow",
            "error",
            "行业资金流向请求失败",
            provider="tencent.get_sector_fund_flow",
            target_keys=["sector_fund_flow"],
            error=str(error),
        )

    emit("  7️⃣.5️⃣ 获取概念板块资金流（成分股聚合）...")
    try:
        concept_flow_fetcher = (request_registry or {}).get("concept_fund_flow")
        concept_flow = {}
        if callable(concept_flow_fetcher):
            concept_flow = concept_flow_fetcher(
                target_date=target_date,
                hot_plates=results.get("hot_plates", []),
                limit=20,
            ) or {}
        rows = list((concept_flow or {}).get("rows") or [])
        results["concept_fund_flow"] = {
            "rows": rows,
            "inflow": list((concept_flow or {}).get("inflow") or []),
            "outflow": list((concept_flow or {}).get("outflow") or []),
            "provider": (concept_flow or {}).get("provider", ""),
        }
        data_status["概念资金流向"] = bool(rows)
        step_status["概念资金流向获取"] = bool(rows)
        elapsed, _ = timer.record("概念资金流向获取", "7.5")
        if rows:
            emit(f"   ✅ 概念资金流成功: {len(rows)} 个概念板块 [⏱ {elapsed:.2f}s]")
        else:
            emit("   ⚠️ 概念资金流未取得，概念板块不写成0")
        _append_log(
            module_logs,
            "request.concept_fund_flow",
            "success" if rows else "degraded",
            "已处理概念板块资金流请求",
            provider=(concept_flow or {}).get("provider", ""),
            target_keys=["concept_fund_flow"],
            row_count=len(rows),
        )
    except Exception as error:
        results["concept_fund_flow"] = {"rows": [], "inflow": [], "outflow": []}
        data_status["概念资金流向"] = False
        step_status["概念资金流向获取"] = False
        emit(f"   ⚠️ 概念资金流获取失败: {error}")
        _append_log(
            module_logs,
            "request.concept_fund_flow",
            "degraded",
            "概念板块资金流请求失败",
            provider="tushare.ths_member+tushare.moneyflow",
            target_keys=["concept_fund_flow"],
            error=str(error),
        )

    emit("  8️⃣ 获取板块涨跌幅排行（Tushare 优先）...")
    try:
        sector_change_fetcher = (request_registry or {}).get("sector_change_rank")
        if callable(sector_change_fetcher):
            sector_up = sector_change_fetcher(target_date=target_date, rank_type="up", limit=10)
            sector_down = sector_change_fetcher(target_date=target_date, rank_type="down", limit=10)
        else:
            sector_up = get_sector_change_from_iwencai(rank_type="up", limit=10, target_date=target_date)
            sector_down = get_sector_change_from_iwencai(rank_type="down", limit=10, target_date=target_date)
        if not sector_up:
            sector_up = _derive_sector_change_rank_from_fund_flow(
                results.get("sector_fund_flow", {}),
                rank_type="up",
                limit=10,
            )
        if not sector_down:
            sector_down = _derive_sector_change_rank_from_fund_flow(
                results.get("sector_fund_flow", {}),
                rank_type="down",
                limit=10,
            )
        results["sector_change_up"] = sector_up or []
        results["sector_change_down"] = sector_down or []
        data_status["板块涨幅排行"] = bool(sector_up)
        data_status["板块跌幅排行"] = bool(sector_down)
        if sector_up and sector_down:
            step_status["板块涨跌幅排行获取"] = True
            elapsed, _ = timer.record("板块涨跌幅排行获取", 8)
            emit(f"   ✅ 板块涨跌幅排行成功 [⏱ {elapsed:.2f}s]")
        else:
            step_status["板块涨跌幅排行获取"] = False
            timer.record("板块涨跌幅排行获取(失败)", 8)
            emit("   ❌ 板块涨跌幅排行为空，关键数据不完整，停止生成")
        _append_log(
            module_logs,
            "request.sector_change_rank",
            "success" if step_status.get("板块涨跌幅排行获取") else "degraded",
            "已处理板块涨跌幅排行请求" if step_status.get("板块涨跌幅排行获取") else "板块涨跌幅排行缺失，关键数据不完整，停止生成",
            provider=_provider_from_rows(
                list(results.get("sector_change_up", [])) + list(results.get("sector_change_down", [])),
                "tencent.sector_change_rank",
            ),
            target_keys=["sector_change_up", "sector_change_down"],
            up_count=len(results.get("sector_change_up", [])),
            down_count=len(results.get("sector_change_down", [])),
            error="" if step_status.get("板块涨跌幅排行获取") else "关键数据不完整，停止生成",
        )
    except Exception as error:
        results["sector_change_up"] = []
        results["sector_change_down"] = []
        data_status["板块涨幅排行"] = False
        data_status["板块跌幅排行"] = False
        step_status["板块涨跌幅排行获取"] = False
        timer.record("板块涨跌幅排行获取(失败)", 8)
        emit(f"   ❌ 板块涨跌幅排行失败: {error}")
        _append_log(
            module_logs,
            "request.sector_change_rank",
            "error",
            "腾讯板块涨跌幅排行请求失败",
            provider="tencent.sector_change_rank",
            target_keys=["sector_change_up", "sector_change_down"],
            error=str(error),
        )

    emit("  9️⃣ 获取成交额排行（Tushare 优先）...")
    try:
        turnover_rank_fetcher = (request_registry or {}).get("turnover_rank")
        if callable(turnover_rank_fetcher):
            turnover_rank = turnover_rank_fetcher(target_date=target_date, limit=50)
        else:
            turnover_rank = get_turnover_rank_from_iwencai(limit=50, target_date=target_date)
        if turnover_rank:
            over_100b = [stock for stock in turnover_rank if stock.get("turnover", 0) > 100]
            results["turnover_rank"] = turnover_rank
            results["turnover_over_100b"] = over_100b
            data_status["成交额排名"] = True
            step_status["成交额排名获取"] = True
            elapsed, _ = timer.record("成交额排名获取", 9)
            emit(f"   ✅ 成交额排行成功: {len(turnover_rank)} 条，>100亿: {len(over_100b)} 只 [⏱ {elapsed:.2f}s]")
        else:
            results["turnover_rank"] = []
            results["turnover_over_100b"] = []
            data_status["成交额排名"] = False
            emit("   ❌ 成交额排行返回空")
        _append_log(
            module_logs,
            "request.turnover_rank",
            "success" if data_status.get("成交额排名") else "degraded",
            "已处理成交额排行请求",
            provider=_provider_from_rows(results.get("turnover_rank", []), "tushare.daily"),
            target_keys=["turnover_rank", "turnover_over_100b"],
            turnover_count=len(results.get("turnover_rank", [])),
            over_100b_count=len(results.get("turnover_over_100b", [])),
        )
    except Exception as error:
        results["turnover_rank"] = []
        results["turnover_over_100b"] = []
        data_status["成交额排名"] = False
        emit(f"   ❌ 东方财富成交额排行失败: {error}")
        _append_log(
            module_logs,
            "request.turnover_rank",
            "error",
            "成交额排行请求失败",
            provider="tushare.daily",
            target_keys=["turnover_rank", "turnover_over_100b"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }


def _normalize_lhb_code(fs_code):
    return str(fs_code or "").replace(".SZ", "").replace(".SH", "").replace(".BJ", "")


def _stock_matches_code(stock, code):
    if not isinstance(stock, dict):
        return False
    expected_code = _normalize_quote_code(code)
    for key in ("code", "代码", "stock_code", "symbol", "prod_code"):
        if expected_code and _normalize_quote_code(stock.get(key)) == expected_code:
            return True
    return False


def _first_valid_plate_name(plates):
    for plate in plates or []:
        if isinstance(plate, dict):
            candidates = (
                plate.get("plate_name"),
                plate.get("name"),
                plate.get("concept_name"),
                plate.get("sector"),
            )
        else:
            candidates = (plate,)
        for candidate in candidates:
            if _is_valid_sector_label(candidate):
                return str(candidate).strip()
    return ""


def _resolve_xuangubao_sector(code, existing_results=None):
    xgb_data = (existing_results or {}).get("xuangubao_data") or {}
    for item in xgb_data.get("xuangubao_limit_up_reasons", []) or []:
        if _stock_matches_code(item, code):
            plate_name = _first_valid_plate_name(item.get("related_plates") or [])
            if plate_name:
                return plate_name

    for news in xgb_data.get("xuangubao_news", []) or []:
        if not isinstance(news, dict):
            continue
        stocks = list(news.get("stocks") or []) + list(news.get("all_stocks") or [])
        if any(_stock_matches_code(stock, code) for stock in stocks):
            plate_name = _first_valid_plate_name(
                news.get("plates")
                or news.get("bkj_infos")
                or news.get("plate_infos")
                or []
            )
            if plate_name:
                return plate_name
    return ""


def _resolve_hot_rank_sector(code, existing_results=None):
    for stock in (existing_results or {}).get("hot_rank_top30", []) or []:
        if _stock_matches_code(stock, code):
            plate_name = _first_valid_plate_name(stock.get("concepts") or [])
            if plate_name:
                return plate_name
    return ""


def _resolve_lhb_sector(code, existing_results=None):
    existing_results = existing_results or {}
    for pool_key in ("zt_pool", "dt_pool"):
        for stock in existing_results.get(pool_key, []) or []:
            if stock.get("代码") == code:
                sector = stock.get("所属行业", "未知")
                if _is_valid_sector_label(sector):
                    return sector
    for resolver in (_resolve_xuangubao_sector, _resolve_hot_rank_sector):
        sector = resolver(code, existing_results)
        if _is_valid_sector_label(sector):
            return sector
    return "待补充板块"


def _quote_info_sector(info):
    info = info or {}
    for key in ("sector", "所属行业", "industry", "sector_name"):
        sector = info.get(key)
        if _is_valid_sector_label(sector):
            return str(sector).strip()
    return ""


def _related_plate_names(related_plates):
    names = []
    for plate in related_plates or []:
        if not isinstance(plate, dict):
            continue
        name = str(plate.get("plate_name") or plate.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _resolve_limit_up_row_sector(row, xgb_reason=None, reason_text=""):
    sector = row.get("所属行业", "未知")
    if _is_valid_sector_label(sector):
        return sector
    plate_name = _first_valid_plate_name((xgb_reason or {}).get("related_plates") or [])
    if plate_name:
        return plate_name
    inferred = _infer_sector_from_reason(
        " / ".join(
            str(value or "")
            for value in (
                reason_text,
                (xgb_reason or {}).get("stock_reason"),
                row.get("涨停统计"),
                row.get("涨停原因"),
                row.get("reason"),
            )
        )
    )
    if inferred:
        return inferred
    return "待补充板块"


def _build_xuangubao_limit_up_reason_map(existing_results):
    xgb_data = (existing_results or {}).get("xuangubao_data") or {}
    mapped = {}
    for item in xgb_data.get("xuangubao_limit_up_reasons", []) or []:
        if not isinstance(item, dict):
            continue
        code = _normalize_quote_code(item.get("symbol") or item.get("code") or item.get("stock_code"))
        if code:
            mapped[code] = item
    return mapped


def collect_market_activity_capital_snapshot_request_bundle(
    target_date,
    *,
    limit_up_df,
    existing_results,
    fetch_lhb_rows,
    request_registry=None,
    limit_up_provider="akshare.limit_up_pool",
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {
        "连板梯队提取": False,
        "龙虎榜数据获取": False,
    }
    module_logs = []
    xuangubao_reason_map = _build_xuangubao_limit_up_reason_map(existing_results)

    emit("  1️⃣3️⃣ 从涨停池提取连板梯队... (依赖: 步骤4)")
    try:
        lianban_data = []
        if limit_up_df is not None and not limit_up_df.empty:
            for _, row in limit_up_df.iterrows():
                lianban_days = row.get("连板数", 1)
                first_limit_time_raw = str(row.get("首次封板时间", "")).strip()
                if first_limit_time_raw and len(first_limit_time_raw) >= 6:
                    first_limit_time = f"{first_limit_time_raw[:2]}:{first_limit_time_raw[2:4]}:{first_limit_time_raw[4:6]}"
                elif first_limit_time_raw and len(first_limit_time_raw) == 4:
                    first_limit_time = f"{first_limit_time_raw[:2]}:{first_limit_time_raw[2:4]}:00"
                else:
                    first_limit_time = "15:00:00"
                xgb_reason = xuangubao_reason_map.get(_normalize_quote_code(row["代码"]), {}) or {}
                stock_reason = xgb_reason.get("stock_reason", "")
                reason_text = stock_reason or row.get("涨停统计", "")
                lianban_item = {
                    "code": row["代码"],
                    "name": row["名称"],
                    "lianban_days": lianban_days,
                    "change_pct": row.get("涨跌幅", 0),
                    "turnover": row.get("成交额", 0),
                    "sector": _resolve_limit_up_row_sector(row, xgb_reason, reason_text),
                    "reason": reason_text,
                    "open_price": row.get("开盘价", 0),
                    "close_price": row.get("最新价", 0),
                    "high_price": row.get("最高价", 0),
                    "low_price": row.get("最低价", 0),
                    "first_limit_time": first_limit_time,
                }
                if xgb_reason:
                    related_plates = xgb_reason.get("related_plates", []) or []
                    lianban_item.update(
                        {
                            "xuangubao_stock_reason": stock_reason,
                            "xuangubao_related_plates": related_plates,
                            "xuangubao_related_plate_names": _related_plate_names(related_plates),
                            "xuangubao_limit_up_days": xgb_reason.get("limit_up_days", 0),
                        }
                    )
                lianban_data.append(lianban_item)
        lianban_data.sort(key=lambda item: (-item["lianban_days"], item["first_limit_time"]))
        results["lianban_data"] = lianban_data
        step_status["连板梯队提取"] = True
        if lianban_data:
            emit(f"   ✅ 连板梯队提取成功: {len(lianban_data)} 只（最高{lianban_data[0]['lianban_days']}连板）")
        else:
            emit("   ⚠️ 连板梯队数据为空（无连板股）")
        _append_log(
            module_logs,
            "request.lianban_snapshot",
            "success",
            "已处理连板梯队请求",
            provider=limit_up_provider or "akshare.limit_up_pool",
            target_keys=["lianban_data"],
            lianban_count=len(lianban_data),
        )
    except Exception as error:
        results["lianban_data"] = []
        emit(f"   ⚠️ 连板梯队提取失败: {error}")
        _append_log(
            module_logs,
            "request.lianban_snapshot",
            "error",
            "连板梯队请求失败",
            provider="akshare.limit_up_pool",
            target_keys=["lianban_data"],
            error=str(error),
        )

    emit("  1️⃣3️⃣ 获取龙虎榜数据（Tushare 优先）...")
    try:
        lhb_fetcher = (request_registry or {}).get("lhb_snapshot")
        if callable(lhb_fetcher):
            snapshot = lhb_fetcher(target_date=target_date) or {}
            net_buy_top10 = list(snapshot.get("lhb_net_buy_top10") or [])
            net_sell_top10 = list(snapshot.get("lhb_net_sell_top10") or [])
            grouped_rows = list(snapshot.get("lhb_analysis") or [])
            inst_detail = list(snapshot.get("lhb_inst_detail") or [])
            for item in net_buy_top10 + net_sell_top10:
                code = item.get("code", "")
                if code and not _is_valid_sector_label(item.get("sector")):
                    item["sector"] = _resolve_lhb_sector(code, existing_results)
        else:
            lhb_rows = fetch_lhb_rows(target_date)
            grouped = {}
            for row in lhb_rows or []:
                code = _normalize_lhb_code(row.get("fs_code", ""))
                if not code:
                    continue
                bucket = grouped.setdefault(
                    code,
                    {
                        "代码": code,
                        "net_buy_amount": 0,
                        "close_price": row.get("close_price", 0),
                        "change_rate": row.get("change_rate", 0),
                        "fs_code": row.get("fs_code", ""),
                    },
                )
                bucket["net_buy_amount"] += row.get("net_buy_amount", 0) or 0
                bucket["close_price"] = bucket.get("close_price") or row.get("close_price", 0)
                bucket["change_rate"] = bucket.get("change_rate") or row.get("change_rate", 0)

            grouped_rows = list(grouped.values())
            buy_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0), reverse=True)[:10]
            sell_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0))[:10]

            net_buy_top10 = []
            for rank, row in enumerate(buy_rows, 1):
                code = row["代码"]
                net_buy_top10.append(
                    {
                        "rank": rank,
                        "code": code,
                        "name": "",
                        "net_buy_amount_yi": (row.get("net_buy_amount", 0) or 0) / 1e8,
                        "change_pct": row.get("change_rate", 0),
                        "zt_status": "正常",
                        "sector": _resolve_lhb_sector(code, existing_results),
                    }
                )

            net_sell_top10 = []
            for rank, row in enumerate(sell_rows, 1):
                code = row["代码"]
                net_sell_top10.append(
                    {
                        "rank": rank,
                        "code": code,
                        "name": "",
                        "net_buy_amount_yi": (row.get("net_buy_amount", 0) or 0) / 1e8,
                        "change_pct": row.get("change_rate", 0),
                        "zt_status": "正常",
                        "sector": _resolve_lhb_sector(code, existing_results),
                    }
                )
            inst_detail = []

        results["lhb_net_buy_top10"] = net_buy_top10
        results["lhb_net_sell_top10"] = net_sell_top10
        results["lhb_analysis"] = grouped_rows
        results["lhb_inst_detail"] = inst_detail
        if "snapshot" in locals() and isinstance(snapshot, dict):
            results["lhb_inst_detail_status"] = snapshot.get("lhb_inst_detail_status") or ("available" if inst_detail else "empty")
        else:
            results["lhb_inst_detail_status"] = "empty"
        has_lhb_rows = bool(net_buy_top10 or net_sell_top10 or grouped_rows)
        lhb_provider = (snapshot or {}).get("provider", "tushare.top_list") if "snapshot" in locals() else "finshare.get_lhb"
        results["lhb_provider"] = lhb_provider
        results["lhb_data_status"] = "available" if has_lhb_rows else "upstream_empty"
        step_status["龙虎榜数据获取"] = has_lhb_rows
        timer.record("龙虎榜数据获取", 13)
        if has_lhb_rows:
            emit(f"   ✅ 龙虎榜: 净买{len(net_buy_top10)}只/净卖{len(net_sell_top10)}只（已去重）")
        else:
            emit("   ⚠️ 龙虎榜返回空")
        _append_log(
            module_logs,
            "request.lhb_snapshot",
            "success" if has_lhb_rows else "degraded",
            "已处理龙虎榜请求" if has_lhb_rows else "龙虎榜返回空",
            provider=lhb_provider,
            target_keys=["lhb_net_buy_top10", "lhb_net_sell_top10", "lhb_analysis", "lhb_inst_detail"],
            lhb_count=len(grouped_rows),
            buy_count=len(net_buy_top10),
            sell_count=len(net_sell_top10),
            inst_detail_count=len(inst_detail),
        )
    except Exception as error:
        results["lhb_net_buy_top10"] = []
        results["lhb_net_sell_top10"] = []
        results["lhb_analysis"] = []
        results["lhb_inst_detail"] = []
        results["lhb_inst_detail_status"] = "error"
        results["lhb_provider"] = "finshare.get_lhb"
        results["lhb_data_status"] = "error"
        emit(f"   ⚠️ 龙虎榜获取失败: {error}")
        _append_log(
            module_logs,
            "request.lhb_snapshot",
            "error",
            "龙虎榜请求失败",
            provider="finshare.get_lhb",
            target_keys=["lhb_net_buy_top10", "lhb_net_sell_top10", "lhb_analysis", "lhb_inst_detail"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }


def _normalize_quote_code(raw_code):
    text = str(raw_code or "").strip()
    for suffix in (".SZ", ".SS", ".SH", ".BJ"):
        if text.upper().endswith(suffix):
            text = text[: -len(suffix)]
            break
    lower_text = text.lower()
    for prefix in ("sz", "sh", "bj"):
        if lower_text.startswith(prefix):
            text = text[len(prefix) :]
            break
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _normalize_quote_trade_date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text[:10]


def _realtime_quote_fallback_allowed(target_date=None, *, current_date=None, allow_realtime_quote_fallback=None):
    if allow_realtime_quote_fallback is not None:
        return bool(allow_realtime_quote_fallback)
    normalized_target = _normalize_quote_trade_date(target_date)
    if not normalized_target:
        return True
    normalized_current = _normalize_quote_trade_date(current_date or _dt.datetime.now().strftime("%Y-%m-%d"))
    return normalized_target == normalized_current


def _report_stock_code(row):
    if not isinstance(row, dict):
        return ""
    for key in ("code", "代码", "stock_code", "symbol", "prod_code", "ts_code", "full_code", "股票代码", "证券代码"):
        code = _normalize_quote_code(row.get(key))
        if code:
            return code
    return ""


def _iter_report_stock_rows(payload, *, depth=0):
    if depth > 5:
        return
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_report_stock_rows(item, depth=depth + 1)
        return
    if not isinstance(payload, dict):
        return
    if _report_stock_code(payload):
        yield payload
    for key, value in payload.items():
        if key in _REPORT_STOCK_LIST_KEYS or key in _REPORT_STOCK_OBJECT_KEYS or key in _REPORT_STOCK_CONTAINER_KEYS:
            yield from _iter_report_stock_rows(value, depth=depth + 1)


def _collect_report_stock_quote_codes(payload):
    return {
        code
        for row in _iter_report_stock_rows(payload)
        for code in (_report_stock_code(row),)
        if code
    }


def _has_report_stock_rows(payload):
    return any(True for _row in _iter_report_stock_rows(payload))


def _normalize_stock_info_map(stock_full_info):
    normalized = {}
    for raw_code, info in (stock_full_info or {}).items():
        code = _normalize_quote_code(raw_code)
        if not code or not isinstance(info, dict):
            continue
        normalized[code] = info
    return normalized


def _quote_info_complete(info, *, target_date=None):
    if not isinstance(info, dict):
        return False
    normalized_target = _normalize_quote_trade_date(target_date)
    if normalized_target:
        source_date = ""
        for key in ("trade_date", "source_date", "query_date", "date"):
            source_date = _normalize_quote_trade_date(info.get(key))
            if source_date:
                break
        if not source_date:
            return False
        if source_date and source_date != normalized_target:
            return False
    if info.get("change_pct") in (None, ""):
        return False
    price_values = [info.get(key) for key in ("open", "high", "low", "close")]
    if any(value in (None, "") for value in price_values):
        return False
    try:
        numeric_prices = [float(value) for value in price_values]
    except (TypeError, ValueError):
        return False
    return all(value > 0 for value in numeric_prices)


def _patch_quote_fields(row, info):
    patched = dict(row or {})
    info = info or {}
    if not patched.get("name"):
        name_from_info = info.get("name") or info.get("名称", "")
        if name_from_info:
            patched["name"] = name_from_info
    if not _is_valid_sector_label(patched.get("sector")):
        sector_from_info = _quote_info_sector(info)
        if sector_from_info:
            patched["sector"] = sector_from_info
    for target_key, source_key in (
        ("change_pct", "change_pct"),
        ("high", "high"),
        ("low", "low"),
        ("open", "open"),
        ("close", "close"),
        ("zt_status", "zt_status"),
    ):
        value = info.get(source_key)
        if value not in (None, ""):
            patched[target_key] = value
    return patched


def _patch_report_stock_quote_sources(payload, stock_full_info, *, depth=0):
    if depth > 5:
        return payload
    if isinstance(payload, list):
        return [_patch_report_stock_quote_sources(item, stock_full_info, depth=depth + 1) for item in payload]
    if not isinstance(payload, dict):
        return payload

    patched = dict(payload)
    code = _report_stock_code(patched)
    if code:
        patched = _patch_quote_fields(patched, stock_full_info.get(code, {}))
    for key, value in list(patched.items()):
        if key in _REPORT_STOCK_LIST_KEYS or key in _REPORT_STOCK_OBJECT_KEYS or key in _REPORT_STOCK_CONTAINER_KEYS:
            patched[key] = _patch_report_stock_quote_sources(value, stock_full_info, depth=depth + 1)
    return patched


def collect_market_activity_stock_quote_request_bundle(
    *,
    existing_results,
    fetch_stock_batch_info,
    fetch_tushare_stock_batch_info=None,
    target_date=None,
    current_date=None,
    allow_realtime_quote_fallback=None,
    timer,
    emit,
):
    existing_results = existing_results or {}
    results = {}
    module_logs = []

    emit("\n📊 批量获取股票完整信息（涨跌幅、最高价、最低价、开盘价、收盘价）...")
    all_stock_codes = _collect_report_stock_quote_codes(existing_results)
    existing_stock_full_info = _normalize_stock_info_map(existing_results.get("stock_full_info") or {})
    realtime_quote_allowed = _realtime_quote_fallback_allowed(
        target_date,
        current_date=current_date,
        allow_realtime_quote_fallback=allow_realtime_quote_fallback,
    )

    if all_stock_codes:
        try:
            stock_full_info = dict(existing_stock_full_info)
            provider = "tencent.get_stock_batch_info"
            refresh_codes = sorted(
                code for code in all_stock_codes if not _quote_info_complete(stock_full_info.get(code), target_date=target_date)
            )
            if callable(fetch_tushare_stock_batch_info) and refresh_codes:
                try:
                    try:
                        raw_tushare_info = fetch_tushare_stock_batch_info(refresh_codes, target_date=target_date)
                    except TypeError as error:
                        if "target_date" not in str(error):
                            raise
                        raw_tushare_info = fetch_tushare_stock_batch_info(refresh_codes)
                    tushare_info = _normalize_stock_info_map(raw_tushare_info)
                    valid_tushare_info = {
                        code: info
                        for code, info in tushare_info.items()
                        if code in refresh_codes and _quote_info_complete(info, target_date=target_date)
                    }
                    if valid_tushare_info:
                        stock_full_info.update(valid_tushare_info)
                        provider = "tushare.daily"
                except Exception as error:
                    if realtime_quote_allowed:
                        emit(f"   ⚠️ Tushare批量股票补数失败: {error}，切换腾讯兜底")
                    else:
                        emit(f"   ⚠️ Tushare批量股票补数失败: {error}，历史日期不使用实时行情源")

            missing_codes = sorted(
                code for code in all_stock_codes if not _quote_info_complete(stock_full_info.get(code), target_date=target_date)
            )
            if missing_codes and realtime_quote_allowed:
                tencent_info = _normalize_stock_info_map(fetch_stock_batch_info(missing_codes))
                if tencent_info:
                    stock_full_info.update({code: info for code, info in tencent_info.items() if code in missing_codes})
                    if provider == "tushare.daily":
                        provider = "tushare.daily+tencent.get_stock_batch_info"
                    else:
                        provider = "tencent.get_stock_batch_info"
                missing_codes = sorted(
                    code for code in all_stock_codes if not _quote_info_complete(stock_full_info.get(code), target_date=target_date)
                )
            elif missing_codes:
                provider = "tushare.daily"
                emit("   ⚠️ 历史日期不使用实时行情源补数，保留未补齐股票")
            results["stock_full_info"] = stock_full_info
            elapsed, _ = timer.record("批量获取股票信息", 15)
            emit(f"   ✅ 成功获取 {len(stock_full_info)} 只股票的完整信息 [⏱ {elapsed:.2f}s]")
            log_status = "success" if not missing_codes else "degraded"
            _append_log(
                module_logs,
                "request.stock_quotes",
                log_status,
                "已处理批量股票补数请求" if not missing_codes else "历史日期股票行情仍有缺口",
                provider=provider,
                target_keys=["stock_full_info"],
                stock_count=len(stock_full_info),
                requested_count=len(all_stock_codes),
                refreshed_count=len(refresh_codes),
                missing_count=len(missing_codes),
                target_date=target_date or "",
                realtime_quote_allowed=realtime_quote_allowed,
            )
        except Exception as error:
            results["stock_full_info"] = existing_stock_full_info
            timer.record("批量获取股票信息(失败)", 15)
            emit(f"   ⚠️ 批量查询失败: {error}")
            _append_log(
                module_logs,
                "request.stock_quotes",
                "error",
                "批量股票补数请求失败",
                provider="tencent.get_stock_batch_info",
                target_keys=["stock_full_info"],
                error=str(error),
            )
    else:
        results["stock_full_info"] = existing_stock_full_info
        timer.record("批量获取股票信息(跳过)", 15)
        _append_log(
            module_logs,
            "request.stock_quotes",
            "degraded",
            "无股票代码可用于批量补数",
            provider="tencent.get_stock_batch_info",
            target_keys=["stock_full_info"],
        )

    stock_full_info_for_fill = results.get("stock_full_info", {}) or {}
    if stock_full_info_for_fill:
        patched_sources = _patch_report_stock_quote_sources(existing_results, stock_full_info_for_fill)
        for key, value in patched_sources.items():
            if (
                key in _REPORT_STOCK_LIST_KEYS
                or key in _REPORT_STOCK_OBJECT_KEYS
                or key in _REPORT_STOCK_CONTAINER_KEYS
            ) and _has_report_stock_rows(existing_results.get(key)):
                results[key] = value

    return {
        "results": results,
        "module_logs": module_logs,
    }
