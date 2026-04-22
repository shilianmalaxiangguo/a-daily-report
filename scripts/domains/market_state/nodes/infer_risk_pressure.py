from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers["action_map"]

    data = inputs.get("data") or {}
    tracked_sector = state.get("tracked_sector", "")
    event_status = "未发现与当前主线强相关的临近兑现事件"
    event_level = "绿灯"
    for event in data.get("calendar_events", [])[:10]:
        title = str(event.get("title", "") or "").strip()
        if not title:
            continue
        event_sector = helpers["analyze_event_sector"](
            title, "", data.get("xuangubao_data"), data.get("hot_rank_top30", [])
        )
        if tracked_sector and event_sector and (tracked_sector in event_sector or event_sector in tracked_sector):
            event_status = f"{title}进入博弈窗口，注意抢跑后兑现"
            event_level = "黄灯"
            break

    signal = {
        "layer": "事件落地风险",
        "status": event_status,
        "level": event_level,
        "action": action_map[event_level],
    }
    return {
        "value": signal,
        "exports": {"risk_signal": signal, "risk_snapshot": {"event_status": event_status, "event_level": event_level}},
        "state_patch": {
            "risk_signal": signal,
            "risk_snapshot": {"event_status": event_status, "event_level": event_level},
        },
        "module_logs": [
            make_market_state_log(
                "risk_pressure",
                "infer.risk_pressure",
                "success",
                "risk signal derived",
                tracked_sector=tracked_sector,
                level=event_level,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
