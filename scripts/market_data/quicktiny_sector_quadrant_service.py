from __future__ import annotations

QUICKTINY_SECTOR_QUADRANT_PROVIDER = "quicktiny.sector_analysis_quadrant"
QUICKTINY_SECTOR_QUADRANT_URL = "https://stock.quicktiny.cn/api/sector-analysis/quadrant"

__all__ = [
    "QUICKTINY_SECTOR_QUADRANT_PROVIDER",
    "fetch_sector_quadrant_data",
]


def _safe_number(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _calculate_quality_score(sector):
    position_in_range = _safe_number((sector or {}).get("positionInRange"))
    recent_change = _safe_number((sector or {}).get("recentChange"))
    volume_ratio = _safe_number((sector or {}).get("volumeRatio"))

    score = 0
    if position_in_range >= 90:
        score += 30
    elif position_in_range >= 80:
        score += 25
    elif position_in_range >= 70:
        score += 15
    else:
        score += 5

    if recent_change >= 8:
        score += 40
    elif recent_change >= 5:
        score += 30
    elif recent_change >= 3:
        score += 20
    else:
        score += 10

    if volume_ratio >= 2.0:
        score += 30
    elif volume_ratio >= 1.5:
        score += 20
    elif volume_ratio >= 1.0:
        score += 10

    return score


def fetch_sector_quadrant_data(period=20, strength_period=3, *, request_get=None, print_fn=print):
    import requests

    request_get = request_get or requests.get
    try:
        url = f"{QUICKTINY_SECTOR_QUADRANT_URL}?source=dongcai_concept&period={period}&strengthPeriod={strength_period}"
        response = request_get(url, timeout=10)
        if response.status_code != 200:
            print_fn(f"   ⚠️ 板块四象限API返回状态码: {response.status_code}")
            return None

        data = response.json()
        if not data.get("quadrants"):
            print_fn("   ⚠️ 板块四象限数据格式异常")
            return None

        quadrants = data["quadrants"]
        high_strong = quadrants.get("highStrong", [])
        for sector in high_strong:
            sector["quality_score"] = _calculate_quality_score(sector)

        tier1 = [item for item in high_strong if item["quality_score"] >= 80]
        tier2 = [item for item in high_strong if 60 <= item["quality_score"] < 80]
        tier3 = [item for item in high_strong if 40 <= item["quality_score"] < 60]
        tier4 = [item for item in high_strong if item["quality_score"] < 40]

        return {
            "provider": QUICKTINY_SECTOR_QUADRANT_PROVIDER,
            "quadrants": quadrants,
            "high_strong_analysis": {
                "total": len(high_strong),
                "tier1_best": sorted(tier1, key=lambda x: x["quality_score"], reverse=True),
                "tier2_good": sorted(tier2, key=lambda x: x["quality_score"], reverse=True),
                "tier3_normal": sorted(tier3, key=lambda x: x["quality_score"], reverse=True),
                "tier4_edge": sorted(tier4, key=lambda x: x["quality_score"], reverse=True),
                "tier1_count": len(tier1),
                "tier2_count": len(tier2),
                "tier3_count": len(tier3),
                "tier4_count": len(tier4),
            },
        }
    except Exception as error:
        print_fn(f"   ⚠️ 板块四象限数据获取失败: {error}")
        return None
