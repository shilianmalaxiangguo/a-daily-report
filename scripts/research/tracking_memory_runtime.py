from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import daily_report_analysis_utils as analysis_utils

try:
    from storage.database_service import DatabaseService
except Exception:  # pragma: no cover - optional runtime path
    DatabaseService = None

__all__ = ["refresh_tracking_memory"]

TRACKING_MEMORY_KEEP_DAYS = 20
TRACKING_MEMORY_TENTATIVE_EXPIRE_DAYS = 5
TRACKING_MEMORY_RECALL_KEEP_DAYS = 45
TRACKING_MEMORY_MAX_ITEMS = 40
TRACKING_MEMORY_PROMOTE_CONFIRMATIONS = 2
INACTIVE_MEMORY_STATUSES = {"inactive_failed", "inactive_recall"}
HIGH_VALUE_MEMORY_KEYWORDS = (
    "首波",
    "龙头",
    "龙一",
    "锚定龙",
    "资金记住",
    "连板已被资金记住",
    "高惯性",
)


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _tracking_memory_path():
    return Path(__file__).resolve().parents[2] / "data" / "tracking_memory.json"


def _safe_parse_report_date(date_text):
    try:
        return datetime.datetime.strptime(str(date_text), "%Y-%m-%d").date()
    except Exception:
        return None


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_source_set(value):
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if item}
    if value:
        return {str(value)}
    return set()


def _is_high_value_memory_item(item):
    item = item or {}
    if item.get("status") == "validated":
        return True

    sources = _as_source_set(item.get("sources"))
    evidence_score = _safe_float(item.get("evidence_score"), 0)
    confirmations = _safe_int(item.get("confirmations"), 0)
    reason_text = " / ".join(
        str(item.get(key, "") or "")
        for key in ("last_reason", "remember_reason", "inactive_reason")
    )

    if confirmations >= 2 or evidence_score >= 5:
        return True
    if "leader_memory" in sources and ("abnormal_watch" in sources or "watchlist" in sources):
        return True
    return any(keyword in reason_text for keyword in HIGH_VALUE_MEMORY_KEYWORDS)


def _build_inactive_memory_item(
    previous,
    entry,
    *,
    target_date,
    status,
    inactive_reason,
    follow_state="",
    evidence_score=None,
    failures=None,
    appearances=None,
    days_since_seen=None,
):
    previous = previous or {}
    entry = entry or {}
    code = entry.get("code") or previous.get("code", "")
    reasons = [str(reason) for reason in entry.get("reasons", []) if reason]
    previous_reason = previous.get("last_reason", "")
    last_reason_parts = [part for part in [previous_reason, *reasons] if part]

    item = {
        **previous,
        "name": entry.get("name") or previous.get("name", ""),
        "code": code,
        "sector": entry.get("sector") or previous.get("sector", ""),
        "status": status,
        "first_seen_date": previous.get("first_seen_date", target_date),
        "last_seen_date": entry.get("last_seen_date") or previous.get("last_seen_date", target_date),
        "confirmations": _safe_int(previous.get("confirmations"), 0),
        "failures": _safe_int(previous.get("failures"), 0) if failures is None else failures,
        "appearances": _safe_int(previous.get("appearances"), 0) if appearances is None else appearances,
        "sources": sorted(entry.get("sources", []) or previous.get("sources", [])),
        "last_reason": " / ".join(last_reason_parts[:4]),
        "follow_state": follow_state or entry.get("follow_state", "") or previous.get("follow_state", ""),
        "evidence_score": _safe_float(previous.get("evidence_score"), 0) if evidence_score is None else evidence_score,
        "inactive_since_date": target_date,
        "inactive_reason": inactive_reason,
    }
    if days_since_seen is not None:
        item["days_since_seen"] = days_since_seen
    return item


def _load_tracking_memory_state():
    path = _tracking_memory_path()
    if not path.exists():
        return {"items": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("items", [])
            return data
    except Exception:
        pass
    return {"items": []}


def _save_tracking_memory_state(state):
    path = _tracking_memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _postgres_database_configured():
    database_url = (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    return database_url.startswith(("postgres://", "postgresql://"))


def _postgres_only_runtime():
    return os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1"


def _configured_tracking_memory_store():
    service_cls = globals().get("DatabaseService")
    postgres_required = _postgres_only_runtime() or _postgres_database_configured()
    if not postgres_required:
        return None
    if _postgres_only_runtime() and not _postgres_database_configured():
        raise RuntimeError("PostgreSQL-only tracking memory storage requires PostgreSQL")
    if service_cls is None:
        raise RuntimeError("PostgreSQL tracking memory storage requires DatabaseService")
    service = service_cls.from_environment()
    if not callable(getattr(service, "is_postgres_backed", None)) or not service.is_postgres_backed():
        raise RuntimeError("PostgreSQL-only tracking memory storage requires PostgreSQL")
    if not callable(getattr(service, "load_tracking_memory_state", None)):
        raise RuntimeError("PostgreSQL tracking memory reader is unavailable")
    if not callable(getattr(service, "save_tracking_memory_state", None)):
        raise RuntimeError("PostgreSQL tracking memory writer is unavailable")
    return service


def refresh_tracking_memory(
    target_date,
    watchlist,
    leader_memory_bank,
    abnormal_watch_pool,
    stock_meta_map=None,
    *,
    load_state=None,
    save_state=None,
    normalize_code=None,
    safe_float_fn=None,
    keep_days=TRACKING_MEMORY_KEEP_DAYS,
    tentative_expire_days=TRACKING_MEMORY_TENTATIVE_EXPIRE_DAYS,
    recall_keep_days=TRACKING_MEMORY_RECALL_KEEP_DAYS,
    max_items=TRACKING_MEMORY_MAX_ITEMS,
    promote_confirmations=TRACKING_MEMORY_PROMOTE_CONFIRMATIONS,
):
    """跨日维护跟踪记忆簿。"""
    if load_state is None and save_state is None:
        store = _configured_tracking_memory_store()
        if store is not None:
            load_state = store.load_tracking_memory_state
            save_state = store.save_tracking_memory_state
    load_state = load_state or _load_tracking_memory_state
    save_state = save_state or _save_tracking_memory_state
    normalize_code = normalize_code or analysis_utils.normalize_stock_code
    safe_float_fn = safe_float_fn or _safe_float

    state = load_state() or {"items": []}
    previous_items = state.get("items", []) if isinstance(state, dict) else []
    previous_map = {}
    for item in previous_items:
        code = normalize_code(item.get("code", ""))
        if code:
            previous_map[code] = item

    today_entries = {}
    follow_state_rank = {
        "已经转弱": 4,
        "跌不下去": 3,
        "缩量消化": 2,
        "新异动待观察": 1,
        "": 0,
    }

    def register_entry(stock, source, raw_score=0, reason="", follow_state=""):
        code = normalize_code(stock.get("code", stock.get("代码", "")))
        if not code:
            return

        meta = (stock_meta_map or {}).get(code, {})
        entry = today_entries.setdefault(
            code,
            {
                "code": code,
                "name": stock.get("name", stock.get("名称", "")) or meta.get("name", ""),
                "sector": stock.get("sector", stock.get("所属板块", "")) or meta.get("sector", ""),
                "sources": set(),
                "reasons": [],
                "raw_scores": [],
                "follow_state": "",
            },
        )
        entry["name"] = entry.get("name") or stock.get("name", stock.get("名称", "")) or meta.get("name", "")
        entry["sector"] = entry.get("sector") or stock.get("sector", stock.get("所属板块", "")) or meta.get("sector", "")
        entry["sources"].add(source)
        if reason:
            entry["reasons"].append(str(reason))
        if raw_score:
            entry["raw_scores"].append(safe_float_fn(raw_score, 0))
        if follow_state_rank.get(str(follow_state), 0) > follow_state_rank.get(entry.get("follow_state", ""), 0):
            entry["follow_state"] = str(follow_state)

    for item in leader_memory_bank or []:
        register_entry(
            item,
            source="leader_memory",
            raw_score=item.get("remember_score", 0),
            reason=item.get("remember_reason", ""),
        )

    for rank, item in enumerate(watchlist or [], 1):
        if rank > 12:
            break
        register_entry(
            item,
            source="watchlist",
            raw_score=max(0, 30 - rank),
            reason=item.get("tomorrow_expectation", "") or item.get("core_logic", ""),
        )

    for item in abnormal_watch_pool or []:
        register_entry(
            item,
            source="abnormal_watch",
            raw_score=item.get("abnormal_score", 0),
            reason=item.get("action_rule", ""),
            follow_state=item.get("follow_state", ""),
        )

    today_date_obj = _safe_parse_report_date(target_date)
    new_items = []
    promoted_items = []
    dropped_items = []
    inactive_items = []
    reactivated_items = []
    kept_items = []
    today_validated_items = []
    today_tentative_items = []

    for code, entry in today_entries.items():
        previous = previous_map.get(code, {})
        previous_status = previous.get("status", "tentative")
        same_day_refresh = previous.get("last_seen_date") == target_date
        confirmations = int(previous.get("confirmations", 0) or 0)
        failures = int(previous.get("failures", 0) or 0)
        appearances = int(previous.get("appearances", 0) or 0)
        if not same_day_refresh:
            appearances += 1

        evidence_score = 0
        if "leader_memory" in entry["sources"]:
            evidence_score += 2
        if "watchlist" in entry["sources"]:
            evidence_score += 1
        if "abnormal_watch" in entry["sources"]:
            evidence_score += 1
        if len(entry["sources"]) >= 2:
            evidence_score += 1
        if max(entry["raw_scores"] or [0]) >= 70:
            evidence_score += 1

        follow_state = entry.get("follow_state", "")
        if follow_state == "跌不下去":
            evidence_score += 2
        elif follow_state == "缩量消化":
            evidence_score += 1
        elif follow_state == "已经转弱":
            evidence_score -= 4

        if follow_state == "已经转弱":
            verdict = "fail"
            if not same_day_refresh:
                failures += 1
        elif evidence_score >= 4:
            verdict = "confirm"
            if not same_day_refresh:
                confirmations += 1
                failures = max(0, failures - 1)
        else:
            verdict = "tentative"

        if verdict == "fail":
            if previous and _is_high_value_memory_item(previous):
                inactive_item = _build_inactive_memory_item(
                    previous,
                    entry,
                    target_date=target_date,
                    status="inactive_failed",
                    inactive_reason="今日已经转弱，取消买入资格，但旧强势样本保留为冷却回看",
                    follow_state=follow_state,
                    evidence_score=evidence_score,
                    failures=failures,
                    appearances=appearances,
                )
                kept_items.append(inactive_item)
                inactive_items.append(inactive_item)
            else:
                dropped_items.append(
                    {
                        "name": entry.get("name", ""),
                        "code": code,
                        "reason": "今日已经转弱，普通旧记忆失效",
                    }
                )
            continue

        was_inactive = previous_status in INACTIVE_MEMORY_STATUSES
        status = "validated" if previous_status == "validated" or confirmations >= promote_confirmations else "tentative"
        last_reason = " / ".join(entry.get("reasons", [])[:3])
        if was_inactive:
            last_reason = f"旧强势样本再激活 / {last_reason}".strip(" /")
        memory_item = {
            "name": entry.get("name", ""),
            "code": code,
            "sector": entry.get("sector", ""),
            "status": status,
            "first_seen_date": previous.get("first_seen_date", target_date),
            "last_seen_date": target_date,
            "confirmations": confirmations,
            "failures": failures,
            "appearances": appearances,
            "sources": sorted(entry.get("sources", [])),
            "last_reason": last_reason,
            "follow_state": follow_state,
            "evidence_score": evidence_score,
        }
        if was_inactive:
            memory_item["reactivated_from_status"] = previous_status
            memory_item["inactive_reason"] = previous.get("inactive_reason", "")
        kept_items.append(memory_item)

        if code not in previous_map:
            new_items.append(memory_item)
        elif was_inactive:
            reactivated_items.append(memory_item)
        elif previous_status != "validated" and status == "validated":
            promoted_items.append(memory_item)

        if status == "validated":
            today_validated_items.append(memory_item)
        else:
            today_tentative_items.append(memory_item)

    for code, previous in previous_map.items():
        if code in today_entries:
            continue

        last_seen_obj = _safe_parse_report_date(previous.get("last_seen_date", ""))
        days_missing = 0
        if today_date_obj and last_seen_obj:
            days_missing = max((today_date_obj - last_seen_obj).days, 0)

        previous_status = previous.get("status", "tentative")
        previous_is_inactive = previous_status in INACTIVE_MEMORY_STATUSES
        should_drop = (
            (previous_status == "tentative" and days_missing > tentative_expire_days)
            or (previous_is_inactive and days_missing > recall_keep_days)
            or days_missing > keep_days
        )
        if should_drop:
            if not previous_is_inactive and _is_high_value_memory_item(previous) and days_missing <= recall_keep_days:
                inactive_item = _build_inactive_memory_item(
                    previous,
                    {},
                    target_date=target_date,
                    status="inactive_recall",
                    inactive_reason="连续多日未再次入池，转入冷却回看；不提供买入资格，只保留再激活线索",
                    days_since_seen=days_missing,
                )
                kept_items.append(inactive_item)
                inactive_items.append(inactive_item)
                continue
            dropped_items.append(
                {
                    "name": previous.get("name", ""),
                    "code": code,
                    "reason": "连续多日未再次进入今日候选，自动清除",
                }
            )
            continue

        kept_previous = {**previous, "days_since_seen": days_missing}
        kept_items.append(kept_previous)
        if previous_is_inactive:
            inactive_items.append(kept_previous)

    kept_items.sort(
        key=lambda item: (
            1 if item.get("status") == "validated" else 0,
            item.get("confirmations", 0),
            item.get("evidence_score", 0),
            item.get("last_seen_date", ""),
        ),
        reverse=True,
    )
    kept_items = kept_items[:max_items]

    save_state({"updated_at": target_date, "items": kept_items})

    validated_items = [item for item in kept_items if item.get("status") == "validated"]
    tentative_items = [item for item in kept_items if item.get("status") == "tentative"]
    return {
        "validated_items": validated_items,
        "tentative_items": tentative_items,
        "inactive_items": inactive_items,
        "today_validated_items": today_validated_items,
        "today_tentative_items": today_tentative_items,
        "new_items": new_items,
        "promoted_items": promoted_items,
        "reactivated_items": reactivated_items,
        "dropped_items": dropped_items,
        "total_items": kept_items,
        "today_seen_count": len(today_entries),
    }
