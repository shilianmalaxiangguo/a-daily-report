from domains.market_activity.quote_lookup import (
    build_market_quote_lookup,
    resolve_market_quote,
)


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_activity.infer",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def _build_unified_sector_strength_rows(data):
    return []


def normalize_stock_code(code):
    return str(code or "")


def analyze_market_and_sectors(data, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _analyze_market_and_sectors_legacy_body(data)
    finally:
        _restore_runtime_bindings(previous)


def resolve_market_mainline_context(data, market_analysis, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _resolve_market_mainline_context_legacy_body(data, market_analysis)
    finally:
        _restore_runtime_bindings(previous)


def _analyze_market_and_sectors_legacy_body(data):
    data = data or {}
    analysis = {
        "market_status": "",
        "main_sectors": [],
        "secondary_sectors": [],
        "risk_sectors": [],
        "sector_analysis": {},
        "unified_sector_rows": [],
    }

    if data.get("indices"):
        sh_change = data["indices"].get("上证指数", {}).get("涨跌幅", 0)
        sz_change = data["indices"].get("深证成指", {}).get("涨跌幅", 0)

        if sh_change > 1.0 and sz_change > 1.0:
            analysis["market_status"] = "强势上涨"
        elif sh_change > 0.5 or sz_change > 0.5:
            analysis["market_status"] = "小幅上涨"
        elif sh_change < -1.0 and sz_change < -1.0:
            analysis["market_status"] = "大幅下跌"
        elif sh_change < -0.5 or sz_change < -0.5:
            analysis["market_status"] = "小幅下跌"
        else:
            analysis["market_status"] = "震荡整理"

    unified_sector_rows = _build_unified_sector_strength_rows(data)
    analysis["unified_sector_rows"] = unified_sector_rows[:12]
    analysis["sector_analysis"] = {
        row.get("name", ""): row
        for row in unified_sector_rows
        if row.get("name")
    }

    main_rows = [row for row in unified_sector_rows if row.get("role") == "main"]
    secondary_rows = [row for row in unified_sector_rows if row.get("role") == "secondary"]

    if not main_rows and unified_sector_rows:
        top_row = unified_sector_rows[0]
        if top_row.get("unified_score", 0) >= 35 or top_row.get("hot_plate_rank"):
            forced_row = dict(top_row)
            forced_row["role"] = "main"
            main_rows = [forced_row]
            secondary_rows = [row for row in unified_sector_rows[1:] if row.get("unified_score", 0) >= 28][:4]

    analysis["main_sectors"] = [dict(item) for item in main_rows[:5]]
    analysis["secondary_sectors"] = [dict(item) for item in secondary_rows[:5]]

    if data.get("sector_fund_flow"):
        outflow = data["sector_fund_flow"].get("outflow", [])
        for sector in outflow[:10]:
            name = sector.get("name", "")
            zljlr = abs(sector.get("zljlr", 0))
            zdf = sector.get("zdf", 0)

            if zljlr > 10 or zdf < -3:
                analysis["risk_sectors"].append(
                    {
                        "name": name,
                        "net_outflow": zljlr,
                        "change": zdf,
                        "risk_level": "high" if zljlr > 20 or zdf < -5 else "medium",
                    }
                )

    if data.get("hot_rank_top30"):
        hot_sectors = {}
        for stock in data["hot_rank_top30"][:10]:
            concepts = stock.get("concepts", [])
            for concept in concepts[:2]:
                if concept not in hot_sectors:
                    hot_sectors[concept] = 0
                hot_sectors[concept] += 1

        analysis["hot_sectors"] = sorted(hot_sectors.items(), key=lambda x: x[1], reverse=True)[:5]

    return analysis


def _build_dragon_stocks_from_zt_pool_legacy_body(data):
    dragon_stocks = []
    for zt in (data or {}).get("zt_pool", []) or []:
        code = zt.get("代码", zt.get("code", ""))
        name = zt.get("名称", zt.get("name", ""))
        lianban = int(float(zt.get("连板数", zt.get("lianban", 0)) or 0))
        if lianban >= 2:
            dragon_stocks.append(
                {
                    "code": normalize_stock_code(code),
                    "name": name,
                    "sector": zt.get("所属板块", zt.get("sector", "")),
                    "lianban": lianban,
                }
            )
    dragon_stocks.sort(key=lambda x: x.get("lianban", 0), reverse=True)
    return dragon_stocks


def _resolve_market_mainline_context_legacy_body(data, market_analysis):
    market_analysis = market_analysis or {}
    main_sectors_info = [dict(item) for item in (market_analysis.get("main_sectors", []) or [])]
    secondary_sectors_info = [dict(item) for item in (market_analysis.get("secondary_sectors", []) or [])]
    unified_rows = market_analysis.get("unified_sector_rows", []) or []

    if not main_sectors_info and unified_rows:
        top_row = unified_rows[0]
        if top_row.get("unified_score", 0) >= 35 or top_row.get("hot_plate_rank"):
            forced_main = dict(top_row)
            forced_main["role"] = "main"
            main_sectors_info = [forced_main]
        if len(unified_rows) > 1:
            secondary_sectors_info = [dict(item) for item in unified_rows[1:4]]

    main_sectors = [item.get("name", "") for item in main_sectors_info if item.get("name")][:3]
    secondary_sectors = [item.get("name", "") for item in secondary_sectors_info if item.get("name")][:3]
    dragon_stocks = _build_dragon_stocks_from_zt_pool_legacy_body(data)

    return {
        "main_sectors_info": main_sectors_info,
        "secondary_sectors_info": secondary_sectors_info,
        "main_sectors": main_sectors,
        "secondary_sectors": secondary_sectors,
        "dragon_stocks": dragon_stocks,
    }


def analyze_single_sector_ai(sector_name: str, all_sectors: set) -> dict:
    analysis = {
        "original_name": sector_name,
        "standard_name": sector_name,
        "parent": None,
        "children": [],
        "related": [],
        "type": "unknown",
        "confidence": 0.5,
    }

    if any(keyword in sector_name for keyword in ["轨交", "轨道交通", "高铁", "铁路", "城轨"]):
        analysis["standard_name"] = "轨道交通"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.95
        if "高铁" in sector_name or "城轨" in sector_name or "地铁" in sector_name:
            analysis["parent"] = "轨道交通"
        elif "设备" in sector_name:
            analysis["parent"] = "轨道交通"
            analysis["related"] = ["机械", "装备制造"]
    elif any(keyword in sector_name for keyword in ["绿电", "电力", "电网", "发电", "供电"]):
        analysis["standard_name"] = "绿电"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.9
        if "算电" in sector_name or "协同" in sector_name:
            analysis["standard_name"] = "算电协同"
            analysis["parent"] = "绿电"
            analysis["related"] = ["算力", "数据中心"]
        elif "光伏" in sector_name:
            analysis["parent"] = "绿电"
            analysis["related"] = ["储能"]
        elif "储能" in sector_name:
            analysis["parent"] = "绿电"
            analysis["related"] = ["光伏", "风电"]
    elif any(keyword in sector_name for keyword in ["航天", "卫星", "太空", "商业航天", "火箭"]):
        analysis["standard_name"] = "商业航天"
        analysis["type"] = "概念"
        analysis["confidence"] = 0.9
        if "光伏" in sector_name and ("太空" in sector_name or "卫星" in sector_name):
            analysis["standard_name"] = "太空光伏"
            analysis["parent"] = "商业航天"
        elif "卫星" in sector_name:
            analysis["parent"] = "商业航天"
        elif "火箭" in sector_name or "发射" in sector_name:
            analysis["parent"] = "商业航天"
    elif any(keyword in sector_name for keyword in ["算力", "AI", "智算", "数据中心", "服务器"]):
        analysis["standard_name"] = "算力"
        analysis["type"] = "概念"
        analysis["confidence"] = 0.9
        if "液冷" in sector_name:
            analysis["standard_name"] = "液冷服务器"
            analysis["parent"] = "算力"
        elif "AI" in sector_name or "人工智能" in sector_name:
            analysis["related"] = ["大模型", "算法"]
    elif any(keyword in sector_name for keyword in ["AI应用", "大模型", "AIGC", "ChatGPT"]):
        analysis["standard_name"] = "AI应用"
        analysis["type"] = "概念"
        analysis["confidence"] = 0.85
        analysis["related"] = ["算力", "大模型"]
    elif any(keyword in sector_name for keyword in ["光通信", "光模块", "CPO", "光纤", "光缆", "光芯片", "光器件", "光学元件"]):
        analysis["standard_name"] = "光通信"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.9
        if "光纤" in sector_name or "光缆" in sector_name:
            analysis["parent"] = "光通信"
            analysis["related"] = ["通信设备"]
    elif any(keyword in sector_name for keyword in ["半导体", "芯片", "集成电路", "晶圆", "元件", "被动元件", "电子元件"]):
        analysis["standard_name"] = "半导体"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.9
        if "设备" in sector_name or "材料" in sector_name:
            analysis["parent"] = "半导体"
    elif any(keyword in sector_name for keyword in ["消费电子", "手机", "苹果", "华为", "小米"]):
        analysis["standard_name"] = "消费电子"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.85
    elif any(keyword in sector_name for keyword in ["电池", "锂电池", "固态电池", "新能源车", "电动车"]):
        analysis["standard_name"] = "新能源车"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.85
        if "电池" in sector_name:
            analysis["parent"] = "新能源车"
    elif any(keyword in sector_name for keyword in ["机器人", "人形机器人", "工业机器人", "减速器"]):
        analysis["standard_name"] = "人形机器人"
        analysis["type"] = "概念"
        analysis["confidence"] = 0.85
    elif any(keyword in sector_name for keyword in ["银行", "券商", "保险", "金融"]):
        analysis["standard_name"] = "大金融"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.8
        if "银行" in sector_name:
            analysis["standard_name"] = "银行"
        elif "券商" in sector_name:
            analysis["standard_name"] = "券商"
    elif any(keyword in sector_name for keyword in ["医药", "医疗", "药", "生物"]):
        analysis["standard_name"] = "医药"
        analysis["type"] = "行业"
        analysis["confidence"] = 0.8
        if "创新药" in sector_name:
            analysis["standard_name"] = "创新药"
            analysis["parent"] = "医药"

    return analysis


def build_sector_tree(sector_relationships: dict) -> dict:
    tree = {}
    parents = set()
    for analysis in sector_relationships.values():
        if analysis["parent"]:
            parents.add(analysis["parent"])
        parents.add(analysis["standard_name"])

    for parent in parents:
        tree[parent] = {"children": [], "all_sectors": []}

    for original, analysis in sector_relationships.items():
        standard = analysis["standard_name"]
        parent = analysis["parent"]
        if parent and parent in tree:
            tree[parent]["children"].append({"name": standard, "original": original, "type": analysis["type"]})
        if standard in tree:
            tree[standard]["all_sectors"].append(original)

    return tree


def analyze_sectors_comprehensive(all_data: dict) -> dict:
    all_sectors = set()
    sector_sources = {}

    if all_data.get("sector_fund_flow"):
        for item in all_data["sector_fund_flow"].get("inflow", []):
            name = item.get("name", "")
            if name:
                all_sectors.add(name)
                sector_sources[name] = "fund_flow"
        for item in all_data["sector_fund_flow"].get("outflow", []):
            name = item.get("name", "")
            if name:
                all_sectors.add(name)
                sector_sources[name] = "fund_flow"

    if all_data.get("hot_plates"):
        for plate in all_data["hot_plates"]:
            name = plate.get("name", "")
            if name:
                all_sectors.add(name)
                sector_sources[name] = "hot_plate"

    if all_data.get("zt_pool_by_sector"):
        for sector_name in all_data["zt_pool_by_sector"].keys():
            if sector_name:
                all_sectors.add(sector_name)
                sector_sources[sector_name] = "zt_pool"

    if all_data.get("xuangubao_data"):
        for plate in all_data["xuangubao_data"].get("xuangubao_plates", []):
            name = plate.get("name", "")
            if name:
                all_sectors.add(name)
                sector_sources[name] = "xuangubao"

    if all_data.get("lianban_data"):
        for stock in all_data["lianban_data"]:
            for plate in stock.get("plates", []):
                if plate:
                    all_sectors.add(plate)
                    sector_sources[plate] = "lianban"

    sector_relationships = {}
    for sector in all_sectors:
        if not sector:
            continue
        analysis = analyze_single_sector_ai(sector, all_sectors)
        analysis["source"] = sector_sources.get(sector, "unknown")
        sector_relationships[sector] = analysis

    mapping = {original: analysis["standard_name"] for original, analysis in sector_relationships.items()}
    standard_sectors = sorted(set(mapping.values()))
    sector_tree = build_sector_tree(sector_relationships)

    return {
        "relationships": sector_relationships,
        "mapping": mapping,
        "standard_sectors": standard_sectors,
        "sector_tree": sector_tree,
        "sector_count": len(all_sectors),
        "standard_count": len(standard_sectors),
    }


def get_standardized_sector(sector_name: str, sector_analysis: dict) -> str:
    if not sector_analysis or not sector_name:
        return sector_name
    mapping = sector_analysis.get("mapping", {})
    return mapping.get(sector_name, sector_name)


def build_market_activity_sector_analysis_bundle(
    all_data,
    *,
    timer,
    emit,
):
    sector_analysis = analyze_sectors_comprehensive(all_data)
    elapsed, _ = timer.record("全局板块AI分析", 16)
    emit(f"   ✅ 标准化板块: {len(sector_analysis['standard_sectors'])} 个 [⏱ {elapsed:.2f}s]")
    emit(f"   ✅ 板块映射: {len(sector_analysis['mapping'])} 条")
    module_logs = []
    _append_log(
        module_logs,
        "infer.sector_ai_analysis",
        "success",
        "已生成 market_activity 板块归链分析",
        sector_count=sector_analysis["sector_count"],
        standard_count=sector_analysis["standard_count"],
    )
    return {
        "results": {"sector_ai_analysis": sector_analysis},
        "module_logs": module_logs,
    }


def _normalize_match_code(code):
    value = str(code or "").replace(".SZ", "").replace(".SS", "").replace(".SH", "").lower()
    if value.startswith("sz") or value.startswith("sh") or value.startswith("bj"):
        value = value[2:]
    return value


def _get_lhb_stock_code(item):
    if hasattr(item, "stock_code"):
        return _normalize_match_code(getattr(item, "stock_code"))
    if isinstance(item, dict):
        return _normalize_match_code(item.get("stock_code") or item.get("code"))
    return ""


def _build_fund_flow_by_standard(all_data):
    sector_ai = all_data.get("sector_ai_analysis", {})
    merged = {}
    for flow in (all_data.get("sector_fund_flow", {}) or {}).get("inflow", []) or []:
        original_name = flow.get("name", "")
        standard_name = get_standardized_sector(original_name, sector_ai)
        if standard_name not in merged:
            merged[standard_name] = dict(flow)
            continue
        bucket = merged[standard_name]
        bucket["zljlr"] = bucket.get("zljlr", 0) + flow.get("zljlr", 0)
        if abs(flow.get("zdf", 0)) > abs(bucket.get("zdf", 0)):
            bucket["zdf"] = flow.get("zdf", 0)
    return merged


def _calculate_sector_volume_change(sector_name, zt_stocks, all_data, stocks_with_history, emit):
    sector_volume_change = 0
    try:
        zt_pool = all_data.get("zt_pool", []) or []
        sector_zt_stocks = [stock for stock in zt_pool if stock.get("所属行业", "") == sector_name]
        if not sector_zt_stocks:
            return 0

        current_sector_volume = sum(stock.get("成交额", 0) or 0 for stock in sector_zt_stocks) / 1e8
        sector_stocks_with_history = [
            stock
            for stock in stocks_with_history
            if any(
                _normalize_match_code(stock.get("code", "")) == _normalize_match_code(zt_item.get("代码", zt_item.get("code", "")))
                for zt_item in zt_stocks
            )
        ]
        if not sector_stocks_with_history:
            return 0

        hist_sector_volumes = []
        for index in range(5):
            day_volume = sum(
                stock.get("hist_turnover", [])[-(index + 1)] if len(stock.get("hist_turnover", [])) > index else 0
                for stock in sector_stocks_with_history
            )
            if day_volume > 0:
                hist_sector_volumes.append(day_volume)

        if not hist_sector_volumes:
            return 0

        avg_sector_volume = sum(hist_sector_volumes) / len(hist_sector_volumes)
        if avg_sector_volume <= 0:
            return 0

        sector_volume_change = ((current_sector_volume / avg_sector_volume) - 1) * 100
        emit(
            f"      📊 {sector_name} 板块放量: 当日{current_sector_volume:.1f}亿 vs "
            f"5日均值{avg_sector_volume:.1f}亿, 变化{sector_volume_change:+.1f}%"
        )
    except Exception as error:
        emit(f"      ⚠️ {sector_name} 板块成交量计算失败: {error}")
    return sector_volume_change


def _build_resonance_sector_payload(all_data, lhb_analysis, stocks_with_history, emit):
    sector_ai = all_data.get("sector_ai_analysis", {})
    zt_sectors = list((all_data.get("zt_pool_by_sector") or {}).keys())
    fund_sectors = [flow.get("name") for flow in ((all_data.get("sector_fund_flow") or {}).get("inflow", []) or [])]
    hot_rank_items = all_data.get("hot_rank") or all_data.get("hot_rank_top30") or []
    emit(f"   📊 涨停池板块: {zt_sectors[:5]}")
    emit(f"   📊 资金流向板块: {fund_sectors[:5]}")

    fund_flow_by_standard = _build_fund_flow_by_standard(all_data)
    sectors_data = {}
    matched_sectors = []
    unmatched_sectors = []

    for sector_name, zt_stocks in (all_data.get("zt_pool_by_sector") or {}).items():
        standard_sector = get_standardized_sector(sector_name, sector_ai)
        fund_flow = fund_flow_by_standard.get(standard_sector, {})
        if fund_flow:
            matched_sectors.append(f"{sector_name}({standard_sector})")
        else:
            unmatched_sectors.append(f"{sector_name}({standard_sector})")

        sector_lhb = [
            item
            for item in lhb_analysis
            if any(_get_lhb_stock_code(item) == _normalize_match_code(stock.get("code", "")) for stock in zt_stocks)
        ]
        hot_rank_count = sum(1 for stock in hot_rank_items if stock.get("sector") == sector_name)
        sector_volume_change = _calculate_sector_volume_change(sector_name, zt_stocks, all_data, stocks_with_history, emit)

        sectors_data[sector_name] = {
            "fund_flow": fund_flow,
            "zt_stocks": zt_stocks,
            "lhb_data": sector_lhb,
            "hot_rank_count": hot_rank_count,
            "volume_change": sector_volume_change,
            "price_change": fund_flow.get("zdf", 0),
        }

    emit(f"   📊 板块匹配统计: {len(matched_sectors)}/{len(zt_sectors)} 个板块成功匹配资金流向（标准化后）")
    emit(f"   ✅ 匹配成功: {matched_sectors[:5]}")
    emit(f"   ❌ 匹配失败: {unmatched_sectors[:5]}")
    return sectors_data


def _safe_signal_value(signal, key):
    if isinstance(signal, dict):
        return signal.get(key)
    return getattr(signal, key, None)


def _backfill_volume_anomaly_price_change(volume_anomalies, quote_lookup):
    normalized = []

    for anomaly in volume_anomalies or []:
        if isinstance(anomaly, dict):
            patched = dict(anomaly)
            stock_code = str(patched.get("stock_code", patched.get("code", "")) or "").strip()
            stock_name = str(patched.get("stock_name", patched.get("name", "")) or "").strip()
            price_change = patched.get("price_change")
            matched = resolve_market_quote(quote_lookup, stock_code=stock_code, stock_name=stock_name)
            if matched and (price_change in (None, "") or float(price_change or 0) == 0.0):
                patched["price_change"] = matched.get("change_pct", 0)
            normalized.append(patched)
            continue

        stock_code = str(getattr(anomaly, "stock_code", getattr(anomaly, "code", "")) or "").strip()
        stock_name = str(getattr(anomaly, "stock_name", getattr(anomaly, "name", "")) or "").strip()
        price_change = getattr(anomaly, "price_change", None)
        matched = resolve_market_quote(quote_lookup, stock_code=stock_code, stock_name=stock_name)
        if matched and (price_change in (None, "") or float(price_change or 0) == 0.0):
            try:
                setattr(anomaly, "price_change", matched.get("change_pct", 0))
            except Exception:
                pass
        normalized.append(anomaly)

    return normalized


def build_market_activity_quant_signal_bundle(
    all_data,
    *,
    analyze_volume_anomaly,
    analyze_lhb,
    calculate_resonance,
    generate_trade_signals,
    timer,
    emit,
):
    all_data = all_data or {}
    results = {}
    module_logs = []
    stocks_with_history = all_data.get("stocks_with_history", []) or []
    market_quote_lookup = build_market_quote_lookup(
        stock_full_info=all_data.get("stock_full_info", {}),
        stocks_with_history=stocks_with_history,
        turnover_rank=all_data.get("turnover_rank", []),
        lianban_data=all_data.get("lianban_data", []),
        zt_pool=all_data.get("zt_pool", []),
        dt_pool=all_data.get("dt_pool", []),
    )

    emit("  1️⃣ 放量异常检测... (依赖: 候选池 - 连板梯队+热榜+龙虎榜)")
    try:
        if stocks_with_history:
            volume_anomalies = analyze_volume_anomaly(stocks_with_history, {})
            volume_anomalies = _backfill_volume_anomaly_price_change(volume_anomalies, market_quote_lookup)
            results["volume_anomalies"] = volume_anomalies
            emit(f"   ✅ 检测到 {len(volume_anomalies)} 个放量异常, 历史数据覆盖{len(stocks_with_history)}只")
            emit("   📊 调试信息（前3只股票）:")
            for index, stock in enumerate(stocks_with_history[:3], 1):
                current = stock.get("turnover", 0)
                history = stock.get("hist_turnover", [])
                avg_5d = sum(history[-5:]) / len(history[-5:]) if len(history) >= 5 else 0
                ratio = current / avg_5d if avg_5d > 0 else 0
                emit(
                    f"      {index}. {stock.get('name', '?')}: 当日{current:.1f}亿, "
                    f"5日均值{avg_5d:.1f}亿, 放量{ratio:.2f}倍"
                )
        else:
            emit("   ⚠️ 无成交额>50亿的候选股")
            results["volume_anomalies"] = []
    except Exception as error:
        emit(f"   ⚠️ 放量异常检测失败: {error}")
        results["volume_anomalies"] = []

    emit("  2️⃣ 龙虎榜深度分析... (依赖: 步骤13-龙虎榜数据)")
    try:
        lhb_analysis = analyze_lhb(
            (all_data.get("lhb_net_buy_top10", []) or []) + (all_data.get("lhb_net_sell_top10", []) or []),
            {},
        )
        results["lhb_analysis"] = lhb_analysis
        emit(f"   ✅ 分析 {len(lhb_analysis)} 只龙虎榜股票")
    except Exception as error:
        emit(f"   ⚠️ 龙虎榜分析失败: {error}")
        results["lhb_analysis"] = []

    emit("  3️⃣ 板块共振评分... (依赖: 步骤4-涨停池, 步骤7-板块资金流向)")
    sectors_data = {}
    try:
        sectors_data = _build_resonance_sector_payload(all_data, results.get("lhb_analysis", []), stocks_with_history, emit)
        resonance_scores = calculate_resonance(sectors_data)
        results["resonance_scores"] = resonance_scores
        emit(f"   ✅ 计算 {len(resonance_scores)} 个板块共振评分")
    except Exception as error:
        emit(f"   ⚠️ 共振评分失败: {error}")
        results["resonance_scores"] = {}

    emit("  4️⃣ 生成交易信号...")
    try:
        signal_payload = {
            "sectors": sectors_data,
            "stocks": stocks_with_history,
            "lhb": results.get("lhb_analysis", []),
            "lhb_history": {},
            "calendar": all_data.get("calendar", []),
            "sector_avg_volume": {},
        }
        trade_signals = generate_trade_signals(signal_payload)
        results["trade_signals"] = trade_signals
        elapsed, _ = timer.record("AI多维量化分析", 17)
        emit(f"   ✅ 生成 {len(trade_signals)} 个交易信号 [⏱ {elapsed:.2f}s]")
        preview_signals = trade_signals[:5] if isinstance(trade_signals, list) else []
        for index, signal in enumerate(preview_signals, 1):
            signal_type = _safe_signal_value(_safe_signal_value(signal, "signal_type"), "value")
            sector_name = _safe_signal_value(signal, "sector_name")
            action = _safe_signal_value(signal, "action")
            emit(f"      {index}. [{signal_type}] {sector_name} - {action}")
    except Exception as error:
        emit(f"   ⚠️ 交易信号生成失败: {error}")
        results["trade_signals"] = []

    _append_log(
        module_logs,
        "infer.quant_signals",
        "success",
        "已生成 market_activity 量化信号快照",
        volume_anomaly_count=len(results.get("volume_anomalies", []) or []),
        lhb_count=len(results.get("lhb_analysis", []) or []),
        resonance_count=len(results.get("resonance_scores", {}) or {}),
        signal_count=len(results.get("trade_signals", []) or []),
    )
    return {
        "results": results,
        "module_logs": module_logs,
    }
