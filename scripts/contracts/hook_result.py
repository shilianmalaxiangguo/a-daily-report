from typing import Any, Dict, TypedDict


class HookResult(TypedDict):
    value: Dict[str, Any]
    patches: Dict[str, Any]
    diagnostics: Dict[str, Any]
    artifacts: Dict[str, Any]
