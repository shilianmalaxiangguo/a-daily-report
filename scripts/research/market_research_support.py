from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from domains.market_activity.limit_pool_facts import resolve_limit_down_count
from report.execution_wording import TWO_B_CONFIRMATION_CLAUSE
from domains.market_state.mainline_history_runtime import (
    build_mainline_history_record as build_mainline_history_record_runtime,
    load_recent_mainline_history as load_recent_mainline_history_runtime,
)
from domains.market_state.mainline_turnover_summary_runtime import (
    build_mainline_turnover_summary as build_mainline_turnover_summary_runtime,
)
from domains.market_state.sector_turnover_history_runtime import (
    load_recent_sector_turnover_history as load_recent_sector_turnover_history_runtime,
)
from input.ths_sector_runtime import (
    get_sector_turnover_snapshot_from_ths as get_sector_turnover_snapshot_from_ths_runtime,
)
from input.tencent_sector_runtime import (
    get_sector_turnover_snapshot_from_tencent_fund_flow as get_sector_turnover_snapshot_from_tencent_fund_flow_runtime,
)
from report.market_research_renderer import (
    render_market_research_snapshot_section as render_market_research_snapshot_section_renderer,
    render_step0_follow_section as render_step0_follow_section_renderer,
)
from research.market_research_context_bundle import build_market_research_context_bundle_contract
from research.market_research_runtime import (
    build_market_research_snapshot_contract,
    derive_step0_follow_plan_contract,
)
from storage.database_service import DatabaseService

__all__ = [
    "build_abnormal_projection_summary",
    "build_mainline_rotation_snapshot",
    "build_mainline_competition_snapshot",
    "build_market_research_context_bundle",
    "build_dialectical_decision_snapshot",
    "build_follow_verdict",
    "build_market_observation_snapshot",
    "build_market_research_snapshot",
    "derive_step0_follow_plan",
    "get_market_daily_total_from_fact_db_runtime",
    "get_market_breadth_from_fact_db_runtime",
    "get_market_total_turnover_from_fact_db_runtime",
    "get_turnover_rank_from_fact_db_runtime",
    "render_market_research_snapshot_section",
    "render_step0_follow_section",
]

_MISSING = object()
_NON_DIRECTIONAL_SECTOR_LABELS = {
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


def _is_directional_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_DIRECTIONAL_SECTOR_LABELS)


def _first_directional_trend_item(items):
    for item in items or []:
        if isinstance(item, dict) and _is_directional_sector_label(item.get("sector")):
            return item
    return {}


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _optional_market_float(value):
    try:
        if value in (None, ""):
            return None
        text = str(value).strip()
        if ":" in text:
            text = text.split(":", 1)[0]
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_heavy_turnover_selloff(observation, style_switch):
    observation = observation or {}
    style_switch = style_switch or {}
    benchmark_change = _optional_market_float(
        observation.get("benchmark_change_pct", observation.get("benchmark_change"))
    )
    dt_count = int(_safe_float(observation.get("dt_count", 0)))
    rise_fall_ratio = _optional_market_float(observation.get("rise_fall_ratio"))
    if rise_fall_ratio is None:
        rise_fall_ratio = _optional_market_float(observation.get("rise_fall_ratio_text"))
    turnover = _safe_float(observation.get("turnover", observation.get("total_turnover", 0.0)))
    turnover_state = str(style_switch.get("turnover_state", "") or "").strip()
    turnover_label = str(style_switch.get("turnover_label", "") or "").strip()
    turnover_is_expanding = turnover_state in ("rising", "rebound") or any(
        keyword in turnover_label for keyword in ("回升", "放大")
    )
    breadth_broken = dt_count >= 30 or (rise_fall_ratio is not None and rise_fall_ratio < 0.4)
    return bool(
        benchmark_change is not None
        and benchmark_change <= -1.5
        and turnover > 0
        and turnover_is_expanding
        and breadth_broken
    )


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def get_market_total_turnover_from_fact_db_runtime(target_date, *, market_scope="all_a", db_path=None):
    row = get_market_daily_total_from_fact_db_runtime(target_date, market_scope=market_scope, db_path=db_path)
    return _safe_float((row or {}).get("total_amount_yi"))


def get_market_daily_total_from_fact_db_runtime(target_date, *, market_scope="all_a", db_path=None):
    try:
        service_factory = getattr(DatabaseService, "fact_store_from_environment", None)
        service = service_factory(db_path) if callable(service_factory) else DatabaseService.from_environment(db_path)
        row = service.query_market_daily_total(target_date, market_scope=market_scope)
    except Exception:
        return {}
    return dict(row or {})


def get_market_breadth_from_fact_db_runtime(target_date, *, db_path=None):
    try:
        service_factory = getattr(DatabaseService, "fact_store_from_environment", None)
        service = service_factory(db_path) if callable(service_factory) else DatabaseService.from_environment(db_path)
        row = service.query_market_breadth_counts(target_date)
    except Exception:
        return {}
    return dict(row or {})


def get_turnover_rank_from_fact_db_runtime(target_date, *, limit=50, rank_scope="all_a", db_path=None):
    try:
        service_factory = getattr(DatabaseService, "fact_store_from_environment", None)
        service = service_factory(db_path) if callable(service_factory) else DatabaseService.from_environment(db_path)
        rows = service.query_turnover_rank_rows(target_date, limit=limit, rank_scope=rank_scope)
    except Exception:
        return []

    ranked = []
    for index, row in enumerate(rows or [], start=1):
        row = row or {}
        stock_code = str(row.get("stock_code") or "").strip()
        ts_code = str(row.get("ts_code") or "").strip().upper()
        code = stock_code or (ts_code.split(".", 1)[0] if "." in ts_code else ts_code)
        turnover = _safe_float(row.get("amount_yi"))
        if not code or turnover <= 0:
            continue
        ranked.append(
            {
                "rank": int(row.get("rank_no") or index),
                "code": code,
                "name": str(row.get("name") or code).strip(),
                "turnover": turnover,
                "change_pct": _safe_float(row.get("pct_chg")),
                "sector": str(row.get("sector") or "未知").strip() or "未知",
                "data_source": "tushare.daily",
                "trade_date": row.get("trade_date") or target_date,
            }
        )
    return ranked


def save_market_cycle_context_runtime(target_date, snapshot, *, db_path=None):
    try:
        service_factory = getattr(DatabaseService, "fact_store_from_environment", None)
        service = service_factory(db_path) if callable(service_factory) else DatabaseService.from_environment(db_path)
        return service.replace_market_cycle_context(target_date, snapshot)
    except Exception:
        return {}


def save_observation_pools_runtime(target_date, pools, *, db_path=None):
    try:
        service_factory = getattr(DatabaseService, "fact_store_from_environment", None)
        service = service_factory(db_path) if callable(service_factory) else DatabaseService.from_environment(db_path)
        return service.replace_observation_pool_items_for_trade_date(target_date, pools)
    except Exception:
        return 0


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


def build_market_research_snapshot(
    data,
    final_gate,
    position_level,
    exit_analysis,
    observation_snapshot=None,
    target_date="",
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_market_research_snapshot_legacy_body(
            data,
            final_gate,
            position_level,
            exit_analysis,
            observation_snapshot=observation_snapshot,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_abnormal_projection_summary(abnormal_watch_pool=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_abnormal_projection_summary_legacy_body(abnormal_watch_pool=abnormal_watch_pool)
    finally:
        _restore_runtime_bindings(previous)


def _build_abnormal_projection_summary(abnormal_watch_pool=None):
    return build_abnormal_projection_summary(abnormal_watch_pool=abnormal_watch_pool)


def build_mainline_competition_snapshot(
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    risk_sectors=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_mainline_competition_snapshot_legacy_body(
            main_sectors_info=main_sectors_info,
            secondary_sectors_info=secondary_sectors_info,
            sector_trend_snapshot=sector_trend_snapshot,
            risk_sectors=risk_sectors,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_mainline_competition_snapshot(
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    risk_sectors=None,
):
    return build_mainline_competition_snapshot(
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        sector_trend_snapshot=sector_trend_snapshot,
        risk_sectors=risk_sectors,
    )


def build_mainline_rotation_snapshot(
    observation=None,
    state_machine=None,
    style_switch=None,
    sector_ai_analysis=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_mainline_rotation_snapshot_legacy_body(
            observation=observation,
            state_machine=state_machine,
            style_switch=style_switch,
            sector_ai_analysis=sector_ai_analysis,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_mainline_rotation_snapshot(
    observation=None,
    state_machine=None,
    style_switch=None,
    sector_ai_analysis=None,
):
    return build_mainline_rotation_snapshot(
        observation=observation,
        state_machine=state_machine,
        style_switch=style_switch,
        sector_ai_analysis=sector_ai_analysis,
    )


def build_dialectical_decision_snapshot(
    observation=None,
    style_switch=None,
    state_machine=None,
    follow_verdict=None,
    final_gate=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_dialectical_decision_snapshot_legacy_body(
            observation=observation,
            style_switch=style_switch,
            state_machine=state_machine,
            follow_verdict=follow_verdict,
            final_gate=final_gate,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_dialectical_decision_snapshot(
    observation=None,
    style_switch=None,
    state_machine=None,
    follow_verdict=None,
    final_gate=None,
):
    return build_dialectical_decision_snapshot(
        observation=observation,
        style_switch=style_switch,
        state_machine=state_machine,
        follow_verdict=follow_verdict,
        final_gate=final_gate,
    )


def build_market_observation_snapshot(
    data,
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    abnormal_watch_pool=None,
    leader_memory_bank=None,
    tracking_memory_status=None,
    mainline_competition_snapshot=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_market_observation_snapshot_legacy_body(
            data,
            main_sectors_info=main_sectors_info,
            secondary_sectors_info=secondary_sectors_info,
            sector_trend_snapshot=sector_trend_snapshot,
            abnormal_watch_pool=abnormal_watch_pool,
            leader_memory_bank=leader_memory_bank,
            tracking_memory_status=tracking_memory_status,
            mainline_competition_snapshot=mainline_competition_snapshot,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_follow_verdict(final_gate, position_level, state_machine_snapshot, special_probe_verdict=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_follow_verdict_legacy_body(
            final_gate,
            position_level,
            state_machine_snapshot,
            special_probe_verdict=special_probe_verdict,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_follow_verdict(final_gate, position_level, state_machine_snapshot, special_probe_verdict=None):
    return build_follow_verdict(
        final_gate,
        position_level,
        state_machine_snapshot,
        special_probe_verdict=special_probe_verdict,
    )


def derive_step0_follow_plan(market_research_snapshot, final_gate, position_level, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _derive_step0_follow_plan_legacy_body(
            market_research_snapshot,
            final_gate,
            position_level,
        )
    finally:
        _restore_runtime_bindings(previous)


def render_market_research_snapshot_section(market_research_snapshot, compact=False, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _render_market_research_snapshot_section_legacy_body(
            market_research_snapshot,
            compact=compact,
        )
    finally:
        _restore_runtime_bindings(previous)


def render_step0_follow_section(step0_plan, market_research_snapshot, compact=False, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _render_step0_follow_section_legacy_body(
            step0_plan,
            market_research_snapshot,
            compact=compact,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_market_research_context_bundle(
    data,
    target_date,
    exit_analysis,
    final_gate,
    position_level,
    main_sectors_info=None,
    secondary_sectors_info=None,
    main_sectors=None,
    secondary_sectors=None,
    dragon_stocks=None,
    decision_strict_mode=None,
    allow_display_degraded_abnormal_snapshot=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_market_research_context_bundle_legacy_body(
            data,
            target_date,
            exit_analysis,
            final_gate,
            position_level,
            main_sectors_info=main_sectors_info,
            secondary_sectors_info=secondary_sectors_info,
            main_sectors=main_sectors,
            secondary_sectors=secondary_sectors,
            dragon_stocks=dragon_stocks,
            decision_strict_mode=decision_strict_mode,
            allow_display_degraded_abnormal_snapshot=allow_display_degraded_abnormal_snapshot,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_market_research_snapshot_legacy_body(
    data,
    final_gate,
    position_level,
    exit_analysis,
    observation_snapshot=None,
    target_date="",
):
    postgres_only = bool(globals().get("postgres_only_runtime") or (data or {}).get("postgres_only"))

    def _load_recent_mainline_history(target_date, lookback_days=5, max_scan_days=20):
        if not postgres_only:
            try:
                return load_recent_mainline_history_runtime(
                    target_date,
                    lookback_days=lookback_days,
                    max_scan_days=max_scan_days,
                )
            except TypeError:
                return load_recent_mainline_history_runtime(target_date, lookback_days=lookback_days)
        return load_recent_mainline_history_runtime(
            target_date,
            lookback_days=lookback_days,
            max_scan_days=max_scan_days,
            helpers={"postgres_only_runtime": True} if postgres_only else None,
        )

    def _load_recent_sector_turnover_history(target_date, sector_name, lookback_days=25, max_scan_days=60):
        if not postgres_only:
            try:
                return load_recent_sector_turnover_history_runtime(
                    target_date,
                    sector_name,
                    lookback_days=lookback_days,
                    max_scan_days=max_scan_days,
                )
            except TypeError:
                return load_recent_sector_turnover_history_runtime(
                    target_date,
                    sector_name,
                    lookback_days=lookback_days,
                )
        return load_recent_sector_turnover_history_runtime(
            target_date,
            sector_name,
            lookback_days=lookback_days,
            max_scan_days=max_scan_days,
            helpers={"postgres_only_runtime": True} if postgres_only else None,
        )

    return build_market_research_snapshot_contract(
        data,
        final_gate,
        position_level,
        exit_analysis,
        observation_snapshot=observation_snapshot,
        target_date=target_date,
        build_abnormal_projection_summary=_build_abnormal_projection_summary,
        build_market_style_switch_snapshot=_build_market_style_switch_snapshot,
        build_market_state_machine_snapshot=_build_market_state_machine_snapshot,
        build_mainline_rotation_snapshot=_build_mainline_rotation_snapshot,
        build_abnormal_probe_group=_build_abnormal_probe_group,
        build_special_probe_verdict=_build_special_probe_verdict,
        build_follow_verdict=_build_follow_verdict,
        build_dialectical_decision_snapshot=_build_dialectical_decision_snapshot,
        build_mainline_turnover_summary=build_mainline_turnover_summary_runtime,
        build_mainline_history_record=build_mainline_history_record_runtime,
        load_recent_mainline_history=_load_recent_mainline_history,
        get_market_total_turnover_from_fact_db=get_market_total_turnover_from_fact_db_runtime,
        get_sector_turnover_snapshot_from_tencent_fund_flow=get_sector_turnover_snapshot_from_tencent_fund_flow_runtime,
        get_sector_turnover_snapshot_from_ths=get_sector_turnover_snapshot_from_ths_runtime,
        load_recent_sector_turnover_history=_load_recent_sector_turnover_history,
        save_market_cycle_context=save_market_cycle_context_runtime,
    )


def _derive_step0_follow_plan_legacy_body(market_research_snapshot, final_gate, position_level):
    return derive_step0_follow_plan_contract(
        market_research_snapshot,
        final_gate,
        position_level,
    )


def _build_dialectical_decision_snapshot_legacy_body(
    observation=None,
    style_switch=None,
    state_machine=None,
    follow_verdict=None,
    final_gate=None,
):
    observation = observation or {}
    style_switch = style_switch or {}
    state_machine = state_machine or {}
    follow_verdict = follow_verdict or {}
    final_gate = final_gate or {}

    benchmark_change = _safe_float(observation.get("benchmark_change_pct", 0.0), 0.0)
    zt_count = int(_safe_float(observation.get("zt_count", 0)))
    dt_count = int(_safe_float(observation.get("dt_count", 0)))
    up_count = int(_safe_float(observation.get("up_count", 0)))
    down_count = int(_safe_float(observation.get("down_count", 0)))
    rise_fall_ratio = observation.get("rise_fall_ratio")
    trend_count = int(_safe_float(observation.get("densest_sector_trend_count", 0)))
    resilient_count = int(_safe_float(observation.get("resilient_abnormal_count", 0)))
    failed_count = int(_safe_float(observation.get("failed_abnormal_count", 0)))
    densest_sector = str(observation.get("densest_sector", "") or "").strip()
    follow_code = str(follow_verdict.get("code", "") or "").strip()
    state_code = str(state_machine.get("state_code", "") or "").strip()
    can_new_entry = bool(final_gate.get("can_new_entry"))
    operation_state = str(final_gate.get("operation_state", "") or "").strip()

    profit_effect_strong = any(
        [
            trend_count >= 2,
            resilient_count >= 2,
            zt_count >= 20,
            follow_code in {"follow", "single_line_follow", "conditional_follow"},
            can_new_entry,
        ]
    )

    if state_code == "expand":
        stage_label = "扩张确认"
        stage_reason = "热点、趋势密度和异常承接已经同向共振，市场不再只是局部修复。"
        stage_action = "可以顺着最强方向做减法，但真正出手只落到09:30-09:35、09:50-10:10或14:30-14:55三段窗口。"
    elif state_code == "migrate":
        stage_label = "分歧迁移"
        stage_reason = "市场不是全面转弱，而是在主攻线和竞争线之间重新分配权重。"
        stage_action = "先看谁胜出，不同时押两边。"
    elif state_code == "probe":
        if can_new_entry or operation_state == "进攻态" or zt_count >= 25 or trend_count >= 3 or resilient_count >= 2:
            stage_label = "负重前行"
            stage_reason = "市场开始修复，但指数、广度和主线承接还没全面顺滑，先按修复初期处理。"
            stage_action = "只做顺势跟随，不把试探修复误判成全面主升。"
        else:
            stage_label = "试探修复"
            stage_reason = "局部有修复迹象，但证据还不够密，更多是研究价值，不是全面执行价值。"
            stage_action = "先研究，再等主线和异常承接继续补证据。"
    else:
        stage_label = "收缩防守"
        stage_reason = "风险释放仍优先，市场还没回到可以放大试错的状态。"
        stage_action = "先防守，不给新增买入资格。"

    breadth_divergence = benchmark_change >= 0.2 and down_count > up_count > 0

    if breadth_divergence:
        index_profit_relation = "指数强但赚钱效应背离"
        index_profit_reason = (
            f"指数上涨{benchmark_change:+.2f}%时，上涨{up_count}家、下跌{down_count}家，"
            f"更像少数方向的窄池子进攻，不是普涨环境。"
        )
        index_profit_action = (
            f"只看{densest_sector or '被资金持续选择的方向'}，没有站对板块路径时不因指数上涨提高观察质量；"
            "先区分核心锚、量化弹性和情绪后排，不能用同一个板块结论覆盖不同持仓周期。"
        )
    elif benchmark_change <= -0.1 and profit_effect_strong:
        index_profit_relation = "指数承压，但赚钱效应还在主线里"
        index_profit_reason = (
            f"上证{benchmark_change:+.2f}%时，热点没有一起塌；真正该盯的是{densest_sector or '当前最强方向'}内部承接有没有继续。"
        )
        index_profit_action = "别被指数单独带偏，优先看主线内部承接是否延续。"
    elif benchmark_change >= 0.2 and profit_effect_strong:
        index_profit_relation = "指数和赚钱效应同步修复"
        index_profit_reason = "指数、热点聚焦和异常承接在同向改善，这种环境更适合顺势跟随。"
        index_profit_action = "可以沿着最强方向做减法，但依旧只做最强对象。"
    elif benchmark_change >= 0.2 and not profit_effect_strong:
        index_profit_relation = "指数回暖了，但赚钱效应还没跟上"
        index_profit_reason = "指数变好看，不代表主线已经清晰，更不代表随便买都能赚钱。"
        index_profit_action = "先看热点聚焦和趋势密度，不因指数变红就提前出手。"
    else:
        index_profit_relation = "指数和赚钱效应都偏弱"
        index_profit_reason = "指数没有给出正反馈，主线承接也还不够集中。"
        index_profit_action = "先观察，不把局部反抽当成可执行机会。"

    if densest_sector and trend_count >= 2:
        focus_label = f"赚钱效应继续向{densest_sector}聚集"
        focus_reason = f"{densest_sector}当前有{trend_count}只活跃趋势股，异常承接{resilient_count}强/{failed_count}弱。"
        focus_action = f"只在{densest_sector}和相关异常承接对象里继续做减法。"
    elif densest_sector:
        focus_label = f"{densest_sector}暂时领先，但聚集还不够"
        focus_reason = f"{densest_sector}虽然领先，但趋势密度只有{trend_count}只，更多还是观察优势，不是绝对优势。"
        focus_action = "先把它当研究重点，不急着给普遍买入资格。"
    else:
        focus_label = "赚钱效应还没真正聚集"
        focus_reason = "热点仍偏散，主线没有形成足够稳定的中心。"
        focus_action = "先观察胜出方向，不在分散题材里乱试错。"

    if profit_effect_strong:
        candidate_focus = "优先率先转强、分歧后仍有承接、异常后跌不下去的对象"
        candidate_action = "长期阴跌后的孤立首板默认只观察；只有后续继续强化，才考虑升级。"
    else:
        candidate_focus = "先分清谁只是反抽，谁真正率先转强"
        candidate_action = "观察池优先保留率先转强和异常承接对象，不给低位幻想买入资格。"

    falsification_conditions = []
    if densest_sector:
        falsification_conditions.append(f"{densest_sector}的趋势密度和承接同时走弱，热点重新变散。")
    else:
        falsification_conditions.append("热点没有继续聚焦，赚钱效应重新变散。")
    falsification_conditions.append("异常对象次日明显转弱，原先“跌不下去”的信号没有继续保住。")
    falsification_conditions.append("三段固定交易窗口内条件都不成立，或者买点只剩情绪顶点可以追。")
    if rise_fall_ratio is not None and _safe_float(rise_fall_ratio, 0.0) > 0:
        falsification_conditions.append(
            f"涨跌比重新恶化到{observation.get('rise_fall_ratio_text', '明显转弱')}附近，且跌停继续增加。"
        )
    else:
        falsification_conditions.append(f"跌停快速增加到{max(dt_count + 5, 8)}只以上，修复链说明显断掉。")

    return {
        "stage_label": stage_label,
        "stage_reason": stage_reason,
        "stage_action": stage_action,
        "index_profit_relation": index_profit_relation,
        "index_profit_reason": index_profit_reason,
        "index_profit_action": index_profit_action,
        "focus_label": focus_label,
        "focus_reason": focus_reason,
        "focus_action": focus_action,
        "candidate_focus": candidate_focus,
        "candidate_action": candidate_action,
        "falsification_conditions": falsification_conditions[:4],
        "style_label": style_switch.get("style_label", ""),
        "style_action": style_switch.get("primary_action", ""),
        "follow_label": follow_verdict.get("label", ""),
    }


def _build_abnormal_projection_summary_legacy_body(abnormal_watch_pool=None):
    abnormal_watch_pool, degraded_abnormal_watch_pool = _split_abnormal_watch_pool(abnormal_watch_pool)
    if not abnormal_watch_pool:
        return {
            "projection_label": "异常观察为空",
            "projection_reason": "当前没有明确的异常承接样本，不能把孤立异动当成主线强化证据。",
            "action": "继续观察，等待更多异常样本确认。",
            "resilient_count": 0,
            "failed_count": 0,
            "setup_breakdown": [],
            "degraded_count": len(degraded_abnormal_watch_pool),
        }

    resilient_count = len([item for item in abnormal_watch_pool if item.get("follow_state") in ("跌不下去", "缩量消化")])
    failed_count = len([item for item in abnormal_watch_pool if item.get("follow_state") == "已经转弱"])
    setup_counter = {}
    for item in abnormal_watch_pool:
        setup_label = item.get("setup_signal_label", item.get("abnormal_type", "未分类")) or "未分类"
        setup_counter[setup_label] = setup_counter.get(setup_label, 0) + 1
    setup_breakdown = sorted(setup_counter.items(), key=lambda x: (-x[1], x[0]))

    if resilient_count >= 2 and failed_count == 0:
        projection_label = "异常承接强化"
        projection_reason = "多个异常信号在后续没有继续塌陷，说明高维主线状态仍在强化。"
        action = "优先盯“跌不下去/缩量消化”的对象，再看三段固定交易窗口内条件是否成立。"
    elif failed_count >= max(2, resilient_count + 1):
        projection_label = "异常失败转弱"
        projection_reason = "异常信号大面积转弱，说明高维状态更像衰减或切换，而不是继续强化。"
        action = "降权这些异常股，防守优先，不因为漂亮K线强行出手。"
    else:
        projection_label = "异常分化观察"
        projection_reason = "异常有出现，但承接和失败并存，说明高维状态还在选择方向。"
        action = "继续观察，不放松买入资格；等更清晰的承接胜出。"

    return {
        "projection_label": projection_label,
        "projection_reason": projection_reason,
        "action": action,
        "resilient_count": resilient_count,
        "failed_count": failed_count,
        "setup_breakdown": setup_breakdown[:5],
        "degraded_count": len(degraded_abnormal_watch_pool),
    }


def _build_mainline_competition_snapshot_legacy_body(
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    risk_sectors=None,
):
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    sector_trend_snapshot = sector_trend_snapshot or []
    risk_sectors = risk_sectors or []

    trend_map = {}
    for item in sector_trend_snapshot:
        sector = item.get("sector", "")
        if sector:
            trend_map[sector] = item

    rows = []
    used_names = set()

    def resolve_trend_item(sector_name):
        for key, item in trend_map.items():
            if sector_name_matches(key, sector_name):
                return item
        return {}

    def append_sector(item, role, default_action):
        sector_name = item.get("name", item.get("sector", "")) if isinstance(item, dict) else str(item or "")
        if not sector_name or sector_name in used_names:
            return
        used_names.add(sector_name)
        trend_item = resolve_trend_item(sector_name)
        flow_yi = _normalize_flow_to_yi(
            item.get("inflow", item.get("fund_flow", item.get("zljlr", item.get("net_inflow_yi", 0.0))))
            if isinstance(item, dict)
            else 0.0
        )
        change_pct = _safe_float(
            item.get("change_pct", item.get("zdf", item.get("涨跌幅", 0.0))) if isinstance(item, dict) else 0.0,
            0.0,
        )
        trend_count = int(_safe_float(trend_item.get("trend_count", 0)))
        strong_count = int(_safe_float(trend_item.get("strong_count", 0)))
        limit_up_count = int(
            _safe_float(
                trend_item.get(
                    "limit_up_count",
                    item.get("limit_up_count", item.get("zt_count", 0)) if isinstance(item, dict) else 0,
                )
            )
        )

        evidence_parts = []
        if flow_yi:
            evidence_parts.append(f"资金{flow_yi:+.1f}亿")
        if change_pct:
            evidence_parts.append(f"涨幅{change_pct:+.2f}%")
        if trend_count:
            evidence_parts.append(f"趋势{trend_count}只")
        if strong_count:
            evidence_parts.append(f"强势{strong_count}只")
        if limit_up_count:
            evidence_parts.append(f"涨停{limit_up_count}只")
        evidence_text = " / ".join(evidence_parts) if evidence_parts else "暂无足够结构证据"

        if role == "主攻线":
            judgement = "当前最值得粘住的方向"
        elif role == "竞争线":
            judgement = "仍在争夺主线地位"
        elif role == "次强线":
            judgement = "有承接，但还不是唯一中心"
        else:
            judgement = "能量外流，优先回避"

        rows.append(
            {
                "role": role,
                "sector": sector_name,
                "evidence": evidence_text,
                "judgement": judgement,
                "action": default_action,
            }
        )

    if main_sectors_info:
        append_sector(main_sectors_info[0], "主攻线", "只在这条线里找买入资格")
    if len(main_sectors_info) >= 2:
        append_sector(main_sectors_info[1], "次强线", "有共振才看，不抢主攻线风头")
    if secondary_sectors_info:
        append_sector(secondary_sectors_info[0], "竞争线", "先观察胜负，不急着给买入资格")
    if risk_sectors:
        append_sector({"name": risk_sectors[0]}, "回避线", "只做风险观察，不做出手方向")

    return rows


def _build_mainline_rotation_snapshot_legacy_body(
    observation=None,
    state_machine=None,
    style_switch=None,
    sector_ai_analysis=None,
):
    observation = observation or {}
    state_machine = state_machine or {}
    style_switch = style_switch or {}
    sector_ai_analysis = sector_ai_analysis or {}

    from collections import Counter

    competition_rows = observation.get("mainline_competition_snapshot", []) or []
    role_counts = Counter()
    role_sectors = {}
    for item in competition_rows:
        role = str(item.get("role", "") or "").strip()
        sector = str(item.get("sector", "") or "").strip()
        if not role:
            continue
        role_counts[role] += 1
        if sector and role not in role_sectors:
            role_sectors[role] = sector

    mainline_sector = str(
        state_machine.get("leading_line", "")
        or role_sectors.get("主攻线", "")
        or (observation.get("mainline_candidates", []) or [""])[0]
        or ""
    ).strip()
    secondary_sector = str(
        role_sectors.get("次强线", "")
        or (observation.get("secondary_candidates", []) or [""])[0]
        or ""
    ).strip()
    competition_sector = str(role_sectors.get("竞争线", "") or "").strip()

    role_counts_text = " / ".join(
        f"{role}{role_counts.get(role, 0)}条"
        for role in ("主攻线", "次强线", "竞争线", "回避线")
        if role_counts.get(role, 0)
    ) or "暂无接力统计"
    relay_sector_parts = [
        part
        for part in (
            f"主攻线{mainline_sector}" if mainline_sector else "",
            f"次强线{secondary_sector}" if secondary_sector else "",
            f"竞争线{competition_sector}" if competition_sector else "",
        )
        if part
    ]
    relay_sector_text = " / ".join(relay_sector_parts) or (mainline_sector or "暂无主线")
    relay_text = f"{relay_sector_text}；接力统计：{role_counts_text}"

    trend_density = int(_safe_float(observation.get("densest_sector_trend_count", 0)))
    resilient_count = int(_safe_float(observation.get("resilient_abnormal_count", 0)))
    failed_count = int(_safe_float(observation.get("failed_abnormal_count", 0)))
    style_code = str(style_switch.get("style_code", "") or "").strip()
    turnover_state = str(style_switch.get("turnover_state", "") or "").strip()
    turnover_label = str(style_switch.get("turnover_label", "") or "").strip()
    pulse_stage = str(state_machine.get("pulse_stage", "") or "").strip()
    state_code = str(state_machine.get("state_code", "") or "").strip()
    heavy_turnover_selloff = _is_heavy_turnover_selloff(observation, style_switch)

    if heavy_turnover_selloff:
        rotation_label = "逆势攻击"
        rotation_reason = (
            f"{turnover_label or turnover_state or '成交额放大'}但盘面是放量杀跌，叠加指数大跌、跌停扩散和涨跌比失衡，"
            f"{mainline_sector or '主攻线'}只是局部逆势攻击；量化动量和风控卖出互相强化时，不能按顺势爆发理解。"
        )
        rotation_action = (
            f"先防踩踏，只观察{mainline_sector or '主攻线'}次日是否修复承接；"
            "承接不足时不追一致，等市场买盘重新站出来。"
        )
    elif state_code == "expand":
        rotation_label = "爆发"
        rotation_reason = f"{turnover_label or turnover_state or '量能'}仍支持主线集中，{relay_sector_text}，趋势密度{trend_density}只，接力还在主线内部。"
        rotation_action = f"继续围着{mainline_sector or '主线'}做减法，只盯主攻线承接，不把支线当新中心。"
    elif state_code == "migrate":
        rotation_label = "分化整理"
        rotation_reason = f"{turnover_label or turnover_state or '量能'}下，主攻线{mainline_sector or '仍在'}，次强线开始分流，市场先整理再决定谁留在中心。"
        rotation_action = f"先看{mainline_sector or '主线'}能否重新聚焦，支线只算轮动，不把分化误判成退潮。"
    elif state_code == "probe":
        rotation_label = "支线轮动"
        rotation_reason = f"{turnover_label or turnover_state or '量能'}偏分歧，资金在{secondary_sector or '支线'}和{competition_sector or '竞争线'}之间轮换，主线内部开始接力切段。"
        rotation_action = "只跟最有承接的支线，不把每一次轮动都理解成新主线。"
    else:
        if style_code == "trend" or pulse_stage in ("启动", "加速"):
            rotation_label = "爆发"
            rotation_reason = f"{turnover_label or turnover_state or '量能'}仍支持主线集中，{relay_sector_text}，趋势密度{trend_density}只，接力还在主线内部。"
            rotation_action = f"继续围着{mainline_sector or '主线'}做减法，只盯主攻线承接，不把支线当新中心。"
        elif style_code == "dual" or pulse_stage == "分歧承接":
            rotation_label = "支线轮动"
            rotation_reason = f"{turnover_label or turnover_state or '量能'}偏分歧，资金在{secondary_sector or '支线'}和{competition_sector or '竞争线'}之间轮换，主线内部开始接力切段。"
            rotation_action = "只跟最有承接的支线，不把每一次轮动都理解成新主线。"
        else:
            rotation_label = "再聚焦"
            rotation_reason = f"{turnover_label or turnover_state or '量能'}收敛后，市场在把权重重新压回少数方向；谁能继续承接，谁就重新拿回中心。"
            rotation_action = f"先等{mainline_sector or '主线'}或新的核心节点重新聚焦，再谈执行。"

    lifecycle_text = "爆发 → 分化整理 → 支线轮动 → 再聚焦"
    style_note = str(style_switch.get("style_reason", "") or turnover_label or turnover_state or "").strip()
    summary_bits = [lifecycle_text, f"当前{rotation_label}"]
    if style_note:
        summary_bits.append(style_note)
    abnormal_acceptance_text = (
        f"异常承接{resilient_count}强/{failed_count}弱"
        if resilient_count > 0 or failed_count > 0
        else "异常承接未形成样本"
    )
    summary_bits.extend([relay_text, f"趋势密度{trend_density}只", abnormal_acceptance_text])
    summary_text = "；".join(summary_bits)

    relationships = sector_ai_analysis.get("relationships", {}) or {}
    mapping = sector_ai_analysis.get("mapping", {}) or {}
    standard_sectors = sector_ai_analysis.get("standard_sectors", []) or []
    node_source = mainline_sector or str(state_machine.get("leading_line", "") or "").strip()
    relation_entry = {}
    relation_name = ""
    if node_source:
        for raw_name, item in relationships.items():
            if raw_name == node_source or sector_name_matches(raw_name, node_source) or sector_name_matches(node_source, raw_name):
                relation_entry = item if isinstance(item, dict) else {}
                relation_name = raw_name
                break
    standard_name = str(
        (relation_entry.get("standard_name", "") if isinstance(relation_entry, dict) else "")
        or mapping.get(node_source, "")
        or mainline_sector
        or node_source
        or ""
    ).strip()
    related = [str(item).strip() for item in (relation_entry.get("related", []) or []) if str(item).strip()][:3]
    parent_name = str(relation_entry.get("parent", "") or "").strip()
    type_name = str(relation_entry.get("type", "") or "").strip()
    if parent_name and parent_name == node_source:
        narrative_label = f"{node_source}节点"
    elif standard_name and standard_name != node_source:
        narrative_label = f"{standard_name}节点"
    elif node_source:
        narrative_label = f"{node_source}节点"
    else:
        narrative_label = "产业叙事节点"
    if relation_entry:
        node_reason_bits = []
        if type_name:
            node_reason_bits.append(type_name)
        if parent_name:
            upper_name = standard_name if parent_name == node_source and standard_name != node_source else parent_name
            node_reason_bits.append(f"上看{upper_name}")
        if related:
            node_reason_bits.append(f"相关环节{' / '.join(related)}")
        extra_reason = f"；{'，'.join(node_reason_bits)}" if node_reason_bits else ""
        display_node_name = parent_name or standard_name or node_source or "主线"
        narrative_reason = f"{relation_name or node_source or '主线'}在归链里更接近{display_node_name}这一节点{extra_reason}。"
    elif standard_sectors:
        narrative_reason = f"AI归链把多条板块压到{standard_sectors[0]}等标准方向，当前交易的是{node_source or '主线'}这个承接节点，而不是泛题材扩散。"
    else:
        narrative_reason = f"当前交易的是{node_source or '主线'}这个承接节点，而不是泛题材扩散。"
    narrative_action = f"先盯{node_source or '主线'}的承接是否继续，别把节点切换误当成主线切换。"
    narrative_text = f"{narrative_label}：{narrative_reason}"

    return {
        "rotation_label": rotation_label,
        "rotation_reason": rotation_reason,
        "rotation_action": rotation_action,
        "relay_text": relay_text,
        "relay_counts_text": role_counts_text,
        "rotation_lifecycle_text": lifecycle_text,
        "summary_text": summary_text,
        "narrative_label": narrative_label,
        "narrative_reason": narrative_reason,
        "narrative_action": narrative_action,
        "narrative_text": narrative_text,
    }


def _build_market_observation_snapshot_legacy_body(
    data,
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    abnormal_watch_pool=None,
    leader_memory_bank=None,
    tracking_memory_status=None,
    mainline_competition_snapshot=None,
):
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    sector_trend_snapshot = sector_trend_snapshot or []
    abnormal_watch_pool, degraded_abnormal_watch_pool = _split_abnormal_watch_pool(abnormal_watch_pool)
    leader_memory_bank = leader_memory_bank or []
    tracking_memory_status = tracking_memory_status or {}
    mainline_competition_snapshot = mainline_competition_snapshot or []

    indices = data.get("indices", {}) or {}
    sh_index = indices.get("上证指数", {}) or {}
    breadth_snapshot = _extract_market_breadth_snapshot(data)
    up_count = int(_safe_float(breadth_snapshot.get("up_count", 0)))
    down_count = int(_safe_float(breadth_snapshot.get("down_count", 0)))
    rise_fall_ratio = breadth_snapshot.get("rise_fall_ratio")
    zt_count = len(data.get("zt_pool", []) or [])
    resolved_dt_count = resolve_limit_down_count(data)
    dt_count = resolved_dt_count if resolved_dt_count is not None else 0
    turnover = _safe_float(data.get("total_turnover", 0.0))

    densest_sector = _first_directional_trend_item(sector_trend_snapshot)
    resilient_count = len([item for item in abnormal_watch_pool if item.get("follow_state") in ("跌不下去", "缩量消化")])
    failed_count = len([item for item in abnormal_watch_pool if item.get("follow_state") == "已经转弱"])

    return {
        "benchmark_change_pct": _round_or_none(sh_index.get("涨跌幅", sh_index.get("change_pct", 0.0)), 4),
        "zt_count": zt_count,
        "dt_count": resolved_dt_count,
        "dt_count_available": resolved_dt_count is not None,
        "up_count": up_count,
        "down_count": down_count,
        "breadth_available": bool(breadth_snapshot.get("breadth_available")),
        "rise_fall_ratio": round(rise_fall_ratio, 4) if rise_fall_ratio is not None else None,
        "rise_fall_ratio_text": breadth_snapshot.get("rise_fall_ratio_text", "暂无"),
        "turnover": round(turnover, 2),
        "main_sectors_info": main_sectors_info[:5],
        "secondary_sectors_info": secondary_sectors_info[:5],
        "mainline_candidates": [item.get("name", "") for item in main_sectors_info if item.get("name")][:3],
        "secondary_candidates": [item.get("name", "") for item in secondary_sectors_info if item.get("name")][:3],
        "sector_trend_snapshot": sector_trend_snapshot[:5],
        "abnormal_watch_pool": abnormal_watch_pool[:5],
        "degraded_abnormal_watch_pool": degraded_abnormal_watch_pool[:3],
        "leader_memory_bank": leader_memory_bank[:5],
        "tracking_memory_status": tracking_memory_status,
        "mainline_competition_snapshot": mainline_competition_snapshot[:5],
        "competition_focus": (mainline_competition_snapshot or [None])[0] or {},
        "densest_sector": densest_sector.get("sector", ""),
        "densest_sector_trend_count": int(_safe_float(densest_sector.get("trend_count", 0))),
        "resilient_abnormal_count": resilient_count,
        "failed_abnormal_count": failed_count,
        "degraded_abnormal_count": len(degraded_abnormal_watch_pool),
        "leader_memory_count": len(leader_memory_bank or []),
        "trusted_tracking_count": len(tracking_memory_status.get("today_validated_items", []) or []),
        "tentative_tracking_count": len(tracking_memory_status.get("today_tentative_items", []) or []),
    }


def _build_follow_verdict_legacy_body(final_gate, position_level, state_machine_snapshot, special_probe_verdict=None):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    special_probe_verdict = special_probe_verdict or {}
    energy_state = state_machine_snapshot.get("energy_state", "未知状态")
    state_code = state_machine_snapshot.get("state_code", "")
    pulse_stage = str(state_machine_snapshot.get("pulse_stage", "") or "").strip()
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    pulse_action_reason = str(state_machine_snapshot.get("pulse_action_reason", "") or "").strip()
    leading_line = str(state_machine_snapshot.get("leading_line", "") or "").strip()
    special_probe_action = str(special_probe_verdict.get("action", "") or "").strip()
    special_probe_summary = str(special_probe_verdict.get("summary_text", "") or "").strip()

    if not final_gate.get("can_new_entry"):
        if execution_bias == "prep_only" or (
            state_code == "migrate" and state_machine_snapshot.get("transition_signal") == "upgrade_ready"
        ):
            return {
                "code": "bridge_prep",
                "label": "🟡 条件执行预备态",
                "reason": pulse_action_reason or state_machine_snapshot.get("transition_reason") or f"当前处于{energy_state}，但主攻线优势已经开始拉开。",
                "action": "先不开新仓，只为最强对象保留观察预备态；若次日09:50-10:10窗口满足条件，结果进入复盘和下一份日报判断",
            }
        if final_gate.get("allow_attack_50_ready") and not final_gate.get("should_reduce"):
            action_text = "只看主线核心是否在固定交易窗口内满足条件：强核心看09:30-09:35竞价表态、开盘前几分钟或回封，普通结构只看09:50-10:10窗口；结果进入复盘和下一份日报判断，否则按0%不参与"
            if special_probe_action:
                action_text = f"{special_probe_action}；{action_text}"
            return {
                "code": "conditional_defense",
                "label": "🟡 条件防守观察",
                "reason": f"当前处于{energy_state}，指数结构未坏，但环境条件还没正式满足，只保留主线核心的条件观察资格。",
                "action": action_text,
            }
        if final_gate.get("should_reduce") or execution_bias == "reduce_only":
            action_text = "若你有旧仓先去弱留强，不新增参与"
            if special_probe_action:
                action_text = f"{special_probe_action}；{action_text}"
            return {
                "code": "reduce_only",
                "label": "🟠 只处理旧仓",
                "reason": pulse_action_reason or f"当前处于{energy_state}，系统只保留旧仓处理资格，不给新增买入资格。",
                "action": action_text,
            }
        if position_level == "0%不参与" or final_gate.get("operation_state") == "撤退态":
            return {
                "code": "avoid",
                "label": "🚫 暂不跟随",
                "reason": f"当前处于{energy_state}，新增买入资格未满足，先研究市场，不做新增参与。",
                "action": "保持空仓，只观察，不新增参与",
            }
        action_text = "先看环境；若你有持仓，只处理持仓，不新增参与"
        if special_probe_action:
            action_text = f"{special_probe_action}；{action_text}"
        return {
            "code": "research_only",
            "label": "🟡 只研究不跟随",
            "reason": pulse_action_reason or f"当前处于{energy_state}，可以继续研究和跟踪，但还不到新增执行的时候。",
            "action": action_text,
        }

    if execution_bias == "avoid":
        reason_text = pulse_action_reason or f"{leading_line or '主线'}已经进入{pulse_stage or '退潮'}，继续参与性价比很差。"
        if special_probe_summary:
            reason_text = f"{reason_text}；{special_probe_summary}"
        action_text = "不参与新脉冲，先等下一轮真正的新启动"
        if special_probe_action:
            action_text = f"{special_probe_action}；{action_text}"
        return {
            "code": "avoid",
            "label": "🚫 暂不跟随",
            "reason": reason_text,
            "action": action_text,
        }
    if execution_bias == "watch_only":
        reason_text = pulse_action_reason or f"{leading_line or '主线'}脉冲已进入{pulse_stage or '钝化'}，逻辑未必错，但再追更像接最后一棒。"
        if special_probe_summary:
            reason_text = f"{reason_text}；{special_probe_summary}"
        action_text = "只处理旧仓或等待下一次新脉冲，不追新的一致加速"
        if special_probe_action:
            action_text = f"{special_probe_action}；{action_text}"
        return {
            "code": "no_chase",
            "label": "🟠 只减不加",
            "reason": reason_text,
            "action": action_text,
        }
    if execution_bias == "divergence_only":
        return {
            "code": "pullback_only",
            "label": "🟡 只做分歧承接",
            "reason": pulse_action_reason or f"{leading_line or '主线'}仍在，但当前处于{pulse_stage or '高位分歧'}，只能等分歧承接，不能追一致加速。",
            "action": "只做主线分歧承接后的固定交易窗口预案，不追一致加速",
        }

    if state_code == "expand":
        return {
            "code": "follow",
            "label": "🟢 跟随主线",
            "reason": "热点、趋势密度和异常承接正在同向共振，可以跟，但只能跟最强方向。",
            "action": f"只在主线和异常承接对象里按三段固定交易窗口处理；{TWO_B_CONFIRMATION_CLAUSE}",
        }
    if state_code == "migrate":
        return {
            "code": "single_line_follow",
            "label": "🟡 只跟唯一胜出方向",
            "reason": "热点和趋势还在重排，先研究胜负，不能同时押主线和竞争线。",
            "action": "先看主线与竞争线谁胜出，固定交易窗口内条件未成立前不分散出手",
        }
    if state_code == "probe":
        return {
            "code": "conditional_follow",
            "label": "🟡 条件跟随",
            "reason": "市场还在试探修复，只有异常继续跌不下去，才允许从研究切到跟随。",
            "action": "轻跟随也必须等固定交易窗口内条件成立，不追一致高潮",
        }
    return {
        "code": "observe",
        "label": "⚠️ 先看环境",
        "reason": f"当前处于{energy_state}，先确认市场没有继续恶化，再谈跟随。",
        "action": "先看竞价表态与开盘承接，固定交易窗口内条件未成立就保持0%",
    }


def _render_market_research_snapshot_section_legacy_body(market_research_snapshot, compact=False):
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get("observation", {}) or {}
    style_switch = market_research_snapshot.get("style_switch", {}) or {}
    state_machine = market_research_snapshot.get("state_machine", {}) or {}
    abnormal_projection = market_research_snapshot.get("abnormal_projection", {}) or {}
    follow_verdict = market_research_snapshot.get("follow_verdict", {}) or {}
    competition_focus = observation.get("competition_focus", {}) or {}
    rotation_snapshot = market_research_snapshot.get("mainline_rotation_snapshot", {}) or _build_mainline_rotation_snapshot(
        observation=observation,
        state_machine=state_machine,
        style_switch=style_switch,
        sector_ai_analysis=market_research_snapshot.get("sector_ai_analysis", {}) or {},
    )
    dialectical_decision = market_research_snapshot.get("dialectical_decision") or _build_dialectical_decision_snapshot(
        observation=observation,
        style_switch=style_switch,
        state_machine=state_machine,
        follow_verdict=follow_verdict,
        final_gate=market_research_snapshot.get("final_gate", {}) or {},
    )
    competition_result = "主线待定"
    competition_evidence = "先看趋势密度、异常承接和资金聚焦谁先胜出"
    if competition_focus:
        competition_result = f"{competition_focus.get('role', '观察线')} {competition_focus.get('sector', '-')}"
        competition_evidence = competition_focus.get("evidence", competition_evidence)

    return render_market_research_snapshot_section_renderer(
        {
            "compact": compact,
            "benchmark_change": _safe_float(observation.get("benchmark_change_pct", 0.0)),
            "turnover": _safe_float(observation.get("turnover", 0.0)),
            "observation": observation,
            "competition_result": competition_result,
            "competition_evidence": competition_evidence,
            "mainline_turnover_summary": market_research_snapshot.get("mainline_turnover_summary", {}) or {},
            "capital_intent_breakdown": market_research_snapshot.get("capital_intent_breakdown", {}) or {},
            "lhb_capital_status": market_research_snapshot.get("lhb_capital_status", {}) or {},
            "capital_conclusion": market_research_snapshot.get("capital_conclusion", {}) or {},
            "realtime_tag_evidence_snapshot": market_research_snapshot.get("realtime_tag_evidence_snapshot", {}) or {},
            "rotation_label": rotation_snapshot.get("rotation_label", "-"),
            "rotation_summary_text": rotation_snapshot.get("summary_text", rotation_snapshot.get("rotation_reason", "-")),
            "rotation_action": rotation_snapshot.get("rotation_action", "-"),
            "narrative_label": rotation_snapshot.get("narrative_label", "-"),
            "narrative_reason": rotation_snapshot.get("narrative_reason", "-"),
            "narrative_action": rotation_snapshot.get("narrative_action", "-"),
            "style_label": style_switch.get("style_label", "-"),
            "style_reason": style_switch.get("style_reason", "-"),
            "style_evidence_text": style_switch.get("evidence_text", "-"),
            "abnormal_projection_label": abnormal_projection.get("projection_label", "-"),
            "abnormal_projection_reason": abnormal_projection.get("projection_reason", "-"),
            "follow_verdict_label": follow_verdict.get("label", "-"),
            "follow_verdict_reason": follow_verdict.get("reason", "-"),
            "state_energy": state_machine.get("energy_state", "-"),
            "state_reason": state_machine.get("state_reason", "-"),
            "state_flow_direction": state_machine.get("flow_direction", "-"),
            "dialectical_decision": dialectical_decision,
        }
    )


def _render_step0_follow_section_legacy_body(step0_plan, market_research_snapshot, compact=False):
    step0_plan = step0_plan or {}
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get("observation", {}) or {}
    style_switch = market_research_snapshot.get("style_switch", {}) or {}
    state_machine = market_research_snapshot.get("state_machine", {}) or {}
    abnormal_projection = market_research_snapshot.get("abnormal_projection", {}) or {}
    return render_step0_follow_section_renderer(
        {
            "compact": compact,
            "step0_prediction_cn": step0_plan.get("step0_prediction_cn", "-"),
            "step0_reason": step0_plan.get("step0_reason", "-"),
            "step0_action": step0_plan.get("step0_action", "-"),
            "final_gate": market_research_snapshot.get("front_page_final_gate")
            or market_research_snapshot.get("final_gate")
            or step0_plan.get("final_gate")
            or {},
            "position_decision": market_research_snapshot.get("position_decision")
            or step0_plan.get("position_decision")
            or {},
            "zt_count": observation.get("zt_count", 0),
            "dt_count": observation.get("dt_count", 0),
            "dt_count_available": observation.get(
                "dt_count_available",
                observation.get("dt_count") is not None,
            ),
            "observation_summary": state_machine.get("observation_summary", "-"),
            "style_label": style_switch.get("style_label", "-"),
            "style_reason": style_switch.get("style_reason", "-"),
            "densest_sector": observation.get("densest_sector", "暂无明确主线"),
            "densest_sector_trend_count": observation.get("densest_sector_trend_count", 0),
            "mainline_turnover_summary": market_research_snapshot.get("mainline_turnover_summary", {}) or {},
            "mainline_attack_evidence_summary": market_research_snapshot.get("mainline_attack_evidence_summary", {}) or {},
            "resilient_abnormal_count": observation.get("resilient_abnormal_count", 0),
            "failed_abnormal_count": observation.get("failed_abnormal_count", 0),
            "abnormal_projection_label": abnormal_projection.get("projection_label", "-"),
            "state_energy": state_machine.get("energy_state", "-"),
            "state_reason": state_machine.get("state_reason", "-"),
        }
    )


def _build_market_research_context_bundle_legacy_body(
    data,
    target_date,
    exit_analysis,
    final_gate,
    position_level,
    main_sectors_info=None,
    secondary_sectors_info=None,
    main_sectors=None,
    secondary_sectors=None,
    dragon_stocks=None,
    decision_strict_mode=None,
    allow_display_degraded_abnormal_snapshot=None,
):
    current_decision_strict_mode = (
        decision_strict_mode
        if decision_strict_mode is not None
        else globals().get("decision_strict_mode", True)
    )
    current_allow_display_degraded_abnormal_snapshot = (
        allow_display_degraded_abnormal_snapshot
        if allow_display_degraded_abnormal_snapshot is not None
        else globals().get("allow_display_degraded_abnormal_snapshot", False)
    )
    return build_market_research_context_bundle_contract(
        data,
        target_date,
        exit_analysis,
        final_gate,
        position_level,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        main_sectors=main_sectors,
        secondary_sectors=secondary_sectors,
        dragon_stocks=dragon_stocks,
        get_active_a_kill_records=get_active_a_kill_records,
        normalize_stock_code=normalize_stock_code,
        safe_float=safe_float,
        is_stock_in_a_kill_cooldown=is_stock_in_a_kill_cooldown,
        sector_name_matches=sector_name_matches,
        build_abnormal_watch_pool=build_abnormal_watch_pool,
        decision_strict_mode=current_decision_strict_mode,
        allow_display_degraded_abnormal_snapshot=current_allow_display_degraded_abnormal_snapshot,
        is_degraded_abnormal_snapshot=is_degraded_abnormal_snapshot,
        build_sector_trend_snapshot=build_sector_trend_snapshot,
        build_leader_memory_bank=build_leader_memory_bank,
        refresh_tracking_memory=refresh_tracking_memory,
        discover_all_gem_breathing_candidates=discover_all_gem_breathing_candidates,
        candidate_matches_mainline=candidate_matches_mainline,
        build_gem_observation_pool=build_gem_observation_pool,
        build_mainline_competition_snapshot=build_mainline_competition_snapshot,
        build_market_observation_snapshot=build_market_observation_snapshot,
        build_market_research_snapshot=build_market_research_snapshot,
        derive_step0_follow_plan=derive_step0_follow_plan,
        save_observation_pools=save_observation_pools_runtime,
    )
