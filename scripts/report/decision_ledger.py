from __future__ import annotations

import hashlib
import json
from pathlib import Path
from selection.candidate_execution_contracts import (
    build_participation_window_from_candidate,
    build_participation_window_policy,
)

ARTIFACT_VERSION = 1
DEFAULT_CYCLE_LENGTH_TRADE_DAYS = 25
SELECTION_RULE_VERSION = "extreme-conviction-ledger-v1"


def _normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return "".join(ch for ch in text if ch.isdigit()) or text


def _clean_text(value, default=""):
    text = str(value or "").strip()
    return text or default


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
                "sector": _clean_text(item.get("sector") or item.get("sector_candidate")),
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
        else:
            preserved[key] = value
    return preserved


def _default_participation_script(item):
    item = item or {}
    sector = _clean_text(item.get("sector") or item.get("sector_candidate"), "主线")
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
    planned.update(build_participation_window_policy(window, missed))
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
    planned.update(build_participation_window_policy(planned.get("participation_window"), planned.get("missed_action")))
    for key in (
        "participation_window_type",
        "auction_required",
        "first_minutes_required",
        "board_or_reseal_required",
        "ordinary_structure_confirm_allowed",
        "missed_entry_policy",
    ):
        if key in script:
            planned[key] = script[key]
    return planned


def classify_planned_participation_review(
    planned_participation=None,
    *,
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

    if cancellation_triggered:
        base.update(
            {
                "status": "预演作废",
                "reason": "作废条件出现，原参与方案不再成立。",
                "evidence": _clean_text(cancellation_evidence, base["evidence"] or "作废条件已触发"),
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


def _parse_participation_scripts(lines):
    header, rows = _parse_markdown_table_after_heading(lines, "极度看好参与脚本")
    if not header:
        return []

    window_idx = _header_index(header, "参与窗口")
    attack_idx = _header_index(header, "仓位三态", "进攻仓位三态")
    auction_idx = _header_index(header, "集合竞价", "竞价表态")
    first_minutes_idx = _header_index(header, "开盘前几分钟", "开盘前分钟")
    board_idx = _header_index(header, "打板策略", "打板")
    reseal_idx = _header_index(header, "回封参与", "回封")
    missed_idx = _header_index(header, "错过后动作")
    cancel_idx = _header_index(header, "作废条件", "取消条件")

    scripts = []
    for row in rows:
        def _cell(index):
            return row[index].strip() if 0 <= index < len(row) else ""

        scripts.append(
            {
                "participation_window": _clean_text(_cell(window_idx)),
                "attack_state": _clean_text(_cell(attack_idx)),
                "auction": _clean_text(_cell(auction_idx)),
                "first_minutes": _clean_text(_cell(first_minutes_idx)),
                "board": _clean_text(_cell(board_idx)),
                "reseal": _clean_text(_cell(reseal_idx)),
                "missed_action": _clean_text(_cell(missed_idx)),
                "cancellation": _clean_text(_cell(cancel_idx)),
            }
        )
    return scripts


def parse_extreme_conviction_list_from_markdown(markdown_text):
    lines = str(markdown_text or "").splitlines()
    header, rows = _parse_markdown_table_after_heading(lines, "极度看好名单")

    if not header:
        return []

    rank_idx = _header_index(header, "优先级", "排名")
    name_idx = _header_index(header, "股票", "名称")
    code_idx = _header_index(header, "代码", "股票代码")
    sector_idx = _header_index(header, "所属板块", "板块", "所属方向")
    reason_idx = _header_index(header, "极看理由", "理由")
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
    participation_review = case.get("participation_review") or {}
    if isinstance(participation_review, dict) and participation_review:
        record["participation_review_status"] = participation_review.get("status")
        record["participation_review"] = {
            "status": participation_review.get("status"),
            "planned_window": participation_review.get("planned_window"),
            "participation_window_type": participation_review.get("participation_window_type"),
            "attack_state": participation_review.get("attack_state"),
            "matched_steps": list(participation_review.get("matched_steps") or []),
            "evidence": participation_review.get("evidence"),
            "reason": participation_review.get("reason"),
        }
    return record


def build_decision_ledger_index(snapshot, previous_index=None):
    previous_index = previous_index or {}
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


def write_decision_ledger_artifacts(snapshot, *, root_dir="."):
    root = Path(root_dir)
    trade_date = snapshot.get("trade_date")
    ledger_dir = root / "data" / "decision-ledger"
    snapshot_path = ledger_dir / f"{trade_date}.json"
    index_path = ledger_dir / "index.json"
    previous_index = _read_json_if_exists(index_path)
    merged_snapshot = merge_snapshot_with_previous_index(snapshot, previous_index)
    index = build_decision_ledger_index(merged_snapshot, previous_index=previous_index)
    _write_json(snapshot_path, merged_snapshot)
    _write_json(index_path, index)
    return {
        "snapshot_path": str(snapshot_path),
        "index_path": str(index_path),
        "case_count": len(merged_snapshot.get("cases") or []),
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
        sector = _clean_text(item.get("sector") or item.get("sector_candidate"), "未归类")
        case = {
            "case_id": _build_case_id(trade_date, stock_code, 1),
            "stock_code": stock_code,
            "stock_name": stock_name,
            "first_seen_trade_date": trade_date,
            "cycle_start_trade_date": trade_date,
            "cycle_day": 1,
            "cycle_length_trade_days": DEFAULT_CYCLE_LENGTH_TRADE_DAYS,
            "mentions": [_build_mention(item, trade_date=trade_date, rank=idx)],
            "hypothesis": {
                "stock_setup": _build_stock_setup(item),
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
        core_identity = item.get("core_identity")
        if isinstance(core_identity, dict) and core_identity:
            case["core_identity"] = core_identity
        planned_participation = _build_planned_participation(item)
        if planned_participation:
            case["planned_participation"] = planned_participation
            review_facts = item.get("participation_review_facts") or item.get("planned_participation_review_facts") or {}
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
            mentions = _copy_mentions(previous_case)
            mentions.extend(case.get("mentions") or [])
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
        merged_cases.append(case)
    merged["cases"] = merged_cases
    return merged


__all__ = [
    "build_decision_ledger_snapshot",
    "build_decision_ledger_snapshot_from_markdown_report",
    "build_decision_ledger_index",
    "classify_cycle_acceptance",
    "classify_planned_participation_review",
    "classify_validation_state",
    "merge_snapshot_with_previous_index",
    "parse_extreme_conviction_list_from_markdown",
    "write_decision_ledger_artifacts",
    "write_decision_ledger_artifacts_from_markdown_report",
]
