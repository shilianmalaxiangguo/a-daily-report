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
]

_MISSING = object()
_llm_call_stats = {
    "total_calls": 0,
    "total_time": 0.0,
    "event_analysis_calls": 0,
    "event_analysis_time": 0.0,
    "sector_analysis_calls": 0,
    "sector_analysis_time": 0.0,
}


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
        return _minimal_fallback_analysis_legacy_body(event_title, event_summary)
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

    if any(term in full_text for term in ["原油", "油价", "石油", "燃油", "opec", "伊朗"]):
        return {
            "main_direction": "周期资源",
            "related_sectors": ["石油", "能源"],
            "trading_logic": "涉及原油/油价相关事件，影响石油产业链",
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
    if any(term in full_text for term in ["光通信", "6g", "5g", "cpo", "光模块", "光芯片"]):
        return {
            "main_direction": "光通信",
            "related_sectors": ["光模块", "CPO", "光芯片", "通信设备"],
            "trading_logic": "涉及光通信技术/标准进展，利好光通信产业链",
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
    try:
        client = _default_get_llm_service()
        result = client.analyze_event_sectors(event_title, event_summary)

        elapsed = time.time() - start_time
        _llm_call_stats["total_calls"] += 1
        _llm_call_stats["total_time"] += elapsed
        _llm_call_stats["event_analysis_calls"] += 1
        _llm_call_stats["event_analysis_time"] += elapsed

        if result.get("main_direction") == "其他":
            fallback_result = minimal_fallback_analysis(event_title, event_summary)
            if fallback_result.get("main_direction") != "其他":
                print_fn(f"  [AI兜底] '{event_title[:30]}...' -> {fallback_result['main_direction']}（极简规则兜底）")
                return fallback_result
            print_fn(f"  [AI分析] '{event_title[:30]}...' -> 其他（AI无法识别明确产业链）")
        else:
            print_fn(f"  [AI分析] '{event_title[:30]}...' -> {result.get('main_direction')}（置信度:{result.get('confidence', '中')}）")

        return result
    except Exception as error:
        elapsed = time.time() - start_time
        print_fn(f"[ai_analyze_event_sectors] LLM调用失败({elapsed:.2f}s): {error}")
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
    return "其他"
