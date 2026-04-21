from typing import Any, Dict, TypedDict


class ReportContext(TypedDict):
    request: Dict[str, Any]
    raw: Dict[str, Any]
    normalized: Dict[str, Any]
    derived: Dict[str, Any]
    decision: Dict[str, Any]
    sections: Dict[str, Any]
    rendered: Dict[str, Any]
    diagnostics: Dict[str, Any]
    runtime: Dict[str, Any]
