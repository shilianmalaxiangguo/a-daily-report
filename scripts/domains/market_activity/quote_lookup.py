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

    if normalized_code and ("code", normalized_code) not in lookup:
        lookup[("code", normalized_code)] = payload
    if normalized_name and ("name", normalized_name) not in lookup:
        lookup[("name", normalized_name)] = payload


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
