import datetime
from copy import deepcopy


def normalized_replay_role_date(value):
    text = str(value or "").strip()[:10]
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return ""


def replay_role_date_after(value, target_date):
    normalized = normalized_replay_role_date(value)
    target = normalized_replay_role_date(target_date)
    return bool(normalized and target and normalized > target)


def _tracking_memory_item_is_after_target(item, target_date):
    if not isinstance(item, dict):
        return False
    for key in (
        "first_seen_date",
        "last_seen_date",
        "mention_trade_date",
        "trade_date",
        "report_date",
        "source_date",
    ):
        if replay_role_date_after(item.get(key), target_date):
            return True
    return False


def _target_date_tracking_memory_status(status, target_date):
    if not isinstance(status, dict):
        return status
    updated = deepcopy(status)
    for key, value in list(updated.items()):
        if not isinstance(value, list):
            continue
        updated[key] = [
            deepcopy(item)
            for item in value
            if not isinstance(item, dict)
            or not _tracking_memory_item_is_after_target(item, target_date)
        ]
    if isinstance(updated.get("today_validated_items"), list) and isinstance(
        updated.get("today_tentative_items"),
        list,
    ):
        updated["today_seen_count"] = len(updated["today_validated_items"]) + len(
            updated["today_tentative_items"]
        )
    return updated


def isolate_replay_named_role_fields(value, target_date, visited=None):
    if visited is None:
        visited = set()
    if not isinstance(value, (dict, list)):
        return value
    marker = id(value)
    if marker in visited:
        return value
    visited.add(marker)
    if isinstance(value, list):
        for item in value:
            isolate_replay_named_role_fields(item, target_date, visited)
        return value
    for key, nested in list(value.items()):
        if key == "tracking_memory_status":
            value[key] = _target_date_tracking_memory_status(nested, target_date)
            continue
        if key in {
            "recent_extreme_conviction_mentions",
            "recent_extreme_conviction_mentions_for_review",
        } and isinstance(nested, list):
            value[key] = [
                deepcopy(item)
                for item in nested
                if not isinstance(item, dict)
                or not replay_role_date_after(
                    item.get("mention_trade_date"),
                    target_date,
                )
            ]
            continue
        isolate_replay_named_role_fields(nested, target_date, visited)
    return value
