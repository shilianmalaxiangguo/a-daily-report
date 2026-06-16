from pathlib import Path

from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot
from domains.market_state.two_market_turnover.node_registry import build_two_market_turnover_node_specs
from domains.market_state.two_market_turnover.node_runtime import run_two_market_turnover_nodes
from report.market_overview_node_registry import build_market_overview_node_specs
from report.market_overview_node_runtime import run_market_overview_nodes
from storage.database_service import DatabaseService


def _data(context):
    return context.get("data") or {}


def _target_date(context):
    return str(context.get("target_date", "") or "")


def _daily_fact_db_path(context):
    if (context or {}).get("daily_fact_db_path"):
        return Path((context or {}).get("daily_fact_db_path"))
    return None


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            if default is None:
                return None
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        if default is None:
            return None
        return float(default)


def evaluate_turnover_quality(market_data):
    """
    评估成交量质量，区分"做多放量"和"杀跌放量"。

    Args:
        market_data: 市场数据字典，包含total_turnover和market_stats

    Returns:
        dict: {
            "turnover_quality": str,  # "做多放量" / "杀跌放量" / "缩量"
            "turnover_quality_desc": str  # 描述
        }
    """
    market_data = market_data or {}

    # 获取两市成交额
    total_turnover = _safe_float(market_data.get("total_turnover"), 0.0)

    # 获取涨跌家数
    market_stats = market_data.get("market_stats") or {}
    up_count = _safe_float(market_stats.get("up_count"), 0.0)
    down_count = _safe_float(market_stats.get("down_count"), 0.0)

    # 处理数据缺失情况
    if total_turnover <= 0 or (up_count <= 0 and down_count <= 0):
        return {
            "turnover_quality": "待累计",
            "turnover_quality_desc": "成交量或涨跌家数数据不足，暂不判断成交量质量"
        }

    # 计算涨跌比
    if down_count > 0:
        rise_fall_ratio = up_count / down_count
    else:
        # 如果下跌家数为0，说明全部上涨，涨跌比视为无穷大
        rise_fall_ratio = float('inf')

    # 判断成交量质量
    if total_turnover > 30000:
        if rise_fall_ratio > 0.5:
            return {
                "turnover_quality": "做多放量",
                "turnover_quality_desc": "成交量充沛且上涨家数占优，赚钱效应较强"
            }
        else:
            return {
                "turnover_quality": "杀跌放量",
                "turnover_quality_desc": "成交量充沛但上涨家数不足，赚钱效应不足"
            }
    else:
        return {
            "turnover_quality": "缩量",
            "turnover_quality_desc": "成交量不足，先按缩量处理"
        }


def _price_band_absolute_label(high_pct, low_pct):
    high_pct = _safe_float(high_pct)
    low_pct = _safe_float(low_pct)
    if high_pct < 0 and low_pct < 0:
        return "同步回落"
    if high_pct > 0 and low_pct > 0:
        return "同步修复"
    if high_pct > 0 and low_pct <= 0:
        return "高价占优"
    if high_pct <= 0 and low_pct > 0:
        return "低价抗跌"
    return "待判断"


def _turnover_rank_amount(row):
    row = row or {}
    for key in ("turnover", "amount_yi", "turnover_yi", "成交额"):
        amount = _safe_float(row.get(key))
        if amount > 0:
            return amount
    return 0.0


def _top50_share_regime(share_pct):
    share_pct = _safe_float(share_pct)
    if share_pct < 18:
        return "冰点"
    if share_pct > 20:
        return "资金活跃期"
    return "震荡"


def _top50_share_interpretation(share_pct):
    regime = _top50_share_regime(share_pct)
    if regime == "冰点":
        return "Top50成交额占比低于18%，头部资金活跃度不足。"
    if regime == "资金活跃期":
        return "Top50成交额占比超过20%，雨量变大，资金处于活跃期。"
    return "Top50成交额占比处在18%到20%，市场仍以震荡结构看待。"


def _top20_capacity_regime(near_150_count, rank20_amount):
    near_150_count = int(near_150_count or 0)
    rank20_amount = _safe_float(rank20_amount)
    if near_150_count >= 18 or rank20_amount >= 145:
        return "高容量聚焦"
    if near_150_count >= 10 or rank20_amount >= 120:
        return "容量活跃"
    return "常规容量"


def resolve_top20_turnover_capacity(data):
    data = data or {}
    rank_rows = list(data.get("turnover_rank") or [])
    top20_rows = rank_rows[:20]
    if len(top20_rows) < 20:
        return {
            "available": False,
            "label": "待累计",
            "regime": "待累计",
            "interpretation": "缺少成交额前20明细，暂不判断Top20成交容量。",
        }

    amounts = [_turnover_rank_amount(row) for row in top20_rows]
    if any(amount <= 0 for amount in amounts):
        return {
            "available": False,
            "label": "待累计",
            "regime": "待累计",
            "interpretation": "成交额前20明细不完整，暂不判断Top20成交容量。",
        }

    near_150_count = sum(1 for amount in amounts if amount >= 150)
    rank20_amount = amounts[19]
    top20_amount = sum(amounts)
    total_turnover = _safe_float(data.get("total_turnover"))
    share_text = ""
    if total_turnover > 0:
        share_text = f"，Top20合计{top20_amount:.2f}亿，占两市{top20_amount / total_turnover * 100:.2f}%"
    return {
        "available": True,
        "label": f"{near_150_count}/20只150亿级",
        "regime": _top20_capacity_regime(near_150_count, rank20_amount),
        "rank20_amount": rank20_amount,
        "top20_amount": top20_amount,
        "near_150_count": near_150_count,
        "interpretation": (
            f"Top20第20名{rank20_amount:.2f}亿{share_text}；"
            "资金集中在大成交趋势核心，作为Top50后的补充观察，只说明资金选择方向，不单独给参与资格。"
        ),
    }


def resolve_top50_turnover_share(data):
    data = data or {}
    total_turnover = _safe_float(data.get("total_turnover"))
    if total_turnover <= 0:
        return {
            "available": False,
            "share_pct": 0.0,
            "regime": "待累计",
            "interpretation": "缺少两市成交额，暂不判断头部成交集中度。",
        }

    rank_rows = list(data.get("turnover_rank") or [])
    top50_amount = sum(_turnover_rank_amount(row) for row in rank_rows[:50])
    if top50_amount <= 0:
        return {
            "available": False,
            "share_pct": 0.0,
            "regime": "待累计",
            "interpretation": "缺少成交额前50明细，暂不判断头部成交集中度。",
        }

    share_pct = top50_amount / total_turnover * 100
    return {
        "available": True,
        "share_pct": share_pct,
        "regime": _top50_share_regime(share_pct),
        "interpretation": _top50_share_interpretation(share_pct),
    }


def _top50_series_rows(data):
    data = data or {}
    for key in ("top50_turnover_share_series", "top50_turnover_share_trend", "top50_turnover_share_trend_rows"):
        value = data.get(key)
        if isinstance(value, dict):
            rows = value.get("rows") or value.get("trend_rows") or []
            if rows:
                return list(rows)
        elif isinstance(value, (list, tuple)):
            if value:
                return list(value)
    return []


def _current_top50_series_row(data, target_date=""):
    data = data or {}
    trade_date = str(target_date or "").strip()
    total_turnover = _safe_float(data.get("total_turnover"))
    if not trade_date or total_turnover <= 0:
        return {}
    rank_rows = list(data.get("turnover_rank") or [])
    top50_amount = sum(_turnover_rank_amount(row) for row in rank_rows[:50])
    if top50_amount <= 0:
        return {}
    return {
        "trade_date": trade_date,
        "top_amount_yi": top50_amount,
        "market_amount_yi": total_turnover,
        "share_pct": top50_amount / total_turnover * 100,
    }


def resolve_top50_turnover_share_trend_rows(data, target_date=""):
    rows = []
    previous_share = None
    source_rows = _top50_series_rows(data)
    if source_rows and target_date:
        existing_dates = {
            str((item or {}).get("trade_date") or (item or {}).get("date") or "").strip()
            for item in source_rows
        }
        if str(target_date).strip() not in existing_dates:
            current_row = _current_top50_series_row(data, target_date)
            if current_row:
                source_rows = [*source_rows, current_row]
    for item in source_rows:
        row = dict(item or {})
        trade_date = row.get("trade_date") or row.get("date") or ""
        top_amount = _safe_float(row.get("top_amount_yi", row.get("top50_amount_yi")))
        market_amount = _safe_float(row.get("market_amount_yi", row.get("total_amount_yi")))
        share_pct = _safe_float(row.get("share_pct", row.get("top50_share_pct")))
        if share_pct <= 0 and top_amount > 0 and market_amount > 0:
            share_pct = top_amount / market_amount * 100
        if not trade_date or share_pct <= 0:
            continue
        change_text = "待累计" if previous_share is None else f"{share_pct - previous_share:+.2f}pct"
        rows.append(
            {
                "trade_date": trade_date,
                "share_pct": share_pct,
                "regime": _top50_share_regime(share_pct),
                "change_text": change_text,
                "top_amount_yi": top_amount,
                "market_amount_yi": market_amount,
            }
        )
        previous_share = share_pct
    if rows:
        return rows[-25:]
    return []


def _top50_turnover_share_trend_summary(rows):
    rows = [row for row in rows or [] if _safe_float((row or {}).get("share_pct")) > 0]
    if not rows:
        return ""
    shares = [_safe_float(row.get("share_pct")) for row in rows]
    current_share = shares[-1]
    low_share = min(shares)
    high_share = max(shares)
    recent_change_text = ""
    if len(shares) >= 5:
        recent_change_text = f"近5日{current_share - shares[-5]:+.2f}pct，"
    elif len(shares) >= 2:
        recent_change_text = f"区间首尾{current_share - shares[0]:+.2f}pct，"
    total_change = current_share - shares[0]
    if total_change >= 0.5:
        direction = "头部成交集中度抬升。"
    elif total_change <= -0.5:
        direction = "头部成交集中度回落。"
    else:
        direction = "头部成交集中度横向震荡。"
    return (
        f"近{len(rows)}个交易日Top50成交额占比趋势："
        f"当前{current_share:.2f}%，"
        f"{recent_change_text}"
        f"区间{low_share:.2f}%-{high_share:.2f}%，"
        f"{direction}"
    )


def _format_pct(value):
    return f"{_safe_float(value):.2f}%"


def _format_top50_share_pct(top50_share):
    if not (top50_share or {}).get("available"):
        return "待累计"
    return _format_pct((top50_share or {}).get("share_pct"))


def _format_signed_pct(value):
    return f"{_safe_float(value):+.2f}%"


def _format_amount_yi(value):
    return f"{_safe_float(value):.2f}亿"


def _etf_turnover_rows(data):
    snapshot = (data or {}).get("etf_turnover_series") or {}
    if isinstance(snapshot, dict):
        source_rows = snapshot.get("rows") or snapshot.get("trend_rows") or []
    else:
        source_rows = snapshot

    rows = []
    previous_amount = None
    for item in source_rows or []:
        row = dict(item or {})
        trade_date = str(row.get("trade_date") or row.get("date") or "").strip()
        amount = _safe_float(
            row.get(
                "etf_turnover_yi",
                row.get("amount_yi", row.get("turnover_yi", row.get("amount"))),
            )
        )
        if not trade_date or amount <= 0:
            continue
        change_pct = row.get("change_pct", row.get("pct_change"))
        if change_pct in (None, "") and previous_amount:
            change_pct = _pct_change_between(amount, previous_amount)
        rows.append(
            {
                **row,
                "trade_date": trade_date,
                "etf_turnover_yi": amount,
                "change_pct": "待累计" if change_pct in (None, "") else change_pct,
                "covered_etf_count": row.get("covered_etf_count", row.get("etf_count", row.get("count", ""))),
            }
        )
        previous_amount = amount
    return rows[-25:]


def _etf_turnover_coverage_anomaly(data, rows):
    snapshot = (data or {}).get("etf_turnover_series") or {}
    if isinstance(snapshot, dict) and (
        snapshot.get("coverage_anomaly") is True or str(snapshot.get("coverage_status") or "") == "partial"
    ):
        return True, str(snapshot.get("coverage_anomaly_reason") or "").strip()
    for row in rows or []:
        if isinstance(row, dict) and row.get("coverage_anomaly") is True:
            return True, str(row.get("coverage_anomaly_reason") or "").strip()
    return False, ""


def _etf_capacity_signal(data):
    rows = _etf_turnover_rows(data)
    if not rows:
        return {
            "available": False,
            "usable_for_capacity_judgment": False,
            "current_amount_yi": 0.0,
            "label": "待累计",
            "basis": "ETF两市成交额待累计。",
            "rows": [],
        }

    current = rows[-1]
    current_amount = _safe_float(current.get("etf_turnover_yi"))
    coverage_anomaly, coverage_reason = _etf_turnover_coverage_anomaly(data, rows)
    if coverage_anomaly:
        basis = coverage_reason or "ETF两市成交额样本覆盖不足，停止用于机构容量判断。"
        if not basis.endswith("。"):
            basis = f"{basis}。"
        basis = _append_sentence(basis, "停止用于机构容量判断")
        return {
            "available": True,
            "usable_for_capacity_judgment": False,
            "current_amount_yi": current_amount,
            "label": "样本覆盖不足",
            "basis": basis,
            "rows": rows,
        }
    recent_rows = rows[-5:] if len(rows) >= 5 else rows
    recent_amounts = [_safe_float(row.get("etf_turnover_yi")) for row in recent_rows]
    recent_change = _pct_change_between(current_amount, recent_amounts[0]) if recent_amounts else None
    recent_avg = sum(recent_amounts) / len(recent_amounts) if recent_amounts else 0.0
    all_amounts = [_safe_float(row.get("etf_turnover_yi")) for row in rows]
    all_avg = sum(all_amounts) / len(all_amounts) if all_amounts else 0.0

    if recent_change is not None and recent_change >= 5 and current_amount >= recent_avg:
        label = "机构容量放大"
        direction = "机构容量流量明显放大。"
    elif recent_change is not None and (recent_change <= -3 or current_amount < recent_avg or current_amount < all_avg):
        label = "机构容量中性偏收缩"
        direction = "机构容量流量未明显放大。"
    else:
        label = "机构容量中性"
        direction = "机构容量流量变化不大。"

    if len(recent_amounts) >= 2:
        basis = (
            f"近{len(recent_amounts)}日{_format_change_pct(recent_change)}，"
            f"区间{min(recent_amounts):.2f}亿-{max(recent_amounts):.2f}亿，"
            f"{direction}"
        )
    else:
        basis = f"当前{_format_amount_yi(current_amount)}，{direction}"

    return {
        "available": True,
        "usable_for_capacity_judgment": True,
        "current_amount_yi": current_amount,
        "label": label,
        "basis": basis,
        "rows": rows,
    }


def _etf_capacity_combo_judgment(etf_capacity, top50_share, new_high_regime, margin_pressure):
    if not (etf_capacity or {}).get("available"):
        return {
            "state": "待累计",
            "basis": "ETF容量数据待累计，暂不判断与其他市场指标的配合。",
        }
    if (etf_capacity or {}).get("usable_for_capacity_judgment") is False:
        return {
            "state": "待复核",
            "basis": "ETF容量数据样本不足，暂不判断与其他市场指标的配合。",
        }

    etf_label = str((etf_capacity or {}).get("label") or "")
    etf_hot = etf_label == "机构容量放大"
    top50_hot = (top50_share or {}).get("regime") == "资金活跃期"
    new_high_hot = new_high_regime == "高潮"
    margin_label = str((margin_pressure or {}).get("latest_pressure_label") or "").strip()
    margin_ok = margin_label in ("舒缓", "中性")

    if etf_hot and top50_hot and new_high_hot and margin_ok:
        return {
            "state": "同向强化",
            "basis": "ETF容量、Top50集中度、创新高扩散、融资承接四项同向走强，市场热度需要按偏热处理。",
        }

    state = "中性偏收缩" if "收缩" in etf_label else "中性"
    return {
        "state": state,
        "basis": "ETF容量、Top50集中度、创新高扩散、融资承接四项未形成同向强化，市场仍按震荡处理。",
    }


def _append_sentence(text, addition):
    text = str(text or "").strip()
    addition = str(addition or "").strip()
    if not addition or addition in text:
        return text
    if text and not text.endswith("。"):
        text = f"{text}。"
    if addition and not addition.endswith("。"):
        addition = f"{addition}。"
    return f"{text}{addition}" if text else addition


def _display_latest_first(rows):
    return list(reversed(list(rows or [])))


def _format_change_pct(value):
    if value is None:
        return "样本不足"
    return f"{_safe_float(value):+.2f}%"


def _format_change_pct_point(value):
    if value is None:
        return "样本不足"
    return f"{_safe_float(value):+.2f}pct"


def _format_turnover_change_pct(value):
    if value is None:
        return "-"
    return _format_signed_pct(value)


def _pct_change_between(current, previous):
    current = _safe_float(current)
    previous = _safe_float(previous)
    if current <= 0 or previous <= 0:
        return None
    return (current / previous - 1) * 100


def _lookback_row(rows, lookback):
    rows = list(rows or [])
    lookback = int(lookback or 0)
    if lookback <= 0 or len(rows) < lookback:
        return None
    return rows[-lookback]


def _margin_pressure_amount_change_text(rows, key, lookback):
    current = (rows or [])[-1] if rows else {}
    previous = _lookback_row(rows, lookback)
    if not current or not previous:
        return "样本不足"
    return _format_change_pct(_pct_change_between(current.get(key), previous.get(key)))


def _margin_pressure_ratio_change_text(rows, lookback):
    current = (rows or [])[-1] if rows else {}
    previous = _lookback_row(rows, lookback)
    if not current or not previous:
        return "样本不足"
    return _format_change_pct_point(
        _safe_float(current.get("margin_turnover_ratio_pct")) - _safe_float(previous.get("margin_turnover_ratio_pct"))
    )


def _margin_pressure_balance_interpretation(rows):
    previous = _lookback_row(rows, 5)
    current = (rows or [])[-1] if rows else {}
    if not previous or not current:
        return "看杠杆存量变化"
    balance_change = _pct_change_between(current.get("margin_balance_yi"), previous.get("margin_balance_yi"))
    turnover_change = _pct_change_between(current.get("market_turnover_yi"), previous.get("market_turnover_yi"))
    if balance_change is not None and balance_change > 0 and turnover_change is not None and turnover_change < 0:
        return "融资余额上升、成交额下降，承接压力加重"
    if balance_change is not None and balance_change < 0:
        return "融资余额回落，杠杆存量降温"
    return "融资余额平稳，重点看成交额能否承接"


def _margin_pressure_turnover_interpretation(rows):
    previous = _lookback_row(rows, 5)
    current = (rows or [])[-1] if rows else {}
    if not previous or not current:
        return "看承接流量变化"
    turnover_change = _pct_change_between(current.get("market_turnover_yi"), previous.get("market_turnover_yi"))
    if turnover_change is not None and turnover_change > 0:
        return "成交额放大，承接条件改善"
    if turnover_change is not None and turnover_change < 0:
        return "成交额回落，承接条件转弱"
    return "成交额变化不大，继续观察"


def _margin_pressure_ratio_interpretation(label):
    label = str(label or "").strip()
    if label == "高压":
        return "承接偏紧，控制追高和加仓冲动"
    if label == "舒缓":
        return "承接相对舒缓，但仍要看主线和个股节奏"
    if label == "中性":
        return "承接中性，不能单独给方向"
    return "只作市场热度背景"


def _margin_pressure_relation_text(snapshot):
    relation = (snapshot or {}).get("index_relation") or (snapshot or {}).get("relation") or {}
    if relation.get("relationship_label"):
        return str(relation.get("relationship_label"))
    return "弱相关"


def _load_margin_pressure_snapshot_from_fact_db(target_date="", *, db_path=None):
    target_date = str(target_date or "").strip()
    if not target_date:
        return {}
    try:
        service = DatabaseService.fact_store_from_environment(db_path)
        payload = service.query_margin_pressure_series(target_date, window_days=250)
        rows = list((payload or {}).get("rows") or [])
        if not rows:
            return {}
        return build_margin_pressure_snapshot(
            rows,
            window_days=25,
            calibration_days=250,
            target_date=target_date,
        )
    except Exception:
        return {}


def _margin_pressure_snapshot(data, target_date="", *, db_path=None):
    if not isinstance(data, dict):
        return {}
    existing = data.get("margin_pressure") or {}
    if (existing or {}).get("available") or (existing or {}).get("rows"):
        return existing
    snapshot = _load_margin_pressure_snapshot_from_fact_db(target_date, db_path=db_path)
    if (snapshot or {}).get("available") or (snapshot or {}).get("rows"):
        data["margin_pressure"] = snapshot
        return snapshot
    return existing


def _margin_pressure_summary(snapshot):
    if not (snapshot or {}).get("available"):
        return "待累计"
    ratio = _safe_float(snapshot.get("latest_margin_turnover_ratio_pct"))
    if ratio <= 0:
        rows = (snapshot.get("rows") or [])
        ratio = _safe_float((rows[-1] if rows else {}).get("margin_turnover_ratio_pct"))
    label = snapshot.get("latest_pressure_label") or "待累计"
    return f"{_format_pct(ratio)} / {label}" if ratio > 0 else label


def _margin_pressure_label(snapshot):
    if not (snapshot or {}).get("available"):
        return "待累计"
    return str(snapshot.get("latest_pressure_label") or "").strip() or "待累计"


def _margin_pressure_latest_date(snapshot):
    if not (snapshot or {}).get("available"):
        return ""
    return str(
        (snapshot or {}).get("latest_data_date")
        or (((snapshot or {}).get("rows") or [{}])[-1] or {}).get("trade_date")
        or ""
    ).strip()


def _margin_pressure_date_note(snapshot, target_date=""):
    latest_date = _margin_pressure_latest_date(snapshot)
    target_date = str(target_date or (snapshot or {}).get("target_date") or "").strip()
    if not latest_date:
        return ""
    if target_date and latest_date < target_date:
        return f"截至{latest_date}，较报告日{target_date}滞后一交易日"
    return f"截至{latest_date}"


def _margin_pressure_basis(snapshot, target_date=""):
    if not (snapshot or {}).get("available"):
        return "融资余额相对两市成交额的承接压力待累计。"
    rows = list((snapshot or {}).get("rows") or [])
    current = rows[-1] if rows else {}
    ratio = _safe_float(
        current.get("margin_turnover_ratio_pct", (snapshot or {}).get("latest_margin_turnover_ratio_pct"))
    )
    latest_date = _margin_pressure_latest_date(snapshot)
    target_date = str(target_date or (snapshot or {}).get("target_date") or "").strip()
    if latest_date and ratio > 0:
        text = f"截至{latest_date}，融资承接比 {_format_pct(ratio)}"
        if target_date and latest_date < target_date:
            text = f"{text}；较报告日{target_date}滞后一交易日"
    elif latest_date:
        text = f"截至{latest_date}"
    elif ratio > 0:
        text = f"融资承接比 {_format_pct(ratio)}"
    else:
        text = "融资承接压力已生成"
    if text and not text.endswith("。"):
        text = f"{text}。"
    return text


def _margin_pressure_usage_note(snapshot, target_date=""):
    if not (snapshot or {}).get("available"):
        return "融资余额相对两市成交额的承接压力待累计。"
    note = str((snapshot or {}).get("usage_note") or "").strip()
    if not note:
        note = "融资余额是杠杆存量，两市成交额是承接流量。"
    note = note.replace("目标日", "报告日")
    if "滞后一交易日" in note and "滞后一交易日" in _margin_pressure_basis(snapshot, target_date):
        parts = [part for part in note.split("。") if "滞后一交易日" not in part]
        note = "。".join(part.strip() for part in parts if part.strip())
        if note:
            note = f"{note}。"
    return note


def _new_high_regime(all_a_share_pct):
    all_a_share_pct = _safe_float(all_a_share_pct)
    if all_a_share_pct < 2:
        return "冰点"
    if all_a_share_pct > 5:
        return "高潮"
    return "震荡"


def _new_high_regime_signal(all_a_share_pct):
    regime = _new_high_regime(all_a_share_pct)
    if regime == "冰点":
        return "趋势扩散偏冷"
    if regime == "高潮":
        return "趋势扩散偏热"
    return "趋势扩散震荡"


def _new_high_interpretation(all_a_share_pct):
    signal = _new_high_regime_signal(all_a_share_pct)
    pct_text = _format_pct(all_a_share_pct)
    if signal == "趋势扩散偏冷":
        return f"全A占比{pct_text}，趋势扩散偏冷，说明趋势赚钱效应扩散不足；这不是整体市场冰点。"
    if signal == "趋势扩散偏热":
        return f"全A占比{pct_text}，趋势扩散偏热；只有成交额、指数位置和涨跌家数同步支持时，整体才按高潮看待。"
    return f"全A占比{pct_text}，趋势扩散震荡，说明趋势扩散存在但还不是极端热度。"


def _price_band_style_signal(label):
    text = str(label or "").strip()
    if text == "高潮":
        return "高价相对占优"
    if text == "冰点":
        return "低价相对抗跌"
    if text == "震荡":
        return "价格带均衡"
    return text or "价格带待判断"


def _price_band_style_summary(snapshot, rows):
    rows = list(rows or [])
    if not rows:
        return snapshot.get("summary") or "价格带风格趋势已生成。"
    latest_row = rows[-1]
    latest_spread = _safe_float(latest_row.get("spread_pct"))
    latest_signal = _price_band_style_signal(latest_row.get("style_label"))
    latest_absolute_label = latest_row.get("absolute_label") or _price_band_absolute_label(
        latest_row.get("high_price_pct"),
        latest_row.get("low_price_pct"),
    )
    high_total = sum(_safe_float((row or {}).get("high_price_pct")) for row in rows)
    low_total = sum(_safe_float((row or {}).get("low_price_pct")) for row in rows)
    return (
        f"近{len(rows)}个交易日价格带风格："
        f"最新差值 {latest_spread:+.2f}pct，相对风格{latest_signal}；"
        f"绝对状态{latest_absolute_label}；"
        f"百元股累计 {high_total:+.2f}%，低价股累计 {low_total:+.2f}%。"
        f"价格带只作局部风格背景，不单独说明整体市场温度，明日仍看成交额与核心承接。"
    )


def _index_risk_is_weak(data):
    data = data or {}
    values = []

    def append_change_if_valid(item):
        if not isinstance(item, dict):
            return
        price = _safe_float(
            item.get("price")
            or item.get("点位")
            or item.get("close")
            or item.get("收盘")
            or item.get("最新价"),
            None,
        )
        has_price_key = any(key in item for key in ("price", "点位", "close", "收盘", "最新价"))
        if has_price_key and (price is None or price <= 0):
            return
        change = _safe_float(item.get("涨跌幅", item.get("change_pct")), None)
        if change is None:
            return
        values.append(change)

    for item in (data.get("indices") or {}).values():
        append_change_if_valid(item)
    wind_a = data.get("wind_a_alternative") or {}
    if wind_a:
        append_change_if_valid(wind_a)
    csi500 = data.get("csi500_index") or {}
    if csi500:
        append_change_if_valid(csi500)
    csi1000 = data.get("csi1000_index") or {}
    if csi1000:
        append_change_if_valid(csi1000)
    return any(value <= -1.5 for value in values)


def _breadth_risk_is_weak(data):
    stats = (data or {}).get("market_stats") or {}
    up_count = _safe_float(stats.get("up_count"))
    down_count = _safe_float(stats.get("down_count"))
    if down_count >= max(3000, up_count * 1.8):
        return True
    return len((data or {}).get("dt_pool") or []) >= 50


def resolve_unified_market_sentiment(data, target_date="", *, db_path=None):
    data = data or {}
    top50_share = resolve_top50_turnover_share(data)
    new_high = data.get("new_high_feedback") or {}
    new_high_regime = _new_high_regime(new_high.get("all_a_share_pct")) if new_high.get("available") else "待累计"
    margin_pressure = _margin_pressure_snapshot(data, target_date, db_path=db_path)
    margin_pressure_hot = (
        bool(margin_pressure.get("available"))
        and str(margin_pressure.get("latest_pressure_label") or "").strip() == "高压"
    )
    risk_weak = _index_risk_is_weak(data) or _breadth_risk_is_weak(data)
    local_hot = top50_share.get("regime") == "资金活跃期" or new_high_regime == "高潮" or margin_pressure_hot

    if risk_weak and local_hot:
        return {
            "state": "震荡偏风险",
            "local_heat": (
                "融资承接压力高，同时指数大跌、跌多涨少、跌停扩散，只写承接风险，不把整体市场升级为高潮。"
                if margin_pressure_hot
                else (
                "创新高高潮，但指数大跌、跌多涨少、跌停扩散，只写局部过热，不把整体市场升级为高潮。"
                if new_high_regime == "高潮"
                else "局部资金活跃，但指数大跌、跌多涨少、跌停扩散，只写局部过热，不把整体市场升级为高潮。"
                )
            ),
            "rr_text": "不值得主动参与",
            "meaning": "趋势扩散偏热，但指数和涨跌家数破坏，先防降温，等待止跌和核心承接。",
        }
    if risk_weak:
        return {
            "state": "冰点",
            "local_heat": "盘面亏钱效应重，指数弱、跌多涨少或跌停扩散，按冰点或收缩环境处理。",
            "rr_text": "不值得主动参与",
            "meaning": "默认先防守，等待下一次更清晰的强化。",
        }
    if local_hot and top50_share.get("regime") == "资金活跃期" and new_high_regime == "高潮":
        return {
            "state": "高潮",
            "local_heat": "盘面亏钱效应不重，资金聚焦和趋势扩散同步走热，整体可按高潮看待。",
            "rr_text": "谨慎参与",
            "meaning": "市场热度较高，参与只看核心承接，避免追一致性加速。",
        }
    return {
        "state": "震荡",
        "local_heat": "局部指标只作证据，整体仍按震荡处理，等待亏钱效应收敛、热度扩散和方向确认。",
        "rr_text": "等待确认",
        "meaning": "量能尚可，但要等更清晰主线信号。",
    }


def _join_names(values, fallback="待补充"):
    items = [str(value or "").strip() for value in values or [] if str(value or "").strip()]
    return "、".join(items) if items else fallback


def build_market_overview_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 二、市场基底"], "exports": {}, "module_logs": []}


def build_market_overview_indices_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    target_date = _target_date(context)
    margin_pressure = _margin_pressure_snapshot(data, target_date, db_path=_daily_fact_db_path(context))
    turnover_result = run_two_market_turnover_nodes(
        build_two_market_turnover_node_specs(enabled_node_keys=["compare"]),
        {"data": data, "target_date": target_date},
    )
    turnover_comparison = turnover_result["context"].get("two_market_turnover_comparison", {})
    lines = [
        "### 1. 指数与市场底色",
        "| 指标 | 数值 | 涨跌幅 | 解读 |",
        "|------|------|--------|------|",
    ]

    def _index_trend_label(index_data, change):
        try:
            change = float(change or 0)
        except (TypeError, ValueError):
            change = 0.0
        close = _safe_float(
            (index_data or {}).get("close")
            or (index_data or {}).get("收盘")
            or (index_data or {}).get("price")
            or (index_data or {}).get("最新价"),
            None,
        )
        low = _safe_float((index_data or {}).get("low") or (index_data or {}).get("最低"), None)
        open_price = _safe_float((index_data or {}).get("open") or (index_data or {}).get("开盘"), None)
        high = _safe_float((index_data or {}).get("high") or (index_data or {}).get("最高"), None)
        intraday_range_pct = None
        low_repair_pct = None
        close_position = None
        if close and low and low > 0:
            low_repair_pct = (close - low) / low * 100
        if high and low and high > low:
            intraday_range_pct = (high - low) / low * 100
            close_position = (close - low) / (high - low) if close is not None else None
        opened_weak = bool(open_price and close and open_price < close)
        has_deep_repair = (
            change > -0.3
            and low_repair_pct is not None
            and low_repair_pct >= 0.8
            and (intraday_range_pct is None or intraday_range_pct >= 1.0)
            and (close_position is None or close_position >= 0.55)
            and opened_weak
        )
        if has_deep_repair:
            return "探底回升"
        if change <= -1.5:
            return "明显走弱"
        if change <= -0.3:
            return "震荡调整"
        if change < 0:
            return "弱震荡"
        if change < 0.3:
            return "小幅修复"
        if change < 0.8:
            return "温和修复"
        if change < 1.5:
            return "偏强修复"
        return "强势上涨"

    if data.get("indices"):
        for name, index_data in data["indices"].items():
            point = _safe_float(
                (index_data or {}).get("点位")
                or (index_data or {}).get("close")
                or (index_data or {}).get("price")
                or (index_data or {}).get("收盘")
                or (index_data or {}).get("最新价"),
                None,
            )
            change = _safe_float((index_data or {}).get("涨跌幅", (index_data or {}).get("change_pct")), None)
            if point is None or point <= 0 or change is None:
                lines.append(f"| {name} | 待补 | 待补 | 待补 |")
                continue
            trend = _index_trend_label(index_data, change)
            lines.append(f"| {name} | {point:.2f} | {change:+.2f}% | {trend} |")

    if data.get("wind_a_alternative"):
        wa = data["wind_a_alternative"]
        point = _safe_float(wa.get("点位", wa.get("price")), None)
        change = _safe_float(wa.get("涨跌幅", wa.get("change_pct")), None)
        if point is None or point <= 0 or change is None:
            lines.append("| 中证全指 | 待补 | 待补 | 待补 |")
        else:
            trend = _index_trend_label(wa, change)
            lines.append(f"| 中证全指 | {point:.2f} | {change:+.2f}% | {trend} |")
    csi500 = data.get("csi500_index")
    if isinstance(csi500, dict):
        point = _safe_float(csi500.get("点位", csi500.get("price")), None)
        change = _safe_float(csi500.get("涨跌幅", csi500.get("change_pct")), None)
        if point is None or point <= 0 or change is None:
            lines.append("| 中证500 | 待补 | 待补 | 待补 |")
        else:
            trend = _index_trend_label(csi500, change)
            lines.append(f"| 中证500 | {point:.2f} | {change:+.2f}% | {trend} |")
    elif "csi500_index" in data:
        lines.append("| 中证500 | 待补 | 待补 | 待补 |")
    if data.get("csi1000_index"):
        csi1000 = data["csi1000_index"]
        point = _safe_float(csi1000.get("点位", csi1000.get("price")), None)
        change = _safe_float(csi1000.get("涨跌幅", csi1000.get("change_pct")), None)
        if point is None or point <= 0 or change is None:
            lines.append("| 中证1000 | 待补 | 待补 | 待补 |")
        else:
            trend = _index_trend_label(csi1000, change)
            lines.append(f"| 中证1000 | {point:.2f} | {change:+.2f}% | {trend} |")
    turnover = float(data.get("total_turnover", 0) or 0)
    zt_count = len(data.get("zt_pool", []))
    dt_count = len(data.get("dt_pool", []))
    up_count = data.get("market_stats", {}).get("up_count", 0)
    down_count = data.get("market_stats", {}).get("down_count", 0)
    top50_share = resolve_top50_turnover_share(data)
    top20_capacity = resolve_top20_turnover_capacity(data)
    etf_capacity = _etf_capacity_signal(data)
    turnover_basis = str(turnover_comparison.get("condition_text") or "").strip()
    turnover_label = str(turnover_comparison.get("label") or "").strip()
    if turnover_label and turnover_label != "量能历史不足":
        turnover_basis = f"{turnover_label}；{turnover_basis}" if turnover_basis else turnover_label
    if not turnover_basis:
        turnover_basis = describe_market_turnover_condition(data)
    lines.append(
        f"| 两市成交额 | {turnover:.2f}亿 | "
        f"{_format_turnover_change_pct(turnover_comparison.get('previous_change_pct'))} | {turnover_basis} |"
    )

    # 追加成交量质量判断，避免只看绝对成交额。
    turnover_quality = evaluate_turnover_quality(data)
    lines.append(
        f"| 成交量质量 | {turnover_quality['turnover_quality']} | - | {turnover_quality['turnover_quality_desc']} |"
    )

    lines.append(
        f"| Top50成交额占比 | {_format_top50_share_pct(top50_share)} | {top50_share['regime']} | {top50_share['interpretation']} |"
    )
    lines.append(
        f"| Top20成交容量 | {top20_capacity['label']} | {top20_capacity['regime']} | {top20_capacity['interpretation']} |"
    )
    if etf_capacity.get("available"):
        lines.append(
            f"| ETF两市成交额 | {_format_amount_yi(etf_capacity.get('current_amount_yi'))} | "
            f"{etf_capacity['label']} | {etf_capacity['basis']} |"
        )
    lines.append(
        f"| 融资承接压力 | {_margin_pressure_summary(margin_pressure)} | - | "
        f"{_append_sentence(_margin_pressure_basis(margin_pressure, target_date), _margin_pressure_usage_note(margin_pressure, target_date))} |"
    )
    lines.append(f"| 涨停 / 跌停 | {zt_count} / {dt_count} | - | {'活跃度还在，但亏钱端不轻' if dt_count >= 3 else '情绪尚可'} |")
    lines.append(f"| 涨跌比 | {up_count} / {down_count} | - | {'下跌家数偏多，底色偏防守' if down_count > up_count else '多头仍占优'} |")
    lines.append("")
    top50_trend_rows = resolve_top50_turnover_share_trend_rows(data, _target_date(context))
    if top50_trend_rows:
        trend_summary = _top50_turnover_share_trend_summary(top50_trend_rows)
        if trend_summary:
            lines.append(f"> {trend_summary}")
            lines.append("")
        lines.extend(
            [
                "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |",
                "|------|-----------|------|--------|-------------|------------|",
            ]
        )
        for row in _display_latest_first(top50_trend_rows):
            lines.append(
                f"| {row.get('trade_date', '')} | {_format_pct(row.get('share_pct'))} | {row.get('regime', '待累计')} | "
                f"{row.get('change_text', '待累计')} | {_format_amount_yi(row.get('top_amount_yi'))} | "
                f"{_format_amount_yi(row.get('market_amount_yi'))} |"
            )
        lines.append("")
    return {
        "lines": lines,
        "exports": {"two_market_turnover_comparison": turnover_comparison},
        "module_logs": list(turnover_result.get("module_logs") or []),
    }


def build_market_overview_volume_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    target_date = _target_date(context)
    daily_fact_db_path = _daily_fact_db_path(context)
    top50_share = resolve_top50_turnover_share(data)
    top20_capacity = resolve_top20_turnover_capacity(data)
    etf_capacity = _etf_capacity_signal(data)
    new_high = data.get("new_high_feedback") or {}
    new_high_regime = _new_high_regime(new_high.get("all_a_share_pct")) if new_high.get("available") else "待累计"
    margin_pressure = _margin_pressure_snapshot(data, target_date, db_path=daily_fact_db_path)
    unified = resolve_unified_market_sentiment(data, target_date, db_path=daily_fact_db_path)
    etf_combo = _etf_capacity_combo_judgment(etf_capacity, top50_share, new_high_regime, margin_pressure)

    return {
        "lines": [
            "### 2. 市场状态结论",
            "> 读法：市场情绪总状态先看盘面亏钱效应，再看局部热度；指数大跌、跌多涨少、跌停扩散时，单个指标高潮只写局部过热，不能单独把整体市场升级为高潮。",
            "",
            "| 项目 | 结论 | 依据 |",
            "|------|------|------|",
            f"| 市场情绪总状态 | {unified['state']} | 先看指数、涨跌家数、跌停扩散，再看局部热度。 |",
            f"| 头部成交状态 | {top50_share['regime']} | {top50_share['interpretation']} |",
            f"| Top20成交容量 | {top20_capacity['regime']} | 详见指数与市场底色表，只作成交容量背景。 |",
            f"| ETF容量协同 | {etf_combo['state']} | {etf_combo['basis']} |",
            f"| 融资承接压力 | {_margin_pressure_label(margin_pressure)} | {_margin_pressure_basis(margin_pressure, target_date)} |",
            f"| 局部热度处理 | {unified['local_heat']} | 单项热度不能替代整体盘面。 |",
            f"| 当前盈亏比 | {unified['rr_text']} | 参与只看主线、承接和个股结构同时成立。 |",
            "| 当前结构位置 | 日线中枢内震荡 | 结构未走出清晰单边，仍按震荡处理。 |",
            f"| 明日总体含义 | {unified['meaning']} | 先等方向确认，再决定是否参与。 |",
            "",
        ],
        "exports": {
            "market_overview_turnover": data.get("total_turnover", 0),
            "top50_turnover_share": top50_share,
            "top20_turnover_capacity": top20_capacity,
            "etf_capacity": etf_capacity,
            "market_sentiment": unified,
        },
        "module_logs": [],
    }


def build_market_overview_sentiment_node(context, node_meta=None, node_lookup=None):
    return {"lines": [], "exports": {}, "module_logs": []}


def build_market_overview_price_band_style_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    snapshot = data.get("price_band_style_series") or {}
    rows = list(snapshot.get("rows") or [])[-25:]
    if not rows:
        return {"lines": [], "exports": {"price_band_style_series": snapshot}, "module_logs": []}
    lines = [
        "### 3. 价格带风格",
        f"> {_price_band_style_summary(snapshot, rows)}",
        "> 读法：这里先看 `百元股涨跌幅 - 低价股涨跌幅` 的相对风格，再看两组自身涨跌的绝对状态。差值越高，说明资金越偏高价核心；差值越低，说明高价核心降温、低价股相对抗跌。价格带只说明高价与低价的相对偏好，不单独代表整体市场冰点或高潮。",
        "",
        "| 日期 | 百元股涨跌幅 | 低价股涨跌幅 | 当日差值 | 相对风格 | 绝对状态 |",
        "|------|--------------|--------------|--------------|----------|----------|",
    ]
    for row in _display_latest_first(rows):
        lines.append(
            f"| {row.get('trade_date', '')} | {_format_signed_pct(row.get('high_price_pct'))} | "
            f"{_format_signed_pct(row.get('low_price_pct'))} | {_safe_float(row.get('spread_pct')):+.2f}pct | "
            f"{_price_band_style_signal(row.get('style_label'))} | "
            f"{row.get('absolute_label') or _price_band_absolute_label(row.get('high_price_pct'), row.get('low_price_pct'))} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {"price_band_style_series": snapshot}, "module_logs": []}


def build_market_overview_new_high_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    snapshot = data.get("new_high_feedback") or {}
    lines = ["### 4. 创新高趋势反馈"]
    if not snapshot.get("available"):
        message = snapshot.get("message") or "创新高趋势反馈待累计。"
        lines.extend([f"> {message}", ""])
        return {"lines": lines, "exports": {"new_high_feedback": snapshot}, "module_logs": []}

    lines.extend(
        [
            f"> {snapshot.get('summary') or '创新高趋势反馈已生成。'}",
            "> 用途：创新高看的是趋势赚钱效应有没有扩散。全A占比越高，说明越多股票突破过去约250个交易日高点；但超过5%后若同时放量，往往偏热，次日更容易降温。",
            "> 读法：全A占比低于2%看趋势扩散偏冷，2%到5%看趋势扩散震荡，5%以上看趋势扩散偏热。这个指标只作趋势扩散背景，整体市场温度仍要结合成交额、指数位置、涨跌家数和核心承接。",
            f"> 当前解读：{_new_high_interpretation(snapshot.get('all_a_share_pct'))}",
            "",
            "| 日期 | 新高数 | 全A占比 | 趋势信号 | 较前日 | 主导板块 |",
            "|------|--------|---------|------|--------|----------|",
        ]
    )
    for row in _display_latest_first(snapshot.get("trend_rows", []) or []):
        lines.append(
            f"| {row.get('trade_date', '')} | {int(_safe_float(row.get('new_high_count')))} | "
            f"{_format_pct(row.get('all_a_share_pct'))} | {_new_high_regime_signal(row.get('all_a_share_pct'))} | "
            f"{row.get('change_text', '待累计')} | "
            f"{row.get('leading_sectors', '待补充板块')} |"
        )

    lines.extend(
        [
            "",
            "| 板块 | 新高数 | 占新高池 | 代表个股 |",
            "|------|--------|----------|----------|",
        ]
    )
    for row in (snapshot.get("sector_distribution") or [])[:10]:
        lines.append(
            f"| {row.get('sector', '待补充板块')} | {int(_safe_float(row.get('new_high_count')))} | "
            f"{_format_pct(row.get('share_pct'))} | {_join_names(row.get('representative_stocks'))} |"
        )

    lines.extend(
        [
            "",
            "| 排名 | 股票 | 代码 | 所属板块 | 涨跌幅 | 成交额 | 新高跨度 |",
            "|------|------|------|----------|--------|--------|----------|",
        ]
    )
    for index, stock in enumerate((snapshot.get("top_stocks") or [])[:30], start=1):
        topdays = int(_safe_float(stock.get("topdays")))
        lines.append(
            f"| {index} | {stock.get('name', '?')} | {stock.get('code', '?')} | "
            f"{stock.get('sector', '待补充板块')} | {_format_signed_pct(stock.get('pct_chg'))} | "
            f"{_format_amount_yi(stock.get('amount_yi'))} | {topdays}日新高 |"
        )
    lines.append("")
    return {"lines": lines, "exports": {"new_high_feedback": snapshot}, "module_logs": []}


def build_market_overview_margin_pressure_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    target_date = _target_date(context)
    snapshot = _margin_pressure_snapshot(data, target_date, db_path=_daily_fact_db_path(context))
    lines = ["### 5. 融资承接与成交量"]
    if not snapshot.get("available"):
        message = snapshot.get("message") or "融资承接压力待累计。"
        lines.extend([f"> {message}", ""])
        return {"lines": lines, "exports": {"margin_pressure": snapshot}, "module_logs": []}
    rows = list(snapshot.get("rows", []) or [])
    current = rows[-1] if rows else {}
    current_label = current.get("pressure_label") or snapshot.get("latest_pressure_label") or "待累计"
    current_ratio = _safe_float(
        current.get("margin_turnover_ratio_pct", snapshot.get("latest_margin_turnover_ratio_pct"))
    )
    lines.extend(
        [
            f"> {snapshot.get('summary') or '融资承接压力已生成。'}",
            f"> {snapshot.get('usage_note') or '融资余额是杠杆存量，两市成交额是承接流量。'}",
            "> 近250日关系校验：融资承接比和上证指数、中证全指后续1/3/5日表现只按弱相关处理，本项不单独预测明日涨跌；只判断两市成交额能否承接融资存量。",
            "> 读法：低于85%看舒缓，85%到100%看中性，超过100%看高压；真正需要警惕的是融资余额上升、成交额下降的组合。",
            "",
            "| 观察项 | 当前 | 近5日变化 | 近20日变化 | 解读 |",
            "|------|------|-----------|------------|------|",
            (
                f"| 融资余额 | {_format_amount_yi(current.get('margin_balance_yi'))} | "
                f"{_margin_pressure_amount_change_text(rows, 'margin_balance_yi', 5)} | "
                f"{_margin_pressure_amount_change_text(rows, 'margin_balance_yi', 20)} | "
                f"{_margin_pressure_balance_interpretation(rows)} |"
            ),
            (
                f"| 两市成交额 | {_format_amount_yi(current.get('market_turnover_yi'))} | "
                f"{_margin_pressure_amount_change_text(rows, 'market_turnover_yi', 5)} | "
                f"{_margin_pressure_amount_change_text(rows, 'market_turnover_yi', 20)} | "
                f"{_margin_pressure_turnover_interpretation(rows)} |"
            ),
            (
                f"| 融资承接比 | {_format_pct(current_ratio)} | "
                f"{_margin_pressure_ratio_change_text(rows, 5)} | "
                f"{_margin_pressure_ratio_change_text(rows, 20)} | "
                f"{_margin_pressure_ratio_interpretation(current_label)} |"
            ),
            f"| 250日关系校验 | {_margin_pressure_relation_text(snapshot)} | - | - | 不单独给方向，只作承接背景 |",
            "",
            "**近10日融资承接表**",
            "",
            "| 日期 | 融资余额 | 两市成交额 | 融资承接比 | 状态 |",
            "|------|----------|------------|------------|------|",
        ]
    )
    for row in _display_latest_first(rows[-10:]):
        lines.append(
            f"| {row.get('trade_date', '')} | {_format_amount_yi(row.get('margin_balance_yi'))} | "
            f"{_format_amount_yi(row.get('market_turnover_yi'))} | {_format_pct(row.get('margin_turnover_ratio_pct'))} | "
            f"{row.get('pressure_label', '待累计')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {"margin_pressure": snapshot}, "module_logs": []}


MARKET_OVERVIEW_NODE_BUILDERS = {
    "header": build_market_overview_header_node,
    "indices": build_market_overview_indices_node,
    "volume": build_market_overview_volume_node,
    "price_band_style": build_market_overview_price_band_style_node,
    "new_high": build_market_overview_new_high_node,
    "margin_pressure": build_market_overview_margin_pressure_node,
    "sentiment": build_market_overview_sentiment_node,
}


def build_market_overview_section_result(context):
    context = context or {}
    node_specs = build_market_overview_node_specs(
        MARKET_OVERVIEW_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_market_overview_nodes(node_specs, context)


def render_market_overview_section(context):
    return build_market_overview_section_result(context)["lines"]
