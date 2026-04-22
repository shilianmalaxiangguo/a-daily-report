from domains.market_state.contracts import (
    NODE_ASSEMBLE_EXIT_ANALYSIS,
    NODE_ENVIRONMENT_SIGNAL,
    NODE_MAINLINE_CANDIDATES,
    NODE_MAINLINE_CONTINUITY,
    NODE_RISK_PRESSURE,
    NODE_SECTOR_COMPETITION,
)
from domains.market_state.nodes.assemble_exit_analysis import run as run_assemble_exit_analysis
from domains.market_state.nodes.infer_environment_signal import run as run_environment_signal
from domains.market_state.nodes.infer_mainline_candidates import run as run_mainline_candidates
from domains.market_state.nodes.infer_mainline_continuity import run as run_mainline_continuity
from domains.market_state.nodes.infer_risk_pressure import run as run_risk_pressure
from domains.market_state.nodes.infer_sector_competition import run as run_sector_competition


def build_market_state_registry():
    return {
        NODE_MAINLINE_CANDIDATES: run_mainline_candidates,
        NODE_ENVIRONMENT_SIGNAL: run_environment_signal,
        NODE_MAINLINE_CONTINUITY: run_mainline_continuity,
        NODE_RISK_PRESSURE: run_risk_pressure,
        NODE_SECTOR_COMPETITION: run_sector_competition,
        NODE_ASSEMBLE_EXIT_ANALYSIS: run_assemble_exit_analysis,
    }
