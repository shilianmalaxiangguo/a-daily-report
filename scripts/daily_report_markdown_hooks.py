#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility wrapper for report markdown hook helpers.

The implementation lives in scripts/knowledge/trading_philosophy.py so the
trading philosophy can be versioned and reused outside the legacy entry script.
"""

from knowledge.trading_philosophy import (
    LEDGER_MODE_FROZEN,
    LEDGER_MODE_REPLAY,
    build_trading_philosophy_snapshot,
    use_contract_logic_digest_text,
    use_execution_framework_text,
    use_report_preamble,
    use_strategy_positioning_lines,
    use_trading_philosophy_lines,
)

__all__ = [
    "LEDGER_MODE_FROZEN",
    "LEDGER_MODE_REPLAY",
    "build_trading_philosophy_snapshot",
    "use_contract_logic_digest_text",
    "use_execution_framework_text",
    "use_report_preamble",
    "use_strategy_positioning_lines",
    "use_trading_philosophy_lines",
]
