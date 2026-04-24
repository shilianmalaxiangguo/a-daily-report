def build_candidate_selection_conclusion_node(context, node_meta=None, node_lookup=None):
    core_stocks = context.get("core_stocks", []) or []
    secondary_stocks = context.get("secondary_stocks", []) or []
    crossline_observation_stocks = context.get("crossline_observation_stocks", []) or []
    gem_observation_stocks = context.get("gem_observation_stocks", []) or []
    ignored_stocks = context.get("ignored_stocks", []) or []
    next_stage_label = str(context.get("next_stage_label", "") or "Step 3").strip() or "Step 3"

    return {
        "lines": [
            "**结论**:",
            f"- **主线核心**: {len(core_stocks)}只（主攻线内最值得盯的可执行候选）",
            f"- **主线次核心**: {len(secondary_stocks)}只（主攻线内备选观察）",
            f"- **跨线观察**: {len(crossline_observation_stocks)}只（只看资金迁移，不代表主线切换）",
            f"- **创业板20cm预启动**: {len(gem_observation_stocks)}只（只先进观察池，等待右侧确认）",
            f"- **暂不关注**: {len(ignored_stocks)}只（预判明日强度不足）",
            f"- **接着做什么**: 进入{next_stage_label}，预判这些核心股明天有没有崩的风险",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }
