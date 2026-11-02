"""Small-cap comparison constants and the frozen-artifact matrix adapter.

This module is the small-cap entry point's only dependency on the historical
market-return artifact.  The old multi-strategy backtest remains available for
archive work, but it no longer needs to be imported to build the current plan.
"""

from __future__ import annotations

import numpy as np


COMPARISONS = {
    "399006.SZ": "创业板指",
    "000688.SH": "科创50",
    "932000.CSI": "中证2000",
}


def history_from_artifact(value):
    """Build the matrix required by current small-cap ranking and checks."""
    from report.market_returns import price_rows, eligible_artifact_rows

    days, codes = value["trade_dates"], value["codes"]
    shape = (len(codes), len(days))
    close, pre, opened, amount = (np.full(shape, np.nan) for _ in range(4))
    for j, day in enumerate(days):
        for i, c, p, o, a in price_rows(value, day):
            close[i, j], pre[i, j] = c, p
            opened[i, j] = np.nan if o is None else o
            amount[i, j] = np.nan if a is None else a
    bench = {r["date"]: r for r in value["benchmark"]["rows"]}
    m_close = np.array([bench[d]["close"] if d in bench else np.nan for d in days])
    m_pre = np.array([bench[d]["pre_close"] if d in bench else np.nan for d in days])
    m_open = np.array(
        [bench[d].get("open") or np.nan if d in bench else np.nan for d in days],
        dtype=float,
    )
    eligible, _ = eligible_artifact_rows(value)
    mask = np.zeros(shape, dtype=bool)
    mask[eligible, :] = True
    return {
        "days": list(days),
        "codes": list(codes),
        "close": close,
        "pre": pre,
        "open": opened,
        "amount": amount,
        "returns": (close - pre) / pre * 100,
        "m_ret": (m_close - m_pre) / m_pre * 100,
        "m_open": m_open,
        "m_close": m_close,
        "m_pre": m_pre,
        "eligible": mask,
        "limit": np.array(
            [20.0 if c.startswith(("300", "301", "688", "689")) else 10.0 for c in codes]
        ),
        "inputs_sha256": value["artifact_hash"],
    }
