def build_entry_plan_priority_discipline_node(context, node_meta=None, node_lookup=None):
    extreme_conviction_list = context.get("extreme_conviction_list", []) or []
    leader_memory_bank = context.get("leader_memory_bank", []) or []

    lines = ["**交易优先级纪律**:"]
    if extreme_conviction_list:
        names = [f"{stock.get('name')}({stock.get('code')})" for stock in extreme_conviction_list]
        lines.append(f"- **重点观察优先**: {', '.join(names)}")
        lines.append("- **先后顺序怎么排**: 先做主线锚定龙，再看普通候选；若重点观察名单全天都不给确认，其余标的宁可继续观察。")
    else:
        lines.append("- **现在先按什么原则**: 没有重点观察的少数标的时，宁可降低频率，也不扩大出手范围。")
    if leader_memory_bank:
        memory_names = [f"{stock.get('name')}({stock.get('code')})" for stock in leader_memory_bank[:3]]
        lines.append(f"- **龙头回看名单**: {', '.join(memory_names)}")
    lines.append("- **盯盘优先级**: 核心可买 > 龙头回看 > 主线盯盘 > 普通观察。没有买入资格，买点到了也只能看。")
    lines.append("- **盘中异动怎么处理**: 绿灯可进入执行层，黄灯保留观察，橙灯先看是否跌得下去，红灯直接取消执行。")
    lines.append("- **纪律补充**: 强者恒强阶段只做领先核心，不为“低位没涨”找理由。")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
