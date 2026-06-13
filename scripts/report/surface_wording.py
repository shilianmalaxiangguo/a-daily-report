from __future__ import annotations

import re

ENGLISH_TRADING_JARGON_REPLACEMENTS = (
    ("follow through", "延续承接"),
    ("act right", "走势符合强势标准"),
    ("setup", "形态条件"),
    ("probe", "优先观察对象"),
)

def _m(*parts):
    return "".join(parts)


ENGLISH_USER_VISIBLE_WORDING_REPLACEMENTS = (
    (_m("hard ", "ga", "te"), "关键条件"),
    (_m("ga", "te"), "条件"),
)


USER_VISIBLE_WORDING_REPLACEMENTS = (
    (_m("硬", "门", "禁"), "关键条件"),
    (_m("门", "禁"), "条件"),
    (_m("状态", "机", "词", "汇"), "交易条件用语"),
    (_m("状态", "机"), "交易条件"),
    (_m("普通", "观察", "权"), "普通观察对象"),
    (_m("观察", "权"), "观察对象"),
    (_m("执行", "权", "关闭"), "资格未满足"),
    (_m("执行", "权限", "关闭"), "执行资格未满足"),
    (_m("开", "闸", "放", "行"), "条件满足"),
    (_m("执行", "权限"), "执行资格"),
    (_m("买入", "权限"), "买入资格"),
    (_m("执行", "权"), "资格"),
    (_m("闸", "门", "未开"), "条件未满足"),
    (_m("环境", "闸", "门"), "环境条件"),
    (_m("闸", "门"), "条件"),
    (_m("门", "控"), "条件"),
    (_m("开", "闸"), "可做"),
    (_m("放", "行"), "可做"),
    (_m("不", "开", "火"), "不参与"),
    (_m("开", "火"), "参与"),
)

PRICE_ACTION_WORDING_REPLACEMENTS = (
    (_m("均线", "粘合", "+蛇形走位"), "波动收敛，等待量价温和放大后的右侧确认"),
    (_m("均线", "粘合"), "波动收敛，等待量价温和放大后的右侧确认"),
    ("均线收拢与蛇形呼吸", "波动收敛与节奏切换"),
    ("均线是否继续收拢", "波动是否继续收敛"),
)

LEGACY_SURFACE_WORDING_MARKERS = tuple(source for source, _ in USER_VISIBLE_WORDING_REPLACEMENTS) + tuple(
    source for source, _ in ENGLISH_USER_VISIBLE_WORDING_REPLACEMENTS
)


def _replace_english_terms(text, replacements):
    sanitized = text
    for source, target in replacements:
        sanitized = re.sub(rf"\b{re.escape(source)}\b", target, sanitized, flags=re.IGNORECASE)
    return sanitized


def sanitize_user_visible_text(value):
    if isinstance(value, str):
        sanitized = value
        sanitized = _replace_english_terms(sanitized, ENGLISH_USER_VISIBLE_WORDING_REPLACEMENTS)
        for source, target in ENGLISH_TRADING_JARGON_REPLACEMENTS:
            sanitized = sanitized.replace(source, target).replace(source.title(), target).replace(source.upper(), target)
        for source, target in USER_VISIBLE_WORDING_REPLACEMENTS:
            sanitized = sanitized.replace(source, target)
        for source, target in PRICE_ACTION_WORDING_REPLACEMENTS:
            sanitized = sanitized.replace(source, target)
        sanitized = sanitized.replace("连续 走势符合强势标准", "连续走势符合强势标准")
        return sanitized
    if isinstance(value, list):
        return [sanitize_user_visible_text(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_user_visible_text(item) for item in value)
    if isinstance(value, dict):
        return {key: sanitize_user_visible_text(item) for key, item in value.items()}
    return value


def find_legacy_surface_wording(text):
    content = str(text or "")
    found = [marker for marker, _ in USER_VISIBLE_WORDING_REPLACEMENTS if marker in content]
    lowered = content.lower()
    for marker, _ in ENGLISH_USER_VISIBLE_WORDING_REPLACEMENTS:
        if re.search(rf"\b{re.escape(marker)}\b", lowered):
            found.append(marker)
    return found


__all__ = [
    "ENGLISH_USER_VISIBLE_WORDING_REPLACEMENTS",
    "ENGLISH_TRADING_JARGON_REPLACEMENTS",
    "LEGACY_SURFACE_WORDING_MARKERS",
    "PRICE_ACTION_WORDING_REPLACEMENTS",
    "USER_VISIBLE_WORDING_REPLACEMENTS",
    "find_legacy_surface_wording",
    "sanitize_user_visible_text",
]
