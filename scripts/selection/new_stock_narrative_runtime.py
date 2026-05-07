from __future__ import annotations

import datetime as _dt
import re

try:
    import daily_report_analysis_utils as analysis_utils
except Exception:  # pragma: no cover - defensive fallback for isolated imports
    analysis_utils = None

__all__ = [
    "build_new_stock_research_pool",
    "score_new_stock_narrative",
    "should_upgrade_new_stock_candidate",
]

UPGRADE_THRESHOLD = 72
ALLOWED_LISTING_WINDOWS = {
    "pre_alert_t2",
    "tomorrow_listing",
    "today_listing",
    "recently_listed",
    "upcoming_soon",
}
FACTOR_KEYS = (
    "listing_window_score",
    "mainline_match_score",
    "narrative_association_score",
    "market_emotion_score",
    "board_resonance_score",
    "trade_value_score",
)
DIRECT_EXECUTION_PERMISSION_FIELDS = {
    "direct_execution_permission",
    "execution_permission",
    "execution_permission_label",
    "permission_label",
    "can_execute",
    "can_new_entry",
    "allow_execute",
    "execution_entry_permission",
}

LISTING_WINDOW_SCORE = {
    "tomorrow_listing": 18,
    "pre_alert_t2": 17,
    "today_listing": 15,
    "recently_listed": 12,
    "upcoming_soon": 8,
}
PRE_LISTING_ACTION_BY_WINDOW = {
    "pre_alert_t2": "prepare_clear_cash",
    "tomorrow_listing": "focus_tomorrow_battle",
    "today_listing": "live_open_confirm",
    "recently_listed": "post_listing_track",
    "upcoming_soon": "none",
    "outside_window": "none",
}


def _safe_float(value, default=0.0):
    if value in (None, ""):
        return float(default)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return float(default)


def _clamp(value, low, high):
    return max(low, min(high, int(round(value))))


def _normalize_code(value):
    text = str(value or "").strip().upper()
    text = text.replace(".SZ", "").replace(".SH", "").replace(".SS", "").replace(".BJ", "")
    for prefix in ("SZ", "SH", "BJ"):
        if text.startswith(prefix):
            text = text[2:]
            break
    match = re.search(r"\d{6}", text)
    return match.group(0) if match else ""


def _normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_name(value):
    text = _normalize_text(value).replace(" ", "")
    if text[:1] in {"N", "C"} and len(text) > 1:
        return text[1:]
    return text


def _split_text_terms(value):
    if isinstance(value, dict):
        terms = []
        for item in value.values():
            terms.extend(_split_text_terms(item))
        return terms
    if isinstance(value, (list, tuple, set)):
        terms = []
        for item in value:
            terms.extend(_split_text_terms(item))
        return terms
    text = _normalize_text(value)
    if not text:
        return []
    pieces = [part.strip() for part in re.split(r"[,，、/|;；]+", text) if part.strip()]
    return pieces or [text]


def _unique_terms(values):
    seen = set()
    result = []
    for value in values or []:
        text = _normalize_text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _parse_date(value):
    text = _normalize_text(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if not match:
        return None
    try:
        return _dt.datetime.strptime(match.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


def _market_from_code(code):
    code = _normalize_code(code)
    if code.startswith(("6", "5", "9")):
        return "sh"
    if code.startswith(("8", "4")) or code.startswith("92"):
        return "bj"
    return "sz" if code else ""


def _sector_name_matches(left, right):
    if analysis_utils is not None:
        return analysis_utils.sector_name_matches(left, right)
    left = str(left or "").strip()
    right = str(right or "").strip()
    return bool(left and right and (left == right or left in right or right in left))


def _name_matches(left, right):
    left_name = _normalize_name(left)
    right_name = _normalize_name(right)
    return bool(left_name and right_name and left_name == right_name)


def _lookup_profile(record, context):
    profiles = (context or {}).get("new_stock_profiles") or {}
    code = _normalize_code((record or {}).get("code") or (record or {}).get("stock_code"))
    name = _normalize_text((record or {}).get("name"))

    if isinstance(profiles, dict):
        direct_keys = [key for key in (code, name, _normalize_name(name)) if key]
        for key in direct_keys:
            profile = profiles.get(key)
            if isinstance(profile, dict):
                return profile
        for key, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            if (code and _normalize_code(key) == code) or _name_matches(key, name):
                return profile

    if isinstance(profiles, (list, tuple)):
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            if code and _normalize_code(profile.get("code")) == code:
                return profile
            if _name_matches(profile.get("name"), name):
                return profile

    return {}


def _merge_profile(record, context):
    merged = dict(record or {})
    profile = _lookup_profile(merged, context)
    list_fields = {
        "concept_tags",
        "concepts",
        "concept_list",
        "sector_tags",
        "customer_anchors",
        "narrative_anchors",
    }

    for key, value in (profile or {}).items():
        if key in list_fields:
            merged[key] = _unique_terms(_split_text_terms(merged.get(key)) + _split_text_terms(value))
        elif merged.get(key) in (None, "", [], {}):
            merged[key] = value

    concepts = []
    for key in ("concept_tags", "concepts", "concept_list", "sector_tags"):
        concepts.extend(_split_text_terms(merged.get(key)))
    if concepts:
        merged["concept_tags"] = _unique_terms(concepts)

    anchors = []
    for key in ("customer_anchors", "narrative_anchors"):
        anchors.extend(_split_text_terms(merged.get(key)))
    if anchors:
        merged["customer_anchors"] = _unique_terms(anchors)

    if not merged.get("sector"):
        merged["sector"] = merged.get("sector_name") or merged.get("industry") or ""
    if not merged.get("market"):
        merged["market"] = _market_from_code(merged.get("code"))

    code = _normalize_code(merged.get("code") or merged.get("stock_code"))
    if code:
        merged["code"] = code

    for key in DIRECT_EXECUTION_PERMISSION_FIELDS:
        merged.pop(key, None)

    return merged


def _resolve_listing_timing(record, target_date):
    listing_date = _parse_date((record or {}).get("listing_date"))
    target = _parse_date(target_date)
    days_to_listing = None
    days_since_listing = None

    if listing_date and target:
        days_to_listing = (listing_date - target).days
        days_since_listing = (target - listing_date).days
    elif (record or {}).get("days_to_listing") not in (None, ""):
        try:
            days_to_listing = int((record or {}).get("days_to_listing"))
            days_since_listing = -days_to_listing
        except (TypeError, ValueError):
            days_to_listing = None

    if days_to_listing == 2:
        window = "pre_alert_t2"
    elif days_to_listing == 1:
        window = "tomorrow_listing"
    elif days_to_listing == 0:
        window = "today_listing"
    elif days_to_listing is not None and -5 <= days_to_listing <= -1:
        window = "recently_listed"
    elif days_to_listing is not None and 3 <= days_to_listing <= 7:
        window = "upcoming_soon"
    else:
        window = _normalize_text((record or {}).get("listing_window")) or "outside_window"

    return {
        "listing_window": window,
        "pre_listing_action": PRE_LISTING_ACTION_BY_WINDOW.get(
            window,
            _normalize_text((record or {}).get("pre_listing_action")) or "none",
        ),
        "days_to_listing": days_to_listing,
        "days_since_listing": days_since_listing,
    }


def _extract_mainline_terms(context):
    context = context or {}
    terms = []
    for key in (
        "mainline_name",
        "current_mainline",
        "potential_mainline",
        "potential_mainlines",
        "mainline",
        "mainline_keywords",
        "mainline_candidates",
        "sector_name",
        "leading_line",
        "daily_attack_line",
        "market_mainline",
    ):
        terms.extend(_split_text_terms(context.get(key)))

    for key in ("exit_analysis", "state_machine_snapshot", "current_mainline_history_record", "mainline_turnover_summary"):
        value = context.get(key) or {}
        if not isinstance(value, dict):
            continue
        for nested_key in ("sector_name", "primary_mainline", "leading_line", "mainline", "current_mainline", "daily_attack_line"):
            terms.extend(_split_text_terms(value.get(nested_key)))

    return _unique_terms(terms)


def _record_mainline_fields(record):
    direct = []
    for key in ("sector", "sector_name", "industry"):
        direct.extend(_split_text_terms((record or {}).get(key)))
    concepts = []
    for key in ("concept_tags", "concepts", "concept_list", "sector_tags"):
        concepts.extend(_split_text_terms((record or {}).get(key)))
    supply = _split_text_terms((record or {}).get("supply_chain_role"))
    return _unique_terms(direct), _unique_terms(concepts), _unique_terms(supply)


def _any_term_match(fields, mainline_terms):
    return any(_sector_name_matches(field, mainline) for field in fields for mainline in mainline_terms)


def _score_mainline_match(record, context):
    mainline_terms = _extract_mainline_terms(context)
    if not mainline_terms:
        return 0

    direct, concepts, supply = _record_mainline_fields(record)
    if _any_term_match(direct, mainline_terms):
        return 24
    if _any_term_match(concepts, mainline_terms):
        return 22
    if _any_term_match(supply, mainline_terms):
        return 20
    return 0


def _score_narrative_association(record, context):
    mainline_terms = _extract_mainline_terms(context)
    anchors = _split_text_terms((record or {}).get("customer_anchors")) + _split_text_terms((record or {}).get("narrative_anchors"))
    role = _normalize_text((record or {}).get("supply_chain_role"))
    domestic = _normalize_text((record or {}).get("domestic_advantage"))
    concepts = _split_text_terms((record or {}).get("concept_tags"))

    score = 0
    if anchors:
        leader_words = ("宁德时代", "比亚迪", "华为", "特斯拉", "苹果", "英伟达", "小米", "隆基", "中芯")
        score += 8 if any(any(word in anchor for word in leader_words) for anchor in anchors) else 5
        if len(_unique_terms(anchors)) >= 2:
            score += 2

    if role:
        role_words = ("产业链", "供应链", "材料链", "设备", "材料", "链", "核心", "关键", "配套链")
        score += 7 if any(word in role for word in role_words) else 4

    if domestic:
        advantage_words = ("国产", "替代", "成本", "效率", "优势", "低价", "制造能力")
        score += 6 if any(word in domestic for word in advantage_words) else 4

    if concepts:
        score += 4 if mainline_terms and _any_term_match(concepts, mainline_terms) else 3

    return _clamp(score, 0, 24)


def _score_level_value(value, max_score):
    if value in (None, ""):
        return 0
    if isinstance(value, bool):
        return max_score if value else 0
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 1:
            return _clamp(number * max_score, 0, max_score)
        if number <= max_score:
            return _clamp(number, 0, max_score)
        if number <= 100:
            return _clamp(number / 100.0 * max_score, 0, max_score)
        return max_score
    if isinstance(value, dict):
        for key in ("score", "emotion_score", "resonance_score", "money_making_score", "strength"):
            if key in value:
                score = _score_level_value(value.get(key), max_score)
                if score:
                    return score
        text = " ".join(_split_text_terms(value))
        return _score_level_value(text, max_score)
    if isinstance(value, (list, tuple, set)):
        return max((_score_level_value(item, max_score) for item in value), default=0)

    text = str(value or "").strip().lower()
    weak_words = ("weak", "cold", "poor", "negative", "弱", "冷", "差", "亏钱", "退潮", "冰点", "不强", "不足")
    strong_words = ("strong", "high", "hot", "positive", "active", "强", "高", "热", "好", "活跃", "赚钱效应强", "升温", "强势")
    neutral_words = ("neutral", "normal", "flat", "一般", "中性", "普通", "平稳")

    if any(word in text for word in weak_words):
        return max(0, max_score // 4)
    if any(word in text for word in strong_words):
        return max_score
    if any(word in text for word in neutral_words):
        return max_score // 3
    return 0


def _score_market_emotion(context):
    context = context or {}
    for key in (
        "new_stock_money_making_effect",
        "recent_new_stock_money_making_effect",
        "new_stock_market_emotion",
        "new_stock_emotion",
        "new_stock_sentiment",
        "market_emotion",
    ):
        score = _score_level_value(context.get(key), 16)
        if score:
            return score
    return 0


def _score_board_resonance(record, context, mainline_match_score):
    context = context or {}
    for key in (
        "board_resonance",
        "sector_resonance",
        "sector_flow",
        "hot_plate_support",
        "mainline_resonance",
    ):
        score = _score_level_value(context.get(key), 10)
        if score:
            return score

    if mainline_match_score >= 20 and _extract_mainline_terms(context):
        return 8
    if mainline_match_score >= 12:
        return 5
    return 0


def _derive_fundraising_yi(record):
    fundraising = _safe_float((record or {}).get("fundraising_yi"), 0.0)
    if fundraising > 0:
        return fundraising
    issue_amount_10k = _safe_float((record or {}).get("issue_amount_10k"), 0.0)
    issue_price = _safe_float((record or {}).get("issue_price"), 0.0)
    if issue_amount_10k > 0 and issue_price > 0:
        return round(issue_amount_10k * issue_price / 100.0, 3)
    return 0.0


def _derive_turnover(record):
    for key in ("turnover", "turnover_yi", "成交额", "amount_yi"):
        value = _safe_float((record or {}).get(key), 0.0)
        if value > 0:
            return round(value, 3)
    return round(_derive_fundraising_yi(record), 3)


def _score_trade_value(record):
    issue_price = _safe_float((record or {}).get("issue_price"), 0.0)
    fundraising_yi = _derive_fundraising_yi(record)
    market = _normalize_text((record or {}).get("market"))

    score = 4
    if 0 < issue_price <= 30:
        score += 2
    elif 30 < issue_price <= 60:
        score += 1

    if 0 < fundraising_yi <= 5:
        score += 2
    elif 5 < fundraising_yi <= 12:
        score += 1

    if market == "bj":
        score -= 1

    return _clamp(score, 0, 8)


def _timing_sentence(scored_record):
    window = _normalize_text((scored_record or {}).get("listing_window"))
    if window == "pre_alert_t2":
        return "T-2提醒：准备清仓/减仓低质量持仓，保留现金和空仓灵活性，明天再复核是否仍符合。"
    if window == "tomorrow_listing":
        return "T-1提醒：明天可战新股，先把现金留出来。"
    if window == "today_listing":
        return "T日提醒：只做开盘确认，不做预先承诺。"
    if window == "recently_listed":
        return "上市后跟踪：只看承接、换手与新股赚钱效应是否延续。"
    if window == "upcoming_soon":
        return "临近上市：先纳入研究池，等T-2/T-1再复核。"
    return "上市窗口不在允许区间，仅保留研究。"


def _upgrade_blockers(scored_record):
    scored_record = scored_record or {}
    factors = scored_record.get("new_stock_factors") or {}
    blockers = []
    if _safe_float(scored_record.get("new_stock_narrative_score"), 0.0) < UPGRADE_THRESHOLD:
        blockers.append("总分未达72")
    if scored_record.get("listing_window") not in ALLOWED_LISTING_WINDOWS:
        blockers.append("上市窗口不在升级范围")
    if _safe_float(factors.get("mainline_match_score"), 0.0) < 20:
        blockers.append("主线匹配不足20")
    if _safe_float(factors.get("narrative_association_score"), 0.0) < 18:
        blockers.append("叙事关联不足18")
    if _safe_float(factors.get("market_emotion_score"), 0.0) < 12 and _safe_float(factors.get("board_resonance_score"), 0.0) < 8:
        blockers.append("缺少新股情绪或板块共振支持")
    return blockers


def _build_candidate_upgrade_reason(scored_record):
    factors = scored_record.get("new_stock_factors") or {}
    score = scored_record.get("new_stock_narrative_score", 0)
    factor_text = (
        f"新股叙事{score}分：上市{factors.get('listing_window_score', 0)}、"
        f"主线{factors.get('mainline_match_score', 0)}、"
        f"叙事{factors.get('narrative_association_score', 0)}、"
        f"情绪{factors.get('market_emotion_score', 0)}、"
        f"板块{factors.get('board_resonance_score', 0)}、"
        f"交易{factors.get('trade_value_score', 0)}。"
    )
    timing_text = _timing_sentence(scored_record)

    anchors = _split_text_terms(scored_record.get("customer_anchors"))
    role = _normalize_text(scored_record.get("supply_chain_role"))
    domestic = _normalize_text(scored_record.get("domestic_advantage"))
    narrative_bits = []
    if anchors:
        narrative_bits.append("锚点" + "/".join(anchors[:3]))
    if role:
        narrative_bits.append(role)
    if domestic:
        narrative_bits.append(domestic)
    narrative_text = "；".join(narrative_bits)

    if scored_record.get("upgrade_eligible"):
        return " ".join(part for part in (factor_text, timing_text, narrative_text) if part)

    blockers = "、".join(_upgrade_blockers(scored_record)) or "条件未完全满足"
    return " ".join(part for part in (factor_text, timing_text, f"暂不升级：{blockers}。", narrative_text) if part)


def should_upgrade_new_stock_candidate(scored_record):
    scored_record = scored_record or {}
    factors = scored_record.get("new_stock_factors") or {}
    return bool(
        _safe_float(scored_record.get("new_stock_narrative_score"), 0.0) >= UPGRADE_THRESHOLD
        and scored_record.get("listing_window") in ALLOWED_LISTING_WINDOWS
        and _safe_float(factors.get("mainline_match_score"), 0.0) >= 20
        and _safe_float(factors.get("narrative_association_score"), 0.0) >= 18
        and (
            _safe_float(factors.get("market_emotion_score"), 0.0) >= 12
            or _safe_float(factors.get("board_resonance_score"), 0.0) >= 8
        )
    )


def score_new_stock_narrative(record, context=None, target_date=""):
    context = context or {}
    scored = _merge_profile(record, context)
    timing = _resolve_listing_timing(scored, target_date)
    scored.update(timing)
    scored["turnover"] = _derive_turnover(scored)

    mainline_match_score = _score_mainline_match(scored, context)
    factors = {
        "listing_window_score": LISTING_WINDOW_SCORE.get(scored.get("listing_window"), 0),
        "mainline_match_score": mainline_match_score,
        "narrative_association_score": _score_narrative_association(scored, context),
        "market_emotion_score": _score_market_emotion(context),
        "board_resonance_score": _score_board_resonance(scored, context, mainline_match_score),
        "trade_value_score": _score_trade_value(scored),
    }
    total_score = sum(factors[key] for key in FACTOR_KEYS)

    scored["new_stock_factors"] = factors
    scored["new_stock_narrative_score"] = total_score
    scored["upgrade_eligible"] = should_upgrade_new_stock_candidate(scored)
    scored["candidate_upgrade_reason"] = _build_candidate_upgrade_reason(scored)
    return scored


def _extract_calendar_records(new_stock_calendar):
    if not new_stock_calendar:
        return []
    if isinstance(new_stock_calendar, dict):
        if isinstance(new_stock_calendar.get("results"), dict):
            return _extract_calendar_records(new_stock_calendar["results"].get("new_stock_calendar"))
        if "new_stock_calendar" in new_stock_calendar:
            return _extract_calendar_records(new_stock_calendar.get("new_stock_calendar"))
        if "code" in new_stock_calendar or "listing_date" in new_stock_calendar:
            return [new_stock_calendar]
        return []
    if isinstance(new_stock_calendar, (list, tuple)):
        return [item for item in new_stock_calendar if isinstance(item, dict)]
    return []


def _build_candidate_upgrade(scored_record):
    return {
        "code": scored_record.get("code", ""),
        "name": scored_record.get("name", ""),
        "sector": scored_record.get("sector") or scored_record.get("industry") or "",
        "turnover": scored_record.get("turnover", 0.0),
        "_source": "新股研究池",
        "watch_source": "new_stock_research_pool",
        "core_level": "新股预期差候选",
        "candidate_upgrade_reason": scored_record.get("candidate_upgrade_reason", ""),
        "new_stock_narrative_score": scored_record.get("new_stock_narrative_score", 0),
        "new_stock_factors": dict(scored_record.get("new_stock_factors") or {}),
        "listing_date": scored_record.get("listing_date", ""),
        "listing_window": scored_record.get("listing_window", ""),
        "pre_listing_action": scored_record.get("pre_listing_action", ""),
    }


def build_new_stock_research_pool(new_stock_calendar=None, target_date="", context=None):
    records = _extract_calendar_records(new_stock_calendar)
    research_pool = [
        score_new_stock_narrative(record, context=context, target_date=target_date)
        for record in records
    ]
    research_pool.sort(
        key=lambda item: (
            item.get("upgrade_eligible", False),
            item.get("new_stock_narrative_score", 0),
            -abs(item.get("days_to_listing") if item.get("days_to_listing") is not None else 999),
        ),
        reverse=True,
    )
    candidate_upgrades = [
        _build_candidate_upgrade(item)
        for item in research_pool
        if should_upgrade_new_stock_candidate(item)
    ]
    return {
        "new_stock_research_pool": research_pool,
        "new_stock_candidate_upgrades": candidate_upgrades,
    }
