#!/usr/bin/env python3
"""
Get Session Context for AI Agent.

Usage:
    .generated/venv-py314/bin/python3.14 get_context.py           Output context in text format
    .generated/venv-py314/bin/python3.14 get_context.py --json    Output context in JSON format
"""

from __future__ import annotations

from common.git_context import main


if __name__ == "__main__":
    main()
