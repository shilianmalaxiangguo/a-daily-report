from __future__ import annotations

import os
from pathlib import Path

from legacy_runtime_shim import export_or_default


def _load_local_env_file():
    for env_path in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
        return


_load_local_env_file()
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-v4-pro")

get_llm_service = export_or_default("llm_service", "get_llm_service", lambda *args, **kwargs: None)

__all__ = ["get_llm_service"]
