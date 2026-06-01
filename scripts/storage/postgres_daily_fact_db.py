from __future__ import annotations

import datetime as _dt
import importlib
import json
from contextlib import contextmanager

POSTGRES_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS market_cycle_days (
        trade_date DATE NOT NULL,
        week_label TEXT NOT NULL DEFAULT '',
        weekday_name TEXT NOT NULL DEFAULT '',
        mainline TEXT NOT NULL DEFAULT '',
        daily_attack_line TEXT NOT NULL DEFAULT '',
        market_state TEXT NOT NULL DEFAULT '',
        cycle_label TEXT NOT NULL DEFAULT '',
        cycle_stage TEXT NOT NULL DEFAULT '',
        transfer_state TEXT NOT NULL DEFAULT '',
        tomorrow_validation TEXT NOT NULL DEFAULT '',
        interpretation TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, weekday_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_cycle_periods (
        trade_date DATE NOT NULL,
        cycle_label TEXT NOT NULL,
        date_range TEXT NOT NULL DEFAULT '',
        trading_days INTEGER NOT NULL DEFAULT 0,
        mainline TEXT NOT NULL DEFAULT '',
        attack_line TEXT NOT NULL DEFAULT '',
        cycle_stage TEXT NOT NULL DEFAULT '',
        transfer_state TEXT NOT NULL DEFAULT '',
        market_state TEXT NOT NULL DEFAULT '',
        tomorrow_validation TEXT NOT NULL DEFAULT '',
        interpretation TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, cycle_label)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mainline_daily (
        trade_date DATE PRIMARY KEY,
        primary_mainline TEXT NOT NULL DEFAULT '',
        daily_attack_line TEXT NOT NULL DEFAULT '',
        secondary_mainline TEXT NOT NULL DEFAULT '',
        competition_mainline TEXT NOT NULL DEFAULT '',
        rotation_label TEXT NOT NULL DEFAULT '',
        leading_line TEXT NOT NULL DEFAULT '',
        state_code TEXT NOT NULL DEFAULT '',
        market_state TEXT NOT NULL DEFAULT '',
        confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
        rotation_summary TEXT NOT NULL DEFAULT '',
        source_policy TEXT NOT NULL DEFAULT '',
        source_run_id BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mainline_switch_events (
        trade_date DATE PRIMARY KEY,
        previous_mainline TEXT NOT NULL DEFAULT '',
        current_mainline TEXT NOT NULL DEFAULT '',
        switch_label TEXT NOT NULL DEFAULT '',
        switch_reason TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mainline_turnover_daily (
        trade_date DATE NOT NULL,
        primary_mainline TEXT NOT NULL,
        turnover_scope_key TEXT NOT NULL DEFAULT '',
        turnover_scope_label TEXT NOT NULL DEFAULT '',
        sector_turnover_yi DOUBLE PRECISION NOT NULL DEFAULT 0,
        total_turnover_yi DOUBLE PRECISION NOT NULL DEFAULT 0,
        turnover_share_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
        source_policy TEXT NOT NULL DEFAULT '',
        source_run_id BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, primary_mainline, turnover_scope_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_daily_totals (
        trade_date DATE NOT NULL,
        market_scope TEXT NOT NULL,
        total_amount_yi DOUBLE PRECISION NOT NULL DEFAULT 0,
        stock_count INTEGER NOT NULL DEFAULT 0,
        source_policy TEXT NOT NULL DEFAULT '',
        source_run_id BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, market_scope)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS monthly_account_ledger (
        trade_date DATE NOT NULL,
        account_id TEXT NOT NULL DEFAULT 'main',
        month_key TEXT NOT NULL DEFAULT '',
        month_return_pct DOUBLE PRECISION,
        simulated_cumulative_return_pct DOUBLE PRECISION,
        equity DOUBLE PRECISION,
        cash DOUBLE PRECISION,
        position_market_value DOUBLE PRECISION,
        realized_pnl DOUBLE PRECISION,
        unrealized_pnl DOUBLE PRECISION,
        max_drawdown_pct DOUBLE PRECISION,
        planned_trade_count INTEGER NOT NULL DEFAULT 0,
        unplanned_trade_count INTEGER NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '',
        source_policy TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, account_id)
    )
    """,
    "ALTER TABLE monthly_account_ledger ADD COLUMN IF NOT EXISTS simulated_cumulative_return_pct DOUBLE PRECISION",
    "CREATE INDEX IF NOT EXISTS idx_monthly_account_ledger_account_month_date ON monthly_account_ledger(account_id, month_key, trade_date)",
    """
    CREATE TABLE IF NOT EXISTS index_daily_bars (
        index_code TEXT NOT NULL,
        trade_date DATE NOT NULL,
        open DOUBLE PRECISION NOT NULL DEFAULT 0,
        high DOUBLE PRECISION NOT NULL DEFAULT 0,
        low DOUBLE PRECISION NOT NULL DEFAULT 0,
        close DOUBLE PRECISION NOT NULL DEFAULT 0,
        volume DOUBLE PRECISION NOT NULL DEFAULT 0,
        amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        source_policy TEXT NOT NULL DEFAULT '',
        source_run_id BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (index_code, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_minute_bars (
        index_code TEXT NOT NULL,
        trade_date DATE NOT NULL,
        period TEXT NOT NULL DEFAULT '60',
        bar_time TEXT NOT NULL DEFAULT '',
        open DOUBLE PRECISION NOT NULL DEFAULT 0,
        high DOUBLE PRECISION NOT NULL DEFAULT 0,
        low DOUBLE PRECISION NOT NULL DEFAULT 0,
        close DOUBLE PRECISION NOT NULL DEFAULT 0,
        volume DOUBLE PRECISION NOT NULL DEFAULT 0,
        amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        source_policy TEXT NOT NULL DEFAULT '',
        source_run_id BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (index_code, trade_date, period, bar_time)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sector_fund_flow_daily (
        trade_date DATE NOT NULL,
        sector_name TEXT NOT NULL,
        net_inflow_yi DOUBLE PRECISION NOT NULL DEFAULT 0,
        source_policy TEXT NOT NULL DEFAULT '',
        source_run_id BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, sector_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sector_attack_evidence_daily (
        trade_date DATE NOT NULL,
        sector_name TEXT NOT NULL,
        net_inflow_rank INTEGER NOT NULL DEFAULT 0,
        net_inflow_amount_yi DOUBLE PRECISION NOT NULL DEFAULT 0,
        limit_up_count INTEGER NOT NULL DEFAULT 0,
        high_anchor_height INTEGER NOT NULL DEFAULT 0,
        sector_turnover_yi DOUBLE PRECISION NOT NULL DEFAULT 0,
        total_turnover_yi DOUBLE PRECISION NOT NULL DEFAULT 0,
        turnover_share_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
        turnover_share_change DOUBLE PRECISION NOT NULL DEFAULT 0,
        source_policy TEXT NOT NULL DEFAULT '',
        source_run_id BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, sector_name)
    )
    """,
    "ALTER TABLE sector_attack_evidence_daily ADD COLUMN IF NOT EXISTS sector_turnover_yi DOUBLE PRECISION NOT NULL DEFAULT 0",
    "ALTER TABLE sector_attack_evidence_daily ADD COLUMN IF NOT EXISTS total_turnover_yi DOUBLE PRECISION NOT NULL DEFAULT 0",
    "ALTER TABLE sector_attack_evidence_daily ADD COLUMN IF NOT EXISTS source_policy TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE sector_attack_evidence_daily ADD COLUMN IF NOT EXISTS source_run_id BIGINT NOT NULL DEFAULT 0",
    """
    CREATE TABLE IF NOT EXISTS sector_diffusion_score_daily (
        trade_date DATE NOT NULL,
        sector_name TEXT NOT NULL,
        total_score DOUBLE PRECISION NOT NULL DEFAULT 0,
        level TEXT NOT NULL DEFAULT '',
        conclusion TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, sector_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sector_diffusion_score_components (
        trade_date DATE NOT NULL,
        sector_name TEXT NOT NULL,
        component_key TEXT NOT NULL,
        score DOUBLE PRECISION NOT NULL DEFAULT 0,
        label TEXT NOT NULL DEFAULT '',
        detail TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, sector_name, component_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sector_competition_daily (
        trade_date DATE NOT NULL,
        sector_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT '',
        evidence TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, sector_name, role)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_capacity_evolution_daily (
        trade_date DATE PRIMARY KEY,
        phase TEXT NOT NULL DEFAULT '',
        turnover_quality TEXT NOT NULL DEFAULT '',
        mainline_regime TEXT NOT NULL DEFAULT '',
        window_state TEXT NOT NULL DEFAULT '',
        capacity_evidence TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS zhongshu_mainline_records (
        trade_date DATE NOT NULL,
        date_range TEXT NOT NULL DEFAULT '',
        pivot_level TEXT NOT NULL DEFAULT '',
        pivot_range TEXT NOT NULL DEFAULT '',
        position TEXT NOT NULL DEFAULT '',
        structure_state TEXT NOT NULL DEFAULT '',
        mainline TEXT NOT NULL DEFAULT '',
        mainline_degree TEXT NOT NULL DEFAULT '',
        evolution TEXT NOT NULL DEFAULT '',
        replacement TEXT NOT NULL DEFAULT '',
        interpretation TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, date_range, mainline)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_observation_pool_items (
        trade_date DATE NOT NULL,
        pool_key TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL DEFAULT '',
        sector_name TEXT NOT NULL DEFAULT '',
        rank_no INTEGER NOT NULL DEFAULT 0,
        score DOUBLE PRECISION NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        action_text TEXT NOT NULL DEFAULT '',
        source_policy TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, pool_key, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS observation_pool_lifecycle (
        stock_code TEXT NOT NULL,
        pool_key TEXT NOT NULL,
        first_seen_date DATE,
        last_seen_date DATE,
        status TEXT NOT NULL DEFAULT '',
        confirmations INTEGER NOT NULL DEFAULT 0,
        failures INTEGER NOT NULL DEFAULT 0,
        appearances INTEGER NOT NULL DEFAULT 0,
        last_reason TEXT NOT NULL DEFAULT '',
        follow_state TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (stock_code, pool_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leader_memory_items (
        trade_date DATE NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL DEFAULT '',
        sector_name TEXT NOT NULL DEFAULT '',
        remember_score DOUBLE PRECISION NOT NULL DEFAULT 0,
        remember_reason TEXT NOT NULL DEFAULT '',
        action_rule TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tracking_memory_daily_status (
        trade_date DATE NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL DEFAULT '',
        sector_name TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        first_seen_date DATE,
        last_seen_date DATE,
        confirmations INTEGER NOT NULL DEFAULT 0,
        failures INTEGER NOT NULL DEFAULT 0,
        appearances INTEGER NOT NULL DEFAULT 0,
        sources_text TEXT NOT NULL DEFAULT '',
        last_reason TEXT NOT NULL DEFAULT '',
        follow_state TEXT NOT NULL DEFAULT '',
        evidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
        inactive_reason TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS a_kill_cooling_items (
        stock_code TEXT PRIMARY KEY,
        stock_name TEXT NOT NULL DEFAULT '',
        sector_name TEXT NOT NULL DEFAULT '',
        a_kill_date DATE,
        ban_until DATE,
        reason TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_performance_ledger (
        mode TEXT NOT NULL,
        report_date DATE NOT NULL,
        action_type TEXT NOT NULL DEFAULT '',
        anchor_type TEXT NOT NULL DEFAULT '',
        position_level TEXT NOT NULL DEFAULT '',
        operation_state TEXT NOT NULL DEFAULT '',
        execution_status TEXT NOT NULL DEFAULT '',
        can_new_entry BOOLEAN NOT NULL DEFAULT false,
        final_action TEXT NOT NULL DEFAULT '',
        mainline_name TEXT NOT NULL DEFAULT '',
        stock_code TEXT NOT NULL DEFAULT '',
        stock_name TEXT NOT NULL DEFAULT '',
        stock_sector TEXT NOT NULL DEFAULT '',
        factor_snapshot_path TEXT NOT NULL DEFAULT '',
        version TEXT NOT NULL DEFAULT '',
        updated_at_text TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (mode, report_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_performance_record_fields (
        mode TEXT NOT NULL,
        report_date DATE NOT NULL,
        field_name TEXT NOT NULL,
        value_text TEXT NOT NULL DEFAULT '',
        value_number DOUBLE PRECISION,
        value_bool BOOLEAN,
        value_kind TEXT NOT NULL DEFAULT 'text',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (mode, report_date, field_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_factor_snapshots (
        mode TEXT NOT NULL,
        report_date DATE NOT NULL,
        version TEXT NOT NULL DEFAULT '',
        market_branch TEXT NOT NULL DEFAULT '',
        source_policy TEXT NOT NULL DEFAULT '',
        saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (mode, report_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_factor_snapshot_fields (
        mode TEXT NOT NULL,
        report_date DATE NOT NULL,
        field_path TEXT NOT NULL,
        value_text TEXT NOT NULL DEFAULT '',
        value_number DOUBLE PRECISION,
        value_bool BOOLEAN,
        value_kind TEXT NOT NULL DEFAULT 'text',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (mode, report_date, field_path)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_factor_snapshot_pool_items (
        mode TEXT NOT NULL,
        report_date DATE NOT NULL,
        pool_name TEXT NOT NULL,
        ordinal INTEGER NOT NULL DEFAULT 0,
        stock_code TEXT NOT NULL DEFAULT '',
        stock_name TEXT NOT NULL DEFAULT '',
        sector_name TEXT NOT NULL DEFAULT '',
        action_type TEXT NOT NULL DEFAULT '',
        participation_mode TEXT NOT NULL DEFAULT '',
        position_pct INTEGER NOT NULL DEFAULT 0,
        setup_signal_id TEXT NOT NULL DEFAULT '',
        setup_signal_label TEXT NOT NULL DEFAULT '',
        follow_state TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        final_action TEXT NOT NULL DEFAULT '',
        trigger_text TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (mode, report_date, pool_name, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_trace_artifacts (
        trade_date DATE PRIMARY KEY,
        artifact_version INTEGER NOT NULL DEFAULT 0,
        visible_scope TEXT NOT NULL DEFAULT '',
        generated_at TEXT NOT NULL DEFAULT '',
        source_report_path TEXT NOT NULL DEFAULT '',
        source_report_variant TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_trace_rows (
        trade_date DATE NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL DEFAULT '',
        tier TEXT NOT NULL DEFAULT '',
        mainline TEXT NOT NULL DEFAULT '',
        sector_name TEXT NOT NULL DEFAULT '',
        final_action TEXT NOT NULL DEFAULT '',
        visible_summary TEXT NOT NULL DEFAULT '',
        trigger_condition TEXT NOT NULL DEFAULT '',
        failure_condition TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_trace_eliminated_groups (
        trade_date DATE NOT NULL,
        reason TEXT NOT NULL,
        count_value INTEGER NOT NULL DEFAULT 0,
        representatives_text TEXT NOT NULL DEFAULT '',
        treatment TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, reason)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_trace_row_fields (
        trade_date DATE NOT NULL,
        stock_code TEXT NOT NULL,
        field_name TEXT NOT NULL,
        value_text TEXT NOT NULL DEFAULT '',
        value_number DOUBLE PRECISION,
        value_bool BOOLEAN,
        value_kind TEXT NOT NULL DEFAULT 'text',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, stock_code, field_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_report_fact_fields (
        trade_date DATE NOT NULL,
        field_path TEXT NOT NULL,
        value_text TEXT NOT NULL DEFAULT '',
        value_number DOUBLE PRECISION,
        value_bool BOOLEAN,
        value_kind TEXT NOT NULL DEFAULT 'text',
        source_policy TEXT NOT NULL DEFAULT 'postgresql.daily_report_facts',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, field_path)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS extreme_conviction_cases (
        case_id TEXT PRIMARY KEY,
        trade_date DATE NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL DEFAULT '',
        first_seen_trade_date DATE,
        cycle_start_trade_date DATE,
        cycle_day INTEGER NOT NULL DEFAULT 0,
        cycle_length_trade_days INTEGER NOT NULL DEFAULT 0,
        sector_candidate TEXT NOT NULL DEFAULT '',
        stock_setup TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS extreme_conviction_mentions (
        record_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL DEFAULT '',
        mention_trade_date DATE NOT NULL,
        stock_code TEXT NOT NULL DEFAULT '',
        stock_name TEXT NOT NULL DEFAULT '',
        rank_no INTEGER NOT NULL DEFAULT 0,
        sector_candidate TEXT NOT NULL DEFAULT '',
        buy_window TEXT NOT NULL DEFAULT '',
        planned_window TEXT NOT NULL DEFAULT '',
        review_status TEXT NOT NULL DEFAULT '',
        next_action TEXT NOT NULL DEFAULT '',
        invalidation TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        source_section TEXT NOT NULL DEFAULT '',
        is_a_kill_eliminated BOOLEAN NOT NULL DEFAULT false,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS extreme_conviction_hypotheses (
        case_id TEXT PRIMARY KEY,
        sector_candidate TEXT NOT NULL DEFAULT '',
        stock_setup TEXT NOT NULL DEFAULT '',
        market_branch TEXT NOT NULL DEFAULT '',
        sector_relationship_state TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS planned_participations (
        record_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL DEFAULT '',
        participation_window TEXT NOT NULL DEFAULT '',
        attack_state TEXT NOT NULL DEFAULT '',
        source_tier TEXT NOT NULL DEFAULT '',
        entry_timing TEXT NOT NULL DEFAULT '',
        buy_window TEXT NOT NULL DEFAULT '',
        missed_action TEXT NOT NULL DEFAULT '',
        cancellation TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS planned_participation_steps (
        record_id TEXT NOT NULL,
        step_key TEXT NOT NULL,
        step_text TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (record_id, step_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS participation_reviews (
        record_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL DEFAULT '',
        review_trade_date DATE,
        status TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        evidence TEXT NOT NULL DEFAULT '',
        next_action TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trend_fates (
        case_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        evidence TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cycle_acceptance_reviews (
        case_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        evidence TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runtime_cache_entries (
        namespace TEXT NOT NULL,
        cache_key TEXT NOT NULL,
        target_date TEXT NOT NULL DEFAULT '',
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        source TEXT NOT NULL DEFAULT '',
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (namespace, cache_key, target_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_runtime_cache_entries_expires_at ON runtime_cache_entries(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_runtime_cache_entries_namespace_date ON runtime_cache_entries(namespace, target_date)",
]

_WEEKDAY_FIELDS = ("monday", "tuesday", "wednesday", "thursday", "friday")
_WEEKDAY_NAME_BY_INDEX = dict(enumerate(_WEEKDAY_FIELDS, start=1))
_RECENT_REPLAY_FACT_DATE_COLUMNS = (
    ("daily_report_fact_fields", "trade_date"),
    ("market_cycle_days", "trade_date"),
    ("market_cycle_periods", "trade_date"),
    ("mainline_daily", "trade_date"),
    ("mainline_switch_events", "trade_date"),
    ("mainline_turnover_daily", "trade_date"),
    ("market_daily_totals", "trade_date"),
    ("index_minute_bars", "trade_date"),
    ("sector_fund_flow_daily", "trade_date"),
    ("sector_attack_evidence_daily", "trade_date"),
    ("sector_diffusion_score_daily", "trade_date"),
    ("sector_diffusion_score_components", "trade_date"),
    ("sector_competition_daily", "trade_date"),
    ("market_capacity_evolution_daily", "trade_date"),
    ("zhongshu_mainline_records", "trade_date"),
    ("daily_observation_pool_items", "trade_date"),
    ("leader_memory_items", "trade_date"),
    ("tracking_memory_daily_status", "trade_date"),
    ("a_kill_cooling_items", "a_kill_date"),
    ("strategy_performance_ledger", "report_date"),
    ("strategy_performance_record_fields", "report_date"),
    ("strategy_factor_snapshots", "report_date"),
    ("strategy_factor_snapshot_fields", "report_date"),
    ("strategy_factor_snapshot_pool_items", "report_date"),
    ("candidate_trace_artifacts", "trade_date"),
    ("candidate_trace_rows", "trade_date"),
    ("candidate_trace_eliminated_groups", "trade_date"),
    ("candidate_trace_row_fields", "trade_date"),
    ("extreme_conviction_cases", "trade_date"),
    ("extreme_conviction_mentions", "mention_trade_date"),
    ("participation_reviews", "review_trade_date"),
)
_RECENT_REPLAY_FACT_ORPHAN_DELETES = (
    (
        "planned_participation_steps",
        "record_id",
        "extreme_conviction_mentions",
        "record_id",
    ),
    (
        "planned_participations",
        "record_id",
        "extreme_conviction_mentions",
        "record_id",
    ),
    ("trend_fates", "case_id", "extreme_conviction_cases", "case_id"),
    ("cycle_acceptance_reviews", "case_id", "extreme_conviction_cases", "case_id"),
    ("extreme_conviction_hypotheses", "case_id", "extreme_conviction_cases", "case_id"),
    ("participation_reviews", "case_id", "extreme_conviction_cases", "case_id"),
)
_RECENT_REPLAY_FACT_RANGE_DELETES = (
    ("observation_pool_lifecycle", "last_seen_date", "first_seen_date"),
)
_RECENT_REPLAY_WINDOW_SERIES_PATHS = (
    ("new_high_feedback", "trend_rows"),
    ("top50_turnover_share_series", "rows"),
    ("etf_turnover_series", "rows"),
    ("margin_pressure", "rows"),
)


def _text(value):
    return str(value or "").strip()


def _normalize_index_code(value):
    text = _text(value).lower().replace(".", "")
    if not text:
        return ""
    if text.startswith(("sh", "sz", "bj")):
        return text
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return text
    digits = digits.zfill(6)
    if digits.startswith("399"):
        return f"sz{digits}"
    return f"sh{digits}"


def _normalize_month_key(*, trade_date="", month_key=""):
    month_key = _text(month_key)
    if month_key:
        return month_key
    trade_date = _text(trade_date)
    if len(trade_date) >= 7 and trade_date[4] == "-":
        return trade_date[:7]
    if len(trade_date) >= 6 and trade_date[:6].isdigit():
        return f"{trade_date[:4]}-{trade_date[4:6]}"
    return ""


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _nullable_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compound_monthly_return_pct(values):
    normalized = []
    for value in values or []:
        number = _nullable_float(value)
        if number is None:
            continue
        normalized.append(number / 100.0)
    if not normalized:
        return None
    try:
        from report.strategy_tracking_support import compound_returns

        compounded = compound_returns(normalized)
    except Exception:
        nav = 1.0
        for value in normalized:
            nav *= 1.0 + value
        compounded = nav - 1.0
    return round(compounded * 100.0, 4)


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return int(default)
        text = str(value).strip()
        if text.endswith("日"):
            text = text[:-1]
        return int(float(text))
    except (TypeError, ValueError):
        return int(default)


def _date_or_none(value):
    text = _text(value)
    if not text:
        return None
    try:
        return _dt.datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return text


def _date_obj_or_none(value):
    text = _date_or_none(value)
    if not text:
        return None
    try:
        return _dt.datetime.strptime(str(text)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _weekday_name_for_date(value):
    date_obj = _date_obj_or_none(value)
    if not date_obj:
        return ""
    return _WEEKDAY_NAME_BY_INDEX.get(date_obj.isoweekday(), "")


def _week_label_for_date(value):
    date_obj = _date_obj_or_none(value)
    if not date_obj:
        return ""
    week_start = date_obj - _dt.timedelta(days=date_obj.weekday())
    return week_start.strftime("%m-%d当周")


def _rows_at_path(data, path):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return []
        current = current.get(key)
    if isinstance(current, list):
        return current
    return []


def _replay_window_series_dates(data, path):
    dates = []
    for row in _rows_at_path(data or {}, path):
        if not isinstance(row, dict):
            continue
        date_obj = _date_obj_or_none(row.get("trade_date") or row.get("date"))
        if date_obj:
            dates.append(date_obj.isoformat())
    return sorted(set(dates))


def _recent_replay_min_trade_date(trade_date, data, *, window_days=25):
    target = _date_obj_or_none(trade_date)
    if not target:
        return None
    target_text = target.isoformat()
    window_days = max(_safe_int(window_days, 25), 1)
    series_candidates = []
    for path in _RECENT_REPLAY_WINDOW_SERIES_PATHS:
        dates = [date for date in _replay_window_series_dates(data, path) if date <= target_text]
        if len(dates) >= window_days:
            if target_text in dates:
                return dates[-window_days]
            series_candidates.append(dates[-window_days])
    if not series_candidates:
        return None
    return max(series_candidates)


def _recent_replay_window_status(trade_date, data, *, window_days=25):
    target = _date_obj_or_none(trade_date)
    if not target:
        return {
            "status": "invalid_target_date",
            "available_days": 0,
            "required_days": max(_safe_int(window_days, 25), 1),
            "min_trade_date": "",
            "max_trade_date": "",
        }
    target_text = target.isoformat()
    dates = sorted(
        {
            date
            for path in _RECENT_REPLAY_WINDOW_SERIES_PATHS
            for date in _replay_window_series_dates(data, path)
            if date <= target_text
        }
    )
    required_days = max(_safe_int(window_days, 25), 1)
    return {
        "status": "ready" if len(dates) >= required_days else "insufficient",
        "available_days": len(dates),
        "required_days": required_days,
        "min_trade_date": dates[0] if dates else "",
        "max_trade_date": dates[-1] if dates else "",
    }


def _is_before_min_trade_date(value, min_trade_date):
    if not min_trade_date:
        return False
    row_date = _date_or_none(value)
    return bool(row_date and row_date < min_trade_date)


def _hot_sector_alias_key(value):
    return _text(value)


def _hot_sector_query_names(values):
    expanded = []
    for value in values or []:
        text = _text(value)
        if text and text not in expanded:
            expanded.append(text)
    return expanded


def _stock_code(item):
    code = _text((item or {}).get("stock_code") or (item or {}).get("code") or (item or {}).get("代码"))
    if "." in code:
        code = code.split(".", 1)[0]
    return "".join(ch for ch in code if ch.isdigit()) or code


def _stock_name(item):
    item = item or {}
    return _text(item.get("stock_name") or item.get("name") or item.get("名称") or item.get("股票简称"))


def _sector_name(item):
    item = item or {}
    return _text(item.get("sector_name") or item.get("sector") or item.get("所属板块") or item.get("industry"))


def _first_text(item, *keys):
    item = item or {}
    for key in keys:
        value = _text(item.get(key))
        if value:
            return value
    return ""


def _record_id(case, mention):
    mention_date = _text((mention or {}).get("mention_trade_date") or (case or {}).get("trade_date"))
    code = _text((case or {}).get("stock_code"))
    rank = _safe_int((mention or {}).get("rank") or (mention or {}).get("rank_no"), 1)
    return _text((mention or {}).get("record_id")) or f"{mention_date}:{code}:{rank}"


def _row_dict(row, columns):
    if not row:
        return {}
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(zip(columns, row))


def _typed_value(value):
    if isinstance(value, bool):
        return ("", None, value, "bool")
    if isinstance(value, dict):
        return ("", None, None, "empty_dict")
    if isinstance(value, (list, tuple)):
        return ("", None, None, "empty_list")
    if isinstance(value, int) and not isinstance(value, bool):
        return ("", float(value), None, "number")
    if isinstance(value, float):
        return ("", float(value), None, "number")
    if value is None:
        return ("", None, None, "none")
    return (_text(value), None, None, "text")


def _restore_typed_value(row):
    value_kind = _text((row or {}).get("value_kind"))
    if value_kind == "bool":
        return bool((row or {}).get("value_bool"))
    if value_kind == "number":
        number = (row or {}).get("value_number")
        if number is None:
            return 0
        try:
            number = float(number)
        except (TypeError, ValueError):
            return 0
        return int(number) if number.is_integer() else number
    if value_kind == "none":
        return None
    if value_kind == "empty_dict":
        return {}
    if value_kind == "empty_list":
        return []
    return _text((row or {}).get("value_text"))


def _iter_structured_scalar_fields(value, *, prefix="", max_depth=5):
    if max_depth < 0:
        return
    if isinstance(value, dict):
        if not value and prefix:
            yield prefix, {}
            return
        for key in sorted(value.keys()):
            key_text = _text(key)
            if not key_text:
                continue
            path = f"{prefix}.{key_text}" if prefix else key_text
            yield from _iter_structured_scalar_fields(value.get(key), prefix=path, max_depth=max_depth - 1)
        return
    if isinstance(value, (list, tuple)):
        if not value and prefix:
            yield prefix, []
            return
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            yield from _iter_structured_scalar_fields(item, prefix=path, max_depth=max_depth - 1)
        return
    if isinstance(value, set):
        return
    yield prefix, value


def _encode_fact_path_part(part):
    if isinstance(part, int):
        return f"#{part}"
    text = _text(part)
    return f"k:{len(text)}:{text}"


def _decode_fact_path(path):
    text = _text(path)
    parts = []
    index = 0
    while index < len(text):
        if text[index] == "#":
            end = text.find("/", index)
            token = text[index + 1:] if end < 0 else text[index + 1:end]
            try:
                parts.append(int(token))
            except ValueError:
                parts.append(token)
            index = len(text) if end < 0 else end + 1
            continue
        if not text.startswith("k:", index):
            end = text.find("/", index)
            token = text[index:] if end < 0 else text[index:end]
            if token:
                parts.append(token)
            index = len(text) if end < 0 else end + 1
            continue
        length_start = index + 2
        length_end = text.find(":", length_start)
        if length_end < 0:
            break
        try:
            key_length = int(text[length_start:length_end])
        except ValueError:
            break
        key_start = length_end + 1
        key = text[key_start:key_start + key_length]
        parts.append(key)
        index = key_start + key_length
        if index < len(text) and text[index] == "/":
            index += 1
    return parts


def _field_path_has_low_value_component(field_path):
    parts = _decode_fact_path(field_path)
    for index, part in enumerate(parts):
        if index == 0 and _text(part) in _DAILY_REPORT_FACT_TOP_LEVEL_KEYS:
            continue
        if _is_low_value_fact_key(part):
            return True
    return False


def _iter_safe_fact_fields(value, *, parts=(), max_depth=8):
    if max_depth < 0:
        return
    if isinstance(value, dict):
        if not value and parts:
            yield "/".join(_encode_fact_path_part(part) for part in parts), {}
            return
        for key in sorted(value.keys(), key=lambda item: _text(item)):
            key_text = _text(key)
            if not key_text:
                continue
            yield from _iter_safe_fact_fields(
                value.get(key),
                parts=parts + (key_text,),
                max_depth=max_depth - 1,
            )
        return
    if isinstance(value, (list, tuple)):
        if not value and parts:
            yield "/".join(_encode_fact_path_part(part) for part in parts), []
            return
        for item_index, item in enumerate(value):
            yield from _iter_safe_fact_fields(
                item,
                parts=parts + (item_index,),
                max_depth=max_depth - 1,
            )
        return
    if isinstance(value, set):
        return
    yield "/".join(_encode_fact_path_part(part) for part in parts), value


_LOW_VALUE_FACT_KEYS = {
    "appendix_b",
    "appendix_c",
    "calibration_rows",
    "candidate_trace_payload",
    "day_rows",
    "debug_payload",
    "decision_ledger_artifacts",
    "details_payload",
    "diagnostics_error",
    "diagnostics_status",
    "duplicate",
    "huge_cache",
    "large_rendered_context",
    "market_research_snapshot",
    "module_logs",
    "payload",
    "payload_json",
    "raw",
    "raw_detail",
    "raw_notice",
    "recent_bars",
    "rendered_tail",
    "request_diagnostics",
    "sector_evidence_rows",
    "sector_tree",
    "step2_bundle",
    "step3_bundle",
    "step_status",
}


def _is_low_value_fact_key(key):
    key = _text(key)
    key_lower = key.lower()
    if key_lower in _LOW_VALUE_FACT_KEYS:
        return True
    if key_lower.startswith(("raw_", "debug_", "cache_")):
        return True
    if key_lower.endswith(("_payload", "_json", "_raw", "_cache")):
        return True
    return False


def _sanitize_fact_value(value, *, max_depth=8):
    if max_depth < 0:
        return None
    if isinstance(value, dict):
        result = {}
        for key in sorted(value.keys(), key=lambda item: _text(item)):
            if _is_low_value_fact_key(key):
                continue
            sanitized = _sanitize_fact_value(value.get(key), max_depth=max_depth - 1)
            if sanitized in (None, "", [], {}):
                continue
            result[_text(key)] = sanitized
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            sanitized = _sanitize_fact_value(item, max_depth=max_depth - 1)
            if sanitized in (None, "", [], {}):
                continue
            result.append(sanitized)
        return result
    if isinstance(value, set):
        return None
    return value


def _set_nested_fact_value(target, path, value):
    parts = _decode_fact_path(path)
    if not parts:
        return
    current = target
    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        next_part = None if is_last else parts[index + 1]
        if isinstance(part, int):
            if not isinstance(current, list):
                return
            while len(current) <= part:
                current.append(None if is_last else _structured_container_for(next_part))
            if is_last:
                current[part] = value
                return
            expected = _structured_container_for(next_part)
            if not isinstance(current[part], type(expected)):
                current[part] = expected
            current = current[part]
            continue
        if is_last:
            current[part] = value
            return
        expected = _structured_container_for(next_part)
        if not isinstance(current.get(part), type(expected)):
            current[part] = expected
        current = current[part]


def _parse_structured_field_path(path):
    path = _text(path)
    parts = []
    token = ""
    index = 0
    while index < len(path):
        char = path[index]
        if char == ".":
            if token:
                parts.append(token)
                token = ""
            index += 1
            continue
        if char == "[":
            if token:
                parts.append(token)
                token = ""
            close_index = path.find("]", index)
            if close_index < 0:
                token += char
                index += 1
                continue
            try:
                parts.append(int(path[index + 1:close_index]))
            except ValueError:
                parts.append(path[index + 1:close_index])
            index = close_index + 1
            continue
        token += char
        index += 1
    if token:
        parts.append(token)
    return parts


def _structured_container_for(next_part):
    return [] if isinstance(next_part, int) else {}


def _set_nested_value(target, path, value):
    parts = _parse_structured_field_path(path)
    if not parts:
        return
    current = target
    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        next_part = None if is_last else parts[index + 1]
        if isinstance(part, int):
            if not isinstance(current, list):
                return
            while len(current) <= part:
                current.append(None if is_last else _structured_container_for(next_part))
            if is_last:
                current[part] = value
                return
            expected = _structured_container_for(next_part)
            if not isinstance(current[part], type(expected)):
                current[part] = expected
            current = current[part]
            continue
        if is_last:
            current[part] = value
            return
        expected = _structured_container_for(next_part)
        if not isinstance(current.get(part), type(expected)):
            current[part] = expected
        current = current[part]


def _set_nested_list(target, path, value):
    parts = _parse_structured_field_path(path)
    if not parts:
        return
    current = target
    for part in parts[:-1]:
        if isinstance(part, int):
            return
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    last = parts[-1]
    if isinstance(last, int):
        return
    existing = current.get(last)
    if isinstance(existing, list):
        merged = []
        for index, item in enumerate(value or []):
            existing_item = existing[index] if index < len(existing) and isinstance(existing[index], dict) else {}
            if isinstance(item, dict):
                merged.append({**existing_item, **item})
            else:
                merged.append(item)
        if len(existing) > len(merged):
            merged.extend(existing[len(merged):])
        current[last] = merged
        return
    current[last] = value


_DAILY_REPORT_FACT_TOP_LEVEL_KEYS = (
    "total_turnover",
    "turnover_data",
    "indices",
    "wind_a_alternative",
    "csi1000_index",
    "turnover_rank",
    "market_stats",
    "hot_rank_top50",
    "hot_rank_top30",
    "integrated_hot_list",
    "calendar_events",
    "xuangubao_data",
    "wanzhu_top10",
    "lianban_data",
    "new_high_feedback",
    "top50_turnover_share_series",
    "etf_turnover_series",
    "concept_fund_flow",
    "sector_fund_flow",
    "sector_change_up",
    "sector_change_down",
    "hot_plates",
    "margin_pressure",
    "lhb_analysis",
    "lhb_net_buy_top10",
    "lhb_net_sell_top10",
    "xueqiu_hot_rank_top100",
    "xueqiu_hot_stock_arguments",
    "data_status",
    "zt_pool",
    "dt_pool",
    "zt_pool_by_sector",
    "dt_pool_by_sector",
    "limit_up_codes",
    "limit_down_codes",
    "market_research_snapshot",
    "mainline_turnover_summary",
    "current_mainline_history_record",
    "recent_mainline_history",
    "current_sector_turnover_snapshot",
    "recent_sector_turnover_history",
    "market_structure_judgement",
    "sector_ai_analysis",
    "sector_quadrant",
    "realtime_tag_evidence_snapshot",
    "exchange_monitor_today",
    "exchange_monitor_nextday",
    "new_stock_research_pool",
    "new_stock_candidate_upgrades",
    "dragon_rebound_watch_pool",
    "entry_cycle_calibration",
    "candidate_trace_artifact",
    "recent_extreme_conviction_mentions",
    "recent_extreme_conviction_mentions_for_review",
    "extreme_conviction_list",
    "execution_stage_context",
    "personal_position_context",
    "position_context_provided",
    "selected_position_candidate",
)

_EXECUTION_CONTEXT_FACT_KEYS = (
    "final_gate",
    "position_decision",
    "position_reason",
    "market_state_snapshot",
    "core_stocks",
    "secondary_stocks",
    "crossline_observation_stocks",
    "gem_observation_stocks",
    "generic_watch_stocks",
    "waiting_stocks",
    "focus_group",
    "keep_group",
    "delete_group",
    "abnormal_watch_pool",
    "abnormal_watch_pool_all",
    "leader_memory_bank",
    "tracking_memory_status",
    "candidate_traces",
    "candidate_trace_artifact",
    "extreme_conviction_list",
    "recent_extreme_conviction_mentions",
    "special_probe_verdict",
    "watch_anchor",
    "selected_position_candidate",
    "monthly_context",
    "today_predictions",
    "nextday_predictions",
)

_MARKET_RESEARCH_BUNDLE_FACT_KEYS = (
    "step0_plan",
    "main_sectors_info",
    "secondary_sectors_info",
    "sector_trend_snapshot",
    "abnormal_watch_pool",
    "leader_memory_bank",
    "tracking_memory_status",
    "mainline_competition_snapshot",
)

_MARKET_RESEARCH_FACT_KEYS = (
    "market_branch",
    "final_gate",
    "front_page_final_gate",
    "position_decision",
    "selected_position_candidate",
    "state_machine",
    "cycle_calendar_rows",
    "cycle_interpretation_rows",
    "pivot_mainline_rows",
    "mainline_turnover_summary",
    "current_mainline_history_record",
    "recent_mainline_history",
    "current_sector_turnover_snapshot",
    "recent_sector_turnover_history",
    "mainline_competition_snapshot",
    "sector_attack_evidence_rows",
    "diffusion_quality",
    "sector_diffusion_quality",
    "sector_internal_analysis",
    "realtime_tag_evidence_snapshot",
    "candidate_snapshot",
    "observation",
    "extreme_conviction_list",
)


def _bounded_list(items, limit):
    if not isinstance(items, list):
        return items
    result = []
    for item in items[: max(int(limit or 0), 0)]:
        sanitized = _sanitize_fact_value(item)
        if sanitized in (None, "", [], {}):
            continue
        result.append(sanitized)
    return result


def _compact_concept_fund_flow(snapshot, limit=80):
    if not isinstance(snapshot, dict):
        return {}
    result = {}
    for key, value in snapshot.items():
        if _is_low_value_fact_key(key):
            continue
        if key in {"rows", "concepts", "items", "top_rows"} and isinstance(value, list):
            result[key] = _bounded_list(value, limit)
            continue
        sanitized = _sanitize_fact_value(value)
        if sanitized not in (None, "", [], {}):
            result[key] = sanitized
    return result


def _compact_stock_item(item):
    if not isinstance(item, dict):
        return item
    keys = (
        "code",
        "stock_code",
        "name",
        "stock_name",
        "sector",
        "sector_name",
        "industry",
        "score",
        "rank",
        "rank_no",
        "status",
        "source",
        "source_tier",
        "pattern",
        "reason",
        "tomorrow_expectation",
        "follow_state",
        "action_rule",
        "action_text",
        "final_action",
        "participation_mode",
        "participation_window",
        "setup_signal_id",
        "setup_signal_label",
        "watch_anchor_type",
        "watch_anchor_note",
        "change",
        "change_pct",
        "pct_chg",
        "close",
        "high",
        "volume",
        "turnover",
        "amount_yi",
        "topdays",
        "remember_score",
        "remember_reason",
        "invalidation",
        "buy_window",
        "planned_window",
    )
    return {key: item.get(key) for key in keys if key in item and item.get(key) not in (None, "")}


def _compact_stock_list(items, limit=80):
    if not isinstance(items, list):
        return items
    return [_compact_stock_item(item) for item in items[: max(int(limit or 0), 0)]]


def _compact_extreme_conviction_item(item):
    if not isinstance(item, dict):
        return item
    keys = (
        "code",
        "stock_code",
        "name",
        "stock_name",
        "sector",
        "sector_name",
        "source_tier",
        "score",
        "conviction_score",
        "conviction_reason",
        "conviction_rule",
        "reason",
        "tomorrow_expectation",
        "core_level",
        "core_identity",
        "core_identity_label",
        "candidate_layer",
        "execution_eligibility",
        "participation_window",
        "planned_window",
        "buy_window",
        "attack_state",
        "auction_script",
        "first_minutes_script",
        "board_script",
        "reseal_script",
        "missed_action",
        "invalid_condition",
        "invalidation",
        "participation_window_type",
        "required_steps",
        "fallback_state",
        "participation_basis",
        "decision_reason_basis",
        "risk_reward_min_ratio",
        "risk_reward_ratio",
        "risk_reward_state",
        "risk_reward_plan",
        "support_price",
        "branch_20cm",
        "ma20_invalidation",
        "limit_up_inertia_level",
        "limit_up_inertia_score",
        "next_day_limit_probability_band",
        "limit_up_inertia_reason",
        "change",
        "change_pct",
        "close",
        "volume",
    )
    return {key: item.get(key) for key in keys if key in item and item.get(key) not in (None, "", [], {})}


def _compact_extreme_conviction_list(items, limit=80):
    if not isinstance(items, list):
        return items
    return [_compact_extreme_conviction_item(item) for item in items[: max(int(limit or 0), 0)]]


def _compact_extreme_conviction_mention(item):
    if not isinstance(item, dict):
        return item
    keys = (
        "record_id",
        "case_id",
        "mention_trade_date",
        "stock_code",
        "stock_name",
        "rank",
        "rank_no",
        "sector_candidate",
        "buy_window",
        "planned_window",
        "review_status",
        "next_action",
        "invalidation",
        "reason",
        "source_section",
        "is_a_kill_eliminated",
        "updated_at",
    )
    return {key: item.get(key) for key in keys if key in item and item.get(key) not in (None, "", [], {})}


def _compact_extreme_conviction_mentions(items, limit=80):
    if not isinstance(items, list):
        return items
    return [_compact_extreme_conviction_mention(item) for item in items[: max(int(limit or 0), 0)]]


def _compact_candidate_trace_artifact(artifact):
    if not isinstance(artifact, dict):
        return {}
    payload = artifact.get("payload") if isinstance(artifact.get("payload"), dict) else {}
    trace_count = artifact.get("trace_count")
    if trace_count in (None, ""):
        trace_count = len(artifact.get("traces") or payload.get("traces") or [])
    eliminated_count = artifact.get("eliminated_group_count")
    if eliminated_count in (None, ""):
        eliminated_count = len(artifact.get("eliminated_summary") or payload.get("eliminated_summary") or [])
    result = {
        "artifact_path": _text(artifact.get("artifact_path")),
        "trace_count": _safe_int(trace_count),
        "eliminated_group_count": _safe_int(eliminated_count),
        "trade_date": _text(artifact.get("trade_date") or payload.get("trade_date")),
        "visible_scope": _text(artifact.get("visible_scope") or payload.get("visible_scope")),
        "artifact_version": _safe_int(artifact.get("artifact_version") or payload.get("artifact_version")),
    }
    source_report = artifact.get("source_report") if isinstance(artifact.get("source_report"), dict) else payload.get("source_report")
    if isinstance(source_report, dict):
        result["source_report"] = {
            key: source_report.get(key)
            for key in ("path", "variant")
            if source_report.get(key) not in (None, "")
        }
    return {key: value for key, value in result.items() if value not in (None, "", [], {})}


def _compact_sector_fund_flow(snapshot, limit=50):
    if not isinstance(snapshot, dict):
        return {}
    result = {}
    for direction in ("inflow", "outflow"):
        rows = []
        for item in snapshot.get(direction) or []:
            if not isinstance(item, dict):
                continue
            net_inflow = item.get("net_inflow_yi")
            if net_inflow in (None, ""):
                net_inflow = item.get("zljlr")
            if net_inflow in (None, ""):
                net_inflow = item.get("net_inflow")
            rows.append(
                {
                    key: value
                    for key, value in {
                        "name": _text(item.get("name") or item.get("sector_name")),
                        "code": _text(item.get("code")),
                        "net_inflow_yi": _safe_float(net_inflow),
                        "change_pct": _safe_float(item.get("change_pct", item.get("zdf"))),
                        "turnover_yi": _safe_float(item.get("turnover_yi")),
                        "stock_count": _safe_int(item.get("stock_count")),
                        "matched_stock_count": _safe_int(item.get("matched_stock_count")),
                        "data_source": _text(item.get("data_source") or item.get("source")),
                        "trade_date": _text(item.get("trade_date")),
                        "source_date": _text(item.get("source_date")),
                        "query_date": _text(item.get("query_date")),
                    }.items()
                    if value not in (None, "", [], {})
                }
            )
        if rows:
            result[direction] = rows[: max(int(limit or 0), 0)]
    return result


def _compact_mainline_attack_summary(summary):
    if not isinstance(summary, dict):
        return {}
    return {
        key: summary.get(key)
        for key in (
            "attack_state",
            "primary_line",
            "candidate_lines",
            "background_lines",
            "relationship_hint",
            "evidence_labels",
            "confirmation_evidence",
            "evidence_gaps",
        )
        if key in summary and summary.get(key) not in (None, "", [], {})
    }


def _compact_turnover_share_trend_rows(rows, limit=25):
    compacted = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        compacted.append(
            {
                key: row.get(key)
                for key in (
                    "date",
                    "cycle_mainline",
                    "daily_attack_line",
                    "mainline_turnover",
                    "market_turnover",
                    "share",
                    "share_change",
                    "interpretation",
                )
                if key in row and row.get(key) not in (None, "")
            }
        )
    return compacted[-max(int(limit or 0), 0):]


def _compact_hot_sector_turnover_watch_rows(rows, limit=30):
    compacted = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = {
            key: row.get(key)
            for key in (
                "date",
                "sector_name",
                "sector_turnover",
                "market_turnover",
                "total_turnover",
                "share",
                "share_change",
                "sample_status",
                "interpretation",
            )
            if key in row and row.get(key) not in (None, "")
        }
        if item.get("market_turnover") and not item.get("total_turnover"):
            item["total_turnover"] = item.get("market_turnover")
        if item.get("total_turnover") and not item.get("market_turnover"):
            item["market_turnover"] = item.get("total_turnover")
        compacted.append(
            item
        )
    return compacted[-max(int(limit or 0), 0):]


def _compact_mainline_turnover_summary(summary):
    if not isinstance(summary, dict):
        return {}
    result = {
        key: summary.get(key)
        for key in (
            "date",
            "label",
            "current_mainline",
            "previous_mainline",
            "share_trend_label",
            "conclusion",
            "data_text",
            "action_text",
            "turnover_share_trend_summary",
            "hot_sector_turnover_watch_summary",
        )
        if key in summary and summary.get(key) not in (None, "")
    }
    for key in (
        "double_mainline_summary",
        "mainline_capacity_regime_summary",
        "overtake_window_summary",
        "trading_arena_fit_summary",
    ):
        value = summary.get(key)
        if isinstance(value, dict):
            result[key] = {
                sub_key: sub_value
                for sub_key, sub_value in value.items()
                if not isinstance(sub_value, (dict, list, tuple, set)) and sub_value not in (None, "")
            }
    attack_summary = _compact_mainline_attack_summary(summary.get("mainline_attack_evidence_summary"))
    if attack_summary:
        result["mainline_attack_evidence_summary"] = attack_summary
    trend_rows = _compact_turnover_share_trend_rows(summary.get("turnover_share_trend_rows"), limit=25)
    if trend_rows:
        result["turnover_share_trend_rows"] = trend_rows
    hot_watch_rows = _compact_hot_sector_turnover_watch_rows(summary.get("hot_sector_turnover_watch_rows"), limit=30)
    if hot_watch_rows:
        result["hot_sector_turnover_watch_rows"] = hot_watch_rows
    return {key: value for key, value in result.items() if value not in (None, "", [], {})}


def _compact_tracking_memory_status(status):
    if not isinstance(status, dict):
        return status
    result = {}
    for key, value in status.items():
        if key.endswith("_count") or not isinstance(value, list):
            result[key] = value
            continue
        result[key] = [_compact_stock_item(item) for item in value[:80]]
    return result


def _compact_xuangubao_data(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    news_items = snapshot.get("xuangubao_news")
    plate_items = snapshot.get("xuangubao_plates")
    limit_up_reason_items = snapshot.get("xuangubao_limit_up_reasons")
    return {
        "news_count": len(news_items) if isinstance(news_items, list) else _safe_int(snapshot.get("news_count")),
        "plate_count": len(plate_items) if isinstance(plate_items, list) else _safe_int(snapshot.get("plate_count")),
        "limit_up_reason_count": (
            len(limit_up_reason_items)
            if isinstance(limit_up_reason_items, list)
            else _safe_int(snapshot.get("limit_up_reason_count"))
        ),
    }


def _compact_new_high_feedback(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    result = {
        key: snapshot.get(key)
        for key in (
            "available",
            "status",
            "source",
            "new_high_count",
            "all_a_share_pct",
            "leading_sectors",
            "summary",
            "requested_trade_date",
            "factor_trade_date",
        )
        if key in snapshot and snapshot.get(key) not in (None, "")
    }
    sector_distribution = []
    for item in snapshot.get("sector_distribution") or []:
        if not isinstance(item, dict):
            continue
        representatives = item.get("representative_stocks") or []
        if isinstance(representatives, list):
            representatives = representatives[:8]
        sector_distribution.append(
            {
                key: value
                for key, value in {
                    "sector": _text(item.get("sector") or item.get("sector_name")),
                    "new_high_count": _safe_int(item.get("new_high_count")),
                    "amount_yi": _safe_float(item.get("amount_yi")),
                    "share_pct": _safe_float(item.get("share_pct")),
                    "representative_stocks": representatives,
                }.items()
                if value not in (None, "", [], {})
            }
        )
    if sector_distribution:
        result["sector_distribution"] = sector_distribution[:40]
    top_stocks = _compact_stock_list(snapshot.get("top_stocks"), limit=40)
    if top_stocks:
        result["top_stocks"] = top_stocks
    trend_rows = []
    for row in snapshot.get("trend_rows") or []:
        if not isinstance(row, dict):
            continue
        trend_rows.append(
            {
                key: row.get(key)
                for key in ("trade_date", "new_high_count", "all_a_share_pct", "leading_sectors", "change_text")
                if key in row and row.get(key) not in (None, "")
            }
        )
    if trend_rows:
        result["trend_rows"] = trend_rows[-25:]
    return result


def _compact_margin_pressure(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    result = {
        key: snapshot.get(key)
        for key in (
            "available",
            "status",
            "source",
            "latest_pressure_label",
            "latest_data_date",
            "target_date",
            "is_stale_for_target",
            "latest_margin_turnover_ratio_pct",
            "latest_pressure_diff_pct",
            "summary",
            "usage_note",
        )
        if key in snapshot and snapshot.get(key) not in (None, "")
    }
    if isinstance(snapshot.get("calibration"), dict):
        result["calibration"] = {
            key: snapshot["calibration"].get(key)
            for key in ("sample_days", "latest_percentile", "low_ratio_pct", "mid_ratio_pct", "high_ratio_pct")
            if key in snapshot["calibration"]
        }
    rows = []
    for row in snapshot.get("rows") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                key: row.get(key)
                for key in (
                    "trade_date",
                    "margin_balance_yi",
                    "short_selling_balance_yi",
                    "margin_trading_balance_yi",
                    "market_turnover_yi",
                    "margin_turnover_ratio_pct",
                    "pressure_diff_pct",
                    "pressure_label",
                    "exchange_count",
                    "source_policy",
                    "is_market_level_margin_balance",
                    "change_text",
                )
                if key in row and row.get(key) not in (None, "")
            }
        )
    if rows:
        result["rows"] = rows[-25:]
    return result


def _compact_sector_quadrant(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    analysis = snapshot.get("high_strong_analysis") if isinstance(snapshot.get("high_strong_analysis"), dict) else {}
    result = {"provider": _text(snapshot.get("provider"))}
    for key in (
        "total",
        "tier1_count",
        "tier2_count",
        "tier3_count",
        "tier4_count",
        "tier1_best",
        "tier2_good",
        "tier3_normal",
        "tier4_edge",
    ):
        if key in analysis:
            result[key] = analysis.get(key)
    return {key: value for key, value in result.items() if value not in (None, "", [], {})}


def _compact_sector_ai_analysis(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    realtime = snapshot.get("realtime_tag_evidence_snapshot")
    result = {
        "sector_count": _safe_int(snapshot.get("sector_count")),
        "standard_count": _safe_int(snapshot.get("standard_count")),
    }
    if isinstance(realtime, dict):
        result["realtime_tag_evidence_snapshot"] = {
            key: realtime.get(key)
            for key in ("adopted_labels", "summary_text")
            if key in realtime and realtime.get(key) not in (None, "", [], {})
        }
        groups = realtime.get("groups")
        if isinstance(groups, list):
            result["realtime_tag_evidence_snapshot"]["group_count"] = len(groups)
    return {key: value for key, value in result.items() if value not in (None, "", [], {})}


def _compact_entry_cycle_calibration(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    result = {
        key: snapshot.get(key)
        for key in ("as_of_date", "source_status", "source_error")
        if key in snapshot and snapshot.get(key) not in (None, "")
    }
    cases = []
    for item in snapshot.get("cases") or []:
        if not isinstance(item, dict):
            continue
        case = {
            key: value
            for key, value in item.items()
            if key != "day_rows" and not isinstance(value, (dict, list, tuple, set)) and value not in (None, "")
        }
        if case:
            cases.append(case)
    if cases:
        result["cases"] = cases[:20]
    return result


def _compact_special_probe_verdict(snapshot):
    if not isinstance(snapshot, dict):
        return snapshot
    result = {
        key: snapshot.get(key)
        for key in (
            "code",
            "label",
            "summary_text",
            "action",
            "probe_state",
            "allows_attack_50_ready",
            "allows_execute_50",
        )
        if key in snapshot and snapshot.get(key) not in (None, "")
    }
    for key in ("probe_candidate", "selected_candidate", "watch_anchor"):
        if isinstance(snapshot.get(key), dict):
            compacted = _compact_stock_item(snapshot.get(key))
            if compacted:
                result[key] = compacted
    return result


def _compact_market_research_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    result = {}
    for key in _MARKET_RESEARCH_FACT_KEYS:
        if key not in snapshot:
            continue
        value = snapshot.get(key)
        if key in {
            "recent_mainline_history",
            "recent_sector_turnover_history",
            "mainline_competition_snapshot",
            "cycle_calendar_rows",
            "cycle_interpretation_rows",
            "pivot_mainline_rows",
        }:
            result[key] = _bounded_list(value, 80)
            continue
        if key == "mainline_turnover_summary":
            result[key] = _compact_mainline_turnover_summary(value)
            continue
        if key == "extreme_conviction_list":
            result[key] = _compact_extreme_conviction_list(value, limit=80)
            continue
        if key == "candidate_snapshot" and isinstance(value, dict):
            result[key] = {
                "extreme_conviction_list": _compact_extreme_conviction_list(value.get("extreme_conviction_list"), limit=80),
                "selected_position_candidate": _compact_stock_item(value.get("selected_position_candidate")),
            }
            result[key] = {sub_key: sub_value for sub_key, sub_value in result[key].items() if sub_value}
            continue
        if key == "observation" and isinstance(value, dict):
            result[key] = {
                "abnormal_watch_pool": _compact_stock_list(value.get("abnormal_watch_pool"), limit=80),
                "leader_memory_bank": _compact_stock_list(value.get("leader_memory_bank"), limit=80),
                "tracking_memory_status": _compact_tracking_memory_status(value.get("tracking_memory_status")),
                "mainline_competition_snapshot": _bounded_list(value.get("mainline_competition_snapshot"), 80),
            }
            result[key] = {sub_key: sub_value for sub_key, sub_value in result[key].items() if sub_value}
            continue
        if key in {"selected_position_candidate", "position_decision"}:
            result[key] = _compact_stock_item(value) if isinstance(value, dict) else value
            continue
        if key == "special_probe_verdict":
            result[key] = _compact_special_probe_verdict(value)
            continue
        if key == "sector_ai_analysis":
            result[key] = _compact_sector_ai_analysis(value)
            continue
        if key == "sector_internal_analysis" and isinstance(value, dict):
            result[key] = {
                "diffusion_quality": value.get("diffusion_quality"),
                "turnover_trend": value.get("turnover_trend"),
                "quant_environment": value.get("quant_environment"),
                "summary": value.get("summary"),
            }
            result[key] = {sub_key: sub_value for sub_key, sub_value in result[key].items() if sub_value}
            continue
        if key == "sector_attack_evidence_rows":
            continue
        result[key] = value
    return result


def _compact_execution_context(context):
    if not isinstance(context, dict):
        return {}
    result = {}
    for key in _EXECUTION_CONTEXT_FACT_KEYS:
        if key not in context:
            continue
        value = context.get(key)
        if key == "data":
            continue
        if key == "market_research_bundle" and isinstance(value, dict):
            result[key] = {sub_key: value.get(sub_key) for sub_key in _MARKET_RESEARCH_BUNDLE_FACT_KEYS if sub_key in value}
            continue
        if key == "tracking_memory_status":
            result[key] = _compact_tracking_memory_status(value)
            continue
        if key in {"selected_position_candidate", "watch_anchor"}:
            result[key] = _compact_stock_item(value) if isinstance(value, dict) else value
            continue
        if key == "special_probe_verdict":
            result[key] = _compact_special_probe_verdict(value)
            continue
        if key in {
            "core_stocks",
            "secondary_stocks",
            "crossline_observation_stocks",
            "gem_observation_stocks",
            "generic_watch_stocks",
            "waiting_stocks",
            "focus_group",
            "keep_group",
            "delete_group",
            "abnormal_watch_pool",
            "abnormal_watch_pool_all",
            "leader_memory_bank",
            "candidate_traces",
        }:
            result[key] = _compact_stock_list(value)
            continue
        if key == "extreme_conviction_list":
            result[key] = _compact_extreme_conviction_list(value, limit=80)
            continue
        if key == "recent_extreme_conviction_mentions":
            result[key] = _compact_extreme_conviction_mentions(value, limit=80)
            continue
        if key == "candidate_trace_artifact":
            result[key] = _compact_candidate_trace_artifact(value)
            continue
        result[key] = value
    return result


def _build_daily_report_fact_projection(data):
    data = data or {}
    projection = {}
    for key in _DAILY_REPORT_FACT_TOP_LEVEL_KEYS:
        if key not in data:
            continue
        if key == "market_research_snapshot":
            projection[key] = _compact_market_research_snapshot(data.get(key))
            continue
        if key == "execution_stage_context":
            projection[key] = _compact_execution_context(data.get(key))
            continue
        if key == "xuangubao_data":
            projection[key] = _compact_xuangubao_data(data.get(key))
            continue
        if key == "new_high_feedback":
            projection[key] = _compact_new_high_feedback(data.get(key))
            continue
        if key == "margin_pressure":
            projection[key] = _compact_margin_pressure(data.get(key))
            continue
        if key == "sector_quadrant":
            projection[key] = _compact_sector_quadrant(data.get(key))
            continue
        if key == "sector_ai_analysis":
            projection[key] = _compact_sector_ai_analysis(data.get(key))
            continue
        if key == "sector_fund_flow":
            projection[key] = _compact_sector_fund_flow(data.get(key), limit=50)
            continue
        if key == "concept_fund_flow":
            projection[key] = _compact_concept_fund_flow(data.get(key), limit=80)
            continue
        if key == "sector_attack_evidence_rows":
            continue
        if key == "mainline_turnover_summary":
            projection[key] = _compact_mainline_turnover_summary(data.get(key))
            continue
        if key == "entry_cycle_calibration":
            projection[key] = _compact_entry_cycle_calibration(data.get(key))
            continue
        if key == "selected_position_candidate":
            projection[key] = _compact_stock_item(data.get(key))
            continue
        if key == "extreme_conviction_list":
            projection[key] = _compact_extreme_conviction_list(data.get(key), limit=80)
            continue
        if key in {"recent_extreme_conviction_mentions", "recent_extreme_conviction_mentions_for_review"}:
            projection[key] = _compact_extreme_conviction_mentions(data.get(key), limit=120)
            continue
        if key == "candidate_trace_artifact":
            projection[key] = _compact_candidate_trace_artifact(data.get(key))
            continue
        if key in {
            "hot_rank_top50",
            "hot_rank_top30",
            "integrated_hot_list",
            "turnover_rank",
            "zt_pool",
            "dt_pool",
            "lianban_data",
            "xueqiu_hot_rank_top100",
            "xueqiu_hot_stock_arguments",
            "exchange_monitor_today",
            "exchange_monitor_nextday",
            "new_stock_research_pool",
            "new_stock_candidate_upgrades",
            "dragon_rebound_watch_pool",
        }:
            projection[key] = _bounded_list(data.get(key), 120)
            continue
        projection[key] = data.get(key)
    projection["postgres_only"] = True
    return projection


def _observation_pools_from_data(data):
    data = data or {}
    ctx = data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {}
    market = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    observation = market.get("observation") if isinstance(market.get("observation"), dict) else {}
    pools = {}
    sources = (
        ("core_stocks", ctx.get("core_stocks")),
        ("secondary_stocks", ctx.get("secondary_stocks")),
        ("crossline_observation_stocks", ctx.get("crossline_observation_stocks")),
        ("gem_observation_stocks", ctx.get("gem_observation_stocks")),
        ("generic_watch_stocks", ctx.get("generic_watch_stocks")),
        ("waiting_stocks", ctx.get("waiting_stocks")),
        ("focus_group", ctx.get("focus_group")),
        ("keep_group", ctx.get("keep_group")),
        ("abnormal_watch_pool", ctx.get("abnormal_watch_pool") or observation.get("abnormal_watch_pool")),
        ("leader_memory_bank", ctx.get("leader_memory_bank") or observation.get("leader_memory_bank")),
        ("tracking_today_validated", (ctx.get("tracking_memory_status") or {}).get("today_validated_items") or (observation.get("tracking_memory_status") or {}).get("today_validated_items")),
        ("tracking_today_tentative", (ctx.get("tracking_memory_status") or {}).get("today_tentative_items") or (observation.get("tracking_memory_status") or {}).get("today_tentative_items")),
    )
    for key, items in sources:
        if isinstance(items, list) and items:
            pools[key] = [_compact_stock_item(item) for item in items if isinstance(item, dict)]
    return pools


def _tracking_memory_state_from_data(data):
    data = data or {}
    ctx = data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {}
    market = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    observation = market.get("observation") if isinstance(market.get("observation"), dict) else {}
    status = ctx.get("tracking_memory_status") or observation.get("tracking_memory_status") or {}
    if not isinstance(status, dict):
        return {}
    items = status.get("total_items") or []
    if not isinstance(items, list):
        items = []
    return {"updated_at": data.get("date") or data.get("target_date") or "", "items": items}


def _market_daily_total_from_data(trade_date, data):
    data = data or {}
    total_turnover = data.get("total_turnover")
    turnover_data = data.get("turnover_data") if isinstance(data.get("turnover_data"), dict) else {}
    if total_turnover in (None, ""):
        total_turnover = turnover_data.get("total_turnover_yi") or turnover_data.get("total_turnover") or turnover_data.get("amount_yi")
    market_stats = data.get("market_stats") if isinstance(data.get("market_stats"), dict) else {}
    if total_turnover in (None, ""):
        total_turnover = market_stats.get("total_turnover") or market_stats.get("total_amount_yi") or market_stats.get("amount_yi")
    total_amount_yi = _safe_float(total_turnover)
    if total_amount_yi <= 0:
        return {}
    stock_count = _safe_int(market_stats.get("stock_count"))
    if not stock_count:
        stock_count = _safe_int(market_stats.get("up_count")) + _safe_int(market_stats.get("down_count"))
    return {
        "trade_date": trade_date,
        "market_scope": "all_a",
        "total_amount_yi": total_amount_yi,
        "stock_count": stock_count,
        "source_policy": "daily_report_facts.total_turnover",
    }


_INDEX_DAILY_BAR_SOURCE_KEYS = (
    ("indices", "上证指数", "sh000001"),
    ("indices", "深证成指", "sz399001"),
    ("indices", "创业板指", "sz399006"),
    ("wind_a_alternative", None, "sh000985"),
    ("csi1000_index", None, "sh000852"),
)


def _index_daily_bar_records_from_data(trade_date, data):
    data = data or {}
    records = []
    for container_key, nested_key, fallback_code in _INDEX_DAILY_BAR_SOURCE_KEYS:
        container = data.get(container_key)
        source = container.get(nested_key) if nested_key and isinstance(container, dict) else container
        if not isinstance(source, dict):
            continue
        code = _normalize_index_code(source.get("code") or fallback_code)
        row_date = _date_or_none(source.get("trade_date") or source.get("date") or trade_date)
        close = _safe_float(source.get("close", source.get("price")))
        if not code or not row_date or close <= 0:
            continue
        records.append(
            (
                code,
                {
                    "trade_date": row_date,
                    "open": _safe_float(source.get("open"), close),
                    "high": _safe_float(source.get("high"), close),
                    "low": _safe_float(source.get("low"), close),
                    "close": close,
                    "volume": _safe_float(source.get("volume", source.get("vol"))),
                    "amount": _safe_float(source.get("amount", source.get("turnover"))),
                    "source_policy": _text(source.get("data_source") or source.get("source") or "daily_report_facts.index_daily"),
                },
            )
        )
    return records


def _monthly_account_ledger_from_data(trade_date, data):
    data = data or {}
    market_snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    execution_context = data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {}
    position_decision = market_snapshot.get("position_decision") if isinstance(market_snapshot.get("position_decision"), dict) else {}
    execution_position_decision = execution_context.get("position_decision") if isinstance(execution_context.get("position_decision"), dict) else {}
    top_position_decision = data.get("position_decision") if isinstance(data.get("position_decision"), dict) else {}
    monthly_rhythm = position_decision.get("monthly_rhythm") if isinstance(position_decision.get("monthly_rhythm"), dict) else {}
    execution_monthly_rhythm = (
        execution_position_decision.get("monthly_rhythm")
        if isinstance(execution_position_decision.get("monthly_rhythm"), dict)
        else {}
    )
    top_monthly_rhythm = (
        top_position_decision.get("monthly_rhythm")
        if isinstance(top_position_decision.get("monthly_rhythm"), dict)
        else {}
    )
    context = {}
    for source in (
        monthly_rhythm,
        execution_monthly_rhythm,
        top_monthly_rhythm,
        execution_context.get("monthly_context") if isinstance(execution_context.get("monthly_context"), dict) else {},
        data.get("monthly_context") if isinstance(data.get("monthly_context"), dict) else {},
    ):
        if isinstance(source, dict):
            context.update({key: value for key, value in source.items() if value not in (None, "")})
    if not context:
        return {}

    account_profile = data.get("account_profile") if isinstance(data.get("account_profile"), dict) else {}
    personal_context = data.get("personal_position_context") if isinstance(data.get("personal_position_context"), dict) else {}
    personal_profile = personal_context.get("account_profile") if isinstance(personal_context.get("account_profile"), dict) else {}
    row = {
        "trade_date": trade_date,
        "account_id": _text(
            context.get("account_id")
            or account_profile.get("account_id")
            or personal_profile.get("account_id")
            or "main"
        )
        or "main",
        "month_key": _normalize_month_key(trade_date=trade_date, month_key=context.get("month_key")),
        "month_return_pct": _nullable_float(context.get("month_return_pct", context.get("monthly_return_pct"))),
        "simulated_cumulative_return_pct": _nullable_float(context.get("simulated_cumulative_return_pct")),
        "equity": _nullable_float(context.get("equity")),
        "cash": _nullable_float(context.get("cash")),
        "position_market_value": _nullable_float(context.get("position_market_value")),
        "realized_pnl": _nullable_float(context.get("realized_pnl")),
        "unrealized_pnl": _nullable_float(context.get("unrealized_pnl")),
        "max_drawdown_pct": _nullable_float(context.get("max_drawdown_pct")),
        "planned_trade_count": _safe_int(context.get("planned_trade_count")),
        "unplanned_trade_count": _safe_int(context.get("unplanned_trade_count")),
        "note": _text(context.get("note") or context.get("reason")),
        "source_policy": _text(context.get("source_policy") or context.get("month_return_source"))
        or "postgresql.daily_report_facts",
    }
    if not row["trade_date"] or not row["account_id"] or not row["month_key"]:
        return {}
    has_account_fact = any(
        row.get(key) is not None
        for key in (
            "month_return_pct",
            "simulated_cumulative_return_pct",
            "equity",
            "cash",
            "position_market_value",
            "realized_pnl",
            "unrealized_pnl",
            "max_drawdown_pct",
        )
    ) or bool(row["note"])
    return row if has_account_fact else {}


def _sector_fund_flow_records_from_data(trade_date, data):
    data = data or {}
    sector_fund_flow = data.get("sector_fund_flow")
    if not isinstance(sector_fund_flow, dict):
        return []
    records = []
    seen = set()
    for direction, sign in (("inflow", 1), ("outflow", -1)):
        for row in sector_fund_flow.get(direction) or []:
            if not isinstance(row, dict):
                continue
            sector_name = _text(row.get("sector_name") or row.get("name") or row.get("板块"))
            if not sector_name:
                continue
            raw_value = row.get("net_inflow_yi")
            if raw_value in (None, ""):
                raw_value = row.get("zljlr")
            if raw_value in (None, ""):
                raw_value = row.get("net_inflow")
            if raw_value in (None, ""):
                raw_value = row.get("inflow")
            value = _safe_float(raw_value)
            if direction == "outflow":
                value = -abs(value)
            elif value < 0:
                value = abs(value) * sign
            if sector_name in seen:
                continue
            seen.add(sector_name)
            records.append(
                {
                    "trade_date": trade_date,
                    "sector_name": sector_name,
                    "net_inflow_yi": value,
                    "source_policy": _text(row.get("data_source") or row.get("source")) or "daily_report_facts.sector_fund_flow",
                }
            )
    return records


def _market_capacity_phase(window_state, mainline_regime, turnover_quality):
    window_state = _text(window_state)
    mainline_regime = _text(mainline_regime)
    turnover_quality = _text(turnover_quality)
    if not turnover_quality or turnover_quality == "待确认":
        return "待确认"
    if window_state == "open" and mainline_regime == "单主线聚焦" and turnover_quality == "做多放量":
        return "分化期（趋势确立）"
    if window_state == "confirm_next" or mainline_regime in {"双主线竞争", "主线+背景线", "交替竞争"}:
        return "接替期（竞争关系）"
    if window_state == "observe" or mainline_regime in {"无主线", "混沌轮动", "混沌接力"} or turnover_quality in {"杀跌放量", "缩量", "待累计"}:
        return "粘合期"
    return "待确认"


class PostgresDailyFactDb:
    def __init__(self, database_url, *, connect=None, ensure_schema=True):
        self.database_url = _text(database_url)
        self._connect_factory = connect
        if ensure_schema:
            self._ensure_schema()

    @contextmanager
    def _connect(self):
        conn = self._connect_factory() if self._connect_factory else self._connect_with_psycopg()
        try:
            yield conn
        finally:
            close = getattr(conn, "close", None)
            if callable(close):
                close()

    def _connect_with_psycopg(self):
        try:
            psycopg = importlib.import_module("psycopg")
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise RuntimeError("psycopg is required when PostgreSQL storage is selected") from exc
        try:  # pragma: no cover - depends on local install
            rows = importlib.import_module("psycopg.rows")
        except ImportError:
            return psycopg.connect(self.database_url)
        return psycopg.connect(self.database_url, row_factory=rows.dict_row)

    def _ensure_schema(self):
        with self._connect() as conn:
            with conn.cursor() as cursor:
                for statement in POSTGRES_SCHEMA_STATEMENTS:
                    cursor.execute(statement)
            conn.commit()

    def is_postgres_backed(self):
        return True

    def _normalize_monthly_account_ledger(self, row):
        row = row or {}
        trade_date = _date_or_none(row.get("trade_date") or row.get("date"))
        month_key = _normalize_month_key(trade_date=trade_date, month_key=row.get("month_key"))
        return {
            "trade_date": trade_date,
            "account_id": _text(row.get("account_id")) or "main",
            "month_key": month_key,
            "month_return_pct": _nullable_float(row.get("month_return_pct", row.get("monthly_return_pct"))),
            "simulated_cumulative_return_pct": _nullable_float(row.get("simulated_cumulative_return_pct")),
            "equity": _nullable_float(row.get("equity")),
            "cash": _nullable_float(row.get("cash")),
            "position_market_value": _nullable_float(row.get("position_market_value")),
            "realized_pnl": _nullable_float(row.get("realized_pnl")),
            "unrealized_pnl": _nullable_float(row.get("unrealized_pnl")),
            "max_drawdown_pct": _nullable_float(row.get("max_drawdown_pct")),
            "planned_trade_count": _safe_int(row.get("planned_trade_count")),
            "unplanned_trade_count": _safe_int(row.get("unplanned_trade_count")),
            "note": _text(row.get("note")),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
        }

    def _monthly_return_by_month_until(self, end_date, *, account_id="main"):
        columns = ("month_key", "trade_date", "month_return_pct")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT month_key, trade_date, month_return_pct
                    FROM monthly_account_ledger
                    WHERE account_id = %s
                      AND trade_date <= %s
                      AND month_return_pct IS NOT NULL
                    ORDER BY month_key ASC, trade_date ASC
                    """,
                    (_text(account_id) or "main", _date_or_none(end_date)),
                )
                rows = list(cursor.fetchall() or [])
        latest_by_month = {}
        for row in rows:
            item = _row_dict(row, columns)
            month_key = _text(item.get("month_key"))
            month_return_pct = _nullable_float(item.get("month_return_pct"))
            if month_key and month_return_pct is not None:
                latest_by_month[month_key] = month_return_pct
        return latest_by_month

    def _simulated_cumulative_return_pct_for_item(self, item):
        item = item or {}
        latest_by_month = self._monthly_return_by_month_until(
            item.get("trade_date"),
            account_id=item.get("account_id") or "main",
        )
        month_key = _text(item.get("month_key"))
        month_return_pct = _nullable_float(item.get("month_return_pct"))
        if month_key and month_return_pct is not None:
            latest_by_month[month_key] = month_return_pct
        values = [latest_by_month[key] for key in sorted(latest_by_month)]
        return _compound_monthly_return_pct(values)

    def _refresh_monthly_account_cumulative_returns(self, *, account_id="main"):
        account_id = _text(account_id) or "main"
        columns = ("trade_date", "account_id", "month_key", "month_return_pct")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trade_date, account_id, month_key, month_return_pct
                    FROM monthly_account_ledger
                    WHERE account_id = %s
                      AND month_return_pct IS NOT NULL
                    ORDER BY trade_date ASC, month_key ASC
                    """,
                    (account_id,),
                )
                rows = list(cursor.fetchall() or [])
                latest_by_month = {}
                updates = []
                for row in rows:
                    item = _row_dict(row, columns)
                    trade_date = _date_or_none(item.get("trade_date"))
                    month_key = _text(item.get("month_key"))
                    month_return_pct = _nullable_float(item.get("month_return_pct"))
                    if not trade_date or not month_key or month_return_pct is None:
                        continue
                    latest_by_month[month_key] = month_return_pct
                    cumulative_return_pct = _compound_monthly_return_pct(
                        [latest_by_month[key] for key in sorted(latest_by_month)]
                    )
                    if cumulative_return_pct is not None:
                        updates.append((cumulative_return_pct, trade_date, account_id))
                if updates:
                    cursor.executemany(
                        """
                        UPDATE monthly_account_ledger
                        SET simulated_cumulative_return_pct = %s,
                            updated_at = now()
                        WHERE trade_date = %s
                          AND account_id = %s
                        """,
                        updates,
                    )
            if updates:
                conn.commit()
        return len(updates)

    def upsert_monthly_account_ledger(self, row):
        item = self._normalize_monthly_account_ledger(row)
        if not item["trade_date"] or not item["account_id"] or not item["month_key"]:
            return {}
        if item["simulated_cumulative_return_pct"] is None:
            item["simulated_cumulative_return_pct"] = self._simulated_cumulative_return_pct_for_item(item)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO monthly_account_ledger(
                        trade_date, account_id, month_key, month_return_pct,
                        simulated_cumulative_return_pct, equity, cash,
                        position_market_value, realized_pnl, unrealized_pnl,
                        max_drawdown_pct, planned_trade_count, unplanned_trade_count,
                        note, source_policy
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date, account_id) DO UPDATE SET
                        month_key=EXCLUDED.month_key,
                        month_return_pct=EXCLUDED.month_return_pct,
                        simulated_cumulative_return_pct=EXCLUDED.simulated_cumulative_return_pct,
                        equity=EXCLUDED.equity,
                        cash=EXCLUDED.cash,
                        position_market_value=EXCLUDED.position_market_value,
                        realized_pnl=EXCLUDED.realized_pnl,
                        unrealized_pnl=EXCLUDED.unrealized_pnl,
                        max_drawdown_pct=EXCLUDED.max_drawdown_pct,
                        planned_trade_count=EXCLUDED.planned_trade_count,
                        unplanned_trade_count=EXCLUDED.unplanned_trade_count,
                        note=EXCLUDED.note,
                        source_policy=EXCLUDED.source_policy,
                        updated_at=now()
                    """,
                    (
                        item["trade_date"],
                        item["account_id"],
                        item["month_key"],
                        item["month_return_pct"],
                        item["simulated_cumulative_return_pct"],
                        item["equity"],
                        item["cash"],
                        item["position_market_value"],
                        item["realized_pnl"],
                        item["unrealized_pnl"],
                        item["max_drawdown_pct"],
                        item["planned_trade_count"],
                        item["unplanned_trade_count"],
                        item["note"],
                        item["source_policy"],
                    ),
                )
            conn.commit()
        self._refresh_monthly_account_cumulative_returns(account_id=item["account_id"])
        return item

    def query_monthly_account_ledger(self, end_date, *, account_id="main"):
        end_date = _date_or_none(end_date)
        account_id = _text(account_id) or "main"
        month_key = _normalize_month_key(trade_date=end_date)
        if not end_date or not month_key:
            return {}
        columns = (
            "trade_date",
            "account_id",
            "month_key",
            "month_return_pct",
            "simulated_cumulative_return_pct",
            "equity",
            "cash",
            "position_market_value",
            "realized_pnl",
            "unrealized_pnl",
            "max_drawdown_pct",
            "planned_trade_count",
            "unplanned_trade_count",
            "note",
            "source_policy",
            "updated_at",
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trade_date, account_id, month_key, month_return_pct,
                           simulated_cumulative_return_pct, equity, cash,
                           position_market_value, realized_pnl, unrealized_pnl,
                           max_drawdown_pct, planned_trade_count, unplanned_trade_count,
                           note, source_policy, updated_at
                    FROM monthly_account_ledger
                    WHERE account_id = %s
                      AND month_key = %s
                      AND trade_date <= %s
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """,
                    (account_id, month_key, end_date),
                )
                row = cursor.fetchone()
        if not row:
            return {}
        item = _row_dict(row, columns)
        result = {
            "trade_date": _text(item.get("trade_date")),
            "account_id": _text(item.get("account_id")) or account_id,
            "month_key": _text(item.get("month_key")) or month_key,
            "month_return_pct": _nullable_float(item.get("month_return_pct")),
            "simulated_cumulative_return_pct": _nullable_float(item.get("simulated_cumulative_return_pct")),
            "equity": _nullable_float(item.get("equity")),
            "cash": _nullable_float(item.get("cash")),
            "position_market_value": _nullable_float(item.get("position_market_value")),
            "realized_pnl": _nullable_float(item.get("realized_pnl")),
            "unrealized_pnl": _nullable_float(item.get("unrealized_pnl")),
            "max_drawdown_pct": _nullable_float(item.get("max_drawdown_pct")),
            "planned_trade_count": _safe_int(item.get("planned_trade_count")),
            "unplanned_trade_count": _safe_int(item.get("unplanned_trade_count")),
            "note": _text(item.get("note")),
            "source_policy": _text(item.get("source_policy")),
            "updated_at": _text(item.get("updated_at")),
        }
        computed_cumulative_return_pct = self._simulated_cumulative_return_pct_for_item(result)
        if computed_cumulative_return_pct is not None:
            result["simulated_cumulative_return_pct"] = computed_cumulative_return_pct
        return result

    def get_runtime_cache_entry(self, namespace, cache_key, target_date=""):
        columns = ("namespace", "cache_key", "target_date", "payload", "source", "expires_at", "updated_at")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT namespace, cache_key, target_date, payload, source, expires_at, updated_at
                    FROM runtime_cache_entries
                    WHERE namespace = %s
                      AND cache_key = %s
                      AND target_date = %s
                      AND expires_at > now()
                    """,
                    (_text(namespace), _text(cache_key), _text(target_date)),
                )
                row = cursor.fetchone()
        if not row:
            return None
        item = _row_dict(row, columns)
        payload = item.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "namespace": _text(item.get("namespace")),
            "cache_key": _text(item.get("cache_key")),
            "target_date": _text(item.get("target_date")),
            "payload": payload,
            "source": _text(item.get("source")),
            "expires_at": _text(item.get("expires_at")),
            "updated_at": _text(item.get("updated_at")),
        }

    def set_runtime_cache_entry(
        self,
        namespace,
        cache_key,
        target_date,
        payload,
        *,
        source="",
        ttl_seconds=None,
    ):
        ttl = _safe_int(ttl_seconds, 7 * 86400)
        if ttl <= 0:
            ttl = 7 * 86400
        payload_json = json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO runtime_cache_entries(
                        namespace, cache_key, target_date, source, payload, expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, now() + (%s * interval '1 second'))
                    ON CONFLICT (namespace, cache_key, target_date) DO UPDATE SET
                        source=EXCLUDED.source,
                        payload=EXCLUDED.payload,
                        expires_at=EXCLUDED.expires_at,
                        updated_at=now()
                    """,
                    (
                        _text(namespace),
                        _text(cache_key),
                        _text(target_date),
                        _text(source),
                        payload_json,
                        ttl,
                    ),
                )
            conn.commit()
        return True

    def delete_expired_runtime_cache_entries(self):
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM runtime_cache_entries
                    WHERE expires_at <= now()
                    """
                )
            conn.commit()
        return 0

    def get_runtime_cache_stats(self, namespace, target_date=""):
        columns = ("entry_count",)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS entry_count
                    FROM runtime_cache_entries
                    WHERE namespace = %s
                      AND target_date = %s
                      AND expires_at > now()
                    """,
                    (_text(namespace), _text(target_date)),
                )
                row = cursor.fetchone()
        item = _row_dict(row, columns)
        return {"count": _safe_int(item.get("entry_count")), "size_mb": 0.0}

    def _a_kill_row_to_record(self, row):
        row = row or {}
        return {
            "code": _text(row.get("stock_code")),
            "name": _text(row.get("stock_name")),
            "sector": _text(row.get("sector_name")),
            "a_kill_date": _text(row.get("a_kill_date")),
            "ban_until": _text(row.get("ban_until")),
            "reason": _text(row.get("reason")),
        }

    def _strategy_ledger_row_to_record(self, row):
        row = row or {}
        return {
            "report_date": _text(row.get("report_date")),
            "action_type": _text(row.get("action_type")),
            "anchor_type": _text(row.get("anchor_type")),
            "position_level": _text(row.get("position_level")),
            "operation_state": _text(row.get("operation_state")),
            "execution_status": _text(row.get("execution_status")),
            "can_new_entry": bool(row.get("can_new_entry")),
            "final_action": _text(row.get("final_action")),
            "mainline_name": _text(row.get("mainline_name")),
            "stock_code": _text(row.get("stock_code")),
            "stock_name": _text(row.get("stock_name")),
            "stock_sector": _text(row.get("stock_sector")),
            "factor_snapshot_path": _text(row.get("factor_snapshot_path")),
        }

    def _strategy_record_scalar_rows(self, mode, report_date, record):
        rows = []
        excluded = {"report_date", "factor_snapshot", "simulation", "attribution"}
        for field_name, value in sorted((record or {}).items()):
            if field_name in excluded or isinstance(value, (dict, list, tuple, set)):
                continue
            value_text, value_number, value_bool, value_kind = _typed_value(value)
            rows.append((mode, report_date, _text(field_name), value_text, value_number, value_bool, value_kind))
        return rows

    def _strategy_factor_field_rows(self, mode, report_date, snapshot):
        rows = []
        for field_path, value in _iter_structured_scalar_fields(snapshot or {}):
            if not field_path:
                continue
            value_text, value_number, value_bool, value_kind = _typed_value(value)
            rows.append((mode, report_date, field_path, value_text, value_number, value_bool, value_kind))
        return rows

    def _strategy_factor_pool_rows(self, mode, report_date, snapshot):
        pool_paths = (
            ("core_stocks", ("core_stocks",)),
            ("secondary_stocks", ("secondary_stocks",)),
            ("crossline_observation_stocks", ("crossline_observation_stocks",)),
            ("gem_observation_stocks", ("gem_observation_stocks",)),
            ("generic_watch_stocks", ("generic_watch_stocks",)),
            ("candidate_stack.execute_candidates", ("candidate_stack", "execute_candidates")),
        )
        rows = []
        for pool_name, path in pool_paths:
            value = snapshot or {}
            for part in path:
                value = value.get(part) if isinstance(value, dict) else None
            if not isinstance(value, list):
                continue
            for ordinal, item in enumerate(value):
                if not isinstance(item, dict):
                    continue
                rows.append(
                    (
                        mode,
                        report_date,
                        pool_name,
                        ordinal,
                        _stock_code(item),
                        _stock_name(item),
                        _sector_name(item),
                        _text(item.get("action_type")),
                        _text(item.get("participation_mode")),
                        _safe_int(item.get("position_pct")),
                        _first_text(item, "setup_signal_id", "abnormal_setup_signal_id"),
                        _first_text(item, "setup_signal_label", "abnormal_setup_signal_label"),
                        _first_text(item, "follow_state", "abnormal_follow_state"),
                        _first_text(item, "reason", "why_watch", "summary_text"),
                        _text(item.get("final_action")),
                        _first_text(item, "trigger_text", "trigger_condition", "entry_condition"),
                    )
                )
        return rows

    def _candidate_trace_field_rows(self, trade_date, trace):
        code = _stock_code(trace)
        if not code:
            return []
        excluded = {
            "stock_code",
            "code",
            "stock_name",
            "name",
            "tier",
            "mainline",
            "sector",
            "sector_name",
            "final_action",
            "visible_summary",
            "summary",
            "trigger_condition",
            "entry_condition",
            "failure_condition",
            "invalidation",
        }
        rows = []
        for field_name, value in sorted((trace or {}).items()):
            if field_name in excluded:
                continue
            if isinstance(value, (dict, list, tuple)):
                for field_path, scalar_value in _iter_structured_scalar_fields(value, prefix=_text(field_name), max_depth=5):
                    if not field_path:
                        continue
                    value_text, value_number, value_bool, value_kind = _typed_value(scalar_value)
                    rows.append((trade_date, code, _text(field_path), value_text, value_number, value_bool, value_kind))
                continue
            value_text, value_number, value_bool, value_kind = _typed_value(value)
            rows.append((trade_date, code, _text(field_name), value_text, value_number, value_bool, value_kind))
        return rows

    def _strategy_factor_pool_row_to_item(self, row):
        row = row or {}
        return {
            "code": _text(row.get("stock_code")),
            "stock_code": _text(row.get("stock_code")),
            "name": _text(row.get("stock_name")),
            "stock_name": _text(row.get("stock_name")),
            "sector": _text(row.get("sector_name")),
            "sector_name": _text(row.get("sector_name")),
            "action_type": _text(row.get("action_type")),
            "participation_mode": _text(row.get("participation_mode")),
            "position_pct": _safe_int(row.get("position_pct")),
            "setup_signal_id": _text(row.get("setup_signal_id")),
            "setup_signal_label": _text(row.get("setup_signal_label")),
            "abnormal_setup_signal_id": _text(row.get("setup_signal_id")),
            "abnormal_setup_signal_label": _text(row.get("setup_signal_label")),
            "follow_state": _text(row.get("follow_state")),
            "abnormal_follow_state": _text(row.get("follow_state")),
            "reason": _text(row.get("reason")),
            "final_action": _text(row.get("final_action")),
            "trigger_text": _text(row.get("trigger_text")),
        }

    def upsert_market_daily_total(self, row):
        row = row or {}
        item = {
            "trade_date": _date_or_none(row.get("trade_date") or row.get("date")),
            "market_scope": _text(row.get("market_scope")) or "all_a",
            "total_amount_yi": _safe_float(row.get("total_amount_yi", row.get("amount_yi"))),
            "stock_count": _safe_int(row.get("stock_count")),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        if not item["trade_date"]:
            return {}
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO market_daily_totals(
                        trade_date, market_scope, total_amount_yi, stock_count,
                        source_policy, source_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date, market_scope) DO UPDATE SET
                        total_amount_yi=EXCLUDED.total_amount_yi,
                        stock_count=EXCLUDED.stock_count,
                        source_policy=EXCLUDED.source_policy,
                        source_run_id=EXCLUDED.source_run_id,
                        updated_at=now()
                    """,
                    (
                        item["trade_date"],
                        item["market_scope"],
                        item["total_amount_yi"],
                        item["stock_count"],
                        item["source_policy"],
                        item["source_run_id"],
                    ),
                )
            conn.commit()
        return item

    def query_market_daily_total(self, trade_date, *, market_scope="all_a"):
        columns = (
            "trade_date",
            "market_scope",
            "total_amount_yi",
            "stock_count",
            "source_policy",
            "source_run_id",
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trade_date, market_scope, total_amount_yi, stock_count,
                           source_policy, source_run_id
                    FROM market_daily_totals
                    WHERE trade_date = %s AND market_scope = %s
                    """,
                    (_date_or_none(trade_date), _text(market_scope) or "all_a"),
                )
                row = cursor.fetchone()
        item = _row_dict(row, columns)
        if item:
            item["trade_date"] = _text(item.get("trade_date"))
        return item

    def upsert_index_daily_bars(self, index_code, rows, *, source_policy="", source_run_id=0):
        index_code = _normalize_index_code(index_code)
        if not index_code:
            return 0
        items = []
        for row in rows or []:
            row = row or {}
            trade_date = _date_or_none(row.get("trade_date") or row.get("date"))
            if not trade_date:
                continue
            items.append(
                (
                    index_code,
                    trade_date,
                    _safe_float(row.get("open")),
                    _safe_float(row.get("high")),
                    _safe_float(row.get("low")),
                    _safe_float(row.get("close")),
                    _safe_float(row.get("volume", row.get("vol"))),
                    _safe_float(row.get("amount")),
                    _text(row.get("source_policy") or source_policy),
                    _safe_int(row.get("source_run_id", source_run_id)),
                )
            )
        if not items:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO index_daily_bars(
                        index_code, trade_date, open, high, low, close,
                        volume, amount, source_policy, source_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (index_code, trade_date) DO UPDATE SET
                        open=EXCLUDED.open,
                        high=EXCLUDED.high,
                        low=EXCLUDED.low,
                        close=EXCLUDED.close,
                        volume=EXCLUDED.volume,
                        amount=EXCLUDED.amount,
                        source_policy=EXCLUDED.source_policy,
                        source_run_id=EXCLUDED.source_run_id,
                        updated_at=now()
                    """,
                    items,
                )
            conn.commit()
        return len(items)

    def query_index_daily_bars(self, index_code, end_date, *, window_days=250):
        index_code = _normalize_index_code(index_code)
        if not index_code:
            return []
        limit = max(_safe_int(window_days, 250), 1)
        columns = (
            "index_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "source_policy",
            "source_run_id",
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT index_code, trade_date, open, high, low, close,
                           volume, amount, source_policy, source_run_id
                    FROM index_daily_bars
                    WHERE index_code = %s
                      AND trade_date <= %s
                    ORDER BY trade_date DESC
                    LIMIT %s
                    """,
                    (index_code, _date_or_none(end_date), limit),
                )
                rows = list(cursor.fetchall() or [])
        records = []
        for row in reversed(rows):
            item = _row_dict(row, columns)
            trade_date = _text(item.get("trade_date"))
            records.append(
                {
                    "date": trade_date,
                    "open": _safe_float(item.get("open")),
                    "high": _safe_float(item.get("high")),
                    "low": _safe_float(item.get("low")),
                    "close": _safe_float(item.get("close")),
                    "volume": _safe_float(item.get("volume")),
                    "amount": _safe_float(item.get("amount")),
                    "data_source": "postgresql.index_daily_bars",
                    "source": _text(item.get("source_policy")) or "postgresql.index_daily_bars",
                    "source_run_id": _safe_int(item.get("source_run_id")),
                }
            )
        return records

    def upsert_index_minute_bars(self, index_code, trade_date, period, rows, *, source_policy="", source_run_id=0):
        index_code = _normalize_index_code(index_code)
        trade_date = _date_or_none(trade_date)
        period = _text(period) or "60"
        if not index_code or not trade_date:
            return 0
        items = []
        for row in rows or []:
            row = row or {}
            bar_time = _text(row.get("time") or row.get("bar_time"))
            if not bar_time:
                datetime_text = _text(row.get("datetime") or row.get("day") or row.get("trade_time"))
                bar_time = datetime_text[-8:] if len(datetime_text) >= 8 else ""
            if not bar_time:
                continue
            items.append(
                (
                    index_code,
                    trade_date,
                    period,
                    bar_time,
                    _safe_float(row.get("open")),
                    _safe_float(row.get("high")),
                    _safe_float(row.get("low")),
                    _safe_float(row.get("close")),
                    _safe_float(row.get("volume", row.get("vol"))),
                    _safe_float(row.get("amount")),
                    _text(row.get("source_policy") or source_policy),
                    _safe_int(row.get("source_run_id", source_run_id)),
                )
            )
        if not items:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO index_minute_bars(
                        index_code, trade_date, period, bar_time,
                        open, high, low, close, volume, amount,
                        source_policy, source_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (index_code, trade_date, period, bar_time) DO UPDATE SET
                        open=EXCLUDED.open,
                        high=EXCLUDED.high,
                        low=EXCLUDED.low,
                        close=EXCLUDED.close,
                        volume=EXCLUDED.volume,
                        amount=EXCLUDED.amount,
                        source_policy=EXCLUDED.source_policy,
                        source_run_id=EXCLUDED.source_run_id,
                        updated_at=now()
                    """,
                    items,
                )
            conn.commit()
        return len(items)

    def query_index_minute_bars(self, index_code, trade_date, *, period="60"):
        index_code = _normalize_index_code(index_code)
        trade_date = _date_or_none(trade_date)
        period = _text(period) or "60"
        if not index_code or not trade_date:
            return []
        columns = (
            "index_code",
            "trade_date",
            "period",
            "bar_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "source_policy",
            "source_run_id",
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT index_code, trade_date, period, bar_time,
                           open, high, low, close, volume, amount,
                           source_policy, source_run_id
                    FROM index_minute_bars
                    WHERE index_code = %s
                      AND trade_date = %s
                      AND period = %s
                    ORDER BY bar_time ASC
                    """,
                    (index_code, trade_date, period),
                )
                rows = list(cursor.fetchall() or [])
        records = []
        for row in rows:
            item = _row_dict(row, columns)
            bar_time = _text(item.get("bar_time"))
            date_text = _text(item.get("trade_date"))
            records.append(
                {
                    "datetime": f"{date_text} {bar_time}".strip(),
                    "date": date_text,
                    "time": bar_time,
                    "open": _safe_float(item.get("open")),
                    "high": _safe_float(item.get("high")),
                    "low": _safe_float(item.get("low")),
                    "close": _safe_float(item.get("close")),
                    "volume": _safe_float(item.get("volume")),
                    "amount": _safe_float(item.get("amount")),
                    "data_source": "postgresql.index_minute_bars",
                    "source": _text(item.get("source_policy")) or "postgresql.index_minute_bars",
                    "source_run_id": _safe_int(item.get("source_run_id")),
                }
            )
        return records

    def upsert_mainline_daily(self, row):
        row = row or {}
        trade_date = _date_or_none(row.get("trade_date") or row.get("date"))
        if not trade_date:
            return {}
        item = {
            "trade_date": trade_date,
            "primary_mainline": _text(row.get("primary_mainline") or row.get("mainline") or row.get("leading_line")),
            "daily_attack_line": _text(row.get("daily_attack_line") or row.get("primary_mainline") or row.get("leading_line")),
            "secondary_mainline": _text(row.get("secondary_mainline")),
            "competition_mainline": _text(row.get("competition_mainline")),
            "rotation_label": _text(row.get("rotation_label")),
            "leading_line": _text(row.get("leading_line") or row.get("primary_mainline")),
            "state_code": _text(row.get("state_code")),
            "market_state": _text(row.get("market_state") or row.get("state")),
            "confidence": _safe_float(row.get("confidence")),
            "rotation_summary": _text(row.get("rotation_summary")),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO mainline_daily(
                        trade_date, primary_mainline, daily_attack_line,
                        secondary_mainline, competition_mainline, rotation_label,
                        leading_line, state_code, market_state, confidence,
                        rotation_summary, source_policy, source_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date) DO UPDATE SET
                        primary_mainline=EXCLUDED.primary_mainline,
                        daily_attack_line=EXCLUDED.daily_attack_line,
                        secondary_mainline=EXCLUDED.secondary_mainline,
                        competition_mainline=EXCLUDED.competition_mainline,
                        rotation_label=EXCLUDED.rotation_label,
                        leading_line=EXCLUDED.leading_line,
                        state_code=EXCLUDED.state_code,
                        market_state=EXCLUDED.market_state,
                        confidence=EXCLUDED.confidence,
                        rotation_summary=EXCLUDED.rotation_summary,
                        source_policy=EXCLUDED.source_policy,
                        source_run_id=EXCLUDED.source_run_id,
                        updated_at=now()
                    """,
                    (
                        item["trade_date"],
                        item["primary_mainline"],
                        item["daily_attack_line"],
                        item["secondary_mainline"],
                        item["competition_mainline"],
                        item["rotation_label"],
                        item["leading_line"],
                        item["state_code"],
                        item["market_state"],
                        item["confidence"],
                        item["rotation_summary"],
                        item["source_policy"],
                        item["source_run_id"],
                    ),
                )
            conn.commit()
        return item

    def query_mainline_daily_series(self, end_date, *, window_days=25):
        columns = (
            "trade_date",
            "primary_mainline",
            "daily_attack_line",
            "secondary_mainline",
            "competition_mainline",
            "rotation_label",
            "leading_line",
            "state_code",
            "market_state",
            "confidence",
            "rotation_summary",
            "source_policy",
            "source_run_id",
        )
        window_days = max(_safe_int(window_days, 25), 1)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trade_date, primary_mainline, daily_attack_line,
                           secondary_mainline, competition_mainline, rotation_label,
                           leading_line, state_code, market_state, confidence,
                           rotation_summary, source_policy, source_run_id
                    FROM mainline_daily
                    WHERE trade_date <= %s
                    ORDER BY trade_date DESC
                    LIMIT %s
                    """,
                    (_date_or_none(end_date), window_days),
                )
                rows = cursor.fetchall()
        result = []
        for row in reversed(rows or []):
            item = _row_dict(row, columns)
            item["trade_date"] = _text(item.get("trade_date"))
            item["date"] = item["trade_date"]
            item["source"] = _text(item.get("source_policy"))
            item["evidence_json"] = ""
            result.append(item)
        return result

    def upsert_mainline_turnover_daily(self, row):
        row = row or {}
        trade_date = _date_or_none(row.get("trade_date") or row.get("date"))
        primary_mainline = _text(
            row.get("primary_mainline")
            or row.get("sector_name")
            or row.get("cycle_mainline")
            or row.get("daily_attack_line")
        )
        if not trade_date or not primary_mainline:
            return {}
        sector_turnover = _safe_float(row.get("sector_turnover_yi", row.get("sector_turnover")))
        total_turnover = _safe_float(row.get("total_turnover_yi", row.get("total_turnover")))
        turnover_share = _safe_float(row.get("turnover_share_pct"))
        if turnover_share <= 0 and sector_turnover > 0 and total_turnover > 0:
            turnover_share = sector_turnover / total_turnover * 100
        item = {
            "trade_date": trade_date,
            "primary_mainline": primary_mainline,
            "turnover_scope_key": _text(row.get("turnover_scope_key")) or primary_mainline,
            "turnover_scope_label": _text(row.get("turnover_scope_label") or row.get("sector_name") or primary_mainline),
            "sector_turnover_yi": sector_turnover,
            "total_turnover_yi": total_turnover,
            "turnover_share_pct": turnover_share,
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO mainline_turnover_daily(
                        trade_date, primary_mainline, turnover_scope_key,
                        turnover_scope_label, sector_turnover_yi, total_turnover_yi,
                        turnover_share_pct, source_policy, source_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date, primary_mainline, turnover_scope_key) DO UPDATE SET
                        turnover_scope_label=EXCLUDED.turnover_scope_label,
                        sector_turnover_yi=EXCLUDED.sector_turnover_yi,
                        total_turnover_yi=EXCLUDED.total_turnover_yi,
                        turnover_share_pct=EXCLUDED.turnover_share_pct,
                        source_policy=EXCLUDED.source_policy,
                        source_run_id=EXCLUDED.source_run_id,
                        updated_at=now()
                    """,
                    (
                        item["trade_date"],
                        item["primary_mainline"],
                        item["turnover_scope_key"],
                        item["turnover_scope_label"],
                        item["sector_turnover_yi"],
                        item["total_turnover_yi"],
                        item["turnover_share_pct"],
                        item["source_policy"],
                        item["source_run_id"],
                    ),
                )
            conn.commit()
        return item

    def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
        columns = (
            "trade_date",
            "primary_mainline",
            "turnover_scope_key",
            "turnover_scope_label",
            "sector_turnover_yi",
            "total_turnover_yi",
            "turnover_share_pct",
            "source_policy",
            "source_run_id",
        )
        sector_name = _text(sector_name)
        window_days = max(_safe_int(window_days, 25), 1)
        if not sector_name:
            return []
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trade_date, primary_mainline, turnover_scope_key,
                           turnover_scope_label, sector_turnover_yi,
                           total_turnover_yi, turnover_share_pct,
                           source_policy, source_run_id
                    FROM mainline_turnover_daily
                    WHERE trade_date <= %s
                      AND (
                        primary_mainline = %s
                        OR turnover_scope_key = %s
                        OR turnover_scope_label = %s
                      )
                    ORDER BY trade_date DESC
                    LIMIT %s
                    """,
                    (_date_or_none(end_date), sector_name, sector_name, sector_name, window_days),
                )
                rows = cursor.fetchall()
        result = []
        for row in reversed(rows or []):
            item = _row_dict(row, columns)
            result.append(
                {
                    "date": _text(item.get("trade_date")),
                    "sector_name": _text(item.get("primary_mainline") or item.get("turnover_scope_label")),
                    "sector_turnover": _safe_float(item.get("sector_turnover_yi")),
                    "total_turnover": _safe_float(item.get("total_turnover_yi")),
                    "turnover_share_pct": _safe_float(item.get("turnover_share_pct")),
                    "matched_sector_names": [_text(item.get("turnover_scope_label")) or sector_name],
                    "matched_sector_codes": [],
                    "source": _text(item.get("source_policy")),
                }
            )
        return result

    def upsert_sector_fund_flow_daily(self, row):
        row = row or {}
        trade_date = _date_or_none(row.get("trade_date") or row.get("date"))
        sector_name = _text(row.get("sector_name"))
        if not trade_date or not sector_name:
            return {}
        item = {
            "trade_date": trade_date,
            "sector_name": sector_name,
            "net_inflow_yi": _safe_float(row.get("net_inflow_yi", row.get("inflow"))),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sector_fund_flow_daily(
                        trade_date, sector_name, net_inflow_yi,
                        source_policy, source_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date, sector_name) DO UPDATE SET
                        net_inflow_yi=EXCLUDED.net_inflow_yi,
                        source_policy=EXCLUDED.source_policy,
                        source_run_id=EXCLUDED.source_run_id,
                        updated_at=now()
                    """,
                    (
                        item["trade_date"],
                        item["sector_name"],
                        item["net_inflow_yi"],
                        item["source_policy"],
                        item["source_run_id"],
                    ),
                )
            conn.commit()
        return item

    def query_sector_fund_flow_series(self, end_date, sector_name, *, window_days=8):
        columns = ("trade_date", "sector_name", "net_inflow_yi")
        sector_name = _text(sector_name)
        window_days = max(_safe_int(window_days, 8), 1)
        if not sector_name:
            return []
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trade_date, sector_name, net_inflow_yi
                    FROM sector_fund_flow_daily
                    WHERE trade_date <= %s AND sector_name = %s
                    ORDER BY trade_date DESC
                    LIMIT %s
                    """,
                    (_date_or_none(end_date), sector_name, window_days),
                )
                rows = cursor.fetchall()
        return [
            {
                "date": _text(item.get("trade_date")),
                "sector_name": _text(item.get("sector_name")),
                "inflow": _safe_float(item.get("net_inflow_yi")),
            }
            for item in (_row_dict(row, columns) for row in reversed(rows or []))
        ]

    def replace_market_cycle_context(self, trade_date, snapshot, *, min_trade_date=None):
        trade_date = _date_or_none(trade_date)
        min_trade_date = _date_or_none(min_trade_date)
        snapshot = snapshot or {}
        counts = {
            "cycle_days": 0,
            "cycle_periods": 0,
            "mainline_records": 0,
            "turnover_records": 0,
            "sector_attack_records": 0,
            "sector_diffusion_records": 0,
            "sector_diffusion_components": 0,
            "sector_competition_records": 0,
            "market_capacity_evolution_records": 0,
            "pivot_records": 0,
        }
        with self._connect() as conn:
            with conn.cursor() as cursor:
                self._replace_market_cycle_days(cursor, trade_date, snapshot, counts, min_trade_date=min_trade_date)
                self._replace_market_cycle_periods(cursor, trade_date, snapshot, counts)
                self._replace_mainline_records(cursor, trade_date, snapshot, counts, min_trade_date=min_trade_date)
                self._replace_turnover_records(cursor, trade_date, snapshot, counts, min_trade_date=min_trade_date)
                self._replace_sector_attack_records(cursor, trade_date, snapshot, counts)
                self._replace_sector_diffusion_records(cursor, trade_date, snapshot, counts)
                self._replace_sector_competition_records(cursor, trade_date, snapshot, counts)
                self._replace_market_capacity_evolution_record(cursor, trade_date, snapshot, counts)
                self._replace_pivot_records(cursor, trade_date, snapshot, counts)
            conn.commit()
        return counts

    def _replace_market_cycle_days(self, cursor, trade_date, snapshot, counts, *, min_trade_date=None):
        cursor.execute("DELETE FROM market_cycle_days WHERE trade_date = %s", (trade_date,))
        rows = []
        row_keys = set()
        cycle_by_mainline = {
            _text(row.get("mainline")): row for row in snapshot.get("cycle_interpretation_rows") or [] if isinstance(row, dict)
        }
        for week_row in snapshot.get("cycle_calendar_rows") or []:
            if not isinstance(week_row, dict):
                continue
            week_label = _text(week_row.get("week_label"))
            for weekday_name in _WEEKDAY_FIELDS:
                cell = week_row.get(weekday_name)
                cells = cell if isinstance(cell, list) else [cell]
                for item in cells:
                    if not isinstance(item, dict):
                        continue
                    short_date = _text(item.get("date"))
                    mainline = _text(item.get("mainline"))
                    if not short_date or not mainline or mainline == "-":
                        continue
                    row_date = _date_from_short(trade_date, short_date)
                    if _is_before_min_trade_date(row_date, min_trade_date):
                        continue
                    row_keys.add((row_date, weekday_name))
                    cycle = cycle_by_mainline.get(mainline, {})
                    rows.append(
                        (
                            row_date,
                            week_label,
                            weekday_name,
                            mainline,
                            _text(cycle.get("attack_line")),
                            _text(item.get("state") or cycle.get("market_state")),
                            _text(cycle.get("cycle_label")),
                            _text(cycle.get("cycle_stage")),
                            _text(cycle.get("transfer_state")),
                            _text(cycle.get("tomorrow_validation")),
                            _text(cycle.get("interpretation")),
                        )
                    )
        target_date = _date_or_none(trade_date)
        if target_date and not any(row_date == target_date for row_date, _weekday in row_keys):
            fallback_rows = []
            current = snapshot.get("current_mainline_history_record")
            if isinstance(current, dict):
                fallback_rows.append(current)
            fallback_rows.extend(row for row in snapshot.get("recent_mainline_history") or [] if isinstance(row, dict))
            for row in fallback_rows:
                row_date = _date_or_none(row.get("trade_date") or row.get("date") or trade_date)
                if row_date != target_date:
                    continue
                if _is_before_min_trade_date(row_date, min_trade_date):
                    continue
                weekday_name = _weekday_name_for_date(row_date)
                mainline = _text(row.get("primary_mainline") or row.get("mainline") or row.get("leading_line"))
                if not weekday_name or not mainline or mainline == "-":
                    continue
                cycle = cycle_by_mainline.get(mainline, {})
                rows.append(
                    (
                        row_date,
                        _text(row.get("week_label")) or _week_label_for_date(row_date),
                        weekday_name,
                        mainline,
                        _text(row.get("daily_attack_line") or cycle.get("attack_line") or mainline),
                        _text(row.get("market_state") or row.get("state") or cycle.get("market_state")),
                        _text(cycle.get("cycle_label")),
                        _text(cycle.get("cycle_stage")),
                        _text(cycle.get("transfer_state")),
                        _text(cycle.get("tomorrow_validation")),
                        _text(row.get("rotation_summary") or cycle.get("interpretation")),
                    )
                )
                break
        if rows:
            cursor.executemany(
                """
                INSERT INTO market_cycle_days(
                    trade_date, week_label, weekday_name, mainline, daily_attack_line,
                    market_state, cycle_label, cycle_stage, transfer_state,
                    tomorrow_validation, interpretation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, weekday_name) DO UPDATE SET
                    week_label=EXCLUDED.week_label,
                    mainline=EXCLUDED.mainline,
                    daily_attack_line=EXCLUDED.daily_attack_line,
                    market_state=EXCLUDED.market_state,
                    cycle_label=EXCLUDED.cycle_label,
                    cycle_stage=EXCLUDED.cycle_stage,
                    transfer_state=EXCLUDED.transfer_state,
                    tomorrow_validation=EXCLUDED.tomorrow_validation,
                    interpretation=EXCLUDED.interpretation,
                    updated_at=now()
                """,
                rows,
            )
        counts["cycle_days"] = len(rows)

    def _replace_market_cycle_periods(self, cursor, trade_date, snapshot, counts):
        cursor.execute("DELETE FROM market_cycle_periods WHERE trade_date = %s", (trade_date,))
        rows = []
        for row in snapshot.get("cycle_interpretation_rows") or []:
            if not isinstance(row, dict):
                continue
            rows.append(
                (
                    trade_date,
                    _text(row.get("cycle_label")),
                    _text(row.get("date_range") or row.get("time_range")),
                    _safe_int(row.get("trading_days")),
                    _text(row.get("mainline")),
                    _text(row.get("attack_line")),
                    _text(row.get("cycle_stage")),
                    _text(row.get("transfer_state")),
                    _text(row.get("market_state")),
                    _text(row.get("tomorrow_validation")),
                    _text(row.get("interpretation")),
                )
            )
        if rows:
            cursor.executemany(
                """
                INSERT INTO market_cycle_periods(
                    trade_date, cycle_label, date_range, trading_days, mainline,
                    attack_line, cycle_stage, transfer_state, market_state,
                    tomorrow_validation, interpretation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, cycle_label) DO UPDATE SET
                    date_range=EXCLUDED.date_range,
                    trading_days=EXCLUDED.trading_days,
                    mainline=EXCLUDED.mainline,
                    attack_line=EXCLUDED.attack_line,
                    cycle_stage=EXCLUDED.cycle_stage,
                    transfer_state=EXCLUDED.transfer_state,
                    market_state=EXCLUDED.market_state,
                    tomorrow_validation=EXCLUDED.tomorrow_validation,
                    interpretation=EXCLUDED.interpretation,
                    updated_at=now()
                """,
                rows,
            )
        counts["cycle_periods"] = len(rows)

    def _replace_mainline_records(self, cursor, trade_date, snapshot, counts, *, min_trade_date=None):
        rows = []
        for row in snapshot.get("recent_mainline_history") or []:
            if isinstance(row, dict):
                rows.append(row)
        current = snapshot.get("current_mainline_history_record")
        if isinstance(current, dict):
            rows.append(current)
        normalized = []
        seen_dates = set()
        for row in rows:
            row_date = _date_or_none(row.get("trade_date") or row.get("date") or trade_date)
            mainline = _text(row.get("primary_mainline") or row.get("mainline") or row.get("leading_line"))
            if not row_date or not mainline or row_date in seen_dates:
                continue
            if _is_before_min_trade_date(row_date, min_trade_date):
                continue
            seen_dates.add(row_date)
            normalized.append(
                (
                    row_date,
                    mainline,
                    _text(row.get("daily_attack_line") or mainline),
                    _text(row.get("secondary_mainline")),
                    _text(row.get("competition_mainline")),
                    _text(row.get("rotation_label")),
                    _text(row.get("leading_line") or mainline),
                    _text(row.get("state_code")),
                    _text(row.get("market_state") or row.get("state")),
                    _safe_float(row.get("confidence")),
                    _text(row.get("rotation_summary")),
                    _text(row.get("source_policy") or row.get("source")),
                    _safe_int(row.get("source_run_id")),
                )
            )
        if normalized:
            cursor.executemany(
                """
                INSERT INTO mainline_daily(
                    trade_date, primary_mainline, daily_attack_line, secondary_mainline,
                    competition_mainline, rotation_label, leading_line, state_code,
                    market_state, confidence, rotation_summary, source_policy, source_run_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date) DO UPDATE SET
                    primary_mainline=EXCLUDED.primary_mainline,
                    daily_attack_line=EXCLUDED.daily_attack_line,
                    secondary_mainline=EXCLUDED.secondary_mainline,
                    competition_mainline=EXCLUDED.competition_mainline,
                    rotation_label=EXCLUDED.rotation_label,
                    leading_line=EXCLUDED.leading_line,
                    state_code=EXCLUDED.state_code,
                    market_state=EXCLUDED.market_state,
                    confidence=EXCLUDED.confidence,
                    rotation_summary=EXCLUDED.rotation_summary,
                    source_policy=EXCLUDED.source_policy,
                    source_run_id=EXCLUDED.source_run_id,
                    updated_at=now()
                """,
                normalized,
            )
        counts["mainline_records"] = len(normalized)

    def _replace_turnover_records(self, cursor, trade_date, snapshot, counts, *, min_trade_date=None):
        rows = []
        for row in snapshot.get("recent_sector_turnover_history") or []:
            if isinstance(row, dict):
                rows.append(row)
        current = snapshot.get("current_sector_turnover_snapshot")
        if isinstance(current, dict):
            rows.append(current)
        normalized = []
        for row in rows:
            row_date = _date_or_none(row.get("trade_date") or row.get("date") or trade_date)
            mainline = _text(row.get("primary_mainline") or row.get("cycle_mainline") or row.get("sector_name"))
            if not row_date or not mainline:
                continue
            if _is_before_min_trade_date(row_date, min_trade_date):
                continue
            scope_key = _text(row.get("turnover_scope_key")) or mainline
            normalized.append(
                (
                    row_date,
                    mainline,
                    scope_key,
                    _text(row.get("turnover_scope_label") or row.get("sector_name") or mainline),
                    _safe_float(row.get("sector_turnover_yi", row.get("sector_turnover"))),
                    _safe_float(row.get("total_turnover_yi", row.get("total_turnover"))),
                    _safe_float(row.get("turnover_share_pct")),
                    _text(row.get("source_policy") or row.get("source")),
                    _safe_int(row.get("source_run_id")),
                )
            )
        if normalized:
            cursor.executemany(
                """
                INSERT INTO mainline_turnover_daily(
                    trade_date, primary_mainline, turnover_scope_key, turnover_scope_label,
                    sector_turnover_yi, total_turnover_yi, turnover_share_pct,
                    source_policy, source_run_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, primary_mainline, turnover_scope_key) DO UPDATE SET
                    turnover_scope_label=EXCLUDED.turnover_scope_label,
                    sector_turnover_yi=EXCLUDED.sector_turnover_yi,
                    total_turnover_yi=EXCLUDED.total_turnover_yi,
                    turnover_share_pct=EXCLUDED.turnover_share_pct,
                    source_policy=EXCLUDED.source_policy,
                    source_run_id=EXCLUDED.source_run_id,
                    updated_at=now()
                """,
                normalized,
            )
        counts["turnover_records"] = len(normalized)

    def _replace_sector_attack_records(self, cursor, trade_date, snapshot, counts):
        attack_summary = snapshot.get("mainline_attack_evidence_summary")
        if not isinstance(attack_summary, dict):
            turnover_summary = snapshot.get("mainline_turnover_summary") if isinstance(snapshot.get("mainline_turnover_summary"), dict) else {}
            attack_summary = turnover_summary.get("mainline_attack_evidence_summary") if isinstance(turnover_summary.get("mainline_attack_evidence_summary"), dict) else {}
        rows = []
        source_rows = snapshot.get("sector_attack_evidence_rows")
        if source_rows is None and isinstance(attack_summary, dict):
            source_rows = attack_summary.get("sector_evidence_rows")
        if source_rows is None:
            counts["sector_attack_records"] = 0
            return
        cursor.execute("DELETE FROM sector_attack_evidence_daily WHERE trade_date = %s", (trade_date,))
        current_snapshot = snapshot.get("current_sector_turnover_snapshot") if isinstance(snapshot.get("current_sector_turnover_snapshot"), dict) else {}
        fallback_total_turnover = _safe_float(
            current_snapshot.get("total_turnover_yi", current_snapshot.get("total_turnover"))
            or snapshot.get("total_turnover")
        )
        for row in source_rows or []:
            if not isinstance(row, dict):
                continue
            sector = _sector_name(row)
            if not sector:
                continue
            share = _safe_float(row.get("turnover_share_pct"))
            total_turnover = _safe_float(row.get("total_turnover_yi", row.get("total_turnover")))
            if total_turnover <= 0:
                total_turnover = fallback_total_turnover
            sector_turnover = _safe_float(row.get("sector_turnover_yi", row.get("sector_turnover")))
            if sector_turnover <= 0 and total_turnover > 0 and share > 0:
                sector_turnover = round(total_turnover * share / 100, 2)
            rows.append(
                (
                    trade_date,
                    sector,
                    _safe_int(row.get("net_inflow_rank")),
                    _safe_float(row.get("net_inflow_amount")),
                    _safe_int(row.get("limit_up_count")),
                    _safe_int(row.get("high_anchor_height")),
                    sector_turnover,
                    total_turnover,
                    share,
                    _safe_float(row.get("turnover_share_change")),
                    _text(row.get("source_policy") or row.get("source")),
                    _safe_int(row.get("source_run_id")),
                )
            )
        if rows:
            cursor.executemany(
                """
                INSERT INTO sector_attack_evidence_daily(
                    trade_date, sector_name, net_inflow_rank, net_inflow_amount_yi,
                    limit_up_count, high_anchor_height, sector_turnover_yi,
                    total_turnover_yi, turnover_share_pct, turnover_share_change,
                    source_policy, source_run_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, sector_name) DO UPDATE SET
                    net_inflow_rank=EXCLUDED.net_inflow_rank,
                    net_inflow_amount_yi=EXCLUDED.net_inflow_amount_yi,
                    limit_up_count=EXCLUDED.limit_up_count,
                    high_anchor_height=EXCLUDED.high_anchor_height,
                    sector_turnover_yi=EXCLUDED.sector_turnover_yi,
                    total_turnover_yi=EXCLUDED.total_turnover_yi,
                    turnover_share_pct=EXCLUDED.turnover_share_pct,
                    turnover_share_change=EXCLUDED.turnover_share_change,
                    source_policy=EXCLUDED.source_policy,
                    source_run_id=EXCLUDED.source_run_id,
                    updated_at=now()
                """,
                rows,
            )
        counts["sector_attack_records"] = len(rows)

    def _replace_sector_diffusion_records(self, cursor, trade_date, snapshot, counts):
        cursor.execute("DELETE FROM sector_diffusion_score_components WHERE trade_date = %s", (trade_date,))
        cursor.execute("DELETE FROM sector_diffusion_score_daily WHERE trade_date = %s", (trade_date,))
        diffusion = (
            snapshot.get("diffusion_quality")
            or snapshot.get("sector_diffusion_quality")
            or (snapshot.get("sector_internal_analysis") or {}).get("diffusion_quality")
            or {}
        )
        sector_rows = diffusion if isinstance(diffusion, list) else diffusion.get("sectors") if isinstance(diffusion, dict) else []
        rows = []
        component_rows = []
        for item in sector_rows or []:
            if not isinstance(item, dict):
                continue
            sector = _text(item.get("sector_name") or item.get("name"))
            if not sector:
                continue
            rows.append(
                (
                    trade_date,
                    sector,
                    _safe_float(item.get("total_score")),
                    _text(item.get("level")),
                    _text(item.get("conclusion")),
                    _text(item.get("action")),
                )
            )
            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            for component_key, component in details.items():
                if not isinstance(component, dict):
                    continue
                component_rows.append(
                    (
                        trade_date,
                        sector,
                        _text(component_key),
                        _safe_float(component.get("score")),
                        _text(component.get("label")),
                        _text(component.get("detail") or component.get("description")),
                    )
                )
        if rows:
            cursor.executemany(
                """
                INSERT INTO sector_diffusion_score_daily(
                    trade_date, sector_name, total_score, level, conclusion, action
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, sector_name) DO UPDATE SET
                    total_score=EXCLUDED.total_score,
                    level=EXCLUDED.level,
                    conclusion=EXCLUDED.conclusion,
                    action=EXCLUDED.action,
                    updated_at=now()
                """,
                rows,
            )
        if component_rows:
            cursor.executemany(
                """
                INSERT INTO sector_diffusion_score_components(
                    trade_date, sector_name, component_key, score, label, detail
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, sector_name, component_key) DO UPDATE SET
                    score=EXCLUDED.score,
                    label=EXCLUDED.label,
                    detail=EXCLUDED.detail,
                    updated_at=now()
                """,
                component_rows,
            )
        counts["sector_diffusion_records"] = len(rows)
        counts["sector_diffusion_components"] = len(component_rows)

    def _replace_sector_competition_records(self, cursor, trade_date, snapshot, counts):
        cursor.execute("DELETE FROM sector_competition_daily WHERE trade_date = %s", (trade_date,))
        observation = snapshot.get("observation") if isinstance(snapshot.get("observation"), dict) else {}
        rows = []
        for item in observation.get("mainline_competition_snapshot") or snapshot.get("mainline_competition_snapshot") or []:
            if not isinstance(item, dict):
                continue
            sector = _text(item.get("sector") or item.get("sector_name"))
            role = _text(item.get("role"))
            if not sector or not role:
                continue
            evidence_parts = [
                _text(item.get("evidence")),
                _text(item.get("judgement")),
                _text(item.get("action")),
            ]
            rows.append((trade_date, sector, role, "；".join(part for part in evidence_parts if part)))
        if rows:
            cursor.executemany(
                """
                INSERT INTO sector_competition_daily(
                    trade_date, sector_name, role, evidence
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (trade_date, sector_name, role) DO UPDATE SET
                    evidence=EXCLUDED.evidence,
                    updated_at=now()
                """,
                rows,
            )
        counts["sector_competition_records"] = len(rows)

    def _replace_market_capacity_evolution_record(self, cursor, trade_date, snapshot, counts):
        cursor.execute("DELETE FROM market_capacity_evolution_daily WHERE trade_date = %s", (trade_date,))
        summary = snapshot.get("mainline_turnover_summary") if isinstance(snapshot.get("mainline_turnover_summary"), dict) else {}
        capacity = summary.get("mainline_capacity_regime_summary") if isinstance(summary.get("mainline_capacity_regime_summary"), dict) else {}
        overtake = summary.get("overtake_window_summary") if isinstance(summary.get("overtake_window_summary"), dict) else {}
        if not any(_text(capacity.get(key)) for key in ("mainline_capacity", "mainline_regime", "primary_line", "sector_relationship_state", "mainline_process")):
            counts["market_capacity_evolution_records"] = 0
            return
        turnover_quality = _text(snapshot.get("turnover_quality") or summary.get("turnover_quality") or capacity.get("turnover_quality"))
        mainline_regime = _text(capacity.get("mainline_regime"))
        window_state = _text(snapshot.get("window_state") or overtake.get("window_state"))
        row = (
            trade_date,
            _market_capacity_phase(window_state, mainline_regime, turnover_quality),
            turnover_quality,
            mainline_regime,
            window_state,
            _text(snapshot.get("capacity_evidence") or capacity.get("capacity_evidence") or capacity.get("confirmation_evidence")),
        )
        cursor.execute(
            """
            INSERT INTO market_capacity_evolution_daily(
                trade_date, phase, turnover_quality, mainline_regime,
                window_state, capacity_evidence
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (trade_date) DO UPDATE SET
                phase=EXCLUDED.phase,
                turnover_quality=EXCLUDED.turnover_quality,
                mainline_regime=EXCLUDED.mainline_regime,
                window_state=EXCLUDED.window_state,
                capacity_evidence=EXCLUDED.capacity_evidence,
                updated_at=now()
            """,
            row,
        )
        counts["market_capacity_evolution_records"] = 1

    def _replace_pivot_records(self, cursor, trade_date, snapshot, counts):
        cursor.execute("DELETE FROM zhongshu_mainline_records WHERE trade_date = %s", (trade_date,))
        rows = []
        for row in snapshot.get("pivot_mainline_rows") or []:
            if not isinstance(row, dict):
                continue
            rows.append(
                (
                    trade_date,
                    _text(row.get("date_range")),
                    _text(row.get("pivot_level")),
                    _text(row.get("pivot_range")),
                    _text(row.get("position")),
                    _text(row.get("structure_state")),
                    _text(row.get("mainline")),
                    _text(row.get("mainline_degree")),
                    _text(row.get("evolution")),
                    _text(row.get("replacement")),
                    _text(row.get("interpretation")),
                )
            )
        if rows:
            cursor.executemany(
                """
                INSERT INTO zhongshu_mainline_records(
                    trade_date, date_range, pivot_level, pivot_range, position,
                    structure_state, mainline, mainline_degree, evolution,
                    replacement, interpretation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, date_range, mainline) DO UPDATE SET
                    pivot_level=EXCLUDED.pivot_level,
                    pivot_range=EXCLUDED.pivot_range,
                    position=EXCLUDED.position,
                    structure_state=EXCLUDED.structure_state,
                    mainline_degree=EXCLUDED.mainline_degree,
                    evolution=EXCLUDED.evolution,
                    replacement=EXCLUDED.replacement,
                    interpretation=EXCLUDED.interpretation,
                    updated_at=now()
                """,
                rows,
            )
        counts["pivot_records"] = len(rows)

    def replace_observation_pool_items_for_trade_date(self, trade_date, pools):
        trade_date = _date_or_none(trade_date)
        rows = []
        for pool_key, items in (pools or {}).items():
            if not isinstance(items, list):
                continue
            for rank, item in enumerate(items, 1):
                if not isinstance(item, dict):
                    continue
                code = _stock_code(item)
                if not code:
                    continue
                rows.append(
                    (
                        trade_date,
                        _text(pool_key),
                        code,
                        _stock_name(item),
                        _sector_name(item),
                        _safe_int(item.get("rank") or item.get("rank_no"), rank),
                        _safe_float(item.get("score") or item.get("remember_score") or item.get("abnormal_score")),
                        _text(item.get("status") or item.get("follow_state")),
                        _first_text(item, "reason", "last_reason", "remember_reason", "action_rule", "tomorrow_expectation"),
                        _first_text(item, "action_text", "action_rule", "missed_action", "tomorrow_expectation"),
                        _text(item.get("source")),
                    )
                )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM daily_observation_pool_items WHERE trade_date = %s", (trade_date,))
                if rows:
                    cursor.executemany(
                        """
                        INSERT INTO daily_observation_pool_items(
                            trade_date, pool_key, stock_code, stock_name, sector_name,
                            rank_no, score, status, reason, action_text, source_policy
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (trade_date, pool_key, stock_code) DO UPDATE SET
                            stock_name=EXCLUDED.stock_name,
                            sector_name=EXCLUDED.sector_name,
                            rank_no=EXCLUDED.rank_no,
                            score=EXCLUDED.score,
                            status=EXCLUDED.status,
                            reason=EXCLUDED.reason,
                            action_text=EXCLUDED.action_text,
                            source_policy=EXCLUDED.source_policy,
                            updated_at=now()
                        """,
                        rows,
                    )
                    lifecycle_rows = [
                        (
                            code,
                            pool_key,
                            trade_date,
                            trade_date,
                            status,
                            reason,
                        )
                        for (
                            _trade_date,
                            pool_key,
                            code,
                            _name,
                            _sector,
                            _rank,
                            _score,
                            status,
                            reason,
                            _action,
                            _source,
                        ) in rows
                    ]
                    cursor.executemany(
                        """
                        INSERT INTO observation_pool_lifecycle(
                            stock_code, pool_key, first_seen_date, last_seen_date,
                            status, last_reason
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (stock_code, pool_key) DO UPDATE SET
                            last_seen_date=EXCLUDED.last_seen_date,
                            status=EXCLUDED.status,
                            last_reason=EXCLUDED.last_reason,
                            appearances=observation_pool_lifecycle.appearances + 1,
                            updated_at=now()
                        """,
                        lifecycle_rows,
                    )
                    leader_rows = [
                        row for row in rows if row[1] == "leader_memory_bank"
                    ]
                    if leader_rows:
                        cursor.executemany(
                            """
                            INSERT INTO leader_memory_items(
                                trade_date, stock_code, stock_name, sector_name,
                                remember_score, remember_reason, action_rule
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (trade_date, stock_code) DO UPDATE SET
                                stock_name=EXCLUDED.stock_name,
                                sector_name=EXCLUDED.sector_name,
                                remember_score=EXCLUDED.remember_score,
                                remember_reason=EXCLUDED.remember_reason,
                                action_rule=EXCLUDED.action_rule,
                                updated_at=now()
                            """,
                            [
                                (row[0], row[2], row[3], row[4], row[6], row[8], row[9])
                                for row in leader_rows
                            ],
                        )
            conn.commit()
        return len(rows)

    def load_tracking_memory_state(self):
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT stock_code, stock_name, sector_name, status, first_seen_date,
                           last_seen_date, confirmations, failures, appearances,
                           sources_text, last_reason, follow_state, evidence_score,
                           inactive_reason
                    FROM tracking_memory_daily_status
                    WHERE trade_date = (
                        SELECT max(trade_date) FROM tracking_memory_daily_status
                    )
                    ORDER BY evidence_score DESC, confirmations DESC, stock_code ASC
                    """
                )
                rows = cursor.fetchall()
        items = []
        columns = (
            "stock_code",
            "stock_name",
            "sector_name",
            "status",
            "first_seen_date",
            "last_seen_date",
            "confirmations",
            "failures",
            "appearances",
            "sources_text",
            "last_reason",
            "follow_state",
            "evidence_score",
            "inactive_reason",
        )
        for row in rows or []:
            item = _row_dict(row, columns)
            items.append(
                {
                    "code": _text(item.get("stock_code")),
                    "name": _text(item.get("stock_name")),
                    "sector": _text(item.get("sector_name")),
                    "status": _text(item.get("status")),
                    "first_seen_date": _text(item.get("first_seen_date")),
                    "last_seen_date": _text(item.get("last_seen_date")),
                    "confirmations": _safe_int(item.get("confirmations")),
                    "failures": _safe_int(item.get("failures")),
                    "appearances": _safe_int(item.get("appearances")),
                    "sources": [part for part in _text(item.get("sources_text")).split(",") if part],
                    "last_reason": _text(item.get("last_reason")),
                    "follow_state": _text(item.get("follow_state")),
                    "evidence_score": _safe_float(item.get("evidence_score")),
                    "inactive_reason": _text(item.get("inactive_reason")),
                }
            )
        return {"items": items}

    def save_tracking_memory_state(self, state):
        trade_date = _date_or_none((state or {}).get("updated_at"))
        rows = []
        for item in (state or {}).get("items") or []:
            if not isinstance(item, dict):
                continue
            code = _stock_code(item)
            if not code:
                continue
            rows.append(
                (
                    trade_date,
                    code,
                    _stock_name(item),
                    _sector_name(item),
                    _text(item.get("status")),
                    _date_or_none(item.get("first_seen_date")),
                    _date_or_none(item.get("last_seen_date")),
                    _safe_int(item.get("confirmations")),
                    _safe_int(item.get("failures")),
                    _safe_int(item.get("appearances")),
                    ",".join(_text(source) for source in item.get("sources") or [] if _text(source)),
                    _text(item.get("last_reason")),
                    _text(item.get("follow_state")),
                    _safe_float(item.get("evidence_score")),
                    _text(item.get("inactive_reason")),
                )
            )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if trade_date:
                    cursor.execute("DELETE FROM tracking_memory_daily_status WHERE trade_date = %s", (trade_date,))
                if rows:
                    cursor.executemany(
                        """
                        INSERT INTO tracking_memory_daily_status(
                            trade_date, stock_code, stock_name, sector_name, status,
                            first_seen_date, last_seen_date, confirmations, failures,
                            appearances, sources_text, last_reason, follow_state,
                            evidence_score, inactive_reason
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (trade_date, stock_code) DO UPDATE SET
                            stock_name=EXCLUDED.stock_name,
                            sector_name=EXCLUDED.sector_name,
                            status=EXCLUDED.status,
                            first_seen_date=EXCLUDED.first_seen_date,
                            last_seen_date=EXCLUDED.last_seen_date,
                            confirmations=EXCLUDED.confirmations,
                            failures=EXCLUDED.failures,
                            appearances=EXCLUDED.appearances,
                            sources_text=EXCLUDED.sources_text,
                            last_reason=EXCLUDED.last_reason,
                            follow_state=EXCLUDED.follow_state,
                            evidence_score=EXCLUDED.evidence_score,
                            inactive_reason=EXCLUDED.inactive_reason,
                            updated_at=now()
                        """,
                        rows,
                    )
            conn.commit()
        return len(rows)

    def query_a_kill_cooling_records(self):
        columns = ("stock_code", "stock_name", "sector_name", "a_kill_date", "ban_until", "reason")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT stock_code, stock_name, sector_name, a_kill_date, ban_until, reason
                    FROM a_kill_cooling_items
                    ORDER BY a_kill_date ASC, stock_code ASC
                    """
                )
                rows = cursor.fetchall()
        return [self._a_kill_row_to_record(_row_dict(row, columns)) for row in rows or []]

    def query_active_a_kill_cooling_records(self, target_date):
        target = _date_or_none(target_date)
        columns = ("stock_code", "stock_name", "sector_name", "a_kill_date", "ban_until", "reason")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT stock_code, stock_name, sector_name, a_kill_date, ban_until, reason
                    FROM a_kill_cooling_items
                    WHERE a_kill_date <= %s AND ban_until > %s
                    ORDER BY ban_until ASC, stock_name ASC
                    """,
                    (target, target),
                )
                rows = cursor.fetchall()
        records = []
        target_dt = None
        try:
            target_dt = _dt.datetime.strptime(_text(target)[:10], "%Y-%m-%d").date()
        except ValueError:
            target_dt = None
        for row in rows or []:
            record = self._a_kill_row_to_record(_row_dict(row, columns))
            if target_dt and record.get("a_kill_date"):
                try:
                    record_dt = _dt.datetime.strptime(record["a_kill_date"][:10], "%Y-%m-%d").date()
                    ban_dt = _dt.datetime.strptime(record.get("ban_until", "")[:10], "%Y-%m-%d").date()
                    record["days_passed"] = (target_dt - record_dt).days
                    record["remaining_days"] = max((ban_dt - target_dt).days, 0)
                except ValueError:
                    pass
            records.append(record)
        return records

    def replace_a_kill_cooling_records(self, records):
        rows = []
        for record in records or []:
            if not isinstance(record, dict):
                continue
            code = _stock_code(record)
            if not code:
                continue
            rows.append(
                (
                    code,
                    _stock_name(record),
                    _sector_name(record),
                    _date_or_none(record.get("a_kill_date")),
                    _date_or_none(record.get("ban_until")),
                    _first_text(record, "reason", "note", "sector"),
                )
            )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM a_kill_cooling_items")
                if rows:
                    cursor.executemany(
                        """
                        INSERT INTO a_kill_cooling_items(
                            stock_code, stock_name, sector_name, a_kill_date, ban_until, reason
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (stock_code) DO UPDATE SET
                            stock_name=EXCLUDED.stock_name,
                            sector_name=EXCLUDED.sector_name,
                            a_kill_date=EXCLUDED.a_kill_date,
                            ban_until=EXCLUDED.ban_until,
                            reason=EXCLUDED.reason,
                            updated_at=now()
                        """,
                        rows,
                    )
            conn.commit()
        return len(rows)

    def load_strategy_performance_ledger(self, mode="frozen"):
        columns = (
            "mode",
            "report_date",
            "action_type",
            "anchor_type",
            "position_level",
            "operation_state",
            "execution_status",
            "can_new_entry",
            "final_action",
            "mainline_name",
            "stock_code",
            "stock_name",
            "stock_sector",
            "factor_snapshot_path",
            "version",
            "updated_at_text",
        )
        field_columns = (
            "report_date",
            "field_name",
            "value_text",
            "value_number",
            "value_bool",
            "value_kind",
        )
        snapshot_field_columns = (
            "report_date",
            "field_path",
            "value_text",
            "value_number",
            "value_bool",
            "value_kind",
        )
        pool_columns = (
            "report_date",
            "pool_name",
            "ordinal",
            "stock_code",
            "stock_name",
            "sector_name",
            "action_type",
            "participation_mode",
            "position_pct",
            "setup_signal_id",
            "setup_signal_label",
            "follow_state",
            "reason",
            "final_action",
            "trigger_text",
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT mode, report_date, action_type, anchor_type, position_level,
                           operation_state, execution_status, can_new_entry,
                           final_action, mainline_name, stock_code, stock_name,
                           stock_sector, factor_snapshot_path, version, updated_at_text
                    FROM strategy_performance_ledger
                    WHERE mode = %s
                    ORDER BY report_date ASC
                    """,
                    (_text(mode) or "frozen",),
                )
                rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT report_date, field_name, value_text, value_number, value_bool, value_kind
                    FROM strategy_performance_record_fields
                    WHERE mode = %s
                    ORDER BY report_date ASC, field_name ASC
                    """,
                    (_text(mode) or "frozen",),
                )
                field_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT report_date, field_path, value_text, value_number, value_bool, value_kind
                    FROM strategy_factor_snapshot_fields
                    WHERE mode = %s
                    ORDER BY report_date ASC, field_path ASC
                    """,
                    (_text(mode) or "frozen",),
                )
                snapshot_field_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT report_date, pool_name, ordinal, stock_code, stock_name,
                           sector_name, action_type, participation_mode, position_pct,
                           setup_signal_id, setup_signal_label, follow_state, reason,
                           final_action, trigger_text
                    FROM strategy_factor_snapshot_pool_items
                    WHERE mode = %s
                    ORDER BY report_date ASC, pool_name ASC, ordinal ASC
                    """,
                    (_text(mode) or "frozen",),
                )
                pool_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT mode, report_date, version, market_branch, source_policy, saved_at
                    FROM strategy_factor_snapshots
                    WHERE mode = %s
                    ORDER BY report_date ASC
                    """,
                    (_text(mode) or "frozen",),
                )
                snapshot_meta_rows = cursor.fetchall()
        fields_by_date = {}
        for row in field_rows or []:
            item = _row_dict(row, field_columns)
            report_date = _text(item.get("report_date"))
            if not report_date:
                continue
            fields_by_date.setdefault(report_date, {})[_text(item.get("field_name"))] = _restore_typed_value(item)

        snapshots_by_date = {}
        for row in snapshot_meta_rows or []:
            item = _row_dict(row, ("mode", "report_date", "version", "market_branch", "source_policy", "saved_at"))
            report_date = _text(item.get("report_date"))
            if not report_date:
                continue
            snapshot = snapshots_by_date.setdefault(report_date, {})
            snapshot["version"] = _text(item.get("version"))
            snapshot["report_date"] = report_date
            if _text(item.get("market_branch")):
                snapshot["market_branch"] = _text(item.get("market_branch"))
            if _text(item.get("source_policy")):
                snapshot["source_policy"] = _text(item.get("source_policy"))

        for row in snapshot_field_rows or []:
            item = _row_dict(row, snapshot_field_columns)
            report_date = _text(item.get("report_date"))
            if not report_date:
                continue
            snapshot = snapshots_by_date.setdefault(report_date, {"report_date": report_date})
            _set_nested_value(snapshot, item.get("field_path"), _restore_typed_value(item))

        pool_groups = {}
        for row in pool_rows or []:
            item = _row_dict(row, pool_columns)
            report_date = _text(item.get("report_date"))
            pool_name = _text(item.get("pool_name"))
            if not report_date or not pool_name:
                continue
            pool_groups.setdefault((report_date, pool_name), []).append(item)
        for (report_date, pool_name), items in pool_groups.items():
            snapshot = snapshots_by_date.setdefault(report_date, {"report_date": report_date})
            pool_items = [self._strategy_factor_pool_row_to_item(item) for item in items]
            _set_nested_list(snapshot, pool_name, pool_items)
            snapshots_by_date[report_date] = snapshot
        records = []
        version = ""
        updated_at = ""
        for row in rows or []:
            item = _row_dict(row, columns)
            version = _text(item.get("version")) or version
            updated_at = _text(item.get("updated_at_text")) or updated_at
            report_date = _text(item.get("report_date"))
            record = self._strategy_ledger_row_to_record(item)
            record.update(fields_by_date.get(report_date, {}))
            if report_date in snapshots_by_date:
                record["factor_snapshot"] = snapshots_by_date[report_date]
            records.append(record)
        return {
            "version": version,
            "updated_at": updated_at,
            "mode": _text(mode) or "frozen",
            "records": records,
        }

    def save_strategy_performance_ledger(self, ledger, mode="frozen"):
        ledger = dict(ledger or {})
        mode = _text(mode) or "frozen"
        records = list(ledger.get("records") or [])
        rows = []
        field_rows = []
        snapshot_rows = []
        snapshot_field_rows = []
        pool_rows = []
        for record in records:
            if not isinstance(record, dict):
                continue
            report_date = _date_or_none(record.get("report_date") or record.get("date") or ledger.get("report_date"))
            if not report_date:
                continue
            selected = record.get("selected_target") if isinstance(record.get("selected_target"), dict) else {}
            factor_snapshot = record.get("factor_snapshot") if isinstance(record.get("factor_snapshot"), dict) else {}
            rows.append(
                (
                    mode,
                    report_date,
                    _text(record.get("action_type")),
                    _text(record.get("anchor_type")),
                    _text(record.get("position_level")),
                    _text(record.get("operation_state")),
                    _text(record.get("execution_status")),
                    bool(record.get("can_new_entry")),
                    _text(record.get("final_action") or record.get("action")),
                    _text(record.get("mainline_name") or record.get("mainline")),
                    _stock_code(selected or record),
                    _stock_name(selected or record),
                    _sector_name(selected or record),
                    _text(record.get("factor_snapshot_path")),
                    _text(ledger.get("version")),
                    _text(ledger.get("updated_at")),
                )
            )
            field_rows.extend(self._strategy_record_scalar_rows(mode, report_date, record))
            if factor_snapshot:
                snapshot_rows.append(
                    (
                        mode,
                        report_date,
                        _text(factor_snapshot.get("version") or ledger.get("version")),
                        _text(factor_snapshot.get("market_branch") or (factor_snapshot.get("mainline") or {}).get("name")),
                        _text(factor_snapshot.get("source_policy") or factor_snapshot.get("source")),
                    )
                )
                snapshot_field_rows.extend(self._strategy_factor_field_rows(mode, report_date, factor_snapshot))
                pool_rows.extend(self._strategy_factor_pool_rows(mode, report_date, factor_snapshot))
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM strategy_performance_ledger WHERE mode = %s", (mode,))
                cursor.execute("DELETE FROM strategy_performance_record_fields WHERE mode = %s", (mode,))
                cursor.execute("DELETE FROM strategy_factor_snapshots WHERE mode = %s", (mode,))
                cursor.execute("DELETE FROM strategy_factor_snapshot_fields WHERE mode = %s", (mode,))
                cursor.execute("DELETE FROM strategy_factor_snapshot_pool_items WHERE mode = %s", (mode,))
                if rows:
                    cursor.executemany(
                        """
                        INSERT INTO strategy_performance_ledger(
                            mode, report_date, action_type, anchor_type, position_level,
                            operation_state, execution_status, can_new_entry,
                            final_action, mainline_name, stock_code, stock_name,
                            stock_sector, factor_snapshot_path, version, updated_at_text
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (mode, report_date) DO UPDATE SET
                            action_type=EXCLUDED.action_type,
                            anchor_type=EXCLUDED.anchor_type,
                            position_level=EXCLUDED.position_level,
                            operation_state=EXCLUDED.operation_state,
                            execution_status=EXCLUDED.execution_status,
                            can_new_entry=EXCLUDED.can_new_entry,
                            final_action=EXCLUDED.final_action,
                            mainline_name=EXCLUDED.mainline_name,
                            stock_code=EXCLUDED.stock_code,
                            stock_name=EXCLUDED.stock_name,
                            stock_sector=EXCLUDED.stock_sector,
                            factor_snapshot_path=EXCLUDED.factor_snapshot_path,
                            version=EXCLUDED.version,
                            updated_at_text=EXCLUDED.updated_at_text,
                            updated_at=now()
                        """,
                        rows,
                    )
                if field_rows:
                    cursor.executemany(
                        """
                        INSERT INTO strategy_performance_record_fields(
                            mode, report_date, field_name, value_text, value_number, value_bool, value_kind
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (mode, report_date, field_name) DO UPDATE SET
                            value_text=EXCLUDED.value_text,
                            value_number=EXCLUDED.value_number,
                            value_bool=EXCLUDED.value_bool,
                            value_kind=EXCLUDED.value_kind,
                            updated_at=now()
                        """,
                        field_rows,
                    )
                if snapshot_rows:
                    cursor.executemany(
                        """
                        INSERT INTO strategy_factor_snapshots(
                            mode, report_date, version, market_branch, source_policy
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (mode, report_date) DO UPDATE SET
                            version=EXCLUDED.version,
                            market_branch=EXCLUDED.market_branch,
                            source_policy=EXCLUDED.source_policy,
                            updated_at=now()
                        """,
                        snapshot_rows,
                    )
                if snapshot_field_rows:
                    cursor.executemany(
                        """
                        INSERT INTO strategy_factor_snapshot_fields(
                            mode, report_date, field_path, value_text, value_number, value_bool, value_kind
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (mode, report_date, field_path) DO UPDATE SET
                            value_text=EXCLUDED.value_text,
                            value_number=EXCLUDED.value_number,
                            value_bool=EXCLUDED.value_bool,
                            value_kind=EXCLUDED.value_kind,
                            updated_at=now()
                        """,
                        snapshot_field_rows,
                    )
                if pool_rows:
                    cursor.executemany(
                        """
                        INSERT INTO strategy_factor_snapshot_pool_items(
                            mode, report_date, pool_name, ordinal, stock_code, stock_name,
                            sector_name, action_type, participation_mode, position_pct,
                            setup_signal_id, setup_signal_label, follow_state, reason,
                            final_action, trigger_text
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (mode, report_date, pool_name, ordinal) DO UPDATE SET
                            stock_code=EXCLUDED.stock_code,
                            stock_name=EXCLUDED.stock_name,
                            sector_name=EXCLUDED.sector_name,
                            action_type=EXCLUDED.action_type,
                            participation_mode=EXCLUDED.participation_mode,
                            position_pct=EXCLUDED.position_pct,
                            setup_signal_id=EXCLUDED.setup_signal_id,
                            setup_signal_label=EXCLUDED.setup_signal_label,
                            follow_state=EXCLUDED.follow_state,
                            reason=EXCLUDED.reason,
                            final_action=EXCLUDED.final_action,
                            trigger_text=EXCLUDED.trigger_text,
                            updated_at=now()
                        """,
                        pool_rows,
                    )
            conn.commit()
        return f"postgresql://strategy_performance/{mode}"

    def save_factor_snapshot(self, target_date, factor_snapshot, mode="frozen"):
        snapshot = dict(factor_snapshot or {})
        if not snapshot:
            return {"path": "", "mode": mode, "saved": False}
        mode = _text(mode) or "frozen"
        report_date = _date_or_none(target_date or snapshot.get("report_date"))
        snapshot.setdefault("report_date", report_date)
        saved_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot_field_rows = self._strategy_factor_field_rows(mode, report_date, snapshot)
        pool_rows = self._strategy_factor_pool_rows(mode, report_date, snapshot)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO strategy_factor_snapshots(
                        mode, report_date, version, market_branch, source_policy, saved_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (mode, report_date) DO UPDATE SET
                        version=EXCLUDED.version,
                        market_branch=EXCLUDED.market_branch,
                        source_policy=EXCLUDED.source_policy,
                        saved_at=EXCLUDED.saved_at,
                        updated_at=now()
                    """,
                    (
                        mode,
                        report_date,
                        _text(snapshot.get("version")),
                        _text(snapshot.get("market_branch")),
                        _text(snapshot.get("source_policy") or snapshot.get("source")),
                        saved_at,
                    ),
                )
                cursor.execute(
                    "DELETE FROM strategy_factor_snapshot_fields WHERE mode = %s AND report_date = %s",
                    (mode, report_date),
                )
                cursor.execute(
                    "DELETE FROM strategy_factor_snapshot_pool_items WHERE mode = %s AND report_date = %s",
                    (mode, report_date),
                )
                if snapshot_field_rows:
                    cursor.executemany(
                        """
                        INSERT INTO strategy_factor_snapshot_fields(
                            mode, report_date, field_path, value_text, value_number, value_bool, value_kind
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (mode, report_date, field_path) DO UPDATE SET
                            value_text=EXCLUDED.value_text,
                            value_number=EXCLUDED.value_number,
                            value_bool=EXCLUDED.value_bool,
                            value_kind=EXCLUDED.value_kind,
                            updated_at=now()
                        """,
                        snapshot_field_rows,
                    )
                if pool_rows:
                    cursor.executemany(
                        """
                        INSERT INTO strategy_factor_snapshot_pool_items(
                            mode, report_date, pool_name, ordinal, stock_code, stock_name,
                            sector_name, action_type, participation_mode, position_pct,
                            setup_signal_id, setup_signal_label, follow_state, reason,
                            final_action, trigger_text
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (mode, report_date, pool_name, ordinal) DO UPDATE SET
                            stock_code=EXCLUDED.stock_code,
                            stock_name=EXCLUDED.stock_name,
                            sector_name=EXCLUDED.sector_name,
                            action_type=EXCLUDED.action_type,
                            participation_mode=EXCLUDED.participation_mode,
                            position_pct=EXCLUDED.position_pct,
                            setup_signal_id=EXCLUDED.setup_signal_id,
                            setup_signal_label=EXCLUDED.setup_signal_label,
                            follow_state=EXCLUDED.follow_state,
                            reason=EXCLUDED.reason,
                            final_action=EXCLUDED.final_action,
                            trigger_text=EXCLUDED.trigger_text,
                            updated_at=now()
                        """,
                        pool_rows,
                    )
            conn.commit()
        return {
            "path": f"postgresql://factor-snapshots/{report_date}",
            "mode": mode,
            "saved": True,
            "saved_at": saved_at,
            "version": _text(snapshot.get("version")),
        }

    def replace_candidate_trace_artifact(self, payload):
        payload = dict(payload or {})
        trade_date = _date_or_none(payload.get("trade_date"))
        source_report = payload.get("source_report") if isinstance(payload.get("source_report"), dict) else {}
        traces = [trace for trace in payload.get("traces") or [] if isinstance(trace, dict)]
        eliminated = [item for item in payload.get("eliminated_summary") or [] if isinstance(item, dict)]
        trace_field_rows = []
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM candidate_trace_rows WHERE trade_date = %s", (trade_date,))
                cursor.execute("DELETE FROM candidate_trace_eliminated_groups WHERE trade_date = %s", (trade_date,))
                cursor.execute("DELETE FROM candidate_trace_row_fields WHERE trade_date = %s", (trade_date,))
                cursor.execute(
                    """
                    INSERT INTO candidate_trace_artifacts(
                        trade_date, artifact_version, visible_scope, generated_at,
                        source_report_path, source_report_variant
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date) DO UPDATE SET
                        artifact_version=EXCLUDED.artifact_version,
                        visible_scope=EXCLUDED.visible_scope,
                        generated_at=EXCLUDED.generated_at,
                        source_report_path=EXCLUDED.source_report_path,
                        source_report_variant=EXCLUDED.source_report_variant,
                        updated_at=now()
                    """,
                    (
                        trade_date,
                        _safe_int(payload.get("artifact_version")),
                        _text(payload.get("visible_scope")),
                        _text(payload.get("generated_at")),
                        _text(source_report.get("path")),
                        _text(source_report.get("variant")),
                    ),
                )
                trace_rows = []
                for trace in traces:
                    code = _stock_code(trace)
                    if not code:
                        continue
                    trace_field_rows.extend(self._candidate_trace_field_rows(trade_date, trace))
                    trace_rows.append(
                        (
                            trade_date,
                            code,
                            _stock_name(trace),
                            _text(trace.get("tier")),
                            _text(trace.get("mainline")),
                            _sector_name(trace),
                            _text(trace.get("final_action")),
                            _first_text(trace, "visible_summary", "summary"),
                            _first_text(trace, "trigger_condition", "entry_condition"),
                            _first_text(trace, "failure_condition", "invalidation"),
                        )
                    )
                if trace_rows:
                    cursor.executemany(
                        """
                        INSERT INTO candidate_trace_rows(
                            trade_date, stock_code, stock_name, tier, mainline,
                            sector_name, final_action, visible_summary,
                            trigger_condition, failure_condition
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (trade_date, stock_code) DO UPDATE SET
                            stock_name=EXCLUDED.stock_name,
                            tier=EXCLUDED.tier,
                            mainline=EXCLUDED.mainline,
                            sector_name=EXCLUDED.sector_name,
                            final_action=EXCLUDED.final_action,
                            visible_summary=EXCLUDED.visible_summary,
                            trigger_condition=EXCLUDED.trigger_condition,
                            failure_condition=EXCLUDED.failure_condition,
                            updated_at=now()
                        """,
                        trace_rows,
                    )
                if trace_field_rows:
                    cursor.executemany(
                        """
                        INSERT INTO candidate_trace_row_fields(
                            trade_date, stock_code, field_name, value_text, value_number, value_bool, value_kind
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (trade_date, stock_code, field_name) DO UPDATE SET
                            value_text=EXCLUDED.value_text,
                            value_number=EXCLUDED.value_number,
                            value_bool=EXCLUDED.value_bool,
                            value_kind=EXCLUDED.value_kind,
                            updated_at=now()
                        """,
                        trace_field_rows,
                    )
                eliminated_rows = []
                for item in eliminated:
                    reason = _text(item.get("reason"))
                    if not reason:
                        continue
                    representatives = item.get("representatives") or []
                    if isinstance(representatives, (list, tuple)):
                        representatives_text = "、".join(_text(value) for value in representatives if _text(value))
                    else:
                        representatives_text = _text(representatives)
                    eliminated_rows.append(
                        (
                            trade_date,
                            reason,
                            _safe_int(item.get("count") or item.get("count_value")),
                            representatives_text,
                            _text(item.get("treatment")),
                        )
                    )
                if eliminated_rows:
                    cursor.executemany(
                        """
                        INSERT INTO candidate_trace_eliminated_groups(
                            trade_date, reason, count_value, representatives_text, treatment
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (trade_date, reason) DO UPDATE SET
                            count_value=EXCLUDED.count_value,
                            representatives_text=EXCLUDED.representatives_text,
                            treatment=EXCLUDED.treatment,
                            updated_at=now()
                        """,
                        eliminated_rows,
                    )
            conn.commit()
        return {
            "artifact_path": f"postgresql://candidate-traces/{trade_date}",
            "trace_count": len(trace_rows),
            "eliminated_group_count": len(eliminated_rows),
        }

    def save_daily_report_snapshot(self, trade_date, data):
        trade_date = _date_or_none(trade_date)
        if not trade_date:
            return {"field_count": 0, "source": ""}
        projected = _build_daily_report_fact_projection(data or {})
        rows = []
        for field_path, value in _iter_safe_fact_fields(projected, max_depth=12):
            if not field_path:
                continue
            if _field_path_has_low_value_component(field_path):
                continue
            value_text, value_number, value_bool, value_kind = _typed_value(value)
            rows.append(
                (
                    trade_date,
                    _text(field_path),
                    value_text,
                    value_number,
                    value_bool,
                    value_kind,
                    "postgresql.daily_report_facts",
                )
            )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM daily_report_fact_fields WHERE trade_date = %s", (trade_date,))
                if rows:
                    cursor.executemany(
                        """
                        INSERT INTO daily_report_fact_fields(
                            trade_date, field_path, value_text, value_number,
                            value_bool, value_kind, source_policy
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (trade_date, field_path) DO UPDATE SET
                            value_text=EXCLUDED.value_text,
                            value_number=EXCLUDED.value_number,
                            value_bool=EXCLUDED.value_bool,
                            value_kind=EXCLUDED.value_kind,
                            source_policy=EXCLUDED.source_policy,
                            updated_at=now()
                        """,
                        rows,
                    )
            conn.commit()
        return {
            "source": f"postgresql://daily-report-facts/{trade_date}",
            "field_count": len(rows),
        }

    def save_daily_report_facts(self, trade_date, data):
        return self.save_daily_report_snapshot(trade_date, data)

    def prune_recent_replay_fact_tables(self, min_trade_date):
        min_trade_date = _date_or_none(min_trade_date)
        if not min_trade_date:
            return 0
        removed = 0
        with self._connect() as conn:
            with conn.cursor() as cursor:
                for table_name, column_name in _RECENT_REPLAY_FACT_DATE_COLUMNS:
                    cursor.execute(
                        f"DELETE FROM {table_name} WHERE {column_name} < %s",
                        (min_trade_date,),
                    )
                    rowcount = getattr(cursor, "rowcount", 0)
                    if isinstance(rowcount, int) and rowcount > 0:
                        removed += rowcount
                for table_name, column_name, source_table, source_column in _RECENT_REPLAY_FACT_ORPHAN_DELETES:
                    cursor.execute(
                        f"""
                        DELETE FROM {table_name}
                        WHERE {column_name} NOT IN (
                            SELECT {source_column} FROM {source_table}
                        )
                        """
                    )
                    rowcount = getattr(cursor, "rowcount", 0)
                    if isinstance(rowcount, int) and rowcount > 0:
                        removed += rowcount
                for table_name, primary_column, fallback_column in _RECENT_REPLAY_FACT_RANGE_DELETES:
                    cursor.execute(
                        f"DELETE FROM {table_name} WHERE COALESCE({primary_column}, {fallback_column}) < %s",
                        (min_trade_date,),
                    )
                    rowcount = getattr(cursor, "rowcount", 0)
                    if isinstance(rowcount, int) and rowcount > 0:
                        removed += rowcount
            conn.commit()
        return removed

    def import_daily_report_facts(self, trade_date, data):
        trade_date = _date_or_none(trade_date)
        data = data or {}
        structured_counts = {}
        market_snapshot = dict(data.get("market_research_snapshot") or {}) if isinstance(data.get("market_research_snapshot"), dict) else {}
        if isinstance(data.get("sector_internal_analysis"), dict):
            existing_internal = market_snapshot.get("sector_internal_analysis")
            merged_internal = dict(existing_internal or {}) if isinstance(existing_internal, dict) else {}
            merged_internal.update(data.get("sector_internal_analysis") or {})
            market_snapshot["sector_internal_analysis"] = merged_internal
        for key in ("diffusion_quality", "sector_diffusion_quality"):
            if key in data and key not in market_snapshot:
                market_snapshot[key] = data.get(key)
        if market_snapshot:
            data = dict(data)
            data["market_research_snapshot"] = market_snapshot
        min_trade_date = _recent_replay_min_trade_date(trade_date, data)
        if min_trade_date:
            structured_counts["recent_replay_min_trade_date"] = min_trade_date
        else:
            structured_counts["recent_replay_window_status"] = _recent_replay_window_status(trade_date, data)
        structured_counts["market_cycle"] = self.replace_market_cycle_context(
            trade_date,
            market_snapshot or data,
            min_trade_date=min_trade_date,
        )
        market_total = _market_daily_total_from_data(trade_date, data)
        if market_total:
            self.upsert_market_daily_total(market_total)
            structured_counts["market_daily_total"] = 1
        else:
            structured_counts["market_daily_total"] = 0
        index_daily_records = _index_daily_bar_records_from_data(trade_date, data)
        index_daily_count = 0
        for index_code, row in index_daily_records:
            index_daily_count += self.upsert_index_daily_bars(
                index_code,
                [row],
                source_policy=row.get("source_policy") or "daily_report_facts.index_daily",
            )
        structured_counts["index_daily_bars"] = index_daily_count
        monthly_ledger = _monthly_account_ledger_from_data(trade_date, data)
        if monthly_ledger:
            saved_monthly_ledger = self.upsert_monthly_account_ledger(monthly_ledger)
            structured_counts["monthly_account_ledger"] = 1 if saved_monthly_ledger else 0
        else:
            structured_counts["monthly_account_ledger"] = 0
        sector_flow_records = _sector_fund_flow_records_from_data(trade_date, data)
        for row in sector_flow_records:
            self.upsert_sector_fund_flow_daily(row)
        structured_counts["sector_fund_flow"] = len(sector_flow_records)
        pools = _observation_pools_from_data(data)
        structured_counts["observation_pools"] = self.replace_observation_pool_items_for_trade_date(trade_date, pools)
        tracking_state = _tracking_memory_state_from_data(data)
        if tracking_state:
            tracking_state["updated_at"] = trade_date
            structured_counts["tracking_memory"] = self.save_tracking_memory_state(tracking_state)
        decision = data.get("decision_ledger_artifacts") if isinstance(data.get("decision_ledger_artifacts"), dict) else {}
        decision_snapshot = decision.get("snapshot") if isinstance(decision.get("snapshot"), dict) else {}
        if decision_snapshot:
            structured_counts["decision_ledger"] = self.replace_decision_ledger_snapshot(decision_snapshot)
        candidate_trace = data.get("candidate_trace_artifact") if isinstance(data.get("candidate_trace_artifact"), dict) else {}
        if candidate_trace.get("traces"):
            structured_counts["candidate_trace"] = self.replace_candidate_trace_artifact(candidate_trace)
        elif isinstance(candidate_trace.get("payload"), dict) and candidate_trace["payload"].get("traces"):
            structured_counts["candidate_trace"] = self.replace_candidate_trace_artifact(candidate_trace["payload"])
        execution_context = data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {}
        factor_snapshot = _compact_execution_context(execution_context)
        if factor_snapshot:
            factor_snapshot["report_date"] = trade_date
            factor_snapshot["source_policy"] = "postgresql.daily_report_facts"
            structured_counts["factor_snapshot"] = self.save_factor_snapshot(trade_date, factor_snapshot, mode="frozen")
        fact_result = self.save_daily_report_snapshot(trade_date, data)
        if min_trade_date:
            structured_counts["pruned_old_replay_rows"] = self.prune_recent_replay_fact_tables(min_trade_date)
        fact_result["structured_counts"] = structured_counts
        return fact_result

    def load_daily_report_snapshot(self, trade_date):
        trade_date = _date_or_none(trade_date)
        columns = ("field_path", "value_text", "value_number", "value_bool", "value_kind")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT field_path, value_text, value_number, value_bool, value_kind
                    FROM daily_report_fact_fields
                    WHERE trade_date = %s
                    ORDER BY field_path ASC
                    """,
                    (trade_date,),
                )
                rows = cursor.fetchall()
        data = {}
        for row in rows or []:
            item = _row_dict(row, columns)
            _set_nested_fact_value(data, item.get("field_path"), _restore_typed_value(item))
        if isinstance(data, dict):
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    data = self._enrich_loaded_report_data_from_structured_tables(cursor, trade_date, data)
            monthly_context = data.get("monthly_context") if isinstance(data.get("monthly_context"), dict) else {}
            monthly_ledger = self.query_monthly_account_ledger(trade_date, account_id=monthly_context.get("account_id") or "main")
            if monthly_ledger:
                merged_monthly_context = dict(monthly_context or {})
                for key in (
                    "trade_date",
                    "account_id",
                    "month_key",
                    "month_return_pct",
                    "simulated_cumulative_return_pct",
                    "equity",
                    "cash",
                    "position_market_value",
                    "realized_pnl",
                    "unrealized_pnl",
                    "max_drawdown_pct",
                    "planned_trade_count",
                    "unplanned_trade_count",
                    "note",
                ):
                    if monthly_ledger.get(key) not in (None, ""):
                        merged_monthly_context[key] = monthly_ledger.get(key)
                merged_monthly_context["month_return_source"] = monthly_ledger.get("source_policy") or "monthly_account_ledger"
                data["monthly_context"] = merged_monthly_context
            data.setdefault("postgres_source", f"postgresql://daily-report-facts/{trade_date}")
            data.setdefault("postgres_only", True)
        return {
            "source": f"postgresql://daily-report-facts/{trade_date}",
            "field_count": len(rows or []),
            "data": data,
        }

    def load_daily_report_facts(self, trade_date):
        return self.load_daily_report_snapshot(trade_date)

    def _load_sector_attack_evidence_rows(self, cursor, trade_date):
        columns = (
            "trade_date",
            "sector_name",
            "net_inflow_rank",
            "net_inflow_amount_yi",
            "limit_up_count",
            "high_anchor_height",
            "sector_turnover_yi",
            "total_turnover_yi",
            "turnover_share_pct",
            "turnover_share_change",
            "source_policy",
            "source_run_id",
        )
        cursor.execute(
            """
            SELECT e.trade_date, e.sector_name, e.net_inflow_rank,
                   e.net_inflow_amount_yi, e.limit_up_count,
                   e.high_anchor_height, e.sector_turnover_yi,
                   COALESCE(NULLIF(e.total_turnover_yi, 0), m.total_amount_yi, 0) AS total_turnover_yi,
                   e.turnover_share_pct, e.turnover_share_change,
                   e.source_policy, e.source_run_id
            FROM sector_attack_evidence_daily e
            LEFT JOIN market_daily_totals m
              ON m.trade_date = e.trade_date
             AND m.market_scope = 'all_a'
            WHERE e.trade_date = %s
            ORDER BY e.turnover_share_pct DESC, e.net_inflow_amount_yi DESC, e.sector_name ASC
            """,
            (trade_date,),
        )
        rows = []
        for row in cursor.fetchall() or []:
            item = _row_dict(row, columns)
            sector_turnover = _safe_float(item.get("sector_turnover_yi"))
            total_turnover = _safe_float(item.get("total_turnover_yi"))
            share = _safe_float(item.get("turnover_share_pct"))
            if sector_turnover <= 0 and total_turnover > 0 and share > 0:
                sector_turnover = round(total_turnover * share / 100, 2)
            rows.append(
                {
                    "date": _text(item.get("trade_date")),
                    "sector_name": _text(item.get("sector_name")),
                    "net_inflow_rank": _safe_int(item.get("net_inflow_rank")),
                    "net_inflow_amount": _safe_float(item.get("net_inflow_amount_yi")),
                    "limit_up_count": _safe_int(item.get("limit_up_count")),
                    "high_anchor_height": _safe_int(item.get("high_anchor_height")),
                    "sector_turnover": sector_turnover,
                    "total_turnover": total_turnover,
                    "turnover_share_pct": share,
                    "turnover_share_change": _safe_float(item.get("turnover_share_change")),
                    "source": _text(item.get("source_policy")) or "sector_attack_evidence_daily",
                    "source_run_id": _safe_int(item.get("source_run_id")),
                }
            )
        return [row for row in rows if row.get("sector_name")]

    def _hot_sector_candidates_from_loaded_data(self, data, current_attack_rows, *, limit=8):
        candidates = []
        seen_alias_keys = set()

        def append(value):
            value = _text(value)
            alias_key = _hot_sector_alias_key(value)
            if (
                value
                and value not in {"-", "暂无", "无主线", "混沌轮动"}
                and alias_key not in seen_alias_keys
            ):
                candidates.append(value)
                seen_alias_keys.add(alias_key)

        for row in current_attack_rows or []:
            append((row or {}).get("sector_name"))
        current = data.get("current_sector_turnover_snapshot") if isinstance(data.get("current_sector_turnover_snapshot"), dict) else {}
        append(current.get("sector_name"))
        summary = data.get("mainline_turnover_summary") if isinstance(data.get("mainline_turnover_summary"), dict) else {}
        for row in reversed(list(summary.get("turnover_share_trend_rows") or [])):
            if isinstance(row, dict):
                append(row.get("cycle_mainline") or row.get("daily_attack_line"))
        for row in reversed(list(data.get("recent_sector_turnover_history") or [])):
            if isinstance(row, dict):
                append(row.get("sector_name") or row.get("cycle_mainline") or row.get("daily_attack_line"))
        for row in reversed(list(data.get("recent_mainline_history") or [])):
            if isinstance(row, dict):
                append(row.get("primary_mainline") or row.get("leading_line"))
        return candidates[: max(int(limit or 0), 1)]

    def _load_recent_hot_sector_turnover_history(self, cursor, trade_date, sector_names, *, window_days=25):
        sector_names = [_text(name) for name in sector_names or [] if _text(name)]
        if not sector_names:
            return []
        query_names = _hot_sector_query_names(sector_names)
        preferred_label_by_alias = {}
        for name in sector_names:
            alias_key = _hot_sector_alias_key(name)
            if alias_key:
                preferred_label_by_alias.setdefault(alias_key, alias_key)
        columns = (
            "trade_date",
            "sector_name",
            "sector_turnover_yi",
            "total_turnover_yi",
            "turnover_share_pct",
            "source_policy",
        )
        cursor.execute(
            """
            SELECT e.trade_date, e.sector_name, e.sector_turnover_yi,
                   COALESCE(NULLIF(e.total_turnover_yi, 0), m.total_amount_yi, 0) AS total_turnover_yi,
                   e.turnover_share_pct,
                   COALESCE(NULLIF(e.source_policy, ''), 'sector_attack_evidence_daily') AS source_policy
            FROM sector_attack_evidence_daily e
            LEFT JOIN market_daily_totals m
              ON m.trade_date = e.trade_date
             AND m.market_scope = 'all_a'
            WHERE e.trade_date <= %s
              AND e.trade_date >= (%s::date - (%s::int * INTERVAL '1 day'))
              AND e.sector_name = ANY(%s)
            UNION ALL
            SELECT t.trade_date, t.primary_mainline AS sector_name,
                   t.sector_turnover_yi, t.total_turnover_yi,
                   t.turnover_share_pct,
                   COALESCE(NULLIF(t.source_policy, ''), 'mainline_turnover_daily') AS source_policy
            FROM mainline_turnover_daily t
            WHERE t.trade_date <= %s
              AND t.trade_date >= (%s::date - (%s::int * INTERVAL '1 day'))
              AND t.primary_mainline = ANY(%s)
            ORDER BY trade_date ASC, sector_name ASC
            """,
            (
                trade_date,
                trade_date,
                max(_safe_int(window_days, 25), 1) * 3,
                query_names,
                trade_date,
                trade_date,
                max(_safe_int(window_days, 25), 1) * 3,
                query_names,
            ),
        )
        rows = []
        index_by_day_alias = {}
        for row in cursor.fetchall() or []:
            item = _row_dict(row, columns)
            sector_turnover = _safe_float(item.get("sector_turnover_yi"))
            total_turnover = _safe_float(item.get("total_turnover_yi"))
            share = _safe_float(item.get("turnover_share_pct"))
            if sector_turnover <= 0 and total_turnover > 0 and share > 0:
                sector_turnover = round(total_turnover * share / 100, 2)
            if sector_turnover <= 0 and share <= 0:
                continue
            date_text = _text(item.get("trade_date"))
            alias_key = _hot_sector_alias_key(item.get("sector_name"))
            output = {
                "date": date_text,
                "sector_name": preferred_label_by_alias.get(alias_key, _text(item.get("sector_name"))),
                "sector_turnover": sector_turnover,
                "total_turnover": total_turnover,
                "turnover_share_pct": share,
                "source": _text(item.get("source_policy")),
            }
            row_key = (date_text, alias_key)
            existing_index = index_by_day_alias.get(row_key)
            if existing_index is None:
                index_by_day_alias[row_key] = len(rows)
                rows.append(output)
                continue
            existing = rows[existing_index]
            if existing.get("sector_turnover", 0) <= 0 < output.get("sector_turnover", 0):
                rows[existing_index] = output
        return [row for row in rows if row.get("sector_name")][-max(_safe_int(window_days, 25) * len(sector_names), 1):]

    def _enrich_loaded_report_data_from_structured_tables(self, cursor, trade_date, data):
        if not isinstance(data, dict):
            return data
        current_attack_rows = self._load_sector_attack_evidence_rows(cursor, trade_date)
        if current_attack_rows:
            data["sector_attack_evidence_rows"] = current_attack_rows
        candidate_names = self._hot_sector_candidates_from_loaded_data(data, current_attack_rows)
        recent_hot_rows = self._load_recent_hot_sector_turnover_history(
            cursor,
            trade_date,
            candidate_names,
            window_days=25,
        )
        if recent_hot_rows:
            data["recent_hot_sector_turnover_history"] = recent_hot_rows
        candidate_trace_artifact = self.load_candidate_trace_artifact(trade_date)
        if candidate_trace_artifact.get("traces"):
            data["candidate_trace_artifact"] = candidate_trace_artifact
        return data

    def load_candidate_trace_artifact(self, trade_date):
        trade_date = _date_or_none(trade_date)
        meta_columns = (
            "trade_date",
            "artifact_version",
            "visible_scope",
            "generated_at",
            "source_report_path",
            "source_report_variant",
        )
        trace_columns = (
            "stock_code",
            "stock_name",
            "tier",
            "mainline",
            "sector_name",
            "final_action",
            "visible_summary",
            "trigger_condition",
            "failure_condition",
        )
        trace_field_columns = (
            "stock_code",
            "field_name",
            "value_text",
            "value_number",
            "value_bool",
            "value_kind",
        )
        eliminated_columns = ("reason", "count_value", "representatives_text", "treatment")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT trade_date, artifact_version, visible_scope, generated_at,
                           source_report_path, source_report_variant
                    FROM candidate_trace_artifacts
                    WHERE trade_date = %s
                    """,
                    (trade_date,),
                )
                meta_row = cursor.fetchone()
                if not meta_row:
                    return {}
                cursor.execute(
                    """
                    SELECT stock_code, stock_name, tier, mainline, sector_name,
                           final_action, visible_summary, trigger_condition, failure_condition
                    FROM candidate_trace_rows
                    WHERE trade_date = %s
                    ORDER BY tier ASC, stock_code ASC
                    """,
                    (trade_date,),
                )
                trace_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT stock_code, field_name, value_text, value_number, value_bool, value_kind
                    FROM candidate_trace_row_fields
                    WHERE trade_date = %s
                    ORDER BY stock_code ASC, field_name ASC
                    """,
                    (trade_date,),
                )
                trace_field_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT reason, count_value, representatives_text, treatment
                    FROM candidate_trace_eliminated_groups
                    WHERE trade_date = %s
                    ORDER BY reason ASC
                    """,
                    (trade_date,),
                )
                eliminated_rows = cursor.fetchall()
        meta = _row_dict(meta_row, meta_columns)
        trace_extra_fields = {}
        for row in trace_field_rows or []:
            item = _row_dict(row, trace_field_columns)
            code = _text(item.get("stock_code"))
            field_name = _text(item.get("field_name"))
            if not code or not field_name:
                continue
            extras = trace_extra_fields.setdefault(code, {})
            if "." in field_name or "[" in field_name:
                parts = _parse_structured_field_path(field_name)
                root_key = _text(parts[0]) if parts else ""
                if len(parts) > 1 and isinstance(parts[1], int) and not isinstance(extras.get(root_key), list):
                    extras[root_key] = []
                _set_nested_value(extras, field_name, _restore_typed_value(item))
            else:
                extras[field_name] = _restore_typed_value(item)
        return {
            "artifact_version": _safe_int(meta.get("artifact_version")),
            "trade_date": _text(meta.get("trade_date")),
            "visible_scope": _text(meta.get("visible_scope")),
            "generated_at": _text(meta.get("generated_at")),
            "source_report": {
                "path": _text(meta.get("source_report_path")),
                "variant": _text(meta.get("source_report_variant")),
            },
            "traces": [
                {
                    **trace_extra_fields.get(_text(item.get("stock_code")), {}),
                    "stock_code": _text(item.get("stock_code")),
                    "stock_name": _text(item.get("stock_name")),
                    "tier": _text(item.get("tier")),
                    "mainline": _text(item.get("mainline")),
                    "sector_name": _text(item.get("sector_name")),
                    "final_action": _text(item.get("final_action")),
                    "visible_summary": _text(item.get("visible_summary")),
                    "trigger_condition": _text(item.get("trigger_condition")),
                    "failure_condition": _text(item.get("failure_condition")),
                }
                for item in (_row_dict(row, trace_columns) for row in trace_rows or [])
            ],
            "eliminated_summary": [
                {
                    "reason": _text(item.get("reason")),
                    "count": _safe_int(item.get("count_value")),
                    "representatives": [
                        part for part in _text(item.get("representatives_text")).split("、") if part
                    ],
                    "treatment": _text(item.get("treatment")),
                }
                for item in (_row_dict(row, eliminated_columns) for row in eliminated_rows or [])
            ],
        }

    def replace_decision_ledger_snapshot(self, snapshot):
        snapshot = snapshot or {}
        trade_date = _date_or_none(snapshot.get("trade_date"))
        counts = {"cases": 0, "mentions": 0}
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM extreme_conviction_mentions WHERE mention_trade_date = %s", (trade_date,))
                for case in snapshot.get("cases") or []:
                    if not isinstance(case, dict):
                        continue
                    self._upsert_decision_case(cursor, trade_date, case)
                    counts["cases"] += 1
                    for mention in case.get("mentions") or []:
                        if not isinstance(mention, dict):
                            continue
                        self._upsert_decision_mention(cursor, case, mention)
                        counts["mentions"] += 1
                    self._upsert_case_review(cursor, case, "participation_review", "participation_reviews")
                    self._upsert_case_review(cursor, case, "trend_fate", "trend_fates")
                    self._upsert_case_review(cursor, case, "cycle_acceptance", "cycle_acceptance_reviews")
            conn.commit()
        return counts

    def _normalize_extreme_conviction_mention(self, row):
        row = row or {}
        mention_date = _date_or_none(row.get("mention_trade_date") or row.get("trade_date") or row.get("date"))
        stock_code = _stock_code(row)
        record_id = _text(row.get("record_id")) or f"{mention_date}:{stock_code}"
        return {
            "record_id": record_id,
            "case_id": _text(row.get("case_id")),
            "mention_trade_date": mention_date,
            "stock_code": stock_code,
            "stock_name": _stock_name(row),
            "rank_no": _safe_int(row.get("rank_no") or row.get("rank")),
            "sector_candidate": _text(row.get("sector_candidate") or row.get("sector")),
            "buy_window": _text(row.get("buy_window")),
            "planned_window": _text(row.get("planned_window") or row.get("participation_window")),
            "review_status": _text(row.get("review_status")),
            "next_action": _text(row.get("next_action")),
            "invalidation": _text(row.get("invalidation")),
            "reason": _text(row.get("reason")),
            "source_section": _text(row.get("source_section")),
            "is_a_kill_eliminated": bool(row.get("is_a_kill_eliminated")),
        }

    def upsert_extreme_conviction_mentions(self, rows):
        normalized = []
        for row in rows or []:
            item = self._normalize_extreme_conviction_mention(row)
            if not item["record_id"] or not item["mention_trade_date"] or not item["stock_code"]:
                continue
            normalized.append(item)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if normalized:
                    cursor.executemany(
                        """
                        INSERT INTO extreme_conviction_mentions(
                            record_id, case_id, mention_trade_date, stock_code,
                            stock_name, rank_no, sector_candidate, buy_window,
                            planned_window, review_status, next_action,
                            invalidation, reason, source_section,
                            is_a_kill_eliminated
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (record_id) DO UPDATE SET
                            case_id=EXCLUDED.case_id,
                            mention_trade_date=EXCLUDED.mention_trade_date,
                            stock_code=EXCLUDED.stock_code,
                            stock_name=EXCLUDED.stock_name,
                            rank_no=EXCLUDED.rank_no,
                            sector_candidate=EXCLUDED.sector_candidate,
                            buy_window=EXCLUDED.buy_window,
                            planned_window=EXCLUDED.planned_window,
                            review_status=EXCLUDED.review_status,
                            next_action=EXCLUDED.next_action,
                            invalidation=EXCLUDED.invalidation,
                            reason=EXCLUDED.reason,
                            source_section=EXCLUDED.source_section,
                            is_a_kill_eliminated=EXCLUDED.is_a_kill_eliminated,
                            updated_at=now()
                        """,
                        [
                            (
                                item["record_id"],
                                item["case_id"],
                                item["mention_trade_date"],
                                item["stock_code"],
                                item["stock_name"],
                                item["rank_no"],
                                item["sector_candidate"],
                                item["buy_window"],
                                item["planned_window"],
                                item["review_status"],
                                item["next_action"],
                                item["invalidation"],
                                item["reason"],
                                item["source_section"],
                                item["is_a_kill_eliminated"],
                            )
                            for item in normalized
                        ],
                    )
            conn.commit()
        return len(normalized)

    def replace_extreme_conviction_mentions_for_trade_date(self, trade_date, rows):
        trade_date = _date_or_none(trade_date)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM extreme_conviction_mentions WHERE mention_trade_date = %s",
                    (trade_date,),
                )
            conn.commit()
        return self.upsert_extreme_conviction_mentions(rows)

    def _query_recent_extreme_conviction_dates(self, cursor, end_date, *, window_days=25):
        cursor.execute(
            """
            SELECT DISTINCT mention_trade_date
            FROM extreme_conviction_mentions
            WHERE mention_trade_date <= %s
            ORDER BY mention_trade_date DESC
            LIMIT %s
            """,
            (_date_or_none(end_date), max(_safe_int(window_days, 25), 1)),
        )
        date_rows = cursor.fetchall()
        return [
            _text(_row_dict(row, ("mention_trade_date",)).get("mention_trade_date"))
            for row in reversed(date_rows or [])
            if _text(_row_dict(row, ("mention_trade_date",)).get("mention_trade_date"))
        ]

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        columns = (
            "record_id",
            "mention_trade_date",
            "stock_code",
            "stock_name",
            "rank_no",
            "sector_candidate",
            "buy_window",
            "planned_window",
            "review_status",
            "next_action",
            "invalidation",
            "reason",
            "source_section",
            "is_a_kill_eliminated",
            "updated_at",
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                dates = self._query_recent_extreme_conviction_dates(cursor, end_date, window_days=window_days)
                if not dates:
                    return []
                query = """
                    SELECT record_id, mention_trade_date, stock_code, stock_name,
                           rank_no, sector_candidate, buy_window, planned_window,
                           review_status, next_action, invalidation, reason,
                           source_section, is_a_kill_eliminated, updated_at
                    FROM extreme_conviction_mentions
                    WHERE mention_trade_date = ANY(%s)
                """
                params = [dates]
                if not include_a_kill:
                    query += " AND is_a_kill_eliminated = false"
                query += " ORDER BY mention_trade_date ASC, rank_no ASC, stock_code ASC"
                cursor.execute(query, params)
                rows = cursor.fetchall()
        result = []
        for row in rows or []:
            item = _row_dict(row, columns)
            item["mention_trade_date"] = _text(item.get("mention_trade_date"))
            item["rank"] = _safe_int(item.get("rank_no"))
            item["is_a_kill_eliminated"] = bool(item.get("is_a_kill_eliminated"))
            item["payload"] = {
                "record_id": _text(item.get("record_id")),
                "mention_trade_date": item["mention_trade_date"],
                "stock_code": _text(item.get("stock_code")),
                "stock_name": _text(item.get("stock_name")),
                "rank_no": _safe_int(item.get("rank_no")),
                "sector_candidate": _text(item.get("sector_candidate")),
                "buy_window": _text(item.get("buy_window")),
                "planned_window": _text(item.get("planned_window")),
                "review_status": _text(item.get("review_status")),
                "next_action": _text(item.get("next_action")),
                "invalidation": _text(item.get("invalidation")),
                "reason": _text(item.get("reason")),
                "source_section": _text(item.get("source_section")),
                "is_a_kill_eliminated": item["is_a_kill_eliminated"],
            }
            result.append(item)
        return result

    def mark_a_kill_shape_extreme_conviction_mentions(self, end_date, *, window_days=25, return_details=False):
        if return_details:
            return {"updated_count": 0, "updated_records": []}
        return 0

    def read_decision_ledger_index(self, end_date=None, window_days=25):
        case_columns = (
            "case_id",
            "trade_date",
            "stock_code",
            "stock_name",
            "first_seen_trade_date",
            "cycle_start_trade_date",
            "cycle_day",
            "cycle_length_trade_days",
            "sector_candidate",
            "stock_setup",
        )
        mention_columns = (
            "record_id",
            "case_id",
            "mention_trade_date",
            "stock_code",
            "stock_name",
            "rank_no",
            "sector_candidate",
            "buy_window",
            "planned_window",
            "review_status",
            "next_action",
            "invalidation",
            "reason",
            "source_section",
            "is_a_kill_eliminated",
        )
        hypothesis_columns = (
            "case_id",
            "sector_candidate",
            "stock_setup",
            "market_branch",
            "sector_relationship_state",
        )
        participation_columns = (
            "record_id",
            "case_id",
            "participation_window",
            "attack_state",
            "source_tier",
            "entry_timing",
            "buy_window",
            "missed_action",
            "cancellation",
        )
        step_columns = ("record_id", "step_key", "step_text")
        participation_review_columns = (
            "record_id",
            "case_id",
            "review_trade_date",
            "status",
            "reason",
            "evidence",
            "next_action",
        )
        review_columns = ("case_id", "status", "reason", "evidence")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                dates = self._query_recent_extreme_conviction_dates(
                    cursor,
                    end_date or _dt.date.today().isoformat(),
                    window_days=window_days,
                )
                if not dates:
                    return {}
                cursor.execute(
                    """
                    SELECT case_id, trade_date, stock_code, stock_name,
                           first_seen_trade_date, cycle_start_trade_date,
                           cycle_day, cycle_length_trade_days, sector_candidate,
                           stock_setup
                    FROM extreme_conviction_cases
                    WHERE trade_date = ANY(%s)
                    ORDER BY trade_date ASC, stock_code ASC
                    """,
                    (dates,),
                )
                case_rows = [_row_dict(row, case_columns) for row in cursor.fetchall()]
                case_ids = [_text(row.get("case_id")) for row in case_rows if _text(row.get("case_id"))]
                if not case_ids:
                    return {}
                cursor.execute(
                    """
                    SELECT record_id, case_id, mention_trade_date, stock_code,
                           stock_name, rank_no, sector_candidate, buy_window,
                           planned_window, review_status, next_action,
                           invalidation, reason, source_section,
                           is_a_kill_eliminated
                    FROM extreme_conviction_mentions
                    WHERE case_id = ANY(%s)
                    ORDER BY mention_trade_date ASC, rank_no ASC, stock_code ASC
                    """,
                    (case_ids,),
                )
                mention_rows = [_row_dict(row, mention_columns) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT case_id, sector_candidate, stock_setup, market_branch,
                           sector_relationship_state
                    FROM extreme_conviction_hypotheses
                    WHERE case_id = ANY(%s)
                    """,
                    (case_ids,),
                )
                hypothesis_rows = [_row_dict(row, hypothesis_columns) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT record_id, case_id, participation_window, attack_state,
                           source_tier, entry_timing, buy_window, missed_action,
                           cancellation
                    FROM planned_participations
                    WHERE case_id = ANY(%s)
                    """,
                    (case_ids,),
                )
                participation_rows = [_row_dict(row, participation_columns) for row in cursor.fetchall()]
                record_ids = [
                    _text(row.get("record_id"))
                    for row in participation_rows + mention_rows
                    if _text(row.get("record_id"))
                ]
                step_rows = []
                if record_ids:
                    cursor.execute(
                        """
                        SELECT record_id, step_key, step_text
                        FROM planned_participation_steps
                        WHERE record_id = ANY(%s)
                        ORDER BY record_id ASC, step_key ASC
                        """,
                        (record_ids,),
                    )
                    step_rows = [_row_dict(row, step_columns) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT record_id, case_id, review_trade_date, status, reason,
                           evidence, next_action
                    FROM participation_reviews
                    WHERE case_id = ANY(%s)
                    """,
                    (case_ids,),
                )
                participation_review_rows = [
                    _row_dict(row, participation_review_columns)
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT case_id, status, reason, evidence
                    FROM trend_fates
                    WHERE case_id = ANY(%s)
                    """,
                    (case_ids,),
                )
                trend_rows = [_row_dict(row, review_columns) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT case_id, status, reason, evidence
                    FROM cycle_acceptance_reviews
                    WHERE case_id = ANY(%s)
                    """,
                    (case_ids,),
                )
                cycle_rows = [_row_dict(row, review_columns) for row in cursor.fetchall()]

        return self._build_decision_ledger_index_from_rows(
            dates,
            case_rows,
            mention_rows,
            hypothesis_rows,
            participation_rows,
            step_rows,
            participation_review_rows,
            trend_rows,
            cycle_rows,
        )

    def _build_decision_ledger_index_from_rows(
        self,
        dates,
        case_rows,
        mention_rows,
        hypothesis_rows,
        participation_rows,
        step_rows,
        participation_review_rows,
        trend_rows,
        cycle_rows,
    ):
        hypotheses_by_case = {_text(row.get("case_id")): row for row in hypothesis_rows or []}
        participations_by_record = {_text(row.get("record_id")): row for row in participation_rows or []}
        steps_by_record = {}
        for row in step_rows or []:
            record_id = _text(row.get("record_id"))
            step_key = _text(row.get("step_key"))
            if not record_id or not step_key:
                continue
            steps_by_record.setdefault(record_id, {})[step_key] = _text(row.get("step_text"))
        participation_reviews_by_case = {
            _text(row.get("case_id")): row for row in participation_review_rows or []
        }
        trend_by_case = {_text(row.get("case_id")): row for row in trend_rows or []}
        cycle_by_case = {_text(row.get("case_id")): row for row in cycle_rows or []}
        mentions_by_case = {}
        for row in mention_rows or []:
            case_id = _text(row.get("case_id"))
            record_id = _text(row.get("record_id"))
            planned = self._planned_participation_from_rows(
                participations_by_record.get(record_id),
                steps_by_record.get(record_id),
            )
            mention = {
                "record_id": record_id,
                "mention_trade_date": _text(row.get("mention_trade_date")),
                "rank": _safe_int(row.get("rank_no")),
                "source_section": _text(row.get("source_section")),
                "reason": _text(row.get("reason")),
                "planned_participation": planned,
                "is_a_kill_eliminated": bool(row.get("is_a_kill_eliminated")),
            }
            if row.get("review_status") or row.get("next_action"):
                mention["participation_review"] = {
                    "status": _text(row.get("review_status")),
                    "next_action": _text(row.get("next_action")),
                    "reason": _text(row.get("reason")),
                }
            mentions_by_case.setdefault(case_id, []).append(mention)

        by_stock_code = {}
        for row in case_rows or []:
            case_id = _text(row.get("case_id"))
            stock_code = _text(row.get("stock_code"))
            if not case_id or not stock_code:
                continue
            hypothesis = self._hypothesis_from_rows(row, hypotheses_by_case.get(case_id))
            mentions = mentions_by_case.get(case_id) or []
            latest_mention = mentions[-1] if mentions else {}
            planned = latest_mention.get("planned_participation") or {}
            record = {
                "case_id": case_id,
                "stock_code": stock_code,
                "stock_name": _text(row.get("stock_name")),
                "first_seen_trade_date": _text(row.get("first_seen_trade_date")),
                "cycle_start_trade_date": _text(row.get("cycle_start_trade_date")),
                "cycle_day": _safe_int(row.get("cycle_day")),
                "cycle_length_trade_days": _safe_int(row.get("cycle_length_trade_days"), 25),
                "latest_trade_date": _text(row.get("trade_date")),
                "cycle_closed": _text((cycle_by_case.get(case_id) or {}).get("status")) == "closed",
                "mentions": mentions,
                "planned_participation": planned,
                "hypothesis": hypothesis,
            }
            participation_review = participation_reviews_by_case.get(case_id)
            if participation_review:
                record["participation_review_status"] = _text(participation_review.get("status"))
                record["participation_review"] = {
                    "status": _text(participation_review.get("status")),
                    "review_trade_date": _text(participation_review.get("review_trade_date")),
                    "reason": _text(participation_review.get("reason")),
                    "evidence": _text(participation_review.get("evidence")),
                    "next_action": _text(participation_review.get("next_action")),
                }
            trend = trend_by_case.get(case_id)
            if trend:
                record["trend_fate"] = self._review_from_row(trend)
            cycle = cycle_by_case.get(case_id)
            if cycle:
                record["cycle_acceptance"] = self._review_from_row(cycle)
            by_stock_code.setdefault(stock_code, []).append(record)

        return {
            "artifact_version": 1,
            "latest_trade_date": max(dates) if dates else "",
            "selection_rule_version": "extreme-conviction-ledger-v1",
            "available_trade_dates": sorted(dates or []),
            "snapshots": [
                {
                    "trade_date": date,
                    "path": f"data/decision-ledger/{date}.json",
                    "case_count": sum(1 for row in case_rows or [] if _text(row.get("trade_date")) == date),
                }
                for date in sorted(dates or [])
            ],
            "selection_input_hash_by_trade_date": {},
            "by_stock_code": by_stock_code,
        }

    def _hypothesis_from_rows(self, case_row, hypothesis_row):
        hypothesis_row = hypothesis_row or {}
        return {
            "sector_candidate": _text(hypothesis_row.get("sector_candidate") or case_row.get("sector_candidate")),
            "stock_setup": _text(hypothesis_row.get("stock_setup") or case_row.get("stock_setup")),
            "market_branch": _text(hypothesis_row.get("market_branch")),
            "sector_relationship_state": _text(hypothesis_row.get("sector_relationship_state")),
        }

    def _planned_participation_from_rows(self, participation_row, step_map):
        participation_row = participation_row or {}
        planned = {
            "participation_window": _text(participation_row.get("participation_window")),
            "attack_state": _text(participation_row.get("attack_state")),
            "source_tier": _text(participation_row.get("source_tier")),
            "entry_timing": _text(participation_row.get("entry_timing")),
            "buy_window": _text(participation_row.get("buy_window")),
            "missed_action": _text(participation_row.get("missed_action")),
            "cancellation": _text(participation_row.get("cancellation")),
        }
        for key, value in (step_map or {}).items():
            if _text(value):
                planned[key] = _text(value)
        return {key: value for key, value in planned.items() if value}

    def _review_from_row(self, row):
        row = row or {}
        return {
            "status": _text(row.get("status")),
            "reason": _text(row.get("reason")),
            "evidence": _text(row.get("evidence")),
        }

    def _upsert_decision_case(self, cursor, trade_date, case):
        hypothesis = case.get("hypothesis") if isinstance(case.get("hypothesis"), dict) else {}
        cursor.execute(
            """
            INSERT INTO extreme_conviction_cases(
                case_id, trade_date, stock_code, stock_name, first_seen_trade_date,
                cycle_start_trade_date, cycle_day, cycle_length_trade_days,
                sector_candidate, stock_setup
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (case_id) DO UPDATE SET
                trade_date=EXCLUDED.trade_date,
                stock_code=EXCLUDED.stock_code,
                stock_name=EXCLUDED.stock_name,
                first_seen_trade_date=EXCLUDED.first_seen_trade_date,
                cycle_start_trade_date=EXCLUDED.cycle_start_trade_date,
                cycle_day=EXCLUDED.cycle_day,
                cycle_length_trade_days=EXCLUDED.cycle_length_trade_days,
                sector_candidate=EXCLUDED.sector_candidate,
                stock_setup=EXCLUDED.stock_setup,
                updated_at=now()
            """,
            (
                _text(case.get("case_id")),
                trade_date,
                _stock_code(case),
                _stock_name(case),
                _date_or_none(case.get("first_seen_trade_date")),
                _date_or_none(case.get("cycle_start_trade_date")),
                _safe_int(case.get("cycle_day")),
                _safe_int(case.get("cycle_length_trade_days")),
                _text(hypothesis.get("sector_candidate") or case.get("sector_candidate") or case.get("sector")),
                _text(hypothesis.get("stock_setup") or case.get("stock_setup")),
            ),
        )
        cursor.execute(
            """
            INSERT INTO extreme_conviction_hypotheses(
                case_id, sector_candidate, stock_setup, market_branch,
                sector_relationship_state
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (case_id) DO UPDATE SET
                sector_candidate=EXCLUDED.sector_candidate,
                stock_setup=EXCLUDED.stock_setup,
                market_branch=EXCLUDED.market_branch,
                sector_relationship_state=EXCLUDED.sector_relationship_state,
                updated_at=now()
            """,
            (
                _text(case.get("case_id")),
                _text(hypothesis.get("sector_candidate")),
                _text(hypothesis.get("stock_setup")),
                _text(hypothesis.get("market_branch")),
                _text(hypothesis.get("sector_relationship_state")),
            ),
        )

    def _upsert_decision_mention(self, cursor, case, mention):
        record_id = _record_id(case, mention)
        planned = mention.get("planned_participation")
        if not isinstance(planned, dict):
            planned = case.get("planned_participation") if isinstance(case.get("planned_participation"), dict) else {}
        cursor.execute(
            """
            INSERT INTO extreme_conviction_mentions(
                record_id, case_id, mention_trade_date, stock_code, stock_name,
                rank_no, sector_candidate, buy_window, planned_window,
                review_status, next_action, invalidation, reason, source_section,
                is_a_kill_eliminated
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (record_id) DO UPDATE SET
                case_id=EXCLUDED.case_id,
                mention_trade_date=EXCLUDED.mention_trade_date,
                stock_code=EXCLUDED.stock_code,
                stock_name=EXCLUDED.stock_name,
                rank_no=EXCLUDED.rank_no,
                sector_candidate=EXCLUDED.sector_candidate,
                buy_window=EXCLUDED.buy_window,
                planned_window=EXCLUDED.planned_window,
                review_status=EXCLUDED.review_status,
                next_action=EXCLUDED.next_action,
                invalidation=EXCLUDED.invalidation,
                reason=EXCLUDED.reason,
                source_section=EXCLUDED.source_section,
                is_a_kill_eliminated=EXCLUDED.is_a_kill_eliminated,
                updated_at=now()
            """,
            (
                record_id,
                _text(case.get("case_id")),
                _date_or_none(mention.get("mention_trade_date")),
                _stock_code(case),
                _stock_name(case),
                _safe_int(mention.get("rank") or mention.get("rank_no")),
                _text((case.get("hypothesis") or {}).get("sector_candidate") or case.get("sector_candidate")),
                _text(planned.get("buy_window")),
                _text(planned.get("participation_window")),
                _text((case.get("participation_review") or {}).get("status") or mention.get("review_status")),
                _text(mention.get("next_action")),
                _text(planned.get("cancellation") or mention.get("invalidation")),
                _text(mention.get("reason")),
                _text(mention.get("source_section")),
                bool(mention.get("is_a_kill_eliminated")),
            ),
        )
        self._upsert_planned_participation(cursor, record_id, case, planned)

    def _upsert_planned_participation(self, cursor, record_id, case, planned):
        cursor.execute(
            """
            INSERT INTO planned_participations(
                record_id, case_id, participation_window, attack_state,
                source_tier, entry_timing, buy_window, missed_action, cancellation
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (record_id) DO UPDATE SET
                case_id=EXCLUDED.case_id,
                participation_window=EXCLUDED.participation_window,
                attack_state=EXCLUDED.attack_state,
                source_tier=EXCLUDED.source_tier,
                entry_timing=EXCLUDED.entry_timing,
                buy_window=EXCLUDED.buy_window,
                missed_action=EXCLUDED.missed_action,
                cancellation=EXCLUDED.cancellation,
                updated_at=now()
            """,
            (
                record_id,
                _text(case.get("case_id")),
                _text(planned.get("participation_window")),
                _text(planned.get("attack_state")),
                _text(planned.get("source_tier")),
                _text(planned.get("entry_timing")),
                _text(planned.get("buy_window")),
                _text(planned.get("missed_action")),
                _text(planned.get("cancellation")),
            ),
        )
        step_rows = [
            (record_id, key, _text(planned.get(key)))
            for key in ("auction", "first_minutes", "board", "reseal", "missed_action", "cancellation")
            if _text(planned.get(key))
        ]
        if step_rows:
            cursor.executemany(
                """
                INSERT INTO planned_participation_steps(record_id, step_key, step_text)
                VALUES (%s, %s, %s)
                ON CONFLICT (record_id, step_key) DO UPDATE SET
                    step_text=EXCLUDED.step_text,
                    updated_at=now()
                """,
                step_rows,
            )

    def _upsert_case_review(self, cursor, case, key, table_name):
        review = case.get(key)
        if not isinstance(review, dict):
            return
        if table_name == "participation_reviews":
            cursor.execute(
                """
                INSERT INTO participation_reviews(
                    record_id, case_id, review_trade_date, status, reason,
                    evidence, next_action
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO UPDATE SET
                    case_id=EXCLUDED.case_id,
                    review_trade_date=EXCLUDED.review_trade_date,
                    status=EXCLUDED.status,
                    reason=EXCLUDED.reason,
                    evidence=EXCLUDED.evidence,
                    next_action=EXCLUDED.next_action,
                    updated_at=now()
                """,
                (
                    _text(case.get("case_id")),
                    _text(case.get("case_id")),
                    _date_or_none(review.get("review_trade_date")),
                    _text(review.get("status")),
                    _text(review.get("reason")),
                    _text(review.get("evidence")),
                    _text(review.get("next_action")),
                ),
            )
            return
        cursor.execute(
            f"""
            INSERT INTO {table_name}(case_id, status, reason, evidence)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (case_id) DO UPDATE SET
                status=EXCLUDED.status,
                reason=EXCLUDED.reason,
                evidence=EXCLUDED.evidence,
                updated_at=now()
            """,
            (
                _text(case.get("case_id")),
                _text(review.get("status")),
                _text(review.get("reason")),
                _text(review.get("evidence")),
            ),
        )


def _date_from_short(anchor_date, short_date):
    anchor = _date_or_none(anchor_date)
    short = _text(short_date)
    if len(short) == 5 and short[2] == "-" and anchor:
        return f"{anchor[:4]}-{short}"
    return _date_or_none(short) or anchor
