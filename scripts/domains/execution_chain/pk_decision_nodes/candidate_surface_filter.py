def candidate_key(candidate):
    candidate = candidate or {}
    return str(
        candidate.get("code")
        or candidate.get("stock_code")
        or candidate.get("代码")
        or candidate.get("name")
        or candidate.get("名称")
        or ""
    ).strip()


def candidate_identity_keys(candidate):
    candidate = candidate or {}
    keys = set()
    for key in ("code", "stock_code", "代码", "symbol", "prod_code"):
        value = clean_text(candidate.get(key))
        if value:
            keys.add(value)
    for key in ("name", "stock_name", "名称"):
        value = clean_text(candidate.get(key))
        if value:
            keys.add(value)
    first = candidate_key(candidate)
    if first:
        keys.add(first)
    return keys


def candidate_matches_any_key(candidate, keys):
    return bool(candidate_identity_keys(candidate) & set(keys or set()))


def clean_text(value):
    return str(value or "").strip()


def anchor_reversal_payload(candidate):
    if not isinstance(candidate, dict):
        return {}
    payload = candidate.get("anchor_reversal") or candidate.get("板块锚反推") or {}
    return payload if isinstance(payload, dict) else {}


def _candidate_observation_texts(candidate):
    if not isinstance(candidate, dict):
        return []
    nested = anchor_reversal_payload(candidate)
    texts = []
    planned = {}
    for source in (candidate, nested):
        if isinstance(source.get("planned_participation"), dict):
            planned = source.get("planned_participation") or {}
        for key in (
            "candidate_role",
            "quality_role",
            "sniper_role",
            "identity",
            "target_role",
            "role",
            "status",
            "candidate_status",
            "sector_role",
            "source_pool",
            "candidate_layer",
            "observation_layer",
            "execution_eligibility",
            "final_action",
            "market_participation_qualification",
            "position_plan_pct",
        ):
            value = clean_text(source.get(key))
            if value:
                texts.append(value)
        source_pools = source.get("source_pools") or []
        if isinstance(source_pools, str):
            source_pools = [source_pools]
        if isinstance(source_pools, (list, tuple, set)):
            texts.extend(clean_text(item) for item in source_pools if clean_text(item))
    if isinstance(planned, dict):
        for key in ("action", "attack_state", "position_plan_pct", "target_position_pct"):
            value = clean_text(planned.get(key))
            if value:
                texts.append(value)
    return texts


def _process_observation_conflict(candidate):
    process_roles = {"观察样本", "跟风样本", "过程候选", "低位补涨", "套利工具", "候选观察补充"}
    texts = _candidate_observation_texts(candidate)
    if any(
        text in process_roles
        or text == "watch_sample"
        or text == "process_observation"
        or text == "过程候选"
        or text == "过程观察样本"
        or text == "过程证据"
        or text
        in {
            "anchor_reversal_observation",
            "anchor_failed_no_participation",
            "observation_only",
        }
        for text in texts
    ):
        return True
    nested = anchor_reversal_payload(candidate)
    planned = candidate.get("planned_participation") if isinstance(candidate.get("planned_participation"), dict) else {}
    if not planned and isinstance(nested.get("planned_participation"), dict):
        planned = nested.get("planned_participation") or {}
    market_qualification = clean_text(
        candidate.get("market_participation_qualification")
        or nested.get("market_participation_qualification")
    )
    planned_action = clean_text(planned.get("action"))
    if market_qualification in {"not_qualified", "不合格"} and planned_action in {"skip", "observe"}:
        return True
    return False


def candidate_blocks_current_observation_target(candidate):
    if not isinstance(candidate, dict):
        return False
    observation_layer = clean_text(
        candidate.get("observation_layer")
        or anchor_reversal_payload(candidate).get("observation_layer")
    )
    account_status = clean_text(candidate.get("account_trade_status") or candidate.get("账户状态"))
    account_reason = clean_text(
        candidate.get("account_trade_reason")
        or candidate.get("front_observation_reason")
    )
    identity = clean_text(candidate.get("identity") or candidate.get("candidate_role") or candidate.get("target_role"))
    if (
        candidate.get("front_observation_qualified") is True
        and observation_layer == "front_observation"
        and (
            account_status == "实际不可买"
            or "买不了一手" in account_reason
        )
        and identity in {"市场核心", "板块锚", "主线核心", "大容量中军"}
    ):
        return False
    if candidate.get("front_observation_qualified") is False:
        return True
    if candidate.get("front_observation_qualified") is True:
        return _process_observation_conflict(candidate)
    nested = anchor_reversal_payload(candidate)
    decision = clean_text(
        candidate.get("anchor_reversal_decision")
        or candidate.get("reversal_decision")
        or nested.get("anchor_reversal_decision")
        or nested.get("reversal_decision")
    )
    if decision in {"降级观察", "不参与", "可作为补位"}:
        return True
    return _process_observation_conflict(candidate)


def blocked_current_observation_keys(candidates):
    keys = set()
    for candidate in list(candidates or []):
        if candidate_blocks_current_observation_target(candidate):
            keys.update(candidate_identity_keys(candidate))
    return keys


def candidate_can_be_current_observation_target(candidate):
    return (
        isinstance(candidate, dict)
        and bool(candidate_key(candidate))
        and not candidate_blocks_current_observation_target(candidate)
    )
