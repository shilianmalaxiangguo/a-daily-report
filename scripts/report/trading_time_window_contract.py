FIXED_TRADING_WINDOWS = ("09:30-09:35", "09:50-10:10", "14:30-14:55")
OPENING_WINDOW = "09:30-09:35"
SECOND_CONFIRM_WINDOW = "09:50-10:10"
SECOND_CONFIRM_LABEL = f"{SECOND_CONFIRM_WINDOW}窗口"
TAIL_WINDOW = "14:30-14:55"


def normalize_trading_time_text(value):
    if isinstance(value, list):
        return [normalize_trading_time_text(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_trading_time_text(item) for item in value)
    if isinstance(value, dict):
        return {key: normalize_trading_time_text(item) for key, item in value.items()}
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    text = str(value or "").strip()
    if not text:
        return text
    replacements = (
        ("形成参与窗口后", f"{SECOND_CONFIRM_WINDOW}窗口内条件成立后"),
        ("参与窗口确认后", "固定交易窗口条件满足后"),
        ("参与窗口确认才执行", "固定交易窗口内条件成立才执行"),
        ("参与窗口失败回到0%", "固定交易窗口内条件不成立就回到0%"),
        ("参与窗口是否成立", "固定交易窗口内条件是否成立"),
        ("参与窗口分层确认", "固定交易窗口条件"),
        ("参与窗口确认", "固定交易窗口条件"),
        ("参与窗口成立", "固定交易窗口内条件成立"),
        ("参与窗口命中", "固定交易窗口条件满足"),
        ("预演参与窗口", "固定交易窗口条件"),
        ("形成参与窗口", "固定交易窗口内条件成立"),
        ("参与窗口失败", "固定交易窗口内条件不成立"),
        ("参与窗口不成立", "固定交易窗口内条件不成立"),
        ("参与窗口", "固定交易窗口条件"),
        ("60分钟确认分层处理", f"{SECOND_CONFIRM_LABEL}处理"),
        ("60分钟分层参与窗口", SECOND_CONFIRM_LABEL),
        ("60分钟分层参与", SECOND_CONFIRM_LABEL),
        ("60 分钟确认", SECOND_CONFIRM_LABEL),
        ("60分钟确认", SECOND_CONFIRM_LABEL),
        ("60分钟定买点", SECOND_CONFIRM_LABEL),
        ("首个60分钟", SECOND_CONFIRM_WINDOW),
        ("10点后", SECOND_CONFIRM_WINDOW),
        ("10点附近", SECOND_CONFIRM_WINDOW),
        ("10点前后", SECOND_CONFIRM_WINDOW),
        ("10点确认", SECOND_CONFIRM_LABEL),
        ("10点看承接", f"{SECOND_CONFIRM_WINDOW}看承接"),
        ("等10点确认", f"等{SECOND_CONFIRM_LABEL}"),
        ("等待10点确认", f"等待{SECOND_CONFIRM_LABEL}"),
        ("10点确认价", f"{SECOND_CONFIRM_WINDOW}观察价"),
        ("10:00左右买", SECOND_CONFIRM_WINDOW),
        ("10:00左右观察", SECOND_CONFIRM_WINDOW),
        (f"{SECOND_CONFIRM_WINDOW}确认并处理买卖", f"{SECOND_CONFIRM_WINDOW}窗口处理买卖"),
        (f"{SECOND_CONFIRM_WINDOW}确认参与", f"{SECOND_CONFIRM_WINDOW}窗口条件满足后参与"),
        (f"完成{SECOND_CONFIRM_WINDOW}确认后", f"{SECOND_CONFIRM_WINDOW}窗口条件满足后"),
        (f"完成{SECOND_CONFIRM_WINDOW}确认", f"{SECOND_CONFIRM_WINDOW}窗口条件满足"),
        (f"等{SECOND_CONFIRM_WINDOW}确认", f"等{SECOND_CONFIRM_WINDOW}窗口条件"),
        ("尾盘买卖窗口", f"{TAIL_WINDOW}买卖窗口"),
        ("**结构确认窗口（09:35-10:30）**:", f"**{SECOND_CONFIRM_WINDOW}买卖窗口（{SECOND_CONFIRM_WINDOW}）**:"),
        ("**盘中执行（10:30-14:30）**:", "**盘中观察（非买卖窗口）**:"),
        ("结构确认窗口（09:35-10:30）", f"{SECOND_CONFIRM_WINDOW}买卖窗口"),
        ("盘中执行（10:30-14:30）", "盘中观察（非买卖窗口）"),
        ("09:35-10:30", SECOND_CONFIRM_WINDOW),
        ("10:30-14:30", "非买卖窗口"),
        ("买后用30分钟结构止损", "买后用失效价和单笔-5%底线处理风险"),
        ("买后30分钟结构止损", "买后用失效价和单笔-5%底线处理风险"),
        ("买入后再用30分钟结构定止损", "买入后按失效价和单笔-5%底线处理风险"),
        ("买入后改用30分钟结构止损", "买入后按失效价和单笔-5%底线处理风险"),
        ("买入后按30分钟结构执行", "买入后按失效价执行"),
        ("买入后用30分钟结构设置止损", "买入后按失效价和单笔-5%底线处理风险"),
        ("30分钟结构失守立即卖", "失效价失守立即卖"),
        ("30分钟结构失守", "失效价失守"),
        ("30分钟结构止损线", "风险线"),
        ("30分钟结构定止损", "按失效价和单笔-5%底线处理风险"),
        ("30分钟定止损", "按失效价和单笔-5%底线处理风险"),
        ("30分钟结构止损", "失效价和单笔-5%底线"),
        ("30分钟止损线", "风险线"),
        ("30分钟止损", "失效价和单笔-5%底线"),
        ("30分钟结构未落地前", "盘前风险线未落地前"),
        ("先看30分钟结构", "先看失效价"),
        ("核心确认窗口", "核心执行窗口"),
        ("结构确认窗口", f"{SECOND_CONFIRM_WINDOW}买卖窗口"),
        ("确认窗口", "执行窗口"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.replace(f"才等{SECOND_CONFIRM_LABEL}", f"只看{SECOND_CONFIRM_LABEL}")
    text = text.replace(f"{SECOND_CONFIRM_LABEL}价", f"{SECOND_CONFIRM_WINDOW}观察价")
    text = text.replace(f"{SECOND_CONFIRM_LABEL}承接", SECOND_CONFIRM_LABEL)
    text = text.replace(f"{SECOND_CONFIRM_WINDOW}确认", f"{SECOND_CONFIRM_LABEL}条件")
    text = text.replace(f"{SECOND_CONFIRM_LABEL}后", f"{SECOND_CONFIRM_LABEL}满足条件后")
    text = text.replace(f"完成{SECOND_CONFIRM_LABEL}", f"{SECOND_CONFIRM_LABEL}满足条件")
    text = text.replace(f"{SECOND_CONFIRM_WINDOW}完成{SECOND_CONFIRM_LABEL}", f"{SECOND_CONFIRM_LABEL}满足条件")
    return text


def normalize_participation_window(value, default=SECOND_CONFIRM_WINDOW):
    text = normalize_trading_time_text(value)
    if not text or text in {"-", "暂无", "不做", "none"}:
        return default
    for window in FIXED_TRADING_WINDOWS:
        if window in text:
            return window
    if any(marker in text for marker in ("竞价", "开盘", "回封", "打板")):
        return OPENING_WINDOW
    if "尾盘" in text:
        return TAIL_WINDOW
    return default
