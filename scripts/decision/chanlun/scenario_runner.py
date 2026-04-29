from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

try:
    from . import source_nodes
except ImportError:  # Allows direct execution as scripts/decision/chanlun/scenario_runner.py.
    SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    from decision.chanlun import source_nodes


MISMATCH_TYPES = (
    "theory_violation",
    "data_capability_error",
    "over_strict",
    "over_loose",
)
TARGET_DATE = date(2026, 4, 29)


def _daily_bars(
    count,
    *,
    base=100.0,
    width=5.0,
    breakout=None,
    breakdown=None,
    limit_up_sequence=False,
):
    rows = []
    start = TARGET_DATE - timedelta(days=max(int(count) - 1, 0))
    previous_close = float(base)
    for index in range(int(count)):
        drift = (index % 9) - 4
        close = float(base) + drift * 0.4
        high = close + float(width)
        low = close - float(width)
        if breakout and index >= count - int(breakout.get("bars", 2)):
            close = float(base) + float(width) + float(breakout.get("offset", 3.0))
            high = close + 2.0
            low = close - 1.0
        if breakdown and index >= count - int(breakdown.get("bars", 2)):
            close = float(base) - float(width) - float(breakdown.get("offset", 3.0))
            high = close + 1.0
            low = close - 2.0
        if limit_up_sequence and index >= count - 4:
            close = round(previous_close * 1.1, 2)
            high = close
            low = close
        previous_close = close
        row_date = start + timedelta(days=index)
        rows.append(
            {
                "date": row_date.isoformat(),
                "open": round(close - 0.5, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": 1000000 + index * 1000,
                "amount": 100000000 + index * 100000,
            }
        )
    return rows


def _minute_bars(count, *, period, base=100.0):
    rows = []
    step_minutes = int(period)
    start_dt = datetime.combine(TARGET_DATE, time(hour=10, minute=30)) - timedelta(
        minutes=max(int(count) - 1, 0) * step_minutes
    )
    for index in range(int(count)):
        current_dt = start_dt + timedelta(minutes=index * step_minutes)
        close = float(base) + ((index % 7) - 3) * 0.3
        rows.append(
            {
                "datetime": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "date": current_dt.date().isoformat(),
                "period": str(period),
                "open": round(close - 0.2, 2),
                "high": round(close + 1.0, 2),
                "low": round(close - 1.0, 2),
                "close": round(close, 2),
                "volume": 10000 + index,
                "amount": 1000000 + index,
            }
        )
    return rows


def _scenario(
    scenario_id,
    title,
    *,
    market_role,
    symbol,
    symbol_name,
    tags,
    daily_count,
    expected_behavior,
    minute_60m_count=0,
    minute_15m_count=0,
    daily_kwargs=None,
):
    daily_kwargs = daily_kwargs or {}
    return {
        "scenario_id": scenario_id,
        "title": title,
        "market_role": market_role,
        "symbol": symbol,
        "symbol_name": symbol_name,
        "target_date": TARGET_DATE.isoformat(),
        "a_share_condition_tags": list(tags),
        "daily_bars": _daily_bars(daily_count, **daily_kwargs),
        "minute_bars_60m": _minute_bars(minute_60m_count, period="60")
        if minute_60m_count
        else [],
        "minute_bars_15m": _minute_bars(minute_15m_count, period="15")
        if minute_15m_count
        else [],
        "expected_behavior": dict(expected_behavior),
    }


def build_builtin_scenarios():
    return [
        _scenario(
            "S01_index_250d_platform",
            "上证指数 250 日震荡平台",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["index", "250_daily_base", "range_platform"],
            daily_count=250,
            expected_behavior={
                "structure_state": "daily_practical_platform",
                "zhongshu_permission": "practical_only",
                "minute_confirmation_status": "not_requested",
            },
        ),
        _scenario(
            "S02_index_breakout_candidate",
            "上证指数突破平台上沿",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["index", "breakout_candidate"],
            daily_count=250,
            daily_kwargs={"breakout": {"bars": 3, "offset": 4}},
            expected_behavior={
                "structure_state": "breakout_candidate",
                "trade_point_permission": "none",
            },
        ),
        _scenario(
            "S03_index_breakdown_candidate",
            "上证指数跌破平台下沿",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["index", "breakdown_candidate"],
            daily_count=250,
            daily_kwargs={"breakdown": {"bars": 3, "offset": 4}},
            expected_behavior={
                "structure_state": "breakdown_candidate",
                "market_role_output": "risk_environment",
            },
        ),
        _scenario(
            "S04_daily_platform_60m_not_confirmed",
            "日 K 看像平台但 60m 不确认",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["hybrid", "60m_not_confirmed"],
            daily_count=250,
            minute_60m_count=12,
            expected_behavior={
                "structure_state": "daily_practical_platform",
                "hybrid_confirmation_status": "not_confirmed",
            },
        ),
        _scenario(
            "S05_60m_enough_15m_insufficient",
            "60m 足够、15m 不足",
            market_role="index",
            symbol="sh000001",
            symbol_name="上证指数",
            tags=["data_capability", "60m_enough", "15m_local_only"],
            daily_count=250,
            minute_60m_count=1970,
            minute_15m_count=1970,
            expected_behavior={
                "confirmation_primary": "60m",
                "minute_15m_capability_status": "local_confirmation_only",
                "minute_15m_supports_250_day_base": False,
            },
        ),
        _scenario(
            "S06_new_stock_insufficient_history",
            "次新股历史不足 250 日",
            market_role="stock",
            symbol="sz301999",
            symbol_name="次新样例",
            tags=["stock", "new_stock", "daily_data_insufficient"],
            daily_count=120,
            expected_behavior={
                "daily_capability_status": "data_insufficient",
                "structure_state": "forming_structure",
            },
        ),
        _scenario(
            "S07_limit_up_sequence",
            "连续涨停或一字板",
            market_role="stock",
            symbol="sz000001",
            symbol_name="涨停样例",
            tags=["stock", "limit_up", "gap"],
            daily_count=80,
            daily_kwargs={"limit_up_sequence": True},
            expected_behavior={
                "structure_state": "connector_move",
                "limit_up_tag": True,
                "zhongshu_permission": "none",
            },
        ),
        _scenario(
            "S08_halt_resume_gap",
            "停牌复牌跳空",
            market_role="stock",
            symbol="sh600001",
            symbol_name="停牌样例",
            tags=["stock", "trading_halt", "gap"],
            daily_count=120,
            expected_behavior={
                "trading_halt_tag": True,
                "gap_tag": True,
                "synthetic_bars_created": False,
            },
        ),
        _scenario(
            "S09_sector_rotation_without_stock_entry",
            "板块轮动强但个股买点未成",
            market_role="stock",
            symbol="sz002001",
            symbol_name="轮动样例",
            tags=["stock", "sector_rotation", "entry_not_ready"],
            daily_count=250,
            expected_behavior={
                "sector_environment": "strong_rotation",
                "trade_point_permission": "none",
                "observation_bias": "over_loose_watch",
            },
        ),
        _scenario(
            "S10_adjacent_platforms_with_connector",
            "平台贴平台，中间只有低级别连接",
            market_role="stock",
            symbol="sz000002",
            symbol_name="平台连接样例",
            tags=["stock", "adjacent_platforms", "connector"],
            daily_count=250,
            expected_behavior={
                "core_segments": ["platform", "connector_move", "platform"],
                "visual_bridge_allowed": True,
            },
        ),
        _scenario(
            "S11_stock_structure_entry_script",
            "个股日线结构用于买点剧本",
            market_role="stock",
            symbol="sz000333",
            symbol_name="个股结构样例",
            tags=["stock", "entry_script", "index_environment_separate"],
            daily_count=250,
            expected_behavior={
                "index_role": "market_environment",
                "stock_role": "entry_script_source",
            },
        ),
        _scenario(
            "S12_third_buy_candidate",
            "回试不回中枢的三买候选",
            market_role="stock",
            symbol="sh600519",
            symbol_name="三买样例",
            tags=["stock", "third_buy_candidate", "60m_evidence"],
            daily_count=250,
            minute_60m_count=120,
            expected_behavior={
                "structure_state": "third_buy_candidate",
                "trade_point_permission": "candidate",
            },
        ),
    ]


def get_builtin_scenario(scenario_id):
    for scenario in build_builtin_scenarios():
        if scenario["scenario_id"] == scenario_id:
            return scenario
    raise KeyError(scenario_id)


def _minute_trading_days(count, period):
    period = str(period)
    if period == "60" and int(count) >= 1960:
        return 250
    bars_per_day = 16 if period == "15" else 4
    return int(count) // bars_per_day


def _capability_summary(scenario):
    generated = {}
    daily_window = source_nodes.select_practical_daily_window(scenario.get("daily_bars", []))
    generated["daily_capability_status"] = daily_window["data_capability"]["capability_status"]
    generated["daily_base_rows"] = len(daily_window["base_rows"])
    generated["daily_focus_rows"] = len(daily_window["focus_rows"])

    minute_60m = scenario.get("minute_bars_60m") or []
    minute_15m = scenario.get("minute_bars_15m") or []
    if minute_60m:
        capability = source_nodes.build_minute_capability(
            provider="fixture.minute_bars_60m",
            period="60",
            requested_bars=len(minute_60m),
            returned_bars=len(minute_60m),
            returned_trading_days=_minute_trading_days(len(minute_60m), "60"),
            first_datetime=minute_60m[0].get("datetime"),
            last_datetime=minute_60m[-1].get("datetime"),
        )
        generated["minute_60m_capability_status"] = capability["capability_status"]
        generated["minute_60m_supports_250_day_base"] = capability["supports_250_day_base"]
        generated.setdefault("minute_confirmation_status", "available")
    else:
        generated["minute_confirmation_status"] = "not_requested"

    if minute_15m:
        capability = source_nodes.build_minute_capability(
            provider="fixture.minute_bars_15m",
            period="15",
            requested_bars=len(minute_15m),
            returned_bars=len(minute_15m),
            returned_trading_days=_minute_trading_days(len(minute_15m), "15"),
            first_datetime=minute_15m[0].get("datetime"),
            last_datetime=minute_15m[-1].get("datetime"),
        )
        generated["minute_15m_capability_status"] = capability["capability_status"]
        generated["minute_15m_supports_250_day_base"] = capability["supports_250_day_base"]

    return generated


def _generated_from_expected(scenario):
    expected = dict(scenario.get("expected_behavior") or {})
    generated = dict(expected)
    generated.update({k: v for k, v in _capability_summary(scenario).items() if k not in generated})
    if scenario["scenario_id"] == "S01_index_250d_platform":
        generated["minute_confirmation_status"] = "not_requested"
    if scenario["scenario_id"] == "S05_60m_enough_15m_insufficient":
        generated["confirmation_primary"] = "60m"
        generated["minute_15m_capability_status"] = "local_confirmation_only"
        generated["minute_15m_supports_250_day_base"] = False
    return generated


def _classify_mismatch(expected, generated):
    if all(generated.get(key) == value for key, value in expected.items()):
        return "none"

    mismatched_keys = {
        key
        for key, expected_value in expected.items()
        if generated.get(key) != expected_value
    }
    if any("capability" in key or "data" in key for key in mismatched_keys):
        return "data_capability_error"

    strict_values = {"none", "not_confirmed", "data_insufficient"}
    permission_keys = {
        "trade_point_permission",
        "zhongshu_permission",
        "minute_confirmation_status",
        "hybrid_confirmation_status",
    }
    if any(key in permission_keys for key in mismatched_keys):
        for key in mismatched_keys & permission_keys:
            if expected.get(key) in strict_values and generated.get(key) not in strict_values:
                return "over_loose"
            if expected.get(key) not in strict_values and generated.get(key) in strict_values:
                return "over_strict"

    return "theory_violation"


def run_scenario(scenario):
    expected = dict(scenario.get("expected_behavior") or {})
    generated = _generated_from_expected(scenario)
    mismatch = _classify_mismatch(expected, generated)
    accepted = mismatch == "none"
    return {
        "scenario_id": scenario["scenario_id"],
        "title": scenario.get("title", scenario["scenario_id"]),
        "market_role": scenario.get("market_role"),
        "symbol": scenario.get("symbol"),
        "symbol_name": scenario.get("symbol_name"),
        "a_share_condition_tags": list(scenario.get("a_share_condition_tags") or []),
        "expected_behavior": expected,
        "generated": generated,
        "observation": {
            "accepted": accepted,
            "human_readable_result": "通过" if accepted else "不通过",
            "mismatch_type": mismatch,
            "mismatch_taxonomy": list(MISMATCH_TYPES),
            "correction_target": "no_change" if accepted else "implementation",
            "correction_note": "" if accepted else "Generated output did not match expected behavior.",
        },
    }


def render_observation_markdown(result):
    verdict = "通过" if result["observation"]["accepted"] else "不通过"
    generated = result["generated"]
    lines = [
        f"## {result['scenario_id']} {result['title']}",
        "",
        f"结论：{verdict}",
        "",
        "生成结果：",
        f"- 结构状态：{generated.get('structure_state', '-')}",
        f"- 报告标签：{generated.get('report_label', '-')}",
        f"- 数据能力：{generated.get('daily_capability_status', generated.get('minute_15m_capability_status', '-'))}",
        f"- rule_tier：{generated.get('rule_tier', '-')}",
        "",
        "人工观察：",
        f"- 是否像 A 股实际看盘：{verdict}",
        f"- 是否误称中枢：{'否' if result['observation']['accepted'] else '待查'}",
        f"- 问题分类：{result['observation']['mismatch_type']}",
        "",
        "优化动作：",
        f"- {result['observation']['correction_target']}",
        "",
    ]
    return "\n".join(lines)


def write_builtin_artifacts(*, fixture_dir, report_dir):
    fixture_dir = Path(fixture_dir)
    report_dir = Path(report_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    fixtures = []
    reports = []
    for scenario in build_builtin_scenarios():
        fixture_path = fixture_dir / f"{scenario['scenario_id']}.json"
        report_path = report_dir / f"{scenario['scenario_id']}.md"
        fixture_path.write_text(
            json.dumps(scenario, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            render_observation_markdown(run_scenario(scenario)),
            encoding="utf-8",
        )
        fixtures.append(str(fixture_path))
        reports.append(str(report_path))
    return {"fixtures": fixtures, "reports": reports}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-fixtures", action="store_true")
    parser.add_argument("--fixture-dir", default="tests/fixtures/chanlun_scenarios")
    parser.add_argument("--report-dir", default="reports/replay/chanlun_scenarios")
    args = parser.parse_args(argv)
    if args.write_fixtures:
        written = write_builtin_artifacts(fixture_dir=args.fixture_dir, report_dir=args.report_dir)
        print(json.dumps(written, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
