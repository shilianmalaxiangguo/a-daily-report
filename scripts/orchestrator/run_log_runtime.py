from __future__ import annotations

import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path


class TeeStream:
    def __init__(self, *streams):
        self._streams = [stream for stream in streams if stream is not None]
        self.encoding = getattr(self._streams[0], "encoding", "utf-8") if self._streams else "utf-8"
        self.errors = getattr(self._streams[0], "errors", "replace") if self._streams else "replace"

    def write(self, data):
        for stream in self._streams:
            stream.write(data)
        return len(data)

    def flush(self):
        for stream in self._streams:
            flush = getattr(stream, "flush", None)
            if flush:
                flush()

    def isatty(self):
        return any(getattr(stream, "isatty", lambda: False)() for stream in self._streams)

    def fileno(self):
        for stream in self._streams:
            fileno = getattr(stream, "fileno", None)
            if fileno is None:
                continue
            return fileno()
        raise OSError("no fileno available")

    def reconfigure(self, **kwargs):
        for stream in self._streams:
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(**kwargs)


class RedactingLineStream:
    def __init__(self, stream):
        self._stream = stream
        self._buffer = ""
        self.encoding = getattr(stream, "encoding", "utf-8")
        self.errors = getattr(stream, "errors", "replace")

    def write(self, data):
        text = str(data or "")
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._stream.write(_redact_sensitive_text(line) + "\n")
        return len(text)

    def flush(self):
        if self._buffer:
            self._stream.write(_redact_sensitive_text(self._buffer))
            self._buffer = ""
        self._stream.flush()

    def isatty(self):
        return getattr(self._stream, "isatty", lambda: False)()

    def fileno(self):
        return self._stream.fileno()

    def reconfigure(self, **kwargs):
        reconfigure = getattr(self._stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(**kwargs)


def _default_logs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "logs"


def _normalize_target_label(argv):
    for item in list(argv or [])[1:]:
        text = _redact_sensitive_text(str(item or "").strip())
        if text and not text.startswith("-"):
            return text.replace("/", "_")
    return "adhoc"


def _normalize_exit_code(code):
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _redact_argv(argv):
    return [_redact_sensitive_text(item) for item in list(argv or [])]


def _write_run_banner(handle, *, started_at, argv, run_log_path):
    handle.write(f"[run-log] started_at={started_at}\n")
    handle.write(f"[run-log] argv={json.dumps(_redact_argv(argv), ensure_ascii=False)}\n")
    handle.write(f"[run-log] file={run_log_path}\n\n")
    handle.flush()


def _write_run_footer(handle, *, finished_at, status, exit_code):
    handle.write(f"\n[run-log] finished_at={finished_at}\n")
    handle.write(f"[run-log] status={status}\n")
    handle.write(f"[run-log] exit_code={exit_code}\n")
    handle.flush()


def _write_error_summary(error_log_path, *, started_at, failed_at, argv, run_log_path, error, tb_text):
    payload = {
        "started_at": started_at,
        "failed_at": failed_at,
        "argv": _redact_argv(argv),
        "run_log_path": str(run_log_path),
        "error_type": error.__class__.__name__,
        "error_message": _redact_sensitive_text(str(error)),
        "traceback": _redact_sensitive_text(tb_text),
    }
    error_log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


_IMPORTANT_LINE_MARKERS = (
    "关键数据不完整",
    "停止生成",
    "日报一致性检查",
    "数据获取失败",
    "失败",
    "Traceback",
    "Error",
    "error",
    "Tushare",
    "tushare",
    "quicktiny",
    "QuickTiny",
    "异动检测",
    "未生成",
)


def _redact_sensitive_text(text):
    value = str(text or "")
    value = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer ***", value)
    value = re.sub(r"(token=)[^;\s\"']+", r"\1***", value, flags=re.IGNORECASE)
    value = re.sub(r"(cookie\s*[:=]\s*)[^\n\r]+", r"\1***", value, flags=re.IGNORECASE)
    value = re.sub(r"postgres(?:ql)?://[^\s\"']+", "postgresql://***", value, flags=re.IGNORECASE)
    value = re.sub(
        r"((?:[A-Z0-9_]*(?:TOKEN|COOKIE|API_KEY|DATABASE_URL|PASSWORD|SECRET))[\"']?\s*[:=]\s*[\"']?)[^\"'\s,;]+",
        r"\1***",
        value,
    )
    value = re.sub(
        r"((?:[A-Za-z0-9_]*(?:_token|_cookie)|api_key|database_url|password|secret)[\"']?\s*[:=]\s*[\"']?)[^\"'\s,;]+",
        r"\1***",
        value,
        flags=re.IGNORECASE,
    )
    return value


def _recent_important_lines(run_log_path, *, limit=40):
    try:
        lines = Path(run_log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    matched = [
        _redact_sensitive_text(line)
        for line in lines
        if any(marker in line for marker in _IMPORTANT_LINE_MARKERS)
    ]
    return matched[-limit:]


def _write_latest_run_summary(root, summary, *, failed=False):
    root = Path(root)
    payload = dict(summary)
    payload["recent_important_lines"] = _recent_important_lines(payload.get("run_log_path", ""))
    (root / "latest_run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if failed:
        (root / "latest_failure.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _build_latest_summary(
    *,
    started_at,
    finished_at,
    argv,
    run_key,
    target_label,
    run_log_path,
    status,
    exit_code,
    error_log_path=None,
    error=None,
):
    payload = {
        "run_key": run_key,
        "target_label": target_label,
        "started_at": started_at,
        "finished_at": finished_at,
        "argv": _redact_argv(argv),
        "status": status,
        "exit_code": int(exit_code),
        "run_log_path": str(run_log_path),
    }
    if error_log_path is not None:
        payload["error_log_path"] = str(error_log_path)
    if error is not None:
        payload["error_type"] = error.__class__.__name__
        payload["error_message"] = _redact_sensitive_text(str(error))
    return payload


def run_with_log_capture(main_fn, *, argv=None, logs_root=None, now=None):
    argv = list(argv or sys.argv)
    started_dt = now or datetime.now()
    started_at = started_dt.strftime("%Y-%m-%d %H:%M:%S")
    target_label = _normalize_target_label(argv)
    run_key = f"{started_dt.strftime('%Y%m%d-%H%M%S')}__{target_label}"

    root = Path(logs_root) if logs_root else _default_logs_root()
    runs_dir = root / "runs"
    errors_dir = root / "errors"
    runs_dir.mkdir(parents=True, exist_ok=True)
    errors_dir.mkdir(parents=True, exist_ok=True)

    run_log_path = runs_dir / f"{run_key}.log"
    error_log_path = errors_dir / f"{run_key}.json"

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    with run_log_path.open("w", encoding="utf-8") as log_handle:
        redacted_log_handle = RedactingLineStream(log_handle)
        redacted_stdout = RedactingLineStream(original_stdout)
        redacted_stderr = RedactingLineStream(original_stderr)
        sys.stdout = TeeStream(redacted_stdout, redacted_log_handle)
        sys.stderr = TeeStream(redacted_stderr, redacted_log_handle)
        _write_run_banner(redacted_log_handle, started_at=started_at, argv=argv, run_log_path=run_log_path)
        try:
            exit_code = _normalize_exit_code(main_fn())
            finished_at = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
            status = "success" if exit_code == 0 else "nonzero_exit"
            _write_run_footer(
                redacted_log_handle,
                finished_at=finished_at,
                status=status,
                exit_code=exit_code,
            )
            _write_latest_run_summary(
                root,
                _build_latest_summary(
                    started_at=started_at,
                    finished_at=finished_at,
                    argv=argv,
                    run_key=run_key,
                    target_label=target_label,
                    run_log_path=run_log_path,
                    status=status,
                    exit_code=exit_code,
                ),
                failed=exit_code != 0,
            )
            return exit_code
        except SystemExit as exc:
            exit_code = _normalize_exit_code(exc.code)
            failed_at = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
            if exit_code != 0:
                tb_text = traceback.format_exc()
                if tb_text.strip() and tb_text.strip() != "NoneType: None":
                    print(tb_text, file=sys.stderr, end="")
                _write_error_summary(
                    error_log_path,
                    started_at=started_at,
                    failed_at=failed_at,
                    argv=argv,
                    run_log_path=run_log_path,
                    error=exc,
                    tb_text=tb_text,
                )
            _write_run_footer(
                redacted_log_handle,
                finished_at=failed_at,
                status="success" if exit_code == 0 else "system_exit",
                exit_code=exit_code,
            )
            _write_latest_run_summary(
                root,
                _build_latest_summary(
                    started_at=started_at,
                    finished_at=failed_at,
                    argv=argv,
                    run_key=run_key,
                    target_label=target_label,
                    run_log_path=run_log_path,
                    error_log_path=error_log_path if exit_code != 0 else None,
                    status="success" if exit_code == 0 else "system_exit",
                    exit_code=exit_code,
                    error=exc if exit_code != 0 else None,
                ),
                failed=exit_code != 0,
            )
            raise
        except Exception as error:
            failed_at = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
            tb_text = traceback.format_exc()
            print(tb_text, file=sys.stderr, end="")
            _write_error_summary(
                error_log_path,
                started_at=started_at,
                failed_at=failed_at,
                argv=argv,
                run_log_path=run_log_path,
                error=error,
                tb_text=tb_text,
            )
            _write_run_footer(
                redacted_log_handle,
                finished_at=failed_at,
                status="error",
                exit_code=1,
            )
            _write_latest_run_summary(
                root,
                _build_latest_summary(
                    started_at=started_at,
                    finished_at=failed_at,
                    argv=argv,
                    run_key=run_key,
                    target_label=target_label,
                    run_log_path=run_log_path,
                    error_log_path=error_log_path,
                    status="error",
                    exit_code=1,
                    error=error,
                ),
                failed=True,
            )
            raise
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
