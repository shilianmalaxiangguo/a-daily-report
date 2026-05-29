def fetch_hot_rank(limit=50):
    try:
        from ths_hot_stock import fetch_ths_hot_stock
    except ImportError:
        return []

    return fetch_ths_hot_stock(num=limit) or []
