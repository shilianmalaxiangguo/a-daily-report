from __future__ import annotations


def _normalize_type(item, index):
    high = float(item["high"])
    low = float(item["low"])
    if high <= low or item.get("status", "completed_trend_type") != "completed_trend_type":
        return None
    return {
        **dict(item),
        "trend_type_id": item.get("trend_type_id") or f"trend_{index + 1}",
        "high": high,
        "low": low,
    }


def _overlap(first_three):
    zg = min(item["high"] for item in first_three)
    zd = max(item["low"] for item in first_three)
    if zg <= zd:
        return None
    return {"ZG": float(zg), "ZD": float(zd)}


def _connector(units, sequence_id, *, bridge=False):
    return {
        "segment_type": "connector",
        "connector_id": f"connector_{sequence_id}",
        "role": "connector_move",
        "trend_type_ids": [item["trend_type_id"] for item in units],
        "rule_tier": "diagnostic_heuristic" if bridge else "derived_contract",
        "reason": "platform visual bridge" if bridge else "no three completed trend types overlap",
    }


def _platform(units, zone, sequence_id, level_id):
    return {
        "segment_type": "zhongshu",
        "role": "inside_zhongshu",
        "zhongshu_id": f"{level_id}_zhongshu_{sequence_id}",
        "level_id": level_id,
        "child_trend_type_ids": [item["trend_type_id"] for item in units[:3]],
        "trend_type_ids": [item["trend_type_id"] for item in units],
        "ZG": zone["ZG"],
        "ZD": zone["ZD"],
        "status": "confirmed",
        "rule_tier": "original_rule",
    }


def identify_platforms_from_trend_types(trend_types, *, level_id):
    units = []
    for index, item in enumerate(list(trend_types or [])):
        normalized = _normalize_type(item, index)
        if normalized is not None:
            units.append(normalized)

    segments = []
    platforms = []
    connector_units = []
    index = 0
    connector_count = 0
    platform_count = 0

    while index <= len(units) - 3:
        zone = _overlap(units[index : index + 3])
        if zone is None:
            connector_units.append(units[index])
            index += 1
            continue

        if connector_units:
            connector_count += 1
            segments.append(_connector(connector_units, connector_count))
            connector_units = []
        elif segments and segments[-1]["segment_type"] == "zhongshu":
            connector_count += 1
            segments.append(_connector([units[index]], connector_count, bridge=True))

        platform_count += 1
        platform = _platform(units[index : index + 3], zone, platform_count, level_id)
        segments.append(platform)
        platforms.append(platform)
        index += 3

    if index < len(units):
        connector_units.extend(units[index:])
    if connector_units:
        connector_count += 1
        segments.append(_connector(connector_units, connector_count))

    return segments, platforms
