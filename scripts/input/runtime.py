from __future__ import annotations

from domains.calendar_events.request import collect_calendar_events_request_bundle
from domains.market_activity.infer import (
    build_market_activity_quant_signal_bundle,
    build_market_activity_sector_analysis_bundle,
)
from domains.market_activity.request import (
    collect_market_activity_capital_snapshot_request_bundle,
    collect_market_activity_hot_rank_request_bundle,
    collect_market_activity_pool_request_bundle,
    collect_market_activity_sector_snapshot_request_bundle,
    collect_market_activity_stock_quote_request_bundle,
)
from domains.market_state.request import collect_market_state_request_bundle
from domains.monitoring.request import collect_monitoring_request_bundle
from domains.new_stock_calendar.request import (
    collect_new_stock_calendar_request_bundle,
    fetch_sina_new_stock_calendar_pages,
)
from domains.watch_candidates.infer import build_watch_candidate_pool_bundle
from domains.watch_candidates.request import collect_watch_candidate_history_request_bundle
from input.request_diagnostics_runtime import (
    build_request_diagnostics,
    render_request_diagnostics_lines,
)
from input.request_registry import build_input_request_registry, resolve_request_target_date
from selection.new_stock_narrative_runtime import build_new_stock_research_pool

__all__ = ["run_input_runtime"]

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


def run_input_runtime(target_date=None, *, helpers=None, config=None):
    bindings = {}
    bindings.update(helpers or {})
    bindings.update(config or {})
    previous = _install_runtime_bindings(bindings)
    try:
        return _run_input_runtime_legacy_body(target_date=target_date)
    finally:
        _restore_runtime_bindings(previous)


def _as_sequence(value):
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        for key in ("items", "data", "rows", "list", "inflow", "outflow"):
            nested = value.get(key)
            if isinstance(nested, (list, tuple, set)):
                return list(nested)
        return [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _extract_named_values(value):
    names = []
    for item in _as_sequence(value):
        if isinstance(item, dict):
            for key in (
                "name",
                "sector_name",
                "standard_sector",
                "standard_name",
                "primary_mainline",
                "leading_line",
                "mainline",
            ):
                if item.get(key):
                    names.append(item.get(key))
        elif item:
            names.append(item)
    return [str(name).strip() for name in names if str(name or "").strip()]


def _extend_unique(target, values):
    seen = set(target)
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            target.append(text)


def _derive_new_stock_context(results, fallback_mainline=""):
    results = results or {}
    market_research_snapshot = results.get("market_research_snapshot") or {}
    state_machine = market_research_snapshot.get("state_machine") or {}
    market_state_snapshot = results.get("market_state_snapshot") or {}
    current_mainline_history_record = results.get("current_mainline_history_record") or {}

    mainline_name = (
        current_mainline_history_record.get("primary_mainline")
        or state_machine.get("leading_line")
        or market_state_snapshot.get("leading_line")
        or fallback_mainline
        or ""
    )

    potential_mainlines = []
    _extend_unique(potential_mainlines, _extract_named_values(state_machine.get("mainline_candidates")))
    _extend_unique(
        potential_mainlines,
        [
            current_mainline_history_record.get("leading_line"),
            current_mainline_history_record.get("primary_mainline"),
            state_machine.get("leading_line"),
            market_state_snapshot.get("leading_line"),
            mainline_name,
        ],
    )

    sector_ai_analysis = results.get("sector_ai_analysis") or {}
    _extend_unique(potential_mainlines, _extract_named_values(sector_ai_analysis.get("standard_sectors")))
    _extend_unique(potential_mainlines, _extract_named_values(results.get("hot_plates")))
    _extend_unique(potential_mainlines, _extract_named_values(results.get("sector_change_up")))

    sector_fund_flow = results.get("sector_fund_flow") or {}
    if isinstance(sector_fund_flow, dict):
        inflow_rows = sector_fund_flow.get("inflow") or []
    else:
        inflow_rows = sector_fund_flow
    _extend_unique(potential_mainlines, _extract_named_values(inflow_rows))

    context = {
        "mainline_name": mainline_name,
        "potential_mainlines": potential_mainlines,
        "new_stock_profiles": results.get("new_stock_profiles", {}),
    }

    for key in ("new_stock_money_making_effect", "recent_new_stock_money_making_effect"):
        if key in results:
            context[key] = results.get(key)

    support_names = []
    _extend_unique(support_names, _extract_named_values(results.get("hot_plates")))
    _extend_unique(support_names, _extract_named_values(results.get("sector_change_up")))
    _extend_unique(support_names, _extract_named_values(inflow_rows))
    if support_names:
        context["sector_resonance"] = {
            "supported_sectors": support_names,
            "score": min(10, 7 + len(support_names)),
            "source": "hot_plates/sector_change_up/sector_fund_flow",
        }

    return context


def _run_input_runtime_legacy_body(target_date=None):
    """
    获取指定日期的A股市场数据 - 严格按照SKILL.md声明
    
    Args:
        target_date: 目标日期字符串，格式 "YYYY-MM-DD"
                    如果为None，则获取前一天的数据
    """
    # 初始化计时器
    timer = StepTimer()
    timer.start()
    
    print("🚀 A股日报数据获取入口 - SKILL.md对齐版", flush=True)
    print("=" * 60, flush=True)
    
    # ========== 初始化状态跟踪字典 ==========
    data_status = {}  # 数据获取状态
    step_status = {}  # 执行步骤状态
    module_logs = []
    
    # 确定目标日期并初始化首批请求注册表
    request_registry = build_input_request_registry(globals())
    target_date = resolve_request_target_date(target_date)
    
    print("📅 目标日期: {}".format(target_date), flush=True)
    print("=" * 60, flush=True)
    
    # 创建数据收集器
    collector = AShareDataCollector()
    tencent = TencentFinanceData()
    
    print("🔍 开始获取市场数据...", flush=True)
    
    results = {}
    
    try:
        market_state_request_result = collect_market_state_request_bundle(
            target_date,
            request_registry=request_registry,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_state_request_result.get("results", {}))
        data_status.update(market_state_request_result.get("data_status", {}))
        step_status.update(market_state_request_result.get("step_status", {}))
        module_logs.extend(market_state_request_result.get("module_logs", []))

        def _fetch_market_activity_df():
            import akshare as ak

            return ak.stock_market_activity_legu()

        market_activity_pool_result = collect_market_activity_pool_request_bundle(
            target_date,
            get_limit_up_pool=get_limit_up_pool,
            get_limit_down_pool=get_limit_down_pool,
            fetch_market_activity_df=_fetch_market_activity_df,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_pool_result.get("results", {}))
        data_status.update(market_activity_pool_result.get("data_status", {}))
        step_status.update(market_activity_pool_result.get("step_status", {}))
        module_logs.extend(market_activity_pool_result.get("module_logs", []))
        market_activity_pool_artifacts = market_activity_pool_result.get("artifacts", {}) or {}
        limit_up_df = market_activity_pool_artifacts.get("limit_up_df")
        limit_down_df = market_activity_pool_artifacts.get("limit_down_df")

        market_activity_hot_rank_result = collect_market_activity_hot_rank_request_bundle(
            target_date,
            existing_results=results,
            fetch_ths_hot_stock=fetch_ths_hot_stock,
            get_integrated_hot_list=get_integrated_hot_list,
            tencent=tencent,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_hot_rank_result.get("results", {}))
        data_status.update(market_activity_hot_rank_result.get("data_status", {}))
        step_status.update(market_activity_hot_rank_result.get("step_status", {}))
        module_logs.extend(market_activity_hot_rank_result.get("module_logs", []))
        
        import datetime as _dt

        current_dates = (
            _dt.datetime.now().strftime("%Y-%m-%d"),
            (_dt.datetime.now() - _dt.timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        market_activity_sector_result = collect_market_activity_sector_snapshot_request_bundle(
            target_date,
            fetch_hot_plate=fetch_hot_plate,
            tencent=tencent,
            get_sector_change_from_iwencai=get_sector_change_from_iwencai,
            get_turnover_rank_from_iwencai=get_turnover_rank_from_iwencai,
            request_registry=request_registry,
            timer=timer,
            emit=lambda message: print(message, flush=True),
            current_dates=current_dates,
        )
        results.update(market_activity_sector_result.get("results", {}))
        data_status.update(market_activity_sector_result.get("data_status", {}))
        step_status.update(market_activity_sector_result.get("step_status", {}))
        module_logs.extend(market_activity_sector_result.get("module_logs", []))
        
        calendar_events_result = collect_calendar_events_request_bundle(
            target_date,
            fetch_calendar_events=lambda target_date=None: tencent.get_calendar_events(target_date=target_date),
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(calendar_events_result.get("results", {}))
        data_status.update(calendar_events_result.get("data_status", {}))
        step_status.update(calendar_events_result.get("step_status", {}))
        module_logs.extend(calendar_events_result.get("module_logs", []))

        new_stock_calendar_result = collect_new_stock_calendar_request_bundle(
            target_date,
            fetch_pages=fetch_sina_new_stock_calendar_pages,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(new_stock_calendar_result.get("results", {}))
        data_status.update(new_stock_calendar_result.get("data_status", {}))
        step_status.update(new_stock_calendar_result.get("step_status", {}))
        module_logs.extend(new_stock_calendar_result.get("module_logs", []))

        try:
            new_stock_research_result = build_new_stock_research_pool(
                results.get("new_stock_calendar", []),
                target_date=target_date,
                context=_derive_new_stock_context(results),
            )
            results.update(new_stock_research_result or {})
        except Exception as error:
            results["new_stock_research_pool"] = []
            results["new_stock_candidate_upgrades"] = []
            module_logs.append(
                {
                    "module": "selection.new_stock_narrative_runtime",
                    "step": "request.new_stock_scoring",
                    "status": "error",
                    "message": "新股研究池评分失败",
                    "details": {
                        "target_keys": [
                            "new_stock_research_pool",
                            "new_stock_candidate_upgrades",
                        ],
                        "error": str(error),
                    },
                }
            )

        def _fetch_exchange_monitor_payload():
            import requests

            url = "https://stock.quicktiny.cn/api/ladder/exchange-monitor/prediction"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                raise RuntimeError(f"exchange monitor status {response.status_code}")
            return response.json()

        monitoring_result = collect_monitoring_request_bundle(
            target_date,
            analyzer_factory=XuangubaoIntradayAnalyzer,
            fetch_wanzhu_top10=collector.get_wanzhu_top10,
            fetch_exchange_monitor_payload=_fetch_exchange_monitor_payload,
            fetch_stock_batch_info=lambda codes: TencentFinanceData().get_stock_batch_info(codes),
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(monitoring_result.get("results", {}))
        data_status.update(monitoring_result.get("data_status", {}))
        step_status.update(monitoring_result.get("step_status", {}))
        module_logs.extend(monitoring_result.get("module_logs", []))

        def _fetch_lhb_rows(request_target_date):
            from finshare import get_lhb

            lhb_date = str(request_target_date or "").replace("-", "")
            lhb_df = get_lhb(start_date=lhb_date, end_date=lhb_date)
            if lhb_df is None or len(lhb_df) == 0:
                return []
            return lhb_df.to_dict("records")

        market_activity_capital_result = collect_market_activity_capital_snapshot_request_bundle(
            target_date,
            limit_up_df=limit_up_df,
            existing_results=results,
            fetch_lhb_rows=_fetch_lhb_rows,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_capital_result.get("results", {}))
        data_status.update(market_activity_capital_result.get("data_status", {}))
        step_status.update(market_activity_capital_result.get("step_status", {}))
        module_logs.extend(market_activity_capital_result.get("module_logs", []))

        # 原始代码（暂时注释）
        '''
        try:
            import finshare as fs
            import requests

            # 获取龙虎榜数据
            lhb_date = target_date.replace('-', '')
            print(f"   📅 调用finshare.get_lhb({lhb_date})...")
            sys.stdout.flush()
            df = fs.get_lhb(lhb_date, lhb_date)
            print(f"   ✅ 龙虎榜数据获取完成: {len(df)}条")
            sys.stdout.flush()

            if df.empty:
                results['lhb_net_buy_top10'] = []
                results['lhb_net_sell_top10'] = []
                print("   ⚠️ 龙虎榜数据为空", flush=True)
            else:
                print(f"   📊 开始排序龙虎榜数据...")
                # 净买入前10
                df_sorted_buy = df.sort_values('net_buy_amount', ascending=False)
                top10_buy = df_sorted_buy.head(10)
                print(f"   ✅ 净买入前10筛选完成")

                # 净流出前10（净买入为负的，取绝对值最大的10个）
                df_sorted_sell = df.sort_values('net_buy_amount', ascending=True)
                top10_sell = df_sorted_sell.head(10)
                print(f"   ✅ 净流出前10筛选完成")

                # 提取所有股票代码
                print(f"   📝 提取股票代码...")
                buy_codes = [str(row['fs_code']).replace('.SZ', '').replace('.SH', '') for _, row in top10_buy.iterrows()]
                sell_codes = [str(row['fs_code']).replace('.SZ', '').replace('.SH', '') for _, row in top10_sell.iterrows()]
                all_codes = list(set(buy_codes + sell_codes))
                print(f"   ✅ 提取完成: {len(all_codes)} 只股票")

                # 批量获取股票信息（名称、涨跌幅、涨停状态）
                print(f"   📡 腾讯API批量查询 {len(all_codes)} 只股票...")
                codes_with_market = []
                for code in all_codes:
                    if code.startswith('6'):
                        codes_with_market.append(f'sh{code}')
                    else:
                        codes_with_market.append(f'sz{code}')

                # 腾讯API批量查询
                url = f"http://qt.gtimg.cn/q={','.join(codes_with_market)}"
                response = requests.get(url, timeout=10)
                response.encoding = 'gbk'
                lines = response.text.strip().split('\n')
                print(f"   ✅ 腾讯API返回 {len(lines)} 行数据")

                stock_info = {}
                for line in lines:
                    if not line.startswith('v_'):
                        continue
                    parts = line.split('~')
                    if len(parts) < 35:
                        continue

                    code = parts[2]
                    name = parts[1]
                    change_pct = float(parts[32])
                    zt_status = '涨停' if change_pct >= 9.9 else ('跌停' if change_pct <= -9.9 else '正常')

                    stock_info[code] = {
                        'name': name,
                        'change_pct': round(change_pct, 2),
                        'zt_status': zt_status
                    }

                # 构建净买入前10
                print(f"   📊 构建龙虎榜净买入前10...")
                lhb_net_buy = []
                for rank, (_, row) in enumerate(top10_buy.iterrows(), 1):
                    stock_code = str(row['fs_code']).replace('.SZ', '').replace('.SH', '')
                    info = stock_info.get(stock_code, {})
                    stock_name = info.get('name', '')

                    # 使用get_stock_sector获取板块（跳过API调用，避免批量处理卡死）
                    sector = get_stock_sector(
                        stock_name,
                        stock_code,
                        hot_rank_data=results.get('hot_rank_top30'),
                        zt_pool_data=results.get('zt_pool_by_sector'),
                        zt_pool_raw=results.get('zt_pool'),
                        dt_pool_raw=results.get('dt_pool'),
                        lianban_data=results.get('lianban_data'),
                        lhb_data=None,  # 避免循环
                        sector_fund_flow=results.get('sector_fund_flow'),
                        skip_api_call=True  # 跳过东方财富API调用
                    )
                    print(f"      {rank}. {stock_name}({stock_code}) - 板块: {sector}")

                    item = {
                        'rank': rank,
                        'code': stock_code,
                        'net_buy_amount_yi': row['net_buy_amount'] / 100000000,
                        'name': stock_name,
                        'change_pct': info.get('change_pct', 0),
                        'zt_status': info.get('zt_status', '正常'),
                        'sector': sector
                    }
                    lhb_net_buy.append(item)

                # 构建净流出前10
                print(f"   📊 构建龙虎榜净流出前10...")
                lhb_net_sell = []
                for rank, (_, row) in enumerate(top10_sell.iterrows(), 1):
                    stock_code = str(row['fs_code']).replace('.SZ', '').replace('.SH', '')
                    info = stock_info.get(stock_code, {})
                    stock_name = info.get('name', '')

                    # 使用get_stock_sector获取板块（跳过API调用，避免批量处理卡死）
                    sector = get_stock_sector(
                        stock_name,
                        stock_code,
                        hot_rank_data=results.get('hot_rank_top30'),
                        zt_pool_data=results.get('zt_pool_by_sector'),
                        zt_pool_raw=results.get('zt_pool'),
                        dt_pool_raw=results.get('dt_pool'),
                        lianban_data=results.get('lianban_data'),
                        lhb_data=None,  # 避免循环
                        sector_fund_flow=results.get('sector_fund_flow'),
                        skip_api_call=True  # 跳过东方财富API调用
                    )
                    print(f"      {rank}. {stock_name}({stock_code}) - 板块: {sector}")

                    item = {
                        'rank': rank,
                        'code': stock_code,
                        'net_sell_amount_yi': abs(row['net_buy_amount']) / 100000000,
                        'name': stock_name,
                        'change_pct': info.get('change_pct', 0),
                        'zt_status': info.get('zt_status', '正常'),
                        'sector': sector
                    }
                    lhb_net_sell.append(item)

                results['lhb_net_buy_top10'] = lhb_net_buy
                results['lhb_net_sell_top10'] = lhb_net_sell
                elapsed, cum = timer.record("龙虎榜数据获取", 13)
                print(f"   ✅ 龙虎榜净买入前十: {len(lhb_net_buy)} 只")
                print(f"   ✅ 龙虎榜净流出前十: {len(lhb_net_sell)} 只 [⏱ {elapsed:.2f}s]")
        except Exception as e:
            elapsed, cum = timer.record("龙虎榜数据获取(失败)", 13)
            print(f"   ⚠️ 龙虎榜失败: {e} [⏱ {elapsed:.2f}s]")
            import traceback
            traceback.print_exc()
            results['lhb_net_buy_top10'] = []
            results['lhb_net_sell_top10'] = []
        '''
        market_activity_quote_result = collect_market_activity_stock_quote_request_bundle(
            existing_results=results,
            fetch_stock_batch_info=lambda codes: TencentFinanceData().get_stock_batch_info(codes),
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_quote_result.get("results", {}))
        module_logs.extend(market_activity_quote_result.get("module_logs", []))

        print("\n🎉 所有数据获取完成!", flush=True)
        
        # ========== 全局板块AI分析 ==========
        print("\n🧠 进行全局板块AI分析...", flush=True)
        market_activity_sector_analysis_result = build_market_activity_sector_analysis_bundle(
            results,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_sector_analysis_result.get("results", {}))
        module_logs.extend(market_activity_sector_analysis_result.get("module_logs", []))
        
        # ========== 15. AI多维量化分析（升级版）==========
        print("\n🔬 进行AI多维量化分析... (依赖: 步骤4, 步骤7, 步骤9, 步骤13)", flush=True)

        watch_candidate_result = build_watch_candidate_pool_bundle(
            results,
            emit=lambda message: print(message, flush=True),
        )
        results.update(watch_candidate_result.get("results", {}))
        module_logs.extend(watch_candidate_result.get("module_logs", []))

        def _fetch_quicktiny_history(*, full_code, code, target_date, days=30):
            import requests

            url = f"https://stock.quicktiny.cn/api/tushare/merged-kline/{full_code}?days={days}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success") or not payload.get("data"):
                return []

            amounts = []
            target_date_compact = str(target_date or "").replace("-", "")
            for item in payload.get("data", []):
                bar_date = item.get("date", "")
                if bar_date and bar_date <= target_date_compact:
                    amount = item.get("amount") or 0
                    if amount:
                        amounts.append(float(amount) / 1e8)
            return amounts

        def _baostock_source_factory():
            from finshare.sources.baostock_source import BaoStockDataSource

            return BaoStockDataSource()

        watch_candidate_history_result = collect_watch_candidate_history_request_bundle(
            target_date,
            candidates=results.get("candidates", []),
            stock_full_info=results.get("stock_full_info", {}),
            get_cache=get_cache,
            fetch_quicktiny_history=_fetch_quicktiny_history,
            baostock_source_factory=_baostock_source_factory,
            timer=timer,
            emit=lambda message: print(message, flush=True),
            enable_live_quicktiny=False,
            enable_baostock_fallback=False,
        )
        results.update(watch_candidate_history_result.get("results", {}))
        module_logs.extend(watch_candidate_history_result.get("module_logs", []))

        market_activity_quant_result = build_market_activity_quant_signal_bundle(
            results,
            analyze_volume_anomaly=analyze_volume_anomaly,
            analyze_lhb=analyze_lhb,
            calculate_resonance=calculate_resonance,
            generate_trade_signals=generate_trade_signals,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_quant_result.get("results", {}))
        module_logs.extend(market_activity_quant_result.get("module_logs", []))

        print("   ✅ AI多维量化分析完成!", flush=True)
        
        # ========== 数据摘要 ==========
        print("\n" + "=" * 60)
        print("📊 数据摘要", flush=True)
        print("=" * 60)
        print(f"💰 两市总成交额: {results['total_turnover']:.2f}亿元")
        
        if results.get('indices'):
            print("📈 主要指数:", flush=True)
            for name, data in results['indices'].items():
                price = data.get('点位', data.get('price', 0))
                change_pct = data.get('涨跌幅', data.get('change_pct', 0))
                print(f"  {name}: {price:.2f}点 ({change_pct:+.2f}%)")
        
        if results.get('wind_a_alternative'):
            wa = results['wind_a_alternative']
            print(f"🌐 中证全指(Wind全A平替): {wa.get('点位', wa.get('price', 0)):.2f}点 ({wa.get('涨跌幅', wa.get('change_pct', 0)):+.2f}%)")
        
        if results.get('hot_rank_top30'):
            print(f"🔥 热度前三十: {len(results['hot_rank_top30'])} 只")
        
        if results.get('hot_plates'):
            print(f"📊 板块热榜: {len(results['hot_plates'])} 条")
        
        if results.get('zt_pool'):
            print(f"📈 涨停池: {len(results['zt_pool'])} 只")
        
        if results.get('dt_pool'):
            print(f"📉 跌停池: {len(results['dt_pool'])} 只")
        
        if results.get('sector_fund_flow'):
            print(f"💹 行业资金流向: {len(results['sector_fund_flow'])} 条")
        
        if results.get('sector_change_up'):
            print(f"📊 涨幅前10板块: {len(results['sector_change_up'])} 条")
        
        if results.get('sector_change_down'):
            print(f"📊 跌幅前10板块: {len(results['sector_change_down'])} 条")
        
        if results.get('turnover_rank'):
            print(f"💵 成交额排名: {len(results['turnover_rank'])} 条")
        
        if results.get('calendar_events'):
            print(f"📅 预期日历: {len(results['calendar_events'])} 条")
        
        if results.get('xuangubao_data') and results['xuangubao_data'].get('xuangubao_news'):
            print(f"📡 选股通异动: {len(results['xuangubao_data'].get('xuangubao_news', []))} 条新闻")
        
        if results.get('wanzhu_top10'):
            print(f"🏆 顽主杯前十: {len(results['wanzhu_top10'])} 只")
        
        if results.get('lhb_net_buy_top10'):
            print(f"🐉 龙虎榜净买入前十: {len(results['lhb_net_buy_top10'])} 只")
        
        # ========== 18. 板块四象限数据（击球区分析）==========
        step_status['板块四象限数据获取'] = False
        print("  1️⃣5️⃣ 获取板块四象限数据（击球区分析）...", flush=True)
        try:
            quadrant_data = get_sector_quadrant_data(period=20, strength_period=3)
            if quadrant_data:
                results['sector_quadrant'] = quadrant_data
                hs_analysis = quadrant_data['high_strong_analysis']
                print(f"   ✅ 板块四象限数据获取成功")
                print(f"   📊 高强区间: {hs_analysis['total']}个板块")
                print(f"      🏆 最佳击球区（≥80分）: {hs_analysis['tier1_count']}个")
                print(f"      ⭐ 优质击球区（60-79分）: {hs_analysis['tier2_count']}个")
                print(f"      ✓ 普通击球区（40-59分）: {hs_analysis['tier3_count']}个")
                print(f"      ⚠️ 边缘击球区（<40分）: {hs_analysis['tier4_count']}个")
                step_status['板块四象限数据获取'] = True
                data_status['板块四象限'] = True
            else:
                print(f"   ⚠️ 板块四象限数据获取失败")
                data_status['板块四象限'] = False
        except Exception as e:
            print(f"   ⚠️ 板块四象限数据获取异常: {e}")
            data_status['板块四象限'] = False
        
        # ========== 添加状态跟踪字典到结果 ==========
        results['data_status'] = data_status
        results['step_status'] = step_status
        request_diagnostics = build_request_diagnostics(module_logs, data_status=data_status, step_status=step_status)
        results["request_diagnostics"] = request_diagnostics

        for line in render_request_diagnostics_lines(request_diagnostics):
            print(line, flush=True)
        
        # 打印状态统计
        print("\n" + "=" * 60)
        print("📊 数据获取状态统计", flush=True)
        print("=" * 60)
        success_count = sum(1 for v in data_status.values() if v)
        total_count = len(data_status)
        print(f"数据源获取成功: {success_count}/{total_count}")
        for key, value in data_status.items():
            status_icon = "✅" if value else "❌"
            print(f"  {status_icon} {key}")
        
        print("\n" + "=" * 60)
        print("📋 执行步骤状态统计", flush=True)
        print("=" * 60)
        step_success_count = sum(1 for v in step_status.values() if v)
        step_total_count = len(step_status)
        print(f"步骤执行成功: {step_success_count}/{step_total_count}")
        for key, value in step_status.items():
            status_icon = "✅" if value else "❌"
            print(f"  {status_icon} {key}")
        
        # 打印计时摘要
        timer.print_summary()
        
        # 打印LLM调用统计
        llm_stats = get_llm_call_stats()
        if llm_stats['total_calls'] > 0:
            print("\n" + "=" * 80)
            print("LLM调用统计", flush=True)
            print("-" * 80)
            print(f"{'类型':<30} {'调用次数':>10} {'总耗时':>12} {'平均耗时':>12}")
            print("-" * 80)
            if llm_stats['event_analysis_calls'] > 0:
                avg_time = llm_stats['event_analysis_time'] / llm_stats['event_analysis_calls']
                print(f"{'事件板块分析':<30} {llm_stats['event_analysis_calls']:>10} {llm_stats['event_analysis_time']:>11.2f}s {avg_time:>11.2f}s")
            if llm_stats['sector_analysis_calls'] > 0:
                avg_time = llm_stats['sector_analysis_time'] / llm_stats['sector_analysis_calls']
                print(f"{'板块关系分析':<30} {llm_stats['sector_analysis_calls']:>10} {llm_stats['sector_analysis_time']:>11.2f}s {avg_time:>11.2f}s")
            print("-" * 80)
            avg_total = llm_stats['total_time'] / llm_stats['total_calls']
            print(f"{'总计':<30} {llm_stats['total_calls']:>10} {llm_stats['total_time']:>11.2f}s {avg_total:>11.2f}s")
            print("=" * 80)
        
        # 将计时数据保存到results中供报告使用
        results['timer_summary'] = timer.get_summary()
        results['llm_stats'] = llm_stats
        
        # 将状态跟踪数据保存到results中供报告使用
        results['data_status'] = data_status
        results['step_status'] = step_status
        results['module_logs'] = module_logs
        results["request_diagnostics"] = request_diagnostics
        
        return results
        
    except Exception as e:
        print(f"\n❌ 数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        results["request_diagnostics"] = build_request_diagnostics(module_logs, data_status=data_status, step_status=step_status)
        return results
