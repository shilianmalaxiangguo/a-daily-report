from typing import List, TypedDict


class DerivationRecord(TypedDict):
    hook_name: str
    inputs: List[str]
    assumptions: List[str]
    formula: str
    output_keys: List[str]
    confidence: float
    warnings: List[str]
