from domains.market_state.contracts import build_market_state_action_map
from domains.market_state.trace import make_market_state_log


def run(ctx):
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = build_market_state_action_map()

    tracked_sector = state.get("tracked_sector", "")
    if not tracked_sector:
        exit_analysis = {
            "sector_name": "暂无明确主线",
            "star_level": "-",
            "leader_name": "-",
            "event_risk_summary": "无主线，无需评估事件兑现风险",
            "overall_level": "红灯",
            "overall_action": action_map["红灯"],
            "exit_conditions": ["暂无明确主线，不值得死在里面，优先空仓或等待新主线"],
            "signals": [
                {"layer": "主线地位复核", "status": "暂无明确主线", "level": "红灯", "action": "没有主线就不能参与，已有仓位也要退出"},
                {"layer": "龙头健康度", "status": "无可跟踪龙头", "level": "红灯", "action": "不能新开仓，已有仓位不做旧线自救"},
                {"layer": "板块内部结构", "status": "主线结构不存在", "level": "红灯", "action": "不参与杂毛补涨，已有仓位按退场处理"},
                {"layer": "持仓个股承接", "status": "无主线核心可跟踪", "level": "红灯", "action": "没有承接就不参与，已有仓位直接退出"},
                {"layer": "事件落地风险", "status": "无主线，无需评估事件风险", "level": "黄灯", "action": action_map["黄灯"]},
                {"layer": "替代主线流向", "status": "等待新主线承接", "level": "黄灯", "action": action_map["黄灯"]},
            ],
        }
    else:
        leader_signal = state.get("leader_signal", {})
        structure_signal = state.get("structure_signal", {})
        core_signal = state.get("core_signal", {})
        risk_signal = state.get("risk_signal", {})
        competition_signal = state.get("competition_signal", {})
        environment_signal = state.get("environment_signal", {})
        continuity_snapshot = state.get("continuity_snapshot", {})
        mainline_score_pct = float(state.get("mainline_score_pct", 0) or 0)
        overall_score = round(
            mainline_score_pct * 0.4
            + continuity_snapshot.get("leader_score", 0) * 0.2
            + continuity_snapshot.get("structure_score", 0) * 0.15
            + continuity_snapshot.get("core_score", 0) * 0.15,
            1,
        )
        overall_level = "绿灯" if overall_score >= 70 else "黄灯" if overall_score >= 50 else "橙灯"
        exit_analysis = {
            "sector_name": tracked_sector,
            "star_level": (state.get("mainline_snapshot", {}) or {}).get("star_level", "⭐"),
            "leader_name": continuity_snapshot.get("leader_name", "-"),
            "event_risk_summary": risk_signal.get("status", ""),
            "overall_level": overall_level,
            "overall_score": overall_score,
            "mainline_score_pct": round(mainline_score_pct, 1),
            "score_detail": {
                "主线": round(mainline_score_pct, 1),
                "龙头": round(float(continuity_snapshot.get("leader_score", 0) or 0), 1),
                "结构": round(float(continuity_snapshot.get("structure_score", 0) or 0), 1),
                "承接": round(float(continuity_snapshot.get("core_score", 0) or 0), 1),
                "事件": 65.0 if risk_signal.get("level") == "黄灯" else 85.0,
                "替代": 65.0 if competition_signal.get("level") == "黄灯" else 85.0,
            },
            "mainline_component_scores": (state.get("mainline_snapshot", {}) or {}).get("component_scores", {}),
            "mainline_trend_label": (state.get("mainline_snapshot", {}) or {}).get("trend_label", ""),
            "overall_action": action_map[overall_level],
            "participation_advice": {
                "绿灯": "可参与，可继续粘住最强趋势",
                "黄灯": "优先围绕主线核心，继续持有最强",
                "橙灯": "禁止新增，旧仓去弱留强，不强就卖",
                "红灯": "停止参与，已有仓位尽快退出",
            }[overall_level],
            "exit_conditions": [
                "跌破止损线（最近前低）立即卖出，不讨论",
                "买入后仅3~5个交易日观察期，走势不及预期即卖（卖出线即止损线）",
                "当日放量大阳线为理想主动卖点：他人眼中的确定性买点，本模式作减仓/清仓点",
            ],
            "price_lines": None,
            "signals": [
                environment_signal,
                leader_signal,
                structure_signal,
                core_signal,
                risk_signal,
                competition_signal,
            ],
        }

    return {
        "value": exit_analysis,
        "exports": {"exit_analysis": exit_analysis},
        "state_patch": {"exit_analysis": exit_analysis},
        "module_logs": [
            make_market_state_log(
                "assemble_exit_analysis",
                "assemble.exit_analysis",
                "success",
                "legacy exit analysis assembled",
                tracked_sector=tracked_sector or "暂无明确主线",
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
