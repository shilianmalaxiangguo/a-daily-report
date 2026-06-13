def normalize_stock_code(raw_code):
    code = str(raw_code or "").strip()
    for suffix in (".SZ", ".SS", ".SH", ".BJ"):
        if code.endswith(suffix):
            code = code[: -len(suffix)]
            break

    lower_code = code.lower()
    for prefix in ("sz", "sh", "bj"):
        if lower_code.startswith(prefix):
            code = code[len(prefix) :]
            break

    return code.strip()


def normalize_stock_name(raw_name):
    return "".join(str(raw_name or "").split())


def _safe_float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_change_pct(row):
    if not isinstance(row, dict):
        return None

    for key in ("change_pct", "涨跌幅", "zdf", "change_rate"):
        if row.get(key) in (None, ""):
            continue
        change_pct = _safe_float_or_none(row.get(key))
        if change_pct is not None:
            return change_pct
    return None


def _positive_float(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _first_positive(row, keys):
    for key in keys:
        value = _positive_float(row.get(key))
        if value is not None:
            return value
    return None


def _quote_complete(row):
    if not isinstance(row, dict):
        return False
    if _extract_change_pct(row) is None:
        return False
    return all(
        _first_positive(row, keys) is not None
        for keys in (
            ("open", "开盘价", "开盘", "open_price"),
            ("high", "最高价", "最高", "high_price"),
            ("low", "最低价", "最低", "low_price"),
            ("close", "最新价", "收盘价", "收盘", "price", "当前价", "close_price"),
        )
    )


def _register_lookup_key(lookup, key, payload):
    existing = lookup.get(key)
    if existing is None or (_quote_complete(payload) and not _quote_complete(existing)):
        lookup[key] = payload


def _register_quote(lookup, row, *, stock_code="", stock_name=""):
    if not isinstance(row, dict):
        return

    change_pct = _extract_change_pct(row)
    if change_pct is None:
        return

    normalized_code = normalize_stock_code(stock_code or row.get("code", row.get("代码", "")))
    normalized_name = normalize_stock_name(stock_name or row.get("name", row.get("名称", "")))
    payload = dict(row)
    payload["change_pct"] = change_pct

    if normalized_code:
        _register_lookup_key(lookup, ("code", normalized_code), payload)
    if normalized_name:
        _register_lookup_key(lookup, ("name", normalized_name), payload)


def build_market_quote_lookup(
    *,
    stock_full_info=None,
    stocks_with_history=None,
    turnover_rank=None,
    lianban_data=None,
    zt_pool=None,
    dt_pool=None,
):
    lookup = {}

    for code, info in (stock_full_info or {}).items():
        _register_quote(lookup, info, stock_code=code)

    for source_rows in (
        stocks_with_history or [],
        turnover_rank or [],
        lianban_data or [],
        zt_pool or [],
        dt_pool or [],
    ):
        for row in source_rows:
            _register_quote(lookup, row)

    return lookup


def resolve_market_quote(quote_lookup, *, stock_code="", stock_name=""):
    normalized_code = normalize_stock_code(stock_code)
    if normalized_code:
        matched = (quote_lookup or {}).get(("code", normalized_code))
        if matched:
            return matched

    normalized_name = normalize_stock_name(stock_name)
    if normalized_name:
        matched = (quote_lookup or {}).get(("name", normalized_name))
        if matched:
            return matched

    return {}


def resolve_change_pct(quote_lookup, *, stock_code="", stock_name="", fallback=0.0):
    info = resolve_market_quote(quote_lookup, stock_code=stock_code, stock_name=stock_name)
    if info.get("change_pct") not in (None, ""):
        return float(info.get("change_pct"))

    try:
        return float(fallback)
    except (TypeError, ValueError):
        return 0.0
