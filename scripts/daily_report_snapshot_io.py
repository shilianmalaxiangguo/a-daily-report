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
import tempfile
import traceback
import types
from enum import Enum
from pathlib import Path
from typing import Any, Tuple

LEDGER_MODE_FROZEN = "frozen"
LEDGER_MODE_REPLAY = "replay"
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
_CIRCULAR_REFERENCE = "<circular_reference>"

__all__ = [
    "LEDGER_MODE_FROZEN",
    "LEDGER_MODE_REPLAY",
    "SnapshotWriteError",
    "_make_serializable",
    "_get_snapshot_path",
    "_save_data_snapshot",
    "load_data_snapshot",
    "add_supplementary_perspective",
    "save_data_snapshot",
]


class SnapshotWriteError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        snapshot_path: str = "",
        mode: str = "",
        bytes_written: int = 0,
        attempted_size_bytes: int = 0,
        size_limited: bool = False,
    ):
        super().__init__(message)
        self.snapshot_path = str(snapshot_path or "")
        self.mode = str(mode or "")
        self.bytes_written = int(bytes_written or 0)
        self.attempted_size_bytes = int(attempted_size_bytes or 0)
        self.size_limited = bool(size_limited)


class _SnapshotTargetExistsError(SnapshotWriteError):
    """Raised when a no-replace snapshot publish loses a concurrent race."""


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


def _make_serializable(obj: Any, _depth: int = 0, _active_ids: set[int] | None = None) -> Any:
    """Recursively convert non-JSON-serializable objects into JSON-safe values."""
    MAX_DEPTH = 50
    if _depth > MAX_DEPTH:
        return "<recursion_limit>"
    active_ids = _active_ids if _active_ids is not None else set()

    # Pandas objects are common in this project but the dependency is optional
    try:
        import pandas as pd  # type: ignore

        if isinstance(obj, (pd.DataFrame, pd.Series)):
            return obj.to_dict(orient="records")
    except Exception:
        pass

    if isinstance(obj, (list, tuple)):
        obj_id = id(obj)
        if obj_id in active_ids:
            return _CIRCULAR_REFERENCE
        active_ids.add(obj_id)
        try:
            return [_make_serializable(item, _depth + 1, active_ids) for item in obj]
        finally:
            active_ids.discard(obj_id)
    if isinstance(obj, dict):
        obj_id = id(obj)
        if obj_id in active_ids:
            return _CIRCULAR_REFERENCE
        active_ids.add(obj_id)
        try:
            return {str(k): _make_serializable(v, _depth + 1, active_ids) for k, v in obj.items()}
        finally:
            active_ids.discard(obj_id)
    if isinstance(obj, set):
        obj_id = id(obj)
        if obj_id in active_ids:
            return _CIRCULAR_REFERENCE
        active_ids.add(obj_id)
        try:
            converted = [_make_serializable(item, _depth + 1, active_ids) for item in obj]
            try:
                return sorted(converted, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
            except Exception:
                return converted
        finally:
            active_ids.discard(obj_id)
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
        obj_id = id(obj)
        if obj_id in active_ids:
            return _CIRCULAR_REFERENCE
        active_ids.add(obj_id)
        try:
            data = {}
            for k, v in obj.__dict__.items():
                data[k] = _make_serializable(v, _depth + 1, active_ids)
            data["__class__"] = obj.__class__.__name__
            return data
        finally:
            active_ids.discard(obj_id)
    if hasattr(obj, "__dict__"):
        obj_id = id(obj)
        if obj_id in active_ids:
            return _CIRCULAR_REFERENCE
        active_ids.add(obj_id)
        skip_attrs = {"__class__", "__module__", "__doc__", "__dict__", "__weakref__"}
        try:
            data = {}
            for k, v in obj.__dict__.items():
                if k.startswith("_") and k not in ("__class__",):
                    continue
                if isinstance(v, (type, types.ModuleType, types.FunctionType, types.LambdaType)):
                    continue
                if k in skip_attrs:
                    continue
                try:
                    data[k] = _make_serializable(v, _depth + 1, active_ids)
                except (RecursionError, TypeError):
                    data[k] = str(v) if not isinstance(v, str) else v
            data["__class__"] = obj.__class__.__name__
            return data
        finally:
            active_ids.discard(obj_id)
    return str(obj)


class _SizeLimitedTextWriter:
    def __init__(self, file_obj, max_bytes: int, *, snapshot_path: Path, mode: str):
        self._file_obj = file_obj
        self._max_bytes = int(max_bytes)
        self._snapshot_path = snapshot_path
        self._mode = str(mode or "")
        self.bytes_written = 0

    def write(self, text: str) -> int:
        encoded_size = len(text.encode("utf-8"))
        next_size = self.bytes_written + encoded_size
        if next_size > self._max_bytes:
            raise SnapshotWriteError(
                f"数据快照超过写入上限（{self._max_bytes} 字节），停止保存",
                snapshot_path=str(self._snapshot_path),
                mode=self._mode,
                bytes_written=self.bytes_written,
                attempted_size_bytes=next_size,
                size_limited=True,
            )
        written = self._file_obj.write(text)
        self.bytes_written = next_size
        return written


def _write_snapshot_payload(
    snapshot_path: Path,
    payload: dict,
    *,
    mode: str,
    replace_existing: bool = True,
) -> int:
    temp_path = None
    limited_writer = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=snapshot_path.parent,
            prefix=f".{snapshot_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file_obj:
            temp_path = Path(file_obj.name)
            limited_writer = _SizeLimitedTextWriter(
                file_obj,
                MAX_SNAPSHOT_BYTES,
                snapshot_path=snapshot_path,
                mode=mode,
            )
            json.dump(payload, limited_writer, ensure_ascii=False, indent=2)
            file_obj.flush()
            os.fsync(file_obj.fileno())
            snapshot_size = limited_writer.bytes_written
        if replace_existing:
            os.replace(temp_path, snapshot_path)
        else:
            try:
                os.link(temp_path, snapshot_path)
            except FileExistsError as error:
                raise _SnapshotTargetExistsError(
                    "正式数据快照已由另一进程保存，本次转存实验快照",
                    snapshot_path=str(snapshot_path),
                    mode=mode,
                    bytes_written=snapshot_size,
                ) from error
            temp_path.unlink()
        temp_path = None
        return snapshot_size
    except Exception as error:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if isinstance(error, SnapshotWriteError):
            raise
        raise SnapshotWriteError(
            f"数据快照保存失败: {error}",
            snapshot_path=str(snapshot_path),
            mode=mode,
            bytes_written=limited_writer.bytes_written if limited_writer is not None else 0,
        ) from error


def _snapshot_payload(data: Any, target_date: str, mode: str, existing_perspective: str = "") -> dict:
    return {
        "date": target_date,
        "saved_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "data": _make_serializable(data),
        "supplementary_perspective": existing_perspective or "",
    }


def _decode_json_string_field_from_text(text: str, field_name: str) -> str:
    marker = json.dumps(str(field_name), ensure_ascii=False)
    index = text.rfind(marker)
    if index < 0:
        return ""
    colon_index = text.find(":", index + len(marker))
    if colon_index < 0:
        return ""
    try:
        value, _ = json.JSONDecoder().raw_decode(text[colon_index + 1 :].lstrip())
    except Exception:
        return ""
    return str(value or "") if isinstance(value, str) else ""


def _load_existing_supplementary_perspective(snapshot_path: Path) -> str:
    """Read only the tail metadata needed from very large historical snapshots."""
    try:
        file_size = snapshot_path.stat().st_size
    except OSError:
        return ""
    if file_size <= 0:
        return ""

    tail_size = min(file_size, 4 * 1024 * 1024)
    try:
        with snapshot_path.open("rb") as file_obj:
            file_obj.seek(max(file_size - tail_size, 0))
            tail_text = file_obj.read(tail_size).decode("utf-8", errors="replace")
    except OSError:
        return ""
    return _decode_json_string_field_from_text(tail_text, "supplementary_perspective")


def _save_data_snapshot(data: Any, target_date: str, mode: str = LEDGER_MODE_FROZEN) -> str:
    """Persist a snapshot.

    Behavior:
    - First frozen save writes snapshots/<date>.json.
    - Subsequent frozen saves keep the official snapshot intact and write a
      replay copy to snapshots/replay/<date>_replay.json.
    - Replay mode writes directly to the replay path.
    """
    requested_path = Path(_get_snapshot_path(target_date, mode=mode))
    official_exists = mode == LEDGER_MODE_FROZEN and requested_path.exists()
    actual_mode = LEDGER_MODE_REPLAY if official_exists else mode
    actual_path = (
        Path(_get_snapshot_path(target_date, mode=LEDGER_MODE_REPLAY))
        if actual_mode == LEDGER_MODE_REPLAY
        else requested_path
    )
    existing_perspective = (
        _load_existing_supplementary_perspective(requested_path)
        if requested_path.exists()
        else ""
    )

    try:
        payload = _snapshot_payload(
            data,
            target_date,
            actual_mode,
            existing_perspective=existing_perspective,
        )
    except Exception as error:
        if mode == LEDGER_MODE_FROZEN and requested_path.exists():
            actual_mode = LEDGER_MODE_REPLAY
            actual_path = Path(_get_snapshot_path(target_date, mode=LEDGER_MODE_REPLAY))
        raise SnapshotWriteError(
            f"数据快照序列化失败: {error}",
            snapshot_path=str(actual_path),
            mode=actual_mode,
            bytes_written=0,
        ) from error

    if actual_mode == LEDGER_MODE_REPLAY and mode == LEDGER_MODE_FROZEN:
        snapshot_size = _write_snapshot_payload(
            actual_path,
            payload,
            mode=LEDGER_MODE_REPLAY,
        )
        print(f"🧊 官方快照已冻结，未覆盖历史: {requested_path}")
        print(f"🧪 当前结果已转存为实验快照: {actual_path} ({snapshot_size} 字节)")
        return str(actual_path)

    try:
        snapshot_size = _write_snapshot_payload(
            actual_path,
            payload,
            mode=actual_mode,
            replace_existing=mode != LEDGER_MODE_FROZEN,
        )
    except _SnapshotTargetExistsError:
        replay_snapshot_path = Path(_get_snapshot_path(target_date, mode=LEDGER_MODE_REPLAY))
        payload["mode"] = LEDGER_MODE_REPLAY
        payload["supplementary_perspective"] = _load_existing_supplementary_perspective(requested_path)
        snapshot_size = _write_snapshot_payload(
            replay_snapshot_path,
            payload,
            mode=LEDGER_MODE_REPLAY,
        )
        print(f"🧊 官方快照已冻结，未覆盖历史: {requested_path}")
        print(f"🧪 当前结果已转存为实验快照: {replay_snapshot_path} ({snapshot_size} 字节)")
        return str(replay_snapshot_path)

    print(f"📸 数据快照已保存: {actual_path} ({snapshot_size} 字节)")
    return str(actual_path)


# Backwards-compatible alias used by some callers.
save_data_snapshot = _save_data_snapshot


def load_data_snapshot(target_date: str) -> Tuple[Any, str]:
    """Load a snapshot JSON.

    Returns (data, supplementary_perspective). If the file does not exist,
    returns (None, None).
    """
    if os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1":
        stack = "".join(traceback.format_stack(limit=12))
        raise RuntimeError(
            "PostgreSQL-only runtime attempted to read JSON snapshot "
            f"for {target_date}.\n{stack}"
        )
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
