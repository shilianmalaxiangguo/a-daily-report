from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pipelines.cloudflare_free_turnover_pipeline import run_turnover_pipeline

__all__ = [
    "PublishTaskRecorder",
    "SnapUiPublicDataPublishError",
    "publish_snap_ui_public_data",
]


TASKS = [
    ("resolve_target_date", "Resolve target date"),
    ("fetch_tushare_turnover", "Fetch Tushare turnover data"),
    ("build_artifacts", "Build D1/R2 artifacts"),
    ("export_static_data", "Export snap-ui static data"),
    ("contract_check", "Run local data contract check"),
    ("write_manifest", "Write publish manifest"),
]


class SnapUiPublicDataPublishError(RuntimeError):
    """Raised when public data is incomplete and release must stop."""


class PublishTaskRecorder:
    def __init__(self, target_date):
        self.target_date = target_date
        self.completed = set()
        self.failure = ""

    def mark_done(self, task_key):
        self.completed.add(task_key)

    def mark_failure(self, message):
        self.failure = str(message or "").strip()

    def render_markdown(self):
        lines = [f"# Snap UI Public Data Tasks - {self.target_date}", ""]
        for task_key, label in TASKS:
            checkbox = "x" if task_key in self.completed else " "
            lines.append(f"- [{checkbox}] {label}")
        if self.failure:
            lines.extend(["", f"Failure: {self.failure}"])
        return "\n".join(lines) + "\n"


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path):
    if not path:
        return ""
    path = Path(path)
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_error(error):
    message = str(error)
    stderr = getattr(error, "stderr", "")
    if stderr:
        message = f"{message}: {stderr}"
    return message


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_tasks(path, recorder):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(recorder.render_markdown(), encoding="utf-8")
    return path


def _resolve_public_latest_date(snap_ui_dir, fallback_date):
    index_path = Path(snap_ui_dir) / "public" / "data" / "daily-reports" / "index.json"
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return str(fallback_date)
    reports = payload.get("reports") if isinstance(payload, dict) else []
    if not isinstance(reports, list) or not reports:
        return str(fallback_date)
    latest = reports[0].get("date") if isinstance(reports[0], dict) else ""
    return str(latest or fallback_date)


def _default_static_export_runner(root, snap_ui_dir):
    command = ["npm", "--prefix", str(snap_ui_dir), "run", "export:static-data"]
    completed = subprocess.run(command, cwd=str(root), check=True, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _default_contract_check_runner(root, snap_ui_dir, target_date):
    command = ["npm", "test", "--", "tests/unit/publicStaticDataContract.test.ts"]
    env = {
        **os.environ,
        "SNAP_UI_EXPECTED_LATEST_DATE": str(target_date),
    }
    completed = subprocess.run(
        command,
        cwd=str(snap_ui_dir),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _build_manifest(
    *,
    target_date,
    status,
    root,
    output_dir,
    artifact_root=None,
    turnover_result=None,
    static_export_result=None,
    contract_check_result=None,
    failure="",
):
    turnover_result = turnover_result or {}
    export_result = turnover_result.get("export") or {}
    local_path = export_result.get("local_path") or (
        str(Path(artifact_root) / export_result.get("r2_key", "")) if artifact_root and export_result.get("r2_key") else ""
    )
    return {
        "schema_version": "snap-ui-public-data-publish/v1",
        "status": status,
        "target_date": target_date,
        "generated_at": _utc_now_iso(),
        "data_source": "tushare",
        "root": str(root),
        "output_dir": str(output_dir),
        "failure": failure,
        "turnover": {
            "trade_date": turnover_result.get("trade_date", target_date),
            "quote_count": int(turnover_result.get("quote_count") or 0),
            "rank_count": int(turnover_result.get("rank_count") or 0),
            "source_run_id": turnover_result.get("source_run_id"),
            "r2_key": export_result.get("r2_key", ""),
            "local_path": str(local_path),
            "content_hash": export_result.get("content_hash") or _sha256_file(local_path),
        },
        "static_export": {
            "command": list((static_export_result or {}).get("command") or []),
            "returncode": (static_export_result or {}).get("returncode"),
        },
        "contract_check": {
            "command": list((contract_check_result or {}).get("command") or []),
            "returncode": (contract_check_result or {}).get("returncode"),
        },
    }


def publish_snap_ui_public_data(
    target_date,
    *,
    root=None,
    output_root=None,
    db_path=None,
    artifact_root=None,
    snap_ui_dir=None,
    turnover_pipeline_runner=None,
    static_export_runner=None,
    contract_check_runner=None,
):
    root = Path(root or Path(__file__).resolve().parents[2])
    snap_ui_dir = Path(snap_ui_dir or root / "snap-ui")
    output_dir = Path(output_root or root / ".generated" / "snap-ui-public-data") / str(target_date)
    db_path = Path(db_path or root / "data" / "cloudflare_free_daily.db")
    artifact_root = Path(artifact_root or root / ".generated" / "r2")
    manifest_path = output_dir / "snap-ui_publish_manifest.json"
    tasks_path = output_dir / "snap-ui_publish_tasks.md"

    recorder = PublishTaskRecorder(target_date)
    turnover_pipeline_runner = turnover_pipeline_runner or run_turnover_pipeline
    static_export_runner = static_export_runner or _default_static_export_runner
    contract_check_runner = contract_check_runner or _default_contract_check_runner

    turnover_result = {}
    static_export_result = {}
    contract_check_result = {}

    try:
        recorder.mark_done("resolve_target_date")
        public_latest_date = _resolve_public_latest_date(snap_ui_dir, target_date)
        turnover_result = turnover_pipeline_runner(
            public_latest_date,
            db_path=db_path,
            artifact_root=artifact_root,
        )
        recorder.mark_done("fetch_tushare_turnover")
        recorder.mark_done("build_artifacts")

        static_export_result = static_export_runner(root, snap_ui_dir)
        recorder.mark_done("export_static_data")

        contract_check_result = contract_check_runner(
            root,
            snap_ui_dir,
            public_latest_date,
        )
        recorder.mark_done("contract_check")

        manifest = _build_manifest(
            target_date=target_date,
            status="success",
            root=root,
            output_dir=output_dir,
            artifact_root=artifact_root,
            turnover_result=turnover_result,
            static_export_result=static_export_result,
            contract_check_result=contract_check_result,
        )
        recorder.mark_done("write_manifest")
        _write_json(manifest_path, manifest)
        _write_tasks(tasks_path, recorder)
        return {
            "status": "success",
            "manifest_path": str(manifest_path),
            "tasks_path": str(tasks_path),
            "manifest": manifest,
        }
    except Exception as error:
        error_message = _format_error(error)
        recorder.mark_failure(error_message)
        manifest = _build_manifest(
            target_date=target_date,
            status="failed",
            root=root,
            output_dir=output_dir,
            artifact_root=artifact_root,
            turnover_result=turnover_result,
            static_export_result=static_export_result,
            contract_check_result=contract_check_result,
            failure=error_message,
        )
        _write_json(manifest_path, manifest)
        _write_tasks(tasks_path, recorder)
        raise SnapUiPublicDataPublishError(error_message) from error
