from __future__ import annotations

import os
import time

__all__ = [
    "ai_analyze_sector_relationships",
    "ai_group_concepts_into_chains",
]

_MISSING = object()
DISPLAY_MVP_MODE = False
ENABLE_REMOTE_SECTOR_LLM = str(os.getenv("A_DAILY_REPORT_ENABLE_REMOTE_SECTOR_LLM", "")).lower() in {
    "1",
    "true",
    "yes",
    "on",
}
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
    context_label = context_info or "本地产业链归并"

    if not ENABLE_REMOTE_SECTOR_LLM:
        return _llm_sector_analysis_legacy_body(sector_list, context_label)

    try:
        client = get_llm_service()
        if client is None:
            raise RuntimeError("远程产业链增强服务未配置")
        result = client.analyze_sector_relationships(sector_list, context_info)
        if not isinstance(result, dict) or not result.get("groups"):
            raise RuntimeError("远程产业链增强返回空结果")

        elapsed = time.time() - start_time
        _llm_call_stats["total_calls"] += 1
        _llm_call_stats["total_time"] += elapsed
        _llm_call_stats["sector_analysis_calls"] += 1
        _llm_call_stats["sector_analysis_time"] += elapsed

        return result
    except Exception as error:
        elapsed = time.time() - start_time
        print(f"[ai_analyze_sector_relationships] 远程增强失败({elapsed:.2f}s)，使用本地归链: {error}")
        return _llm_sector_analysis_legacy_body(sector_list, f"{context_label}；远程增强失败后本地归链")


def _ai_group_concepts_into_chains_legacy_body(concepts_list):
    if not concepts_list:
        return {}

    if DISPLAY_MVP_MODE:
        ai_result = _llm_sector_analysis_legacy_body(concepts_list, "MVP模式使用本地归链")
    else:
        ai_result = ai_analyze_sector_relationships(concepts_list)
        if not ai_result.get("groups"):
            ai_result = _llm_sector_analysis_legacy_body(concepts_list, "远程增强未产出后回退本地归链")

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
        "半导体": {
            "keywords": ["半导体", "芯片", "存储芯片", "HBM", "DRAM", "NAND", "光刻机", "光刻胶", "EDA", "大基金", "大基金系", "先进封装", "封测", "晶圆", "摩尔线程", "国产芯片"],
            "segments": {
                "设计与IP": ["EDA", "芯片", "国产芯片", "摩尔线程"],
                "制造设备": ["光刻机", "晶圆", "半导体设备"],
                "材料": ["光刻胶", "半导体材料"],
                "存储与封测": ["HBM", "DRAM", "NAND", "存储芯片", "先进封装", "封测"],
                "产业资本": ["大基金", "大基金系"],
            },
        },
        "AI算力": {
            "keywords": ["算力", "AI芯片", "服务器", "数据中心", "云计算", "液冷", "通信设备", "通信", "高速连接器", "连接器", "高速铜缆", "铜缆高速连接"],
            "segments": {
                "芯片算力": ["AI芯片"],
                "基础设施": ["服务器", "数据中心", "云计算", "液冷", "液冷服务器"],
                "网络通信": ["通信设备", "通信", "算力", "高速连接器", "连接器", "高速铜缆", "铜缆高速连接"],
            },
        },
        "数字经济": {
            "keywords": ["数字经济", "工业互联网", "物联网", "电子身份证", "人脸识别", "超高清视频", "空间计算", "数据要素", "网络安全", "人工智能", "AIGC", "信创", "软件服务", "电信运营", "运营商"],
            "segments": {
                "数字基础设施": ["工业互联网", "物联网", "数据要素", "电信运营", "运营商"],
                "身份与安全": ["电子身份证", "人脸识别", "网络安全", "信创"],
                "内容与交互": ["超高清视频", "空间计算", "AIGC", "人工智能"],
                "软件服务": ["软件服务"],
            },
        },
        "消费电子": {
            "keywords": ["消费电子", "苹果产业链", "苹果概念", "无线耳机", "耳机", "LED", "MiniLED", "MicroLED", "面板", "家电", "智能音箱", "智能穿戴", "折叠屏", "MR", "VR", "AR"],
            "segments": {
                "品牌链": ["苹果产业链", "苹果概念"],
                "声学与穿戴": ["无线耳机", "耳机", "智能音箱", "智能穿戴"],
                "显示": ["LED", "MiniLED", "MicroLED", "面板"],
                "终端家电": ["家电", "折叠屏", "MR", "VR", "AR"],
            },
        },
        "人形机器人": {
            "keywords": ["机器人", "人形机器人", "具身智能", "减速器", "伺服电机", "执行器", "传感器", "电机"],
            "segments": {
                "核心零部件": ["减速器", "伺服电机", "执行器", "传感器", "电机"],
                "整机系统": ["机器人", "人形机器人", "具身智能"],
            },
        },
        "高端制造": {
            "keywords": ["高端制造", "新型工业化", "机器视觉", "工业母机", "智能制造", "工业自动化", "工控", "数控机床"],
            "segments": {
                "智能制造": ["新型工业化", "智能制造", "工业自动化", "工控"],
                "感知检测": ["机器视觉"],
                "核心设备": ["工业母机", "数控机床"],
            },
        },
        "新能源": {
            "keywords": ["光伏", "储能", "锂电池", "电池", "电力", "电网", "风电", "核电", "氢能源", "固态电池", "电网设备", "绿色电力", "绿电", "碳中和", "碳交易", "节能环保"],
            "segments": {
                "发电端": ["光伏", "风电", "核电", "氢能源", "绿色电力", "绿电"],
                "储能端": ["储能", "锂电池", "电池", "固态电池"],
                "输配电": ["电力", "电网", "电网设备"],
                "双碳政策": ["碳中和", "碳交易", "节能环保"],
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
            "keywords": ["汽车", "汽车零部件", "整车", "新能源车", "新能源汽车", "智能驾驶", "无人驾驶", "车联网", "一体化压铸", "压铸"],
            "segments": {
                "整车制造": ["整车", "汽车", "新能源车", "新能源汽车"],
                "零部件": ["汽车零部件", "一体化压铸", "压铸"],
                "智能系统": ["智能驾驶", "无人驾驶", "车联网"],
            },
        },
        "区域国资": {
            "keywords": ["国资", "上海国资", "浙江国资", "新疆国资", "地方国资", "振兴东北", "东北振兴", "自贸区", "海南自贸", "粤港澳", "长三角", "西部大开发"],
            "segments": {
                "地方国资": ["上海国资", "浙江国资", "新疆国资", "地方国资", "国资"],
                "区域经济": ["振兴东北", "东北振兴", "自贸区", "海南自贸", "粤港澳", "长三角", "西部大开发"],
            },
        },
        "地产基建": {
            "keywords": ["地产", "房地产", "基建", "水泥", "建材", "家居装饰", "陶瓷", "陶瓷产业", "检测检验", "建筑", "工程机械", "装配式建筑"],
            "segments": {
                "地产后周期": ["地产", "房地产", "家居装饰"],
                "建筑材料": ["水泥", "建材", "陶瓷", "陶瓷产业"],
                "工程服务": ["基建", "建筑", "检测检验", "工程机械", "装配式建筑"],
            },
        },
        "化工材料": {
            "keywords": ["化工", "氟化工", "工业气体", "有机硅", "磷化工", "钛白粉", "化纤", "新材料", "碳纤维", "复合材料"],
            "segments": {
                "基础化工": ["化工", "氟化工", "磷化工", "钛白粉", "化纤"],
                "电子/工业材料": ["工业气体", "有机硅", "新材料", "碳纤维", "复合材料"],
            },
        },
        "军工装备": {
            "keywords": ["军工", "航海装备", "船舶", "航母", "航空发动机", "大飞机", "无人机", "低空经济", "卫星导航", "商业航天"],
            "segments": {
                "海空装备": ["航海装备", "船舶", "航母", "航空发动机", "大飞机", "无人机"],
                "空天信息": ["卫星导航", "商业航天"],
                "低空场景": ["低空经济"],
            },
        },
        "食品饮料": {
            "keywords": ["食品饮料", "休闲食品", "代糖", "甜味剂", "白酒", "啤酒", "乳业", "调味品", "预制菜"],
            "segments": {
                "大众消费": ["休闲食品", "预制菜", "调味品"],
                "添加剂": ["代糖", "甜味剂"],
                "酒饮乳品": ["白酒", "啤酒", "乳业"],
            },
        },
        "出海链": {
            "keywords": ["出海", "出海概念", "跨境电商", "外贸", "海外收入", "一带一路"],
            "segments": {
                "外需链": ["出海", "出海概念", "外贸", "海外收入"],
                "跨境渠道": ["跨境电商"],
                "区域合作": ["一带一路"],
            },
        },
        "文旅消费": {
            "keywords": ["文旅", "旅游", "冰雪产业", "体育产业", "赛事经济", "免税"],
            "segments": {
                "旅游休闲": ["文旅", "旅游", "免税"],
                "体育赛事": ["冰雪产业", "体育产业", "赛事经济"],
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
        elif chain_name == "半导体":
            investment_logic = "国产替代与AI硬件周期共振，重点看设备、材料、存储和设计端承接"
        elif chain_name == "AI算力":
            investment_logic = "AI产业核心基础设施，算力需求持续增长"
        elif chain_name == "数字经济":
            investment_logic = "数字化基础设施与AI应用扩散方向，资金偏事件催化与应用落地"
        elif chain_name == "高端制造":
            investment_logic = "制造业升级与智能工厂方向，重点看设备端订单和国产替代弹性"
        elif chain_name == "消费电子":
            investment_logic = "终端创新和品牌链复苏预期，重点看放量订单与新品催化"
        elif chain_name == "人形机器人":
            investment_logic = "智能制造新方向，产业政策支持"
        elif chain_name == "新能源":
            investment_logic = "能源转型大趋势，政策+需求双驱动"
        elif chain_name == "汽车产业链":
            investment_logic = "新能源汽车渗透率提升，智能化加速"
        elif chain_name == "商业航天":
            investment_logic = "军工外延与低空场景共振，资金容易围绕卫星/飞行器链条做扩散"
        elif chain_name == "区域国资":
            investment_logic = "地方国资改革与区域政策预期，更多按事件驱动和资产重估观察"
        elif chain_name == "地产基建":
            investment_logic = "地产后周期和基建稳增长链条，重点看政策落地后的需求修复"
        elif chain_name == "化工材料":
            investment_logic = "周期品价格与新材料需求共振，重点看供需拐点和涨价弹性"
        elif chain_name == "军工装备":
            investment_logic = "装备升级与订单预期驱动，适合观察趋势承接和事件催化"
        elif chain_name == "食品饮料":
            investment_logic = "消费复苏与细分品类景气驱动，更多看业绩弹性和渠道改善"
        elif chain_name == "出海链":
            investment_logic = "外需和海外收入弹性方向，重点看订单、汇率和关税扰动"
        elif chain_name == "文旅消费":
            investment_logic = "服务消费修复与事件催化方向，适合按节假日和赛事预期观察"
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
