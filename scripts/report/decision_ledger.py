from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from selection.candidate_execution_contracts import (
    build_participation_window_from_candidate,
    build_participation_window_policy,
)

ARTIFACT_VERSION = 1
DEFAULT_CYCLE_LENGTH_TRADE_DAYS = 25
SELECTION_RULE_VERSION = "extreme-conviction-ledger-v1"
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
_STOCK_SECTOR_REPAIRS = {
    "001259": "股权转让",
    "300721": "湿电子化学品",
    "688549": "电子特气",
}


def _normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return "".join(ch for ch in text if ch.isdigit()) or text


def _clean_text(value, default=""):
    text = str(value or "").strip()
    return text or default


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _iter_plate_names(value):
    for item in value or []:
        if isinstance(item, dict):
            for key in ("plate_name", "name", "concept_name", "sector"):
                candidate = _clean_text(item.get(key))
                if candidate:
                    yield candidate
        else:
            candidate = _clean_text(item)
            if candidate:
                yield candidate


def _resolve_sector_candidate(item, default="未归类"):
    item = item or {}
    for value in (
        item.get("sector"),
        item.get("sector_candidate"),
    ):
        if _is_valid_sector_label(value):
            return _clean_text(value)
    for field in (
        "xuangubao_related_plates",
        "related_plates",
        "plates",
        "concepts",
        "xuangubao_related_plate_names",
    ):
        for value in _iter_plate_names(item.get(field)):
            if _is_valid_sector_label(value):
                return _clean_text(value)
    for value in (
        item.get("industry"),
        item.get("所属行业"),
        item.get("sector_name"),
    ):
        if _is_valid_sector_label(value):
            return _clean_text(value)
    return default


def _replace_invalid_sector_tokens(text, sector):
    if not _is_valid_sector_label(sector) or not isinstance(text, str):
        return text
    updated = text
    for label in _NON_SECTOR_LABELS:
        if not label or label in {"-", "其他", "其它", "未知", "未归类"}:
            continue
        updated = updated.replace(f"沿{label}趋势比价链", f"沿{sector}趋势比价链")
        updated = updated.replace(f"{label}趋势比价链", f"{sector}趋势比价链")
    return updated


def _sanitize_sector_references(value, sector):
    if isinstance(value, dict):
        return {key: _sanitize_sector_references(item, sector) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_sector_references(item, sector) for item in value]
    if isinstance(value, str):
        return _replace_invalid_sector_tokens(value, sector)
    return value


def _sector_from_case_or_record(record, default=""):
    record = record or {}
    candidates = [
        (record.get("hypothesis") or {}).get("sector_candidate") if isinstance(record.get("hypothesis"), dict) else "",
        record.get("sector"),
        record.get("sector_candidate"),
        record.get("industry"),
        record.get("所属行业"),
        record.get("sector_name"),
    ]
    for value in candidates:
        if _is_valid_sector_label(value):
            return _clean_text(value)
    stock_code = _normalize_stock_code(record.get("stock_code") or record.get("code"))
    if stock_code and _is_valid_sector_label(_STOCK_SECTOR_REPAIRS.get(stock_code)):
        return _STOCK_SECTOR_REPAIRS[stock_code]
    return default


def _sanitize_case_or_record_sector(record):
    if not isinstance(record, dict):
        return record
    sector = _sector_from_case_or_record(record)
    if not _is_valid_sector_label(sector):
        return record
    updated = _sanitize_sector_references(record, sector)
    hypothesis = dict(updated.get("hypothesis") or {})
    if hypothesis:
        hypothesis["sector_candidate"] = sector
        updated["hypothesis"] = hypothesis
    if not _is_valid_sector_label(updated.get("sector")) and "sector" in updated:
        updated["sector"] = sector
    if not _is_valid_sector_label(updated.get("sector_candidate")) and "sector_candidate" in updated:
        updated["sector_candidate"] = sector
    return updated


def _prune_future_mentions_from_case(record, trade_date):
    if not isinstance(record, dict):
        return record
    trade_date = _clean_text(trade_date)
    if not trade_date:
        return record
    mentions = []
    changed = False
    for mention in list(record.get("mentions") or []):
        mention_date = _clean_text((mention or {}).get("mention_trade_date"))
        if mention_date and mention_date > trade_date:
            changed = True
            continue
        mentions.append(mention)
    if not changed:
        return record
    if not mentions:
        return None
    return _sync_record_to_latest_remaining_mention(record, mentions)


def _dedupe_case_mentions(record):
    if not isinstance(record, dict):
        return record
    mentions = _merge_mentions_without_duplicates([], record.get("mentions") or [])
    if len(mentions) == len(list(record.get("mentions") or [])):
        return record
    if not mentions:
        return None
    return _sync_record_to_latest_remaining_mention(record, mentions)


def _sanitize_decision_ledger_index(index):
    if not isinstance(index, dict):
        return {}
    updated_index = dict(index)
    sanitized_by_stock_code = {}
    for code, records in (index.get("by_stock_code") or {}).items():
        sanitized_by_stock_code[code] = [
            _sanitize_case_or_record_sector(record) for record in list(records or [])
        ]
    updated_index["by_stock_code"] = sanitized_by_stock_code
    if "extreme_conviction_backtest_rows" in updated_index:
        updated_index["extreme_conviction_backtest_rows"] = build_extreme_conviction_backtest_rows(
            {"by_stock_code": sanitized_by_stock_code},
            max_rows=25,
        )
    return updated_index


def _sanitize_decision_ledger_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    updated_snapshot = dict(snapshot)
    trade_date = str(snapshot.get("trade_date") or "").strip()
    cases = []
    for case in list(snapshot.get("cases") or []):
        pruned_case = _prune_future_mentions_from_case(case, trade_date)
        pruned_case = _dedupe_case_mentions(pruned_case)
        if pruned_case:
            cases.append(_sanitize_case_or_record_sector(pruned_case))
    updated_snapshot["cases"] = cases
    return updated_snapshot


def _safe_float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_or_none(value, digits=2):
    number = _safe_float(value)
    return round(number, digits) if number is not None else None


def _build_stock_setup(item):
    reason = _clean_text(item.get("conviction_reason") or item.get("reason"), "形态条件待补充")
    pattern = _clean_text(item.get("pattern"))
    return f"{reason}；{pattern}" if pattern else reason


def _build_case_id(trade_date, stock_code, sequence=1):
    return f"{trade_date}-{stock_code}-{int(sequence):02d}"


def _canonical_json_hash(payload):
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _selection_input_hash(*, trade_date, extreme_conviction_list, market_branch, sector_relationship_state):
    normalized_items = []
    for item in list(extreme_conviction_list or []):
        normalized_items.append(
            {
                "code": _normalize_stock_code(item.get("code") or item.get("stock_code")),
                "name": _clean_text(item.get("name") or item.get("stock_name")),
                "sector": _resolve_sector_candidate(item, ""),
                "conviction_reason": _clean_text(item.get("conviction_reason") or item.get("reason")),
                "conviction_rule": _clean_text(item.get("conviction_rule")),
                "pattern": _clean_text(item.get("pattern")),
            }
        )
    return _canonical_json_hash(
        {
            "selection_rule_version": SELECTION_RULE_VERSION,
            "trade_date": trade_date,
            "market_branch": _clean_text(market_branch),
            "sector_relationship_state": _clean_text(sector_relationship_state),
            "extreme_conviction_list": normalized_items,
        }
    )


def _build_mention(item, *, trade_date, rank):
    mention = {
        "mention_trade_date": trade_date,
        "rank": rank,
        "source_section": "极度看好名单",
        "reason": _clean_text(
            item.get("conviction_reason") or item.get("reason") or item.get("conviction_rule"),
            "判断理由待补充",
        ),
    }
    core_identity = item.get("core_identity")
    if isinstance(core_identity, dict) and core_identity:
        mention["core_identity"] = core_identity
    planned_participation = _build_planned_participation(item)
    if planned_participation:
        mention["planned_participation"] = planned_participation
    return mention


def _split_markdown_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _is_markdown_separator(cells):
    return bool(cells) and all(set(str(cell).replace(" ", "")) <= {"-", ":"} for cell in cells)


def _header_index(headers, *names):
    for name in names:
        if name in headers:
            return headers.index(name)
    return -1


def _parse_markdown_table_after_heading(lines, heading_text):
    table_start = -1
    for idx, line in enumerate(lines):
        if heading_text in line:
            table_start = idx + 1
            break
    if table_start < 0:
        return [], []

    header = []
    rows = []
    for line in lines[table_start:]:
        stripped = line.strip()
        if not stripped:
            if header:
                break
            continue
        if not stripped.startswith("|"):
            if header:
                break
            continue
        cells = _split_markdown_row(stripped)
        if _is_markdown_separator(cells):
            continue
        if not header:
            header = cells
            continue
        rows.append(cells)
    return header, rows


def _parse_markdown_table_after_any_heading(lines, *heading_texts):
    for heading_text in heading_texts:
        header, rows = _parse_markdown_table_after_heading(lines, heading_text)
        if header:
            return header, rows
    return [], []


def _execution_layer_fields(layer_label):
    label = _clean_text(layer_label)
    if not label:
        return {}
    if "风险" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "risk_blocked",
            "execution_eligibility": "blocked_by_negative_news",
        }
    if "可执行" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "executable_candidate",
            "execution_eligibility": "auction_reseal",
        }
    if "修复" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "watch_sample",
            "execution_eligibility": "structure_confirm_only",
        }
    if "观察" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "watch_sample",
            "execution_eligibility": "structure_confirm_only",
        }
    return {"candidate_layer_label": label}


def _normalize_participation_script(item):
    item = item or {}
    nested = item.get("participation_script") or item.get("planned_participation") or {}
    if not isinstance(nested, dict):
        nested = {}

    def _value(*keys):
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return _clean_text(value)
            value = nested.get(key)
            if value not in (None, ""):
                return _clean_text(value)
        return ""

    script = {
        "participation_window": _value("participation_window", "entry_window", "window"),
        "participation_window_type": _value("participation_window_type", "window_type"),
        "attack_state": _value("attack_state", "position_state", "target_position_pct"),
        "auction_required": _value("auction_required"),
        "first_minutes_required": _value("first_minutes_required"),
        "board_or_reseal_required": _value("board_or_reseal_required"),
        "ordinary_structure_confirm_allowed": _value("ordinary_structure_confirm_allowed"),
        "missed_entry_policy": _value("missed_entry_policy"),
        "source_tier": _value("source_tier"),
        "entry_timing": _value("entry_timing"),
        "buy_window": _value("buy_window"),
        "entry_timing_reason": _value("entry_timing_reason"),
        "limit_up_inertia_level": _value("limit_up_inertia_level"),
        "limit_up_inertia_score": _value("limit_up_inertia_score"),
        "next_day_limit_probability_band": _value("next_day_limit_probability_band"),
        "limit_up_inertia_reason": _value("limit_up_inertia_reason"),
        "risk_reward_min_ratio": _value("risk_reward_min_ratio"),
        "risk_reward_ratio": _value("risk_reward_ratio"),
        "risk_reward_state": _value("risk_reward_state"),
        "risk_reward_plan": _value("risk_reward_plan"),
        "auction": _value("auction", "auction_script"),
        "first_minutes": _value("first_minutes", "first_minutes_script", "opening_script"),
        "board": _value("board", "board_script", "limit_board_script"),
        "reseal": _value("reseal", "reseal_script"),
        "missed_action": _value("missed_action", "missed_entry_action"),
        "cancellation": _value("cancellation", "invalid_condition", "cancel_condition", "failure_condition"),
    }
    preserved = {}
    for key, value in script.items():
        if value in (None, ""):
            continue
        if key in {
            "auction_required",
            "first_minutes_required",
            "board_or_reseal_required",
            "ordinary_structure_confirm_allowed",
        } and isinstance(value, str):
            preserved[key] = value.strip().lower() in ("1", "true", "yes", "y", "是", "需要", "允许")
        elif key in {"limit_up_inertia_score", "risk_reward_min_ratio", "risk_reward_ratio"}:
            preserved[key] = _safe_float(value, None)
        else:
            preserved[key] = value
    return preserved


def _default_participation_script(item):
    item = item or {}
    sector = _resolve_sector_candidate(item, "主线")
    source_tier = _clean_text(item.get("source_tier") or item.get("selection_source_tier"), "extreme_conviction")
    window = build_participation_window_from_candidate(item)
    if window == "打板/错过":
        window = "打板/错过"
        board = "只做首次强封且大单金额持续进入，封死买不到就不追"
        missed = f"封死买不到就沿{sector}趋势比价链找低位承接，找不到就跳过"
    elif "回封参与" in window:
        window = "竞价表态 + 回封参与"
        board = "首次封板只看大单金额持续进入，弱封不追"
        missed = f"过快封死就沿{sector}趋势比价链找低位承接，找不到就跳过"
    else:
        window = "60分钟确认"
        board = "不以涨停为唯一条件，先等价格确认和承接连续"
        missed = f"确认前快速拉高就跳过，只沿{sector}趋势比价链找低位承接，找不到就跳过"
    planned = {
        "participation_window": window,
        "attack_state": "100%" if item.get("allow_full_attack") or item.get("a_grade_candidate") else "50%",
        "auction": "09:20后看价格位置、匹配金额、委托稳定和板块同步，任一不合格按0%不参与",
        "first_minutes": "09:30-09:35只看主动资金是否继续抬价，承接不连续按0%不参与",
        "board": board,
        "reseal": "开板释放抛压后快速回封，且封单质量改善、板块同步",
        "missed_action": missed,
        "cancellation": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
    }
    planned.update(build_participation_window_policy(window, missed, source_tier, candidate=item))
    return planned


def _build_planned_participation(item):
    script = _normalize_participation_script(item)
    required_keys = (
        "participation_window",
        "auction",
        "first_minutes",
        "board",
        "reseal",
        "missed_action",
        "cancellation",
    )
    if not any(script.get(key) for key in required_keys):
        return _default_participation_script(item)
    planned = {**_default_participation_script(item), **script}
    planned.update(
        build_participation_window_policy(
            planned.get("participation_window"),
            planned.get("missed_action"),
            planned.get("source_tier", "extreme_conviction"),
            candidate=item,
        )
    )
    for key in (
        "participation_window_type",
        "auction_required",
        "first_minutes_required",
        "board_or_reseal_required",
        "ordinary_structure_confirm_allowed",
        "missed_entry_policy",
        "source_tier",
        "entry_timing",
        "buy_window",
        "entry_timing_reason",
        "limit_up_inertia_level",
        "limit_up_inertia_score",
        "next_day_limit_probability_band",
        "limit_up_inertia_reason",
        "risk_reward_min_ratio",
        "risk_reward_ratio",
        "risk_reward_state",
        "risk_reward_plan",
    ):
        if key in script:
            planned[key] = script[key]
    return planned


def classify_planned_participation_review(
    planned_participation=None,
    *,
    review_trade_date=None,
    auction_matched=False,
    first_minutes_accepted=False,
    structure_confirmed=False,
    board_sealed=False,
    reseal_success=False,
    sector_supported=False,
    cancellation_triggered=False,
    primary_unavailable=False,
    missed_action_worked=False,
    cancellation_evidence=None,
    missed_action_evidence=None,
    evidence=None,
    entry_decision=None,
    window_confirmed=False,
    window_failed=False,
    same_day_action=None,
    avoid_action=None,
    next_action=None,
    standard_answer_basis=None,
    market_outcome=None,
):
    planned = planned_participation or {}
    planned_window = _clean_text(planned.get("participation_window"), "未记录参与窗口")
    attack_state = _clean_text(planned.get("attack_state"), "未记录仓位三态")
    participation_window_type = _clean_text(planned.get("participation_window_type"), "structure_confirm")

    base = {
        "planned_window": planned_window,
        "participation_window_type": participation_window_type,
        "attack_state": attack_state,
        "matched_steps": [],
        "evidence": _clean_text(evidence),
    }
    optional_fields = {
        "review_trade_date": review_trade_date,
        "entry_decision": entry_decision,
        "same_day_action": same_day_action,
        "avoid_action": avoid_action,
        "next_action": next_action,
        "standard_answer_basis": standard_answer_basis,
        "market_outcome": market_outcome,
    }
    for key, value in optional_fields.items():
        if value not in (None, "", [], {}):
            base[key] = value
    if auction_matched:
        base["matched_steps"].append("竞价表态")
    if first_minutes_accepted:
        base["matched_steps"].append("开盘前几分钟承接")
    if structure_confirmed:
        base["matched_steps"].append("60分钟确认")
    if board_sealed:
        base["matched_steps"].append("打板策略")
    if reseal_success:
        base["matched_steps"].append("回封参与")
    if sector_supported:
        base["matched_steps"].append("板块同步")
    if window_confirmed:
        base["matched_steps"].append("09:50-10:10承接")

    if cancellation_triggered:
        base.update(
            {
                "status": "预演作废",
                "reason": "作废条件出现，原参与方案不再成立。"
                if not window_failed
                else "09:50-10:10窗口继续走弱，原参与方案不再成立。",
                "evidence": _clean_text(cancellation_evidence, base["evidence"] or "作废条件已触发"),
            }
        )
        return base

    if primary_unavailable and not missed_action_worked:
        base.update(
            {
                "status": "主目标不可成交",
                "reason": "主目标封死或不可成交，按错过后动作观察，不补票。",
                "evidence": base["evidence"] or "主目标不可成交",
            }
        )
        return base

    if primary_unavailable and missed_action_worked:
        base.update(
            {
                "status": "错过后方案命中",
                "reason": "核心目标不可得，但错过后动作沿原趋势比价链生效。",
                "evidence": _clean_text(missed_action_evidence, base["evidence"] or "错过后动作获得验证"),
            }
        )
        return base

    if entry_decision == "window_confirm_buy":
        base.update(
            {
                "status": "预演命中",
                "reason": "09:50-10:10窗口完成承接确认，参与预演获得验证。",
                "evidence": base["evidence"] or "09:50-10:10承接成立",
            }
        )
        return base

    if entry_decision == "waiting_window_review":
        base.update(
            {
                "status": "等待窗口复盘",
                "reason": "日线出现下影或盘中分歧，不能仅凭全天低点判定计划窗口失败，需要分钟窗口承接事实。",
                "evidence": base["evidence"] or "等待分钟窗口承接事实",
            }
        )
        return base

    if participation_window_type == "structure_confirm":
        if structure_confirmed and sector_supported:
            base.update(
                {
                    "status": "预演命中",
                    "reason": "60分钟确认和板块同步共同验证。",
                    "evidence": base["evidence"] or "结构确认命中",
                }
            )
            return base
        base.update(
            {
                "status": "等待复盘",
                "reason": "普通结构确认样本还缺少60分钟确认事实。",
                "evidence": base["evidence"],
            }
        )
        return base

    if auction_matched and first_minutes_accepted and (board_sealed or reseal_success) and sector_supported:
        base.update(
            {
                "status": "预演命中",
                "reason": "参与窗口、承接、封板/回封和板块同步共同验证。",
                "evidence": base["evidence"] or "预演关键步骤连续命中",
            }
        )
        return base

    if auction_matched and not first_minutes_accepted:
        base.update(
            {
                "status": "预演过早",
                "reason": "竞价信号出现，但开盘承接没有延续。",
                "evidence": base["evidence"] or "竞价之后承接断档",
            }
        )
        return base

    base.update(
        {
            "status": "等待复盘",
            "reason": "参与预演还缺少足够的次日事实。",
            "evidence": base["evidence"],
        }
    )
    return base


def _infer_limit_up_pct(stock_code="", stock_name=""):
    code = _normalize_stock_code(stock_code)
    name = str(stock_name or "")
    if "ST" in name.upper() or "退" in name:
        return 5.0
    if code.startswith(("300", "301", "688")):
        return 20.0
    return 10.0


def _pct_change(value, base):
    value_num = _safe_float(value)
    base_num = _safe_float(base)
    if value_num is None or base_num in (None, 0):
        return None
    return (value_num / base_num - 1) * 100


def _close_position(high, low, close):
    high_num = _safe_float(high)
    low_num = _safe_float(low)
    close_num = _safe_float(close)
    if high_num is None or low_num is None or close_num is None:
        return None
    if high_num <= low_num:
        return 1.0 if close_num >= high_num else 0.0
    return max(0.0, min(1.0, (close_num - low_num) / (high_num - low_num)))


def _format_price(value):
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}"


def _time_to_minutes(value):
    text = str(value or "").strip()
    if " " in text:
        text = text.rsplit(" ", 1)[-1]
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    return hour * 60 + minute


def _minute_bar_minutes(row):
    row = row or {}
    return _time_to_minutes(
        row.get("time")
        or row.get("datetime")
        or row.get("trade_time")
        or row.get("day")
        or row.get("时间")
    )


def _parse_review_window_minutes(window_text):
    matches = re.findall(r"(\d{1,2}:\d{2})", str(window_text or ""))
    if len(matches) < 2:
        return None, None
    return _time_to_minutes(matches[0]), _time_to_minutes(matches[1])


def _minute_window_review_fact(fact, review_window):
    fact = fact or {}
    minute_bars = fact.get("minute_bars") or fact.get("intraday_bars") or fact.get("minutes") or []
    if not isinstance(minute_bars, list) or not minute_bars:
        return {}
    start_minute, end_minute = _parse_review_window_minutes(review_window)
    if start_minute is None or end_minute is None:
        return {}

    prepared = []
    for row in minute_bars:
        minute_value = _minute_bar_minutes(row)
        if minute_value is None:
            continue
        prepared.append((minute_value, row or {}))
    prepared.sort(key=lambda item: item[0])
    window_rows = [row for minute_value, row in prepared if start_minute <= minute_value <= end_minute]
    if not window_rows:
        return {}

    def _price(row, *keys):
        for key in keys:
            value = _safe_float((row or {}).get(key))
            if value is not None:
                return value
        return None

    window_open = _price(window_rows[0], "open", "开盘")
    window_close = _price(window_rows[-1], "close", "收盘")
    highs = [_price(row, "high", "最高") for row in window_rows]
    lows = [_price(row, "low", "最低") for row in window_rows]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    window_high = max(highs) if highs else None
    window_low = min(lows) if lows else None

    previous_lows = [
        _price(row, "low", "最低")
        for minute_value, row in prepared
        if minute_value < start_minute
    ]
    previous_lows = [value for value in previous_lows if value is not None]
    pre_window_low = min(previous_lows) if previous_lows else None
    reference_price = _safe_float(
        fact.get("window_reference_price")
        or fact.get("intraday_yellow_line_price")
        or fact.get("yellow_line_price")
        or fact.get("ma_reversion_price")
        or fact.get("prev_close")
    )

    reclaimed_reference = (
        reference_price is not None
        and window_close is not None
        and window_close >= reference_price
    )
    closes_up = window_open is not None and window_close is not None and window_close >= window_open
    does_not_break_prior_low = (
        pre_window_low is None
        or window_low is None
        or window_low >= pre_window_low * 0.995
    )
    confirmed = bool(reclaimed_reference and closes_up and does_not_break_prior_low)
    failed = bool(
        reference_price is not None
        and window_close is not None
        and window_open is not None
        and window_low is not None
        and window_close < reference_price
        and window_close < window_open
        and window_low < reference_price
    )

    if confirmed:
        state = "confirmed"
    elif failed:
        state = "failed"
    else:
        state = "mixed"

    return {
        "state": state,
        "window_open": window_open,
        "window_high": window_high,
        "window_low": window_low,
        "window_close": window_close,
        "window_reference_price": reference_price,
        "pre_window_low": pre_window_low,
        "summary": (
            f"{review_window}窗口开{_format_price(window_open)}、高{_format_price(window_high)}、"
            f"低{_format_price(window_low)}、窗口收盘{_format_price(window_close)}、"
            f"参考{_format_price(reference_price)}"
        ),
    }


def _bool_from_fact(fact, key, fallback=False):
    if key not in fact:
        return bool(fallback)
    value = fact.get(key)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "是", "命中", "成立")
    return bool(value)


def _standard_action_text(entry_timing, buy_window, decision):
    window = _clean_text(buy_window, "none")
    if decision == "unavailable":
        return "主目标封死或不可成交，0%不参与；只记录错过后动作，不补票"
    if decision == "skip":
        return "0%不参与；等下一次预演条件重新成立"
    if decision == "waiting_window_review":
        return f"仅凭日线不能判死{window}窗口；等待分钟窗口承接事实回写后再定买点质量"
    if decision == "window_confirm_buy":
        return f"按{window}承接成立参与；只做计划内试错，不因盘中噪音临时加码"
    if decision == "window_confirm_failed":
        return f"{window}继续走弱，0%不参与；不把日内反抽当买点"
    if entry_timing == "open_core":
        return f"按{window}开盘核心参与；只在竞价表态、开盘承接、回封/打板同时成立时买"
    if entry_timing == "ten_confirm":
        return f"按{window}完成10点确认后再参与；确认前不抢跑"
    if entry_timing == "tail_exception":
        return f"按{window}尾盘例外确认；只用于避开盘中分歧消耗"
    return "只观察，不生成买入动作"


def build_participation_review_facts_from_market_fact(planned_participation=None, market_fact=None):
    planned = planned_participation or {}
    fact = market_fact or {}
    stock_code = _normalize_stock_code(fact.get("stock_code"))
    stock_name = _clean_text(fact.get("stock_name"))
    entry_timing = _clean_text(planned.get("entry_timing"), "ten_confirm")
    buy_window = _clean_text(planned.get("buy_window"), "09:50-10:10")
    source_tier = _clean_text(planned.get("source_tier"), "extreme_conviction")
    ma_reversion_window = _clean_text(planned.get("ma_reversion_window"))
    if entry_timing == "open_core" and not ma_reversion_window and source_tier == "extreme_conviction":
        ma_reversion_window = "09:50-10:10"
    review_window = ma_reversion_window if entry_timing == "open_core" and ma_reversion_window else buy_window
    limit_up_pct = _safe_float(fact.get("limit_up_pct"), _infer_limit_up_pct(stock_code, stock_name))
    prev_close = _safe_float(fact.get("prev_close"))
    open_price = _safe_float(fact.get("open"))
    high_price = _safe_float(fact.get("high"))
    low_price = _safe_float(fact.get("low"))
    close_price = _safe_float(fact.get("close"))

    open_change_pct = _pct_change(open_price, prev_close)
    high_change_pct = _pct_change(high_price, prev_close)
    low_change_pct = _pct_change(low_price, prev_close)
    close_change_pct = _pct_change(close_price, prev_close)
    close_pos = _close_position(high_price, low_price, close_price)
    board_like = bool(
        high_change_pct is not None
        and close_change_pct is not None
        and high_change_pct >= limit_up_pct - 0.8
        and close_change_pct >= limit_up_pct - 1.0
        and (close_pos or 0) >= 0.85
    )
    one_word_limit = bool(
        board_like
        and open_price is not None
        and high_price is not None
        and low_price is not None
        and close_price is not None
        and abs(open_price - high_price) < 1e-9
        and abs(high_price - low_price) < 1e-9
        and abs(low_price - close_price) < 1e-9
    )
    strong_close = bool(
        close_change_pct is not None
        and close_change_pct > 0
        and close_price is not None
        and open_price is not None
        and close_price >= open_price
        and (close_pos or 0) >= 0.65
    )
    window_review = _minute_window_review_fact(fact, review_window)
    window_confirmed = window_review.get("state") == "confirmed"
    window_failed = window_review.get("state") == "failed"

    auction_matched = _bool_from_fact(
        fact,
        "auction_matched",
        open_change_pct is not None and open_change_pct >= 0 and (low_change_pct is None or low_change_pct >= -3),
    )
    first_minutes_accepted = _bool_from_fact(
        fact,
        "first_minutes_accepted",
        window_confirmed or (strong_close and (low_price is None or open_price is None or low_price >= open_price * 0.95)),
    )
    structure_confirmed = _bool_from_fact(fact, "structure_confirmed", strong_close)
    board_sealed = _bool_from_fact(fact, "board_sealed", board_like and close_price == high_price)
    reseal_success = _bool_from_fact(fact, "reseal_success", board_like and low_price is not None and high_price is not None and low_price < high_price)
    sector_supported = _bool_from_fact(fact, "sector_supported", board_like or strong_close)
    cancellation_triggered = _bool_from_fact(
        fact,
        "cancellation_triggered",
        window_failed or (
            close_change_pct is not None and (close_change_pct <= -3 or (close_pos is not None and close_pos < 0.25))
        ),
    )
    primary_unavailable = _bool_from_fact(fact, "primary_unavailable", one_word_limit)
    missed_action_worked = _bool_from_fact(fact, "missed_action_worked", False)
    needs_window_review = bool(
        entry_timing == "open_core"
        and "09:50" in review_window
        and board_like
        and low_change_pct is not None
        and low_change_pct <= -3
        and not window_confirmed
        and not window_failed
        and not any(
            key in fact
            for key in (
                "first_minutes_accepted",
                "structure_confirmed",
                "cancellation_triggered",
            )
        )
    )

    if primary_unavailable and not missed_action_worked:
        entry_decision = "unavailable"
    elif window_failed:
        entry_decision = "window_confirm_failed"
    elif window_confirmed:
        entry_decision = "window_confirm_buy"
    elif cancellation_triggered:
        entry_decision = "skip"
    elif needs_window_review:
        entry_decision = "waiting_window_review"
    elif entry_timing == "open_core" and auction_matched and first_minutes_accepted and (board_sealed or reseal_success) and sector_supported:
        entry_decision = "open_buy"
    elif entry_timing == "ten_confirm" and structure_confirmed and sector_supported:
        entry_decision = "ten_confirm_buy"
    elif entry_timing == "tail_exception" and structure_confirmed and sector_supported:
        entry_decision = "tail_confirm"
    else:
        entry_decision = "skip"

    outcome_parts = []
    for label, value in (
        ("开盘", open_change_pct),
        ("最高", high_change_pct),
        ("最低", low_change_pct),
        ("收盘", close_change_pct),
    ):
        if value is not None:
            outcome_parts.append(f"{label}{value:+.2f}%")
    if close_pos is not None:
        outcome_parts.append(f"收盘位置{close_pos:.0%}")
    if window_review:
        outcome_parts.append(str(window_review.get("summary") or ""))
    market_outcome = "，".join(outcome_parts)

    basis = []
    if auction_matched:
        basis.append("竞价表态")
    if first_minutes_accepted:
        basis.append("开盘承接")
    if structure_confirmed:
        basis.append("结构确认")
    if board_sealed or reseal_success:
        basis.append("回封/打板")
    if sector_supported:
        basis.append("板块同步")
    if window_confirmed:
        basis.append(f"{review_window}承接成立")
    if window_failed:
        basis.append(f"{review_window}继续走弱")
    if cancellation_triggered:
        basis.append("作废条件")
    if needs_window_review:
        basis.append(f"{review_window}窗口事实待补")
    standard_answer_basis = " / ".join(basis) or "条件不足"
    evidence = _clean_text(
        fact.get("evidence"),
        f"{market_outcome}；标准答案依据：{standard_answer_basis}",
    )

    return {
        "review_trade_date": _clean_text(fact.get("review_trade_date")),
        "auction_matched": auction_matched,
        "first_minutes_accepted": first_minutes_accepted,
        "structure_confirmed": structure_confirmed,
        "board_sealed": board_sealed,
        "reseal_success": reseal_success,
        "sector_supported": sector_supported,
        "cancellation_triggered": cancellation_triggered,
        "primary_unavailable": primary_unavailable,
        "missed_action_worked": missed_action_worked,
        "evidence": evidence,
        "entry_decision": entry_decision,
        "window_confirmed": window_confirmed,
        "window_failed": window_failed,
        "same_day_action": _standard_action_text(
            entry_timing,
            review_window if entry_decision in {"waiting_window_review", "window_confirm_buy", "window_confirm_failed"} else buy_window,
            entry_decision,
        ),
        "avoid_action": "任一预演条件失败按0%；封死买不到就跳过，不补票",
        "next_action": "若已买入，次日先看是否继续强于市场；30分钟结构失守立即卖，不能把短线拿成长线",
        "standard_answer_basis": standard_answer_basis,
        "market_outcome": market_outcome,
    }


def _parse_participation_scripts(lines):
    header, rows = _parse_markdown_table_after_any_heading(
        lines,
        "极度看好参与脚本",
        "重点观察参与脚本",
    )
    if not header:
        return []

    window_idx = _header_index(header, "参与窗口")
    attack_idx = _header_index(header, "仓位三态", "进攻仓位三态")
    inertia_idx = _header_index(header, "涨停惯性", "惯性等级", "概率优势")
    risk_reward_idx = _header_index(header, "盈亏比", "风险收益比", "风险收益")
    auction_idx = _header_index(header, "集合竞价", "竞价表态")
    first_minutes_idx = _header_index(header, "开盘前几分钟", "开盘前分钟")
    ma_reversion_idx = _header_index(header, "均线回归试错", "日K均线回归", "分时黄线承接")
    board_idx = _header_index(header, "打板策略", "打板")
    reseal_idx = _header_index(header, "回封参与", "回封")
    missed_idx = _header_index(header, "错过后动作")
    ma20_idx = _header_index(header, "MA20作废", "MA20失效", "趋势作废")
    tracking_idx = _header_index(header, "跟踪周期", "追踪周期", "跟踪天数")
    cancel_idx = _header_index(header, "作废条件", "取消条件")

    scripts = []
    for row in rows:
        def _cell(index):
            return row[index].strip() if 0 <= index < len(row) else ""

        tracking_text = _clean_text(_cell(tracking_idx))
        tracking_days = None
        if tracking_text:
            match = re.search(r"(\d+)", tracking_text)
            if match:
                tracking_days = int(match.group(1))

        inertia_text = _clean_text(_cell(inertia_idx))
        inertia_parts = [part.strip() for part in re.split(r"[；;]", inertia_text) if part.strip()]
        risk_reward_text = _clean_text(_cell(risk_reward_idx))
        risk_reward_parts = [part.strip() for part in re.split(r"[；;]", risk_reward_text) if part.strip()]
        risk_reward_ratio = None
        ratio_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*:\s*1", risk_reward_text)
        if ratio_match:
            risk_reward_ratio = _safe_float(ratio_match.group(1), None)

        script = {
            "participation_window": _clean_text(_cell(window_idx)),
            "attack_state": _clean_text(_cell(attack_idx)),
            "limit_up_inertia_level": inertia_parts[0] if len(inertia_parts) >= 1 else "",
            "next_day_limit_probability_band": inertia_parts[1] if len(inertia_parts) >= 2 else "",
            "limit_up_inertia_reason": inertia_parts[2] if len(inertia_parts) >= 3 else inertia_text,
            "risk_reward_state": risk_reward_parts[0] if len(risk_reward_parts) >= 1 else "",
            "risk_reward_plan": risk_reward_parts[-1] if risk_reward_parts else risk_reward_text,
            "auction": _clean_text(_cell(auction_idx)),
            "first_minutes": _clean_text(_cell(first_minutes_idx)),
            "intraday_yellow_line_probe": _clean_text(_cell(ma_reversion_idx)),
            "board": _clean_text(_cell(board_idx)),
            "reseal": _clean_text(_cell(reseal_idx)),
            "missed_action": _clean_text(_cell(missed_idx)),
            "ma20_invalidation": _clean_text(_cell(ma20_idx)),
            "cancellation": _clean_text(_cell(cancel_idx)),
        }
        if risk_reward_ratio is not None:
            script["risk_reward_ratio"] = risk_reward_ratio
        if tracking_days is not None:
            script["tracking_window_trade_days"] = tracking_days
        scripts.append(
            script
        )
    return scripts


def parse_extreme_conviction_list_from_markdown(markdown_text):
    lines = str(markdown_text or "").splitlines()
    header, rows = _parse_markdown_table_after_any_heading(
        lines,
        "极度看好名单",
        "重点观察名单",
    )

    if not header:
        return []

    rank_idx = _header_index(header, "优先级", "排名")
    name_idx = _header_index(header, "股票", "名称")
    code_idx = _header_index(header, "代码", "股票代码")
    sector_idx = _header_index(header, "所属板块", "板块", "所属方向")
    core_identity_idx = _header_index(header, "核心身份")
    layer_idx = _header_index(header, "执行分层")
    reason_idx = _header_index(header, "观察理由", "极看理由", "理由")
    rule_idx = _header_index(header, "明日原则", "原则")
    participation_scripts = _parse_participation_scripts(lines)

    items = []
    for sequence, row in enumerate(rows, 1):
        def _cell(index):
            return row[index].strip() if 0 <= index < len(row) else ""

        code = _normalize_stock_code(_cell(code_idx))
        name = _clean_text(_cell(name_idx), code)
        if not code and not name:
            continue
        try:
            rank = int(_cell(rank_idx) or sequence)
        except ValueError:
            rank = sequence
        item = {
            "rank": rank,
            "name": name,
            "code": code,
            "sector": _clean_text(_cell(sector_idx), "未归类"),
            "conviction_reason": _clean_text(_cell(reason_idx), "判断理由待补充"),
            "conviction_rule": _clean_text(_cell(rule_idx), "明日原则待补充"),
        }
        core_identity_label = _clean_text(_cell(core_identity_idx))
        if core_identity_label:
            item["core_identity_label"] = core_identity_label
        item.update(_execution_layer_fields(_cell(layer_idx)))
        if sequence <= len(participation_scripts):
            item["participation_script"] = _build_planned_participation(participation_scripts[sequence - 1])
        items.append(item)
    return items


def _find_open_previous_case(previous_index, stock_code):
    by_stock_code = (previous_index or {}).get("by_stock_code") or {}
    records = by_stock_code.get(stock_code) or []
    for record in reversed(records):
        if not record.get("cycle_closed"):
            return record
    return None


def _copy_mentions(record):
    return [dict(item) for item in list((record or {}).get("mentions") or [])]


def _mention_identity(mention):
    mention = mention or {}
    return (
        _clean_text(mention.get("mention_trade_date")),
        _clean_text(mention.get("source_section")),
    )


def _merge_mentions_without_duplicates(previous_mentions, current_mentions):
    merged = []
    for mention in list(previous_mentions or []) + list(current_mentions or []):
        copied = dict(mention or {})
        key = _mention_identity(copied)
        replaced = False
        for index, existing in enumerate(merged):
            if _mention_identity(existing) == key:
                merged[index] = copied
                replaced = True
                break
        if replaced:
            continue
        merged.append(copied)
    return merged


def _sync_record_to_latest_remaining_mention(record, mentions):
    updated = dict(record or {})
    updated["mentions"] = list(mentions or [])
    latest = updated["mentions"][-1] if updated["mentions"] else {}
    latest_planned = latest.get("planned_participation")
    if isinstance(latest_planned, dict) and latest_planned:
        updated["planned_participation"] = latest_planned
    latest_review = latest.get("participation_review")
    if isinstance(latest_review, dict) and latest_review:
        updated["participation_review"] = dict(latest_review)
        updated["participation_review_status"] = latest_review.get("status")
    return updated


def prune_replaced_same_day_extreme_mentions(previous_index, *, trade_date="", current_codes=None):
    previous_index = previous_index or {}
    trade_date = str(trade_date or "").strip()
    if not trade_date:
        return previous_index
    current_codes = {_normalize_stock_code(code) for code in list(current_codes or []) if _normalize_stock_code(code)}
    updated = dict(previous_index)
    updated_by_stock_code = {}
    for code, records in (previous_index.get("by_stock_code") or {}).items():
        normalized_code = _normalize_stock_code(code)
        kept_records = []
        for record in list(records or []):
            mentions = list((record or {}).get("mentions") or [])
            has_stale_same_day_extreme_mention = any(
                str(mention.get("mention_trade_date") or "").strip() == trade_date
                and _mention_source_tier(mention, _record_planned_participation(record)) == "extreme_conviction"
                and normalized_code not in current_codes
                for mention in mentions
            )
            if not has_stale_same_day_extreme_mention:
                kept_records.append(record)
                continue
            kept_mentions = [
                mention
                for mention in mentions
                if not (
                    str(mention.get("mention_trade_date") or "").strip() == trade_date
                    and _mention_source_tier(mention, _record_planned_participation(record)) == "extreme_conviction"
                )
            ]
            if not kept_mentions:
                continue
            kept_records.append(_sync_record_to_latest_remaining_mention(record, kept_mentions))
        if kept_records:
            updated_by_stock_code[code] = kept_records
    updated["by_stock_code"] = updated_by_stock_code
    if "extreme_conviction_backtest_rows" in updated:
        updated["extreme_conviction_backtest_rows"] = build_extreme_conviction_backtest_rows(
            {"by_stock_code": updated_by_stock_code},
            max_rows=25,
        )
    return updated


def _prune_replaced_same_day_records(previous_index, snapshot):
    snapshot = snapshot or {}
    current_codes = {
        _normalize_stock_code(case.get("stock_code"))
        for case in list(snapshot.get("cases") or [])
        if _normalize_stock_code(case.get("stock_code"))
    }
    return prune_replaced_same_day_extreme_mentions(
        previous_index,
        trade_date=snapshot.get("trade_date"),
        current_codes=current_codes,
    )


def _cycle_day_from_dates(start_trade_date, trade_date):
    try:
        start_day = int(str(start_trade_date).replace("-", ""))
        current_day = int(str(trade_date).replace("-", ""))
    except (TypeError, ValueError):
        return 1
    if current_day <= start_day:
        return 1
    return 2


def classify_validation_state(
    *,
    sector_selected=False,
    stock_acceptance=False,
    sector_path_lost=False,
    stock_structure_broken=False,
    stock_setup_intact=True,
    sector_selection_evidence=None,
    stock_acceptance_evidence=None,
    confirmation_date=None,
    failure_reason=None,
):
    if sector_path_lost and stock_structure_broken:
        return {
            "status": "真正失败",
            "selection_confirmed_date": None,
            "selection_confirmed_evidence": None,
            "sector_selection_evidence": sector_selection_evidence,
            "stock_acceptance_evidence": stock_acceptance_evidence,
            "failure_reason": _clean_text(failure_reason, "板块路径失去选择，个股结构或承接失败"),
        }
    if sector_selected and stock_acceptance:
        sector_evidence = _clean_text(sector_selection_evidence, "所属板块被资金选择")
        stock_evidence = _clean_text(stock_acceptance_evidence, "个股承接或强度跟上")
        return {
            "status": "市场选择确认",
            "selection_confirmed_date": confirmation_date,
            "selection_confirmed_evidence": f"{sector_evidence}；{stock_evidence}",
            "sector_selection_evidence": sector_evidence,
            "stock_acceptance_evidence": stock_evidence,
        }
    return {
        "status": "等待市场选择",
        "selection_confirmed_date": None,
        "selection_confirmed_evidence": None,
        "sector_selection_evidence": sector_selection_evidence,
        "stock_acceptance_evidence": stock_acceptance_evidence,
        "stock_setup_intact": bool(stock_setup_intact),
    }


def _closed_acceptance(final_label, reason, iteration_note=None):
    return {
        "status": "closed",
        "final_label": final_label,
        "reason": reason,
        "iteration_note": iteration_note,
    }


def classify_cycle_acceptance(
    *,
    validation_status=None,
    trend_delivered=False,
    stock_setup_intact=False,
    sector_branch_selected=False,
    market_selected_other_branch=False,
    eliminated_early=False,
    continued_strength_after_elimination=False,
):
    if eliminated_early and continued_strength_after_elimination:
        return _closed_acceptance(
            "提前淘汰后继续走强",
            "样本被提前移除后仍在同周期继续走强，需要复盘淘汰条件。",
            "检查淘汰条件是否过敏。",
        )
    if validation_status == "真正失败":
        return _closed_acceptance(
            "真正失败",
            "所属方向持续失去选择，且个股自身结构或承接也失败。",
        )
    if validation_status == "市场选择确认" and trend_delivered:
        return _closed_acceptance(
            "市场选择确认后趋势兑现",
            "市场选择确认后，个股趋势继续兑现。",
        )
    if market_selected_other_branch and stock_setup_intact:
        return _closed_acceptance(
            "市场分支未选择且个股假设保留",
            "市场选择了其他分支，但个股形态假设尚未被自身走势否定。",
        )
    if validation_status == "等待市场选择" and stock_setup_intact and not sector_branch_selected:
        return _closed_acceptance(
            "等待市场选择但周期未验证",
            "个股结构仍在，但所属方向在周期内没有获得清晰选择。",
        )
    return _closed_acceptance(
        "等待市场选择但周期未验证",
        "周期结束时没有足够证据归入其他验收结论。",
    )


def _snapshot_relative_path(trade_date):
    return f"data/decision-ledger/{trade_date}.json"


def _case_index_record(case, snapshot_path, trade_date):
    record = {
        "case_id": case.get("case_id"),
        "stock_code": case.get("stock_code"),
        "stock_name": case.get("stock_name"),
        "first_seen_trade_date": case.get("first_seen_trade_date"),
        "cycle_start_trade_date": case.get("cycle_start_trade_date"),
        "cycle_day": case.get("cycle_day"),
        "cycle_length_trade_days": case.get("cycle_length_trade_days", DEFAULT_CYCLE_LENGTH_TRADE_DAYS),
        "latest_trade_date": trade_date,
        "status": (case.get("validation") or {}).get("status"),
        "snapshot_path": snapshot_path,
        "cycle_closed": (case.get("cycle_acceptance") or {}).get("status") == "closed",
        "mentions": list(case.get("mentions") or []),
    }
    planned_participation = case.get("planned_participation") or {}
    if isinstance(planned_participation, dict) and planned_participation:
        record["planned_participation"] = planned_participation
    hypothesis = case.get("hypothesis") or {}
    if isinstance(hypothesis, dict) and hypothesis:
        record["hypothesis"] = dict(hypothesis)
    participation_review = case.get("participation_review") or {}
    if isinstance(participation_review, dict) and participation_review:
        record["participation_review_status"] = participation_review.get("status")
        record["participation_review"] = {
            "status": participation_review.get("status"),
            "review_trade_date": participation_review.get("review_trade_date"),
            "planned_window": participation_review.get("planned_window"),
            "participation_window_type": participation_review.get("participation_window_type"),
            "attack_state": participation_review.get("attack_state"),
            "matched_steps": list(participation_review.get("matched_steps") or []),
            "evidence": participation_review.get("evidence"),
            "reason": participation_review.get("reason"),
            "entry_decision": participation_review.get("entry_decision"),
            "same_day_action": participation_review.get("same_day_action"),
            "avoid_action": participation_review.get("avoid_action"),
            "next_action": participation_review.get("next_action"),
            "standard_answer_basis": participation_review.get("standard_answer_basis"),
            "market_outcome": participation_review.get("market_outcome"),
        }
    return record


def build_decision_ledger_index(snapshot, previous_index=None):
    previous_index = _sanitize_decision_ledger_index(previous_index or {})
    snapshot = _sanitize_decision_ledger_snapshot(snapshot or {})
    trade_date = snapshot.get("trade_date")
    snapshot_path = _snapshot_relative_path(trade_date)
    available_dates = set(previous_index.get("available_trade_dates") or [])
    if trade_date:
        available_dates.add(trade_date)

    snapshots = [
        item
        for item in list(previous_index.get("snapshots") or [])
        if item.get("trade_date") != trade_date
    ]
    cases = list(snapshot.get("cases") or [])
    snapshots.append(
        {
            "trade_date": trade_date,
            "path": snapshot_path,
            "case_count": len(cases),
            "open_case_count": sum(1 for case in cases if (case.get("cycle_acceptance") or {}).get("status") != "closed"),
        }
    )
    snapshots.sort(key=lambda item: item.get("trade_date") or "")

    by_stock_code = {
        code: list(records or [])
        for code, records in (previous_index.get("by_stock_code") or {}).items()
    }
    for case in cases:
        stock_code = case.get("stock_code")
        if not stock_code:
            continue
        records = [
            record
            for record in by_stock_code.get(stock_code, [])
            if record.get("case_id") != case.get("case_id")
        ]
        records.append(_case_index_record(case, snapshot_path, trade_date))
        by_stock_code[stock_code] = records

    return {
        "artifact_version": ARTIFACT_VERSION,
        "latest_trade_date": max(available_dates) if available_dates else trade_date,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "selection_input_hash_by_trade_date": {
            **(previous_index.get("selection_input_hash_by_trade_date") or {}),
            trade_date: snapshot.get("selection_input_hash"),
        },
        "available_trade_dates": sorted(available_dates),
        "snapshots": snapshots,
        "by_stock_code": by_stock_code,
        "extreme_conviction_backtest_rows": build_extreme_conviction_backtest_rows(
            {"by_stock_code": by_stock_code},
            max_rows=25,
        ),
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json_if_exists(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _latest_mention(record):
    mentions = list((record or {}).get("mentions") or [])
    return mentions[-1] if mentions else {}


def _record_planned_participation(record):
    latest = _latest_mention(record)
    planned = (record or {}).get("planned_participation") or latest.get("planned_participation") or {}
    return planned if isinstance(planned, dict) else {}


def _record_is_extreme_conviction(record):
    latest = _latest_mention(record)
    planned = _record_planned_participation(record)
    return planned.get("source_tier") == "extreme_conviction" or "极度看好" in str(latest.get("source_section") or "")


def _mention_source_tier(mention, fallback_planned=None):
    planned = mention.get("planned_participation") or fallback_planned or {}
    if isinstance(planned, dict) and planned.get("source_tier"):
        return planned.get("source_tier")
    if "极度看好" in str(mention.get("source_section") or ""):
        return "extreme_conviction"
    return ""


def _review_is_rewritable(review):
    status = _clean_text((review or {}).get("status"))
    return not status or status in {"等待复盘", "等待窗口复盘"}


def _latest_unreviewed_extreme_mention(record, trade_date):
    if not record or record.get("cycle_closed"):
        return None
    planned = _record_planned_participation(record)
    if not planned:
        return None
    for mention in reversed(list(record.get("mentions") or [])):
        mention_date = str(mention.get("mention_trade_date") or "").strip()
        if not mention_date or not trade_date or not mention_date < str(trade_date):
            continue
        if not _review_is_rewritable(mention.get("participation_review")):
            continue
        if _mention_source_tier(mention, planned) != "extreme_conviction":
            continue
        return mention
    return None


def _record_needs_participation_review(record, trade_date):
    return _latest_unreviewed_extreme_mention(record, trade_date) is not None


def _extract_kline_rows(payload, stock_code):
    payload = payload or {}
    if isinstance(payload.get("rows"), list):
        return list(payload.get("rows") or [])
    stock_klines = payload.get("stock_klines") or payload.get("stockKlines") or {}
    if isinstance(stock_klines, dict):
        rows = stock_klines.get(stock_code) or stock_klines.get(_normalize_stock_code(stock_code)) or []
        return list(rows or []) if isinstance(rows, list) else []
    if isinstance(stock_klines, list):
        return list(stock_klines)
    return []


def _extract_minute_rows(payload, stock_code):
    payload = payload or {}
    for key in ("rows", "minute_bars", "minuteBars", "intraday_bars", "intradayBars", "minutes"):
        if isinstance(payload.get(key), list):
            return list(payload.get(key) or [])
    stock_minutes = payload.get("stock_minute_bars") or payload.get("stockMinuteBars") or payload.get("stock_minutes")
    if isinstance(stock_minutes, dict):
        rows = stock_minutes.get(stock_code) or stock_minutes.get(_normalize_stock_code(stock_code)) or []
        return list(rows or []) if isinstance(rows, list) else []
    return []


def _bar_date(row):
    return str((row or {}).get("date") or (row or {}).get("trade_date") or "").strip()


def _market_fact_from_rows(record, trade_date, rows):
    rows = sorted([row for row in list(rows or []) if _bar_date(row)], key=_bar_date)
    if not rows:
        return None
    mention = _latest_unreviewed_extreme_mention(record, trade_date) or _latest_mention(record)
    mention_date = str(mention.get("mention_trade_date") or record.get("latest_trade_date") or "").strip()
    review_bar = next((row for row in rows if _bar_date(row) == trade_date), None)
    if not review_bar:
        return None

    prev_bar = None
    if mention_date:
        prev_bar = next((row for row in rows if _bar_date(row) == mention_date), None)
    if not prev_bar:
        review_index = rows.index(review_bar)
        prev_bar = rows[review_index - 1] if review_index > 0 else None
    if not prev_bar:
        return None

    return {
        "stock_code": record.get("stock_code"),
        "stock_name": record.get("stock_name"),
        "review_trade_date": trade_date,
        "prev_close": prev_bar.get("close"),
        "open": review_bar.get("open"),
        "high": review_bar.get("high"),
        "low": review_bar.get("low"),
        "close": review_bar.get("close"),
        "volume": review_bar.get("volume"),
        "prev_volume": prev_bar.get("volume"),
    }


def _load_local_stock_kline_fact(root, record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    if not stock_code:
        return None
    candidates = [
        root / "data" / "snap-ui" / "stock-klines" / f"{trade_date}-{stock_code}.json",
        root / "snap-ui" / "public" / "data" / "snap-ui" / "stock-klines" / f"{trade_date}-{stock_code}.json",
    ]
    for path in candidates:
        payload = _read_json_if_exists(path)
        rows = _extract_kline_rows(payload, stock_code)
        fact = _market_fact_from_rows(record, trade_date, rows)
        if fact:
            return fact
    return None


def _load_local_stock_minute_fact(root, record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    if not stock_code:
        return {}
    candidates = [
        root / "data" / "snap-ui" / "stock-minute-bars" / f"{trade_date}-{stock_code}.json",
        root / "snap-ui" / "public" / "data" / "snap-ui" / "stock-minute-bars" / f"{trade_date}-{stock_code}.json",
    ]
    for path in candidates:
        payload = _read_json_if_exists(path)
        rows = _extract_minute_rows(payload, stock_code)
        if not rows:
            continue
        fact = {"minute_bars": rows}
        reference_price = _safe_float(
            payload.get("windowReferencePrice")
            or payload.get("window_reference_price")
            or payload.get("intradayYellowLinePrice")
            or payload.get("intraday_yellow_line_price")
            or payload.get("yellowLinePrice")
            or payload.get("yellow_line_price")
        )
        if reference_price is not None:
            fact["window_reference_price"] = reference_price
        return fact
    return {}


def _fetch_stock_minute_fact(record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    if not stock_code:
        return {}
    try:
        from market_data.tushare_minute_service import fetch_tushare_minute_bars

        rows = fetch_tushare_minute_bars(stock_code, period="5", target_date=trade_date)
    except Exception:
        rows = []
    return {"minute_bars": rows} if rows else {}


def _fetch_stock_kline_fact(record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    mention = _latest_unreviewed_extreme_mention(record, trade_date) or _latest_mention(record)
    mention_date = str(mention.get("mention_trade_date") or record.get("latest_trade_date") or "").strip()
    if not stock_code or not mention_date:
        return None
    try:
        from market_data.daily_price_runtime import fetch_daily_price_bars

        rows = fetch_daily_price_bars(stock_code, mention_date, trade_date, prefer_fast=True)
    except Exception:
        rows = []
    return _market_fact_from_rows(record, trade_date, rows)


def _load_review_market_facts(root, trade_date, previous_index):
    facts = {}
    for records in (previous_index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            if not _record_needs_participation_review(record, trade_date):
                continue
            code = _normalize_stock_code(record.get("stock_code"))
            fact = _load_local_stock_kline_fact(root, record, trade_date) or _fetch_stock_kline_fact(record, trade_date)
            if fact:
                minute_fact = _load_local_stock_minute_fact(root, record, trade_date) or _fetch_stock_minute_fact(record, trade_date)
                if minute_fact:
                    fact = {**fact, **minute_fact}
                facts[code] = fact
    return facts


def _compact_participation_review_for_index(review):
    review = review or {}
    return {
        "status": review.get("status"),
        "review_trade_date": review.get("review_trade_date"),
        "planned_window": review.get("planned_window"),
        "participation_window_type": review.get("participation_window_type"),
        "attack_state": review.get("attack_state"),
        "matched_steps": list(review.get("matched_steps") or []),
        "evidence": review.get("evidence"),
        "reason": review.get("reason"),
        "entry_decision": review.get("entry_decision"),
        "same_day_action": review.get("same_day_action"),
        "avoid_action": review.get("avoid_action"),
        "next_action": review.get("next_action"),
        "standard_answer_basis": review.get("standard_answer_basis"),
        "market_outcome": review.get("market_outcome"),
    }


def _clean_markdown_cell(value, default="-"):
    text = _clean_text(value, default)
    return text.replace("|", "/") or default


def _tracking_sort_key(record):
    return (
        bool(record.get("cycle_closed")),
        -int(record.get("cycle_day") or 0),
        str(record.get("cycle_start_trade_date") or ""),
        str(record.get("stock_code") or ""),
    )


def render_extreme_conviction_tracking_lines(index, *, max_rows=8):
    index = index or {}
    rows = []
    for records in (index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            if not _record_is_extreme_conviction(record):
                continue
            if record.get("cycle_closed"):
                continue
            planned = _record_planned_participation(record)
            review = record.get("participation_review") or {}
            rows.append(
                {
                    "stock_name": record.get("stock_name"),
                    "stock_code": record.get("stock_code"),
                    "cycle": f"D{record.get('cycle_day') or 1}/{record.get('cycle_length_trade_days') or DEFAULT_CYCLE_LENGTH_TRADE_DAYS}",
                    "first_seen": record.get("cycle_start_trade_date") or record.get("first_seen_trade_date"),
                    "latest": record.get("latest_trade_date"),
                    "planned_window": planned.get("participation_window"),
                    "buy_window": planned.get("buy_window"),
                    "review_status": review.get("status") or record.get("participation_review_status") or record.get("status"),
                    "next_action": review.get("next_action") or review.get("same_day_action") or "等待下一次参与窗口确认",
                    "invalidation": planned.get("ma20_invalidation") or planned.get("cancellation") or "按原计划作废条件处理",
                    "_record": record,
                }
            )

    lines = ["**重点观察25日跟踪表**（只展示仍在周期内的样本）:"]
    if not rows:
        lines.append("- 暂无仍在25日周期内的重点观察样本。")
        lines.append("")
        return lines

    rows.sort(key=lambda item: _tracking_sort_key(item["_record"]))
    lines.append("| 股票 | 代码 | 周期日 | 首次入选 | 最近复盘 | 计划窗口 | 买入窗口 | 预演复盘 | 下一步动作 | 作废线 |")
    lines.append("|------|------|--------|----------|----------|----------|----------|----------|------------|--------|")
    for row in rows[:max_rows]:
        lines.append(
            "| {stock_name} | {stock_code} | {cycle} | {first_seen} | {latest} | {planned_window} | {buy_window} | {review_status} | {next_action} | {invalidation} |".format(
                stock_name=_clean_markdown_cell(row.get("stock_name")),
                stock_code=_clean_markdown_cell(row.get("stock_code")),
                cycle=_clean_markdown_cell(row.get("cycle")),
                first_seen=_clean_markdown_cell(row.get("first_seen")),
                latest=_clean_markdown_cell(row.get("latest")),
                planned_window=_clean_markdown_cell(row.get("planned_window")),
                buy_window=_clean_markdown_cell(row.get("buy_window")),
                review_status=_clean_markdown_cell(row.get("review_status")),
                next_action=_clean_markdown_cell(row.get("next_action")),
                invalidation=_clean_markdown_cell(row.get("invalidation")),
            )
        )
    lines.append("")
    return lines


def _record_first_mention_date(record):
    mentions = list((record or {}).get("mentions") or [])
    for mention in mentions:
        mention_date = _clean_text(mention.get("mention_trade_date"))
        if mention_date:
            return mention_date
    return _clean_text((record or {}).get("cycle_start_trade_date") or (record or {}).get("first_seen_trade_date"))


def _risk_reward_label(planned):
    planned = planned or {}
    state = _clean_text(planned.get("risk_reward_state"))
    ratio = _round_or_none(planned.get("risk_reward_ratio"), 2)
    if ratio is not None:
        ratio_text = f"{ratio:g}:1"
        return f"{state} {ratio_text}".strip()
    plan = _clean_text(planned.get("risk_reward_plan"))
    if plan:
        return f"{state} {plan}".strip()
    min_ratio = _round_or_none(planned.get("risk_reward_min_ratio"), 2)
    if min_ratio is not None:
        return f"{state} 默认不低于{min_ratio:g}:1".strip()
    return state or "待补充"


def _selection_quality_label(planned):
    planned = planned or {}
    level = _clean_text(planned.get("limit_up_inertia_level"), "待验证")
    probability = _clean_text(planned.get("next_day_limit_probability_band"))
    return f"{level} / {probability}" if probability else level


def _extreme_conviction_mentions(record):
    planned = _record_planned_participation(record)
    mentions = []
    seen_keys = set()
    for mention in list((record or {}).get("mentions") or []):
        if _mention_source_tier(mention, planned) != "extreme_conviction":
            continue
        key = _mention_identity(mention)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        mentions.append(mention)
    return mentions


def _mention_planned_participation(mention, record):
    planned = (mention or {}).get("planned_participation") or _record_planned_participation(record)
    return planned if isinstance(planned, dict) else {}


def _mention_participation_review(mention, record, extreme_mention_count):
    review = (mention or {}).get("participation_review") or {}
    if isinstance(review, dict) and review:
        return review
    if extreme_mention_count == 1:
        fallback = (record or {}).get("participation_review") or {}
        return fallback if isinstance(fallback, dict) else {}
    return {}


def _buy_point_quality_label(review):
    review = review or {}
    status = _clean_text(review.get("status"))
    decision = _clean_text(review.get("entry_decision"))
    if status == "主目标不可成交" or decision == "unavailable":
        return "主目标不可成交"
    if status == "预演作废" or decision == "skip":
        return "买点作废"
    if status == "预演过早":
        return "买点过早"
    if decision in {"open_buy", "ten_confirm_buy", "tail_confirm"} or status == "预演命中":
        return "买点成立"
    if status == "错过后方案命中":
        return "错过后方案成立"
    if status == "等待复盘":
        return "等待复盘"
    return status or "等待事实"


def build_extreme_conviction_backtest_rows(index, *, max_rows=12):
    index = index or {}
    rows = []
    for records in (index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            extreme_mentions = _extreme_conviction_mentions(record)
            if not extreme_mentions and _record_is_extreme_conviction(record):
                extreme_mentions = [_latest_mention(record)]
            if not extreme_mentions:
                continue
            for mention in extreme_mentions:
                planned = _mention_planned_participation(mention, record)
                review = _mention_participation_review(mention, record, len(extreme_mentions))
                rows.append(
                    {
                        "mention_trade_date": _clean_text(mention.get("mention_trade_date"))
                        or _record_first_mention_date(record),
                        "stock_name": record.get("stock_name"),
                        "stock_code": record.get("stock_code"),
                        "rank": mention.get("rank"),
                        "source_section": mention.get("source_section") or "",
                        "reason": mention.get("reason") or "",
                        "sector_candidate": _sector_from_case_or_record(record),
                        "selection_quality": _selection_quality_label(planned),
                        "buy_window": planned.get("buy_window") or planned.get("participation_window"),
                        "risk_reward": _risk_reward_label(planned),
                        "buy_point_quality": _buy_point_quality_label(review),
                        "review_status": review.get("status") or "等待复盘",
                        "standard_action": review.get("same_day_action") or review.get("next_action") or "等待计划窗口事实回写",
                        "market_outcome": review.get("market_outcome") or "",
                    }
                )
    rows.sort(
        key=lambda item: (
            str(item.get("mention_trade_date") or ""),
            str(item.get("stock_code") or ""),
        ),
        reverse=True,
    )
    return rows[:max_rows]


def render_extreme_conviction_backtest_lines(index, *, max_rows=12):
    rows = build_extreme_conviction_backtest_rows(index, max_rows=max_rows)
    lines = ["**重点观察历史回测表**（拆分选股样本、买点质量、执行复盘）:"]
    if not rows:
        lines.append("- 暂无可复盘的重点观察历史样本。")
        lines.append("")
        return lines

    lines.append("| 入选日 | 股票 | 代码 | 选股样本 | 买点窗口 | 盈亏比 | 买点质量 | 执行复盘 | 标准动作 |")
    lines.append("|--------|------|------|----------|----------|--------|----------|----------|----------|")
    for row in rows:
        lines.append(
            "| {mention_trade_date} | {stock_name} | {stock_code} | {selection_quality} | {buy_window} | {risk_reward} | {buy_point_quality} | {review_status} | {standard_action} |".format(
                mention_trade_date=_clean_markdown_cell(row.get("mention_trade_date")),
                stock_name=_clean_markdown_cell(row.get("stock_name")),
                stock_code=_clean_markdown_cell(row.get("stock_code")),
                selection_quality=_clean_markdown_cell(row.get("selection_quality")),
                buy_window=_clean_markdown_cell(row.get("buy_window")),
                risk_reward=_clean_markdown_cell(row.get("risk_reward")),
                buy_point_quality=_clean_markdown_cell(row.get("buy_point_quality")),
                review_status=_clean_markdown_cell(row.get("review_status")),
                standard_action=_clean_markdown_cell(row.get("standard_action")),
            )
        )
    lines.append("")
    return lines


def _attach_review_to_latest_prior_mention(record, trade_date, review):
    mentions = [dict(item) for item in list((record or {}).get("mentions") or [])]
    compact_review = _compact_participation_review_for_index(review)
    planned = _record_planned_participation(record)
    for index in range(len(mentions) - 1, -1, -1):
        mention_date = str(mentions[index].get("mention_trade_date") or "").strip()
        if (
            mention_date
            and str(mention_date) < str(trade_date)
            and _review_is_rewritable(mentions[index].get("participation_review"))
            and _mention_source_tier(mentions[index], planned) == "extreme_conviction"
        ):
            mentions[index]["participation_review"] = compact_review
            return mentions
    return mentions


def _apply_participation_reviews_to_previous_index(previous_index, trade_date, review_market_facts_by_stock_code=None):
    previous_index = previous_index or {}
    facts_by_code = {
        _normalize_stock_code(code): dict(fact or {})
        for code, fact in (review_market_facts_by_stock_code or {}).items()
        if _normalize_stock_code(code)
    }
    if not facts_by_code:
        return previous_index

    updated_index = dict(previous_index)
    updated_by_stock_code = {}
    for code, records in (previous_index.get("by_stock_code") or {}).items():
        normalized_code = _normalize_stock_code(code)
        fact = facts_by_code.get(normalized_code)
        updated_records = []
        for record in list(records or []):
            if not fact or not _record_needs_participation_review(record, trade_date):
                updated_records.append(record)
                continue
            planned = _record_planned_participation(record)
            review_facts = build_participation_review_facts_from_market_fact(
                planned,
                {
                    **fact,
                    "stock_code": record.get("stock_code") or normalized_code,
                    "stock_name": record.get("stock_name"),
                    "review_trade_date": fact.get("review_trade_date") or trade_date,
                },
            )
            review = classify_planned_participation_review(planned, **review_facts)
            compact_review = _compact_participation_review_for_index(review)
            updated_record = {
                **record,
                "latest_trade_date": trade_date,
                "participation_review_status": review.get("status"),
                "participation_review": compact_review,
                "mentions": _attach_review_to_latest_prior_mention(record, trade_date, review),
            }
            updated_records.append(updated_record)
        updated_by_stock_code[code] = updated_records
    updated_index["by_stock_code"] = updated_by_stock_code
    return updated_index


def write_decision_ledger_artifacts(snapshot, *, root_dir=".", review_market_facts_by_stock_code=None):
    root = Path(root_dir)
    snapshot = _sanitize_decision_ledger_snapshot(snapshot or {})
    trade_date = snapshot.get("trade_date")
    ledger_dir = root / "data" / "decision-ledger"
    snapshot_path = ledger_dir / f"{trade_date}.json"
    index_path = ledger_dir / "index.json"
    previous_index = _sanitize_decision_ledger_index(_read_json_if_exists(index_path))
    if review_market_facts_by_stock_code is None:
        review_market_facts_by_stock_code = _load_review_market_facts(root, trade_date, previous_index)
    previous_index = _apply_participation_reviews_to_previous_index(
        previous_index,
        trade_date,
        review_market_facts_by_stock_code=review_market_facts_by_stock_code,
    )
    previous_index = _sanitize_decision_ledger_index(previous_index)
    previous_index = _prune_replaced_same_day_records(previous_index, snapshot)
    merged_snapshot = _sanitize_decision_ledger_snapshot(merge_snapshot_with_previous_index(snapshot, previous_index))
    index = build_decision_ledger_index(merged_snapshot, previous_index=previous_index)
    _write_json(snapshot_path, merged_snapshot)
    _write_json(index_path, index)
    return {
        "snapshot_path": str(snapshot_path),
        "index_path": str(index_path),
        "case_count": len(merged_snapshot.get("cases") or []),
        "index": index,
    }


def _relative_report_path(report_path, root_dir):
    path = Path(report_path)
    root = Path(root_dir)
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_decision_ledger_artifacts_from_markdown_report(
    report_path,
    *,
    trade_date,
    market_branch,
    sector_relationship_state,
    root_dir=".",
    generated_at=None,
):
    report_file = Path(report_path)
    root = Path(root_dir)
    snapshot = build_decision_ledger_snapshot_from_markdown_report(
        report_file.read_text(encoding="utf-8"),
        trade_date=trade_date,
        market_branch=market_branch,
        sector_relationship_state=sector_relationship_state,
        source_report={
            "path": _relative_report_path(report_file, root),
            "variant": "full",
        },
        generated_at=generated_at,
    )
    return write_decision_ledger_artifacts(snapshot, root_dir=root)


def build_decision_ledger_snapshot(
    *,
    trade_date,
    extreme_conviction_list,
    market_branch,
    sector_relationship_state,
    source_report=None,
    generated_at=None,
):
    cases = []
    for idx, item in enumerate(list(extreme_conviction_list or []), 1):
        stock_code = _normalize_stock_code(item.get("code") or item.get("stock_code"))
        stock_name = _clean_text(item.get("name") or item.get("stock_name"), stock_code or "判断样本")
        sector = _resolve_sector_candidate(item, "未归类")
        normalized_item = {**item, "sector": sector}
        case = {
            "case_id": _build_case_id(trade_date, stock_code, 1),
            "stock_code": stock_code,
            "stock_name": stock_name,
            "first_seen_trade_date": trade_date,
            "cycle_start_trade_date": trade_date,
            "cycle_day": 1,
            "cycle_length_trade_days": DEFAULT_CYCLE_LENGTH_TRADE_DAYS,
            "mentions": [_build_mention(normalized_item, trade_date=trade_date, rank=idx)],
            "hypothesis": {
                "stock_setup": _build_stock_setup(normalized_item),
                "sector_candidate": sector,
                "market_branch": _clean_text(market_branch, "待验证市场演变"),
                "sector_relationship_state": _clean_text(sector_relationship_state, "暂未分出"),
            },
            "validation": {
                "status": "等待市场选择",
                "selection_confirmed_date": None,
                "selection_confirmed_evidence": None,
                "sector_selection_evidence": None,
                "stock_acceptance_evidence": None,
            },
            "trend_fate": {
                "label": None,
                "elimination_event": None,
                "missed_upside_after_elimination": None,
            },
            "cycle_acceptance": {
                "status": "open",
                "final_label": None,
                "reason": None,
                "iteration_note": None,
            },
        }
        core_identity = normalized_item.get("core_identity")
        if isinstance(core_identity, dict) and core_identity:
            case["core_identity"] = core_identity
        planned_participation = _build_planned_participation(normalized_item)
        if planned_participation:
            case["planned_participation"] = planned_participation
            review_facts = normalized_item.get("participation_review_facts") or normalized_item.get("planned_participation_review_facts") or {}
            if isinstance(review_facts, dict) and review_facts:
                case["participation_review"] = classify_planned_participation_review(
                    planned_participation,
                    **review_facts,
                )
        cases.append(case)

    return {
        "artifact_version": ARTIFACT_VERSION,
        "trade_date": trade_date,
        "generated_at": generated_at,
        "frozen": True,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "selection_input_hash": _selection_input_hash(
            trade_date=trade_date,
            extreme_conviction_list=extreme_conviction_list,
            market_branch=market_branch,
            sector_relationship_state=sector_relationship_state,
        ),
        "source_report": source_report or {},
        "cases": cases,
    }


def build_decision_ledger_snapshot_from_markdown_report(
    markdown_text,
    *,
    trade_date,
    market_branch,
    sector_relationship_state,
    source_report=None,
    generated_at=None,
):
    return build_decision_ledger_snapshot(
        trade_date=trade_date,
        extreme_conviction_list=parse_extreme_conviction_list_from_markdown(markdown_text),
        market_branch=market_branch,
        sector_relationship_state=sector_relationship_state,
        source_report=source_report,
        generated_at=generated_at,
    )


def merge_snapshot_with_previous_index(snapshot, previous_index=None):
    merged = {**(snapshot or {})}
    merged_cases = []
    trade_date = merged.get("trade_date")
    for case in list(merged.get("cases") or []):
        stock_code = case.get("stock_code")
        previous_case = _find_open_previous_case(previous_index, stock_code)
        if previous_case:
            mentions = _merge_mentions_without_duplicates(
                _copy_mentions(previous_case),
                case.get("mentions") or [],
            )
            previous_review = previous_case.get("participation_review") or {}
            case = {
                **case,
                "case_id": previous_case.get("case_id") or case.get("case_id"),
                "first_seen_trade_date": previous_case.get("cycle_start_trade_date")
                or previous_case.get("first_seen_trade_date")
                or case.get("first_seen_trade_date"),
                "cycle_start_trade_date": previous_case.get("cycle_start_trade_date")
                or case.get("cycle_start_trade_date"),
                "cycle_day": _cycle_day_from_dates(
                    previous_case.get("cycle_start_trade_date") or case.get("cycle_start_trade_date"),
                    trade_date,
                ),
                "mentions": mentions,
            }
            if previous_review and not case.get("participation_review"):
                case["participation_review"] = previous_review
            sector = _clean_text((case.get("hypothesis") or {}).get("sector_candidate"))
            if _is_valid_sector_label(sector):
                case = _sanitize_sector_references(case, sector)
        merged_cases.append(case)
    merged["cases"] = merged_cases
    return merged


__all__ = [
    "build_decision_ledger_snapshot",
    "build_decision_ledger_snapshot_from_markdown_report",
    "build_extreme_conviction_backtest_rows",
    "build_participation_review_facts_from_market_fact",
    "build_decision_ledger_index",
    "classify_cycle_acceptance",
    "classify_planned_participation_review",
    "classify_validation_state",
    "merge_snapshot_with_previous_index",
    "parse_extreme_conviction_list_from_markdown",
    "prune_replaced_same_day_extreme_mentions",
    "render_extreme_conviction_backtest_lines",
    "render_extreme_conviction_tracking_lines",
    "write_decision_ledger_artifacts",
    "write_decision_ledger_artifacts_from_markdown_report",
]
