WORKFLOW_KEY = "market_state_v1"

# Node keys are semantic graph identifiers (not Python module names).
# Node modules keep infer_/assemble_ filename prefixes for intent clarity.
NODE_MAINLINE_CANDIDATES = "mainline_candidates"
NODE_ENVIRONMENT_SIGNAL = "environment_signal"
NODE_MAINLINE_CONTINUITY = "mainline_continuity"
NODE_RISK_PRESSURE = "risk_pressure"
NODE_SECTOR_COMPETITION = "sector_competition"
NODE_ASSEMBLE_EXIT_ANALYSIS = "assemble_exit_analysis"

MARKET_STATE_EXPORT_KEYS = [
    "environment_signal",
    "mainline_candidates",
    "continuity_snapshot",
    "risk_snapshot",
    "competition_snapshot",
    "exit_analysis",
]


def build_market_state_action_map():
    return {
        "绿灯": "主线健康，可继续做",
        "黄灯": "主升强化，优先做核心",
        "橙灯": "退潮预警，禁止新增",
        "红灯": "退潮确认，尽快退出",
    }


def build_market_state_severity_map():
    return {"绿灯": 0, "黄灯": 1, "橙灯": 2, "红灯": 3}
