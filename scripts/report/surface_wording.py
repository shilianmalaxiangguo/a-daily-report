from __future__ import annotations

ENGLISH_TRADING_JARGON_REPLACEMENTS = (
    ("follow through", "延续承接"),
    ("act right", "走势符合强势标准"),
    ("setup", "形态条件"),
    ("probe", "优先观察对象"),
)

USER_VISIBLE_WORDING_REPLACEMENTS = (
    ("执行权关闭", "资格未满足"),
    ("执行权限关闭", "执行资格未满足"),
    ("开闸放行", "条件满足"),
    ("执行权限", "执行资格"),
    ("买入权限", "买入资格"),
    ("执行权", "资格"),
    ("闸门未开", "条件未满足"),
    ("环境闸门", "环境条件"),
    ("闸门", "条件"),
    ("门控", "条件"),
    ("开闸", "可做"),
    ("放行", "可做"),
)

LEGACY_SURFACE_WORDING_MARKERS = tuple(source for source, _ in USER_VISIBLE_WORDING_REPLACEMENTS)


def sanitize_user_visible_text(value):
    if isinstance(value, str):
        sanitized = value
        for source, target in ENGLISH_TRADING_JARGON_REPLACEMENTS:
            sanitized = sanitized.replace(source, target).replace(source.title(), target).replace(source.upper(), target)
        for source, target in USER_VISIBLE_WORDING_REPLACEMENTS:
            sanitized = sanitized.replace(source, target)
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
    return [marker for marker in LEGACY_SURFACE_WORDING_MARKERS if marker in content]


__all__ = [
    "ENGLISH_TRADING_JARGON_REPLACEMENTS",
    "LEGACY_SURFACE_WORDING_MARKERS",
    "USER_VISIBLE_WORDING_REPLACEMENTS",
    "find_legacy_surface_wording",
    "sanitize_user_visible_text",
]
