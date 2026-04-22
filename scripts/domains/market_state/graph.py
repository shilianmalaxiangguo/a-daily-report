from domains.market_state.contracts import (
    MARKET_STATE_EXPORT_KEYS,
    NODE_ASSEMBLE_EXIT_ANALYSIS,
    NODE_ENVIRONMENT_SIGNAL,
    NODE_MAINLINE_CANDIDATES,
    NODE_MAINLINE_CONTINUITY,
    NODE_RISK_PRESSURE,
    NODE_SECTOR_COMPETITION,
    WORKFLOW_KEY,
)


def build_market_state_graph():
    return {
        "workflow_key": WORKFLOW_KEY,
        "version": "1.0.0",
        "entry_nodes": [NODE_MAINLINE_CANDIDATES],
        "nodes": [
            {"key": NODE_MAINLINE_CANDIDATES, "kind": "infer"},
            {"key": NODE_ENVIRONMENT_SIGNAL, "kind": "infer"},
            {"key": NODE_MAINLINE_CONTINUITY, "kind": "infer"},
            {"key": NODE_RISK_PRESSURE, "kind": "infer"},
            {"key": NODE_SECTOR_COMPETITION, "kind": "infer"},
            {"key": NODE_ASSEMBLE_EXIT_ANALYSIS, "kind": "assemble"},
        ],
        "edges": [
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_ENVIRONMENT_SIGNAL},
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_MAINLINE_CONTINUITY},
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_RISK_PRESSURE},
            {"from": NODE_MAINLINE_CANDIDATES, "to": NODE_SECTOR_COMPETITION},
            {"from": NODE_ENVIRONMENT_SIGNAL, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
            {"from": NODE_MAINLINE_CONTINUITY, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
            {"from": NODE_RISK_PRESSURE, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
            {"from": NODE_SECTOR_COMPETITION, "to": NODE_ASSEMBLE_EXIT_ANALYSIS},
        ],
        "exports": MARKET_STATE_EXPORT_KEYS,
    }
