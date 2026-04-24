from __future__ import annotations

import json
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


def _default_logs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "logs"


def _normalize_target_label(argv):
    for item in list(argv or [])[1:]:
        text = str(item or "").strip()
        if text and not text.startswith("-"):
            return text.replace("/", "_")
    return "adhoc"


def _normalize_exit_code(code):
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _write_run_banner(handle, *, started_at, argv, run_log_path):
    handle.write(f"[run-log] started_at={started_at}\n")
    handle.write(f"[run-log] argv={json.dumps(list(argv or []), ensure_ascii=False)}\n")
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
        "argv": list(argv or []),
        "run_log_path": str(run_log_path),
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "traceback": tb_text,
    }
    error_log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_with_log_capture(main_fn, *, argv=None, logs_root=None, now=None):
    argv = list(argv or sys.argv)
    started_dt = now or datetime.now()
    started_at = started_dt.strftime("%Y-%m-%d %H:%M:%S")
    run_key = f"{started_dt.strftime('%Y%m%d-%H%M%S')}__{_normalize_target_label(argv)}"

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
        sys.stdout = TeeStream(original_stdout, log_handle)
        sys.stderr = TeeStream(original_stderr, log_handle)
        _write_run_banner(log_handle, started_at=started_at, argv=argv, run_log_path=run_log_path)
        try:
            exit_code = _normalize_exit_code(main_fn())
            _write_run_footer(
                log_handle,
                finished_at=(now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
                status="success" if exit_code == 0 else "nonzero_exit",
                exit_code=exit_code,
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
                log_handle,
                finished_at=failed_at,
                status="success" if exit_code == 0 else "system_exit",
                exit_code=exit_code,
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
                log_handle,
                finished_at=failed_at,
                status="error",
                exit_code=1,
            )
            raise
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
