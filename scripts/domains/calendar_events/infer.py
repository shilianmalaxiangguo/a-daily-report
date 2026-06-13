from __future__ import annotations

import time

from llm_service import get_llm_service as _default_get_llm_service

__all__ = [
    "ai_analyze_event_sectors",
    "analyze_event_sector",
    "fallback_sector_analysis",
    "generate_related_sectors",
    "generate_trading_logic",
    "has_clear_signal",
    "infer_expectation",
    "infer_related_sectors",
    "llm_analyze_event",
    "minimal_fallback_analysis",
    "normalize_calendar_ai_analysis",
]

GENERIC_CALENDAR_DIRECTION = "政策催化"
GENERIC_CALENDAR_SECTORS = ["政策催化"]
PENDING_CALENDAR_DIRECTION = "待确认"
PENDING_CALENDAR_SECTORS = ["待确认"]
_INVALID_CALENDAR_SECTOR_LABELS = {"", "其他", "需盘面确认", "相关产业链标的"}
_SEMANTIC_PRIORITY_DIRECTIONS = {
    "云计算",
    "电子元器件",
    "新能源",
    "汽车产业链",
    "原油",
    "有色金属",
    "消费电子",
    "本地生活",
    "宏观经济",
    "供应链服务",
    "金融流动性",
    "海峡概念",
    "文旅体育",
}
_BROAD_REMOTE_DIRECTIONS = {
    "半导体",
    "外贸投资",
    "宏观经济",
    "周期资源",
    "消费",
    "金融",
    "政策催化",
}
_MISSING = object()
_llm_call_stats = {
    "total_calls": 0,
    "total_time": 0.0,
    "event_analysis_calls": 0,
    "event_analysis_time": 0.0,
    "sector_analysis_calls": 0,
    "sector_analysis_time": 0.0,
}
ENABLE_REMOTE_CALENDAR_LLM = False


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def minimal_fallback_analysis(event_title: str, event_summary: str = "", *, helpers=None) -> dict:
    previous = _install_runtime_bindings(helpers or {})
    try:
        return normalize_calendar_ai_analysis(
            _minimal_fallback_analysis_legacy_body(event_title, event_summary),
            event_title,
            event_summary,
            allow_rule_fallback=False,
        )
    finally:
        _restore_runtime_bindings(previous)


def ai_analyze_event_sectors(event_title, event_summary="", *, helpers=None, print_fn=print):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _ai_analyze_event_sectors_legacy_body(event_title, event_summary, print_fn=print_fn)
    finally:
        _restore_runtime_bindings(previous)


def llm_analyze_event(event_text, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _llm_analyze_event_legacy_body(event_text)
    finally:
        _restore_runtime_bindings(previous)


def fallback_sector_analysis(text, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _fallback_sector_analysis_legacy_body(text)
    finally:
        _restore_runtime_bindings(previous)


def infer_related_sectors(text, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _infer_related_sectors_legacy_body(text)
    finally:
        _restore_runtime_bindings(previous)


def generate_related_sectors(direction, text="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _generate_related_sectors_legacy_body(direction, text)
    finally:
        _restore_runtime_bindings(previous)


def generate_trading_logic(direction, text="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _generate_trading_logic_legacy_body(direction, text)
    finally:
        _restore_runtime_bindings(previous)


def infer_expectation(text, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _infer_expectation_legacy_body(text)
    finally:
        _restore_runtime_bindings(previous)


def has_clear_signal(text, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _has_clear_signal_legacy_body(text)
    finally:
        _restore_runtime_bindings(previous)


def _has_policy_catalyst_evidence(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    direct_terms = [
        "政策",
        "新规",
        "监管",
        "条例",
        "办法",
        "意见",
        "通知",
        "细则",
        "征求意见",
        "国常会",
        "国务院",
        "发改委",
        "工信部",
        "证监会",
        "央行",
        "国新办",
        "统计局",
    ]
    if any(term in normalized for term in direct_terms):
        return True
    document_terms = ["规划", "方案", "规则", "标准"]
    action_terms = ["发布", "出台", "实施", "落地", "印发", "生效"]
    return any(term in normalized for term in document_terms) and any(term in normalized for term in action_terms)


def _generic_calendar_analysis(event_title: str = "", event_summary: str = "", *, reason: str = "") -> dict:
    text = f"{event_title} {event_summary}".strip()
    if _has_policy_catalyst_evidence(text):
        return {
            "main_direction": GENERIC_CALENDAR_DIRECTION,
            "related_sectors": list(GENERIC_CALENDAR_SECTORS),
            "trading_logic": reason or "标题包含明确政策、规则或官方文件证据，按政策催化观察",
            "expectation": infer_expectation(text) if text else "中性",
            "confidence": "低",
        }
    return {
        "main_direction": PENDING_CALENDAR_DIRECTION,
        "related_sectors": list(PENDING_CALENDAR_SECTORS),
        "trading_logic": reason or "标题缺少明确产业链或政策文件证据，保留待确认",
        "expectation": infer_expectation(text) if text else "中性",
        "confidence": "低",
    }


def _is_invalid_calendar_label(value) -> bool:
    return str(value or "").strip() in _INVALID_CALENDAR_SECTOR_LABELS


def _is_generic_calendar_label(value) -> bool:
    return str(value or "").strip() == GENERIC_CALENDAR_DIRECTION


def _should_prefer_title_semantics(result: dict, fallback_result: dict) -> bool:
    fallback_direction = str((fallback_result or {}).get("main_direction") or "").strip()
    remote_direction = str((result or {}).get("main_direction") or "").strip()
    if (
        not fallback_direction
        or _is_invalid_calendar_label(fallback_direction)
        or _is_generic_calendar_label(fallback_direction)
        or fallback_direction == remote_direction
    ):
        return False
    if fallback_direction not in _SEMANTIC_PRIORITY_DIRECTIONS:
        return False
    confidence = str((result or {}).get("confidence") or "").strip()
    if confidence == "低":
        return True
    if confidence in ("", "中") and remote_direction in _BROAD_REMOTE_DIRECTIONS:
        return True
    return False


def _dedupe_valid_calendar_sectors(sectors) -> list:
    if isinstance(sectors, str):
        candidates = [sectors]
    elif isinstance(sectors, (list, tuple, set)):
        candidates = list(sectors)
    else:
        candidates = []

    cleaned = []
    for sector in candidates:
        label = str(sector or "").strip()
        if _is_invalid_calendar_label(label):
            continue
        if label not in cleaned:
            cleaned.append(label)
    return cleaned


def normalize_calendar_ai_analysis(result, event_title: str = "", event_summary: str = "", *, allow_rule_fallback: bool = True) -> dict:
    if not isinstance(result, dict):
        result = {}

    direction = str(result.get("main_direction") or "").strip()
    needs_concrete_direction = _is_invalid_calendar_label(direction)
    needs_semantic_override = _is_generic_calendar_label(direction)
    fallback_result = None
    if (needs_concrete_direction or needs_semantic_override) and allow_rule_fallback:
        fallback_result = _minimal_fallback_analysis_legacy_body(event_title, event_summary)
        fallback_direction = str((fallback_result or {}).get("main_direction") or "").strip()
        if not _is_invalid_calendar_label(fallback_direction) and not _is_generic_calendar_label(fallback_direction):
            result = fallback_result
            direction = fallback_direction
            needs_concrete_direction = False
            needs_semantic_override = False

    if allow_rule_fallback and not needs_concrete_direction and not needs_semantic_override:
        fallback_result = fallback_result or _minimal_fallback_analysis_legacy_body(event_title, event_summary)
        if _should_prefer_title_semantics(result, fallback_result):
            result = fallback_result
            direction = str(result.get("main_direction") or "").strip()

    if needs_semantic_override and not _has_policy_catalyst_evidence(f"{event_title} {event_summary}"):
        result = _generic_calendar_analysis(
            event_title,
            event_summary,
            reason=str(result.get("trading_logic") or "").strip(),
        )
        direction = str(result.get("main_direction") or "").strip()
        needs_concrete_direction = False
        needs_semantic_override = False

    if needs_concrete_direction:
        generic_result = _generic_calendar_analysis(
            event_title,
            event_summary,
            reason=str(result.get("trading_logic") or "").strip(),
        )
        preserved = {
            key: value
            for key, value in result.items()
            if key not in ("main_direction", "related_sectors") and value not in (None, "", [])
        }
        result = {**generic_result, **preserved}
        direction = str(generic_result.get("main_direction") or "").strip()

    related_sectors = _dedupe_valid_calendar_sectors(result.get("related_sectors"))
    if not related_sectors:
        related_sectors = [direction] if not _is_invalid_calendar_label(direction) else list(GENERIC_CALENDAR_SECTORS)

    normalized = dict(result)
    normalized["main_direction"] = direction if not _is_invalid_calendar_label(direction) else PENDING_CALENDAR_DIRECTION
    normalized["related_sectors"] = related_sectors
    normalized["trading_logic"] = str(normalized.get("trading_logic") or "事件催化，需结合盘面资金确认").strip()
    normalized["expectation"] = str(normalized.get("expectation") or infer_expectation(f"{event_title} {event_summary}")).strip()
    normalized["confidence"] = str(normalized.get("confidence") or "低").strip()
    return normalized


def analyze_event_sector(event_title, event_summary="", xuangubao_data=None, hot_rank_data=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _analyze_event_sector_legacy_body(
            event_title,
            event_summary=event_summary,
            xuangubao_data=xuangubao_data,
            hot_rank_data=hot_rank_data,
        )
    finally:
        _restore_runtime_bindings(previous)


def _minimal_fallback_analysis_legacy_body(event_title: str, event_summary: str = "") -> dict:
    full_text = f"{event_title} {event_summary}".lower()

    if any(term in full_text for term in ["fomc", "美联储", "利率决议", "经济预期摘要", "降息", "加息"]):
        return {
            "main_direction": "金融流动性",
            "related_sectors": ["美元流动性", "黄金", "银行", "券商", "汇率"],
            "trading_logic": "涉及全球利率和流动性预期，主要影响金融、黄金和风险偏好",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["逆回购", "mlf", "shibor", "同业存单", "流动性", "央行公开市场"]):
        return {
            "main_direction": "金融流动性",
            "related_sectors": ["银行", "券商", "国债期货", "货币政策"],
            "trading_logic": "涉及公开市场或资金面事件，主要影响流动性预期和金融板块风险偏好",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["数字金融", "金融安全", "金融科技", "数字货币", "稳定币", "跨境支付"]):
        return {
            "main_direction": "金融流动性",
            "related_sectors": ["金融科技", "数字货币", "跨境支付", "银行", "券商"],
            "trading_logic": "涉及数字金融或金融安全议题，映射到金融科技与金融流动性链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["amd", "英伟达", "gpu", "ai开发者日", "智算", "算力", "数据中心", "液冷", "服务器"]):
        return {
            "main_direction": "AI算力",
            "related_sectors": ["AI芯片", "服务器", "液冷", "数据中心", "光模块"],
            "trading_logic": "涉及AI算力基础设施或芯片平台事件，优先映射到算力产业链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["联想", "天禧ai", "ai pc", "ai电脑", "ai手机", "ai终端", "端侧ai", "claw"]):
        return {
            "main_direction": "AI终端",
            "related_sectors": ["AI PC", "消费电子", "端侧AI", "智能硬件"],
            "trading_logic": "涉及AI终端产品升级，映射到端侧AI和消费电子链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["google i/o", "谷歌开发者", "aigc", "人工智能技术大会", "agentarts", "智能体", "meta", "ai应用", "生成式ai", "ai峰会", "ai技术论坛", "金蝶ai", "ai生态"]):
        return {
            "main_direction": "AI应用",
            "related_sectors": ["AI应用", "大模型", "智能体", "多模态"],
            "trading_logic": "涉及AI应用、开发者生态或智能体平台事件，映射到AI应用链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["小米汽车", "yu7", "新车型", "整车上市", "汽车上市", "新车上市"]):
        return {
            "main_direction": "汽车产业链",
            "related_sectors": ["整车", "汽车零部件", "智能驾驶", "新能源车"],
            "trading_logic": "涉及汽车新品上市或车企产品周期，映射到整车、零部件和智能驾驶链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["汽车产业链", "汽车供应链", "汽车及供应链", "中汽协", "汽车产业生态"]):
        return {
            "main_direction": "汽车产业链",
            "related_sectors": ["整车", "汽车零部件", "智能驾驶", "机器人", "工业自动化"],
            "trading_logic": "涉及汽车产业链生态和供应链协同，主线映射到汽车，制造端可联动机器人和自动化",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["无人机", "低空", "eVTOL".lower(), "飞行汽车"]):
        return {
            "main_direction": "低空经济",
            "related_sectors": ["无人机", "eVTOL", "飞行汽车", "空管系统"],
            "trading_logic": "涉及无人机/低空产业活动，映射到低空经济链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["绿色燃料", "绿色燃料未来论坛", "氢燃料", "生物燃料", "可持续燃料", "绿色能源"]):
        return {
            "main_direction": "新能源",
            "related_sectors": ["氢能源", "生物燃料", "绿色电力", "储能", "能源设备"],
            "trading_logic": "涉及绿色燃料和能源转型议题，映射到新能源、氢能和绿电链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["computex", "台北电脑展", "电脑展", "pc展", "消费电子展"]):
        return {
            "main_direction": "消费电子",
            "related_sectors": ["AI PC", "半导体", "存储", "散热", "消费电子"],
            "trading_logic": "涉及PC和消费电子新品/供应链展示，映射到消费电子与AI PC链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["spacex", "星舰", "火箭发射", "商业航天", "卫星互联网"]):
        return {
            "main_direction": "商业航天",
            "related_sectors": ["商业航天", "卫星互联网", "火箭发射", "航天装备"],
            "trading_logic": "涉及商业航天公司、火箭发射或上市融资事件，映射到商业航天链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["美团", "本地生活", "外卖", "即时零售", "到店酒旅"]):
        return {
            "main_direction": "本地生活",
            "related_sectors": ["平台经济", "本地生活", "即时零售", "酒旅消费", "外卖配送"],
            "trading_logic": "涉及互联网平台财报或本地生活业务，映射到平台经济和服务消费链",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["世界杯", "足球联赛", "体育场", "体育赛事", "东北超", "城市足球"]):
        return {
            "main_direction": "文旅体育",
            "related_sectors": ["体育产业", "赛事运营", "文化传媒", "文旅消费"],
            "trading_logic": "涉及体育赛事和线下文旅消费场景，映射到体育、文化传媒和文旅消费链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["半导体", "集微", "集成电路", "芯片大会", "晶圆", "先进封装"]):
        return {
            "main_direction": "半导体",
            "related_sectors": ["半导体设备", "半导体材料", "先进封装", "存储芯片"],
            "trading_logic": "涉及半导体产业会议或技术生态，映射到半导体链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["天微电子", "电子元器件", "元器件", "传感器", "电子产品价格上调"]) or ("电子" in full_text and any(term in full_text for term in ["价格上调", "产品价格", "涨价", "调价"])):
        return {
            "main_direction": "电子元器件",
            "related_sectors": ["电子元器件", "半导体元件", "传感器", "消费电子"],
            "trading_logic": "涉及电子元器件产品涨价或供需变化，映射到电子元器件链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["临床肿瘤", "asco", "世界卫生大会", "医药", "医疗", "创新药", "肿瘤"]):
        return {
            "main_direction": "医药医疗",
            "related_sectors": ["创新药", "医疗器械", "CXO", "生物医药"],
            "trading_logic": "涉及医疗卫生或肿瘤学会议，映射到医药医疗链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["畜牧", "养殖", "饲料", "生猪", "禽"]):
        return {
            "main_direction": "农牧养殖",
            "related_sectors": ["养殖业", "饲料", "动物保健", "农产品"],
            "trading_logic": "涉及畜牧养殖行业活动，映射到农牧产业链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["光谷", "光电子", "光博会", "光通信", "6g", "5g", "cpo", "光模块", "光芯片"]):
        return {
            "main_direction": "光通信",
            "related_sectors": ["光模块", "CPO", "光芯片", "光通信设备"],
            "trading_logic": "涉及光电子/光通信产业活动，映射到光通信链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["工程机械", "建筑及工程机械", "工程装备", "矿山机械"]):
        return {
            "main_direction": "工程机械",
            "related_sectors": ["工程机械", "建筑机械", "出口链", "机械设备"],
            "trading_logic": "涉及工程机械展会或出口场景，映射到工程机械链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["世界智能产业", "智能产业博览会", "智能制造", "工业互联网"]):
        return {
            "main_direction": "智能制造",
            "related_sectors": ["智能制造", "工业互联网", "机器人", "自动化"],
            "trading_logic": "涉及智能产业或制造业数字化活动，映射到智能制造链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["华为云", "短信服务", "阿里云", "云服务", "云计算", "云通信"]):
        return {
            "main_direction": "云计算",
            "related_sectors": ["云服务", "云通信", "数字经济", "软件服务"],
            "trading_logic": "涉及云服务价格或平台变化，映射到云计算和软件服务链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["数据周", "数据要素", "数据合作", "全球数字合作", "数字合作", "数据交易"]):
        return {
            "main_direction": "数字经济",
            "related_sectors": ["数据要素", "数字经济", "云计算", "软件服务", "网络安全"],
            "trading_logic": "涉及数据合作或数据要素议题，映射到数字经济链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["开源中国", "开源世界", "开源软件", "开源生态", "开源鸿蒙"]):
        return {
            "main_direction": "软件服务",
            "related_sectors": ["软件服务", "信创", "开发工具", "操作系统", "数字经济"],
            "trading_logic": "涉及开源软件生态会议，映射到软件服务和信创链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["openvan", "无人物流车", "无人配送车", "智能物流车"]):
        return {
            "main_direction": "汽车产业链",
            "related_sectors": ["商用车", "智能驾驶", "物流车", "汽车零部件"],
            "trading_logic": "涉及车企无人化物流产品发布，映射到商用车和智能驾驶链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["工业气体", "气体产业链", "气体展", "ig china"]):
        return {
            "main_direction": "化工材料",
            "related_sectors": ["工业气体", "电子特气", "化工材料", "半导体材料"],
            "trading_logic": "涉及工业气体产业链展会，映射到化工材料和电子特气链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["网络文明", "网络安全", "数字治理", "内容治理"]):
        return {
            "main_direction": "网络安全",
            "related_sectors": ["网络安全", "数字治理", "内容安全", "信创"],
            "trading_logic": "涉及网络治理和数字生态会议，映射到网络安全/数字治理链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["贸促会", "贸易投资", "apec", "亚太经合", "贸易部长"]):
        return {
            "main_direction": "外贸投资",
            "related_sectors": ["外贸", "跨境支付", "港口航运", "供应链服务"],
            "trading_logic": "涉及贸易投资或区域经贸会议，映射到外贸和跨境链",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["普京", "中俄", "俄罗斯总统", "国事访问"]):
        return {
            "main_direction": "中俄贸易",
            "related_sectors": ["中俄贸易", "跨境支付", "能源贸易", "港口航运"],
            "trading_logic": "涉及中俄关系或访问事件，映射到中俄贸易和跨境链",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["圣彼得堡国际经济论坛", "夏季达沃斯", "达沃斯论坛", "国际经济论坛"]):
        return {
            "main_direction": "宏观经济",
            "related_sectors": ["宏观经济", "外贸投资", "顺周期", "金融"],
            "trading_logic": "涉及国际经济论坛或宏观议题，主要用于观察宏观预期和顺周期风险偏好",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["供应链促进博览会", "供应链博览会", "国际供应链"]):
        return {
            "main_direction": "供应链服务",
            "related_sectors": ["供应链服务", "物流", "跨境贸易", "港口航运"],
            "trading_logic": "涉及供应链展会和产业协同，映射到供应链服务、物流和外贸链",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["国民经济运行", "经济运行情况", "统计局", "国新办"]):
        return {
            "main_direction": "宏观经济",
            "related_sectors": ["顺周期", "金融", "消费", "周期资源"],
            "trading_logic": "涉及宏观数据披露，主要用于判断经济预期和顺周期风险偏好",
            "expectation": "中性",
            "confidence": "中",
        }
    if any(term in full_text for term in ["lme", "铅", "锌", "铜", "铝", "镍", "锡", "小金属", "有色金属"]):
        return {
            "main_direction": "有色金属",
            "related_sectors": ["铅锌", "小金属", "有色金属", "期货"],
            "trading_logic": "涉及LME金属合约规则或价格约束，映射到有色金属和小金属链",
            "expectation": infer_expectation(full_text),
            "confidence": "中",
        }
    if any(term in full_text for term in ["原油", "成品油", "油价", "石油", "燃油", "opec", "伊朗", "iea"]):
        return {
            "main_direction": "原油",
            "related_sectors": ["原油", "油气开采", "石油化工", "大宗商品", "成品油"],
            "trading_logic": "涉及原油、成品油或能源机构报告，映射到原油和大宗商品链",
            "expectation": "根据具体事件判断",
            "confidence": "中",
        }
    if any(term in full_text for term in ["包装", "印刷", "纸箱"]):
        return {
            "main_direction": "消费",
            "related_sectors": ["包装印刷", "轻工制造"],
            "trading_logic": "涉及包装行业发展，利好相关产业链",
            "expectation": "根据具体事件判断",
            "confidence": "中",
        }
    if any(term in full_text for term in ["机床", "数控", "工业母机", "装备制造"]):
        return {
            "main_direction": "机械设备",
            "related_sectors": ["工业母机", "机床", "自动化", "人形机器人"],
            "trading_logic": "涉及机床/工业设备展览，利好装备制造及机器人产业链",
            "expectation": "根据具体事件判断",
            "confidence": "中",
        }
    if any(term in full_text for term in ["海峡", "台湾", "国台办", "两岸", "闽台", "对台", "台海"]):
        return {
            "main_direction": "海峡概念",
            "related_sectors": ["福建板块", "平潭综合实验区", "两岸金融"],
            "trading_logic": "涉及两岸关系事件，利好福建及海峡相关板块",
            "expectation": "根据具体事件判断",
            "confidence": "中",
        }
    if any(term in full_text for term in ["消防", "救援", "应急", "防火", "灭火"]):
        return {
            "main_direction": "消防设备",
            "related_sectors": ["消防设备", "应急救援", "安防"],
            "trading_logic": "涉及消防/应急政策，利好消防设备产业链",
            "expectation": "根据具体事件判断",
            "confidence": "中",
        }
    if any(term in full_text for term in ["机器人", "具身智能", "减速器", "伺服电机"]):
        return {
            "main_direction": "人形机器人",
            "related_sectors": ["减速器", "伺服电机", "传感器", "执行器"],
            "trading_logic": "涉及机器人产业进展，利好人形机器人产业链",
            "expectation": "根据具体事件判断",
            "confidence": "中",
        }

    return {
        "main_direction": "其他",
        "related_sectors": [],
        "trading_logic": "事件产业链方向不明确",
        "expectation": "中性",
        "confidence": "低",
    }


def _ai_analyze_event_sectors_legacy_body(event_title, event_summary="", *, print_fn=print):
    global _llm_call_stats
    start_time = time.time()
    if not ENABLE_REMOTE_CALENDAR_LLM:
        result = minimal_fallback_analysis(event_title, event_summary)
        print_fn(f"  [本地规则] '{event_title[:30]}...' -> {result.get('main_direction')}")
        return result

    try:
        client = _default_get_llm_service()
        result = client.analyze_event_sectors(event_title, event_summary)

        elapsed = time.time() - start_time
        _llm_call_stats["total_calls"] += 1
        _llm_call_stats["total_time"] += elapsed
        _llm_call_stats["event_analysis_calls"] += 1
        _llm_call_stats["event_analysis_time"] += elapsed

        normalized_result = normalize_calendar_ai_analysis(result, event_title, event_summary)
        raw_direction = result.get("main_direction") if isinstance(result, dict) else None
        if normalized_result.get("main_direction") != raw_direction:
            print_fn(f"  [AI兜底] '{event_title[:30]}...' -> {normalized_result['main_direction']}（日历归一化）")
        else:
            print_fn(f"  [AI分析] '{event_title[:30]}...' -> {normalized_result.get('main_direction')}（置信度:{normalized_result.get('confidence', '中')}）")

        return normalized_result
    except Exception as error:
        elapsed = time.time() - start_time
        print_fn(f"[ai_analyze_event_sectors] 远程LLM失败({elapsed:.2f}s)，使用本地规则: {error}")
        return minimal_fallback_analysis(event_title, event_summary)


def _llm_analyze_event_legacy_body(event_text):
    return ai_analyze_event_sectors(event_text)


def _fallback_sector_analysis_legacy_body(text):
    if any(term in text for term in ["gdp", "cpi", "ppi", "pmi", "非农", "就业", "失业", "通胀", "通缩", "经济数据", "经济指标", "统计", "公布", "财报", "业绩"]):
        if any(term in text for term in ["cpi", "ppi", "通胀", "物价"]):
            return "消费"
        if any(term in text for term in ["gdp", "pmi", "工业"]):
            return "周期资源"
        return "金融"
    if any(term in text for term in ["监管", "证监会", "银保监会", "央行", "政策", "新规", "办法", "条例"]):
        return "金融"
    if any(term in text for term in ["关税", "贸易", "出口", "进口", "海关总署", "中美", "欧盟"]):
        return "周期资源"
    if any(term in text for term in ["峰会", "论坛", "大会", "会议", " expo", " conference"]):
        if any(term in text for term in ["ai", "智能", "科技", "数字"]):
            return "AI算力"
        if any(term in text for term in ["医疗", "医药", "健康"]):
            return "医药医疗"
        if any(term in text for term in ["能源", "环境", "气候", "碳"]):
            return "新能源"
        if any(term in text for term in ["金融", "经济", "投资", "银行"]):
            return "金融"
    if any(term in text for term in ["发布", "新品", "上市", "预售", "发布会"]):
        if any(term in text for term in ["车", "汽车", "电动"]):
            return "汽车产业链"
        if any(term in text for term in ["手机", "电脑", "平板", "耳机", "手表"]):
            return "消费电子"
    return None


def _infer_related_sectors_legacy_body(text):
    sectors = []
    sector_mapping = {
        "ai": ["AI应用", "大模型", "算力", "AI芯片"],
        "医药": ["化学制药", "生物制品", "医疗器械", "CXO"],
        "光通信": ["光模块", "CPO", "光芯片", "光纤光缆"],
        "机器人": ["人形机器人", "减速器", "伺服电机", "传感器"],
        "新能源": ["光伏", "储能", "锂电池", "电网设备"],
        "半导体": ["半导体设备", "半导体材料", "存储芯片", "先进封装"],
        "汽车": ["汽车零部件", "智能驾驶", "整车", "锂电池"],
        "消费电子": ["手机产业链", "面板", "VR/AR", "穿戴设备"],
    }
    for key, vals in sector_mapping.items():
        if key in text.lower():
            sectors.extend(vals)
    return list(set(sectors))[:5] if sectors else []


def _generate_related_sectors_legacy_body(direction, text=""):
    sector_map = {
        "AI算力": ["AI芯片", "服务器", "液冷", "数据中心", "云计算", "光模块"],
        "医药医疗": ["创新药", "CXO", "化学制药", "医疗器械", "中药", "生物制品"],
        "光通信": ["光模块", "CPO", "光芯片", "光纤光缆", "通信设备"],
        "人形机器人": ["减速器", "伺服电机", "传感器", "执行器", "灵巧手"],
        "新能源": ["光伏组件", "储能", "锂电池", "电网设备", "逆变器"],
        "半导体": ["半导体设备", "光刻胶", "存储芯片", "先进封装", "EDA"],
        "汽车产业链": ["汽车零部件", "智能驾驶", "激光雷达", "整车", "充电桩"],
        "消费电子": ["手机产业链", "面板", "VR/AR", "穿戴设备", "折叠屏"],
        "商业航天": ["卫星制造", "火箭发射", "卫星互联网", "遥感导航", "地面设备"],
        "周期资源": ["有色金属", "稀土永磁", "化工新材料", "贵金属", "能源金属"],
        "金融": ["券商", "银行", "保险", "金融科技", "数字货币"],
        "消费": ["白酒", "免税", "旅游酒店", "食品饮料", "家电"],
        "房地产": ["房地产开发", "建材", "物业管理", "家居", "基建"],
        "军工": ["航空装备", "航天装备", "船舶", "军工电子", "地面兵装"],
    }
    return sector_map.get(direction, ["相关产业链标的"])


def _generate_trading_logic_legacy_body(direction, text):
    logic_map = {
        "AI算力": "AI产业核心基础设施，算力需求持续增长，大模型迭代驱动",
        "医药医疗": "政策驱动+防守属性，博弈医药改革/创新药政策预期",
        "光通信": "AI算力基建受益方向，高速光互联需求爆发，海外订单驱动",
        "人形机器人": "智能制造新方向，特斯拉/华为等产业巨头布局，商业化加速",
        "新能源": "能源转型大趋势，政策+需求双驱动，关注产能出清进度",
        "半导体": "国产替代加速，产业链自主可控，设备材料率先受益",
        "汽车产业链": "新能源汽车渗透率提升，智能化加速，出海逻辑顺畅",
        "消费电子": "新品周期驱动，AI终端渗透预期，华为/苹果产业链催化",
        "商业航天": "卫星互联网建设加速，商业航天政策放开，星座组网需求",
        "周期资源": "供需格局变化，涨价预期驱动，关注库存周期和产能变化",
        "金融": "政策宽松预期，资本市场改革受益，市场活跃度提升",
        "消费": "经济复苏预期，节假日/旺季催化，关注政策刺激力度",
        "房地产": "政策边际放松，销售数据改善预期，城中村改造催化",
        "军工": "国防预算增长，装备更新周期，人事调整落地后订单恢复",
    }
    base_logic = logic_map.get(direction, "产业链景气度变化，需结合资金流向判断")
    if "发布" in text or "出台" in text:
        base_logic += "，政策发布短期催化"
    elif "会议" in text or "峰会" in text:
        base_logic += "，事件驱动短期博弈"
    elif "获批" in text or "通过" in text:
        base_logic += "，审批进展利好兑现"
    return base_logic


def _infer_expectation_legacy_body(text):
    positive = ["利好", "发布", "启动", "开幕", "获批", "突破", "增长", "支持", "鼓励", "推进", "加速", "通过", "落地", "实施", "提升", "扩大"]
    negative = ["收紧", "监管", "限制", "禁止", "下滑", "下降", "利空", "风险", "暂停", "终止", "取消", "调查", "处罚", "违规", "暴雷"]
    pos_count = sum(1 for p in positive if p in text)
    neg_count = sum(1 for n in negative if n in text)
    if pos_count > neg_count:
        return "利好"
    if neg_count > pos_count:
        return "利空"
    return "中性"


def _has_clear_signal_legacy_body(text):
    return any(s in text for s in ["发布", "启动", "开幕", "获批", "利好", "政策", "大会", "会议"])


def _analyze_event_sector_legacy_body(event_title, event_summary="", xuangubao_data=None, hot_rank_data=None):
    if xuangubao_data:
        for news in xuangubao_data.get("xuangubao_news", [])[:20]:
            if event_title.lower() in news.get("title", "").lower() or event_title.lower() in news.get("summary", "").lower():
                news_summary = news.get("summary", "")
                for sector_keyword in [
                    "绿电", "电力", "半导体", "芯片", "消费电子", "轨交", "铁路", "航天", "卫星",
                    "AI", "人工智能", "液冷", "服务器", "算力", "光伏", "储能", "机器人",
                    "医药", "医疗", "银行", "金融", "汽车", "通信", "有色", "金属", "煤炭", "农业",
                    "旅游", "食品", "饮料", "地产", "建筑", "传媒", "教育", "环保", "军工", "化工",
                ]:
                    if sector_keyword in news_summary:
                        return sector_keyword

    if hot_rank_data:
        for stock in hot_rank_data[:10]:
            concepts = stock.get("concepts", [])
            if concepts:
                for concept in concepts:
                    if concept in event_title:
                        return concept

    title_lower = event_title.lower()
    mapping = [
        (["AI应用", "人工智能应用", "短剧", "AIGC", "生成式AI", "ChatGPT", "大模型", "文生视频", "多模态"], "AI应用"),
        (["算力", "计算", "云计算", "数据中心", "服务器", "液冷", "AI芯片", "智算中心"], "算力"),
        (["光刻机", "光刻胶", "玻璃布", "PCB", "封装", "测试设备", "半导体材料", "晶圆制造", "先进封装"], "半导体设备材料"),
        (["核聚变", "可控核聚变", "人造太阳", "特高压", "电网设备", "电气设备", "智能电网", "输配电"], "绿色电力"),
        (["航天", "卫星", "火箭", "商业航天", "太空", "飞船", "大飞机", "军工", "北斗", "导弹"], "航天军工"),
        (["人形机器人", "具身智能", "减速器", "伺服电机", "机器人"], "机器人"),
        (["无人驾驶", "自动驾驶", "智能驾驶", "激光雷达", "车载芯片", "新能源车"], "新能源汽车"),
        (["脑机接口", "脑科学", "神经接口", "医疗AI", "创新药", "CXO"], "医药生物"),
        (["光电", "光学", "激光", "LED", "显示面板", "光通信", "CPO", "光模块"], "光电"),
        (["冰雪经济", "户外", "露营", "滑雪", "旅游", "景区", "免税"], "消费"),
        (["数字金融", "稳定币", "数字货币", "非银金融", "支付", "金融科技"], "金融"),
        (["海峡", "两岸", "福建", "台湾", "平潭", "闽台"], "海峡概念"),
        (["有色", "稀土", "稀土永磁", "化工", "化学原料", "新材料"], "周期资源"),
        (["绿电", "电力", "电网", "发电", "新能源", "光伏", "风电", "储能", "能源", "碳中和"], "绿电"),
        (["半导体", "芯片", "集成电路", "存储芯片", "晶圆"], "半导体"),
        (["消费电子", "苹果", "华为", "小米", "手机", "耳机", "穿戴", "电子"], "消费电子"),
        (["轨交", "铁路", "高铁", "地铁", "轨道交通", "中车"], "轨交设备"),
        (["医药", "医疗", "生物", "疫苗", "创新药"], "医药"),
        (["银行", "金融", "券商", "保险", "证券"], "银行"),
        (["汽车", "新能源车", "电动车", "自动驾驶"], "汽车"),
        (["旅游", "团队旅游", "出境游", "入境游", "景区", "酒店", "免税", "旅行社", "文旅", "休闲"], "旅游"),
        (["食品", "饮料", "白酒", "啤酒", "乳业", "调味品", "预制菜", "餐饮"], "食品饮料"),
        (["房地产", "地产", "物业", "住房", "楼市", "保障房"], "房地产"),
        (["建筑", "建材", "水泥", "玻璃", "钢结构", "基建"], "建筑建材"),
        (["传媒", "娱乐", "游戏", "影视", "短视频", "直播", "广告"], "传媒娱乐"),
        (["教育", "培训", "职业", "学校", "在线教育"], "教育"),
        (["环保", "环境", "污水处理", "垃圾处理", "碳中和", "碳交易"], "环保"),
        (["军工", "国防", "武器", "装备", "舰船", "战机"], "军工"),
        (["化工", "化学", "化纤", "塑料", "橡胶", "农药", "化肥"], "化工"),
        (["轻工", "造纸", "包装", "家具", "家电", "纺织", "服装"], "轻工制造"),
        (["电力设备", "变压器", "开关", "电缆", "输配电"], "电力设备"),
        (["通信", "5G", "6G", "光通信", "物联网", "运营商"], "通信"),
        (["计算机", "软件", "信创", "网络安全", "大数据", "区块链"], "计算机"),
    ]
    for keywords, label in mapping:
        if any(keyword in title_lower for keyword in keywords):
            return label
    return PENDING_CALENDAR_DIRECTION
