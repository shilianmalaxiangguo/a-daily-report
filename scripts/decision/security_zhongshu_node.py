from __future__ import annotations

import traceback
from typing import Any, Mapping, Sequence

PRACTICAL_SOURCE_ALGORITHM = "practical_daily_node_runtime; full_recursive_mode_deferred"


def strict_chanlun_policy_for_security(security_type: str = "stock") -> dict[str, str]:
    security_type = str(security_type or "stock")
    return {
        "source_algorithm": PRACTICAL_SOURCE_ALGORITHM,
        "default_mode": "practical_daily_mode",
        "daily_level_confirmation": "日线平台由日线走势类型重叠识别",
        "minute_confirmation": "not_requested",
        "full_recursive_mode": "deferred",
        "execution_reference": "分钟级别仅作执行与止损辅助，当前画布不请求分钟确认",
        "market_index_role": "上证指数决定市场参与条件",
        "stock_position_role": "个股自身结构决定单票仓位",
        "security_type": security_type,
    }


def _signal_texts(security_type: str) -> dict[str, str]:
    if security_type == "index":
        return {
            "breakout_status": "✅ 突破中枢",
            "breakout_signal_type": "大盘突破",
            "breakout_position_level": "三档进攻档（50%）",
            "breakout_action": "积极做多",
            "down_status": "⚠️ 跌破中枢",
            "down_signal_type": "跌破支撑",
            "down_position_level": "一档空仓档（0%）",
            "down_action": "清仓观望",
            "range_status": "➖ 中枢内震荡",
            "range_signal_type": "按个股信号操作",
            "range_position_level": "二档防守档（30%）",
            "range_action": "精选个股",
        }
    return {
        "breakout_status": "✅ 突破日线平台",
        "breakout_signal_type": "个股突破",
        "breakout_position_level": "个股结构进攻观察",
        "breakout_action": "按个股买点与风控执行",
        "down_status": "⚠️ 跌破日线平台",
        "down_signal_type": "个股跌破结构",
        "down_position_level": "个股结构防守观察",
        "down_action": "降低单票仓位或等待重新站回",
        "range_status": "➖ 日线平台内震荡",
        "range_signal_type": "个股结构内震荡",
        "range_position_level": "单票节奏观察",
        "range_action": "等待离开平台方向",
    }


def build_security_zhongshu_signal(
    current: Mapping[str, Any] | None,
    zhongshu_list: Sequence[Mapping[str, Any]],
    *,
    today_price: float,
    today_date: str,
    min_zhongshu_klines: int,
    security_type: str = "stock",
) -> dict[str, Any]:
    signal: dict[str, Any] = {}
    if not current:
        return signal

    texts = _signal_texts(security_type)
    zg = current["zg"]
    zd = current["zd"]
    comparison_high = float(current.get("high") or current.get("segment_high") or zg)
    comparison_low = float(current.get("low") or current.get("segment_low") or zd)
    is_current_forming = current.get("confirmation_status") == "forming"
    current_kline_count = int(current.get("kline_count") or 0)
    required_kline_count = int(current.get("required_kline_count") or min_zhongshu_klines)
    dist_to_zg = (today_price - comparison_high) / comparison_high
    dist_to_zd = (today_price - comparison_low) / comparison_low

    signal["zg"] = zg
    signal["zd"] = zd
    signal["range_high"] = comparison_high
    signal["range_low"] = comparison_low
    signal["dist_to_zg"] = dist_to_zg
    signal["dist_to_zd"] = dist_to_zd
    signal["today_price"] = today_price
    signal["today_date"] = today_date

    if today_price > comparison_high:
        signal["comparison_result"] = "突破"
        signal["comparison_state"] = "breakout"
        signal["status"] = texts["breakout_status"]
        signal["signal_type"] = texts["breakout_signal_type"]
        signal["position_level"] = texts["breakout_position_level"]
        signal["action"] = texts["breakout_action"]
    elif today_price < comparison_low:
        signal["comparison_result"] = "下跌"
        signal["comparison_state"] = "down"
        signal["status"] = texts["down_status"]
        signal["signal_type"] = texts["down_signal_type"]
        signal["position_level"] = texts["down_position_level"]
        signal["action"] = texts["down_action"]
        if security_type == "index":
            signal["fell_into_next_zone"] = False
            if len(zhongshu_list) >= 2:
                for prev_zs in reversed(zhongshu_list[:-1]):
                    if prev_zs["zd"] <= today_price <= prev_zs["zg"]:
                        signal["status"] = "🚨 跌破并落入下中枢区间"
                        signal["signal_type"] = "暴跌至下一中枢"
                        signal["action"] = "严禁抄底，等待企稳"
                        signal["fell_into_next_zone"] = True
                        break
    else:
        signal["comparison_result"] = "震荡"
        signal["comparison_state"] = "range"
        signal["status"] = texts["range_status"]
        signal["signal_type"] = texts["range_signal_type"]
        signal["position_level"] = texts["range_position_level"]
        signal["action"] = texts["range_action"]

    if is_current_forming:
        original_status = signal.get("status", "待确认")
        signal["structure_confirmation"] = "forming"
        signal["current_kline_count"] = current_kline_count
        signal["required_kline_count"] = required_kline_count
        signal["status"] = (
            f"⏳ 当前中枢形成中（{current_kline_count}/{required_kline_count}，"
            f"原信号：{original_status}，仅观察）"
        )
        signal["action"] = "只观察，等平台结构确认"

    return signal


def analyze_security_zhongshu_from_frame(
    df,
    *,
    security_code: str,
    security_name: str = "",
    security_type: str = "stock",
    recent_days: int = 120,
    min_zhongshu_klines: int = 20,
    target_date: str | None = None,
    data_source: str = "injected_dataframe",
    print_fn=print,
) -> dict[str, Any]:
    from decision.zhongshu_runtime import (
        append_tail_candidate_platform,
        append_today_trailing_connector,
        build_zhongshu_structure,
        split_zhongshu_history_and_today,
    )

    try:
        import pandas as pd

        if df is None or len(df) == 0:
            return {"success": False, "error": "K线数据为空"}

        frame = df.copy() if hasattr(df, "copy") else pd.DataFrame(df)
        for price_col in ["open", "high", "low", "close", "volume", "amount"]:
            if price_col in frame.columns:
                frame[price_col] = pd.to_numeric(frame[price_col], errors="coerce")
        frame = frame.dropna(subset=["high", "low", "close"])

        recent_df, hist_df, today_df = split_zhongshu_history_and_today(
            frame,
            recent_days=recent_days,
            target_date=target_date,
        )
        del recent_df

        structure_segments, zhongshu_list = build_zhongshu_structure(
            hist_df,
            min_zhongshu_klines=min_zhongshu_klines,
            min_overlap_bars=3,
        )

        today_price = float(today_df["close"])
        today_date = today_df["date"]
        structure_segments = append_today_trailing_connector(structure_segments, today_df)
        structure_segments = append_tail_candidate_platform(structure_segments, hist_df.to_dict("records") + [today_df.to_dict()])
        current = zhongshu_list[-1] if zhongshu_list else None
        latest_structure_segment = structure_segments[-1] if structure_segments else None
        normalized_security_type = str(security_type or "stock")

        signal = build_security_zhongshu_signal(
            current,
            zhongshu_list,
            today_price=today_price,
            today_date=today_date,
            min_zhongshu_klines=min_zhongshu_klines,
            security_type=normalized_security_type,
        )

        label = "大盘结构" if normalized_security_type == "index" else "个股结构"
        print_fn(
            f"[{label}] 数据源: {data_source}，识别到{len(zhongshu_list)}个结构中枢，"
            f"当前价格{today_price:.2f}"
        )
        return {
            "security_code": security_code,
            "security_name": security_name,
            "security_type": normalized_security_type,
            "zhongshu_list": zhongshu_list,
            "current_zhongshu": current,
            "structure_segments": structure_segments,
            "latest_structure_segment": latest_structure_segment,
            "today_price": today_price,
            "today_date": today_date,
            "signal": signal,
            "success": True,
            "data_source": data_source,
            "strict_chanlun_policy": strict_chanlun_policy_for_security(normalized_security_type),
        }
    except Exception as error:
        print_fn(f"中枢结构分析失败: {error}")
        traceback.print_exc()
        return {
            "security_code": security_code,
            "security_name": security_name,
            "security_type": str(security_type or "stock"),
            "success": False,
            "error": str(error),
        }


def analyze_security_zhongshu_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    security_code: str,
    security_name: str = "",
    security_type: str = "stock",
    recent_days: int = 120,
    min_zhongshu_klines: int = 20,
    target_date: str | None = None,
    data_source: str = "injected_rows",
    print_fn=print,
) -> dict[str, Any]:
    import pandas as pd

    return analyze_security_zhongshu_from_frame(
        pd.DataFrame(list(rows or [])),
        security_code=security_code,
        security_name=security_name,
        security_type=security_type,
        recent_days=recent_days,
        min_zhongshu_klines=min_zhongshu_klines,
        target_date=target_date,
        data_source=data_source,
        print_fn=print_fn,
    )
