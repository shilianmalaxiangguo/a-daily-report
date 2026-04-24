from __future__ import annotations

from legacy_runtime_shim import export_or_default


class _DataValidatorFallback:
    pass


DataValidator = export_or_default("data_validator", "DataValidator", _DataValidatorFallback)

__all__ = ["DataValidator"]
