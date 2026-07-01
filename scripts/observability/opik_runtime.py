from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


OPIK_ENABLED_ENV = "A_DAILY_REPORT_OPIK_ENABLED"
OPIK_PROJECT_ENV = "A_DAILY_REPORT_OPIK_PROJECT"
DEFAULT_OPIK_PROJECT = "a-daily-report"
_TRUTHY_VALUES = {"1", "true", "yes", "on", "enabled"}
_MAX_ITEMS = 30
_MAX_TEXT = 1000


def opik_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return str(source.get(OPIK_ENABLED_ENV, "") or "").strip().lower() in _TRUTHY_VALUES


class NoopOpikObserver:
    enabled = False

    def __init__(self, reason: str = "disabled"):
        self.reason = reason

    def record_step(
        self,
        name: str,
        *,
        status: str,
        input_payload: Mapping[str, Any] | None = None,
        output_payload: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        error: BaseException | str | None = None,
    ) -> None:
        return None

    def finish(
        self,
        *,
        status: str,
        output_payload: Mapping[str, Any] | None = None,
    ) -> None:
        return None


class OpikRunObserver:
    enabled = True

    def __init__(self, *, client: Any, trace: Any):
        self._client = client
        self._trace = trace

    def record_step(
        self,
        name: str,
        *,
        status: str,
        input_payload: Mapping[str, Any] | None = None,
        output_payload: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        error: BaseException | str | None = None,
    ) -> None:
        try:
            output = dict(output_payload or {})
            output["status"] = status
            if error is not None:
                output["error"] = str(error)
            span = _call_optional(
                getattr(self._trace, "span", None),
                name=name,
                type="tool",
                input=_compact_payload(input_payload or {}),
                output=_compact_payload(output),
                metadata=_compact_payload(metadata or {}),
            )
            _end_optional(span)
        except Exception:
            return None

    def finish(
        self,
        *,
        status: str,
        output_payload: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            output = dict(output_payload or {})
            output["status"] = status
            _call_optional(
                getattr(self._trace, "end", None),
                output=_compact_payload(output),
            )
            _call_optional(getattr(self._client, "flush", None))
        except Exception:
            return None


def build_report_run_observer(
    *,
    run_name: str,
    trace_input: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    client_factory: Callable[[], Any] | None = None,
    env: Mapping[str, str] | None = None,
):
    source = env if env is not None else os.environ
    if not opik_enabled(source):
        return NoopOpikObserver()
    try:
        client = client_factory() if client_factory else _create_opik_client(source)
        trace = _call_optional(
            getattr(client, "trace", None),
            name=run_name,
            input=_compact_payload(trace_input or {}),
            metadata=_compact_payload(metadata or {}),
        )
        if trace is None:
            return NoopOpikObserver(reason="trace_unavailable")
        return OpikRunObserver(client=client, trace=trace)
    except Exception:
        return NoopOpikObserver(reason="client_unavailable")


def _create_opik_client(env: Mapping[str, str]) -> Any:
    opik_module = importlib.import_module("opik")
    client_cls = getattr(opik_module, "Opik")
    project_name = str(env.get(OPIK_PROJECT_ENV) or DEFAULT_OPIK_PROJECT).strip()
    try:
        return client_cls(project_name=project_name)
    except TypeError:
        return client_cls()


def _call_optional(method: Any, **kwargs: Any) -> Any:
    if method is None:
        return None
    attempts = [
        kwargs,
        {key: value for key, value in kwargs.items() if value is not None},
        {key: value for key, value in kwargs.items() if key != "metadata" and value is not None},
        {key: value for key, value in kwargs.items() if key in {"name", "input", "output"} and value is not None},
        {key: value for key, value in kwargs.items() if key == "name" and value is not None},
        {},
    ]
    for attempt in attempts:
        try:
            return method(**attempt)
        except TypeError:
            continue
        except Exception:
            return None
    return None


def _end_optional(span: Any) -> None:
    end = getattr(span, "end", None)
    if end is None:
        return None
    _call_optional(end)
    return None


def _compact_payload(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return _compact_scalar(value)
    if isinstance(value, Mapping):
        compact = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                compact["__truncated_items__"] = len(value) - _MAX_ITEMS
                break
            compact[str(key)] = _compact_payload(item, depth=depth + 1)
        return compact
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        compact = [_compact_payload(item, depth=depth + 1) for item in items[:_MAX_ITEMS]]
        if len(items) > _MAX_ITEMS:
            compact.append({"__truncated_items__": len(items) - _MAX_ITEMS})
        return compact
    return _compact_scalar(value)


def _compact_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    text = str(value)
    if len(text) <= _MAX_TEXT:
        return text
    return text[:_MAX_TEXT] + f"...[truncated {len(text) - _MAX_TEXT} chars]"
