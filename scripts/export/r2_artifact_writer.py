from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = [
    "R2ArtifactWriter",
]


def _default_command_runner(command):
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


class R2ArtifactWriter:
    def __init__(self, *, bucket_name, command_runner=None, wrangler_command=None, remote=True):
        self.bucket_name = str(bucket_name or "").strip()
        if not self.bucket_name:
            raise ValueError("bucket_name is required")
        self.command_runner = command_runner or _default_command_runner
        self.wrangler_command = list(wrangler_command or ["wrangler"])
        self.remote = bool(remote)

    def build_put_command(self, r2_key, local_path):
        r2_key = str(r2_key or "").strip().lstrip("/")
        if not r2_key:
            raise ValueError("r2_key is required")
        command = [
            *self.wrangler_command,
            "r2",
            "object",
            "put",
            f"{self.bucket_name}/{r2_key}",
        ]
        if self.remote:
            command.append("--remote")
        command.extend([
            "--file",
            str(local_path),
        ])
        return command

    def upload_local_artifact(self, r2_key, local_path):
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        command = self.build_put_command(r2_key, str(path))
        result = self.command_runner(command)
        return {
            "status": "success" if int(result.get("returncode", 1)) == 0 else "failed",
            "command": command,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }
