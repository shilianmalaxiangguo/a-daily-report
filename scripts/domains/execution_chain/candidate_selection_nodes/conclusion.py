def build_candidate_selection_conclusion_node(context, node_meta=None, node_lookup=None):
    core_stocks = context.get("core_stocks", []) or []
    secondary_stocks = context.get("secondary_stocks", []) or []
    crossline_observation_stocks = context.get("crossline_observation_stocks", []) or []
    gem_observation_stocks = context.get("gem_observation_stocks", []) or []
    ignored_stocks = context.get("ignored_stocks", []) or []
    next_stage_label = str(context.get("next_stage_label", "") or "Step 3").strip() or "Step 3"
    if core_stocks:
        next_action = f"进入{next_stage_label}，只把{len(core_stocks)}只主线核心送去风险复核"
    elif secondary_stocks:
        next_action = f"主线核心为0；{len(secondary_stocks)}只次核心只作观察复核，不生成执行对象"
    elif crossline_observation_stocks or gem_observation_stocks:
        next_action = "主线核心为0；跨线和创业板样本只保留观察，不进入执行筛选"
    else:
        next_action = "没有主线核心或观察样本进入下一层，后续只看市场是否重新给出对象"

    return {
        "lines": [
            "**结论**:",
            f"- **主线核心**: {len(core_stocks)}只（只有这里才可能继续进入执行筛选；为0时不产生执行对象）",
            f"- **主线次核心**: {len(secondary_stocks)}只（主线内备选观察，不直接生成执行对象）",
            f"- **跨线观察**: {len(crossline_observation_stocks)}只（只看资金迁移，不代表主线切换）",
            f"- **创业板20cm预启动**: {len(gem_observation_stocks)}只（只先进观察池，等待右侧确认）",
            f"- **暂不关注**: {len(ignored_stocks)}只（预判明日强度不足）",
            f"- **传给下一步**: {next_action}",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }
