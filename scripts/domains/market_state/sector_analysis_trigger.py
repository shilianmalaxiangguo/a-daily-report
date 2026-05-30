PARTIAL_DIMENSIONS = ["中军识别与跟踪", "板块间资金流动"]

CONFIRMATION_DIMENSIONS = [
    "中军识别与跟踪",
    "板块内相对位置",
    "弹性载体识别",
    "后排承接质量",
    "二波创新高群",
]

STABLE_DIMENSIONS = CONFIRMATION_DIMENSIONS + ["板块间资金流动"]

CONSERVATIVE_PATTERNS = {"无主线", "混沌轮动", "混沌接力"}
CONSERVATIVE_TURNOVER_QUALITIES = {"杀跌放量", "缩量", "待累计"}
REPLACEMENT_PATTERNS = {"双主线竞争", "主线+背景线", "交替竞争"}


def evaluate_sector_analysis_trigger(context_or_signal=None, **overrides):
    context = dict(context_or_signal or {})
    context.update({key: value for key, value in overrides.items() if value is not None})

    window_state = _clean_text(context.get("window_state"))
    mainline_pattern = _first_text(
        context.get("mainline_pattern"),
        context.get("mainline_regime"),
        context.get("sector_relationship_state"),
    )
    turnover_quality = _clean_text(context.get("turnover_quality"))
    mainline_days = _safe_int(context.get("mainline_days"), default=0)

    if not window_state or not mainline_pattern or not turnover_quality:
        return _result(
            should_analyze=False,
            phase="粘合期",
            dimensions=[],
            reason="条件不完整，先不做板块内部分析。",
        )

    if (
        window_state == "observe"
        or mainline_pattern in CONSERVATIVE_PATTERNS
        or turnover_quality in CONSERVATIVE_TURNOVER_QUALITIES
    ):
        return _result(
            should_analyze=False,
            phase="粘合期",
            dimensions=[],
            reason="条件偏观察，先不做板块内部分析。",
        )

    if window_state == "confirm_next" and mainline_pattern in REPLACEMENT_PATTERNS:
        return _result(
            should_analyze=True,
            phase="接替期",
            dimensions=PARTIAL_DIMENSIONS,
            reason="接替期看竞争关系，先盯中军和资金流向。",
        )

    if window_state == "open" and mainline_pattern == "单主线聚焦" and turnover_quality == "做多放量":
        if mainline_days >= 3:
            return _result(
                should_analyze=True,
                phase="主线稳定期",
                dimensions=STABLE_DIMENSIONS,
                reason="主线连续3天以上，内部强弱和板块间流向都要看。",
            )
        return _result(
            should_analyze=True,
            phase="分化确认期",
            dimensions=CONFIRMATION_DIMENSIONS,
            reason="主线已聚焦，开始看板块内部强弱和接力。",
        )

    return _result(
        should_analyze=False,
        phase="粘合期",
        dimensions=[],
        reason="条件偏观察，先不做板块内部分析。",
    )


def _result(should_analyze, phase, dimensions, reason):
    return {
        "should_analyze": bool(should_analyze),
        "phase": phase,
        "dimensions": list(dimensions or []),
        "reason": reason,
    }


def _clean_text(value):
    return str(value or "").strip()


def _first_text(*values):
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
