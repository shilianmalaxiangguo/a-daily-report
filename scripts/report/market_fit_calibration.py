from __future__ import annotations


def _normalize_code(value):
    return str(value or "").strip()


def _normalize_sector(value):
    return str(value or "").strip()


_NON_SECTOR_LABELS = {
    "HS",
    "GEM",
    "STAR",
    "BJ",
    "SH",
    "SZ",
    "沪深",
    "创业板",
    "科创板",
    "北交所",
    "未知",
    "未归类",
    "其他",
    "其它",
    "-",
}


def _is_valid_sector_label(value):
    sector = _normalize_sector(value)
    return bool(sector and sector not in _NON_SECTOR_LABELS)


def _sample_sector(sample):
    if not isinstance(sample, dict):
        return ""
    sector = _normalize_sector(
        sample.get("sector")
        or sample.get("所属行业")
        or sample.get("board")
        or sample.get("industry")
    )
    return sector if _is_valid_sector_label(sector) else ""


def _sample_code(sample):
    if not isinstance(sample, dict):
        return ""
    return _normalize_code(sample.get("code") or sample.get("代码") or sample.get("stock_code"))


def _dominant_sector(strong_samples):
    counts = {}
    for sample in strong_samples:
        sector = _sample_sector(sample)
        if sector:
            counts[sector] = counts.get(sector, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def build_market_fit_calibration(strong_samples=None, current_mainline="", observation_pool=None):
    strong_samples = [item for item in list(strong_samples or []) if isinstance(item, dict)]
    observation_pool = [item for item in list(observation_pool or []) if isinstance(item, dict)]
    current_mainline = _normalize_sector(current_mainline)

    if not strong_samples:
        return {
            "fit_label": "数据不足",
            "evidence_text": "强势样本0只，先不放大结论",
            "cycle_note": "强势样本不足，先累计市场真实大涨样本。",
            "action_text": "先累计强势样本",
        }

    strong_count = len(strong_samples)
    mainline_hits = sum(1 for sample in strong_samples if current_mainline and _sample_sector(sample) == current_mainline)
    observation_codes = {_sample_code(item) for item in observation_pool if _sample_code(item)}
    observation_hits = sum(1 for sample in strong_samples if _sample_code(sample) in observation_codes)
    dominant_sector = _dominant_sector(strong_samples) or current_mainline or "强势方向"

    if current_mainline and mainline_hits == 0:
        fit_label = "主线偏差"
        action_text = "修正主线观察池"
    elif observation_hits == 0:
        fit_label = "主线有效，池子偏窄" if mainline_hits > 0 else "池子偏窄"
        action_text = "只扩主线内强票池" if mainline_hits > 0 else "先扩强势样本池"
    else:
        fit_label = "贴合"
        action_text = "继续保留主线内观察"

    return {
        "fit_label": fit_label,
        "evidence_text": f"强势样本{strong_count}只，主线命中{mainline_hits}只，观察池命中{observation_hits}只",
        "cycle_note": f"强势样本集中{dominant_sector}，主线成交额占比抬升时优先看承接。",
        "action_text": action_text,
    }
