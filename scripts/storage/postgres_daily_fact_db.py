from __future__ import annotations

import datetime as _dt
import importlib
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
        turnover_share_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
        turnover_share_change DOUBLE PRECISION NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (trade_date, sector_name)
    )
    """,
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
]

_WEEKDAY_FIELDS = ("monday", "tuesday", "wednesday", "thursday", "friday")


def _text(value):
    return str(value or "").strip()


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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

    def replace_market_cycle_context(self, trade_date, snapshot):
        trade_date = _date_or_none(trade_date)
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
                self._replace_market_cycle_days(cursor, trade_date, snapshot, counts)
                self._replace_market_cycle_periods(cursor, trade_date, snapshot, counts)
                self._replace_mainline_records(cursor, trade_date, snapshot, counts)
                self._replace_turnover_records(cursor, trade_date, snapshot, counts)
                self._replace_sector_attack_records(cursor, trade_date, snapshot, counts)
                self._replace_sector_diffusion_records(cursor, trade_date, snapshot, counts)
                self._replace_sector_competition_records(cursor, trade_date, snapshot, counts)
                self._replace_market_capacity_evolution_record(cursor, trade_date, snapshot, counts)
                self._replace_pivot_records(cursor, trade_date, snapshot, counts)
            conn.commit()
        return counts

    def _replace_market_cycle_days(self, cursor, trade_date, snapshot, counts):
        cursor.execute("DELETE FROM market_cycle_days WHERE trade_date = %s", (trade_date,))
        rows = []
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

    def _replace_mainline_records(self, cursor, trade_date, snapshot, counts):
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

    def _replace_turnover_records(self, cursor, trade_date, snapshot, counts):
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
        cursor.execute("DELETE FROM sector_attack_evidence_daily WHERE trade_date = %s", (trade_date,))
        rows = []
        for row in snapshot.get("sector_attack_evidence_rows") or []:
            if not isinstance(row, dict):
                continue
            sector = _sector_name(row)
            if not sector:
                continue
            rows.append(
                (
                    trade_date,
                    sector,
                    _safe_int(row.get("net_inflow_rank")),
                    _safe_float(row.get("net_inflow_amount")),
                    _safe_int(row.get("limit_up_count")),
                    _safe_int(row.get("high_anchor_height")),
                    _safe_float(row.get("turnover_share_pct")),
                    _safe_float(row.get("turnover_share_change")),
                )
            )
        if rows:
            cursor.executemany(
                """
                INSERT INTO sector_attack_evidence_daily(
                    trade_date, sector_name, net_inflow_rank, net_inflow_amount_yi,
                    limit_up_count, high_anchor_height, turnover_share_pct,
                    turnover_share_change
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date, sector_name) DO UPDATE SET
                    net_inflow_rank=EXCLUDED.net_inflow_rank,
                    net_inflow_amount_yi=EXCLUDED.net_inflow_amount_yi,
                    limit_up_count=EXCLUDED.limit_up_count,
                    high_anchor_height=EXCLUDED.high_anchor_height,
                    turnover_share_pct=EXCLUDED.turnover_share_pct,
                    turnover_share_change=EXCLUDED.turnover_share_change,
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
            trace_extra_fields.setdefault(code, {})[field_name] = _restore_typed_value(item)
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
