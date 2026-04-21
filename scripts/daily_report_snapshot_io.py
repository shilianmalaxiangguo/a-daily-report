#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Snapshot IO helpers for a-daily-report.

This module centralizes the snapshot persistence contract used by the report
entry script and the review workflow.

Layout:
- snapshots/<date>.json           official/frozen snapshot
- snapshots/replay/<date>_replay.json  replay snapshot when frozen data already exists
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import types
from enum import Enum
from pathlib import Path
from typing import Any, Tuple

LEDGER_MODE_FROZEN = "frozen"
LEDGER_MODE_REPLAY = "replay"

__all__ = [
    "LEDGER_MODE_FROZEN",
    "LEDGER_MODE_REPLAY",
    "_make_serializable",
    "_get_snapshot_path",
    "_save_data_snapshot",
    "load_data_snapshot",
    "add_supplementary_perspective",
    "save_data_snapshot",
]


def _module_dir() -> Path:
    return Path(__file__).parent


def _snapshot_root() -> Path:
    return _module_dir().parent / "snapshots"


def _get_snapshot_path(target_date: str, mode: str = LEDGER_MODE_FROZEN) -> str:
    """Return the absolute path for a snapshot JSON file.

    The function mirrors the historic behavior used by daily_report_entry_demo:
    frozen snapshots live directly under snapshots/, while replay snapshots are
    stored in snapshots/replay/ with a _replay suffix.
    """
    snapshots_dir = _snapshot_root()
    if mode == LEDGER_MODE_REPLAY:
        snapshots_dir = snapshots_dir / "replay"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    return str(snapshots_dir / f"{target_date}{suffix}.json")


def _make_serializable(obj: Any, _depth: int = 0) -> Any:
    """Recursively convert non-JSON-serializable objects into JSON-safe values."""
    MAX_DEPTH = 50
    if _depth > MAX_DEPTH:
        return "<recursion_limit>"

    # Pandas objects are common in this project but the dependency is optional
    try:
        import pandas as pd  # type: ignore

        if isinstance(obj, (pd.DataFrame, pd.Series)):
            return obj.to_dict(orient="records")
    except Exception:
        pass

    if isinstance(obj, (list, tuple)):
        return [_make_serializable(item, _depth + 1) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, set):
        converted = [_make_serializable(item, _depth + 1) for item in obj]
        try:
            return sorted(converted, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
        except Exception:
            return converted
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, (_dt.date, _dt.datetime)):
        if isinstance(obj, _dt.date) and not isinstance(obj, _dt.datetime):
            return obj.strftime("%Y-%m-%d")
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(obj, Enum):
        return {"__enum__": obj.__class__.__name__, "name": obj.name, "value": obj.value}
    if hasattr(obj, "__dataclass_fields__"):
        data = {}
        for k, v in obj.__dict__.items():
            data[k] = _make_serializable(v, _depth + 1)
        data["__class__"] = obj.__class__.__name__
        return data
    if hasattr(obj, "__dict__"):
        skip_attrs = {"__class__", "__module__", "__doc__", "__dict__", "__weakref__"}
        data = {}
        for k, v in obj.__dict__.items():
            if k.startswith("_") and k not in ("__class__",):
                continue
            if isinstance(v, (type, types.ModuleType, types.FunctionType, types.LambdaType)):
                continue
            if k in skip_attrs:
                continue
            try:
                data[k] = _make_serializable(v, _depth + 1)
            except (RecursionError, TypeError):
                data[k] = str(v) if not isinstance(v, str) else v
        data["__class__"] = obj.__class__.__name__
        return data
    return str(obj)


def _snapshot_payload(data: Any, target_date: str, mode: str, existing_perspective: str = "") -> dict:
    return {
        "date": target_date,
        "saved_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "data": _make_serializable(data),
        "supplementary_perspective": existing_perspective or "",
    }


def _save_data_snapshot(data: Any, target_date: str, mode: str = LEDGER_MODE_FROZEN) -> str:
    """Persist a snapshot.

    Behavior:
    - First frozen save writes snapshots/<date>.json.
    - Subsequent frozen saves keep the official snapshot intact and write a
      replay copy to snapshots/replay/<date>_replay.json.
    - Replay mode writes directly to the replay path.
    """
    snapshot_path = _get_snapshot_path(target_date, mode=mode)

    existing_perspective = ""
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                existing_perspective = str(existing.get("supplementary_perspective", "") or "")
        except Exception:
            existing_perspective = ""

    payload = _snapshot_payload(data, target_date, mode, existing_perspective=existing_perspective)

    # Freeze the official snapshot once it exists; keep newer data in replay.
    if mode == LEDGER_MODE_FROZEN and os.path.exists(snapshot_path):
        replay_snapshot_path = _get_snapshot_path(target_date, mode=LEDGER_MODE_REPLAY)
        payload["mode"] = LEDGER_MODE_REPLAY
        with open(replay_snapshot_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"🧊 官方快照已冻结，未覆盖历史: {snapshot_path}")
        print(f"🧪 当前结果已转存为实验快照: {replay_snapshot_path}")
        return replay_snapshot_path

    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"📸 数据快照已保存: {snapshot_path}")
    return snapshot_path


# Backwards-compatible alias used by some callers.
save_data_snapshot = _save_data_snapshot


def load_data_snapshot(target_date: str) -> Tuple[Any, str]:
    """Load a snapshot JSON.

    Returns (data, supplementary_perspective). If the file does not exist,
    returns (None, None).
    """
    snapshot_path = Path(_get_snapshot_path(target_date, mode=LEDGER_MODE_FROZEN))
    if not snapshot_path.exists():
        return None, None

    with snapshot_path.open("r", encoding="utf-8") as f:
        snapshot = json.load(f)

    if isinstance(snapshot, dict) and "data" in snapshot:
        return snapshot.get("data"), snapshot.get("supplementary_perspective", "") or ""

    # Backward-compatible fallback for older flat snapshot formats.
    if isinstance(snapshot, dict):
        perspective = snapshot.get("supplementary_perspective", "") or ""
        ignored = {"supplementary_perspective", "perspective_updated_at", "saved_at", "mode", "date"}
        data = {k: v for k, v in snapshot.items() if k not in ignored}
        return data, perspective

    return snapshot, ""


def add_supplementary_perspective(target_date: str, perspective_text: str) -> bool:
    """Add or update the supplementary perspective in an existing snapshot."""
    snapshot_path = Path(_get_snapshot_path(target_date, mode=LEDGER_MODE_FROZEN))
    if not snapshot_path.exists():
        print(f"❌ 快照不存在: {snapshot_path}")
        return False

    with snapshot_path.open("r", encoding="utf-8") as f:
        snapshot = json.load(f)

    if not isinstance(snapshot, dict):
        snapshot = {"data": snapshot}

    snapshot["supplementary_perspective"] = perspective_text
    snapshot["perspective_updated_at"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"✅ 补充视角已更新: {snapshot_path}")
    return True
