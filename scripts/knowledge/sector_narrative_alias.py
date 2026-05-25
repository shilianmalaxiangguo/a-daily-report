from __future__ import annotations

AUTO_PARTS_SURFACE_LABELS = (
    "汽车零部件",
    "汽车配件",
    "新能源车零部件",
    "汽车电子",
)

ROBOT_COMPONENT_LABELS = (
    "电机",
    "传感器",
    "执行器",
    "伺服",
    "减速器",
    "机械基件",
)

ROBOT_CONTEXT_MARKERS = (
    "机器人",
    "人形机器人",
    "具身智能",
    "智元",
    "优必选",
    "减速器",
    "伺服",
    "执行器",
    "传感器",
    "灵巧手",
    "机器视觉",
    "智能制造",
)

HARD_TECH_ELECTRONICS_SURFACE_LABELS = (
    "半导体",
    "半导体概念",
    "元器件",
    "元件",
    "电子元件",
    "电子元器件",
    "芯片",
    "芯片概念",
)

AMBIGUOUS_COMPONENT_SURFACE_LABELS = (
    "元器件",
    "元件",
    "电子元件",
    "电子元器件",
)

HARD_TECH_ELECTRONICS_CONTEXT_MARKERS = (
    "半导体",
    "芯片",
    "存储芯片",
    "先进封装",
    "第三代半导体",
    "国家大基金",
    "光刻胶",
    "氮化镓",
    "碳化硅",
    "PCB",
    "电子布",
    "玻璃基板",
    "玻璃玻纤",
    "覆铜板",
    "铜箔",
    "CPO",
    "共封装光学",
    "光通信模块",
    "光模块",
    "光纤",
    "F5G",
    "铜缆高速连接",
    "MLCC",
    "被动元件",
    "超级电容",
    "电容",
    "电感",
)

CONSUMER_ELECTRONICS_CONTEXT_MARKERS = (
    "消费电子",
    "苹果概念",
    "AI眼镜",
    "AI PC",
    "智能穿戴",
    "无线耳机",
    "3D摄像头",
    "OLED",
    "柔性屏",
    "MR",
    "VR",
    "AR",
)

AI_COMPUTE_CONTEXT_MARKERS = (
    "数据中心",
    "液冷服务器",
    "算力",
    "英伟达概念",
    "服务器",
    "AIDC",
    "东数西算",
    "云计算",
)

SMART_AUTO_CONTEXT_MARKERS = (
    "汽车电子",
    "无人驾驶",
    "智能驾驶",
    "车联网",
    "激光雷达",
    "毫米波雷达",
)

POWER_STORAGE_CONTEXT_MARKERS = (
    "储能",
    "电力",
    "虚拟电厂",
    "智能电网",
    "特高压",
    "光伏",
    "风电",
    "充电桩",
)

BRANCH_TO_FAMILY = {
    "光通信/CPO": "泛半导体/硬科技电子",
    "存储/芯片": "泛半导体/硬科技电子",
    "PCB/电子材料": "泛半导体/硬科技电子",
    "被动元件/MLCC": "泛半导体/硬科技电子",
    "AI终端/消费电子": "AI终端/消费电子",
    "数据中心/液冷算力": "AI算力基础设施",
    "智能汽车/无人驾驶": "智能汽车",
    "电力/储能": "电力储能",
    "人形机器人": "人形机器人",
}

DRIVER_BRANCH_MARKERS = (
    (
        "光通信/CPO",
        (
            "CPO",
            "共封装光学",
            "光模块",
            "光通信模块",
            "光纤",
            "F5G",
            "铜缆高速连接",
        ),
    ),
    (
        "存储/芯片",
        (
            "存储芯片",
            "半导体",
            "芯片概念",
            "半导体概念",
            "先进封装",
            "第三代半导体",
            "汽车芯片",
            "国家大基金",
            "光刻胶",
            "氮化镓",
            "碳化硅",
        ),
    ),
    (
        "PCB/电子材料",
        (
            "PCB",
            "电子布",
            "玻璃基板",
            "玻璃玻纤",
            "覆铜板",
            "铜箔",
        ),
    ),
    (
        "被动元件/MLCC",
        (
            "MLCC",
            "被动元件",
            "超级电容",
            "电容",
            "电感",
        ),
    ),
    (
        "AI终端/消费电子",
        CONSUMER_ELECTRONICS_CONTEXT_MARKERS,
    ),
    (
        "数据中心/液冷算力",
        AI_COMPUTE_CONTEXT_MARKERS,
    ),
    (
        "智能汽车/无人驾驶",
        SMART_AUTO_CONTEXT_MARKERS,
    ),
    (
        "电力/储能",
        POWER_STORAGE_CONTEXT_MARKERS,
    ),
    (
        "人形机器人",
        ROBOT_CONTEXT_MARKERS,
    ),
)

SUM_FIELDS = (
    "net_inflow_amount",
    "net_inflow_yi",
    "zljlr",
    "inflow",
    "fund_flow",
    "sector_turnover",
    "turnover_yi",
    "turnover_share_pct",
    "turnover_share_change",
    "limit_up_count",
    "strong_gain_count",
)

MIN_FIELDS = ("net_inflow_rank",)
MAX_FIELDS = ("high_anchor_height", "broad_rally_pct")


def _clean_text(value) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def _as_terms(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, dict):
        terms = []
        for key, value in values.items():
            terms.append(key)
            terms.extend(_as_terms(value))
        return [term for term in terms if term]
    if isinstance(values, (list, tuple, set)):
        terms = []
        for value in values:
            terms.extend(_as_terms(value))
        return [term for term in terms if term]
    text = _clean_text(values)
    if not text:
        return []
    for marker in (";", "；", "、", "|", "/", "，"):
        text = text.replace(marker, ",")
    return [_clean_text(part) for part in text.split(",") if _clean_text(part)]


def _contains_any(text: str, markers) -> bool:
    return any(marker and marker in text for marker in markers)


def _matched_marker_count(text: str, markers) -> int:
    return sum(1 for marker in markers if marker and marker in text)


def _has_robot_context(terms) -> bool:
    text = " ".join(_as_terms(terms))
    if _contains_any(text, ROBOT_CONTEXT_MARKERS):
        return True
    return _contains_any(text, AUTO_PARTS_SURFACE_LABELS) and _contains_any(text, ROBOT_COMPONENT_LABELS)


def build_sector_driver_tag_profile(tags, context_terms=None) -> dict:
    surface_tags = []
    for tag in _as_terms([tags, context_terms]):
        if tag and tag not in surface_tags:
            surface_tags.append(tag)

    text = " ".join(surface_tags)
    driver_branches = []
    for branch, markers in DRIVER_BRANCH_MARKERS:
        if _contains_any(text, markers):
            driver_branches.append(branch)

    hard_tech_signal = _contains_any(text, HARD_TECH_ELECTRONICS_SURFACE_LABELS) or _contains_any(
        text,
        HARD_TECH_ELECTRONICS_CONTEXT_MARKERS,
    )
    consumer_signal = _contains_any(text, CONSUMER_ELECTRONICS_CONTEXT_MARKERS)
    hard_tech_branch_signal = any(BRANCH_TO_FAMILY.get(branch) == "泛半导体/硬科技电子" for branch in driver_branches)

    family = ""
    if hard_tech_signal and hard_tech_branch_signal:
        family = "泛半导体/硬科技电子"
    elif consumer_signal:
        family = "AI终端/消费电子"
    else:
        for branch in driver_branches:
            family = BRANCH_TO_FAMILY.get(branch, "")
            if family:
                break

    return {
        "family": family,
        "driver_branches": driver_branches,
        "surface_tags": surface_tags,
    }


def resolve_sector_narrative_label(label, context_terms=None) -> str:
    label_text = _clean_text(label)
    if not label_text:
        return ""
    terms = [label_text] + _as_terms(context_terms)
    if _contains_any(label_text, AUTO_PARTS_SURFACE_LABELS) and _has_robot_context(terms):
        return "人形机器人"
    if _contains_any(label_text, ROBOT_COMPONENT_LABELS) and _has_robot_context(terms):
        return "人形机器人"
    if "算电" in label_text:
        return "算电协同"

    if _contains_any(label_text, CONSUMER_ELECTRONICS_CONTEXT_MARKERS):
        return "AI终端/消费电子"
    if _contains_any(label_text, AI_COMPUTE_CONTEXT_MARKERS) and _matched_marker_count(" ".join(terms), AI_COMPUTE_CONTEXT_MARKERS) >= 2:
        return "AI算力基础设施"
    if _contains_any(label_text, SMART_AUTO_CONTEXT_MARKERS) and _matched_marker_count(" ".join(terms), SMART_AUTO_CONTEXT_MARKERS) >= 2:
        return "智能汽车"
    if _contains_any(label_text, POWER_STORAGE_CONTEXT_MARKERS) and _matched_marker_count(" ".join(terms), POWER_STORAGE_CONTEXT_MARKERS) >= 2:
        return "电力储能"

    if not _contains_any(label_text, AMBIGUOUS_COMPONENT_SURFACE_LABELS):
        return label_text

    profile = build_sector_driver_tag_profile(terms)
    if profile["family"] == "泛半导体/硬科技电子":
        return profile["family"]
    return label_text


def normalize_sector_list_by_narrative(values, context_terms=None) -> list[str]:
    normalized = []
    context = _as_terms(context_terms) + _as_terms(values)
    for value in _as_terms(values):
        label = resolve_sector_narrative_label(value, context)
        if label and label not in normalized:
            normalized.append(label)
    return normalized


def _safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _merge_numeric(target, row, key, mode):
    value = _safe_float((row or {}).get(key))
    if value is None:
        return
    current = _safe_float(target.get(key))
    if mode == "sum":
        target[key] = round((current or 0.0) + value, 4)
    elif mode == "min":
        target[key] = value if current is None else min(current, value)
    elif mode == "max":
        target[key] = value if current is None else max(current, value)


def merge_sector_evidence_rows_by_narrative(rows) -> list[dict]:
    source_rows = [row for row in rows or [] if isinstance(row, dict)]
    context_terms = []
    for row in source_rows:
        context_terms.extend(
            _as_terms(
                [
                    row.get("sector_name"),
                    row.get("sector"),
                    row.get("high_anchor_name"),
                    row.get("matched_flow_names"),
                    row.get("surface_sector_names"),
                    row.get("concepts"),
                    row.get("reason"),
                ]
            )
        )

    merged = {}
    ordered_keys = []
    for row in source_rows:
        surface_name = _clean_text(row.get("sector_name") or row.get("sector"))
        narrative_name = resolve_sector_narrative_label(surface_name, context_terms)
        if not narrative_name:
            continue
        if narrative_name not in merged:
            merged[narrative_name] = {"sector_name": narrative_name, "surface_sector_names": []}
            ordered_keys.append(narrative_name)
        target = merged[narrative_name]
        if surface_name and surface_name not in target["surface_sector_names"]:
            target["surface_sector_names"].append(surface_name)
        for original_surface_name in row.get("surface_sector_names") or []:
            original_surface_name = _clean_text(original_surface_name)
            if original_surface_name and original_surface_name not in target["surface_sector_names"]:
                target["surface_sector_names"].append(original_surface_name)

        missing_fields = set(target.get("missing_fields") or [])
        missing_fields.update(row.get("missing_fields") or [])
        if missing_fields:
            target["missing_fields"] = sorted(missing_fields)

        for key in SUM_FIELDS:
            _merge_numeric(target, row, key, "sum")
        for key in MIN_FIELDS:
            _merge_numeric(target, row, key, "min")
        for key in MAX_FIELDS:
            _merge_numeric(target, row, key, "max")

        row_height = _safe_float(row.get("high_anchor_height"))
        target_height = _safe_float(target.get("high_anchor_height"))
        if row.get("high_anchor_name") and (target_height is None or row_height == target_height):
            target["high_anchor_name"] = _clean_text(row.get("high_anchor_name"))

        for key, value in row.items():
            if key in target or key in SUM_FIELDS or key in MIN_FIELDS or key in MAX_FIELDS:
                continue
            if value not in (None, ""):
                target[key] = value

    return [merged[key] for key in ordered_keys]


__all__ = [
    "build_sector_driver_tag_profile",
    "merge_sector_evidence_rows_by_narrative",
    "normalize_sector_list_by_narrative",
    "resolve_sector_narrative_label",
]
