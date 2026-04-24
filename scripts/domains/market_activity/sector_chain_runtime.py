from __future__ import annotations

import time

__all__ = [
    "ai_analyze_sector_relationships",
    "ai_group_concepts_into_chains",
]

_MISSING = object()
DISPLAY_MVP_MODE = False
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


def get_llm_service():
    return None


def ai_analyze_sector_relationships(sector_list, context_info="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _ai_analyze_sector_relationships_legacy_body(sector_list, context_info=context_info)
    finally:
        _restore_runtime_bindings(previous)


def ai_group_concepts_into_chains(concepts_list, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _ai_group_concepts_into_chains_legacy_body(concepts_list)
    finally:
        _restore_runtime_bindings(previous)


def _ai_analyze_sector_relationships_legacy_body(sector_list, context_info=""):
    global _llm_call_stats
    start_time = time.time()

    try:
        client = get_llm_service()
        result = client.analyze_sector_relationships(sector_list, context_info)

        elapsed = time.time() - start_time
        _llm_call_stats["total_calls"] += 1
        _llm_call_stats["total_time"] += elapsed
        _llm_call_stats["sector_analysis_calls"] += 1
        _llm_call_stats["sector_analysis_time"] += elapsed

        return result
    except Exception as error:
        elapsed = time.time() - start_time
        print(f"[ai_analyze_sector_relationships] LLM调用失败({elapsed:.2f}s)，使用兜底方案: {error}")
        return {"groups": [], "insights": "LLM分析失败，无法生成产业链洞察"}


def _ai_group_concepts_into_chains_legacy_body(concepts_list):
    if not concepts_list:
        return {}

    if DISPLAY_MVP_MODE:
        ai_result = _llm_sector_analysis_legacy_body(concepts_list, "MVP模式使用本地归链")
    else:
        ai_result = ai_analyze_sector_relationships(concepts_list)
        if not ai_result.get("groups"):
            ai_result = _llm_sector_analysis_legacy_body(concepts_list, "LLM失败后回退本地归链")

    chains = {}
    for group in ai_result.get("groups", []):
        chain_name = group["name"]
        sectors = group["sectors"]
        chains[chain_name] = sectors
    return chains


def _llm_sector_analysis_legacy_body(sectors, context):
    industry_chains = {
        "医药医疗": {
            "keywords": ["医药", "医疗", "制药", "生物", "CXO", "CRO", "中药", "化学制药", "生物制品", "医疗器械", "医药商业", "医药流通", "医疗服务", "创新药", "重组蛋白", "仿制药", "疫苗"],
            "segments": {
                "研发服务": ["CRO", "CXO", "医疗研发外包"],
                "药品制造": ["化学制药", "生物制品", "中药", "创新药", "重组蛋白", "仿制药", "疫苗"],
                "流通销售": ["医药商业", "医药流通"],
                "医疗服务": ["医疗服务", "医疗器械", "其他医疗服务", "创新医疗服务"],
            },
        },
        "光通信": {
            "keywords": ["光通信", "光模块", "光纤", "光缆", "CPO", "通信线缆", "光芯片", "光器件", "光引擎", "硅光", "激光雷达", "光通信模块", "通信网络设备", "OCS", "全光交换"],
            "segments": {
                "传输介质": ["光纤", "光缆", "通信线缆", "通信线缆及配套"],
                "核心器件": ["光模块", "光通信模块", "光芯片", "光器件", "光引擎", "CPO", "共封装光学"],
                "系统设备": ["光通信", "通信网络设备", "通信网络设备及器件", "OCS", "全光交换"],
                "终端应用": ["激光雷达"],
            },
        },
        "AI算力": {
            "keywords": ["算力", "AI芯片", "服务器", "数据中心", "云计算", "液冷", "存储芯片", "半导体", "芯片", "通信设备", "通信"],
            "segments": {
                "芯片算力": ["AI芯片", "芯片", "半导体", "存储芯片"],
                "基础设施": ["服务器", "数据中心", "云计算", "液冷", "液冷服务器"],
                "网络通信": ["通信设备", "通信", "算力"],
            },
        },
        "人形机器人": {
            "keywords": ["机器人", "人形机器人", "具身智能", "减速器", "伺服电机", "执行器", "传感器", "电机"],
            "segments": {
                "核心零部件": ["减速器", "伺服电机", "执行器", "传感器", "电机"],
                "整机系统": ["机器人", "人形机器人", "具身智能"],
            },
        },
        "新能源": {
            "keywords": ["光伏", "储能", "锂电池", "电池", "电力", "电网", "风电", "核电", "氢能源", "固态电池", "电网设备", "绿色电力", "绿电"],
            "segments": {
                "发电端": ["光伏", "风电", "核电", "氢能源", "绿色电力", "绿电"],
                "储能端": ["储能", "锂电池", "电池", "固态电池"],
                "输配电": ["电力", "电网", "电网设备"],
            },
        },
        "商业航天": {
            "keywords": ["商业航天", "卫星导航", "卫星", "航天", "火箭", "大飞机", "低空"],
            "segments": {
                "核心装备": ["火箭", "大飞机"],
                "通信导航": ["卫星导航", "卫星"],
                "场景应用": ["低空", "商业航天"],
            },
        },
        "汽车产业链": {
            "keywords": ["汽车", "汽车零部件", "整车", "新能源车", "智能驾驶", "无人驾驶", "车联网"],
            "segments": {
                "整车制造": ["整车", "汽车", "新能源车"],
                "零部件": ["汽车零部件"],
                "智能系统": ["智能驾驶", "无人驾驶", "车联网"],
            },
        },
    }

    matched_groups = {}
    unmatched = []
    for sector in sectors:
        matched = False
        for chain_name, chain_info in industry_chains.items():
            for keyword in chain_info["keywords"]:
                if keyword in sector or sector in keyword:
                    if chain_name not in matched_groups:
                        matched_groups[chain_name] = {
                            "sectors": [],
                            "segments": {key: [] for key in chain_info["segments"].keys()},
                        }
                    matched_groups[chain_name]["sectors"].append(sector)

                    for segment_name, segment_keywords in chain_info["segments"].items():
                        for segment_keyword in segment_keywords:
                            if segment_keyword in sector or sector in segment_keyword:
                                matched_groups[chain_name]["segments"][segment_name].append(sector)
                                break

                    matched = True
                    break
            if matched:
                break
        if not matched:
            unmatched.append(sector)

    groups = []
    for chain_name, data in matched_groups.items():
        segments_with_data = {key: value for key, value in data["segments"].items() if value}
        if segments_with_data:
            segment_desc = "、".join([f"{key}({'、'.join(value[:2])}等)" for key, value in list(segments_with_data.items())[:2]])
            reason = f"同属{chain_name}产业链，涵盖{segment_desc}"
        else:
            reason = f"同属{chain_name}大方向"

        if chain_name == "医药医疗":
            investment_logic = "防守属性，博弈医药改革/创新药政策预期"
        elif chain_name == "光通信":
            investment_logic = "AI算力基建受益方向，高速光互联需求驱动"
        elif chain_name == "AI算力":
            investment_logic = "AI产业核心基础设施，算力需求持续增长"
        elif chain_name == "人形机器人":
            investment_logic = "智能制造新方向，产业政策支持"
        elif chain_name == "新能源":
            investment_logic = "能源转型大趋势，政策+需求双驱动"
        elif chain_name == "汽车产业链":
            investment_logic = "新能源汽车渗透率提升，智能化加速"
        elif chain_name == "商业航天":
            investment_logic = "军工外延与低空场景共振，资金容易围绕卫星/飞行器链条做扩散"
        else:
            investment_logic = "产业链景气度提升，资金关注度高"

        groups.append(
            {
                "name": chain_name,
                "sectors": data["sectors"],
                "reason": reason,
                "investment_logic": investment_logic,
            }
        )

    for sector in unmatched:
        groups.append(
            {
                "name": sector,
                "sectors": [sector],
                "reason": "独立板块，暂无明确产业链关联",
                "investment_logic": "需单独分析其驱动逻辑",
            }
        )

    insights = _generate_ai_insights_legacy_body(groups, context)
    return {"groups": groups, "insights": insights}


def _generate_ai_insights_legacy_body(groups, context):
    del context
    insights = []

    if len(groups) >= 2:
        insights.append(f"资金在博弈{len(groups)}个大方向：")
        for group in groups:
            insights.append(f"- **{group['name']}**：{group['investment_logic']}")

    has_defensive = any(group["name"] in ["医药医疗"] for group in groups)
    has_growth = any(group["name"] in ["光通信", "AI算力", "人形机器人"] for group in groups)

    if has_defensive and has_growth:
        insights.append("\n**配置特征**：资金在'防守+进攻'双向布局，成长与价值兼顾")
    elif has_defensive:
        insights.append("\n**配置特征**：偏向防守，市场风险偏好较低")
    elif has_growth:
        insights.append("\n**配置特征**：偏向进攻，看好科技成长方向")

    mainline_consistency = "分散" if len(groups) > 2 else "相对集中"
    insights.append(
        f"\n**主线判断**：资金聚集{mainline_consistency}，"
        f"{'缺乏明确主线，需观察哪个方向能走出持续性' if len(groups) > 2 else '有明确主线方向'}"
    )
    return "\n".join(insights)
