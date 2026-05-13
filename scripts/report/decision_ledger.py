from __future__ import annotations

import json
from pathlib import Path

ARTIFACT_VERSION = 1
DEFAULT_CYCLE_LENGTH_TRADE_DAYS = 25


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


def _build_mention(item, *, trade_date, rank):
    return {
        "mention_trade_date": trade_date,
        "rank": rank,
        "source_section": "极度看好名单",
        "reason": _clean_text(
            item.get("conviction_reason") or item.get("reason") or item.get("conviction_rule"),
            "判断理由待补充",
        ),
    }


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


def parse_extreme_conviction_list_from_markdown(markdown_text):
    lines = str(markdown_text or "").splitlines()
    table_start = -1
    for idx, line in enumerate(lines):
        if "极度看好名单" in line:
            table_start = idx + 1
            break
    if table_start < 0:
        return []

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

    if not header:
        return []

    rank_idx = _header_index(header, "优先级", "排名")
    name_idx = _header_index(header, "股票", "名称")
    code_idx = _header_index(header, "代码", "股票代码")
    sector_idx = _header_index(header, "所属板块", "板块", "所属方向")
    reason_idx = _header_index(header, "极看理由", "理由")
    rule_idx = _header_index(header, "明日原则", "原则")

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
        items.append(
            {
                "rank": rank,
                "name": name,
                "code": code,
                "sector": _clean_text(_cell(sector_idx), "未归类"),
                "conviction_reason": _clean_text(_cell(reason_idx), "判断理由待补充"),
                "conviction_rule": _clean_text(_cell(rule_idx), "明日原则待补充"),
            }
        )
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
    return {
        "case_id": case.get("case_id"),
        "stock_name": case.get("stock_name"),
        "cycle_start_trade_date": case.get("cycle_start_trade_date"),
        "latest_trade_date": trade_date,
        "status": (case.get("validation") or {}).get("status"),
        "snapshot_path": snapshot_path,
        "cycle_closed": (case.get("cycle_acceptance") or {}).get("status") == "closed",
        "mentions": list(case.get("mentions") or []),
    }


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
        cases.append(case)

    return {
        "artifact_version": ARTIFACT_VERSION,
        "trade_date": trade_date,
        "generated_at": generated_at,
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
    "classify_validation_state",
    "merge_snapshot_with_previous_index",
    "parse_extreme_conviction_list_from_markdown",
    "write_decision_ledger_artifacts",
    "write_decision_ledger_artifacts_from_markdown_report",
]
