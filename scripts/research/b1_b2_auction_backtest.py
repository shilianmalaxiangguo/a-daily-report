from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import statistics
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "b1_b2_auction_backtest" / "cases.json"
)
DEFAULT_OUTPUT_JSON = (
    ROOT / "reports" / "research" / "b1-b2-auction-backtest-20260721.json"
)
DEFAULT_OUTPUT_MD = (
    ROOT / "reports" / "research" / "b1-b2-auction-backtest-20260721.md"
)

FIXTURE_SCHEMA_VERSION = "b1_b2_auction_cases.v2"
RESULT_SCHEMA_VERSION = "b1_b2_auction_backtest.v2"
AS_OF_DATE = "2026-07-21"
BENCHMARK_CODE = "000001"
BENCHMARK_NAME = "上证指数"
BENCHMARK_MARKET = 1
DEFAULT_TDX_HOSTS = (
    ("杭州电信主站J2", "115.238.56.198", 7709),
    ("杭州电信主站J3", "218.75.126.9", 7709),
)

OPENING_GAP_ORDER = (
    "大幅高开",
    "中高开",
    "平开",
    "中低开",
    "大幅低开",
)
MORNING_PATH_ORDER = (
    "高开延续",
    "高开回落",
    "低开修复",
    "低开延续下行",
    "平开走强",
    "平开走弱",
    "震荡",
)
VALID_MORNING_PATHS_BY_OPENING = {
    "大幅高开": ("高开延续", "高开回落", "震荡"),
    "中高开": ("高开延续", "高开回落", "震荡"),
    "平开": ("平开走强", "平开走弱", "震荡"),
    "中低开": ("低开修复", "低开延续下行", "震荡"),
    "大幅低开": ("低开修复", "低开延续下行", "震荡"),
}
STRATEGY_ORDER = (
    "auction_1x",
    "qualified_b1_1x",
    "split_1x_confirm",
    "formal_plan_b1_b2",
    "auction_full_plan",
)
STRATEGY_LABELS = {
    "auction_1x": "开盘价代理一次买1x",
    "qualified_b1_1x": "价格条件成立后买B1/1x",
    "split_1x_confirm": "开盘0.5x+确认0.5x（实验）",
    "formal_plan_b1_b2": "正式计划：B1/1x，B2确认后到2x",
    "auction_full_plan": "开盘价代理一次买完整计划",
}

DECISION_CASES = (
    {
        "case_id": "20260602_300308",
        "report_date": "2026-06-02",
        "source_format": "legacy_explicit",
        "security_code": "300308",
        "security_name": "中际旭创",
        "planned_position_x": 2,
        "evidence_labels": ["T0主对象", "唯一对象", "明日唯一动作"],
    },
    {
        "case_id": "20260603_600584",
        "report_date": "2026-06-03",
        "source_format": "legacy_explicit",
        "security_code": "600584",
        "security_name": "长电科技",
        "planned_position_x": 2,
        "evidence_labels": ["最终结果", "明日执行目标", "明日唯一动作"],
    },
    {
        "case_id": "20260615_002428",
        "report_date": "2026-06-15",
        "source_format": "standardized",
        "security_code": "002428",
        "security_name": "云南锗业",
        "planned_position_x": 1,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260616_002436",
        "report_date": "2026-06-16",
        "source_format": "standardized",
        "security_code": "002436",
        "security_name": "兴森科技",
        "planned_position_x": 1,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260617_603986",
        "report_date": "2026-06-17",
        "source_format": "standardized",
        "security_code": "603986",
        "security_name": "兆易创新",
        "planned_position_x": 1,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260618_600667",
        "report_date": "2026-06-18",
        "source_format": "standardized",
        "security_code": "600667",
        "security_name": "太极实业",
        "planned_position_x": 1,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260624_600584",
        "report_date": "2026-06-24",
        "source_format": "standardized",
        "security_code": "600584",
        "security_name": "长电科技",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260626_600667",
        "report_date": "2026-06-26",
        "source_format": "standardized",
        "security_code": "600667",
        "security_name": "太极实业",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260629_000021",
        "report_date": "2026-06-29",
        "source_format": "standardized",
        "security_code": "000021",
        "security_name": "深科技",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260630_002407",
        "report_date": "2026-06-30",
        "source_format": "standardized",
        "security_code": "002407",
        "security_name": "多氟多",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260701_600667",
        "report_date": "2026-07-01",
        "source_format": "standardized",
        "security_code": "600667",
        "security_name": "太极实业",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260703_600667",
        "report_date": "2026-07-03",
        "source_format": "standardized",
        "security_code": "600667",
        "security_name": "太极实业",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "执行性质"],
    },
    {
        "case_id": "20260707_002185",
        "report_date": "2026-07-07",
        "source_format": "standardized",
        "security_code": "002185",
        "security_name": "华天科技",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "B1先买参与权", "B2只在确认后补"],
    },
    {
        "case_id": "20260709_600584",
        "report_date": "2026-07-09",
        "source_format": "standardized",
        "security_code": "600584",
        "security_name": "长电科技",
        "planned_position_x": 2,
        "evidence_labels": ["明日执行对象", "B1先买参与权", "B2只买确认权"],
    },
)


__all__ = [
    "build_backtest",
    "build_daily_ledgers",
    "build_strategy_legs",
    "classify_morning_path",
    "classify_opening_gap",
    "collect_fixture",
    "evaluate_strategies",
    "expected_a_share_one_minute_bar_times",
    "find_b1_fill",
    "find_b2_fill",
    "render_markdown",
    "summarize_strategy_rows",
    "tail_window_exit_price",
    "validate_benchmark_market_data",
    "validate_case_market_data",
    "validate_fixture",
]


def _round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(value):
    if not isinstance(value, (bytes, bytearray)):
        value = str(value).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value):
    return _sha256(_canonical_json(value))


def _atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def expected_a_share_one_minute_bar_times():
    times = []
    for hour, minute_start, minute_end in ((9, 31, 59), (10, 0, 59), (11, 0, 30)):
        times.extend(f"{hour:02d}:{minute:02d}" for minute in range(minute_start, minute_end + 1))
    times.extend(f"13:{minute:02d}" for minute in range(1, 60))
    times.extend(f"14:{minute:02d}" for minute in range(0, 60))
    times.append("15:00")
    return times


def classify_opening_gap(gap_pct):
    gap_pct = float(gap_pct)
    if gap_pct >= 5.0:
        return "大幅高开"
    if gap_pct >= 2.0:
        return "中高开"
    if gap_pct > -2.0:
        return "平开"
    if gap_pct > -5.0:
        return "中低开"
    return "大幅低开"


def _bar_time(bar):
    return str(bar.get("datetime") or "")[11:16]


def _cumulative_vwaps(bars):
    cumulative_amount = 0.0
    cumulative_volume = 0.0
    values = []
    for bar in bars:
        volume = max(float(bar.get("volume") or 0.0), 0.0)
        amount = max(float(bar.get("amount") or 0.0), 0.0)
        cumulative_volume += volume
        cumulative_amount += amount
        if cumulative_volume > 0 and cumulative_amount > 0:
            values.append(cumulative_amount / cumulative_volume)
        else:
            values.append(float(bar.get("close") or 0.0))
    return values


def _find_time_index(bars, time_text):
    for index, bar in enumerate(bars):
        if _bar_time(bar) == time_text:
            return index
    raise ValueError(f"minute bar {time_text} is missing")


def find_b1_fill(bars, *, previous_close, t0_ma5):
    if len(bars) < 41:
        raise ValueError("B1 evaluation requires bars through 10:11")
    previous_close = float(previous_close)
    t0_ma5 = float(t0_ma5)
    vwaps = _cumulative_vwaps(bars)
    opening_index = _find_time_index(bars, "09:35")
    opening_bars = bars[: opening_index + 1]
    opening_price = float(bars[0]["open"])
    opening_close = float(bars[opening_index]["close"])
    opening_high = max(float(bar["high"]) for bar in opening_bars)
    opening_gap_pct = (opening_price / previous_close - 1.0) * 100.0
    high_drawdown_pct = (
        (opening_high - opening_close) / opening_high * 100.0 if opening_high else 0.0
    )
    opening_ok = all(
        (
            opening_close >= vwaps[opening_index],
            opening_close >= previous_close,
            opening_close >= opening_price,
            high_drawdown_pct <= 2.0,
            opening_gap_pct <= 5.0,
        )
    )
    if opening_ok:
        fill = bars[opening_index + 1]
        return {
            "path": "opening_attack",
            "signal_time": _bar_time(bars[opening_index]),
            "fill_time": _bar_time(fill),
            "fill_price": _round(fill["open"], 4),
            "signal_close": _round(opening_close, 4),
            "signal_vwap": _round(vwaps[opening_index], 4),
        }

    start_index = _find_time_index(bars, "09:50")
    last_fill_index = _find_time_index(bars, "10:10")
    for index in range(start_index + 2, last_fill_index):
        current = bars[index]
        closes_above_vwap = all(
            float(bars[cursor]["close"]) >= vwaps[cursor]
            for cursor in range(index - 2, index + 1)
        )
        close = float(current["close"])
        secondary_ok = all(
            (
                closes_above_vwap,
                close >= opening_price,
                close >= t0_ma5,
                close >= float(bars[index - 3]["close"]),
                close <= previous_close * 1.05,
            )
        )
        if not secondary_ok:
            continue
        fill = bars[index + 1]
        if _bar_time(fill) > "10:10":
            continue
        return {
            "path": "secondary_acceptance",
            "signal_time": _bar_time(current),
            "fill_time": _bar_time(fill),
            "fill_price": _round(fill["open"], 4),
            "signal_close": _round(close, 4),
            "signal_vwap": _round(vwaps[index], 4),
        }
    return None


def find_b2_fill(bars, *, previous_close, earliest_fill_time="09:30"):
    if len(bars) < 41:
        raise ValueError("B2 evaluation requires bars through 10:11")
    previous_close = float(previous_close)
    vwaps = _cumulative_vwaps(bars)
    opening_high = max(float(bar["high"]) for bar in bars[:5])
    start_index = _find_time_index(bars, "09:50")
    last_fill_index = _find_time_index(bars, "10:10")
    for index in range(max(start_index + 4, 9), last_fill_index):
        current = bars[index]
        if _bar_time(current) <= earliest_fill_time:
            continue
        closes_above_vwap = all(
            float(bars[cursor]["close"]) >= vwaps[cursor]
            for cursor in range(index - 2, index + 1)
        )
        recent_amount = sum(float(bar.get("amount") or 0.0) for bar in bars[index - 4 : index + 1])
        prior_amount = sum(float(bar.get("amount") or 0.0) for bar in bars[index - 9 : index - 4])
        close = float(current["close"])
        confirmation_ok = all(
            (
                closes_above_vwap,
                close >= previous_close,
                close >= opening_high,
                recent_amount >= prior_amount,
                close <= previous_close * 1.05,
            )
        )
        if not confirmation_ok:
            continue
        fill = bars[index + 1]
        if _bar_time(fill) > "10:10":
            continue
        return {
            "path": "confirmation",
            "signal_time": _bar_time(current),
            "fill_time": _bar_time(fill),
            "fill_price": _round(fill["open"], 4),
            "signal_close": _round(close, 4),
            "signal_vwap": _round(vwaps[index], 4),
        }
    return None


def _relative_snapshot(bars, *, index, previous_close, vwaps):
    close = float(bars[index]["close"])
    vwap = float(vwaps[index])
    previous_close = float(previous_close)
    return {
        "time": _bar_time(bars[index]),
        "close": _round(close, 4),
        "vwap": _round(vwap, 4),
        "vs_vwap_pct": _round((close / vwap - 1.0) * 100.0, 4),
        "vs_previous_close_pct": _round(
            (close / previous_close - 1.0) * 100.0, 4
        ),
        "at_or_above_vwap": close >= vwap,
        "at_or_above_previous_close": close >= previous_close,
    }


def classify_morning_path(bars, *, previous_close):
    open_price = float(bars[0]["open"])
    gap_pct = (open_price / float(previous_close) - 1.0) * 100.0
    opening_class = classify_opening_gap(gap_pct)
    vwaps = _cumulative_vwaps(bars)
    index_0935 = _find_time_index(bars, "09:35")
    index_1010 = _find_time_index(bars, "10:10")
    close_1010 = float(bars[index_1010]["close"])
    vwap_1010 = vwaps[index_1010]
    is_high = opening_class in {"大幅高开", "中高开"}
    is_low = opening_class in {"中低开", "大幅低开"}
    if is_high and close_1010 >= open_price and close_1010 >= vwap_1010:
        path = "高开延续"
    elif is_high and close_1010 < open_price and close_1010 < vwap_1010:
        path = "高开回落"
    elif is_low and close_1010 > open_price and close_1010 >= vwap_1010:
        path = "低开修复"
    elif is_low and close_1010 <= open_price and close_1010 < vwap_1010:
        path = "低开延续下行"
    elif opening_class == "平开" and close_1010 > open_price and close_1010 >= vwap_1010:
        path = "平开走强"
    elif opening_class == "平开" and close_1010 < open_price and close_1010 < vwap_1010:
        path = "平开走弱"
    else:
        path = "震荡"
    return {
        "opening_gap_pct": _round(gap_pct, 4),
        "opening_gap_class": opening_class,
        "morning_path": path,
        "open_price": _round(open_price, 4),
        "close_1010": _round(close_1010, 4),
        "vwap_1010": _round(vwap_1010, 4),
        "status_0935": _relative_snapshot(
            bars,
            index=index_0935,
            previous_close=previous_close,
            vwaps=vwaps,
        ),
        "status_1010": _relative_snapshot(
            bars,
            index=index_1010,
            previous_close=previous_close,
            vwaps=vwaps,
        ),
    }


def _execution_decisions(planned_position_x, b1_fill, b2_fill):
    b1_path_labels = {
        "opening_attack": "09:35主动进攻",
        "secondary_acceptance": "09:50-10:10承接修复",
    }
    if b1_fill:
        b1_decision = {
            "status": "executed",
            "signal_time": b1_fill["signal_time"],
            "fill_time": b1_fill["fill_time"],
            "reason": (
                f"{b1_path_labels.get(b1_fill['path'], 'B1')}价格条件成立，"
                "下一分钟开盘代理成交"
            ),
        }
    else:
        b1_decision = {
            "status": "not_participated",
            "cancellation_time": "10:10",
            "reason": "截至10:10未满足B1价格条件，不参与",
        }

    if int(planned_position_x) != 2:
        formal_b2_decision = {
            "status": "not_in_plan",
            "reason": "计划上限为1x，不执行B2",
        }
    elif not b1_fill:
        formal_b2_decision = {
            "status": "no_execution_qualification",
            "cancellation_time": "10:10",
            "reason": "B1未取得，B2没有执行资格",
        }
    elif b2_fill:
        formal_b2_decision = {
            "status": "executed",
            "signal_time": b2_fill["signal_time"],
            "fill_time": b2_fill["fill_time"],
            "reason": "B2价格确认成立，下一分钟开盘代理成交",
        }
    else:
        formal_b2_decision = {
            "status": "not_executed",
            "cancellation_time": "10:10",
            "reason": "截至10:10未满足B2价格确认，不补第二个1x",
        }
    return b1_decision, formal_b2_decision


def _leg(weight_x, price, fill_time, reason, signal_time=None):
    return {
        "weight_x": float(weight_x),
        "fill_price": _round(price, 4),
        "fill_time": fill_time,
        "signal_time": signal_time or fill_time,
        "reason": reason,
    }


def build_strategy_legs(planned_position_x, features):
    planned_position_x = int(planned_position_x)
    if planned_position_x not in {1, 2}:
        raise ValueError("planned_position_x must be 1 or 2")
    open_price = float(features["open_price"])
    open_fill_time = str(features.get("open_fill_time") or "09:30")
    b1_fill = features.get("b1_fill")
    b2_fill = features.get("b2_fill")
    auction_leg = _leg(1.0, open_price, open_fill_time, "开盘价代理取得1x")
    auction_full_leg = _leg(
        float(planned_position_x),
        open_price,
        open_fill_time,
        "开盘价代理一次买入完整计划",
    )
    b1_leg = None
    if b1_fill:
        b1_leg = _leg(
            1.0,
            b1_fill["fill_price"],
            b1_fill["fill_time"],
            f"B1价格条件成立：{b1_fill['path']}",
            b1_fill["signal_time"],
        )
    confirmation_leg = None
    if b2_fill:
        confirmation_leg = _leg(
            1.0,
            b2_fill["fill_price"],
            b2_fill["fill_time"],
            "B2价格确认成立",
            b2_fill["signal_time"],
        )
    split_confirmation_leg = None
    if b2_fill:
        split_confirmation_leg = _leg(
            0.5,
            b2_fill["fill_price"],
            b2_fill["fill_time"],
            "拆分1x实验的第二个0.5x确认",
            b2_fill["signal_time"],
        )

    formal_legs = []
    if b1_leg:
        formal_legs.append(b1_leg)
        if planned_position_x == 2 and confirmation_leg:
            formal_legs.append(confirmation_leg)
    split_legs = [_leg(0.5, open_price, open_fill_time, "拆分1x实验的首个0.5x")]
    if split_confirmation_leg:
        split_legs.append(split_confirmation_leg)
    return {
        "auction_1x": [auction_leg],
        "qualified_b1_1x": [b1_leg] if b1_leg else [],
        "split_1x_confirm": split_legs,
        "formal_plan_b1_b2": formal_legs,
        "auction_full_plan": [auction_full_leg],
    }


def _market_for_code(code):
    return "SH" if str(code).startswith(("6", "9")) else "SZ"


def _trade_fees(
    gross_value,
    *,
    side,
    market,
    commission_rate,
    minimum_commission,
    stamp_tax_rate,
    transfer_fee_rate,
):
    if gross_value <= 0:
        return 0.0
    commission = max(float(minimum_commission), gross_value * float(commission_rate))
    transfer = gross_value * float(transfer_fee_rate) if market == "SH" else 0.0
    stamp = gross_value * float(stamp_tax_rate) if side == "sell" else 0.0
    return commission + transfer + stamp


def _simulate_actual_lots(
    legs,
    *,
    exit_price,
    market,
    account_capital,
    commission_rate,
    minimum_commission,
    stamp_tax_rate,
    transfer_fee_rate,
):
    cash = float(account_capital)
    total_shares = 0
    total_buy_gross = 0.0
    total_buy_cost = 0.0
    filled_legs = 0
    for leg in legs:
        target_cash = account_capital * 0.5 * float(leg["weight_x"])
        maximum_cash = account_capital * 0.6 * float(leg["weight_x"])
        lot_value = float(leg["fill_price"]) * 100.0
        maximum_lots = int(min(maximum_cash, cash) // lot_value)
        feasible_shares = []
        for lots in range(1, maximum_lots + 1):
            shares = lots * 100
            gross = shares * float(leg["fill_price"])
            fee = _trade_fees(
                gross,
                side="buy",
                market=market,
                commission_rate=commission_rate,
                minimum_commission=minimum_commission,
                stamp_tax_rate=stamp_tax_rate,
                transfer_fee_rate=transfer_fee_rate,
            )
            if gross + fee <= cash + 1e-9:
                feasible_shares.append(shares)
        if not feasible_shares:
            continue
        shares = min(
            feasible_shares,
            key=lambda value: (
                abs(value * float(leg["fill_price"]) - target_cash),
                value * float(leg["fill_price"]) > target_cash,
            ),
        )
        gross = shares * float(leg["fill_price"])
        fee = _trade_fees(
            gross,
            side="buy",
            market=market,
            commission_rate=commission_rate,
            minimum_commission=minimum_commission,
            stamp_tax_rate=stamp_tax_rate,
            transfer_fee_rate=transfer_fee_rate,
        )
        cash -= gross + fee
        total_buy_gross += gross
        total_buy_cost += gross + fee
        total_shares += shares
        filled_legs += 1
    if total_shares <= 0:
        return {
            "actual_shares": 0,
            "actual_filled_leg_count": 0,
            "actual_all_legs_filled": False,
            "actual_position_pct": 0.0,
            "actual_return_net_pct": 0.0,
        }
    sale_gross = total_shares * float(exit_price)
    sale_fee = _trade_fees(
        sale_gross,
        side="sell",
        market=market,
        commission_rate=commission_rate,
        minimum_commission=minimum_commission,
        stamp_tax_rate=stamp_tax_rate,
        transfer_fee_rate=transfer_fee_rate,
    )
    final_value = cash + sale_gross - sale_fee
    return {
        "actual_shares": total_shares,
        "actual_filled_leg_count": filled_legs,
        "actual_all_legs_filled": filled_legs == len(legs),
        "actual_position_pct": _round(total_buy_gross / account_capital * 100.0, 6),
        "actual_return_net_pct": _round(
            (final_value / account_capital - 1.0) * 100.0, 6
        ),
        "actual_buy_cost": _round(total_buy_cost, 2),
        "actual_sale_value_after_fees": _round(sale_gross - sale_fee, 2),
    }


def evaluate_strategies(
    strategies,
    *,
    exit_price,
    exit_time,
    market,
    account_capital,
    commission_rate,
    minimum_commission,
    stamp_tax_rate,
    transfer_fee_rate,
):
    output = OrderedDict()
    for strategy_id in STRATEGY_ORDER:
        legs = [dict(leg) for leg in strategies.get(strategy_id, []) if leg]
        if not legs:
            output[strategy_id] = {
                "strategy_id": strategy_id,
                "strategy_label": STRATEGY_LABELS[strategy_id],
                "traded": False,
                "legs": [],
                "held_x": 0.0,
                "exit_price": _round(exit_price, 4),
                "exit_time": exit_time,
                "account_return_gross_pct": 0.0,
                "account_return_net_pct": 0.0,
                "price_return_gross_pct": None,
                "actual_shares": 0,
                "actual_filled_leg_count": 0,
                "actual_all_legs_filled": False,
                "actual_position_pct": 0.0,
                "actual_return_net_pct": 0.0,
            }
            continue
        total_allocation = 0.0
        total_shares_proxy = 0.0
        buy_fees = 0.0
        for leg in legs:
            allocation = account_capital * 0.5 * float(leg["weight_x"])
            gross_shares = allocation / float(leg["fill_price"])
            total_allocation += allocation
            total_shares_proxy += gross_shares
            buy_fees += _trade_fees(
                allocation,
                side="buy",
                market=market,
                commission_rate=commission_rate,
                minimum_commission=minimum_commission,
                stamp_tax_rate=stamp_tax_rate,
                transfer_fee_rate=transfer_fee_rate,
            )
        sale_gross = total_shares_proxy * float(exit_price)
        sale_fees = _trade_fees(
            sale_gross,
            side="sell",
            market=market,
            commission_rate=commission_rate,
            minimum_commission=minimum_commission,
            stamp_tax_rate=stamp_tax_rate,
            transfer_fee_rate=transfer_fee_rate,
        )
        weighted_entry = total_allocation / total_shares_proxy
        gross_pnl = sale_gross - total_allocation
        net_pnl = gross_pnl - buy_fees - sale_fees
        result = {
            "strategy_id": strategy_id,
            "strategy_label": STRATEGY_LABELS[strategy_id],
            "traded": True,
            "legs": legs,
            "held_x": _round(sum(float(leg["weight_x"]) for leg in legs), 3),
            "weighted_entry_price": _round(weighted_entry, 4),
            "exit_price": _round(exit_price, 4),
            "exit_time": exit_time,
            "price_return_gross_pct": _round(
                (float(exit_price) / weighted_entry - 1.0) * 100.0, 6
            ),
            "account_return_gross_pct": _round(
                gross_pnl / account_capital * 100.0, 6
            ),
            "account_return_net_pct": _round(net_pnl / account_capital * 100.0, 6),
            "buy_fees": _round(buy_fees, 2),
            "sell_fees": _round(sale_fees, 2),
        }
        result.update(
            _simulate_actual_lots(
                legs,
                exit_price=exit_price,
                market=market,
                account_capital=account_capital,
                commission_rate=commission_rate,
                minimum_commission=minimum_commission,
                stamp_tax_rate=stamp_tax_rate,
                transfer_fee_rate=transfer_fee_rate,
            )
        )
        output[strategy_id] = result
    return output


def _daily_by_date(case):
    if case.get("daily_bars"):
        return {str(row["date"]): row for row in case["daily_bars"]}
    if case.get("daily_closes"):
        return {
            str(date): {"date": str(date), "close": float(close)}
            for date, close in case["daily_closes"].items()
        }
    raise ValueError(f"{case.get('case_id', 'case')} lacks daily marks")


def _aggregate_minute_day(bars):
    return {
        "open": float(bars[0]["open"]),
        "high": max(float(row["high"]) for row in bars),
        "low": min(float(row["low"]) for row in bars),
        "close": float(bars[-1]["close"]),
        "volume": sum(float(row.get("volume") or 0.0) for row in bars),
        "amount": sum(float(row.get("amount") or 0.0) for row in bars),
    }


def validate_case_market_data(case):
    report_date = str(case.get("report_date") or "")
    entry_date = str(case.get("entry_date") or "")
    exit_date = str(case.get("exit_date") or "")
    if not report_date or not entry_date or not exit_date:
        raise ValueError("report_date, entry_date and exit_date are required")
    if not report_date < entry_date < exit_date:
        raise ValueError("report_date, entry_date and exit_date must be ordered")
    expected_times = expected_a_share_one_minute_bar_times()
    daily = _daily_by_date(case)
    if report_date not in daily:
        raise ValueError(f"daily bar missing for report_date {report_date}")
    next_trade_dates = sorted(date for date in daily if date > report_date)[:2]
    if next_trade_dates != [entry_date, exit_date]:
        raise ValueError(
            "entry_date and exit_date must be the first two trading dates after "
            f"report_date: {next_trade_dates} != {[entry_date, exit_date]}"
        )
    for target_date in (entry_date, exit_date):
        bars = (case.get("minute_days") or {}).get(target_date) or []
        if len(bars) != 240:
            raise ValueError(f"{target_date} must contain 240 minute bars")
        observed_dates = {str(row.get("datetime") or "")[:10] for row in bars}
        if observed_dates != {target_date}:
            role = "entry_date" if target_date == entry_date else "exit_date"
            raise ValueError(f"minute bars do not match {role} {target_date}")
        observed_times = [_bar_time(row) for row in bars]
        if observed_times != expected_times:
            raise ValueError(f"{target_date} minute grid is incomplete or out of order")
        if target_date not in daily:
            raise ValueError(f"daily bar missing for {target_date}")
        aggregate = _aggregate_minute_day(bars)
        daily_row = daily[target_date]
        for field in ("open", "high", "low", "close"):
            if not math.isclose(
                aggregate[field], float(daily_row[field]), abs_tol=0.021, rel_tol=0.0
            ):
                raise ValueError(
                    f"{target_date} minute/daily {field} mismatch: "
                    f"{aggregate[field]} != {daily_row[field]}"
                )
        for field in ("volume", "amount"):
            if not math.isclose(
                aggregate[field],
                float(daily_row[field]),
                abs_tol=1.0,
                rel_tol=0.00001,
            ):
                raise ValueError(
                    f"{target_date} minute/daily {field} mismatch: "
                    f"{aggregate[field]} != {daily_row[field]}"
                )
    return {
        "status": "verified",
        "entry_bar_count": 240,
        "exit_bar_count": 240,
    }


def validate_benchmark_market_data(benchmark, target_dates):
    if benchmark.get("code") != BENCHMARK_CODE:
        raise ValueError(f"benchmark code must be {BENCHMARK_CODE}")
    if benchmark.get("name") != BENCHMARK_NAME:
        raise ValueError(f"benchmark name must be {BENCHMARK_NAME}")
    if int(benchmark.get("market_number", -1)) != BENCHMARK_MARKET:
        raise ValueError(f"benchmark market_number must be {BENCHMARK_MARKET}")
    source = benchmark.get("source") or {}
    if source.get("query_date") != AS_OF_DATE:
        raise ValueError("benchmark source query_date must match as_of_date")
    if source.get("bar_time_semantics") != "interval_end":
        raise ValueError("benchmark bar_time_semantics must be interval_end")

    target_dates = sorted(set(str(value) for value in target_dates))
    if source.get("source_dates") != target_dates:
        raise ValueError("benchmark source_dates mismatch")
    daily_rows = sorted(benchmark.get("daily_bars") or [], key=lambda row: row["date"])
    daily_by_date = {str(row["date"]): row for row in daily_rows}
    if len(daily_by_date) != len(daily_rows):
        raise ValueError("benchmark daily dates must be unique")
    daily_dates = [str(row["date"]) for row in daily_rows]
    expected_times = expected_a_share_one_minute_bar_times()
    for target_date in target_dates:
        if target_date not in daily_by_date:
            raise ValueError(f"benchmark daily bar missing for {target_date}")
        target_index = daily_dates.index(target_date)
        if target_index <= 0:
            raise ValueError(
                f"benchmark previous trading close missing before {target_date}"
            )
        bars = (benchmark.get("minute_days") or {}).get(target_date) or []
        if len(bars) != 240:
            raise ValueError(f"benchmark {target_date} must contain 240 minute bars")
        if {str(row.get("datetime") or "")[:10] for row in bars} != {target_date}:
            raise ValueError(f"benchmark minute bars do not match {target_date}")
        if [_bar_time(row) for row in bars] != expected_times:
            raise ValueError(
                f"benchmark {target_date} minute grid is incomplete or out of order"
            )
        aggregate = _aggregate_minute_day(bars)
        daily_row = daily_by_date[target_date]
        for field in ("open", "high", "low", "close"):
            if not math.isclose(
                aggregate[field], float(daily_row[field]), abs_tol=0.021, rel_tol=0.0
            ):
                raise ValueError(
                    f"benchmark {target_date} minute/daily {field} mismatch: "
                    f"{aggregate[field]} != {daily_row[field]}"
                )
        if not math.isclose(
            aggregate["amount"],
            float(daily_row["amount"]),
            abs_tol=1.0,
            rel_tol=0.00001,
        ):
            raise ValueError(
                f"benchmark {target_date} minute/daily amount mismatch: "
                f"{aggregate['amount']} != {daily_row['amount']}"
            )

    market_payload = {
        "daily_bars": benchmark.get("daily_bars") or [],
        "minute_days": benchmark.get("minute_days") or {},
        "source": source,
    }
    if _canonical_hash(market_payload) != benchmark.get("market_data_sha256"):
        raise ValueError("benchmark market_data_sha256 mismatch")
    return {
        "status": "verified",
        "target_date_count": len(target_dates),
        "minute_bar_count": len(target_dates) * 240,
    }


def _window_vwap(bars, start_time, end_time):
    selected = [row for row in bars if start_time <= _bar_time(row) <= end_time]
    volume = sum(float(row.get("volume") or 0.0) for row in selected)
    amount = sum(float(row.get("amount") or 0.0) for row in selected)
    if volume <= 0 or amount <= 0:
        raise ValueError(f"{start_time}-{end_time} has no usable turnover")
    return amount / volume


def tail_window_exit_price(bars):
    return _window_vwap(bars, "14:31", "14:55")


def _benchmark_tail_window_exit_price(bars):
    selected = [
        float(row["close"])
        for row in bars
        if "14:31" <= _bar_time(row) <= "14:55"
    ]
    if len(selected) != 25:
        raise ValueError("benchmark 14:31-14:55 requires 25 minute closes")
    return statistics.fmean(selected)


def _benchmark_fill_price(benchmark, trade_date, fill_time):
    daily = {str(row["date"]): row for row in benchmark["daily_bars"]}
    if fill_time == "09:30":
        return float(daily[trade_date]["open"])
    bars = benchmark["minute_days"][trade_date]
    index = _find_time_index(bars, fill_time)
    return float(bars[index]["open"])


def _price_extremes(entry_bars, exit_bars, fill_time):
    path = [row for row in entry_bars if _bar_time(row) >= fill_time]
    path.extend(row for row in exit_bars if _bar_time(row) <= "14:55")
    if not path:
        return None, None
    return (
        max(float(row["high"]) for row in path),
        min(float(row["low"]) for row in path),
    )


def _t0_moving_average(case, window):
    rows = sorted(case["daily_bars"], key=lambda row: row["date"])
    eligible = [row for row in rows if row["date"] <= case["report_date"]]
    if len(eligible) < window:
        raise ValueError(f"{case['case_id']} lacks T0 MA{window} history")
    return sum(float(row["close"]) for row in eligible[-window:]) / window


def _attach_path_metrics(strategy_results, entry_bars, exit_bars, sensitivity_prices):
    for result in strategy_results.values():
        if not result["traded"]:
            result.update(
                {
                    "mfe_price_pct": None,
                    "mae_price_pct": None,
                    "sensitivity_price_return_pct": {},
                }
            )
            continue
        fill_time = min(str(leg["fill_time"]) for leg in result["legs"])
        high, low = _price_extremes(entry_bars, exit_bars, fill_time)
        entry = float(result["weighted_entry_price"])
        result["mfe_price_pct"] = _round((high / entry - 1.0) * 100.0, 6)
        result["mae_price_pct"] = _round((low / entry - 1.0) * 100.0, 6)
        result["sensitivity_price_return_pct"] = {
            key: _round((float(price) / entry - 1.0) * 100.0, 6)
            for key, price in sensitivity_prices.items()
        }


def _build_case_result(case, parameters):
    validate_case_market_data(case)
    daily = _daily_by_date(case)
    report_daily = daily[case["report_date"]]
    entry_daily = daily[case["entry_date"]]
    exit_daily = daily[case["exit_date"]]
    entry_bars = case["minute_days"][case["entry_date"]]
    exit_bars = case["minute_days"][case["exit_date"]]
    previous_close = float(report_daily["close"])
    t0_ma5 = _t0_moving_average(case, 5)
    scenario = classify_morning_path(entry_bars, previous_close=previous_close)
    b1_fill = find_b1_fill(
        entry_bars,
        previous_close=previous_close,
        t0_ma5=t0_ma5,
    )
    earliest = b1_fill["fill_time"] if b1_fill else "09:30"
    b2_fill = find_b2_fill(
        entry_bars,
        previous_close=previous_close,
        earliest_fill_time=earliest,
    )
    b1_decision, formal_b2_decision = _execution_decisions(
        case["planned_position_x"], b1_fill, b2_fill
    )
    features = {
        **scenario,
        "open_fill_time": "09:30",
        "previous_close": _round(previous_close, 4),
        "t0_ma5": _round(t0_ma5, 4),
        "t0_ma7": _round(_t0_moving_average(case, 7), 4),
        "b1_fill": b1_fill,
        "b2_fill": b2_fill,
        "b1_decision": b1_decision,
        "formal_b2_decision": formal_b2_decision,
        "opening_liquidity_proxy": bool(float(entry_bars[0].get("volume") or 0.0) > 0),
    }
    legs = build_strategy_legs(case["planned_position_x"], features)
    exit_price = tail_window_exit_price(exit_bars)
    exit_time = f"{case['exit_date']} 14:30-14:55"
    results = evaluate_strategies(
        legs,
        exit_price=exit_price,
        exit_time=exit_time,
        market=_market_for_code(case["security_code"]),
        account_capital=parameters["account_capital"],
        commission_rate=parameters["commission_rate"],
        minimum_commission=parameters["minimum_commission"],
        stamp_tax_rate=parameters["stamp_tax_rate"],
        transfer_fee_rate=parameters["transfer_fee_rate"],
    )
    sensitivity = {
        "entry_day_close": float(entry_daily["close"]),
        "exit_day_open": float(exit_daily["open"]),
        "exit_day_close": float(exit_daily["close"]),
    }
    _attach_path_metrics(results, entry_bars, exit_bars, sensitivity)
    auction_net = float(results["auction_1x"]["account_return_net_pct"])
    qualified = results["qualified_b1_1x"]
    missed_opportunity = {
        "qualified_b1_not_participated": not qualified["traded"],
        "auction_1x_net_pct": _round(auction_net, 6),
        "missed_positive_auction_outcome": bool(
            not qualified["traded"] and auction_net > 0.0
        ),
        "avoided_negative_auction_outcome": bool(
            not qualified["traded"] and auction_net < 0.0
        ),
    }
    return {
        "case_id": case["case_id"],
        "report_date": case["report_date"],
        "entry_date": case["entry_date"],
        "exit_date": case["exit_date"],
        "source_format": case["source_format"],
        "security_code": case["security_code"],
        "security_name": case["security_name"],
        "planned_position_x": int(case["planned_position_x"]),
        "report_source": case["report_source"],
        "market_data_sha256": case["market_data_sha256"],
        "features": features,
        "primary_exit": {
            "time": exit_time,
            "price": _round(exit_price, 4),
            "price_proxy": "14:30-14:55成交额加权均价",
        },
        "sensitivity_prices": {key: _round(value, 4) for key, value in sensitivity.items()},
        "daily_closes": {
            str(row["date"]): _round(row["close"], 4)
            for row in case["daily_bars"]
        },
        "missed_opportunity": missed_opportunity,
        "strategies": results,
    }


def _actual_lot_fill(
    *,
    price,
    target_gross,
    minimum_gross,
    maximum_gross,
    cash,
    market,
    parameters,
):
    lot_value = float(price) * 100.0
    maximum_lots = int(min(float(maximum_gross), float(cash)) // lot_value)
    candidates = []
    for lots in range(1, maximum_lots + 1):
        shares = lots * 100
        gross = shares * float(price)
        if gross + 1e-9 < float(minimum_gross):
            continue
        fee = _trade_fees(
            gross,
            side="buy",
            market=market,
            commission_rate=parameters["commission_rate"],
            minimum_commission=parameters["minimum_commission"],
            stamp_tax_rate=parameters["stamp_tax_rate"],
            transfer_fee_rate=parameters["transfer_fee_rate"],
        )
        if gross + fee <= float(cash) + 1e-9:
            candidates.append((shares, gross, fee))
    if not candidates:
        return None
    shares, gross, fee = min(
        candidates,
        key=lambda row: (
            abs(row[1] - float(target_gross)),
            row[1] > float(target_gross),
        ),
    )
    return {"shares": shares, "gross": gross, "fee": fee}


def _actual_lot_unavailable_reason(
    *,
    price,
    minimum_gross,
    maximum_gross,
    cash,
    market,
    parameters,
):
    """Explain why no 100-share fill was possible without guessing."""
    if float(cash) <= 0.0:
        return "现金不足"
    lot_value = float(price) * 100.0
    maximum_lots = int(min(float(maximum_gross), float(cash)) // lot_value)
    if maximum_lots < 1:
        if lot_value > float(maximum_gross) + 1e-9:
            return "一手金额超过60%仓位容忍上限"
        return "现金不足以买入一手并支付费用"
    minimum_lot_fee = _trade_fees(
        lot_value,
        side="buy",
        market=market,
        commission_rate=parameters["commission_rate"],
        minimum_commission=parameters["minimum_commission"],
        stamp_tax_rate=parameters["stamp_tax_rate"],
        transfer_fee_rate=parameters["transfer_fee_rate"],
    )
    if float(cash) < lot_value + minimum_lot_fee:
        return "现金不足以支付一手费用"
    return "100股整手不落在40%-60%仓位容忍带"


def _benchmark_daily_maps(benchmark):
    rows = sorted(benchmark["daily_bars"], key=lambda row: row["date"])
    return rows, {str(row["date"]): row for row in rows}


def _ledger_drawdown_pct(daily_rows):
    peak = 1.0
    value = 1.0
    drawdown = 0.0
    for row in daily_rows:
        value *= 1.0 + float(row["account_return_pct"]) / 100.0
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1.0)
    return _round(drawdown * 100.0, 6)


def _standardized_contribution(
    *,
    position,
    role,
    end_price,
    benchmark_end_price,
    starting_nav,
    fee,
):
    weight = 0.5 * float(position["nominal_x"])
    start_price = float(position["last_mark_price"])
    price_return = float(end_price) / start_price - 1.0
    benchmark_start_price = float(position["last_benchmark_price"])
    benchmark_return = float(benchmark_end_price) / benchmark_start_price - 1.0
    gross_contribution_pct = weight * price_return * 100.0
    fee_pct = float(fee) / float(starting_nav) * 100.0
    return {
        "case_id": position["case_id"],
        "security_code": position["security_code"],
        "security_name": position["security_name"],
        "role": role,
        "nominal_x": _round(position["nominal_x"], 3),
        "account_weight_pct": _round(weight * 100.0, 6),
        "start_price": _round(start_price, 4),
        "end_price": _round(end_price, 4),
        "price_return_pct": _round(price_return * 100.0, 6),
        "fees": _round(fee, 2),
        "gross_account_contribution_pct": _round(gross_contribution_pct, 6),
        "account_contribution_pct": _round(
            gross_contribution_pct - fee_pct, 6
        ),
        "benchmark_start_price": _round(benchmark_start_price, 4),
        "benchmark_end_price": _round(benchmark_end_price, 4),
        "benchmark_price_return_pct": _round(benchmark_return * 100.0, 6),
        "benchmark_contribution_pct": _round(
            weight * benchmark_return * 100.0, 6
        ),
    }


def _build_standardized_daily_ledger(
    case_rows, benchmark, parameters, strategy_id
):
    initial_capital = float(parameters["account_capital"])
    nav = initial_capital
    benchmark_nav = initial_capital
    positions = []
    entries_by_date = {}
    for case in case_rows:
        entries_by_date.setdefault(case["entry_date"], []).append(case)
    benchmark_rows, benchmark_daily = _benchmark_daily_maps(benchmark)
    benchmark_dates = [str(row["date"]) for row in benchmark_rows]
    if not case_rows:
        return {
            "mode": "standardized",
            "calculation_contract": (
                "每条1x固定贡献0.5×该腿当日收益率；同日各腿相加后扣当日费用"
            ),
            "strategy_id": strategy_id,
            "strategy_label": STRATEGY_LABELS[strategy_id],
            "initial_capital": _round(initial_capital, 2),
            "ending_nav": _round(initial_capital, 6),
            "cumulative_return_pct": 0.0,
            "benchmark_ending_nav": _round(initial_capital, 6),
            "benchmark_cumulative_return_pct": 0.0,
            "cumulative_return_difference_pct": 0.0,
            "relative_nav_excess_pct": 0.0,
            "maximum_drawdown_pct": 0.0,
            "total_fees": 0.0,
            "capacity_limited_leg_count": 0,
            "lot_unavailable_leg_count": 0,
            "overlap_dates": [],
            "daily": [],
        }
    min_entry_date = min(str(case["entry_date"]) for case in case_rows)
    max_exit_date = max(str(case["exit_date"]) for case in case_rows)
    event_dates = [
        date for date in benchmark_dates if min_entry_date <= date <= max_exit_date
    ]
    daily_rows = []
    total_fees = 0.0
    capacity_limited_leg_count = 0
    overlap_dates = []

    for trade_date in event_dates:
        starting_nav = nav
        starting_benchmark_nav = benchmark_nav
        starting_nominal_x = sum(float(position["nominal_x"]) for position in positions)
        peak_nominal_x = starting_nominal_x
        actions = []
        contributions = []
        executed_entry_count = 0

        for case in sorted(entries_by_date.get(trade_date, []), key=lambda row: row["case_id"]):
            strategy = case["strategies"][strategy_id]
            legs = sorted(
                (dict(leg) for leg in strategy.get("legs") or []),
                key=lambda leg: (str(leg["fill_time"]), float(leg["weight_x"])),
            )
            for leg_index, leg in enumerate(legs, start=1):
                requested_x = float(leg["weight_x"])
                occupied_x = sum(float(position["nominal_x"]) for position in positions)
                available_x = max(0.0, 2.0 - occupied_x)
                accepted_x = min(requested_x, available_x)
                action = {
                    "action": "buy",
                    "case_id": case["case_id"],
                    "security_code": case["security_code"],
                    "security_name": case["security_name"],
                    "leg_index": leg_index,
                    "fill_time": str(leg["fill_time"]),
                    "requested_x": _round(requested_x, 3),
                    "available_x_before": _round(available_x, 3),
                }
                if accepted_x <= 1e-9:
                    action.update(
                        status="not_executed",
                        executed_x=0.0,
                        reason="旧仓仍占满账户容量，早盘不新增",
                    )
                    capacity_limited_leg_count += 1
                    actions.append(action)
                    continue
                if accepted_x + 1e-9 < requested_x:
                    capacity_limited_leg_count += 1
                market = _market_for_code(case["security_code"])
                notional = starting_nav * 0.5 * accepted_x
                buy_fee = _trade_fees(
                    notional,
                    side="buy",
                    market=market,
                    commission_rate=parameters["commission_rate"],
                    minimum_commission=parameters["minimum_commission"],
                    stamp_tax_rate=parameters["stamp_tax_rate"],
                    transfer_fee_rate=parameters["transfer_fee_rate"],
                )
                positions.append(
                    {
                        "case": case,
                        "case_id": case["case_id"],
                        "security_code": case["security_code"],
                        "security_name": case["security_name"],
                        "leg_index": leg_index,
                        "entry_date": trade_date,
                        "exit_date": case["exit_date"],
                        "fill_time": str(leg["fill_time"]),
                        "nominal_x": accepted_x,
                        "entry_notional": notional,
                        "entry_price": float(leg["fill_price"]),
                        "pending_buy_fee": buy_fee,
                        "last_mark_price": float(leg["fill_price"]),
                        "last_benchmark_price": _benchmark_fill_price(
                            benchmark, trade_date, str(leg["fill_time"])
                        ),
                    }
                )
                executed_entry_count += 1
                peak_nominal_x = max(
                    peak_nominal_x,
                    sum(float(position["nominal_x"]) for position in positions),
                )
                action.update(
                    status=(
                        "capacity_clipped"
                        if accepted_x + 1e-9 < requested_x
                        else "executed"
                    ),
                    executed_x=_round(accepted_x, 3),
                    account_weight_pct=_round(accepted_x * 50.0, 6),
                    notional=_round(notional, 2),
                    fee=_round(buy_fee, 2),
                    reason=(
                        "账户只剩部分容量，按剩余容量执行"
                        if accepted_x + 1e-9 < requested_x
                        else "按计划容量执行"
                    ),
                )
                actions.append(action)

        if starting_nominal_x > 1e-9 and executed_entry_count:
            overlap_dates.append(trade_date)

        exiting = [position for position in positions if position["exit_date"] == trade_date]
        benchmark_exit_price = (
            _benchmark_tail_window_exit_price(benchmark["minute_days"][trade_date])
            if exiting
            else None
        )
        for position in exiting:
            case = position["case"]
            exit_price = float(case["primary_exit"]["price"])
            target_sale_value = (
                float(position["entry_notional"])
                / float(position["entry_price"])
                * exit_price
            )
            sell_fee = _trade_fees(
                target_sale_value,
                side="sell",
                market=_market_for_code(position["security_code"]),
                commission_rate=parameters["commission_rate"],
                minimum_commission=parameters["minimum_commission"],
                stamp_tax_rate=parameters["stamp_tax_rate"],
                transfer_fee_rate=parameters["transfer_fee_rate"],
            )
            contributions.append(
                _standardized_contribution(
                    position=position,
                    role="旧仓尾盘退出",
                    end_price=exit_price,
                    benchmark_end_price=benchmark_exit_price,
                    starting_nav=starting_nav,
                    fee=sell_fee,
                )
            )
            actions.append(
                {
                    "action": "sell",
                    "case_id": position["case_id"],
                    "security_code": position["security_code"],
                    "security_name": position["security_name"],
                    "status": "executed",
                    "fill_time": "14:30-14:55",
                    "executed_x": _round(position["nominal_x"], 3),
                    "account_weight_pct": _round(
                        float(position["nominal_x"]) * 50.0, 6
                    ),
                    "notional": _round(target_sale_value, 2),
                    "fee": _round(sell_fee, 2),
                }
            )
        if exiting:
            exiting_ids = {id(position) for position in exiting}
            positions = [position for position in positions if id(position) not in exiting_ids]

        for position in positions:
            case = position["case"]
            case_daily = _daily_by_date(case)
            if trade_date == position["entry_date"]:
                end_price = float(case["sensitivity_prices"]["entry_day_close"])
                role = "新仓入场至收盘"
            else:
                if trade_date not in case_daily:
                    raise ValueError(
                        f"{position['case_id']} lacks daily mark for {trade_date}"
                    )
                end_price = float(case_daily[trade_date]["close"])
                role = "持仓日收盘标记"
            benchmark_end_price = float(benchmark_daily[trade_date]["close"])
            contributions.append(
                _standardized_contribution(
                    position=position,
                    role=role,
                    end_price=end_price,
                    benchmark_end_price=benchmark_end_price,
                    starting_nav=starting_nav,
                    fee=position["pending_buy_fee"],
                )
            )
            position["pending_buy_fee"] = 0.0
            position["last_mark_price"] = end_price
            position["last_benchmark_price"] = benchmark_end_price

        account_return_pct = sum(
            float(row["account_contribution_pct"]) for row in contributions
        )
        benchmark_return_pct = sum(
            float(row["benchmark_contribution_pct"]) for row in contributions
        )
        nav *= 1.0 + account_return_pct / 100.0
        benchmark_nav *= 1.0 + benchmark_return_pct / 100.0
        benchmark_index = benchmark_dates.index(trade_date)
        previous_benchmark_close = float(benchmark_rows[benchmark_index - 1]["close"])
        benchmark_close = float(benchmark_daily[trade_date]["close"])
        fees_today = sum(float(row["fees"]) for row in contributions)
        total_fees += fees_today
        ending_nominal_x = sum(float(position["nominal_x"]) for position in positions)
        daily_rows.append(
            {
                "date": trade_date,
                "starting_nav": _round(starting_nav, 6),
                "ending_nav": _round(nav, 6),
                "account_return_pct": _round(account_return_pct, 6),
                "cumulative_account_return_pct": _round(
                    (nav / initial_capital - 1.0) * 100.0, 6
                ),
                "benchmark_starting_nav": _round(starting_benchmark_nav, 6),
                "benchmark_ending_nav": _round(benchmark_nav, 6),
                "benchmark_same_period_return_pct": _round(
                    benchmark_return_pct, 6
                ),
                "cumulative_benchmark_return_pct": _round(
                    (benchmark_nav / initial_capital - 1.0) * 100.0, 6
                ),
                "daily_excess_pct": _round(
                    account_return_pct - benchmark_return_pct, 6
                ),
                "daily_relative_excess_pct": _round(
                    (
                        (1.0 + account_return_pct / 100.0)
                        / (1.0 + benchmark_return_pct / 100.0)
                        - 1.0
                    )
                    * 100.0,
                    6,
                ),
                "cumulative_return_difference_pct": _round(
                    (nav - benchmark_nav) / initial_capital * 100.0, 6
                ),
                "relative_nav_excess_pct": _round(
                    (nav / benchmark_nav - 1.0) * 100.0, 6
                ),
                "shanghai_full_day_return_pct": _round(
                    (benchmark_close / previous_benchmark_close - 1.0) * 100.0,
                    6,
                ),
                "starting_nominal_x": _round(starting_nominal_x, 3),
                "peak_nominal_x": _round(peak_nominal_x, 3),
                "ending_nominal_x": _round(ending_nominal_x, 3),
                "fees": _round(fees_today, 2),
                "contributions": sorted(
                    contributions,
                    key=lambda row: (row["role"], row["case_id"]),
                ),
                "actions": actions,
            }
        )

    if positions:
        raise ValueError(f"{strategy_id} standardized ledger ended with open positions")
    return {
        "mode": "standardized",
        "calculation_contract": (
            "每条1x固定贡献0.5×该腿当日收益率；同日各腿相加后扣当日费用"
        ),
        "strategy_id": strategy_id,
        "strategy_label": STRATEGY_LABELS[strategy_id],
        "initial_capital": _round(initial_capital, 2),
        "ending_nav": _round(nav, 6),
        "cumulative_return_pct": _round(
            (nav / initial_capital - 1.0) * 100.0, 6
        ),
        "benchmark_ending_nav": _round(benchmark_nav, 6),
        "benchmark_cumulative_return_pct": _round(
            (benchmark_nav / initial_capital - 1.0) * 100.0, 6
        ),
        "cumulative_return_difference_pct": _round(
            (nav - benchmark_nav) / initial_capital * 100.0, 6
        ),
        "relative_nav_excess_pct": _round(
            (nav / benchmark_nav - 1.0) * 100.0, 6
        ),
        "maximum_drawdown_pct": _ledger_drawdown_pct(daily_rows),
        "total_fees": _round(total_fees, 2),
        "capacity_limited_leg_count": capacity_limited_leg_count,
        "lot_unavailable_leg_count": 0,
        "overlap_dates": sorted(set(overlap_dates)),
        "daily": daily_rows,
    }


def _build_daily_ledger(case_rows, benchmark, parameters, strategy_id, mode):
    if mode not in {"standardized", "actual_lots"}:
        raise ValueError("ledger mode must be standardized or actual_lots")
    if mode == "standardized":
        return _build_standardized_daily_ledger(
            case_rows, benchmark, parameters, strategy_id
        )
    initial_capital = float(parameters["account_capital"])
    cash = initial_capital
    positions = []
    entries_by_date = {}
    for case in case_rows:
        entries_by_date.setdefault(case["entry_date"], []).append(case)
    benchmark_rows, benchmark_daily = _benchmark_daily_maps(benchmark)
    benchmark_dates = [str(row["date"]) for row in benchmark_rows]
    benchmark_nav = initial_capital
    if case_rows:
        min_entry_date = min(str(case["entry_date"]) for case in case_rows)
        max_exit_date = max(str(case["exit_date"]) for case in case_rows)
        event_dates = [
            date for date in benchmark_dates if min_entry_date <= date <= max_exit_date
        ]
    else:
        event_dates = []
    daily_rows = []
    total_fees = 0.0
    capacity_limited_leg_count = 0
    lot_unavailable_leg_count = 0
    overlap_dates = []

    for trade_date in event_dates:
        starting_nav = cash + sum(
            float(position["shares"]) * float(position["last_mark_price"])
            for position in positions
        )
        starting_benchmark_nav = benchmark_nav
        starting_nominal_x = sum(float(position["nominal_x"]) for position in positions)
        peak_nominal_x = starting_nominal_x
        actions = []
        contributions = []
        executed_entry_count = 0

        for case in sorted(entries_by_date.get(trade_date, []), key=lambda row: row["case_id"]):
            strategy = case["strategies"][strategy_id]
            legs = sorted(
                (dict(leg) for leg in strategy.get("legs") or []),
                key=lambda leg: (str(leg["fill_time"]), float(leg["weight_x"])),
            )
            for leg_index, leg in enumerate(legs, start=1):
                requested_x = float(leg["weight_x"])
                occupied_x = sum(float(position["nominal_x"]) for position in positions)
                available_x = max(0.0, 2.0 - occupied_x)
                accepted_x = min(requested_x, available_x)
                action = {
                    "action": "buy",
                    "case_id": case["case_id"],
                    "security_code": case["security_code"],
                    "security_name": case["security_name"],
                    "leg_index": leg_index,
                    "fill_time": str(leg["fill_time"]),
                    "requested_x": _round(requested_x, 3),
                    "available_x_before": _round(available_x, 3),
                }
                if accepted_x <= 1e-9:
                    action.update(
                        status="not_executed",
                        executed_x=0.0,
                        reason="旧仓仍占满账户容量，早盘不新增",
                    )
                    capacity_limited_leg_count += 1
                    actions.append(action)
                    continue
                if accepted_x + 1e-9 < requested_x:
                    capacity_limited_leg_count += 1

                market = _market_for_code(case["security_code"])
                fill = _actual_lot_fill(
                    price=leg["fill_price"],
                    target_gross=starting_nav * 0.5 * accepted_x,
                    minimum_gross=starting_nav * 0.4 * accepted_x,
                    maximum_gross=starting_nav * 0.6 * accepted_x,
                    cash=cash,
                    market=market,
                    parameters=parameters,
                )
                if not fill:
                    unavailable_reason = _actual_lot_unavailable_reason(
                        price=leg["fill_price"],
                        minimum_gross=starting_nav * 0.4 * accepted_x,
                        maximum_gross=starting_nav * 0.6 * accepted_x,
                        cash=cash,
                        market=market,
                        parameters=parameters,
                    )
                    action.update(
                        status="not_executed",
                        executed_x=0.0,
                        reason=unavailable_reason,
                    )
                    lot_unavailable_leg_count += 1
                    actions.append(action)
                    continue

                benchmark_fill_price = _benchmark_fill_price(
                    benchmark, trade_date, str(leg["fill_time"])
                )
                cash -= float(fill["gross"]) + float(fill["fee"])
                position = {
                    "case": case,
                    "case_id": case["case_id"],
                    "security_code": case["security_code"],
                    "security_name": case["security_name"],
                    "leg_index": leg_index,
                    "entry_date": trade_date,
                    "exit_date": case["exit_date"],
                    "fill_time": str(leg["fill_time"]),
                    "nominal_x": accepted_x,
                    "shares": float(fill["shares"]),
                    "buy_gross": float(fill["gross"]),
                    "pending_buy_fee": float(fill["fee"]),
                    "last_mark_price": float(leg["fill_price"]),
                    "last_benchmark_price": benchmark_fill_price,
                }
                positions.append(position)
                executed_entry_count += 1
                peak_nominal_x = max(
                    peak_nominal_x,
                    sum(float(item["nominal_x"]) for item in positions),
                )
                action.update(
                    status=(
                        "capacity_clipped"
                        if accepted_x + 1e-9 < requested_x
                        else "executed"
                    ),
                    executed_x=_round(accepted_x, 3),
                    shares=_round(fill["shares"], 6),
                    gross=_round(fill["gross"], 2),
                    fee=_round(fill["fee"], 2),
                    account_weight_pct=_round(
                        float(fill["gross"]) / starting_nav * 100.0, 6
                    ),
                    reason=(
                        "账户只剩部分容量，按剩余容量执行"
                        if accepted_x + 1e-9 < requested_x
                        else "按计划容量执行"
                    ),
                )
                actions.append(action)

        if starting_nominal_x > 1e-9 and executed_entry_count:
            overlap_dates.append(trade_date)

        exiting = [position for position in positions if position["exit_date"] == trade_date]
        exiting_case_ids = sorted({position["case_id"] for position in exiting})
        for case_id in exiting_case_ids:
            group = [position for position in exiting if position["case_id"] == case_id]
            case = group[0]["case"]
            exit_price = float(case["primary_exit"]["price"])
            sale_gross = sum(float(position["shares"]) * exit_price for position in group)
            sale_fee = _trade_fees(
                sale_gross,
                side="sell",
                market=_market_for_code(case["security_code"]),
                commission_rate=parameters["commission_rate"],
                minimum_commission=parameters["minimum_commission"],
                stamp_tax_rate=parameters["stamp_tax_rate"],
                transfer_fee_rate=parameters["transfer_fee_rate"],
            )
            cash += sale_gross - sale_fee
            benchmark_exit_price = _benchmark_tail_window_exit_price(
                benchmark["minute_days"][trade_date]
            )
            for position in group:
                position_sale_gross = float(position["shares"]) * exit_price
                allocated_sale_fee = (
                    sale_fee * position_sale_gross / sale_gross if sale_gross else 0.0
                )
                start_price = float(position["last_mark_price"])
                account_weight = (
                    float(position["shares"]) * start_price / starting_nav
                )
                price_pnl = float(position["shares"]) * (exit_price - start_price)
                fees = float(position["pending_buy_fee"]) + allocated_sale_fee
                account_pnl = price_pnl - fees
                benchmark_return = (
                    benchmark_exit_price / float(position["last_benchmark_price"])
                    - 1.0
                )
                contributions.append(
                    {
                        "case_id": position["case_id"],
                        "security_code": position["security_code"],
                        "security_name": position["security_name"],
                        "role": "旧仓尾盘退出",
                        "nominal_x": _round(position["nominal_x"], 3),
                        "account_weight_pct": _round(account_weight * 100.0, 6),
                        "start_price": _round(start_price, 4),
                        "end_price": _round(exit_price, 4),
                        "price_return_pct": _round(
                            (exit_price / start_price - 1.0) * 100.0, 6
                        ),
                        "fees": _round(fees, 2),
                        "account_pnl": _round(account_pnl, 6),
                        "account_contribution_pct": _round(
                            account_pnl / starting_nav * 100.0, 6
                        ),
                        "benchmark_start_price": _round(
                            position["last_benchmark_price"], 4
                        ),
                        "benchmark_end_price": _round(benchmark_exit_price, 4),
                        "benchmark_price_return_pct": _round(
                            benchmark_return * 100.0, 6
                        ),
                        "benchmark_contribution_pct": _round(
                            account_weight * benchmark_return * 100.0, 6
                        ),
                    }
                )
                position["pending_buy_fee"] = 0.0
            actions.append(
                {
                    "action": "sell",
                    "case_id": case_id,
                    "security_code": case["security_code"],
                    "security_name": case["security_name"],
                    "status": "executed",
                    "fill_time": "14:30-14:55",
                    "shares": _round(sum(position["shares"] for position in group), 6),
                    "gross": _round(sale_gross, 2),
                    "fee": _round(sale_fee, 2),
                }
            )
        if exiting:
            exiting_ids = {id(position) for position in exiting}
            positions = [position for position in positions if id(position) not in exiting_ids]

        for position in positions:
            case = position["case"]
            case_daily = _daily_by_date(case)
            if trade_date == position["entry_date"]:
                end_price = float(case["sensitivity_prices"]["entry_day_close"])
                role = "新仓入场至收盘"
            else:
                if trade_date not in case_daily:
                    raise ValueError(
                        f"{position['case_id']} lacks daily mark for {trade_date}"
                    )
                end_price = float(case_daily[trade_date]["close"])
                role = "持仓日收盘标记"
            benchmark_end_price = float(benchmark_daily[trade_date]["close"])
            start_price = float(position["last_mark_price"])
            account_weight = float(position["shares"]) * start_price / starting_nav
            fees = float(position["pending_buy_fee"])
            account_pnl = (
                float(position["shares"]) * (end_price - start_price) - fees
            )
            benchmark_return = (
                benchmark_end_price / float(position["last_benchmark_price"]) - 1.0
            )
            contributions.append(
                {
                    "case_id": position["case_id"],
                    "security_code": position["security_code"],
                    "security_name": position["security_name"],
                    "role": role,
                    "nominal_x": _round(position["nominal_x"], 3),
                    "account_weight_pct": _round(account_weight * 100.0, 6),
                    "start_price": _round(start_price, 4),
                    "end_price": _round(end_price, 4),
                    "price_return_pct": _round(
                        (end_price / start_price - 1.0) * 100.0, 6
                    ),
                    "fees": _round(fees, 2),
                    "account_pnl": _round(account_pnl, 6),
                    "account_contribution_pct": _round(
                        account_pnl / starting_nav * 100.0, 6
                    ),
                    "benchmark_start_price": _round(
                        position["last_benchmark_price"], 4
                    ),
                    "benchmark_end_price": _round(benchmark_end_price, 4),
                    "benchmark_price_return_pct": _round(
                        benchmark_return * 100.0, 6
                    ),
                    "benchmark_contribution_pct": _round(
                        account_weight * benchmark_return * 100.0, 6
                    ),
                }
            )
            position["pending_buy_fee"] = 0.0
            position["last_mark_price"] = end_price
            position["last_benchmark_price"] = benchmark_end_price

        ending_nav = cash + sum(
            float(position["shares"]) * float(position["last_mark_price"])
            for position in positions
        )
        contribution_pnl = sum(
            float(row["account_pnl"]) for row in contributions
        )
        if not math.isclose(
            ending_nav - starting_nav,
            contribution_pnl,
            abs_tol=0.02,
            rel_tol=0.0,
        ):
            raise ValueError(
                f"{strategy_id} {mode} {trade_date} contribution reconciliation failed"
            )
        account_return_pct = (ending_nav / starting_nav - 1.0) * 100.0
        benchmark_return_pct = sum(
            float(row["benchmark_contribution_pct"]) for row in contributions
        )
        benchmark_nav *= 1.0 + benchmark_return_pct / 100.0
        benchmark_index = benchmark_dates.index(trade_date)
        previous_benchmark_close = float(
            benchmark_rows[benchmark_index - 1]["close"]
        )
        benchmark_close = float(benchmark_daily[trade_date]["close"])
        fees_today = sum(float(row["fees"]) for row in contributions)
        total_fees += fees_today
        ending_nominal_x = sum(float(position["nominal_x"]) for position in positions)
        daily_rows.append(
            {
                "date": trade_date,
                "starting_nav": _round(starting_nav, 6),
                "ending_nav": _round(ending_nav, 6),
                "account_return_pct": _round(account_return_pct, 6),
                "cumulative_account_return_pct": _round(
                    (ending_nav / initial_capital - 1.0) * 100.0, 6
                ),
                "benchmark_starting_nav": _round(starting_benchmark_nav, 6),
                "benchmark_ending_nav": _round(benchmark_nav, 6),
                "benchmark_same_period_return_pct": _round(
                    benchmark_return_pct, 6
                ),
                "cumulative_benchmark_return_pct": _round(
                    (benchmark_nav / initial_capital - 1.0) * 100.0, 6
                ),
                "daily_excess_pct": _round(
                    account_return_pct - benchmark_return_pct, 6
                ),
                "daily_relative_excess_pct": _round(
                    (
                        (1.0 + account_return_pct / 100.0)
                        / (1.0 + benchmark_return_pct / 100.0)
                        - 1.0
                    )
                    * 100.0,
                    6,
                ),
                "cumulative_return_difference_pct": _round(
                    (ending_nav - benchmark_nav) / initial_capital * 100.0, 6
                ),
                "relative_nav_excess_pct": _round(
                    (ending_nav / benchmark_nav - 1.0) * 100.0, 6
                ),
                "shanghai_full_day_return_pct": _round(
                    (benchmark_close / previous_benchmark_close - 1.0) * 100.0,
                    6,
                ),
                "starting_nominal_x": _round(starting_nominal_x, 3),
                "peak_nominal_x": _round(peak_nominal_x, 3),
                "ending_nominal_x": _round(ending_nominal_x, 3),
                "fees": _round(fees_today, 2),
                "contributions": sorted(
                    contributions,
                    key=lambda row: (row["role"], row["case_id"]),
                ),
                "actions": actions,
            }
        )

    if positions:
        raise ValueError(f"{strategy_id} {mode} ledger ended with open positions")
    ending_nav = float(daily_rows[-1]["ending_nav"]) if daily_rows else initial_capital
    return {
        "mode": mode,
        "strategy_id": strategy_id,
        "strategy_label": STRATEGY_LABELS[strategy_id],
        "initial_capital": _round(initial_capital, 2),
        "ending_nav": _round(ending_nav, 6),
        "cumulative_return_pct": _round(
            (ending_nav / initial_capital - 1.0) * 100.0, 6
        ),
        "benchmark_ending_nav": _round(benchmark_nav, 6),
        "benchmark_cumulative_return_pct": _round(
            (benchmark_nav / initial_capital - 1.0) * 100.0, 6
        ),
        "cumulative_return_difference_pct": _round(
            (ending_nav - benchmark_nav) / initial_capital * 100.0, 6
        ),
        "relative_nav_excess_pct": _round(
            (ending_nav / benchmark_nav - 1.0) * 100.0, 6
        ),
        "maximum_drawdown_pct": _ledger_drawdown_pct(daily_rows),
        "total_fees": _round(total_fees, 2),
        "capacity_limited_leg_count": capacity_limited_leg_count,
        "lot_unavailable_leg_count": lot_unavailable_leg_count,
        "overlap_dates": sorted(set(overlap_dates)),
        "daily": daily_rows,
    }


def build_daily_ledgers(case_rows, benchmark, parameters):
    return {
        mode: OrderedDict(
            (
                strategy_id,
                _build_daily_ledger(
                    case_rows,
                    benchmark,
                    parameters,
                    strategy_id,
                    mode,
                ),
            )
            for strategy_id in STRATEGY_ORDER
        )
        for mode in ("standardized", "actual_lots")
    }


def _maximum_drawdown(returns_pct):
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns_pct:
        equity *= 1.0 + float(value) / 100.0
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    return max_drawdown * 100.0


def summarize_strategy_rows(case_rows):
    output = OrderedDict()
    for strategy_id in STRATEGY_ORDER:
        results = [row["strategies"][strategy_id] for row in case_rows]
        returns = [float(row["account_return_net_pct"]) for row in results]
        gross_returns = [
            float(row.get("account_return_gross_pct", row["account_return_net_pct"]))
            for row in results
        ]
        traded = [row for row in results if row["traded"]]
        traded_returns = [float(row["account_return_net_pct"]) for row in traded]
        actual_returns = [
            float(row["actual_return_net_pct"])
            for row in traded
            if int(row.get("actual_shares") or 0) > 0
        ]
        compounded = math.prod(1.0 + value / 100.0 for value in returns) - 1.0
        actual_compounded = (
            math.prod(
                1.0 + float(row.get("actual_return_net_pct") or 0.0) / 100.0
                for row in results
            )
            - 1.0
        )
        output[strategy_id] = {
            "strategy_label": STRATEGY_LABELS[strategy_id],
            "sample_count": len(results),
            "traded_count": len(traded),
            "not_participated_count": len(results) - len(traded),
            "win_rate_pct": _round(
                sum(value > 0 for value in traded_returns)
                / len(traded_returns)
                * 100.0,
                3,
            )
            if traded_returns
            else None,
            "opportunity_positive_rate_pct": _round(
                sum(value > 0 for value in returns) / len(returns) * 100.0, 3
            )
            if returns
            else None,
            "mean_account_return_net_pct": _round(statistics.fmean(returns), 6)
            if returns
            else None,
            "mean_account_return_gross_pct": _round(
                statistics.fmean(gross_returns), 6
            )
            if gross_returns
            else None,
            "mean_fee_drag_pct": _round(
                statistics.fmean(gross_returns) - statistics.fmean(returns), 6
            )
            if returns
            else None,
            "median_account_return_net_pct": _round(statistics.median(returns), 6)
            if returns
            else None,
            "independent_compound_return_pct": _round(compounded * 100.0, 6)
            if returns
            else None,
            "path_max_drawdown_pct": _round(_maximum_drawdown(returns), 6)
            if returns
            else None,
            "best_case_net_pct": _round(max(returns), 6) if returns else None,
            "worst_case_net_pct": _round(min(returns), 6) if returns else None,
            "mean_traded_mfe_price_pct": _round(
                statistics.fmean(row["mfe_price_pct"] for row in traded), 6
            )
            if traded
            else None,
            "mean_traded_mae_price_pct": _round(
                statistics.fmean(row["mae_price_pct"] for row in traded), 6
            )
            if traded
            else None,
            "actual_lot_trade_count": len(actual_returns),
            "mean_actual_lot_return_net_pct": _round(
                statistics.fmean(actual_returns), 6
            )
            if actual_returns
            else None,
            "mean_actual_account_return_net_pct": _round(
                statistics.fmean(
                    float(row.get("actual_return_net_pct") or 0.0) for row in results
                ),
                6,
            )
            if results
            else None,
            "actual_lot_independent_compound_return_pct": _round(
                actual_compounded * 100.0, 6
            )
            if results
            else None,
            "traded_mean_net_pct": _round(statistics.fmean(traded_returns), 6)
            if traded_returns
            else None,
        }
    return output


_summarize_strategy_rows = summarize_strategy_rows


def _scenario_summary(case_rows, *, field, value):
    selected = [row for row in case_rows if row["features"].get(field) == value]
    return {
        "field": field,
        "value": value,
        "case_count": len(selected),
        "strategies": summarize_strategy_rows(selected),
    }


def _valid_scenario_combination(opening_gap_class, morning_path):
    return morning_path in VALID_MORNING_PATHS_BY_OPENING[opening_gap_class]


def _build_conclusion(case_rows, summaries, daily_ledgers=None):
    auction = summaries["auction_1x"]
    qualified = summaries["qualified_b1_1x"]
    formal = summaries["formal_plan_b1_b2"]
    auction_full = summaries["auction_full_plan"]
    split = summaries["split_1x_confirm"]
    same_1x_diff = (
        qualified["mean_account_return_net_pct"] - auction["mean_account_return_net_pct"]
    )
    plan_diff = (
        formal["mean_account_return_net_pct"]
        - auction_full["mean_account_return_net_pct"]
    )
    auction_better = 0
    qualified_better = 0
    equal = 0
    for case in case_rows:
        left = case["strategies"]["auction_1x"]["account_return_net_pct"]
        right = case["strategies"]["qualified_b1_1x"]["account_return_net_pct"]
        if left > right + 1e-9:
            auction_better += 1
        elif right > left + 1e-9:
            qualified_better += 1
        else:
            equal += 1
    b2_cases = [
        case
        for case in case_rows
        if case["strategies"]["formal_plan_b1_b2"]["held_x"] > 1.0
    ]
    b2_case_results = [
        {
            "case_id": case["case_id"],
            "security_name": case["security_name"],
            "formal_plan_net_pct": case["strategies"]["formal_plan_b1_b2"][
                "account_return_net_pct"
            ],
            "b1_only_net_pct": case["strategies"]["qualified_b1_1x"][
                "account_return_net_pct"
            ],
            "incremental_account_return_pct": _round(
                case["strategies"]["formal_plan_b1_b2"]["account_return_net_pct"]
                - case["strategies"]["qualified_b1_1x"]["account_return_net_pct"],
                6,
            ),
        }
        for case in b2_cases
    ]
    if abs(same_1x_diff) < 0.1:
        verdict = "同1x入场差异很小，当前样本不足以偏向任一方式"
    elif same_1x_diff > 0:
        verdict = "同1x比较中，等待价格条件的初步结果更好，但仍需扩大前瞻样本"
    else:
        verdict = "同1x比较中，开盘价代理的初步结果更好，B1等待规则尚未证明优势"
    conclusion = {
        "verdict": verdict,
        "same_1x_mean_net_difference_pct": _round(same_1x_diff, 6),
        "formal_vs_auction_full_mean_net_difference_pct": _round(plan_diff, 6),
        "auction_1x_better_case_count": auction_better,
        "qualified_b1_better_case_count": qualified_better,
        "equal_case_count": equal,
        "qualified_b1_path_drawdown_reduction_pct": _round(
            qualified["path_max_drawdown_pct"] - auction["path_max_drawdown_pct"],
            6,
        ),
        "qualified_b1_worst_loss_reduction_pct": _round(
            qualified["worst_case_net_pct"] - auction["worst_case_net_pct"],
            6,
        ),
        "formal_plan_path_drawdown_reduction_pct": _round(
            formal["path_max_drawdown_pct"] - auction_full["path_max_drawdown_pct"],
            6,
        ),
        "formal_plan_worst_loss_reduction_pct": _round(
            formal["worst_case_net_pct"] - auction_full["worst_case_net_pct"],
            6,
        ),
        "split_1x_mean_net_difference_pct": _round(
            split["mean_account_return_net_pct"] - auction["mean_account_return_net_pct"],
            6,
        ),
        "split_1x_path_drawdown_reduction_pct": _round(
            split["path_max_drawdown_pct"] - auction["path_max_drawdown_pct"],
            6,
        ),
        "formal_b2_executed_case_count": len(b2_cases),
        "formal_b2_case_results": b2_case_results,
        "interpretation": (
            "这是14笔历史重放的初步证据，不是长期有效证明；报告文件冻结时间、"
            "板块分钟同步和真实竞价成交均未被完整恢复。"
        ),
    }
    standardized_ledgers = (daily_ledgers or {}).get("standardized") or {}
    actual_ledgers = (daily_ledgers or {}).get("actual_lots") or {}
    account_auction = standardized_ledgers.get("auction_1x") or {}
    account_qualified = standardized_ledgers.get("qualified_b1_1x") or {}
    account_formal = standardized_ledgers.get("formal_plan_b1_b2") or {}
    if account_auction and account_qualified:
        return_difference = (
            float(account_qualified["cumulative_return_pct"])
            - float(account_auction["cumulative_return_pct"])
        )
        drawdown_improvement = (
            float(account_qualified["maximum_drawdown_pct"])
            - float(account_auction["maximum_drawdown_pct"])
        )
        if abs(return_difference) <= 0.1 and drawdown_improvement > 0.1:
            account_verdict = (
                "逐日账户收益基本打平；等待B1用明显更小的回撤取得相近收益"
            )
        elif return_difference > 0:
            account_verdict = "逐日账户中等待B1收益更高，但样本仍不足"
        else:
            account_verdict = "逐日账户中开盘1x收益更高，但样本仍不足"
        conclusion["daily_account"] = {
            "verdict": account_verdict,
            "auction_1x_cumulative_return_pct": account_auction[
                "cumulative_return_pct"
            ],
            "qualified_b1_cumulative_return_pct": account_qualified[
                "cumulative_return_pct"
            ],
            "qualified_minus_auction_return_pct": _round(
                return_difference, 6
            ),
            "auction_1x_maximum_drawdown_pct": account_auction[
                "maximum_drawdown_pct"
            ],
            "qualified_b1_maximum_drawdown_pct": account_qualified[
                "maximum_drawdown_pct"
            ],
            "qualified_drawdown_improvement_pct": _round(
                drawdown_improvement, 6
            ),
            "standardized_formal_matches_qualified_after_capacity": bool(
                account_formal
                and math.isclose(
                    float(account_formal["cumulative_return_pct"]),
                    float(account_qualified["cumulative_return_pct"]),
                    abs_tol=1e-9,
                    rel_tol=0.0,
                )
            ),
        }
        conclusion["verdict"] = account_verdict
    if actual_ledgers:
        conclusion["actual_lot_account"] = {
            strategy_id: {
                "cumulative_return_pct": row["cumulative_return_pct"],
                "lot_unavailable_leg_count": row["lot_unavailable_leg_count"],
                "capacity_limited_leg_count": row["capacity_limited_leg_count"],
            }
            for strategy_id, row in actual_ledgers.items()
        }
    return conclusion


def validate_fixture(fixture):
    if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise ValueError(f"fixture schema must be {FIXTURE_SCHEMA_VERSION}")
    if fixture.get("as_of_date") != AS_OF_DATE:
        raise ValueError(f"fixture as_of_date must be {AS_OF_DATE}")
    fixture_source = fixture.get("source") or {}
    if fixture_source.get("query_date") != fixture.get("as_of_date"):
        raise ValueError("fixture source query_date must match as_of_date")
    discovered_coverage = _discover_coverage()
    if fixture.get("coverage") != discovered_coverage:
        raise ValueError("fixture coverage differs from current report coverage")
    cases = fixture.get("cases") or []
    if len(cases) != 14:
        raise ValueError("fixture must contain 14 positive decision cases")
    if sum(case.get("source_format") == "standardized" for case in cases) != 12:
        raise ValueError("fixture must contain 12 standardized cases")
    expected_cases = {case["case_id"]: case for case in DECISION_CASES}
    observed_case_ids = [str(case.get("case_id") or "") for case in cases]
    if len(set(observed_case_ids)) != len(observed_case_ids):
        raise ValueError("fixture case_id values must be unique")
    if set(observed_case_ids) != set(expected_cases):
        raise ValueError("fixture cases must match the frozen decision list")
    for case in cases:
        expected = expected_cases[case["case_id"]]
        for field in (
            "report_date",
            "source_format",
            "security_code",
            "security_name",
            "planned_position_x",
            "evidence_labels",
        ):
            if case.get(field) != expected[field]:
                raise ValueError(f"{case['case_id']} {field} differs from decision list")
        source = case.get("source") or {}
        for field in (
            "provider",
            "server_name",
            "host",
            "port",
            "source_uri",
            "query_date",
            "bar_time_semantics",
        ):
            if source.get(field) != fixture_source.get(field):
                raise ValueError(f"{case['case_id']} source {field} mismatch")
        if source.get("query_date") != fixture.get("as_of_date"):
            raise ValueError(f"{case['case_id']} source query_date mismatch")
        if source.get("source_dates") != [case["entry_date"], case["exit_date"]]:
            raise ValueError(f"{case['case_id']} source_dates mismatch")
        if source.get("bar_time_semantics") != "interval_end":
            raise ValueError(f"{case['case_id']} bar_time_semantics mismatch")
        if source["query_date"] < case["exit_date"]:
            raise ValueError(f"{case['case_id']} query_date precedes exit_date")
        report_source = case.get("report_source") or {}
        expected_report_path = (
            f"reports/{case['report_date']}_A股日报_执行摘要.md"
        )
        verified_report_source = _verify_report_evidence(expected)
        if report_source != verified_report_source:
            if report_source.get("path") != expected_report_path:
                raise ValueError(f"{case['case_id']} report source path mismatch")
            if report_source.get("evidence_labels") != expected["evidence_labels"]:
                raise ValueError(f"{case['case_id']} report evidence labels mismatch")
            raise ValueError(f"{case['case_id']} report source sha256 mismatch")
        validate_case_market_data(case)
        market_payload = {
            "daily_bars": case["daily_bars"],
            "minute_days": case["minute_days"],
            "source": case["source"],
        }
        if _canonical_hash(market_payload) != case.get("market_data_sha256"):
            raise ValueError(f"{case['case_id']} market_data_sha256 mismatch")
    target_dates = sorted(
        {
            str(case[field])
            for case in cases
            for field in ("entry_date", "exit_date")
        }
    )
    benchmark = fixture.get("benchmark") or {}
    benchmark_source = benchmark.get("source") or {}
    for field in (
        "provider",
        "server_name",
        "host",
        "port",
        "source_uri",
        "query_date",
        "bar_time_semantics",
    ):
        if benchmark_source.get(field) != fixture_source.get(field):
            raise ValueError(f"benchmark source {field} mismatch")
    benchmark_status = validate_benchmark_market_data(benchmark, target_dates)
    return {
        "status": "verified",
        "case_count": len(cases),
        "benchmark": benchmark_status,
    }


def build_backtest(
    fixture,
    *,
    account_capital=20000.0,
    commission_rate=0.00025,
    minimum_commission=5.0,
    stamp_tax_rate=0.0005,
    transfer_fee_rate=0.00001,
):
    validate_fixture(fixture)
    parameters = {
        "account_capital": float(account_capital),
        "one_x_budget": float(account_capital) / 2.0,
        "commission_rate": float(commission_rate),
        "minimum_commission": float(minimum_commission),
        "stamp_tax_rate": float(stamp_tax_rate),
        "transfer_fee_rate": float(transfer_fee_rate),
        "primary_exit": "T+2 14:30-14:55成交额加权均价",
        "signal_fill_policy": "已结束分钟形成信号，下一分钟开盘代理成交",
        "strategy_version": "frozen_20260721.v1",
    }
    case_rows = [_build_case_result(case, parameters) for case in fixture["cases"]]
    daily_ledgers = build_daily_ledgers(case_rows, fixture["benchmark"], parameters)
    standardized_rows = [row for row in case_rows if row["source_format"] == "standardized"]
    all_summary = summarize_strategy_rows(case_rows)
    standardized_summary = summarize_strategy_rows(standardized_rows)
    opening_summaries = [
        _scenario_summary(case_rows, field="opening_gap_class", value=value)
        for value in OPENING_GAP_ORDER
    ]
    path_summaries = [
        _scenario_summary(case_rows, field="morning_path", value=value)
        for value in MORNING_PATH_ORDER
    ]
    combination_summaries = []
    for opening in OPENING_GAP_ORDER:
        for path in MORNING_PATH_ORDER:
            if not _valid_scenario_combination(opening, path):
                continue
            selected = [
                row
                for row in case_rows
                if row["features"]["opening_gap_class"] == opening
                and row["features"]["morning_path"] == path
            ]
            combination_summaries.append(
                {
                    "opening_gap_class": opening,
                    "morning_path": path,
                    "case_count": len(selected),
                    "strategies": summarize_strategy_rows(selected),
                }
            )
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "as_of_date": AS_OF_DATE,
        "coverage": fixture["coverage"],
        "source": fixture["source"],
        "benchmark": {
            "code": fixture["benchmark"]["code"],
            "name": fixture["benchmark"]["name"],
            "market_number": fixture["benchmark"]["market_number"],
            "source": fixture["benchmark"]["source"],
            "market_data_sha256": fixture["benchmark"]["market_data_sha256"],
            "entry_proxy": "集合竞价用日线开盘；盘中信号用对应分钟开盘",
            "exit_proxy": "14:31-14:55分钟收盘价算术平均",
        },
        "parameters": parameters,
        "strategy_definitions": [
            {"strategy_id": strategy_id, "label": STRATEGY_LABELS[strategy_id]}
            for strategy_id in STRATEGY_ORDER
        ],
        "summaries": {
            "all": all_summary,
            "standardized": standardized_summary,
        },
        "daily_ledgers": daily_ledgers,
        "opening_gap_summaries": opening_summaries,
        "morning_path_summaries": path_summaries,
        "combination_summaries": combination_summaries,
        "scenario_summaries": opening_summaries + path_summaries,
        "cases": case_rows,
        "limitations": [
            "只有14笔历史重放，不能证明长期正期望；统一字段保护样本只有12笔。",
            "历史报告未进入可追溯的新增提交，无法证明在次日开盘前已经冻结。",
            "开盘价只作集合竞价成交代理，不等于个人真实撮合、排队或滑点。",
            "未核验停牌、涨跌停价格可成交性和封板排队；分钟开盘价存在也不证明该价能够成交。",
            "B1/B2只重放价格、VWAP、成交额和时间窗口；板块分钟同步与盘口大单事实缺失。",
            "逐笔独立复合只用于比较单个信号，账户累计以逐日账本为准。",
            "标准化账本以初始2万元为基线，1x固定使用1万元；2万元整手账本按全局现金、100股和40%-60%仓位容忍带执行。",
            "账户账本恢复了策略信号的资金占用，但没有恢复当时计划外交易、真实委托、滑点或外部出入金。",
            "上证同持有时段对照使用相同入场时刻与退出窗口；指数分钟成交额用于事实交叉核验，指数分钟成交量单位不直接参与价格计算，尾盘使用25根分钟收盘价均值。",
        ],
    }
    payload["missed_opportunity_summary"] = {
        "qualified_b1_not_participated_case_count": sum(
            case["missed_opportunity"]["qualified_b1_not_participated"]
            for case in case_rows
        ),
        "missed_positive_auction_outcome_count": sum(
            case["missed_opportunity"]["missed_positive_auction_outcome"]
            for case in case_rows
        ),
        "avoided_negative_auction_outcome_count": sum(
            case["missed_opportunity"]["avoided_negative_auction_outcome"]
            for case in case_rows
        ),
    }
    payload["conclusion"] = _build_conclusion(
        case_rows, all_summary, daily_ledgers
    )
    payload["payload_sha256"] = _canonical_hash(payload)
    return payload


def _fmt_pct(value):
    if value is None:
        return "样本不足"
    return f"{float(value):+.2f}%"


def _fmt_pp(value):
    if value is None:
        return "样本不足"
    return f"{float(value):+.2f}个百分点"


def _ledger_summary_table(lines, standardized, actual_lots):
    lines.extend(
        [
            "| 执行方式 | 标准化账户累计 | 同持有时段上证 | 累计收益差 | 标准化最大回撤 | 2万元整手累计 | 整手未成交腿/容量受限腿 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for strategy_id in STRATEGY_ORDER:
        normalized = standardized.get(strategy_id) or {}
        actual = actual_lots.get(strategy_id) or {}
        lines.append(
            "| {label} | {account} | {benchmark} | {difference} | {drawdown} | {actual_return} | {lot_unavailable}/{capacity} |".format(
                label=STRATEGY_LABELS[strategy_id],
                account=_fmt_pct(normalized.get("cumulative_return_pct")),
                benchmark=_fmt_pct(
                    normalized.get("benchmark_cumulative_return_pct")
                ),
                difference=_fmt_pp(
                    normalized.get("cumulative_return_difference_pct")
                ),
                drawdown=_fmt_pct(normalized.get("maximum_drawdown_pct")),
                actual_return=_fmt_pct(actual.get("cumulative_return_pct")),
                lot_unavailable=actual.get("lot_unavailable_leg_count", 0),
                capacity=actual.get("capacity_limited_leg_count", 0),
            )
        )


def _daily_contribution_text(row):
    parts = []
    role_labels = {
        "新仓入场至收盘": "入场",
        "旧仓尾盘退出": "退出",
        "持仓日收盘标记": "持有",
    }
    for item in row.get("contributions") or []:
        parts.append(
            "{name}{role}：{weight:.0f}%×{price_return}，费用后贡献{contribution}".format(
                name=item["security_name"],
                role=role_labels.get(item["role"], item["role"]),
                weight=float(item["account_weight_pct"]),
                price_return=_fmt_pct(item["price_return_pct"]),
                contribution=_fmt_pp(item["account_contribution_pct"]),
            )
        )
    return "；".join(parts) or "当日无持仓收益"


def _daily_ledger_table(lines, ledger):
    lines.extend(
        [
            "| 日期 | 持仓贡献 | 账户当日 | 上证同持有时段 | 当日收益差 | 累计账户 | 累计上证 | 累计收益差 | 上证全日 | 最高仓位 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in ledger.get("daily") or []:
        lines.append(
            "| {date} | {contributions} | {account} | {benchmark} | {daily_difference} | {cumulative_account} | {cumulative_benchmark} | {cumulative_difference} | {full_day} | {peak:.1f}x |".format(
                date=row["date"],
                contributions=_daily_contribution_text(row),
                account=_fmt_pct(row["account_return_pct"]),
                benchmark=_fmt_pct(row["benchmark_same_period_return_pct"]),
                daily_difference=_fmt_pp(row["daily_excess_pct"]),
                cumulative_account=_fmt_pct(
                    row["cumulative_account_return_pct"]
                ),
                cumulative_benchmark=_fmt_pct(
                    row["cumulative_benchmark_return_pct"]
                ),
                cumulative_difference=_fmt_pp(
                    row["cumulative_return_difference_pct"]
                ),
                full_day=_fmt_pct(row["shanghai_full_day_return_pct"]),
                peak=float(row["peak_nominal_x"]),
            )
        )


def _summary_table(lines, summary):
    lines.extend(
        [
            "| 执行方式 | 样本/参与/未参与 | 平均费用前收益 | 平均费用后收益 | 费用影响 | 独立样本复合 | 路径最大回撤 | 交易胜率 | 机会正收益率 | 平均MFE | 平均MAE | 最差单笔 | 2万元一手机会平均/至少一手成交笔数 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for strategy_id in STRATEGY_ORDER:
        row = summary.get(strategy_id) or {}
        lines.append(
            "| {label} | {sample}/{traded}/{not_participated} | {gross} | {mean} | {fee} | {compound} | {drawdown} | {win} | {opportunity} | {mfe} | {mae} | {worst} | {actual}/{lots} |".format(
                label=STRATEGY_LABELS[strategy_id],
                sample=row.get("sample_count", 0),
                traded=row.get("traded_count", 0),
                not_participated=row.get("not_participated_count", 0),
                gross=_fmt_pct(row.get("mean_account_return_gross_pct")),
                mean=_fmt_pct(row.get("mean_account_return_net_pct")),
                fee=_fmt_pp(row.get("mean_fee_drag_pct")),
                compound=_fmt_pct(row.get("independent_compound_return_pct")),
                drawdown=_fmt_pct(row.get("path_max_drawdown_pct")),
                win=_fmt_pct(row.get("win_rate_pct")),
                opportunity=_fmt_pct(row.get("opportunity_positive_rate_pct")),
                mfe=_fmt_pct(row.get("mean_traded_mfe_price_pct")),
                mae=_fmt_pct(row.get("mean_traded_mae_price_pct")),
                worst=_fmt_pct(row.get("worst_case_net_pct")),
                actual=_fmt_pct(row.get("mean_actual_account_return_net_pct")),
                lots=row.get("actual_lot_trade_count", 0),
            )
        )


def _fmt_status_snapshot(snapshot):
    return (
        f"{snapshot['time']}收盘 {snapshot['close']:.2f}，"
        f"相对VWAP {_fmt_pct(snapshot['vs_vwap_pct'])}，"
        f"相对昨收 {_fmt_pct(snapshot['vs_previous_close_pct'])}"
    )


def _fmt_execution_decision(decision):
    text = str(decision.get("reason") or "事实不足")
    if decision.get("signal_time") and decision.get("fill_time"):
        return (
            f"{text}（信号 {decision['signal_time']}，"
            f"成交代理 {decision['fill_time']}）"
        )
    if decision.get("cancellation_time"):
        return f"{text}（{decision['cancellation_time']}停止检查）"
    return text


def _missed_outcome_text(case):
    missed = case["missed_opportunity"]
    if not missed["qualified_b1_not_participated"]:
        return "B1已执行，不属于未参与样本"
    baseline = _fmt_pct(missed["auction_1x_net_pct"])
    if missed["missed_positive_auction_outcome"]:
        return f"未参与；开盘1x基线最终为 {baseline}，记为错过正收益"
    if missed["avoided_negative_auction_outcome"]:
        return f"未参与；开盘1x基线最终为 {baseline}，记为避开负收益"
    return f"未参与；开盘1x基线最终为 {baseline}"


def _scenario_action_text(opening_gap_class, morning_path):
    if opening_gap_class == "大幅高开":
        return "开盘偏离超过5%，本轮固定规则不取得B1；开盘1x只作对照，错过后不在10:10外追入"
    if morning_path == "高开延续":
        return "09:35仍在开盘、昨收和VWAP上方才于09:36执行B1；B2仍等09:50后突破开盘高点且量额不减"
    if morning_path == "高开回落":
        return "不把高开当资格；跌回开盘和VWAP下方取消B1，已有开盘仓只承担对照风险"
    if morning_path == "低开修复":
        return "不在低开时摊便宜；09:50后连续3分钟站上VWAP、开盘和T0 MA5，下一分钟执行B1"
    if morning_path == "低开延续下行":
        return "不执行B1/B2；等待规则的价值是保留现金，不用更低价格证明原计划"
    if morning_path == "平开走强":
        return "优先检查09:35主动进攻；未通过则等09:50后连续承接，B2只在进一步突破后出现"
    if morning_path == "平开走弱":
        return "取消B1/B2；开盘1x会完整承受走弱，是等待规则需要保护的样本"
    return "只在固定窗口按同一条件检查；信号互相冲突则不执行，10:10后不新增"


def render_markdown(payload):
    coverage = payload.get("coverage") or {}
    conclusion = payload.get("conclusion") or {}
    parameters = payload.get("parameters") or {}
    all_summary = (payload.get("summaries") or {}).get("all", {})
    daily_ledgers = payload.get("daily_ledgers") or {}
    standardized_ledgers = daily_ledgers.get("standardized") or {}
    actual_lot_ledgers = daily_ledgers.get("actual_lots") or {}
    auction_full_standardized = standardized_ledgers.get("auction_full_plan") or {}
    formal_standardized = standardized_ledgers.get("formal_plan_b1_b2") or {}
    split_actual_lot = actual_lot_ledgers.get("split_1x_confirm") or {}
    formal_actual_lot = actual_lot_ledgers.get("formal_plan_b1_b2") or {}
    auction_full_actual_lot = actual_lot_ledgers.get("auction_full_plan") or {}
    missed_opportunity = payload.get("missed_opportunity_summary") or {}
    completed_exit_dates = [
        str(case.get("exit_date"))
        for case in payload.get("cases") or []
        if case.get("exit_date")
    ]
    outcome_end = max(completed_exit_dates) if completed_exit_dates else "无完成样本"
    lines = [
        "# B1/B2 与集合竞价 1x 历史重放",
        "",
        f"> 结论：{conclusion.get('verdict', '待计算')}。",
        "",
        "## 先说清比较对象",
        "",
        "- 正式口径：B1 是 1x/50%，B2 确认后才把 2x 计划补到 100%。",
        "- `开盘0.5x+确认0.5x` 只是把同一个 1x 拆开的实验，不代表当前正式 B1/B2。",
        "- 集合竞价成交统一使用开盘价代理；所有执行方式共享 T+2 14:30-14:55 退出价。",
        f"- 账户基线 {float(parameters.get('account_capital') or 20000):,.0f} 元，1x目标 {float(parameters.get('one_x_budget') or 10000):,.0f} 元；整手结果按100股取最接近目标且单腿不超过60%风险带的可成交股数，不足一手记0股。",
        f"- 费用：佣金万{float(parameters.get('commission_rate') or 0.00025) * 10000:g}、单笔最低{float(parameters.get('minimum_commission') or 5):g}元；卖出印花税万{float(parameters.get('stamp_tax_rate') or 0.0005) * 10000:g}；沪市双边过户费万{float(parameters.get('transfer_fee_rate') or 0.00001) * 10000:g}。",
        f"- 信号与成交：{parameters.get('signal_fill_policy', '已结束分钟形成信号，下一分钟开盘代理成交')}；10:10后不新增。",
        "",
        "## B1/B2固定回放规则",
        "",
        "- B1第一路径：回放等09:35分钟结束；收盘同时不低于累计VWAP、昨收和开盘，距前五分钟高点回撤不超过2%，且开盘涨幅不超过5%，才把09:36开盘价记为1x成交代理。",
        "- B1第二路径：回放在09:50-10:10逐分钟检查；连续3分钟收盘不低于各自累计VWAP，当前收盘不低于开盘、T0 MA5和3分钟前收盘，且不高于昨收5%，才把下一分钟开盘价记为1x成交代理。",
        "- B2：只有2x计划且B1已经执行才进入回放检查；连续3分钟站在累计VWAP上方，当前收盘不低于昨收并突破09:31-09:35高点，最近5分钟成交额不低于此前5分钟，且不高于昨收5%，才把下一分钟开盘价记为第二个1x成交代理。",
        "- 取消：截至10:10仍不满足B1，回放记为不参与；B1未执行时B2不单独出现；B2未确认就维持1x，不把第二笔补成任务仓。",
        "",
        "## 样本覆盖",
        "",
        f"- 已有日报：{coverage.get('report_count', 0)} 个日期。",
        f"- 明确正向对象：{coverage.get('positive_case_count', 0)} 笔；正文以下按 {coverage.get('positive_case_count', 0)} 笔全样本展示。",
        f"- 统一字段保护样本：{coverage.get('standardized_case_count', 0)} 笔。",
        f"- 无新增对象：{coverage.get('no_action_count', 0)} 个日期，不伪造成交易。",
        "",
        f"## {coverage.get('window_start', '2026-06-01')} 至 {coverage.get('window_end', AS_OF_DATE)} 收益怎么读",
        "",
        f"- 日报覆盖到 {coverage.get('window_end', AS_OF_DATE)}；14笔正向对象中，最后一笔统一退出日是 {outcome_end}。",
        "- 本页先看逐日账户账本：每个1x固定为50%资金，同日不同股票按各自收益率分别乘50%后相加，再扣当天费用；价格差先除以该腿成交价，不能直接相加不同股票的价差。",
        "- 标准化账本回答策略本身的资金占用；真实2万元账户区间累计收益由2万元整手账本回答，按100股一手和现金约束计算。两者不是同一个账户假设，不能混读。",
        "- 独立样本复合只保留在后面的逐笔旁证，不再当作从6月至今的账户累计收益。",
        "",
        "### 账户累计结论",
        "",
    ]
    _ledger_summary_table(lines, standardized_ledgers, actual_lot_ledgers)
    account_conclusion = conclusion.get("daily_account") or {}
    if account_conclusion:
        lines.extend(
            [
                "",
                f"- 标准化账户判断：{account_conclusion.get('verdict', '样本不足')}。开盘1x累计 {_fmt_pct(account_conclusion.get('auction_1x_cumulative_return_pct'))}，等待B1累计 {_fmt_pct(account_conclusion.get('qualified_b1_cumulative_return_pct'))}；等待B1相对开盘1x为 {_fmt_pp(account_conclusion.get('qualified_minus_auction_return_pct'))}。",
                f"- 标准化最大回撤：开盘1x {_fmt_pct(account_conclusion.get('auction_1x_maximum_drawdown_pct'))}，等待B1 {_fmt_pct(account_conclusion.get('qualified_b1_maximum_drawdown_pct'))}；回撤改善 {_fmt_pp(account_conclusion.get('qualified_drawdown_improvement_pct'))}。",
                f"- 标准化账本中，正式B1/B2在账户容量约束后是否与等待B1相同：{'是' if account_conclusion.get('standardized_formal_matches_qualified_after_capacity') else '否'}；这不代表2万元整手账本相同。2万元整手累计分别为正式B1/B2 {_fmt_pct((actual_lot_ledgers.get('formal_plan_b1_b2') or {}).get('cumulative_return_pct'))}、等待B1 {_fmt_pct((actual_lot_ledgers.get('qualified_b1_1x') or {}).get('cumulative_return_pct'))}。",
            ]
        )
    lines.extend(
        [
            "",
            "### 本轮最优解边界与收益解释",
            "",
            f"- 这{coverage.get('positive_case_count', 0)}笔不能证明全局最优解。若只比较同样1x的标准化账户，开盘1x累计 {_fmt_pct(account_conclusion.get('auction_1x_cumulative_return_pct'))}，等待B1累计 {_fmt_pct(account_conclusion.get('qualified_b1_cumulative_return_pct'))}；等待B1最大回撤改善 {_fmt_pp(account_conclusion.get('qualified_drawdown_improvement_pct'))}。因此本轮证据更支持把等待B1当作风险控制，而不是收益增强器。",
            f"- 标准化账本中，正式B1/B2累计 {_fmt_pct(formal_standardized.get('cumulative_return_pct'))}、最大回撤 {_fmt_pct(formal_standardized.get('maximum_drawdown_pct'))}；开盘直接买完整计划累计 {_fmt_pct(auction_full_standardized.get('cumulative_return_pct'))}、最大回撤 {_fmt_pct(auction_full_standardized.get('maximum_drawdown_pct'))}。本轮标准化结果不支持集合竞价一次买满完整计划。",
            f"- 2万元整手账本的结论不同：正式B1/B2累计 {_fmt_pct(formal_actual_lot.get('cumulative_return_pct'))}，开盘直接买完整计划累计 {_fmt_pct(auction_full_actual_lot.get('cumulative_return_pct'))}；在这套实际可成交假设下，正式B1/B2反而更差，不能把标准化结论直接套到2万元账户。",
            f"- 累计收益没有像独立逐笔数字那样被放大，主要因为1x只占账户50%、重叠日总仓位不能超过100%、等待B1有 {missed_opportunity.get('qualified_b1_not_participated_case_count', 0)} 笔未参与、所有方式共用 {parameters.get('primary_exit', 'T+2退出')}，并且费用逐笔扣除。",
            "- 2万元整手账本还会被高价股一手不可买、40%-60%仓位容忍带和最低佣金改变参与样本。因此它出现负收益，不是标准化公式算错，而是小账户实际可执行集合已经不同。",
            f"- 拆分1x实验的整手累计为 {_fmt_pct(split_actual_lot.get('cumulative_return_pct'))}，但有 {split_actual_lot.get('lot_unavailable_leg_count', 0)} 条腿无法成交，样本选择发生明显变化，不能据此把它升级为最优方案。",
        ]
    )
    lines.extend(
        [
            "",
            "### 逐日账户账本：开盘1x",
            "",
            "下表中“账户当日”是所有活跃腿贡献之和；“上证同持有时段”使用对应入场时刻和14:31-14:55退出窗口；“上证全日”只作市场背景。",
            "",
        ]
    )
    _daily_ledger_table(lines, standardized_ledgers.get("auction_1x") or {})
    lines.extend(["", "### 逐日账户账本：等待B1 1x", ""])
    _daily_ledger_table(lines, standardized_ledgers.get("qualified_b1_1x") or {})
    lines.extend(
        [
            "",
            "### 逐笔独立旁证（不是账户累计）",
            "",
            "| 执行方式 | 14次机会平均费用后收益 | 独立样本复合 | 2万元一手机会平均/至少一手成交笔数 |",
            "|---|---:|---:|---:|",
        ]
    )
    for strategy_id in STRATEGY_ORDER:
        row = all_summary.get(strategy_id) or {}
        lines.append(
            "| {label} | {mean} | {compound} | {actual}/{lots} |".format(
                label=STRATEGY_LABELS[strategy_id],
                mean=_fmt_pct(row.get("mean_account_return_net_pct")),
                compound=_fmt_pct(row.get("independent_compound_return_pct")),
                actual=_fmt_pct(row.get("mean_actual_account_return_net_pct")),
                lots=row.get("actual_lot_trade_count", 0),
            )
        )
    lines.extend(
        [
        "",
        "## 14 笔全样本结果",
        "",
        ]
    )
    _summary_table(lines, all_summary)
    lines.extend(["", "## 12 笔统一字段保护样本", ""])
    _summary_table(lines, (payload.get("summaries") or {}).get("standardized", {}))
    lines.extend(
        [
            "",
            "## 配对结论",
            "",
            f"- 等待 B1 与开盘 1x 的平均净收益相差：{_fmt_pp(conclusion.get('same_1x_mean_net_difference_pct'))}。",
            f"- 等待 B1 的路径最大回撤相对开盘 1x 改善：{_fmt_pp(conclusion.get('qualified_b1_path_drawdown_reduction_pct'))}；最差单笔改善：{_fmt_pp(conclusion.get('qualified_b1_worst_loss_reduction_pct'))}。",
            f"- 正式 B1/B2 与开盘买完整计划的平均净收益相差：{_fmt_pp(conclusion.get('formal_vs_auction_full_mean_net_difference_pct'))}。",
            f"- 正式计划的路径最大回撤相对开盘买完整计划改善：{_fmt_pp(conclusion.get('formal_plan_path_drawdown_reduction_pct'))}；最差单笔改善：{_fmt_pp(conclusion.get('formal_plan_worst_loss_reduction_pct'))}。",
            f"- 拆分同一个 1x 的平均净收益相对开盘 1x：{_fmt_pp(conclusion.get('split_1x_mean_net_difference_pct'))}；路径最大回撤改善：{_fmt_pp(conclusion.get('split_1x_path_drawdown_reduction_pct'))}。",
            f"- 逐笔比较：开盘 1x 更好 {conclusion.get('auction_1x_better_case_count', 0)} 笔，等待 B1 更好 {conclusion.get('qualified_b1_better_case_count', 0)} 笔，相同 {conclusion.get('equal_case_count', 0)} 笔。",
            f"- 满仓计划中真正补出 B2 的只有 {conclusion.get('formal_b2_executed_case_count', 0)} 笔；这不足以证明 B2 的收益贡献。",
            f"- 等待B1未参与 {(payload.get('missed_opportunity_summary') or {}).get('qualified_b1_not_participated_case_count', 0)} 笔：其中错过开盘1x正收益 {(payload.get('missed_opportunity_summary') or {}).get('missed_positive_auction_outcome_count', 0)} 笔，避开开盘1x负收益 {(payload.get('missed_opportunity_summary') or {}).get('avoided_negative_auction_outcome_count', 0)} 笔。",
            "",
            "## 开盘位置",
            "",
            "| 开盘位置 | 样本数 | 开盘1x平均净收益 | 等待B1平均净收益 | 正式B1/B2平均净收益 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for group in payload.get("opening_gap_summaries") or []:
        summaries = group.get("strategies") or {}
        lines.append(
            "| {value} | {count} | {auction} | {qualified} | {formal} |".format(
                value=group["value"],
                count=group["case_count"],
                auction=_fmt_pct((summaries.get("auction_1x") or {}).get("mean_account_return_net_pct")),
                qualified=_fmt_pct((summaries.get("qualified_b1_1x") or {}).get("mean_account_return_net_pct")),
                formal=_fmt_pct((summaries.get("formal_plan_b1_b2") or {}).get("mean_account_return_net_pct")),
            )
        )
    lines.extend(
        [
            "",
            "## 10:10前分时路径",
            "",
            "| 路径 | 样本数 | 开盘1x平均净收益 | 等待B1平均净收益 | 正式B1/B2平均净收益 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for group in payload.get("morning_path_summaries") or []:
        summaries = group.get("strategies") or {}
        lines.append(
            "| {value} | {count} | {auction} | {qualified} | {formal} |".format(
                value=group["value"],
                count=group["case_count"],
                auction=_fmt_pct((summaries.get("auction_1x") or {}).get("mean_account_return_net_pct")),
                qualified=_fmt_pct((summaries.get("qualified_b1_1x") or {}).get("mean_account_return_net_pct")),
                formal=_fmt_pct((summaries.get("formal_plan_b1_b2") or {}).get("mean_account_return_net_pct")),
            )
        )
    lines.extend(
        [
            "",
            "## 开盘位置与分时走势的历史回放规则",
            "",
            "以下规则只用于解释这14笔历史重放，不直接转化为未来交易动作。",
            "",
            "| 开盘位置 | 10:10前路径 | 历史样本 | 开盘1x净收益/回撤/胜率 | 等待B1净收益/回撤/胜率 | 本轮固定回放规则 |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for group in payload.get("combination_summaries") or []:
        summaries = group.get("strategies") or {}
        auction = summaries.get("auction_1x") or {}
        qualified = summaries.get("qualified_b1_1x") or {}
        auction_result = "/".join(
            (
                _fmt_pct(auction.get("mean_account_return_net_pct")),
                _fmt_pct(auction.get("path_max_drawdown_pct")),
                _fmt_pct(auction.get("win_rate_pct")),
            )
        )
        qualified_result = "/".join(
            (
                _fmt_pct(qualified.get("mean_account_return_net_pct")),
                _fmt_pct(qualified.get("path_max_drawdown_pct")),
                _fmt_pct(qualified.get("win_rate_pct")),
            )
        )
        lines.append(
            f"| {group['opening_gap_class']} | {group['morning_path']} | {group['case_count']} | "
            f"{auction_result} | {qualified_result} | "
            f"{_scenario_action_text(group['opening_gap_class'], group['morning_path'])} |"
        )
    missing_opening = [
        group["value"]
        for group in payload.get("opening_gap_summaries") or []
        if not group.get("case_count")
    ]
    missing_paths = [
        group["value"]
        for group in payload.get("morning_path_summaries") or []
        if not group.get("case_count")
    ]
    if missing_opening or missing_paths:
        lines.extend(
            [
                "",
                f"> 样本不足：开盘位置缺少 {('、'.join(missing_opening) or '无')}；分时路径缺少 {('、'.join(missing_paths) or '无')}。这些组合只保留规则，不填写历史收益。",
            ]
        )
    b2_results = conclusion.get("formal_b2_case_results") or []
    lines.extend(["", "## B2实际触发", ""])
    if not b2_results:
        lines.append("本轮没有一笔满仓计划触发 B2，无法评价第二个 1x 的收益贡献。")
    else:
        lines.extend(
            [
                "| 样本 | B1单独净收益 | B1+B2净收益 | B2带来的账户收益变化 |",
                "|---|---:|---:|---:|",
            ]
        )
        for row in b2_results:
            lines.append(
                f"| {row['case_id']} {row['security_name']} | "
                f"{_fmt_pct(row['b1_only_net_pct'])} | "
                f"{_fmt_pct(row['formal_plan_net_pct'])} | "
                f"{_fmt_pp(row['incremental_account_return_pct'])} |"
            )
    lines.extend(["", "## 逐笔结果", ""])
    for case in payload.get("cases") or []:
        features = case["features"]
        lines.extend(
            [
                f"### {case['report_date']} {case['security_name']}({case['security_code']})",
                "",
                f"- 入场/退出：{case['entry_date']} / {case['primary_exit']['time']}，计划 {case['planned_position_x']}x。",
                f"- 开盘：{features['opening_gap_class']} {_fmt_pct(features['opening_gap_pct'])}；10:10前路径：{features['morning_path']}。",
                f"- 时间快照：{_fmt_status_snapshot(features['status_0935'])}；{_fmt_status_snapshot(features['status_1010'])}。",
                f"- B1：{_fmt_execution_decision(features['b1_decision'])}。",
                f"- 正式B2：{_fmt_execution_decision(features['formal_b2_decision'])}。",
                f"- 未参与结果：{_missed_outcome_text(case)}。",
                "",
                "| 执行方式 | 持仓x | 加权买价 | 主退出净收益 | 入场日收盘价格变化 | T+2开盘价格变化 | T+2收盘价格变化 | MFE | MAE | 实际股数/仓位 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for strategy_id in STRATEGY_ORDER:
            row = case["strategies"][strategy_id]
            sensitivity = row.get("sensitivity_price_return_pct") or {}
            lines.append(
                "| {label} | {held:.2f} | {entry} | {net} | {entry_close} | {exit_open} | {exit_close} | {mfe} | {mae} | {shares}/{position} |".format(
                    label=STRATEGY_LABELS[strategy_id],
                    held=float(row.get("held_x") or 0.0),
                    entry=f"{row['weighted_entry_price']:.2f}" if row.get("weighted_entry_price") else "未参与",
                    net=_fmt_pct(row.get("account_return_net_pct")),
                    entry_close=_fmt_pct(sensitivity.get("entry_day_close")),
                    exit_open=_fmt_pct(sensitivity.get("exit_day_open")),
                    exit_close=_fmt_pct(sensitivity.get("exit_day_close")),
                    mfe=_fmt_pct(row.get("mfe_price_pct")),
                    mae=_fmt_pct(row.get("mae_price_pct")),
                    shares=row.get("actual_shares", 0),
                    position=_fmt_pct(row.get("actual_position_pct")),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## 读法",
            "",
            "- 大幅或中幅高开且10:10前回落时，开盘买入承担完整回落；等待价格条件可能不参与，但也可能错过随后修复。",
            "- 平开或低开修复时，B1必须在既定窗口内完成承接确认；10:10后出现的上涨不回填为当时买点。",
            "- 回放中的B2成交代理价可能更高，但只有突破开盘高点、持续站上VWAP且成交额不减时才出现；没有确认就没有第二个1x。",
            "- 表中“独立样本复合”不是账户真实累计收益，因为历史信号日期存在资金占用重叠。",
            "",
            "## 限制",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload.get("limitations") or [])
    lines.extend(
        [
            "",
            "投资有风险，以上仅为历史重放与规则研究，不构成投资建议或操作指导。",
            "",
        ]
    )
    return "\n".join(lines)


def _normalize_tdx_daily(row):
    date = str(row.get("datetime") or "")[:10]
    return {
        "date": date,
        "open": _round(row.get("open"), 4),
        "high": _round(row.get("high"), 4),
        "low": _round(row.get("low"), 4),
        "close": _round(row.get("close"), 4),
        "volume": _round(row.get("vol"), 4),
        "amount": _round(row.get("amount"), 4),
    }


def _normalize_tdx_minute(row):
    return {
        "datetime": f"{str(row.get('datetime') or '')}:00",
        "open": _round(row.get("open"), 4),
        "high": _round(row.get("high"), 4),
        "low": _round(row.get("low"), 4),
        "close": _round(row.get("close"), 4),
        "volume": _round(row.get("vol"), 4),
        "amount": _round(row.get("amount"), 4),
    }


def _report_path(report_date):
    return ROOT / "reports" / f"{report_date}_A股日报_执行摘要.md"


def _verify_report_evidence(decision):
    path = _report_path(decision["report_date"])
    text = path.read_text(encoding="utf-8")
    for token in (
        decision["security_code"],
        decision["security_name"],
        *decision["evidence_labels"],
    ):
        if token not in text:
            raise ValueError(f"{path.name} is missing decision evidence: {token}")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256(path.read_bytes()),
        "evidence_labels": list(decision["evidence_labels"]),
    }


def _discover_coverage():
    pattern = re.compile(r"^(2026-(?:06|07)-\d{2})_A股日报_执行摘要\.md$")
    report_dates = []
    for path in sorted((ROOT / "reports").glob("2026-0[67]-*_A股日报_执行摘要.md")):
        match = pattern.match(path.name)
        if match and "2026-06-01" <= match.group(1) < AS_OF_DATE:
            report_dates.append(match.group(1))
    positive_dates = {decision["report_date"] for decision in DECISION_CASES}
    return {
        "window_start": "2026-06-01",
        "window_end": "2026-07-21",
        "report_dates": report_dates,
        "report_count": len(report_dates),
        "positive_case_count": len(DECISION_CASES),
        "standardized_case_count": sum(
            row["source_format"] == "standardized" for row in DECISION_CASES
        ),
        "positive_report_dates": sorted(positive_dates),
        "no_action_report_dates": sorted(set(report_dates) - positive_dates),
        "no_action_count": len(set(report_dates) - positive_dates),
    }


def _connect_tdx(hosts):
    from pytdx.hq import TdxHq_API

    errors = []
    for server_name, host, port in hosts:
        api = TdxHq_API(raise_exception=True, auto_retry=True)
        try:
            connected = api.connect(host, int(port), time_out=6)
            if connected:
                return api, {
                    "provider": "pytdx.TdxHq_API",
                    "server_name": server_name,
                    "host": host,
                    "port": int(port),
                    "source_uri": f"tdx://{host}:{port}",
                }
        except Exception as error:
            errors.append(f"{server_name}: {type(error).__name__}: {error}")
            try:
                api.disconnect()
            except Exception:
                pass
    raise ConnectionError("; ".join(errors) or "no TDX server connected")


def _fetch_daily(api, market, code):
    from pytdx.params import TDXParams

    rows = api.get_security_bars(TDXParams.KLINE_TYPE_DAILY, market, code, 0, 800) or []
    normalized = [_normalize_tdx_daily(row) for row in rows]
    return sorted((row for row in normalized if row["date"]), key=lambda row: row["date"])


def _fetch_index_daily(api, market, code):
    from pytdx.params import TDXParams

    rows = api.get_index_bars(
        TDXParams.KLINE_TYPE_DAILY, market, code, 0, 800
    ) or []
    normalized = [_normalize_tdx_daily(row) for row in rows]
    return sorted((row for row in normalized if row["date"]), key=lambda row: row["date"])


def _fetch_minute_days(api, market, code, target_dates):
    from pytdx.params import TDXParams

    target_dates = set(target_dates)
    earliest = min(target_dates)
    collected = {date: {} for date in target_dates}
    batch_meta = []
    for start in range(0, 16000, 800):
        rows = api.get_security_bars(
            TDXParams.KLINE_TYPE_1MIN, market, code, start, 800
        ) or []
        dates = [str(row.get("datetime") or "")[:10] for row in rows]
        batch_meta.append(
            {
                "start": start,
                "count": len(rows),
                "min_datetime": min(
                    (str(row.get("datetime") or "") for row in rows), default=""
                ),
                "max_datetime": max(
                    (str(row.get("datetime") or "") for row in rows), default=""
                ),
            }
        )
        for row in rows:
            date = str(row.get("datetime") or "")[:10]
            if date not in collected:
                continue
            normalized = _normalize_tdx_minute(row)
            collected[date][normalized["datetime"]] = normalized
        if target_dates.issubset(
            {date for date, values in collected.items() if len(values) >= 240}
        ):
            break
        if dates and min(dates) < earliest and not rows:
            break
    output = {
        date: sorted(values.values(), key=lambda row: row["datetime"])
        for date, values in collected.items()
    }
    missing = {date: len(rows) for date, rows in output.items() if len(rows) != 240}
    if missing:
        raise ValueError(f"{code} incomplete target minute dates: {missing}")
    return output, batch_meta


def _fetch_index_minute_days(api, market, code, target_dates):
    from pytdx.params import TDXParams

    target_dates = set(target_dates)
    collected = {date: {} for date in target_dates}
    batch_meta = []
    for start in range(0, 16000, 800):
        rows = api.get_index_bars(
            TDXParams.KLINE_TYPE_1MIN, market, code, start, 800
        ) or []
        batch_meta.append(
            {
                "start": start,
                "count": len(rows),
                "min_datetime": min(
                    (str(row.get("datetime") or "") for row in rows), default=""
                ),
                "max_datetime": max(
                    (str(row.get("datetime") or "") for row in rows), default=""
                ),
            }
        )
        for row in rows:
            date = str(row.get("datetime") or "")[:10]
            if date not in collected:
                continue
            normalized = _normalize_tdx_minute(row)
            collected[date][normalized["datetime"]] = normalized
        if target_dates.issubset(
            {date for date, values in collected.items() if len(values) >= 240}
        ):
            break
        if not rows:
            break
    output = {
        date: sorted(values.values(), key=lambda row: row["datetime"])
        for date, values in collected.items()
    }
    missing = {date: len(rows) for date, rows in output.items() if len(rows) != 240}
    if missing:
        raise ValueError(f"benchmark incomplete target minute dates: {missing}")
    return output, batch_meta


def collect_fixture(path=DEFAULT_FIXTURE_PATH, *, hosts=DEFAULT_TDX_HOSTS):
    coverage = _discover_coverage()
    if coverage["report_count"] != 35:
        raise ValueError(f"expected 35 report dates, got {coverage['report_count']}")
    report_sources = {
        decision["case_id"]: _verify_report_evidence(decision)
        for decision in DECISION_CASES
    }
    decisions_by_code = {}
    for decision in DECISION_CASES:
        decisions_by_code.setdefault(decision["security_code"], []).append(decision)
    api, source_identity = _connect_tdx(hosts)
    cases = []
    try:
        for code, decisions in decisions_by_code.items():
            market_number = 1 if _market_for_code(code) == "SH" else 0
            daily = _fetch_daily(api, market_number, code)
            daily_by_date = {row["date"]: row for row in daily}
            resolved = []
            target_minute_dates = set()
            for decision in decisions:
                trade_dates = [row["date"] for row in daily if row["date"] > decision["report_date"]]
                if len(trade_dates) < 2:
                    raise ValueError(f"{decision['case_id']} lacks T+1/T+2 daily bars")
                entry_date, exit_date = trade_dates[:2]
                target_minute_dates.update((entry_date, exit_date))
                resolved.append((decision, entry_date, exit_date))
            minute_days, batch_meta = _fetch_minute_days(
                api, market_number, code, target_minute_dates
            )
            for decision, entry_date, exit_date in resolved:
                report_index = next(
                    index for index, row in enumerate(daily) if row["date"] == decision["report_date"]
                )
                if report_index < 7:
                    raise ValueError(f"{decision['case_id']} lacks MA7 daily history")
                exit_index = next(index for index, row in enumerate(daily) if row["date"] == exit_date)
                daily_slice = daily[report_index - 7 : exit_index + 1]
                source = {
                    **source_identity,
                    "query_date": AS_OF_DATE,
                    "source_dates": [entry_date, exit_date],
                    "timezone": "Asia/Shanghai",
                    "bar_time_semantics": "interval_end",
                    "daily_protocol": f"get_security_bars(KLINE_TYPE_DAILY, market={market_number}, code={code}, start=0, count=800)",
                    "minute_protocol": f"get_security_bars(KLINE_TYPE_1MIN, market={market_number}, code={code}, start=N, count=800)",
                    "volume_unit": "shares",
                    "amount_unit": "CNY",
                    "batches": batch_meta,
                }
                case = {
                    **decision,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "report_source": report_sources[decision["case_id"]],
                    "daily_bars": daily_slice,
                    "minute_days": {
                        entry_date: minute_days[entry_date],
                        exit_date: minute_days[exit_date],
                    },
                    "source": source,
                }
                validate_case_market_data(case)
                case["market_data_sha256"] = _canonical_hash(
                    {
                        "daily_bars": case["daily_bars"],
                        "minute_days": case["minute_days"],
                        "source": case["source"],
                    }
                )
                cases.append(case)
        target_dates = sorted(
            {
                str(case[field])
                for case in cases
                for field in ("entry_date", "exit_date")
            }
        )
        benchmark_daily = _fetch_index_daily(
            api, BENCHMARK_MARKET, BENCHMARK_CODE
        )
        benchmark_daily_dates = [row["date"] for row in benchmark_daily]
        if min(target_dates) not in benchmark_daily_dates:
            raise ValueError("benchmark daily history does not reach first target date")
        first_target_index = benchmark_daily_dates.index(min(target_dates))
        if first_target_index <= 0:
            raise ValueError("benchmark lacks previous close before first target date")
        last_target_index = benchmark_daily_dates.index(max(target_dates))
        benchmark_daily_slice = benchmark_daily[
            first_target_index - 1 : last_target_index + 1
        ]
        benchmark_minutes, benchmark_batches = _fetch_index_minute_days(
            api, BENCHMARK_MARKET, BENCHMARK_CODE, target_dates
        )
        benchmark_source = {
            **source_identity,
            "query_date": AS_OF_DATE,
            "source_dates": target_dates,
            "timezone": "Asia/Shanghai",
            "bar_time_semantics": "interval_end",
            "daily_protocol": (
                "get_index_bars(KLINE_TYPE_DAILY, market=1, "
                "code=000001, start=0, count=800)"
            ),
            "minute_protocol": (
                "get_index_bars(KLINE_TYPE_1MIN, market=1, "
                "code=000001, start=N, count=800)"
            ),
            "price_projection": (
                "入场取对应分钟open；14:31-14:55退出取分钟close算术平均"
            ),
            "volume_unit_note": "指数分钟volume与日线单位不直接可比，仅保留原始字段，不参与价格代理",
            "batches": benchmark_batches,
        }
        benchmark = {
            "code": BENCHMARK_CODE,
            "name": BENCHMARK_NAME,
            "market_number": BENCHMARK_MARKET,
            "daily_bars": benchmark_daily_slice,
            "minute_days": benchmark_minutes,
            "source": benchmark_source,
        }
        benchmark["market_data_sha256"] = _canonical_hash(
            {
                "daily_bars": benchmark["daily_bars"],
                "minute_days": benchmark["minute_days"],
                "source": benchmark["source"],
            }
        )
        validate_benchmark_market_data(benchmark, target_dates)
    finally:
        api.disconnect()
    cases.sort(key=lambda row: (row["report_date"], row["security_code"]))
    fixture = {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "as_of_date": AS_OF_DATE,
        "coverage": coverage,
        "source": {
            **source_identity,
            "query_date": AS_OF_DATE,
            "bar_time_semantics": "interval_end",
            "collection_scope": "14个正式明日对象的T+1/T+2，不是全市场采集",
        },
        "benchmark": benchmark,
        "cases": cases,
    }
    validate_fixture(fixture)
    text = json.dumps(fixture, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    _atomic_write_text(path, text)
    return fixture


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="B1/B2 与集合竞价 1x 历史重放")
    parser.add_argument("--collect", action="store_true", help="连接通达信并刷新冻结事实")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--account-capital", type=float, default=20000.0)
    parser.add_argument("--commission-rate", type=float, default=0.00025)
    parser.add_argument("--minimum-commission", type=float, default=5.0)
    parser.add_argument("--stamp-tax-rate", type=float, default=0.0005)
    parser.add_argument("--transfer-fee-rate", type=float, default=0.00001)
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    if args.collect:
        fixture = collect_fixture(args.fixture)
        print(f"已冻结 {len(fixture['cases'])} 笔历史对象：{args.fixture}")
    else:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if not args.output_json and not args.output_md:
        if args.collect:
            return 0
        args.output_json = DEFAULT_OUTPUT_JSON
        args.output_md = DEFAULT_OUTPUT_MD
    payload = build_backtest(
        fixture,
        account_capital=args.account_capital,
        commission_rate=args.commission_rate,
        minimum_commission=args.minimum_commission,
        stamp_tax_rate=args.stamp_tax_rate,
        transfer_fee_rate=args.transfer_fee_rate,
    )
    if args.output_json:
        _atomic_write_text(
            args.output_json,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
        print(f"已写入回测 JSON：{args.output_json}")
    if args.output_md:
        _atomic_write_text(args.output_md, render_markdown(payload))
        print(f"已写入回测报告：{args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
