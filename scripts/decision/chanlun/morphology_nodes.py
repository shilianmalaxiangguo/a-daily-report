from __future__ import annotations


def _is_contained(prev, curr):
    return (
        float(curr["high"]) <= float(prev["high"])
        and float(curr["low"]) >= float(prev["low"])
    ) or (
        float(curr["high"]) >= float(prev["high"])
        and float(curr["low"]) <= float(prev["low"])
    )


def merge_inclusion_bars(rows):
    merged = []
    for row in list(rows or []):
        item = dict(row)
        item.setdefault("source_bar_count", 1)
        item.setdefault("source_dates", [item.get("date")])
        item["rule_tier"] = "original_rule"

        if merged and _is_contained(merged[-1], item):
            prev = merged[-1]
            prev["high"] = max(float(prev["high"]), float(item["high"]))
            prev["low"] = min(float(prev["low"]), float(item["low"]))
            prev["close"] = item.get("close", prev.get("close"))
            prev["date"] = item.get("date", prev.get("date"))
            prev["source_bar_count"] = int(prev.get("source_bar_count", 1)) + 1
            prev["source_dates"] = list(prev.get("source_dates") or []) + [item.get("date")]
        else:
            merged.append(item)
    return merged


def detect_fractals(processed_bars):
    bars = list(processed_bars or [])
    fractals = []

    for index in range(1, len(bars) - 1):
        prev_bar = bars[index - 1]
        bar = bars[index]
        next_bar = bars[index + 1]

        if (
            float(bar["high"]) > float(prev_bar["high"])
            and float(bar["high"]) > float(next_bar["high"])
            and float(bar["low"]) > float(prev_bar["low"])
            and float(bar["low"]) > float(next_bar["low"])
        ):
            fractals.append(
                {
                    "fractal_id": f"fractal_{len(fractals) + 1}",
                    "fractal_type": "top",
                    "index": index,
                    "date": bar.get("date"),
                    "price": float(bar["high"]),
                    "source": "processed_bars",
                    "rule_tier": "original_rule",
                }
            )

        if (
            float(bar["low"]) < float(prev_bar["low"])
            and float(bar["low"]) < float(next_bar["low"])
            and float(bar["high"]) < float(prev_bar["high"])
            and float(bar["high"]) < float(next_bar["high"])
        ):
            fractals.append(
                {
                    "fractal_id": f"fractal_{len(fractals) + 1}",
                    "fractal_type": "bottom",
                    "index": index,
                    "date": bar.get("date"),
                    "price": float(bar["low"]),
                    "source": "processed_bars",
                    "rule_tier": "original_rule",
                }
            )

    return fractals


def _prefer_fractal(existing, incoming):
    if existing["fractal_type"] == "top":
        return incoming if float(incoming["price"]) > float(existing["price"]) else existing
    return incoming if float(incoming["price"]) < float(existing["price"]) else existing


def build_strokes(fractals):
    selected = []
    for fractal in list(fractals or []):
        item = dict(fractal)
        if selected and selected[-1]["fractal_type"] == item["fractal_type"]:
            selected[-1] = _prefer_fractal(selected[-1], item)
        else:
            selected.append(item)

    strokes = []
    for start, end in zip(selected, selected[1:]):
        direction = (
            "up"
            if start["fractal_type"] == "bottom" and end["fractal_type"] == "top"
            else "down"
        )
        strokes.append(
            {
                "stroke_id": f"stroke_{len(strokes) + 1}",
                "start_date": start.get("date"),
                "end_date": end.get("date"),
                "start_index": int(start.get("index", 0)),
                "end_index": int(end.get("index", 0)),
                "direction": direction,
                "fractal_ids": [start.get("fractal_id"), end.get("fractal_id")],
                "rule_tier": "derived_contract",
                "status": "completed_stroke",
            }
        )

    return strokes
