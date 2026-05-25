from __future__ import annotations

__all__ = ["build_grouped_advantage_score"]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value, low=None, high=None):
    numeric = _safe_float(value)
    if low is not None:
        numeric = max(_safe_float(low), numeric)
    if high is not None:
        numeric = min(_safe_float(high), numeric)
    return numeric


def _normalized_point(point):
    point = dict(point or {})
    group = str(point.get("group") or point.get("bucket") or "misc").strip() or "misc"
    raw_score = _safe_float(point.get("score", 0))
    capped_score = raw_score
    if point.get("cap") is not None:
        capped_score = _clamp(capped_score, high=point.get("cap"))
    return {
        "group": group,
        "label": str(point.get("label") or group).strip() or group,
        "score": capped_score,
        "raw_score": raw_score,
        "source": str(point.get("source") or "").strip(),
    }


def build_grouped_advantage_score(points, group_caps=None):
    """Count only the strongest advantage inside each source group.

    Repeated evidence still stays available for explanation, but it does not
    add extra ranking power.
    """
    group_caps = dict(group_caps or {})
    selected_by_group = {}
    suppressed_points = []

    for raw_point in points or []:
        point = _normalized_point(raw_point)
        group = point["group"]
        if group in group_caps:
            point["score"] = _clamp(point["score"], high=group_caps[group])
        current = selected_by_group.get(group)
        if current is None or point["score"] > current["score"]:
            if current is not None:
                suppressed_points.append(current)
            selected_by_group[group] = point
        else:
            suppressed_points.append(point)

    selected_points = list(selected_by_group.values())
    group_scores = {point["group"]: point["score"] for point in selected_points}
    total_score = sum(group_scores.values())
    return {
        "total_score": total_score,
        "group_scores": group_scores,
        "selected_points": selected_points,
        "suppressed_points": suppressed_points,
        "repeated_advantage_count": len(suppressed_points),
    }
