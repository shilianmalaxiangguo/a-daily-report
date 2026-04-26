from __future__ import annotations

__all__ = ["analyze_candlestick_pattern"]


def analyze_candlestick_pattern(open_price, close_price, high_price, low_price, change_pct, first_limit_time=None):
    """
    判断蜡烛图形态。

    Returns:
        tuple[str, float, str]: 形态名称、形态得分、操作建议。
    """
    amplitude = high_price - low_price

    time_bonus = 0
    time_desc = ""
    if first_limit_time and change_pct >= 9.9:
        try:
            time_parts = first_limit_time.split(":")
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                total_minutes = hour * 60 + minute

                if total_minutes <= 9 * 60 + 35:
                    time_bonus = 3
                    time_desc = "(9:35前封板+3)"
                elif total_minutes <= 10 * 60:
                    time_bonus = 2
                    time_desc = "(10:00前封板+2)"
                elif total_minutes <= 11 * 60 + 30:
                    time_bonus = 1
                    time_desc = "(11:30前封板+1)"
                elif total_minutes <= 14 * 60 + 30:
                    time_bonus = 0.5
                    time_desc = "(14:30前封板+0.5)"
                else:
                    time_bonus = 0
                    time_desc = ""
        except Exception:
            pass

    price_tolerance = max(abs(close_price) * 0.005, 0.01) if close_price else 0.01
    close_at_high = abs(close_price - high_price) <= price_tolerance
    open_near_high = abs(open_price - high_price) <= price_tolerance
    has_intraday_break = low_price < min(open_price, close_price) - price_tolerance

    if change_pct >= 9.9 and abs(open_price - close_price) <= price_tolerance and abs(high_price - low_price) <= price_tolerance:
        final_score = 10 + time_bonus
        return f"一字板加速{time_desc}", final_score, "最强加速形态，次日可能继续加速或分歧"

    if change_pct >= 9.9 and close_at_high and open_near_high and has_intraday_break:
        final_score = 8 + time_bonus
        return f"T字板分歧转一致{time_desc}", final_score, "涨停价开盘，盘中炸板后回封，分歧转一致"

    if change_pct >= 9.9 and high_price == close_price and open_price < close_price:
        final_score = 4 + time_bonus
        return f"光头大阳柱涨停{time_desc}", final_score, "低位拉板封涨停，强势吸筹，分歧较小"

    amplitude_pct = (amplitude / open_price) * 100 if open_price > 0 else 0
    upper_shadow_pct = ((high_price - max(open_price, close_price)) / close_price) * 100 if close_price > 0 else 0

    if change_pct > 5 and amplitude_pct > 5:
        base_score = 2
        if upper_shadow_pct > 3:
            score = max(base_score - 2, 0)
            return f"放量大阳线+长上影线({upper_shadow_pct:.1f}%)", score, "放量上涨但长上影线，主力试盘或遇强压，信号减弱"
        if upper_shadow_pct > 1:
            score = max(base_score - 1, 0)
            return f"放量大阳线+上影线({upper_shadow_pct:.1f}%)", score, "放量上涨但有上影线，有一定抛压，信号打折"
        return "放量大阳线", base_score, "强势上涨形态，次日可能延续"

    if change_pct > 0 and 2 <= amplitude_pct <= 5:
        return "温和放量+多头排列", 2, "温和上涨形态"

    if -2 <= change_pct <= 2:
        return "震荡整理", 0, "震荡整理，观望为主"

    if amplitude_pct < 2:
        return "缩量调整", 0, "量能萎缩，观望情绪浓厚"

    if change_pct < -2:
        return "下跌趋势", 0, "下跌趋势，回避为主"

    if change_pct < -3 and amplitude > 5:
        return "高位大绿棒放量", 0, "出货形态，风险较大，坚决回避"

    return "普通形态", 0, "无明显特征"
