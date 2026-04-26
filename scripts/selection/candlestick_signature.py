def safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace("%", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def first_number(stock, keys):
    for key in keys:
        value = safe_float(stock.get(key))
        if value is not None:
            return value
    return None


def volume_prefix(stock):
    summary = " ".join(
        str(stock.get(key) or "")
        for key in (
            "volume_state",
            "volume_pattern",
            "volume_summary",
            "abnormal_summary",
            "reason",
            "capital_trace",
        )
    )
    if "缩量" in summary:
        return "缩量"
    if "放量" in summary or "显著放量" in summary or "倍" in summary:
        return "放量"
    return ""


def infer_signature_big_yangline(stock):
    explicit = stock.get("signature_big_yangline")
    if explicit:
        return explicit

    pattern = str(stock.get("pattern") or stock.get("shape") or stock.get("candlestick") or "").strip()
    prefix = volume_prefix(stock)
    if "一字" in pattern:
        return "一字板"
    if "T字" in pattern or "T板" in pattern:
        return f"{prefix}T字板" if prefix else "T字板"

    open_price = first_number(stock, ("open", "open_price", "开盘价"))
    high_price = first_number(stock, ("high", "high_price", "最高价"))
    low_price = first_number(stock, ("low", "low_price", "最低价"))
    close_price = first_number(stock, ("close", "close_price", "最新价", "收盘价"))
    change_pct = first_number(stock, ("change", "change_pct", "涨跌幅"))
    if None in (open_price, high_price, low_price, close_price, change_pct):
        return "-"

    is_limit_up = change_pct >= 9.8
    price_tolerance = max(abs(close_price) * 0.005, 0.01)
    close_at_high = abs(close_price - high_price) <= price_tolerance
    open_near_high = abs(open_price - high_price) <= price_tolerance
    has_intraday_break = low_price < min(open_price, close_price) - price_tolerance

    if is_limit_up and abs(open_price - close_price) <= price_tolerance and abs(high_price - low_price) <= price_tolerance:
        return "一字板"
    if is_limit_up and close_at_high and open_near_high and has_intraday_break:
        return f"{prefix}T字板" if prefix else "T字板"
    if is_limit_up and close_at_high:
        return f"{prefix}大阳线" if prefix else "大阳线"
    if change_pct >= 5:
        return f"{prefix}大阳线" if prefix else "大阳线"
    return "-"
