"""Small shared helpers for frozen market and strategy artifacts."""
import hashlib
import json


def evidence_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                                    allow_nan=False).encode()).hexdigest()


def price_rows(value, day):
    text = value['prices'].get(day)
    if not text:
        return []
    rows = []
    for item in text.split(';'):
        index, close, previous, opened, amount = item.split(',')
        rows.append((int(index), float(close), float(previous),
                     float(opened) if opened else None, float(amount) if amount else None))
    return rows


def eligible_indices(value):
    """Exclude target-day ST stocks and stocks listed inside the frozen data span."""
    first = value['trade_dates'][0]
    st = set(value.get('st_codes') or [])
    profile = value['profile']
    eligible = []
    for index, code in enumerate(value['codes']):
        name = profile['names'][index]
        listed = profile['list_dates'][index]
        is_st = code in st if value.get('st_codes') is not None else name.upper().startswith(('ST', '*ST'))
        if not is_st and listed and listed < first:
            eligible.append(index)
    return eligible
