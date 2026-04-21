def fetch_hot_rank(limit=30):
    from ths_hot_stock import fetch_ths_hot_stock

    return fetch_ths_hot_stock(num=limit) or []
