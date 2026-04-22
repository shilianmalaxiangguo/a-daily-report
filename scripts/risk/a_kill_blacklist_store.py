import datetime
import json
import os

import daily_report_analysis_utils as analysis_utils


def _normalize_stock_code(code):
    code = analysis_utils.normalize_stock_code(code)
    return str(code or "").replace("SZ", "").replace("SH", "")


def _get_a_kill_blacklist_path(path=None):
    if path:
        return path
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "a_kill_blacklist.json")


def load_a_kill_blacklist(path=None):
    path = _get_a_kill_blacklist_path(path)
    if not os.path.exists(path):
        return {"updated_at": "", "cooldown_days": 25, "records": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("blacklist json must be dict")
        data.setdefault("updated_at", "")
        data.setdefault("cooldown_days", 25)
        data.setdefault("records", [])
        return data
    except Exception:
        return {"updated_at": "", "cooldown_days": 25, "records": []}


def save_a_kill_blacklist(blacklist_data, path=None):
    path = _get_a_kill_blacklist_path(path)
    blacklist_data["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blacklist_data, f, ensure_ascii=False, indent=2)
    return path


def get_active_a_kill_records(target_date, path=None):
    blacklist_data = load_a_kill_blacklist(path=path)
    cooldown_days = int(blacklist_data.get("cooldown_days", 25) or 25)
    try:
        target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
    except Exception:
        return []
    active_records = []
    for record in blacklist_data.get("records", []):
        a_kill_date = record.get("a_kill_date", "")
        if not a_kill_date:
            continue
        try:
            record_dt = datetime.datetime.strptime(a_kill_date, "%Y-%m-%d").date()
        except Exception:
            continue
        days_passed = (target_dt - record_dt).days
        if 0 <= days_passed < cooldown_days:
            enriched = dict(record)
            enriched["days_passed"] = days_passed
            enriched["remaining_days"] = cooldown_days - days_passed
            active_records.append(enriched)
    active_records.sort(key=lambda x: (x.get("remaining_days", 999), x.get("name", "")))
    return active_records


def update_a_kill_blacklist(target_date, stocks, sector_name="", path=None):
    if not stocks:
        return []
    blacklist_data = load_a_kill_blacklist(path=path)
    records = blacklist_data.get("records", [])
    existing_index = {}
    for idx, record in enumerate(records):
        key = ((record.get("code") or "").strip(), (record.get("name") or "").strip())
        existing_index[key] = idx
    added_or_updated = []
    for stock in stocks:
        name = (stock.get("name") or stock.get("名称") or "").strip()
        code = _normalize_stock_code(stock.get("code") or stock.get("代码") or "").strip()
        if not name and not code:
            continue
        item = {
            "name": name,
            "code": code,
            "sector": sector_name or stock.get("sector", ""),
            "a_kill_date": target_date,
            "ban_until": (datetime.datetime.strptime(target_date, "%Y-%m-%d").date() + datetime.timedelta(days=25)).strftime("%Y-%m-%d"),
        }
        key = (code, name)
        if key in existing_index:
            records[existing_index[key]].update(item)
        else:
            records.append(item)
            existing_index[key] = len(records) - 1
        added_or_updated.append(item)
    blacklist_data["records"] = records
    save_a_kill_blacklist(blacklist_data, path=path)
    return added_or_updated


def is_stock_in_a_kill_cooldown(stock, active_records):
    stock_code = _normalize_stock_code(stock.get("code", "")).strip()
    stock_name = (stock.get("name") or "").strip()
    for record in active_records:
        record_code = _normalize_stock_code(record.get("code", "")).strip()
        record_name = (record.get("name") or "").strip()
        if stock_code and record_code and stock_code == record_code:
            return True, record
        if stock_name and record_name and stock_name == record_name:
            return True, record
    return False, None
