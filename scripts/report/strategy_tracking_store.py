from __future__ import annotations

import os

from daily_report_snapshot_io import _make_serializable

try:
    from storage.database_service import DatabaseService
except Exception:  # pragma: no cover - optional runtime path
    DatabaseService = None

__all__ = [
    "get_factor_snapshot_path",
    "get_strategy_performance_path",
    "load_strategy_performance_ledger",
    "save_factor_snapshot",
    "save_strategy_performance_ledger",
]

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


def _postgres_database_configured():
    database_url = (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    return database_url.startswith(("postgres://", "postgresql://"))


def _configured_postgres_service():
    service_cls = globals().get("DatabaseService")
    if not _postgres_database_configured():
        return None
    if service_cls is None:
        raise RuntimeError("PostgreSQL strategy tracking storage is configured but DatabaseService is unavailable")
    service = service_cls.from_environment()
    checker = getattr(service, "is_postgres_backed", None)
    if not callable(checker) or not checker():
        raise RuntimeError("PostgreSQL strategy tracking storage is configured but DatabaseService did not select PostgreSQL")
    return service


def load_strategy_performance_ledger(*, mode="frozen", helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        service = _configured_postgres_service()
        if service is not None:
            reader = getattr(service, "load_strategy_performance_ledger", None)
            if callable(reader):
                result = reader(mode=mode)
                if isinstance(result, dict):
                    return result
            raise RuntimeError("PostgreSQL strategy performance ledger reader is unavailable")
        return _load_strategy_performance_ledger_legacy_body(mode=mode)
    finally:
        _restore_runtime_bindings(previous)


def save_strategy_performance_ledger(ledger, *, mode="frozen", helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        service = _configured_postgres_service()
        if service is not None:
            writer = getattr(service, "save_strategy_performance_ledger", None)
            if callable(writer):
                return writer(ledger, mode=mode)
            raise RuntimeError("PostgreSQL strategy performance ledger writer is unavailable")
        return _save_strategy_performance_ledger_legacy_body(ledger, mode=mode)
    finally:
        _restore_runtime_bindings(previous)


def save_factor_snapshot(target_date, factor_snapshot, *, mode="frozen", helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        service = _configured_postgres_service()
        if service is not None:
            writer = getattr(service, "save_factor_snapshot", None)
            if callable(writer):
                return writer(target_date, factor_snapshot, mode=mode)
            raise RuntimeError("PostgreSQL strategy factor snapshot writer is unavailable")
        return _save_factor_snapshot_legacy_body(target_date, factor_snapshot, mode=mode)
    finally:
        _restore_runtime_bindings(previous)


def get_strategy_performance_path(*, mode="frozen", helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_strategy_performance_path_legacy_body(mode=mode)
    finally:
        _restore_runtime_bindings(previous)


def get_factor_snapshot_path(target_date, *, mode="frozen", helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_factor_snapshot_path_legacy_body(target_date, mode=mode)
    finally:
        _restore_runtime_bindings(previous)


def _get_strategy_performance_path(mode="frozen"):
    return _get_strategy_performance_path_legacy_body(mode=mode)


def _get_factor_snapshot_path(target_date, mode="frozen"):
    return _get_factor_snapshot_path_legacy_body(target_date, mode=mode)


def _load_strategy_performance_ledger_legacy_body(*, mode="frozen"):
    import json

    path = _get_strategy_performance_path(mode=mode)
    default_data = {
        'version': STRATEGY_PERFORMANCE_LEDGER_VERSION,
        'updated_at': '',
        'mode': mode,
        'records': [],
    }
    if not os.path.exists(path):
        return default_data

    try:
        with open(path, 'r', encoding='utf-8') as file_obj:
            data = json.load(file_obj)
        if not isinstance(data, dict):
            return default_data
        data.setdefault('version', STRATEGY_PERFORMANCE_LEDGER_VERSION)
        data.setdefault('updated_at', '')
        data.setdefault('mode', mode)
        data.setdefault('records', [])
        if not isinstance(data.get('records'), list):
            data['records'] = []
        return data
    except Exception as error:
        print(f"⚠️ 策略绩效账本读取失败，重置为空: {error}")
        return default_data


def _save_strategy_performance_ledger_legacy_body(ledger, *, mode="frozen"):
    import datetime as _dt
    import json

    path = _get_strategy_performance_path(mode=mode)
    ledger = dict(ledger or {})
    ledger['version'] = STRATEGY_PERFORMANCE_LEDGER_VERSION
    ledger['updated_at'] = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ledger['mode'] = mode
    ledger.setdefault('records', [])
    with open(path, 'w', encoding='utf-8') as file_obj:
        json.dump(ledger, file_obj, ensure_ascii=False, indent=2)
    return path


def _save_factor_snapshot_legacy_body(target_date, factor_snapshot, *, mode="frozen"):
    import datetime as _dt
    import json

    snapshot = dict(factor_snapshot or {})
    if not snapshot:
        return {
            'path': '',
            'mode': mode,
            'saved': False,
        }

    snapshot.setdefault('report_date', target_date)
    snapshot_path = _get_factor_snapshot_path(target_date, mode=mode)
    payload = {
        'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
        'mode': mode,
        'saved_at': _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'snapshot': _make_serializable(snapshot),
    }

    if mode == LEDGER_MODE_FROZEN and os.path.exists(snapshot_path):
        return {
            'path': snapshot_path,
            'mode': mode,
            'saved': False,
            'frozen': True,
            'saved_at': payload['saved_at'],
            'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
        }

    with open(snapshot_path, 'w', encoding='utf-8') as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
    return {
        'path': snapshot_path,
        'mode': mode,
        'saved': True,
        'saved_at': payload['saved_at'],
        'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
    }


def _get_strategy_performance_path_legacy_body(*, mode="frozen"):
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    if mode == LEDGER_MODE_REPLAY:
        return os.path.join(data_dir, "strategy_performance_replay.json")
    return os.path.join(data_dir, "strategy_performance.json")


def _get_factor_snapshot_path_legacy_body(target_date, *, mode="frozen"):
    factor_dir = os.path.join(os.path.dirname(__file__), "..", "data", "factor_snapshots")
    if mode == LEDGER_MODE_REPLAY:
        factor_dir = os.path.join(factor_dir, "replay")
    os.makedirs(factor_dir, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    return os.path.join(factor_dir, f"{target_date}{suffix}.json")
